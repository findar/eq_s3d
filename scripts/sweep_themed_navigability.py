"""Content-layer navigability sweep.

Builds themed dungeon zones across archetypes x layouts x verticalities x room
counts x seeds and runs each through the generate path's gate: the spec is drawn
the way a controls generate draws it (``ZonePlan.from_controls`` then
``plan_to_spec``, Decor at its default), built, and judged with
``analyzer.traverse.validate(check_corridors=True)`` (every room reachable, every
corridor continuous) and the RoF2 Format_Checker. First written for the Step 1
content-layer re-sweep; step 21 (zone-generator-cave task 6) added ``cave``, the
layout, verticality and room-count axes, and parallel workers.

``--pair`` (zone-generator-district-looks task 5) sweeps districted dungeons
instead of one archetype per zone: the Districts switch on and the plan's
``district_plan`` pinning a ``cave`` District and a built one, the cave District
first (``cave_first``) or second (``cave_second``). Each build draws its built
Purpose from every non-cave archetype; with 14 or more rooms the third District
is left to the relationship. The CSV records the resolved District Purposes.

Usage:
    python -m scripts.sweep_themed_navigability [--seeds N] [--rooms N ...] [--keep]
    python -m scripts.sweep_themed_navigability --only cave --layouts classic graph \\
        --verticality flat moderate dramatic --rooms 2-30 --seeds 2 --jobs 3
    python -m scripts.sweep_themed_navigability --pair cave_first cave_second \\
        --layouts classic graph --verticality flat moderate dramatic --rooms 8-30 --jobs 3

Prints a per-zone OK/FAIL line, a tally per (archetype, layout, verticality),
writes one CSV row per build (``--csv``, default ``output/themed_navigability.csv``)
and exits non-zero if any zone fails. Artifacts go to a temp dir that is deleted
afterward unless ``--keep``.
"""
from __future__ import annotations

import argparse
import csv
import random
import shutil
import sys
import tempfile
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ARCHETYPES = [
    "fortress", "war_city", "warren", "temple", "tomb", "wizard_lair",
    "corrupted_sanctum", "mine_delve", "sunken_ruin", "lava_forge", "ice_keep",
    "cave",
]
VERTICALITIES = ("flat", "moderate", "dramatic")
PAIRS = ("cave_first", "cave_second")
BUILT = [a for a in ARCHETYPES if a != "cave"]


def _district_plan(arch):
    """``(dungeon_theme, district_plan)`` for a sweep cell: an archetype pins the
    zone's theme and no Districts; ``cave_first:<built>`` / ``cave_second:<built>``
    pin the two District Purposes in that order."""
    pair, _, built = arch.partition(":")
    if pair not in PAIRS:
        return arch, None
    return "", (["cave", built] if pair == "cave_first" else [built, "cave"])


def _room_counts(tokens):
    """``["8"]``, ``["2-30"]`` or ``["4", "12", "30"]`` as a list of room counts."""
    out = []
    for t in tokens:
        lo, _, hi = str(t).partition("-")
        out.extend(range(int(lo), int(hi or lo) + 1))
    return out


def build_one(job):
    """One build: plan, build, gate. Returns a CSV row."""
    arch, layout, verticality, rooms, seed, out_dir = job
    from ai.expand import plan_to_spec
    from ai.schema import ZonePlan
    from analyzer.rof2check import check_eqg
    from analyzer.traverse import validate
    from generators.builder import ZoneBuilder
    from generators.pipeline import _with_decor

    theme, dplan = _district_plan(arch)
    c = {"zone_type": "dungeon", "room_count": rooms, "verticality": verticality,
         "layout": layout}
    if theme:
        c["dungeon_theme"] = theme
    if dplan:
        c.update(districts=True, district_plan=dplan)
    plan = ZonePlan.from_controls(c, [])
    plan.name = f"nav_{arch.replace(':', '_')}_{layout[0]}{verticality[0]}{rooms}_{seed}"
    spec = _with_decor(plan_to_spec(plan, seed=seed, warnings=[]))
    res = ZoneBuilder(spec).build(output_dir=Path(out_dir), write_glb=False)
    report = validate(res.eqg_path, spec=spec, check_corridors=True)
    fmt = check_eqg(res.eqg_path, spec)
    reasons = [f"{r.room_id}: {r.reason or 'unreachable'}" for r in report.rooms
               if not r.reachable]
    reasons += [f"{o.room_id}: {o.reason}" for o in report.outlines if not o.ok]
    reasons += [f"corridor {c.corridor_id}: {c.reason}" for c in report.corridors
                if not c.connected]
    reasons += [f"conflict {c}" for c in report.conflicts]
    reasons += [f"format {c}" for c in (fmt.failed_checks or ([] if fmt.passed else ["format"]))]
    passed = report.passed and report.corridors_passed and fmt.passed
    return {"archetype": arch, "layout": layout, "verticality": verticality,
            "room_count": rooms, "n_rooms": len(spec.rooms), "seed": seed,
            "districts": "+".join(d.purpose for d in spec.districts),
            "passed": int(passed), "reachable": report.reachable_rooms,
            "total": report.total_rooms, "reasons": " | ".join(reasons)}


