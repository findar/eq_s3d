r"""Measure the walls, floors and ceilings of stock rooms (step 8, task 1).

Walks each zone's floor and splits it into chambers with step 6's survey
(``dungeon_topology_survey``), then reports per zone:

- **axis**: Axis_Share, the share of wall area whose plan direction is within
  ``AXIS_TOL`` degrees of the zone's main grid (the rotation that catches most).
  Walls are solid faces with ``|nz| < WALL_NZ`` beside the walked floor (within
  ``NEAR`` u in plan, at most ``ABOVE`` u over it). Random directions would give
  about 0.12.
- **plumb**: the share of wall area within ``PLUMB`` degrees of vertical.
- **edge**: the median triangle edge of the walls (u).
- **run**: straight wall runs: neighbouring wall faces bending less than
  ``RUN_BEND`` degrees join; a run's length is its extent in plan. p10/p50/p90
  over the runs at least ``MIN_RUN`` u long, weighted by length.
- **corners**: runs per chamber (each run goes to the chamber whose floor it
  stands beside), p50 over the chambers. Door jambs count, so a build of nothing
  but rectangles measures 9.5-12.
- **fill**: a chamber's floor area over its bounding box on the zone's grid, p50.
  This reads low: the split keeps door stubs in a chamber and the raster loses its
  edge, so a build of nothing but rectangles measures 0.78-0.81. Compare built
  zones to stock with this same code; don't read it as true floor over Box.
- **floor**: a chamber's floor height p10-p90 (u), p50 over the chambers, and the
  zone's flat share (floor area within 2.6 degrees of level).
- **ceiling**: a chamber's headroom p10-p90 over its median, p50 over the covered
  chambers, and the zone's flat share. Open-air lids are ignored as in
  ``race_size_survey``.

``measure`` takes any mesh with ``vertices`` and ``polygons``, so built zones are
judged by the same code as stock ones (task 12): pass ``floors_up=True`` for
those (WLD floors wind down, generated floors wind up).

``--plots DIR`` draws each zone's plan (wall runs coloured by direction, chambers
grey) and side view, to ``DIR/<zone>.png``; the style labels in ``STYLES`` come
from looking at them. ``--cache DIR`` keeps each zone's floor and ceiling faces,
since ``build_walk_surface`` is slow.

Usage::

    python scripts/wall_survey.py --eq-path F:\everquest_rof2
    python scripts/wall_survey.py --eq-path F:\everquest_rof2 --zones blackburrow \
        --plots %TEMP%\walls --cache %TEMP%\walls\cache
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from analyzer.traverse import AgentModel, build_walk_surface  # noqa: E402
from core.ter import FLAG_PASSABLE  # noqa: E402
from dungeon_topology_survey import CELL, Floor, split  # noqa: E402
from dungeon_vertical_survey import _column_heights  # noqa: E402
from outdoor_dungeon_survey import load_mesh  # noqa: E402

WALL_NZ = 0.7       # a wall face's normal is at most this far up
NEAR = 8.0          # a wall stands within this of walked floor (u, in plan)
ABOVE = 60.0        # and at most this far over it (u)
AXIS_TOL = 5.0      # degrees either side of the grid
PLUMB = 3.0         # degrees from vertical
RUN_BEND = 5.0      # faces bending less than this are one straight run (degrees)
MIN_RUN = 4.0       # shorter runs are seams, not wall (u)
FLAT_NZ = 0.999     # a flat floor or ceiling face (2.6 degrees)
WIDTH = 40.0        # chamber split width, as step 6's survey
MIN_ROOM = 30.0     # chambers under this side are left out (u)
MIN_HEAD = 4.0      # a ceiling at least this over the floor (u)
MIN_COVER = 0.5     # a chamber with a ceiling over at least this share of it
LID_TOL = 2.0       # ceilings this near the zone's top are a sky lid (u)

#: Zone -> style, from the plots (design finding 1).
STYLES = {
    "blackburrow": "rough", "paw": "rough", "crystal": "rough", "runnyeye": "rough",
    "soldungb": "rough", "soldunga": "rough", "permafrost": "rough",
    "kaesora": "hewn", "guktop": "hewn", "najena": "hewn", "gukbottom": "hewn",
    "sebilis": "hewn",
    "qcat": "built", "befallen": "built", "kurn": "built",
}

#: Zones that don't separate, and why.
LEFT_OUT = {
    "chardok": "built halls and cave tunnels, about half each",
    "cazicthule": "a built temple, a tunnel maze and a pyramid",
    "mistmoore": "a castle in open grounds",
    "hole": "a ruined city inside caves",
    "velketor": "large geometric facets, not rock and not masonry",
    "unrest": "a house in an open yard",
    "dulak": "a harbour town, mostly open",
    "kedge": "one chamber, mostly water",
    "droga": "the split makes 124 chambers",
    "crushbone": "mostly outdoors",
}


def _arrays(mesh):
    """Solid faces of a mesh: (triangles, vertex ids, unit normals, areas)."""
    v = np.array([(p.x, p.y, p.z) for p in mesh.vertices], dtype=np.float64)
    f = np.array([(p.v1, p.v2, p.v3) for p in mesh.polygons
                  if not p.flags & FLAG_PASSABLE], dtype=np.int64)
    # Weld, as ``load_mesh`` does for WLD: a built mesh repeats its vertices per face,
    # and a straight run is found across shared edges.
    v, welded = np.unique(np.round(v, 2), axis=0, return_inverse=True)
    f = welded.ravel()[f]
    tri = v[f]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    a = np.linalg.norm(n, axis=1)
    ok = a > 1e-6
    return tri[ok], f[ok], n[ok] / a[ok, None], a[ok] / 2


def walls_beside_floor(cen, wall_idx, floor: Floor) -> np.ndarray:
    """The wall faces near a walked floor, and the node each stands beside (-1 for none)."""
    cols: dict = {}
    for k, (i, j) in enumerate(floor.ij):
        cols.setdefault((int(i), int(j)), []).append(k)
    reach = int(math.ceil(NEAR / CELL))
    ij = np.floor(cen[wall_idx, :2] / CELL).astype(np.int64)
    node = np.full(len(wall_idx), -1)
    for m, (ci, cj) in enumerate(ij):
        z = cen[wall_idx[m], 2]
        best = None
        for di in range(-reach, reach + 1):
            for dj in range(-reach, reach + 1):
                for k in cols.get((int(ci) + di, int(cj) + dj), ()):
                    if floor.z[k] - 4 <= z <= floor.z[k] + ABOVE:
                        d = di * di + dj * dj
                        if best is None or d < best[0]:
                            best = (d, k)
        if best is not None:
            node[m] = best[1]
    return node


def _main_grid(normals, areas) -> tuple:
    """The grid rotation (degrees, 0-90) catching most wall area, and the offsets from it."""
    ang = np.degrees(np.arctan2(normals[:, 1], normals[:, 0])) % 90
    hist = np.bincount(np.round(ang).astype(int) % 90, areas, 90)
    tol = int(AXIS_TOL)
    theta = int(sum(np.roll(hist, s) for s in range(-tol, tol + 1)).argmax())
    return theta, np.abs((ang - theta + 45) % 90 - 45)


def wall_runs(faces, normals, tri) -> np.ndarray:
    """Group wall faces into straight runs: a run id per face, then each id's length."""
    parent = np.arange(len(faces))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owners: dict = {}
    for k, (a, b, c) in enumerate(faces):
        for e in ((a, b), (b, c), (c, a)):
            owners.setdefault((min(e), max(e)), []).append(k)
    cos = math.cos(math.radians(RUN_BEND))
    for o in owners.values():
        if len(o) == 2 and abs(float(np.dot(normals[o[0]], normals[o[1]]))) >= cos:
            parent[find(o[0])] = find(o[1])
    ids = np.array([find(i) for i in range(len(faces))])
    uniq, run = np.unique(ids, return_inverse=True)
    length = np.zeros(len(uniq))
    for r in range(len(uniq)):
        m = run == r
        pts = tri[m][:, :, :2].reshape(-1, 2)
        k = np.nonzero(m)[0][0]
        along = np.array([-normals[k, 1], normals[k, 0]])
        norm = np.linalg.norm(along)
        if norm > 1e-6:
            s = pts @ (along / norm)
            length[r] = s.max() - s.min()
    return run, length


