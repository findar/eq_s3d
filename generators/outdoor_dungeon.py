"""
generators/outdoor_dungeon.py
-----------------------------
The outdoor dungeon's Envelope, built from the host terrain (outdoor-dungeon
design "Envelope", task 4), and its Entrance (design "Entrance", task 5).

A host-hill wilderness spec (``wilderness_spec(..., landform=...)``) is built
to its TER; the Envelope's surface is that TER, interpolated exactly as the
client walks it (two triangles per quad, split along the (i, j)-(i+1, j+1)
diagonal), not the design matrix. The footprint is the hill region: a disc at
the placed Landform's centre out to where its relief falls to half (radius
plus half the flank). The Rock_Cover and floor limit are the survey defaults
(design finding 4).

``layout_in_envelope`` sizes the rooms to the Envelope, not to the dungeon
style profile's whole-zone floor area (which would give rooms the size of
the hill), so the default room count fits.

``plan_entrance`` picks a room wall facing the approach, a Tunnel strip one
terrain cell wide and the vertex row its portal opens at;
``build_outdoor_ter`` digs the Apron, cuts the Mouth and returns one TER
holding the terrain and the dungeon.

A build (task 6) is one ``ZoneSpec``: ``outdoor_dungeon_spec`` returns the
host wilderness spec (terrain payload, regions, materials, the outdoor
Spawn as safe point) carrying the dungeon's rooms, corridors, lights and
materials, plus a ``dungeon`` section in the wilderness payload recording
the Entrance. The terrain backend builds it with
``build_outdoor_dungeon_ter``; the pipeline gates it with
``outdoor_dungeon_report`` (the bowl check on the open ground, then every
room reached from the outdoor Spawn and every corridor continuous).

The Mouth is built on the terrain grid so it stitches exactly. The Tunnel
runs between two adjacent vertex columns and ends at vertex row ``m``. The
one terrain cell between rows ``m`` and ``m + 1`` over the strip (the slope
in front of the portal) is removed and replaced by a flat floor at the Apron
height, two vertical jambs (from that floor up to the neighbouring cells'
edges) and a headwall (from the Tunnel's ceiling up to the row-``m`` terrain
edge). Every edge of those pieces is an edge of a terrain triangle or of the
Tunnel's open end, so nothing can be fallen or seen through. The Apron is
the terrain beyond row ``m`` lowered to a cone that climbs at ``MAX_GRADE``
from the notch's outer edge until it meets the ground; nothing behind row
``m`` changes.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from core.ter import MAGIC_TERRAIN, Material, Polygon, TerFile, Vertex
from generators.envelope import Envelope, EnvelopeFitError
from generators.geometry import MeshBuilder, _ensure_materials
from generators import semantics
from generators.layout import LayoutGenerator
from generators.routing import corridor_route, route_footprint
from generators.wilderness.build import (DEFAULT_BIOME, build_wilderness_ter,
                                         landscape_for, wilderness_spec)
from generators.wilderness.matrix import (DEFAULT_HOST_HILL, OUTDOOR_DUNGEON_ZONE_SIZE,
                                          Landform)
from generators.wilderness.biome import load_biome_kit
from generators.zone_spec import MaterialSpec, ZoneSpec

#: Minimum terrain left above any ceiling (design finding 4: stock p10 rock
#: is 12-22 u).
ROCK_COVER: float = 24.0
#: How far below the Entrance's floor the dungeon may reach (finding 4:
#: covered floor sits at most ~130 u below the open ground near it).
FLOOR_DEPTH: float = 150.0
#: Rooms laid out under the default Host_Hill.
DEFAULT_ROOMS: int = 5
#: When a dungeon can't be planned with every room asked for (they don't all
#: fit, or the entrance room sits too deep for a Tunnel), it is planned again
#: with rooms this much smaller (in side), up to FIT_SHRINKS times. Rooms are
#: sized from the race's bands like any dungeon's (step 7 task 17; before
#: stock scale they were sized to the Envelope, 80 u tall), so a shrink is a
#: step down the bands (``layout_in_envelope``) and never leaves them. A
#: theme's room types and the climax's role scale rooms up after they are
#: sized, and one tall room under the flank sinks the whole layout
#: (``_fit_floors``).
FIT_SHRINK: float = 0.85
FIT_SHRINKS: int = 3
#: Steepest Tunnel ramp and Apron cone (rise / run): the layout's grade cap.
MAX_GRADE: float = 0.5
#: Furthest (in terrain rows) the Apron's trench may run to meet the ground.
APRON_REACH: int = 8
#: Shortest Tunnel from the room wall to the portal.
MIN_TUNNEL: float = 20.0
#: Wall left either side of the Tunnel's doorway.
DOOR_MARGIN: float = 8.0
#: Biome-kit materials for the Mouth's floor, and for its jambs and headwall.
MOUTH_FLOOR_MATERIAL = "wild_dirt"
MOUTH_WALL_MATERIAL = "wild_cliff"

_SIDE_STEP = {"N": (0.0, 1.0), "S": (0.0, -1.0), "E": (1.0, 0.0), "W": (-1.0, 0.0)}


def _grid_surface(z: np.ndarray, origin: Tuple[float, float], resolution: float
                  ) -> Callable[[np.ndarray, np.ndarray], np.ndarray]:
    """Height at XY of the triangulated vertex grid ``z`` (see ``ter_surface``)."""
    nx, ny = z.shape
    ox, oy = origin
    res = float(resolution)

    def surface(x, y):
        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        fx = np.clip((x - ox) / res - 0.5, 0.0, nx - 1.0)
        fy = np.clip((y - oy) / res - 0.5, 0.0, ny - 1.0)
        i = np.minimum(np.floor(fx).astype(int), nx - 2)
        j = np.minimum(np.floor(fy).astype(int), ny - 2)
        u, v = fx - i, fy - j
        za, zb = z[i, j], z[i + 1, j]
        zc, zd = z[i + 1, j + 1], z[i, j + 1]
        lower = za + u * (zb - za) + v * (zc - zb)      # triangle a-b-c (u >= v)
        upper = za + v * (zd - za) + u * (zc - zd)      # triangle a-c-d (v > u)
        return np.where(u >= v, lower, upper)

    return surface


def ter_surface(ter: TerFile, origin: Tuple[float, float], resolution: float,
                shape: Tuple[int, int]) -> Callable[[np.ndarray, np.ndarray], np.ndarray]:
    """Height of a heightfield TER at XY, vectorised.

    The TER's first ``nx * ny`` vertices are the grid (vertex ``i * ny + j``
    at the centre of fine cell ``(i, j)``); later vertices (the water surface)
    are ignored. Each quad is two triangles split along its (i, j)-(i+1, j+1)
    diagonal, as ``build_wilderness_ter`` emits them. Points beyond the grid
    take the nearest edge's height."""
    nx, ny = shape
    z = np.array([v.z for v in ter.vertices[:nx * ny]], dtype=np.float64).reshape(nx, ny)
    return _grid_surface(z, origin, resolution)


