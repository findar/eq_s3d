"""
generators/mapgeom.py
---------------------
Outline extractor and depth bands: the walls and ledges of the walkable floor,
traced from the built TER mesh and the safe point (M2, roadmap step 1b).

The outline is the Floor_Boundary of the Floor_Region: the points on edges of
floor faces where the floor ends. A point is on it when the XY point a short
probe outside the face, across that edge, lies inside no Floor_Region face whose
plane height there is within the agent's step-up of the point. Welded seams,
T-junctions and overlapping corridor ends are therefore not boundary, and the
test is exact: each covering triangle contributes one closed interval of the
edge (Liang-Barsky against its three half-planes, trimmed by two linear height
conditions), so there is no sampling and no raster in the coverage.

Interior welded edges (an edge used by exactly one other region face lying on
its other side) are cancelled vectorised before any geometric test, so on a
terrain only the perimeter reaches the per-edge loop (design finding 6).

Design reference: ``.kiro/specs/zone-generator-m2-true-layout-artifacts/design.md``
("Outline extractor", "Depth bands", Algorithms, Decisions 1-3 and 7).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from analyzer.traverse import (
    AgentModel,
    WalkSurface,
    build_walk_surface,
    flood_reachable,
    seed_face_for,
)
from core.ter import FLAG_PASSABLE, TerFile

FLOOR_COS = math.cos(math.radians(40.0))      # = AgentModel().min_up_normal
WELD = 0.01                                   # vertex weld grid (u)
PROBE = 0.05                                  # outward probe distance (<= 0.1 by definition)
COLLINEAR_EPS = 0.02                          # max deviation when merging collinear runs
STACK_GAP = 12.0                              # 2 x player height
MAX_BANDS = 4
BAND_CELL = 8.0                               # depth-band raster cell (u)
MIN_SEGMENT = 0.01                            # shortest emitted segment (u)

# Output coordinates are rounded to this grid so the result depends on the
# coordinates alone, not on the ULP noise of the face/vertex order (Req 1.8).
_OUT_DECIMALS = 6
_EPS = 1e-9
# Height slack on the step-up test so a step of exactly ``max_step_up`` is not
# decided by the rounding of a plane evaluation.
_Z_TOL = 1e-6


class EmptyFloorRegion(Exception):
    """No Floor_Face is reachable from the safe point (or none exists)."""


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

Point3 = Tuple[float, float, float]


@dataclass(frozen=True)
class Polyline:
    points: Tuple[Point3, ...]   # world coords, >= 2, consecutive >= 0.01 u apart
    kind: str                    # "wall" | "ledge"
    band: int                    # DepthBand.index

    def __post_init__(self) -> None:
        if self.kind not in ("wall", "ledge"):
            raise ValueError(f"Polyline kind must be 'wall' or 'ledge', not {self.kind!r}")
        if len(self.points) < 2:
            raise ValueError("Polyline needs at least 2 points")
        for p, q in zip(self.points, self.points[1:]):
            if math.dist(p, q) < MIN_SEGMENT:
                raise ValueError(f"Polyline points {p} and {q} are closer than {MIN_SEGMENT}")

    @property
    def length(self) -> float:
        return sum(math.dist(p, q) for p, q in zip(self.points, self.points[1:]))


@dataclass(frozen=True)
class DepthBand:
    index: int            # 0 = Main_Band; others in ascending median floor Z order
    z_lo: float           # band height range (-inf/+inf at the ends)
    z_hi: float
    median_z: float       # area-weighted median floor Z of the band
    role: str             # "main" | "above" | "below"
    offset: int           # signed rank from the Main_Band (colour key)

    def contains(self, z: float) -> bool:
        """Half-open membership ``z_lo <= z < z_hi`` used to assign pieces."""
        return self.z_lo <= z < self.z_hi


@dataclass(frozen=True)
class OutlineSet:
    polylines: Tuple[Polyline, ...]
    bands: Tuple[DepthBand, ...]          # 1..4
    bounds: Tuple[float, float, float, float, float, float]   # Floor_Region bbox
    seed_face: int
    reachable_only: bool


@dataclass(frozen=True)
class FloorSet:
    """The Floor_Region as triangles: ``tris`` is (N, 3, 3) world positions."""
    tris: np.ndarray


# ---------------------------------------------------------------------------
# Mesh arrays
# ---------------------------------------------------------------------------

def _arrays(ter: TerFile) -> Tuple[np.ndarray, np.ndarray]:
    V = np.array([[v.x, v.y, v.z] for v in ter.vertices], dtype=np.float64).reshape(-1, 3)
    F = np.array([[p.v1, p.v2, p.v3] for p in ter.polygons], dtype=np.int64).reshape(-1, 3)
    return V, F


def _floor_mask(ter: TerFile, V: np.ndarray, F: np.ndarray) -> np.ndarray:
    if len(F) == 0:
        return np.zeros(0, bool)
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    n = np.cross(b - a, c - a)
    ln = np.linalg.norm(n, axis=1)
    ok = ln > 1e-9
    nz = np.zeros(len(F))
    nz[ok] = n[ok, 2] / ln[ok]
    passable = np.array([bool(p.flags & FLAG_PASSABLE) for p in ter.polygons], dtype=bool)
    # Signed rule (Decision 1): a face pointing DOWN (a box ceiling) is never
    # floor, whatever its |n_z|. Passable faces are walked through, not on.
    return ok & (nz >= FLOOR_COS) & ~passable


def floor_faces(ter: TerFile) -> np.ndarray:
    """Bool mask of Floor_Faces: signed unit normal ``n_z >= cos 40 deg``.

    Non-collidable (``FLAG_PASSABLE``) faces are excluded, as the walk surface
    excludes them: the client walks through them.
    """
    V, F = _arrays(ter)
    return _floor_mask(ter, V, F)


def _lexsorted_tris(T: np.ndarray) -> np.ndarray:
    """Each triangle's vertices in lexicographic (x, y, z) order, then turned
    counter-clockwise in XY. Makes every per-triangle computation independent of
    the face's vertex order (Req 1.8)."""
    out = T.copy()
    # Sort the 3 vertices of each triangle: a 3-element sorting network on
    # (x, y, z) tuples, vectorised.
    def _less(p, q):
        return ((p[:, 0] < q[:, 0])
                | ((p[:, 0] == q[:, 0]) & (p[:, 1] < q[:, 1]))
                | ((p[:, 0] == q[:, 0]) & (p[:, 1] == q[:, 1]) & (p[:, 2] < q[:, 2])))

    def _cswap(i, j):
        sw = _less(out[:, j], out[:, i])
        tmp = out[sw, i].copy()
        out[sw, i] = out[sw, j]
        out[sw, j] = tmp

    _cswap(0, 1)
    _cswap(1, 2)
    _cswap(0, 1)
    e1 = out[:, 1, :2] - out[:, 0, :2]
    e2 = out[:, 2, :2] - out[:, 0, :2]
    cw = (e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) < 0
    tmp = out[cw, 1].copy()
    out[cw, 1] = out[cw, 2]
    out[cw, 2] = tmp
    return out


