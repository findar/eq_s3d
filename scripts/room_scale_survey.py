r"""Measure how stock rooms change from one to the next (step 9, task 12).

Splits each zone into chambers with step 6's survey, then reports per zone:

- **finish**: a 0-10 estimate per chamber, from the share of its wall area on the
  zone's main grid (``AXIS_TOL``), through the style bands of step 8's survey
  (``FINISH_AT``). p10/p50/p90 over the chambers. It sees how square a chamber
  is, not what it's made of, and a small chamber's few walls make it noisy.
- **drift**: the median finish difference between neighbouring chambers. **shuffled**
  is the same with the zone's values dealt out at random: drift well under shuffled
  means neighbours really do agree.
- **break**: the share of neighbours at least ``BREAK`` apart. **wings**: chambers
  grouped across anything less than a break; the count of groups of 2 or more, and
  the largest group's share of the zone.
- **coherence**: the value of the draw's lean (design, "Scales") whose simulated
  drift, on this zone's graph and with its values as weights, best matches.
- **mat**: the share of neighbours whose main wall texture differs, overall and at
  breaks. **width**: the median passage width (u) between neighbours, at breaks and
  elsewhere: does a passage narrow where the style changes?

What it can't see: doors are server records, not in the zone's files, and door frames
are mostly placed objects. Texture indices compare within a zone, not between zones.

``measure_scales`` takes any mesh with ``vertices`` and ``polygons``, so built zones
are judged by the same code as stock ones (task 15).

Usage::

    python scripts/room_scale_survey.py --eq-path F:\everquest_rof2 --cache %TEMP%\walls\cache
"""

from __future__ import annotations

import argparse
import random
import sys
from collections import defaultdict, deque
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from analyzer.traverse import AgentModel, build_walk_surface  # noqa: E402
from core.pfs import PfsArchive  # noqa: E402
from core.ter import FLAG_PASSABLE  # noqa: E402
from core.wld import load_wld  # noqa: E402
from dungeon_topology_survey import Floor, _sub_components, chamber_graph, split  # noqa: E402
from outdoor_dungeon_survey import load_mesh  # noqa: E402
from wall_survey import (AXIS_TOL, LEFT_OUT, MIN_ROOM, STYLES, WALL_NZ, WIDTH, _band, _main_grid,  # noqa: E402
                         stock_faces, walls_beside_floor)

CELL_AREA_MIN = MIN_ROOM * MIN_ROOM
#: Axis share -> finish: the style bands of step 8 (rough 0.37-0.57, hewn 0.52-0.69, built
#: 0.71-0.96) placed on the 0-3, 4-6, 7-10 of Requirement 12.
FINISH_AT = ((0.20, 0.0), (0.55, 3.5), (0.70, 6.5), (1.00, 10.0))
BREAK = 4.0         # neighbours this far apart in finish are a break
MIN_WALL = 200.0    # a chamber with less wall area than this has no finish (u^2)
SIMS = 40           # draws per coherence, to fit it
COHERENCES = tuple(range(0, 11))
#: Zones the wall survey left out for being mixed: the ones that most need measuring.
MIXED = ("chardok", "cazicthule", "hole", "mistmoore", "velketor")


def stock_textures(eq_path: Path, zone: str) -> np.ndarray:
    """Each polygon's texture index, in ``load_mesh``'s order (-1 where a mesh has none)."""
    wld = load_wld(PfsArchive.from_file(eq_path / f"{zone}.s3d").get(f"{zone}.wld"))
    out = []
    for m in wld.meshes:
        n = len(m.vertices)
        tex = m.polygon_textures or [-1] * len(m.polygons)
        out.extend(t for (v1, v2, v3, _), t in zip(m.polygons, tex) if v1 < n and v2 < n and v3 < n)
    return np.array(out, dtype=np.int64)


def _solid_faces(mesh):
    """Centres, unit normals and areas of the solid faces, and their polygon indices."""
    v = np.array([(p.x, p.y, p.z) for p in mesh.vertices], dtype=np.float64)
    which = np.array([i for i, p in enumerate(mesh.polygons) if not p.flags & FLAG_PASSABLE], dtype=np.int64)
    f = np.array([(mesh.polygons[i].v1, mesh.polygons[i].v2, mesh.polygons[i].v3) for i in which], dtype=np.int64)
    tri = v[f]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    a = np.linalg.norm(n, axis=1)
    ok = a > 1e-6
    return tri[ok].mean(1), n[ok] / a[ok, None], a[ok] / 2, which[ok]


