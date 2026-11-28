"""
main.py
-------
CLI entry point for eq_s3d.

Commands:
    generate   — procedurally generate a zone from parameters
    export     — export a build as a takeover of an existing zone (default arena)
    --edit     — the next version of a Server zone from feedback on one of its versions

Usage::

    python main.py generate myrealm --zone-type dungeon --rooms 5
    python main.py export output/myrealm/v1 --shortname arena
    python main.py --edit gen_20261118_ab12cd 1 "make the boss room a forge"
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from ai.expand import plan_to_spec
from ai.schema import (
    LAYOUT_ZONE_TYPES, SCALE_CONTROLS, VALID_FEATURES, VALID_LAYOUTS, ZonePlan, available_overlays,
    available_rule_sets, available_wall_styles, VALID_SITES, available_inhabitants,
    DECOR_ZONE_TYPES, DEFAULT_DECOR, VALID_DECOR, decor_layers,
    MAX_DISTRICT_PROPOSALS, VALID_DISTRICT_RELATIONSHIPS, VALID_DUNGEON_THEMES,
)
from core.env import env_value
from core.paths import (
    OutputRoot,
    OutsideOutputError,
    assert_output_allowed,
    new_zone_id,
)
from generators.builder import BUILD_NAME_RE, with_decor_layers, with_district_notes
from generators.pipeline import generate_validated, GenerationFailed
from generators.quality import quality_summary
from generators.zone_types import (
    DEFINED_ZONE_TYPES, DEFAULT_ZONE_TYPE, LANDSCAPE_ZONE_TYPES,
    canonical_zone_type, enabled_zone_types, is_enabled,
)


# ---------------------------------------------------------------------------
# Range-checked argparse ``type=`` functions (Req 2.5)
#
# Every one raises ``argparse.ArgumentTypeError`` for an out-of-domain value,
# so argparse exits 2 DURING parse_args — before ``cmd_generate`` runs and so
# before any build or write. The geometry-slice controls are the surface, plus the
# options later steps added (the Districts are step 20's); there is no target /
# topology option (Req 2.3, 8.1).
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
_decor_seed_arg = _int_in_range("--decor-seed", 0, 2_147_483_647)
_rooms_seed_arg = _int_in_range("--rooms-seed", 0, 2_147_483_647)


def _edges_arg(value: str) -> dict:
    """``--edges`` converter: ``N=zoneline,E=river`` -> four-side Rim
    declaration (unnamed sides are mountain). Exit 2 on a bad side/type."""
    from generators.wilderness.build import parse_edges
    try:
        return parse_edges(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc))


def _layout_arg(value: str) -> str:
    """``--layout`` converter: one of ``VALID_LAYOUTS`` (case-insensitive),
    else exit 2 naming them."""
    v = value.strip().lower()
    if v not in VALID_LAYOUTS:
        raise argparse.ArgumentTypeError(
            f"{value!r} is not one of: {', '.join(VALID_LAYOUTS)}")
    return v


def _rule_set_arg(value: str) -> str:
    """``--rule-set`` converter: a base set under ``rules/topology/`` (or
    ``""`` for the theme's set), else exit 2 naming them."""
    v = value.strip()
    sets = available_rule_sets()
    if v and v not in sets:
        raise argparse.ArgumentTypeError(
            f"{value!r} is not one of: {', '.join(sets)} "
            "(or \"\" for the theme's set)")
    return v


def _decor_layer_arg(value: str) -> str:
    """``--decor-layer`` converter: a decor layer under ``rules/decor/layers/``,
    else exit 2 naming them."""
    try:
        return (decor_layers(value) or ("",))[0]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc))


def print_quality(block) -> None:
    """A Quality_Degraded build's lines (umbrella 25.9): the reason, the out-of-band count
    and each entry's metric, value, ``lo`` and ``hi``. A passing build (or none) prints
    nothing. ``block`` is the Quality_Block (``generators.quality.quality_summary``)."""
    if not block or not block.get("degraded"):
        return
    entries = block.get("out_of_band") or []
    print(f"  Quality: walkable but outside quality targets ({block.get('reason')}), "
          f"{len(entries)} metric(s) out of band:")
    for o in entries:
        print(f"    - {o['metric']} = {o['value']:.3f} (band {_bound(o.get('lo'))}"
              f"..{_bound(o.get('hi'))})")


