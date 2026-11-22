"""Grid score and the placement's side effects, per Graph dungeon theme
(random-placement step 27, task 1; design "Measuring set").

For each theme, Graph builds over seeds 2000-2039 (seed 2000 + i: 8 + i % 23
rooms, verticality flat / moderate / dramatic by i % 3, defaults otherwise,
drawn as a controls generate draws them: ``ZonePlan.from_controls`` then
``plan_to_spec``). Per theme it prints:

- grid: the share of room-centre pairs whose x or y agree within 10 u (mean,
  p90, max over the builds). Scattered rooms score 0.06-0.09.
- d2d p50: the median corridor length door to door (u), over every corridor
  of every build (its ``path`` when it has one, else its route's waypoints).
- broken: ``relations_broken`` summed over the builds (vertical relations
  whose final floors don't hold).
- fidelity: mean ``edge_fidelity`` (the grown edges Job B still built).
- cycles, dead: the built graph's cycles per room and dead-end share (the
  corridors' graph, ``tests/test_topology_embed._built_shape``), means.
- jit: the builds whose layout record says ``jitter``.

Usage (from the repo root):
    python scripts/grid_score.py [--themes T ...] [--seeds N] [--jobs 4]
                                 [--json out.json] [--compare before.json]

``--compare`` prints the before (that file) and now side by side, with the
door-to-door ratio against the 4/3 limit.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

THEMES = ["fortress", "war_city", "temple", "tomb", "wizard_lair", "corrupted_sanctum",
          "mine_delve", "sunken_ruin", "lava_forge", "ice_keep", "warren", "cave"]
VERTS = ("flat", "moderate", "dramatic")
FIRST_SEED = 2000
TOL = 10.0


def grid_score(spec, tol: float = TOL) -> float:
    """Share of room-centre pairs whose x or y agree within ``tol``."""
    pts = [(r.center_x, r.center_y) for r in spec.rooms]
    pairs = list(combinations(pts, 2))
    if not pairs:
        return 0.0
    return sum(abs(a[0] - b[0]) < tol or abs(a[1] - b[1]) < tol for a, b in pairs) / len(pairs)


def built_shape(spec, record):
    """Cycles per room and dead-end share of the corridors' graph."""
    n = len(spec.rooms)
    adj = {r.id: set() for r in spec.rooms}
    for c in spec.corridors:
        adj[c.from_room].add(c.to_room)
        adj[c.to_room].add(c.from_room)
    pairs = sum(len(v) for v in adj.values()) // 2
    return (pairs - n + 1) / n, sum(1 for v in adj.values() if len(v) == 1) / n


def one(job):
    theme, i = job
    os.chdir(ROOT)
    from ai.expand import plan_to_spec
    from ai.schema import ZonePlan
    from generators.routing import corridor_route
    seed = FIRST_SEED + i
    plan = ZonePlan.from_controls({"zone_type": "dungeon", "dungeon_theme": theme,
                                   "layout": "graph", "room_count": 8 + i % 23,
                                   "verticality": VERTS[i % 3]}, [])
    plan.name = f"grid_{theme}_{seed}"
    spec = plan_to_spec(plan, seed=seed, warnings=[])
    by = {r.id: r for r in spec.rooms}
    d2d = []
    for cor in spec.corridors:
        line = cor.path or list(corridor_route(cor, by).waypoints)
        d2d.append(sum(math.dist(a, b) for a, b in zip(line, line[1:])))
    rec = spec.layout or {}
    cyc, dead = built_shape(spec, rec)
    return {"theme": theme, "seed": seed, "rooms": len(spec.rooms),
            "grid": grid_score(spec), "d2d": d2d,
            "broken": rec.get("relations_broken") or 0,
            "fidelity": rec.get("edge_fidelity", 1.0), "cycles": cyc, "dead": dead,
            "jitter": bool(rec.get("jitter"))}


def summarise(rows):
    out = {}
    for theme in dict.fromkeys(r["theme"] for r in rows):
        rs = [r for r in rows if r["theme"] == theme]
        g = sorted(r["grid"] for r in rs)
        d = [x for r in rs for x in r["d2d"]]
        out[theme] = {
            "n": len(rs), "grid": statistics.fmean(g), "grid_p90": g[int(0.9 * (len(g) - 1))],
            "grid_max": g[-1], "d2d_p50": statistics.median(d) if d else float("nan"),
            "broken": sum(r["broken"] for r in rs),
            "fidelity": statistics.fmean(r["fidelity"] for r in rs),
            "cycles": statistics.fmean(r["cycles"] for r in rs),
            "dead": statistics.fmean(r["dead"] for r in rs),
            "jit": sum(r["jitter"] for r in rs)}
    return out


def table(now, before=None):
    head = (f"{'theme':18s} {'grid':>6s} {'p90':>6s} {'max':>6s} {'d2d p50':>8s} "
            f"{'broken':>6s} {'fidel':>6s} {'cycles':>6s} {'dead':>6s} {'jit':>4s}")
    lines = [head]
    for theme, s in now.items():
        lines.append(f"{theme:18s} {s['grid']:6.3f} {s['grid_p90']:6.3f} {s['grid_max']:6.3f} "
                     f"{s['d2d_p50']:8.1f} {s['broken']:6d} {s['fidelity']:6.3f} "
                     f"{s['cycles']:6.3f} {s['dead']:6.3f} {s['jit']:4d}")
        if before and theme in before:
            b = before[theme]
            lines.append(f"{'  before':18s} {b['grid']:6.3f} {b['grid_p90']:6.3f} {b['grid_max']:6.3f} "
                         f"{b['d2d_p50']:8.1f} {b['broken']:6d} {b['fidelity']:6.3f} "
                         f"{b['cycles']:6.3f} {b['dead']:6.3f} {b['jit']:4d}"
                         f"   d2d x{s['d2d_p50'] / b['d2d_p50']:.3f} (limit 1.333)")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--themes", nargs="+", default=THEMES)
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--json", help="write the per-theme summary here")
    ap.add_argument("--compare", help="a --json summary to print beside this one")
    a = ap.parse_args(argv)
    jobs = [(t, i) for t in a.themes for i in range(a.seeds)]
    with ProcessPoolExecutor(a.jobs) as ex:
        rows = list(ex.map(one, jobs, chunksize=2))
    now = summarise(rows)
    before = json.loads(Path(a.compare).read_text()) if a.compare else None
    print(table(now, before))
    if a.json:
        Path(a.json).write_text(json.dumps(now, indent=1))


if __name__ == "__main__":
    main()
