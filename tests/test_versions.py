"""
tests/test_versions.py
----------------------
Versions of one zone (partial-rebuild Reqs 1, 2.1, 2.2, task 2): every Server build saves
``<name>.request.json`` and ``<name>.spec.json``; ``POST /api/rebuild`` builds the next
version of the same zone from a version's saved request, and its ``.eqg`` equals a Generate
of that request with the new seed (footer aside: the PFS footer holds the write time);
``GET /api/zones/<zone>/versions`` lists them; bad bodies are 400s and unknown zones or
versions 404s; two rebuilds at once take two numbers; a failed one writes nothing.
"""

from __future__ import annotations

import json
import threading

import pytest
from fastapi.testclient import TestClient

import server.app as app_mod
from generators.pipeline import GenerationFailed
from generators.zone_spec import ZoneSpec

#: A small decorated dungeon that passes the gate on its pinned seed, with every decor
#: and rooms seed tried here (a pinned rebuild that fails the gate is a 503).
CONTROLS = {"zone_type": "dungeon", "room_count": 5}
SEED = 4
PROMPT = "a dark dungeon with a few rooms"


def _files(root, zone, n):
    return root / zone / f"v{n}"


def _sidecar(root, zone, n):
    return json.loads((_files(root, zone, n) / f"{zone}.zone.json").read_text(encoding="utf-8"))


def _eqg(root, zone, n):
    return (_files(root, zone, n) / f"{zone}.eqg").read_bytes()[:-4]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    """The Server writing into its own output folder, with one controls-mode v1 and one
    prompt-mode v1 built."""
    mp = pytest.MonkeyPatch()
    root = tmp_path_factory.mktemp("versions") / "web"
    root.mkdir()
    mp.setattr(app_mod, "OUTPUT_DIR", root)
    mp.setattr(app_mod, "FAILURE_LOG", root.parent / "failures.jsonl")
    client = TestClient(app_mod.app)
    r = client.post("/api/generate", json={"controls": CONTROLS, "seed": SEED})
    assert r.status_code == 200, r.text
    p = client.post("/api/generate", json={"prompt": PROMPT, "seed": SEED})
    assert p.status_code == 200, p.text
    yield client, root, r.json()["id"], p.json()["id"]
    mp.undo()


def _reference(client, monkeypatch, tmp_path, zone, body):
    """A Generate of ``body`` under the same zone id in another output folder."""
    other = tmp_path / "ref"
    other.mkdir()
    monkeypatch.setattr(app_mod, "OUTPUT_DIR", other)
    monkeypatch.setattr(app_mod, "new_zone_id", lambda: zone)
    r = client.post("/api/generate", json=body)
    assert r.status_code == 200, r.text
    return other


def test_v1_saves_its_inputs_and_has_no_version_block(server):
    _client, root, zone, _ = server
    v1 = _files(root, zone, 1)
    assert "version" not in _sidecar(root, zone, 1)
    saved = json.loads((v1 / f"{zone}.request.json").read_text(encoding="utf-8"))
    assert saved["mode"] == "controls" and saved["controls"] == CONTROLS
    assert saved["seed"] == SEED and saved["seeds"] == _sidecar(root, zone, 1)["seeds"]
    assert saved["plan"]["name"] == zone and isinstance(saved["took_ms"], int)
    spec = json.loads((v1 / f"{zone}.spec.json").read_text(encoding="utf-8"))
    assert spec.pop("decor_layers") == []
    assert json.loads(json.dumps(ZoneSpec.from_dict(spec).to_dict())) == spec


@pytest.mark.parametrize("change", [{"decor_seed": 11}, {"rooms_seed": 21}])
def test_rebuild_is_the_next_version_and_equals_a_generate(server, change, monkeypatch, tmp_path):
    client, root, zone, _ = server
    r = client.post("/api/rebuild", json={"zone": zone, "version": 1, **change})
    assert r.status_code == 200, r.text
    body = r.json()
    n = body["version"]
    assert n >= 2 and body["id"] == zone and body["glb_url"] == f"/api/zones/{zone}/v{n}/{zone}.glb"
    (key, value), = change.items()
    block = {"n": n, "parent": 1, "changed": [key], "how": "full" if key == "rooms_seed" else "partial"}
    assert body["version_info"] == block
    side = _sidecar(root, zone, n)
    assert side["version"] == block and side["seeds"][key] == value

    ref = _reference(client, monkeypatch, tmp_path, zone,
                     {"controls": CONTROLS, "seed": SEED, **change})
    assert _eqg(root, zone, n) == _eqg(ref, zone, 1)
    ref_side = _sidecar(ref, zone, 1)
    assert {k: v for k, v in side.items() if k != "version"} == ref_side


def test_prompt_rebuild_takes_the_saved_plan(server, monkeypatch, tmp_path):
    client, root, _, zone = server

    def no_planner(*_a, **_k):
        raise AssertionError("a rebuild called the planner")

    with monkeypatch.context() as m:
        m.setattr(app_mod, "make_plan", no_planner)
        r = client.post("/api/rebuild", json={"zone": zone, "version": "v1", "decor_seed": 12})
    assert r.status_code == 200, r.text
    n = r.json()["version"]
    assert r.json()["plan"]["decor_seed"] == 12
    ref = _reference(client, monkeypatch, tmp_path, zone,
                     {"prompt": PROMPT, "seed": SEED, "decor_seed": 12})
    assert _eqg(root, zone, n) == _eqg(ref, zone, 1)


