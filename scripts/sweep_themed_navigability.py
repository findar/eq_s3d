"""Content-layer navigability sweep.

Builds themed dungeon zones across archetypes x layouts x verticalities x room
counts x seeds and runs each through the generate path's gate: the spec is drawn
the way a controls generate draws it (``ZonePlan.from_controls`` then
``plan_to_spec``, Decor at ``--decor``, default none), built, and judged with
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

``--intrusion`` (zone-generator-district-races task 10) sweeps districted dungeons
whose Districts break into one another: the Districts switch on, ``district_relationship``
``intrusion`` (``--relationship`` names another, to compare) and ``district_plan``
pinning a host and an intruder, each ``purpose[/race]``, given as ``HOST+INTRUDER``
(default ``fortress/giant+warren/goblin``; e.g. ``cave/giant+warren/goblin``). Each
zone goes through the generate path itself, ``generate_validated`` with an unpinned
seed drawn from the job's rng (the quality Draws, the gate and its retries), as a
user's generate does. The CSV adds the attempts, the Draws (each timed and measured
against the bands), the cross-District links, the breaches and the drops of the
accepted build.

``--outdoor`` (zone-generator-random-placement task 4) sweeps outdoor dungeons
(``zone_type`` ``outdoor_dungeon``) instead, judged with the outdoor gate
(``generators.outdoor_dungeon.outdoor_dungeon_report``: the bowl, every room
reached from the outdoor Spawn, every corridor continuous) and the Format_Checker.
The archetype axis is the dungeon theme: ``default`` (none pinned) unless
``--only`` names themes. A plan error (``PLAN_ERRORS``, which the pipeline retries
with a fresh seed) counts as a failure with the reason ``plan: ...``.

Usage:
    python -m scripts.sweep_themed_navigability [--seeds N] [--rooms N ...] [--keep]
    python -m scripts.sweep_themed_navigability --only cave --layouts classic graph \\
        --verticality flat moderate dramatic --rooms 2-30 --seeds 2 --jobs 3
    python -m scripts.sweep_themed_navigability --pair cave_first cave_second \\
        --layouts classic graph --verticality flat moderate dramatic --rooms 8-30 --jobs 3
    python -m scripts.sweep_themed_navigability --intrusion fortress/giant+warren/goblin \\
        cave/giant+warren/goblin --layouts classic graph --rooms 16 24 --jobs 6
    python -m scripts.sweep_themed_navigability --outdoor --layouts graph \\
        --verticality flat moderate dramatic --rooms 2-30 --seeds 2 --seed 23 --jobs 3

``--decor`` (decor-off step 34) sets every zone's Decor level: ``none`` (the default,
as a generate that doesn't choose one builds), ``sparse``, ``normal`` or ``dense``.

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
DEFAULT_INTRUSION = "fortress/giant+warren/goblin"


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
    arch, layout, verticality, rooms, seed, out_dir, winding, hall_length, decor, *rest = job
    if rest and rest[0] == "outdoor":
        return _build_outdoor(arch, layout, verticality, rooms, seed, out_dir, winding,
                              hall_length, decor)
    if rest and rest[0] == "intrusion":
        return _build_intrusion(arch, layout, verticality, rooms, seed, out_dir, winding,
                                hall_length, rest[1], decor)
    from ai.expand import plan_to_spec
    from ai.schema import ZonePlan
    from analyzer.rof2check import check_eqg
    from analyzer.traverse import validate
    from generators.builder import ZoneBuilder
    from generators.pipeline import _with_decor

    theme, dplan = _district_plan(arch)
    c = {"zone_type": "dungeon", "room_count": rooms, "verticality": verticality,
         "layout": layout, "decor": decor}
    if theme:
        c["dungeon_theme"] = theme
    if dplan:
        c.update(districts=True, district_plan=dplan)
    if winding is not None:
        c["winding"] = winding
    if hall_length is not None:
        c["hall_length"] = hall_length
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


def _intrusion_plan(cell):
    """``"fortress/giant+warren/goblin"`` as a ``district_plan``: host first, then the
    intruder, each ``{"purpose"[, "race"]}`` (no race: the zone's)."""
    plan = []
    for part in cell.split("+"):
        purpose, _, race = part.partition("/")
        plan.append({"purpose": purpose, **({"race": race} if race else {})})
    return plan


def _build_intrusion(cell, layout, verticality, rooms, seed, out_dir, winding, hall_length,
                     relationship, decor):
    """One intrusion zone (``--intrusion``) through ``generate_validated``, as a generate
    builds it: its Draws timed and measured, then the accepted build's links, breaches
    and drops."""
    import dataclasses
    import time

    from ai.expand import plan_to_spec
    from ai.schema import ZonePlan
    from generators import quality
    from generators.builder import with_district_notes
    from generators.pipeline import GenerationFailed, generate_validated
    from generators.transitions import breach_hosts

    c = {"zone_type": "dungeon", "room_count": rooms, "verticality": verticality,
         "layout": layout, "districts": True, "district_plan": _intrusion_plan(cell),
         "decor": decor}
    if relationship != "sequential":
        c["district_relationship"] = relationship
    if winding is not None:
        c["winding"] = winding
    if hall_length is not None:
        c["hall_length"] = hall_length
    plan = ZonePlan.from_controls(c, [])
    plan.name = f"nav_intr_{layout[0]}{verticality[0]}{rooms}_{seed}"
    draws = []

    def factory(s, rooms_seed=None):
        p = plan if rooms_seed is None else dataclasses.replace(plan, rooms_seed=rooms_seed)
        notes: list = []
        t0 = time.perf_counter()
        spec = plan_to_spec(p, seed=s, warnings=notes)
        dt = time.perf_counter() - t0
        ok = quality.measure(spec, verticality=verticality).passed
        draws.append(f"{dt:.2f}/{int(ok)}/{quality.spec_districts(spec)}")
        return with_district_notes(spec, notes)

    row = {"archetype": cell, "layout": layout, "verticality": verticality,
           "room_count": rooms, "n_rooms": 0, "seed": seed, "relationship": relationship,
           "districts": "", "passed": 0, "reachable": 0, "total": 0, "attempts": 0,
           "build_seed": "", "wall_s": 0.0, "timed_out": 0,
           "draws": "", "links": 0, "breaches": 0, "drops": 0, "drop_u": "", "reasons": ""}
    t_zone = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="intr", dir=out_dir,
                                     ignore_cleanup_errors=True) as tmp:
        try:
            vb = generate_validated(factory, zone_type="dungeon", zone_id=plan.name,
                                    output_dir=Path(tmp), write_glb=False,
                                    rng=random.Random(seed), failure_log=None,
                                    verticality=verticality)
        except GenerationFailed as e:
            last = e.failures[-1] if e.failures else None
            why = "; ".join(last.reasons) if last else str(e)
            return dict(row, attempts=len(e.failures), draws=";".join(draws),
                        build_seed=last.seed if last else "", timed_out=int(e.timed_out),
                        wall_s=round(time.perf_counter() - t_zone, 1),
                        reasons=f"failed: {why}"[:400])
    spec = vb.spec
    rid = {r.id: r.district for r in spec.rooms}
    cross = [k for k in spec.corridors if rid.get(k.from_room) != rid.get(k.to_room)]
    drops = [k.drop for k in cross if k.drop]
    return dict(row, n_rooms=len(spec.rooms), seed=seed,
                districts="+".join(f"{d.purpose}/{d.race}" if d.race else d.purpose
                                   for d in spec.districts),
                passed=int(vb.validated), reachable=vb.report.reachable_rooms,
                total=vb.report.total_rooms, attempts=vb.attempts, draws=";".join(draws),
                build_seed=vb.seed, wall_s=round(time.perf_counter() - t_zone, 1),
                links=len(cross), breaches=len(breach_hosts(spec)), drops=len(drops),
                drop_u=" ".join(f"{d:.0f}" for d in drops))


