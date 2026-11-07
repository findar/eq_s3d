"""Dungeon verticality task 7 (Requirement 7; design "Outdoor dungeons"):
outdoor dungeons honour the Verticality control and go down into the hill.

V8 on the step 5 acceptance seeds (docs/ACCEPTANCE.md "Step 5 — Outdoor
dungeon" cases a-g) at ``moderate`` and ``dramatic``: every room under the
hill with the Rock_Cover, one Entrance at the top Level, every room reached
from the Outdoor_Spawn on the built mesh, and at least two Levels where the
hill holds them (else rooms dropped with ``rooms_reduced``). ``flat`` is
step 5's one-Level dungeon, unchanged.
"""

import itertools

import pytest

from ai.expand import layout_engine, plan_to_spec
from ai.rule_planner import RulePlanner
from ai.schema import ZonePlan
from generators import outdoor_dungeon as od
from generators.builder import ZoneBuilder
from generators.layout import LayoutGenerator
from generators.layout_engine import GraphEngine
from generators.topology.embed import SLAB
from generators.wilderness.build import build_wilderness_ter

# docs/ACCEPTANCE.md "Step 5 — Outdoor dungeon" cases a-g: (prompt or room
# count + locks, edges, seed). Case d is ACCEPTANCE.md's seed 2: stacked, it
# plans (test_graph_layout_controls pins seed 3 for the one-Level dungeon).
CASES = {
    "a": ("a cave in a hill where kobolds live", None, None, 7),
    "b": ("an old barrow on the moors", None, None, 11),
    "c": ("a hillside cave temple with 6 rooms", None, None, 3),
    "d": ("a gnoll warren in the hills", None, None, 2),
    "e": (None, (5, 0), None, 5),
    "f": (None, (4, 1), {"N": "zoneline", "E": "river"}, 2),
    "g": (None, (6, 0), None, 42),
}


def _plan(case, verticality, layout="graph"):
    prompt, counts, _edges, _seed = CASES[case]
    if prompt:
        plan = RulePlanner().plan(prompt)
        plan.zone_type = "outdoor_dungeon"
    else:
        plan = ZonePlan(name="od", zone_type="outdoor_dungeon",
                        room_count=counts[0], locks=counts[1])
    plan.name = f"odl{case}{verticality[0]}"
    plan.layout = layout
    plan.verticality = verticality
    return plan.validate()


def _spec(case, verticality, layout="graph"):
    _p, _c, edges, seed = CASES[case]
    return plan_to_spec(_plan(case, verticality, layout), seed=seed, edges=edges)


def _envelope(spec, verticality):
    ter = build_wilderness_ter(spec, "ter_check", 1)
    return od.host_envelope(spec, ter, depth=od.floor_depth(verticality, spec.dungeon_race))


def _overlap_in_plan(a, b):
    return (abs(a.center_x - b.center_x) < (a.width + b.width) / 2
            and abs(a.center_y - b.center_y) < (a.depth + b.depth) / 2)


@pytest.mark.slow
@pytest.mark.parametrize("verticality", ["moderate", "dramatic"])
@pytest.mark.parametrize("case", sorted(CASES))
def test_v8_outdoor_dungeon_goes_down(tmp_path, case, verticality):
    spec = _spec(case, verticality)
    data = spec.wilderness[od.DUNGEON_KEY]
    levels = spec.layout["levels"]
    assert set(levels) == {r.id for r in spec.rooms}

    # At least two Levels where the hill holds them, else rooms dropped.
    if len(set(levels.values())) < 2:
        assert "rooms_reduced" in " ".join(data["warnings"])
    # One Entrance, into the entrance room, on the top Level.
    side = od.sidecar_block(spec)
    assert len(side["entrances"]) == 1
    entrance = od.Entrance.from_dict(data["entrance"])
    room = next(r for r in spec.rooms if r.id == entrance.room_id)
    assert room.role == "entrance"
    assert levels[room.id] == max(levels.values()) == 0

    # Under the hill: every room and corridor in the Envelope (footprint,
    # the deeper floor limit, the Rock_Cover under the surface), and the
    # cover kept over all of it once the Apron is dug.
    env = _envelope(spec, verticality)
    assert env.floor_limit == pytest.approx(data["floor_limit"])
    assert LayoutGenerator.fits(spec, env)
    grid = od._host_grid(spec, build_wilderness_ter(spec, "ter_check", 1))
    dug = od._grid_surface(od._apron(grid, entrance)[0], grid.origin, grid.res)
    assert od._boxes_covered(spec, dug, od.ROCK_COVER)

    # The Levels kept their stack through the fit: a room over another in
    # plan has the Slab between them.
    for a, b in itertools.combinations(spec.rooms, 2):
        if levels[a.id] != levels[b.id] and _overlap_in_plan(a, b):
            lo, hi = sorted((a, b), key=lambda r: levels[r.id])
            assert hi.floor_z - (lo.floor_z + lo.height) >= SLAB - 1e-6

    # Every room reached from the Outdoor_Spawn on the built mesh.
    result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)
    report = od.outdoor_dungeon_report(result.eqg_path, spec)
    assert report.passed, report.summary()
    assert report.reachable_rooms == report.total_rooms == len(spec.rooms) + 1
    assert report.corridors_passed


def _boxes(spec):
    """The rooms without what wall styles add (step 8)."""
    rooms = spec.to_dict()["rooms"]
    for r in rooms:
        for key in ("outline", "floor_material", "wall_material", "ceiling_material", "features", "pois",
                    "prop_hints"):
            r.pop(key, None)
    return rooms


