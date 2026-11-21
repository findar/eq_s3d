"""
generators/routing.py
----------------------
One place that decides how a corridor travels between two wall openings.

Historically the route was decided TWICE — once in `MeshBuilder.add_corridor`
(to build the mesh) and once in `LayoutGenerator._route_legs` (to measure the
legs for the elevation cap) — and both copies duplicated the straight / Z / L
test. M1 adds further consumers (continuity footprints, terrain paths), so the
decision lives here and every caller shares it.

A corridor route is one of three shapes:

* **Straight** — the two openings are (near) collinear on the run axis: a
  single axis-aligned leg.
* **Z-corridor** (3 legs) — both rooms face each other on PARALLEL walls (both
  E/W, or both N/S). A perpendicular stub out of A, a middle cross-jog, then a
  perpendicular stub into B. The jog carries the whole rise.
* **L-bend** (2 legs) — the genuine cross-axis case (one opening on an E/W
  wall, the other on an N/S wall): a perpendicular leg out of A then a
  perpendicular leg into B.
* **U** (3 legs, step 7) — both openings on walls facing the SAME way, named
  by ``CorridorSpec.side``: a stub out of each wall, joined by a middle leg
  that runs past both rooms on that side. A stair between two rooms stacked
  over each other takes it (the rooms overlap in plan, so no pair of facing
  walls has a gap between them). The middle leg carries the rise.

`Route` records the waypoints (one point per bend, >= 2), which axis each leg
runs along, which leg carries the entire elevation change, and the kind. The
geometry builder's `_emit_route` consumes `waypoints`/`axes`/`carry` directly,
and the doorway cuts and layout leg measurements plan through here too, so
they all agree on one route.

EQ coordinate convention: Z is up; routes live in the XY plane.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Mapping, Optional, Sequence, Tuple, Union

from .zone_spec import CorridorSpec, RoomSpec


# An axis-aligned rectangle (x0, y0, x1, y1) with x0 <= x1 and y0 <= y1.
Rect = Tuple[float, float, float, float]


@dataclass(frozen=True)
class Route:
    """A planned corridor path between two wall openings.

    `waypoints`  ordered (x, y) points, one per bend, always >= 2.
    `axes`       one bool per leg (len == len(waypoints) - 1); True = the leg
                 runs along X.
    `carry`      index of the leg that carries the entire elevation change, or
                 -1 to mean "carry the longest leg" (the geometry builder's
                 default).
    `kind`       "straight" | "z" | "l" | "u".
    """

    waypoints: Tuple[Tuple[float, float], ...]   # >= 2 points
    axes: Tuple[bool, ...]                        # True = leg runs along X
    carry: int                                    # leg that carries the rise
    kind: str                                     # "straight" | "z" | "l" | "u"


def plan_route(from_xy: Tuple[float, float], to_xy: Tuple[float, float],
               exit_from_x: bool, exit_to_x: bool,
               hw: float, steps: int) -> Route:
    """Decide the straight / Z / L route between two openings.

    `from_xy`/`to_xy`  the two wall-opening points.
    `exit_from_x`      True when the `from` opening is on an E/W wall, so its
                       stub runs along X; likewise `exit_to_x` for `to`.
    `hw`               corridor half-width (sets the straight-vs-bend slack).
    `steps`            > 0 for a staircase (kept for callers; every route
                       shape now picks its carry leg the same way for ramps
                       and stairs).

    A Z-corridor always carries on its interior jog (leg 1), so the flat end
    stubs stay flush with their rooms. `carry == -1` means "carry the longest
    leg" (straight and L routes).
    """
    from_x, from_y = from_xy
    to_x, to_y = to_xy
    dx = to_x - from_x
    dy = to_y - from_y

    same_axis = (exit_from_x == exit_to_x)
    primary_x = exit_from_x
    cross_off = abs(dy) if primary_x else abs(dx)
    carry = -1   # default: carry the rise on the longest leg

    if same_axis and cross_off <= max(2.0, hw * 0.5):
        # --- Straight: (near) collinear openings meet with a single leg.
        waypoints = ((from_x, from_y), (to_x, to_y))
        axes = (primary_x,)
        kind = "straight"
    elif same_axis:
        # --- Z-corridor: parallel facing walls. Perpendicular stub out of A,
        # a cross-jog, then a perpendicular stub into B.
        if primary_x:
            mid = (from_x + to_x) / 2
            waypoints = (
                (from_x, from_y),
                (mid, from_y),
                (mid, to_y),
                (to_x, to_y),
            )
            axes = (True, False, True)   # X stub, Y jog, X stub
        else:
            mid = (from_y + to_y) / 2
            waypoints = (
                (from_x, from_y),
                (from_x, mid),
                (to_x, mid),
                (to_x, to_y),
            )
            axes = (False, True, False)  # Y stub, X jog, Y stub
        # The interior jog (leg 1) carries the rise, ramp or staircase alike:
        # both end stubs then stay flat at their own room's floor, so each
        # doorway is level, and the layout caps the grade by the jog's run.
        carry = 1
        kind = "z"
    else:
        # --- L-bend: genuine cross-axis pair (perpendicular walls).
        if exit_from_x:
            corner = (to_x, from_y)
            axes = (True, False)
        else:
            corner = (from_x, to_y)
            axes = (False, True)
        waypoints = ((from_x, from_y), corner, (to_x, to_y))
        kind = "l"

    return Route(waypoints=waypoints, axes=axes, carry=carry, kind=kind)


# A U-route's middle leg runs this many corridor widths past the outermost
# opening, so the bend squares (half a width) clear the wall with half a width
# to spare.
U_REACH = 1.0
SIDES_OUT = {"N": (False, 1.0), "S": (False, -1.0), "E": (True, 1.0), "W": (True, -1.0)}


def plan_u_route(from_xy: Tuple[float, float], to_xy: Tuple[float, float],
                 side: str, width: float) -> Route:
    """The U-route between two openings on walls facing ``side``: a stub out
    of each wall (perpendicular to it, outward), joined by a middle leg
    ``U_REACH`` corridor widths past the outermost opening. Leg 1 carries the
    rise, as a Z-corridor's jog does, so both stubs stay flat at their own
    room's floor."""
    if side not in SIDES_OUT:
        raise ValueError(f"unknown corridor side {side!r}; expected N, S, E or W")
    exit_x, sign = SIDES_OUT[side]
    (fx, fy), (tx, ty) = from_xy, to_xy
    if exit_x:
        out = (max(fx, tx) if sign > 0 else min(fx, tx)) + sign * U_REACH * width
        waypoints = ((fx, fy), (out, fy), (out, ty), (tx, ty))
        axes = (True, False, True)
    else:
        out = (max(fy, ty) if sign > 0 else min(fy, ty)) + sign * U_REACH * width
        waypoints = ((fx, fy), (fx, out), (tx, out), (tx, ty))
        axes = (False, True, False)
    return Route(waypoints=waypoints, axes=axes, carry=1, kind="u")


