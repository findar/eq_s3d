"""Room layouts task 19 (Requirements 14.2, 14.6): Seam, Frame and Breach, given by hand in a spec.

The gate from task 18 judges each one, so these say what's in the mesh and that it walks.
"""

import pytest

from analyzer.traverse import AgentModel, build_walk_surface, check_transition
from generators.geometry import MeshBuilder, _ensure_materials
from generators.zone_spec import CorridorSpec, RoomSpec, Transition, ZoneSpec

AGENT = AgentModel()


def _spec(transition=None, rough=0.0, to_z=0.0, steps=0, route="straight"):
    a = RoomSpec("a", 0.0, 0.0, width=100.0, depth=60.0, height=40.0, open_walls=["E"])
    by = 0.0 if route == "straight" else 80.0
    b = RoomSpec("b", 200.0, by, floor_z=to_z, width=100.0, depth=60.0, height=40.0, open_walls=["W"])
    cor = CorridorSpec("c", 50.0, 0.0, 150.0, by, to_z=to_z, width=18.0, height=30.0, from_room="a", to_room="b",
                       steps=steps, rough=rough, transition=transition)
    spec = ZoneSpec(name="t", zone_type="dungeon", safe_point=(0.0, 0.0, 1.0))
    spec.rooms, spec.corridors = [a, b], [cor]
    _ensure_materials(spec)
    spec.add_material("past_floor", "past_floor.dds")
    spec.add_material("past_wall", "past_wall.dds")
    spec.add_material("past_ceiling", "past_ceiling.dds")
    return spec


PAST = dict(floor_material="past_floor", wall_material="past_wall", ceiling_material="past_ceiling")


def _build(spec):
    mb = MeshBuilder()
    for r in spec.rooms:
        mb.add_room(r, spec)
    mb.add_corridor(spec.corridors[0], spec)
    return mb


def _verdict(spec):
    surf = build_walk_surface(_build(spec).to_ter("t"), AGENT)
    return check_transition(surf, spec.corridors[0], spec, AGENT)


def _xs(mb, material):
    """The X span of the corridor's faces in a material."""
    mat = mb.material_id(material)
    pts = [mb.vertices[i] for p in mb.polygons if p.material == mat for i in (p.v1, p.v2, p.v3)]
    return min(v.x for v in pts), max(v.x for v in pts)


def _seam(x=100.0, z=0.0, rough=0.0, **over):
    return Transition("seam", x, 0.0, z, along_x=True, rough=rough, **{**PAST, **over})


@pytest.mark.parametrize("before, after", [(0.0, 0.0), (0.0, 0.2), (0.2, 0.0), (0.2, 0.2)])
def test_a_seam_splits_a_leg_and_the_sections_meet(before, after):
    spec = _spec(_seam(rough=after), rough=before)
    v = _verdict(spec)
    assert v.ok, v.reason
    mb = _build(spec)
    for surface in ("past_floor", "past_wall", "past_ceiling"):
        assert _xs(mb, spec.materials[surface]) == pytest.approx((100.0, 150.0))
    x0, x1 = _xs(mb, spec.materials[spec.corridors[0].wall_material])
    assert x0 <= 50.0 and x1 >= 100.0


def test_a_seam_on_a_ramp_meets_at_the_line():
    spec = _spec(_seam(z=8.0, rough=0.2), to_z=16.0)
    v = _verdict(spec)
    assert v.ok, v.reason


def test_a_seam_meets_on_a_near_straight_route():
    """The two doors differ by a little across the corridor, and both parts keep one line."""
    spec = _spec(_seam(rough=0.2), rough=0.2)
    spec.corridors[0].to_y = 3.0
    v = _verdict(spec)
    assert v.ok, v.reason


def test_a_seam_past_a_bend_changes_the_bends_too():
    spec = _spec(Transition("seam", 100.0, 40.0, 0.0, along_x=False, **PAST), route="z")
    v = _verdict(spec)
    assert v.ok, v.reason
    assert _xs(_build(spec), spec.materials["past_floor"])[1] == pytest.approx(150.0)


