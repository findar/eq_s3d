"""Content-layer navigability sweep.

Builds themed dungeon zones across every archetype x several seeds and walks each
generated TER mesh with analyzer.traverse to confirm every room is reachable on
foot. This is the re-run of the Step 1 navigability sweep from
tasks/content-layer-dungeon.md, done after corridor-connection landed to confirm
the content layer's own elevation is navigable with ZERO content-layer changes.

Usage:  python -m scripts.sweep_themed_navigability [--seeds N] [--rooms N] [--keep]

Prints a per-zone OK/FAIL line and a final tally; exits non-zero if any zone
fails. By default it generates into a temp dir and deletes artifacts afterward.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from generators.layout import LayoutGenerator
from generators.builder import ZoneBuilder
from analyzer import traverse

ARCHETYPES = [
    "fortress", "war_city", "warren", "temple", "tomb", "wizard_lair",
    "corrupted_sanctum", "mine_delve", "sunken_ruin", "lava_forge", "ice_keep",
]


def run(seeds: int, rooms: int, keep: bool) -> int:
    out_dir = Path(tempfile.mkdtemp(prefix="navsweep_")) if not keep else Path("output")
    seed_list = [1, 42, 99, 678358326, 1955208177][:max(seeds, 1)]

    results = []  # (archetype, seed, passed, reachable, total, reasons)
    for arch in ARCHETYPES:
        for seed in seed_list:
            name = f"nav_{arch}_{seed}"
            spec = LayoutGenerator(theme="dungeon", seed=seed).generate(
                name, room_count=rooms, dungeon_theme=arch)
            res = ZoneBuilder(spec).build(output_dir=out_dir, write_glb=False)
            report = traverse.validate(res.eqg_path, spec=spec)
            reasons = [f"{r.room_id}: {r.reason}" for r in report.rooms if not r.reachable]
            results.append((arch, seed, report.passed,
                            report.reachable_rooms, report.total_rooms, reasons))
            mark = "OK  " if report.passed else "FAIL"
            print(f"  {mark} {arch:<18} seed {seed:<12} "
                  f"{report.reachable_rooms}/{report.total_rooms} reachable")
            for why in reasons:
                print(f"         - {why}")

    passed = sum(1 for r in results if r[2])
    total = len(results)
    print(f"\nTally: {passed}/{total} themed zones fully reachable "
          f"({len(ARCHETYPES)} archetypes x {len(seed_list)} seeds, rooms={rooms})")

    if not keep:
        shutil.rmtree(out_dir, ignore_errors=True)

    return 0 if passed == total else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=2, help="how many seeds per archetype (<=5)")
    ap.add_argument("--rooms", type=int, default=8, help="room count per zone")
    ap.add_argument("--keep", action="store_true", help="keep artifacts in output/ (default: temp dir, cleaned)")
    args = ap.parse_args()
    sys.exit(run(args.seeds, args.rooms, args.keep))
