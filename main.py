"""
main.py
-------
CLI entry point for eq_s3d.

Commands:
    generate   — procedurally generate a zone from parameters

Usage::

    python main.py generate myrealm --theme dungeon --rooms 5
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from generators.layout import LayoutGenerator
from generators.pipeline import generate_validated, GenerationFailed


def cmd_generate(args) -> None:
    print(f"Generating zone '{args.name}' (theme={args.theme}, rooms={args.rooms})")

    def factory(seed):
        return LayoutGenerator(theme=args.theme, seed=seed).generate(
            args.name, room_count=args.rooms,
        )

    # Build through the shared validated pipeline, so the CLI gets the same
    # "every room reachable on foot" guarantee as the server (dungeon/box
    # backend). --no-validate bypasses the gate to inspect a broken seed.
    try:
        vb = generate_validated(
            factory,
            theme=args.theme,
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
        print(f"  Traversability: ungated theme '{args.theme}' (not validated)")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="eq_s3d", description="Agentic EverQuest zone generator")
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="Procedurally generate a zone")
    g.add_argument("name", help="Zone short name (lowercase, no spaces)")
    g.add_argument("--theme", default="dungeon",
                   choices=["dungeon", "outdoor", "city"])
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