def host_footprint(landform: Landform, sides: int = 64) -> Tuple[Tuple[float, float], ...]:
    """The hill region: a ``sides``-gon at the Landform's centre out to where
    its relief falls to half (``radius + flank / 2``)."""
    cx, cy = landform.centre
    r = landform.radius + landform.flank / 2.0
    return tuple((cx + r * math.cos(2 * math.pi * k / sides),
                  cy + r * math.sin(2 * math.pi * k / sides)) for k in range(sides))


def bowl_interior(land) -> Tuple[float, float, float, float]:
    """The bowl's interior ``(x0, y0, x1, y1)``: the zone less the Rim's
    boundary strips (``bowl._segment_band``, the off-map bands the bowl gate
    tests). Nothing of the dungeon may sit in a strip: the gate reads any
    reached floor there as the flood escaping the bowl, and a room there is
    under the map's edge."""
    from generators.wilderness.bowl import _segment_band

    synth, matrix = land.synth, land.matrix
    nx, ny = synth.heights.shape
    ox, oy = synth.origin
    res = float(synth.resolution)
    x0, y0, x1, y1 = ox, oy, ox + nx * res, oy + ny * res
    for k, ec in enumerate(matrix.edges):
        band = _segment_band(synth, matrix, k)
        if band is None:
            continue
        bx0, by0, bx1, by1 = band
        if ec.side == "W":
            x0 = max(x0, bx1)
        elif ec.side == "E":
            x1 = min(x1, bx0)
        elif ec.side == "S":
            y0 = max(y0, by1)
        elif ec.side == "N":
            y1 = min(y1, by0)
    return x0, y0, x1, y1


def clip_to_rect(poly, rect) -> Tuple[Tuple[float, float], ...]:
    """Polygon ``poly`` clipped to the axis-aligned ``rect`` (x0, y0, x1, y1)
    (Sutherland-Hodgman; a convex polygon stays convex)."""
    x0, y0, x1, y1 = rect
    planes = ((0, x0, 1.0), (0, x1, -1.0), (1, y0, 1.0), (1, y1, -1.0))
    pts = [tuple(map(float, p)) for p in poly]
    for axis, edge, sign in planes:
        if not pts:
            break
        out = []
        for k, cur in enumerate(pts):
            prev = pts[k - 1]
            cin = sign * (cur[axis] - edge) >= 0.0
            pin = sign * (prev[axis] - edge) >= 0.0
            if cin != pin:
                t = (edge - prev[axis]) / (cur[axis] - prev[axis])
                out.append((prev[0] + t * (cur[0] - prev[0]),
                            prev[1] + t * (cur[1] - prev[1])))
            if cin:
                out.append(cur)
        pts = out
    return tuple(pts)


def approach_foot(landform: Landform) -> Tuple[float, float]:
    """Where the Landform's flank meets the open ground on its approach side."""
    dx, dy = _SIDE_STEP[landform.approach]
    reach = landform.radius + landform.flank
    return landform.centre[0] + dx * reach, landform.centre[1] + dy * reach


def host_envelope(spec: ZoneSpec, ter: TerFile, *,
                  rock_cover: float = ROCK_COVER,
                  entrance_floor: Optional[float] = None) -> Envelope:
    """The Envelope under a host-hill spec's built terrain.

    ``entrance_floor`` defaults to the TER height at the hill's foot on the
    approach side (the open ground the Entrance will open onto); the floor
    limit is ``FLOOR_DEPTH`` below it. That foot is the Envelope's entry, so
    the layout's entrance room is the one nearest it."""
    land = landscape_for(spec)
    landform = land.matrix.landform
    if landform is None:
        raise ValueError(f"spec {spec.name!r} has no Landform to build an Envelope under")
    surface = ter_surface(ter, land.synth.origin, land.synth.resolution,
                          land.bowl.heights.shape)
    foot = approach_foot(landform)
    if entrance_floor is None:
        entrance_floor = float(surface(*foot))
    # The hill disc can reach past the bowl's interior (the default hill's
    # does, under the W Rim); the Envelope is the disc clipped to it.
    footprint = clip_to_rect(host_footprint(landform), bowl_interior(land))
    return Envelope(footprint, entrance_floor - FLOOR_DEPTH,
                    surface, rock_cover, entry=foot)


