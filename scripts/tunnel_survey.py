r"""Measure how stock cave tunnels wind (step 23, task 1).

Reads each zone as ``scripts/wall_survey.py`` does (its floor faces, cached with
``--cache``), rasters the floor and splits it into chambers with step 6's survey
(``dungeon_topology_survey.split``, width threshold ``WIDTH`` = 40 u):

1. **Tunnels.** Floor narrower than ``WIDTH`` (no node more than 20 u from the
   floor's edge) is passage; wider floor, grown back out to its walls, is
   chamber. Tunnel floor is passage at least ``BUFFER`` along the floor from
   every chamber, so the strip of passage hugging a chamber's wall (an alcove
   the chamber didn't grow into) drops out. A tunnel is a connected piece of
   tunnel floor whose mouths (its nodes just past the buffer) reach at least two
   chambers. A piece touching k >= 3 chambers is a junction; it gives one
   tunnel per edge of the shortest tree between its chamber mouths, as the
   topology survey counts its edges. Passage touching fewer than two chambers
   (dead ends, tunnel-only levels) is left out, and so is a tunnel whose
   centreline runs under ``MIN_LENGTH`` (a doorway, not a tunnel).
2. **Centreline.** The cheapest path through the passage from one chamber's
   mouth to the other's, where a step costs its length times
   ``(widest / local)^2`` (local = the node's distance to the floor's edge), so
   the path keeps to the middle of the floor. It is smoothed (a running mean of
   ``SMOOTH`` nodes) and simplified with Ramer-Douglas-Peucker at ``EPS`` of the
   tunnel's median width (never under one raster cell): the polyline. Each
   run's heading is a line fitted to its middle (``TRIM`` cut at each end), not
   its chord, which cuts the rounded corner and reads every turn short.
3. **Measures**, in plan:
   - segment: the length of each polyline segment with a turn at both ends
     (the run between turns; the first and last are the ends, below);
   - turn: the angle between consecutive runs' headings (degrees, unsigned);
   - wander: the smoothed path's largest sideways offset from the straight
     line between its ends, over that line's length (the span);
   - width: twice the distance to the floor's edge along the centreline;
   - end: the first and last segment's lengths (the straight at each mouth);
   - span and centreline: the straight distance between the mouths and the
     polyline's length (pooled p10/p25/p50/p75/p90; task 9 sets the cave
     profile's corridor run from them).

Per tunnel it prints these (p10/p50/p90 where there are several), per zone and
pooled over all zones (every tunnel, and again without junction legs), then a
proposal for ``[tunnel]`` in ``rules/walls/rough.toml``: segment p10-p90,
max_turn p90, wander p50, end p10, all over every tunnel.

Floors on other levels share a plan, so a centreline drawn over a chamber in
the plots is usually a tunnel under or over it. ``--eps`` moves the polyline
tolerance: turns grow and segments lengthen with it (a coarser line merges two
small bends into one).

Usage::

    python scripts/tunnel_survey.py --eq-path F:\everquest_rof2
    python scripts/tunnel_survey.py --zones blackburrow --cache %TEMP%\walls\cache \
        --plots %TEMP%\tunnels

``--eq-path`` defaults to ``$EQ_PATH``.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from analyzer.traverse import AgentModel  # noqa: E402
from dungeon_topology_survey import CELL, Floor, split  # noqa: E402

WIDTH = 40.0        # passage is floor narrower than this (u), as the topology survey
BUFFER = 8.0        # tunnel floor keeps this far off every chamber (u, along the floor)
MIN_LENGTH = 32.0   # a tunnel's centreline runs at least this far (u)
SMOOTH = 5          # running-mean window over the raster path (nodes)
EPS = 0.35          # simplification tolerance, a share of the tunnel's median width
MIN_EPS = CELL      # and never under one raster cell (u)
TRIM = 0.2          # a run's heading is fitted to its middle, this share cut at each end
SPAN_QS = (10, 25, 50, 75, 90)   # the span's percentiles (step 23 task 9: cave run length)

#: The rough-style zones ``rough.toml`` was measured on (``wall_survey.STYLES``).
ZONES = ("blackburrow", "paw", "crystal", "runnyeye", "soldungb", "soldunga", "permafrost")


# ---------------------------------------------------------------------------
# Polyline geometry
# ---------------------------------------------------------------------------

def smooth(path: np.ndarray, window: int = SMOOTH) -> np.ndarray:
    """A running mean along the path; the two ends stay put."""
    if len(path) < 3 or window < 2:
        return path.copy()
    h = window // 2
    pad = np.r_[np.repeat(path[:1], h, 0), path, np.repeat(path[-1:], h, 0)]
    c = np.cumsum(np.r_[np.zeros((1, path.shape[1])), pad], axis=0)
    out = (c[window:] - c[:-window]) / window
    out = out[: len(path)]
    out[0], out[-1] = path[0], path[-1]
    return out


def rdp(path: np.ndarray, eps: float) -> np.ndarray:
    """Ramer-Douglas-Peucker: the indices of the vertices of ``path`` kept at
    tolerance ``eps``."""
    keep = np.zeros(len(path), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(path) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, b = path[i], path[j]
        d = _offsets(path[i + 1:j], a, b)
        k = int(np.argmax(d))
        if d[k] > eps:
            m = i + 1 + k
            keep[m] = True
            stack += [(i, m), (m, j)]
    return np.nonzero(keep)[0]


def _offsets(pts: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Distance of each point from the line through a and b (from a, if a == b)."""
    ab = b - a
    n = np.linalg.norm(ab)
    if n < 1e-9:
        return np.linalg.norm(pts - a, axis=1)
    return np.abs(ab[0] * (pts[:, 1] - a[1]) - ab[1] * (pts[:, 0] - a[0])) / n


