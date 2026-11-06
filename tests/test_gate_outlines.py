"""Room walls task 2 (Requirement 3; design W4): the gate judges shaped rooms before
any generator makes one.

The rooms are built by hand here, cells on a grid welded like the real thing, so
each break is exactly the one named: a door with no Throat, a wall across a Throat,
a Throat cut off from the Core, and an open seam.
"""

import json

import numpy as np

import analyzer.traverse as T
from analyzer.traverse import AgentModel, build_walk_surface, check_outline, outline_checks
from generators.geometry import MeshBuilder, _ensure_materials
from generators.outline import Outline
from generators.zone_spec import CorridorSpec, RoomSpec, ZoneSpec

AGENT = AgentModel()
HEIGHT = 40.0
CORR_W = 18.0
XS = (-50.0, -20.0, 20.0, 50.0)
YS = (-50.0, -20.0, -9.0, 9.0, 20.0, 50.0)
CORE = (-20.0, -20.0, 20.0, 20.0)
THROAT = (20.0, -9.0, 50.0, 9.0)
# (column, row) grid cells: the Core, the east Throat and a north-west arm.
SHAPE = {(1, 1), (1, 2), (1, 3), (2, 2), (0, 3), (0, 4), (1, 4)}


def _outline(cells=SHAPE, throats=(THROAT,), core=CORE):
    index = {}
    verts = []

    def vid(i, j):
        if (i, j) not in index:
            index[(i, j)] = len(verts)
            verts.append((XS[i], YS[j]))
        return index[(i, j)]
    return Outline(verts=verts,
                   cells=[[vid(c, r), vid(c + 1, r), vid(c + 1, r + 1), vid(c, r + 1)]
                          for c, r in sorted(cells)],
                   core=core, throats=list(throats))


def _spec(outline):
    a = RoomSpec("a", 0.0, 0.0, width=100.0, depth=100.0, height=HEIGHT, open_walls=["E"],
                 outline=outline)
    b = RoomSpec("b", 200.0, 0.0, width=100.0, depth=100.0, height=HEIGHT, open_walls=["W"])
    cor = CorridorSpec("c", 50.0, 0.0, 150.0, 0.0, width=CORR_W, height=HEIGHT - 10,
                       from_room="a", to_room="b")
    spec = ZoneSpec(name="o", zone_type="dungeon", safe_point=(0.0, 0.0, 1.0))
    spec.rooms, spec.corridors = [a, b], [cor]
    _ensure_materials(spec)
    return spec


def _build(spec, cells=SHAPE, skip_wall=None, extra_wall=None, skip_floor=()):
    """The mesh of room a by hand (doors in the E wall), plus b and the corridor."""
    mb = MeshBuilder()
    a = spec.rooms[0]
    fl = mb.material_id(spec.materials[a.floor_material])
    wa = mb.material_id(spec.materials[a.wall_material])
    ce = mb.material_id(spec.materials[a.ceiling_material])
    door_top = spec.corridors[0].height
    for c, r in sorted(cells):
        x0, x1, y0, y1 = XS[c], XS[c + 1], YS[r], YS[r + 1]
        if (c, r) not in skip_floor:
            mb.add_quad((x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0), normal=(0, 0, 1), material=fl)
        mb.add_quad((x0, y1, HEIGHT), (x1, y1, HEIGHT), (x1, y0, HEIGHT), (x0, y0, HEIGHT),
                    normal=(0, 0, -1), material=ce)
        for edge, nb, a0, b0, n in (("S", (c, r - 1), (x0, y0), (x1, y0), (0, 1, 0)),
                                    ("E", (c + 1, r), (x1, y0), (x1, y1), (-1, 0, 0)),
                                    ("N", (c, r + 1), (x1, y1), (x0, y1), (0, -1, 0)),
                                    ("W", (c - 1, r), (x0, y1), (x0, y0), (1, 0, 0))):
            if nb in cells or skip_wall == (c, r, edge):
                continue
            if (c, r, edge) == (2, 2, "E"):     # the door: only a lintel
                mb.add_quad((*a0, door_top), (*a0, HEIGHT), (*b0, HEIGHT), (*b0, door_top),
                            normal=n, material=wa)
                continue
            mb.add_quad((*a0, 0), (*a0, HEIGHT), (*b0, HEIGHT), (*b0, 0), normal=n, material=wa)
    if extra_wall is not None:
        (ax, ay), (bx, by) = extra_wall
        mb.add_quad((ax, ay, 0), (ax, ay, HEIGHT), (bx, by, HEIGHT), (bx, by, 0),
                    normal=(1, 0, 0), material=wa)
    mb.add_room(spec.rooms[1], spec)
    mb.add_corridor(spec.corridors[0], spec)
    return mb.to_ter("o")


