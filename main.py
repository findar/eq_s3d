"""
main.py
-------
CLI entry point for eq_s3d.

Phase 2 commands:
    generate   — procedurally generate a zone from parameters
    preview    — launch the browser preview for a generated zone

Usage::

    python main.py generate myrealm --theme dungeon --rooms 5
    python main.py generate myrealm --theme dungeon --rooms 5 --preview
    python main.py preview myrealm
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from generators.layout import LayoutGenerator
from generators.builder import ZoneBuilder
from generators.zone_spec import ZoneSpec


def cmd_generate(args) -> None:
    print(f"Generating zone '{args.name}' (theme={args.theme}, rooms={args.rooms})")

    gen = LayoutGenerator(theme=args.theme, seed=args.seed)
    spec = gen.generate(args.name, room_count=args.rooms)

    # Save the spec alongside output for inspection / iteration
    out_dir = Path(args.output)
    spec_path = out_dir / f"{args.name}.json"
    spec.save(spec_path)
    print(f"  Spec saved: {spec_path}")

    result = ZoneBuilder(spec).build(output_dir=args.output,
                                     ter_version=args.ter_version)
    print()
    print(result.summary())

    if args.preview:
        _launch_preview(result.glb_path)


def cmd_preview(args) -> None:
    glb = Path(args.output) / f"{args.name}.glb"
    if not glb.exists():
        print(f"GLB not found: {glb}\nRun 'generate' first.")
        sys.exit(1)
    _launch_preview(glb)


def _launch_preview(glb_path) -> None:
    if glb_path is None:
        print("No GLB was produced (is trimesh installed?). Skipping preview.")
        return
    print(f"\nLaunching preview for {glb_path} ...")
    from viewer.serve import serve
    serve(str(glb_path))


def main() -> None:
    parser = argparse.ArgumentParser(prog="eq_s3d", description="Agentic EverQuest zone generator")
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="Procedurally generate a zone")
    g.add_argument("name", help="Zone short name (lowercase, no spaces)")
    g.add_argument("--theme", default="dungeon",
                   choices=["dungeon", "outdoor", "cave", "city"])
    g.add_argument("--rooms", type=int, default=5, help="Number of rooms")
    g.add_argument("--seed", type=int, default=None, help="Random seed")
    g.add_argument("--output", default="output", help="Output directory")
    g.add_argument("--ter-version", type=int, default=2, choices=[2, 3])
    g.add_argument("--preview", action="store_true", help="Launch browser preview")
    g.set_defaults(func=cmd_generate)

    p = sub.add_parser("preview", help="Preview a generated zone in the browser")
    p.add_argument("name", help="Zone short name")
    p.add_argument("--output", default="output")
    p.set_defaults(func=cmd_preview)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