def exit_axis_x(acx: float, acy: float, ahw: float, ahd: float,
                bcx: float, bcy: float, bhw: float, bhd: float) -> bool:
    """Which wall AXIS the A→B corridor exits A along: True = E/W (runs X).

    Chosen by the GAP between the two footprints, not the centre delta. The
    separation on an axis is the centre distance minus the two half-extents on
    that axis; a positive separation means the footprints are clear of each
    other there, so a stub can leave through that wall and travel toward the
    real gap. Picking the axis with the larger separation keeps the facing
    walls from crossing — the fix for the inverted-stub (`fx past tx`) class in
    the design suspect table.

    When neither axis separates the footprints (the rooms overlap both ways,
    e.g. one nested near another after re-separation), both separations are
    negative and we fall back to the dominant centre delta — the historic
    basis — because there is no clean gap to prefer. The `>=` tie-break matches
    the old centre-delta tie-break (X wins ties), keeping byte-identity for
    pairs that already separated cleanly on the dominant axis.
    """
    sep_x = abs(bcx - acx) - (ahw + bhw)
    sep_y = abs(bcy - acy) - (ahd + bhd)
    if sep_x >= 0.0 or sep_y >= 0.0:
        # At least one axis has a clean gap: exit along the better-separated one.
        return sep_x >= sep_y
    # Fully overlapping footprints: no clean gap, keep the centre-delta basis.
    return abs(bcx - acx) >= abs(bcy - acy)