def _heading(path: np.ndarray, i: int, j: int, trim: float = TRIM) -> float:
    """The heading (radians) of the run ``path[i..j]``: the principal direction of its
    points, ``trim`` of them dropped at each end, pointed from i to j. The simplified
    polyline's own chords cut each rounded corner and read every turn short; a line
    fitted to the straight middle of each run does not."""
    pts = path[i:j + 1]
    cut = int(len(pts) * trim)
    if len(pts) - 2 * cut >= 3:
        pts = pts[cut:len(pts) - cut]
    chord = path[j] - path[i]
    if len(pts) < 3:
        return math.atan2(chord[1], chord[0])
    d = np.linalg.svd(pts - pts.mean(0), full_matrices=False)[2][0]
    if d @ chord < 0:
        d = -d
    return math.atan2(d[1], d[0])


def polyline_measures(path: np.ndarray, eps: float) -> dict:
    """Segments, turns and wander of a plan path (N x 2), simplified at ``eps``."""
    keep = rdp(path, eps)
    line = path[keep]
    seg = np.diff(line, axis=0)
    lengths = np.linalg.norm(seg, axis=1)
    ang = np.array([_heading(path, i, j) for i, j in zip(keep, keep[1:])])
    turns = np.degrees(np.abs((np.diff(ang) + np.pi) % (2 * np.pi) - np.pi))
    span = float(np.linalg.norm(path[-1] - path[0]))
    wander = float(_offsets(path, path[0], path[-1]).max() / span) if span > 0 else float("nan")
    return {"line": line, "segments": lengths[1:-1], "turns": turns, "span": span,
            "wander": wander, "length": float(lengths.sum()),
            "ends": np.array([lengths[0], lengths[-1]]), "all_segments": lengths}


# ---------------------------------------------------------------------------
# Tunnels
# ---------------------------------------------------------------------------

def _centre_path(floor: Floor, nodes: np.ndarray, src: np.ndarray, dst: np.ndarray):
    """Cheapest centre-hugging path through ``nodes`` from any of ``src`` to any of
    ``dst`` (indices into ``nodes``); returns floor node ids or None."""
    sub = floor.graph[nodes][:, nodes].tocoo()
    d = floor.dist[nodes]
    widest = d.max()
    local = 0.5 * (d[sub.row] + d[sub.col])
    w = sub.data * (widest / local) ** 2
    g = csr_matrix((w, (sub.row, sub.col)), shape=(len(nodes), len(nodes)))
    dist, pred = _multi_dijkstra(g, src)
    if not np.isfinite(dist[dst]).any():
        return None
    k = int(dst[np.argmin(dist[dst])])
    path = [k]
    while pred[k] >= 0:
        k = int(pred[k])
        path.append(k)
    return nodes[np.array(path[::-1])]


def _multi_dijkstra(g, src):
    """Shortest paths from a set of sources, as one search from a virtual source."""
    n = g.shape[0]
    g = g.tocoo()
    rows = np.r_[g.row, np.full(len(src), n)]
    cols = np.r_[g.col, src]
    data = np.r_[g.data, np.full(len(src), 1e-9)]
    big = csr_matrix((data, (rows, cols)), shape=(n + 1, n + 1))
    dist, pred = dijkstra(big, directed=True, indices=n, return_predecessors=True)
    pred = pred[:n].copy()
    pred[pred == n] = -9999
    return dist[:n], pred


