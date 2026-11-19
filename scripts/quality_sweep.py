r"""Sweep the quality meter over the generator's own specs (zone-generator-quality task 2).

Draws specs the way a controls generate does (``ZonePlan.from_controls`` then
``plan_to_spec``, no build) for every enabled zone type that has rooms, both
layouts where the type has an engine (``LAYOUT_ZONE_TYPES``), each verticality,
and room counts cycling through 4..30. Each Draw's dungeon theme is picked at
random from "" (none) and every theme, since the key doesn't hold the theme and
ordinary output mixes them. Wilderness has no rooms (every band unbounded), so
it isn't swept.

Each Draw is measured with ``quality.measure`` against the current
``BAND_TABLE`` and timed. Writes one CSV row per Draw to
``output/quality_sweep.csv`` and prints, per key (zone type, layout,
verticality) and room-count row of the band table, each metric's quantiles,
then per key the share of Draws failing the bands, the expected Draws per
generate (1 / pass share, capped by the pipeline's 32), the Draw time and a few
failing seeds with the controls that reproduce them.

    python scripts/quality_sweep.py --per-key 40
    python scripts/quality_sweep.py --per-key 600 --jobs 6 --svg 4

``--svg N`` writes the top-down maps (``generators/mapview.py``) of up to N
failing specs per key to ``output/quality_sweep_svg/``, to look at before
calling them dull.
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ai.schema import LAYOUT_ZONE_TYPES, VALID_DUNGEON_THEMES  # noqa: E402
from generators import quality  # noqa: E402
from generators.zone_types import enabled_zone_types  # noqa: E402

VERTICALITIES = ("flat", "moderate", "dramatic")
ROOM_COUNTS = range(4, 31)
THEMES = ("",) + tuple(VALID_DUNGEON_THEMES)
MAX_DRAWS = 32          # the pipeline's quality Draw cap (Requirement 3.1)
QUANTILES = (0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99)
# Room-count rows the quantiles are printed by when a key has no band rows yet.
DEFAULT_ROWS = ((4, 5), (6, 9), (10, 15), (16, 22), (23, 30))


def keys():
    """(zone_type, layout, verticality) for every enabled zone type with rooms."""
    out = []
    for zt in sorted(enabled_zone_types()):
        if zt == "wilderness":
            continue
        layouts = ("classic", "graph") if zt in LAYOUT_ZONE_TYPES else ("classic",)
        for layout in layouts:
            for v in VERTICALITIES:
                out.append((zt, layout, v))
    return out


def controls(zone_type, layout, verticality, rooms, theme):
    """The controls a generate would send for this Draw."""
    c = {"zone_type": zone_type, "room_count": rooms, "verticality": verticality}
    if zone_type in LAYOUT_ZONE_TYPES:
        c["layout"] = layout
    if theme:
        c["dungeon_theme"] = theme
    return c


def draw(job):
    """One Draw: the spec for ``seed`` under the job's controls, measured and timed."""
    zone_type, layout, verticality, rooms, theme, seed = job
    from ai.expand import plan_to_spec
    from ai.schema import ZonePlan
    plan = ZonePlan.from_controls(controls(zone_type, layout, verticality, rooms, theme), [])
    plan.name = "sweep"
    from generators.outdoor_dungeon import PLAN_ERRORS
    row = {"zone_type": zone_type, "layout": layout, "verticality": verticality,
           "room_count": rooms, "n_rooms": 0, "theme": theme, "seed": seed}
    t0 = time.perf_counter()
    try:
        spec = plan_to_spec(plan, seed=seed)
    except PLAN_ERRORS as e:
        # The pipeline retries such a seed like a gate failure; not a quality Draw.
        row.update(draw_s=round(time.perf_counter() - t0, 4), plan_error=type(e).__name__,
                   passed="", score="", out_of_band="", **{m: "" for m in quality.METRICS})
        return row
    dt = time.perf_counter() - t0
    report = quality.measure(spec, verticality=verticality)
    row.update(layout=quality.spec_layout(spec), n_rooms=len(spec.rooms),
               draw_s=round(dt, 4), plan_error="", passed=int(report.passed),
               score=round(report.score, 6),
               out_of_band=" ".join(o.metric for o in report.out_of_band))
    row.update(report.metrics)
    return row


def quantile(xs, q):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    i = q * (len(xs) - 1)
    lo = int(i)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def row_ranges(key):
    rows = quality.BAND_TABLE.get(key)
    return [(lo, hi) for lo, hi, _ in rows] if rows else list(DEFAULT_ROWS)


