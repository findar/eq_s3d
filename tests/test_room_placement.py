"""Room layouts task 4 (Requirement 4; design F4, F5): placement keeps the way through clear, a
misfit drops and never fails, and arrangements look like themselves. Over plain and shaped rooms.
"""

import copy
import random

import numpy as np
import pytest
from hypothesis import given, settings, strategies as st

from generators.outline import draw_outline
from generators.room_features import CUT, DAIS, PILLAR, PLINTH, ROUGH, SQUARE
from generators.room_layouts import ARRANGEMENTS, Ask, RoomGrid, place
from generators.zone_spec import RoomSpec

H = 6.0
SHAPES = st.sampled_from([None, "voronoi", "grid", "facet"])


def _room(w, d, complex=None, doors=(), seed=1, height=40.0):
    r = RoomSpec("r", 0.0, 0.0, width=w, depth=d, height=height)
    if complex:
        size = {"voronoi": 24.0, "grid": 24.0, "facet": 0.0}[complex]
        r.outline = draw_outline((-w / 2, -d / 2, w / 2, d / 2), list(doors), [], complex=complex, cell_size=size,
                                 fill=0.8, shape="blob", rng=random.Random(seed), wobble=6.0 if complex == "voronoi" else 0.0)
    return r


def _doors(w, d, picks):
    out = {}
    for side, t in picks:
        span = (w if side in "NS" else d) - 18.0
        lo = -span / 2 + span * t - 9.0
        out[side] = (side, lo, lo + 18.0)
    return sorted(out.values())


ASKS = [Ask(DAIS, "far_end", poi="boss"), Ask(PLINTH, "centre", height_h=1.0), Ask(PILLAR, "ring", count=(4, 8)),
        Ask(PILLAR, "rows"), Ask(PILLAR, "corners", count=(4, 4)), Ask(PILLAR, "along_wall"),
        Ask(PLINTH, "scatter", count=(1, 4), height_h=1.0)]


@settings(max_examples=60, deadline=None)
@given(w=st.floats(48.0, 200.0), d=st.floats(48.0, 200.0), complex=SHAPES, seed=st.integers(0, 10 ** 6),
       picks=st.lists(st.tuples(st.sampled_from("NSEW"), st.floats(0.0, 1.0)), min_size=1, max_size=4),
       asks=st.lists(st.sampled_from(ASKS), min_size=1, max_size=4))
def test_f4_placement_keeps_the_way_clear_and_never_fails(w, d, complex, seed, picks, asks):
    doors = _doors(w, d, picks)
    room = _room(w, d, complex, doors, seed)
    placed = place(room, doors, [], asks, H, SQUARE, random.Random(seed))
    grid = RoomGrid(room, doors, [], H)
    solid = np.zeros(grid.floor.shape, bool)
    for f in placed.features:
        cells = grid.footprint(f.plan)
        assert not (cells & grid.spine).any(), "off the Spine"
        assert (cells <= grid.floor).all(), "on the floor"
        solid |= cells
        if f.kind == DAIS:
            grid.raised |= cells
    assert grid.doors_stay_joined(solid), "doors joined, no pocket"


def test_f5_same_inputs_same_placement_and_the_room_is_untouched():
    doors = [("E", -9.0, 9.0), ("W", -9.0, 9.0)]
    room = _room(120.0, 90.0, "voronoi", doors)
    before = copy.deepcopy(room)
    a = place(room, doors, [], ASKS, H, ROUGH, random.Random(5))
    b = place(room, doors, [], ASKS, H, ROUGH, random.Random(5))
    assert a == b
    assert room == before


def test_a_room_too_small_drops_and_records():
    doors = [("E", -9.0, 9.0), ("W", -9.0, 9.0), ("N", -9.0, 9.0), ("S", -9.0, 9.0)]
    placed = place(_room(48.0, 48.0), doors, [], [Ask(DAIS, "far_end", share=0.5), Ask(PLINTH, "centre")], H,
                   SQUARE, random.Random(1))
    assert not any(f.kind == PLINTH for f in placed.features)
    assert placed.dropped


def test_a_slot_stays_clear():
    doors = [("E", -9.0, 9.0)]
    slot = (-20.0, -20.0, 20.0, 20.0)
    placed = place(_room(160.0, 160.0), doors, [slot], [Ask(PLINTH, "centre", height_h=1.0)], H, SQUARE,
                   random.Random(1))
    assert not placed.features and placed.dropped


def test_a_ring_is_a_ring():
    placed = place(_room(160.0, 160.0), [("E", -9.0, 9.0)], [], [Ask(PILLAR, "ring", count=(6, 6), radius=0.35)], H,
                   CUT, random.Random(1))
    assert len(placed.features) >= 4
    mids = np.array([np.mean(f.plan, axis=0) for f in placed.features])
    assert np.ptp(np.hypot(mids[:, 0], mids[:, 1])) < 1.0, "the same distance from the middle"


def test_rows_run_along_the_long_side_in_two_lines():
    placed = place(_room(200.0, 100.0), [("E", -9.0, 9.0), ("W", -9.0, 9.0)], [], [Ask(PILLAR, "rows", count=(6, 6))], H,
                   SQUARE, random.Random(1))
    mids = np.array([np.mean(f.plan, axis=0) for f in placed.features])
    assert len(mids) >= 4
    assert len(set(np.round(mids[:, 1], 1))) == 2, "two lines"