def corridor_route(cor: CorridorSpec, rooms: Mapping[str, RoomSpec]) -> Route:
    """Plan the route for a built corridor spec.

    The exit axis of each opening is derived from the FOOTPRINT SEPARATION (the
    same basis `LayoutGenerator._wall_point` now uses to cut the walls),
    computed INDEPENDENTLY per end so a genuine cross-axis pair still routes as
    an L. When the corridor records no rooms (hand-authored spec), both ends
    fall back to the endpoint delta, treating the pair as same-axis. A
    corridor with a ``side`` is a U-route (``plan_u_route``) whatever its
    rooms.
    """
    if cor.side:
        return plan_u_route((cor.from_x, cor.from_y), (cor.to_x, cor.to_y),
                            cor.side, cor.width)
    a = rooms.get(cor.from_room)
    b = rooms.get(cor.to_room)
    if a is not None and b is not None:
        ahw, ahd = a.width / 2, a.depth / 2
        bhw, bhd = b.width / 2, b.depth / 2
        # True = this opening is on an E/W wall → its stub runs along X.
        exit_from_x = exit_axis_x(a.center_x, a.center_y, ahw, ahd,
                                  b.center_x, b.center_y, bhw, bhd)
        exit_to_x = exit_axis_x(b.center_x, b.center_y, bhw, bhd,
                                a.center_x, a.center_y, ahw, ahd)
    else:
        dx = cor.to_x - cor.from_x
        dy = cor.to_y - cor.from_y
        exit_from_x = exit_to_x = abs(dx) >= abs(dy)

    return plan_route(
        (cor.from_x, cor.from_y), (cor.to_x, cor.to_y),
        exit_from_x, exit_to_x, cor.width / 2, cor.steps)


def route_footprint(route: Route, hw: float) -> List[Rect]:
    """The XY footprint of a route as a list of axis-aligned rectangles.

    One rectangle per leg (the leg segment grown by `hw` on every side) plus a
    `hw`-square at each interior corner, so the union covers the whole floor of
    the corridor including the bends. Rectangles are `(x0, y0, x1, y1)` with
    `x0 <= x1` and `y0 <= y1`.
    """
    rects: List[Rect] = []
    wps = route.waypoints
    for k in range(len(wps) - 1):
        (x0, y0), (x1, y1) = wps[k], wps[k + 1]
        rects.append((
            min(x0, x1) - hw, min(y0, y1) - hw,
            max(x0, x1) + hw, max(y0, y1) + hw,
        ))
    # Square at each interior corner, so the bend is covered flush.
    for i in range(1, len(wps) - 1):
        cx, cy = wps[i]
        rects.append((cx - hw, cy - hw, cx + hw, cy + hw))
    return rects


# --- Winding tunnels (step 23, winding-tunnels Requirement 2) ---------------------------

Point = Tuple[float, float]
#: Less sideways room than this (u) and a leg stays straight: a wander no one would see.
MIN_WANDER = 1.0


@dataclass(frozen=True)
class TunnelRules:
    """How a rough corridor's plain legs wind (``[tunnel]`` in a wall style), from the
    stock tunnel survey (winding-tunnels archive decisions 3 and 4)."""
    segment: Tuple[float, float]    # a run between two turns, measured along the leg (u)
    max_turn: float                 # the most a turn bends (degrees)
    wander: float                   # the most the centreline strays, over the leg's span
    end: float                      # each end runs straight at least this far (u)


