"""A room's real walls in plan (roadmap step 8, design "Outlines").

A room keeps its Box (``RoomSpec.bounds``) as its allotment: placement, stacking,
corridors and the Envelope all use it. An ``Outline`` is what the room actually
is inside that Box: a connected set of convex Cells on shared vertices, so a
floor, a ceiling and a wall weld exactly. A wall is any Cell edge with a chosen
Cell on one side only.

Doors reach the room through Throats, straight strips of floor as wide as the
corridor, and every Throat ends in the Core, the part round the Box's centre that
is always floor (the spawn and labels stand there).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

import numpy as np
from scipy.spatial import Voronoi, cKDTree

from .field.noise import _value_noise_3d

Rect = Tuple[float, float, float, float]    # x0, y0, x1, y1


@dataclass
class Outline:
    verts: List[Tuple[float, float]]        # plan vertices, shared between Cells
    cells: List[List[int]]                  # convex Cells, counter-clockwise from above
    core: Rect                              # always floor; holds the Box's centre
    throats: List[Rect] = field(default_factory=list)   # one per door, Tunnel or slot
    # Relief, per vertex, in u: how far the floor rises and the ceiling falls. Empty
    # is flat, so a flat room's JSON is as short as it can be.
    lift: List[float] = field(default_factory=list)
    drop: List[float] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Outline":
        return cls(verts=[tuple(v) for v in d["verts"]],
                   cells=[list(c) for c in d["cells"]],
                   core=tuple(d["core"]),
                   throats=[tuple(t) for t in d.get("throats", [])],
                   lift=list(d.get("lift", [])), drop=list(d.get("drop", [])))

    def contains(self, pts: np.ndarray, tol: float = 1e-6) -> np.ndarray:
        """Which of the plan points ``pts`` (N, 2) lie on the room's floor. Each
        Cell is tested as the fan the mesh builds, since a wandering wall can bend
        a Cell a little off convex."""
        pts = np.asarray(pts, dtype=np.float64)
        verts = np.asarray(self.verts, dtype=np.float64)
        a, b, c = [], [], []
        for cell in self.cells:
            poly = verts[cell]
            a.append(poly)
            b.append(np.roll(poly, -1, axis=0))
            c.append(np.broadcast_to(poly.mean(axis=0), poly.shape))
        a, b, c = np.vstack(a), np.vstack(b), np.vstack(c)

        def left_of(p, q):
            return ((q[:, 0] - p[:, 0]) * (pts[:, 1, None] - p[:, 1])
                    - (q[:, 1] - p[:, 1]) * (pts[:, 0, None] - p[:, 0])) >= -tol

        return (left_of(a, b) & left_of(b, c) & left_of(c, a)).any(axis=1)

    def lift_at(self, i: int) -> float:
        return self.lift[i] if self.lift else 0.0

    def drop_at(self, i: int) -> float:
        return self.drop[i] if self.drop else 0.0

    def fill(self, box: Rect) -> float:
        """The room's floor over its Box."""
        area = sum(_area([self.verts[i] for i in c]) for c in self.cells)
        return area / ((box[2] - box[0]) * (box[3] - box[1]))

    def wall_loops(self) -> List[List[int]]:
        """The walls as closed vertex loops, the floor on the left of each edge. A
        directed edge with its opposite in another Cell is inside the floor; what's
        left always closes. Cells touching at a corner join whichever edge comes first."""
        nexts: Dict[int, List[int]] = {}
        for a, b in _wall_edges(self.cells):
            nexts.setdefault(a, []).append(b)
        loops = []
        for start in sorted(nexts):
            while nexts[start]:
                loop = [start]
                while True:
                    b = nexts[loop[-1]].pop()
                    if b == start:
                        break
                    loop.append(b)
                loops.append(loop)
        return loops


# ---------------------------------------------------------------------------
# Drawing an Outline
# ---------------------------------------------------------------------------