@pytest.mark.parametrize("case", ["e", "f"])
def test_flat_is_the_step5_dungeon(case):
    """``flat`` lays the outdoor dungeon out as before task 7: one Level,
    stacking off, the vertical rules as ramp hints, step 5's floor limit."""
    spec = _spec(case, "flat")
    _p, counts, edges, seed = CASES[case]
    before = od.outdoor_dungeon_spec(
        "odl" + case + "f", seed, edges, room_count=counts[0], locks=counts[1],
        engine=GraphEngine(None, vertical_weight=1.0))
    assert _boxes(spec) == _boxes(before), "the layout is step 5's; only its walls differ"
    assert spec.wilderness[od.DUNGEON_KEY] == before.wilderness[od.DUNGEON_KEY]
    assert "levels" not in spec.layout
    foot = od.approach_foot(od.landscape_for(spec).matrix.landform)
    ground = od.ter_surface(build_wilderness_ter(spec, "t", 1),
                            od.landscape_for(spec).synth.origin,
                            od.landscape_for(spec).synth.resolution,
                            od.landscape_for(spec).bowl.heights.shape)(*foot)
    assert spec.wilderness[od.DUNGEON_KEY]["floor_limit"] == pytest.approx(
        float(ground) - od.FLOOR_DEPTH)


def test_floor_limit_follows_the_control():
    """The floor limit: step 5's 150 u, plus one race Level height (tallest
    room + Slab + floor variation) per extra Level the control asks for."""
    assert od.floor_depth(None) == od.floor_depth("flat") == od.FLOOR_DEPTH
    human = od.level_height("")
    assert human == pytest.approx(60.0 + SLAB + 28.0)
    assert od.floor_depth("moderate") == pytest.approx(od.FLOOR_DEPTH + human)
    assert od.floor_depth("dramatic") == pytest.approx(od.FLOOR_DEPTH + 2 * human)
    assert od.floor_depth("dramatic", "giant") > od.floor_depth("dramatic", "ogre")


def test_classic_layout_keeps_one_level():
    """The classic engine has no Levels: its outdoor dungeon keeps step 5's
    floor limit at any Verticality (the classic golden is unchanged)."""
    spec = _spec("e", "dramatic", layout="classic")
    flat = _spec("e", "flat", layout="classic")
    assert spec.wilderness[od.DUNGEON_KEY]["floor_limit"] == \
        flat.wilderness[od.DUNGEON_KEY]["floor_limit"]
    assert spec.layout is None


@pytest.mark.parametrize("verticality", ["moderate", "dramatic"])
def test_outdoor_engine_descends(verticality):
    """The outdoor engine's Levels go down from the entrance only (Level 0
    on top), on at least two Levels, and every edge's relation agrees with
    its rooms' Levels (a graph turned over flips its relations)."""
    engine = layout_engine("graph", "", verticality, outdoor=True)
    assert engine.stacking and engine.descend
    for seed, n in itertools.product(range(12), (4, 6, 9)):
        gen = LayoutGenerator("dungeon", seed=seed, engine=engine)
        gen.generate("d", room_count=n)
        rec = gen.layout_record
        levels = rec["levels"]
        entrance = next(r for r, v in rec["rooms"].items() if v["kind"] == "entrance")
        assert levels[entrance] == 0 == max(levels.values()), (seed, n)
        assert len(set(levels.values())) >= 2, (seed, n)
        for a, b, rel in rec["edges"]:
            step = levels[b] - levels[a]
            if rel == "above":
                assert step >= 0, (seed, n, a, b)
            elif rel == "below":
                assert step <= 0, (seed, n, a, b)


def test_flat_outdoor_engine_is_step5s():
    engine = layout_engine("graph", "", "flat", outdoor=True)
    assert not engine.stacking and not engine.descend
    assert engine.vertical_weight == 1.0


@pytest.mark.slow
def test_dragon_stairs_stay_inside_the_bowl(tmp_path):
    """Task 19 (Req 7.2): on seed 1654615998 (dragon, temple, 5 rooms,
    moderate) a U-route stair's Switchback stairwell ran past the W map edge
    (x < -440) under the boundary, and the bowl gate read the flood as
    escaping (task 9). Every corridor piece (legs, bends, the stairwell the
    builder folds the stair into) now stays inside the bowl interior, and
    the build passes the gate on this seed."""
    import random

    from generators.geometry import stair_layout
    from generators.pipeline import generate_validated
    from generators.routing import corridor_route, route_footprint

    plan = ZonePlan(name="odbowl", zone_type="outdoor_dungeon", room_count=5,
                    dungeon_theme="temple", dungeon_race="dragon", layout="graph",
                    rule_set="classic_eq", verticality="moderate").validate()
    # The pipeline's first attempt seed for random.Random(0) is 1654615998
    # (task 9's sweep seed 0); one attempt, so the gate passes first try.
    vb = generate_validated(lambda s: plan_to_spec(plan, seed=s),
                            zone_type=plan.zone_type, zone_id=plan.name,
                            output_dir=tmp_path, write_glb=False,
                            rng=random.Random(0), failure_log=None, max_attempts=1)
    assert vb.seed == 1654615998 and vb.attempts == 1 and vb.validated
    spec = vb.spec
    x0, y0, x1, y1 = od.bowl_interior(od.landscape_for(spec))
    rooms = {r.id: r for r in spec.rooms}
    stairs = 0
    for c in spec.corridors:
        pieces = list(route_footprint(corridor_route(c, rooms), c.width / 2))
        lay = stair_layout(c, rooms)
        stairs += lay is not None
        if lay is not None and lay.stairwell is not None:
            pieces.append(lay.stairwell)
        for p in pieces:
            assert x0 - 1e-6 <= p[0] and p[2] <= x1 + 1e-6, (c.id, p)
            assert y0 - 1e-6 <= p[1] and p[3] <= y1 + 1e-6, (c.id, p)
    assert stairs, "no stair between Levels left to check"
