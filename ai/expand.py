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
from typing import Dict, List, Mapping, Optional

from generators import districts as _districts
from generators import semantics
from generators.layout import LayoutGenerator
from generators.layout_engine import GraphEngine
from generators.zone_spec import ZoneSpec, RegionSpec
from generators.zone_types import STYLE_PROFILE
from .schema import (
    DEFAULT_SITES, DISTRICT_ZONE_TYPES, MAX_DISTRICT_PROPOSALS, SCALE_CONTROLS, ZonePlan,
    LAYOUT_ZONE_TYPES,
)

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
                 trees_source: str = "cli",
                 sites_source: Optional[str] = None,
                 warnings: Optional[List[str]] = None) -> ZoneSpec:
    """Build a ZoneSpec from a validated ZonePlan.

    ``edges`` declares the Rim of a wilderness or outdoor-dungeon zone
    (``{"N": "zoneline", ...}``; undeclared sides are mountain). ``trees`` is
    their Density_Level set by ``trees_source`` (``"controls"`` or ``"cli"``);
    it beats a level the prompt's wording asks for. Both are ignored for
    room-graph zone types.

    The plan's ``sites`` / ``inhabitant`` reach the spec on those two types;
    its ``decor`` / ``decor_seed`` / ``rooms_seed`` reach any spec when chosen.
    ``seed`` makes the World; the plan's ``rooms_seed`` (unset: ``seed``) lays out
    the rooms, their walls, Scales and Features, and the Sites (world-sockets Req 4).
    ``sites_source`` says who set them (``"controls"`` or ``"cli"``); left
    ``None`` it is ``"prompt"`` when a prompt plan moved them off their
    defaults, else ``"default"``.

    The plan's Districts (districts spec Req 4) reach the layout on a dungeon only (A2);
    on any other zone type the switch is kept on the plan but ignored. ``warnings`` is an
    optional accumulator, as for ``ZonePlan.validate``: it gains that A2 note and the
    layout's own notes (``districts_reduced``, ``district_purposes_relaxed``, ...; every
    entry of ``LayoutGenerator.warnings``), for the caller's response and Sidecar. Call
    it with a fresh list per spec: a retry on a new seed makes new notes.
    """
    plan.validate(warnings)
    notes: List[str] = [] if warnings is None else warnings
    if plan.districts and plan.zone_type not in DISTRICT_ZONE_TYPES:
        notes.append(f"districts_ignored: Districts apply to dungeons only; "
                     f"this {plan.zone_type} builds without them")
    rng_seed = seed if seed is not None else random.randint(0, 2 ** 31 - 1)
    rooms_seed = rng_seed if plan.rooms_seed is None else plan.rooms_seed

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
                verticality=plan.verticality, rooms_seed=plan.rooms_seed,
                engine=layout_engine(plan.layout, plan.rule_set, plan.verticality,
                                     outdoor=True))
            spec.layout = layout_block(spec.layout, spec)
            # A grown dungeon under a hill draws its real walls; with no theme it's a
            # cave, the Blackburrow it's modelled on.
            if spec.layout is not None:
                from generators.outdoor_dungeon import tunnel_doors
                _dress_rooms(spec, plan, rooms_seed, extra_doors=tunnel_doors(spec),
                             overlay="" if plan.dungeon_theme else "natural_cave")
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
        spec.sites, spec.inhabitant = plan.sites, plan.inhabitant
        if sites_source is None:
            moved = (plan.sites, plan.inhabitant) != (DEFAULT_SITES, "")
            sites_source = "prompt" if moved and plan.prompt else "default"
        spec.sites_source = sites_source
        return _decor(spec, plan)

    engine = layout_engine(plan.layout, plan.rule_set, plan.verticality) \
        if plan.zone_type in LAYOUT_ZONE_TYPES else None
    district_args = _district_args(plan, rooms_seed, notes)
    profile = purpose_profile(plan, district_args)
    gen = LayoutGenerator(zone_type=plan.zone_type, seed=rooms_seed, engine=engine,
                          profile=profile)

    # Apply size as a shift within the race's room bands (generate() sizes
    # the rooms from the race; this persists), on top of the Purpose's
    # profile shift (0.0 unless a profile was passed).
    gen.size_shift = gen.profile_shift + _SIZE_SHIFT.get(plan.size, 0.0)

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
        **district_args,
    )
    notes.extend(gen.warnings)
    pinned = plan.pinned_purpose()
    if pinned and len(spec.districts) >= 2:
        notes.append(f"district_purpose_pinned: every District is {pinned}")
    spec.seed = rng_seed        # the World's; the layout ran on the rooms seed
    spec.layout = layout_block(gen.layout_record, spec)

    # Add requested regions, placed in/near rooms. When the semantic layer is
    # active it already emits themed elemental region volumes (water/lava), so
    # skip those kinds here to avoid double-placing; keep any non-elemental
    # regions the plan requested (pvp/zoneline/generic).
    themed = bool(spec.dungeon_theme)
    _add_regions(spec, plan, rooms_seed, skip_elemental=themed)

    # Fold mood into material descriptions so textures pick it up.
    if plan.mood:
        for mat in spec.materials.values():
            mat.description = f"{mat.description}, {plan.mood}".strip(", ")

    # Record provenance: the measured style-profile name the layout read: the
    # Purpose's (``PURPOSE_PROFILE``), else the zone type's (wilderness ->
    # "outdoor"; dungeon/city map to themselves).
    spec.style_profile = profile or STYLE_PROFILE[plan.zone_type]

    # A grown dungeon's rooms draw their real walls, last, when every door is known.
    if spec.layout is not None and plan.zone_type == "dungeon":
        _dress_rooms(spec, plan, rooms_seed)
    return _decor(spec, plan)