def _weighted_p(values, weights, qs=(10, 50, 90)) -> list:
    if not len(values):
        return [float("nan")] * len(qs)
    order = np.argsort(values)
    c = np.cumsum(weights[order]) / weights.sum() * 100
    return [float(values[order][min(np.searchsorted(c, q), len(c) - 1)]) for q in qs]


def _flat_share(tris) -> float:
    if not len(tris):
        return float("nan")
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    a = np.linalg.norm(n, axis=1)
    ok = a > 1e-6
    return float(a[ok][np.abs(n[ok, 2]) / a[ok] > FLAT_NZ].sum() / a[ok].sum())


def measure(mesh, agent: AgentModel, floors_up: bool = True, faces=None) -> dict:
    """Every measure of one mesh. ``faces`` is (floor triangles, ceiling triangles)
    when the caller already has them (``build_walk_surface`` is slow)."""
    if faces is None:
        surf = build_walk_surface(mesh, agent, floors_up=floors_up)
        tri = surf.verts[surf.faces]
        nz = surf.normals[:, 2]
        upward = nz > 0 if floors_up else nz < 0
        passable = np.array([bool(p.flags & FLAG_PASSABLE) for p in mesh.polygons])
        floor_tris = tri[np.nonzero(surf.standable & upward)[0]]
        down = nz < -0.1 if floors_up else nz > 0.1
        ceil_tris = tri[down & ~passable]
    else:
        floor_tris, ceil_tris = faces
    floor = Floor(floor_tris, agent)
    chamber, nch = split(floor, WIDTH)

    tri, f, n, a = _arrays(mesh)
    cen = tri.mean(1)
    wall = np.nonzero(np.abs(n[:, 2]) < WALL_NZ)[0]
    node = walls_beside_floor(cen, wall, floor)
    keep = node >= 0
    idx, node = wall[keep], node[keep]
    wn, wa, wt, wf = n[idx], a[idx], tri[idx], f[idx]
    theta, off = _main_grid(wn, wa)
    total = wa.sum()
    lean = np.degrees(np.arcsin(np.minimum(1, np.abs(wn[:, 2]))))
    edges = np.linalg.norm(wt - np.roll(wt, 1, axis=1), axis=2).ravel()

    run, length = wall_runs(wf, wn, wt)
    long = length >= MIN_RUN
    corners = np.zeros(max(nch, 1))
    wall_ch = chamber[node]
    for r in np.nonzero(long)[0]:
        chs = wall_ch[run == r]
        chs = chs[chs >= 0]
        if len(chs):
            corners[np.bincount(chs).argmax()] += 1

    c, s = math.cos(math.radians(theta)), math.sin(math.radians(theta))
    rot = np.array([[c, s], [-s, c]])
    cols = _column_heights(ceil_tris)
    tops = [z.max() for z in cols.values() if len(z)]
    lid = max(tops) - LID_TOL if tops else np.inf
    fills, floors, spreads, rooms = [], [], [], []
    for ch in range(nch):
        m = chamber == ch
        if m.sum() * CELL * CELL < MIN_ROOM * MIN_ROOM:
            continue
        rooms.append(ch)
        xy = floor.xy[m] @ rot.T
        size = xy.max(0) - xy.min(0) + CELL
        fills.append(m.sum() * CELL * CELL / (size[0] * size[1]))
        z = floor.z[m]
        floors.append(np.percentile(z, 90) - np.percentile(z, 10))
        head = []
        for (i, j), zz in zip(floor.ij[m], z):
            cz = cols.get((int(i), int(j)))
            if cz is None:
                continue
            up = cz[cz > zz + MIN_HEAD]
            if len(up) and up[0] < lid:
                head.append(up[0] - zz)
        if len(head) >= MIN_COVER * m.sum():
            head = np.array(head)
            spreads.append((np.percentile(head, 90) - np.percentile(head, 10))
                           / max(np.median(head), 1.0))
    med = lambda v: float(np.median(v)) if len(v) else float("nan")  # noqa: E731
    return {
        "axis": float(wa[off <= AXIS_TOL].sum() / total),
        "plumb": float(wa[lean <= PLUMB].sum() / total),
        "edge": float(np.median(edges)),
        "run": _weighted_p(length[long], length[long]),
        "corners": med(corners[rooms]) if rooms else float("nan"),
        "fill": med(fills),
        "floor_relief": med(floors),
        "floor_flat": _flat_share(floor_tris),
        "ceil_spread": med(spreads),
        "ceil_flat": _flat_share(ceil_tris),
        "rooms": len(rooms),
        # For the plots.
        "_floor": floor, "_chamber": chamber, "_wall_tris": wt, "_off": off, "_theta": theta,
    }


