"""
tests/test_corridor_clearance.py
--------------------------------
Corridors stay out of rooms, and corridor bends are walled (M2 task 14).

Two defects showed up when the walkable floor's outline was traced from built
box zones:

1. Rooms sat only half a corridor width apart, so a Z-corridor's full-width
   middle leg reached into both rooms; elevated, that leg is the ramp, so it ran
   under one room's floor and over the other's (stacked floors). Corridors that
   clipped a third room's corner, or crossed another corridor from the same
   room, did the same.
2. A bend square had a floor and ceiling but no walls, so the outer corner of
   every bend was a hole (a ledge in the outline).

`validate(check_corridors=True)` lives in `analyzer/traverse.py` and does not
look at room footprints; the clearance property below is the guard.

Stacked builds (step 7: moderate and dramatic graph dungeons put rooms on
several Levels) keep both checks, Level-aware: a corridor may pass over or
under a room on another storey when the Slab clears it all along (the gate's
rule, as Job B's ``_z_clear`` and ``analyzer.traverse.stacked_rooms``, here
judged piece by piece of the route), and a
build has at most one depth band per Level (bands split only floors that
stack in plan, so a Level standing clear of the others shares a band). A
build on one Level is judged exactly as before: one band (the flat cases pin
it).
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ai.expand import plan_to_spec
from generators.geometry import MeshBuilder
from generators.topology.embed import SLAB
from ai.schema import ZonePlan
from generators import mapgeom
from generators.backends import backend_for
from generators.geometry import build_mesh, _ensure_materials
from generators.layout import LayoutGenerator
from generators.routing import corridor_route, route_footprint
from generators.zone_spec import CorridorSpec, RoomSpec, ZoneSpec
from tests.pbt_helpers import build_settings, scaled
from tests.strategies import (
    box_zone_types, room_counts_wide, seeds, verticality_all,
)

# _wall_point's inset: a corridor starts this far inside its room's wall.
DOOR_INSET = 2.0
TOUCH = 1e-6


def _plan_spec(zone_type, n, verticality, seed):
    plan = ZonePlan(name="clear", zone_type=zone_type, room_count=n,
                    verticality=verticality, elevation=verticality != "flat")
    return plan_to_spec(plan, seed=seed)


def _room_rect(r):
    return (r.center_x - r.width / 2, r.center_y - r.depth / 2,
            r.center_x + r.width / 2, r.center_y + r.depth / 2)


def _overlap(a, b):
    """The intersection of two rects, or None when they only touch."""
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    if x1 - x0 > TOUCH and y1 - y0 > TOUCH:
        return (x0, y0, x1, y1)
    return None


def _doorway_slab(room, route, end, hw):
    """The part of `room` a corridor's footprint may cover at its doorway:
    the end leg's width across, `hw` + the inset deep from the wall
    (`route_footprint` grows each leg by `hw` past its end, and boxes a
    straight leg's small sideways offset between its two openings too)."""
    k = 0 if end == "from" else len(route.axes) - 1
    (ax, ay), (bx, by) = route.waypoints[k], route.waypoints[k + 1]
    ex, ey = route.waypoints[0 if end == "from" else -1]
    x0, y0, x1, y1 = _room_rect(room)
    depth = hw + DOOR_INSET + TOUCH
    w = hw + TOUCH
    if route.axes[k]:
        c0, c1 = min(ay, by) - w, max(ay, by) + w
        if ex >= room.center_x:
            return (x1 - depth, c0, x1, c1)
        return (x0, c0, x0 + depth, c1)
    c0, c1 = min(ax, bx) - w, max(ax, bx) + w
    if ey >= room.center_y:
        return (c0, y1 - depth, c1, y1)
    return (c0, y0, c1, y0 + depth)


def _inside(a, b):
    return (a[0] >= b[0] - TOUCH and a[1] >= b[1] - TOUCH
            and a[2] <= b[2] + TOUCH and a[3] <= b[3] + TOUCH)


def _piece_heights(cor, route):
    """The floor's (lowest, highest) z on each ``route_footprint`` rectangle:
    one per leg, then one per interior corner."""
    wps = list(route.waypoints)
    zs, _ = MeshBuilder._waypoint_zs(wps, None if route.carry < 0 else route.carry,
                                     cor.from_z, cor.to_z)
    legs = [(min(zs[k], zs[k + 1]), max(zs[k], zs[k + 1])) for k in range(len(wps) - 1)]
    return legs + [(zs[i], zs[i]) for i in range(1, len(wps) - 1)]


def _slab_clear(cor, lo, hi, room) -> bool:
    """The corridor's tube (floor to floor + height) lies wholly under the
    room's floor or over its ceiling with the Slab between."""
    return (hi + cor.height + SLAB <= room.floor_z + 1e-6
            or lo >= room.floor_z + room.height + SLAB - 1e-6)


def clearance_violations(spec):
    """Every place a corridor's floor footprint lies inside a room beyond its
    doorway, unless that piece of the corridor passes over or under the room
    with the Slab between (another storey of a stacked build):
    [(corridor id, room id, overlap rect)]."""
    rooms = {r.id: r for r in spec.rooms}
    out = []
    for cor in spec.corridors:
        hw = cor.width / 2
        route = corridor_route(cor, rooms)
        rects = route_footprint(route, hw)
        heights = _piece_heights(cor, route)
        for r in spec.rooms:
            ends = [e for e, rid in (("from", cor.from_room), ("to", cor.to_room))
                    if rid == r.id]
            slabs = [_doorway_slab(r, route, e, hw) for e in ends]
            for rect, (lo, hi) in zip(rects, heights):
                ov = _overlap(rect, _room_rect(r))
                if ov is not None and not any(_inside(ov, s) for s in slabs):
                    if _slab_clear(cor, lo, hi, r):
                        continue
                    out.append((cor.id, r.id, tuple(round(v, 2) for v in ov)))
    return out


def _ter(spec):
    _ensure_materials(spec)
    return backend_for(spec.zone_type).build(spec, "ter_clear", 2)


def _level_count(spec) -> int:
    """The build's Levels: 1 unless its layout block names more."""
    levels = (spec.layout or {}).get("levels") or {}
    return len(set(levels.values())) or 1


def _bands_ok(spec, bands) -> bool:
    """One band on one Level; on several, at least one and at most one per
    Level."""
    n = _level_count(spec)
    return len(bands) == 1 if n == 1 else 1 <= len(bands) <= n


def _bands(spec):
    ter = _ter(spec)
    V, F = mapgeom._arrays(ter)
    tris = V[F[mapgeom.floor_faces(ter)]]
    return mapgeom.depth_bands(mapgeom.FloorSet(tris), spec.safe_point[2])


# The seeds the defects were found on (M2 tasks 4 and 5).
FOUND_ON = [
    ("dungeon", 12, "moderate", 1955208177),
    ("dungeon", 12, "flat", 1516796975),
    ("dungeon", 12, "moderate", 678358326),
    # Seed 7 clipped a third room's corner with a stair's stub until step 7
    # task 12; seed 9 stood in for it after task 11.
    ("dungeon", 30, "moderate", 7),
    ("dungeon", 30, "moderate", 9),
]


@settings(max_examples=scaled(25), deadline=None)
@given(s=seeds, zone_type=box_zone_types, n=room_counts_wide,
       verticality=verticality_all)
def test_corridor_floor_stays_out_of_rooms(s, zone_type, n, verticality):
    """No corridor's floor overlaps a room footprint beyond its doorway inset,
    flat or elevated: not its own two rooms, not a third room."""
    spec = _plan_spec(zone_type, n, verticality, s)
    bad = clearance_violations(spec)
    assert not bad, (f"seed={s} {zone_type} rooms={n} {verticality}: "
                     f"corridor floor inside a room: {bad[:5]}")


@pytest.mark.parametrize("zone_type,n,verticality,seed", FOUND_ON)
def test_found_on_seeds_clear_and_one_band(zone_type, n, verticality, seed):
    spec = _plan_spec(zone_type, n, verticality, seed)
    assert clearance_violations(spec) == []
    bands = _bands(spec)
    assert _bands_ok(spec, bands), (
        f"seed {seed}: {len(bands)} depth bands, {_level_count(spec)} Levels")


@pytest.mark.slow
def test_no_corridor_clips_a_room_over_the_sweep():
    """A stacked edge a third room blocks on every route, after its one split,
    is dropped or swapped (step 7 task 12). It used to be kept, its stub in
    that room's corner: 4 of these 240 builds, all at 30 rooms."""
    builds = [("dungeon", n, v, s) for n in (12, 20, 30)
              for v in ("moderate", "dramatic") for s in range(40)]
    bad = [b for b in builds if clearance_violations(_plan_spec(*b))]
    assert not bad, f"{len(bad)} of {len(builds)} builds: {bad[:5]}"


@pytest.mark.parametrize("rule_set", ["classic_eq", "warren"])
def test_stacked_corridors_clear_each_other_on_their_final_floors(monkeypatch, rule_set):
    """Job B's last word on a stacked build: on the floors it builds, no two
    corridors clash, restored edges included (step 7 task 12)."""
    clashes = []
    build = LayoutGenerator._build_corridors

    def checked(self, spec, rooms, edges):
        if self._stack is not None:
            clashes.extend((a, b) for k, a in enumerate(edges) for b in edges[k + 1:]
                           if self._clash_3d(rooms, a, b))
        return build(self, spec, rooms, edges)

    monkeypatch.setattr(LayoutGenerator, "_build_corridors", checked)
    for n in (15, 30):
        for s in range(8):
            plan = ZonePlan(name="clear", zone_type="dungeon", room_count=n, layout="graph",
                            rule_set=rule_set, verticality="dramatic").validate()
            plan_to_spec(plan, seed=1000 * n + s)
            assert not clashes, (n, s, clashes)


@pytest.mark.slow
@build_settings(15)
@given(s=seeds, zone_type=box_zone_types, n=room_counts_wide,
       verticality=st.sampled_from(["moderate", "dramatic"]))
def test_elevated_box_builds_have_one_band(s, zone_type, n, verticality):
    """A box build stacks floors only by Levels: at most one depth band per
    Level (one for a build on one Level), elevated or not."""
    spec = _plan_spec(zone_type, n, verticality, s)
    bands = _bands(spec)
    assert _bands_ok(spec, bands), (
        f"seed={s} {zone_type} rooms={n} {verticality}: "
        f"{len(bands)} depth bands, {_level_count(spec)} Levels")


def _ledges(spec):
    ter = _ter(spec)
    outline = mapgeom.extract_outline(ter, spec.safe_point)
    return [p for p in outline.polylines if p.kind == "ledge"]


def test_bends_walled_on_flat_seed():
    """A flat zone whose walls are complete has no ledge in its outline; the
    open outer corner of each bend used to show up as one."""
    spec = _plan_spec("dungeon", 12, "flat", 1516796975)
    for room in spec.rooms:
        room.features = []          # a dais's edge is a real ledge; this is about bends
    led = _ledges(spec)
    assert not led, [(p.points[0], round(p.length, 1)) for p in led[:5]]


@pytest.mark.parametrize("dy", [20.0, 60.0, 200.0])
def test_bend_walls_when_jog_is_short_or_long(dy):
    """A Z-corridor whose jog is shorter than its width has two overlapping
    bend squares; their walls must not close the corridor or leave holes."""
    a = RoomSpec("a", center_x=0, center_y=0, width=200, depth=300, height=90)
    b = RoomSpec("b", center_x=320, center_y=dy, width=200, depth=300,
                 height=90)
    a.open_walls.append("E")
    b.open_walls.append("W")
    spec = ZoneSpec(name="t", zone_type="dungeon")
    spec.rooms.extend([a, b])
    spec.corridors.append(CorridorSpec(
        "c", from_x=98, from_y=0, to_x=222, to_y=dy, width=50, height=60,
        from_room="a", to_room="b"))
    spec.safe_point = (0.0, 0.0, 5.0)
    assert corridor_route(spec.corridors[0], {"a": a, "b": b}).kind == "z"
    _ensure_materials(spec)
    ter = build_mesh(spec).to_ter("t")
    outline = mapgeom.extract_outline(ter, spec.safe_point)
    assert not [p for p in outline.polylines if p.kind == "ledge"]
    # Both rooms are reachable: the walls did not seal the corridor.
    pts = np.array([q for p in outline.polylines for q in p.points])
    assert pts[:, 0].max() > 400.0


def stair_or_ramp_violations(spec, gen):
    """Corridors that break the walkable rise: a ramp steeper than run x 0.5
    (``_elevation_run``), or a planned stair (step 7, between Levels) whose
    risers exceed ``RISER_CAP`` or that is built cramped (treads stretched
    under the planned depth)."""
    from generators.geometry import RISER_CAP, is_auto_stair, stair_layout
    rooms = {r.id: r for r in spec.rooms}
    out = []
    for c in spec.corridors:
        if is_auto_stair(c):
            sl = stair_layout(c, rooms)
            if sl is None or sl.plan.riser > RISER_CAP + 1e-6 or sl.cramped:
                out.append((c.id, "stair"))
            continue
        run = gen._elevation_run(rooms[c.from_room], rooms[c.to_room])
        if abs(c.from_z - c.to_z) > run * 0.5 + 0.01:
            out.append((c.id, "ramp"))
    return out


@pytest.mark.parametrize("layout", ["classic", "graph"])
def test_tight_bands_stay_within_grade_cap(layout):
    # Seed 22, 22 dramatic rooms: zero-run Z jogs pin their rooms level, and the
    # relax clamp stalled at a conflicting-neighbours midpoint, leaving corr_0
    # 0.03 u over run * 0.5. The exact projection fallback must clear it.
    # Classic is one Level (every corridor a ramp); the graph build stacks
    # (step 7), its stairs judged by their risers.
    plan = ZonePlan(name="grade22", zone_type="dungeon", room_count=22,
                    elevation=True, verticality="dramatic", layout=layout,
                    dungeon_theme="sunken_ruin", dungeon_race="froglok")
    spec = plan_to_spec(plan, seed=22)
    gen = LayoutGenerator("dungeon")
    gen.race = "froglok"        # the run is measured at the froglok's corridor width
    gen._apply_room_scale(22)
    assert stair_or_ramp_violations(spec, gen) == []
    if layout == "classic":
        assert _level_count(spec) == 1 and all(c.steps >= 0 for c in spec.corridors)
