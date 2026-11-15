r"""Decorate one room and write a GLB of it alone (roadmap step 11, Req 13.5; design "Looking
at one room"). A thin command line on ``generators/decor/room_view.py`` (decor-rules task 4),
which the Server's room view (``POST /api/room_decor``) uses too.

Reads one RoomContext file (a recording of ``tests/fixtures/rooms/``, a build's
``<name>.rooms.json``, or any file ``generators/room_context.save`` wrote), decorates one room as a
build does (``room_view.decorate_room``) and writes ``<out>/<recording>_<room>.glb``: the room's
floor (reached floor grey, the Spine and the doors' Throats tinted), its wall faces as they were
sampled from the built walls, its Features, a marker on each POI, and the Props.
``<out>/<recording>_<room>.decor.json`` holds the report (Props, POIs, drops). A look in seconds
instead of a zone build.

Props are the client's own models, read from the install (``EQ_PATH``, or ``--eq-path``;
``F:\everquest_rof2`` here), each coloured by its textures' mean colour. Without the install
(or with ``--boxes``) each Prop is a box of the catalogue's measured size, coloured by its
Category, and the script says so. A recording has no built wall mesh, so wall Props stand where
placement put them (a build's own room comes out flush in the Server's room view).

Usage::

    python scripts/decor_room.py tests/fixtures/rooms/war_city_troll.json --out output/decor_room
    python scripts/decor_room.py <file> --room room_6 --control dense --decor-seed 3
    python scripts/decor_room.py <file> --layer tomb     # one more decor layer (repeatable)

The rules take the layers a build would: the theme's and race's (``rules/decor/themes.toml``;
from the recording's plan, else a corridor's context, which carries the zone's), then each
``--layer``.
    python scripts/decor_room.py <file> --any-use       # preview: count use = "review" models too
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from generators.decor.catalogue import load as load_catalogue  # noqa: E402
from ai import schema  # noqa: E402
from generators.decor.rules import CONTROLS, DEFAULT_CONTROL, layers_for  # noqa: E402
from generators.decor.room_view import (  # noqa: E402,F401 - Meshes, prop_parts, room_parts: scripts/stage.py's
    Meshes, any_use, decorate_room, eq_path_of, prop_parts, room_parts, write_glb, zone_theme_race)
from generators.room_context import load  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("context", help="a RoomContext file (tests/fixtures/rooms/<name>.json, <build>.rooms.json)")
    ap.add_argument("--out", default="output/decor_room", help="folder for the GLB (default output/decor_room)")
    ap.add_argument("--room", help="the room's id (default: the file's first)")
    ap.add_argument("--control", default=DEFAULT_CONTROL, choices=CONTROLS)
    ap.add_argument("--decor-seed", type=int, help="salt the decor stream (default: the room's seed)")
    ap.add_argument("--layer", action="append", default=[], help="a decor layer to merge on (repeatable)")
    ap.add_argument("--any-use", action="store_true", help='count use = "review" models as usable (preview only)')
    ap.add_argument("--boxes", action="store_true", help="draw every Prop as a box, without the install")
    ap.add_argument("--eq-path", help="the EverQuest install (default EQ_PATH, else F:\\everquest_rof2)")
    args = ap.parse_args(argv)

    path = Path(args.context)
    _recipe, rooms = load(path)
    room = args.room or rooms[0].id
    if room not in {c.id for c in rooms}:
        raise SystemExit(f"no room {room!r}; the file holds {', '.join(c.id for c in rooms)}")
    # The layers a build of it takes: its theme's and race's (themes.toml), then --layer's.
    ctx = next(c for c in rooms if c.id == room)
    theme, race = zone_theme_race(_recipe, rooms, ctx)
    layers = layers_for(theme, race, args.layer, schema.RULES_DECOR_DIR)
    eq = None if args.boxes else eq_path_of(args.eq_path)
    cat = load_catalogue()
    glb, report = decorate_room(rooms, room, seed=args.decor_seed, control=args.control, layers=layers,
                                eq_path=eq, catalogue=cat, preview_any_use=args.any_use)
    out = Path(args.out)
    stem = f"{path.stem.removesuffix('.rooms')}_{room}"
    out.mkdir(parents=True, exist_ok=True)
    glb_path = out / f"{stem}.glb"
    glb_path.write_bytes(glb)
    (out / f"{stem}.decor.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")

    r = report["room"]
    kinds = {}
    for p in report["props"]:
        kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
    print(f"{r['id']}: {r['room_type'] or r['kind'] or r['source']} ({r['race'] or '-'}, {r['theme'] or '-'}, "
          f"{r['zone_type']}), Sets {', '.join(report['sets'])}{', bare' if report['bare'] else ''}"
          + (f", layers {', '.join(report['layers'])}" if report["layers"] else ""))
    print(f"  {len(report['props'])} Props: " + ", ".join(f"{k} x{n}" for k, n in sorted(kinds.items())))
    if report["drops"]:
        reasons = {}
        for x in report["drops"]:
            reasons[x["reason"]] = reasons.get(x["reason"], 0) + 1
        print(f"  {len(report['drops'])} dropped: " + ", ".join(f"{k} x{n}" for k, n in sorted(reasons.items())))
    usable = len(cat.usable())
    if usable < 200 and not args.any_use:
        print(f"  note: only {usable} models are use = \"yes\"; --any-use previews with every catalogued model")
    if eq is None:
        why = "--boxes" if args.boxes else "no EverQuest install (EQ_PATH)"
        print(f"  note: {why}: Props drawn as boxes of their measured size")
    for note in report["notes"]:
        if eq is not None:
            print(f"  note: {note}")
    problems = report["check"]
    print("  room check: " + ("ok" if not problems else "; ".join(problems)))
    print(f"  wrote {glb_path} in {report['took_ms'] / 1000:.1f} s")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