def tunnel_wall(resolution: float) -> float:
    """The shortest room wall that can hold a Tunnel on a terrain grid of
    ``resolution``: one cell between two adjacent vertex columns, with
    ``DOOR_MARGIN`` of wall either side. (Whether a wall this short holds
    one depends on where the grid falls; ``plan_dungeon`` tries the graph
    engine's other facings, which move the room against the grid. Asking for
    two cells, so any alignment fits, made entrance rooms big enough to push
    other layouts out of planning.)"""
    return float(resolution) + 2.0 * DOOR_MARGIN


def layout_in_envelope(name: str, seed: Optional[int], envelope: Envelope,
                       room_count: int = DEFAULT_ROOMS, scale: float = 1.0,
                       engine=None, facing: int = 0, entrance_side: float = 0.0,
                       **kwargs) -> Tuple[ZoneSpec, List[str]]:
    """A box-dungeon layout inside ``envelope``.

    Rooms are sized from the race's bands as in any dungeon; ``scale`` (< 1
    on a shrink) moves them down the bands by that factor in side
    (``size_shift`` = log(scale) over the log of the side band's max/min),
    still inside them. ``engine`` is the
    Layout_Engine (``None`` is classic; see ``ai.expand.layout_engine``); the
    layout's ``layout`` field carries its record (``None`` for classic).
    An engine that takes them (the graph engine) lays out with ``facing``
    (which of its ranked turns faces the entrance room toward the way in)
    and ``entrance_side`` (the entrance room's least side, not scaled);
    the engine's own values are restored afterwards.
    Returns the layout and the generator's warnings (``rooms_reduced`` when
    rooms were dropped)."""
    gen = LayoutGenerator("dungeon", seed=seed, engine=engine)
    lo, hi = semantics.ROOM_SIDE_BAND
    gen.size_shift = math.log(scale) / math.log(hi / lo)
    options = hasattr(engine, "facing") and hasattr(engine, "entrance_side")
    if options:
        saved = (engine.facing, engine.entrance_side)
        engine.facing, engine.entrance_side = facing, entrance_side
    try:
        spec = gen.generate(name, room_count=room_count, envelope=envelope, **kwargs)
    finally:
        if options:
            engine.facing, engine.entrance_side = saved
    spec.layout = gen.layout_record
    return spec, list(gen.warnings)


def plan_dungeon(host: ZoneSpec, ter: TerFile, envelope: Envelope, name: str,
                 seed: Optional[int], room_count: int = DEFAULT_ROOMS,
                 engine=None, **kwargs) -> Tuple[ZoneSpec, List[str], "Entrance"]:
    """The dungeon under ``host``: its layout (with warnings) and the
    Entrance into its entrance room. ``engine`` is the one Layout_Engine every
    shrink step lays out with (built once by the caller, not re-chosen per
    scale).

    Rooms start at the size the Envelope suggests and shrink by
    ``FIT_SHRINK`` (up to ``FIT_SHRINKS`` times) until every room asked for
    fits and the entrance room takes a Tunnel (each layout first shifted so
    its entrance wall holds a terrain cell, :func:`align_to_grid`). An engine
    with ``facings``
    (the graph engine) tries each of its turns of the layout at a size before
    shrinking it, best-facing first, and keeps its entrance room at least
    :func:`tunnel_wall` on a side through every shrink. If no size keeps them
    all, the largest plan that drops rooms wins; if none plans at all, the
    last ``PLAN_ERRORS`` error is raised."""
    reduced, error = None, None
    facings = int(getattr(engine, "facings", 1)) if engine is not None else 1
    side = tunnel_wall(landscape_for(host).synth.resolution) if facings > 1 else 0.0
    for shrink in range(FIT_SHRINKS + 1):
        for facing in range(facings):
            try:
                layout, warnings = layout_in_envelope(
                    name, seed, envelope, room_count, scale=FIT_SHRINK ** shrink,
                    engine=engine, facing=facing, entrance_side=side, **kwargs)
                # The Tunnel opens into the layout's entrance room, so the
                # pacing (depth, climax, keys) runs from the way in.
                first = next(r.id for r in layout.rooms if r.role == "entrance")
                layout = align_to_grid(host, ter, envelope, layout, first)
                entrance = plan_entrance(host, ter, layout, room_id=first)
            except PLAN_ERRORS as e:
                error = e
                continue
            if len(layout.rooms) == room_count:
                return layout, warnings, entrance
            reduced = reduced or (layout, warnings, entrance)
    if reduced is None:
        raise error
    return reduced


#: How far (u) ``align_to_grid`` may lower a moved layout, in steps of
#: ALIGN_DROP_STEP, to keep the rock cover over it: the fitted layout sits as
#: high as the cover allows, so moving it sideways under a sloping flank
#: needs it a little lower.
ALIGN_DROP: float = 40.0
ALIGN_DROP_STEP: float = 4.0


def _translate(spec: ZoneSpec, axis: int, d: float, dz: float = 0.0) -> None:
    """Move a layout's every point by ``d`` along ``axis`` (0 = x, 1 = y)
    and ``dz`` up."""
    def mv(x, y):
        return (x + d, y) if axis == 0 else (x, y + d)
    for r in spec.rooms:
        r.center_x, r.center_y = mv(r.center_x, r.center_y)
        r.floor_z += dz
    for c in spec.corridors:
        c.from_x, c.from_y = mv(c.from_x, c.from_y)
        c.to_x, c.to_y = mv(c.to_x, c.to_y)
        c.from_z += dz
        c.to_z += dz
    for lt in spec.lights:
        lt.x, lt.y = mv(lt.x, lt.y)
        lt.z += dz
    for rg in spec.regions:
        rg.center_x, rg.center_y = mv(rg.center_x, rg.center_y)
        rg.center_z += dz
    for g in spec.gates:
        g.lock_x, g.lock_y = mv(g.lock_x, g.lock_y)
        g.key_x, g.key_y = mv(g.key_x, g.key_y)
        g.lock_z += dz
        g.key_z += dz
    sx, sy, sz = spec.safe_point
    spec.safe_point = (*mv(sx, sy), sz + dz)


