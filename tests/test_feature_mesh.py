"""Room layouts task 3 (Requirement 3; design F2, F3): Features are closed solids on any floor
and under any ceiling, a dais walks from the floor, and the room's own checks still pass.
Driven by hand; no layout places one yet.
"""

import random

import numpy as np
import pytest
from hypothesis import given, settings, strategies as st

from analyzer.traverse import AgentModel, build_walk_surface, check_features, check_outline
from generators.geometry import MeshBuilder, _ensure_materials, build_mesh, dais_steps, room_doors, step_plans
from generators.outline import add_relief, draw_outline
from generators.room_features import CUT, DAIS, FORMS, PILLAR, PLINTH, ROUGH, SQUARE, Feature, POI, dais_plan, solid_plan
from generators.zone_spec import CorridorSpec, RoomSpec, ZoneSpec

AGENT = AgentModel()
HEIGHT = 40.0


def _spec(features=(), pois=(), shaped=False, relief=False, seed=1):
    a = RoomSpec("a", 0.0, 0.0, width=120.0, depth=100.0, height=HEIGHT, open_walls=["E"],
                 features=list(features), pois=list(pois))
    b = RoomSpec("b", 220.0, 0.0, width=100.0, depth=60.0, height=HEIGHT, open_walls=["W"])
    cor = CorridorSpec("c", 60.0, 0.0, 170.0, 0.0, width=18.0, height=30.0, from_room="a", to_room="b")
    spec = ZoneSpec(name="f", zone_type="dungeon", safe_point=(0.0, 0.0, 1.0))
    spec.rooms, spec.corridors = [a, b], [cor]
    _ensure_materials(spec)
    if shaped:
        a.outline = draw_outline((-60.0, -50.0, 60.0, 50.0), room_doors(a, spec), [], complex="voronoi",
                                 cell_size=24.0, fill=0.92, shape="cut", rng=random.Random(seed), wobble=6.0)
        if relief:
            add_relief(a.outline, HEIGHT, 5.0, 12.0, 8.0, 30.0, random.Random(seed))
    return spec


def _tris(mb, polys=None):
    return [[(mb.vertices[i].x, mb.vertices[i].y, mb.vertices[i].z) for i in (p.v1, p.v2, p.v3)]
            for p in (mb.polygons if polys is None else polys)]


def _solid_faces(plan, z0, z1):
    mb = MeshBuilder()
    from generators.zone_spec import MaterialSpec
    mat = mb.material_id(MaterialSpec(name="m", texture="m.dds"))
    mb._add_solid(plan, z0, z1, mat, mat)
    return mb


@settings(max_examples=40, deadline=None)
@given(form=st.sampled_from(FORMS), side=st.floats(3.0, 60.0), height=st.floats(4.0, 90.0), seed=st.integers(0, 9999))
def test_f2_a_solid_is_closed_and_faces_outward(form, side, height, seed):
    plan = solid_plan(form, 5.0, -7.0, side, random.Random(seed))
    mb = _solid_faces(plan, 2.0, 2.0 + height)
    tri = np.array(_tris(mb))
    keys = np.round(tri, 2)
    count = {}
    for t in keys:
        for i in range(3):
            a, b = tuple(t[i]), tuple(t[(i + 1) % 3])
            k = (a, b) if a < b else (b, a)
            count[k] = count.get(k, 0) + 1
    # Rows and pieces meet on shared lines: every edge has a partner, T-junctions aside.
    cx, cy = np.mean(plan, axis=0)
    for p in mb.polygons:
        v = mb.vertices[p.v1]
        a, b, c = (np.array([mb.vertices[i].x, mb.vertices[i].y, mb.vertices[i].z]) for i in (p.v1, p.v2, p.v3))
        n = np.cross(b - a, c - a)
        assert np.dot(n, [v.nx, v.ny, v.nz]) > 0, "winding matches the normal"
        if abs(v.nz) < 0.5:
            mid = (a + b + c) / 3
            assert (mid[0] - cx) * v.nx + (mid[1] - cy) * v.ny > 0, "sides face outward"
    assert all(n % 2 == 0 for n in count.values()), "closed"


def test_only_a_walkable_top_faces_up():
    mb = _solid_faces(solid_plan(SQUARE, 0, 0, 10, random.Random(1)), 0, 20)
    assert all(mb.vertices[p.v1].nz <= 0 for p in mb.polygons), "a pillar isn't floor"


@pytest.mark.parametrize("form", FORMS)
def test_plans_wind_counter_clockwise_and_are_about_the_size_asked(form):
    plan = solid_plan(form, 0.0, 0.0, 20.0, random.Random(3))
    area = 0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(plan, plan[1:] + plan[:1]))
    assert area > 0
    ext = np.ptp(np.array(plan), axis=0)
    assert ext.max() <= 20.0 + 1e-6 and ext.max() >= 10.0