def scaled_tunnel(rules: Optional[TunnelRules], k: float) -> Optional[TunnelRules]:
    """``rules`` with its wander times ``k`` (a zone's Winding, winding-control Req 2): the same
    object at 1, None at 0 or below (nothing winds), else a copy whose ``segment``,
    ``max_turn`` and ``end`` stay as measured."""
    if rules is None or k == 1.0:
        return rules
    if k <= 0.0:
        return None
    return TunnelRules(rules.segment, rules.max_turn, rules.wander * k, rules.end)


def _wind_limit(span: float, hw: float, clearance: float, rules: TunnelRules) -> float:
    """How far a leg's centreline may stray: ``min(clearance, wander × span)``, less what a
    mitre at a turn adds to the strip's reach. 0 when that is too little to wind."""
    reserve = hw * (1.0 / math.cos(math.radians(rules.max_turn / 2)) - 1.0)
    lim = min(clearance, rules.wander * span) - reserve
    return lim if lim >= MIN_WANDER else 0.0


def wind_leg(start: Point, end: Point, along_x: bool, hw: float, clearance: float,
             rules: TunnelRules, seed: Union[int, str]) -> List[Point]:
    """A plain leg's winding centreline, from ``start`` to ``end``, as a polyline.

    The leg runs on ``start``'s line, as a straight leg is built, and the polyline ends
    exactly at ``end``'s place along the leg on that line, so its square ends weld to the
    room or bend square as today. It runs straight for ``max(hw, rules.end)`` from each end.
    Between, segments ``rules.segment`` long (along the leg) turn by at most
    ``rules.max_turn``: every heading keeps within half of it of the leg's axis, so any turn,
    the first and last included, is at most the whole. The centreline strays at most
    ``min(clearance, wander × span)``, less a mitre's reach, so the strip (centreline ±
    ``hw``) stays within ``clearance`` of the straight strip on either side. Too little
    clearance or too short a leg gives the straight leg, ``[start, end on start's line]``.

    Pure: the same inputs give the same polyline. ``seed`` seeds its own stream (the
    corridor id and the leg index, ``winding_legs``), never a shared one."""
    ax = 0 if along_x else 1
    a0, a1 = start[ax], end[ax]
    cross = start[1 - ax]
    span = abs(a1 - a0)
    sign = 1.0 if a1 >= a0 else -1.0

    def at(u: float, v: float) -> Point:
        along = a1 if u == span else a0 + sign * u
        return (along, cross + v) if along_x else (cross + v, along)

    straight = [(float(start[0]), float(start[1])), at(span, 0.0)]
    run_in = max(hw, rules.end)
    middle = span - 2 * run_in
    lim = _wind_limit(span, hw, clearance, rules)
    lo, hi = rules.segment
    if lim <= 0.0 or middle < 2 * lo:
        return straight
    rng = random.Random(seed)
    gaps: List[float] = []
    left = middle
    # Split at least once: a middle of 2 × lo up to hi takes one bend (a stock-length
    # tunnel, ~86 u, winds), a longer one as many as its gaps need.
    while left > hi or (not gaps and left >= 2 * lo):
        g = rng.uniform(lo, max(lo, min(hi, left - lo)))
        gaps.append(g)
        left -= g
    gaps.append(left)
    if len(gaps) < 2:
        return straight
    us = [run_in]
    for g in gaps:
        us.append(us[-1] + g)
    us[-1] = span - run_in
    slope = math.tan(math.radians(rules.max_turn / 2))
    n = len(us) - 1
    vs = [0.0]
    for i in range(1, n):
        du, rest = us[i] - us[i - 1], us[n] - us[i]
        v_lo = max(vs[-1] - slope * du, -lim, -slope * rest)
        v_hi = min(vs[-1] + slope * du, lim, slope * rest)
        vs.append(rng.uniform(v_lo, v_hi))
    vs.append(0.0)
    return [straight[0]] + [at(u, v) for u, v in zip(us, vs)] + [straight[1]]


def wind_seed(cor: CorridorSpec, k: int, start: Point) -> str:
    """Leg ``k``'s own stream: the corridor's id and the leg's index (and where it starts,
    so two zones' ``corr_0`` don't wind alike)."""
    return f"wind:{cor.id}:{k}:{start[0]:.2f},{start[1]:.2f}"