def align_to_grid(host: ZoneSpec, ter: TerFile, envelope: Envelope, layout: ZoneSpec,
                  room_id: str) -> ZoneSpec:
    """``layout`` moved across the approach (by the least amount, under half
    a terrain cell) so that room ``room_id``'s wall facing the approach holds
    a whole cell between two vertex columns with ``DOOR_MARGIN`` either side,
    which a Tunnel needs, and lowered as little as keeps it in the Envelope
    (at most ``ALIGN_DROP``); unchanged when the wall already holds a cell,
    is too short, or no such move fits.

    Stock-scale rooms (step 7 task 17) are ~56-120 u across against a 40 u
    cell, so whether a wall holds a cell used to be down to where the grid
    happened to fall."""
    land = landscape_for(host)
    landform = land.matrix.landform
    if landform is None:
        return layout
    ax, _out = _RUN[landform.approach]
    cross = 1 - ax
    grid = _host_grid(host, ter)
    room = next(r for r in layout.rooms if r.id == room_id)
    half = (room.depth if ax == 0 else room.width) / 2
    mid = room.center_y if ax == 0 else room.center_x
    lo, hi = mid - half + DOOR_MARGIN, mid + half - DOOR_MARGIN
    if hi - lo < grid.res:
        return layout
    best = None
    for q in range(grid.size(cross) - 1):
        c0, c1 = grid.coord(cross, q), grid.coord(cross, q + 1)
        s0, s1 = c1 - hi, c0 - lo          # shifts that put cell q in the wall
        s = min(max(0.0, s0), s1)
        if s0 <= s1 + 1e-9 and (best is None or abs(s) < abs(best)):
            best = s
    if best is None or abs(best) < 1e-9 or abs(best) > grid.res / 2:
        return layout
    drop = 0.0
    while drop <= ALIGN_DROP + 1e-9:
        moved = copy.deepcopy(layout)
        _translate(moved, cross, best, -drop)
        if LayoutGenerator.fits(moved, envelope):
            return moved
        drop += ALIGN_DROP_STEP
    return layout


# ---------------------------------------------------------------------------
# Entrance
# ---------------------------------------------------------------------------

class EntranceError(ValueError):
    """No room wall gives a Tunnel that fits under the host terrain."""


#: Fine-cell types the Apron never digs, nor within a cell of.
_UNDIGGABLE = ("mountain_rim", "zoneline_gap", "water", "river", "lava")

#: Approach side -> (run axis: 0 = X, 1 = Y; outward sign along it).
_RUN = {"W": (0, -1), "E": (0, 1), "S": (1, -1), "N": (1, 1)}


@dataclass(frozen=True)
class Entrance:
    """Where the Tunnel leaves a room and opens onto the Apron.

    The Tunnel runs along X (``axis`` 0) or Y (1), away from the room in
    direction ``outward``, between terrain vertex columns ``cross`` and
    ``cross + 1``, from the room's wall plane ``wall`` to vertex row
    ``portal``. It ramps from ``room_floor`` at the wall to ``floor`` (the
    Apron's height) at the portal, and is ``height`` tall."""
    room_id: str
    side: str
    axis: int
    outward: int
    cross: int
    portal: int
    wall: float
    room_floor: float
    floor: float
    height: float

    def to_dict(self) -> Dict:
        return {"room": self.room_id, "side": self.side, "axis": self.axis,
                "outward": self.outward, "cross": self.cross, "portal": self.portal,
                "wall": self.wall, "room_floor": self.room_floor,
                "floor": self.floor, "height": self.height}

    @classmethod
    def from_dict(cls, d: Dict) -> "Entrance":
        return cls(room_id=d["room"], side=d["side"], axis=int(d["axis"]),
                   outward=int(d["outward"]), cross=int(d["cross"]),
                   portal=int(d["portal"]), wall=float(d["wall"]),
                   room_floor=float(d["room_floor"]), floor=float(d["floor"]),
                   height=float(d["height"]))


class _Grid:
    """The host TER's vertex grid, addressed along a run and a cross axis."""

    def __init__(self, ter: TerFile, origin, resolution: float, shape):
        self.nx, self.ny = shape
        self.origin = (float(origin[0]), float(origin[1]))
        self.res = float(resolution)
        self.z = np.array([v.z for v in ter.vertices[:self.nx * self.ny]],
                          dtype=np.float64).reshape(self.nx, self.ny)

    def coord(self, axis: int, k: int) -> float:
        """World coordinate of vertex index ``k`` along ``axis``."""
        return self.origin[axis] + (k + 0.5) * self.res

    def size(self, axis: int) -> int:
        return self.nx if axis == 0 else self.ny

    def ij(self, axis: int, run: int, cross: int) -> Tuple[int, int]:
        return (run, cross) if axis == 0 else (cross, run)

    def point(self, axis: int, run: int, cross: int, z: float) -> Tuple[float, float, float]:
        r, c = self.coord(axis, run), self.coord(1 - axis, cross)
        return (r, c, z) if axis == 0 else (c, r, z)


def _host_grid(host: ZoneSpec, ter: TerFile) -> _Grid:
    land = landscape_for(host)
    return _Grid(ter, land.synth.origin, land.synth.resolution, land.bowl.heights.shape)


def _strip_rect(axis: int, a: float, b: float, c0: float, c1: float):
    lo, hi = min(a, b), max(a, b)
    return (lo, c0, hi, c1) if axis == 0 else (c0, lo, c1, hi)


def _overlaps(r, s, eps: float = 1e-6) -> bool:
    return (r[0] < s[2] - eps and s[0] < r[2] - eps
            and r[1] < s[3] - eps and s[1] < r[3] - eps)