# ---------------------------------------------------------------------------
# Step 2: weld + vectorised interior-edge cancellation
# ---------------------------------------------------------------------------

def _candidate_edges(V: np.ndarray, F: np.ndarray, region: np.ndarray):
    """Region face edges that are NOT a welded interior seam.

    Returns ``(face, a, b, c)`` vertex-index arrays: the edge ``a-b`` of
    ``face`` and its third vertex ``c``.
    """
    q = np.round(V / WELD).astype(np.int64)
    _, W = np.unique(q, axis=0, return_inverse=True)
    W = W.reshape(-1)
    R = np.nonzero(region)[0]
    FR = F[R]
    ea = FR[:, [0, 1, 2]].reshape(-1)
    eb = FR[:, [1, 2, 0]].reshape(-1)
    ec = FR[:, [2, 0, 1]].reshape(-1)
    ef = np.repeat(R, 3)
    wa, wb = W[ea], W[eb]
    keep = wa != wb                                  # drop sub-weld edges
    ea, eb, ec, ef, wa, wb = ea[keep], eb[keep], ec[keep], ef[keep], wa[keep], wb[keep]
    if len(ea) == 0:
        return ef, ea, eb, ec

    # Orient each edge by welded id so both faces of a seam see one direction,
    # then the third vertex's side of it (XY cross sign).
    swap = wa > wb
    lo_v = np.where(swap, eb, ea)
    hi_v = np.where(swap, ea, eb)
    P, Q, C = V[lo_v], V[hi_v], V[ec]
    side = np.sign((Q[:, 0] - P[:, 0]) * (C[:, 1] - P[:, 1])
                   - (Q[:, 1] - P[:, 1]) * (C[:, 0] - P[:, 0]))
    nW = int(W.max()) + 1
    key = np.minimum(wa, wb) * nW + np.maximum(wa, wb)
    order = np.argsort(key, kind="stable")
    sk = key[order]
    _, start, counts = np.unique(sk, return_index=True, return_counts=True)
    pair_start = start[counts == 2]
    i0, i1 = order[pair_start], order[pair_start + 1]
    interior = side[i0] * side[i1] < 0               # the two faces on opposite sides
    cancel = np.zeros(len(ea), bool)
    cancel[i0[interior]] = True
    cancel[i1[interior]] = True
    k = ~cancel
    return ef[k], ea[k], eb[k], ec[k]


# ---------------------------------------------------------------------------
# Step 3: exact interval coverage
# ---------------------------------------------------------------------------