def _build_outdoor(theme, layout, verticality, rooms, seed, out_dir, winding, hall_length,
                   decor):
    """One outdoor-dungeon build (``--outdoor``): plan, build, the outdoor gate."""
    from ai.expand import plan_to_spec
    from ai.schema import ZonePlan
    from analyzer.rof2check import check_eqg
    from generators.builder import ZoneBuilder
    from generators.outdoor_dungeon import PLAN_ERRORS, outdoor_dungeon_report
    from generators.pipeline import _with_decor

    c = {"zone_type": "outdoor_dungeon", "room_count": rooms, "verticality": verticality,
         "layout": layout, "decor": decor}
    if theme != "default":
        c["dungeon_theme"] = theme
    if winding is not None:
        c["winding"] = winding
    if hall_length is not None:
        c["hall_length"] = hall_length
    plan = ZonePlan.from_controls(c, [])
    plan.name = (f"odnav_{verticality[0]}{rooms}_{seed}" if theme == "default"
                 else f"odnav_{theme}_{verticality[0]}{rooms}_{seed}")
    row = {"archetype": theme, "layout": layout, "verticality": verticality,
           "room_count": rooms, "n_rooms": 0, "seed": seed, "districts": "",
           "passed": 0, "reachable": 0, "total": 0, "reasons": ""}
    try:
        spec = _with_decor(plan_to_spec(plan, seed=seed, warnings=[]))
    except PLAN_ERRORS as e:
        return dict(row, reasons=f"plan: {type(e).__name__}: {e}"[:200])
    res = ZoneBuilder(spec).build(output_dir=Path(out_dir), write_glb=False)
    report = outdoor_dungeon_report(res.eqg_path, spec)
    fmt = check_eqg(res.eqg_path, spec)
    reasons = [f"{r.room_id}: {r.reason or 'unreachable'}" for r in report.rooms
               if not r.reachable]
    reasons += [f"{o.room_id}: {o.reason}" for o in getattr(report, "outlines", []) if not o.ok]
    reasons += [f"corridor {c.corridor_id}: {c.reason}" for c in report.corridors
                if not c.connected]
    reasons += [f"conflict {c}" for c in report.conflicts]
    reasons += [f"format {c}" for c in (fmt.failed_checks or ([] if fmt.passed else ["format"]))]
    passed = report.passed and report.corridors_passed and fmt.passed
    return dict(row, n_rooms=len(spec.rooms), passed=int(passed),
                reachable=report.reachable_rooms, total=report.total_rooms,
                reasons=" | ".join(reasons))


