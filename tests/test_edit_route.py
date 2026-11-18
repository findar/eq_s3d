"""
tests/test_edit_route.py
------------------------
The edit route (zone-generator-edits Req 3, task 4): ``POST /api/edit`` with feedback text or
ops makes the next version of a zone, with step 16's ``version`` block and an ``edit`` block in
its sidecar, and ``GET /api/zones/<zone>/versions`` shows the edit. Every ``applied: false``
answer leaves the zone folder byte-identical; a partial edit equals a full build of the edited
spec (and one whose saved stages are stale is built in full); an edit that draws seeds tries
up to five candidates and a deterministic one exactly one; a second edit while one builds is a
429. Also the CLI's ``--edit``. Built ``.eqg`` files hold the client's art: they live in
``tmp_path`` only.
"""

from __future__ import annotations

import hashlib
import json
import threading

import pytest
from fastapi.testclient import TestClient

import generators.builder as builder_mod
import generators.rebuild as rebuild_mod
import main as main_mod
import server.app as app_mod
from ai.edits import HELP, RuleEditInterpreter
from generators.decor.stock import eq_path_from_env
from generators.pipeline import AttemptFailure, GenerationFailed, generate_validated

pytestmark = pytest.mark.skipif(eq_path_from_env() is None,
                                reason="EQ_PATH is not set (no EQ install to read)")

#: A small decorated dungeon that passes the gate on its pinned seed (as test_versions').
CONTROLS = {"zone_type": "dungeon", "room_count": 5}
SEED = 4


def _dir(root, zone, n):
    return root / zone / f"v{n}"


def _json(root, zone, n, ext):
    return json.loads((_dir(root, zone, n) / f"{zone}.{ext}.json").read_text(encoding="utf-8"))


def _eqg(root, zone, n):
    return (_dir(root, zone, n) / f"{zone}.eqg").read_bytes()[:-4]


def _hashes(folder):
    """Every file under ``folder`` by relative path, with its bytes' hash."""
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    """The Server writing into its own output folder, with the rule interpreter (whatever keys
    the machine has) and one controls-mode v1."""
    mp = pytest.MonkeyPatch()
    root = tmp_path_factory.mktemp("edits") / "web"
    root.mkdir()
    mp.setattr(app_mod, "OUTPUT_DIR", root)
    mp.setattr(app_mod, "FAILURE_LOG", root.parent / "failures.jsonl")
    mp.setattr(app_mod, "get_edit_interpreter", RuleEditInterpreter)
    client = TestClient(app_mod.app)
    r = client.post("/api/generate", json={"controls": CONTROLS, "seed": SEED})
    assert r.status_code == 200, r.text
    yield client, root, r.json()["id"]
    mp.undo()


def _rooms(root, zone, n=1):
    return _json(root, zone, n, "spec")["rooms"]


def _plain_room(root, zone):
    """A room that isn't the entrance, and a room type it isn't."""
    room = next(r for r in _rooms(root, zone) if r.get("role") != "entrance")
    return room["id"], "forge" if room.get("semantic_type") != "forge" else "vault"


def _full_build_of_spec(root, zone, n, tmp_path):
    """Version ``n``'s ``spec.json`` built in full (no saved stages) in another folder."""
    other = tmp_path / "ref"
    other.mkdir()
    build_spec_doc = _json(root, zone, n, "spec")
    rebuild_mod.build_spec(_dir(root, zone, n), build_spec_doc, zone_id=zone, stages=False,
                           generate=generate_validated, zone_type="dungeon", version=1,
                           output_dir=other, failure_log=other / "failures.jsonl")
    return other