EDGE_MAX = 14.0     # the era's edge: longer Cell edges split (design finding 1)
PLACES = 3          # vertices keep this many decimals
SNAP = 0.01         # points closer than this are one vertex
FILL_FLOOR = 0.65   # a room's floor never goes under this share of its Box
SHAPES = ("blob", "long", "cut", "ell", "cross")
COMPLEXES = ("voronoi", "grid", "facet")
JITTER = {"voronoi": 0.25, "grid": 0.0, "facet": 0.0}   # how far growth strays from its shape
#: A facet room's corner cuts, as shares of the Box's sides: (low, high) for the
#: cut at each corner, then one corner's own (an ell's big bite).
FACET_CUTS = {"blob": ((0.20, 0.32), None), "cut": ((0.18, 0.28), None),
              "long": ((0.28, 0.40), None), "cross": ((0.32, 0.42), None),
              "ell": ((0.12, 0.22), (0.42, 0.55))}

Door = Tuple[str, float, float]             # side (N/S/E/W), c0, c1 along that wall


def _wall_edges(cells: List[List[int]]) -> List[Tuple[int, int]]:
    """The directed edges with no opposite: each opposite pair is inside the floor."""
    left: Dict[Tuple[int, int], int] = {}
    for c in cells:
        for a, b in zip(c, c[1:] + c[:1]):
            if left.get((b, a), 0) > 0:
                left[(b, a)] -= 1
            else:
                left[(a, b)] = left.get((a, b), 0) + 1
    return [e for e, n in left.items() for _ in range(n)]


def _no_spikes(cell: List[int]) -> List[int]:
    """A cell with its out-and-back runs (a, b, a) taken out: they enclose nothing."""
    out = list(cell)
    changed = True
    while changed and len(out) >= 3:
        changed = False
        for k in range(len(out)):
            if out[k - 1] == out[(k + 1) % len(out)] or out[k] == out[k - 1]:
                del out[k]
                changed = True
                break
    return out


def _area(poly) -> float:
    x, y = zip(*poly)
    return 0.5 * abs(sum(x[i] * y[(i + 1) % len(x)] - x[(i + 1) % len(x)] * y[i]
                         for i in range(len(x))))


