"""
tests/test_partial_rebuild.py
-----------------------------
Partial rebuilds (partial-rebuild Reqs 2.2, 2.3, 4.1, task 3): ``POST /api/rebuild`` with a
new ``decor_seed`` or one ``room_decor`` builds the next version from the parent's saved spec,
TER and textures (``generators.rebuild``), and the result equals a full Generate of the new
version's own ``request.json``: the ``.eqg`` byte for byte (footer aside: the PFS footer holds
the write time) and the sidecar but for its ``version`` block, for every zone type that takes
Decor. The rebuild never plans the zone or draws a texture (both are made to raise), so the
equality also proves the reused DDS are the ones a build draws.

Also: bad ``room_decor`` bodies, a gate failure on the pinned decor seed (one attempt, a 503,
no version folder), a parent whose stages are missing or stale (the full path), and the room
view's "As built" taking a room's own decor seed. Built ``.eqg`` files hold the client's art:
they live in ``tmp_path`` only.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import generators.builder as builder_mod
import generators.pipeline as pipeline_mod
import generators.rebuild as rebuild_mod
import server.app as app_mod
from generators.decor.stock import eq_path_from_env

pytestmark = [pytest.mark.slow,
              pytest.mark.skipif(eq_path_from_env() is None,
                                 reason="EQ_PATH is not set (no EQ install to read)")]

#: label -> (controls, seed): pinned builds whose rebuilds below pass the gate.
CASES = {
    "graph16": ({"zone_type": "dungeon", "room_count": 16, "layout": "graph"}, 2),
    "city": ({"zone_type": "city"}, 5),
    "outdoor_dungeon": ({"zone_type": "outdoor_dungeon", "room_count": 5}, 2),
    "tomb": ({"zone_type": "dungeon", "dungeon_theme": "tomb"}, 4),
    "wilderness": ({"zone_type": "wilderness", "sites": "normal"}, 4),
}
DECOR_SEED = 11
ROOM_SEED = 123457


def _dir(root, zone, n):
    return root / zone / f"v{n}"


def _json(root, zone, n, ext):
    return json.loads((_dir(root, zone, n) / f"{zone}.{ext}.json").read_text(encoding="utf-8"))


def _eqg(root, zone, n):
    return (_dir(root, zone, n) / f"{zone}.eqg").read_bytes()[:-4]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    """The Server writing into its own output folder, and a v1 per case, built once."""
    mp = pytest.MonkeyPatch()
    root = tmp_path_factory.mktemp("partial") / "web"
    root.mkdir()
    mp.setattr(app_mod, "OUTPUT_DIR", root)
    mp.setattr(app_mod, "FAILURE_LOG", root.parent / "failures.jsonl")
    client = TestClient(app_mod.app)
    zones = {}

    def v1(label):
        if label not in zones:
            controls, seed = CASES[label]
            r = client.post("/api/generate", json={"controls": controls, "seed": seed})
            assert r.status_code == 200, r.text
            zones[label] = r.json()["id"]
        return zones[label]

    yield client, root, v1
    mp.undo()


def _dressed_room(root, zone, n=1):
    """A room of version ``n`` that has Props (not left bare)."""
    rooms = _json(root, zone, n, "zone")["rooms"]
    return next(r["id"] for r in rooms if r.get("props") and not r.get("bare"))


def _no_planning_or_drawing(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("a partial rebuild planned the zone or drew a texture")
    monkeypatch.setattr(app_mod, "plan_to_spec", boom)
    monkeypatch.setattr(builder_mod, "texture_with_mode", boom)


def _rebuild(client, monkeypatch, body):
    with monkeypatch.context() as m:
        _no_planning_or_drawing(m)
        return client.post("/api/rebuild", json=body)


def _generate_saved(client, monkeypatch, tmp_path, zone, saved):
    """A Generate of a version's ``request.json`` under the same zone id in another folder."""
    other = tmp_path / "ref"
    other.mkdir()
    monkeypatch.setattr(app_mod, "OUTPUT_DIR", other)
    monkeypatch.setattr(app_mod, "new_zone_id", lambda: zone)
    r = client.post("/api/generate", json=saved)
    assert r.status_code == 200, r.text
    return other


@pytest.mark.parametrize("change", ["decor_seed", "room_decor"])
@pytest.mark.parametrize("label", list(CASES))
def test_partial_rebuild_equals_a_full_generate(server, label, change, monkeypatch, tmp_path):
    client, root, v1 = server
    zone = v1(label)
    if change == "decor_seed":
        body, changed = {"decor_seed": DECOR_SEED}, ["decor_seed"]
    elif label == "wilderness":
        # Only rooms take a room decor seed (decision 6); a wilderness has none.
        r = client.post("/api/rebuild", json={"zone": zone, "version": 1,
                                              "room_decor": {"room": "room_0", "decor_seed": 7}})
        assert r.status_code == 404, r.text
        return
    else:
        room = _dressed_room(root, zone)
        body = {"room_decor": {"room": room, "decor_seed": ROOM_SEED}}
        changed = ["room_decor_seeds"]

    r = _rebuild(client, monkeypatch, {"zone": zone, "version": 1, **body})
    assert r.status_code == 200, r.text
    n = r.json()["version"]
    block = {"n": n, "parent": 1, "changed": changed, "how": "partial"}
    assert r.json()["version_info"] == block
    side = _json(root, zone, n, "zone")
    assert side["version"] == block
    saved = _json(root, zone, n, "request")
    if change == "decor_seed":
        assert saved["decor_seed"] == DECOR_SEED and side["seeds"]["decor_seed"] == DECOR_SEED
    else:
        assert saved["controls"]["room_decor_seeds"] == {room: ROOM_SEED}
        assert side["seeds"]["room_decor_seeds"] == {room: ROOM_SEED}
        assert next(x for x in side["rooms"] if x["id"] == room)["decor_seed"] == ROOM_SEED
    assert _eqg(root, zone, n) != _eqg(root, zone, 1)        # the Props did change

    ref = _generate_saved(client, monkeypatch, tmp_path, zone, saved)
    assert _eqg(root, zone, n) == _eqg(ref, zone, 1)
    assert {k: v for k, v in side.items() if k != "version"} == _json(ref, zone, 1, "zone")


