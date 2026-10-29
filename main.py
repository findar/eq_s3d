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

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from core.env import env_value
from core.paths import (
    OutputRoot,
    OutsideOutputError,
    assert_output_allowed,
    new_zone_id,
)
from generators.builder import BUILD_NAME_RE
from generators.pipeline import generate_validated, GenerationFailed
from generators.zone_types import (
    DEFINED_ZONE_TYPES, DEFAULT_ZONE_TYPE,
    canonical_zone_type, enabled_zone_types, is_enabled,
)


# ---------------------------------------------------------------------------
# Range-checked argparse ``type=`` functions (Req 2.5)
#
# Every one raises ``argparse.ArgumentTypeError`` for an out-of-domain value,
# so argparse exits 2 DURING parse_args — before ``cmd_generate`` runs and so
# before any build or write. The geometry-slice controls are the ONLY surface:
# there is no target / topology / district / content option (Req 2.3, 8.1).
# ---------------------------------------------------------------------------

def _enabled_set_str() -> str:
    """The enabled zone types in canonical listing order, comma-joined."""
    return ", ".join(z for z in DEFINED_ZONE_TYPES if z in enabled_zone_types())


def _build_name_arg(value: str) -> str:
    """``generate`` positional-name converter (Req 8.2, 8.3).

    Lower-cases the value and requires it to match the Build_Name alphabet
    (``^[a-z0-9_]+$`` — the umbrella glossary's Build_Name grammar, shared with
    ``generators.builder.BUILD_NAME_RE``). An out-of-alphabet name raises
    ``argparse.ArgumentTypeError`` → argparse exits 2 DURING parse_args, before
    ``cmd_generate`` runs and so before any build or write. No length limit or
    reserved-name list; just the one regex. The accepted value is returned
    lower-cased, so it IS the Build_Name the builder then validates again.
    """
    lowered = value.lower()
    if not BUILD_NAME_RE.fullmatch(lowered):
        raise argparse.ArgumentTypeError(
            f"name {value!r} is not a valid Build_Name; use only lower-case "
            f"letters, digits and underscore (matching {BUILD_NAME_RE.pattern})"
        )
    return lowered


def _zone_type_arg(value: str) -> str:
    """``--zone-type`` / ``--theme`` converter (Req 3.3, 11.3).

    Maps the legacy ``outdoor`` forward to ``wilderness`` (via
    ``canonical_zone_type``), then REJECTS any value that is not an *enabled*
    zone type — an undefined name (e.g. ``cave``, which canonicalises to
    ``None``) OR a defined-but-disabled one (``wilderness`` / its ``outdoor``
    alias). The error names the enabled set, so argparse exits 2 before any
    write. An accepted value is returned canonicalised.
    """
    canonical = canonical_zone_type(value)
    if canonical is None or not is_enabled(canonical):
        raise argparse.ArgumentTypeError(
            f"zone type {value!r} is not available; enabled: {_enabled_set_str()}"
        )
    return canonical


def _int_in_range(name: str, lo: int, hi: int):
    """Build a ``type=`` converter for an int constrained to ``[lo, hi]``."""

    def _conv(value: str) -> int:
        try:
            n = int(value)
        except (TypeError, ValueError):
            raise argparse.ArgumentTypeError(
                f"{name} must be an integer, got {value!r}"
            )
        if not (lo <= n <= hi):
            raise argparse.ArgumentTypeError(
                f"{name} must be between {lo} and {hi}, got {n}"
            )
        return n

    return _conv


# --rooms 1-30, --locks 0-5, --seed 0..2^31-1 (Req 2.5).
_rooms_arg = _int_in_range("--rooms", 1, 30)
_locks_arg = _int_in_range("--locks", 0, 5)
_seed_arg = _int_in_range("--seed", 0, 2_147_483_647)


def _edges_arg(value: str) -> dict:
    """``--edges`` converter: ``N=zoneline,E=river`` -> four-side Rim
    declaration (unnamed sides are mountain). Exit 2 on a bad side/type."""
    from generators.wilderness.build import parse_edges
    try:
        return parse_edges(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc))