def test_a_dais_stands_at_the_far_end_with_steps_toward_the_room():
    placed = place(_room(120.0, 120.0), [("S", -9.0, 9.0)], [], [Ask(DAIS, "far_end", poi="boss")], H, SQUARE,
                   random.Random(1))
    (dais,) = placed.features
    assert np.mean(dais.plan, axis=0)[1] > 20.0, "away from the door"
    assert dais.steps_side == "S" and dais.height == pytest.approx(5.1)
    assert np.array(dais.plan)[:, 1].max() <= 60.0 - H + 1e-6, "a body's margin from the wall"
    (poi,) = placed.pois
    assert poi.purpose == "boss" and poi.z == pytest.approx(5.1) and poi.feature == 0


def test_a_dais_takes_the_side_furthest_from_the_doors_that_fits():
    doors = [("E", -20.0, -2.0), ("W", 5.0, 23.0)]
    placed = place(_room(130.0, 100.0), doors, [], [Ask(DAIS, "far_end")], H, SQUARE, random.Random(1))
    (dais,) = placed.features
    assert dais.steps_side in ("N", "S"), "not the walls the doors are in"


def test_a_centre_piece_finds_the_middle_when_the_way_through_leaves_it():
    doors = [("E", -30.0, -12.0), ("W", -30.0, -12.0)]
    placed = place(_room(130.0, 120.0), doors, [], [Ask(PLINTH, "centre", height_h=1.0)], H, SQUARE, random.Random(1))
    (plinth,) = placed.features
    assert np.allclose(np.mean(plinth.plan, axis=0), (0.0, 0.0), atol=12.0)


def test_only_the_entrance_keeps_its_middle_clear():
    doors = [("E", -30.0, -12.0), ("W", -30.0, -12.0)]
    plain, entrance = _room(130.0, 120.0), _room(130.0, 120.0)
    entrance.role = "entrance"
    g0, g1 = RoomGrid(plain, doors, [], H), RoomGrid(entrance, doors, [], H)
    at = np.argmin(np.hypot(g0.gx, g0.gy))
    at = np.unravel_index(at, g0.gx.shape)
    assert not g0.spine[at] and g1.spine[at]


def test_a_low_ceiling_drops_a_dais():
    placed = place(_room(120.0, 120.0, height=15.0), [("S", -9.0, 9.0)], [], [Ask(DAIS, "far_end", height_h=2.0)], H,
                   SQUARE, random.Random(1))
    assert not placed.features and placed.dropped


def test_on_dais_stands_on_it():
    placed = place(_room(120.0, 120.0), [("S", -9.0, 9.0)], [],
                   [Ask(DAIS, "far_end"), Ask(PLINTH, "on_dais", height_h=1.0)], H, SQUARE, random.Random(1))
    dais, plinth = placed.features
    assert plinth.height == pytest.approx(dais.height + H)
    assert np.allclose(np.mean(plinth.plan, axis=0), np.mean(dais.plan, axis=0))


def test_a_poi_stands_beside_a_solid_not_on_it():
    placed = place(_room(160.0, 160.0), [("S", -9.0, 9.0)], [], [Ask(PLINTH, "along_wall", poi="altar", count=(1, 1))],
                   H, SQUARE, random.Random(1))
    (poi,) = placed.pois
    plan = np.array(placed.features[0].plan)
    assert not (plan[:, 0].min() <= poi.x <= plan[:, 0].max() and plan[:, 1].min() <= poi.y <= plan[:, 1].max())


def test_every_arrangement_is_exercised():
    assert set(ARRANGEMENTS) == {a.at for a in ASKS} | {"on_dais"}


@pytest.mark.parametrize("complex", [None, "voronoi", "grid", "facet"])
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_placements_pass_the_gate_on_built_meshes(complex, seed):
    from analyzer.traverse import AgentModel, build_walk_surface, check_features, check_outline
    from generators.geometry import _ensure_materials, build_mesh, room_doors
    from generators.zone_spec import CorridorSpec, ZoneSpec

    agent = AgentModel()
    a = RoomSpec("a", 0, 0, width=130.0, depth=100.0, height=40.0, open_walls=["E", "W"])
    spec = ZoneSpec(name="o", zone_type="dungeon", safe_point=(0, 0, 1))
    spec.rooms = [a, RoomSpec("e", 165.0, -11.0, width=100, depth=40, height=40, open_walls=["W"]),
                  RoomSpec("w", -165.0, 14.0, width=100, depth=40, height=40, open_walls=["E"])]
    spec.corridors = [CorridorSpec("ce", 65, -11, 115, -11, width=18, height=30, from_room="a", to_room="e"),
                      CorridorSpec("cw", -115, 14, -65, 14, width=18, height=30, from_room="w", to_room="a")]
    _ensure_materials(spec)
    doors = room_doors(a, spec)
    if complex:
        a.outline = draw_outline((-65.0, -50.0, 65.0, 50.0), doors, [], complex=complex, cell_size=24.0, fill=0.8,
                                 shape="blob", rng=random.Random(seed), wobble=7.8 if complex == "voronoi" else 0.0)
    asks = [Ask(DAIS, "far_end", poi="boss"), Ask(PILLAR, "ring", count=(4, 8)), Ask(PLINTH, "centre", height_h=1.0)]
    placed = place(a, doors, [], asks, H, SQUARE, random.Random(seed))
    a.features, a.pois = placed.features, placed.pois
    surf = build_walk_surface(build_mesh(spec).to_ter("o"), agent)
    v = check_features(surf, a, spec, agent)
    assert v.ok, v.reason
    if a.outline is not None:
        v = check_outline(surf, a, spec, agent)
        assert v.ok, v.reason

