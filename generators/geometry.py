"""
generators/geometry.py
----------------------
Procedural mesh generation. Converts RoomSpec / CorridorSpec into vertices and
triangles, accumulating them into a MeshBuilder that can emit a TerFile.

Everything is built from axis-aligned boxes (rooms and corridors), with inward-
facing walls so the player sees textured surfaces from inside.

EQ coordinate convention: Z is up. Winding order is counter-clockwise when
viewed from the visible side.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.ter import TerFile, Material, Vertex, Polygon, MAGIC_TERRAIN
from .zone_spec import ZoneSpec, RoomSpec, CorridorSpec, MaterialSpec
from .routing import corridor_route


# A sloped corridor floor is subdivided so each segment rises at most this much
# in Z. A single tall ramp quad splits into two triangles whose centroids sit
# dz/3 apart in Z; the traversability agent (step-up ~3u) then reads its own
# ramp as an unclimbable gap. Fine segments keep every walkable face within a
# small step of its neighbour so a ramp is actually walkable end to end.
MAX_SEG_RISE = 2.5


# ---------------------------------------------------------------------------
# Planned staircases (verticality step 7, Requirement 3)
# ---------------------------------------------------------------------------
#
# A corridor asks for a planned stair with ``steps = AUTO_STAIRS`` (-1): the
# builder picks the risers itself. ``steps = 0`` (ramp) and ``steps > 0`` (a
# hand-picked count spread over the carry leg) build exactly as before. The
# stair constants live here, in one place, set from task 1's survey (design
# finding 7): over 40 stock stairs risers are 1.0 u median and 2.0 u at p90
# (Chardok's all 2.0), and 3 u treads under 2 u risers give the stock median
# grade, 0.67 (34 deg).

# The tallest riser a generated stair uses: under the walk agent's 3 u step-up
# (archive "Stair collision": real treads and risers are the collision).
RISER_CAP = 2.0
# The run of one tread, in world units (over the gate's 2 u minimum).
TREAD_DEPTH = 3.0
# The narrowest lane a switchback flight is built at. A carry leg shorter
# than two lanes can't fold a switchback; it is built as a stretched straight
# stair (``steps`` = the planned risers), which the gate then names.
MIN_LANE = 6.0
# ``CorridorSpec.steps`` value asking for a planned stair.
AUTO_STAIRS = -1


@dataclass(frozen=True)
class StairPlan:
    """How a stair climbs ``rise`` on a carry leg of a given length.

    ``risers`` = ceil(rise / RISER_CAP) and ``run`` = risers × tread for a
    straight stair; when the leg is shorter than that run the stair is a
    Switchback: two flights of half the rise each (``flight_risers`` risers
    apiece, so ``risers`` is even) with a flat landing between them.
    """
    rise: float          # |dz|
    risers: int          # all risers of the stair
    riser: float         # each riser's height (<= the cap)
    tread: float         # each tread's run
    run: float           # the straight stair's run: ceil(rise / cap) × tread
    switchback: bool

    @property
    def flights(self) -> int:
        return 2 if self.switchback else 1

    @property
    def flight_risers(self) -> int:
        return self.risers // self.flights

    @property
    def flight_run(self) -> float:
        return self.flight_risers * self.tread


def stair_plan(rise: float, leg_length: float, *, riser_cap: float = RISER_CAP,
               tread: float = TREAD_DEPTH) -> StairPlan:
    """The stair for ``rise`` (either sign) on a leg ``leg_length`` long:
    straight when the leg holds risers × tread, else a Switchback."""
    rise = abs(rise)
    n = max(1, int(math.ceil(rise / riser_cap - 1e-9)))
    run = n * tread
    if leg_length + 1e-6 >= run:
        return StairPlan(rise, n, rise / n, tread, run, False)
    m = int(math.ceil(n / 2))
    return StairPlan(rise, 2 * m, rise / (2 * m), tread, run, True)


def is_auto_stair(cor: CorridorSpec) -> bool:
    """True when ``cor`` asks for a planned stair and has a rise to climb."""
    return cor.steps < 0 and abs(cor.to_z - cor.from_z) > 0.01


@dataclass(frozen=True)
class StairLayout:
    """Where a planned stair sits on its route (``stair_layout``).

    ``start``/``end`` are the carry leg's built span in route order (from_z
    at ``start``). A straight stair is one flight centred on that span. A
    Switchback folds into a stairwell box beside the span: two lanes
    ``lane`` wide side by side along the leg (at its ``placement`` end); the
    walk turns out of the leg into lane 1, climbs flight 1 away from the leg,
    crosses the landing, climbs flight 2 back in lane 2 and rejoins the leg.
    ``side`` is the cross-axis direction (+1/-1) the stairwell lies on, and
    ``stairwell`` its plan rectangle (x0, y0, x1, y1): the box task 5 keeps
    clear of rooms. ``path`` is the walk's centreline through the leg, in
    route order, and ``profile`` the stair's pitch line along it as (arc
    length from ``path[0]``, z) breakpoints: level, each flight from its first
    tread's start to its last riser, level. The built floor is within one
    riser of it everywhere. ``cramped``: the leg can't hold even two lanes,
    so the stair is built straight with ``plan.risers`` stretched over the leg
    (its profile is then linear over the leg).
    """
    plan: StairPlan
    carry: int
    along_x: bool
    start: Tuple[float, float]
    end: Tuple[float, float]
    from_z: float
    to_z: float
    lane: float
    side: int = 0
    placement: str = ""
    stairwell: Optional[Tuple[float, float, float, float]] = None
    path: Tuple[Tuple[float, float], ...] = ()
    profile: Tuple[Tuple[float, float], ...] = ()
    cramped: bool = False


def stair_layout(cor: CorridorSpec, rooms) -> Optional[StairLayout]:
    """The planned stair of ``cor`` on its route, or None when ``cor`` isn't
    a planned stair (``steps`` >= 0, or no rise). ``rooms`` maps room id to
    RoomSpec, as for ``corridor_route``."""
    if not is_auto_stair(cor):
        return None
    route = corridor_route(cor, rooms)
    carry = None if route.carry < 0 else route.carry
    return _layout_stair(list(route.waypoints), list(route.axes), carry,
                         cor.from_z, cor.to_z, cor.width / 2,
                         avoid=_room_rects(rooms.values()))


def _room_rects(rooms):
    """Room footprints as (x0, y0, x1, y1): what a stairwell keeps off."""
    out = []
    for r in rooms:
        (x0, y0, _), (x1, y1, _) = r.bounds
        out.append((x0, y0, x1, y1))
    return out


def _uv_to_xy(along_x: bool, u: float, v: float) -> Tuple[float, float]:
    """A leg's (along, cross) coordinates to world XY."""
    return (u, v) if along_x else (v, u)


def _uv_rect(along_x, u0, u1, v0, v1):
    """An (along, cross) rectangle as a world (x0, y0, x1, y1)."""
    ua, ub = min(u0, u1), max(u0, u1)
    va, vb = min(v0, v1), max(v0, v1)
    return (ua, va, ub, vb) if along_x else (va, ua, vb, ub)


def _overlap_area(a, b) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 1e-6 and h > 1e-6 else 0.0


def _layout_stair(waypoints, axes, carry, from_z, to_z, hw, avoid=()
                  ) -> Optional[StairLayout]:
    """``stair_layout`` on a route's waypoints (``carry`` None = longest).
    A Switchback's stairwell goes at the end and side of the leg that
    overlaps least of the route's other legs and the ``avoid`` rectangles
    (room footprints); the first of start/+, start/-, end/+, end/- on a tie."""
    zs, carry = MeshBuilder._waypoint_zs(waypoints, carry, from_z, to_z)
    ends = MeshBuilder._leg_ends(waypoints, carry, hw, zs)
    if ends is None:
        return None
    (sx, sy), (ex, ey) = ends
    along_x = axes[carry]
    us, ue = (sx, ex) if along_x else (sy, ey)
    c = sy if along_x else sx
    length = abs(ue - us)
    if length < 1e-6:
        return None
    z0, z1 = zs[carry], zs[carry + 1]
    plan = stair_plan(z1 - z0, length)
    base = dict(plan=plan, carry=carry, along_x=along_x, start=ends[0],
                end=ends[1], from_z=z0, to_z=z1)
    if not plan.switchback:
        fa = (length - plan.run) / 2
        return StairLayout(lane=2 * hw, path=(ends[0], ends[1]),
                           profile=((0.0, z0), (fa, z0), (fa + plan.run, z1),
                                    (length, z1)), **base)
    lane = min(2 * hw, length / 2)
    if lane < MIN_LANE:
        return StairLayout(lane=lane, path=(ends[0], ends[1]), cramped=True,
                           profile=((0.0, z0), (length, z1)), **base)

    d = 1.0 if ue > us else -1.0
    depth = plan.flight_run + lane
    # The route's other legs (bend squares included) and the rooms: the
    # stairwell keeps off them where it can.
    others = list(avoid)
    for k in range(len(waypoints) - 1):
        if k == carry:
            continue
        (ax, ay), (bx, by) = waypoints[k], waypoints[k + 1]
        others.append((min(ax, bx) - hw, min(ay, by) - hw,
                       max(ax, bx) + hw, max(ay, by) + hw))
    best = None
    for placement in ("start", "end"):
        a1 = us if placement == "start" else ue - 2 * d * lane
        for side in (1, -1):
            ve = c + side * hw
            rect = _uv_rect(along_x, a1, a1 + 2 * d * lane, ve, ve + side * depth)
            cost = sum(_overlap_area(rect, o) for o in others)
            if best is None or cost < best[0] - 1e-9:
                best = (cost, placement, side, a1, rect)
    _, placement, side, a1, rect = best
    ve = c + side * hw
    u1 = a1 + d * lane / 2           # lane 1's centre line
    u2 = a1 + 1.5 * d * lane         # lane 2's
    vl = ve + side * (plan.flight_run + lane / 2)   # across the landing
    path = (ends[0], _uv_to_xy(along_x, u1, c), _uv_to_xy(along_x, u1, vl),
            _uv_to_xy(along_x, u2, vl), _uv_to_xy(along_x, u2, c), ends[1])
    cum = [0.0]
    for p, q in zip(path, path[1:]):
        cum.append(cum[-1] + abs(q[0] - p[0]) + abs(q[1] - p[1]))
    zm = (z0 + z1) / 2
    fr = plan.flight_run
    f1 = cum[1] + hw                 # flight 1 leaves the leg's edge
    f2 = cum[3] + lane / 2           # flight 2 leaves the landing's edge
    profile = ((0.0, z0), (f1, z0), (f1 + fr, zm), (f2, zm), (f2 + fr, z1),
               (cum[-1], z1))
    return StairLayout(lane=lane, side=side, placement=placement,
                       stairwell=rect, path=path, profile=profile, **base)


