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

from generators.layout import LayoutGenerator
from generators.zone_spec import ZoneSpec, RegionSpec
from generators.zone_types import STYLE_PROFILE
from .schema import ZonePlan

# size → footprint scale applied to the layout generator's room spacing
_SIZE_SCALE = {"small": 0.7, "medium": 1.0, "large": 1.5, "huge": 2.2}

# verticality → elevation chance + rise magnitude
_VERTICALITY = {
    "flat":     (0.0, 0.0, 0.0),
    "moderate": (0.5, 20.0, 80.0),
    "dramatic": (0.85, 60.0, 180.0),
}


def plan_to_spec(plan: ZonePlan, seed: Optional[int] = None,
                 edges: Optional[Mapping[str, str]] = None) -> ZoneSpec:
    """Build a ZoneSpec from a validated ZonePlan.

    ``edges`` declares the Rim of a wilderness zone (``{"N": "zoneline", ...}``;
    undeclared sides are mountain). It is ignored for room-graph zone types.
    """
    plan.validate()
    rng_seed = seed if seed is not None else random.randint(0, 2 ** 31 - 1)

    # Open-world wilderness: no room layout; the wilderness pipeline describes
    # the whole landscape (generators/wilderness/build.py).
    if plan.zone_type == "wilderness":
        from generators.wilderness.biome_resolve import resolve_biome
        from generators.wilderness.build import wilderness_spec
        intent = resolve_biome(plan)
        spec = wilderness_spec(plan.name, rng_seed, edges, biome=intent.biome)
        # Keep the fallback record (Req 1.4) for the sidecar; only when one fired.
        if intent.substitution is not None:
            spec.wilderness["biome_substitution"] = intent.substitution.to_dict()
        return spec

    gen = LayoutGenerator(zone_type=plan.zone_type, seed=rng_seed)

    # Apply size as a multiplier on top of the theme-accurate base footprint.
    # (generate() recomputes room scale from the measured profile; this persists.)
    gen.size_multiplier = _SIZE_SCALE.get(plan.size, 1.0)

    # Apply verticality
    chance, rise_min, rise_max = _VERTICALITY.get(plan.verticality, _VERTICALITY["moderate"])
    gen.elevation_chance = chance
    gen.step_rise_min = rise_min
    gen.step_rise_max = rise_max

    spec = gen.generate(
        plan.name,
        room_count=plan.room_count,
        elevation=plan.elevation and plan.verticality != "flat",
        locks=plan.locks,
        dungeon_theme=plan.dungeon_theme,
        dungeon_race=plan.dungeon_race,
        elemental_tint=(plan.elemental_tint or None),
    )

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
    return spec


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
