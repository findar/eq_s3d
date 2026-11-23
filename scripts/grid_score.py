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

``--shapes`` (task 9, Requirements 7-8) prints instead what the eye sees, per kind
of build (``KINDS``: cave, fortress, temple and warren Graph, outdoor dungeon
Graph, classic fortress, city; the same seeds and room counts):

- ax10: the share of graph edges (corridors) whose centre-to-centre bearing is
  within 10 deg of N/S/E/W; uniform bearings give 0.22. axbst: the same at the
  grid rotation catching most (a stock zone may sit off the world axes;
  uniform bearings give about 0.3 there for a dozen edges). ``hist``: the
  offsets from the nearest axis in 5 deg bins (0-5 ... 40-45), as shares.
- nn: each room's nearest other room centre (3D, floor height); its CV over the rooms, and
  min/median/max over the zone's median room side (clumping: a min well under
  1 is rooms nearly touching).
- entry: the angle between a corridor's first leg (its ``path`` or route) and
  the outward normal of the wall it leaves, at both ends; p50/p90 and the share
  over 20 deg.
- side: sqrt(width x depth): min and max over the zone's median, p10-p90 over
  the median (pooled), and p10/p50/p90 in H (the race's body height). Aspect
  long/short p50/p90/max and share over 1.5 (pooled); area CV and max/min. Per-zone
  values (grid, axbst, nn, side mn/mx, area) are the median over the zones.

``measure_shape`` takes centres, edges and room footprints only, so
``scripts/stock_room_shapes.py`` judges stock chambers with the same code.
``--one SEED --rooms N --vert V`` measures one build per kind (the first-look
cave: ``--shapes --kinds cave --one 731402518 --rooms 12 --vert moderate``).
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


# ---------------------------------------------------------------------------
# What the eye sees (task 9): shared with scripts/stock_room_shapes.py
# ---------------------------------------------------------------------------

AXIS_TOL_DEG = 10.0
HIST_BIN = 5.0

#: Kinds of build for ``--shapes``: the controls each draws.
KINDS = {
    "cave": {"zone_type": "dungeon", "dungeon_theme": "cave", "layout": "graph"},
    "fortress": {"zone_type": "dungeon", "dungeon_theme": "fortress", "layout": "graph"},
    "temple": {"zone_type": "dungeon", "dungeon_theme": "temple", "layout": "graph"},
    "warren": {"zone_type": "dungeon", "dungeon_theme": "warren", "layout": "graph"},
    "outdoor": {"zone_type": "outdoor_dungeon", "layout": "graph"},
    "classic_fortress": {"zone_type": "dungeon", "dungeon_theme": "fortress",
                         "layout": "classic"},
    "city": {"zone_type": "city"},
}


def axis_offsets(centres, edges):
    """Each edge's centre-to-centre bearing's offset from the nearest axis (deg, 0-45),
    and the raw bearings (deg, 0-180)."""
    bear = []
    for i, j in edges:
        dx, dy = centres[j][0] - centres[i][0], centres[j][1] - centres[i][1]
        if dx or dy:
            bear.append(math.degrees(math.atan2(dy, dx)) % 180.0)
    off = [abs((b + 45.0) % 90.0 - 45.0) for b in bear]
    return off, bear


def best_axis_share(bearings, tol: float = AXIS_TOL_DEG) -> float:
    """The axis share at the grid rotation (whole degrees) catching most bearings."""
    if not bearings:
        return float("nan")
    best = 0
    for th in range(90):
        best = max(best, sum(abs((b - th + 45.0) % 90.0 - 45.0) < tol for b in bearings))
    return best / len(bearings)


def nearest_neighbours(centres):
    """Each centre's nearest other centre (u, in 3D: stacked rooms aren't neighbours)."""
    out = []
    for k, a in enumerate(centres):
        d = [math.dist(a, b) for m, b in enumerate(centres) if m != k]
        if d:
            out.append(min(d))
    return out


def _cv(v):
    v = list(v)
    if len(v) < 2 or not statistics.fmean(v):
        return 0.0
    return statistics.pstdev(v) / statistics.fmean(v)


def measure_shape(centres, edges, sides, aspects, areas, h: float) -> dict:
    """The task-9 measures of one zone: centres (x, y[, z]), edges (index pairs),
    per room side (u), aspect (long/short) and area (u^2); ``h`` the race's H."""
    off, bear = axis_offsets(centres, edges)
    hist = [0] * int(45 / HIST_BIN)
    for o in off:
        hist[min(len(hist) - 1, int(o // HIST_BIN))] += 1
    nn = nearest_neighbours(centres)
    med = statistics.median(sides)
    nan = float("nan")
    return {
        "edges": len(off),
        "axis10": (sum(o < AXIS_TOL_DEG for o in off) / len(off)) if off else nan,
        "axis10_best": best_axis_share(bear), "hist": hist, "offsets": off,
        "nn_cv": _cv(nn), "nn_min": min(nn) / med if nn else nan,
        "nn_med": statistics.median(nn) / med if nn else nan,
        "nn_max": max(nn) / med if nn else nan,
        "side_min": min(sides) / med, "side_max": max(sides) / med,
        "side_rel": [x / med for x in sides], "side_h": [x / h for x in sides],
        "aspects": list(aspects), "area_cv": _cv(areas),
        "area_ratio": max(areas) / min(areas) if min(areas) > 0 else nan,
    }


def _wall_normal(room, x, y):
    """The outward normal of the room wall nearest (x, y)."""
    dx, dy = x - room.center_x, y - room.center_y
    ex, ey = abs(abs(dx) - room.width / 2), abs(abs(dy) - room.depth / 2)
    return (math.copysign(1.0, dx), 0.0) if ex <= ey else (0.0, math.copysign(1.0, dy))


def angle_between(u, v) -> float:
    nu, nv = math.hypot(*u), math.hypot(*v)
    if not nu or not nv:
        return float("nan")
    c = max(-1.0, min(1.0, (u[0] * v[0] + u[1] * v[1]) / (nu * nv)))
    return math.degrees(math.acos(c))


def entry_angles(spec):
    """Per corridor end: the angle (deg) between its first leg and its wall's outward normal."""
    from generators.routing import corridor_route
    by = {r.id: r for r in spec.rooms}
    out = []
    for cor in spec.corridors:
        if cor.from_room not in by or cor.to_room not in by:
            continue
        line = [tuple(p) for p in (cor.path or list(corridor_route(cor, by).waypoints))]
        line = [p for k, p in enumerate(line) if k == 0 or math.dist(p, line[k - 1]) > 1e-6]
        if len(line) < 2:
            continue
        for room, a, b in ((by[cor.from_room], line[0], line[1]),
                           (by[cor.to_room], line[-1], line[-2])):
            out.append(angle_between((b[0] - a[0], b[1] - a[1]), _wall_normal(room, *a)))
    return [x for x in out if x == x]


def spec_shape(spec) -> dict:
    """``measure_shape`` of a ZoneSpec, plus its entry angles and grid score."""
    from generators import semantics
    idx = {r.id: k for k, r in enumerate(spec.rooms)}
    centres = [(r.center_x, r.center_y, r.floor_z) for r in spec.rooms]
    edges = sorted({tuple(sorted((idx[c.from_room], idx[c.to_room]))) for c in spec.corridors
                    if c.from_room in idx and c.to_room in idx and c.from_room != c.to_room})
    m = measure_shape(centres, edges,
                      [math.sqrt(r.width * r.depth) for r in spec.rooms],
                      [max(r.width, r.depth) / min(r.width, r.depth) for r in spec.rooms],
                      [r.width * r.depth for r in spec.rooms],
                      semantics.body_height(spec.dungeon_race or "default"))
    m["entry"] = entry_angles(spec)
    m["grid"] = grid_score(spec)
    return m


def one_shape(job):
    kind, seed, rooms, vert = job
    os.chdir(ROOT)
    from ai.expand import plan_to_spec
    from ai.schema import ZonePlan
    plan = ZonePlan.from_controls(dict(KINDS[kind], room_count=rooms, verticality=vert), [])
    plan.name = f"shape_{kind}_{seed}"
    spec = plan_to_spec(plan, seed=seed, warnings=[])
    m = spec_shape(spec)
    m.update(kind=kind, seed=seed, rooms=len(spec.rooms))
    return m


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(round(q / 100 * (len(v) - 1))))] if v else float("nan")


def summarise_shapes(rows) -> dict:
    """Pool the per-zone measures of each kind (``kind`` key) into one row."""
    nan = float("nan")
    out = {}
    for kind in dict.fromkeys(r["kind"] for r in rows):
        rs = [r for r in rows if r["kind"] == kind]
        off = [o for r in rs for o in r["offsets"]]
        hist = [sum(r["hist"][b] for r in rs) for b in range(len(rs[0]["hist"]))]
        ent = [a for r in rs for a in r.get("entry", [])]
        asp = [a for r in rs for a in r["aspects"]]
        rel = [a for r in rs for a in r["side_rel"]]
        sh = [a for r in rs for a in r["side_h"]]

        def fm(k):     # the median zone (a few open zones would swamp a mean)
            v = [r[k] for r in rs if k in r and r[k] == r[k]]
            return statistics.median(v) if v else nan
        out[kind] = {
            "n": len(rs), "edges": len(off), "grid": fm("grid"),
            "axis10": sum(o < AXIS_TOL_DEG for o in off) / len(off) if off else nan,
            "axis10_best": fm("axis10_best"),
            "hist": [h / max(1, len(off)) for h in hist],
            "nn_cv": fm("nn_cv"), "nn_min": fm("nn_min"), "nn_med": fm("nn_med"),
            "nn_max": fm("nn_max"),
            "entry_p50": pct(ent, 50), "entry_p90": pct(ent, 90),
            "entry_over20": sum(a > 20 for a in ent) / len(ent) if ent else nan,
            "side_min": fm("side_min"), "side_max": fm("side_max"),
            "rel_p10": pct(rel, 10), "rel_p90": pct(rel, 90),
            "h_p10": pct(sh, 10), "h_p50": pct(sh, 50), "h_p90": pct(sh, 90),
            "asp_p50": pct(asp, 50), "asp_p90": pct(asp, 90), "asp_max": max(asp),
            "asp_over15": sum(a > 1.5 for a in asp) / len(asp),
            "area_cv": fm("area_cv"), "area_ratio": fm("area_ratio"),
        }
    return out


def shape_table(s: dict) -> str:
    head = (f"{'kind':16s} {'n':>3s} {'grid':>5s} {'ax10':>5s} {'axbst':>5s} "
            f"{'nnCV':>5s} {'nn mn/md/mx':>14s} {'ent 50/90/>20':>14s} "
            f"{'side mn/mx':>10s} {'rel10-90':>9s} {'H 10/50/90':>14s} "
            f"{'asp 50/90/mx >1.5':>19s} {'arCV':>5s} {'mx/mn':>6s}")
    lines = [head]
    for kind, r in s.items():
        lines.append(
            f"{kind:16s} {r['n']:3d} {r['grid']:5.3f} {r['axis10']:5.2f} {r['axis10_best']:5.2f} "
            f"{r['nn_cv']:5.2f} {r['nn_min']:4.2f}/{r['nn_med']:4.2f}/{r['nn_max']:4.2f} "
            f"{r['entry_p50']:4.0f}/{r['entry_p90']:3.0f}/{r['entry_over20']:4.2f} "
            f"{r['side_min']:4.2f}/{r['side_max']:4.2f} {r['rel_p10']:4.2f}-{r['rel_p90']:4.2f} "
            f"{r['h_p10']:4.1f}/{r['h_p50']:4.1f}/{r['h_p90']:4.1f} "
            f"{r['asp_p50']:4.2f}/{r['asp_p90']:4.2f}/{r['asp_max']:4.2f} {r['asp_over15']:4.2f} "
            f"{r['area_cv']:5.2f} {r['area_ratio']:6.1f}")
    lines.append("bearing offsets from the nearest axis, 5 deg bins 0-45 (shares of edges):")
    for kind, r in s.items():
        lines.append(f"  {kind:14s} " + " ".join(f"{h:4.2f}" for h in r["hist"]))
    return "\n".join(lines)


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
    ap.add_argument("--shapes", action="store_true",
                    help="print what the eye sees per kind (task 9) instead")
    ap.add_argument("--kinds", nargs="+", default=list(KINDS))
    ap.add_argument("--one", type=int, help="--shapes: one build of this seed per kind")
    ap.add_argument("--rooms", type=int, default=12)
    ap.add_argument("--vert", default="moderate")
    a = ap.parse_args(argv)
    if a.shapes:
        if a.one is not None:
            sjobs = [(k, a.one, a.rooms, a.vert) for k in a.kinds]
        else:
            sjobs = [(k, FIRST_SEED + i, 8 + i % 23, VERTS[i % 3])
                     for k in a.kinds for i in range(a.seeds)]
        with ProcessPoolExecutor(a.jobs) as ex:
            srows = list(ex.map(one_shape, sjobs, chunksize=2))
        snow = summarise_shapes(srows)
        print(shape_table(snow))
        if a.json:
            Path(a.json).write_text(json.dumps(snow, indent=1))
        return
    jobs =[(t, i) for t in a.themes for i in range(a.seeds)]
    with ProcessPoolExecutor(a.jobs) as ex:
        rows = list(ex.map(one, jobs, chunksize=2))
    now = summarise(rows)
    before = json.loads(Path(a.compare).read_text()) if a.compare else None
    print(table(now, before))
    if a.json:
        Path(a.json).write_text(json.dumps(now, indent=1))


if __name__ == "__main__":
    main()
