r"""Measure the vertical anatomy of the stock dungeons (step 7, task 1).

Walks each zone's floor with step 6's survey (``dungeon_topology_survey``:
WLD floor-wound standable faces, sampled onto its layered 4 u raster, the
largest piece the agent can walk) and reports, per zone:

- **span**: p10-p90 (and p0-p100) of the walked floor's height, by area.
- **levels**: height clusters of the floor area. The floor heights are
  histogrammed (2 u bins, Gaussian-smoothed by ``SMOOTH`` u); peaks closer
  than ``MIN_SEP`` u, or whose valley holds more than ``PROMINENCE`` of the
  lower peak, merge; each node goes to the cluster between the valleys. A
  level is a cluster holding at least ``--level-share`` of the floor area
  (the share is printed; the count at half that share is printed too).
- **Stacked_Share**: the share of the floor area with another walked floor
  more than ``CLEARANCE`` u above it in the same raster column.
- **level-to-level height**: for each stacked node, the gap to the next
  walked floor above it (p10/p50/p90 by area). Over the same nodes,
  **headroom** (the lower floor up to the first ceiling-wound face over it)
  and **slab** (that ceiling up to the upper floor).
- **connectors**: steep floor. Each node's grade is a plane fit over its
  2-hop raster neighbourhood (~20 u across); nodes at grade >= ``STEEP``
  form connected runs, and a run rising at least ``MIN_RISE`` u is a
  connector: rise (z range), run (along-floor distance from its lowest to its
  highest node), grade = rise / run. Where its flat faces (normal within
  ``TREAD_DEG`` of up) are distinct steps, it is a stair: the tread faces
  grouped by height give the risers (p50 / max) and the treads (going = run
  per riser, landings included). The steepest
  connectors are listed per zone.
- **water**: passable WLD faces (water / lava planes and the like, which the
  walk surface never stands on) over the kept floor, and floor that is not
  in the walked piece at all ("dropped": flooded halls reached only by
  swimming, unreached ledges), with the share of it under a passable face.

``--plots DIR`` draws, per zone, a side view (height against the longer plan
axis, coloured by level, connectors black) and a plan view coloured by level
(stacked floor drawn on top), to ``DIR/<zone>.png``. ``EXCLUDED`` names zones
whose levels came out wrong on those plots; they are printed but left out of
the bands.

``--cache DIR`` keeps each zone's faces (``build_walk_surface`` is slow) so a
rerun takes seconds.

Usage::

    python scripts/dungeon_vertical_survey.py --eq-path F:\everquest_rof2
    python scripts/dungeon_vertical_survey.py --eq-path F:\everquest_rof2 \
        --zones befallen --plots %TEMP%\vert --cache %TEMP%\vert\cache
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.sparse import identity
from scipy.sparse.csgraph import connected_components, dijkstra

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from analyzer.traverse import AgentModel, build_walk_surface  # noqa: E402
from dungeon_topology_survey import CELL, LAYER_GAP, Floor, _band, _p  # noqa: E402
from core.ter import FLAG_PASSABLE  # noqa: E402
from outdoor_dungeon_survey import load_mesh  # noqa: E402

# Step 6's kept classic dungeons, then the ones this step adds.
ZONES = ("befallen", "najena", "permafrost", "sebilis", "chardok",
         "blackburrow", "runnyeye", "guktop", "gukbottom", "unrest")

CLEARANCE = 12.0      # a floor this far above another stacks on it (mapgeom.STACK_GAP)
LEVEL_SHARE = 0.10    # a level holds at least this share of the floor area
SMOOTH = 6.0          # height histogram smoothing (u, Gaussian sigma)
MIN_SEP = 16.0        # two levels' peaks at least this far apart (u)
PROMINENCE = 0.6      # merge two peaks whose valley holds > this of the lower one
STEEP = 0.35          # grade (rise / run) of a connector node (~19 deg)
MIN_RISE = 12.0       # a connector climbs at least this (u)
TREAD_DEG = 3.0       # a tread face is within this of flat
TREAD_TOL = 0.6       # tread faces this close in height are one tread (u)
MIN_TREAD_AREA = 6.0  # u^2: smaller flat bits are not a tread

# Zones whose levels are wrong on the side-view plots (finding 7).
EXCLUDED = {
    "unrest": "the outdoor yard is most of the floor at one height, so its level "
              "count and span describe the yard; the house's storeys (-14, 0, 16, "
              "44 u) hold under a tenth each, and its roof top walks as floor",
}


# ---------------------------------------------------------------------------
# Faces
# ---------------------------------------------------------------------------

def load_faces(eq_path: Path, zone: str, agent: AgentModel, cache: Path = None):
    """Floor triangles (as ``dungeon_topology_survey.load_floor`` keeps them),
    ceiling-wound triangles and passable non-vertical triangles."""
    if cache is not None:
        f = cache / f"{zone}.npz"
        if f.exists():
            d = np.load(f)
            return d["floor"], d["ceil"], d["wet"]
    mesh = load_mesh(eq_path, zone)
    surf = build_walk_surface(mesh, agent)
    tri = surf.verts[surf.faces]
    # Same filter as load_floor: WLD floors wind with the normal down.
    floor = tri[np.nonzero(surf.standable & (surf.normals[:, 2] < 0))[0]]
    passable = np.array([bool(p.flags & FLAG_PASSABLE) for p in mesh.polygons])
    nz = surf.normals[:, 2]
    ceil = tri[(nz > 0.1) & ~passable]
    wet = tri[(np.abs(nz) > 0.1) & passable]
    if cache is not None:
        cache.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache / f"{zone}.npz", floor=floor, ceil=ceil, wet=wet)
    return floor, ceil, wet


def _column_heights(tris: np.ndarray) -> dict:
    """(i, j) raster column -> sorted heights of the surfaces over its centre."""
    from dungeon_topology_survey import _samples
    if len(tris) == 0:
        return {}
    pts = _samples(tris, CELL / 2)
    ij = np.floor(pts[:, :2] / CELL).astype(np.int64)
    order = np.lexsort((pts[:, 2], ij[:, 1], ij[:, 0]))
    ij, z = ij[order], pts[order, 2]
    cut = np.nonzero((ij[1:] != ij[:-1]).any(1))[0] + 1
    out = {}
    for a, b in zip(np.r_[0, cut], np.r_[cut, len(z)]):
        out[(int(ij[a, 0]), int(ij[a, 1]))] = z[a:b]
    return out


def _columns(floor: Floor) -> dict:
    cols: dict = defaultdict(list)
    for k, (ci, cj) in enumerate(floor.ij):
        cols[(int(ci), int(cj))].append(k)
    return cols


# ---------------------------------------------------------------------------
# Levels and stacking
# ---------------------------------------------------------------------------

def levels(z: np.ndarray):
    """Cluster floor heights: returns (label per node, cluster centres)."""
    lo, hi = z.min() - 4 * SMOOTH, z.max() + 4 * SMOOTH
    edges = np.arange(lo, hi + 2.0, 2.0)
    h, _ = np.histogram(z, edges)
    s = gaussian_filter1d(h.astype(float), SMOOTH / 2.0)
    mid = (edges[:-1] + edges[1:]) / 2
    peaks = [i for i in range(1, len(s) - 1) if s[i] > 0 and s[i] >= s[i - 1] and s[i] > s[i + 1]]
    changed = True
    while changed and len(peaks) > 1:
        changed = False
        for a in range(len(peaks) - 1):
            p, q = peaks[a], peaks[a + 1]
            valley = s[p:q + 1].min()
            if mid[q] - mid[p] < MIN_SEP or valley > PROMINENCE * min(s[p], s[q]):
                peaks.pop(a + 1 if s[p] >= s[q] else a)
                changed = True
                break
    cuts = [mid[p + int(np.argmin(s[p:q + 1]))] for p, q in zip(peaks, peaks[1:])]
    lab = np.searchsorted(np.array(cuts), z)
    centres = np.array([np.median(z[lab == k]) if (lab == k).any() else mid[p]
                        for k, p in enumerate(peaks)])
    return lab, centres


def stacking(floor: Floor, cols: dict, ceil_cols: dict):
    """Per node: gap to the next walked floor above (nan if none), the
    headroom to the first ceiling over it, and the slab under the upper floor."""
    gap = np.full(floor.n, np.nan)
    head = np.full(floor.n, np.nan)
    slab = np.full(floor.n, np.nan)
    for key, ks in cols.items():
        if len(ks) < 2:
            continue
        ks = sorted(ks, key=lambda k: floor.z[k])
        cz = ceil_cols.get(key)
        for a in range(len(ks) - 1):
            k = ks[a]
            above = [m for m in ks[a + 1:] if floor.z[m] - floor.z[k] > CLEARANCE]
            if not above:
                continue
            up = floor.z[above[0]]
            gap[k] = up - floor.z[k]
            if cz is not None:
                c = cz[(cz > floor.z[k] + 2.0) & (cz < up - 0.5)]
                if len(c):
                    head[k] = c[0] - floor.z[k]
                    slab[k] = up - c[0]
    return gap, head, slab


# ---------------------------------------------------------------------------
# Connectors
# ---------------------------------------------------------------------------

def grade_field(floor: Floor) -> np.ndarray:
    """Plane-fit grade over each node's 2-hop raster neighbourhood."""
    a = floor.graph.copy()
    a.data[:] = 1.0
    a = a + identity(floor.n, format="csr")
    a2 = a @ a
    a2.data[:] = 1.0
    x = floor.xy[:, 0] - floor.xy[:, 0].mean()
    y = floor.xy[:, 1] - floor.xy[:, 1].mean()
    z = floor.z - floor.z.mean()
    n = a2 @ np.ones(floor.n)
    m = {k: a2 @ v / n for k, v in
         (("x", x), ("y", y), ("z", z), ("xx", x * x), ("xy", x * y),
          ("yy", y * y), ("xz", x * z), ("yz", y * z))}
    cxx = m["xx"] - m["x"] ** 2
    cxy = m["xy"] - m["x"] * m["y"]
    cyy = m["yy"] - m["y"] ** 2
    cxz = m["xz"] - m["x"] * m["z"]
    cyz = m["yz"] - m["y"] * m["z"]
    det = cxx * cyy - cxy ** 2
    ok = det > 1e-6
    ga = np.zeros(floor.n)
    gb = np.zeros(floor.n)
    ga[ok] = (cxz[ok] * cyy[ok] - cyz[ok] * cxy[ok]) / det[ok]
    gb[ok] = (cyz[ok] * cxx[ok] - cxz[ok] * cxy[ok]) / det[ok]
    return np.hypot(ga, gb)


