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

`Route` records the waypoints (one point per bend, >= 2), which axis each leg
runs along, which leg carries the entire elevation change, and the kind. The
geometry builder's `_emit_route` consumes `waypoints`/`axes`/`carry` directly,
so this module must reproduce them byte-for-byte with the former inline logic.

EQ coordinate convention: Z is up; routes live in the XY plane.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Mapping, Optional, Tuple

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
    `kind`       "straight" | "z" | "l".
    """

    waypoints: Tuple[Tuple[float, float], ...]   # >= 2 points
    axes: Tuple[bool, ...]                        # True = leg runs along X
    carry: int                                    # leg that carries the rise
    kind: str                                     # "straight" | "z" | "l"


def plan_route(from_xy: Tuple[float, float], to_xy: Tuple[float, float],
               exit_from_x: bool, exit_to_x: bool,
               hw: float, steps: int) -> Route:
    """Decide the straight / Z / L route between two openings.

    `from_xy`/`to_xy`  the two wall-opening points.
    `exit_from_x`      True when the `from` opening is on an E/W wall, so its
                       stub runs along X; likewise `exit_to_x` for `to`.
    `hw`               corridor half-width (sets the straight-vs-bend slack).
    `steps`            > 0 for a staircase; a Z-corridor staircase must ride the
                       interior jog (leg 1) so the flat end stubs stay flush.

    The straight/Z/L selection and the staircase carry rule mirror the former
    inline logic in `MeshBuilder.add_corridor` exactly, so the emitted mesh is
    byte-identical. `carry == -1` means "carry the longest leg" (ramps).
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
        # A STAIRCASE must ride the interior jog (leg 1); a smooth RAMP can ride
        # the longest leg (carry = -1) for the gentlest grade.
        if steps > 0:
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
    fall back to the endpoint delta, treating the pair as same-axis.
    """
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
