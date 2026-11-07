"""
ai/expand.py
------------
Expand a ZonePlan into a full ZoneSpec by driving the existing LayoutGenerator
with the plan's parameters, then layering on plan-specific extras (regions,
mood-driven material descriptions).

This is the bridge: planners produce a small plan, and this turns it into the
same ZoneSpec the dropdowns produce — so everything downstream is unchanged.
"""

from __future__ import annotations

import random
from typing import Mapping, Optional

from generators import semantics
from generators.layout import LayoutGenerator
from generators.layout_engine import GraphEngine
from generators.zone_spec import ZoneSpec, RegionSpec
from generators.zone_types import STYLE_PROFILE
from .schema import ZonePlan, LAYOUT_ZONE_TYPES

# size -> shift of every room's position in its race's bands (step 7 task 17:
# rooms are sized from the race's body height, so Size moves them within the
# race's own band instead of multiplying them).
_SIZE_SHIFT = semantics.SIZE_SHIFT

# verticality -> elevation chance + rise magnitude, the rise in body heights
# (H; 6 u for a human). Before stock scale the rises were 20-80 u and 60-180 u
# under 121 u rooms; stock rooms are a quarter of that, and so are these
# (moderate 6-21 u for a human, dramatic 15-45 u; stock connectors rise
# 15-28 u at the median).
_VERTICALITY = {
    "flat":     (0.0, 0.0, 0.0),
    "moderate": (0.5, 1.0, 3.5),
    "dramatic": (0.85, 2.5, 7.5),
}

# verticality -> (graph stacking, weight on the vertical rules): step 7
# (design "Rule format"). A vertical rule is one whose replacement has an
# ``above`` / ``below`` edge (``layout_engine.is_vertical``). ``flat`` is
# stacking off, which leaves them out and keeps every room on one Level;
# ``dramatic`` doubles their weight. The classic elevation mapping above
# still applies to both engines.
VERTICAL_RULES = {
    "flat":     (False, 0.0),
    "moderate": (True, 1.0),
    "dramatic": (True, 2.0),
}


def plan_to_spec(plan: ZonePlan, seed: Optional[int] = None,
                 edges: Optional[Mapping[str, str]] = None,
                 trees: Optional[str] = None,
                 trees_source: str = "cli") -> ZoneSpec:
    """Build a ZoneSpec from a validated ZonePlan.

    ``edges`` declares the Rim of a wilderness or outdoor-dungeon zone
    (``{"N": "zoneline", ...}``; undeclared sides are mountain). ``trees`` is
    their Density_Level set by ``trees_source`` (``"controls"`` or ``"cli"``);
    it beats a level the prompt's wording asks for. Both are ignored for
    room-graph zone types.
    """
    plan.validate()
    rng_seed = seed if seed is not None else random.randint(0, 2 ** 31 - 1)

    # Open-world wilderness: no room layout; the wilderness pipeline describes
    # the whole landscape (generators/wilderness/build.py). An outdoor dungeon
    # is that landscape with a dungeon laid out under its hill
    # (generators/outdoor_dungeon.py); room count, theme, race, tint and locks
    # apply to the dungeon as for a dungeon zone.
    if plan.zone_type in ("wilderness", "outdoor_dungeon"):
        from generators.wilderness.biome_resolve import resolve_biome
        intent = resolve_biome(plan)
        if plan.zone_type == "wilderness":
            from generators.wilderness.build import wilderness_spec
            spec = wilderness_spec(plan.name, rng_seed, edges, biome=intent.biome)
        else:
            from generators.outdoor_dungeon import outdoor_dungeon_spec
            spec = outdoor_dungeon_spec(
                plan.name, rng_seed, edges, biome=intent.biome,
                room_count=plan.room_count, locks=plan.locks,
                dungeon_theme=plan.dungeon_theme, dungeon_race=plan.dungeon_race,
                elemental_tint=(plan.elemental_tint or None),
                verticality=plan.verticality,
                engine=layout_engine(plan.layout, plan.rule_set, plan.verticality,
                                     outdoor=True))
            spec.layout = layout_block(spec.layout, spec)
            # A grown dungeon under a hill draws its real walls; with no theme it's a
            # cave, the Blackburrow it's modelled on.
            if spec.layout is not None:
                from generators.outdoor_dungeon import tunnel_doors
                from generators.wall_styles import apply_walls, load_styles, style_for_theme
                if plan.walls:
                    style = load_styles()[plan.walls]
                elif plan.dungeon_theme:
                    style = style_for_theme(plan.dungeon_theme)
                else:
                    style = load_styles()["rough"]
                doors = tunnel_doors(spec)
                apply_walls(spec, style, rng_seed, extra_doors=doors)
                from generators.room_layouts import apply_features
                apply_features(spec, style.complex, rng_seed, extra_doors=doors)
        # Keep the fallback record (Req 1.4) for the sidecar; only when one fired.
        if intent.substitution is not None:
            spec.wilderness["biome_substitution"] = intent.substitution.to_dict()
        if trees is not None:
            from generators.vegetation.kit import DENSITY_LEVELS
            if trees not in DENSITY_LEVELS:
                raise ValueError(f"trees must be one of {', '.join(DENSITY_LEVELS)}")
            spec.wilderness["trees"] = trees
            spec.wilderness["trees_source"] = trees_source
        elif intent.trees is not None:
            spec.wilderness["trees"] = intent.trees
            spec.wilderness["trees_source"] = "prompt"
        return spec

    engine = layout_engine(plan.layout, plan.rule_set, plan.verticality) \
        if plan.zone_type in LAYOUT_ZONE_TYPES else None
    gen = LayoutGenerator(zone_type=plan.zone_type, seed=rng_seed, engine=engine)

    # Apply size as a shift within the race's room bands (generate() sizes
    # the rooms from the race; this persists).
    gen.size_shift = _SIZE_SHIFT.get(plan.size, 0.0)

    # Apply verticality (rises in body heights; generate() turns them into u)
    chance, rise_min, rise_max = _VERTICALITY.get(plan.verticality, _VERTICALITY["moderate"])
    gen.elevation_chance = chance
    gen.rise_h = (rise_min, rise_max)

    spec = gen.generate(
        plan.name,
        room_count=plan.room_count,
        elevation=plan.elevation and plan.verticality != "flat",
        locks=plan.locks,
        dungeon_theme=plan.dungeon_theme,
        dungeon_race=plan.dungeon_race,
        elemental_tint=(plan.elemental_tint or None),
    )
    spec.layout = layout_block(gen.layout_record, spec)

    # Add requested regions, placed in/near rooms. When the semantic layer is
    # active it already emits themed elemental region volumes (water/lava), so
    # skip those kinds here to avoid double-placing; keep any non-elemental
    # regions the plan requested (pvp/zoneline/generic).
    themed = bool(spec.dungeon_theme)
    _add_regions(spec, plan, rng_seed, skip_elemental=themed)

    # Fold mood into material descriptions so textures pick it up.
    if plan.mood:
        for mat in spec.materials.values():
            mat.description = f"{mat.description}, {plan.mood}".strip(", ")

    # Record provenance: the measured style-profile name for this zone type
    # (wilderness -> "outdoor"; dungeon/city map to themselves).
    spec.style_profile = STYLE_PROFILE[plan.zone_type]

    # A grown dungeon's rooms draw their real walls, last, when every door is known.
    if spec.layout is not None and plan.zone_type == "dungeon":
        from generators.wall_styles import apply_walls, load_styles, style_for_theme
        style = load_styles()[plan.walls] if plan.walls else style_for_theme(plan.dungeon_theme)
        apply_walls(spec, style, rng_seed)
        from generators.room_layouts import apply_features
        apply_features(spec, style.complex, rng_seed)
    return spec


