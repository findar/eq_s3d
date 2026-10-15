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
from typing import Optional

from generators.layout import LayoutGenerator
from generators.zone_spec import ZoneSpec, RegionSpec
from .schema import ZonePlan

# size → footprint scale applied to the layout generator's room spacing
_SIZE_SCALE = {"small": 0.7, "medium": 1.0, "large": 1.5, "huge": 2.2}

# verticality → elevation chance + rise magnitude
_VERTICALITY = {
    "flat":     (0.0, 0.0, 0.0),
    "moderate": (0.5, 20.0, 80.0),
    "dramatic": (0.85, 60.0, 180.0),
}


def plan_to_spec(plan: ZonePlan, seed: Optional[int] = None) -> ZoneSpec:
    """Build a ZoneSpec from a validated ZonePlan."""
    plan.validate()
    rng_seed = seed if seed is not None else random.randint(0, 2 ** 31 - 1)

    gen = LayoutGenerator(theme=plan.theme, seed=rng_seed)

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
    )

    # Add requested regions, placed in/near rooms.
    _add_regions(spec, plan, rng_seed)

    # Fold mood into material descriptions so textures pick it up.
    if plan.mood:
        for mat in spec.materials.values():
            mat.description = f"{mat.description}, {plan.mood}".strip(", ")

    # Record provenance
    spec.style_profile = plan.theme
    return spec


def _add_regions(spec: ZoneSpec, plan: ZonePlan, seed: int) -> None:
    """Place each requested region kind in a room (water/lava pools, etc.)."""
    if not plan.regions or not spec.rooms:
        return
    rng = random.Random(seed ^ 0x5EED)
    for i, kind in enumerate(plan.regions):
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