def _apron(grid: _Grid, e: Entrance) -> Tuple[np.ndarray, bool]:
    """Terrain heights with the Apron dug, and whether it reaches the ground.

    The Apron is a trench: the strip's columns and one either side, from
    row ``portal + outward`` outward, lowered to a cone rising at
    ``MAX_GRADE`` from the notch's outer edge (heights only fall; that edge's
    two vertices sit at ``floor``). It stops at the first row whose strip
    vertices are already at or under the cone: the trench has met the
    ground. If it hasn't within ``APRON_REACH`` rows, the second value is
    False and the Entrance is unusable."""
    ax, out, q = e.axis, e.outward, e.cross
    edge = grid.coord(ax, e.portal + out)
    c0, c1 = grid.coord(1 - ax, q), grid.coord(1 - ax, q + 1)
    z = grid.z.copy()
    for step in range(APRON_REACH + 1):
        k = e.portal + out * (1 + step)
        if not 0 <= k < grid.size(ax):
            return z, False
        d = abs(grid.coord(ax, k) - edge)
        if step > 0 and all(z[grid.ij(ax, k, c)] <= e.floor + MAX_GRADE * d + 1e-6
                            for c in (q, q + 1)):
            return z, True
        for c in range(q - 1, q + 3):
            if not 0 <= c < grid.size(1 - ax):
                continue
            lateral = max(0.0, c0 - grid.coord(1 - ax, c), grid.coord(1 - ax, c) - c1)
            cone = e.floor + MAX_GRADE * math.hypot(d, lateral)
            ij = grid.ij(ax, k, c)
            z[ij] = e.floor if step == 0 and c in (q, q + 1) else min(z[ij], cone)
    return z, False


def _tunnel_covered(grid: _Grid, e: Entrance, cover: float) -> bool:
    """Does the terrain keep ``cover`` over the Tunnel's ceiling from the
    wall to the portal (the headwall's crest included)? Checked per terrain
    cell over the strip: the cell's lowest vertex (a triangle's lowest
    point is a vertex) against the highest the ceiling reaches inside it."""
    ax, q = e.axis, e.cross
    end = grid.coord(ax, e.portal)
    lo_t, hi_t = min(e.wall, end), max(e.wall, end)

    def ceiling(t):
        return e.room_floor + (e.floor - e.room_floor) * (t - e.wall) / (end - e.wall) + e.height

    for k in range(grid.size(ax) - 1):
        lo = max(grid.coord(ax, k), lo_t)
        hi = min(grid.coord(ax, k + 1), hi_t)
        if hi <= lo:
            continue
        lowest = min(grid.z[grid.ij(ax, r, c)] for r in (k, k + 1) for c in (q, q + 1))
        if lowest < max(ceiling(lo), ceiling(hi)) + cover - 1e-6:
            return False
    return True


def _boxes_covered(dungeon: ZoneSpec, surface, cover: float, sample: float = 8.0) -> bool:
    """Is every room and corridor leg still ``cover`` under ``surface``?"""
    rooms = {r.id: r for r in dungeon.rooms}
    boxes = [(r.center_x - r.width / 2, r.center_y - r.depth / 2,
              r.center_x + r.width / 2, r.center_y + r.depth / 2, r.floor_z + r.height)
             for r in dungeon.rooms]
    for c in dungeon.corridors:
        top = max(c.from_z, c.to_z) + c.height
        boxes += [(*rect, top) for rect in
                  route_footprint(corridor_route(c, rooms), c.width / 2)]
    for x0, y0, x1, y1, top in boxes:
        nx = max(2, int(math.ceil((x1 - x0) / sample)) + 1)
        ny = max(2, int(math.ceil((y1 - y0) / sample)) + 1)
        gx, gy = np.meshgrid(np.linspace(x0, x1, nx), np.linspace(y0, y1, ny))
        if float(np.min(surface(gx, gy))) < top + cover - 1e-6:
            return False
    return True