def _verdict(ter, spec):
    return check_outline(build_walk_surface(ter, AGENT), spec.rooms[0], spec, AGENT)


def test_a_sound_shaped_room_passes():
    spec = _spec(_outline())
    v = _verdict(_build(spec), spec)
    assert v.ok, v.reason


def test_a_door_with_no_throat_fails():
    spec = _spec(_outline(throats=()))
    v = _verdict(_build(spec), spec)
    assert not v.ok and v.reason.startswith("door without a throat at E -9.0..9.0"), v.reason


def test_a_throat_short_of_the_door_fails():
    spec = _spec(_outline(throats=((20.0, -9.0, 40.0, 9.0),)))
    v = _verdict(_build(spec), spec)
    assert not v.ok and v.reason.startswith("door without a throat"), v.reason


def test_a_throat_narrower_than_the_door_fails():
    spec = _spec(_outline(throats=((20.0, -5.0, 50.0, 5.0),)))
    v = _verdict(_build(spec), spec)
    assert not v.ok and v.reason.startswith("door without a throat"), v.reason


def test_a_throat_that_stops_short_of_the_core_fails():
    spec = _spec(_outline(throats=((30.0, -9.0, 50.0, 9.0),)))
    v = _verdict(_build(spec), spec)
    assert not v.ok and "does not reach the core" in v.reason, v.reason


def test_a_wall_across_a_throat_fails():
    spec = _spec(_outline())
    v = _verdict(_build(spec, extra_wall=((35.0, -9.0), (35.0, 9.0))), spec)
    assert not v.ok and v.reason.startswith("wall across throat"), v.reason


def test_a_gap_in_the_throats_floor_fails():
    spec = _spec(_outline())
    v = _verdict(_build(spec, skip_floor={(2, 2)}), spec)
    assert not v.ok and v.reason.startswith("no walkable path from the core to throat"), v.reason


def test_an_open_seam_fails_and_is_named():
    spec = _spec(_outline())
    v = _verdict(_build(spec, skip_wall=(0, 4, "W")), spec)
    assert not v.ok and v.reason.startswith("open seam at (-50.0"), v.reason


def test_floor_in_a_box_corner_outside_the_outline_is_not_the_rooms():
    """Req 3: a walkable face in the Box but off the Cells doesn't pass for the room."""
    spec = _spec(_outline())
    surf = build_walk_surface(_build(spec, cells=SHAPE | {(2, 4)}), AGENT)
    corner = (surf.centroids[:, 0] > 20) & (surf.centroids[:, 1] > 20) & surf.standable
    assert corner.any(), "the stray floor is in the mesh"
    faces = T._faces_in_room(surf, spec.rooms[0], spec.rooms)
    assert len(faces) and not (surf.centroids[faces, 0] > 20)[surf.centroids[faces, 1] > 20].any()


def test_a_bad_outline_fails_the_report(monkeypatch):
    """The pipeline gates on ``report.passed``, so a bad room fails the build."""
    spec = _spec(_outline())
    ter = _build(spec, skip_wall=(0, 4, "W"))
    monkeypatch.setattr(T, "load_ter_from_eqg", lambda _p: (ter, "o"))
    report = T.validate("o.eqg", spec=spec, agent=AGENT)
    assert report.reachable_rooms == report.total_rooms
    assert not report.passed
    assert "XX outline a" in report.summary() and "open seam" in report.summary()


def test_no_outline_means_no_verdicts():
    spec = _spec(None)
    mb = MeshBuilder()
    for r in spec.rooms:
        mb.add_room(r, spec)
    mb.add_corridor(spec.corridors[0], spec)
    assert outline_checks(build_walk_surface(mb.to_ter("o"), AGENT), spec, AGENT) == []


def test_outline_round_trips_through_the_zone_spec_json_and_is_absent_when_unset():
    spec = _spec(_outline())
    again = ZoneSpec.from_dict(json.loads(json.dumps(spec.to_dict())))
    assert again.rooms[0].outline == spec.rooms[0].outline
    assert "outline" not in spec.to_dict()["rooms"][1]


def test_contains_is_the_cells():
    o = _outline()
    pts = np.array([[0.0, 0.0], [35.0, 0.0], [35.0, 15.0], [-35.0, 35.0], [-35.0, -35.0]])
    assert o.contains(pts).tolist() == [True, True, False, True, False]