def _bound(value) -> str:
    """A band end as the CLI prints it; an open end is ``-``."""
    return "-" if value is None else f"{value:g}"


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
    # The layout engine (graph-layout Req 7.1): only named when given; a run
    # without ``--layout`` takes the plan default (graph on a dungeon /
    # outdoor dungeon since task 21; ``--layout classic`` for TinyKeep).
    for key in ("layout", "rule_set", "walls", "features", "finish", "structure", "clutter", "overlay",
                "decor", "decor_seed", "decor_layers", "rooms_seed"):
        if getattr(args, key, None) is not None:
            controls[key] = getattr(args, key)
    # Districts (districts spec Req 4.3): only named when given, so a run without them
    # plans as before. On a zone type other than a dungeon they are ignored with a note (A2).
    if getattr(args, "districts", False):
        controls["districts"] = True
    for key in ("district_plan", "district_relationship"):
        if getattr(args, key, None) is not None:
            controls[key] = getattr(args, key)
    # Sites (wilderness / outdoor dungeon): only named when given, so the
    # sidecar says who set them.
    sites_source = None
    for key in ("sites", "inhabitant"):
        if getattr(args, key, None) is not None:
            controls[key] = getattr(args, key)
            sites_source = "cli"
    plan = ZonePlan.from_controls(controls)
    # The positional is the Build_Name (lower-cased + validated by
    # ``_build_name_arg``); it names every artifact. The zone id — the per-build
    # directory — is ``new_zone_id(prefix=<name>)`` so two runs with the same
    # name land in DIFFERENT directories (Req 8.3) while every file inside still
    # carries the Build_Name stem.
    plan.name = args.name
    zone_id = new_zone_id(prefix=args.name)

    edges = getattr(args, "edges", None)
    trees = getattr(args, "trees", None)

    def factory(seed, rooms_seed=None):
        # ``rooms_seed`` is the pipeline's rooms reroll on a gate failure (task 19).
        p = plan if rooms_seed is None else dataclasses.replace(plan, rooms_seed=rooms_seed)
        notes: list = []      # fresh per spec: a retry's District notes are its own
        spec = plan_to_spec(p, seed=seed, edges=edges, trees=trees, trees_source="cli",
                            sites_source=sites_source, warnings=notes)
        return with_decor_layers(with_district_notes(spec, notes), p.decor_layers)

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
            verticality=plan.verticality,
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
    if vb.quality is not None:
        print_quality(quality_summary(vb.quality))
    for note in vb.spec.notes:          # District notes, also in the sidecar's warnings
        print(f"  note: {note}")


def cmd_export(args) -> None:
    """Export a build directory (step 17 Req 4.3): the archive, maps, SQL, sidecar,
    INSTALL.txt and the bundle in ``<build dir>/export/<short>/``. An unknown short name
    or a build directory that isn't one exits 2 before anything is written; a build that
    can't be exported or fails the format check exits 1."""
    from generators.export import (ExportError, UnknownShortname, export_build,
                                   resolve_shortname, write_bundle)
    try:
        short = resolve_shortname(args.shortname)
    except UnknownShortname as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
    build_dir = Path(args.build_dir)
    if not build_dir.is_dir():
        print(f"error: no build directory {build_dir}", file=sys.stderr)
        sys.exit(2)
    try:
        assert_output_allowed(build_dir, env_value("EQ_PATH"))
        res = export_build(build_dir, short, clear_spawns=args.clear_spawns)
    except OutsideOutputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
    except ExportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Exported {build_dir} as '{short}' -> {res.dir}")
    for w in res.warnings:
        print(f"  warning: {w}")
    if not res.format.passed:
        print("  Format check FAILED; no SQL or bundle written:", file=sys.stderr)
        for msg in res.format.messages:
            print(f"    - {msg}", file=sys.stderr)
        sys.exit(1)
    bundle = write_bundle(build_dir, short)
    for p in res.files + [bundle]:
        print(f"  {p.relative_to(res.dir).as_posix()}")
    print(f"  Read {res.dir / 'INSTALL.txt'} before installing; apply the SQL by hand.")


