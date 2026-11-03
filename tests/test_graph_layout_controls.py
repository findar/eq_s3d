"""Graph-layout task 10: ``--layout`` / ``--rule-set`` on the CLI, ``layout`` /
``rule_set`` in the server's controls, and the outdoor dungeon laying out
with the engine they pick (Req 7.1, 6.6)."""

import json
import tempfile

import pytest
from fastapi.testclient import TestClient

import main
import server.app as app_mod
from ai.expand import plan_to_spec
from ai.rule_planner import RulePlanner
from ai.schema import ZonePlan, available_rule_sets
import generators.outdoor_dungeon as od

SETS = available_rule_sets()


@pytest.fixture
def client(tmp_path, monkeypatch):
    out = tmp_path / "web_out"
    out.mkdir()
    monkeypatch.setattr(app_mod, "OUTPUT_DIR", out)
    monkeypatch.setattr(app_mod, "FAILURE_LOG", tmp_path / "failures.jsonl")
    return TestClient(app_mod.app)


@pytest.fixture
def cli(monkeypatch, tmp_path):
    """Run ``main.main`` with the output in ``tmp_path``; returns the sidecar
    of the build it made."""
    # main() points tempfile at the output dir for the whole process.
    monkeypatch.setattr(tempfile, "tempdir", tempfile.tempdir)

    def run(name, *args):
        main.main(["generate", name, *args, "--output", str(tmp_path)])
        (path,) = tmp_path.glob(f"{name}_*/v1/{name}.zone.json")
        return json.loads(path.read_text(encoding="utf-8"))
    return run


def _server_sidecar(body):
    return json.loads((app_mod.OUTPUT_DIR / body["id"] / "v1"
                       / f"{body['id']}.zone.json").read_text(encoding="utf-8"))


# --- bad values -------------------------------------------------------------