def find_tunnels(floor: Floor, chamber: np.ndarray) -> list:
    """Each tunnel: its chamber pair, the floor nodes of its centreline, and whether
    it comes out of a junction."""
    # Distance along the floor to the nearest chamber, and which chamber that is.
    seeds = np.nonzero(chamber >= 0)[0]
    if not len(seeds):
        return []
    dch, _, src_of = dijkstra(floor.graph, directed=False, indices=seeds,
                              min_only=True, return_predecessors=True)
    near = np.full(floor.n, -1)
    ok = src_of >= 0
    near[ok] = chamber[src_of[ok]]
    # Tunnel floor keeps BUFFER off every chamber, so a strip of passage hugging
    # a chamber's wall (an alcove the chamber didn't grow into) is not a tunnel.
    tunnel = (chamber < 0) & (dch > BUFFER)
    idx = np.nonzero(tunnel)[0]
    sub = floor.graph[idx][:, idx]
    _, lab = connected_components(sub, directed=False)
    # A piece's mouth on a chamber: its nodes within one step of the buffer.
    mouth = tunnel & (dch <= BUFFER + 1.5 * CELL)
    mouths: dict = defaultdict(lambda: defaultdict(set))
    for k in np.nonzero(mouth[idx])[0]:
        mouths[int(lab[k])][int(near[idx[k]])].add(int(idx[k]))
    out = []
    for p, chs in mouths.items():
        ids = sorted(chs)
        if len(ids) < 2:
            continue
        nodes = idx[lab == p]
        local = {int(n): i for i, n in enumerate(nodes)}
        pos = {c: floor.xy[list(chs[c])].mean(0) for c in ids}
        # The shortest tree between the mouths, as the topology survey's edges.
        inside, rest, pairs = {ids[0]}, set(ids[1:]), []
        while rest:
            _, u, v = min((np.linalg.norm(pos[u] - pos[v]), u, v)
                          for u in inside for v in rest)
            pairs.append((u, v))
            inside.add(v)
            rest.discard(v)
        for u, v in pairs:
            src = np.array([local[n] for n in chs[u]])
            dst = np.array([local[n] for n in chs[v]])
            path = _centre_path(floor, nodes, src, dst)
            if path is not None and len(path) >= 2:
                out.append({"chambers": (u, v), "path": path, "junction": len(ids) > 2})
    return out


def measure_tunnel(floor: Floor, path: np.ndarray, eps_share: float = EPS) -> dict:
    xy = smooth(floor.xy[path])
    width = 2 * floor.dist[path]
    eps = max(MIN_EPS, eps_share * float(np.median(width)))
    m = polyline_measures(xy, eps)
    m["width"] = width
    m["smoothed"] = xy
    return m


def survey(floor: Floor, width: float = WIDTH, chamber: np.ndarray = None,
           eps_share: float = EPS) -> list:
    """Every tunnel of a floor, measured; short ones are dropped."""
    if chamber is None:
        chamber, _ = split(floor, width)
    out = []
    for t in find_tunnels(floor, chamber):
        m = measure_tunnel(floor, t["path"], eps_share)
        if m["length"] < MIN_LENGTH:
            continue
        m.update(t)
        out.append(m)
    return out


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _p(v, qs=(10, 50, 90), fmt="{:.0f}") -> str:
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    if not len(v):
        return "-"
    return "/".join(fmt.format(np.percentile(v, q)) for q in qs)