def plan_entrance(host: ZoneSpec, ter: TerFile, dungeon: ZoneSpec, *,
                  rock_cover: float = ROCK_COVER,
                  room_id: Optional[str] = None) -> Entrance:
    """The Entrance with the least Apron digging, over every room wall facing
    the approach (only room ``room_id``'s when given), every strip that fits
    in its wall and every portal row.

    A candidate must keep ``rock_cover`` over the Tunnel all the way (the
    headwall included), ramp within ``MAX_GRADE``, stay clear of every other
    room and corridor in XY, dig no ground within a cell of the Rim, a
    zoneline or water, and not dig the Apron through the cover over the
    dungeon. The portal's floor is as high as the headwall's cover allows,
    lowered if need be so the Tunnel's ramp keeps to the grade."""
    land = landscape_for(host)
    landform = land.matrix.landform
    if landform is None:
        raise EntranceError(f"spec {host.name!r} has no Landform")
    side = landform.approach
    ax, out = _RUN[side]
    grid = _host_grid(host, ter)
    # Vertices within a cell of a frozen one: digging them would open the
    # Rim, move a zoneline or sink ground under the water plane.
    frozen = np.pad(np.isin(land.synth.node_type, _UNDIGGABLE), 1)
    keep = np.zeros(grid.z.shape, bool)
    for di in (0, 1, 2):
        for dj in (0, 1, 2):
            keep |= frozen[di:di + grid.nx, dj:dj + grid.ny]
    rooms = {r.id: r for r in dungeon.rooms}
    blockers = [(r.id, (r.center_x - r.width / 2, r.center_y - r.depth / 2,
                        r.center_x + r.width / 2, r.center_y + r.depth / 2))
                for r in dungeon.rooms]
    blockers += [(None, rect) for c in dungeon.corridors
                 for rect in route_footprint(corridor_route(c, rooms), c.width / 2)]
    # The Tunnel is one of the dungeon's corridors: its race's height.
    h = semantics.corridor_size(dungeon.dungeon_race)[1]
    candidates = []
    for room in dungeon.rooms:
        if h > room.height or room_id not in (None, room.id):
            continue
        wall = {"W": room.center_x - room.width / 2, "E": room.center_x + room.width / 2,
                "S": room.center_y - room.depth / 2, "N": room.center_y + room.depth / 2}[side]
        half = (room.depth if ax == 0 else room.width) / 2
        mid = room.center_y if ax == 0 else room.center_x
        for q in range(grid.size(1 - ax) - 1):
            c0, c1 = grid.coord(1 - ax, q), grid.coord(1 - ax, q + 1)
            if c0 < mid - half + DOOR_MARGIN or c1 > mid + half - DOOR_MARGIN:
                continue
            for m in range(grid.size(ax)):
                if not 0 <= m + 2 * out < grid.size(ax):
                    continue
                run = (grid.coord(ax, m) - wall) * out
                if run < MIN_TUNNEL:
                    continue
                top = min(grid.z[grid.ij(ax, m, q)], grid.z[grid.ij(ax, m, q + 1)])
                floor = min(float(top) - h - rock_cover, room.floor_z + MAX_GRADE * run)
                if floor < room.floor_z - MAX_GRADE * run:
                    continue
                e = Entrance(room.id, side, ax, out, q, m, wall, room.floor_z, floor, h)
                if not _tunnel_covered(grid, e, rock_cover):
                    continue
                strip = _strip_rect(ax, wall, grid.coord(ax, m), c0, c1)
                if any(rid != room.id and _overlaps(strip, r) for rid, r in blockers):
                    continue
                apron, surfaced = _apron(grid, e)
                if not surfaced:
                    continue
                dug = grid.z - apron
                if (dug[keep] > 1e-6).any():
                    continue
                cost = float(np.sum(dug))
                candidates.append((cost, len(candidates), e))
    for _cost, _n, e in sorted(candidates):
        dug = _grid_surface(_apron(grid, e)[0], grid.origin, grid.res)
        if _boxes_covered(dungeon, dug, rock_cover):
            return e
    raise EntranceError(f"no wall of {room_id or 'any room'} facing {side} "
                        "gives a Tunnel under the terrain")


def _face(ter: TerFile, pts, normal, material: int, uv_scale: float = 1.0 / 128.0) -> None:
    """Append one triangle to ``ter``, wound counter-clockwise seen from the
    side ``normal`` points to; UVs planar like the terrain's."""
    a, b, c = (np.asarray(p, dtype=np.float64) for p in pts)
    if np.dot(np.cross(b - a, c - a), normal) < 0:
        b, c = c, b
    base = len(ter.vertices)
    for x, y, z in (a, b, c):
        if abs(normal[2]) > 0.5:
            u, v = x * uv_scale, y * uv_scale
        else:
            u, v = (-x * normal[1] + y * normal[0]) * uv_scale, -z * uv_scale
        ter.vertices.append(Vertex(x=float(x), y=float(y), z=float(z), nx=normal[0],
                                   ny=normal[1], nz=normal[2], u=float(u), v=float(v)))
    ter.polygons.append(Polygon(base, base + 1, base + 2, material=material, flags=0))


def _material(ter: TerFile, name: str, host: ZoneSpec) -> int:
    """Index of material ``name`` in ``ter``, added (from the host spec's
    materials when it has one) if missing."""
    for m in ter.materials:
        if m.name == name:
            return m.index
    spec = host.materials.get(name)
    mat = Material(index=len(ter.materials), name=name,
                   shader=spec.shader if spec else "Opaque_MaxCB1.fx")
    mat.add_diffuse(spec.texture if spec else f"{name}.dds")
    ter.materials.append(mat)
    return mat.index


#: Triangles in the Mouth: floor 2, jambs 2 x 2, headwall 2.
MOUTH_FACES = 8


def mouth_faces(host_ter: TerFile) -> range:
    """Indices of the Mouth's triangles in the TER ``build_outdoor_ter``
    made from ``host_ter``: they follow the terrain's, less the two cut."""
    start = len(host_ter.polygons) - 2
    return range(start, start + MOUTH_FACES)