def test_text_edit_is_the_next_version_with_its_edit_block(server):
    client, root, zone = server
    r = client.post("/api/edit", json={"zone": zone, "version": 1, "text": "much less decor"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["applied"] is True and body["interpreter"] == "rule"
    n = body["version"]
    assert n >= 2 and body["parent"] == 1 and body["how"] == "partial"
    assert body["ops"] and body["ops"][0]["op"] == "set_decor_level"
    rooms = [x["id"] for x in _rooms(root, zone)]
    assert body["affected"] == {"rooms": rooms, "corridors": []}
    block = {"n": n, "parent": 1, "changed": ["decor"], "how": "partial"}
    assert body["build"]["version_info"] == block
    assert body["build"]["glb_url"] == f"/api/zones/{zone}/v{n}/{zone}.glb"
    side = _json(root, zone, n, "zone")
    assert side["version"] == block
    assert side["edit"] == {"text": "much less decor", "ops": body["ops"], "interpreter": "rule",
                            "notes": body["notes"], "affected": body["affected"]}
    assert _json(root, zone, n, "spec")["decor"] == body["ops"][0]["level"]
    assert _json(root, zone, n, "request")["controls"]["decor"] == body["ops"][0]["level"]

    listing = {v["n"]: v for v in client.get(f"/api/zones/{zone}/versions").json()["versions"]}
    assert listing[1]["edit"] is None
    assert listing[n]["edit"] == {"text": "much less decor", "ops": body["ops"]}
    assert (listing[n]["parent"], listing[n]["how"]) == (1, "partial")


@pytest.mark.parametrize("fault", [None, "stale"])
def test_ops_edit_equals_a_full_build_of_the_edited_spec(server, fault, monkeypatch, tmp_path):
    """A partial edit builds from the parent's stages; stale stages are built in full
    (decision 4); either way the ``.eqg`` equals a full build of the version's spec."""
    client, root, zone = server
    room, kind = _plain_room(root, zone)
    if fault == "stale":
        monkeypatch.setattr(rebuild_mod, "saved_stages",
                            lambda *_a: builder_mod.SavedStages(b"not this ter", {}, {}))
    r = client.post("/api/edit", json={"zone": zone, "version": "v1",
                                       "ops": [{"op": "set_purpose", "target": room, "type": kind}]})
    assert r.status_code == 200, r.text
    body = r.json()
    n = body["version"]
    how = "full" if fault else "partial"
    assert body["applied"] is True and body["how"] == how and body["interpreter"] is None
    assert body["affected"] == {"rooms": [room], "corridors": []}
    side = _json(root, zone, n, "zone")
    assert side["version"] == {"n": n, "parent": 1, "changed": ["semantic_type"], "how": how}
    assert side["edit"]["text"] is None and side["edit"]["ops"] == body["ops"]
    spec = _json(root, zone, n, "spec")
    assert next(x for x in spec["rooms"] if x["id"] == room)["semantic_type"] == kind
    monkeypatch.undo()
    ref = _full_build_of_spec(root, zone, n, tmp_path)
    assert _eqg(root, zone, n) == _eqg(ref, zone, 1)


def test_regenerate_plans_again_at_the_new_seed(server):
    client, root, zone = server
    r = client.post("/api/edit", json={"zone": zone, "version": 1,
                                       "ops": [{"op": "regenerate", "seed": SEED + 1},
                                               {"op": "reroll_decor"}]})
    assert r.status_code == 200, r.text
    body = r.json()
    n = body["version"]
    assert body["applied"] and body["how"] == "full"
    assert body["ops"] == [{"op": "regenerate", "seed": SEED + 1}]
    assert any("skipped" in note for note in body["notes"])
    side = _json(root, zone, n, "zone")
    assert side["version"]["changed"] == ["seed"] and side["seed"] == SEED + 1
    saved = _json(root, zone, n, "request")
    assert saved["seed"] == SEED + 1 and saved["controls"] == CONTROLS


@pytest.mark.parametrize("body, field", [
    ({"text": ""}, "help"),
    ({"text": "   \n\t"}, "help"),
    ({"text": "zzz qqq"}, "help"),
    ({"ops": []}, "help"),
    ({"ops": [{"op": "bogus"}]}, "invalid"),
    ({"ops": [{"op": "set_decor_level"}]}, "invalid"),
    ({"ops": [{"op": "reroll_room", "target": "no_such_room"}]}, "rejected"),
    ({"ops": [{"op": "add_lock", "target": "ENTRANCE"}]}, "rejected"),
    ({"ops": [{"op": "add_room"}]}, "rejected"),
])
def test_not_applied_changes_nothing(server, body, field):
    client, root, zone = server
    if body.get("ops") and isinstance(body["ops"], list) and body["ops"][0].get("target") == "ENTRANCE":
        entrance = next(x["id"] for x in _rooms(root, zone) if x.get("role") == "entrance")
        body = {"ops": [{"op": "add_lock", "target": entrance}]}
    before = _hashes(root)
    r = client.post("/api/edit", json={"zone": zone, "version": 1, **body})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["applied"] is False and out["version"] is None and out["build"] is None
    assert out[field], out
    if field == "help":
        assert out["help"] == HELP
    else:
        assert out["help"] is None and out["notes"]
    assert _hashes(root) == before


@pytest.mark.parametrize("ops, candidates", [
    ([{"op": "reroll_decor"}], 5),           # draws a seed: the next seed each time
    ([{"op": "set_decor_level", "level": "dense"}], 1),
])
def test_a_gate_failure_is_reported_and_changes_nothing(server, monkeypatch, ops, candidates):
    client, root, zone = server
    calls = []

    def fails(*_a, **k):
        calls.append(k.get("seed"))
        raise GenerationFailed(k["zone_id"], k["zone_type"], [AttemptFailure(
            seed=k["seed"], attempt=1, reachable_rooms=2, total_rooms=5,
            reasons=["room_3: unreachable"], checks=["traversability"])], pinned=True)

    monkeypatch.setattr(app_mod, "generate_validated", fails)
    before = _hashes(root)
    r = client.post("/api/edit", json={"zone": zone, "version": 1, "ops": ops, "seed": 77})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["applied"] is False and len(out["diagnostics"]) == candidates == len(calls)
    assert out["diagnostics"][0]["checks"] == ["traversability"]
    assert out["diagnostics"][0]["reasons"] == ["room_3: unreachable"]
    assert _hashes(root) == before
    nxt = max(app_mod._version_dirs(root / zone)) + 1
    assert app_mod._take_version(zone, root / zone) == nxt      # the number was given back
    app_mod._release_version(zone, nxt)


def test_a_second_edit_while_one_builds_is_a_429(server, monkeypatch):
    client, root, zone = server
    real = app_mod.generate_validated
    started, release = threading.Event(), threading.Event()

    def slow(*a, **k):
        started.set()
        assert release.wait(120)
        return real(*a, **k)

    monkeypatch.setattr(app_mod, "generate_validated", slow)
    results = {}

    def first():
        results["first"] = client.post("/api/edit", json={"zone": zone, "version": 1,
                                                          "text": "less decor"})

    t = threading.Thread(target=first)
    t.start()
    try:
        assert started.wait(120)
        before = _hashes(root / zone)
        second = client.post("/api/edit", json={"zone": zone, "version": 1, "text": "more decor"})
        assert second.status_code == 429, second.text
        rebuild = client.post("/api/rebuild", json={"zone": zone, "version": 1, "decor_seed": 31})
        assert rebuild.status_code == 429, rebuild.text
        assert _hashes(root / zone) == before
    finally:
        release.set()
        t.join()
    assert results["first"].status_code == 200 and results["first"].json()["applied"]


@pytest.mark.parametrize("body, status", [
    ({"version": 1}, 400),                                      # neither text nor ops
    ({"version": 1, "text": "less decor", "ops": []}, 400),     # both
    ({"version": 1, "text": 5}, 400),
    ({"version": 1, "ops": "less decor"}, 400),
    ({"version": 1, "text": "less decor", "seed": -1}, 400),
    ({"version": "1", "text": "less decor"}, 400),
    ({"version": "v1\n", "text": "less decor"}, 400),
    ({"version": 99, "text": "less decor"}, 404),
    ({"zone": "gen_nope", "version": 1, "text": "less decor"}, 404),
    ({"zone": "..", "version": 1, "text": "less decor"}, 400),
    ({"zone": "gen_x\n", "version": 1, "text": "less decor"}, 400),
])
def test_bad_edits(server, body, status):
    client, root, zone = server
    before = _hashes(root)
    r = client.post("/api/edit", json={"zone": zone, **body})
    assert r.status_code == status, r.text
    assert _hashes(root) == before


def test_cli_edit_takes_the_same_path(server, capsys):
    _client, root, zone = server
    main_mod.main(["--edit", zone, "1", "more decor"])
    out = capsys.readouterr().out
    n = max(app_mod._version_dirs(root / zone))
    assert f"v{n}" in out and "set_decor_level" in out
    assert _json(root, zone, n, "zone")["edit"]["text"] == "more decor"

    before = _hashes(root)
    with pytest.raises(SystemExit) as exc:
        main_mod.main(["--edit", zone, "v1", "zzz qqq"])
    assert exc.value.code == 1 and _hashes(root) == before
    with pytest.raises(SystemExit) as exc:
        main_mod.main(["--edit", "gen_nope", "1", "less decor"])
    assert exc.value.code == 2