@given(height=st.floats(0.5, 30.0))
def test_f3_no_riser_passes_the_cap(height):
    n = dais_steps(height)
    assert height / (n + 1) <= 2.0 + 1e-6


def test_step_plans_stand_outside_the_right_side():
    plan = [(-20.0, 10.0), (20.0, 10.0), (20.0, 26.0), (-20.0, 26.0)]
    for side, axis, sign, edge in (("S", 1, -1, 10.0), ("N", 1, 1, 26.0), ("E", 0, 1, 20.0), ("W", 0, -1, -20.0)):
        steps = step_plans(Feature(DAIS, plan, 8.0, side), 3)
        for k, s in enumerate(steps):
            coords = [p[axis] for p in s]
            assert (min(coords) >= edge - 1e-6) if sign > 0 else (max(coords) <= edge + 1e-6)
            area = 0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(s, s[1:] + s[:1]))
            assert area > 0, (side, k)
        # Lowest first, furthest out.
        outer = [max(p[axis] * sign for p in s) for s in steps]
        assert outer == sorted(outer, reverse=True)


PILLARS = [Feature(PILLAR, solid_plan(SQUARE, x, y, 8.0, random.Random(1))) for x, y in ((-25, 20), (-25, -20))]
PLINTHS = [Feature(PLINTH, solid_plan(CUT, -35.0, 0.0, 10.0, random.Random(2)), height=6.0)]
A_DAIS = Feature(DAIS, [(-30.0, 22.0), (10.0, 22.0), (10.0, 40.0), (-30.0, 40.0)], height=6.0, steps_side="S")


def _checks(spec):
    surf = build_walk_surface(build_mesh(spec).to_ter("f"), AGENT)
    room = spec.rooms[0]
    out = [check_features(surf, room, spec, AGENT)]
    if room.outline is not None:
        out.append(check_outline(surf, room, spec, AGENT))
    return out


@pytest.mark.parametrize("shaped, relief", [(False, False), (True, False), (True, True)])
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_room_checks_pass_with_features_standing_in_it(shaped, relief, seed):
    pois = [POI("altar", -20.0, 30.0, 6.0, feature=2)]
    spec = _spec(PILLARS + [A_DAIS], pois, shaped=shaped, relief=relief, seed=seed)
    for v in _checks(spec):
        assert v.ok, v.reason


def test_a_low_dais_needs_no_steps_and_walks():
    low = Feature(DAIS, A_DAIS.plan, height=2.0, steps_side="")
    assert dais_steps(2.0) == 0
    assert all(v.ok for v in _checks(_spec([low])))


def test_the_gate_sees_a_dais_with_no_steps():
    no_way = Feature(DAIS, A_DAIS.plan, height=8.0, steps_side="")
    v = _checks(_spec([no_way]))[0]
    assert not v.ok and "can't be walked onto" in v.reason


def test_a_room_with_no_features_adds_nothing():
    mb = MeshBuilder()
    spec = _spec()
    mb._add_features(spec.rooms[0], spec)
    assert not mb.polygons and not mb.vertices


def test_polygon_cap_and_edge_in_the_era_band():
    mb = _solid_faces(solid_plan(ROUGH, 0, 0, 16.0, random.Random(1)), 0, 60.0)
    assert len(mb.polygons) <= 400
    tri = np.array(_tris(mb, [p for p in mb.polygons if abs(mb.vertices[p.v1].nz) < 0.5]))
    edges = np.linalg.norm(tri - np.roll(tri, 1, axis=1), axis=2).ravel()
    assert 3.0 <= np.median(edges) <= 15.0, np.median(edges)


@pytest.mark.parametrize("form", FORMS)
@pytest.mark.parametrize("side", ["N", "S", "E", "W"])
@pytest.mark.parametrize("seed", [1, 2])
def test_a_dais_keeps_its_steps_side_straight_and_winds_right(form, side, seed):
    box = (-20.0, 10.0, 20.0, 34.0)
    plan = dais_plan(form, box, side, random.Random(seed))
    area = 0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(plan, plan[1:] + plan[:1]))
    assert area > 0, "counter-clockwise"
    assert area >= 0.6 * 40 * 24
    axis, at = {"N": (1, 34.0), "S": (1, 10.0), "E": (0, 20.0), "W": (0, -20.0)}[side]
    on_side = [p for p in plan if abs(p[axis] - at) < 1e-9]
    span = 40.0 if axis == 1 else 24.0
    assert len(on_side) == 2 and abs(on_side[0][1 - axis] - on_side[1][1 - axis]) == pytest.approx(span)


@pytest.mark.parametrize("form", FORMS)
def test_every_form_of_dais_walks_and_closes(form):
    plan = dais_plan(form, (-30.0, 22.0, 10.0, 40.0), "S", random.Random(1))
    spec = _spec([Feature(DAIS, plan, height=6.0, steps_side="S")], shaped=False)
    for v in _checks(spec):
        assert v.ok, v.reason
