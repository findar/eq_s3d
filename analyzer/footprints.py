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
    POI it names (``subjects``), and where."""

    kind: str
    subjects: Tuple[str, ...]
    detail: str

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
