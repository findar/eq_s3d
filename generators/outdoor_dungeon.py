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

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from core.ter import MAGIC_TERRAIN, Material, Polygon, TerFile, Vertex
from generators.envelope import Envelope
from generators.geometry import MeshBuilder, _ensure_materials
from generators.layout import LayoutGenerator
from generators.routing import corridor_route, route_footprint
from generators.wilderness.build import landscape_for
from generators.wilderness.matrix import Landform
from generators.zone_spec import ZoneSpec

#: Minimum terrain left above any ceiling (design finding 4: stock p10 rock
#: is 12-22 u).
ROCK_COVER: float = 24.0
#: How far below the Entrance's floor the dungeon may reach (finding 4:
#: covered floor sits at most ~130 u below the open ground near it).
FLOOR_DEPTH: float = 150.0
#: Rooms laid out under the default Host_Hill.
DEFAULT_ROOMS: int = 5
#: Mean room side as a share of the Envelope's inradius, before dividing by
#: sqrt(room count): the rooms' combined floor is about this share squared
#: of the inradius square, leaving room for separation and corridors.
ROOM_FILL: float = 0.6
#: Room height (the layout's ceiling) under a hill. The dungeon profile's
#: 121 u leaves too thin a band under the flank; 80 u is still ~13 player
#: heights, and 5 rooms then fit every seed sampled (0.8 fill or 121 u
#: rooms drop rooms on a few).
ROOM_HEIGHT: float = 80.0
#: Tunnel height: the layout's corridor height for ROOM_HEIGHT rooms.
TUNNEL_HEIGHT: float = 0.8 * ROOM_HEIGHT
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
    limit is ``FLOOR_DEPTH`` below it."""
    land = landscape_for(spec)
    landform = land.matrix.landform
    if landform is None:
        raise ValueError(f"spec {spec.name!r} has no Landform to build an Envelope under")
    surface = ter_surface(ter, land.synth.origin, land.synth.resolution,
                          land.bowl.heights.shape)
    if entrance_floor is None:
        fx, fy = approach_foot(landform)
        entrance_floor = float(surface(fx, fy))
    return Envelope(host_footprint(landform), entrance_floor - FLOOR_DEPTH,
                    surface, rock_cover)


def layout_in_envelope(name: str, seed: Optional[int], envelope: Envelope,
                       room_count: int = DEFAULT_ROOMS,
                       **kwargs) -> Tuple[ZoneSpec, List[str]]:
    """A box-dungeon layout inside ``envelope``, rooms sized to it.

    The mean room side is ``ROOM_FILL * inradius / sqrt(room_count)``, set
    through the generator's size multiplier. Returns the layout and the
    generator's warnings (``rooms_reduced`` when rooms were dropped)."""
    gen = LayoutGenerator("dungeon", seed=seed)
    gen.ceiling = ROOM_HEIGHT
    gen._apply_room_scale(room_count)
    base = (gen.room_min + gen.room_max) / 2.0
    gen.size_multiplier = ROOM_FILL * envelope.inradius / math.sqrt(room_count) / base
    spec = gen.generate(name, room_count=room_count, envelope=envelope, **kwargs)
    return spec, list(gen.warnings)


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
        return {"room": self.room_id, "side": self.side, "floor": self.floor,
                "room_floor": self.room_floor, "height": self.height}


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
                  rock_cover: float = ROCK_COVER) -> Entrance:
    """The Entrance with the least Apron digging, over every room wall facing
    the approach, every strip that fits in its wall and every portal row.

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
    h = TUNNEL_HEIGHT
    candidates = []
    for room in dungeon.rooms:
        if h > room.height:
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
    raise EntranceError(f"no room wall facing {side} gives a Tunnel under the terrain")


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