def _lex_less_rows(P: np.ndarray, Q: np.ndarray) -> np.ndarray:
    return ((P[:, 0] < Q[:, 0])
            | ((P[:, 0] == Q[:, 0]) & (P[:, 1] < Q[:, 1]))
            | ((P[:, 0] == Q[:, 0]) & (P[:, 1] == Q[:, 1]) & (P[:, 2] < Q[:, 2])))


def _coverage_intervals(A, B, out, Tg, step):
    """Closed ``t`` interval per (edge, triangle) pair where the probe
    ``A + t(B - A) + PROBE*out`` lies in triangle ``Tg``'s XY closure with the
    triangle's plane within ``step`` of the edge height. Arrays are aligned
    pair-wise; returns ``(lo, hi)`` with ``lo > hi`` meaning empty."""
    P0 = A[:, :2] + PROBE * out
    D = B[:, :2] - A[:, :2]
    n = len(A)
    lo = np.zeros(n)
    hi = np.ones(n)
    empty = np.zeros(n, bool)

    def _apply(alpha, beta):
        nonlocal lo, hi, empty
        scale = np.maximum(1.0, np.abs(alpha) + np.abs(beta))
        tol = 1e-12 * scale
        pos = beta > tol
        neg = beta < -tol
        zer = ~(pos | neg)
        with np.errstate(divide="ignore", invalid="ignore"):
            r = -alpha / np.where(zer, 1.0, beta)
        lo = np.where(pos, np.maximum(lo, r), lo)
        hi = np.where(neg, np.minimum(hi, r), hi)
        empty |= zer & (alpha < -tol)

    for i, j in ((0, 1), (1, 2), (2, 0)):
        Ti = Tg[:, i, :2]
        E = Tg[:, j, :2] - Ti
        R0 = P0 - Ti
        alpha = E[:, 0] * R0[:, 1] - E[:, 1] * R0[:, 0]
        beta = E[:, 0] * D[:, 1] - E[:, 1] * D[:, 0]
        _apply(alpha, beta)

    # Plane height of Tg along the probe, minus the edge height: h0 + h1*t.
    T0 = Tg[:, 0]
    nrm = np.cross(Tg[:, 1] - T0, Tg[:, 2] - T0)
    gx = -nrm[:, 0] / nrm[:, 2]
    gy = -nrm[:, 1] / nrm[:, 2]
    h0 = T0[:, 2] + gx * (P0[:, 0] - T0[:, 0]) + gy * (P0[:, 1] - T0[:, 1]) - A[:, 2]
    h1 = gx * D[:, 0] + gy * D[:, 1] - (B[:, 2] - A[:, 2])
    _apply(step - h0, -h1)
    _apply(step + h0, h1)
    lo = np.where(empty, 1.0, lo)
    hi = np.where(empty, 0.0, hi)
    return lo, hi