def tunnel_for(cor: CorridorSpec, spec) -> Optional[TunnelRules]:
    """The rules a reader re-winds ``cor``'s legs by: the spec's scaled tunnel
    (``wall_styles.tunnel_rules_for``), read only when a leg winds (``cor.wind``), else None
    (``winding_legs`` then winds nothing and reads no rules)."""
    if not any(cor.wind):
        return None
    from .wall_styles import tunnel_rules_for     # wall_styles imports this module
    return tunnel_rules_for(spec)


def winding_legs(cor: CorridorSpec, rooms: Mapping[str, RoomSpec],
                 rules: Optional[TunnelRules] = None) -> List[Optional[List[Point]]]:
    """One entry per leg of ``cor``'s route: the winding centreline of a leg ``cor.wind``
    lets wind, over the leg's built span (``MeshBuilder._leg_ends``), else None. The one
    source the mesh, decor and map read, so they agree. ``rules`` defaults to the tunnel of
    the wall styles (``wall_styles.tunnel_rules``), the stock tunnel: a zone with a Winding
    other than 1 must pass its own (``wall_styles.tunnel_rules_for(spec)``), or
    ``_wind_limit`` clips its legs at the stock wander."""
    route = corridor_route(cor, rooms)
    n = len(route.waypoints) - 1
    if not any(cor.wind):
        return [None] * n
    from .geometry import MeshBuilder       # geometry imports this module
    if rules is None:
        from .wall_styles import tunnel_rules
        rules = tunnel_rules()
    waypoints = list(route.waypoints)
    zs, _ = MeshBuilder._waypoint_zs(waypoints, None if route.carry < 0 else route.carry,
                                     cor.from_z, cor.to_z)
    out: List[Optional[List[Point]]] = []
    for k in range(n):
        ends = MeshBuilder._leg_ends(waypoints, k, cor.width / 2, zs)
        limit = cor.wind[k] if k < len(cor.wind) else 0.0
        if ends is None or limit <= 0 or rules is None:
            out.append(None)
            continue
        line = wind_leg(ends[0], ends[1], route.axes[k], cor.width / 2, limit, rules,
                        wind_seed(cor, k, ends[0]))
        out.append(line if len(line) > 2 else None)
    return out


# --- Winding routes (step 25, winding-routes Requirement 1) -----------------------------

def route_seed(cor: CorridorSpec) -> str:
    """A route line's own stream: the corridor's id and where it starts."""
    return f"wind:{cor.id}:route:{cor.from_x:.2f},{cor.from_y:.2f}"


def _unit(p: Point, q: Point) -> Optional[Point]:
    d = math.hypot(q[0] - p[0], q[1] - p[1])
    return None if d < 1e-9 else ((q[0] - p[0]) / d, (q[1] - p[1]) / d)


def _turn(d0: Point, d1: Point) -> float:
    """The signed turn from heading ``d0`` to ``d1`` (radians, left positive)."""
    return math.atan2(d0[0] * d1[1] - d0[1] * d1[0], d0[0] * d1[0] + d0[1] * d1[1])


def _cuts(lengths: Sequence[float], lefts: Sequence[bool], run: float, lo: float) -> List[float]:
    """How far each bend of the route is cut back from its corner, along both legs: the most
    that leaves every inner leg at least ``lo`` straight, or nothing straight where two cuts
    meet on a leg between bends of opposite turn (a Z's jog, one diagonal). The first and last
    legs keep their run-outs (``run``) whole."""
    n = len(lengths) - 1                    # bends
    cuts = []
    for i in range(n):
        own = [lengths[i] - (run if i == 0 else 0.0), lengths[i + 1] - (run if i + 1 == n else 0.0)]
        cuts.append(max(0.0, min(own)))
    for k in range(1, n):                   # inner leg k, between bends k-1 and k
        length = lengths[k]
        a, b = cuts[k - 1], cuts[k]
        if a + b <= length - lo:
            continue
        if lefts[k - 1] != lefts[k] and a + b >= length:
            # A Z's jog: the two cuts meet, its two diagonals one straight line.
            a = min(a, max(length - b, length / 2))
            b = length - a
        else:
            spare = max(0.0, length - lo)
            over = a + b - spare
            a, b = max(0.0, a - over / 2), max(0.0, b - over / 2)
            if a + b > spare:
                a = b = spare / 2
        cuts[k - 1], cuts[k] = a, b
    return cuts


