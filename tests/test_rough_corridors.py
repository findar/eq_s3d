"""Room walls task 9 (Requirement 8; design W8): corridors match their rooms. Walls and
ceilings come in, the floor and route stay, and the ends meet their rooms square.
"""

import numpy as np
import pytest
from hypothesis import given, settings, strategies as st

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from analyzer.traverse import AgentModel, build_walk_surface, corridor_continuity
from generators.geometry import MeshBuilder, _ensure_materials, build_mesh
from generators.semantics import body_height
from generators.wall_styles import load_styles
from generators.zone_spec import CorridorSpec, RoomSpec, ZoneSpec

AGENT = AgentModel()


def _spec(rough, length=120.0, rise=0.0, width=18.0, height=15.0):
    a = RoomSpec("a", 0.0, 0.0, width=60.0, depth=60.0, height=30.0, open_walls=["E"])
    b = RoomSpec("b", 60.0 + length, 0.0, floor_z=rise, width=60.0, depth=60.0, height=30.0, open_walls=["W"])
    cor = CorridorSpec("c", 30.0, 0.0, 30.0 + length, 0.0, from_z=0.0, to_z=rise, width=width, height=height,
                       from_room="a", to_room="b", rough=rough)
    spec = ZoneSpec(name="c", zone_type="dungeon", safe_point=(0.0, 0.0, 1.0))
    spec.rooms, spec.corridors = [a, b], [cor]
    _ensure_materials(spec)
    return spec


def _mesh(spec):
    mb = MeshBuilder()
    mb.add_corridor(spec.corridors[0], spec)
    return mb


def _faces(mb, up):
    out = []
    for p in mb.polygons:
        v = mb.vertices[p.v1]
        if up(v):
            out.append([(mb.vertices[i].x, mb.vertices[i].y, mb.vertices[i].z) for i in (p.v1, p.v2, p.v3)])
    return np.array(out)


@settings(max_examples=25, deadline=None)
@given(length=st.floats(30.0, 300.0), rise=st.floats(0.0, 20.0), rough=st.floats(0.01, 0.15))
def test_w8_clear_width_ends_and_floor(length, rise, rough):
    spec = _spec(rough, length, rise)
    mb = _mesh(spec)
    walls = _faces(mb, lambda v: abs(v.nz) < 0.5)
    ys = walls[:, :, 1]
    south, north = ys[ys.mean(axis=1) < 0], ys[ys.mean(axis=1) > 0]
    # Clear width: a share off each side at most, so 2 H of a 3 H corridor stays.
    assert south.max() <= -9.0 + rough * 18 + 1e-6 and north.min() >= 9.0 - rough * 18 - 1e-6
    assert north.min() - south.max() >= 18 * (1 - 2 * rough) - 1e-6
    # Square at both ends, where it meets the rooms.
    for end in (30.0, 30.0 + length):
        at = walls.reshape(-1, 3)
        here = at[np.abs(at[:, 0] - end) < 1e-6]
        assert len(here) and set(np.round(np.abs(here[:, 1]), 6)) == {9.0}
    # The floor is the plain corridor's: the same area at the same heights.
    plain = _faces(_mesh(_spec(0.0, length, rise)), lambda v: v.nz > 0.5)
    floor = _faces(mb, lambda v: v.nz > 0.5)

    def area(tris):
        return np.abs(np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])).sum() / 2
    assert area(floor) == pytest.approx(area(plain), rel=1e-6)
    assert floor[:, :, 1].min() == -9.0 and floor[:, :, 1].max() == 9.0


def test_faces_wind_the_way_their_normals_say():
    mb = _mesh(_spec(0.15, rise=10.0))
    for p in mb.polygons:
        a, b, c = (np.array([mb.vertices[i].x, mb.vertices[i].y, mb.vertices[i].z]) for i in (p.v1, p.v2, p.v3))
        v = mb.vertices[p.v1]
        assert np.dot(np.cross(b - a, c - a), [v.nx, v.ny, v.nz]) > 0


def test_a_y_leg_builds_too():
    spec = _spec(0.15)
    cor = spec.corridors[0]
    spec.rooms[0].open_walls, spec.rooms[1].open_walls = ["N"], ["S"]
    spec.rooms[1].center_x, spec.rooms[1].center_y = 0.0, 180.0
    cor.from_x, cor.from_y, cor.to_x, cor.to_y = 0.0, 30.0, 0.0, 150.0
    mb = _mesh(spec)
    walls = _faces(mb, lambda v: abs(v.nz) < 0.5)
    assert abs(walls[:, :, 0]).min() < 9.0
    for p in mb.polygons:
        a, b, c = (np.array([mb.vertices[i].x, mb.vertices[i].y, mb.vertices[i].z]) for i in (p.v1, p.v2, p.v3))
        v = mb.vertices[p.v1]
        assert np.dot(np.cross(b - a, c - a), [v.nx, v.ny, v.nz]) > 0


def test_same_corridor_same_mesh():
    a, b = _mesh(_spec(0.15)), _mesh(_spec(0.15))
    assert [(v.x, v.y, v.z) for v in a.vertices] == [(v.x, v.y, v.z) for v in b.vertices]


@pytest.mark.parametrize("theme, expected", [("warren", True), ("mine_delve", True), ("", False)])
def test_styles_set_the_break_and_stairs_and_bridges_stay_square(theme, expected):
    plan = ZonePlan(name="w9", zone_type="dungeon", room_count=12, layout="graph", dungeon_theme=theme).validate()
    spec = plan_to_spec(plan, seed=11)
    style = load_styles()[spec.layout["walls"]]
    flat = [c for c in spec.corridors if c.steps == 0 and not c.bridge]
    assert flat and all(c.rough == style.corridor_break for c in flat)
    assert all(c.rough == 0 for c in spec.corridors if c.steps != 0 or c.bridge)
    assert bool(style.corridor_break) is expected
    assert all("rough" not in d or d["rough"] for d in spec.to_dict()["corridors"])


@pytest.mark.parametrize("theme, race, seed", [("warren", "", 11), ("mine_delve", "", 4), ("warren", "ogre", 10)])
def test_continuity_passes_on_built_zones(theme, race, seed):
    plan = ZonePlan(name="w9", zone_type="dungeon", room_count=12, layout="graph", dungeon_theme=theme,
                    dungeon_race=race).validate()
    spec = plan_to_spec(plan, seed=seed)
    surf = build_walk_surface(build_mesh(spec).to_ter("w9"), AGENT)
    bad = [c for c in corridor_continuity(surf, spec, AGENT) if not c.connected]
    assert not bad, bad
    h = body_height(race)
    style = load_styles()["rough"]
    assert 3 * h * (1 - 2 * style.corridor_break) >= 2 * h, "2 H clear of a 3 H corridor"
