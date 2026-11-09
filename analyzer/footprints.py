"""
analyzer/footprints.py
----------------------
The walk gate's Structure check (wilderness POIs spec task 2, Requirement 2).

Placed models (trees, and later a Site's Structures) stand on the ground as ZON
objects. The walk surface alone can't see them: the ground runs on under a hut
wall. This module judges them from the models' OWN collidable triangles, placed
by their ZON objects, so the gate never takes the placer's word for a shape.

Four failures, each named (:class:`GateFailure` ``kind``):

``footprint_cut``
    The Footprints cut reached ground off from Spawn. With every Footprint
    removed, the ground joined to Spawn may lose nothing but the Footprints
    themselves.
``opening_narrow`` / ``opening_low``
    An Enterable's opening is narrower than :data:`CLEAR_WIDTH`, or lower than
    :data:`HEAD_HEIGHT`. Measured on the model at the object's scale, the
    ground (z = 0, the model's origin) as its floor.
``interior_unreached``
    No ground inside an Enterable is reached from Spawn.
``poi_unreached``
    A POI doesn't stand on (or beside) reached ground.

The Footprint
~~~~~~~~~~~~~
A pixel of ground (centre ``p``, ground height ``g``) is covered when a player
standing there would touch a collidable triangle in the band
``[g + max_step_up, g + HEAD_HEIGHT]``: lower than that is stepped over, higher
is over the head. Two rules:

* **Near a triangle.** The triangle, clipped to the pixel's own band, comes
  within the player's half-width of ``p`` in plan. This is a distance test
  against the exact clipped polygon, not a sample of it, so a wall of no
  thickness still covers a strip ``2 x half-width`` wide.
* **Inside a solid.** Looking straight up from the band's floor, the first
  collidable triangle met faces up (its winding's normal): ``p`` is inside a
  closed solid (a trunk, a tower). This is why solids must be closed and
  wound outward (task 3's P3).

The raster
~~~~~~~~~~
The zone is judged at :data:`GATE_STEP` (2 u, the step ``trees_block`` used),
4-connected. A covered strip is at least ``2 x half-width = 3 u`` wide along
any axis, more than the 2 u between 4-neighbours, so no wall slips between
samples. A gap leaves a free strip ``width - 3 u`` wide, and any strip at least
``step x sqrt 2 = 2.83 u`` wide holds a 4-connected run of pixel centres at
any angle, so every gap from 5.83 u up stays open; :data:`CLEAR_WIDTH` (8 u) is
well above that.

Openings are measured on a finer local raster (:data:`OPENING_STEP`, 0.5 u):
the walls grown by ``CLEAR_WIDTH / 2 - OPENING_STEP / sqrt 2`` must leave the
inside joined to the outside. Any opening at least ``CLEAR_WIDTH`` wide passes
whatever its angle to the grid; one narrower than ``CLEAR_WIDTH - 0.71 u``
always fails.

A model is Enterable when its walls enclose free ground: inside the plan hull
of its collidable triangles in the band, not covered, at least
:data:`MIN_INTERIOR` u^2 of it. Trunks are filled and fence runs enclose
nothing, so neither is; anything that does enclose ground must let a player in.

Entry points: :func:`placed_from_zon`, :class:`GroundRaster`,
:func:`check_footprints`.

The room gate
~~~~~~~~~~~~~
Room-graph builds (dungeon, city, an outdoor dungeon's rooms) judge placed
models too (room-decor spec task 5), through :func:`check_room_props`, which
``analyzer.traverse.validate`` runs on every ``.eqg`` whose ZON places a model
in the room graph. Its floor is the mesh's own reached faces, sampled on every
Level at once; its obstacles are the models' collidable triangles beside the
mesh's walls, open shells and odd winding included (no "inside a solid" rule).
Its failures are ``footprint_cut``, ``throat_narrow`` and ``poi_unreached``;
see the section at the end of this module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from scipy.ndimage import binary_dilation, label

from analyzer.traverse import AgentModel
from core.ter import FLAG_PASSABLE, TerFile
from core.zon import ZonFile

#: Half the player's width (u): a Footprint is the triangles grown by this.
PLAYER_HALF_WIDTH = 1.5
#: Head height (u): collidable triangles below it, above the ground, block. The
#: player is 6 u tall; 8 u is the headroom the Transition check also asks.
HEAD_HEIGHT = 8.0
#: The clear width an Enterable's opening leaves (u), all the way up to
#: HEAD_HEIGHT.
CLEAR_WIDTH = 8.0
#: Raster step of the zone check (u). Must stay under 2 x PLAYER_HALF_WIDTH.
GATE_STEP = 2.0
#: Raster step of the opening measure (u).
OPENING_STEP = 0.5
#: Least enclosed free ground that makes a model Enterable (u^2).
MIN_INTERIOR = 4.0
#: A POI stands on reached ground when reached ground lies this close (u).
POI_REACH = PLAYER_HALF_WIDTH + GATE_STEP
#: Pairs of (triangle, pixel) handled per numpy batch.
_BATCH = 20_000


# ---------------------------------------------------------------------------
# Placed models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Placed:
    """One ZON object with the model it places."""

    name: str
    model_name: str
    model: TerFile
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    scale: float = 1.0


def placed_from_zon(zon: ZonFile, models: Mapping[str, TerFile]) -> List[Placed]:
    """Every ZON object with its model, looked up by archive filename (case
    doesn't matter). Objects placing the terrain (``*.ter``) are skipped; an
    object whose model the archive doesn't hold raises ``ValueError`` naming
    it, since the gate can't judge what it can't see."""
    lookup = {k.lower(): v for k, v in models.items()}
    out: List[Placed] = []
    for obj in zon.objects:
        fname = zon.models[obj.model_id]
        if fname.lower().endswith(".ter"):
            continue
        model = lookup.get(fname.lower())
        if model is None:
            raise ValueError(f"ZON object {obj.name!r} places {fname!r}, "
                             f"which the archive doesn't hold")
        out.append(Placed(obj.name, fname, model, obj.x, obj.y, obj.z,
                          obj.yaw, obj.pitch, obj.roll, obj.scale))
    return out


def collidable_triangles(model: TerFile) -> np.ndarray:
    """The model's collidable triangles, (T, 3, 3), model space."""
    v = np.array([[p.x, p.y, p.z] for p in model.vertices], dtype=np.float64).reshape(-1, 3)
    f = np.array([[q.v1, q.v2, q.v3] for q in model.polygons
                  if not q.flags & FLAG_PASSABLE], dtype=np.int64).reshape(-1, 3)
    return v[f]


def _rotation(yaw: float, pitch: float, roll: float) -> np.ndarray:
    """Yaw about Z, after pitch about Y, after roll about X (all radians)."""
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cr, sr = math.cos(roll), math.sin(roll)
    rz = np.array([[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]])
    ry = np.array([[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]])
    rx = np.array([[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]])
    return rz @ ry @ rx


def world_triangles(p: Placed, local: Optional[np.ndarray] = None) -> np.ndarray:
    """``p``'s collidable triangles in world space, (T, 3, 3): scaled, turned
    and moved as the client places the object."""
    tri = collidable_triangles(p.model) if local is None else local
    rot = _rotation(p.yaw, p.pitch, p.roll)
    return tri @ rot.T * p.scale + np.array([p.x, p.y, p.z])


# ---------------------------------------------------------------------------
# The ground raster
# ---------------------------------------------------------------------------

@dataclass
class GroundRaster:
    """Pixel centres ``xs`` x ``ys``, which pixels are reached ground
    (``walk``), the ground height under each, and Spawn's pixel.

    Ground height comes from ``face_of`` (the TER face under each pixel) and
    ``face_verts`` (each face's corners), or is ``flat_z`` everywhere.
    ``cell_origin`` / ``cell_res`` name a pixel by its terrain cell in
    failures; without them a pixel is named by its world XY."""

    xs: np.ndarray
    ys: np.ndarray
    walk: np.ndarray
    spawn: Tuple[int, int]
    face_of: Optional[np.ndarray] = None
    face_verts: Optional[np.ndarray] = None
    flat_z: float = 0.0
    cell_origin: Optional[Tuple[float, float]] = None
    cell_res: Optional[float] = None

    @property
    def step(self) -> float:
        return float(self.xs[1] - self.xs[0]) if len(self.xs) > 1 else GATE_STEP

    def z_at(self, ii: np.ndarray, jj: np.ndarray) -> np.ndarray:
        """Ground height at pixels (ii, jj): the face's plane at the centre."""
        if self.face_of is None:
            return np.full(np.shape(ii), self.flat_z, dtype=np.float64)
        t = self.face_verts[self.face_of[ii, jj]]
        return _plane_z(t, self.xs[ii], self.ys[jj])

    def index(self, x: float, y: float) -> Tuple[int, int]:
        x0, y0, s = self.xs[0], self.ys[0], self.step
        i = min(max(int(round((x - x0) / s)), 0), len(self.xs) - 1)
        j = min(max(int(round((y - y0) / s)), 0), len(self.ys) - 1)
        return i, j

    def name(self, i: int, j: int) -> str:
        x, y = float(self.xs[i]), float(self.ys[j])
        if self.cell_origin is not None and self.cell_res:
            ox, oy = self.cell_origin
            return f"playable cell ({int((x - ox) // self.cell_res)},{int((y - oy) // self.cell_res)})"
        return f"({x:.0f}, {y:.0f})"


def flat_raster(x0: float, y0: float, x1: float, y1: float, step: float,
                z: float = 0.0) -> GroundRaster:
    """A flat, all-walkable raster over a box (an opening's local frame)."""
    xs = np.arange(x0 + step / 2, x1, step)
    ys = np.arange(y0 + step / 2, y1, step)
    return GroundRaster(xs=xs, ys=ys, walk=np.ones((len(xs), len(ys)), bool),
                        spawn=(0, 0), flat_z=z)


def _plane_z(t: np.ndarray, px: np.ndarray, py: np.ndarray) -> np.ndarray:
    """z of each triangle's plane (``t`` (N, 3, 3)) at (px, py); a vertical
    triangle gives its lowest corner."""
    a, b, c = t[:, 0], t[:, 1], t[:, 2]
    n = np.cross(b - a, c - a)
    nz = n[:, 2]
    ok = np.abs(nz) > 1e-12
    safe = np.where(ok, nz, 1.0)
    z = a[:, 2] - (n[:, 0] * (px - a[:, 0]) + n[:, 1] * (py - a[:, 1])) / safe
    return np.where(ok, z, t[:, :, 2].min(axis=1))


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------

def _clip(poly: np.ndarray, sign: float, c: np.ndarray):
    """Clip convex polygons ``poly`` (N, K, 3) to ``sign * (z - c) >= 0``.
    Returns (N, 2K, 3) polygons (missing corners repeat a neighbour) and which
    rows are non-empty."""
    n, k, _ = poly.shape
    d = sign * (poly[..., 2] - c[:, None])
    nxt = np.roll(poly, -1, axis=1)
    dn = np.roll(d, -1, axis=1)
    keep = d >= 0
    cross = keep != (dn >= 0)
    denom = np.where(cross, d - dn, 1.0)
    t = np.where(cross, d / denom, 0.0)
    ip = poly + t[..., None] * (nxt - poly)
    out = np.stack([poly, ip], axis=2).reshape(n, 2 * k, 3)
    ok = np.stack([keep, cross], axis=2).reshape(n, 2 * k)
    idx = np.where(ok, np.arange(2 * k)[None, :], -1)
    idx = np.maximum.accumulate(idx, axis=1)
    idx = np.where(idx < 0, idx[:, -1:], idx)
    out = np.take_along_axis(out, np.maximum(idx, 0)[..., None], axis=1)
    return out, ok.any(axis=1)


def _dist_to_polygon(poly: np.ndarray, px: np.ndarray, py: np.ndarray) -> np.ndarray:
    """Plan distance from (px, py) to each convex polygon (N, M, 2+), zero
    inside. A polygon of no area (a wall seen from above) is its edges."""
    a = poly[..., :2]
    b = np.roll(a, -1, axis=1)
    p = np.stack([px, py], axis=-1)[:, None, :]
    ab = b - a
    ap = p - a
    l2 = (ab ** 2).sum(-1)
    t = np.clip((ap * ab).sum(-1) / np.where(l2 > 0, l2, 1.0), 0.0, 1.0)
    d = np.sqrt(((ap - t[..., None] * ab) ** 2).sum(-1)).min(axis=1)
    cr = ab[..., 0] * ap[..., 1] - ab[..., 1] * ap[..., 0]
    area = 0.5 * np.abs((a[..., 0] * b[..., 1] - b[..., 0] * a[..., 1]).sum(axis=1))
    inside = (area > 1e-9) & ((cr >= -1e-9).all(axis=1) | (cr <= 1e-9).all(axis=1))
    return np.where(inside, 0.0, d)


def _pairs(lo_i, hi_i, lo_j, hi_j):
    """All (row, i, j) with lo <= i < hi, lo <= j < hi per row."""
    ni = np.maximum(hi_i - lo_i, 0)
    nj = np.maximum(hi_j - lo_j, 0)
    n = ni * nj
    total = int(n.sum())
    if total == 0:
        e = np.zeros(0, np.int64)
        return e, e, e
    row = np.repeat(np.arange(len(n)), n)
    off = np.arange(total) - np.repeat(np.cumsum(n) - n, n)
    njr = nj[row]
    return row, lo_i[row] + off // njr, lo_j[row] + off % njr


def _batches(counts: np.ndarray, limit: int = _BATCH):
    """Split rows into consecutive runs of about ``limit`` pairs."""
    start, acc = 0, 0
    for k, c in enumerate(counts.tolist()):
        if acc and acc + c > limit:
            yield start, k
            start, acc = k, 0
        acc += c
    if start < len(counts):
        yield start, len(counts)


@dataclass
class Coverage:
    """Which pixels the triangles cover, and which object (index into the
    owners passed in) last covered each (-1 for none)."""

    covered: np.ndarray
    owner: np.ndarray


def coverage(ground: GroundRaster, tris: np.ndarray, owners: np.ndarray,
             radius: float, low: float, high: float) -> Coverage:
    """Pixels a body of ``radius`` can't stand on: near a triangle clipped to
    the band ``[g + low, g + high]`` above the pixel's ground ``g``, or inside a
    solid (see the module docstring)."""
    nx, ny = len(ground.xs), len(ground.ys)
    covered = np.zeros((nx, ny), dtype=bool)
    owner = np.full((nx, ny), -1, dtype=np.int32)
    if len(tris) == 0:
        return Coverage(covered, owner)
    x0, y0, s = float(ground.xs[0]), float(ground.ys[0]), ground.step
    lo = tris.min(axis=1)
    hi = tris.max(axis=1)

    def span(a, b, x00, n):
        i0 = np.clip(np.ceil((a - x00) / s).astype(np.int64), 0, n)
        i1 = np.clip(np.floor((b - x00) / s).astype(np.int64) + 1, 0, n)
        return i0, i1

    # Rule 1: near a triangle's part in the band.
    i0, i1 = span(lo[:, 0] - radius, hi[:, 0] + radius, x0, nx)
    j0, j1 = span(lo[:, 1] - radius, hi[:, 1] + radius, y0, ny)
    counts = np.maximum(i1 - i0, 0) * np.maximum(j1 - j0, 0)
    for a, b in _batches(counts):
        row, ii, jj = _pairs(i0[a:b], i1[a:b], j0[a:b], j1[a:b])
        if len(row) == 0:
            continue
        row = row + a
        g = ground.z_at(ii, jj)
        # Quick reject: the triangle lies wholly under or over the band.
        keep = (hi[row, 2] >= g + low) & (lo[row, 2] <= g + high)
        row, ii, jj, g = row[keep], ii[keep], jj[keep], g[keep]
        if len(row) == 0:
            continue
        poly, ok1 = _clip(tris[row], 1.0, g + low)
        poly, ok2 = _clip(poly, -1.0, g + high)
        ok = ok1 & ok2
        d = _dist_to_polygon(poly[ok], ground.xs[ii[ok]], ground.ys[jj[ok]])
        hit = d <= radius
        ci, cj = ii[ok][hit], jj[ok][hit]
        covered[ci, cj] = True
        owner[ci, cj] = owners[row[ok][hit]]

    # Rule 2: inside a solid. The first triangle above the band's floor, in
    # plan over the pixel, faces up.
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    flat = np.abs(n[:, 2]) > 1e-9
    idx = np.nonzero(flat)[0]
    if len(idx):
        i0, i1 = span(lo[idx, 0], hi[idx, 0], x0, nx)
        j0, j1 = span(lo[idx, 1], hi[idx, 1], y0, ny)
        counts = np.maximum(i1 - i0, 0) * np.maximum(j1 - j0, 0)
        keys, zs, ups, objs = [], [], [], []
        for a, b in _batches(counts):
            row, ii, jj = _pairs(i0[a:b], i1[a:b], j0[a:b], j1[a:b])
            if len(row) == 0:
                continue
            t = idx[row + a]
            px, py = ground.xs[ii], ground.ys[jj]
            tri = tris[t]
            # Inside the triangle's plan (either winding).
            e = [(tri[:, (k + 1) % 3, :2] - tri[:, k, :2]) for k in range(3)]
            w = [e[k][:, 0] * (py - tri[:, k, 1]) - e[k][:, 1] * (px - tri[:, k, 0])
                 for k in range(3)]
            inside = (((w[0] >= 0) & (w[1] >= 0) & (w[2] >= 0))
                      | ((w[0] <= 0) & (w[1] <= 0) & (w[2] <= 0)))
            t, ii, jj, px, py = t[inside], ii[inside], jj[inside], px[inside], py[inside]
            if len(t) == 0:
                continue
            z = _plane_z(tris[t], px, py)
            g = ground.z_at(ii, jj)
            above = z >= g + low
            keys.append(ii[above] * ny + jj[above])
            zs.append(z[above])
            ups.append(n[t[above], 2] > 0)
            objs.append(owners[t[above]])
        if keys:
            keys = np.concatenate(keys)
            zs = np.concatenate(zs)
            ups = np.concatenate(ups)
            objs = np.concatenate(objs)
            if len(keys):
                order = np.lexsort((zs, keys))
                keys, ups, objs = keys[order], ups[order], objs[order]
                first = np.r_[True, keys[1:] != keys[:-1]]
                k, u, o = keys[first], ups[first], objs[first]
                fi, fj = k[u] // ny, k[u] % ny
                covered[fi, fj] = True
                owner[fi, fj] = o[u]
    return Coverage(covered, owner)


# ---------------------------------------------------------------------------
# Enterables
# ---------------------------------------------------------------------------

def _hull(points: np.ndarray) -> np.ndarray:
    """Convex hull of plan points, counter-clockwise (monotone chain)."""
    pts = np.unique(np.round(points, 6), axis=0)
    if len(pts) < 3:
        return pts
    pts = pts[np.lexsort((pts[:, 1], pts[:, 0]))]

    def half(seq):
        out: List[np.ndarray] = []
        for p in seq:
            while len(out) >= 2 and ((out[-1][0] - out[-2][0]) * (p[1] - out[-2][1])
                                     - (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0])) <= 0:
                out.pop()
            out.append(p)
        return out

    lower, upper = half(pts), half(pts[::-1])
    return np.array(lower[:-1] + upper[:-1])