@pytest.mark.parametrize("room_decor, extra, status", [
    ({"room": "nope", "decor_seed": 7}, {}, 404),
    ({"room": "../x", "decor_seed": 7}, {}, 400),
    ({"room": "room_0\n", "decor_seed": 7}, {}, 400),
    ({"room": "room_0", "decor_seed": -1}, {}, 400),
    ({"room": "room_0", "decor_seed": "7"}, {}, 400),
    ({"room": "room_0"}, {}, 400),
    ({"room": "room_0", "decor_seed": 7, "x": 1}, {}, 400),
    ({"room": "room_0", "decor_seed": 7}, {"rooms_seed": 9}, 400),
])
def test_bad_room_decor_bodies(server, room_decor, extra, status):
    client, root, v1 = server
    zone = v1("city")
    before = sorted(p.name for p in root.rglob("*"))
    r = client.post("/api/rebuild", json={"zone": zone, "version": 1,
                                          "room_decor": room_decor, **extra})
    assert r.status_code == status, r.text
    assert sorted(p.name for p in root.rglob("*")) == before


def test_a_gate_failure_on_the_pinned_decor_seed_is_reported(server, monkeypatch):
    """One attempt (never a reroll), a 503, and no version folder."""
    client, root, v1 = server
    zone = v1("city")
    builds = []
    real_build = builder_mod.ZoneBuilder.build

    def counted(self, *a, **k):
        builds.append(k.get("saved"))
        return real_build(self, *a, **k)

    def failing(eqg_path, spec, agent):
        return pipeline_mod._plan_failure_report(spec.name, ValueError("forced"))

    before = sorted(p.name for p in (root / zone).iterdir())
    monkeypatch.setattr(builder_mod.ZoneBuilder, "build", counted)
    monkeypatch.setattr(pipeline_mod, "_traversal_report", failing)
    r = client.post("/api/rebuild", json={"zone": zone, "version": 1, "decor_seed": 99})
    assert r.status_code == 503, r.text
    assert len(builds) == 1 and builds[0] is not None
    assert sorted(p.name for p in (root / zone).iterdir()) == before
    assert not (root / ".attempts").exists()


@pytest.mark.parametrize("fault", ["missing", "stale"])
def test_missing_or_stale_stages_take_the_full_path(server, monkeypatch, fault):
    client, root, v1 = server
    zone = v1("city")

    def stages(parent_dir, name):
        if fault == "missing":
            raise rebuild_mod.NoSavedStages("gone")
        return builder_mod.SavedStages(b"not this ter", {}, {})

    monkeypatch.setattr(rebuild_mod, "saved_stages", stages)
    r = client.post("/api/rebuild", json={"zone": zone, "version": 1, "decor_seed": 12})
    assert r.status_code == 200, r.text
    n = r.json()["version"]
    assert r.json()["version_info"]["how"] == "full"
    assert _json(root, zone, n, "zone")["version"]["how"] == "full"


def test_room_seeds_through_versions_and_the_room_view(server, monkeypatch):
    """Use in zone keeps a room's seed; the room view's As built takes it; a new decor seed
    clears it (and says so)."""
    client, root, v1 = server
    zone = v1("city")
    room = _dressed_room(root, zone)
    a = _rebuild(client, monkeypatch, {"zone": zone, "version": 1,
                                       "room_decor": {"room": room, "decor_seed": ROOM_SEED}})
    assert a.status_code == 200, a.text
    n = a.json()["version"]
    zone_decor = _json(root, zone, 1, "zone")["seeds"]["decor_seed"]

    view = client.post("/api/room_decor", json={"zone": zone, "version": n, "room": room})
    assert view.status_code == 200, view.text
    rep = view.json()
    assert (rep["seed"], rep["room_seed"], rep["zone_seed"]) == (ROOM_SEED, ROOM_SEED, zone_decor)
    built = next(x for x in _json(root, zone, n, "zone")["rooms"] if x["id"] == room)
    assert len(rep["props"]) == len(built["props"])

    reroll = client.post("/api/room_decor", json={"zone": zone, "version": 1, "room": room,
                                                  "decor_seed": 5})
    assert reroll.status_code == 200, reroll.text
    assert (reroll.json()["seed"], reroll.json()["zone_seed"]) == (5, zone_decor)

    same = client.post("/api/rebuild", json={"zone": zone, "version": n,
                                             "room_decor": {"room": room, "decor_seed": ROOM_SEED}})
    assert same.status_code == 400, same.text                   # nothing changes

    b = _rebuild(client, monkeypatch, {"zone": zone, "version": n, "decor_seed": DECOR_SEED + 1})
    assert b.status_code == 200, b.text
    m = b.json()["version"]
    assert b.json()["version_info"]["changed"] == ["decor_seed", "room_decor_seeds"]
    assert "room_decor_seeds" not in _json(root, zone, m, "request")["controls"]
    assert "room_decor_seeds" not in _json(root, zone, m, "zone")["seeds"]