def _chamfer(corner: Point, d_in: Point, d_out: Point, cut: float, turns: int) -> List[Point]:
    """A 90 degree bend at ``corner`` cut as ``turns`` equal turns, leaving the incoming leg
    ``cut`` before the corner and joining the outgoing leg ``cut`` past it: the turn vertices
    of a polygon about a circle tangent to both legs."""
    if cut <= 1e-6 or turns <= 1:
        return [corner]
    step = _turn(d_in, d_out) / turns
    radius = cut / (1.0 - math.tan(abs(step) / 2))
    side = 2 * radius * math.tan(abs(step) / 2)
    p = (corner[0] - d_in[0] * cut, corner[1] - d_in[1] * cut)
    out = [p]
    heading = math.atan2(d_in[1], d_in[0])
    for _ in range(turns - 1):
        heading += step
        p = (p[0] + math.cos(heading) * side, p[1] + math.sin(heading) * side)
        out.append(p)
    out[-1] = (corner[0] + d_out[0] * cut, corner[1] + d_out[1] * cut)
    return out


def _wind_run(p: Point, q: Point, hw: float, rules: TunnelRules, seed: int) -> List[Point]:
    """``wind_leg`` along any heading: the run from ``p`` to ``q`` wound in its own frame."""
    span = math.hypot(q[0] - p[0], q[1] - p[1])
    d = ((q[0] - p[0]) / span, (q[1] - p[1]) / span)
    local = wind_leg((0.0, 0.0), (span, 0.0), True, hw, float("inf"), rules, seed)
    pts = [(p[0] + u * d[0] - v * d[1], p[1] + u * d[1] + v * d[0]) for u, v in local]
    pts[0], pts[-1] = p, q
    return pts


def _tidy(line: List[Point], keep: Sequence[int]) -> List[Point]:
    """``line`` without repeated points and without straight-through vertices, except those
    at indices ``keep`` (the run-outs' ends)."""
    out: List[Point] = []
    kept: List[bool] = []
    for i, p in enumerate(line):
        if out and math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) < 1e-6:
            kept[-1] = kept[-1] or i in keep
            continue
        out.append(p)
        kept.append(i in keep)
    i = 1
    while i < len(out) - 1:
        a, b = _unit(out[i - 1], out[i]), _unit(out[i], out[i + 1])
        if not kept[i] and abs(_turn(a, b)) < 1e-9:
            del out[i], kept[i]
        else:
            i += 1
    return out