def build_outdoor_ter(host: ZoneSpec, ter: TerFile, dungeon: ZoneSpec,
                      entrance: Entrance, name: str, version: int = 1) -> TerFile:
    """One TER: the host terrain with the Apron dug and the Mouth cut, the
    Mouth's floor, jambs and headwall, and the dungeon mesh (rooms,
    corridors and the Tunnel). Terrain materials keep their indices; the
    dungeon's follow."""
    grid = _host_grid(host, ter)
    nx, ny = grid.nx, grid.ny
    z, _ = _apron(grid, entrance)
    ax, out, m, q = entrance.axis, entrance.outward, entrance.portal, entrance.cross

    merged = TerFile(name=name, magic=MAGIC_TERRAIN, version=version)
    merged.materials = [Material(index=k, name=mt.name, shader=mt.shader,
                                 properties=list(mt.properties))
                        for k, mt in enumerate(ter.materials)]
    gx, gy = np.gradient(z, grid.res)
    nlen = np.sqrt(gx ** 2 + gy ** 2 + 1.0)
    for idx, v in enumerate(ter.vertices):
        if idx < nx * ny:
            i, j = divmod(idx, ny)
            v = Vertex(x=v.x, y=v.y, z=float(z[i, j]), nx=float(-gx[i, j] / nlen[i, j]),
                       ny=float(-gy[i, j] / nlen[i, j]), nz=float(1.0 / nlen[i, j]),
                       u=v.u, v=v.v)
        else:
            v = Vertex(x=v.x, y=v.y, z=v.z, nx=v.nx, ny=v.ny, nz=v.nz, u=v.u, v=v.v)
        merged.vertices.append(v)
    # The notch cell: quad (qi, qj) is polygons 2 * (qi * (ny - 1) + qj) and
    # the next.
    qi, qj = grid.ij(ax, min(m, m + out), q)
    cut = 2 * (qi * (ny - 1) + qj)
    merged.polygons = [Polygon(p.v1, p.v2, p.v3, p.material, p.flags)
                       for k, p in enumerate(ter.polygons) if k not in (cut, cut + 1)]

    # The Mouth: floor, two jambs, headwall. Corners are the terrain's own
    # vertex positions, so every edge meets a terrain or Tunnel edge exactly.
    fl, ceil = entrance.floor, entrance.floor + entrance.height
    top = {c: float(z[grid.ij(ax, m, c)]) for c in (q, q + 1)}
    up = (0.0, 0.0, 1.0)
    outward = tuple(float(out) if a == ax else 0.0 for a in range(2)) + (0.0,)
    across = tuple(1.0 if a == 1 - ax else 0.0 for a in range(2)) + (0.0,)
    floor_mat = _material(merged, MOUTH_FLOOR_MATERIAL, host)
    wall_mat = _material(merged, MOUTH_WALL_MATERIAL, host)
    P = grid.point
    _face(merged, (P(ax, m, q, fl), P(ax, m, q + 1, fl), P(ax, m + out, q + 1, fl)), up, floor_mat)
    _face(merged, (P(ax, m, q, fl), P(ax, m + out, q + 1, fl), P(ax, m + out, q, fl)), up, floor_mat)
    for c, sign in ((q, 1.0), (q + 1, -1.0)):
        n = tuple(sign * a for a in across)
        base, lintel = P(ax, m, c, fl), P(ax, m, c, ceil)
        crest, foot = P(ax, m, c, top[c]), P(ax, m + out, c, fl)
        _face(merged, (base, lintel, foot), n, wall_mat)
        _face(merged, (lintel, crest, foot), n, wall_mat)
    _face(merged, (P(ax, m, q, ceil), P(ax, m, q + 1, ceil), P(ax, m, q + 1, top[q + 1])),
          outward, wall_mat)
    _face(merged, (P(ax, m, q, ceil), P(ax, m, q + 1, top[q + 1]), P(ax, m, q, top[q])),
          outward, wall_mat)

    # The dungeon, with the Tunnel and its doorway.
    mesh = _dungeon_mesh(dungeon, entrance, grid)
    offset = len(merged.vertices)
    remap = {}
    for mt in mesh.materials:
        k = _material(merged, mt.name, host)
        merged.materials[k] = Material(index=k, name=mt.name, shader=mt.shader,
                                       properties=list(mt.properties))
        remap[mt.index] = k
    merged.vertices.extend(mesh.vertices)
    merged.polygons.extend(Polygon(p.v1 + offset, p.v2 + offset, p.v3 + offset,
                                   remap[p.material], p.flags) for p in mesh.polygons)
    return merged


def _dungeon_mesh(dungeon: ZoneSpec, e: Entrance, grid: _Grid) -> MeshBuilder:
    """The box-backend mesh of ``dungeon`` plus the Tunnel: a ramp from the
    room's floor at its wall to ``e.floor`` at the portal, through a doorway
    cut in that wall."""
    _ensure_materials(dungeon)
    mb = MeshBuilder()
    c0, c1 = grid.coord(1 - e.axis, e.cross), grid.coord(1 - e.axis, e.cross + 1)
    for room in dungeon.rooms:
        extra = None
        if room.id == e.room_id:
            if e.side not in room.open_walls:
                room.open_walls.append(e.side)
            extra = {e.side: [(c0, c1, e.room_floor + e.height)]}
        mb.add_room(room, dungeon, extra_doors=extra)
    for cor in dungeon.corridors:
        mb.add_corridor(cor, dungeon)
    room = next(r for r in dungeon.rooms if r.id == e.room_id)
    floor_mat = mb.material_id(dungeon.materials[room.floor_material])
    wall_mat = mb.material_id(dungeon.materials[room.wall_material])
    ceil_mat = mb.material_id(dungeon.materials[room.ceiling_material])
    portal, mid = grid.coord(e.axis, e.portal), (c0 + c1) / 2.0
    (fx, fy), (tx, ty) = ((e.wall, mid), (portal, mid)) if e.axis == 0 else \
        ((mid, e.wall), (mid, portal))
    mb._add_straight_leg(fx, fy, e.room_floor, tx, ty, e.floor, e.axis == 0,
                         (c1 - c0) / 2.0, e.height, 0, floor_mat, wall_mat, ceil_mat)
    return mb


# ---------------------------------------------------------------------------
# The build: spec, backend and gate (task 6)
# ---------------------------------------------------------------------------

#: The wilderness-payload key that makes a spec an outdoor dungeon.
DUNGEON_KEY = "dungeon"
#: Planning failures a fresh seed can cure: the pipeline retries on them.
PLAN_ERRORS = (EnvelopeFitError, EntranceError)


def is_outdoor_dungeon(spec: ZoneSpec) -> bool:
    """Does ``spec`` describe an outdoor dungeon (a host terrain with a
    dungeon under it)?"""
    return bool(spec.wilderness) and DUNGEON_KEY in spec.wilderness


