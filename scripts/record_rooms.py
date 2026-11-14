r"""Record the room corpus (roadmap step 11, Req 13.2; design "Stages and the RoomContext").

Each recording is a zone made from a pinned plan and seed, built, and read back as one
RoomContext per room, per corridor (world-sockets task 14; not stairs or Bridges) and per Site
(``generators/room_context.py``). The files land in
``tests/fixtures/rooms/<name>.json``; decor's tests run on them without building a zone.
Together the recordings hold every room type, wall style and race.

Usage::

    python scripts/record_rooms.py                  # record every recording
    python scripts/record_rooms.py --only temple_giant city_plain
    python scripts/record_rooms.py --check          # re-record in memory, compare, write nothing
    python scripts/record_rooms.py --list           # the recordings and what they cover

When room generation changes on purpose, re-record and commit the new files: the contract
test (``tests/test_room_context.py``, ``slow``) compares a sample of them with what the room
stage makes now.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from generators.room_context import RoomContext, contexts, dumps, load, save, site_contexts  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "rooms"

#: Every recording: a name, the seed, and the plan's fields. Rooms are kept small (size and
#: count) so the corpus stays a few MB; together they cover every room type, wall style and race.
RECORDINGS: List[Dict] = [
    {"name": "fortress_goblin_built", "seed": 101,
     "plan": {"zone_type": "dungeon", "dungeon_theme": "fortress", "dungeon_race": "goblin", "walls": "built"}},
    {"name": "war_city_troll", "seed": 102,
     "plan": {"zone_type": "dungeon", "dungeon_theme": "war_city", "dungeon_race": "troll"}},
    {"name": "warren_kobold_rough", "seed": 103,
     "plan": {"zone_type": "dungeon", "dungeon_theme": "warren", "dungeon_race": "kobold", "walls": "rough"}},
    {"name": "temple_human_hewn", "seed": 104,
     "plan": {"zone_type": "dungeon", "dungeon_theme": "temple", "walls": "hewn"}},
    {"name": "tomb_froglok", "seed": 105,
     "plan": {"zone_type": "dungeon", "dungeon_theme": "tomb", "dungeon_race": "froglok"}},
    {"name": "wizard_lair_gnoll", "seed": 106,
     "plan": {"zone_type": "dungeon", "dungeon_theme": "wizard_lair", "dungeon_race": "gnoll"}},
    {"name": "corrupted_sanctum_sarnak", "seed": 107,
     "plan": {"zone_type": "dungeon", "dungeon_theme": "corrupted_sanctum", "dungeon_race": "sarnak"}},
    {"name": "mine_delve_ogre_rough", "seed": 108,
     "plan": {"zone_type": "dungeon", "dungeon_theme": "mine_delve", "dungeon_race": "ogre", "walls": "rough"}},
    {"name": "sunken_ruin_lizardman", "seed": 109,
     "plan": {"zone_type": "dungeon", "dungeon_theme": "sunken_ruin", "dungeon_race": "lizardman"}},
    {"name": "lava_forge_giant_built", "seed": 110,
     "plan": {"zone_type": "dungeon", "dungeon_theme": "lava_forge", "dungeon_race": "giant", "walls": "built"}},
    {"name": "ice_keep_dragon_hewn", "seed": 111,
     "plan": {"zone_type": "dungeon", "dungeon_theme": "ice_keep", "dungeon_race": "dragon", "walls": "hewn",
              "room_count": 4}},
    {"name": "classic_plain", "seed": 112,
     "plan": {"zone_type": "dungeon", "layout": "classic"}},
    {"name": "city_plain", "seed": 113,
     "plan": {"zone_type": "city"}},
    {"name": "outdoor_cave", "seed": 114,
     "plan": {"zone_type": "outdoor_dungeon"}},
    {"name": "outdoor_tomb_goblin", "seed": 115,
     "plan": {"zone_type": "outdoor_dungeon", "dungeon_theme": "tomb", "dungeon_race": "goblin", "sites": "dense"}},
    {"name": "wilderness_sites", "seed": 116,
     "plan": {"zone_type": "wilderness", "sites": "dense"}},
    {"name": "fortress_classic", "seed": 121,
     "plan": {"zone_type": "dungeon", "dungeon_theme": "fortress", "layout": "classic", "room_count": 10}},
    {"name": "wilderness_orc", "seed": 120,
     "plan": {"zone_type": "wilderness", "sites": "dense", "inhabitant": "orc"}},
    {"name": "wilderness_gnoll", "seed": 119,
     "plan": {"zone_type": "wilderness", "sites": "dense", "inhabitant": "gnoll"}},
    {"name": "wilderness_centaur", "seed": 120,
     "plan": {"zone_type": "wilderness", "sites": "dense", "inhabitant": "centaur"}},
    # Farmsteads are human only; seed 127 gives two, with a hut, a shrine and a ruin (task 11).
    {"name": "wilderness_farmstead", "seed": 127,
     "plan": {"zone_type": "wilderness", "sites": "dense", "inhabitant": "human"}},
]
DEFAULTS = {"room_count": 8, "size": "small"}


def recipe_named(name: str) -> Dict:
    for r in RECORDINGS:
        if r["name"] == name:
            return r
    raise KeyError(f"no recording named {name!r}; see --list")


def record(recipe: Mapping) -> List[RoomContext]:
    """Make the recording's zone (its plan and seed), build its TER, and read every room's,
    corridor's and Site's context from them."""
    from ai.expand import plan_to_spec
    from ai.schema import ZonePlan
    from generators.backends import backend_for

    name = "rc_" + recipe["name"]
    plan = ZonePlan(name=name, **{**DEFAULTS, **recipe["plan"]})
    spec = plan_to_spec(plan, seed=recipe["seed"])
    ter = backend_for(spec.zone_type).build(spec, f"ter_{name}", 2)
    rooms = contexts(spec, ter) if spec.rooms else []
    if spec.wilderness is not None:
        rooms += site_contexts(spec, ter)
    return rooms


def path_for(name: str, folder: Path = FIXTURES) -> Path:
    return folder / f"{name}.json"


def coverage(rooms: Sequence[RoomContext]) -> Dict[str, set]:
    """What a set of contexts holds: room types, wall styles, races, zone types, Sites."""
    out: Dict[str, set] = {"room_type": set(), "style": set(), "race": set(), "zone_type": set(), "site": set()}
    for c in rooms:
        if c.source == "site":
            out["site"].add(c.room_type)
        else:
            if c.room_type:
                out["room_type"].add(c.room_type)
            if c.style:
                out["style"].add(c.style)
            out["race"].add(c.race)
        out["zone_type"].add(c.zone_type)
    return out


def missing(rooms: Sequence[RoomContext]) -> Dict[str, List[str]]:
    """Every room type, wall style, race and Site kind the contexts lack ("" is the default
    race)."""
    from ai.schema import VALID_DUNGEON_RACES
    from generators.semantics import ROOM_TYPES
    from generators.sites.rules import load_sites
    from generators.wall_styles import load_styles

    have = coverage(rooms)
    want = {"room_type": set(ROOM_TYPES), "style": set(load_styles()), "race": set(VALID_DUNGEON_RACES) | {""},
            "site": set(load_sites().kinds)}
    return {k: sorted(want[k] - have[k]) for k in want if want[k] - have[k]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--only", nargs="+", metavar="NAME", help="record just these")
    ap.add_argument("--check", action="store_true", help="compare with the saved files; write nothing")
    ap.add_argument("--list", action="store_true", help="list the recordings")
    ap.add_argument("--out", type=Path, default=FIXTURES)
    args = ap.parse_args(argv)

    if args.list:
        for r in RECORDINGS:
            print(f"{r['name']:28s} seed {r['seed']:<5d} {r['plan']}")
        return 0
    todo = [recipe_named(n) for n in args.only] if args.only else RECORDINGS
    args.out.mkdir(parents=True, exist_ok=True)
    every: List[RoomContext] = []
    differ = []
    start = time.time()
    for recipe in todo:
        t = time.time()
        rooms = record(recipe)
        every += rooms
        target = path_for(recipe["name"], args.out)
        if args.check:
            _, saved = load(target)
            same = [dumps(c.to_dict()) for c in rooms] == [dumps(c.to_dict()) for c in saved]
            if not same:
                differ.append(recipe["name"])
            state = "same" if same else "DIFFERS"
        else:
            save(target, recipe, rooms)
            state = f"{target.stat().st_size / 1024:.0f} KB"
        print(f"{recipe['name']:28s} {len(rooms):3d} contexts  {time.time() - t:5.1f}s  {state}")
    print(f"{len(every)} contexts in {time.time() - start:.0f}s")
    if not args.only:
        size = sum(p.stat().st_size for p in args.out.glob("*.json"))
        print(f"corpus: {size / 1024 / 1024:.2f} MB")
        for k, v in coverage(every).items():
            print(f"  {k}: {len(v)} {sorted(v)}")
        gaps = missing(every)
        if gaps:
            print(f"MISSING: {gaps}")
            return 1
    if differ:
        print(f"differ from the saved files: {', '.join(differ)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