def run(args) -> int:
    out_dir = Path(tempfile.mkdtemp(prefix="navsweep_")) if not args.keep else ROOT / "output"
    if args.outdoor:
        archetypes = list(args.only) or ["default"]
    elif args.intrusion is not None:
        archetypes = list(args.intrusion) or [DEFAULT_INTRUSION]
    else:
        archetypes = list(args.pair) or [a for a in ARCHETYPES if not args.only or a in args.only]
    rng = random.Random(args.seed)
    jobs = []
    for arch in archetypes:
        for layout in args.layouts:
            for v in args.verticality:
                for n in _room_counts(args.rooms):
                    for _ in range(max(args.seeds, 1)):
                        cell = f"{arch}:{rng.choice(BUILT)}" if arch in PAIRS else arch
                        job = (cell, layout, v, n, rng.randint(0, 2 ** 31 - 1),
                               str(out_dir), args.winding, args.hall_length, args.decor)
                        if args.outdoor:
                            job += ("outdoor",)
                        elif args.intrusion is not None:
                            job += ("intrusion", args.relationship)
                        jobs.append(job)

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
    if args.intrusion is not None:
        _intrusion_summary(rows)
    if args.pair:
        cave = sum(1 for r in rows if "cave" in r["districts"].split("+"))
        print(f"\n{cave}/{len(rows)} builds resolved a cave District "
              f"({sum(1 for r in rows if not r['districts'])} resolved one District)")
    print(f"\nTally: {passed}/{len(rows)} {'outdoor dungeons' if args.outdoor else 'themed zones'} pass the gate "
          f"(rooms {args.rooms}, {args.seeds} seed(s) per cell, decor {args.decor}). CSV: {path}")

    if not args.keep:
        shutil.rmtree(out_dir, ignore_errors=True)
    return 0 if passed == len(rows) else 1


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    return (xs[n // 2] + xs[(n - 1) // 2]) / 2 if xs else float("nan")


def _intrusion_summary(rows):
    """Per pair / layout / rooms: links, breaches, drops; per band key (layout,
    verticality, District count): the Draws failing the bands; per room count: Draw time."""
    links = defaultdict(lambda: [0, 0, 0, 0])
    bands = defaultdict(lambda: [0, 0])
    times = defaultdict(list)
    for r in rows:
        t = links[(r["archetype"], r["layout"], r["room_count"])]
        t[0] += 1
        t[1] += r["links"]
        t[2] += r["breaches"]
        t[3] += r["drops"]
        for d in filter(None, r["draws"].split(";")):
            dt, ok, nd = d.split("/")
            b = bands[(r["layout"], r["verticality"], nd)]
            b[0] += 1
            b[1] += 1 - int(ok)
            times[r["room_count"]].append(float(dt))
    print("\nper pair / layout / rooms: zones, cross links, breaches, drops (share of links):")
    for key, (n, li, br, dr) in sorted(links.items()):
        share = dr / li if li else 0.0
        print(f"  {key[0]:<30} {key[1]:<8} {key[2]:<3} {n:>4} {li:>5} {br:>5} {dr:>4} "
              f"({share:.1%})")
    print("\nquality Draws per key (layout / verticality / Districts): draws, fail share:")
    for key, (n, f) in sorted(bands.items()):
        print(f"  {'/'.join(key):<24} {n:>5} {f / n:6.1%}")
    print("\nDraw time (plan_to_spec, s) per room count: draws, median, max:")
    for n, ts in sorted(times.items()):
        print(f"  rooms {n:<3} {len(ts):>5} {_median(ts):7.2f} {max(ts):7.2f}")
    walls = defaultdict(list)
    for r in rows:
        walls[r["room_count"]].append(r["wall_s"])
    print("\nZone wall time (generate_validated, s) per room count: zones, median, max:")
    for n, ws in sorted(walls.items()):
        print(f"  rooms {n:<3} {len(ws):>5} {_median(ws):7.1f} {max(ws):7.1f}")


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
    ap.add_argument("--intrusion", nargs="*", default=None, metavar="HOST+INTRUDER",
                    help="districted builds through generate_validated pinning a host and an "
                         "intruder District, each purpose[/race] (default "
                         f"{DEFAULT_INTRUSION}; replaces the archetype axis)")
    ap.add_argument("--relationship", default="intrusion",
                    help="the --intrusion zones' District relationship (default intrusion)")
    ap.add_argument("--outdoor", action="store_true",
                    help="sweep outdoor dungeons with the outdoor gate (--only names themes; "
                         "default: no theme pinned)")
    ap.add_argument("--winding", type=float, default=None,
                    help="the plan's Winding (0..WINDING_MAX; default unset, the plan's default)")
    ap.add_argument("--hall-length", type=float, default=None,
                    help="the plan's Hall length (HALL_MIN..HALL_MAX; default unset, the plan's default)")
    ap.add_argument("--decor", default="none", choices=("none", "sparse", "normal", "dense"),
                    help="every zone's Decor level (default none, as a generate that "
                         "doesn't choose one)")
    ap.add_argument("--jobs", type=int, default=1, help="worker processes")
    ap.add_argument("--csv", default="", help="CSV path (default output/themed_navigability.csv)")
    ap.add_argument("--keep", action="store_true", help="keep artifacts in output/ (default: temp dir, cleaned)")
    sys.exit(run(ap.parse_args()))
