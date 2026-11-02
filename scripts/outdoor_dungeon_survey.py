"""Survey the anatomy of classic outdoor dungeons (step 5, task 1).

Walks each zone's WLD floor with the traversal agent's rules (slope <= 40 deg,
step <= 3 u) and reports, for the reachable floor only:

- span       XY extent of the reachable floor
- covered    share of floor area with a surface 8-250 u above it (a roof)
- depth      how far covered floor sits below the nearest open floor (p50/p90)
- rock       thickness between a covered floor's ceiling and the next surface
             above it, where there is one (p10/p50/p90)
- interiors  covered regions of at least ``MIN_INTERIOR`` u^2
- boundaries separate places where open floor walks straight onto an
             interior. NOT a count of cave mouths: roofless patches inside a
             dungeon count too (befallen gives 16; design finding 3)

The walk starts from the zone's largest walkable network (by floor area): the
stock safe points are not in the client files, and the main floor is where
the safe point lies in every zone surveyed. Sky planes, roof tops and the
backs of dungeon shells are not connected to it, so they drop out.

Usage::

    python scripts/outdoor_dungeon_survey.py --eq-path F:\\everquest_rof2
    python scripts/outdoor_dungeon_survey.py --eq-path F:\\everquest_rof2 --zones unrest
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzer.traverse import AgentModel, build_walk_surface  # noqa: E402
from core.pfs import PfsArchive  # noqa: E402
from core.ter import FLAG_PASSABLE  # noqa: E402
from core.wld import load_wld  # noqa: E402

ZONES = ("mistmoore", "blackburrow", "runnyeye", "unrest", "highkeep",
         "kaesora", "befallen")
CONTROL = "befallen"          # all indoors: must come out mostly covered

CELL = 8.0                    # overhead raster cell (u)
ROOF_MIN, ROOF_MAX = 8.0, 250.0
ROCK_MAX = 1000.0             # look this far above a ceiling for the ground
MIN_INTERIOR = 2000.0         # u^2 of covered floor that counts as an interior
BOUNDARY_GAP = 32.0           # threshold faces closer than this are one boundary
WLD_PASSABLE = 0x10           # 0x36 polygon flag: non-solid


@dataclass
class _Vert:
    x: float
    y: float
    z: float


@dataclass
class _Poly:
    v1: int
    v2: int
    v3: int
    flags: int


@dataclass
class _Mesh:
    """The two fields ``build_walk_surface`` reads from a TerFile."""
    vertices: list
    polygons: list


def load_mesh(eq_path: Path, zone: str) -> _Mesh:
    """All zone triangles in one welded mesh (WLD regions share no vertex
    indices, so coincident points are merged to let the walk cross them)."""
    wld = load_wld(PfsArchive.from_file(eq_path / f"{zone}.s3d").get(f"{zone}.wld"))
    index: dict = {}
    verts: list = []
    polys: list = []
    for m in wld.meshes:
        local = []
        for x, y, z in m.vertices:
            key = (round(x, 2), round(y, 2), round(z, 2))
            if key not in index:
                index[key] = len(verts)
                verts.append(_Vert(x, y, z))
            local.append(index[key])
        n = len(local)
        for v1, v2, v3, flag in m.polygons:
            if v1 < n and v2 < n and v3 < n:
                flags = FLAG_PASSABLE if flag & WLD_PASSABLE else 0
                polys.append(_Poly(local[v1], local[v2], local[v3], flags))
    return _Mesh(verts, polys)


def overhead(tris: np.ndarray) -> dict:
    """Cell -> sorted heights of every non-vertical surface over its centre."""
    cells: dict = defaultdict(list)
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    n = np.cross(b - a, c - a)
    keep = np.abs(n[:, 2]) > 0.05 * np.linalg.norm(n, axis=1).clip(1e-9)
    for t in tris[keep]:
        lo = np.floor(t[:, :2].min(0) / CELL).astype(int)
        hi = np.floor(t[:, :2].max(0) / CELL).astype(int)
        if (hi - lo + 1).prod() > 40000:
            continue
        ii, jj = np.meshgrid(np.arange(lo[0], hi[0] + 1),
                             np.arange(lo[1], hi[1] + 1), indexing="ij")
        ii, jj = ii.ravel(), jj.ravel()
        px, py = (ii + 0.5) * CELL, (jj + 0.5) * CELL
        (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = t
        det = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        if abs(det) < 1e-9:
            continue
        w1 = ((y2 - y3) * (px - x3) + (x3 - x2) * (py - y3)) / det
        w2 = ((y3 - y1) * (px - x3) + (x1 - x3) * (py - y3)) / det
        w3 = 1.0 - w1 - w2
        inside = (w1 >= 0) & (w2 >= 0) & (w3 >= 0)
        zs = w1 * z1 + w2 * z2 + w3 * z3
        for ci, cj, z in zip(ii[inside], jj[inside], zs[inside]):
            cells[(int(ci), int(cj))].append(float(z))
    for v in cells.values():
        v.sort()
    return cells


def _components(nodes: set, adjacency: dict) -> list:
    seen: set = set()
    out = []
    for start in nodes:
        if start in seen:
            continue
        comp, stack = [], [start]
        seen.add(start)
        while stack:
            f = stack.pop()
            comp.append(f)
            for nb in adjacency.get(f, ()):
                if nb in nodes and nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        out.append(comp)
    return out


def _clusters(points: np.ndarray, gap: float) -> int:
    if len(points) == 0:
        return 0
    pairs = cKDTree(points).query_pairs(gap)
    parent = list(range(len(points)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, j in pairs:
        parent[find(i)] = find(j)
    return len({find(i) for i in range(len(points))})


def survey(eq_path: Path, zone: str, agent: AgentModel) -> dict:
    mesh = load_mesh(eq_path, zone)
    surf = build_walk_surface(mesh, agent)
    v, f = surf.verts, surf.faces
    tri = v[f]
    e1, e2 = tri[:, 1, :2] - tri[:, 0, :2], tri[:, 2, :2] - tri[:, 0, :2]
    area = 0.5 * np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0])

    # The main floor: the walkable component with the most floor area.
    std = np.nonzero(surf.standable)[0]
    by_comp: dict = defaultdict(float)
    for fi in std:
        by_comp[int(surf.component[fi])] += area[fi]
    main = max(by_comp, key=by_comp.get)
    reached = std[surf.component[std] == main]

    solid = np.array([not (p.flags & FLAG_PASSABLE) for p in mesh.polygons])
    cells = overhead(tri[solid])
    cen = surf.centroids[reached]
    covered = np.zeros(len(reached), bool)
    rock = []
    for k, (x, y, z) in enumerate(cen):
        above = [s for s in cells.get((int(math.floor(x / CELL)),
                                       int(math.floor(y / CELL))), ())
                 if s - z > ROOF_MIN]
        if above and above[0] - z < ROOF_MAX:
            covered[k] = True
            ceiling = above[0]
            beyond = [s for s in above[1:] if ROOF_MIN < s - ceiling < ROCK_MAX]
            if beyond:
                rock.append(beyond[-1] - ceiling)

    w = area[reached]
    open_c, cov_c = cen[~covered], cen[covered]
    depth = np.zeros(0)
    if len(open_c) and len(cov_c):
        _, near = cKDTree(open_c[:, :2]).query(cov_c[:, :2])
        depth = open_c[near, 2] - cov_c[:, 2]

    # Boundaries: open floor that walks straight onto an interior.
    cov_set = {int(fi) for fi in reached[covered]}
    open_set = {int(fi) for fi in reached[~covered]}
    interiors = [c for c in _components(cov_set, surf.adjacency)
                 if area[c].sum() >= MIN_INTERIOR]
    interior = {fi for c in interiors for fi in c}
    thresh = [fi for fi in interior
              if any(nb in open_set for nb in surf.adjacency.get(fi, ()))]

    xy = surf.centroids[reached, :2]
    return {
        "zone": zone,
        "span": xy.max(0) - xy.min(0),
        "floor_area": float(w.sum()),
        "covered": float(w[covered].sum() / w.sum()),
        "depth": depth,
        "rock": np.asarray(rock),
        "interiors": len(interiors),
        "boundaries": _clusters(surf.centroids[thresh, :2], BOUNDARY_GAP),
        "faces": len(reached),
    }


def _q(values: np.ndarray, qs=(50, 90)) -> str:
    if len(values) == 0:
        return "-"
    return "/".join(f"{np.percentile(values, q):.0f}" for q in qs)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--eq-path", required=True, type=Path)
    ap.add_argument("--zones", default=",".join(ZONES))
    args = ap.parse_args(argv)
    agent = AgentModel()

    print(f"{'zone':12s} {'span (u)':>11s} {'floor u^2':>10s} {'covered':>8s} "
          f"{'depth p50/90':>13s} {'rock p10/50/90':>15s} {'interiors':>9s} {'boundaries':>10s}")
    for zone in args.zones.split(","):
        try:
            r = survey(args.eq_path, zone, agent)
        except Exception as e:  # a zone missing from this install
            print(f"{zone:12s} error: {type(e).__name__}: {e}")
            continue
        tag = "  (control)" if zone == CONTROL else ""
        print(f"{zone:12s} {r['span'][0]:5.0f}x{r['span'][1]:<5.0f} "
              f"{r['floor_area']:10.0f} {r['covered']:8.0%} "
              f"{_q(r['depth']):>13s} {_q(r['rock'], (10, 50, 90)):>15s} "
              f"{r['interiors']:9d} {r['boundaries']:10d}{tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