def outdoor_dungeon_spec(name: str, seed: int, edges=None, biome: str = DEFAULT_BIOME,
                         room_count: int = DEFAULT_ROOMS, engine=None,
                         **layout_kwargs) -> ZoneSpec:
    """One spec for an outdoor dungeon: the host wilderness spec (Host_Hill
    terrain at the outdoor-dungeon size) with the dungeon laid out inside its
    Envelope and an Entrance planned to it. ``engine`` is the dungeon's
    Layout_Engine (``None`` is classic); its record rides on ``spec.layout``.

    Raises one of ``PLAN_ERRORS`` when the seed's hill can't hold the minimum
    rooms or no wall gives an Entrance (the pipeline retries on a fresh
    seed)."""
    spec = wilderness_spec(name, seed, edges, biome, landform=DEFAULT_HOST_HILL,
                           zone_size=OUTDOOR_DUNGEON_ZONE_SIZE)
    spec.zone_type = "outdoor_dungeon"
    ter = build_wilderness_ter(spec, f"ter_{name}", 1)
    envelope = host_envelope(spec, ter)
    layout, warnings, entrance = plan_dungeon(spec, ter, envelope, name, seed, room_count,
                                              engine=engine, **layout_kwargs)
    # The Apron lowers the ground in front of the Mouth; when it reaches the
    # Outdoor_Spawn, the safe point drops with it onto the dug ground.
    grid = _host_grid(spec, ter)
    dug, _ = _apron(grid, entrance)
    sx, sy, sz = spec.safe_point
    before = float(_grid_surface(grid.z, grid.origin, grid.res)(sx, sy))
    after = float(_grid_surface(dug, grid.origin, grid.res)(sx, sy))
    if after < before:
        spec.safe_point = (sx, sy, sz + after - before)
    spec.layout = layout.layout
    spec.rooms = layout.rooms
    spec.corridors = layout.corridors
    spec.lights = layout.lights
    spec.gates = layout.gates
    for mat_name, mat in layout.materials.items():
        spec.materials.setdefault(mat_name, mat)
    # The Mouth's materials, from the biome kit, whether or not the host
    # terrain uses them (so their textures are packed).
    kit_mats = load_biome_kit(biome).materials()
    for mat_name in (MOUTH_FLOOR_MATERIAL, MOUTH_WALL_MATERIAL):
        if mat_name not in spec.materials:
            m = kit_mats[mat_name]
            spec.materials[mat_name] = MaterialSpec(
                name=mat_name, texture=f"{mat_name}.dds", color=m.color,
                description=m.description)
    spec.dungeon_theme = layout.dungeon_theme
    spec.dungeon_race = layout.dungeon_race
    spec.elemental_tint = layout.elemental_tint
    spec.wilderness[DUNGEON_KEY] = {
        "entrance": entrance.to_dict(),
        "rock_cover": envelope.rock_cover,
        "floor_limit": envelope.floor_limit,
        "rooms_requested": room_count,
        "warnings": list(warnings),
    }
    return spec


def build_outdoor_dungeon_ter(spec: ZoneSpec, ter_name: str, ter_version: int) -> TerFile:
    """The one TER an outdoor-dungeon spec ships: its host terrain with the
    Apron and Mouth, and its rooms, corridors and Tunnel."""
    host = build_wilderness_ter(spec, ter_name, ter_version)
    entrance = Entrance.from_dict(spec.wilderness[DUNGEON_KEY]["entrance"])
    return build_outdoor_ter(spec, host, spec, entrance, ter_name, ter_version)


def outdoor_dungeon_report(eqg_path, spec: ZoneSpec, agent=None):
    """The gate on a built outdoor dungeon, as one ``TraversalReport``: the
    wilderness bowl check on the open ground (its "bowl" room), then every
    dungeon room reached from the outdoor Spawn (the spec's safe point) and
    every corridor continuous, on the same merged TER."""
    from analyzer.traverse import AgentModel, load_ter_from_eqg, validate
    from generators.wilderness.build import bowl_report

    agent = agent or AgentModel()
    ter, _ = load_ter_from_eqg(eqg_path)
    bowl = bowl_report(spec, ter, agent)
    report = validate(eqg_path, spec=spec, agent=agent, check_corridors=True)
    report.rooms = list(bowl.rooms) + list(report.rooms)
    report.total_rooms += bowl.total_rooms
    report.reachable_rooms += bowl.reachable_rooms
    report.notes = list(bowl.notes) + list(report.notes)
    return report


def sidecar_block(spec: ZoneSpec) -> Dict:
    """The ``outdoor_dungeon`` block of the ``.zone.json`` sidecar (Req 6.3):
    the Envelope's bounds and Rock_Cover, each Entrance (Apron centre, Mouth,
    Tunnel id) and the Outdoor_Spawn. Advisory only."""
    data = spec.wilderness[DUNGEON_KEY]
    land = landscape_for(spec)
    e = Entrance.from_dict(data["entrance"])
    ox, oy = land.synth.origin
    res = float(land.synth.resolution)

    def coord(axis, k):
        return (ox, oy)[axis] + (k + 0.5) * res

    def point(run, cross, z):
        return [run, cross, z] if e.axis == 0 else [cross, run, z]

    foot = host_footprint(land.matrix.landform)
    xs, ys = [p[0] for p in foot], [p[1] for p in foot]
    c0, c1 = coord(1 - e.axis, e.cross), coord(1 - e.axis, e.cross + 1)
    mid = (c0 + c1) / 2.0
    return {
        "envelope": {"min_xy": [min(xs), min(ys)], "max_xy": [max(xs), max(ys)],
                     "floor_limit": data["floor_limit"]},
        "rock_cover": data["rock_cover"],
        "entrances": [{
            "tunnel_id": "tunnel_0",
            "room": e.room_id,
            "side": e.side,
            "apron_centre": point(coord(e.axis, e.portal + e.outward), mid, e.floor),
            "mouth": {"centre": point(coord(e.axis, e.portal), mid, e.floor + e.height / 2),
                      "width": c1 - c0, "height": e.height, "floor": e.floor},
        }],
        "outdoor_spawn": list(spec.safe_point),
        "rooms_requested": data["rooms_requested"],
        "rooms": len(spec.rooms),
    }
