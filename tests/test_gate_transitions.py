"""Room layouts task 18 (Requirement 14.3; design F14): the gate walks through a Transition.

Each break is built by hand, so the check is proved before any generator makes one.
"""

import pytest

from analyzer.traverse import AgentModel, build_walk_surface, check_transition, outline_checks
from generators.geometry import MeshBuilder, _ensure_materials
from generators.zone_spec import CorridorSpec, RoomSpec, Transition, ZoneSpec

AGENT = AgentModel()
LINE = (100.0, 0.0, 0.0)


def _spec(depth=1.0, form="frame"):
    a = RoomSpec("a", 0.0, 0.0, width=100.0, depth=60.0, height=40.0, open_walls=["E"])
    b = RoomSpec("b", 200.0, 0.0, width=100.0, depth=60.0, height=40.0, open_walls=["W"])
    cor = CorridorSpec("c", 50.0, 0.0, 150.0, 0.0, width=18.0, height=30.0, from_room="a", to_room="b",
                       transition=Transition(form, *LINE, along_x=True, depth=depth))
    spec = ZoneSpec(name="t", zone_type="dungeon", safe_point=(0.0, 0.0, 1.0))
    spec.rooms, spec.corridors = [a, b], [cor]
    _ensure_materials(spec)
    return spec


def _box(mb, mat, x0, y0, z0, x1, y1, z1):
    """A closed block."""
    for a, b, n in (((x0, y0), (x1, y0), (0, -1, 0)), ((x1, y0), (x1, y1), (1, 0, 0)),
                    ((x1, y1), (x0, y1), (0, 1, 0)), ((x0, y1), (x0, y0), (-1, 0, 0))):
        mb.add_quad((*b, z0), (*b, z1), (*a, z1), (*a, z0), normal=n, material=mat)
    mb.add_quad((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), normal=(0, 0, 1), material=mat)
    mb.add_quad((x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0), normal=(0, 0, -1), material=mat)


def _verdict(*boxes, extra=None, spec=None):
    spec = spec or _spec()
    mb = MeshBuilder()
    for r in spec.rooms:
        mb.add_room(r, spec)
    mb.add_corridor(spec.corridors[0], spec)
    mat = mb.material_id(spec.materials[spec.rooms[0].wall_material])
    for b in boxes:
        _box(mb, mat, *b)
    if extra:
        extra(mb, mat)
    surf = build_walk_surface(mb.to_ter("t"), AGENT)
    return check_transition(surf, spec.corridors[0], spec, AGENT)


JAMBS = ((99.0, -9.0, 0.0, 101.0, -7.0, 30.0), (99.0, 7.0, 0.0, 101.0, 9.0, 30.0))


def test_an_open_corridor_passes():
    v = _verdict()
    assert v.ok, v.reason


def test_a_good_frame_passes():
    v = _verdict(*JAMBS, (99.0, -7.0, 24.0, 101.0, 7.0, 30.0))
    assert v.ok, v.reason


def test_a_narrow_frame_fails():
    v = _verdict((99.0, -9.0, 0.0, 101.0, -3.0, 30.0), (99.0, 3.0, 0.0, 101.0, 9.0, 30.0))
    assert not v.ok and "clear" in v.reason, v.reason


def test_a_low_lintel_fails():
    v = _verdict(*JAMBS, (99.0, -7.0, 7.0, 101.0, 7.0, 30.0))
    assert not v.ok and "headroom" in v.reason, v.reason


def test_a_step_in_the_way_fails():
    v = _verdict((99.0, -2.0, 0.0, 101.0, 2.0, 5.0))
    assert not v.ok and "a step of" in v.reason, v.reason


def test_an_open_seam_fails():
    def dangling(mb, mat):
        mb.add_quad((100.0, 6.0, 26.0), (100.0, 6.0, 28.0), (100.0, 8.0, 28.0), (100.0, 8.0, 26.0),
                    normal=(-1, 0, 0), material=mat)
    v = _verdict(extra=dangling)
    assert not v.ok and v.reason.startswith("open seam"), v.reason


def test_a_gap_in_the_floor_fails():
    spec = _spec()
    spec.corridors[0].transition.x = 120.0
    mb = MeshBuilder()
    for r in spec.rooms:
        mb.add_room(r, spec)
    surf = build_walk_surface(mb.to_ter("t"), AGENT)     # no corridor at all
    v = check_transition(surf, spec.corridors[0], spec, AGENT)
    assert not v.ok and v.reason.startswith("no floor"), v.reason


def test_a_big_race_needs_more_room():
    """Clear width and headroom are in body heights."""
    spec = _spec()
    spec.dungeon_race = "giant"
    v = _verdict((99.0, -9.0, 0.0, 101.0, -7.0, 30.0), (99.0, 7.0, 0.0, 101.0, 9.0, 30.0), spec=spec)
    assert not v.ok and "clear" in v.reason, v.reason


def test_the_gate_reports_a_corridors_transition():
    spec = _spec()
    mb = MeshBuilder()
    for r in spec.rooms:
        mb.add_room(r, spec)
    mb.add_corridor(spec.corridors[0], spec)
    mat = mb.material_id(spec.materials[spec.rooms[0].wall_material])
    _box(mb, mat, 99.0, -9.0, 0.0, 101.0, -3.0, 30.0)
    _box(mb, mat, 99.0, 3.0, 0.0, 101.0, 9.0, 30.0)
    surf = build_walk_surface(mb.to_ter("t"), AGENT)
    bad = [o for o in outline_checks(surf, spec, AGENT) if not o.ok]
    assert [o.room_id for o in bad] == ["c"]


def test_a_transition_round_trips_through_json_and_only_when_set():
    spec = _spec()
    d = spec.to_dict()
    assert d["corridors"][0]["transition"]["form"] == "frame"
    assert ZoneSpec.from_dict(d).corridors[0].transition == spec.corridors[0].transition
    spec.corridors[0].transition = None
    assert "transition" not in spec.to_dict()["corridors"][0]


@pytest.mark.parametrize("form", ["seam", "frame", "breach"])
def test_the_form_is_named_in_the_reason(form):
    v = _verdict((99.0, -9.0, 0.0, 101.0, -3.0, 30.0), (99.0, 3.0, 0.0, 101.0, 9.0, 30.0), spec=_spec(form=form))
    assert form in v.reason, v.reason