def _in_hull(hull: np.ndarray, px: np.ndarray, py: np.ndarray) -> np.ndarray:
    """Which points lie strictly inside a CCW hull."""
    if len(hull) < 3:
        return np.zeros(np.broadcast(px, py).shape, dtype=bool)
    inside = np.ones(np.broadcast(px, py).shape, dtype=bool)
    for k in range(len(hull)):
        a, b = hull[k], hull[(k + 1) % len(hull)]
        inside &= (b[0] - a[0]) * (py - a[1]) - (b[1] - a[1]) * (px - a[0]) > 1e-9
    return inside


@dataclass(frozen=True)
class Opening:
    """What the opening measure found for one model at one scale."""

    enterable: bool
    hull: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    narrow: bool = False
    low: bool = False
    width: float = 0.0      # the widest body that gets in (u), when narrow
    height: float = 0.0     # the tallest band that lets a body in (u), when low


def _band_points(tris: np.ndarray, low: float, high: float) -> np.ndarray:
    """Plan corners of the triangles' parts between z = low and z = high."""
    if len(tris) == 0:
        return np.zeros((0, 2))
    poly, ok1 = _clip(tris, 1.0, np.full(len(tris), low))
    poly, ok2 = _clip(poly, -1.0, np.full(len(tris), high))
    return poly[ok1 & ok2][..., :2].reshape(-1, 2)


