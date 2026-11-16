"""
tests/test_room_decor_seeds.py
------------------------------
Room decor seeds (partial-rebuild task 1, Req 3): a room that keeps its own decor seed.

- Fast: ``ZoneSpec`` and ``ZonePlan`` round-trip ``room_decor_seeds`` (left out while empty),
  the plan validates it, and ``plan_to_spec`` carries it.
- With the install (``EQ_PATH``; slow): on the 16-room Graph dungeon seed 2 and a city, a room's
  own seed changes that room's Props and no other room's or corridor's (Props and bare flags);
  a room the zone's draw leaves bare stays bare; the sidecar names the seeds; the room view's
  "As built" for each room equals the build's Props, and a reroll of the room in the build
  without the seed previews exactly what the build with it holds (one rule for both).
"""

from __future__ import annotations

import json

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.builder import ZoneBuilder
from generators.decor.stock import eq_path_from_env
from generators.zone_spec import ZoneSpec

EQ = eq_path_from_env()
needs_install = pytest.mark.skipif(EQ is None, reason="EQ_PATH is not set (no EQ install to read)")

#: The room's own seed the builds below give one room.
OWN = 123457

CASES = {
    "graph_dungeon": (dict(zone_type="dungeon", room_count=16, layout="graph"), 2),
    "city": (dict(zone_type="city"), 5),
}


def test_spec_and_plan_round_trip_room_decor_seeds():
    spec = ZoneSpec(name="x")
    assert "room_decor_seeds" not in spec.to_dict()
    spec.room_decor_seeds = {"room_3": 7}
    assert ZoneSpec.from_dict(spec.to_dict()).room_decor_seeds == {"room_3": 7}

    plan = ZonePlan(name="x").validate()
    assert "room_decor_seeds" not in plan.to_dict()
    plan = ZonePlan(name="x", room_decor_seeds={"room_3": 7}).validate()
    assert ZonePlan.from_dict(plan.to_dict()).room_decor_seeds == {"room_3": 7}
    assert plan_to_spec(plan, seed=1).room_decor_seeds == {"room_3": 7}
    assert plan_to_spec(ZonePlan(name="x").validate(), seed=1).room_decor_seeds == {}


@pytest.mark.parametrize("bad", [{"room_3": -1}, {"room_3": 2 ** 31}, {"room_3": "7"},
                                 {"room_3": True}, {"room 3": 7}, {"": 7}, ["room_3"], 7])
def test_plan_rejects_a_bad_room_decor_seeds(bad):
    with pytest.raises(ValueError):
        ZonePlan(name="x", room_decor_seeds=bad).validate()


def _build(tmp, fields, seed, own=None):
    spec = plan_to_spec(ZonePlan(name="rds", **fields).validate(), seed=seed)
    spec.decor = "normal"
    if own:
        spec.room_decor_seeds = dict(own)
    result = ZoneBuilder(spec).build(output_dir=tmp, write_glb=False)
    for fname, text in result.handoffs().items():     # the rooms file the room view reads
        (tmp / fname).write_text(text, encoding="utf-8")
    return json.loads(result.sidecar_path.read_text(encoding="utf-8"))


def _records(side):
    out = {r["id"]: (r.get("props", []), r.get("bare")) for r in side["rooms"]}
    out.update({c["id"]: (c.get("props", []), c.get("bare")) for c in side.get("corridors", [])})
    return out


def _room_view(tmp, room, **kw):
    from generators.decor.room_view import decorate_room, load_build
    b = load_build(tmp, "rds")
    _glb, rep = decorate_room(b.contexts, room, seed=b.seed, control=b.control, layers=b.layers,
                              eq_path=EQ, mesh=b.mesh, room_seeds=b.room_seeds, **kw)
    return rep


@pytest.mark.slow
@needs_install
@pytest.mark.parametrize("label", sorted(CASES))
def test_a_rooms_own_seed_moves_that_room_alone(tmp_path, label):
    fields, seed = CASES[label]
    base_dir, own_dir = tmp_path / "base", tmp_path / "own"
    base = _build(base_dir, fields, seed)
    before = _records(base)
    rooms = [r for r in base["rooms"] if "props" in r]
    target = next(r["id"] for r in rooms if not r["bare"] and r["props"])
    bare = next((r["id"] for r in rooms if r["bare"]), None)
    own = {target: OWN, **({bare: OWN} if bare else {})}

    side = _build(own_dir, fields, seed, own)
    after = _records(side)
    assert side["seeds"]["room_decor_seeds"] == own
    assert set(after) == set(before)
    assert after[target][0] != before[target][0], "the room's own seed changes its Props"
    assert after[target][1] is False
    for rid in before:
        if rid != target:
            assert after[rid] == before[rid], f"{label}: {rid} moved"   # a bare room stays bare
    recs = {r["id"]: r for r in side["rooms"]}
    assert all(recs[rid]["decor_seed"] == s for rid, s in own.items())
    assert all("decor_seed" not in r for r in side["rooms"] if r["id"] not in own)
    assert "room_decor_seeds" not in base["seeds"]

    # The room view: "As built" takes the room's own seed and gives the build's Props.
    for rid in own:
        rep = _room_view(own_dir, rid)
        assert rep["props"] == after[rid][0] and rep["bare"] == after[rid][1], rid
        assert rep["room_seed"] == OWN and rep["zone_seed"] == base["decor"]["seed"]
        assert rep["seed"] == (base["decor"]["seed"] if rep["bare"] else OWN)
    # A room without one is as before.
    other = next(r["id"] for r in rooms if r["id"] not in own)
    rep = _room_view(own_dir, other)
    assert rep["props"] == after[other][0] and rep["room_seed"] is None
    # A reroll of the room in the build without the seed previews what Use in zone keeps.
    rep = _room_view(base_dir, target, room_seed=OWN)
    assert rep["props"] == after[target][0] and rep["seed"] == OWN


def test_a_plans_fields_stay_hashable():
    """The sweeps key builds on ``asdict(plan)`` (``tests/conftest.gated_key``)."""
    import pickle
    from dataclasses import asdict
    from tests.conftest import gated_key
    plan = ZonePlan(name="x", room_decor_seeds={"room_3": 7}).validate()
    hash(asdict(plan)["room_decor_seeds"])
    hash(gated_key(dict(zone_type="dungeon"), 1, 1, 1.0))
    hash(gated_key(dict(zone_type="dungeon", room_decor_seeds={"room_3": 7}), 1, 1, 1.0))
    assert pickle.loads(pickle.dumps(plan)).room_decor_seeds == {"room_3": 7}