def test_a_seam_with_no_room_leaves_one_look():
    spec = _spec(_seam(x=149.9))
    mb = _build(spec)
    assert not any(p.material == mb.material_id(spec.materials["past_wall"]) for p in mb.polygons)


def _frame(**over):
    return Transition("frame", 100.0, 0.0, 0.0, along_x=True, jamb=2.0, lintel=4.0, material="past_wall", **over)


@pytest.mark.parametrize("rough", [0.0, 0.2])
def test_a_frame_stands_closed_and_clear(rough):
    spec = _spec(_frame(), rough=rough)
    v = _verdict(spec)
    assert v.ok, v.reason
    assert _xs(_build(spec), spec.materials["past_wall"]) == pytest.approx((99.0, 101.0))


def test_a_frame_over_a_seam_changes_the_look_too():
    spec = _spec(Transition("frame", 100.0, 0.0, 0.0, along_x=True, jamb=2.0, lintel=4.0, material="past_wall",
                            rough=0.2, **PAST))
    v = _verdict(spec)
    assert v.ok, v.reason
    assert _xs(_build(spec), spec.materials["past_wall"]) == pytest.approx((99.0, 150.0))


def test_a_frame_is_really_narrower_at_the_line():
    """Its jambs are there: too big a frame fails the gate."""
    v = _verdict(_spec(Transition("frame", 100.0, 0.0, 0.0, along_x=True, jamb=7.0, lintel=4.0, material="past_wall")))
    assert not v.ok and "clear" in v.reason, v.reason


def _breach(x=100.0, y=0.0, **over):
    return Transition("breach", x, y, 0.0, along_x=True, depth=1.5, jamb=2.5, material="past_wall", **over)


def test_a_breach_has_uneven_jambs_and_a_flush_floor():
    spec = _spec(_breach())
    v = _verdict(spec)
    assert v.ok, v.reason
    mb = _build(spec)
    mat = mb.material_id(spec.materials["past_wall"])
    ys = {round(mb.vertices[i].y, 3) for p in mb.polygons if p.material == mat for i in (p.v1, p.v2, p.v3)}
    north = max(y for y in ys if y < 0)
    south = min(y for y in ys if y > 0)
    assert abs(north + south) > 0.01          # one side comes in further than the other


def test_a_breach_has_no_lintel():
    spec = _spec(_breach())
    mb = _build(spec)
    mat = mb.material_id(spec.materials["past_wall"])
    spans = [mb.vertices[i].y for p in mb.polygons if p.material == mat for i in (p.v1, p.v2, p.v3)
             if mb.vertices[i].z < 30.0]
    assert not any(-1.0 < y < 1.0 for y in spans)


def test_a_stair_takes_its_frame_at_a_door_with_no_seam():
    spec = _spec(Transition("frame", 53.0, 0.0, 0.0, along_x=True, jamb=2.0, lintel=4.0, material="past_wall", **PAST),
                 to_z=40.0, steps=-1)
    mb = _build(spec)
    assert not any(p.material == mb.material_id(spec.materials["past_floor"]) for p in mb.polygons)
    assert _xs(mb, spec.materials["past_wall"]) == pytest.approx((52.0, 54.0))


def test_a_corridor_with_no_transition_is_built_as_before():
    plain, other = _build(_spec()), _build(_spec(rough=0.0))
    assert [(v.x, v.y, v.z) for v in plain.vertices] == [(v.x, v.y, v.z) for v in other.vertices]
    assert len(plain.polygons) == len(other.polygons)


def test_the_look_past_the_line_round_trips():
    spec = _spec(_seam(rough=0.2))
    assert ZoneSpec.from_dict(spec.to_dict()).corridors[0].transition == spec.corridors[0].transition