def _boundary_pieces(V, F, region, step) -> List[Tuple[np.ndarray, np.ndarray]]:
    """The Floor_Boundary as 3D segments ``(P, Q)`` (exact, unmerged)."""
    ef, ea, eb, ec = _candidate_edges(V, F, region)
    if len(ef) == 0:
        return []
    A, B, C = V[ea], V[eb], V[ec]
    # Canonical edge direction: lexicographically smaller endpoint first.
    sw = _lex_less_rows(B, A)
    A, B = np.where(sw[:, None], B, A), np.where(sw[:, None], A, B)
    d = B[:, :2] - A[:, :2]
    out = np.stack([d[:, 1], -d[:, 0]], axis=1)
    ln = np.linalg.norm(out, axis=1)
    good = ln > 1e-12
    A, B, C, ef, out, ln = A[good], B[good], C[good], ef[good], out[good], ln[good]
    out = out / ln[:, None]
    flip = ((C[:, 0] - A[:, 0]) * out[:, 0] + (C[:, 1] - A[:, 1]) * out[:, 1]) > 0
    out[flip] *= -1.0

    R = np.nonzero(region)[0]
    Tg_all = _lexsorted_tris(V[F[R]])
    gmin = Tg_all[:, :, :2].min(axis=1)
    gmax = Tg_all[:, :, :2].max(axis=1)
    P0 = A[:, :2] + PROBE * out
    P1 = B[:, :2] + PROBE * out
    pmin = np.minimum(P0, P1) - 1e-9
    pmax = np.maximum(P0, P1) + 1e-9

    pairs_e: List[np.ndarray] = []
    pairs_g: List[np.ndarray] = []
    chunk = max(1, 4_000_000 // max(1, len(R)))
    for s in range(0, len(A), chunk):
        e = slice(s, s + chunk)
        hit = ((gmin[None, :, 0] <= pmax[e, None, 0]) & (gmax[None, :, 0] >= pmin[e, None, 0])
               & (gmin[None, :, 1] <= pmax[e, None, 1]) & (gmax[None, :, 1] >= pmin[e, None, 1]))
        ii, gg = np.nonzero(hit)
        pairs_e.append(ii + s)
        pairs_g.append(gg)
    pe = np.concatenate(pairs_e)
    pg = np.concatenate(pairs_g)
    own = R[pg] == ef[pe]
    pe, pg = pe[~own], pg[~own]
    lo, hi = _coverage_intervals(A[pe], B[pe], out[pe], Tg_all[pg], step)
    keep = hi > lo
    pe, lo, hi = pe[keep], lo[keep], hi[keep]
    order = np.lexsort((lo, pe))
    pe, lo, hi = pe[order], lo[order], hi[order]
    starts = np.searchsorted(pe, np.arange(len(A)), side="left")
    ends = np.searchsorted(pe, np.arange(len(A)), side="right")

    pieces: List[Tuple[np.ndarray, np.ndarray]] = []
    elen = np.linalg.norm(B - A, axis=1)
    for k in range(len(A)):
        free: List[Tuple[float, float]] = []
        cur = 0.0
        for j in range(starts[k], ends[k]):
            if lo[j] > cur:
                free.append((cur, float(lo[j])))
            cur = max(cur, float(hi[j]))
            if cur >= 1.0:
                break
        if cur < 1.0:
            free.append((cur, 1.0))
        for t0, t1 in free:
            if (t1 - t0) * elen[k] <= _EPS:
                continue
            P = A[k] + t0 * (B[k] - A[k]) if t0 > 0.0 else A[k].copy()
            Q = A[k] + t1 * (B[k] - A[k]) if t1 < 1.0 else B[k].copy()
            pieces.append((P, Q))
    return pieces


# ---------------------------------------------------------------------------
# Supporting-line grouping (dedupe overlapping collinear pieces)
# ---------------------------------------------------------------------------

def _line_key(P: np.ndarray, Q: np.ndarray):
    d = Q - P
    d = d / np.linalg.norm(d)
    off = P - np.dot(P, d) * d
    return (tuple(np.round(d * 1e4).astype(np.int64).tolist()),
            tuple(np.round(off / WELD).astype(np.int64).tolist())), d


def _merge_collinear_pieces(pieces):
    """Union overlapping pieces on one supporting line (an overlapping corridor
    end and the room floor both contribute the same boundary). Pieces that only
    touch end to end stay separate so their junction survives."""
    groups: Dict[tuple, list] = {}
    for P, Q in pieces:
        if _lex_less_rows(Q[None], P[None])[0]:
            P, Q = Q, P
        key, d = _line_key(P, Q)
        groups.setdefault(key, []).append((P, Q))
    merged = []
    for key in sorted(groups):
        items = groups[key]
        d = np.array(key[0], float)
        d = d / np.linalg.norm(d)
        rows = sorted(((float(np.dot(P, d)), float(np.dot(Q, d)),
                        tuple(P.tolist()), tuple(Q.tolist())) for P, Q in items))
        cur = None
        for s0, s1, P, Q in rows:
            if cur is not None and s0 < cur[1] - _EPS:
                if s1 > cur[1]:
                    cur = [cur[0], s1, cur[2], Q]
                continue
            if cur is not None:
                merged.append((np.array(cur[2]), np.array(cur[3])))
            cur = [s0, s1, P, Q]
        if cur is not None:
            merged.append((np.array(cur[2]), np.array(cur[3])))
    return merged


# ---------------------------------------------------------------------------
# Step 4: wall / ledge classification
# ---------------------------------------------------------------------------

def _classify(pieces, V, F, nonfloor):
    """Split each piece into ``(P, Q, kind)``: ``wall`` where a non-floor face
    has an edge collinear with it (within WELD), overlapping it, and a vertex
    more than WELD above it; ``ledge`` elsewhere."""
    NF = np.nonzero(nonfloor)[0]
    if len(NF):
        T = V[F[NF]]
        EA = T[:, [0, 1, 2]].reshape(-1, 3)
        EB = T[:, [1, 2, 0]].reshape(-1, 3)
        top = np.repeat(T[:, :, 2].max(axis=1), 3)
        emin = np.minimum(EA, EB) - WELD
        emax = np.maximum(EA, EB) + WELD
    out = []
    for P, Q in pieces:
        L = float(np.linalg.norm(Q - P))
        walls: List[Tuple[float, float]] = []
        if len(NF):
            pmin = np.minimum(P, Q)
            pmax = np.maximum(P, Q)
            near = np.nonzero(np.all(emin <= pmax, axis=1) & np.all(emax >= pmin, axis=1)
                              & (top > max(P[2], Q[2]) + WELD))[0]
            if len(near):
                d = (Q - P) / L
                ra = EA[near] - P
                rb = EB[near] - P
                sa = ra @ d
                sb = rb @ d
                da = np.linalg.norm(ra - sa[:, None] * d, axis=1)
                db = np.linalg.norm(rb - sb[:, None] * d, axis=1)
                ok = (da <= WELD) & (db <= WELD)
                s0 = np.maximum(np.minimum(sa, sb), 0.0)
                s1 = np.minimum(np.maximum(sa, sb), L)
                ok &= (s1 - s0) > _EPS
                walls = sorted(zip((s0[ok] / L).tolist(), (s1[ok] / L).tolist()))
        cuts: List[Tuple[float, float, str]] = []
        cur = 0.0
        for a, b in walls:
            if a > cur:
                cuts.append((cur, a, "ledge"))
                cuts.append((a, b, "wall"))
            elif b > cur:
                cuts.append((cur, b, "wall"))
            cur = max(cur, b)
        if cur < 1.0:
            cuts.append((cur, 1.0, "ledge"))
        for t0, t1, kind in cuts:
            if t1 - t0 <= 0:
                continue
            a = P if t0 == 0.0 else P + t0 * (Q - P)
            b = Q if t1 == 1.0 else P + t1 * (Q - P)
            out.append((a, b, kind))
    return out


# ---------------------------------------------------------------------------
# Depth bands
# ---------------------------------------------------------------------------

def _points_in_tris(pts: np.ndarray, T: np.ndarray):
    """All (point, triangle) pairs with the point in the triangle's XY closure,
    via an 8 u cell bin. Returns ``(pi, ti, z)`` with ``z`` the plane height."""
    if len(pts) == 0 or len(T) == 0:
        return np.zeros(0, np.int64), np.zeros(0, np.int64), np.zeros(0)
    pc = np.floor(pts[:, :2] / BAND_CELL).astype(np.int64)
    tmin = np.floor(T[:, :, :2].min(axis=1) / BAND_CELL).astype(np.int64)
    tmax = np.floor(T[:, :, :2].max(axis=1) / BAND_CELL).astype(np.int64)
    base = np.minimum(pc.min(axis=0), tmin.min(axis=0))
    span = np.maximum(pc.max(axis=0), tmax.max(axis=0)) - base + 1
    pid = (pc[:, 0] - base[0]) * span[1] + (pc[:, 1] - base[1])
    porder = np.argsort(pid, kind="stable")
    spid = pid[porder]
    nx = tmax[:, 0] - tmin[:, 0] + 1
    ny = tmax[:, 1] - tmin[:, 1] + 1
    cnt = nx * ny
    ti = np.repeat(np.arange(len(T)), cnt)
    k = np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)
    cx = tmin[ti, 0] + k // ny[ti]
    cy = tmin[ti, 1] + k % ny[ti]
    cid = (cx - base[0]) * span[1] + (cy - base[1])
    s = np.searchsorted(spid, cid, side="left")
    e = np.searchsorted(spid, cid, side="right")
    m = e - s
    ti2 = np.repeat(ti, m)
    off = np.arange(m.sum()) - np.repeat(np.cumsum(m) - m, m)
    pi2 = porder[np.repeat(s, m) + off]
    tri = T[ti2]
    p = pts[pi2]
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    det = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    okd = np.abs(det) > 1e-12
    det = np.where(okd, det, 1.0)
    l1 = ((b[:, 1] - c[:, 1]) * (p[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (p[:, 1] - c[:, 1])) / det
    l2 = ((c[:, 1] - a[:, 1]) * (p[:, 0] - c[:, 0]) + (a[:, 0] - c[:, 0]) * (p[:, 1] - c[:, 1])) / det
    l3 = 1.0 - l1 - l2
    tol = -1e-9
    inside = okd & (l1 >= tol) & (l2 >= tol) & (l3 >= tol)
    # Plane height by slopes, not barycentric weights: exact on a flat face.
    n = np.cross(b - a, c - a)
    nz = np.where(np.abs(n[:, 2]) > 1e-12, n[:, 2], 1.0)
    z = a[:, 2] - (n[:, 0] * (p[:, 0] - a[:, 0]) + n[:, 1] * (p[:, 1] - a[:, 1])) / nz
    return pi2[inside], ti2[inside], z[inside]


def _stack_intervals(tris: np.ndarray) -> np.ndarray:
    """Every ``(z_lo, z_hi)`` of a floor height and the nearest height above it
    more than STACK_GAP higher, at the 8 u cell centres and at the centroids of
    faces too small to cover a centre. Not only CONSECUTIVE heights: floors at
    0, 12 and 24 have no consecutive gap over 12 yet 0 and 24 are stacked; the
    nearest-above interval from each height is contained in every wider one,
    so stabbing these stabs every stacked pair."""
    cmin = np.floor(tris[:, :, :2].min(axis=1) / BAND_CELL - 0.5).astype(np.int64)
    cmax = np.floor(tris[:, :, :2].max(axis=1) / BAND_CELL - 0.5).astype(np.int64) + 1
    nx = cmax[:, 0] - cmin[:, 0] + 1
    ny = cmax[:, 1] - cmin[:, 1] + 1
    cnt = nx * ny
    fi = np.repeat(np.arange(len(tris)), cnt)
    k = np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)
    cells = np.stack([cmin[fi, 0] + k // ny[fi], cmin[fi, 1] + k % ny[fi]], axis=1)
    cells = np.unique(cells, axis=0)
    centres = (cells + 0.5) * BAND_CELL
    centres = np.concatenate([centres, np.zeros((len(centres), 1))], axis=1)
    pi, ti, z = _points_in_tris(centres, tris)
    covered = np.zeros(len(tris), bool)
    covered[ti] = True
    small = np.nonzero(~covered)[0]
    if len(small):
        cen = tris[small].mean(axis=1)
        pj, tj, zj = _points_in_tris(cen, tris)
        pi = np.concatenate([pi, pj + len(centres)])
        z = np.concatenate([z, zj])
    if len(z) == 0:
        return np.zeros((0, 2))
    order = np.lexsort((z, pi))
    pi, z = pi[order], z[order]
    zmin = float(z.min())
    K = float(z.max() - zmin) + 2.0 * STACK_GAP + 1.0
    comp = pi.astype(np.float64) * K + (z - zmin)
    j = np.searchsorted(comp, comp + STACK_GAP, side="right")
    ok = j < len(z)
    jj = np.where(ok, j, 0)
    ok &= pi[jj] == pi
    iv = np.stack([z[ok], z[jj[ok]]], axis=1)
    return np.unique(iv, axis=0) if len(iv) else np.zeros((0, 2))


def _stab(intervals: np.ndarray) -> List[float]:
    """Fewest cut heights so every open interval ``(lo, hi)`` holds one."""
    ivs = sorted((float(h), float(l)) for l, h in intervals)
    cuts: List[float] = []
    for i, (hi, lo) in enumerate(ivs):
        if cuts and lo < cuts[-1]:
            continue
        group_lo = max(l for h, l in ivs[i:] if l < hi)
        # On the output grid, so a polyline split at the cut lands exactly on it.
        cuts.append(round((group_lo + hi) / 2.0, _OUT_DECIMALS))
    return cuts


def _band_extents(zr: np.ndarray, slabs: List[Tuple[float, float]]):
    """Min/max floor Z per slab ``[lo, hi)`` from face z-ranges clipped into it."""
    ext = []
    for lo, hi in slabs:
        m = (zr[:, 0] < hi) & (zr[:, 1] >= lo)
        if not m.any():
            ext.append((math.nan, math.nan))
            continue
        ext.append((float(np.maximum(zr[m, 0], lo).min()),
                    float(np.minimum(zr[m, 1], hi).max())))
    return ext


def _weighted_median(z: np.ndarray, w: np.ndarray) -> float:
    order = np.lexsort((w, z))
    z, w = z[order], w[order]
    cw = np.cumsum(w)
    if cw[-1] <= 0:
        return float(np.median(z))
    return float(z[int(np.searchsorted(cw, cw[-1] / 2.0, side="left"))])


def depth_bands(floor: FloorSet, safe_z: float,
                max_bands: int = MAX_BANDS) -> List[DepthBand]:
    """Split the Floor_Region into at most ``max_bands`` height bands so the two
    floors of every stacked pair (XY overlap, more than STACK_GAP apart) fall in
    different bands (Req 2, Decision 7)."""
    tris = np.asarray(floor.tris, dtype=np.float64).reshape(-1, 3, 3)
    if len(tris) == 0:
        return [DepthBand(0, -math.inf, math.inf, float(safe_z), "main", 0)]
    cuts = _stab(_stack_intervals(tris))
    bounds = [-math.inf] + cuts + [math.inf]
    slabs = list(zip(bounds[:-1], bounds[1:]))
    zr = np.stack([tris[:, :, 2].min(axis=1), tris[:, :, 2].max(axis=1)], axis=1)
    ext = _band_extents(zr, slabs)
    while len(slabs) > max_bands:
        gaps = [ext[i + 1][0] - ext[i][1] for i in range(len(slabs) - 1)]
        i = int(np.argmin(gaps))                    # ties go to the lower pair
        slabs[i:i + 2] = [(slabs[i][0], slabs[i + 1][1])]
        ext[i:i + 2] = [(min(ext[i][0], ext[i + 1][0]), max(ext[i][1], ext[i + 1][1]))]

    cz = tris[:, :, 2].mean(axis=1)
    e1 = tris[:, 1, :2] - tris[:, 0, :2]
    e2 = tris[:, 2, :2] - tris[:, 0, :2]
    area = 0.5 * np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0])
    medians = []
    for (lo, hi), (zmin, zmax) in zip(slabs, ext):
        m = (cz >= lo) & (cz < hi)
        if m.any():
            medians.append(_weighted_median(cz[m], area[m]))
        else:
            medians.append((zmin + zmax) / 2.0)
    main = next(i for i, (lo, hi) in enumerate(slabs) if lo <= safe_z < hi)
    others = sorted((i for i in range(len(slabs)) if i != main),
                    key=lambda i: (medians[i], slabs[i][0]))
    index = {main: 0}
    for k, i in enumerate(others, start=1):
        index[i] = k
    bands = []
    for i, (lo, hi) in enumerate(slabs):
        role = "main" if i == main else ("above" if i > main else "below")
        bands.append(DepthBand(index[i], lo, hi, medians[i], role, i - main))
    return sorted(bands, key=lambda b: b.index)


# ---------------------------------------------------------------------------
# Steps 5-7: band split, chaining, simplification, canonical order
# ---------------------------------------------------------------------------

def _split_at_cuts(pieces, cuts: Sequence[float]):
    out = []
    for P, Q, kind in pieces:
        ts = []
        if P[2] != Q[2]:
            for c in cuts:
                if min(P[2], Q[2]) < c < max(P[2], Q[2]):
                    ts.append((c - P[2]) / (Q[2] - P[2]))
        ts = [0.0] + sorted(ts) + [1.0]
        for t0, t1 in zip(ts[:-1], ts[1:]):
            a = P if t0 == 0.0 else P + t0 * (Q - P)
            b = Q if t1 == 1.0 else P + t1 * (Q - P)
            out.append((a, b, kind))
    return out


def _key(p) -> Tuple[int, int, int]:
    return tuple(int(v) for v in np.round(np.asarray(p) / WELD))


def _rnd(p) -> Point3:
    return tuple(float(round(float(v), _OUT_DECIMALS)) + 0.0 for v in p)


def _chain(segs):
    """Maximal paths through welded endpoints of degree 2 with one kind and
    band; breaks at junctions, class changes and band changes."""
    node_pt: Dict[tuple, Point3] = {}
    inc: Dict[tuple, List[int]] = {}
    S = []
    for P, Q, kind, band in segs:
        kp, kq = _key(P), _key(Q)
        if kp == kq:
            continue
        for k, p in ((kp, _rnd(P)), (kq, _rnd(Q))):
            if k not in node_pt or p < node_pt[k]:
                node_pt[k] = p
        S.append((kp, kq, kind, band))
    for i, (kp, kq, _, _) in enumerate(S):
        inc.setdefault(kp, []).append(i)
        inc.setdefault(kq, []).append(i)

    def through(node) -> bool:
        lst = inc[node]
        return (len(lst) == 2 and lst[0] != lst[1]
                and S[lst[0]][2:] == S[lst[1]][2:])

    used = [False] * len(S)
    chains = []

    def walk(start, si):
        nodes = [start]
        node = start
        while True:
            used[si] = True
            kp, kq = S[si][0], S[si][1]
            node = kq if node == kp else kp
            nodes.append(node)
            if not through(node):
                break
            nxt = [j for j in inc[node] if not used[j]]
            if not nxt:
                break
            si = nxt[0]
        return nodes

    for node in sorted(inc):
        if through(node):
            continue
        for si in sorted(inc[node]):
            if not used[si]:
                chains.append(([node_pt[n] for n in walk(node, si)], S[si][2], S[si][3]))
    for si in range(len(S)):                         # leftover closed loops
        if not used[si]:
            start = min(S[si][0], S[si][1])
            kind, band = S[si][2], S[si][3]
            chains.append(([node_pt[n] for n in walk(start, si)], kind, band))
    return chains


def _canonical_points(pts: List[Point3]) -> List[Point3]:
    if len(pts) > 2 and pts[0] == pts[-1]:           # closed loop
        ring = pts[:-1]
        i = min(range(len(ring)), key=lambda k: ring[k])
        ring = ring[i:] + ring[:i]
        if len(ring) > 2 and ring[-1] < ring[1]:
            ring = [ring[0]] + ring[1:][::-1]
        return ring + [ring[0]]
    return pts if pts[0] <= pts[-1] else pts[::-1]


def _seg_dist(p, a, b) -> float:
    p, a, b = np.asarray(p), np.asarray(a), np.asarray(b)
    ab = b - a
    L2 = float(ab @ ab)
    if L2 == 0.0:
        return float(np.linalg.norm(p - a))
    t = min(1.0, max(0.0, float((p - a) @ ab) / L2))
    return float(np.linalg.norm(p - (a + t * ab)))


def _simplify(pts: List[Point3]) -> List[Point3]:
    """Merge collinear runs (every dropped vertex within COLLINEAR_EPS of the
    merged segment), then drop vertices closer than MIN_SEGMENT."""
    out = [pts[0]]
    i = 0
    while i < len(pts) - 1:
        j = i + 1
        while j + 1 < len(pts) and all(
                _seg_dist(pts[k], pts[i], pts[j + 1]) <= COLLINEAR_EPS
                for k in range(i + 1, j + 1)):
            j += 1
        out.append(pts[j])
        i = j
    res = [out[0]]
    for p in out[1:-1]:
        if math.dist(p, res[-1]) >= MIN_SEGMENT:
            res.append(p)
    last = out[-1]
    while len(res) > 1 and math.dist(res[-1], last) < MIN_SEGMENT:
        res.pop()
    if math.dist(res[-1], last) >= MIN_SEGMENT:
        res.append(last)
    return res


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def _plane_z(tri: np.ndarray, x: float, y: float) -> float:
    n = np.cross(tri[1] - tri[0], tri[2] - tri[0])
    if abs(n[2]) < 1e-12:
        return float(tri[:, 2].mean())
    return float(tri[0, 2] - (n[0] * (x - tri[0, 0]) + n[1] * (y - tri[0, 1])) / n[2])


def extract_outline(ter: TerFile, safe_point: Tuple[float, float, float],
                    agent: Optional[AgentModel] = None, *,
                    reachable_only: bool = True,
                    surface: Optional[WalkSurface] = None) -> OutlineSet:
    """Trace the walls and ledges of the walkable floor (Req 1, 2).

    ``surface`` is the walk surface the validator already built for this TER
    and agent; when ``None`` it is built here. Raises ``EmptyFloorRegion`` when
    no Floor_Face is reachable from the safe point.
    """
    agent = agent or AgentModel()
    V, F = _arrays(ter)
    floor = _floor_mask(ter, V, F)
    surf = surface if surface is not None else build_walk_surface(ter, agent)
    seed = seed_face_for(surf, safe_point)
    if seed is None:
        raise EmptyFloorRegion("the mesh has no standable face")
    if reachable_only:
        reach = np.zeros(len(F), bool)
        reached = np.fromiter(flood_reachable(surf, seed), dtype=np.int64)
        reach[reached] = True
        region = floor & reach
    else:
        region = floor
    if not region.any():
        raise EmptyFloorRegion("no floor face reachable from the safe point")

    pieces = _boundary_pieces(V, F, region, agent.max_step_up + _Z_TOL)
    pieces = _merge_collinear_pieces(pieces)
    nonfloor = ~floor
    nonfloor &= np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]),
                               axis=1) > 1e-9
    pieces = _classify(pieces, V, F, nonfloor)

    tris = V[F[region]]
    safe_z = _plane_z(V[F[seed]], float(safe_point[0]), float(safe_point[1]))
    bands = depth_bands(FloorSet(tris), safe_z)
    ordered = sorted(bands, key=lambda b: b.offset)
    cuts = [b.z_lo for b in ordered[1:]]
    pieces = _split_at_cuts(pieces, cuts)
    segs = []
    for P, Q, kind in pieces:
        mz = (P[2] + Q[2]) / 2.0
        band = next(b.index for b in bands if b.contains(mz))
        segs.append((P, Q, kind, band))

    polylines = []
    for pts, kind, band in _chain(segs):
        pts = _canonical_points(pts)
        pts = _simplify(pts)
        if len(pts) < 2:
            continue
        polylines.append(Polyline(tuple(pts), kind, band))
    polylines.sort(key=lambda p: (p.band, p.kind, p.points[0], p.length, p.points))

    vr = tris.reshape(-1, 3)
    lo, hi = vr.min(axis=0), vr.max(axis=0)
    bounds = tuple(float(v) for v in (*lo, *hi))
    return OutlineSet(tuple(polylines), tuple(bands), bounds, int(seed), reachable_only)


def outline_summary(outline: OutlineSet) -> dict:
    """The Sidecar ``outline`` block (the Pipeline adds each band's ``file``)."""
    def _num(v: float):
        return None if math.isinf(v) else float(v)

    bands = []
    for b in sorted(outline.bands, key=lambda b: b.index):
        mine = [p for p in outline.polylines if p.band == b.index]
        bands.append({
            "index": b.index,
            "role": b.role,
            "z_lo": _num(b.z_lo),
            "z_hi": _num(b.z_hi),
            "median_z": float(b.median_z),
            "walls": sum(1 for p in mine if p.kind == "wall"),
            "ledges": sum(1 for p in mine if p.kind == "ledge"),
        })
    return {
        "reachable_only": outline.reachable_only,
        "bounds": [float(v) for v in outline.bounds],
        "bands": bands,
    }
