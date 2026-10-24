"""Large-zone connectivity sweep (M1 wave 1, Requirements 5.2 / 5.3 / 5.4).

Builds box zones across the M1 connectivity domain and reports, per failure
*class*, how many builds exhibit it and which seeds do. This is the "measure
before fixing" step (task 5.1): it produces the per-class table that tasks 6.5
(flat) and 8.3 (elevation) drive their root-cause fixes from, and is re-run
after each fix to watch a class fall to zero. No fix lives here — this is
measurement only.

Domain (the full sweep):
    zone types : dungeon, city
    room counts: 12, 20, 30
    verticality: flat (elevation off), elevation (verticality "dramatic")
    seeds      : 200 per cell  (default; override with --seeds)

That is 2 x 3 x 2 x 200 = 2400 builds for the full sweep. Each build goes
through ``plan_to_spec`` + ``ZoneBuilder`` (the same path the dropdowns and the
planner use) and is walked with ``analyzer.traverse.validate(check_corridors=
True)`` on the real generated mesh.

Failure classes (a single build can land in several):
    gap            a corridor's floor is discontinuous within its own region
                   (CorridorResult.reason == "gap").
    crosses room   a corridor's route runs through a third room
                   (reason starts with "crosses room").
    no floor       a corridor end has no standable floor in its room
                   (reason starts with "no floor").
    inverted stub  a corridor's from-opening sits *past* its to-opening on the
                   exit axis (the facing walls are crossed). Computed straight
                   from the spec openings + room centres — independent of the
                   mesh flood — so it is visible even when the flood also calls
                   the corridor a "gap".
    conflict       two corridors that share no room cross too close in Z
                   (report.conflicts non-empty; design decision 12).
    unreachable    at least one room is not reachable from the safe point
                   (P1 / umbrella Req 4.2: not report.passed).

Usage:
    python -m scripts.sweep_connectivity                 # full sweep
    python -m scripts.sweep_connectivity --seeds 50      # fewer seeds per cell
    python -m scripts.sweep_connectivity --flat          # flat half only
    python -m scripts.sweep_connectivity --elevation     # elevation half only
    python -m scripts.sweep_connectivity --rooms 12 30   # pick room counts
    python -m scripts.sweep_connectivity --zone-types dungeon
    python -m scripts.sweep_connectivity --keep          # keep .eqg/.glb/.json

Prints a per-class table (overall and split by zone type / room count /
verticality) plus a handful of representative seeds per class, and exits 0
regardless of findings (it is a measurement tool, not a gate).
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from ai import ZonePlan, plan_to_spec
from analyzer import traverse
from generators.builder import ZoneBuilder
from generators.routing import corridor_route, exit_axis_x


# The failure classes, in report order.
CLASSES = ["gap", "crosses room", "no floor", "inverted stub", "conflict",
           "unreachable"]


def _inverted_stubs(spec) -> List[str]:
    """Corridor ids whose from-opening sits past their to-opening on the exit
    axis (the facing walls are crossed), computed from the spec alone.

    The exit axis of each opening is the room-centre delta basis
    ``corridor_route`` uses. A stub is "inverted" when, on the leg's run axis,
    the from-opening has already passed the to-opening relative to the direction
    the from-wall faces — i.e. the stub out of the from-room would have to travel
    backwards to reach the jog. This is the ``fx past tx`` class from the design
    suspect table; it survives in the spec even when the mesh flood reports the
    same corridor as a plain ``gap``.
    """
    rooms = {r.id: r for r in spec.rooms}
    bad: List[str] = []
    for cor in spec.corridors:
        a = rooms.get(cor.from_room)
        b = rooms.get(cor.to_room)
        if a is None or b is None:
            continue
        # Exit axis for the FROM opening (same footprint-separation basis as
        # corridor_route / _wall_point): the wall faces along X when the rooms
        # are better separated on X.
        exit_from_x = exit_axis_x(
            a.center_x, a.center_y, a.width / 2, a.depth / 2,
            b.center_x, b.center_y, b.width / 2, b.depth / 2)
        if exit_from_x:
            # Direction the from-wall faces, and the opening vs. opening delta.
            facing = 1.0 if (b.center_x - a.center_x) >= 0 else -1.0
            delta = cor.to_x - cor.from_x
        else:
            facing = 1.0 if (b.center_y - a.center_y) >= 0 else -1.0
            delta = cor.to_y - cor.from_y
        # Inverted when the stub would run opposite the way its wall faces: the
        # from-opening is already on the far side of the to-opening.
        if delta * facing < 0.0:
            bad.append(cor.id)
    return bad


def _classify(spec, report) -> Dict[str, bool]:
    """Which failure classes this one build exhibits."""
    hit = {c: False for c in CLASSES}
    for c in report.corridors:
        if c.reason == "gap":
            hit["gap"] = True
        elif c.reason.startswith("crosses room"):
            hit["crosses room"] = True
        elif c.reason.startswith("no floor"):
            hit["no floor"] = True
    if _inverted_stubs(spec):
        hit["inverted stub"] = True
    if report.conflicts:
        hit["conflict"] = True
    if not report.passed:
        hit["unreachable"] = True
    return hit


def _plan(zone_type: str, rooms: int, elevation: bool) -> ZonePlan:
    """A ZonePlan for one sweep cell. Flat = elevation off; the elevation half
    uses verticality 'dramatic' so the fixes face the steepest routes."""
    return ZonePlan(
        name=f"sweep_{zone_type}_{rooms}",
        theme=zone_type,
        room_count=rooms,
        size="medium",
        elevation=elevation,
        verticality="dramatic" if elevation else "flat",
    )


def run(zone_types: List[str], room_counts: List[int],
        verticalities: List[Tuple[str, bool]], seeds: int, keep: bool) -> int:
    out_dir = Path("output") if keep else Path(tempfile.mkdtemp(prefix="connsweep_"))
    seed_list = list(range(1, seeds + 1))

    # class -> list of (zone_type, rooms, vert_label, seed)
    hits: Dict[str, List[Tuple[str, int, str, int]]] = {c: [] for c in CLASSES}
    # (zone_type, rooms, vert_label) -> {class: count}
    by_cell: Dict[Tuple[str, int, str], Dict[str, int]] = defaultdict(
        lambda: {c: 0 for c in CLASSES})
    total_builds = 0
    build_errors: List[Tuple[str, int, str, int, str]] = []

    for zt in zone_types:
        for rooms in room_counts:
            for vlabel, elevation in verticalities:
                by_cell[(zt, rooms, vlabel)]  # ensure the cell shows up at 0
                for seed in seed_list:
                    plan = _plan(zt, rooms, elevation)
                    try:
                        spec = plan_to_spec(plan, seed=seed)
                        res = ZoneBuilder(spec).build(output_dir=out_dir,
                                                      write_glb=False)
                        report = traverse.validate(res.eqg_path, spec=spec,
                                                   check_corridors=True)
                    except Exception as exc:  # noqa: BLE001 — record, keep sweeping
                        build_errors.append((zt, rooms, vlabel, seed,
                                             f"{type(exc).__name__}: {exc}"))
                        total_builds += 1
                        continue
                    total_builds += 1
                    hit = _classify(spec, report)
                    cell = (zt, rooms, vlabel)
                    for c, did in hit.items():
                        if did:
                            hits[c].append((zt, rooms, vlabel, seed))
                            by_cell[cell][c] += 1
                    if not keep:
                        # Keep the temp dir small during a long sweep.
                        for p in (res.eqg_path, res.glb_path):
                            if p:
                                Path(p).unlink(missing_ok=True)
                        Path(res.eqg_path).with_suffix(".json").unlink(missing_ok=True)
                        Path(res.eqg_path).with_suffix(".zone.json").unlink(
                            missing_ok=True)

    _report(zone_types, room_counts, verticalities, seeds, total_builds,
            hits, by_cell, build_errors)

    if not keep:
        shutil.rmtree(out_dir, ignore_errors=True)
    return 0


def _report(zone_types, room_counts, verticalities, seeds, total_builds,
            hits, by_cell, build_errors) -> None:
    print("\n" + "=" * 70)
    print("CONNECTIVITY SWEEP")
    print("=" * 70)
    print(f"  zone types : {', '.join(zone_types)}")
    print(f"  room counts: {', '.join(str(r) for r in room_counts)}")
    print(f"  verticality: {', '.join(v for v, _ in verticalities)}")
    print(f"  seeds/cell : {seeds}")
    print(f"  builds     : {total_builds}")
    if build_errors:
        print(f"  build errors: {len(build_errors)} "
              f"(e.g. {build_errors[0][4]})")

    print("\nPer-class totals (builds exhibiting the class):")
    print(f"  {'class':<16}{'count':>8}{'  representative seeds'}")
    print("  " + "-" * 60)
    for c in CLASSES:
        rows = hits[c]
        reps = ", ".join(str(s) for (_, _, _, s) in rows[:8])
        more = "" if len(rows) <= 8 else f" (+{len(rows) - 8} more)"
        print(f"  {c:<16}{len(rows):>8}  {reps}{more}")

    print("\nPer-cell breakdown (zone_type x rooms x verticality):")
    header = f"  {'cell':<26}" + "".join(f"{c[:10]:>12}" for c in CLASSES)
    print(header)
    print("  " + "-" * (len(header) - 2))
    for zt in zone_types:
        for rooms in room_counts:
            for vlabel, _ in verticalities:
                cell = (zt, rooms, vlabel)
                counts = by_cell.get(cell)
                label = f"{zt}/{rooms}/{vlabel}"
                if counts is None:
                    continue
                print(f"  {label:<26}"
                      + "".join(f"{counts[c]:>12}" for c in CLASSES))

    # A fuller seed dump per class (for pinning Regression_Examples in 6.5/8.3).
    print("\nFailing seeds per class (zone_type/rooms/verticality:seed):")
    for c in CLASSES:
        rows = hits[c]
        if not rows:
            print(f"  {c}: none")
            continue
        shown = rows[:40]
        tags = ", ".join(f"{zt}/{r}/{v}:{s}" for (zt, r, v, s) in shown)
        more = "" if len(rows) <= 40 else f" (+{len(rows) - 40} more)"
        print(f"  {c} ({len(rows)}): {tags}{more}")
    print()


def _parse_args(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=200,
                    help="seeds per cell (default 200 = full sweep)")
    ap.add_argument("--rooms", type=int, nargs="+", default=[12, 20, 30],
                    help="room counts to sweep (default 12 20 30)")
    ap.add_argument("--zone-types", nargs="+", default=["dungeon", "city"],
                    help="zone types to sweep (default dungeon city)")
    ap.add_argument("--flat", action="store_true",
                    help="flat half only (elevation off)")
    ap.add_argument("--elevation", action="store_true",
                    help="elevation half only")
    ap.add_argument("--keep", action="store_true",
                    help="keep artifacts in output/ (default: temp dir, cleaned)")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    verticalities: List[Tuple[str, bool]] = [("flat", False), ("elevation", True)]
    if args.flat and not args.elevation:
        verticalities = [("flat", False)]
    elif args.elevation and not args.flat:
        verticalities = [("elevation", True)]
    return run(args.zone_types, args.rooms, verticalities, args.seeds, args.keep)


if __name__ == "__main__":
    sys.exit(main())
