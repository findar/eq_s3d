"""
tests/test_room_view.py
-----------------------
Re-decorating one room of a build (decor-rules task 4, Req 4): ``generators/decor/room_view.py``
and ``POST /api/room_decor``.

- Fast, no install (Props drawn as boxes, said in the report): the route answers a report and a
  GLB the build-file route serves; a fresh decor seed changes the Props; an edited rule file
  shows on the next call (rules read fresh, no restart); a rule file that fails its check is a
  400 listing the failures; a bad zone, version or room id is a 400 or 404 and nothing is
  written outside the output root.
- With the install (``EQ_PATH``; slow): for the decor goldens' builds
  (``tests/test_decor_builds.DECORATED``), the route's Props for every room and corridor, with
  the build's own seed, level and layers, equal the sidecar's ``props`` (Req 4.2).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import server.app as app_module
from ai import schema
from generators.decor.stock import eq_path_from_env

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "rooms" / "war_city_troll.json"
ZONE = "rv_troll"
#: war_city_troll's throne room: Dressing at its POI and a dozen Props at Normal.
ROOM = "room_6"

EQ = eq_path_from_env()
needs_install = pytest.mark.skipif(EQ is None, reason="EQ_PATH is not set (no EQ install to read)")


@pytest.fixture
def out(tmp_path, monkeypatch):
    """A Server output root holding one build folder with a recorded rooms file (no sidecar,
    no ``.eqg``) and no install: the route answers boxes."""
    root = tmp_path / "web"
    build = root / ZONE / "v1"
    build.mkdir(parents=True)
    shutil.copy(FIXTURE, build / f"{ZONE}.rooms.json")
    monkeypatch.setattr(app_module, "OUTPUT_DIR", root)
    monkeypatch.setattr(app_module, "_room_eq_path", lambda: None)
    monkeypatch.setattr(app_module, "_ROOM_BUILDS", {})
    return root


@pytest.fixture
def client():
    return TestClient(app_module.app)


def _post(client, **body):
    return client.post("/api/room_decor", json={"zone": ZONE, "version": 1, "room": ROOM, **body})


def test_route_answers_the_report_and_a_served_glb(out, client):
    r = _post(client)
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["room"]["id"] == ROOM and rep["control"] == "normal" and rep["seed"] == 102
    assert rep["install"] is False and any("boxes" in n for n in rep["notes"])
    assert rep["props"], "the throne room at seed 102 holds Props"
    assert any(poi["dressing"] for poi in rep["pois"])
    for p in rep["props"]:
        assert {"line", "step", "at", "key", "kind", "category", "x", "y", "z"} <= set(p)
    for poi in rep["pois"]:
        assert {"purpose", "x", "y", "z", "dressing"} <= set(poi)
    for d in rep["drops"]:
        assert {"line", "what", "reason"} <= set(d)
    assert isinstance(rep["took_ms"], int)
    glb = client.get(rep["glb_url"])
    assert glb.status_code == 200 and glb.content[:4] == b"glTF"
    assert rep["glb_url"].startswith(f"/api/zones/{ZONE}/v1/room_{ROOM}_")
    # The same inputs give the same room (and the same file).
    assert _post(client).json()["props"] == rep["props"]


def test_a_fresh_decor_seed_changes_the_props(out, client):
    base = _post(client).json()["props"]
    others = [_post(client, decor_seed=s).json()["props"] for s in (1, 2, 3)]
    assert any(o != base for o in others)


def test_an_edited_rule_file_shows_without_a_restart(out, client, tmp_path, monkeypatch):
    rules = tmp_path / "decor"
    shutil.copytree(schema.RULES_DECOR_DIR, rules)
    monkeypatch.setattr(schema, "RULES_DECOR_DIR", rules)
    before = _post(client).json()["props"]
    assert any(p["step"] != "dressing" for p in before)
    rooms = rules / "rooms.toml"
    zero = "".join(f"{c} = 0\n" for c in ("light", "container", "furniture", "hanging", "structure",
                                           "debris", "plant", "other"))
    text = rooms.read_text(encoding="utf-8")
    assert "[weights.controls.normal]\n" in text
    rooms.write_text(text.replace("[weights.controls.normal]\n", "[weights.controls.normal]\n" + zero),
                     encoding="utf-8")
    after = _post(client).json()["props"]
    assert after != before and all(p["step"] == "dressing" for p in after)


def test_a_rule_file_that_fails_its_check_is_a_400(out, client, tmp_path, monkeypatch):
    rules = tmp_path / "decor"
    shutil.copytree(schema.RULES_DECOR_DIR, rules)
    monkeypatch.setattr(schema, "RULES_DECOR_DIR", rules)
    rooms = rules / "rooms.toml"
    rooms.write_text(rooms.read_text(encoding="utf-8").replace("bare = 0.26", 'bare = "lots"', 1),
                     encoding="utf-8")
    r = _post(client)
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["errors"] and any("rooms.toml" in e and "bare" in e for e in detail["errors"])


def test_an_unknown_layer_or_control_is_a_400(out, client):
    r = _post(client, decor_layers=["no_such_layer"])
    assert r.status_code == 400 and "no_such_layer" in r.json()["detail"]
    assert _post(client, control="lavish").status_code == 400
    assert _post(client, decor_seed=-1).status_code == 400


@pytest.mark.parametrize("body, status", [
    (dict(zone="../x"), 400),
    (dict(zone="..\\x"), 400),
    (dict(zone=f"{ZONE}\n"), 400),
    (dict(zone="C:"), 400),
    (dict(room="../../evil"), 400),
    (dict(room=".."), 400),
    (dict(version="v1/.."), 400),
    (dict(version="1"), 400),
    (dict(zone="no_such_build"), 404),
    (dict(version=2), 404),
    (dict(room="room_99"), 404),
])
def test_bad_ids_are_refused(out, client, body, status):
    before = {p for p in out.parent.rglob("*")}
    r = client.post("/api/room_decor", json={"zone": ZONE, "version": 1, "room": ROOM, **body})
    assert r.status_code == status, r.text
    assert {p for p in out.parent.rglob("*")} == before, "nothing written"


def test_a_build_without_room_contexts_is_a_404(out, client):
    (out / ZONE / "v1" / f"{ZONE}.rooms.json").unlink()
    assert _post(client).status_code == 404


# ---------------------------------------------------------------------------
# Same Props as the build (Req 4.2)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """The decor goldens' builds, made as the Server makes them (the pipeline writes the rooms
    file for the accepted build)."""
    from ai.expand import plan_to_spec
    from ai.schema import ZonePlan
    from generators.pipeline import generate_validated
    from tests.test_decor_builds import DECORATED

    root = tmp_path_factory.mktemp("rv") / "web"
    names = []
    for label, (fields, seed) in sorted(DECORATED.items()):
        plan = ZonePlan(name=f"rv_{label}", **fields).validate()
        vb = generate_validated(lambda s, rs=None, plan=plan: plan_to_spec(plan, seed=s),
                                zone_type=fields["zone_type"], zone_id=plan.name, seed=seed,
                                output_dir=root, write_glb=False, failure_log=None)
        names.append((plan.name, vb.build_dir))
    return root, names


def _same_props(client, name, build_dir, **body):
    """Every room and corridor of a build re-decorated through the route equals the sidecar's."""
    side = json.loads((build_dir / f"{name}.zone.json").read_text(encoding="utf-8"))
    want = {r["id"]: r.get("props", []) for r in side["rooms"]}
    want.update({c["id"]: c.get("props", []) for c in side.get("corridors", [])})
    assert sum(len(v) for v in want.values()) > 0
    for room_id, props in want.items():
        r = client.post("/api/room_decor", json={"zone": name, "version": 1, "room": room_id, **body})
        assert r.status_code == 200, r.text
        rep = r.json()
        assert rep["install"] is True and rep["seed"] == side["decor"]["seed"]
        assert rep["layers"] == side["decor"].get("layers", [])
        assert rep["props"] == props, f"{name} {room_id}"
    return side