def _face_nodes(floor: Floor, cols: dict, tris: np.ndarray) -> np.ndarray:
    """Raster node under each face's centroid (-1 if none)."""
    c = tris.mean(1)
    ij = np.floor(c[:, :2] / CELL).astype(np.int64)
    out = np.full(len(tris), -1, np.int64)
    for f, (ci, cj) in enumerate(ij):
        ks = cols.get((int(ci), int(cj)))
        if not ks:
            continue
        dz = [abs(floor.z[k] - c[f, 2]) for k in ks]
        b = int(np.argmin(dz))
        if dz[b] <= LAYER_GAP:
            out[f] = ks[b]
    return out


def connectors(floor: Floor, cols: dict, tris: np.ndarray, grade: np.ndarray):
    steep = grade >= STEEP
    idx = np.nonzero(steep)[0]
    if len(idx) == 0:
        return [], steep
    sub = floor.graph[idx][:, idx]
    _, lab = connected_components(sub, directed=False)

    n3 = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    area = 0.5 * np.abs(n3[:, 2])
    flat = np.abs(n3[:, 2]) >= math.cos(math.radians(TREAD_DEG)) * np.linalg.norm(n3, axis=1)
    fnode = _face_nodes(floor, cols, tris)
    region_of = np.full(floor.n, -1, np.int64)
    region_of[idx] = lab

    out = []
    for r in range(lab.max() + 1):
        loc = np.nonzero(lab == r)[0]
        nodes = idx[loc]
        z = floor.z[nodes]
        rise = float(z.max() - z.min())
        if rise < MIN_RISE or len(nodes) < 3:
            continue
        lo, hi = loc[np.argmin(z)], loc[np.argmax(z)]
        rsub = sub[loc][:, loc]
        d = dijkstra(rsub, directed=False, indices=int(np.argmin(z)))
        run = float(d[int(np.argmax(z))])
        if not np.isfinite(run) or run <= 0:
            continue
        c = {"nodes": nodes, "rise": rise, "run": run, "grade": rise / run,
             "at": np.r_[floor.xy[idx[lo]], floor.z[idx[lo]]],
             "stair": False}
        # Treads: flat faces over this run's nodes, grouped by height.
        fs = np.nonzero(flat & (fnode >= 0))[0]
        fs = fs[region_of[fnode[fs]] == r]
        if len(fs):
            fz = tris[fs, :, 2].mean(1)
            o = np.argsort(fz)
            fs, fz = fs[o], fz[o]
            cut = np.nonzero(np.diff(fz) > TREAD_TOL)[0] + 1
            groups = [g for g in np.split(np.arange(len(fs)), cut)
                      if area[fs[g]].sum() >= MIN_TREAD_AREA]
            tread_area = sum(area[fs[g]].sum() for g in groups)
            if len(groups) >= 3 and tread_area >= 0.4 * len(nodes) * CELL * CELL:
                hz = np.array([np.average(fz[g], weights=area[fs[g]]) for g in groups])
                risers = np.diff(hz)
                c.update(stair=True, treads=len(groups), risers=risers,
                         going=run / len(risers))
        out.append(c)
    out.sort(key=lambda c: -c["grade"])
    return out, steep


