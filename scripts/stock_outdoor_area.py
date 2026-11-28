r"""Stock outdoor zones: extent, the interiors they hold, and the ways in (step 35, task 1).

Reads each Classic-PoP outdoor zone's WLD mesh (``outdoor_dungeon_survey.load_mesh``) and
walks it with the traversal agent's rules (slope <= 40 deg, step <= 3 u). The **walked
ground** is the largest walkable network by face count (the stock safe point is in the
server's database, not the client files). The step 5 and step 10 surveys take the largest
by area, which in some outdoor zones is a flat sheet of a few big faces laid under the
whole map. Walked floor whose first surface above faces the ground (the terrain's own
single-sided top, no ceiling between) lies under the map and is dropped.

**Extent**, per zone: the walked ground's plan bounding box, width (the longer side) by
depth (the shorter), aspect = width / depth, and its plan area (``PLAN`` u cells). The
whole mesh's box is printed beside it. Pooled p10/p50/p90/max over the zones, per group
(``wild``: open land; ``odun``: the outdoor dungeons, a ruin or castle in open land).
A zone whose walked ground is more than ``MAX_COVERED`` under a roof is not outdoor and
is left out of the bands, and so is one whose walked width is under ``MIN_FILL`` of its
mesh's (water or islands split the network: oot, erudsxing...). Both are named.

**Interiors**: walked floor with a ceiling 8-250 u above it is *covered*
(``outdoor_dungeon_survey``'s test, here on an exact ``CELL`` u raster of every solid
non-vertical surface, and the first surface above must face down: a WLD zone's terrain
is single-sided, so ground over ground is not a roof). A connected covered region is an interior when its plan area is
at least ``MIN_AREA`` u^2 AND some of its floor lies at least ``MIN_REACH`` u walk from
open floor; that drops bridges, arches and overhangs (long but shallow). Per interior:

- *footprint*: plan box and area; *reach*: the farthest walk from the way in (u);
  *drop*: how far its floor goes below the way in's floor (u), *rise*: above it.
- *built* or *rock*: the Axis_Share of the walls standing in its footprint (step 8's
  ``wall_survey`` measure: the share of wall area square to the main grid). Built when
  at least ``BUILT_AXIS``. The flat floor share and the roof thickness (top surface less
  the ceiling, p50) are printed as checks, not used: Classic caves have flat floors
  (steamfont's minotaur caves are all level), and a ruin dug into a hill has a thick roof.
- *zoneline*: a zoneline region (``DRNTP``) inside it: the interior is the way out to
  another zone (a dungeon's entrance tunnel), not a place in this one.
- *host*: the landform it sits in. The top surface (highest solid surface per cell) is
  thresholded at ``HOST_RISE`` u over the main way in's floor; the host is the connected
  high ground over the interior's footprint. Its box, height (top less that floor),
  whether it runs to the mesh's edge (``edge``: the interior is dug into the zone's
  boundary mountains, so it has no size of its own), and the *margin*: how far the
  footprint's cells sit from the host's edge, p10 and p50 (u).

**Ways in**: open walked floor stepping straight onto an interior. The contact edges are
clustered ``GAP`` u apart; each cluster is one way in. *width*: the extent of the contact's points (shared vertices and pair midpoints)
along its principal axis (u); it reads up to about a face short. Then its kind, by rules on numbers printed beside it:

- *wall*: the share of 16 rays from the way in (32-240 u) that meet top ground at least
  ``WALL_RISE`` u over its floor; *sunk*: the open walked ground 100-250 u away (p50)
  less the way in's floor (positive = the approach lies in a hollow); *lip*: the top
  surface 24 u inside, over the floor (the face above the opening).
- built: ``ruin stairs`` when its floor drops ``STAIR_DROP`` u or more below the way in,
  else ``door`` (a level doorway into a building).
- rock: ``sinkhole`` when sunk >= ``SUNK`` and wall >= 0.75; ``ravine`` when sunk >=
  ``SUNK`` and wall >= 0.4; ``cliff opening`` when lip >= ``CLIFF_LIP``; else ``mouth``.
- ``well`` (a shaft) is never drawn: the agent can't walk down a shaft, so an interior
  entered only by one is not on the walked network and this survey can't see it.

Ways in narrower than ``MIN_WAY`` u (single shared vertices, seams) are dropped.

``--plots DIR``: each zone with interiors, walked ground grey, covered floor dark, host
outlined, ways in marked with their kind. Plots stay out of git (zone geometry).
``--cache DIR`` keeps each zone's walk surface (``build_walk_surface`` is the slow part).

Usage::

    python scripts/stock_outdoor_area.py --eq-path F:\everquest_rof2 --cache %TEMP%\soa
    python scripts/stock_outdoor_area.py --eq-path F:\everquest_rof2 --zones steamfont \
        --plots %TEMP%\soa_plots --cache %TEMP%\soa
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from analyzer.traverse import AgentModel, build_walk_surface  # noqa: E402
from core.ter import FLAG_PASSABLE  # noqa: E402
from outdoor_dungeon_survey import load_mesh  # noqa: E402
from site_survey import region_of, regions  # noqa: E402
from wall_survey import AXIS_TOL, WALL_NZ, _main_grid  # noqa: E402

#: Classic-PoP outdoor zones (open sky) in a RoF2 install, by era. West Commonlands,
#: Misty Thicket, Highpass Hold and Lavastorm ship only as later ``.eqg`` remakes there,
#: so they are missing. qey2hh1 is West Karana's file name.
ZONES = {
    "classic": ("qeytoqrg", "qey2hh1", "northkarana", "eastkarana", "southkarana",
                "lakerathe", "rathemtn", "ecommons", "nro", "sro", "oasis", "erudsxing",
                "tox", "butcher", "steamfont", "lfaydark", "gfaydark", "kithicor",
                "nektulos", "innothule", "feerrott", "everfrost", "cauldron", "qrg", "oot",
                "kerraridge", "fearplane", "airplane", "stonebrunt"),
    "kunark": ("fieldofbone", "warslikswood", "lakeofillomen", "firiona",
               "swampofnohope", "frontiermtns", "dreadlands", "burningwood", "overthere",
               "timorous", "emeraldjungle", "trakanon", "skyfire"),
    "velious": ("iceclad", "greatdivide", "eastwastes", "cobaltscar", "wakening",
                "westwastes", "necropolis", "growthplane", "mischiefplane"),
    "luclin": ("dawnshroud", "scarlet", "twilight", "mseru", "tenebrous", "maiden",
               "umbral", "sseru", "grimling", "hollowshade", "letalis", "griegsend",
               "thegrey", "shadeweaver"),
    "pop": ("potranquility", "ponightmare", "podisease", "povalor", "postorms", "poair",
            "poeartha", "pofire", "bothunder"),
}
#: The outdoor dungeons: a ruin, castle or gorge with its rooms in open land. Measured
#: as their own group (the outdoor dungeon's whole zone).
ODUN = ("beholder", "crushbone", "mistmoore", "unrest", "kaesora", "karnor", "citymist",
        "akheva")

CELL = 8.0            # surface raster (u)
PLAN = 16.0           # walked-ground plan raster for areas (u)
ROOF_MIN, ROOF_MAX = 8.0, 250.0
MAX_COVERED = 0.5     # a zone more covered than this is not outdoor
MIN_FILL = 0.6        # walked width under this share of the mesh's: the network is split
MIN_AREA = 5000.0     # u^2: an interior's least plan area
MIN_REACH = 48.0      # u: some of its floor this far walk from open floor
GAP = 32.0            # contact points closer than this are one way in
#: Built or rock: the Axis_Share of the interior's walls (``wall_survey``, step 8: rough
#: caves 0.37-0.57, hewn 0.52-0.69, built 0.71-0.96). Hewn reads as built here: a
#: dressed-stone ruin's way in is its stairs or door, not a cave mouth.
BUILT_AXIS = 0.60
MIN_WAY = 6.0         # a contact narrower than this (u) is a seam, not a way in
HOST_RISE = 24.0      # host: top ground this far over the way in's floor
WALL_RISE = 32.0
SUNK = 30.0
CLIFF_LIP = 80.0
STAIR_DROP = 24.0



# --- the walk surface (cached) --------------------------------------------------------

def walk_data(eq_path: Path, zone: str, cache: Path | None) -> dict:
    """verts, faces, solid, standable, component, adjacency edges (i, j)."""
    f = cache / f"{zone}.npz" if cache else None
    if f is not None and f.exists():
        z = np.load(f)
        return {k: z[k] for k in z.files}
    mesh = load_mesh(eq_path, zone)
    surf = build_walk_surface(mesh, AgentModel(), floors_up=False)
    edges = np.array([(i, j) for i, nb in surf.adjacency.items() for j in nb if i < j],
                     np.int64).reshape(-1, 2)
    solid = np.array([not (p.flags & FLAG_PASSABLE) for p in mesh.polygons])
    d = {"verts": surf.verts, "faces": surf.faces, "solid": solid,
         "standable": surf.standable, "component": surf.component, "edges": edges}
    if f is not None:
        cache.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(f, **d)
    return d


# --- rasters ---------------------------------------------------------------------------

class Surfaces:
    """Every solid non-vertical surface's exact height at each ``CELL`` cell centre it
    covers, sorted by (cell, z): ``above`` finds the lowest surface in a z window."""

    def __init__(self, tri: np.ndarray, origin: np.ndarray, shape: tuple):
        self.origin, self.shape = origin, shape
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        keep = np.abs(n[:, 2]) > 0.05 * np.linalg.norm(n, axis=1).clip(1e-9)
        ground = n[:, 2] < 0                  # WLD floors wind down
        keys, zs, ups = [], [], []
        for t, g in zip(tri[keep], ground[keep]):
            lo = np.floor((t[:, :2].min(0) - origin) / CELL - 0.5).astype(int) + 1
            hi = np.floor((t[:, :2].max(0) - origin) / CELL - 0.5).astype(int)
            if (hi < lo).any() or (hi - lo + 1).prod() > 250000:
                continue
            ii, jj = np.meshgrid(np.arange(lo[0], hi[0] + 1), np.arange(lo[1], hi[1] + 1),
                                 indexing="ij")
            ii, jj = ii.ravel(), jj.ravel()
            px = origin[0] + (ii + 0.5) * CELL
            py = origin[1] + (jj + 0.5) * CELL
            (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = t
            det = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
            if abs(det) < 1e-9:
                continue
            w1 = ((y2 - y3) * (px - x3) + (x3 - x2) * (py - y3)) / det
            w2 = ((y3 - y1) * (px - x3) + (x1 - x3) * (py - y3)) / det
            w3 = 1.0 - w1 - w2
            m = (w1 >= -1e-6) & (w2 >= -1e-6) & (w3 >= -1e-6)
            keys.append(ii[m] * shape[1] + jj[m])
            zs.append((w1 * z1 + w2 * z2 + w3 * z3)[m])
            ups.append(np.full(int(m.sum()), bool(g)))
        key = np.concatenate(keys) if keys else np.zeros(0, np.int64)
        z = np.concatenate(zs) if zs else np.zeros(0)
        up = np.concatenate(ups) if ups else np.zeros(0, bool)
        order = np.lexsort((z, key))
        self.key, self.z, self.ground = key[order], z[order], up[order]
        # The top: the highest GROUND-facing surface per cell (wound as a floor, which a
        # WLD winds down). A ceiling is wound the other way, so a zone's sky cap or a
        # cave's single-sided ceiling never reads as the top of a hill.
        top = np.full(shape[0] * shape[1], np.nan)
        ku, zu = key[up], z[up]
        if len(ku):
            o = np.lexsort((zu, ku))
            ku, zu = ku[o], zu[o]
            last = np.r_[ku[1:] != ku[:-1], True]
            top[ku[last]] = zu[last]
        self.top = top.reshape(shape)

    def cell(self, xy: np.ndarray) -> tuple:
        ij = np.floor((xy - self.origin) / CELL).astype(int)
        ij[:, 0] = ij[:, 0].clip(0, self.shape[0] - 1)
        ij[:, 1] = ij[:, 1].clip(0, self.shape[1] - 1)
        return ij[:, 0], ij[:, 1]

    def above(self, pts: np.ndarray, lo: float, hi: float) -> tuple:
        """The lowest surface in (z + lo, z + hi] over each point: its z (nan where none)
        and whether it faces the ground (wound as a floor) rather than down."""
        i, j = self.cell(pts[:, :2])
        k = i * self.shape[1] + j
        start = np.searchsorted(self.key, k, "left")
        end = np.searchsorted(self.key, k, "right")
        out = np.full(len(pts), np.nan)
        grd = np.zeros(len(pts), bool)
        for n in range(len(pts)):
            seg = self.z[start[n]:end[n]]
            p = np.searchsorted(seg, pts[n, 2] + lo, "right")
            if p < len(seg) and seg[p] <= pts[n, 2] + hi:
                out[n] = seg[p]
                grd[n] = self.ground[start[n] + p]
        return out, grd

    def top_at(self, xy: np.ndarray) -> np.ndarray:
        i, j = self.cell(xy)
        return self.top[i, j]


def plan_cells(tri: np.ndarray, origin: np.ndarray, cell: float) -> set:
    """The ``cell`` u plan cells a set of triangles covers (sampled at cell / 2)."""
    out = set()
    step = cell / 2
    for t in tri:
        e = max(np.linalg.norm(t[1, :2] - t[0, :2]), np.linalg.norm(t[2, :2] - t[0, :2]),
                np.linalg.norm(t[2, :2] - t[1, :2]))
        k = max(1, int(math.ceil(e / step)))
        i, j = np.meshgrid(np.arange(k + 1), np.arange(k + 1), indexing="ij")
        m = i + j <= k
        u, w = i[m] / k, j[m] / k
        p = t[0, :2] + np.outer(u, t[1, :2] - t[0, :2]) + np.outer(w, t[2, :2] - t[0, :2])
        out.update(map(tuple, np.floor((p - origin) / cell).astype(int)))
    return out


# --- per zone --------------------------------------------------------------------------

def _components(nodes: np.ndarray, nbr: dict) -> list:
    nodes_set = set(int(n) for n in nodes)
    seen, out = set(), []
    for s in nodes_set:
        if s in seen:
            continue
        comp, stack = [], [s]
        seen.add(s)
        while stack:
            f = stack.pop()
            comp.append(f)
            for g in nbr.get(f, ()):
                if g in nodes_set and g not in seen:
                    seen.add(g)
                    stack.append(g)
        out.append(np.array(comp))
    return out


def _clusters(points: np.ndarray, gap: float) -> np.ndarray:
    parent = np.arange(len(points))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, j in cKDTree(points).query_pairs(gap):
        parent[find(i)] = find(j)
    return np.array([find(i) for i in range(len(points))])


def _extent(xy: np.ndarray) -> float:
    """Extent along the principal axis."""
    if len(xy) < 2:
        return 0.0
    c = xy - xy.mean(0)
    _, vec = np.linalg.eigh(np.cov(c.T))
    p = c @ vec[:, -1]
    return float(p.max() - p.min())


def _walk_from(starts, members: set, nbr: dict, cen: np.ndarray) -> dict:
    dist = {int(s): 0.0 for s in starts}
    heap = [(0.0, int(s)) for s in starts]
    while heap:
        d, f = heapq.heappop(heap)
        if d > dist[f]:
            continue
        for g in nbr.get(f, ()):
            if g in members:
                nd = d + float(np.linalg.norm(cen[f] - cen[g]))
                if nd < dist.get(g, math.inf):
                    dist[g] = nd
                    heapq.heappush(heap, (nd, g))
    return dist


def classify(e: dict, built: bool) -> str:

    if built:
        return "ruin stairs" if e["drop"] >= STAIR_DROP else "door"
    if e["sunk"] >= SUNK and e["wall"] >= 0.75:
        return "sinkhole"
    if e["sunk"] >= SUNK and e["wall"] >= 0.4:
        return "ravine"
    if e["lip"] >= CLIFF_LIP:
        return "cliff opening"
    return "mouth"


def analyse(eq_path: Path, zone: str, cache: Path | None) -> dict:
    d = walk_data(eq_path, zone, cache)
    v, faces = d["verts"], d["faces"]
    tri = v[faces]
    cr = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area_xy = 0.5 * np.abs(cr[:, 2])
    area = 0.5 * np.linalg.norm(cr, axis=1)
    slope = np.degrees(np.arccos(np.clip(-cr[:, 2] / np.maximum(2 * area, 1e-9), -1, 1)))
    cen = tri.mean(1)
    std = np.nonzero(d["standable"])[0]
    # The main network by face count, not area: several zones lay a flat sheet of a few
    # large faces under the whole map (steamfont's at z -232, 969 faces, outweighs its
    # 10073-face terrain by area).
    main = Counter(d["component"][std].tolist()).most_common(1)[0][0]
    walked = std[d["component"][std] == main]
    nbr: dict = defaultdict(list)
    for i, j in d["edges"]:
        nbr[int(i)].append(int(j))
        nbr[int(j)].append(int(i))

    vmin, vmax = v.min(0), v.max(0)
    origin = vmin[:2] - CELL
    shape = tuple((np.ceil((vmax[:2] - origin) / CELL) + 2).astype(int))
    surf = Surfaces(tri[d["solid"]], origin, shape)

    # Under the world: walked floor whose first surface above faces the ground (the
    # terrain's own top, single-sided) has no ceiling between it and the sky: it lies
    # under the map (fieldofbone's sheet at z -279 joins its ground somewhere). Dropped.
    first, first_ground = surf.above(cen[walked], ROOF_MIN, 5000.0)
    under = ~np.isnan(first) & first_ground
    under_share = float(area_xy[walked[under]].sum() / area_xy[walked].sum())
    walked = walked[~under]
    xy = cen[walked, :2]
    ground_cells = plan_cells(tri[walked], origin, PLAN)
    span = xy.max(0) - xy.min(0)
    # Covered: a ceiling (a down-facing surface) 8-250 u over the floor.
    roof, roof_ground = surf.above(cen[walked], ROOF_MIN, ROOF_MAX)
    covered = ~np.isnan(roof) & ~roof_ground
    out = {
        "zone": zone,
        "span": [float(span[0]), float(span[1])],
        "mesh": [float(vmax[0] - vmin[0]), float(vmax[1] - vmin[1])],
        "ground": len(ground_cells) * PLAN * PLAN,
        "covered": float(area_xy[walked][covered].sum() / area_xy[walked].sum()),
        "under": under_share,
        "interiors": [],
    }

    # --- interiors
    cov_faces = walked[covered]
    open_set = set(int(f) for f in walked[~covered])
    roof_of = dict(zip(cov_faces.tolist(), roof[covered].tolist()))
    nrm = cr / np.maximum(np.linalg.norm(cr, axis=1), 1e-9)[:, None]
    wall_mask = d["solid"] & (np.abs(nrm[:, 2]) < WALL_NZ) & (area > 1e-6)
    wall_n, wall_area = nrm, area
    nodes, kinds = regions(eq_path, zone)
    zl_regions = {r for r, k in kinds.items() if k == "zoneline"}
    for comp in _components(cov_faces, nbr):
        a_plan = float(area_xy[comp].sum())
        if a_plan < MIN_AREA:
            continue
        members = set(comp.tolist())
        contact = [(f, g) for f in comp for g in nbr.get(int(f), ()) if g in open_set]
        if not contact:
            continue
        dist = _walk_from({f for f, _ in contact}, members, nbr, cen)
        reach = max(dist.values())
        if reach < MIN_REACH:
            continue
        # ways in: each contact pair's shared vertices and its midpoint (faces the walk
        # joins by plan overlap share no vertex, and WLD ground often meets that way)
        pts, owner = [], []
        for k, (f, g) in enumerate(contact):
            sh = set(faces[f].tolist()) & set(faces[g].tolist())
            ps = [v[s] for s in sh] + [(cen[f] + cen[g]) / 2]
            pts += ps
            owner += [k] * len(ps)
        pts = np.array(pts)
        lab = _clusters(pts[:, :2], GAP)
        top_in = surf.top_at(cen[comp, :2])
        thick = top_in - np.array([roof_of[int(f)] for f in comp])
        wf = area_xy[comp]
        flat = float(wf[slope[comp] < 2.0].sum() / wf.sum())
        zfloor = cen[comp, 2]
        fp = plan_cells(tri[comp], origin, CELL)
        # Axis share of the walls standing in the footprint (step 8's measure)
        wi = np.nonzero(wall_mask & (cen[:, 2] >= zfloor.min() - 4)
                        & (cen[:, 2] <= zfloor.max() + 60))[0]
        wij = np.floor((cen[wi, :2] - origin) / CELL).astype(int)
        inside = np.array([any((a + da, b + db) in fp for da in (-1, 0, 1) for db in (-1, 0, 1))
                           for a, b in wij], bool) if len(wi) else np.zeros(0, bool)
        wi = wi[inside]
        axis = float("nan")
        if len(wi) and wall_area[wi].sum() >= 200.0:
            _, off = _main_grid(wall_n[wi], wall_area[wi])
            axis = float(wall_area[wi][off <= AXIS_TOL].sum() / wall_area[wi].sum())
        built = bool(axis >= BUILT_AXIS)
        zl = False
        if zl_regions:
            reg = region_of(nodes, cen[comp] + [0, 0, 3.0])
            zl = bool(np.isin(reg, list(zl_regions)).any())
        ways = []
        owner = np.array(owner)
        for L in np.unique(lab):
            m = lab == L
            p = pts[m]
            ks = np.unique(owner[m])
            fin = np.array([contact[k][0] for k in ks])
            fout = np.array([contact[k][1] for k in ks])
            c = p.mean(0)
            z0 = float(p[:, 2].mean())
            into = cen[fin, :2].mean(0) - cen[fout, :2].mean(0)
            into = into / max(np.linalg.norm(into), 1e-9)
            lip = float(surf.top_at((c[:2] + 24 * into)[None])[0] - z0)
            # walls: 16 rays
            ang = np.linspace(0, 2 * np.pi, 16, endpoint=False)
            rad = np.arange(32, 241, 16)
            rays = c[:2] + np.stack([np.cos(ang), np.sin(ang)], 1)[:, None, :] * rad[None, :, None]
            tops = surf.top_at(rays.reshape(-1, 2)).reshape(16, -1)
            wall = float((np.nanmax(np.nan_to_num(tops, nan=-1e9), 1) >= z0 + WALL_RISE).mean())
            dd = np.linalg.norm(xy - c[:2], axis=1)
            ring = cen[walked[~covered & (dd >= 100) & (dd <= 250)], 2]
            sunk = float(np.median(ring) - z0) if len(ring) else 0.0
            near = [f for f in comp if dist[int(f)] <= 120]
            # The opening's height: the ceiling over the covered faces it opens onto, less
            # their floor (p50; step 35 task 5). Read just inside the portal, where the roof
            # raster sees the opening's top.
            heights = [roof_of[int(f)] - cen[int(f), 2] for f in fin if int(f) in roof_of]
            ways.append({
                "at": [float(c[0]), float(c[1]), z0],
                "width": _extent(p[:, :2]),
                "wall": wall, "sunk": sunk, "lip": lip,
                "drop": float(z0 - cen[near, 2].min()) if near else 0.0,
                "height": float(np.median(heights)) if heights else float("nan"),
            })
        main_way = max(ways, key=lambda w: w["width"])
        ways = [w for w in ways if w["width"] >= MIN_WAY] or [main_way]
        for w in ways:
            w["kind"] = classify(w, built)
        base = main_way["at"][2]
        # footprint & host on the CELL raster
        fi_ = np.array(sorted(fp))
        fi_[:, 0] = fi_[:, 0].clip(0, shape[0] - 1)
        fi_[:, 1] = fi_[:, 1].clip(0, shape[1] - 1)
        high = np.nan_to_num(surf.top, nan=-1e9) >= base + HOST_RISE
        labels, _ = ndimage.label(high)
        hl = set(np.unique(labels[fi_[:, 0], fi_[:, 1]]).tolist()) - {0}
        host = {}
        if hl:
            hm = np.isin(labels, list(hl))
            hi, hj = np.nonzero(hm)
            hx = origin[0] + (hi + 0.5) * CELL
            hy = origin[1] + (hj + 0.5) * CELL
            edt = ndimage.distance_transform_edt(hm) * CELL
            marg = edt[fi_[:, 0], fi_[:, 1]]
            marg = marg[marg > 0]
            edge = (hx.min() - vmin[0] < 48 or vmax[0] - hx.max() < 48
                    or hy.min() - vmin[1] < 48 or vmax[1] - hy.max() < 48)
            host = {
                "size": [float(hx.max() - hx.min() + CELL), float(hy.max() - hy.min() + CELL)],
                "area": float(hm.sum() * CELL * CELL),
                "height": float(np.nanmax(surf.top[hm]) - base),
                "edge": bool(edge),
                "margin": [float(np.percentile(marg, 10)), float(np.percentile(marg, 50))]
                if len(marg) else [0.0, 0.0],
                "under": float(len(marg) / len(fi_)),
            }
        fx = origin[0] + (fi_[:, 0] + 0.5) * CELL
        fy = origin[1] + (fi_[:, 1] + 0.5) * CELL
        out["interiors"].append({
            "centre": [float(fx.mean()), float(fy.mean())],
            "foot": [float(fx.max() - fx.min() + CELL), float(fy.max() - fy.min() + CELL)],
            "area": float(len(fi_) * CELL * CELL),
            "reach": float(reach),
            "drop": float(base - zfloor.min()),
            "rise": float(zfloor.max() - base),
            "flat": flat, "thick": float(np.nanmedian(thick)), "built": built, "axis": axis,
            "zoneline": zl, "ways": ways, "host": host,
        })
    return out


# --- report ----------------------------------------------------------------------------

def _q(a, qs=(10, 50, 90, 100), fmt="{:.0f}") -> str:
    a = np.asarray(a, float)
    a = a[~np.isnan(a)]
    if not len(a):
        return "-"
    return "/".join(fmt.format(np.percentile(a, q)) for q in qs)


def plot(r: dict, eq_path: Path, cache: Path | None, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    d = walk_data(eq_path, r["zone"], cache)
    tri = d["verts"][d["faces"]]
    cen = tri.mean(1)
    std = d["standable"]
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.scatter(cen[std, 0], cen[std, 1], s=0.2, c="0.75")
    for it in r["interiors"]:
        h = it["host"]
        ax.add_patch(plt.Rectangle((it["centre"][0] - it["foot"][0] / 2,
                                    it["centre"][1] - it["foot"][1] / 2),
                                   it["foot"][0], it["foot"][1], fill=False,
                                   ec="k" if it["built"] else "brown"))
        for w in it["ways"]:
            ax.plot(w["at"][0], w["at"][1], "r^" if w["width"] >= 16 else "r.")
            ax.annotate(f"{w['kind']} {w['width']:.0f}", w["at"][:2], fontsize=7)
        if h:
            ax.annotate(f"host {h['size'][0]:.0f}x{h['size'][1]:.0f}"
                        f"{' edge' if h['edge'] else ''}", it["centre"], fontsize=7,
                        color="blue")
    ax.set_aspect("equal")
    ax.set_title(r["zone"])
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"{r['zone']}.png", dpi=110)
    plt.close(fig)


def _job(args):
    eq_path, zone, cache = args
    try:
        return analyse(eq_path, zone, cache)
    except Exception as e:  # a zone missing from this install
        return {"zone": zone, "error": f"{type(e).__name__}: {e}"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--eq-path", required=True, type=Path)
    ap.add_argument("--zones", help="comma list (default: every zone in ZONES and ODUN)")
    ap.add_argument("--cache", type=Path)
    ap.add_argument("--plots", type=Path)
    ap.add_argument("--json", type=Path, help="write the per-zone results here")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args(argv)

    group = {z: "wild" for zs in ZONES.values() for z in zs}
    group.update({z: "odun" for z in ODUN})
    era = {z: e for e, zs in ZONES.items() for z in zs}
    zones = args.zones.split(",") if args.zones else list(group)
    jobs = [(args.eq_path, z, args.cache) for z in zones]
    if args.workers > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(args.workers) as ex:
            results = list(ex.map(_job, jobs))
    else:
        results = [_job(j) for j in jobs]
    if args.json:
        args.json.write_text(json.dumps(results, indent=1))

    print(f"{'zone':14s} {'grp':4s} {'era':7s} {'width':>6s} {'depth':>6s} {'aspect':>6s} "
          f"{'ground 1e6':>10s} {'mesh box':>11s} {'covered':>7s}")
    bands = defaultdict(lambda: defaultdict(list))
    outdoor = set()
    for r in results:
        if "error" in r:
            print(f"{r['zone']:14s} error: {r['error']}")
            continue
        w, dpt = max(r["span"]), min(r["span"])
        g = group.get(r["zone"], "wild")
        why = ""
        if r["covered"] > MAX_COVERED:
            why = "not outdoor"
        elif w < MIN_FILL * max(r["mesh"]):
            why = "network split (water, islands)"
        print(f"{r['zone']:14s} {g:4s} {era.get(r['zone'], '-'):7s} {w:6.0f} {dpt:6.0f} "
              f"{w / max(dpt, 1):6.2f} {r['ground'] / 1e6:10.2f} "
              f"{r['mesh'][0]:5.0f}x{r['mesh'][1]:<5.0f} {r['covered']:7.0%}"
              f"{f'  ({why}: left out)' if why else ''}")
        if why != "not outdoor":
            outdoor.add(r["zone"])
        if not why:
            for key, val in (("width", w), ("depth", dpt), ("aspect", w / max(dpt, 1)),
                             ("ground", r["ground"] / 1e6)):
                bands[g][key].append(val)
                bands["all"][key].append(val)
    print("\nextent bands, p10/p50/p90/max (quartiles for width: p25/p50/p75)")
    for g, b in bands.items():
        print(f"  {g:4s} n={len(b['width']):2d}  width {_q(b['width'])}  depth {_q(b['depth'])}"
              f"  aspect {_q(b['aspect'], fmt='{:.2f}')}  ground 1e6 u^2 "
              f"{_q(b['ground'], fmt='{:.1f}')}  width quartiles {_q(b['width'], (25, 50, 75))}"
              f"  depth quartiles {_q(b['depth'], (25, 50, 75))}")

    print(f"\ninteriors in outdoor zones (plan >= {MIN_AREA:.0f} u^2, reach >= {MIN_REACH:.0f} u)")
    print(f"{'zone':14s} {'kind':5s} {'foot':>11s} {'area':>7s} {'reach':>5s} {'drop':>5s} "
          f"{'axis':>4s} {'flat':>4s} {'roof':>4s} {'zl':2s} {'host':>11s} {'h':>4s} {'margin':>8s} "
          f" ways (kind width wall sunk lip drop height)")
    rows = []
    for r in results:
        if "error" in r or r["zone"] not in outdoor:
            continue
        for it in r["interiors"]:
            h = it["host"]
            hs = (f"{h['size'][0]:5.0f}x{h['size'][1]:<5.0f}" if h else "-")
            ways = "; ".join(f"{w['kind']} {w['width']:.0f} {w['wall']:.2f} {w['sunk']:.0f} "
                             f"{w['lip']:.0f} {w['drop']:.0f} {w['height']:.0f}"
                             for w in it["ways"])
            print(f"{r['zone']:14s} {'built' if it['built'] else 'rock':5s} "
                  f"{it['foot'][0]:5.0f}x{it['foot'][1]:<5.0f} {it['area']:7.0f} "
                  f"{it['reach']:5.0f} {it['drop']:5.0f} {it['axis']:4.2f} {it['flat']:4.2f} {it['thick']:4.0f} "
                  f"{'Z' if it['zoneline'] else '':2s} {hs:>11s} "
                  f"{(h['height'] if h else 0):4.0f} "
                  f"{(('%.0f/%.0f' % tuple(h['margin'])) + ('E' if h['edge'] else '')) if h else '-':>8s}"
                  f"  {ways}")
            rows.append((r["zone"], it))
    zones_held = sorted({z for z, _ in rows})
    print(f"\n{len(zones_held)} outdoor zones hold an interior; {len(rows)} interiors "
          f"({sum(1 for _, i in rows if i['zoneline'])} lead to a zoneline, "
          f"{sum(1 for _, i in rows if i['built'])} built)")
    for label, pick in (("rock", lambda i: not i["built"]), ("built", lambda i: i["built"])):
        sel = [i for _, i in rows if pick(i)]
        inz = [i for i in sel if not i["zoneline"]]
        print(f"\n{label}: {len(sel)} interiors in {len({z for z, i in rows if pick(i)})} zones, "
              f"{len(inz)} in-zone (no zoneline)")
        kinds, widths, mains = Counter(), defaultdict(list), Counter()
        for i in sel:
            for w in i["ways"]:
                kinds[w["kind"]] += 1
                widths[w["kind"]].append(w["width"])
            mains[max(i["ways"], key=lambda w: w["width"])["kind"]] += 1
        print("  ways in by kind: count, width p10/p50/p90/max; [interiors whose widest way is it]")
        for k, n in kinds.most_common():
            print(f"    {k:14s} {n:3d}  {_q(widths[k])}  [{mains[k]}]")
        # The opening's height and height / width at the portal (step 35 task 5), per kind,
        # over the ways in at least 16 u wide (narrower ones are seams more than openings),
        # then over those in the generated Mouth's drawn range (32-96 u). A height within
        # CELL of ROOF_MAX saw no roof inside the raster's window, not the opening's top:
        # counted, then left out.
        print("  opening height p10/p50/p90/max, height / width p10/p50/p90/max "
              f"(ways >= 16 u; [32-96 u]; heights >= {ROOF_MAX - CELL:.0f} u left out)")
        for k, _n in kinds.most_common():
            hw = [(w["height"], w["width"]) for i in sel for w in i["ways"]
                  if w["kind"] == k and w["width"] >= 16 and not math.isnan(w["height"])]
            seen = [(h, wd) for h, wd in hw if h < ROOF_MAX - CELL]
            band = [(h, wd) for h, wd in seen if 32 <= wd <= 96]
            if seen:
                print(f"    {k:14s} n={len(seen):3d} (+{len(hw) - len(seen)} roofless)  "
                      f"height {_q([h for h, _ in seen])}  "
                      f"ratio {_q([h / wd for h, wd in seen], fmt='{:.2f}')}")
            if band:
                print(f"    {'':14s} [32-96 u] n={len(band):3d}  height {_q([h for h, _ in band])}  "
                      f"ratio {_q([h / wd for h, wd in band], fmt='{:.2f}')}")
        print(f"  ways per interior {_q([len(i['ways']) for i in sel])}")
        hosted = [i for i in inz if i["host"] and not i["host"]["edge"]]
        print(f"  in-zone: host is the edge massif {sum(1 for i in inz if i['host'] and i['host']['edge'])}, "
              f"own host {len(hosted)}, no high ground over it {sum(1 for i in inz if not i['host'])}")
        print(f"  in-zone footprint side (sqrt area) {_q([math.sqrt(i['area']) for i in inz])}  "
              f"reach {_q([i['reach'] for i in inz])}  drop {_q([i['drop'] for i in inz])}")
        if hosted:
            side_i = np.array([math.sqrt(i["area"]) for i in hosted])
            side_h = np.array([math.sqrt(i["host"]["area"]) for i in hosted])
            print(f"  own host: side / interior side {_q(side_h / side_i, fmt='{:.2f}')}  "
                  f"host side {_q(side_h)}  host height {_q([i['host']['height'] for i in hosted])}")
            print(f"  own host: margin (footprint to host edge) p10 {_q([i['host']['margin'][0] for i in hosted])}"
                  f"  p50 {_q([i['host']['margin'][1] for i in hosted])}  "
                  f"footprint under high ground {_q([i['host']['under'] for i in hosted], fmt='{:.2f}')}")
    if args.plots:
        for r in results:
            if "error" not in r and r["interiors"]:
                plot(r, args.eq_path, args.cache, args.plots)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