@pytest.mark.parametrize("argv, named", [
    (["--layout", "maze"], ["classic", "graph"]),
    (["--layout", "graph", "--rule-set", "nope"], SETS),
    (["--zone-type", "city", "--layout", "graph"], ["dungeon", "outdoor_dungeon"]),
    (["--zone-type", "city", "--rule-set", SETS[0]], ["dungeon", "outdoor_dungeon"]),
])
def test_cli_bad_value_is_a_usage_error(argv, named, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(main, "cmd_generate", lambda args: pytest.fail("built"))
    with pytest.raises(SystemExit) as exc:
        main.main(["generate", "bad", *argv, "--output", str(tmp_path)])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert all(n in err for n in named), err


def test_cli_passes_the_values_to_the_plan(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(main, "cmd_generate", lambda args: seen.update(vars(args)))
    monkeypatch.setattr(tempfile, "tempdir", tempfile.tempdir)
    main.main(["generate", "ok", "--layout", "GRAPH", "--rule-set", SETS[-1],
               "--output", str(tmp_path)])
    assert seen["layout"] == "graph" and seen["rule_set"] == SETS[-1]
    # The default classic is accepted (a no-op) on a type that takes no layout.
    main.main(["generate", "ok", "--zone-type", "city", "--layout", "classic",
               "--output", str(tmp_path)])
    assert seen["layout"] == "classic"


@pytest.mark.parametrize("controls, named", [
    ({"layout": "maze"}, ["classic", "graph"]),
    ({"layout": 3}, ["classic", "graph"]),
    ({"layout": "graph", "rule_set": "nope"}, SETS),
    ({"layout": "graph", "rule_set": ["warren"]}, SETS),
    ({"zone_type": "city", "layout": "graph"}, ["dungeon", "outdoor_dungeon"]),
    ({"zone_type": "city", "rule_set": SETS[0]}, ["dungeon", "outdoor_dungeon"]),
])
def test_server_bad_value_is_a_400(client, controls, named):
    resp = client.post("/api/generate", json={
        "mode": "controls", "controls": {"zone_type": "dungeon", **controls}})
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"]
    assert all(n in detail for n in named), detail
    assert not any(app_mod.OUTPUT_DIR.iterdir())     # refused before any write


# --- builds -------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.parametrize("rule_set", SETS)
def test_cli_builds_a_graph_dungeon(cli, rule_set):
    lay = cli("gcli", "--layout", "graph", "--rule-set", rule_set,
              "--rooms", "6", "--seed", "3")["layout"]
    assert lay["engine"] == "graph" and lay["rule_set"] == rule_set
    assert len(lay["rooms"]) == 6


@pytest.mark.slow
@pytest.mark.parametrize("rule_set", SETS)
def test_server_builds_a_graph_dungeon(client, rule_set):
    resp = client.post("/api/generate", json={
        "mode": "controls", "seed": 3,
        "controls": {"zone_type": "dungeon", "rooms": 6,
                     "layout": "graph", "rule_set": rule_set}})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["validated"] and body["plan"]["layout"] == "graph"
    lay = _server_sidecar(body)["layout"]
    assert lay["engine"] == "graph" and lay["rule_set"] == rule_set


@pytest.mark.slow
def test_cli_builds_a_graph_outdoor_dungeon(cli):
    side = cli("godcli", "--zone-type", "outdoor_dungeon", "--layout", "graph",
               "--rooms", "5", "--seed", "5")
    assert side["layout"]["engine"] == "graph"
    assert len(side["layout"]["rooms"]) == 5 and "outdoor_dungeon" in side


@pytest.mark.slow
def test_server_builds_a_graph_outdoor_dungeon(client):
    resp = client.post("/api/generate", json={
        "mode": "controls", "seed": 5,
        "controls": {"zone_type": "outdoor_dungeon", "rooms": 5, "layout": "graph"}})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["zone_type"] == "outdoor_dungeon" and body["validated"]
    assert _server_sidecar(body)["layout"]["engine"] == "graph"


# --- the outdoor dungeon on the step 5 acceptance seeds ------------------------

# docs/ACCEPTANCE.md "Step 5 — Outdoor dungeon" cases a-g: (prompt or room
# count + locks, edges, seed).
STEP5_CASES = {
    "a": ("a cave in a hill where kobolds live", None, None, 7),
    "b": ("an old barrow on the moors", None, None, 11),
    "c": ("a hillside cave temple with 6 rooms", None, None, 3),
    "d": ("a gnoll warren in the hills", None, None, 2),
    "e": (None, (5, 0), None, 5),
    "f": (None, (4, 1), {"N": "zoneline", "E": "river"}, 2),
    "g": (None, (6, 0), None, 42),
}

# The graph engine places its rooms without regard to the Envelope's way in,
# so the room nearest the hill foot (the pacing entrance, which takes the
# Tunnel) can be a small side room no Tunnel fits. Fixing it means facing the
# engine's entrance room toward ``envelope.entry`` (generators/layout_engine.py
# or generators/topology/embed.py), outside task 10's files.
_UNPLANNED = {"d", "g"}


def _plan(case, layout):
    prompt, counts, _edges, _seed = STEP5_CASES[case]
    if prompt:
        plan = RulePlanner().plan(prompt)
        plan.zone_type = "outdoor_dungeon"
    else:
        plan = ZonePlan(name="od", zone_type="outdoor_dungeon",
                        room_count=counts[0], locks=counts[1])
    plan.layout = layout
    return plan.validate()


@pytest.mark.parametrize("case", [
    pytest.param(c, marks=pytest.mark.xfail(
        raises=od.PLAN_ERRORS, strict=True,
        reason="graph entrance room not faced to the Envelope's entry"))
    if c in _UNPLANNED else c
    for c in STEP5_CASES])
def test_graph_outdoor_dungeon_plans_on_the_step5_seeds(case):
    _prompt, _counts, edges, seed = STEP5_CASES[case]
    plan = _plan(case, "graph")
    spec = plan_to_spec(plan, seed=seed, edges=edges)
    data = spec.wilderness[od.DUNGEON_KEY]
    assert spec.layout["engine"] == "graph"
    if len(spec.rooms) < plan.room_count:
        assert "rooms_reduced" in " ".join(data["warnings"])
    else:
        assert len(spec.rooms) == plan.room_count
    room = od.Entrance.from_dict(data["entrance"]).room_id
    assert next(r for r in spec.rooms if r.id == room).role == "entrance"


def test_shrink_retry_reuses_one_engine(monkeypatch):
    """``plan_dungeon`` lays out every shrink step with the engine it was
    given, not a fresh one per scale."""
    seen = []

    def spy(*args, engine=None, **kwargs):
        seen.append(engine)
        raise od.EntranceError("force every shrink step")
    monkeypatch.setattr(od, "layout_in_envelope", spy)
    plan = _plan("e", "graph")
    with pytest.raises(od.EntranceError):
        plan_to_spec(plan, seed=5)
    assert len(seen) == od.FIT_SHRINKS + 1
    assert seen[0] is not None and all(e is seen[0] for e in seen)


def test_classic_outdoor_dungeon_is_unchanged():
    """No toggle: the outdoor dungeon lays out classic and records no engine
    (the builder's sidecar then writes ``{"engine": "classic", ...}``)."""
    spec = plan_to_spec(_plan("e", "classic"), seed=5)
    assert spec.layout is None
    assert all(r.kind == "" for r in spec.rooms)
    assert "layout" not in spec.to_dict()