def stock_faces(eq_path: Path, zone: str, mesh, agent: AgentModel, cache: Path = None):
    """(floor, ceiling) triangles of a WLD zone: floors wind down, ceilings up."""
    if cache is not None:
        f = cache / f"{zone}.npz"
        if f.exists():
            d = np.load(f)
            return d["floor"], d["ceil"]
    surf = build_walk_surface(mesh, agent, floors_up=False)
    tri = surf.verts[surf.faces]
    nz = surf.normals[:, 2]
    passable = np.array([bool(p.flags & FLAG_PASSABLE) for p in mesh.polygons])
    floor, ceil = tri[np.nonzero(surf.standable & (nz < 0))[0]], tri[(nz > 0.1) & ~passable]
    if cache is not None:
        cache.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache / f"{zone}.npz", floor=floor, ceil=ceil)
    return floor, ceil


def plot(zone: str, r: dict, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    f, ch = r["_floor"], r["_chamber"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(22, 10), dpi=70,
                                 gridspec_kw={"width_ratios": [1.4, 1]})
    a1.scatter(f.xy[:, 0], f.xy[:, 1], s=3, marker="s", c=np.where(ch >= 0, "#dddddd", "#f2f2f2"),
               linewidths=0)
    wt = r["_wall_tris"]
    segs, cols = [], []
    for t, off in zip(wt, r["_off"]):
        order = np.argsort(t[:, 2])
        segs.append(t[order[1:], :2])
        cols.append("tab:blue" if off <= AXIS_TOL else "tab:red")
    a1.add_collection(LineCollection(segs, colors=cols, linewidths=0.6))
    a1.set_aspect("equal")
    a1.autoscale()
    a1.set_title(f"{zone}: walls on the grid (blue, {r['_theta']} deg) and off it (red)")
    i = int(np.argmax(f.xy.max(0) - f.xy.min(0)))
    a2.scatter(f.xy[:, i], f.z, s=1, c="#888888", linewidths=0)
    a2.set_aspect("equal")
    a2.set_title("floor, side view; 1:1")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)