def wind_route(route: Route, hw: float, rules: TunnelRules, seed: Union[int, str],
               wander: bool = True) -> Optional[List[Point]]:
    """A corridor route's winding centreline, from its first opening to its last, as one
    polyline (winding-routes design "The route line"), or None when nothing on it can wind.

    From each opening the line runs straight ``max(hw, rules.end)`` along its exit axis (the
    run-outs; ``line[1]`` and ``line[-2]`` are their ends). Each 90 degree bend between them
    is cut as a chamfer of ``ceil(90 / max_turn)`` equal turns, cut back as far as leaves every
    inner leg at least ``segment[0]`` straight (or none, where a Z's two diagonals meet). With
    ``wander``, each straight run between is wound as ``wind_leg`` winds a leg (its own
    straight ``hw`` at each end, a wander of at most ``wander`` x its span). No turn exceeds
    ``rules.max_turn``. Nothing here measures clearance: ``transitions.measure_winds`` checks
    the line against the spec.

    Pure: the same inputs give the same line; ``seed`` (``route_seed``) seeds its own stream."""
    wps = [(float(x), float(y)) for x, y in route.waypoints]
    n = len(wps) - 1
    run = max(hw, rules.end)
    lengths = [math.hypot(wps[k + 1][0] - wps[k][0], wps[k + 1][1] - wps[k][1]) for k in range(n)]
    if min(lengths) < 1e-6 or lengths[0] < run or lengths[-1] < run or (n == 1 and lengths[0] < 2 * run):
        return None
    dirs = [_unit(wps[k], wps[k + 1]) for k in range(n)]
    for i in range(n - 1):
        if abs(abs(_turn(dirs[i], dirs[i + 1])) - math.pi / 2) > 1e-6:
            return None                     # a route bends square; anything else isn't one
    turns = max(1, int(math.ceil(90.0 / rules.max_turn - 1e-9)))
    a_out = (wps[0][0] + dirs[0][0] * run, wps[0][1] + dirs[0][1] * run)
    b_in = (wps[n][0] - dirs[-1][0] * run, wps[n][1] - dirs[-1][1] * run)

    # The bones: the run-outs' ends, and each bend cut as its chamfer.
    lefts = [_turn(dirs[i], dirs[i + 1]) > 0 for i in range(n - 1)]
    cuts = _cuts(lengths, lefts, run, rules.segment[0])
    bones: List[Point] = [a_out]
    for i in range(n - 1):
        bones += _chamfer(wps[i + 1], dirs[i], dirs[i + 1], cuts[i], turns)
    bones.append(b_in)
    bones = _tidy(bones, (0, len(bones) - 1))

    line: List[Point] = [wps[0], bones[0]]
    if wander:
        rng = random.Random(seed)
        inner = TunnelRules(rules.segment, rules.max_turn, rules.wander, 0.0)
        for p, q in zip(bones, bones[1:]):
            line += _wind_run(p, q, hw, inner, rng.getrandbits(64))[1:]
    else:
        line += bones[1:]
    line.append(wps[n])
    line = _tidy(line, (1, len(line) - 2))
    if len(line) < 4:
        return None
    # Every turn within the rule, the first and last included.
    for i in range(1, len(line) - 1):
        a, b = _unit(line[i - 1], line[i]), _unit(line[i], line[i + 1])
        if abs(math.degrees(_turn(a, b))) > rules.max_turn + 1e-6:
            return None
    # Only the route's own legs again (no bend cut, no wander): nothing wound.
    if len(line) == n + 3 and all(math.hypot(p[0] - q[0], p[1] - q[1]) < 1e-6
                                  for p, q in zip(line[2:-2], wps[1:-1])):
        return None
    return line


def strip_corners(line: Sequence[Point], hw: float) -> Optional[List[Tuple[Point, Point]]]:
    """The strip ``hw`` either side of ``line``, as ``MeshBuilder._add_winding_leg`` builds it:
    (left, right) corners at each vertex, mitred where the line turns. None when a mitre would
    fold an edge back on itself."""
    pts = [(float(x), float(y)) for x, y in line]
    m = len(pts) - 1
    seg = [math.hypot(pts[j + 1][0] - pts[j][0], pts[j + 1][1] - pts[j][1]) for j in range(m)]
    if m < 1 or min(seg) < 1e-6:
        return None
    dirs = [((pts[j + 1][0] - pts[j][0]) / seg[j], (pts[j + 1][1] - pts[j][1]) / seg[j]) for j in range(m)]
    lefts = [(-dy, dx) for dx, dy in dirs]
    corners = []
    for i in range(m + 1):
        ns = [lefts[j] for j in (i - 1, i) if 0 <= j < m]
        mx, my = sum(v[0] for v in ns), sum(v[1] for v in ns)
        size = math.hypot(mx, my)
        mx, my = mx / size, my / size
        reach = hw / (mx * ns[0][0] + my * ns[0][1])
        px, py = pts[i]
        corners.append(((px + mx * reach, py + my * reach), (px - mx * reach, py - my * reach)))
    for j in range(m):
        for side in (0, 1):
            a, b = corners[j][side], corners[j + 1][side]
            if (b[0] - a[0]) * dirs[j][0] + (b[1] - a[1]) * dirs[j][1] <= 1e-6:
                return None
    return corners