def write_svgs(rows, per_key, out_dir):
    from ai.expand import plan_to_spec
    from ai.schema import ZonePlan
    from generators.mapview import render_map_svg
    out_dir.mkdir(parents=True, exist_ok=True)
    done = defaultdict(int)
    for r in rows:
        key = (r["zone_type"], r["layout"], r["verticality"])
        if r["passed"] or done[key] >= per_key:
            continue
        done[key] += 1
        plan = ZonePlan.from_controls(controls(r["zone_type"], r["layout"], r["verticality"],
                                               r["room_count"], r["theme"]), [])
        plan.name = "sweep"
        spec = plan_to_spec(plan, seed=r["seed"])
        name = "_".join(str(x) for x in (*key, r["room_count"], r["theme"] or "none", r["seed"]))
        (out_dir / f"{name}.svg").write_text(render_map_svg(spec), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--per-key", type=int, default=40,
                    help="Draws per (zone type, layout, verticality) key")
    ap.add_argument("--seed", type=int, default=19, help="seed of the sweep's own rng")
    ap.add_argument("--jobs", type=int, default=1, help="worker processes")
    ap.add_argument("--only", default="", help="comma list of zone types to sweep")
    ap.add_argument("--csv", default=str(ROOT / "output" / "quality_sweep.csv"))
    ap.add_argument("--svg", type=int, default=0,
                    help="write maps of up to N failing specs per key")
    ap.add_argument("--fails", type=int, default=4, help="failing seeds listed per key")
    args = ap.parse_args(argv)

    rng = random.Random(args.seed)
    only = {s for s in args.only.split(",") if s}
    jobs = []
    for key in keys():
        if only and key[0] not in only:
            continue
        counts = list(ROOM_COUNTS)
        for i in range(args.per_key):
            if i % len(counts) == 0:
                rng.shuffle(counts)
            jobs.append((*key, counts[i % len(counts)], rng.choice(THEMES),
                         rng.randint(0, 2 ** 31 - 1)))

    t0 = time.perf_counter()
    if args.jobs > 1:
        with ProcessPoolExecutor(args.jobs) as ex:
            rows = list(ex.map(draw, jobs, chunksize=4))
    else:
        rows = [draw(j) for j in jobs]
    print(f"{len(rows)} Draws in {time.perf_counter() - t0:.0f} s")

    path = Path(args.csv)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"CSV: {path}")

    by_key = defaultdict(list)
    plan_errors = defaultdict(int)
    for r in rows:
        if r["plan_error"]:
            plan_errors[(r["zone_type"], r["layout"], r["verticality"])] += 1
            continue
        by_key[(r["zone_type"], r["layout"], r["verticality"])].append(r)

    qhead = " ".join(f"p{int(q * 100):02d}".rjust(8) for q in QUANTILES)
    for key, krows in by_key.items():
        for lo, hi in row_ranges(key):
            sub = [r for r in krows if lo <= r["n_rooms"] <= hi]
            if not sub:
                continue
            print(f"\n== {'/'.join(key)}  rooms {lo}-{hi}  ({len(sub)} Draws)")
            print(f"{'metric':<22}{qhead}")
            for m in quality.METRICS:
                vals = [r[m] for r in sub]
                print(f"{m:<22}" + " ".join(f"{quantile(vals, q):8.3f}" for q in QUANTILES))

    print("\n== bands: fail share, expected Draws per generate, Draw time")
    print(f"{'key':<34}{'draws':>6}{'fail%':>7}{'E[draws]':>9}{'draw p50':>9}"
          f"{'p95':>7}{'max':>7}{'plan err':>9}  top out-of-band")
    for key, krows in by_key.items():
        n = len(krows)
        fails = [r for r in krows if not r["passed"]]
        p = len(fails) / n
        # Expected Draws with the 32 cap: sum of P(reaching Draw k).
        expect = sum(p ** k for k in range(MAX_DRAWS))
        times = [r["draw_s"] for r in krows]
        tally = defaultdict(int)
        for r in fails:
            for m in r["out_of_band"].split():
                tally[m] += 1
        top = ", ".join(f"{m} {c}" for m, c in sorted(tally.items(), key=lambda x: -x[1])[:4])
        print(f"{'/'.join(key):<34}{n:>6}{100 * p:>6.1f}%{expect:>9.3f}"
              f"{quantile(times, .5):>8.2f}s{quantile(times, .95):>6.2f}s"
              f"{max(times):>6.2f}s{plan_errors[key]:>9}  {top}")
    print("\n== failing seeds (controls + seed reproduce the spec)")
    for key, krows in by_key.items():
        fails = sorted((r for r in krows if not r["passed"]), key=lambda r: -r["score"])
        for r in fails[:args.fails]:
            c = controls(r["zone_type"], r["layout"], r["verticality"], r["room_count"],
                         r["theme"])
            print(f"{'/'.join(key):<34} seed {r['seed']:<11} score {r['score']:.3f}  "
                  f"{c}  out: {r['out_of_band']}")

    if args.svg:
        out = ROOT / "output" / "quality_sweep_svg"
        write_svgs(rows, args.svg, out)
        print(f"\nmaps: {out}")


if __name__ == "__main__":
    main()