def measure_opening(local: np.ndarray, scale: float = 1.0,
                    agent: Optional[AgentModel] = None,
                    clear_width: float = CLEAR_WIDTH,
                    head_height: float = HEAD_HEIGHT,
                    step: float = OPENING_STEP) -> Opening:
    """Is the model (collidable triangles ``local``, model space, origin on
    the ground) Enterable at ``scale``, and is its way in at least
    ``clear_width`` wide all the way up to ``head_height``?"""
    agent = agent or AgentModel()
    tris = local * scale
    low = agent.max_step_up
    pts = _band_points(tris, low, head_height)
    if len(pts) < 3:
        return Opening(enterable=False)
    hull = _hull(pts)
    if len(hull) < 3:
        return Opening(enterable=False)
    pad = clear_width + 4 * step
    (ax, ay), (bx, by) = pts.min(axis=0) - pad, pts.max(axis=0) + pad
    ground = flat_raster(ax, ay, bx, by, step)
    gx, gy = np.meshgrid(ground.xs, ground.ys, indexing="ij")
    in_hull = _in_hull(hull, gx, gy)
    owners = np.zeros(len(tris), dtype=np.int32)

    def free(radius: float, high: float) -> np.ndarray:
        return ~coverage(ground, tris, owners, radius, low, high).covered

    inside = in_hull & free(step, head_height)
    if inside.sum() * step * step < MIN_INTERIOR:
        return Opening(enterable=False)

    def gets_in(radius: float, high: float) -> bool:
        f = free(radius, high)
        labels, _ = label(f)
        border = set(np.unique(np.r_[labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
        border.discard(0)
        reach = np.isin(labels, list(border))
        return bool((reach & in_hull & f).any())

    grain = step / math.sqrt(2.0)
    r_clear = max(clear_width / 2 - grain, 0.0)
    if gets_in(r_clear, head_height):
        return Opening(enterable=True, hull=hull)
    if gets_in(r_clear, agent.player_height):
        # Wide enough at the body, so something over it is too low.
        lo_h, hi_h = agent.player_height, head_height
        for _ in range(6):
            mid = (lo_h + hi_h) / 2
            lo_h, hi_h = (mid, hi_h) if gets_in(r_clear, mid) else (lo_h, mid)
        return Opening(enterable=True, hull=hull, low=True, height=lo_h)
    lo_r, hi_r = 0.0, r_clear
    for _ in range(6):
        mid = (lo_r + hi_r) / 2
        lo_r, hi_r = (mid, hi_r) if gets_in(mid, head_height) else (lo_r, mid)
    return Opening(enterable=True, hull=hull, narrow=True,
                   width=2 * (lo_r + grain) if lo_r > 0 else 0.0)


# ---------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GateFailure:
    """One named failure: ``kind`` (see the module docstring), the objects or
    POI it names (``subjects``), and where. ``where`` is the room (or
    corridor) the room gate found it in; "" on the wilderness gate."""

    kind: str
    subjects: Tuple[str, ...]
    detail: str
    where: str = ""

    def __str__(self) -> str:
        names = ", ".join(self.subjects[:3])
        if len(self.subjects) > 3:
            names += f" and {len(self.subjects) - 3} more"
        return f"{self.kind}: {names}: {self.detail}"


@dataclass
class FootprintReport:
    failures: List[GateFailure]
    covered: np.ndarray
    reached: np.ndarray        # ground joined to Spawn with the Footprints removed

    @property
    def passed(self) -> bool:
        return not self.failures

    def of(self, kind: str) -> List[GateFailure]:
        return [f for f in self.failures if f.kind == kind]


@dataclass(frozen=True)
class POI:
    """A named point that must stand on reached ground."""

    name: str
    x: float
    y: float


def _spawn_component(mask: np.ndarray, si: int, sj: int) -> np.ndarray:
    labels, _ = label(mask)
    lab = labels[si, sj]
    if lab == 0:  # Spawn's own pixel isn't in the mask: use the nearest one
        ii, jj = np.nonzero(mask)
        if len(ii) == 0:
            return np.zeros_like(mask)
        k = int(np.argmin((ii - si) ** 2 + (jj - sj) ** 2))
        lab = labels[ii[k], jj[k]]
    return labels == lab


def check_footprints(ground: GroundRaster, placed: Sequence[Placed],
                     pois: Sequence[POI] = (),
                     agent: Optional[AgentModel] = None) -> FootprintReport:
    """Judge the placed models on the ground (see the module docstring)."""
    agent = agent or AgentModel()
    low, high = agent.max_step_up, HEAD_HEIGHT
    locals_: Dict[int, np.ndarray] = {}
    parts, owners = [], []
    for k, p in enumerate(placed):
        loc = locals_.get(id(p.model))
        if loc is None:
            loc = locals_[id(p.model)] = collidable_triangles(p.model)
        if len(loc):
            parts.append(world_triangles(p, loc))
            owners.append(np.full(len(loc), k, dtype=np.int32))
    tris = np.concatenate(parts) if parts else np.zeros((0, 3, 3))
    own = np.concatenate(owners) if owners else np.zeros(0, np.int32)
    cov = coverage(ground, tris, own, PLAYER_HALF_WIDTH, low, high)
    covered = cov.covered

    si, sj = ground.spawn
    walk = ground.walk
    before = _spawn_component(walk, si, sj)
    after = _spawn_component(walk & ~covered, si, sj) if covered.any() else before
    failures: List[GateFailure] = []

    cut = before & ~covered & ~after
    if cut.any():
        labels, n = label(cut)
        for lab in range(1, n + 1):
            piece = labels == lab
            ring = binary_dilation(piece, iterations=2) & covered
            who = sorted({placed[o].name for o in np.unique(cov.owner[ring]) if o >= 0})
            ci, cj = (int(v[0]) for v in np.nonzero(piece))
            failures.append(GateFailure("footprint_cut", tuple(who),
                                        f"cuts off {ground.name(ci, cj)} from Spawn"))

    # Enterables: each model at each scale it's placed at, measured once.
    measured: Dict[Tuple[int, float], Opening] = {}
    probe: Dict[int, bool] = {}
    for k, p in enumerate(placed):
        loc = locals_.get(id(p.model))
        if loc is None or not len(loc):
            continue
        if id(p.model) not in probe:  # cheap: is it Enterable at all, at scale 1?
            probe[id(p.model)] = measure_opening(loc, 1.0, agent).enterable
        if not probe[id(p.model)]:
            continue
        key = (id(p.model), round(float(p.scale), 4))
        if key not in measured:
            measured[key] = measure_opening(loc, float(p.scale), agent)
        op = measured[key]
        if not op.enterable:
            continue
        if op.narrow:
            failures.append(GateFailure(
                "opening_narrow", (p.name,),
                f"its opening lets in {op.width:.1f} u, under the {CLEAR_WIDTH:g} u clear width"))
        elif op.low:
            failures.append(GateFailure(
                "opening_low", (p.name,),
                f"its opening is {op.height:.1f} u high, under the {HEAD_HEIGHT:g} u head height"))
        # Its interior on the ground: the hull, turned and moved as placed.
        rot = _rotation(p.yaw, 0.0, 0.0)[:2, :2]
        hull = op.hull @ rot.T + np.array([p.x, p.y])
        (ax, ay), (bx, by) = hull.min(axis=0), hull.max(axis=0)
        s = ground.step
        i0 = max(int(np.floor((ax - ground.xs[0]) / s)), 0)
        i1 = min(int(np.ceil((bx - ground.xs[0]) / s)) + 1, len(ground.xs))
        j0 = max(int(np.floor((ay - ground.ys[0]) / s)), 0)
        j1 = min(int(np.ceil((by - ground.ys[0]) / s)) + 1, len(ground.ys))
        reached_in = False
        if i0 < i1 and j0 < j1:
            px, py = np.meshgrid(ground.xs[i0:i1], ground.ys[j0:j1], indexing="ij")
            inside = _in_hull(hull, px, py)
            reached_in = bool((inside & after[i0:i1, j0:j1] & ~covered[i0:i1, j0:j1]).any())
        if not reached_in:
            failures.append(GateFailure("interior_unreached", (p.name,),
                                        f"no ground inside it at ({p.x:.0f}, {p.y:.0f}) "
                                        f"is reached from Spawn"))

    # POIs: reached ground within POI_REACH.
    if pois:
        s = ground.step
        r = int(math.ceil(POI_REACH / s))
        for poi in pois:
            i, j = ground.index(poi.x, poi.y)
            win = after[max(i - r, 0):i + r + 1, max(j - r, 0):j + r + 1]
            px, py = np.meshgrid(ground.xs[max(i - r, 0):i + r + 1],
                                 ground.ys[max(j - r, 0):j + r + 1], indexing="ij")
            near = np.hypot(px - poi.x, py - poi.y) <= POI_REACH
            if not (win & near).any():
                failures.append(GateFailure("poi_unreached", (poi.name,),
                                            f"at ({poi.x:.0f}, {poi.y:.0f}) is not on "
                                            f"reached ground"))
    return FootprintReport(failures=failures, covered=covered, reached=after)


# ---------------------------------------------------------------------------
# The room gate (room-decor spec task 5, Requirement 2)
# ---------------------------------------------------------------------------
#
# Room-graph builds (dungeon, city, an outdoor dungeon's rooms) have no ground
# raster: their floor is the mesh's own reached faces, on any number of Levels
# at one XY. So the room gate samples the reached faces at points (a 2.5D
# raster: each sample keeps its own floor height, and two samples join when
# they are 4-neighbours within a step of each other in height). The placed
# models' collidable triangles are obstacles beside the mesh's own walls, by
# the "near a triangle" rule above. There is no "inside a solid" rule here:
# stock models are open shells wound any way, so a solid's inside is told by
# its plan instead (a cut-off piece inside one model's plan hull is that
# model's inside, not floor anyone lost).
#
# Every verdict compares the floor with the models to the floor without them,
# on the same samples and the same mesh walls, so the raster's own artefacts
# (a narrow nook, a seam) never fail a build: only what the models change can.

#: Sample step of the room gate's clear-width check (u): an opening at least
#: CLEAR_WIDTH wide always passes, one under CLEAR_WIDTH - 2 x step / sqrt 2
#: (6.6 u) always fails.
ROOM_WIDE_STEP = 1.0
#: How far round a placed model the room gate reads the mesh's own walls (u).
ROOM_WINDOW = CLEAR_WIDTH + 2 * GATE_STEP
#: How far off a room's floor height a door or core sample may stand (u).
FLOOR_LEVEL_TOL = 4.0
#: Floor samples at one XY closer than this in height are one sample (u).
_SAME_FLOOR = 0.5


@dataclass
class FloorSamples:
    """Points on a mesh's floor faces: pixel ``(i, j)`` of a grid at ``step``
    from ``(x0, y0)``, its floor height ``z`` and the ``face`` it lies on,
    sorted by ``key`` (``i * ny + j``). One XY may hold several samples, one per
    Level."""

    x0: float
    y0: float
    step: float
    ny: int
    i: np.ndarray
    j: np.ndarray
    z: np.ndarray
    face: np.ndarray
    key: np.ndarray

    @property
    def x(self) -> np.ndarray:
        return self.x0 + (self.i + 0.5) * self.step

    @property
    def y(self) -> np.ndarray:
        return self.y0 + (self.j + 0.5) * self.step

    def __len__(self) -> int:
        return len(self.z)

    def lookup(self, keys: np.ndarray):
        """For each key: the first sample holding it, and how many do."""
        lo = np.searchsorted(self.key, keys, side="left")
        hi = np.searchsorted(self.key, keys, side="right")
        return lo, hi - lo


def floor_samples(tris: np.ndarray, faces: np.ndarray, step: float,
                  box: Optional[Tuple[float, float, float, float]] = None) -> FloorSamples:
    """Sample the floor triangles ``tris`` (F, 3, 3), whose face ids are
    ``faces``, at ``step``, inside the plan ``box`` (x0, y0, x1, y1) if given.
    The grid is anchored at a multiple of ``step``."""
    if box is None and len(tris):
        lo, hi = tris.reshape(-1, 3).min(axis=0), tris.reshape(-1, 3).max(axis=0)
        box = (float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1]))
    elif box is None:
        box = (0.0, 0.0, 0.0, 0.0)
    gx0 = math.floor(box[0] / step) * step - step
    gy0 = math.floor(box[1] / step) * step - step
    ni = int(math.ceil((box[2] - gx0) / step)) + 2
    ny = int(math.ceil((box[3] - gy0) / step)) + 2
    ints = np.zeros(0, np.int64)
    empty = FloorSamples(gx0, gy0, step, ny, ints, ints, np.zeros(0), ints, ints)
    if len(tris) == 0:
        return empty
    lo, hi = tris.min(axis=1), tris.max(axis=1)

    def span(a, b, origin, n):
        k0 = np.clip(np.ceil((a - origin) / step - 0.5), 0, n).astype(np.int64)
        k1 = np.clip(np.floor((b - origin) / step - 0.5) + 1, 0, n).astype(np.int64)
        return k0, k1

    i0, i1 = span(np.maximum(lo[:, 0], box[0]), np.minimum(hi[:, 0], box[2]), gx0, ni)
    j0, j1 = span(np.maximum(lo[:, 1], box[1]), np.minimum(hi[:, 1], box[3]), gy0, ny)
    counts = np.maximum(i1 - i0, 0) * np.maximum(j1 - j0, 0)
    out_i, out_j, out_z, out_f = [], [], [], []
    for a, b in _batches(counts):
        row, ii, jj = _pairs(i0[a:b], i1[a:b], j0[a:b], j1[a:b])
        if len(row) == 0:
            continue
        t = tris[row + a]
        px, py = gx0 + (ii + 0.5) * step, gy0 + (jj + 0.5) * step
        e = [(t[:, (k + 1) % 3, :2] - t[:, k, :2]) for k in range(3)]
        w = [e[k][:, 0] * (py - t[:, k, 1]) - e[k][:, 1] * (px - t[:, k, 0]) for k in range(3)]
        inside = (((w[0] >= -1e-9) & (w[1] >= -1e-9) & (w[2] >= -1e-9))
                  | ((w[0] <= 1e-9) & (w[1] <= 1e-9) & (w[2] <= 1e-9)))
        if not inside.any():
            continue
        out_i.append(ii[inside])
        out_j.append(jj[inside])
        out_z.append(_plane_z(t[inside], px[inside], py[inside]))
        out_f.append(faces[row[inside] + a])
    if not out_i:
        return empty
    i, j = np.concatenate(out_i), np.concatenate(out_j)
    z, f = np.concatenate(out_z), np.concatenate(out_f)
    key = i * ny + j
    order = np.lexsort((z, key))
    i, j, z, f, key = i[order], j[order], z[order], f[order], key[order]
    new = np.r_[True, (key[1:] != key[:-1]) | (z[1:] - z[:-1] > _SAME_FLOOR)]
    return FloorSamples(gx0, gy0, step, ny, i[new], j[new], z[new], f[new], key[new])


def _expand(first: np.ndarray, count: np.ndarray):
    """(which row, which index) for rows each naming ``count`` consecutive
    indices from ``first``."""
    total = int(count.sum())
    row = np.repeat(np.arange(len(count)), count)
    return row, np.repeat(first, count) + (np.arange(total) - np.repeat(np.cumsum(count) - count, count))


def _sample_edges(fs: FloorSamples, step_up: float):
    """4-neighbour sample pairs (a, b) whose floors are within ``step_up``."""
    aa, bb = [], []
    for dk in (fs.ny, 1):
        first, count = fs.lookup(fs.key + dk)
        a, b = _expand(first, count)
        ok = np.abs(fs.z[a] - fs.z[b]) <= step_up
        aa.append(a[ok])
        bb.append(b[ok])
    return np.concatenate(aa), np.concatenate(bb)


def _sample_labels(n: int, edges, free: np.ndarray) -> np.ndarray:
    """Component label of each free sample (-1 for the rest)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    a, b = edges
    m = free[a] & free[b]
    g = coo_matrix((np.ones(int(m.sum()), np.int8), (a[m], b[m])), shape=(n, n))
    _, lab = connected_components(g, directed=False)
    return np.where(free, lab, -1)


def cover_samples(fs: FloorSamples, tris: np.ndarray, owners: np.ndarray,
                  radius: float, low: float, high: float) -> Coverage:
    """:func:`coverage`'s "near a triangle" rule on floor samples: a sample
    (floor ``g``) is covered when a triangle, clipped to ``[g + low, g + high]``,
    comes within ``radius`` of it in plan. ``Coverage`` arrays are per sample."""
    n = len(fs)
    covered = np.zeros(n, dtype=bool)
    owner = np.full(n, -1, dtype=np.int32)
    if n == 0 or len(tris) == 0:
        return Coverage(covered, owner)
    s = fs.step
    ni = int(fs.i.max()) + 1
    lo, hi = tris.min(axis=1), tris.max(axis=1)

    def span(a, b, origin, m):
        k0 = np.clip(np.ceil((a - origin) / s - 0.5), 0, m).astype(np.int64)
        k1 = np.clip(np.floor((b - origin) / s - 0.5) + 1, 0, m).astype(np.int64)
        return k0, k1

    i0, i1 = span(lo[:, 0] - radius, hi[:, 0] + radius, fs.x0, ni)
    j0, j1 = span(lo[:, 1] - radius, hi[:, 1] + radius, fs.y0, fs.ny)
    counts = np.maximum(i1 - i0, 0) * np.maximum(j1 - j0, 0)
    for a, b in _batches(counts):
        row, ii, jj = _pairs(i0[a:b], i1[a:b], j0[a:b], j1[a:b])
        if len(row) == 0:
            continue
        first, count = fs.lookup(ii * fs.ny + jj)
        k, p = _expand(first, count)
        row = row[k] + a
        g = fs.z[p]
        # Quick reject: the triangle lies wholly under or over the band.
        keep = (hi[row, 2] >= g + low) & (lo[row, 2] <= g + high)
        row, p, g = row[keep], p[keep], g[keep]
        if len(row) == 0:
            continue
        poly, ok1 = _clip(tris[row], 1.0, g + low)
        poly, ok2 = _clip(poly, -1.0, g + high)
        ok = ok1 & ok2
        if not ok.any():
            continue
        d = _dist_to_polygon(poly[ok], fs.x[p[ok]], fs.y[p[ok]])
        hit = d <= radius
        covered[p[ok][hit]] = True
        owner[p[ok][hit]] = owners[row[ok][hit]]
    return Coverage(covered, owner)


def _boxes_hit(lo: np.ndarray, hi: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    """Which 3D boxes ``lo``..``hi`` (N, 3) meet any of ``boxes`` (M, 6:
    x0 y0 z0 x1 y1 z1)."""
    out = np.zeros(len(lo), dtype=bool)
    for k in range(0, len(boxes), 64):
        b = boxes[k:k + 64]
        m = ((lo[:, None, 0] <= b[None, :, 3]) & (hi[:, None, 0] >= b[None, :, 0])
             & (lo[:, None, 1] <= b[None, :, 4]) & (hi[:, None, 1] >= b[None, :, 1])
             & (lo[:, None, 2] <= b[None, :, 5]) & (hi[:, None, 2] >= b[None, :, 2]))
        out |= m.any(axis=1)
    return out


def _region_boxes(spec) -> np.ndarray:
    """The room graph's 3D boxes: each room's, and each corridor leg's from its
    lower floor to its ceiling. A placed model meeting none (an outdoor
    dungeon's trees) is the wilderness gate's, not the room gate's."""
    from generators.routing import corridor_route, route_footprint

    rooms = {r.id: r for r in spec.rooms}
    out = []
    for r in spec.rooms:
        (x0, y0, z0), (x1, y1, z1) = r.bounds
        out.append((x0, y0, z0 - 1.0, x1, y1, z1))
    for c in spec.corridors:
        if c.from_room not in rooms or c.to_room not in rooms:
            continue
        z0 = min(c.from_z, c.to_z) - 1.0
        z1 = max(c.from_z, c.to_z) + c.height
        for x0, y0, x1, y1 in route_footprint(corridor_route(c, rooms), c.width / 2):
            out.append((x0, y0, z0, x1, y1, z1))
    return np.array(out, dtype=np.float64).reshape(-1, 6)


def _where(spec, x: float, y: float, z: float) -> str:
    """The room whose Box holds (x, y, z), else the nearest one."""
    best, dist = "", math.inf
    for r in spec.rooms:
        (x0, y0, z0), (x1, y1, z1) = r.bounds
        if x0 <= x <= x1 and y0 <= y <= y1 and z0 - 1.0 <= z <= z1:
            return r.id
        d = math.hypot(max(x0 - x, 0.0, x - x1), max(y0 - y, 0.0, y - y1)) + abs(z - z0)
        if d < dist:
            best, dist = r.id, d
    return best


def _nearest(fs: FloorSamples, mask: np.ndarray, x: float, y: float, z: float,
             limit: float = math.inf) -> int:
    """The masked sample nearest (x, y) in plan within ``limit``, preferring
    those within FLOOR_LEVEL_TOL of ``z``; -1 when there is none."""
    idx = np.nonzero(mask)[0]
    if len(idx) == 0:
        return -1
    d = np.hypot(fs.x[idx] - x, fs.y[idx] - y)
    dz = np.abs(fs.z[idx] - z)
    k = int(np.argmin(d + np.where(dz <= FLOOR_LEVEL_TOL, 0.0, 1e6 + dz)))
    return int(idx[k]) if d[k] <= limit else -1


#: How far into its room a door's way runs, for the clear-width check (u).
DOOR_WAY = 2 * CLEAR_WIDTH


def _door_way(room, door, margin: float) -> Tuple[float, float, float, float]:
    """The plan rect a door's way into ``room`` takes: the door's strip,
    ``margin`` wider each side, DOOR_WAY deep."""
    (x0, y0, _), (x1, y1, _) = room.bounds
    side, c0, c1 = door
    a, b = c0 - margin, c1 + margin
    return {"S": (a, y0, b, y0 + DOOR_WAY), "N": (a, y1 - DOOR_WAY, b, y1),
            "W": (x0, a, x0 + DOOR_WAY, b), "E": (x1 - DOOR_WAY, a, x1, b)}[side]


def _in_doorway(fs: FloorSamples, room, side: str, c0: float, c1: float,
                depth: float) -> np.ndarray:
    """Samples in a door's strip, at most ``depth`` into the room."""
    (x0, y0, _), (x1, y1, _) = room.bounds
    along, d = {"S": (fs.x, fs.y - y0), "N": (fs.x, y1 - fs.y),
                "W": (fs.y, fs.x - x0), "E": (fs.y, x1 - fs.x)}[side]
    return (along >= c0) & (along <= c1) & (d >= -ROOM_WIDE_STEP) & (d <= depth)


def _in_room_graph(placed: Sequence[Placed], spec):
    """The placed models standing in the room graph: (their indices, their
    world triangles, each triangle's owner)."""
    grown = _region_boxes(spec) + np.array(
        [-ROOM_WINDOW, -ROOM_WINDOW, 0.0, ROOM_WINDOW, ROOM_WINDOW, 0.0])
    locals_: Dict[int, np.ndarray] = {}
    kept, parts, owners = [], [], []
    for k, p in enumerate(placed):
        loc = locals_.get(id(p.model))
        if loc is None:
            loc = locals_[id(p.model)] = collidable_triangles(p.model)
        if not len(loc):
            continue
        w = world_triangles(p, loc)
        if not _boxes_hit(w.min(axis=(0, 1))[None], w.max(axis=(0, 1))[None], grown)[0]:
            continue
        kept.append(k)
        parts.append(w)
        owners.append(np.full(len(w), k, dtype=np.int32))
    if not parts:
        return kept, np.zeros((0, 3, 3)), np.zeros(0, np.int32)
    return kept, np.concatenate(parts), np.concatenate(owners)


def check_room_props(surf, reached, spec, placed: Sequence[Placed], mesh: np.ndarray,
                     seed_face: Optional[int],
                     agent: Optional[AgentModel] = None) -> List[GateFailure]:
    """The room gate's verdict on placed models (Requirement 2): every
    failure, named, its ``where`` the room it's in. Empty when no placed
    model stands in the room graph, whatever else the zone holds.

    ``surf`` and ``reached`` are the walk surface and the faces reached from
    the entrance (``analyzer.traverse``), ``mesh`` the mesh's own collidable
    triangles (T, 3, 3), ``seed_face`` the face the walk starts on.

    ``footprint_cut``
        Floor joined to the entrance without the models is cut off with them:
        at least ``WALLED_OFF`` u^2 of it (step 9's walled-off pocket), not
        inside one model's plan.
    ``throat_narrow``
        A door's way to its room's Core (its Throat, and the Spine on) let a
        body CLEAR_WIDTH wide through without the models and doesn't with them.
    ``poi_unreached``
        A POI on reached floor without the models isn't with them.
    """
    from analyzer.traverse import WALLED_OFF, _door_strips, _faces_in_room

    agent = agent or AgentModel()
    low, high = agent.max_step_up, HEAD_HEIGHT
    if not placed or seed_face is None:
        return []
    kept, props, own = _in_room_graph(placed, spec)
    if not kept:
        return []
    names = {k: placed[k].name for k in kept}
    plo, phi = props.min(axis=1), props.max(axis=1)
    mlo, mhi = mesh.min(axis=1), mesh.max(axis=1)

    # The reached floor, sampled; the mesh's own walls read round each model.
    faces = np.array(sorted(int(f) for f in reached), dtype=np.int64)
    fs = floor_samples(surf.verts[surf.faces[faces]], faces, GATE_STEP)
    if len(fs) == 0:
        return []
    windows = []
    for k in kept:
        m = own == k
        a, b = plo[m].min(axis=0), phi[m].max(axis=0)
        windows.append((a[0] - ROOM_WINDOW, a[1] - ROOM_WINDOW, a[2] - HEAD_HEIGHT,
                        b[0] + ROOM_WINDOW, b[1] + ROOM_WINDOW, b[2] + HEAD_HEIGHT))
    windows = np.array(windows)
    near = mesh[_boxes_hit(mlo, mhi, windows)]
    walls = cover_samples(fs, near, np.zeros(len(near), np.int32), PLAYER_HALF_WIDTH, low, high)
    cov = cover_samples(fs, props, own, PLAYER_HALF_WIDTH, low, high)
    edges = _sample_edges(fs, agent.max_step_up)
    before = _sample_labels(len(fs), edges, ~walls.covered)
    after = _sample_labels(len(fs), edges, ~walls.covered & ~cov.covered)

    # The entrance: the free sample nearest the safe point on the seed face.
    safe = np.asarray(spec.safe_point, dtype=np.float64)
    on_seed = (fs.face == seed_face) & (before >= 0)
    if on_seed.any():
        s0 = _nearest(fs, on_seed, safe[0], safe[1], float(np.median(fs.z[on_seed])))
    else:
        seed_z = float(surf.centroids[seed_face, 2])
        s0 = _nearest(fs, before >= 0, safe[0], safe[1], seed_z)
    if s0 < 0:
        return []
    joined_before = before == before[s0]
    a0 = _nearest(fs, (after >= 0) & joined_before, fs.x[s0], fs.y[s0], fs.z[s0], POI_REACH)
    joined_after = (after == after[a0]) if a0 >= 0 else np.zeros(len(fs), bool)

    failures: List[GateFailure] = []

    # Footprint cut: reached floor the models cut off.
    cut = joined_before & ~cov.covered & ~joined_after
    if cut.any():
        ea, eb = edges
        hulls: Dict[int, np.ndarray] = {}
        for lab in np.unique(after[cut]):
            piece = cut & (after == lab)
            n = int(piece.sum())
            area = n * fs.step ** 2
            if area < WALLED_OFF:
                continue
            px, py = fs.x[piece], fs.y[piece]
            inside_one = False
            for k in kept:
                if k not in hulls:
                    pts = props[own == k][..., :2].reshape(-1, 2)
                    hulls[k] = _hull(pts) if len(pts) >= 3 else np.zeros((0, 2))
                if len(hulls[k]) >= 3 and _in_hull(hulls[k], px, py).all():
                    inside_one = True
                    break
            if inside_one:
                continue
            ring = np.r_[eb[piece[ea]], ea[piece[eb]]]
            who = sorted({names[o] for o in np.unique(cov.owner[ring]) if o >= 0})
            k0 = int(np.nonzero(piece)[0][0])
            x, y, z = float(fs.x[k0]), float(fs.y[k0]), float(fs.z[k0])
            first = next((placed[k] for k in kept if placed[k].name in who), None)
            room = _where(spec, first.x, first.y, first.z) if first else _where(spec, x, y, z)
            failures.append(GateFailure(
                "footprint_cut", tuple(who),
                f"cuts {area:.0f} u^2 of floor at ({x:.0f}, {y:.0f}, {z:.0f}) in "
                f"{_where(spec, x, y, z)} off from the entrance", where=room))

    # POIs: on reached floor without the models, so on it with them.
    def stands(mask, poi) -> bool:
        d = np.hypot(fs.x - poi.x, fs.y - poi.y)
        return bool((mask & (d <= POI_REACH) & (np.abs(fs.z - poi.z) <= agent.max_step_up)).any())

    for room in spec.rooms:
        for poi in room.pois:
            if stands(joined_before, poi) and not stands(joined_after, poi):
                failures.append(GateFailure(
                    "poi_unreached", (f"{poi.purpose}",),
                    f"the {poi.purpose} POI at ({poi.x:.0f}, {poi.y:.0f}, {poi.z:.0f}) "
                    f"is not on reached floor", where=room.id))

    # Clear width: each door's way to its room's Core, for a body CLEAR_WIDTH
    # wide. Only models near a door's way (its first DOOR_WAY u in, or its
    # Throat) can narrow it, so only rooms holding one are sampled.
    radius = CLEAR_WIDTH / 2 - ROOM_WIDE_STEP / math.sqrt(2.0)
    reach = radius + ROOM_WIDE_STEP
    for room in spec.rooms:
        (x0, y0, z0), (x1, y1, z1) = room.bounds
        extra = list(room.outline.extra_doors) if room.outline is not None else []
        doors = _door_strips(room, spec) + extra
        if not doors:
            continue
        zones = [_door_way(room, d, reach) for d in doors]
        throats = list(room.outline.throats) if room.outline is not None else []
        areas = zones + [(t[0] - reach, t[1] - reach, t[2] + reach, t[3] + reach) for t in throats]
        boxes = np.array([(a, b, z0 - 1.0, c, d, z1) for a, b, c, d in areas])
        grown = boxes + np.array([-radius, -radius, 0.0, radius, radius, 0.0])
        mine = _boxes_hit(plo, phi, grown)
        if not mine.any():
            continue
        rf = np.array([int(f) for f in _faces_in_room(surf, room, spec.rooms) if int(f) in reached],
                      dtype=np.int64)
        if not len(rf):
            continue
        rs = floor_samples(surf.verts[surf.faces[rf]], rf, ROOM_WIDE_STEP, (x0, y0, x1, y1))
        if not len(rs):
            continue
        # The room's walls round those models (far from them, nothing changes).
        win = np.r_[plo[mine].min(axis=0) - ROOM_WINDOW, phi[mine].max(axis=0) + ROOM_WINDOW]
        win[2], win[5] = z0 - HEAD_HEIGHT, z1 + HEAD_HEIGHT
        win = win.reshape(1, 6)
        rmesh = mesh[_boxes_hit(mlo, mhi, win)]
        rwalls = cover_samples(rs, rmesh, np.zeros(len(rmesh), np.int32), radius, low, high)
        rcov = cover_samples(rs, props[mine], own[mine], radius, low, high)
        redges = _sample_edges(rs, agent.max_step_up)
        wide_before = _sample_labels(len(rs), redges, ~rwalls.covered)
        wide_after = _sample_labels(len(rs), redges, ~rwalls.covered & ~rcov.covered)
        if room.outline is not None:
            c = room.outline.core
            core = ((c[0] + c[2]) / 2, (c[1] + c[3]) / 2)
        else:
            core = (room.center_x, room.center_y)
        cb = _nearest(rs, wide_before >= 0, core[0], core[1], z0)
        if cb < 0:
            continue
        ca = _nearest(rs, wide_after >= 0, core[0], core[1], z0)
        for (side, c0, c1), zone in zip(doors, zones):
            at = _in_doorway(rs, room, side, c0, c1, 1.5 * ROOM_WIDE_STEP)
            if not (at & (wide_before == wide_before[cb])).any():
                continue        # no way CLEAR_WIDTH wide without the models either
            if ca >= 0 and (at & (wide_after == wide_after[ca])).any():
                continue
            here = ((rs.x >= zone[0]) & (rs.x <= zone[2]) & (rs.y >= zone[1]) & (rs.y <= zone[3]))
            for t in throats:
                here |= (rs.x >= t[0]) & (rs.x <= t[2]) & (rs.y >= t[1]) & (rs.y <= t[3])
            lost = (wide_before >= 0) & rcov.covered & here
            who = sorted({names[o] for o in np.unique(rcov.owner[lost]) if o >= 0})
            failures.append(GateFailure(
                "throat_narrow", tuple(who),
                f"the way from door {side} {c0:.1f}..{c1:.1f} to the core is under the "
                f"{CLEAR_WIDTH:g} u clear width", where=room.id))
    return failures