def cmd_generate(args) -> None:
    # Resolve the zone type. ``--zone-type`` / ``--theme`` share one dest and
    # are already converted + validated by ``_zone_type_arg`` (so a disabled or
    # undefined value exited 2 during parsing). A caller that builds the
    # Namespace directly may still pass the legacy ``theme`` field name; honour
    # it, canonicalising through to the default as a safety net.
    raw = getattr(args, "zone_type", None)
    if raw is None:
        raw = getattr(args, "theme", None)
    zone_type = canonical_zone_type(raw) or DEFAULT_ZONE_TYPE
    print(f"Generating zone '{args.name}' (zone_type={zone_type}, rooms={args.rooms})")

    # Build the plan through ZonePlan.from_controls — the SAME controls path the
    # server uses (Req 2.2). The controls dict is the geometry slice only:
    # zone_type, rooms, size, verticality, locks. from_controls folds the
    # ``rooms`` alias into ``room_count`` and runs the shared validate(), so the
    # CLI's plan equals the server's controls plan for the same values (the
    # 17.8 test asserts this equality).
    controls = {
        "zone_type": zone_type,
        "rooms": args.rooms,
        "size": args.size,
        "verticality": args.verticality,
        "locks": args.locks,
    }
    plan = ZonePlan.from_controls(controls)
    # The positional is the Build_Name (lower-cased + validated by
    # ``_build_name_arg``); it names every artifact. The zone id — the per-build
    # directory — is ``new_zone_id(prefix=<name>)`` so two runs with the same
    # name land in DIFFERENT directories (Req 8.3) while every file inside still
    # carries the Build_Name stem.
    plan.name = args.name
    zone_id = new_zone_id(prefix=args.name)

    edges = getattr(args, "edges", None)

    def factory(seed):
        return plan_to_spec(plan, seed=seed, edges=edges)

    # Build through the shared validated pipeline, so the CLI gets the same
    # "every room reachable on foot" guarantee as the server (dungeon/box
    # backend). --no-validate bypasses the gate to inspect a broken seed.
    try:
        vb = generate_validated(
            factory,
            zone_type=zone_type,
            zone_id=zone_id,
            seed=args.seed,
            output_dir=args.output,
            ter_version=args.ter_version,
            validate_enabled=not args.no_validate,
            failure_log=Path(args.output) / "validation_failures.jsonl",
            mode="controls",
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

    # Save the passing spec as ``<name>.json`` in the build directory (next to
    # the artifacts), so ``python -m analyzer.traverse <dir>/<name>.eqg`` finds
    # it (design "CLI"). Using vb.spec records the seed that actually produced a
    # valid zone. ``vb.build_dir`` is ``<output>/<zone_id>/v1`` for a gated or
    # ungated build; fall back to the output dir only if it is somehow unset.
    build_dir = Path(vb.build_dir) if vb.build_dir is not None else Path(args.output)
    # The spec save is confinement-checked against the output dir (Req 10.1):
    # ``OutputRoot.path`` raises ``OutsideOutputError`` if the resolved path
    # escapes ``args.output``; ``ZoneSpec.save`` then writes to that checked
    # path. Resolve ``build_dir`` to an absolute path first — it is built
    # relative to the CWD, and ``OutputRoot.path`` would otherwise re-join a
    # relative part onto the root and double the output segment.
    spec_rel = (build_dir / f"{args.name}.json").resolve()
    spec_path = OutputRoot(args.output).path(str(spec_rel))
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
    g.add_argument("name", type=_build_name_arg,
                   help="Build name / zone stem (lower-cased; must match "
                        "[a-z0-9_]+, else exit 2)")
    # --zone-type is the current option; --theme is a deprecated alias that
    # shares the same dest (later option wins). Both convert through
    # _zone_type_arg, which maps the legacy "outdoor" forward and REJECTS a
    # disabled or undefined value (exit 2, listing the enabled set). The
    # choices=list(DEFINED_ZONE_TYPES) is kept as the defined vocabulary the
    # surface exposes; _zone_type_arg runs first and is the real gate.
    g.add_argument("--zone-type", dest="zone_type", default=DEFAULT_ZONE_TYPE,
                   type=_zone_type_arg, choices=list(DEFINED_ZONE_TYPES),
                   metavar="{dungeon,city,wilderness}",
                   help="Zone type to generate (disabled types exit 2)")
    g.add_argument("--theme", dest="zone_type", type=_zone_type_arg,
                   metavar="{dungeon,city}",
                   help="Deprecated alias for --zone-type (accepts legacy "
                        "'outdoor'; disabled types exit 2)")
    # Geometry-slice controls (Req 2.2, 2.3). Range-checked type= functions
    # exit 2 on an out-of-domain value before any build/write.
    g.add_argument("--rooms", type=_rooms_arg, default=5,
                   help="Number of rooms (1-30)")
    g.add_argument("--size", default="medium",
                   choices=["small", "medium", "large", "huge"],
                   help="Overall footprint")
    g.add_argument("--verticality", default="moderate",
                   choices=["flat", "moderate", "dramatic"],
                   help="How much floor height varies between rooms")
    g.add_argument("--locks", type=_locks_arg, default=0,
                   help="Number of locked gates (0-5)")
    g.add_argument("--seed", type=_seed_arg, default=None,
                   help="Random seed (0-2147483647)")
    g.add_argument("--edges", type=_edges_arg, default=None,
                   help="Wilderness Rim per side, e.g. N=zoneline,E=river "
                        "(types: mountain, river, zoneline; unnamed sides "
                        "are mountain)")
    g.add_argument("--output", default="output", help="Output directory")
    g.add_argument("--ter-version", type=int, default=2, choices=[2, 3])
    g.add_argument("--no-validate", "--allow-invalid", dest="no_validate",
                   action="store_true",
                   help="Skip the traversability gate (build even an invalid "
                        "zone — for debugging broken seeds on purpose)")
    g.set_defaults(func=cmd_generate)

    args = parser.parse_args(argv)
    if (getattr(args, "edges", None) is not None
            and canonical_zone_type(args.zone_type) != "wilderness"):
        parser.error("--edges only applies to --zone-type wilderness")

    # Refusal (Req 10.2): right after parsing — before any build or write —
    # refuse an output directory that resolves to, inside, or around the
    # EQ_PATH install, so a build can never write into (or over) EverQuest.
    # EQ_PATH unset ⇒ nothing to compare, the check passes. Exit 2 (a usage
    # error), naming BOTH paths.
    output = getattr(args, "output", None)
    if output is not None:
        try:
            assert_output_allowed(Path(output), env_value("EQ_PATH"))
        except OutsideOutputError as exc:
            print(f"error: {exc}", file=sys.stderr)
            sys.exit(2)

        # Keep dependency temp files inside the output dir, process-wide, set
        # HERE in main() (never at import, so the test suite's temp dirs are
        # untouched). The <output>/.tmp dir is confinement-checked and created.
        import tempfile
        tempfile.tempdir = str(OutputRoot(output).mkdir(".tmp"))

    args.func(args)


if __name__ == "__main__":
    main()