# ---------------------------------------------------------------------------
# Water and dropped floor
# ---------------------------------------------------------------------------

def water(floor: Floor, floor_tris: np.ndarray, wet_cols: dict):
    """Share of the kept floor under a passable face (within 80 u), the
    dropped floor area (u^2) and the share of it under a passable face."""
    def under(key, z):
        w = wet_cols.get(key)
        return w is not None and bool(((w > z) & (w < z + 80.0)).any())

    kept_wet = sum(under((int(i), int(j)), z) for (i, j), z in zip(floor.ij, floor.z))
    from dungeon_topology_survey import _samples
    pts = _samples(floor_tris, CELL / 2)
    keys = set(zip(*np.floor(pts[:, :2] / CELL).astype(np.int64).T,
                   np.floor(pts[:, 2] / LAYER_GAP).astype(np.int64)))
    kept = set()
    for (i, j), z in zip(floor.ij, floor.z):
        layer = int(math.floor(z / LAYER_GAP))
        for dl in (-1, 0, 1):
            kept.add((int(i), int(j), layer + dl))
    dropped = [k for k in keys if k not in kept]
    dropped_wet = sum(under((k[0], k[1]), (k[2] + 0.5) * LAYER_GAP) for k in dropped)
    return (kept_wet / max(floor.n, 1), len(dropped) * CELL * CELL,
            dropped_wet / max(len(dropped), 1))


