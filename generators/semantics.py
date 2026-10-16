"""
generators/semantics.py
------------------------
The content / semantic layer (Step 1 — single district).

Turns the geometric room graph into a *place*: each room is assigned a semantic
TYPE drawn from the zone's ARCHETYPE arc, coherent with the pacing graph
(role + graph_depth) that layout.py already computes. The archetype, together
with an inhabiting RACE (a global scale multiplier) and an optional ELEMENTAL
TINT (lava/ice/water region + light overlay), is realised through the EXISTING
pipeline — shape/proportion bias, region volumes, lighting mood, elevation
character, and per-room material (palette) selection. No new art is placed;
props / spawns / boss are emitted as *suggestions* only (RoomSpec fields).

This is a graph-LABELLING step layered on top of _apply_pacing, not a new
geometry backend. It is deterministic given the layout's RNG, so "randomness is
a feature" holds (fresh seed → different assignment).

Design & sources: docs/RESEARCH.md "Content / semantic layer — dungeon theme
vocabulary & districts". The room-type vocabulary and archetypes are grounded in
real EQ dungeons (Sebilis, Guk, Najena, Cazic-Thule, Kael Drakkel, Permafrost)
but intentionally generalised to high-fantasy / real-world analogues.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .zone_spec import ZoneSpec, RoomSpec, RegionSpec, LightSpec


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RoomType:
    """
    A semantic room type and its deterministic realization rules.

      footprint   — multiplier on room width/depth (proportion bias, composed
                    with the pacing role scale).
      aspect      — >1 stretches the room along its longer axis (processional
                    halls); 1.0 keeps it square.
      ceiling     — multiplier on room height (ceiling mood).
      sink        — floor-height bias (negative = sunken, positive = raised),
                    consumed as an elevation-character hint. In world units
                    BEFORE race scaling.
      light       — base light (r,g,b) 0-1 + intensity multiplier for the mood.
      region      — elemental region kind to flood the room with, or "".
      props       — set-dressing suggestions (data only).
      encounter   — encounter/spawn intent note (data only).
    """
    name: str
    footprint: float = 1.0
    aspect: float = 1.0
    ceiling: float = 1.0
    sink: float = 0.0
    light: Tuple[float, float, float] = (1.0, 0.55, 0.15)
    intensity: float = 1.0
    region: str = ""
    props: Tuple[str, ...] = ()
    encounter: str = ""


# Torch-orange is the dungeon baseline (matches layout._add_room_lights).
_WARM = (1.0, 0.55, 0.15)
_COLD = (0.45, 0.6, 0.85)
_FIRE = (1.0, 0.45, 0.12)
_ARCANE = (0.7, 0.45, 0.95)
_GREEN = (0.5, 0.75, 0.55)

# The realizable room-type catalogue. Keyed by type name.
ROOM_TYPES: Dict[str, RoomType] = {
    # --- connective / neutral ---
    "entry_hall":    RoomType("entry_hall", footprint=1.1, ceiling=1.05, light=_WARM, intensity=1.0,
                              props=("entrance banners", "worn threshold"),
                              encounter="light guard presence"),
    "gatehouse":     RoomType("gatehouse", footprint=1.0, ceiling=1.0, light=_WARM, intensity=0.95,
                              props=("portcullis frame", "guard alcoves"),
                              encounter="gate sentries"),
    "passage":       RoomType("passage", footprint=0.85, ceiling=0.9, light=_WARM, intensity=0.7,
                              props=("sconces",), encounter="patrol"),
    "warren":        RoomType("warren", footprint=0.8, ceiling=0.8, light=_WARM, intensity=0.6,
                              props=("nest bedding", "bone litter", "food cache"),
                              encounter="swarming den creatures"),
    "guard_post":    RoomType("guard_post", footprint=0.9, ceiling=0.95, light=_WARM, intensity=0.85,
                              props=("weapon racks", "watch brazier"),
                              encounter="alert guards"),
    # --- martial ---
    "barracks":      RoomType("barracks", footprint=1.15, aspect=1.4, ceiling=0.95, light=_WARM, intensity=0.85,
                              props=("bunk rows", "foot lockers", "weapon racks"),
                              encounter="off-duty soldiers"),
    "armory":        RoomType("armory", footprint=1.0, ceiling=0.95, light=_WARM, intensity=0.8,
                              props=("weapon stands", "armor racks", "supply crates"),
                              encounter="quartermaster + guards"),
    "prison_cell":   RoomType("prison_cell", footprint=0.65, ceiling=0.8, light=_WARM, intensity=0.5,
                              props=("barred cells", "chains", "straw"),
                              encounter="jailers; captive NPCs"),
    "storeroom":     RoomType("storeroom", footprint=0.8, ceiling=0.85, light=_WARM, intensity=0.6,
                              props=("stacked crates", "barrels", "sacks"),
                              encounter="vermin; a lone watchman"),
    "battle_arena":  RoomType("battle_arena", footprint=1.6, ceiling=1.5, sink=-20.0, light=_WARM, intensity=1.0,
                              props=("sand floor", "spectator tiers", "weapon racks"),
                              encounter="champion duel; crowd of combatants"),
    # --- sacred / ritual ---
    "shrine":        RoomType("shrine", footprint=1.05, ceiling=1.15, light=_ARCANE, intensity=0.8,
                              props=("altar", "offering bowls", "candles"),
                              encounter="acolytes at prayer"),
    "sacrifice_chamber": RoomType("sacrifice_chamber", footprint=1.1, aspect=1.2, ceiling=1.2, sink=-10.0,
                              light=_ARCANE, intensity=0.75,
                              props=("blood altar", "restraint slab", "braziers"),
                              encounter="cultists mid-ritual"),
    "ritual_chamber": RoomType("ritual_chamber", footprint=1.3, aspect=1.2, ceiling=1.3,
                              light=_ARCANE, intensity=0.9,
                              props=("summoning circle", "ritual braziers", "raised dais"),
                              encounter="ritual in progress; boss"),
    "ossuary":       RoomType("ossuary", footprint=1.0, ceiling=0.9, light=_COLD, intensity=0.55,
                              props=("bone racks", "skull niches", "sarcophagi"),
                              encounter="risen dead"),
    # --- arcane ---
    "laboratory":    RoomType("laboratory", footprint=1.0, ceiling=1.0, light=_ARCANE, intensity=0.8,
                              props=("alchemy benches", "specimen jars", "arcane apparatus"),
                              encounter="apprentices; failed experiments"),
    "summoning_hall": RoomType("summoning_hall", footprint=1.25, ceiling=1.25, light=_ARCANE, intensity=0.85,
                              props=("binding circle", "rune pillars", "brazier ring"),
                              encounter="summoned guardians"),
    # --- earthen / industrial ---
    "forge":         RoomType("forge", footprint=1.1, ceiling=1.1, light=_FIRE, intensity=1.0, region="lava",
                              props=("great forge", "anvils", "slag channels"),
                              encounter="smiths; fire-tied guardian"),
    "collapsed_gallery": RoomType("collapsed_gallery", footprint=0.9, ceiling=0.8, sink=-15.0,
                              light=_WARM, intensity=0.55,
                              props=("rubble", "broken supports", "cave-in debris"),
                              encounter="scavengers in the ruin"),
    # --- water ---
    "flooded_gallery": RoomType("flooded_gallery", footprint=1.2, ceiling=1.05, sink=-25.0,
                              light=_COLD, intensity=0.6, region="water",
                              props=("waterline stains", "island platform", "submerged debris"),
                              encounter="amphibious dwellers"),
    "sump":          RoomType("sump", footprint=0.9, ceiling=0.85, sink=-30.0, light=_COLD, intensity=0.5,
                              region="water",
                              props=("standing water", "pump works", "slime"),
                              encounter="things that lurk in the water"),
    # --- climactic / terminal ---
    "throne":        RoomType("throne", footprint=1.6, aspect=1.5, ceiling=1.5, sink=8.0,
                              light=_WARM, intensity=1.0,
                              props=("raised throne dais", "banners", "honor guard"),
                              encounter="the ruler; boss"),
    "vault":         RoomType("vault", footprint=1.3, ceiling=1.4, sink=-20.0, light=_WARM, intensity=0.7,
                              props=("treasure hoard", "reinforced door", "ward runes"),
                              encounter="vault guardian; boss"),
    "inner_sanctum": RoomType("inner_sanctum", footprint=1.5, aspect=1.3, ceiling=1.5,
                              light=_ARCANE, intensity=0.95,
                              props=("central altar", "pillar ring", "focal idol"),
                              encounter="high priest / archon; boss"),
    "dragon_lair":   RoomType("dragon_lair", footprint=1.8, ceiling=1.6, sink=-10.0,
                              light=_COLD, intensity=0.85,
                              props=("hoard pile", "scorched/frozen floor", "bones"),
                              encounter="the dragon; boss"),
}


@dataclass(frozen=True)
class Archetype:
    """
    A dungeon archetype: an ordered progression arc of room types plus
    role-specific overrides. The arc is sampled by graph depth so shallow rooms
    get early-arc types and deep rooms late-arc types.

      entrance_type — type for the entrance room.
      climax_type   — type for the climax/boss room.
      hub_type      — type for crossroads rooms.
      arc           — ordered mid types, shallow → deep, for standard/deadends.
      tint          — default elemental tint ("" = none).
    """
    name: str
    entrance_type: str
    climax_type: str
    hub_type: str
    arc: Tuple[str, ...]
    tint: str = ""


ARCHETYPES: Dict[str, Archetype] = {
    "fortress": Archetype(
        "fortress", entrance_type="gatehouse", climax_type="throne", hub_type="guard_post",
        arc=("guard_post", "barracks", "armory", "storeroom", "prison_cell", "battle_arena")),
    "war_city": Archetype(
        "war_city", entrance_type="gatehouse", climax_type="throne", hub_type="battle_arena",
        arc=("guard_post", "barracks", "armory", "shrine", "battle_arena")),
    "warren": Archetype(
        "warren", entrance_type="entry_hall", climax_type="throne", hub_type="warren",
        arc=("warren", "storeroom", "warren", "collapsed_gallery")),
    "temple": Archetype(
        "temple", entrance_type="entry_hall", climax_type="inner_sanctum", hub_type="shrine",
        arc=("passage", "shrine", "sacrifice_chamber", "ossuary", "ritual_chamber")),
    "tomb": Archetype(
        "tomb", entrance_type="entry_hall", climax_type="vault", hub_type="ossuary",
        arc=("passage", "ossuary", "ossuary", "ritual_chamber", "collapsed_gallery")),
    "wizard_lair": Archetype(
        "wizard_lair", entrance_type="entry_hall", climax_type="inner_sanctum", hub_type="laboratory",
        arc=("passage", "laboratory", "prison_cell", "summoning_hall", "storeroom")),
    "corrupted_sanctum": Archetype(
        "corrupted_sanctum", entrance_type="entry_hall", climax_type="inner_sanctum", hub_type="shrine",
        arc=("shrine", "ossuary", "sacrifice_chamber", "summoning_hall")),
    "mine_delve": Archetype(
        "mine_delve", entrance_type="entry_hall", climax_type="vault", hub_type="collapsed_gallery",
        arc=("passage", "storeroom", "collapsed_gallery", "sump", "forge")),
    "sunken_ruin": Archetype(
        "sunken_ruin", entrance_type="entry_hall", climax_type="inner_sanctum", hub_type="flooded_gallery",
        arc=("passage", "flooded_gallery", "ossuary", "sump", "ritual_chamber"), tint="water"),
    "lava_forge": Archetype(
        "lava_forge", entrance_type="entry_hall", climax_type="vault", hub_type="forge",
        arc=("passage", "forge", "storeroom", "armory", "collapsed_gallery"), tint="lava"),
    "ice_keep": Archetype(
        "ice_keep", entrance_type="gatehouse", climax_type="dragon_lair", hub_type="guard_post",
        arc=("guard_post", "barracks", "warren", "ossuary", "collapsed_gallery"), tint="ice"),
}

DEFAULT_ARCHETYPE = "fortress"


# ---------------------------------------------------------------------------
# Race scale axis
#
# KNOWN GAP (docs/RESEARCH.md): these multipliers are RELATIVE placeholders.
# Real per-race limits should come from EQ model bounding boxes (doorway
# clearance / headroom), which we do not yet have. Treat as a tunable knob, not
# an accurate measurement. The RoF2 install at F:\everquest_rof2 could later be
# mined for model bounds the way the era-fidelity edge-length table was.
# ---------------------------------------------------------------------------

RACE_SCALE: Dict[str, float] = {
    "default": 1.0,     # human / iksar / dark-elf baseline
    "goblin": 0.85,
    "froglok": 0.9,
    "kobold": 0.85,
    "lizardman": 1.0,
    "gnoll": 1.0,
    "sarnak": 1.05,
    "troll": 1.15,
    "ogre": 1.4,
    "giant": 2.2,       # Kael Drakkel — halls dwarf the player
}


def race_scale(race: str) -> float:
    return RACE_SCALE.get((race or "default").lower(), 1.0)


# Elemental tint → (region kind, light tint rgb, light intensity mult). The
# region kind maps to the existing RegionSpec kinds (water→AWT_, lava→ALV_,
# ice→AWT_ treated as water by the client but tinted cold here).
_TINTS: Dict[str, Tuple[str, Tuple[float, float, float], float]] = {
    "lava":  ("lava",  (1.0, 0.4, 0.1),  1.1),
    "ice":   ("water", (0.55, 0.7, 0.95), 0.85),
    "water": ("water", (0.45, 0.6, 0.85), 0.85),
}


# ---------------------------------------------------------------------------
# Assignment — graph labelling on top of the pacing graph
# ---------------------------------------------------------------------------

def label_rooms(spec: ZoneSpec,
                rooms: List[RoomSpec],
                rng: random.Random,
                archetype: str = "",
                race: str = "",
                tint: Optional[str] = None,
                overrides: Optional[Dict[str, str]] = None) -> None:
    """
    Phase 1 — assign each room a semantic type + theme and realise the parts
    that affect GEOMETRY (shape / proportion / ceiling / floor-height / race
    scale) plus the suggestion fields. Call AFTER _apply_pacing (rooms must have
    role + graph_depth) and BEFORE re-separate / elevation, so the biased shapes
    are resolved for overlaps and elevation builds on the sunk/raised floors.

    *rooms* is the working list (not yet appended to spec). Zone-level theme
    fields are recorded on *spec*.

    *archetype* selects the arc (defaults deterministically if unknown).
    *race* is the global scale multiplier. *tint* overrides the archetype's
    default elemental tint ("" to force none; None to use the archetype default).
    *overrides* maps room.id → semantic_type for planner-driven assignment.
    """
    if not rooms:
        return

    arch = ARCHETYPES.get((archetype or "").lower(), ARCHETYPES[DEFAULT_ARCHETYPE])
    effective_tint = arch.tint if tint is None else tint

    spec.dungeon_theme = arch.name
    spec.dungeon_race = (race or "default").lower()
    spec.elemental_tint = effective_tint

    overrides = overrides or {}
    max_depth = max((r.graph_depth for r in rooms), default=0)

    for r in rooms:
        # Choose the semantic type (planner override wins, else from the arc).
        if r.id in overrides and overrides[r.id] in ROOM_TYPES:
            type_name = overrides[r.id]
        else:
            type_name = _type_for_room(arch, r, max_depth, rng)
        rt = ROOM_TYPES.get(type_name, ROOM_TYPES["passage"])

        r.semantic_type = type_name
        r.room_theme = arch.name
        r.boss = r.role == "climax"

        # Suggestion fields (data only — never placed geometry).
        r.prop_hints = list(rt.props)
        r.encounter_intent = rt.encounter

        # Realize shape / proportion / ceiling / elevation character + race.
        _apply_shape(r, rt, race)


def realize_semantics(spec: ZoneSpec, rng: random.Random) -> None:
    """
    Phase 2 — realise the parts that depend on final room geometry and on the
    spec being fully assembled: per-room material (palette) selection, elemental
    region volumes, and lighting mood. Call AFTER rooms (and their pacing
    lights, if any) are appended to the spec.
    """
    if not spec.rooms:
        return
    tint = spec.elemental_tint
    for room in spec.rooms:
        rt = ROOM_TYPES.get(room.semantic_type, ROOM_TYPES["passage"])
        _apply_materials(spec, room, rt, tint)
    _apply_regions_and_lights(spec, tint)


def assign_semantics(spec: ZoneSpec,
                     edges: List[Tuple[int, int]],
                     rng: random.Random,
                     archetype: str = "",
                     race: str = "",
                     tint: Optional[str] = None,
                     overrides: Optional[Dict[str, str]] = None) -> None:
    """
    Convenience: run both phases against rooms already appended to *spec*. Used
    by callers (e.g. tests, hand-authored specs) that assemble the spec first.
    Note: shape bias runs here too, so overlaps/elevation are the caller's
    responsibility if called late.
    """
    label_rooms(spec, spec.rooms, rng, archetype=archetype, race=race,
                tint=tint, overrides=overrides)
    realize_semantics(spec, rng)


def _type_for_room(arch: Archetype, room: RoomSpec, max_depth: int,
                   rng: random.Random) -> str:
    """Pick a room type from the archetype arc, anchored by role + depth."""
    if room.role == "entrance":
        return arch.entrance_type
    if room.role == "climax":
        return arch.climax_type
    if room.role == "hub":
        return arch.hub_type

    # standard / deadend: sample the arc by normalised depth so shallow rooms
    # get early-arc types and deep rooms late-arc types. A small jitter keeps
    # neighbours from being identical without breaking the depth ordering.
    arc = arch.arc
    if not arc:
        return "passage"
    frac = (room.graph_depth / max_depth) if max_depth > 0 else 0.0
    idx = int(round(frac * (len(arc) - 1)))
    jitter = rng.choice([-1, 0, 0, 1])
    idx = max(0, min(len(arc) - 1, idx + jitter))
    return arc[idx]


def _apply_shape(room: RoomSpec, rt: RoomType, race: str) -> None:
    """
    Compose the semantic-type shape bias with the pacing role scale already on
    the room, then apply the race scale globally. Keeps floors flat/walkable —
    only footprint, aspect, ceiling, and floor height change.
    """
    scale = race_scale(race)

    # Footprint + aspect: stretch the longer axis for processional rooms.
    fw = rt.footprint
    fd = rt.footprint
    if rt.aspect != 1.0:
        if room.width >= room.depth:
            fw *= rt.aspect
        else:
            fd *= rt.aspect

    room.width = max(80.0, room.width * fw * scale)
    room.depth = max(80.0, room.depth * fd * scale)
    room.height = max(50.0, room.height * rt.ceiling * scale)

    # Elevation character: nudge the floor height (sunken/raised). Scaled by
    # race so a giant's sunken arena sinks proportionally. This is a hint on the
    # base floor_z; _assign_elevation still runs afterward over the graph.
    if rt.sink:
        room.floor_z += rt.sink * scale


def _material_variant(base: str, theme: str, tint: str) -> str:
    """Logical material name for a themed/tinted variant, e.g. 'wall_temple'."""
    key = tint if tint else theme
    return f"{base}_{key}" if key else base


# Per-theme / per-tint palette deltas layered on the base dungeon palette.
# (r,g,b) 0-255 + a short texture-description hint. Zero new art: distinct
# material NAMES yield distinct procedural DDS keyed on name/colour/description.
_THEME_PALETTES: Dict[str, Dict[str, Tuple[Tuple[int, int, int], str]]] = {
    "fortress": {
        "floor": ((95, 88, 80), "worn fortress flagstone, boot-scuffed"),
        "wall":  ((112, 103, 94), "cut stone block wall, mortar joints"),
    },
    "temple": {
        "floor": ((120, 110, 95), "carved temple flagstone, faded glyphs"),
        "wall":  ((135, 122, 100), "sandstone temple wall, relief carvings"),
    },
    "tomb": {
        "floor": ((85, 82, 78), "cold crypt flagstone, dust"),
        "wall":  ((100, 96, 92), "sealed tomb stone, carved niches"),
    },
    "wizard_lair": {
        "floor": ((78, 74, 82), "arcane-stained stone floor"),
        "wall":  ((92, 86, 100), "rune-etched dark stone wall"),
    },
    "sunken_ruin": {
        "floor": ((74, 82, 78), "water-stained flagstone, algae"),
        "wall":  ((86, 96, 92), "damp ruined stone, waterline, moss"),
    },
    "ice_keep": {
        "floor": ((150, 165, 180), "frost-rimed flagstone, ice patches"),
        "wall":  ((160, 175, 195), "ice-sheathed castle stone"),
    },
    "lava_forge": {
        "floor": ((88, 72, 64), "soot-blackened forge stone, ember glow"),
        "wall":  ((104, 82, 72), "heat-cracked basalt wall"),
    },
}
# Elemental tints override the archetype palette where present.
_TINT_PALETTES: Dict[str, Dict[str, Tuple[Tuple[int, int, int], str]]] = {
    "lava": _THEME_PALETTES["lava_forge"],
    "ice":  _THEME_PALETTES["ice_keep"],
    "water": _THEME_PALETTES["sunken_ruin"],
}


def _apply_materials(spec: ZoneSpec, room: RoomSpec, rt: RoomType, tint: str) -> None:
    """
    Point the room at themed floor/wall material variants, registering them in
    spec.materials on first use. Ceiling keeps the base (shared) material.
    """
    theme = spec.dungeon_theme
    palette = _TINT_PALETTES.get(tint) or _THEME_PALETTES.get(theme)
    if not palette:
        return  # no themed palette → keep base materials

    shaders = spec.materials.get("wall")
    shader = shaders.shader if shaders else "Opaque_MaxCB1.fx"

    for base in ("floor", "wall"):
        if base not in palette:
            continue
        name = _material_variant(base, theme, tint)
        if name not in spec.materials:
            color, desc = palette[base]
            spec.add_material(name, f"{name}.dds", shader=shader,
                              color=color, description=desc)
        if base == "floor":
            room.floor_material = name
        else:
            room.wall_material = name


def _apply_regions_and_lights(spec: ZoneSpec, tint: str) -> None:
    """
    Emit elemental region volumes for rooms whose type requests one, and re-tint
    each room's light to its semantic mood. Lighting replaces
    layout._add_room_lights' output for themed zones so the mood reflects the
    room type, not just depth.
    """
    tint_region, tint_rgb, tint_imult = _TINTS.get(tint, ("", None, 1.0))

    for i, room in enumerate(spec.rooms):
        rt = ROOM_TYPES.get(room.semantic_type, ROOM_TYPES["passage"])

        # --- region: a room whose type requests an elemental volume gets one. ---
        if rt.region:
            _add_room_region(spec, room, rt.region, i)

        # --- lighting mood: type base light × type intensity, fades a little
        #     with depth, overridden by the elemental tint where set. ---
        base_r, base_g, base_b = rt.light
        intensity = rt.intensity
        if tint_rgb is not None and rt.region:
            # Only rooms actually carrying the tint region take the tint light.
            base_r, base_g, base_b = tint_rgb
            intensity *= tint_imult
        fade = max(0.5, 1.0 - room.graph_depth * 0.05)
        intensity *= fade
        if room.role == "entrance":
            intensity = max(intensity, 0.95)

        _set_room_light(spec, room, i,
                        base_r * intensity, base_g * intensity, base_b * intensity)


def _add_room_region(spec: ZoneSpec, room: RoomSpec, kind: str, idx: int) -> None:
    """Flood the lower part of a room with an elemental region volume."""
    ext_x = room.width * 0.38
    ext_y = room.depth * 0.38
    ext_z = max(8.0, room.height * 0.18)
    spec.regions.append(RegionSpec(
        id=f"{kind}_{idx}",
        kind=kind,
        center_x=room.center_x,
        center_y=room.center_y,
        center_z=room.floor_z + ext_z,
        extent_x=ext_x,
        extent_y=ext_y,
        extent_z=ext_z,
    ))


def _set_room_light(spec: ZoneSpec, room: RoomSpec, idx: int,
                    r: float, g: float, b: float) -> None:
    """
    Re-tint the pacing light for this room (matched by position) to the semantic
    mood. If no light exists at the room (add_lights=False), lighting stays off
    — semantic lighting only refines lights that pacing already placed.
    """
    r = max(0.0, min(1.0, r))
    g = max(0.0, min(1.0, g))
    b = max(0.0, min(1.0, b))
    for lt in spec.lights:
        if abs(lt.x - room.center_x) < 1.0 and abs(lt.y - room.center_y) < 1.0:
            lt.r, lt.g, lt.b = r, g, b
            lt.radius = max(lt.radius, max(room.width, room.depth) * 0.9)
            lt.id = f"light_{idx}_{room.semantic_type}"
            return