def _passage_widths(floor: Floor, chamber: np.ndarray) -> dict:
    """(chamber, chamber) -> a passage's mean width: its area over the distance it spans."""
    g = floor.graph.tocoo()
    plab = _sub_components(floor.graph, chamber < 0)
    touch = (chamber[g.row] < 0) & (chamber[g.col] >= 0)
    contacts = defaultdict(lambda: defaultdict(list))
    for r, c in zip(g.row[touch], chamber[g.col][touch]):
        contacts[int(plab[r])][int(c)].append(r)
    area = np.bincount(plab[chamber < 0]) if (chamber < 0).any() else np.zeros(0)
    cell = float(np.median(np.abs(np.diff(np.unique(floor.xy[:, 0]))))) if len(floor.xy) > 1 else 1.0
    out = {}
    for p, chs in contacts.items():
        if len(chs) != 2:
            continue
        u, v = sorted(chs)
        span = np.linalg.norm(floor.xy[chs[u]].mean(0) - floor.xy[chs[v]].mean(0))
        if span > 0:
            out[(u, v)] = area[p] * cell * cell / span
    return out


def _lean_draw(n, adj, weights, coherence, rng) -> list:
    """The draw of the design's Scales section, on one graph: breadth first, leaning on
    the neighbours already drawn."""
    values = [None] * n
    seen = [False] * n
    sigma = 10.0 / coherence if coherence else None
    for start in range(n):
        if seen[start]:
            continue
        seen[start] = True
        queue = deque([start])
        while queue:
            u = queue.popleft()
            w = weights
            drawn = [values[x] for x in adj[u] if values[x] is not None]
            if sigma and drawn:
                m = sum(drawn) / len(drawn)
                w = weights * np.exp(-(((np.arange(11) - m) / sigma) ** 2) / 2)
            values[u] = rng.choices(range(11), weights=(w + 1e-9).tolist())[0]
            for x in adj[u]:
                if not seen[x]:
                    seen[x] = True
                    queue.append(x)
    return values


def fit_coherence(values: np.ndarray, edges, seed: int = 0) -> float:
    """The coherence whose simulated drift best matches this zone's."""
    n = len(values)
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
        adj[v].append(u)
    weights = np.bincount(np.round(values).astype(int), minlength=11).astype(float) + 0.25
    target = np.median([abs(values[u] - values[v]) for u, v in edges])
    rng = random.Random(seed)
    best, best_gap = 0, np.inf
    for c in COHERENCES:
        drifts = []
        for _ in range(SIMS):
            d = _lean_draw(n, adj, weights, c, rng)
            drifts.append(np.median([abs(d[u] - d[v]) for u, v in edges]))
        gap = abs(np.mean(drifts) - target)
        if gap < best_gap:
            best, best_gap = c, gap
    return float(best)


