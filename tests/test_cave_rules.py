"""The cave Purpose's rule files (step 21 task 2; Requirements 2.1-2.3, amendment A1).

A cave's rooms draw a low finish, so they take the `rough` wall style and never `built`;
it grows with the warren set, whose kinds all map to cave Room_Types; its new Room_Types
have recipes; its wall and floor resolve to their own cave_rock textures.
"""

import tomllib
from collections import Counter
from pathlib import Path

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators import semantics
from generators.room_layouts import load_layouts
from generators.room_scales import load_scales
from generators.textures.recipes import resolve
from generators.topology.ruleset import load_theme_map

TOPOLOGY = Path(__file__).resolve().parents[1] / "rules" / "topology"
NEW_TYPES = ("cave_mouth", "cavern", "crystal_grotto", "grotto")


def _graph_cave(seed):
    plan = ZonePlan(name="cv", zone_type="dungeon", layout="graph", dungeon_theme="cave",
                    room_count=6 + seed).validate()
    return plan_to_spec(plan, seed=seed)


def test_cave_rooms_are_mostly_rough_and_never_built():
    """A1. Only the graph layout draws a finish per room (the classic layout's rooms keep the
    box walls), so the share is over 20 graph caves of 6-25 rooms."""
    styles = Counter()
    for seed in range(20):
        spec = _graph_cave(seed)
        styles += Counter(spec.layout["rooms"][r.id]["style"] for r in spec.rooms)
    total = sum(styles.values())
    assert styles["built"] == 0, styles
    assert styles["rough"] / total >= 0.7, styles


def test_cave_finish_rules_out_built():
    """Only a written 0 rules a value out (scales.toml): 7-10 are."""
    finish = load_scales().themes["cave"].weights["finish"]
    assert finish[:4] and all(w > 0 for w in finish[:4])
    assert all(w == 0 for w in finish[7:])


def test_cave_grows_with_the_warren_set_and_every_kind_maps():
    entry = load_theme_map(TOPOLOGY / "themes.toml").entry_for("cave")
    assert entry.base == "warren"
    data = tomllib.loads((TOPOLOGY / "warren.toml").read_text(encoding="utf-8"))
    kinds = {n["kind"] for n in data["set"]["start_nodes"]}
    for rule in data["rules"].values():
        kinds |= {n["kind"] for n in rule.get("replace", [])}
    kinds.discard("Area")
    assert semantics.unmapped_kinds("cave", kinds) == []


@pytest.mark.parametrize("room_type", NEW_TYPES)
def test_the_new_room_types_have_recipes(room_type):
    source, asks = load_layouts().recipe_for(room_type, "chamber")
    assert source == f"type:{room_type}"
    assert asks, room_type


def test_cave_textures_are_rock_and_its_own():
    for surface in ("wall", "floor"):
        r = resolve(f"cave_{surface}")
        assert (r.family, r.source) == ("cave_rock", "theme")
        assert r != resolve(f"dungeon_{surface}")
        assert r == resolve(f"kobold_cave_{surface}")