# ---------------------------------------------------------------------------
# Bridges (verticality step 7 task 11, Requirement 3.4)
# ---------------------------------------------------------------------------
#
# A Bridge is a corridor between two rooms on one Level that crosses a lower
# room's footprint; ``CorridorSpec.bridge`` names that room. The deck runs at
# the corridor's own height, ABOVE the lower room's ceiling: a stacked layout
# keeps the Slab between every upper floor and every lower ceiling, so the
# deck always fits and the lower room keeps its height (nothing of it changes
# but its ceiling). The lower room's ceiling is cut open in a slot under the
# deck and ``margin`` either side of it, so the void reads from both levels:
# from below, a slot in the roof with the deck across it; from the deck, a
# drop past the rails into the room. The slot is a shaft up to the corridor's
# ceiling: side walls ``margin`` off the deck from the lower ceiling to the
# corridor's ceiling, the corridor's ceiling spanning the shaft, and each end
# closed down to the lower ceiling round the deck (where the corridor goes on
# past the room's wall, round the tube's opening; at a doorway, back to back
# with the room's wall). The deck is a slab DECK_THICKNESS thick with a low
# wall (rail) on each edge, RAIL_SHARE of the corridor's height (the corridor
# is 2.5 H tall, so 0.6 H) and never under RAIL_MIN (over the walk agent's
# 3 u step-up, so the walk can't step onto a rail). Falling past a rail lands
# in the room below, which the gate requires reachable on foot anyway.

#: The deck slab's thickness (its underside is the lower room's view of it).
DECK_THICKNESS = 2.0
#: A rail's height as a share of the corridor's height, and its least height.
RAIL_SHARE = 0.24
RAIL_MIN = 3.5
#: The lower room's ceiling kept either side of the slot, in corridor
#: half-widths; the slot's margin either side of the deck is one half-width,
#: never less than MIN_MARGIN of one (else no bridge).
LEDGE = 0.5
MIN_MARGIN = 0.5


@dataclass(frozen=True)
class BridgeLayout:
    """Where a Bridge's deck and slot sit (``bridge_layout``).

    The deck is leg ``leg`` of the corridor's route (along X when
    ``along_x``, on the cross line ``cross``) between ``s0`` and ``s1``
    along that axis (s0 < s1): the stretch over the bridged ``room``. Its
    floor is ``z0`` at s0 and ``z1`` at s1 (linear: a ramp's slope goes
    through). ``ends`` says what closes each end: ``"wall"`` (the room's
    wall, the corridor going on past it) or ``"door"`` (the doorway of the
    room the corridor ends in). ``ceiling`` is the bridged room's ceiling,
    ``margin`` the open slot either side of the deck, ``rail`` the rails'
    height and ``top`` the shaft's highest point (the corridor's ceiling).
    """
    room: str
    leg: int
    along_x: bool
    cross: float
    s0: float
    s1: float
    z0: float
    z1: float
    hw: float
    margin: float
    ceiling: float
    ends: Tuple[str, str]
    rail: float
    top: float

    @property
    def slot(self) -> Tuple[float, float, float, float]:
        """The opening cut in the room's ceiling, (x0, y0, x1, y1)."""
        w = self.hw + self.margin
        return _uv_rect(self.along_x, self.s0, self.s1, self.cross - w, self.cross + w)

    def z_at(self, s: float) -> float:
        """The deck's floor height at ``s`` along the leg."""
        if self.s1 - self.s0 <= 1e-9:
            return self.z0
        return self.z0 + (self.z1 - self.z0) * (s - self.s0) / (self.s1 - self.s0)


def bridge_layout(cor: CorridorSpec, rooms) -> Optional[BridgeLayout]:
    """The Bridge ``cor`` makes over the room ``cor.bridge`` names, or None
    when it can't make one: not a bridge, a stair (``steps`` != 0), the room
    missing or one of its own, a route that doesn't cross the room on exactly
    one leg (or turns inside it), a slot that doesn't fit (``MIN_MARGIN``
    within the room's ``LEDGE``, and at a doorway within that room's wall), a
    deck shorter than it is wide, or a deck less than the Slab over the
    room's ceiling. ``rooms`` maps room id
    to RoomSpec, as for ``corridor_route``. The builder builds from it and
    the layout plans with it, so the two agree."""
    if not cor.bridge or cor.steps != 0 or cor.bridge in (cor.from_room, cor.to_room):
        return None
    room = rooms.get(cor.bridge)
    if room is None:
        return None
    from .topology.embed import SLAB
    route = corridor_route(cor, rooms)
    wps = list(route.waypoints)
    axes = list(route.axes)
    zs, _carry = MeshBuilder._waypoint_zs(wps, None if route.carry < 0 else route.carry,
                                          cor.from_z, cor.to_z)
    hw = cor.width / 2
    (rx0, ry0, _), (rx1, ry1, _) = room.bounds
    fp = (rx0, ry0, rx1, ry1)
    for i in range(1, len(wps) - 1):
        if _overlap_area(MeshBuilder._bend_square(wps, i, hw), fp) > 0:
            return None
    hits = []
    for k in range(len(wps) - 1):
        ends = MeshBuilder._leg_ends(wps, k, hw, zs)
        if ends is None:
            continue
        (ax, ay), (bx, by) = ends
        if axes[k]:
            rect = (min(ax, bx), ay - hw, max(ax, bx), ay + hw)
        else:
            rect = (ax - hw, min(ay, by), ax + hw, max(ay, by))
        if _overlap_area(rect, fp) > 0:
            hits.append((k, ends))
    if len(hits) != 1:
        return None
    k, ((ax, ay), (bx, by)) = hits[0]
    along_x = axes[k]
    ua, ub = (ax, bx) if along_x else (ay, by)
    c = ay if along_x else ax
    h_lo, h_hi = (rx0, rx1) if along_x else (ry0, ry1)
    c_lo, c_hi = (ry0, ry1) if along_x else (rx0, rx1)
    lo, hi = min(ua, ub), max(ua, ub)
    s0, s1 = max(lo, h_lo), min(hi, h_hi)

    def z_leg(u):
        if abs(ub - ua) <= 1e-9:
            return zs[k]
        return zs[k] + (zs[k + 1] - zs[k]) * (u - ua) / (ub - ua)

    margin = min(hw, (c - hw) - (c_lo + LEDGE * hw), (c_hi - LEDGE * hw) - (c + hw))
    end_kind = []
    for low, s, past in ((True, s0, h_lo > lo + 1e-6), (False, s1, h_hi < hi - 1e-6)):
        if past:
            end_kind.append("wall")
            continue
        # The deck ends at the leg's own end there: a doorway, or no bridge.
        wp = k if abs(s - ua) <= 1e-6 else k + 1
        if wp not in (0, len(wps) - 1):
            return None
        door = rooms.get(cor.from_room if wp == 0 else cor.to_room)
        if door is None:
            return None
        (dx0, dy0, _), (dx1, dy1, _) = door.bounds
        d_lo, d_hi = (dy0, dy1) if along_x else (dx0, dx1)
        margin = min(margin, (c - hw) - d_lo, d_hi - (c + hw))
        # The doorway sits a little inside its room's wall: the slot starts
        # at the wall, so the room's own floor stays whole.
        a_lo, a_hi = (dx0, dx1) if along_x else (dy0, dy1)
        if low:
            s0 = max(s0, a_hi)
        else:
            s1 = min(s1, a_lo)
        end_kind.append("door")
    if margin < MIN_MARGIN * hw - 1e-9 or s1 - s0 < 2 * hw - 1e-9:
        return None
    z0, z1 = z_leg(s0), z_leg(s1)
    ceiling = room.floor_z + room.height
    if min(z0, z1) - ceiling < SLAB - 1e-6:
        return None
    rail = min(max(RAIL_MIN, RAIL_SHARE * cor.height), cor.height / 2)
    return BridgeLayout(room=room.id, leg=k, along_x=along_x, cross=c, s0=s0, s1=s1,
                        z0=z0, z1=z1, hw=hw, margin=margin, ceiling=ceiling,
                        ends=(end_kind[0], end_kind[1]), rail=rail,
                        top=max(z0, z1) + cor.height)


def _bridge_slots(room: RoomSpec, spec: ZoneSpec):
    """The slots Bridges cut in ``room``'s ceiling (none for every room no
    corridor bridges, so those build exactly as before)."""
    bridging = [c for c in spec.corridors if c.bridge == room.id]
    if not bridging:
        return []
    rooms = {r.id: r for r in spec.rooms}
    out = []
    for c in bridging:
        bl = bridge_layout(c, rooms)
        if bl is not None:
            out.append(bl.slot)
    return out


def _ceiling_cells(x0, y0, x1, y1, holes):
    """The rectangle (x0, y0, x1, y1) less the ``holes``, as grid cells."""
    xs = sorted({x0, x1, *(min(x1, max(x0, v)) for h in holes for v in (h[0], h[2]))})
    ys = sorted({y0, y1, *(min(y1, max(y0, v)) for h in holes for v in (h[1], h[3]))})
    out = []
    for xa, xb in zip(xs, xs[1:]):
        for ya, yb in zip(ys, ys[1:]):
            mx, my = (xa + xb) / 2, (ya + yb) / 2
            if any(h[0] < mx < h[2] and h[1] < my < h[3] for h in holes):
                continue
            out.append((xa, ya, xb, yb))
    return out


# ---------------------------------------------------------------------------
# Mesh builder
# ---------------------------------------------------------------------------

# UV units per world unit when a material has no texel_density: one texture
# repeat per 100 u (the box backend's scale before interesting textures).
DEFAULT_UV_SCALE = 0.01
ROUGH_SPACING = 16.0    # a rough corridor's walls bend about this often (u)
STEP_WIDTH = 14.0   # a dais's steps are this wide, or most of its side (u)
WALL_ROW = 14.0     # a shaped room's walls come in rows about this tall (the era's edge)