def layout_engine(layout: str, rule_set: str = "", verticality: Optional[str] = None,
                  outdoor: bool = False):
    """The Layout_Engine for a plan's ``layout`` / ``rule_set``: ``None``
    (classic) or a graph engine whose set comes from the dungeon theme
    (``rules/topology/themes.toml``) unless *rule_set* names a base set.

    *verticality* (``flat`` / ``moderate`` / ``dramatic``) sets the graph
    engine's stacking and the weight on the set's vertical rules
    (``VERTICAL_RULES``); ``None`` is the engine's default: no stacking, so
    no vertical rules. *outdoor* (the outdoor dungeon): at ``flat`` (or
    no verticality) the vertical rules stay at their weights as step 6's
    ramp hints, stacking off, as before step 7; at ``moderate`` /
    ``dramatic`` it stacks like any graph dungeon, its Levels only going
    down from the entrance (``descend``: the Tunnel enters at the top
    Level, step 7 task 7)."""
    if layout != "graph":
        return None
    if outdoor:
        if verticality in (None, "flat"):
            return GraphEngine(rule_set or None, vertical_weight=1.0)
        _stacking, weight = VERTICAL_RULES.get(verticality, VERTICAL_RULES["moderate"])
        return GraphEngine(rule_set or None, stacking=True, vertical_weight=weight,
                           descend=True)
    if verticality is None:
        return GraphEngine(rule_set or None)
    stacking, weight = VERTICAL_RULES.get(verticality, VERTICAL_RULES["moderate"])
    return GraphEngine(rule_set or None, stacking=stacking, vertical_weight=weight)


def layout_block(record: Optional[dict], spec: ZoneSpec) -> Optional[dict]:
    """``ZoneSpec.layout`` from ``LayoutGenerator.layout_record``: ``None``
    for classic, else the record plus a ``notes`` list naming any room kind
    the spec's theme doesn't map to a room type (those rooms took the arc's
    type instead)."""
    if record is None:
        return None
    block = dict(record)
    notes = list(block.get("notes", []))
    if spec.dungeon_theme:
        kinds = [r.get("kind", "") for r in block.get("rooms", {}).values()]
        for kind in semantics.unmapped_kinds(spec.dungeon_theme, kinds):
            notes.append(f"kind_unmapped: {spec.dungeon_theme} has no room type "
                         f"for kind {kind!r}; its rooms took the arc's type")
    if notes:
        block["notes"] = notes
    return block


_ELEMENTAL_KINDS = {"water", "lava", "ice"}


def _add_regions(spec: ZoneSpec, plan: ZonePlan, seed: int,
                 skip_elemental: bool = False) -> None:
    """Place each requested region kind in a room (water/lava pools, etc.)."""
    if not plan.regions or not spec.rooms:
        return
    rng = random.Random(seed ^ 0x5EED)
    kinds = plan.regions
    if skip_elemental:
        kinds = [k for k in kinds if k not in _ELEMENTAL_KINDS]
    for i, kind in enumerate(kinds):
        # Put the region in a room (cycle through rooms if more regions)
        room = spec.rooms[i % len(spec.rooms)]
        # A pool covering part of the room floor
        ext_x = room.width * 0.3
        ext_y = room.depth * 0.3
        ext_z = max(6.0, room.height * 0.12)
        spec.regions.append(RegionSpec(
            id=f"{kind}_{i}",
            kind=kind,
            center_x=room.center_x,
            center_y=room.center_y,
            center_z=room.floor_z + ext_z,
            extent_x=ext_x,
            extent_y=ext_y,
            extent_z=ext_z,
        ))