def plot(zone: str, floor: Floor, chamber: np.ndarray, tunnels: list, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(14, 14), dpi=80)
    ax.scatter(floor.xy[:, 0], floor.xy[:, 1], s=3, marker="s", linewidths=0,
               c=np.where(chamber >= 0, "#e8c48a", "#cccccc"))
    for k, t in enumerate(tunnels):
        ax.plot(*t["smoothed"].T, color="tab:blue", lw=0.8)
        ax.plot(*t["line"].T, color="tab:red", lw=1.4, marker="o", ms=3)
        ax.text(*t["line"][len(t["line"]) // 2], str(k), fontsize=8, color="black")
    ax.set_aspect("equal")
    ax.set_title(f"{zone}: {len(tunnels)} tunnels (blue: centre path, red: polyline)")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)


def load_floor(eq_path: Path, zone: str, agent: AgentModel, cache: Path = None) -> Floor:
    from outdoor_dungeon_survey import load_mesh
    from wall_survey import stock_faces
    if cache is not None and (cache / f"{zone}.npz").exists():
        floor_tris = np.load(cache / f"{zone}.npz")["floor"]
    else:
        floor_tris, _ = stock_faces(eq_path, zone, load_mesh(eq_path, zone), agent, cache)
    return Floor(floor_tris, agent)


def _cat(tunnels: list, key: str) -> np.ndarray:
    return np.concatenate([np.asarray(t[key], float).ravel() for t in tunnels] or [[]])


def _pooled(tunnels: list, label: str) -> None:
    print(f"\nPooled, {label}, {len(tunnels)} tunnels (p10 / p50 / p90):")
    print(f"  segment (u)      {_p(_cat(tunnels, 'segments')):>11}   ({len(_cat(tunnels, 'segments'))} segments)")
    print(f"  turn (deg)       {_p(_cat(tunnels, 'turns')):>11}   ({len(_cat(tunnels, 'turns'))} turns)")
    print(f"  wander (/ span)  {_p([t['wander'] for t in tunnels], fmt='{:.2f}'):>11}")
    print(f"  width (u)        {_p(_cat(tunnels, 'width')):>11}")
    print(f"  end straight (u) {_p(_cat(tunnels, 'ends')):>11}")
    spans = [t["span"] for t in tunnels]
    lengths = [t["length"] for t in tunnels]
    print(f"  span (u)         {_p(spans, SPAN_QS):>19}   (p10/p25/p50/p75/p90, mouth to mouth)")
    print(f"  centreline (u)   {_p(lengths, SPAN_QS):>19}   (p10/p25/p50/p75/p90, along the polyline)")


def proposal(tunnels: list) -> tuple:
    """``[tunnel]`` values: segment p10-p90, max_turn p90, wander p50, end p10."""
    seg = np.percentile(_cat(tunnels, "segments"), [10, 90])
    turn = float(np.percentile(_cat(tunnels, "turns"), 90))
    wander = float(np.nanmedian([t["wander"] for t in tunnels]))
    end = float(np.percentile(_cat(tunnels, "ends"), 10))
    return seg, turn, wander, end


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--eq-path", type=Path, default=os.environ.get("EQ_PATH"))
    ap.add_argument("--zones", default=",".join(ZONES))
    ap.add_argument("--width", type=float, default=WIDTH, help="passage width threshold (u)")
    ap.add_argument("--eps", type=float, default=EPS,
                    help="polyline tolerance, a share of the tunnel's median width")
    ap.add_argument("--cache", type=Path, help="keep each zone's faces here (wall_survey's cache)")
    ap.add_argument("--plots", type=Path, help="write <zone>.png here")
    ap.add_argument("--quiet", action="store_true", help="zone totals only, no per-tunnel rows")
    args = ap.parse_args(argv)
    if args.eq_path is None:
        ap.error("--eq-path or $EQ_PATH is required")
    agent = AgentModel()
    every = []
    print(f"passage < {args.width:.0f} u wide; tunnels >= {MIN_LENGTH:.0f} u; polyline tolerance "
          f"{args.eps:.2f} x width (>= {MIN_EPS:.0f} u). Columns p10/p50/p90; * = junction leg.")
    for zone in args.zones.split(","):
        floor = load_floor(args.eq_path, zone, agent, args.cache)
        chamber, _ = split(floor, args.width)
        tunnels = survey(floor, args.width, chamber, args.eps)
        every += tunnels
        if args.plots:
            plot(zone, floor, chamber, tunnels, args.plots / f"{zone}.png")
        print(f"\n-- {zone}: {len(tunnels)} tunnels")
        if not args.quiet:
            print(f"{'#':>3} {'ch':>7} {'len':>5} {'span':>5} {'segs':>4} {'segment':>11} "
                  f"{'turn':>11} {'wander':>6} {'width':>9} {'ends':>9}")
            for k, t in enumerate(tunnels):
                print(f"{k:3d} {'%d-%d' % t['chambers']:>7}{'*' if t['junction'] else ' '}"
                      f"{t['length']:5.0f} {t['span']:5.0f} {len(t['all_segments']):4d} "
                      f"{_p(t['segments']):>11} {_p(t['turns']):>11} {t['wander']:6.2f} "
                      f"{_p(t['width']):>9} {'%.0f/%.0f' % tuple(t['ends']):>9}")
        if tunnels:
            print(f"   zone: segment {_p(_cat(tunnels, 'segments'))}, "
                  f"turn {_p(_cat(tunnels, 'turns'))}, "
                  f"wander {_p([t['wander'] for t in tunnels], fmt='{:.2f}')}, "
                  f"width {_p(_cat(tunnels, 'width'))}")
    _pooled(every, "every tunnel")
    _pooled([t for t in every if not t["junction"]], "plain tunnels (no junction legs)")
    seg, turn, wander, end = proposal(every)
    print("\nProposed [tunnel] (segment p10-p90, max_turn p90, wander p50, end p10; every tunnel):")
    print(f"  segment = [{seg[0]:.0f}, {seg[1]:.0f}]\n  max_turn = {turn:.0f}\n"
          f"  wander = {wander:.2f}\n  end = {end:.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