class MeshBuilder:
    """
    Accumulates geometry and resolves materials, then emits a TerFile.

    Vertices are deduplicated only implicitly (each quad adds its own 4 verts).
    This keeps the generator simple; the resulting mesh is still valid.
    """

    def __init__(self):
        self.vertices: List[Vertex] = []
        self.polygons: List[Polygon] = []
        self._material_index: Dict[str, int] = {}
        self.materials: List[Material] = []
        self._uv_scale: Dict[int, float] = {}   # material index -> UV per world unit

    # ------------------------------------------------------------------
    # Material resolution
    # ------------------------------------------------------------------

    def material_id(self, mat_spec: MaterialSpec) -> int:
        """Return the index for a material, registering it if new. A material
        with a ``texel_density`` (world units per repeat) maps its UVs at that
        scale; without one, at ``DEFAULT_UV_SCALE`` (100 u per repeat)."""
        if mat_spec.name in self._material_index:
            return self._material_index[mat_spec.name]
        idx = len(self.materials)
        mat = Material(index=idx, name=mat_spec.name, shader=mat_spec.shader)
        mat.add_diffuse(mat_spec.texture)
        self.materials.append(mat)
        self._material_index[mat_spec.name] = idx
        density = getattr(mat_spec, "texel_density", None)
        self._uv_scale[idx] = 1.0 / density if density else DEFAULT_UV_SCALE
        return idx

    # ------------------------------------------------------------------
    # Primitive: a textured quad (two triangles)
    # ------------------------------------------------------------------

    def add_quad(self,
                 p0: Tuple[float, float, float],
                 p1: Tuple[float, float, float],
                 p2: Tuple[float, float, float],
                 p3: Tuple[float, float, float],
                 normal: Tuple[float, float, float],
                 material: int,
                 uv_scale: Optional[float] = None,
                 flags: int = 0) -> None:
        """
        Add a quad defined by four corners in CCW order (viewed from the
        visible side, i.e. the side the normal points toward).

        UVs are planar-projected based on world position * uv_scale so textures
        tile consistently regardless of surface size. ``uv_scale`` defaults to
        the material's own (its ``texel_density``, see ``material_id``). A wall follows EQ's
        (Direct3D) convention as stock zones do: ``v`` grows down the wall, so
        the texture's top row is at the top, and ``u`` grows to the right of a
        viewer facing the visible side, so the texture isn't mirrored.
        """
        base = len(self.vertices)
        corners = [p0, p1, p2, p3]
        if uv_scale is None:
            uv_scale = self._uv_scale.get(material, DEFAULT_UV_SCALE)

        nx, ny, nz = (abs(normal[0]), abs(normal[1]), abs(normal[2]))
        if nz >= nx and nz >= ny and normal[2] > 0:
            # Floor, seen from above: u along +X, v down the screen (-Y), so
            # a texture reads unmirrored with +Y ahead.
            def uv(cx, cy, cz):
                return cx * uv_scale, -cy * uv_scale
        elif nz >= nx and nz >= ny:
            # Ceiling, seen from below: planar XY already reads unmirrored.
            def uv(cx, cy, cz):
                return cx * uv_scale, cy * uv_scale
        else:
            # Wall: the viewer faces -normal; their right is (-normal) × up.
            h = math.hypot(normal[0], normal[1])
            rx, ry = -normal[1] / h, normal[0] / h

            def uv(cx, cy, cz):
                return (cx * rx + cy * ry) * uv_scale, -cz * uv_scale

        for cx, cy, cz in corners:
            u, v = uv(cx, cy, cz)
            self.vertices.append(Vertex(
                x=cx, y=cy, z=cz,
                nx=normal[0], ny=normal[1], nz=normal[2],
                u=u, v=v,
            ))

        # Two triangles: (0,1,2) and (0,2,3)
        self.polygons.append(Polygon(base + 0, base + 1, base + 2, material, flags))
        self.polygons.append(Polygon(base + 0, base + 2, base + 3, material, flags))

    # ------------------------------------------------------------------
    # Primitive: a hollow box room
    # ------------------------------------------------------------------

    def add_room(self, room: RoomSpec, spec: ZoneSpec,
                 extra_doors: Optional[Dict[str, List[Tuple[float, float, float]]]] = None
                 ) -> None:
        """Build a hollow box with inward-facing walls, floor, and ceiling.

        ``extra_doors`` adds openings no corridor in the spec makes, as
        ``{side: [(c0, c1, top), ...]}`` like ``_door_openings`` (an outdoor
        dungeon's Tunnel); the side must be in ``room.open_walls``. A room with
        an Outline builds from that instead (``add_outline_room``). What stands in the room
        (its Features) is built either way."""
        self._add_features(room, spec)
        if room.outline is not None:
            self.add_outline_room(room, spec, extra_doors)
            return
        (x0, y0, z0), (x1, y1, z1) = room.bounds

        floor_mat   = self.material_id(spec.materials[room.floor_material])
        wall_mat    = self.material_id(spec.materials[room.wall_material])
        ceiling_mat = self.material_id(spec.materials[room.ceiling_material])

        # Floor — normal points up (+Z), CCW from above
        self.add_quad(
            (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
            normal=(0, 0, 1), material=floor_mat,
        )
        # Ceiling — normal points down (-Z), CCW from below. A room a Bridge
        # crosses has the bridge's slot cut out of it (``bridge_layout``).
        slots = _bridge_slots(room, spec)
        for cx0, cy0, cx1, cy1 in (_ceiling_cells(x0, y0, x1, y1, slots) if slots
                                   else [(x0, y0, x1, y1)]):
            self.add_quad(
                (cx0, cy1, z1), (cx1, cy1, z1), (cx1, cy0, z1), (cx0, cy0, z1),
                normal=(0, 0, -1), material=ceiling_mat,
            )

        # Walls (inward-facing). A side in open_walls is cut only where a
        # corridor meets it: wall pieces either side of each doorway and a
        # lintel above it, so the floor never ends at a drop beside a door. An
        # open side no corridor reaches (hand-authored specs) stays fully open.
        doors = _door_openings(room, spec)
        for side, cuts in (extra_doors or {}).items():
            doors.setdefault(side, []).extend(cuts)
        extents = {
            "S": (x0, x1), "N": (x0, x1),   # along X
            "W": (y0, y1), "E": (y0, y1),   # along Y
        }
        for side in ("S", "N", "W", "E"):
            lo, hi = extents[side]
            if side not in room.open_walls:
                self._add_room_wall(room, side, lo, hi, z0, z1, wall_mat)
                continue
            cuts = _merge_openings(doors.get(side, []), lo, hi)
            if not cuts:
                continue
            pos = lo
            for c0, c1, top in cuts:
                if c0 > pos:
                    self._add_room_wall(room, side, pos, c0, z0, z1, wall_mat)
                if top < z1:
                    self._add_room_wall(room, side, c0, c1, top, z1, wall_mat)
                pos = c1
            if pos < hi:
                self._add_room_wall(room, side, pos, hi, z0, z1, wall_mat)

    def _add_room_wall(self, room: RoomSpec, side: str, a: float, b: float,
                       lo: float, hi: float, wall_mat: int) -> None:
        """One inward-facing rectangle of a room wall, spanning a..b along the
        wall (a < b) and lo..hi in Z. Corner order matches the whole-wall quads
        so an uncut wall is byte-identical to the historic build."""
        (x0, y0, _), (x1, y1, _) = room.bounds
        if side == "S":     # y = y0, normal +Y
            self.add_quad((a, y0, lo), (a, y0, hi), (b, y0, hi), (b, y0, lo),
                          normal=(0, 1, 0), material=wall_mat)
        elif side == "N":   # y = y1, normal -Y
            self.add_quad((b, y1, lo), (b, y1, hi), (a, y1, hi), (a, y1, lo),
                          normal=(0, -1, 0), material=wall_mat)
        elif side == "W":   # x = x0, normal +X
            self.add_quad((x0, b, lo), (x0, b, hi), (x0, a, hi), (x0, a, lo),
                          normal=(1, 0, 0), material=wall_mat)
        else:               # "E": x = x1, normal -X
            self.add_quad((x1, a, lo), (x1, a, hi), (x1, b, hi), (x1, b, lo),
                          normal=(-1, 0, 0), material=wall_mat)

    # ------------------------------------------------------------------
    # Primitive: what stands in a room (step 9, generators/room_features.py)
    # ------------------------------------------------------------------

    def _add_features(self, room: RoomSpec, spec: ZoneSpec) -> None:
        if not room.features:
            return
        wall_mat = self.material_id(spec.materials[room.wall_material])
        floor_mat = self.material_id(spec.materials[room.floor_material])
        for feat in room.features:
            top = feat.height if feat.height > 0 else room.height
            self._add_solid(feat.plan, room.floor_z, room.floor_z + top, wall_mat,
                            floor_mat if feat.kind == "dais" else wall_mat,
                            walkable=feat.kind == "dais")
            if feat.kind == "dais":
                self._add_dais_steps(feat, room, wall_mat, floor_mat)

    def _add_solid(self, plan, z0, z1, side_mat, top_mat, walkable=False) -> None:
        """A closed solid over ``plan``, from z0 to z1. Its foot and head stand past a moving
        floor or ceiling, so those meet it with no gap. Its caps close it; only a walkable
        top faces up, so nothing else reads as floor."""
        # Long sides split to the era's edge, in the caps too, so there's no T-junction.
        pts = []
        for a, b in zip(plan, list(plan[1:]) + list(plan[:1])):
            pieces = max(1, math.ceil(math.hypot(b[0] - a[0], b[1] - a[1]) / WALL_ROW))
            pts += [(a[0] + (b[0] - a[0]) * k / pieces, a[1] + (b[1] - a[1]) * k / pieces) for k in range(pieces)]
        rows = max(1, math.ceil((z1 - z0) / WALL_ROW))
        scale = self._uv_scale[side_mat]
        along = 0.0
        for k in range(len(pts)):
            b, a = pts[k], pts[(k + 1) % len(pts)]      # reversed, so the floor outside is on the left
            run = math.hypot(b[0] - a[0], b[1] - a[1])
            if run < 1e-9:
                continue
            normal = (-(b[1] - a[1]) / run, (b[0] - a[0]) / run, 0.0)
            for row in range(rows):
                lo, hi = z0 + (z1 - z0) * row / rows, z0 + (z1 - z0) * (row + 1) / rows
                self._add_face([(a[0], a[1], lo), (a[0], a[1], hi), (b[0], b[1], hi), (b[0], b[1], lo)],
                               [(-along * scale, -lo * scale), (-along * scale, -hi * scale),
                                (-(along + run) * scale, -hi * scale), (-(along + run) * scale, -lo * scale)],
                               normal, side_mat)
            along += run
        cx, cy = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
        top_uv = self._uv_scale[top_mat]
        for a, b in zip(pts, pts[1:] + pts[:1]):
            tri = [(cx, cy), a, b] if walkable else [(cx, cy), b, a]
            self._add_face([(x, y, z1) for x, y in tri], [(x * top_uv, -y * top_uv) for x, y in tri],
                           (0, 0, 1 if walkable else -1), top_mat)
            tri = [(cx, cy), b, a]
            self._add_face([(x, y, z0) for x, y in tri], [(x * top_uv, -y * top_uv) for x, y in tri],
                           (0, 0, -1), top_mat)

    def _add_dais_steps(self, feat, room: RoomSpec, wall_mat: int, floor_mat: int) -> None:
        """Steps up the dais's ``steps_side``: each a closed block, the lowest furthest out. A
        dais within one step-up needs none."""
        n = dais_steps(feat.height)
        if n == 0 or not feat.steps_side:
            return
        for k, plan in enumerate(step_plans(feat, n)):
            self._add_solid(plan, room.floor_z, room.floor_z + feat.height * (k + 1) / (n + 1),
                            wall_mat, floor_mat, walkable=True)

    # ------------------------------------------------------------------
    # Primitive: a shaped room (step 8, generators/outline.py)
    # ------------------------------------------------------------------

    def _add_face(self, corners, uvs, normal, material: int) -> None:
        """A convex face with its own texture coordinates, fanned from corner 0."""
        base = len(self.vertices)
        for (cx, cy, cz), (u, v) in zip(corners, uvs):
            self.vertices.append(Vertex(x=cx, y=cy, z=cz, nx=normal[0], ny=normal[1],
                                        nz=normal[2], u=u, v=v))
        for k in range(1, len(corners) - 1):
            self.polygons.append(Polygon(base, base + k, base + k + 1, material, 0))

    def add_outline_room(self, room: RoomSpec, spec: ZoneSpec,
                         extra_doors: Optional[Dict[str, List[Tuple[float, float, float]]]] = None
                         ) -> None:
        """Vertical walls over the room's Outline, a floor and a ceiling meeting
        them on shared vertices. Every Cell fans from its centre, so its edges
        stay whole. Wall texture runs on round a bend: its U is the distance
        along the wall, not each face's own projection."""
        (x0, y0, z0), (x1, y1, z1) = room.bounds
        outline = room.outline
        floor_mat = self.material_id(spec.materials[room.floor_material])
        wall_mat = self.material_id(spec.materials[room.wall_material])
        ceiling_mat = self.material_id(spec.materials[room.ceiling_material])
        slots = _bridge_slots(room, spec)

        def under_slot(cx, cy):
            return any(s[0] <= cx <= s[2] and s[1] <= cy <= s[3] for s in slots)

        floor_uv = self._uv_scale[floor_mat]
        ceiling_uv = self._uv_scale[ceiling_mat]
        floor_at: Dict[Tuple[float, float], int] = {}
        ceiling_at: Dict[Tuple[float, float], int] = {}

        def vertex(at, x, y, z, nz, uv):
            """One vertex per point, so the walk gate sees one welded floor."""
            k = at.get((x, y))
            if k is None:
                k = at[(x, y)] = len(self.vertices)
                u, v = uv
                self.vertices.append(Vertex(x=x, y=y, z=z, nx=0, ny=0, nz=nz, u=u, v=v))
            return k

        for cell in outline.cells:
            pts = [outline.verts[i] for i in cell]
            lifts = [outline.lift_at(i) for i in cell]
            drops = [outline.drop_at(i) for i in cell]
            cx, cy = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
            mid_lift, mid_drop = sum(lifts) / len(cell), sum(drops) / len(cell)
            open_above = under_slot(cx, cy)
            for k, ((ax, ay), (bx, by)) in enumerate(zip(pts, pts[1:] + pts[:1])):
                k2 = (k + 1) % len(cell)
                f = [vertex(floor_at, x, y, z0 + rise, 1, (x * floor_uv, -y * floor_uv))
                     for x, y, rise in ((cx, cy, mid_lift), (ax, ay, lifts[k]), (bx, by, lifts[k2]))]
                self.polygons.append(Polygon(f[0], f[1], f[2], floor_mat, 0))
                if not open_above:
                    c = [vertex(ceiling_at, x, y, z1 - fall, -1, (x * ceiling_uv, y * ceiling_uv))
                         for x, y, fall in ((bx, by, drops[k2]), (ax, ay, drops[k]), (cx, cy, mid_drop))]
                    self.polygons.append(Polygon(c[0], c[1], c[2], ceiling_mat, 0))

        doors = _door_openings(room, spec)
        for side, cuts in (extra_doors or {}).items():
            doors.setdefault(side, []).extend(cuts)
        extents = {"S": (x0, x1), "N": (x0, x1), "W": (y0, y1), "E": (y0, y1)}
        merged = {side: _merge_openings(doors.get(side, []), *extents[side]) for side in doors}
        planes = (("S", 1, y0), ("N", 1, y1), ("W", 0, x0), ("E", 0, x1))

        def door_top(a, b) -> Optional[float]:
            """The lintel's underside if the wall edge a..b is in a doorway."""
            for side, axis, plane in planes:
                if abs(a[axis] - plane) > 0.01 or abs(b[axis] - plane) > 0.01:
                    continue
                lo, hi = sorted((a[1 - axis], b[1 - axis]))
                for c0, c1, top in merged.get(side, ()):
                    if lo >= c0 - 0.01 and hi <= c1 + 0.01:
                        return top
            return None

        scale = self._uv_scale[wall_mat]
        rows = max(1, math.ceil((z1 - z0) / WALL_ROW))
        for loop in outline.wall_loops():
            along = 0.0
            for i, i2 in zip(loop, loop[1:] + loop[:1]):
                a, b = outline.verts[i], outline.verts[i2]
                run = math.hypot(b[0] - a[0], b[1] - a[1])
                normal = (-(b[1] - a[1]) / run, (b[0] - a[0]) / run, 0.0)
                la, lb = z0 + outline.lift_at(i), z0 + outline.lift_at(i2)
                ha, hb = z1 - outline.drop_at(i), z1 - outline.drop_at(i2)
                top = door_top(a, b)
                if top is not None:
                    bands = [(top, ha, top, hb)]
                else:
                    bands = [(la + (ha - la) * k / rows, la + (ha - la) * (k + 1) / rows,
                              lb + (hb - lb) * k / rows, lb + (hb - lb) * (k + 1) / rows)
                             for k in range(rows)]
                for lo_a, hi_a, lo_b, hi_b in bands:
                    if hi_a <= lo_a or hi_b <= lo_b:
                        continue
                    self._add_face([(a[0], a[1], lo_a), (a[0], a[1], hi_a), (b[0], b[1], hi_b), (b[0], b[1], lo_b)],
                                   [(-along * scale, -lo_a * scale), (-along * scale, -hi_a * scale),
                                    (-(along + run) * scale, -hi_b * scale), (-(along + run) * scale, -lo_b * scale)],
                                   normal, wall_mat)
                along += run

    # ------------------------------------------------------------------
    # Primitive: a corridor (floor + ceiling + two side walls)
    # ------------------------------------------------------------------

    def add_corridor(self, cor: CorridorSpec, spec: ZoneSpec) -> None:
        """
        Build a corridor between two wall openings, picking one of three routes
        so the corridor meets BOTH openings perpendicularly and at the right
        floor height:

        * **Straight** — the openings are (near) collinear on the run axis: a
          single axis-aligned leg.
        * **Z-corridor** (3 segments) — both rooms face each other on PARALLEL
          walls (both E/W, or both N/S). This is the common layout case. A
          single-corner L cannot serve it: one of its legs would run *along* a
          wall face instead of out through the opening, so it meets that opening
          at the wrong XY and (for elevation) the wrong floor height, leaving a
          gap (seed 1955208177). Instead we emit a perpendicular stub straight
          out of wall A, a middle cross-jog, and a perpendicular stub into wall
          B. Each end stub stays flat at its own room's floor; the middle jog
          carries the entire elevation change.
        * **L-bend** (2 segments) — the genuine cross-axis case (one opening on
          an E/W wall, the other on an N/S wall). A single corner serves it: a
          perpendicular leg out of A, then a perpendicular leg into B.

        For every route the whole height change (ramp or staircase) is confined
        to ONE segment via the shared `_emit_route` helper, so that segment
        lands flush with its room while the flat segments sit exactly at the
        other room's floor — no gap at either opening, and ramp/stair behave
        identically regardless of route.
        """
        floor_mat   = self.material_id(spec.materials[cor.floor_material])
        wall_mat    = self.material_id(spec.materials[cor.wall_material])
        ceiling_mat = self.material_id(spec.materials[cor.ceiling_material])

        hw = cor.width / 2

        # The straight / Z / L decision (and which leg carries the rise) lives
        # in generators.routing.corridor_route, shared with the layout's leg
        # measurement and the continuity/terrain consumers. A Route's
        # carry == -1 means "carry the longest leg", which _emit_route spells
        # as carry=None.
        rooms = {r.id: r for r in spec.rooms}
        route = corridor_route(cor, rooms)
        z_carry = None if route.carry < 0 else route.carry

        self._emit_route(
            list(route.waypoints), list(route.axes), carry=z_carry,
            from_z=cor.from_z, to_z=cor.to_z,
            hw=hw, height=cor.height, steps=cor.steps,
            floor_mat=floor_mat, wall_mat=wall_mat, ceiling_mat=ceiling_mat,
            avoid=_room_rects(spec.rooms) if cor.steps < 0 else (),
            bridge=bridge_layout(cor, rooms) if cor.bridge else None, rough=cor.rough)

    @staticmethod
    def _seg_len(waypoints, k):
        (x0, y0), (x1, y1) = waypoints[k], waypoints[k + 1]
        return abs(x1 - x0) + abs(y1 - y0)   # axis-aligned → one term is 0

    @classmethod
    def _waypoint_zs(cls, waypoints, carry, from_z, to_z):
        """Floor height at each waypoint, and the resolved carry leg: from_z up
        to (and including) the start of the carry leg, to_z from the end of the
        carry leg onward. `carry` None means the longest leg."""
        n_legs = len(waypoints) - 1
        if carry is None:
            carry = max(range(n_legs), key=lambda k: cls._seg_len(waypoints, k))
        zs = [from_z if i <= carry else to_z for i in range(len(waypoints))]
        return zs, carry

    def _emit_route(self, waypoints, axes, carry, from_z, to_z, hw, height,
                    steps, floor_mat, wall_mat, ceiling_mat, avoid=(), bridge=None, rough=0.0):
        """
        Shared multi-segment corridor builder. `waypoints` is an ordered list of
        (x, y) points (>= 2); each consecutive pair is one axis-aligned leg, and
        `axes[k]` is True when leg k runs along X.

        The ENTIRE elevation change (and the staircase, if any) is confined to
        leg `carry`: every leg before it stays flat at `from_z`, every leg after
        stays flat at `to_z`. This single rule keeps ramps and stairs behaving
        identically across the straight / Z / L routes — the carry leg lands
        flush with its room, the flat legs sit exactly at the other room's
        floor, so there is no gap at either opening — regardless of WHICH leg
        carries. We therefore default `carry` to the LONGEST leg, which gives
        the gentlest ramp grade / most room for stair treads without disturbing
        the flush landings (seed 481893615 verified both openings stay flush).
        Each bend is a flat corridor-wide square at the waypoint's height, and
        the legs stop at its edge (`_leg_ends`), so no ramp overlaps a flat
        bend floor and the carry leg's slope runs only between the squares.
        The square is walled on the two sides no leg leaves through: without
        those walls the outer corner of every bend was a hole (task 14).
        """
        zs, carry = self._waypoint_zs(waypoints, carry, from_z, to_z)

        for k in range(len(waypoints) - 1):
            if (steps < 0 and k == carry
                    and abs(zs[k + 1] - zs[k]) > 0.01):
                # A planned stair (steps == AUTO_STAIRS) on the carry leg.
                lay = _layout_stair(waypoints, axes, carry, from_z, to_z, hw,
                                    avoid)
                if lay is not None:
                    self._add_planned_stair(lay, hw, height, floor_mat,
                                            wall_mat, ceiling_mat)
                    continue
            ends = self._leg_ends(waypoints, k, hw, zs)
            if ends is None:
                continue   # the bend squares already cover this short leg
            (x0, y0), (x1, y1) = ends
            if bridge is not None and k == bridge.leg:
                self._add_bridge_leg(ends, zs[k], zs[k + 1], bridge, height,
                                     floor_mat, wall_mat, ceiling_mat)
                continue
            leg_steps = steps if k == carry else 0
            if rough > 0:
                self._add_rough_leg(x0, y0, zs[k], x1, y1, zs[k + 1], axes[k], hw, height, rough,
                                    floor_mat, wall_mat, ceiling_mat)
                continue
            self._add_straight_leg(
                x0, y0, zs[k], x1, y1, zs[k + 1],
                axes[k], hw, height, leg_steps,
                floor_mat, wall_mat, ceiling_mat)

        # Fill each interior corner flush with the shared floor height there.
        for i in range(1, len(waypoints) - 1):
            self._add_corner_fill(self._bend_square(waypoints, i, hw), zs[i],
                                  height, floor_mat, ceiling_mat)
            self._add_corner_walls(waypoints, axes, i, zs[i], hw, height,
                                   wall_mat)

    @staticmethod
    def _leg_ends(waypoints, k, hw, zs):
        """The built span of leg k: its waypoints, each end that is a bend
        pulled back by `hw` to the bend square's edge (a doorway end is kept).
        None when nothing is left between the squares.

        A leg that rises (`zs[k] != zs[k + 1]`) but is shorter than the two
        squares is built at full length instead, so the rise isn't lost. The
        layout never makes one (its grade cap gives such a jog no rise); a
        hand-authored spec can."""
        n_legs = len(waypoints) - 1
        (x0, y0), (x1, y1) = waypoints[k], waypoints[k + 1]
        length = abs(x1 - x0) + abs(y1 - y0)   # axis-aligned → one term is 0
        t0 = hw if k > 0 else 0.0
        t1 = hw if k < n_legs - 1 else 0.0
        if length - t0 - t1 <= 1e-6:
            if length > 1e-6 and abs(zs[k + 1] - zs[k]) > 0.01:
                return (waypoints[k], waypoints[k + 1])
            return None
        ux, uy = (x1 - x0) / length, (y1 - y0) / length
        return ((x0 + ux * t0, y0 + uy * t0), (x1 - ux * t1, y1 - uy * t1))

    @staticmethod
    def _bend_square(waypoints, i, hw):
        """The floor square of the bend at waypoint i, (x0, y0, x1, y1): a
        corridor width across, centred on the waypoint, but cut back to a
        doorway it would overhang (a doorway leg shorter than `hw`), so the
        corridor floor never reaches past its opening into the room."""
        cx, cy = waypoints[i]
        x0, y0, x1, y1 = cx - hw, cy - hw, cx + hw, cy + hw
        last = len(waypoints) - 1
        for j in (i - 1, i + 1):
            if j not in (0, last):
                continue
            px, py = waypoints[j]
            if abs(px - cx) >= abs(py - cy):
                if px > cx:
                    x1 = min(x1, max(px, cx))
                else:
                    x0 = max(x0, min(px, cx))
            elif py > cy:
                y1 = min(y1, max(py, cy))
            else:
                y0 = max(y0, min(py, cy))
        return (x0, y0, x1, y1)

    def _add_corner_walls(self, waypoints, axes, i, cz, hw, height, wall_mat):
        """Wall the bend square at waypoint i on its closed sides.

        The two sides facing the previous and next waypoints are where the
        legs join, so they stay open. The other two are walled, except where
        another part of the corridor's floor lies right past them (a second
        bend square sharing an edge when the jog is shorter than a corridor
        width, and the leg leaving it).
        """
        cx, cy = waypoints[i]
        sq = self._bend_square(waypoints, i, hw)
        # Floor rectangles of the rest of the route: every leg at full length,
        # every other bend square.
        others = []
        for k in range(len(waypoints) - 1):
            (ax, ay), (bx, by) = waypoints[k], waypoints[k + 1]
            if axes[k]:
                others.append((min(ax, bx), ay - hw, max(ax, bx), ay + hw))
            else:
                others.append((ax - hw, min(ay, by), ax + hw, max(ay, by)))
        for j in range(1, len(waypoints) - 1):
            if j != i:
                others.append(self._bend_square(waypoints, j, hw))

        def toward(p):
            """The side of the square facing waypoint p."""
            dx, dy = p[0] - cx, p[1] - cy
            if abs(dx) >= abs(dy):
                return "E" if dx > 0 else "W"
            return "N" if dy > 0 else "S"

        open_sides = {toward(waypoints[i - 1]), toward(waypoints[i + 1])}
        eps = 1e-6
        for side in ("S", "N", "W", "E"):
            if side in open_sides:
                continue
            along_x = side in "SN"
            plane = {"S": sq[1], "N": sq[3], "W": sq[0], "E": sq[2]}[side]
            out = -1.0 if side in "SW" else 1.0
            lo, hi = (sq[0], sq[2]) if along_x else (sq[1], sq[3])
            covered = []
            for (rx0, ry0, rx1, ry1) in others:
                # Does this rectangle hold the floor just outside the side?
                n0, n1 = (ry0, ry1) if along_x else (rx0, rx1)
                inside = (n0 <= plane + eps and n1 > plane + eps) if out > 0 \
                    else (n0 < plane - eps and n1 >= plane - eps)
                if inside:
                    c0, c1 = (rx0, rx1) if along_x else (ry0, ry1)
                    c0, c1 = max(lo, c0), min(hi, c1)
                    if c1 > c0:
                        covered.append((c0, c1))
            pos = lo
            for c0, c1 in sorted(covered) + [(hi, hi)]:
                if c0 > pos + eps:
                    self._add_bend_wall(side, plane, pos, c0, cz, cz + height,
                                        wall_mat)
                pos = max(pos, c1)

    def _add_bend_wall(self, side, plane, a, b, lo, hi, wall_mat):
        """One wall rectangle on side `side` of a bend square, a..b along the
        side, lo..hi in Z, facing into the square."""
        if side == "S":     # y = plane, normal +Y
            self.add_quad((a, plane, lo), (a, plane, hi), (b, plane, hi),
                          (b, plane, lo), normal=(0, 1, 0), material=wall_mat)
        elif side == "N":   # y = plane, normal -Y
            self.add_quad((b, plane, lo), (b, plane, hi), (a, plane, hi),
                          (a, plane, lo), normal=(0, -1, 0), material=wall_mat)
        elif side == "W":   # x = plane, normal +X
            self.add_quad((plane, b, lo), (plane, b, hi), (plane, a, hi),
                          (plane, a, lo), normal=(1, 0, 0), material=wall_mat)
        else:               # "E": x = plane, normal -X
            self.add_quad((plane, a, lo), (plane, a, hi), (plane, b, hi),
                          (plane, b, lo), normal=(-1, 0, 0), material=wall_mat)

    def _add_straight_leg(self, fx, fy, fz, tx, ty, tz, along_x, hw, height,
                          steps, floor_mat, wall_mat, ceiling_mat):
        """
        Build one straight axis-aligned leg between two points that share the
        cross coordinate (collinear along the run axis). Ramps or steps between
        fz and tz. This is the single-segment primitive both straight and
        L-shaped corridors are built from.
        """
        if along_x:
            if fx <= tx:
                a_pos, a_z, b_pos, b_z = fx, fz, tx, tz
            else:
                a_pos, a_z, b_pos, b_z = tx, tz, fx, fz
            cross = fy
        else:
            if fy <= ty:
                a_pos, a_z, b_pos, b_z = fy, fz, ty, tz
            else:
                a_pos, a_z, b_pos, b_z = ty, tz, fy, fz
            cross = fx
        c0, c1 = cross - hw, cross + hw

        # Degenerate leg (zero length) — nothing to build.
        if abs(b_pos - a_pos) < 1e-6:
            return

        if steps > 0 and abs(b_z - a_z) > 0.01:
            self._add_stepped_corridor(a_pos, a_z, b_pos, b_z, c0, c1,
                                       height, steps, along_x,
                                       floor_mat, wall_mat, ceiling_mat)
        else:
            self._add_ramp_corridor(a_pos, a_z, b_pos, b_z, c0, c1,
                                    height, along_x,
                                    floor_mat, wall_mat, ceiling_mat)

    def _add_rough_leg(self, fx, fy, fz, tx, ty, tz, along_x, hw, height, rough,
                       floor_mat, wall_mat, ceiling_mat):
        """A leg with broken walls and a moving ceiling, square where it meets a room or
        a bend. The floor is the same floor at the same heights, its full width, so every
        route and continuity check holds; only what stands on it moves in, by up to
        ``rough`` of the width each side and of the height above."""
        axis = 0 if along_x else 1
        a, b = ((fx, fy), (tx, ty)) if (fx, fy)[axis] <= (tx, ty)[axis] else ((tx, ty), (fx, fy))
        a_z, b_z = (fz, tz) if a == (fx, fy) else (tz, fz)
        a_pos, b_pos = a[axis], b[axis]
        run = b_pos - a_pos
        if run < 1e-6:
            return
        c0, c1 = a[1 - axis] - hw, a[1 - axis] + hw
        n = max(int(math.ceil(abs(b_z - a_z) / MAX_SEG_RISE)), int(math.ceil(run / ROUGH_SPACING)), 1)
        rng = random.Random(f"{a_pos:.2f},{c0:.2f},{b_pos:.2f}")
        s0, s1, fall = [0.0], [0.0], [0.0]
        for _ in range(n - 1):
            s0.append(rng.uniform(0.0, rough * 2 * hw))
            s1.append(rng.uniform(0.0, rough * 2 * hw))
            fall.append(rng.uniform(0.0, rough * height))
        s0.append(0.0)
        s1.append(0.0)
        fall.append(0.0)
        scale = self._uv_scale[wall_mat]

        def point(pos, cross, z):
            return (pos, cross, z) if along_x else (cross, pos, z)

        def wall(p0, q0, p1, q1, z0, z1, h0, h1, along0):
            """One wall piece from (p0, q0) to (p1, q1), floor on its left going that way."""
            pa, pb = point(p0, q0, 0.0), point(p1, q1, 0.0)
            dx, dy = pb[0] - pa[0], pb[1] - pa[1]
            length = math.hypot(dx, dy)
            corners = [point(p0, q0, z0), point(p0, q0, h0), point(p1, q1, h1), point(p1, q1, z1)]
            uvs = [(-along0 * scale, -z0 * scale), (-along0 * scale, -h0 * scale),
                   (-(along0 + length) * scale, -h1 * scale), (-(along0 + length) * scale, -z1 * scale)]
            self._add_face(corners, uvs, (-dy / length, dx / length, 0.0), wall_mat)
            return length

        # One floor, on shared vertices: the walk gate then sees it joined without
        # working out a seam between every two pieces.
        floor_scale = self._uv_scale[floor_mat]
        floor_at: Dict[Tuple[float, float, float], int] = {}

        def floor_vertex(x, y, z):
            k = floor_at.get((x, y, z))
            if k is None:
                k = floor_at[(x, y, z)] = len(self.vertices)
                self.vertices.append(Vertex(x=x, y=y, z=z, nx=0, ny=0, nz=1,
                                            u=x * floor_scale, v=-y * floor_scale))
            return k

        def floor_quad(*corners):
            a_, b_, c_, d_ = (floor_vertex(*c) for c in corners)
            self.polygons.append(Polygon(a_, b_, c_, floor_mat, 0))
            self.polygons.append(Polygon(a_, c_, d_, floor_mat, 0))

        along_a = along_b = 0.0
        for i in range(n):
            p0, p1 = a_pos + run * i / n, a_pos + run * (i + 1) / n
            z0, z1 = a_z + (b_z - a_z) * i / n, a_z + (b_z - a_z) * (i + 1) / n
            h0, h1 = z0 + height - fall[i], z1 + height - fall[i + 1]
            # The floor and ceiling as _seg_quad lays them, full width, walls of no length.
            if along_x:
                floor_quad((p0, c0, z0), (p1, c0, z1), (p1, c1, z1), (p0, c1, z0))
                self.add_quad((p0, c1, h0), (p1, c1, h1), (p1, c0, h1), (p0, c0, h0),
                              normal=(0, 0, -1), material=ceiling_mat)
                along_a += wall(p0, c0 + s0[i], p1, c0 + s0[i + 1], z0, z1, h0, h1, along_a)
                along_b += wall(p1, c1 - s1[i + 1], p0, c1 - s1[i], z1, z0, h1, h0, along_b)
            else:
                floor_quad((c0, p0, z0), (c1, p0, z0), (c1, p1, z1), (c0, p1, z1))
                self.add_quad((c0, p1, h1), (c1, p1, h1), (c1, p0, h0), (c0, p0, h0),
                              normal=(0, 0, -1), material=ceiling_mat)
                along_a += wall(p1, c0 + s0[i + 1], p0, c0 + s0[i], z1, z0, h1, h0, along_a)
                along_b += wall(p0, c1 - s1[i], p1, c1 - s1[i + 1], z0, z1, h0, h1, along_b)

    def _add_corner_fill(self, square, cz, height, floor_mat, ceiling_mat):
        """
        Fill the square where two perpendicular legs meet, so the floor and
        ceiling are continuous through the bend (no hole at the corner).
        `square` is the bend's (x0, y0, x1, y1) from `_bend_square`.
        """
        x0, y0, x1, y1 = square
        # Floor
        self.add_quad((x0, y0, cz), (x1, y0, cz), (x1, y1, cz), (x0, y1, cz),
                      normal=(0, 0, 1), material=floor_mat)
        # Ceiling
        zc = cz + height
        self.add_quad((x0, y1, zc), (x1, y1, zc), (x1, y0, zc), (x0, y0, zc),
                      normal=(0, 0, -1), material=ceiling_mat)

    # ------------------------------------------------------------------
    # Bridges (step 7 task 11): the deck over a lower room's slot
    # ------------------------------------------------------------------

    def _facing_quad(self, pts, normal, material) -> None:
        """A planar quad from four corners in any order, wound CCW seen from
        the side ``normal`` points to (the winding is the floor/ceiling test)."""
        cx = sum(p[0] for p in pts) / 4
        cy = sum(p[1] for p in pts) / 4
        cz = sum(p[2] for p in pts) / 4
        n = normal
        e1 = (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0)
        d = sum(a * b for a, b in zip(e1, n))
        e1 = tuple(a - d * b for a, b in zip(e1, n))
        e2 = (n[1] * e1[2] - n[2] * e1[1], n[2] * e1[0] - n[0] * e1[2],
              n[0] * e1[1] - n[1] * e1[0])

        def ang(p):
            q = (p[0] - cx, p[1] - cy, p[2] - cz)
            return math.atan2(sum(a * b for a, b in zip(q, e2)),
                              sum(a * b for a, b in zip(q, e1)))

        a, b, c, e = sorted(pts, key=ang)
        self.add_quad(a, b, c, e, normal=normal, material=material)

    def _add_bridge_leg(self, ends, fz, tz, bl: "BridgeLayout", height,
                        floor_mat, wall_mat, ceiling_mat) -> None:
        """Leg ``bl.leg`` of a Bridge: the plain corridor up to the slot, the
        deck and its shaft over it (``_add_bridge_span``), the plain corridor
        after it. The ramp's slope runs straight through all three."""
        (x0, y0), (x1, y1) = ends
        ua, ub = (x0, x1) if bl.along_x else (y0, y1)

        def z(u):
            return fz if abs(ub - ua) <= 1e-9 else fz + (tz - fz) * (u - ua) / (ub - ua)

        def xy(u):
            return _uv_to_xy(bl.along_x, u, bl.cross)

        lo, hi = min(ua, ub), max(ua, ub)
        for p, q in ((lo, bl.s0), (bl.s1, hi)):
            if q - p > 1e-6:
                (px, py), (qx, qy) = xy(p), xy(q)
                self._add_straight_leg(px, py, z(p), qx, qy, z(q), bl.along_x,
                                       bl.hw, height, 0, floor_mat, wall_mat,
                                       ceiling_mat)
        self._add_bridge_span(bl, height, floor_mat, wall_mat, ceiling_mat)

    def _add_bridge_span(self, bl: "BridgeLayout", height, floor_mat, wall_mat,
                         ceiling_mat) -> None:
        """The deck (floor, underside, edges and rails) and the shaft round
        it (side walls down to the lower room's ceiling, the corridor's
        ceiling across it, the two end walls), from ``bl.s0`` to ``bl.s1``.
        Subdivided like a ramp so each deck face rises at most MAX_SEG_RISE."""
        ax = bl.along_x
        A = (1.0, 0.0, 0.0) if ax else (0.0, 1.0, 0.0)
        V = (0.0, 1.0, 0.0) if ax else (1.0, 0.0, 0.0)
        neg = lambda v: (-v[0], -v[1], -v[2])  # noqa: E731
        up, down = (0.0, 0.0, 1.0), (0.0, 0.0, -1.0)

        def P(u, v, z):
            x, y = _uv_to_xy(ax, u, v)
            return (x, y, z)

        t = DECK_THICKNESS
        hc = bl.ceiling
        c, hw, m = bl.cross, bl.hw, bl.margin
        d0, d1, w0, w1 = c - hw, c + hw, c - hw - m, c + hw + m
        n = max(1, int(math.ceil(abs(bl.z1 - bl.z0) / MAX_SEG_RISE)))
        for i in range(n):
            p0 = bl.s0 + (bl.s1 - bl.s0) * i / n
            p1 = bl.s0 + (bl.s1 - bl.s0) * (i + 1) / n
            za, zb = bl.z_at(p0), bl.z_at(p1)
            quad = self._facing_quad
            # Deck: floor, underside, its two edges and a rail on each edge
            # (both faces of a thin wall).
            quad([P(p0, d0, za), P(p1, d0, zb), P(p1, d1, zb), P(p0, d1, za)], up, floor_mat)
            quad([P(p0, d0, za - t), P(p1, d0, zb - t), P(p1, d1, zb - t), P(p0, d1, za - t)],
                 down, wall_mat)
            for v, out in ((d0, neg(V)), (d1, V)):
                quad([P(p0, v, za - t), P(p1, v, zb - t), P(p1, v, zb), P(p0, v, za)],
                     out, wall_mat)
                for face in (out, neg(out)):
                    quad([P(p0, v, za), P(p1, v, zb), P(p1, v, zb + bl.rail),
                          P(p0, v, za + bl.rail)], face, wall_mat)
            # Shaft: side walls from the lower ceiling to the corridor's
            # ceiling, and that ceiling across the whole slot.
            for v, inward in ((w0, V), (w1, neg(V))):
                quad([P(p0, v, hc), P(p1, v, hc), P(p1, v, zb + height), P(p0, v, za + height)],
                     inward, wall_mat)
            quad([P(p0, w0, za + height), P(p1, w0, zb + height), P(p1, w1, zb + height),
                  P(p0, w1, za + height)], down, ceiling_mat)
        # Ends: closed from the lower ceiling up round the deck (the tube
        # going on, or the room's doorway, fills the deck's own width).
        for s, inward in ((bl.s0, A), (bl.s1, neg(A))):
            z = bl.z_at(s)
            for v0, v1 in ((w0, d0), (d1, w1)):
                quad([P(s, v0, hc), P(s, v1, hc), P(s, v1, z + height), P(s, v0, z + height)],
                     inward, wall_mat)
            if z - t - hc > 1e-6:
                quad([P(s, d0, hc), P(s, d1, hc), P(s, d1, z - t), P(s, d0, z - t)],
                     inward, wall_mat)

    def _seg_quad(self, along_x, pos0, pos1, c0, c1, z_lo0, z_lo1, zc0, zc1,
                  floor_mat, wall_mat, ceiling_mat):
        """
        Build one segment of a corridor between pos0..pos1 (along the run axis),
        with floor heights z_lo0/z_lo1 and ceiling heights zc0/zc1 at each end.
        """
        if along_x:
            # Run axis = X, cross axis = Y
            # Floor (slopes from z_lo0 to z_lo1), normal roughly +Z
            self.add_quad((pos0, c0, z_lo0), (pos1, c0, z_lo1),
                          (pos1, c1, z_lo1), (pos0, c1, z_lo0),
                          normal=(0, 0, 1), material=floor_mat)
            # Ceiling
            self.add_quad((pos0, c1, zc0), (pos1, c1, zc1),
                          (pos1, c0, zc1), (pos0, c0, zc0),
                          normal=(0, 0, -1), material=ceiling_mat)
            # South wall (c0), normal +Y
            self.add_quad((pos0, c0, z_lo0), (pos0, c0, zc0),
                          (pos1, c0, zc1), (pos1, c0, z_lo1),
                          normal=(0, 1, 0), material=wall_mat)
            # North wall (c1), normal -Y
            self.add_quad((pos1, c1, z_lo1), (pos1, c1, zc1),
                          (pos0, c1, zc0), (pos0, c1, z_lo0),
                          normal=(0, -1, 0), material=wall_mat)
        else:
            # Run axis = Y, cross axis = X
            self.add_quad((c0, pos0, z_lo0), (c1, pos0, z_lo0),
                          (c1, pos1, z_lo1), (c0, pos1, z_lo1),
                          normal=(0, 0, 1), material=floor_mat)
            self.add_quad((c0, pos1, zc1), (c1, pos1, zc1),
                          (c1, pos0, zc0), (c0, pos0, zc0),
                          normal=(0, 0, -1), material=ceiling_mat)
            # West wall (c0), normal +X
            self.add_quad((c0, pos1, z_lo1), (c0, pos1, zc1),
                          (c0, pos0, zc0), (c0, pos0, z_lo0),
                          normal=(1, 0, 0), material=wall_mat)
            # East wall (c1), normal -X
            self.add_quad((c1, pos0, z_lo0), (c1, pos0, zc0),
                          (c1, pos1, zc1), (c1, pos1, z_lo1),
                          normal=(-1, 0, 0), material=wall_mat)

    def _add_ramp_corridor(self, a_pos, a_z, b_pos, b_z, c0, c1, height,
                           along_x, floor_mat, wall_mat, ceiling_mat):
        """
        Sloped floor from (a_pos, a_z) to (b_pos, b_z), subdivided along the run
        into segments that each rise at most MAX_SEG_RISE. The subdivision is
        what makes a ramp walkable to the per-triangle traversability agent: a
        single quad would present a dz/3 step between its two triangles, read as
        an unclimbable gap. Visually it is still a smooth ramp.
        """
        dz = abs(b_z - a_z)
        n = max(1, int(math.ceil(dz / MAX_SEG_RISE)))
        for i in range(n):
            t0, t1 = i / n, (i + 1) / n
            p0 = a_pos + (b_pos - a_pos) * t0
            p1 = a_pos + (b_pos - a_pos) * t1
            z0 = a_z + (b_z - a_z) * t0
            z1 = a_z + (b_z - a_z) * t1
            self._seg_quad(along_x, p0, p1, c0, c1,
                           z0, z1, z0 + height, z1 + height,
                           floor_mat, wall_mat, ceiling_mat)

    def _add_stepped_corridor(self, a_pos, a_z, b_pos, b_z, c0, c1, height,
                              steps, along_x, floor_mat, wall_mat, ceiling_mat):
        """
        Staircase from (a_pos, a_z) up/down to (b_pos, b_z): `steps` flat treads
        connected by vertical risers.

        Tread i sits at height `a_z + i*rise` (so the FIRST tread is flush with
        the lower floor and the LAST tread's far edge reaches b_z — no gap at
        either landing). The riser is at the far edge of each tread and climbs
        to the next tread's height. The riser normal faces back down the run so
        it is visible to someone ascending.
        """
        total_run = b_pos - a_pos
        total_rise = b_z - a_z
        run_per_step = total_run / steps
        rise_per_step = total_rise / steps

        for i in range(steps):
            p0 = a_pos + i * run_per_step
            p1 = a_pos + (i + 1) * run_per_step
            z_tread = a_z + i * rise_per_step            # this tread's height
            z_next = a_z + (i + 1) * rise_per_step        # next tread's height
            # Ceiling follows the ascending treads so headroom stays constant.
            zc0 = z_tread + height
            zc1 = z_next + height

            # Flat tread (floor + ceiling + side walls) at constant z_tread.
            self._seg_quad(along_x, p0, p1, c0, c1,
                           z_tread, z_tread, zc0, zc1,
                           floor_mat, wall_mat, ceiling_mat)

            # Vertical riser at the FAR edge of this tread, climbing to the
            # next tread's height. The final riser (i == steps-1) climbs to b_z
            # so the staircase lands flush with the upper floor — no gap at the
            # top landing.
            if abs(z_next - z_tread) > 1e-6:
                lo, hi = (z_tread, z_next) if z_next > z_tread else (z_next, z_tread)
                if along_x:
                    # Riser plane at x = p1, normal facing -X (back down an
                    # ascending run toward the start).
                    self.add_quad((p1, c0, lo), (p1, c0, hi),
                                  (p1, c1, hi), (p1, c1, lo),
                                  normal=(-1, 0, 0), material=wall_mat)
                else:
                    # Riser plane at y = p1, normal facing -Y.
                    self.add_quad((c0, p1, lo), (c1, p1, lo),
                                  (c1, p1, hi), (c0, p1, hi),
                                  normal=(0, -1, 0), material=wall_mat)

    # ------------------------------------------------------------------
    # Planned staircases (steps == AUTO_STAIRS)
    # ------------------------------------------------------------------
    #
    # Built in the carry leg's own (u, v) frame: u along the leg, v across.
    # Every piece is a flat-floored box rectangle; its ceiling is level or
    # slopes along one axis (following the flight's pitch line), and it is
    # walled on the edges listed. Risers are wall quads facing the lower tread.

    # The world side a (u, v) edge maps to: "u0" is the edge at the lower u.
    _EDGE_SIDE = {True: {"u0": "W", "u1": "E", "v0": "S", "v1": "N"},
                  False: {"u0": "S", "u1": "N", "v0": "W", "v1": "E"}}

    def _stair_piece(self, along_x, u0, u1, v0, v1, fz, cz, edges,
                     floor_mat, wall_mat, ceiling_mat):
        """One flat-floored piece over u0..u1 × v0..v1 at floor height ``fz``.
        ``cz(u, v)`` is the ceiling height (linear in u or v); ``edges`` the
        (u, v) edges ("u0", "u1", "v0", "v1") to wall."""
        ua, ub = min(u0, u1), max(u0, u1)
        va, vb = min(v0, v1), max(v0, v1)
        if ub - ua < 1e-6 or vb - va < 1e-6:
            return
        x0, y0, x1, y1 = _uv_rect(along_x, ua, ub, va, vb)

        def ceil_at(x, y):
            return cz(x, y) if along_x else cz(y, x)

        self.add_quad((x0, y0, fz), (x1, y0, fz), (x1, y1, fz), (x0, y1, fz),
                      normal=(0, 0, 1), material=floor_mat)
        self.add_quad((x0, y1, ceil_at(x0, y1)), (x1, y1, ceil_at(x1, y1)),
                      (x1, y0, ceil_at(x1, y0)), (x0, y0, ceil_at(x0, y0)),
                      normal=(0, 0, -1), material=ceiling_mat)
        sides = self._EDGE_SIDE[along_x]
        for edge in edges:
            side = sides[edge]
            if side in "SN":
                y = y0 if side == "S" else y1
                self._stair_wall(side, y, x0, x1, fz,
                                 ceil_at(x0, y), ceil_at(x1, y), wall_mat)
            else:
                x = x0 if side == "W" else x1
                self._stair_wall(side, x, y0, y1, fz,
                                 ceil_at(x, y0), ceil_at(x, y1), wall_mat)

    def _stair_wall(self, side, plane, a, b, lo, hi_a, hi_b, wall_mat):
        """A wall on side ``side`` of a piece (facing into it), a..b along the
        side, from ``lo`` up to ``hi_a`` at a and ``hi_b`` at b. Corner order
        as ``_add_bend_wall``."""
        if side == "S":
            self.add_quad((a, plane, lo), (a, plane, hi_a), (b, plane, hi_b),
                          (b, plane, lo), normal=(0, 1, 0), material=wall_mat)
        elif side == "N":
            self.add_quad((b, plane, lo), (b, plane, hi_b), (a, plane, hi_a),
                          (a, plane, lo), normal=(0, -1, 0), material=wall_mat)
        elif side == "W":
            self.add_quad((plane, b, lo), (plane, b, hi_b), (plane, a, hi_a),
                          (plane, a, lo), normal=(1, 0, 0), material=wall_mat)
        else:
            self.add_quad((plane, a, lo), (plane, a, hi_a), (plane, b, hi_b),
                          (plane, b, lo), normal=(-1, 0, 0), material=wall_mat)

    def _stair_riser(self, along_x, axis, p, a, b, lo, hi, lower_below,
                     wall_mat):
        """A riser on the plane ``axis`` = p ("u" or "v"), a..b along the other
        axis, lo..hi in Z, facing the lower tread: on the low-coordinate side
        when ``lower_below``."""
        edge = axis + ("1" if lower_below else "0")
        side = self._EDGE_SIDE[along_x][edge]
        self._add_bend_wall(side, p, min(a, b), max(a, b), lo, hi, wall_mat)

    def _stair_flight(self, along_x, axis, s0, d, z0, n, r, height, l0, l1,
                      floor_mat, wall_mat, ceiling_mat):
        """A flight of ``n`` treads of TREAD_DEPTH and ``n`` risers of ``r``
        (signed), starting at position ``s0`` on ``axis`` ("u" runs the flight
        along the leg, "v" across it) and walking in direction ``d`` (+1/-1).
        The first tread is at ``z0``; each riser stands at a tread's far end,
        so the last climbs to z0 + n·r at s0 + d·n·TREAD_DEPTH. The other axis
        spans l0..l1, walled both sides. The ceiling follows the pitch line,
        z0 + height at s0 to z0 + n·r + height at the flight's end."""
        T = TREAD_DEPTH
        run = n * T

        def cz(u, v):
            s = (u if axis == "u" else v) - s0
            t = min(1.0, max(0.0, d * s / run))
            return z0 + height + n * r * t

        lower_below = (r > 0) == (d > 0)
        for j in range(n):
            a, b = s0 + d * j * T, s0 + d * (j + 1) * T
            if axis == "u":
                self._stair_piece(along_x, a, b, l0, l1, z0 + j * r, cz,
                                  ("v0", "v1"), floor_mat, wall_mat,
                                  ceiling_mat)
            else:
                self._stair_piece(along_x, l0, l1, a, b, z0 + j * r, cz,
                                  ("u0", "u1"), floor_mat, wall_mat,
                                  ceiling_mat)
            lo, hi = sorted((z0 + j * r, z0 + (j + 1) * r))
            self._stair_riser(along_x, axis, b, l0, l1, lo, hi, lower_below,
                              wall_mat)

    def _add_planned_stair(self, lay: StairLayout, hw, height, floor_mat,
                           wall_mat, ceiling_mat):
        """Build a planned stair (``stair_layout``) on its carry leg."""
        plan = lay.plan
        along_x = lay.along_x
        (sx, sy), (ex, ey) = lay.start, lay.end
        us, ue = (sx, ex) if along_x else (sy, ey)
        c = sy if along_x else sx
        z0, z1 = lay.from_z, lay.to_z
        mats = (floor_mat, wall_mat, ceiling_mat)
        length = abs(ue - us)
        d = 1.0 if ue > us else -1.0

        if lay.cramped:
            # No room for two lanes: the hand-count stair stretched over the
            # leg (its treads come out short; the gate names it).
            self._add_straight_leg(sx, sy, z0, ex, ey, z1, along_x, hw,
                                   height, plan.risers, *mats)
            return

        def level(z):
            return lambda u, v: z + height

        if not plan.switchback:
            # One flight centred on the leg, level approaches either side.
            n, r = plan.risers, (z1 - z0) / plan.risers
            fa = us + d * (length - plan.run) / 2
            fb = fa + d * plan.run
            self._stair_piece(along_x, us, fa, c - hw, c + hw, z0, level(z0),
                              ("v0", "v1"), *mats)
            self._stair_flight(along_x, "u", fa, d, z0, n, r, height,
                               c - hw, c + hw, *mats)
            self._stair_piece(along_x, fb, ue, c - hw, c + hw, z1, level(z1),
                              ("v0", "v1"), *mats)
            return

        # Switchback: lanes 1 and 2 side by side along the leg, flights out
        # across it into the stairwell and back, a landing at the far end.
        m = plan.flight_risers
        r = (z1 - z0) / (2 * m)
        zm = z0 + m * r
        lane, side = lay.lane, lay.side
        a1 = us if lay.placement == "start" else ue - 2 * d * lane
        a2 = a1 + d * lane                  # the dividing wall
        a3 = a1 + 2 * d * lane
        ve = c + side * hw                  # the leg's edge on the stairwell side
        vfar = c - side * hw                # its other edge
        vl = ve + side * plan.flight_run    # the landing's near edge
        vend = vl + side * lane             # the stairwell's far wall

        # Lane 1's dividing-wall edge: its high-u edge when lane 1 is the
        # low-u lane (the walk runs toward +u).
        mid_u = "u1" if d > 0 else "u0"
        far_v = "v0" if vfar < ve else "v1"

        # The leg: a level approach, the two lane squares, a level approach.
        if lay.placement == "end":
            self._stair_piece(along_x, us, a1, c - hw, c + hw, z0, level(z0),
                              ("v0", "v1"), *mats)
        self._stair_piece(along_x, a1, a2, c - hw, c + hw, z0, level(z0),
                          (far_v, mid_u), *mats)
        self._stair_piece(along_x, a2, a3, c - hw, c + hw, z1, level(z1),
                          (far_v, "u0" if mid_u == "u1" else "u1"), *mats)
        if lay.placement == "start":
            self._stair_piece(along_x, a3, ue, c - hw, c + hw, z1, level(z1),
                              ("v0", "v1"), *mats)
        # Flight 1 out across the leg in lane 1; the landing; flight 2 back
        # in lane 2, its last riser at the leg's edge onto lane 2's square.
        self._stair_flight(along_x, "v", ve, side, z0, m, r, height, a1, a2,
                           *mats)
        far_end = "v1" if side > 0 else "v0"
        self._stair_piece(along_x, a1, a3, vl, vend, zm, level(zm),
                          ("u0", "u1", far_end), *mats)
        self._stair_flight(along_x, "v", vl, -side, zm, m, r, height, a2, a3,
                           *mats)

    # ------------------------------------------------------------------
    # Emit
    # ------------------------------------------------------------------

    def to_ter(self, name: str, version: int = 2) -> TerFile:
        """Emit a TerFile from the accumulated geometry."""
        ter = TerFile(name=name, magic=MAGIC_TERRAIN, version=version)
        ter.materials = list(self.materials)
        ter.vertices  = list(self.vertices)
        ter.polygons  = list(self.polygons)
        return ter


# ---------------------------------------------------------------------------
# High-level entry point
# ---------------------------------------------------------------------------

def build_mesh(spec: ZoneSpec) -> MeshBuilder:
    """Build a complete MeshBuilder from a ZoneSpec."""
    mb = MeshBuilder()

    # Ensure every referenced material exists (fallback to a default grey)
    _ensure_materials(spec)

    for room in spec.rooms:
        mb.add_room(room, spec)
    for cor in spec.corridors:
        mb.add_corridor(cor, spec)

    return mb


def dais_steps(height: float) -> int:
    """How many steps a dais this high needs: none within a riser, else enough that no riser
    passes ``RISER_CAP``."""
    return 0 if height <= RISER_CAP else int(math.ceil(height / RISER_CAP)) - 1


def step_plans(feat, n: int) -> List[List[Tuple[float, float]]]:
    """The footprints of a dais's ``n`` steps, lowest first, outside its ``steps_side``."""
    xs, ys = [p[0] for p in feat.plan], [p[1] for p in feat.plan]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    along_x = feat.steps_side in ("N", "S")
    mid = ((x0 + x1) if along_x else (y0 + y1)) / 2
    width = min(STEP_WIDTH, (x1 - x0 if along_x else y1 - y0) * 0.8)
    out = []
    for k in range(n):
        near, far = (n - 1 - k) * TREAD_DEPTH, (n - k) * TREAD_DEPTH
        if feat.steps_side == "N":
            a0, a1 = y1 + near, y1 + far
        elif feat.steps_side == "S":
            a0, a1 = y0 - far, y0 - near
        elif feat.steps_side == "E":
            a0, a1 = x1 + near, x1 + far
        else:
            a0, a1 = x0 - far, x0 - near
        c0, c1 = mid - width / 2, mid + width / 2
        out.append([(a0, c0), (a1, c0), (a1, c1), (a0, c1)] if not along_x
                   else [(c0, a0), (c1, a0), (c1, a1), (c0, a1)])
    return out


def room_doors(room: RoomSpec, spec: ZoneSpec,
               extra_doors: Optional[Dict[str, List[Tuple[float, float, float]]]] = None):
    """Each door on ``room``'s walls as (side, c0, c1), merged where they overlap,
    the form ``outline.draw_outline`` takes."""
    (x0, y0, _), (x1, y1, _) = room.bounds
    extents = {"S": (x0, x1), "N": (x0, x1), "W": (y0, y1), "E": (y0, y1)}
    doors = _door_openings(room, spec)
    for side, cuts in (extra_doors or {}).items():
        doors.setdefault(side, []).extend(cuts)
    return [(side, c0, c1) for side in sorted(doors)
            for c0, c1, _top in _merge_openings(doors[side], *extents[side])]


def _door_openings(room: RoomSpec, spec: ZoneSpec
                   ) -> Dict[str, List[Tuple[float, float, float]]]:
    """Where each corridor attached to *room* passes through its walls.

    Returns {side: [(c0, c1, top), ...]}: the corridor's end leg spans c0..c1
    along that wall (its own width, centred on the leg's cross coordinate as
    `_add_straight_leg` builds it) and its ceiling meets the wall plane at
    `top`. The ceiling of a ramp or staircase is linear along the leg, so it is
    interpolated at the wall plane; a lintel from there up stays clear of it.
    Only sides listed in room.open_walls are reported.
    """
    rooms = {r.id: r for r in spec.rooms}
    (x0, y0, _), (x1, y1, _) = room.bounds
    out: Dict[str, List[Tuple[float, float, float]]] = {}
    for cor in spec.corridors:
        ends = []
        if cor.from_room == room.id:
            ends.append("from")
        if cor.to_room == room.id:
            ends.append("to")
        if not ends:
            continue
        route = corridor_route(cor, rooms)
        wps = list(route.waypoints)
        zs, _ = MeshBuilder._waypoint_zs(
            wps, None if route.carry < 0 else route.carry,
            cor.from_z, cor.to_z)
        hw = cor.width / 2
        for end in ends:
            k = 0 if end == "from" else len(wps) - 2
            along_x = route.axes[k]
            # The leg as built: its bend end stops at the bend square. When the
            # squares swallow the whole leg, the floor there is the bend's.
            built = MeshBuilder._leg_ends(wps, k, hw, zs)
            if built is None:
                zb_end = zs[k + 1] if end == "from" else zs[k]
                built, zs_k = (wps[k], wps[k + 1]), (zb_end, zb_end)
            else:
                zs_k = (zs[k], zs[k + 1])
            (ax, ay), (bx, by) = built
            ex, ey = wps[0] if end == "from" else wps[-1]
            if along_x:
                side = "E" if ex >= room.center_x else "W"
                plane, pa, pb, cross = (x1 if side == "E" else x0), ax, bx, ay
            else:
                side = "N" if ey >= room.center_y else "S"
                plane, pa, pb, cross = (y1 if side == "N" else y0), ay, by, ax
            if side not in room.open_walls:
                continue
            za, zb = zs_k
            if abs(pb - pa) > 1e-9:
                t = min(1.0, max(0.0, (plane - pa) / (pb - pa)))
            else:
                t = 0.0
            top = za + (zb - za) * t + cor.height
            out.setdefault(side, []).append((cross - hw, cross + hw, top))
    return out


def _merge_openings(openings, lo: float, hi: float
                    ) -> List[Tuple[float, float, float]]:
    """Clip openings to the wall's extent lo..hi and merge overlaps, sorted
    along the wall. A merged opening takes the higher top, so its lintel stays
    clear of every corridor ceiling it covers."""
    clipped = sorted((max(lo, c0), min(hi, c1), top)
                     for c0, c1, top in openings if min(hi, c1) > max(lo, c0))
    merged: List[Tuple[float, float, float]] = []
    for c0, c1, top in clipped:
        if merged and c0 <= merged[-1][1]:
            m0, m1, mt = merged[-1]
            merged[-1] = (m0, max(m1, c1), max(mt, top))
        else:
            merged.append((c0, c1, top))
    return merged


def _ensure_materials(spec: ZoneSpec) -> None:
    """Give a hand-built spec sensible floor/wall/ceiling defaults: all three
    when it defines no materials yet, otherwise each bare name a room or
    corridor uses but the spec lacks. Generated specs name their own
    materials, so nothing unused is added to them."""
    defaults = {
        "floor":   ((100, 95, 90),  "worn stone flagstone floor"),
        "wall":    ((110, 105, 100),"rough hewn stone block wall"),
        "ceiling": ((70, 68, 65),   "dark rough rock ceiling"),
    }
    used = {m for part in (*spec.rooms, *spec.corridors)
            for m in (part.floor_material, part.wall_material, part.ceiling_material)}
    wanted = set(defaults) if not spec.materials else used
    for name, (color, desc) in defaults.items():
        if name in wanted and name not in spec.materials:
            spec.add_material(name, f"{name}.dds", color=color, description=desc)