def _split(poly, axis: int, at: float):
    """A convex polygon cut by the line ``coord[axis] == at``: (below, above)."""
    lo, hi = [], []
    for k, p in enumerate(poly):
        q = poly[(k + 1) % len(poly)]
        if p[axis] <= at:
            lo.append(p)
        if p[axis] >= at:
            hi.append(p)
        if (p[axis] - at) * (q[axis] - at) < 0:
            t = (at - p[axis]) / (q[axis] - p[axis])
            cut = (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
            lo.append(cut)
            hi.append(cut)
    return lo, hi


def _clip(poly, r: Rect):
    """``poly`` inside the rect ``r``, and the convex pieces of it outside."""
    outside = []
    for axis, lo_at, hi_at in ((0, r[0], r[2]), (1, r[1], r[3])):
        below, poly = _split(poly, axis, lo_at)
        if len(below) >= 3:
            outside.append(below)
        if len(poly) < 3:
            return [], outside
        poly, above = _split(poly, axis, hi_at)
        if len(above) >= 3:
            outside.append(above)
        if len(poly) < 3:
            return [], outside
    return poly, outside


def _voronoi_cells(box: Rect, spacing: float, relax: int, rng: random.Random):
    """Voronoi Cells over the Box, from a jittered grid of seeds. The seeds are
    mirrored over each side, so every Cell is finite and the sides are real edges."""
    x0, y0, x1, y1 = box
    nx = max(2, round((x1 - x0) / spacing))
    ny = max(2, round((y1 - y0) / spacing))
    dx, dy = (x1 - x0) / nx, (y1 - y0) / ny
    seeds = np.array([(x0 + (i + 0.5 + 0.8 * (rng.random() - 0.5)) * dx,
                       y0 + (j + 0.5 + 0.8 * (rng.random() - 0.5)) * dy)
                      for i in range(nx) for j in range(ny)])
    cells = []
    for _ in range(relax + 1):
        pts = np.vstack([seeds,
                         np.c_[2 * x0 - seeds[:, 0], seeds[:, 1]],
                         np.c_[2 * x1 - seeds[:, 0], seeds[:, 1]],
                         np.c_[seeds[:, 0], 2 * y0 - seeds[:, 1]],
                         np.c_[seeds[:, 0], 2 * y1 - seeds[:, 1]]])
        vor = Voronoi(pts)
        cells = []
        for k in range(len(seeds)):
            region = vor.regions[vor.point_region[k]]
            poly = vor.vertices[region]
            ang = np.arctan2(poly[:, 1] - seeds[k, 1], poly[:, 0] - seeds[k, 0])
            inside, _out = _clip([tuple(p) for p in poly[np.argsort(ang)]], box)
            cells.append(inside)
        seeds = np.array([np.mean(c, axis=0) if len(c) else s for c, s in zip(cells, seeds)])
    return [c for c in cells if len(c) >= 3]


def _grid_cells(box: Rect, module: float):
    """A grid of Cells over the Box; each corner Cell is two triangles, so its
    outer half can go and leave a corner cut at 45 degrees."""
    x0, y0, x1, y1 = box
    nx, ny = max(2, round((x1 - x0) / module)), max(2, round((y1 - y0) / module))
    xs = [x0 + (x1 - x0) * i / nx for i in range(nx + 1)]
    ys = [y0 + (y1 - y0) * j / ny for j in range(ny + 1)]
    cells = []
    for i in range(nx):
        for j in range(ny):
            a, b, c, d = (xs[i], ys[j]), (xs[i + 1], ys[j]), (xs[i + 1], ys[j + 1]), (xs[i], ys[j + 1])
            corner = (i in (0, nx - 1)) and (j in (0, ny - 1))
            if not corner:
                cells.append([a, b, c, d])
            elif (i == 0) == (j == 0):      # SW and NE: cut along b-d
                cells += [[a, b, d], [b, c, d]]
            else:                           # SE and NW: cut along a-c
                cells += [[a, b, c], [a, c, d]]
    return cells


def _cut_corner(poly, corner, dx: float, dy: float):
    """``poly`` less the corner ``corner``: the kept side, and the piece cut off,
    along the line from ``dx`` along X to ``dy`` along Y from it."""
    ax, ay, bx, by = corner[0] + dx, corner[1], corner[0], corner[1] + dy
    side = lambda p: (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax)  # noqa: E731
    sign = side(corner)
    keep, off = [], []
    for k, p in enumerate(poly):
        q = poly[(k + 1) % len(poly)]
        sp, sq = side(p) * sign, side(q) * sign
        (off if sp > 0 else keep).append(p)
        if sp * sq < 0:
            t = sp / (sp - sq)
            cut = (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
            keep.append(cut)
            off.append(cut)
    return keep, off


def _facet_cells(box: Rect, shape: str, rng: random.Random):
    """A room of a few long facets: the Box with its corners cut at uneven angles.
    Returns the kept polygon and the corner pieces, which only a Throat keeps."""
    x0, y0, x1, y1 = box
    w, d = x1 - x0, y1 - y0
    usual, own = FACET_CUTS.get(shape, FACET_CUTS["blob"])
    corners = [(x0, y0, 1, 1), (x1, y0, -1, 1), (x1, y1, -1, -1), (x0, y1, 1, -1)]
    big = rng.randrange(4)
    middle = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    pieces = []
    for k, (cx, cy, sx, sy) in enumerate(corners):
        lo, hi = own if own is not None and k == big else usual
        dx, dy = sx * w * rng.uniform(lo, hi), sy * d * rng.uniform(lo, hi)
        middle, off = _cut_corner(middle, (cx, cy), dx, dy)
        pieces.append(off)
    return middle, pieces


def _core_rect(box: Rect, door_width: float) -> Rect:
    """Round the Box's centre: a fifth of the Box each way, and wide enough to take
    any door's strip across it."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hx = min(max(0.2 * (x1 - x0), door_width / 2 + 1.0), (x1 - x0) / 2)
    hy = min(max(0.2 * (y1 - y0), door_width / 2 + 1.0), (y1 - y0) / 2)
    return (cx - hx, cy - hy, cx + hx, cy + hy)


def _overlap(a: Rect, b: Rect, axis: int) -> float:
    return min(a[axis + 2], b[axis + 2]) - max(a[axis], b[axis])


def _link(r: Rect, core: Rect, width: float) -> List[Rect]:
    """The rects joining ``r`` to the Core, none if they already touch: straight
    across when they share a range on one axis, otherwise an L."""
    ox, oy = _overlap(r, core, 0), _overlap(r, core, 1)
    if ox > 1e-6 and oy >= -1e-6 or oy > 1e-6 and ox >= -1e-6:
        return []
    if ox > 1e-6:
        return [(max(r[0], core[0]), min(r[3], core[3]), min(r[2], core[2]), max(r[1], core[1]))]
    if oy > 1e-6:
        return [(min(r[2], core[2]), max(r[1], core[1]), max(r[0], core[0]), min(r[3], core[3]))]
    # An L: along Y from ``r`` to the Core's middle, then along X into the Core.
    mx, my = (r[0] + r[2]) / 2, (core[1] + core[3]) / 2
    w = min(width, r[2] - r[0], core[3] - core[1]) / 2
    leg = (mx - w, min(r[3], my - w), mx + w, max(r[1], my + w))
    if r[3] < my - w:           # ``r`` is below the band
        leg = (mx - w, r[3], mx + w, my + w)
    elif r[1] > my + w:
        leg = (mx - w, my - w, mx + w, r[1])
    run = (mx + w, my - w, core[0], my + w) if mx < core[0] else (core[2], my - w, mx - w, my + w)
    return [leg, run]


def _door_throats(box: Rect, door: Door, core: Rect) -> List[Rect]:
    """A door's strip from its wall to the Core's middle band, and any run across
    to the Core from there."""
    x0, y0, x1, y1 = box
    side, c0, c1 = door
    w = c1 - c0
    if side in ("N", "S"):
        m = (core[1] + core[3]) / 2
        stem = (c0, m - w / 2, c1, y1) if side == "N" else (c0, y0, c1, m + w / 2)
    else:
        m = (core[0] + core[2]) / 2
        stem = (m - w / 2, c0, x1, c1) if side == "E" else (x0, c0, m + w / 2, c1)
    return [stem] + _link(stem, core, w)


def _weld(polys) -> Tuple[list, list]:
    """Polygons to shared vertices: ids per polygon, no T-junctions."""
    # Points this close are one point. Rounding alone isn't enough: the same corner
    # worked out from two Cells can round to either side of a thousandth, and the two
    # copies leave a sliver whose edges read as walls.
    raw = np.array([p for poly in polys for p in poly], dtype=np.float64)
    parent = list(range(len(raw)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in sorted(cKDTree(raw).query_pairs(SNAP)):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    ids: Dict[Tuple[float, float], int] = {}
    by_id: List[Tuple[float, float]] = []
    cells = []
    k = 0
    for poly in polys:
        cell = []
        for _ in poly:
            x, y = raw[find(k)]
            k += 1
            key = (round(float(x), PLACES), round(float(y), PLACES))
            i = ids.setdefault(key, len(ids))
            if i == len(by_id):
                by_id.append(key)
            if not cell or cell[-1] != i:
                cell.append(i)
        if len(cell) > 1 and cell[0] == cell[-1]:
            cell.pop()
        # A cut through a corner can leave a piece with no area; its edges lie on
        # its neighbours' and would read as walls.
        cell = _no_spikes(cell)
        if len(cell) >= 3 and _area([by_id[v] for v in cell]) >= 1e-2:
            cells.append(cell)
    verts = list(ids)
    pts = np.array(verts)

    def on_edge(a: int, b: int) -> List[int]:
        p, q = pts[a], pts[b]
        d = q - p
        length = float(np.hypot(*d))
        if length < 1e-9:
            return []
        t = (pts - p) @ d / length ** 2
        off = np.abs((pts[:, 0] - p[0]) * d[1] - (pts[:, 1] - p[1]) * d[0]) / length
        hit = np.nonzero((off < SNAP) & (t > 1e-9) & (t < 1 - 1e-9))[0]
        return [int(i) for i in hit[np.argsort(t[hit])]]

    return verts, [[i for k, a in enumerate(c)
                    for i in [a] + on_edge(a, c[(k + 1) % len(c)])] for c in cells]


def _split_long_edges(verts: list, cells: list) -> Tuple[list, list]:
    """Every wall edge over ``EDGE_MAX`` cut evenly. Only walls: edges inside the floor
    stay whole, since every floor triangle is work for the walk gate."""
    verts = list(verts)
    ids = {v: i for i, v in enumerate(verts)}
    walls = set(_wall_edges(cells))

    def mids(a: int, b: int) -> List[int]:
        if (a, b) not in walls:
            return []
        lo, hi = (a, b) if a < b else (b, a)
        p, q = np.array(verts[lo]), np.array(verts[hi])
        n = int(math.ceil(float(np.hypot(*(q - p))) / EDGE_MAX))
        out = []
        for k in range(1, n):
            key = tuple(round(float(c), PLACES) for c in p + (q - p) * k / n)
            if key not in ids:
                ids[key] = len(verts)
                verts.append(key)
            out.append(ids[key])
        return out if a == lo else out[::-1]

    return verts, [[i for k, a in enumerate(c) for i in [a] + mids(a, c[(k + 1) % len(c)])]
                   for c in cells]


def _Pt(c) -> Tuple[float, float]:
    return float(c[0]), float(c[1])


def _in_convex(poly, p) -> bool:
    """Is ``p`` inside the counter-clockwise convex polygon ``poly``?"""
    return all((q[0] - a[0]) * (p[1] - a[1]) - (q[1] - a[1]) * (p[0] - a[0]) >= -1e-6
               for a, q in zip(poly, poly[1:] + poly[:1]))


def _close_holes(verts: list, cells: list) -> list:
    """Only the outer wall stays. A dropped sliver can leave a pinhole in the floor:
    a loop with next to no area collapses to one vertex, and anything bigger becomes
    a Cell of its own."""
    loops = Outline(verts=verts, cells=cells, core=(0, 0, 0, 0)).wall_loops()
    if len(loops) < 2:
        return cells
    outer = max(loops, key=lambda loop: _area([verts[i] for i in loop]))
    merge: Dict[int, int] = {}
    extra = []
    for loop in loops:
        if loop is outer:
            continue
        if _area([verts[i] for i in loop]) < 0.5:
            merge.update({i: loop[0] for i in loop})
        else:
            extra.append(loop[::-1])
    out = []
    for c in cells + extra:
        cell = []
        for i in c:
            i = merge.get(i, i)
            if not cell or cell[-1] != i:
                cell.append(i)
        if len(cell) > 1 and cell[0] == cell[-1]:
            cell.pop()
        if len(cell) >= 3:
            out.append(cell)
    return out


def _fans_sound(verts: list, cell: List[int]) -> bool:
    """Does every triangle of the Cell's fan, from the mean of its vertices, keep
    its winding? The mesh fans from there, so this is what must hold."""
    pts = [verts[i] for i in cell]
    cx, cy = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
    return all((a[0] - cx) * (b[1] - cy) - (a[1] - cy) * (b[0] - cx) > 1e-3
               for a, b in zip(pts, pts[1:] + pts[:1]))


def _wander(verts: list, cells: list, keep_still: List[Rect], wobble: float,
            rng: random.Random) -> list:
    """Move each wall vertex off every Throat and the Core toward the Cells it
    belongs to, by up to ``wobble``, never past 45% of the way to their middle and
    never so far that a Cell's fan folds over."""
    if wobble <= 0:
        return verts
    owners: Dict[int, List[List[int]]] = {}
    for c in cells:
        for a in c:
            owners.setdefault(a, []).append(c)
    wall = sorted({i for edge in _wall_edges(cells) for i in edge})
    moved = list(verts)
    tol = 1e-3
    for i in wall:
        x, y = verts[i]
        if any(r[0] - tol <= x <= r[2] + tol and r[1] - tol <= y <= r[3] + tol for r in keep_still):
            continue
        mids = [np.mean([moved[k] for k in c], axis=0) for c in owners[i]]
        to = np.mean(mids, axis=0) - np.array((x, y))
        dist = float(np.hypot(*to))
        step = min(wobble * rng.random(), 0.45 * dist)
        if dist <= 1e-6:
            continue
        for scale in (1.0, 0.5, 0.25):
            moved[i] = (round(x + to[0] / dist * step * scale, PLACES),
                        round(y + to[1] / dist * step * scale, PLACES))
            if all(_fans_sound(moved, c) for c in owners[i]):
                break
        else:
            moved[i] = (x, y)
    return moved


def _score(shape: str, u: float, v: float, wide: bool, su: int, sv: int) -> float:
    """How late a Cell at (u, v) joins: 0 at the Box's centre, about 1 at a side."""
    au, av = abs(u), abs(v)
    if shape == "cut":
        return au + av
    if shape == "cross":
        return min(au, av)
    if shape == "long":
        return av + 0.2 * au if wide else au + 0.2 * av
    if shape == "ell":
        arm_u = av if su * u >= 0 else math.hypot(u, v)
        arm_v = au if sv * v >= 0 else math.hypot(u, v)
        return min(arm_u, arm_v)
    return math.hypot(u, v)


def draw_outline(box: Rect, doors: List[Door], slots: List[Rect], *, complex: str,
                 cell_size: float, fill: float, shape: str, rng: random.Random,
                 relax: int = 0, wobble: float = 0.0) -> Outline:
    """A room's Outline inside ``box``: Core and Throats first, then neighbouring
    Cells in the order ``shape`` asks for until the floor reaches ``fill`` of the
    Box, then any hole filled. Doors may need more floor than ``fill``. A ``facet``
    room is its middle polygon instead, however much floor that is. Then each wall
    vertex off a Throat moves inward by up to ``wobble``, so no wall keeps to the
    Box's straight side."""
    x0, y0, x1, y1 = box
    door_width = max([c1 - c0 for _s, c0, c1 in doors], default=0.0)
    core = _core_rect(box, door_width)
    throats: List[Rect] = []
    for door in doors:
        throats += _door_throats(box, door, core)
    for s in slots:
        throats += [s] + _link(s, core, max(door_width, 6.0))
    throats = [(max(t[0], x0), max(t[1], y0), min(t[2], x1), min(t[3], y1)) for t in throats]

    if complex == "voronoi":
        polys = _voronoi_cells(box, cell_size, relax, rng)
    elif complex == "grid":
        polys = _grid_cells(box, cell_size)
    elif complex == "facet":
        middle, corners = _facet_cells(box, shape, rng)
        polys = [middle] + corners
    else:
        raise ValueError(f"complex {complex!r}: expected one of {COMPLEXES}")
    forced_rects = [core] + throats
    for r in forced_rects:
        cut = []
        for poly in polys:
            inside, outside = _clip(poly, r)
            cut += ([inside] if len(inside) >= 3 else []) + outside
        polys = cut

    verts, cells = _weld(polys)
    pts = np.array(verts)
    cen = np.array([pts[c].mean(axis=0) for c in cells])
    areas = np.array([_area([verts[i] for i in c]) for c in cells])
    box_area = (x1 - x0) * (y1 - y0)
    edge_cells: Dict[Tuple[int, int], List[int]] = {}
    for k, c in enumerate(cells):
        for a, b in zip(c, c[1:] + c[:1]):
            edge_cells.setdefault((min(a, b), max(a, b)), []).append(k)
    neighbours: List[set] = [set() for _ in cells]
    for owners in edge_cells.values():
        for a in owners:
            neighbours[a].update(o for o in owners if o != a)

    chosen = np.zeros(len(cells), bool)
    for r in forced_rects:
        chosen |= ((cen[:, 0] >= r[0]) & (cen[:, 0] <= r[2]) & (cen[:, 1] >= r[1]) & (cen[:, 1] <= r[3]))

    if complex == "facet":
        centres = [_Pt(c) for c in cen]
        chosen |= np.array([_in_convex(middle, p) for p in centres])

    wide = (x1 - x0) >= (y1 - y0)
    su, sv = rng.choice((-1, 1)), rng.choice((-1, 1))
    jitter = JITTER[complex]
    scores = [(_score(shape, (cx - (x0 + x1) / 2) / ((x1 - x0) / 2),
                      (cy - (y0 + y1) / 2) / ((y1 - y0) / 2), wide, su, sv)
               + jitter * rng.random()) for cx, cy in cen]
    target = 0.0 if complex == "facet" else max(fill, FILL_FLOOR) * box_area
    area = float(areas[chosen].sum())
    frontier = {n for k in np.nonzero(chosen)[0] for n in neighbours[k] if not chosen[n]}
    while area < target and frontier:
        k = min(frontier, key=lambda f: (scores[f], f))
        frontier.discard(k)
        chosen[k] = True
        area += float(areas[k])
        frontier |= {n for n in neighbours[k] if not chosen[n]}

    # A pocket of Cells ringed by chosen ones is a hole; columns are step 9's.
    outer = {k for owners in edge_cells.values() if len(owners) == 1 for k in owners if not chosen[k]}
    stack, seen = list(outer), set(outer)
    while stack:
        for n in neighbours[stack.pop()]:
            if not chosen[n] and n not in seen:
                seen.add(n)
                stack.append(n)
    chosen |= np.array([not chosen[k] and k not in seen for k in range(len(cells))])

    keep = [cells[k] for k in np.nonzero(chosen)[0]]
    used = sorted({i for c in keep for i in c})
    remap = {old: new for new, old in enumerate(used)}
    keep = _close_holes([verts[i] for i in used], [[remap[i] for i in c] for c in keep])
    verts = [verts[i] for i in used]
    # Splitting edges moves a Cell's mean, so judge the fans again afterwards.
    for scale in (1.0, 0.5, 0.25, 0.0):
        final, final_cells = _split_long_edges(_wander(verts, keep, forced_rects, wobble * scale, rng), keep)
        if all(_fans_sound(final, c) for c in final_cells):
            break
    return Outline(verts=final, cells=final_cells, core=core, throats=throats)


# ---------------------------------------------------------------------------
# Relief (step 8, Requirement 7)
# ---------------------------------------------------------------------------

MAX_GRADE = 0.45        # a floor's rise over run between vertices: about 24 degrees


def _noise_01(pts: np.ndarray, scale: float, seed: int) -> np.ndarray:
    """Smooth noise over the plan, 0 to 1 (the lower half of the noise reads as flat)."""
    z = np.zeros(len(pts), dtype=np.float32)
    return np.clip(_value_noise_3d(pts[:, 0] / scale, pts[:, 1] / scale, z, seed) * 2.0, 0.0, 1.0)


def add_relief(outline: Outline, height: float, floor_rise: float, ceiling_fall: float,
               min_head: float, scale: float, rng: random.Random) -> None:
    """Set the Outline's ``lift`` and ``drop``. A floor only rises and a ceiling only
    falls, so a stacked room's Slab stands. Floors stay at their height in the Core
    (the spawn stands there) and every Throat; ceilings stay in Throats, so lintels and
    Bridge shafts meet them. No edge climbs over ``MAX_GRADE``, so the walk gate passes
    the first time rather than on a retry. Headroom stays at least ``min_head``."""
    if floor_rise <= 0 and ceiling_fall <= 0:
        return
    pts = np.array(outline.verts, dtype=np.float64)

    def within(rects: List[Rect]) -> np.ndarray:
        mask = np.zeros(len(pts), bool)
        for r in rects:
            mask |= (pts[:, 0] >= r[0] - 1e-3) & (pts[:, 0] <= r[2] + 1e-3) & \
                    (pts[:, 1] >= r[1] - 1e-3) & (pts[:, 1] <= r[3] + 1e-3)
        return mask

    in_throat = within(outline.throats)
    lift = _noise_01(pts, scale, rng.randrange(1 << 30)).astype(np.float64) * floor_rise
    lift[in_throat | within([outline.core])] = 0.0
    drop = _noise_01(pts, scale, rng.randrange(1 << 30)).astype(np.float64) * ceiling_fall
    drop[in_throat] = 0.0

    # The steepest a floor may climb, along each edge of the mesh: relax to the bound.
    edges = {(min(a, b), max(a, b)) for c in outline.cells for a, b in zip(c, c[1:] + c[:1])}
    ea = np.array([e[0] for e in edges], dtype=np.int64)
    eb = np.array([e[1] for e in edges], dtype=np.int64)
    cap = np.hypot(*(pts[ea] - pts[eb]).T) * MAX_GRADE
    for _ in range(len(pts)):
        before = lift.copy()
        np.minimum.at(lift, ea, lift[eb] + cap)
        np.minimum.at(lift, eb, lift[ea] + cap)
        if np.array_equal(before, lift):
            break

    drop = np.minimum(drop, np.maximum(0.0, height - lift - min_head))
    outline.lift = [round(float(v), PLACES) for v in lift]
    outline.drop = [round(float(v), PLACES) for v in drop]

