r"""Record the World corpus (roadmap step 12, Req 7.1, 7.3; design "Testing in isolation").

Each recording is the World stage's result (``generators.world.world_for``) for a pinned zone
type, seed and world controls, saved as the World's stable JSON text in
``tests/fixtures/worlds/<name>.json``. The Attach tests load these files and run one Socket's
Attachment without making terrain, building a TER or running the zone gate. Together the
recordings hold every biome, every approach side (N, S, E, W), water and none (for each
landscape zone type), and every Socket kind the World stage makes (``door`` is reserved and
nothing makes one, so it is not recorded).

Usage::

    python scripts/record_worlds.py                  # record every recording
    python scripts/record_worlds.py --only outdoor_n wilderness_river
    python scripts/record_worlds.py --check          # re-make in memory, compare, write nothing
    python scripts/record_worlds.py --list           # the recordings and what they cover

When the World stage changes on purpose, re-record and commit the new files: the contract test
(``tests/test_world_corpus.py``, ``slow``) compares them with what the World stage makes now.
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

from generators.world import KINDS, World, load, save, world_for  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "worlds"

#: Zone types with a landscape: each is recorded with water and without.
LANDSCAPE = ("wilderness", "outdoor_dungeon")
SIDES = ("N", "S", "E", "W")

#: Every recording: a name, the zone type, the seed and the world controls (``edges``,
#: ``biome``) passed to ``world_for``. An outdoor dungeon's approach side is DRAWN FROM THE
#: SEED, not asked for; ``side`` is what that seed gives (the ``hill0`` Socket's side), and the
#: test holds the file to it. Seeds were found by sweeping 1-12 (all-mountain edges: 1 E, 2 W,
#: 4 S, 11 N; 11 is the only N among them). Water comes from a ``river`` edge: with
#: none, no seed has water. Sizes: about 1 KB for a root World, 28 KB for a dry outdoor
#: dungeon, 41 KB for a wet one, 79 KB for a dry wilderness and 142 KB for a wet one.
RECORDINGS: List[Dict] = [
    {"name": "dungeon_root", "zone_type": "dungeon", "seed": 7},
    {"name": "city_root", "zone_type": "city", "seed": 7},
    {"name": "wilderness_plains", "zone_type": "wilderness", "seed": 1},
    # A river on S and a zone line on E: water regions, sunk bed, a zoneline gap.
    {"name": "wilderness_river", "zone_type": "wilderness", "seed": 3,
     "edges": {"E": "zoneline", "S": "river"}},
    {"name": "outdoor_n", "zone_type": "outdoor_dungeon", "seed": 11, "side": "N"},
    {"name": "outdoor_s", "zone_type": "outdoor_dungeon", "seed": 4, "side": "S"},
    {"name": "outdoor_e", "zone_type": "outdoor_dungeon", "seed": 1, "side": "E"},
    {"name": "outdoor_w", "zone_type": "outdoor_dungeon", "seed": 2, "side": "W"},
    # Wet, with a zone line: seed 1 with these edges approaches from S (the river's side).
    {"name": "outdoor_river", "zone_type": "outdoor_dungeon", "seed": 1, "side": "S",
     "edges": {"S": "river", "W": "zoneline"}},
]


def recipe_named(name: str) -> Dict:
    for r in RECORDINGS:
        if r["name"] == name:
            return r
    raise KeyError(f"no recording named {name!r}; see --list")


def record(recipe: Mapping) -> World:
    """Make the recording's World from its zone type, seed and world controls."""
    return world_for(recipe["zone_type"], recipe["seed"], biome=recipe.get("biome"),
                     edges=recipe.get("edges"))


def path_for(name: str, folder: Path = FIXTURES) -> Path:
    return folder / f"{name}.json"


def load_world(name: str, folder: Path = FIXTURES) -> World:
    """A recorded World by its recording name."""
    return load(path_for(name, folder))


def is_wet(world: World) -> bool:
    """A World has water when it has a water region (a river edge's channel)."""
    return any(r.get("kind") == "water" for r in world.regions)


def coverage(worlds: Sequence[World]) -> Dict[str, set]:
    """What a set of Worlds holds: zone types, biomes, approach sides (``hillside`` Sockets),
    water (``(zone_type, wet)`` for the landscape zone types) and Socket kinds."""
    out: Dict[str, set] = {"zone_type": set(), "biome": set(), "side": set(), "water": set(),
                           "kind": set()}
    for w in worlds:
        zt = w.recipe["zone_type"]
        out["zone_type"].add(zt)
        if w.recipe.get("biome"):
            out["biome"].add(w.recipe["biome"])
        if zt in LANDSCAPE:
            out["water"].add((zt, is_wet(w)))
        for s in w.sockets:
            out["kind"].add(s.kind)
            if s.kind == "hillside":
                out["side"].add(s.side)
    return out


def wanted() -> Dict[str, set]:
    """What the corpus must hold. ``door`` is a reserved kind nothing makes (design question 3)."""
    from generators.wilderness.biome_resolve import V1_BIOMES
    from generators.zone_types import DEFINED_ZONE_TYPES

    return {"zone_type": set(DEFINED_ZONE_TYPES), "biome": set(V1_BIOMES), "side": set(SIDES),
            "water": {(zt, wet) for zt in LANDSCAPE for wet in (False, True)},
            "kind": set(KINDS) - {"door"}}


def missing(worlds: Sequence[World]) -> Dict[str, List]:
    """Every zone type, biome, approach side, water case and Socket kind the Worlds lack."""
    have, want = coverage(worlds), wanted()
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
            extra = {k: v for k, v in r.items() if k not in ("name", "zone_type", "seed")}
            print(f"{r['name']:20s} {r['zone_type']:16s} seed {r['seed']:<4d} {extra or ''}")
        return 0
    todo = [recipe_named(n) for n in args.only] if args.only else RECORDINGS
    if not args.check:
        args.out.mkdir(parents=True, exist_ok=True)
    every: List[World] = []
    differ = []
    start = time.time()
    for recipe in todo:
        t = time.time()
        world = record(recipe)
        every.append(world)
        target = path_for(recipe["name"], args.out)
        if args.check:
            same = target.is_file() and target.read_text(encoding="utf-8") == world.to_json()
            if not same:
                differ.append(recipe["name"])
            state = "same" if same else "DIFFERS"
        else:
            save(target, world)
            state = f"{target.stat().st_size / 1024:.0f} KB"
        print(f"{recipe['name']:20s} {[s.id for s in world.sockets]!s:22s} {time.time() - t:5.1f}s  {state}")
    print(f"{len(every)} Worlds in {time.time() - start:.1f}s")
    if not args.only:
        if not args.check:
            size = sum(p.stat().st_size for p in args.out.glob("*.json"))
            print(f"corpus: {size / 1024 / 1024:.2f} MB")
        for k, v in coverage(every).items():
            print(f"  {k}: {sorted(v)}")
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