def measure_scales(mesh, agent: AgentModel, floors_up: bool = True, faces=None, textures=None) -> dict:
    """Every measure of one mesh. ``faces`` is the (floor, ceiling) triangles if the caller has
    them, ``textures`` each polygon's texture index if it wants the material columns."""
    if faces is None:
        surf = build_walk_surface(mesh, agent, floors_up=floors_up)
        nz = surf.normals[:, 2]
        floor_tris = surf.verts[surf.faces][np.nonzero(surf.standable & (nz > 0 if floors_up else nz < 0))[0]]
    else:
        floor_tris = faces[0]
    floor = Floor(floor_tris, agent)
    chamber, nch = split(floor, WIDTH)
    cen, n, a, which = _solid_faces(mesh)
    wall = np.nonzero(np.abs(n[:, 2]) < WALL_NZ)[0]
    node = walls_beside_floor(cen, wall, floor)
    keep = node >= 0
    idx, wall_ch = wall[keep], chamber[node[keep]]
    _theta, off = _main_grid(n[idx], a[idx])

    cell_area = floor.graph.shape[0] and np.bincount(chamber[chamber >= 0], minlength=nch)
    xs = np.unique(floor.xy[:, 0])
    cell = float(np.median(np.diff(xs))) if len(xs) > 1 else 1.0
    axes, tex = {}, {}
    for ch in range(nch):
        m = wall_ch == ch
        area = a[idx][m].sum()
        if cell_area[ch] * cell * cell < CELL_AREA_MIN or area < MIN_WALL:
            continue
        axes[ch] = a[idx][m][off[m] <= AXIS_TOL].sum() / area
        if textures is not None:
            t = textures[which[idx][m]]
            keys, counts = np.unique(t, return_counts=True)
            tex[ch] = int(keys[counts.argmax()])
    keptch = sorted(axes)
    new = {c: i for i, c in enumerate(keptch)}
    xp, fp = zip(*FINISH_AT)
    values = np.interp([axes[c] for c in keptch], xp, fp)
    edges = [(new[u], new[v]) for u, v in chamber_graph(floor, chamber, nch) if u in new and v in new]
    if not edges:
        return {"rooms": len(keptch), "edges": 0}
    diffs = np.array([abs(values[u] - values[v]) for u, v in edges])
    rng = np.random.default_rng(0)
    shuffled = []
    for _ in range(200):
        s = rng.permutation(values)
        shuffled.append(np.median([abs(s[u] - s[v]) for u, v in edges]))
    parent = list(range(len(values)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for (u, v), d in zip(edges, diffs):
        if d < BREAK:
            parent[find(u)] = find(v)
    sizes = np.bincount([find(i) for i in range(len(values))])
    out = {"_floor": floor, "_chamber": chamber, "_values": dict(zip(keptch, values.tolist())),
           "rooms": len(values), "edges": len(edges), "finish": np.percentile(values, [10, 50, 90]).tolist(),
           "drift": float(np.median(diffs)), "shuffled": float(np.mean(shuffled)),
           "break": float((diffs >= BREAK).mean()), "wings": int((sizes >= 2).sum()),
           "largest": float(sizes.max() / len(values)), "coherence": fit_coherence(values, edges)}
    widths = _passage_widths(floor, chamber)
    at, off_break = [], []
    for (u, v), (i, j) in zip(((a_, b_) for a_, b_ in chamber_graph(floor, chamber, nch) if a_ in new and b_ in new), edges):
        w = widths.get((u, v))
        if w is not None:
            (at if abs(values[i] - values[j]) >= BREAK else off_break).append(w)
    out["width_break"] = float(np.median(at)) if at else float("nan")
    out["width_other"] = float(np.median(off_break)) if off_break else float("nan")
    if textures is not None:
        changes = np.array([tex[keptch[u]] != tex[keptch[v]] for u, v in edges])
        out["mat"] = float(changes.mean())
        out["mat_break"] = float(changes[diffs >= BREAK].mean()) if (diffs >= BREAK).any() else float("nan")
    return out


def plot(zone: str, r: dict, out: Path) -> None:
    """Each chamber's floor from above, coloured by its finish; grey has none."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    floor, chamber = r["_floor"], r["_chamber"]
    c = np.array([r["_values"].get(int(ch), np.nan) for ch in chamber])
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.scatter(*floor.xy[np.isnan(c)].T, s=1, c="0.8")
    sc = ax.scatter(*floor.xy[~np.isnan(c)].T, s=2, c=c[~np.isnan(c)], cmap="coolwarm", vmin=0, vmax=10)
    fig.colorbar(sc, label="finish")
    ax.set_title(zone)
    ax.set_aspect("equal")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=90)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--eq-path", required=True, type=Path)
    ap.add_argument("--zones", default=",".join(list(STYLES) + list(MIXED)))
    ap.add_argument("--cache", type=Path, help="keep each zone's faces here")
    ap.add_argument("--plots", type=Path, help="write <zone>.png here")
    args = ap.parse_args(argv)
    agent = AgentModel()
    print(f"{'zone':12} {'style':6} rooms finish p10/50/90 drift shuf break wings largest coh  mat @brk  width @brk/else")
    rows = {}
    for zone in args.zones.split(","):
        mesh = load_mesh(args.eq_path, zone)
        tex = stock_textures(args.eq_path, zone)
        assert len(tex) == len(mesh.polygons), zone
        r = measure_scales(mesh, agent, floors_up=False, textures=tex,
                           faces=stock_faces(args.eq_path, zone, mesh, agent, args.cache))
        rows[zone] = r
        if args.plots and r["edges"]:
            plot(zone, r, args.plots / f"{zone}.png")
        style = STYLES.get(zone, "mixed" if zone in LEFT_OUT else "-")
        if not r["edges"]:
            print(f"{zone:12} {style:6} {r['rooms']:5} no neighbours")
            continue
        f = r["finish"]
        print(f"{zone:12} {style:6} {r['rooms']:5} {f[0]:4.1f}/{f[1]:4.1f}/{f[2]:4.1f}    {r['drift']:4.1f} {r['shuffled']:4.1f} "
              f"{r['break']:.2f}  {r['wings']:3}  {r['largest']:.2f}   {r['coherence']:4.1f} {r['mat']:.2f} {r['mat_break']:.2f}  "
              f"{r['width_break']:5.1f} /{r['width_other']:5.1f}", flush=True)
    print("\nBands:")
    for label, zones in (("kept", list(STYLES)), ("mixed", list(MIXED))):
        kept = [rows[z] for z in zones if z in rows and rows[z]["edges"]]
        if kept:
            print(f"  {label:6} drift {_band([r['drift'] for r in kept])}, shuffled {_band([r['shuffled'] for r in kept])}, "
                  f"break {_band([r['break'] for r in kept])}, largest wing {_band([r['largest'] for r in kept])}, "
                  f"coherence {_band([r['coherence'] for r in kept])}, mat {_band([r['mat'] for r in kept])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
