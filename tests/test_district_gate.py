"""District looks task 5: the three gate failures the districted sweep found, pinned.

Each seed is a districted dungeon with a cave District first, drawn as a generate draws it
(``ZonePlan.from_controls`` then ``plan_to_spec``); the checks read the spec, no build.
"""

import numpy as np
import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.geometry import _bridge_slots, room_doors
from generators.outline import _close_holes
from generators.room_layouts import RoomGrid, _steep_floor
from generators.routing import corridor_route, route_footprint
from generators.semantics import body_height


def _spec(rooms, verticality, purposes, seed):
    plan = ZonePlan.from_controls(
        {"zone_type": "dungeon", "room_count": rooms, "verticality": verticality,
         "layout": "graph", "districts": True, "district_plan": purposes}, [])
    plan.name = "gate"
    return plan_to_spec(plan, seed=seed, warnings=[])


def _room(spec, rid):
    return next(r for r in spec.rooms if r.id == rid)


def _grid(spec, room):
    return RoomGrid(room, room_doors(room, spec, None), _bridge_slots(room, spec),
                    body_height(spec.dungeon_race))


def test_pinhole_collapses_onto_the_throat_corner():
    """A dropped sliver's pinhole collapses onto the vertex on the most rect sides."""
    verts = [(0, 0), (10, 0), (10, 10), (0, 10), (5, 5), (5.1, 5.1), (5, 5.1)]
    # Four Cells round a pinhole (4, 5, 6).
    cells = [[0, 1, 5, 4], [1, 2, 5], [2, 3, 6, 5], [3, 0, 4, 6]]
    rects = [(0, 0, 5, 5.1)]
    out = _close_holes(verts, cells, rects)
    used = {i for c in out for i in c}
    assert 6 in used and not {4, 5} & used
    assert {i for c in _close_holes(verts, cells) for i in c} >= {4}


@pytest.mark.slow
def test_bridge_slot_ceiling_hole_stays_on_the_slot():
    """A pinhole collapsed off the slot's corner, an open seam (first seen at seed 486546126,
    8 dramatic cave+fortress; re-pinned by winding-tunnels task 5 once the cave run moved
    that layout: seed 2103223021 collapses a pinhole by room_1's slot; random placement task 11
    moved its Bridge to room_4; cave clumps task 3's throats left that seed no Bridge: seed 7
    bridges room_7)."""
    spec = _spec(8, "moderate", ["cave", "wizard_lair"], 7)
    room = _room(spec, "room_7")
    slots = _bridge_slots(room, spec)
    assert slots
    o = room.outline
    for cell in o.cells:
        pts = np.array([o.verts[i] for i in cell])
        cx, cy = pts.mean(axis=0)
        for s in slots:
            if s[0] <= cx <= s[2] and s[1] <= cy <= s[3]:
                assert (pts[:, 0] >= s[0] - 0.05).all() and (pts[:, 0] <= s[2] + 0.05).all()
                assert (pts[:, 1] >= s[1] - 0.05).all() and (pts[:, 1] <= s[3] + 0.05).all()


@pytest.mark.slow
def test_props_see_a_slit_in_the_wall(tmp_path):
    """seed 1146655999: a wedge-shaped slit in room_1's wall, narrower than decor's cells,
    read as open floor, and rocks walled floor off behind it."""
    from generators.decor.stock import eq_path_from_env
    if eq_path_from_env() is None:
        pytest.skip("EQ_PATH is not set (no EQ install to read)")
    from analyzer.traverse import validate
    from generators.builder import ZoneBuilder
    from generators.pipeline import _with_decor
    spec = _with_decor(_spec(14, "moderate", ["warren", "cave"], 1146655999))
    res = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)
    report = validate(res.eqg_path, spec=spec)
    assert all(o.ok for o in report.outlines), [o.reason for o in report.outlines if not o.ok]


@pytest.mark.slow
def test_a_slit_in_the_wall_counts_as_wall():
    """seed 1946780458: a 1.1 u slit fell between grid cells, and a boulder under it
    walled floor off."""
    spec = _spec(17, "flat", ["cave", "warren"], 1946780458)
    room = _room(spec, "room_7")
    grid = _grid(spec, room)
    for f in room.features:
        grid.taken |= grid.footprint(f.plan)
    assert grid.doors_stay_joined(np.zeros(grid.gx.shape, bool))


@pytest.mark.slow
def test_clashing_tree_corridors_redraw():
    """seed 1867829545: two tree corridors crossed with no stand-in inside their
    Districts, and were built through each other."""
    spec = _spec(10, "flat", ["wizard_lair", "cave"], 1867829545)
    rooms = {r.id: r for r in spec.rooms}
    feet = [(c, route_footprint(corridor_route(c, rooms), c.width / 2)) for c in spec.corridors]
    for k, (a, fa) in enumerate(feet):
        for b, fb in feet[k + 1:]:
            if {a.from_room, a.to_room} & {b.from_room, b.to_room}:
                continue
            assert not any(min(p[2], q[2]) > max(p[0], q[0]) and min(p[3], q[3]) > max(p[1], q[1])
                           for p in fa for q in fb), (a.id, b.id)


@pytest.mark.slow
def test_floor_poi_stands_on_floor_the_gate_stands_on():
    """A boss POI on a relief wedge steeper than 40 degrees (first seen at seed 1476063938,
    room_9; the cave run moved that layout). Since winding-tunnels task 5 relief leaves no
    such wedge at all (``outline.FAN_GRADE``): seed 124576495 has six rooms with one when it
    is off, and none with it. No POI stands on steep floor either way."""
    spec = _spec(21, "moderate", ["cave", "lava_forge"], 124576495)
    for room in spec.rooms:
        if room.outline is None:
            continue
        grid = _grid(spec, room)
        steep = _steep_floor(grid)
        assert not steep.any(), room.id
        for p in room.pois:
            i = int(np.abs(grid.xs - p.x).argmin())
            j = int(np.abs(grid.ys - p.y).argmin())
            assert not steep[i, j], p