def _band(vals) -> str:
    v = [x for x in vals if x == x]
    return f"{min(v):.2f}-{max(v):.2f}" if v else "-"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--eq-path", required=True, type=Path)
    ap.add_argument("--zones", default=",".join(list(STYLES) + list(LEFT_OUT)))
    ap.add_argument("--plots", type=Path, help="write <zone>.png here")
    ap.add_argument("--cache", type=Path, help="keep each zone's faces here")
    args = ap.parse_args(argv)
    agent = AgentModel()
    print(f"{'zone':12} {'style':6} axis plumb edge  run p10/p50/p90  corners fill "
          "floor flat | ceil flat rooms")
    rows = {}
    for zone in args.zones.split(","):
        mesh = load_mesh(args.eq_path, zone)
        faces = stock_faces(args.eq_path, zone, mesh, agent, args.cache)
        r = measure(mesh, agent, floors_up=False, faces=faces)
        rows[zone] = r
        print(f"{zone:12} {STYLES.get(zone, '-'):6} {r['axis']:.2f} {r['plumb']:.2f} {r['edge']:5.1f} "
              f"{r['run'][0]:5.1f}/{r['run'][1]:5.1f}/{r['run'][2]:5.1f}  {r['corners']:5.1f} "
              f"{r['fill']:.2f} {r['floor_relief']:5.1f} {r['floor_flat']:.2f} | "
              f"{r['ceil_spread']:.2f} {r['ceil_flat']:.2f} {r['rooms']:4}"
              + (f"  LEFT OUT: {LEFT_OUT[zone]}" if zone in LEFT_OUT else ""), flush=True)
        if args.plots:
            plot(zone, r, args.plots / f"{zone}.png")
    print("\nBands (kept zones):")
    for style in ("rough", "hewn", "built"):
        kept = [r for z, r in rows.items() if STYLES.get(z) == style]
        if not kept:
            continue
        print(f"  {style:6} axis {_band([r['axis'] for r in kept])}, plumb {_band([r['plumb'] for r in kept])}, "
              f"edge {_band([r['edge'] for r in kept])}, run p50 {_band([r['run'][1] for r in kept])}, "
              f"corners {_band([r['corners'] for r in kept])}, fill {_band([r['fill'] for r in kept])}, "
              f"floor {_band([r['floor_relief'] for r in kept])}, ceil {_band([r['ceil_spread'] for r in kept])}, "
              f"flat floor {_band([r['floor_flat'] for r in kept])}, flat ceil {_band([r['ceil_flat'] for r in kept])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
