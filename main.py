"""
main.py
-------
CLI entry point for eq_s3d.

Commands:
    generate   — procedurally generate a zone from parameters

Usage::

    python main.py generate myrealm --zone-type dungeon --rooms 5
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from generators.layout import LayoutGenerator
from generators.pipeline import generate_validated, GenerationFailed
from generators.zone_types import (
    DEFINED_ZONE_TYPES, DEFAULT_ZONE_TYPE, canonical_zone_type,
)


def cmd_generate(args) -> None:
    # Legacy-map the chosen value (``--theme outdoor`` == ``--zone-type
    # wilderness``); argparse shares one dest so the later option wins. Read a
    # legacy ``theme`` attribute too, for callers that build the Namespace
    # directly with the old field name.
    raw = getattr(args, "zone_type", None)
    if raw is None:
        raw = getattr(args, "theme", None)
    zone_type = canonical_zone_type(raw) or DEFAULT_ZONE_TYPE
    print(f"Generating zone '{args.name}' (zone_type={zone_type}, rooms={args.rooms})")

    def factory(seed):
        return LayoutGenerator(zone_type=zone_type, seed=seed).generate(
            args.name, room_count=args.rooms,
        )

    # Build through the shared validated pipeline, so the CLI gets the same
    # "every room reachable on foot" guarantee as the server (dungeon/box
    # backend). --no-validate bypasses the gate to inspect a broken seed.
    try:
        vb = generate_validated(
            factory,
            zone_type=zone_type,
            zone_id=args.name,
            seed=args.seed,
            output_dir=args.output,
            ter_version=args.ter_version,
            validate_enabled=not args.no_validate,
            failure_log=Path(args.output) / "validation_failures.jsonl",
        )
    except GenerationFailed as e:
        print(f"\nerror: {e}", file=sys.stderr)
        for fail in e.failures:
            print(f"  attempt {fail.attempt} (seed {fail.seed}): "
                  f"{fail.reachable_rooms}/{fail.total_rooms} rooms reachable",
                  file=sys.stderr)
            for reason in fail.reasons:
                print(f"    - {reason}", file=sys.stderr)
        if e.pinned:
            print("  (pinned seed failed; omit --seed to let the generator "
                  "find a valid one, or use --no-validate to build it anyway)",
                  file=sys.stderr)
        sys.exit(1)

    # Save the passing spec alongside output for inspection / iteration. Using
    # vb.spec records the seed that actually produced a valid zone.
    spec_path = Path(args.output) / f"{args.name}.json"
    vb.spec.save(spec_path)
    print(f"  Spec saved: {spec_path}")

    print()
    print(vb.result.summary())
    if vb.gated:
        status = "validated" if vb.validated else "NOT validated"
        print(f"  Traversability: {status} "
              f"(seed {vb.seed}, {vb.attempts} attempt(s))")
    elif args.no_validate:
        print("  Traversability: skipped (--no-validate)")
    else:
        print(f"  Traversability: ungated zone type '{zone_type}' (not validated)")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="eq_s3d", description="Agentic EverQuest zone generator")
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="Procedurally generate a zone")
    g.add_argument("name", help="Zone short name (lowercase, no spaces)")
    # --zone-type is the current option; --theme is a deprecated alias that
    # shares the same dest (later option wins) and still accepts the legacy
    # "outdoor" value, mapped forward to "wilderness" in cmd_generate.
    g.add_argument("--zone-type", dest="zone_type", default=DEFAULT_ZONE_TYPE,
                   choices=list(DEFINED_ZONE_TYPES),
                   help="Zone type to generate")
    g.add_argument("--theme", dest="zone_type",
                   choices=list(DEFINED_ZONE_TYPES) + ["outdoor"],
                   help="Deprecated alias for --zone-type (accepts legacy "
                        "'outdoor' == 'wilderness')")
    g.add_argument("--rooms", type=int, default=5, help="Number of rooms")
    g.add_argument("--seed", type=int, default=None, help="Random seed")
    g.add_argument("--output", default="output", help="Output directory")
    g.add_argument("--ter-version", type=int, default=2, choices=[2, 3])
    g.add_argument("--no-validate", "--allow-invalid", dest="no_validate",
                   action="store_true",
                   help="Skip the traversability gate (build even an invalid "
                        "zone — for debugging broken seeds on purpose)")
    g.set_defaults(func=cmd_generate)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