def run(args) -> int:
    out_dir = Path(tempfile.mkdtemp(prefix="navsweep_")) if not args.keep else ROOT / "output"
    archetypes = list(args.pair) or [a for a in ARCHETYPES if not args.only or a in args.only]
    rng = random.Random(args.seed)
    jobs = []
    for arch in archetypes:
        for layout in args.layouts:
            for v in args.verticality:
                for n in _room_counts(args.rooms):
                    for _ in range(max(args.seeds, 1)):
                        cell = f"{arch}:{rng.choice(BUILT)}" if arch in PAIRS else arch
                        jobs.append((cell, layout, v, n, rng.randint(0, 2 ** 31 - 1),
                                     str(out_dir)))

    rows = []
    if args.jobs > 1:
        with ProcessPoolExecutor(args.jobs) as ex:
            it = ex.map(build_one, jobs, chunksize=1)
            for row in it:
                rows.append(row)
                _print(row)
    else:
        for job in jobs:
            rows.append(build_one(job))
            _print(rows[-1])

    path = Path(args.csv) if args.csv else ROOT / "output" / "themed_navigability.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    tally = defaultdict(lambda: [0, 0])
    for r in rows:
        t = tally[(r["archetype"].partition(":")[0], r["layout"], r["verticality"])]
        t[0] += r["passed"]
        t[1] += 1
    print("\nper archetype / layout / verticality:")
    for key, (p, n) in sorted(tally.items()):
        print(f"  {'/'.join(key):<36} {p}/{n}")
    passed = sum(r["passed"] for r in rows)
    if args.pair:
        cave = sum(1 for r in rows if "cave" in r["districts"].split("+"))
        print(f"\n{cave}/{len(rows)} builds resolved a cave District "
              f"({sum(1 for r in rows if not r['districts'])} resolved one District)")
    print(f"\nTally: {passed}/{len(rows)} themed zones pass the gate "
          f"(rooms {args.rooms}, {args.seeds} seed(s) per cell). CSV: {path}")

    if not args.keep:
        shutil.rmtree(out_dir, ignore_errors=True)
    return 0 if passed == len(rows) else 1


def _print(row):
    mark = "OK  " if row["passed"] else "FAIL"
    print(f"  {mark} {row['archetype']:<26} {row['layout']:<8} {row['verticality']:<9} "
          f"rooms {row['room_count']:<3} seed {row['seed']:<11} "
          f"{row['reachable']}/{row['total']} reachable", flush=True)
    if row["reasons"]:
        for why in row["reasons"].split(" | "):
            print(f"         - {why}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seeds", type=int, default=2, help="seeds per cell")
    ap.add_argument("--seed", type=int, default=21, help="seed of the sweep's own rng")
    ap.add_argument("--rooms", nargs="+", default=["8"],
                    help="room counts: N, a range LO-HI, or several")
    ap.add_argument("--layouts", nargs="+", default=["classic"], choices=("classic", "graph"))
    ap.add_argument("--verticality", nargs="+", default=["moderate"], choices=VERTICALITIES)
    ap.add_argument("--only", nargs="+", default=[], help="archetypes to sweep (default all)")
    ap.add_argument("--pair", nargs="+", default=[], choices=PAIRS,
                    help="districted builds pinning a cave District and a built one, in "
                         "these orders (replaces the archetype axis)")
    ap.add_argument("--jobs", type=int, default=1, help="worker processes")
    ap.add_argument("--csv", default="", help="CSV path (default output/themed_navigability.csv)")
    ap.add_argument("--keep", action="store_true", help="keep artifacts in output/ (default: temp dir, cleaned)")
    sys.exit(run(ap.parse_args()))