# ---------------------------------------------------------------------------
# Survey
# ---------------------------------------------------------------------------

def survey(eq_path: Path, zone: str, agent: AgentModel, share: float,
           cache: Path = None) -> dict:
    floor_tris, ceil_tris, wet_tris = load_faces(eq_path, zone, agent, cache)
    floor = Floor(floor_tris, agent)
    cols = _columns(floor)
    lab, centres = levels(floor.z)
    shares = np.bincount(lab, minlength=len(centres)) / floor.n
    gap, head, slab = stacking(floor, cols, _column_heights(ceil_tris))
    grade = grade_field(floor)
    conns, steep = connectors(floor, cols, floor_tris, grade)
    kept_wet, dropped, dropped_wet = water(floor, floor_tris, _column_heights(wet_tris))
    return {
        "zone": zone, "floor": floor, "lab": lab, "centres": centres,
        "shares": shares, "nlev": int((shares >= share).sum()),
        "nlev_half": int((shares >= share / 2).sum()),
        "span": np.percentile(floor.z, [0, 10, 90, 100]),
        "stacked": float(np.isfinite(gap).mean()), "gap": gap[np.isfinite(gap)],
        "head": head[np.isfinite(head)], "slab": slab[np.isfinite(slab)],
        "conns": conns, "steep": steep, "area": floor.n * CELL * CELL,
        "kept_wet": kept_wet, "dropped": dropped, "dropped_wet": dropped_wet,
    }