def test_a_rebuild_of_a_rebuild_keeps_its_seeds(server):
    """v<n> from a decor rebuild, rebuilt with a rooms seed, keeps that decor seed."""
    client, root, zone, _ = server
    a = client.post("/api/rebuild", json={"zone": zone, "version": 1, "decor_seed": 13}).json()
    b = client.post("/api/rebuild", json={"zone": zone, "version": a["version"], "rooms_seed": 22})
    assert b.status_code == 200, b.text
    b = b.json()
    assert b["version_info"] == {"n": b["version"], "parent": a["version"],
                                 "changed": ["rooms_seed"], "how": "full"}
    assert _sidecar(root, zone, b["version"])["seeds"] == {
        "seed": SEED, "rooms_seed": 22, "decor_seed": 13}


def test_versions_lists_every_version(server):
    client, root, zone, _ = server
    if not (root / zone / "v2").is_dir():
        assert client.post("/api/rebuild", json={"zone": zone, "version": 1,
                                                 "decor_seed": 11}).status_code == 200
    r = client.get(f"/api/zones/{zone}/versions")
    assert r.status_code == 200, r.text
    versions = r.json()["versions"]
    on_disk = sorted(int(d.name[1:]) for d in (root / zone).iterdir())
    assert [v["n"] for v in versions] == on_disk
    v1, v2 = versions[0], versions[1]
    assert (v1["parent"], v1["changed"], v1["how"]) == (None, [], None)
    assert v2["parent"] is not None and v2["how"] == "partial" and v2["changed"]
    for v in versions:
        assert isinstance(v["took_ms"], int) and v["created"]
        assert v["eqg_url"] == f"/api/zones/{zone}/v{v['n']}/{zone}.eqg"
        assert client.head(v["eqg_url"]).status_code == 200


@pytest.mark.parametrize("body, status", [
    ({"version": 1}, 400),                                      # names no change
    ({"version": 1, "decor_seed": SEED}, 400),                  # the seed it already has
    ({"version": 1, "decor_seed": -1}, 400),
    ({"version": 1, "decor_seed": "7"}, 400),
    ({"version": 1, "decor_seed": True}, 400),
    ({"version": "1", "decor_seed": 7}, 400),
    ({"version": "v1\n", "decor_seed": 7}, 400),
    ({"version": "../v1", "decor_seed": 7}, 400),
    ({"version": 0, "decor_seed": 7}, 400),
    ({"version": 99, "decor_seed": 7}, 404),
    ({"zone": "gen_nope", "version": 1, "decor_seed": 7}, 404),
    ({"zone": "..", "version": 1, "decor_seed": 7}, 400),
    ({"zone": "a/b", "version": 1, "decor_seed": 7}, 400),
    ({"zone": "gen_x\n", "version": 1, "decor_seed": 7}, 400),
    ({"zone": 5, "version": 1, "decor_seed": 7}, 400),
])
def test_bad_rebuilds(server, body, status):
    client, root, zone, _ = server
    before = sorted(p.name for p in root.rglob("*"))
    r = client.post("/api/rebuild", json={"zone": zone, **body})
    assert r.status_code == status, r.text
    assert sorted(p.name for p in root.rglob("*")) == before


def test_versions_of_unknown_or_bad_zones(server):
    client, _root, _, _ = server
    assert client.get("/api/zones/gen_nope/versions").status_code == 404
    assert client.get("/api/zones/../versions").status_code in (400, 404)
    assert client.get("/api/zones/a%0A/versions").status_code == 400


def test_a_version_without_a_saved_request_is_404(server, tmp_path):
    client, root, zone, _ = server
    old = root / "gen_old" / "v1"
    old.mkdir(parents=True)
    for f in _files(root, zone, 1).iterdir():
        if f.is_file() and not f.name.endswith(".request.json"):
            (old / f.name.replace(zone, "gen_old")).write_bytes(f.read_bytes())
    r = client.post("/api/rebuild", json={"zone": "gen_old", "version": 1, "decor_seed": 7})
    assert r.status_code == 404 and "saved request" in r.text


def test_two_rebuilds_at_once_take_two_numbers(server, monkeypatch):
    """Both rebuilds hold their numbers before either finishes (a barrier in the build)."""
    client, root, zone, _ = server
    real = app_mod.generate_validated
    barrier = threading.Barrier(2, timeout=60)

    def gated(*a, **k):
        barrier.wait()
        return real(*a, **k)

    monkeypatch.setattr(app_mod, "generate_validated", gated)
    results = {}

    def run(seed):
        results[seed] = client.post("/api/rebuild", json={"zone": zone, "version": 1,
                                                          "decor_seed": seed})

    threads = [threading.Thread(target=run, args=(s,)) for s in (11, 12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(r.status_code == 200 for r in results.values()), [r.text for r in results.values()]
    numbers = {r.json()["version"] for r in results.values()}
    assert len(numbers) == 2
    for seed, r in results.items():
        assert _sidecar(root, zone, r.json()["version"])["seeds"]["decor_seed"] == seed
    assert not (root / ".attempts").exists()


def test_a_failed_rebuild_writes_nothing(server, monkeypatch):
    client, root, zone, _ = server

    def fails(*_a, **k):
        raise GenerationFailed(k["zone_id"], k["zone_type"], [], pinned=True)

    before = sorted(p.name for p in (root / zone).iterdir())
    with monkeypatch.context() as m:
        m.setattr(app_mod, "generate_validated", fails)
        r = client.post("/api/rebuild", json={"zone": zone, "version": 1, "decor_seed": 7})
    assert r.status_code == 503
    assert sorted(p.name for p in (root / zone).iterdir()) == before
    nxt = max(int(n[1:]) for n in before) + 1
    assert app_mod._take_version(zone, root / zone) == nxt     # the number was given back
    app_mod._release_version(zone, nxt)