def cmd_edit(zone: str, version: str, text: str) -> None:
    """``--edit <zone> <version> "<text>"`` (zone-generator-edits Req 3.6): the edit route's
    own path (``server.app.edit_zone``) on a zone in the Server's output folder. Prints the new
    version, its ops and notes; an edit that applies nothing exits 1 with why, a bad zone or
    version exits 2."""
    from fastapi import HTTPException

    import server.app as app_mod

    v = int(version) if version.isdigit() else version
    try:
        req = app_mod.EditRequest(zone=zone, version=v, text=text)
        res = app_mod.edit_zone(req)
    except HTTPException as exc:
        print(f"error: {exc.detail}", file=sys.stderr)
        sys.exit(2 if exc.status_code in (400, 404) else 1)
    except ValueError as exc:                        # the request model refused it
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
    if res.applied:
        print(f"Edited {zone} v{res.parent} -> v{res.version} ({res.how}, "
              f"interpreter {res.interpreter})")
        for op in res.ops:
            print(f"  op: {json.dumps(op)}")
        if res.build is not None:
            print_quality(res.build.quality)
    else:
        print(f"Nothing applied to {zone} v{res.parent}", file=sys.stderr)
    for note in res.notes:
        print(f"  note: {note}", file=sys.stderr if not res.applied else sys.stdout)
    for d in res.diagnostics:
        print(f"  gate: seed {d['seed']} failed [{', '.join(d['checks']) or 'validation'}]",
              file=sys.stderr)
    if res.help:
        print(f"  {res.help}", file=sys.stderr)
    if res.applied:
        print(f"  Files: {app_mod.OUTPUT_DIR / zone / f'v{res.version}'}")
    else:
        sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="eq_s3d", description="Agentic EverQuest zone generator")
    parser.add_argument("--edit", nargs=3, metavar=("ZONE", "VERSION", "TEXT"), default=None,
                        help="Make the next version of a Server zone (output/web/<zone>) from "
                             "feedback on VERSION (2 or v2), e.g. --edit <zone> 1 \"less decor\"")
    sub = parser.add_subparsers(dest="command")

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
                   metavar="{dungeon,city,wilderness,outdoor_dungeon}",
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
                   help="Wilderness / outdoor-dungeon Rim per side, e.g. "
                        "N=zoneline,E=river "
                        "(types: mountain, river, zoneline; unnamed sides "
                        "are mountain)")
    g.add_argument("--trees", default=None,
                   choices=["none", "sparse", "normal", "dense"],
                   help="Wilderness / outdoor-dungeon tree density "
                        "(default normal)")
    g.add_argument("--sites", default=None, choices=VALID_SITES,
                   help="Wilderness / outdoor-dungeon Sites: camps, huts, "
                        "farmsteads, towers, shrines, ruins (default normal)")
    g.add_argument("--inhabitant", default=None, choices=available_inhabitants(),
                   help="Wilderness / outdoor-dungeon: who builds every Site "
                        "(default: the biome's mix)")
    g.add_argument("--layout", type=_layout_arg, default=None,
                   metavar="{" + ",".join(VALID_LAYOUTS) + "}",
                   help="Layout engine for dungeon / outdoor_dungeon: graph "
                        "(rule-grown, the default) or classic (TinyKeep)")
    g.add_argument("--rule-set", dest="rule_set", type=_rule_set_arg, default=None,
                   help="Graph layout base rule set (" + ", ".join(available_rule_sets())
                        + "); default: the dungeon theme's")
    g.add_argument("--walls", dest="walls", choices=available_wall_styles(), default=None,
                   help="Graph layout wall style; default: the dungeon theme's")
    g.add_argument("--features", dest="features", choices=VALID_FEATURES, default=None,
                   help="Graph layout: how much stands in rooms (default normal)")
    for name in SCALE_CONTROLS:
        g.add_argument(f"--{name}", dest=name, type=int, choices=range(11), metavar="0-10", default=None,
                       help=f"Graph layout: lean each room's {name} this way; default: the rules alone")
    g.add_argument("--overlay", dest="overlay", choices=available_overlays(), default=None,
                   help="Graph layout: what's happened to the place since, on top of its race and theme")
    g.add_argument("--decor", dest="decor", choices=VALID_DECOR, default=None,
                   help="Dungeon, city or outdoor dungeon: how many Props (furniture, lights, "
                        f"clutter) stand in the rooms (default {DEFAULT_DECOR}: no Props unless "
                        "the prompt or this asks; needs EQ_PATH)")
    g.add_argument("--decor-seed", dest="decor_seed", type=_decor_seed_arg, default=None,
                   help="Reroll the Props alone (0-2147483647); default: the zone's seed")
    g.add_argument("--decor-layer", dest="decor_layers", type=_decor_layer_arg, action="append",
                   default=None, metavar="LAYER",
                   help="A decor layer (rules/decor/layers/) on top of the dungeon theme's; "
                        "repeat for more, merged in order")
    g.add_argument("--rooms-seed", dest="rooms_seed", type=_rooms_seed_arg, default=None,
                   help="Reroll the rooms and Sites on the same World (0-2147483647); "
                        "default: the zone's seed")
    g.add_argument("--districts", dest="districts", action="store_true",
                   help="Dungeon: split the zone into contrasting areas (Districts) joined by "
                        "one corridor each (ignored with a note on other zone types)")
    g.add_argument("--district-theme", dest="district_plan", action="append",
                   choices=VALID_DUNGEON_THEMES, default=None, metavar="PURPOSE",
                   help="With --districts: one District's Purpose, in District order; repeat "
                        f"for up to {MAX_DISTRICT_PROPOSALS} (the rest follow the relationship)")
    g.add_argument("--district-relationship", dest="district_relationship",
                   choices=VALID_DISTRICT_RELATIONSHIPS, default=None,
                   help="With --districts: how the Districts relate (default sequential)")
    g.add_argument("--output", default="output", help="Output directory")
    g.add_argument("--ter-version", type=int, default=2, choices=[2, 3])
    g.add_argument("--no-validate", "--allow-invalid", dest="no_validate",
                   action="store_true",
                   help="Skip the traversability gate (build even an invalid "
                        "zone — for debugging broken seeds on purpose)")
    g.set_defaults(func=cmd_generate)

    e = sub.add_parser("export", help="Export a build as a takeover of an existing zone")
    e.add_argument("build_dir", help="The build directory, e.g. output/myrealm/v1")
    e.add_argument("--shortname", default=None,
                   help="The existing zone to take over (default arena; any case; "
                        "unknown names exit 2)")
    e.add_argument("--clear-spawns", dest="clear_spawns", action="store_true",
                   help="The SQL also deletes the zone's spawns")
    e.set_defaults(func=cmd_export)

    args = parser.parse_args(argv)
    if args.edit is not None:
        if args.command is not None:
            parser.error("--edit takes no command")
        cmd_edit(*args.edit)
        return
    if args.command is None:
        parser.error("a command is required (generate, export) or --edit")
    if args.command == "export":
        args.func(args)
        return
    if (getattr(args, "edges", None) is not None
            and canonical_zone_type(args.zone_type) not in LANDSCAPE_ZONE_TYPES):
        parser.error("--edges only applies to --zone-type wilderness or "
                     "outdoor_dungeon")
    if (getattr(args, "trees", None) is not None
            and canonical_zone_type(args.zone_type) not in LANDSCAPE_ZONE_TYPES):
        parser.error("--trees only applies to --zone-type wilderness or "
                     "outdoor_dungeon")
    for opt in ("sites", "inhabitant"):
        if (getattr(args, opt, None) is not None
                and canonical_zone_type(args.zone_type) not in LANDSCAPE_ZONE_TYPES):
            parser.error(f"--{opt} only applies to --zone-type wilderness or "
                         "outdoor_dungeon")
    for opt in ("decor", "decor_seed"):
        if (getattr(args, opt, None) is not None
                and canonical_zone_type(args.zone_type) not in DECOR_ZONE_TYPES):
            parser.error(f"--{opt.replace('_', '-')} only applies to --zone-type "
                         "dungeon, city or outdoor_dungeon")
    if len(getattr(args, "district_plan", None) or ()) > MAX_DISTRICT_PROPOSALS:
        parser.error(f"--district-theme names at most {MAX_DISTRICT_PROPOSALS} Districts")
    # As --edges / --trees: a graph layout or a rule set on a zone type that
    # doesn't take them is a usage error (the default classic is a no-op).
    if canonical_zone_type(args.zone_type) not in LAYOUT_ZONE_TYPES:
        if getattr(args, "layout", None) == "graph":
            parser.error("--layout graph only applies to --zone-type dungeon or "
                         "outdoor_dungeon")
        if getattr(args, "rule_set", None):
            parser.error("--rule-set only applies to --zone-type dungeon or "
                         "outdoor_dungeon")
        if getattr(args, "features", None):
            parser.error("--features only applies to --zone-type dungeon or "
                         "outdoor_dungeon")
        if getattr(args, "walls", None):
            parser.error("--walls only applies to --zone-type dungeon or "
                         "outdoor_dungeon")
        for name in SCALE_CONTROLS + ("overlay",):
            if getattr(args, name, None) is not None:
                parser.error(f"--{name} only applies to --zone-type dungeon or outdoor_dungeon")

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