def plot(r: dict, share: float, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    f = r["floor"]
    ext = f.xy.max(0) - f.xy.min(0)
    ax_i = int(np.argmax(ext))
    cmap = plt.get_cmap("tab10")
    big = r["shares"] >= share
    col = np.where(big[r["lab"]][:, None], cmap(r["lab"] % 10), (0.75, 0.75, 0.75, 1.0))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(22, 10), dpi=70,
                                 gridspec_kw={"width_ratios": [1.4, 1]})
    a1.scatter(f.xy[:, ax_i], f.z, s=2, c=col, linewidths=0)
    conn = np.zeros(f.n, bool)
    for c in r["conns"]:
        conn[c["nodes"]] = True
    a1.scatter(f.xy[conn, ax_i], f.z[conn], s=2, c="black", linewidths=0)
    for k, zc in enumerate(r["centres"]):
        if big[k]:
            a1.axhline(zc, color=cmap(k % 10), lw=0.6, ls="--")
            a1.text(f.xy[:, ax_i].min(), zc + 1, f"L{k} {r['shares'][k]:.0%}",
                    color=cmap(k % 10), fontsize=9)
    a1.set_xlabel("world " + "XY"[ax_i])
    a1.set_ylabel("height (u)")
    a1.set_aspect(3.0)
    a1.set_title(f"{r['zone']}: side view ({r['nlev']} levels at >= {share:.0%}; "
                 f"connectors black; height x3)")
    order = np.argsort(f.z)  # higher floor drawn on top
    a2.scatter(f.xy[order, 0], f.xy[order, 1], s=6, marker="s", c=col[order], linewidths=0)
    a2.set_aspect("equal")
    a2.set_title(f"plan, higher floors on top; stacked share {r['stacked']:.0%}")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def _f(v, fmt="{:.0f}") -> str:
    return "-" if v is None else fmt.format(v)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--eq-path", required=True, type=Path)
    ap.add_argument("--zones", default=",".join(ZONES))
    ap.add_argument("--level-share", type=float, default=LEVEL_SHARE)
    ap.add_argument("--exclude", default=",".join(EXCLUDED),
                    help="zones measured but left out of the bands")
    ap.add_argument("--plots", type=Path, help="write <zone>.png side views here")
    ap.add_argument("--cache", type=Path, help="keep each zone's faces here")
    ap.add_argument("--top", type=int, default=4, help="steepest connectors listed per zone")
    args = ap.parse_args(argv)
    agent = AgentModel()
    excluded = {z for z in args.exclude.split(",") if z}
    share = args.level_share

    print(f"raster {CELL:.0f} u; level = height cluster with >= {share:.0%} of the floor "
          f"(count at {share/2:.0%} in brackets); stacked = another walked floor "
          f"> {CLEARANCE:.0f} u above; connector = grade >= {STEEP} rising >= {MIN_RISE:.0f} u")
    print()
    head = (f"{'zone':12s} {'area k':>6s} {'span p10-p90':>12s} {'p0-p100':>9s} "
            f"{'lev':>5s} {'stack':>5s} {'gap p10/50/90':>13s} {'headroom':>11s} "
            f"{'slab':>11s} {'conn':>4s} {'stairs':>6s} {'wet':>4s} {'drop k':>6s} {'d.wet':>5s}")
    print(head)
    rows = {}
    for zone in [z for z in args.zones.split(",") if z]:
        try:
            r = survey(args.eq_path, zone, agent, share, args.cache)
        except Exception as e:  # a zone missing from this install
            print(f"{zone:12s} error: {type(e).__name__}: {e}")
            continue
        rows[zone] = r
        if args.plots:
            args.plots.mkdir(parents=True, exist_ok=True)
            plot(r, share, args.plots / f"{zone}.png")
        s = r["span"]
        stairs = sum(c["stair"] for c in r["conns"])
        tag = " (excluded)" if zone in excluded else ""
        print(f"{zone:12s} {r['area']/1e3:6.0f} {s[2]-s[1]:12.0f} {s[3]-s[0]:9.0f} "
              f"{r['nlev']:>2d} [{r['nlev_half']}] {r['stacked']:5.0%} "
              f"{_p(r['gap']):>13s} {_p(r['head'], (25, 50, 75)):>11s} "
              f"{_p(r['slab'], (25, 50, 75)):>11s} {len(r['conns']):4d} {stairs:6d} "
              f"{r['kept_wet']:4.0%} {r['dropped']/1e3:6.0f} {r['dropped_wet']:5.0%}{tag}")
    print()
    print("levels (centre height, share of floor):")
    for zone, r in rows.items():
        lv = ", ".join(f"{c:.0f}:{s:.0%}" for c, s in zip(r["centres"], r["shares"]) if s >= share / 2)
        print(f"  {zone:12s} {lv}")
    print()
    print("steepest connectors (rise, run, grade; stairs: treads, riser p50/max, going = run per riser):")
    for zone, r in rows.items():
        cs = r["conns"][:args.top]
        print(f"  {zone}: {len(r['conns'])} connectors, rise p50 "
              f"{_f(np.median([c['rise'] for c in r['conns']]) if r['conns'] else None)} u")
        for c in cs:
            x, y, z = c["at"]
            line = (f"    rise {c['rise']:5.1f} run {c['run']:6.1f} grade {c['grade']:.2f} "
                    f"({math.degrees(math.atan(c['grade'])):4.1f} deg) at ({x:.0f}, {y:.0f}, {z:.0f})")
            if c["stair"]:
                line += (f"  STAIR {c['treads']} treads, riser {np.median(c['risers']):.1f}/"
                         f"{c['risers'].max():.1f}, going {c['going']:.1f}")
            print(line)
        stairs = [c for c in r["conns"] if c["stair"]]
        if stairs:
            rs = np.concatenate([c["risers"] for c in stairs])
            print(f"    all {len(stairs)} stairs: riser p10/50/90 {np.percentile(rs, 10):.1f}/"
                  f"{np.median(rs):.1f}/{np.percentile(rs, 90):.1f}, going p50 "
                  f"{np.median([c['going'] for c in stairs]):.1f}, grade p50 "
                  f"{np.median([c['grade'] for c in stairs]):.2f}")
    print()
    for zone in sorted(excluded & set(rows)):
        print(f"excluded {zone}: {EXCLUDED.get(zone, 'by --exclude')}")
    kept = [r for z, r in rows.items() if z not in excluded]
    if kept:
        print(f"bands (p10-p90 over {len(kept)} zones: {', '.join(r['zone'] for r in kept)})")
        print(f"  Stacked_Share    {_band([r['stacked'] for r in kept])}")
        print(f"  level count      {_band([r['nlev'] for r in kept])}")
        print(f"  span p10-p90 (u) {_band([r['span'][2] - r['span'][1] for r in kept])}")
        print(f"  span / level-to-level p50 "
              f"{_band([(r['span'][2] - r['span'][1]) / np.median(r['gap']) for r in kept if len(r['gap'])])}")
        gaps = [np.median(r["gap"]) for r in kept if len(r["gap"])]
        heads = [np.median(r["head"]) for r in kept if len(r["head"])]
        slabs = [np.median(r["slab"]) for r in kept if len(r["slab"])]
        print(f"  level-to-level p50 (u) {_band(gaps)}; headroom p50 {_band(heads)}; "
              f"slab p50 {_band(slabs)}")
        stairs = [c for r in kept for c in r["conns"] if c["stair"]]
        if stairs:
            rs = np.concatenate([c["risers"] for c in stairs])
            print(f"  stairs: {len(stairs)}; riser p10/50/90 {np.percentile(rs, 10):.1f}/"
                  f"{np.median(rs):.1f}/{np.percentile(rs, 90):.1f}; going p50 "
                  f"{np.median([c['going'] for c in stairs]):.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