@pytest.mark.slow
@needs_install
def test_the_builds_seed_gives_the_builds_props(built, client, monkeypatch):
    root, names = built
    monkeypatch.setattr(app_module, "OUTPUT_DIR", root)
    monkeypatch.setattr(app_module, "_ROOM_BUILDS", {})
    for name, build_dir in names:
        _same_props(client, name, build_dir)


THEMED_LAYER = "rv_theme_test"
THEMED_TOML = f'''
[layer]
name        = "{THEMED_LAYER}"
description = "Two more lights on every room's walls (a test layer)"

[every]
mode  = "add"
props = [ {{ kind = ["torch", "lantern", "lamp"], at = "on_wall", count = 2 }} ]
'''


@pytest.mark.slow
@needs_install
def test_a_theme_mapped_layer_gives_the_builds_props(tmp_path, client, monkeypatch):
    """A build whose theme takes a layer (``themes.toml``): the room view merges the build's
    layers, so its Props are the build's; the base alone would not give them."""
    from ai.expand import plan_to_spec
    from ai.schema import ZonePlan
    from generators.decor.room_view import decorate_room, load_build
    from generators.pipeline import generate_validated

    rules = tmp_path / "decor"
    shutil.copytree(schema.RULES_DECOR_DIR, rules)
    (rules / "layers" / f"{THEMED_LAYER}.toml").write_text(THEMED_TOML, encoding="utf-8")
    (rules / "themes.toml").write_text(f'fortress = {{ layers = ["{THEMED_LAYER}"] }}\n', encoding="utf-8")
    monkeypatch.setattr(schema, "RULES_DECOR_DIR", rules)
    root = tmp_path / "web"
    plan = ZonePlan(name="rv_fortress", zone_type="dungeon", dungeon_theme="fortress").validate()
    vb = generate_validated(lambda s, rs=None: plan_to_spec(plan, seed=s), zone_type="dungeon",
                            zone_id=plan.name, seed=4, output_dir=root, write_glb=False, failure_log=None)
    monkeypatch.setattr(app_module, "OUTPUT_DIR", root)
    monkeypatch.setattr(app_module, "_ROOM_BUILDS", {})
    side = _same_props(client, plan.name, vb.build_dir)
    assert side["decor"]["layers"] == [THEMED_LAYER]
    # ``decor_layers: []`` is the theme's alone: the same layers, the same Props.
    _same_props(client, plan.name, vb.build_dir, decor_layers=[])
    # The base alone gives other Props: the layer is what makes them match.
    b = load_build(vb.build_dir, plan.name)
    base = [decorate_room(b.contexts, c.id, seed=b.seed, control=b.control, layers=(), eq_path=EQ,
                          mesh=b.mesh)[1]["props"] for c in b.contexts if c.source == "room"]
    want = [r.get("props", []) for r in side["rooms"]]
    assert base != want
