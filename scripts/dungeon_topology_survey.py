r"""Measure the room graphs of the stock dungeons (step 6, task 1).

Takes each zone's WLD floor (the walk surface's standable faces, rules of the
traversal agent: slope <= 40 deg, step <= 3 u; meshes loaded as in the step 5
survey, ``scripts/outdoor_dungeon_survey.py``), keeps the largest connected
floor and splits it into chambers and passages by floor width:

1. The floor faces are sampled onto a layered XY raster (``CELL`` u): a column
   holds one node per floor level, so stacked floors stay apart. Neighbouring
   nodes join when the agent could walk between them (rise <= 3 u plus a
   40 deg slope over the cell step). The largest connected piece is the zone.
   It is larger than the walk surface's own largest component in the guk
   zones, chardok and sebilis: WLD seams and stair treads the per-face test
   doesn't join are joined at this resolution.
2. Floor width: each node's distance, along the floor, to the floor's
   boundary (a node missing one of its 8 neighbours). Twice that distance on
   the medial line is the local width.
3. Chambers: floor wider than ``--width`` (the cores), split at necks (a
   watershed on the distance: two wide basins stay apart when the floor where
   they meet is under ``NECK`` of the narrower basin's widest point, i.e. a
   doorway between rooms), then grown back out by half the threshold.
   Everything else is passage.
4. Edges: two chambers that touch, or that one passage component touches.
   A passage touching k >= 3 chambers is a junction and adds k - 1 edges
   (shortest spanning tree between its contacts), so a junction adds no
   cycle. Loops made of passages alone are therefore not counted.

Per zone it prints chamber count, chamber sides (p10/p50/p90, side = sqrt of
the chamber's floor area), the degree histogram, cycle rank (E - N + C),
dead-end share (degree-1 chambers over N), deep-end distance (longest
shortest path in hops from the entry chamber, over N), the Size_Class mix
(each side over the zone's median side, binned at the class centres 0.5 /
0.75 / 1.0 / 1.4 / 1.9 with geometric-mean bounds), the passage share of the
floor and the ridge widths (twice the boundary distance at its local maxima:
p25/p50 are the corridors). Then p10-p90 bands over the zones kept.

Entry chamber: stock safe points and zone lines are server data, not in the
client files. The EQ map files label the zone-in (``to_<zone>`` /
``from_<zone>``), so the entry is the chamber nearest that label (``ENTRY``
below). With no label it falls back to the chamber farthest from the
floor's centre.

``EXCLUDED`` names the zones whose chamber graph a map reading shows wrong
(checked by eye with ``--plots``); they are printed but left out of the
bands. ``--plots DIR`` draws each zone's floor (coloured by chamber, grey =
passage), its EQ map lines and the chamber graph to ``DIR/<zone>.png``.

Usage::

    python scripts/dungeon_topology_survey.py --eq-path F:\everquest_rof2
    python scripts/dungeon_topology_survey.py --eq-path F:\everquest_rof2 \
        --zones befallen --plots %TEMP%\topo
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from analyzer.traverse import AgentModel, build_walk_surface  # noqa: E402
from generators.eqmap import map_to_world, parse_map_layer  # noqa: E402
from outdoor_dungeon_survey import load_mesh  # noqa: E402

CLASSIC = ("befallen", "crushbone", "najena", "gukbottom", "guktop",
           "permafrost", "soldunga", "kaesora", "sebilis", "chardok")
WARREN = ("blackburrow", "runnyeye")

# The zone-in label in the zone's EQ map file (substring, case-insensitive).
# gukbottom is entered from guktop's lower gates; the main one sits by
# (216, -1194) in both zones' maps.
ENTRY = {
    "befallen": "to_West_Commonlands",
    "crushbone": "to_The_Greater_Faydark",
    "najena": "to_The_Lavastorm",
    "gukbottom": "to_The_City_of_Guk@216",
    "guktop": "to_Innothule",
    "permafrost": "to_Everfrost",
    "soldunga": "to_The_Lavastorm",
    "kaesora": "to_The_Field_of_Bone",
    "sebilis": "from_Trakanon",
    "chardok": "from_The_Burning_Woods",
    "blackburrow": "to_Qeynos_Hills",
    "runnyeye": "to_Misty_Thicket",
}

# Map files: the RoF2 install's own first, then a full classic set.
MAP_DIRS = ("maps", r"F:\EQlegends\maps")

CELL = 4.0                    # raster cell (u)
LAYER_GAP = 8.0               # floors closer than this in one column merge
# The width threshold. Our corridors (generators/layout.py): corridor_width =
# max(40, side * 0.25), 50 u at the default room band, never under 40. Stock
# corridors: the ridge widths' p25/p50 are 12-20 / 12-28 u in every zone
# surveyed, and 64-75 % of the floor lies within 12 u of a wall (2 * dist
# < 24). 40 u sits above every stock corridor and at our narrowest corridor,
# so neither reads as a chamber. 32 and 48 are printed by --width for the
# sensitivity (finding 5).
WIDTH = 40.0
MIN_CORE = 6                  # core nodes a chamber needs (drops slivers)
NECK = 0.75                   # doorway under 3/4 of the narrower room: split

# Zones whose chamber graph is wrong against the map (finding 5).
EXCLUDED = {
    "crushbone": "outdoor: the open valley is cut into arbitrary chambers",
    "gukbottom": "cell-sized rooms under the threshold; flooded halls are not floor",
    "guktop": "the flooded east halls are not floor: only the west half is graphed",
    "soldunga": "its central cave tunnels hold no chamber: one passage edge spans 600 u",
    "kaesora": "the temple (zone-in) is a separate floor, reached by a drop",
    "runnyeye": "upper two levels are tunnels with no chamber: their rooms and loops vanish",
}

SIZE_CLASSES = ("tiny", "small", "medium", "large", "huge")
SIZE_CENTRES = (0.5, 0.75, 1.0, 1.4, 1.9)
SIZE_BOUNDS = tuple(math.sqrt(a * b) for a, b in zip(SIZE_CENTRES, SIZE_CENTRES[1:]))


# ---------------------------------------------------------------------------
# Floor raster
# ---------------------------------------------------------------------------

def _samples(tris: np.ndarray, step: float) -> np.ndarray:
    """Points covering each triangle at ``step`` spacing (barycentric grid)."""
    out = []
    for t in tris:
        span = max(np.linalg.norm(t[1, :2] - t[0, :2]),
                   np.linalg.norm(t[2, :2] - t[1, :2]),
                   np.linalg.norm(t[0, :2] - t[2, :2]))
        n = max(1, int(math.ceil(span / step)))
        i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing="ij")
        keep = i + j <= n
        a = i[keep] / n
        b = j[keep] / n
        c = 1.0 - a - b
        pts = a[:, None] * t[0] + b[:, None] * t[1] + c[:, None] * t[2]
        out.append(pts)
        out.append(t.mean(0, keepdims=True))
    return np.concatenate(out)


class Floor:
    """Layered raster of the reached floor: nodes, their XY/Z, the step graph."""

    def __init__(self, tris: np.ndarray, agent: AgentModel):
        pts = _samples(tris, CELL / 2)
        ij = np.floor(pts[:, :2] / CELL).astype(np.int64)
        order = np.lexsort((pts[:, 2], ij[:, 1], ij[:, 0]))
        ij, z = ij[order], pts[order, 2]
        new_col = np.ones(len(z), bool)
        new_col[1:] = (ij[1:] != ij[:-1]).any(1)
        new_node = new_col.copy()
        new_node[1:] |= (z[1:] - z[:-1]) > LAYER_GAP
        node = np.cumsum(new_node) - 1
        n = int(node[-1]) + 1
        self.ij = ij[new_node]
        self.z = np.bincount(node, z, n) / np.bincount(node, None, n)
        self.xy = (self.ij + 0.5) * CELL
        self.n = n

        cols: dict = defaultdict(list)
        for k, (ci, cj) in enumerate(self.ij):
            cols[(int(ci), int(cj))].append(k)
        tan = math.tan(math.radians(agent.walkable_slope_deg))
        rows, colz, wts = [], [], []
        nbrs = [(di, dj) for di in (-1, 0, 1) for dj in (-1, 0, 1) if di or dj]
        for k, (ci, cj) in enumerate(self.ij):
            for di, dj in nbrs:
                d = math.hypot(di, dj) * CELL
                lim = agent.max_step_up + d * tan
                best = None
                for m in cols.get((int(ci) + di, int(cj) + dj), ()):
                    dz = abs(self.z[m] - self.z[k])
                    if dz <= lim and (best is None or dz < best[1]):
                        best = (m, dz)
                if best is not None:
                    rows.append(k)
                    colz.append(best[0])
                    wts.append(d)
        g = coo_matrix((wts, (rows, colz)), shape=(n, n)).tocsr()
        g = g.maximum(g.T)
        # The raster's largest connected piece (sliver faces the walk joined
        # across a seam can fall apart at this resolution).
        _, lab = connected_components(g, directed=False)
        keep = lab == np.bincount(lab).argmax()
        idx = np.nonzero(keep)[0]
        self.graph = g[idx][:, idx]
        self.ij, self.z, self.xy = self.ij[idx], self.z[idx], self.xy[idx]
        self.n = len(idx)
        self.boundary = np.diff(self.graph.indptr) < 8
        dist = dijkstra(self.graph, directed=False,
                        indices=np.nonzero(self.boundary)[0], min_only=True)
        self.dist = dist + CELL / 2   # a boundary node's centre is half a cell in


# ---------------------------------------------------------------------------
# Chambers and the chamber graph
# ---------------------------------------------------------------------------

def _sub_components(graph, mask: np.ndarray):
    idx = np.nonzero(mask)[0]
    sub = graph[idx][:, idx]
    _, lab = connected_components(sub, directed=False)
    full = np.full(len(mask), -1, np.int64)
    full[idx] = lab
    return full


def _watershed(floor: Floor, core: np.ndarray, neck: float) -> np.ndarray:
    """Split the core at necks: flood nodes from the widest down; two basins
    that meet stay apart when the floor where they meet is narrower than
    ``neck`` times the narrower basin's widest point (a doorway between two
    rooms, not a lumpy wall inside one)."""
    order = np.nonzero(core)[0]
    order = order[np.argsort(-floor.dist[order], kind="stable")]
    parent = np.full(floor.n, -1, np.int64)
    peak: dict = {}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    ip, ix = floor.graph.indptr, floor.graph.indices
    for k in order:
        roots = {find(m) for m in ix[ip[k]:ip[k + 1]] if parent[m] >= 0}
        if not roots:
            parent[k] = k
            peak[k] = floor.dist[k]
            continue
        roots = sorted(roots, key=lambda r: -peak[r])
        top = roots[0]
        parent[k] = top
        for r in roots[1:]:
            if floor.dist[k] >= neck * min(peak[r], peak[top]):
                parent[r] = top
    lab = np.full(floor.n, -1, np.int64)
    for k in order:
        lab[k] = find(k)
    return lab


def split(floor: Floor, width: float, neck: float = None):
    """Label each node with a chamber id (>= 0) or -1 (passage)."""
    neck = NECK if neck is None else neck
    core = floor.dist >= width / 2
    lab = _watershed(floor, core, neck) if neck > 0 else         _sub_components(floor.graph, core)
    keep = {c for c, k in zip(*np.unique(lab[core], return_counts=True))
            if k >= MIN_CORE}
    core &= np.isin(lab, list(keep))
    remap = {c: i for i, c in enumerate(sorted(keep))}
    seeds = np.nonzero(core)[0]
    dist, _, src = dijkstra(floor.graph, directed=False, indices=seeds,
                            min_only=True, return_predecessors=True)
    chamber = np.full(floor.n, -1, np.int64)
    near = np.isfinite(dist) & (dist <= width / 2 + CELL)
    chamber[near] = [remap[int(lab[s])] for s in src[near]]
    return chamber, len(remap)


def chamber_graph(floor: Floor, chamber: np.ndarray, nch: int):
    g = floor.graph.tocoo()
    a, b = chamber[g.row], chamber[g.col]
    edges = set()
    both = (a >= 0) & (b >= 0) & (a != b)
    for i, j in zip(a[both], b[both]):
        edges.add((min(i, j), max(i, j)))

    passage = chamber < 0
    plab = _sub_components(floor.graph, passage)
    touch = (a < 0) & (b >= 0)
    contacts: dict = defaultdict(lambda: defaultdict(list))
    for r, c in zip(g.row[touch], b[touch]):
        contacts[int(plab[r])][int(c)].append(r)
    for p, chs in contacts.items():
        ids = sorted(chs)
        if len(ids) < 2:
            continue
        pos = {c: np.c_[floor.xy[chs[c]], floor.z[chs[c]]].mean(0) for c in ids}
        # Prim's tree over the contacts: a junction joins, it adds no cycle.
        inside, rest = {ids[0]}, set(ids[1:])
        while rest:
            best = min(((np.linalg.norm(pos[u] - pos[v]), u, v)
                        for u in inside for v in rest))
            _, u, v = best
            edges.add((min(u, v), max(u, v)))
            inside.add(v)
            rest.discard(v)
    return sorted(edges)


def _hops(n: int, edges, start: int) -> np.ndarray:
    adj = defaultdict(list)
    for i, j in edges:
        adj[i].append(j)
        adj[j].append(i)
    d = np.full(n, -1)
    d[start] = 0
    q = [start]
    for u in q:
        for v in adj[u]:
            if d[v] < 0:
                d[v] = d[u] + 1
                q.append(v)
    return d


# ---------------------------------------------------------------------------
# Map files
# ---------------------------------------------------------------------------

def load_map(eq_path: Path, zone: str):
    """Map lines from the first map set that has the zone; labels from all of
    them (the RoF2 set's crushbone labels its zone-in for another zone)."""
    lines, labels, src = [], [], None
    for d in MAP_DIRS:
        base = Path(d) if Path(d).is_absolute() else eq_path / d
        files = sorted(base.glob(f"{zone}.txt")) + sorted(base.glob(f"{zone}_[0-9].txt"))
        for f in files:
            layer = parse_map_layer(f.read_text(errors="replace")).layer
            if src is None or src == base:
                lines += layer.lines
            labels += layer.labels
        if files and src is None:
            src = base
    return src, lines, labels


def entry_point(zone: str, labels):
    key = ENTRY.get(zone)
    if not key:
        return None
    text, _, near = key.partition("@")
    hits = [lb for lb in labels if text.lower() in lb.text.lower()]
    if near:
        hits.sort(key=lambda lb: abs(lb.x - float(near)))
    if not hits:
        return None
    x, y, z = map_to_world(hits[0].x, hits[0].y, hits[0].z)
    return np.array([x, y, z]), hits[0].text


# ---------------------------------------------------------------------------
# Survey
# ---------------------------------------------------------------------------

def load_floor(eq_path: Path, zone: str, agent: AgentModel) -> Floor:
    mesh = load_mesh(eq_path, zone)
    surf = build_walk_surface(mesh, agent)
    tri = surf.verts[surf.faces]
    # The walk surface takes |nz|, so ceilings pass as standable. WLD winds
    # its polygons the other way round: a floor's computed normal points down
    # (the lowest surface in 92-95 % of XY columns does, in befallen,
    # blackburrow and gukbottom). Keep the floors only.
    std = np.nonzero(surf.standable & (surf.normals[:, 2] < 0))[0]
    return Floor(tri[std], agent)


def survey(eq_path: Path, zone: str, agent: AgentModel, width: float,
           floor: Floor = None, neck: float = None) -> dict:
    if floor is None:
        floor = load_floor(eq_path, zone, agent)
    chamber, nch = split(floor, width, neck)
    edges = chamber_graph(floor, chamber, nch)

    sizes = np.array([math.sqrt((chamber == c).sum()) * CELL for c in range(nch)])
    centres = np.array([np.r_[floor.xy[chamber == c].mean(0), floor.z[chamber == c].mean()]
                        for c in range(nch)])
    deg = np.zeros(nch, np.int64)
    for i, j in edges:
        deg[i] += 1
        deg[j] += 1
    ncomp = connected_components(
        coo_matrix((np.ones(len(edges)), tuple(np.array(edges).T) if edges else ([], [])),
                   shape=(nch, nch)), directed=False)[0] if nch else 0

    _, map_lines, labels = load_map(eq_path, zone)
    ep = entry_point(zone, labels)
    if ep is not None:
        p, entry_label = ep
        # Nearest chamber node to the label, along the floor where possible.
        d3 = np.linalg.norm(np.c_[floor.xy, floor.z] - p, axis=1)
        ch_nodes = np.nonzero(chamber >= 0)[0]
        entry = int(chamber[ch_nodes[np.argmin(d3[ch_nodes])]])
    else:
        entry_label = "(fallback: farthest from centre)"
        mid = floor.xy.mean(0)
        entry = int(np.argmax(np.linalg.norm(centres[:, :2] - mid, axis=1)))
    hops = _hops(nch, edges, entry)
    reach = hops >= 0

    # Ridge widths: twice the boundary distance at local maxima of it, a
    # sample of the floor's corridor and room widths.
    g = floor.graph.tocoo()
    nb_max = np.zeros(floor.n)
    np.maximum.at(nb_max, g.row, floor.dist[g.col])
    ridge = 2 * floor.dist[(floor.dist >= nb_max) & ~floor.boundary]

    med = float(np.median(sizes)) if nch else 0.0
    cls = np.searchsorted(SIZE_BOUNDS, sizes / med) if nch else np.zeros(0, int)
    return {
        "zone": zone, "floor": floor, "chamber": chamber, "nch": nch,
        "edges": edges, "sizes": sizes, "centres": centres, "deg": deg,
        "components": int(ncomp),
        "cycle_rank": len(edges) - nch + int(ncomp),
        "dead_end": float((deg == 1).mean()) if nch else 0.0,
        "deep_end": float(hops[reach].max() / nch) if nch else 0.0,
        "entry": entry, "entry_label": entry_label,
        "mix": np.bincount(cls, minlength=5) / max(nch, 1),
        "ridge": ridge, "map_lines": map_lines,
        "passage_share": float((chamber < 0).mean()),
    }


def plot(r: dict, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    f, ch = r["floor"], r["chamber"]
    fig, ax = plt.subplots(figsize=(14, 14), dpi=80)
    for ln in r["map_lines"]:
        x1, y1, _ = map_to_world(ln.x1, ln.y1, ln.z1)
        x2, y2, _ = map_to_world(ln.x2, ln.y2, ln.z2)
        ax.plot([x1, x2], [y1, y2], color="black", lw=0.6, zorder=1)
    pas = ch < 0
    ax.scatter(f.xy[pas, 0], f.xy[pas, 1], s=3, c="#bbbbbb", marker="s",
               linewidths=0, zorder=0)
    hues = np.random.default_rng(1).permutation(max(r["nch"], 1)) / max(r["nch"], 1)
    cols = plt.get_cmap("hsv")(hues)
    ax.scatter(f.xy[~pas, 0], f.xy[~pas, 1], s=3, marker="s", linewidths=0,
               c=cols[ch[~pas]], zorder=0, alpha=0.8)
    c = r["centres"]
    for i, j in r["edges"]:
        ax.plot([c[i, 0], c[j, 0]], [c[i, 1], c[j, 1]], color="red", lw=1.5, zorder=3)
    ax.scatter(c[:, 0], c[:, 1], s=30, c="red", zorder=4)
    for k, (x, y, _) in enumerate(c):
        ax.text(x, y, str(k), fontsize=7, color="blue", zorder=5)
    e = r["entry"]
    ax.scatter([c[e, 0]], [c[e, 1]], s=250, marker="*", c="lime",
               edgecolors="black", zorder=6)
    lo, hi = f.xy.min(0) - 40, f.xy.max(0) + 40
    ax.set_xlim(lo[0], hi[0])
    ax.set_ylim(lo[1], hi[1])
    ax.set_aspect("equal")
    ax.set_title(f"{r['zone']}: {r['nch']} chambers, {len(r['edges'])} edges "
                 f"(world XY, north up)")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def _p(v, qs=(10, 50, 90)) -> str:
    if len(v) == 0:
        return "-"
    return "/".join(f"{np.percentile(v, q):.0f}" for q in qs)


def _band(vals) -> str:
    return f"{np.percentile(vals, 10):.2f}-{np.percentile(vals, 90):.2f}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--eq-path", required=True, type=Path)
    ap.add_argument("--zones", default=",".join(CLASSIC + WARREN))
    ap.add_argument("--width", type=float, default=WIDTH,
                    help="chamber width threshold (u)")
    ap.add_argument("--exclude", default=",".join(EXCLUDED),
                    help="zones measured but left out of the bands")
    ap.add_argument("--neck", type=float, default=NECK,
                    help="doorway / room width ratio that splits two rooms")
    ap.add_argument("--plots", type=Path, help="write <zone>.png checks here")
    args = ap.parse_args(argv)
    agent = AgentModel()
    excluded = {z for z in args.exclude.split(",") if z}

    print(f"width threshold: {args.width:.0f} u (chamber = floor wider than this; "
          f"ours: corridor_width = max(40, side*0.25), 50 u at the default band)")
    print(f"neck split: {args.neck:.2f}; raster: {CELL:.0f} u cells; size classes at x{SIZE_CENTRES} of the "
          f"zone's median side")
    print()
    head = (f"{'zone':12s} {'N':>3s} {'side p10/50/90':>14s} {'deg 1/2/3/4/5+':>15s} "
            f"{'E':>3s} {'C':>2s} {'cyc':>3s} {'cyc/N':>5s} {'dead':>5s} {'deep':>5s} "
            f"{'mix t/s/m/l/h':>19s} {'pass':>5s} {'ridge p25/50':>12s}  entry")
    rows = {}
    for group, zones in (("classic", CLASSIC), ("warren-like", WARREN)):
        todo = [z for z in args.zones.split(",") if z in zones]
        if not todo:
            continue
        print(f"-- {group}")
        print(head)
        for zone in todo:
            try:
                r = survey(args.eq_path, zone, agent, args.width, neck=args.neck)
            except Exception as e:  # a zone missing from this install
                print(f"{zone:12s} error: {type(e).__name__}: {e}")
                continue
            if args.plots:
                args.plots.mkdir(parents=True, exist_ok=True)
                plot(r, args.plots / f"{zone}.png")
            rows[zone] = (group, r)
            h = np.bincount(np.minimum(r["deg"], 5), minlength=6)
            hist = "/".join(str(x) for x in h[1:])
            if h[0]:
                hist += f" +{h[0]}iso"
            mix = "/".join(f"{m*100:.0f}" for m in r["mix"])
            tag = " (excluded)" if zone in excluded else ""
            print(f"{zone:12s} {r['nch']:3d} {_p(r['sizes']):>14s} {hist:>15s} "
                  f"{len(r['edges']):3d} {r['components']:2d} {r['cycle_rank']:3d} "
                  f"{r['cycle_rank']/max(r['nch'],1):5.2f} {r['dead_end']:5.2f} "
                  f"{r['deep_end']:5.2f} {mix:>19s} {r['passage_share']:5.0%} "
                  f"{_p(r['ridge'], (25, 50)):>12s}  {r['entry_label']}{tag}")
        print()

    for zone in sorted(excluded & set(rows)):
        print(f"excluded {zone}: {EXCLUDED.get(zone, 'by --exclude')}")
    print()
    for group in ("classic", "warren-like"):
        kept = [r for z, (g, r) in rows.items() if g == group and z not in excluded]
        if not kept:
            continue
        print(f"bands ({group}, p10-p90 over {len(kept)} zones: "
              f"{', '.join(r['zone'] for r in kept)})")
        print(f"  dead-end share   {_band([r['dead_end'] for r in kept])}")
        print(f"  cycle rank / N   {_band([r['cycle_rank'] / r['nch'] for r in kept])}")
        print(f"  deep-end dist    {_band([r['deep_end'] for r in kept])}")
        print(f"  chambers         {_band([r['nch'] for r in kept])}")
        print(f"  median side (u)  {_band([np.median(r['sizes']) for r in kept])}")
        print(f"  passage share    {_band([r['passage_share'] for r in kept])}")
        for k, name in enumerate(SIZE_CLASSES):
            print(f"  {name:6s} share     {_band([r['mix'][k] for r in kept])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