#: Purposes with a measured style profile of their own (cave spec Req 3): a
#: dungeon with one of these Purposes (District 0's, with Districts) sizes its
#: rooms from it. Any other Purpose keeps its zone type's profile.
PURPOSE_PROFILE: Dict[str, str] = {"cave": "cave"}


def purpose_profile(plan: ZonePlan, district_args: Mapping[str, object]) -> Optional[str]:
    """The style profile *plan*'s Purpose brings (``PURPOSE_PROFILE``), or ``None``.

    A ``dungeon`` only (an outdoor dungeon and a city keep theirs). The Purpose is
    District 0's when Districts are on (*district_args* from :func:`_district_args`)
    and the room count can split: its first proposal when it names a Purpose, else
    the plan's dungeon theme, as ``assign_district_purposes`` fills District 0. A
    District 0 the layout draws (no theme, no proposal) is not known here, so it
    keeps the dungeon profile."""
    if plan.zone_type != "dungeon":
        return None
    purpose = plan.dungeon_theme
    if district_args and plan.room_count >= _districts.MIN_ROOMS:
        proposals = district_args.get("district_plan") or []
        first = proposals[0].get("purpose", "") if proposals else ""
        if first in semantics.ARCHETYPES:
            purpose = first
    return PURPOSE_PROFILE.get(purpose or "")


def _district_args(plan: ZonePlan, seed: int, notes: List[str]) -> Dict[str, object]:
    """``LayoutGenerator.generate``'s District arguments for *plan*: none (the switch off,
    or a zone type other than a dungeon), else the switch, the proposals and the
    relationship. A dungeon too small to split gets a note (umbrella 23.1's count is the
    layout's: the plan's proposal count never overrides it)."""
    if not (plan.districts and plan.zone_type in DISTRICT_ZONE_TYPES):
        return {}
    if plan.room_count < _districts.MIN_ROOMS:
        notes.append(f"districts_too_few_rooms: {plan.room_count} rooms; Districts need "
                     f"{_districts.MIN_ROOMS} or more")
    return {"districts": True,
            "district_plan": layout_proposals(plan, seed),
            "district_relationship": plan.district_relationship}


def layout_proposals(plan: ZonePlan, seed: int) -> List[Dict[str, str]]:
    """The plan's District proposals as the layout takes them: named Purposes only, in
    District id order (``generators.districts.assign_district_purposes`` notes an empty
    one as unknown).

    A pinned plan (``ZonePlan.pinned_purpose``) proposes its Purpose for every District,
    up to three, so however many the room count resolves all share it (23.10). Open
    proposals at the end are dropped: the layout chooses those Districts by the
    relationship (23.11). An open proposal before a named one is filled here: District 0
    by the plan's dungeon theme when no other proposal names it, else (and for any later
    one) a Purpose next to the one before it (District 0: the first named) in the relationship's table (the
    contrast table for ``factional``, the compatibility table otherwise), drawn from a
    generator salted off *seed* and unused by the other proposals."""
    pinned = plan.pinned_purpose()
    if pinned:
        return [{"purpose": pinned}] * MAX_DISTRICT_PROPOSALS
    names = [p["purpose"] for p in plan.district_plan]
    while names and not names[-1]:
        names.pop()
    if "" in names:
        rng = random.Random(seed ^ 0xD157)
        table = (_districts.CONTRASTS if plan.district_relationship == "factional"
                 else _districts.COMPATIBLE)
        for d, name in enumerate(names):
            if name:
                continue
            used = {n for n in names if n}
            if d == 0 and plan.dungeon_theme and plan.dungeon_theme not in used:
                names[0] = plan.dungeon_theme
                continue
            near = names[d - 1] if d else next(n for n in names if n)
            pool = [p for p in table[near] if p not in used] or \
                [p for p in _districts.PURPOSES if p not in used]
            names[d] = rng.choice(pool)
    return [{"purpose": n} for n in names]


def _decor(spec: ZoneSpec, plan: ZonePlan) -> ZoneSpec:
    """The plan's Decor control, decor seed, rooms seed and room decor seeds on the spec, only
    when chosen:
    an unset control is built at the default by the pipeline and as none by a
    bare ``ZoneBuilder`` (room-decor decision 28), so a plan naming neither
    gives the spec it always did."""
    if plan.decor:
        spec.decor = plan.decor
    if plan.decor_seed is not None:
        spec.decor_seed = plan.decor_seed
    if plan.rooms_seed is not None:
        spec.rooms_seed = plan.rooms_seed
    if plan.room_decor_seeds:
        spec.room_decor_seeds = dict(plan.room_decor_seeds)
    return spec


def _dress_rooms(spec, plan: ZonePlan, seed: int, extra_doors=None, overlay: str = "") -> None:
    """What a grown zone's rooms are like, then their walls, then what stands in them."""
    from generators.room_layouts import apply_features
    from generators.room_scales import draw_room_scales
    from generators.wall_styles import apply_walls, apply_walls_by_finish, load_styles
    asked = {name: getattr(plan, name) for name in SCALE_CONTROLS if getattr(plan, name) is not None}
    draw_room_scales(spec, seed, overlay=plan.overlay or overlay, asked=asked)
    # The Winding goes on the spec before the walls: drawing them measures how far each
    # rough corridor winds (``transitions.measure_winds``), by the spec's scaled tunnel.
    spec.winding = plan.winding
    if plan.walls:
        apply_walls(spec, load_styles()[plan.walls], seed, extra_doors=extra_doors)
    else:
        apply_walls_by_finish(spec, seed, extra_doors=extra_doors)
    apply_features(spec, "", seed, plan.features, extra_doors=extra_doors)


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
