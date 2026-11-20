"""
generators/semantics.py
------------------------
The content / semantic layer (Step 1 — single district).

Turns the geometric room graph into a *place*: each room is assigned a semantic
TYPE drawn from the zone's ARCHETYPE arc, coherent with the pacing graph
(role + graph_depth) that layout.py already computes. The archetype, together
with an inhabiting RACE (whose body height sizes the rooms) and an optional ELEMENTAL
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
from typing import Dict, List, Optional, Sequence, Tuple

from core.ter import SHADER_OPAQUE

from .zone_spec import DistrictSpec, ZoneSpec, RoomSpec, RegionSpec, LightSpec


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
                    consumed as an elevation-character hint. In units of the
                    pre-stock-scale human room (``SINK_PER_H`` turns it into H).
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
# The cave Purpose's mood: blue-grey rock light, and a brighter crystal glow
# (cold with an arcane edge) in its climax.
_CAVE = (0.5, 0.58, 0.72)
_CRYSTAL = (0.6, 0.72, 1.0)

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
    # --- natural cave (the ``cave`` Purpose, step 21) ---
    "cave_mouth":    RoomType("cave_mouth", footprint=1.2, ceiling=0.85, light=_CAVE, intensity=0.75,
                              props=("daylight spill", "rock fall", "moss"),
                              encounter="cave dwellers at the threshold"),
    "cavern":        RoomType("cavern", footprint=1.35, ceiling=1.3, light=_CAVE, intensity=0.55,
                              props=("stalagmites", "dripstone columns", "boulders"),
                              encounter="cave beasts"),
    "grotto":        RoomType("grotto", footprint=0.75, ceiling=0.8, light=_CAVE, intensity=0.45,
                              props=("fungus clusters", "dripping water", "loose scree"),
                              encounter="a lurking den creature"),
    "crystal_grotto": RoomType("crystal_grotto", footprint=1.1, ceiling=1.3, light=_CRYSTAL, intensity=1.0,
                              props=("crystal clusters", "glowing geode", "mirror pool"),
                              encounter="crystal guardian; boss"),
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
    "cave": Archetype(
        "cave", entrance_type="cave_mouth", climax_type="crystal_grotto", hub_type="cavern",
        arc=("passage", "grotto", "flooded_gallery", "sump", "collapsed_gallery", "warren")),
}

DEFAULT_ARCHETYPE = "fortress"


# ---------------------------------------------------------------------------
# Room kinds -> room types (graph layout engine; graph-layout Req 7.4)
#
# Rules set kinds, themes set types. A room grown by a rule set carries a kind
# (generators/topology/graph.py ROOM_KINDS); each theme maps it here to one or
# more of its room types. A kind with several types is sampled by graph depth
# like the archetype arc (shallow rooms take the first). ``entrance``, ``hub``
# and ``deep`` come from the archetype itself (entrance / hub / climax type: a
# fortress's deep end is its throne room); the rest are per theme. A kind a
# theme doesn't map (a set's own extra kind) falls back to the arc assignment,
# and the sidecar notes it (``unmapped_kinds``). Classic rooms carry no kind,
# so none of this touches them.
# ---------------------------------------------------------------------------

_THEME_KIND_TYPES: Dict[str, Dict[str, Tuple[str, ...]]] = {
    "fortress": {
        "passage": ("guard_post",),
        "chamber": ("barracks", "armory", "storeroom"),
        "lair":    ("prison_cell", "storeroom"),
        "hall":    ("barracks", "battle_arena"),
    },
    "war_city": {
        "passage": ("guard_post",),
        "chamber": ("barracks", "armory", "shrine"),
        "lair":    ("storeroom", "prison_cell"),
        "hall":    ("battle_arena",),
    },
    "warren": {
        "passage": ("warren",),
        "chamber": ("warren", "storeroom", "collapsed_gallery"),
        "lair":    ("warren", "storeroom"),
        "hall":    ("collapsed_gallery",),
    },
    "temple": {
        "passage": ("passage",),
        "chamber": ("shrine", "sacrifice_chamber", "ossuary"),
        "lair":    ("shrine",),                                 # the nave's side chapels
        "hall":    ("sacrifice_chamber", "ritual_chamber"),     # the nave
    },
    "tomb": {
        "passage": ("passage",),
        "chamber": ("ossuary", "ritual_chamber", "collapsed_gallery"),
        "lair":    ("ossuary",),
        "hall":    ("ritual_chamber",),
    },
    "wizard_lair": {
        "passage": ("passage",),
        "chamber": ("laboratory", "storeroom", "summoning_hall"),
        "lair":    ("prison_cell", "storeroom"),
        "hall":    ("summoning_hall",),
    },
    "corrupted_sanctum": {
        "passage": ("passage",),
        "chamber": ("shrine", "ossuary", "sacrifice_chamber"),
        "lair":    ("ossuary", "shrine"),
        "hall":    ("summoning_hall",),
    },
    "mine_delve": {
        "passage": ("passage",),
        "chamber": ("storeroom", "collapsed_gallery", "forge"),
        "lair":    ("sump", "storeroom"),
        "hall":    ("collapsed_gallery", "forge"),
    },
    "sunken_ruin": {
        "passage": ("passage",),
        "chamber": ("flooded_gallery", "ossuary", "ritual_chamber"),
        "lair":    ("sump",),
        "hall":    ("flooded_gallery",),
    },
    "lava_forge": {
        "passage": ("passage",),
        "chamber": ("forge", "storeroom", "armory"),
        "lair":    ("storeroom", "collapsed_gallery"),
        "hall":    ("forge",),
    },
    "ice_keep": {
        "passage": ("guard_post",),
        "chamber": ("barracks", "warren", "ossuary"),
        "lair":    ("warren", "collapsed_gallery"),
        "hall":    ("barracks",),
    },
    "cave": {
        "passage": ("passage", "grotto"),
        "chamber": ("grotto", "flooded_gallery", "collapsed_gallery"),
        "lair":    ("grotto", "sump", "warren"),
        "hall":    ("cavern",),
    },
}


def kind_types(archetype: str) -> Dict[str, Tuple[str, ...]]:
    """The theme's kind -> room types map (an unknown theme is the default's)."""
    arch = ARCHETYPES.get((archetype or "").lower(), ARCHETYPES[DEFAULT_ARCHETYPE])
    return {
        "entrance": (arch.entrance_type,),
        "hub": (arch.hub_type,),
        "deep": (arch.climax_type,),
        **_THEME_KIND_TYPES.get(arch.name, {}),
    }


def unmapped_kinds(archetype: str, kinds) -> List[str]:
    """The room kinds in *kinds* the theme has no type for (sorted, unique)."""
    mapped = kind_types(archetype)
    return sorted({k for k in kinds if k and k not in mapped})


# ---------------------------------------------------------------------------
# Race-sized rooms (verticality step 7, Requirement 10; design "Race-sized
# rooms", finding 8). The ONE place a room-graph zone's rooms and corridors
# get their size, for both layout engines.
#
# Each race has a body height H: its default height in the client's
# racedata.txt (world units; the human is 6 u, the walk agent's player
# height). Every room's height and footprint side sit in a band of multiples
# of H, the same for every race (task 16 measured stock rooms against the race
# that lives in them; the user chose stock scale, 2026-11-04):
#
#   room height     [2.5 H, 10 H]   human 15-60 u, dragon 53-210 u
#   footprint side  [8 H, 20 H]     human 48-120 u, dragon 168-420 u
#
# A Size_Class picks a point in the band (``CLASS_POSITION``: tiny at the
# minimum, huge at the maximum), geometrically, so each class step is the same
# ratio. The plan's Size control shifts that point (``SIZE_SHIFT``), still
# inside the band. Corridors are a fixed multiple of H (stock corridors are
# 12-28 u for humans, about 2-5 H wide). The measured whole-zone floor area no
# longer sizes room-graph rooms; a zone's total size follows from its room
# count and its rooms' classes.
# ---------------------------------------------------------------------------

#: Body height H (u) per race: racedata.txt's default height (finding 8).
RACE_HEIGHT: Dict[str, float] = {
    "default": 6.0,     # human (HUM); the walk agent's 6 u player
    "goblin": 6.0,
    "froglok": 5.0,
    "kobold": 5.0,
    "lizardman": 6.0,
    "gnoll": 6.0,
    "sarnak": 9.0,
    "troll": 8.0,
    "ogre": 9.0,
    "giant": 22.0,      # frost giant (Kael Drakkel)
    "dragon": 21.0,     # DRA (Nagafen, Veeshan's Peak)
}
DEFAULT_RACE_HEIGHT = RACE_HEIGHT["default"]

#: Room height and footprint side bands, as multiples of H.
ROOM_HEIGHT_BAND: Tuple[float, float] = (2.5, 10.0)
ROOM_SIDE_BAND: Tuple[float, float] = (8.0, 20.0)

#: Size_Class -> position in the bands (0 the minimum, 1 the maximum).
CLASS_POSITION: Dict[str, float] = {
    "tiny": 0.0, "small": 0.25, "medium": 0.5, "large": 0.75, "huge": 1.0,
}
#: The plan's Size control: a shift of every room's band position (clamped
#: to the band, so a race's rooms stay its own).
SIZE_SHIFT: Dict[str, float] = {
    "small": -0.125, "medium": 0.0, "large": 0.125, "huge": 0.25,
}

#: Corridor width and height, as multiples of H: 3 H wide (18 u for a human,
#: inside stock's 12-28 u) and as tall as the lowest room (2.5 H, 15 u: over
#: the 6 u player and never above a room's ceiling at a doorway).
CORRIDOR_WIDTH_H = 3.0
CORRIDOR_HEIGHT_H = ROOM_HEIGHT_BAND[0]
#: The corridor band V11 checks (multiples of H; stock 2-5 H wide).
CORRIDOR_WIDTH_BAND: Tuple[float, float] = (2.0, 5.0)
CORRIDOR_HEIGHT_BAND: Tuple[float, float] = ROOM_HEIGHT_BAND

#: A room type's floor sink/raise (``RoomType.sink``) is in units of a human
#: room as it was before stock scale (121 u, 20 H); this turns it into H.
#: A -30 u sump sinks 1.25 H (7.5 u for a human, 27.5 u for a giant).
SINK_PER_H = 1.0 / 24.0


def body_height(race: str) -> float:
    """The race's body height H in world units (the default race: a human)."""
    return RACE_HEIGHT.get((race or "default").lower(), DEFAULT_RACE_HEIGHT)


def race_scale(race: str) -> float:
    """H over a human's: what the topology rules' ``race_scale`` condition
    reads (``great_hall`` at >= 1.4: sarnak, ogres, giants, dragons)."""
    return body_height(race) / DEFAULT_RACE_HEIGHT


def band_position(size: Optional[str], shift: float = 0.0) -> float:
    """A Size_Class's position in the bands, after the Size control's shift,
    clamped to [0, 1]. An unknown or missing class is medium."""
    t = CLASS_POSITION.get(size or "medium", CLASS_POSITION["medium"]) + shift
    return min(1.0, max(0.0, t))


def _band_at(band: Tuple[float, float], t: float, h: float) -> float:
    lo, hi = band
    return h * lo * (hi / lo) ** min(1.0, max(0.0, t))


def room_side(race: str, t: float) -> float:
    """Footprint side (u) at band position ``t`` for ``race``."""
    return _band_at(ROOM_SIDE_BAND, t, body_height(race))


def room_height(race: str, t: float) -> float:
    """Room height (u) at band position ``t`` for ``race``."""
    return _band_at(ROOM_HEIGHT_BAND, t, body_height(race))


def room_bands(race: str) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """``((side_min, side_max), (height_min, height_max))`` in u."""
    h = body_height(race)
    return ((ROOM_SIDE_BAND[0] * h, ROOM_SIDE_BAND[1] * h),
            (ROOM_HEIGHT_BAND[0] * h, ROOM_HEIGHT_BAND[1] * h))


def corridor_size(race: str) -> Tuple[float, float]:
    """``(width, height)`` of the race's corridors, in u."""
    h = body_height(race)
    return CORRIDOR_WIDTH_H * h, CORRIDOR_HEIGHT_H * h


def fit_to_band(room: RoomSpec, race: str) -> None:
    """Clamp ``room``'s width, depth and height into ``race``'s bands. The
    last step of sizing: the role and room-type biases (and the classic
    engine's gaussian spread) can push a room past either end."""
    (s0, s1), (h0, h1) = room_bands(race)
    room.width = min(s1, max(s0, room.width))
    room.depth = min(s1, max(s0, room.depth))
    room.height = min(h1, max(h0, room.height))


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
                overrides: Optional[Dict[str, str]] = None,
                districts: Optional[Sequence[DistrictSpec]] = None) -> None:
    """
    Phase 1 — assign each room a semantic type + theme and realise the parts
    that affect GEOMETRY (shape / proportion / ceiling / floor-height) plus the suggestion fields. Call AFTER _apply_pacing (rooms must have
    role + graph_depth) and BEFORE re-separate / elevation, so the biased shapes
    are resolved for overlaps and elevation builds on the sunk/raised floors.

    *rooms* is the working list (not yet appended to spec). Zone-level theme
    fields are recorded on *spec*.

    *archetype* selects the arc (defaults deterministically if unknown).
    *race* sizes the floor sink (its body height). *tint* overrides the archetype's
    default elemental tint ("" to force none; None to use the archetype default).
    *overrides* maps room.id → semantic_type for planner-driven assignment.

    *districts* (two or more, districts spec Req 2.2): each room takes its
    types from its own District's Purpose (``room.district`` -> the District
    with that id) by in-District depth; *archetype* is then unused and
    ``spec.dungeon_theme`` is District 0's Purpose. ``None`` or one District
    is the single-District path, unchanged.
    """
    if not rooms:
        return
    if districts is not None and len(districts) >= 2:
        _label_districted(spec, rooms, rng, districts, race, tint, overrides or {})
        return

    arch =ARCHETYPES.get((archetype or "").lower(), ARCHETYPES[DEFAULT_ARCHETYPE])
    effective_tint = arch.tint if tint is None else tint

    spec.dungeon_theme = arch.name
    spec.dungeon_race = (race or "default").lower()
    spec.elemental_tint = effective_tint

    overrides = overrides or {}
    max_depth = max((r.graph_depth for r in rooms), default=0)

    kmap = kind_types(arch.name)

    for r in rooms:
        # Choose the semantic type: planner override wins, then the theme's
        # map of the room's kind (graph layouts), else the arc by role/depth.
        if r.id in overrides and overrides[r.id] in ROOM_TYPES:
            type_name = overrides[r.id]
        elif r.kind and r.kind in kmap:
            type_name = _pick_by_depth(kmap[r.kind], r, max_depth, rng)
        else:
            type_name = _type_for_room(arch, r, max_depth, rng)
        rt = ROOM_TYPES.get(type_name, ROOM_TYPES["passage"])

        r.semantic_type = type_name
        r.room_theme = arch.name
        # The boss room is the pacing climax (on a grown layout the engine
        # names the rules' deep end as the climax).
        r.boss = r.role == "climax"

        # Suggestion fields (data only — never placed geometry).
        r.prop_hints = list(rt.props)
        r.encounter_intent = rt.encounter

        # Realize shape / proportion / ceiling / elevation character + race.
        _apply_shape(r, rt, race)


def realize_semantics(spec: ZoneSpec, rng: random.Random,
                      districts: Optional[Sequence[DistrictSpec]] = None,
                      thresholds: Optional[Sequence[Tuple[int, int]]] = None) -> None:
    """
    Phase 2 — realise the parts that depend on final room geometry and on the
    spec being fully assembled: per-room material (palette) selection, elemental
    region volumes, and lighting mood. Call AFTER rooms (and their pacing
    lights, if any) are appended to the spec.

    *districts* defaults to ``spec.districts``. With two or more, each room
    takes its District's palette (variant included) and light mood, and each
    of *thresholds* (``(parent side, child side)`` indices into ``spec.rooms``,
    as ``Partition.thresholds``) gets ends that differ in material set and in
    light (districts spec Req 2.4, umbrella 23.5). With none or one District
    this is the single-District path, unchanged.
    """
    if not spec.rooms:
        return
    if districts is None:
        districts = spec.districts
    if len(districts) >= 2:
        _realize_districted(spec, districts, thresholds or ())
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
    return _pick_by_depth(arc, room, max_depth, rng)


def _pick_by_depth(arc: Tuple[str, ...], room: RoomSpec, max_depth: int,
                   rng: random.Random) -> str:
    """One type of *arc* by the room's normalised graph depth, with a small
    jitter. A one-type arc draws nothing from *rng*."""
    return _pick_at(arc, room.graph_depth, max_depth, rng)


def _pick_at(arc: Tuple[str, ...], depth: int, max_depth: int,
             rng: random.Random) -> str:
    """:func:`_pick_by_depth` at an explicit depth (a District's in-District depth)."""
    if len(arc) == 1:
        return arc[0]
    frac = (depth / max_depth) if max_depth > 0 else 0.0
    idx = int(round(frac * (len(arc) - 1)))
    jitter = rng.choice([-1, 0, 0, 1])
    idx = max(0, min(len(arc) - 1, idx + jitter))
    return arc[idx]


def _apply_shape(room: RoomSpec, rt: RoomType, race: str) -> None:
    """
    Compose the semantic-type shape bias with the pacing role scale already on
    the room. Keeps floors flat/walkable — only footprint, aspect, ceiling, and
    floor height change.

    A room grown by a rule set (it carries a ``kind``) has its footprint area
    from its Size_Class (graph-layout Req 6.1: rules own size), so the type
    keeps only its PROPORTION: the aspect stretch is applied, then the
    footprint is renormalised to the area the room came with (the type's
    footprint multiplier drops out). Ceiling mood and floor sink still apply.

    The race is already in every room's size (both engines size rooms from
    the race's bands, step 7 task 17), so it is never applied here; the
    layout clamps the biased room back into the bands (``fit_to_band``). The
    floor sink is in H (``SINK_PER_H``), so a giant's sunken arena sinks
    proportionally.
    """
    # Footprint + aspect: stretch the longer axis for processional rooms.
    fw = rt.footprint
    fd = rt.footprint
    if rt.aspect != 1.0:
        if room.width >= room.depth:
            fw *= rt.aspect
        else:
            fd *= rt.aspect
    if room.kind:
        k = (fw * fd) ** -0.5
        fw *= k
        fd *= k

    room.width = room.width * fw
    room.depth = room.depth * fd
    room.height = room.height * rt.ceiling

    # Elevation character: nudge the floor height (sunken/raised), in H. This
    # is a hint on the base floor_z; _assign_elevation still runs afterward
    # over the graph.
    if rt.sink:
        room.floor_z += rt.sink * SINK_PER_H * body_height(race)


def texture_set(zone_type: str, race: str = "", key: str = "") -> str:
    """The Texture_Set a room-graph material belongs to (placeholder textures
    spec Req 1.3-1.4): a dungeon's race (unless unset or ``default``) then the
    theme or tint *key*, or ``dungeon`` for shared surfaces; a city is ``city``,
    followed by the *key* for a themed room."""
    if zone_type == "city":
        words = ["city", key]
    else:
        race = "" if (race or "").lower() == "default" else race
        words = [race, key or zone_type or "dungeon"]
    return "_".join(w.lower() for w in words if w)


def material_name(tex_set: str, surface: str) -> str:
    """Material_Name ``<Texture_Set>_<Surface>``, e.g. ``gnoll_temple_wall``."""
    return f"{tex_set}_{surface}"


def _material_variant(spec: ZoneSpec, base: str, theme: str, tint: str) -> str:
    """Material_Name for a themed/tinted room surface, e.g. 'gnoll_temple_wall'."""
    key = tint if tint else theme
    return material_name(texture_set(spec.zone_type, spec.dungeon_race, key), base)


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
    "cave": {
        "floor": ((70, 72, 74), "damp cave rock floor, wet stone, mineral seams"),
        "wall":  ((84, 86, 90), "rough natural rock wall, wet sheen, mineral streaks"),
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

    for base in ("floor", "wall"):
        if base not in palette:
            continue
        name = _material_variant(spec, base, theme, tint)
        if name not in spec.materials:
            color, desc = palette[base]
            spec.add_material(name, f"{name}.dds", shader=SHADER_OPAQUE,
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


# ---------------------------------------------------------------------------
# Districts (districts spec Requirement 2, umbrella 23.4-23.5, 23.8, 23.10)
#
# A multi-District zone labels each room from its own District's Purpose and
# realises each District's palette and light. A District's palette is its
# Purpose's at a variant level: 0 as built, 1 ``abandoned`` (half saturation,
# dimmer and colder light), 2 ``ruined`` (further still). The level is in the
# palette key (``temple``, ``temple_abandoned``) and so in the Material_Name,
# which keys the texture. Nothing here runs for a one-District zone.
# ---------------------------------------------------------------------------

#: Palettes for the four archetypes that had none (A3). Used ONLY in
#: multi-District zones (archive decision 4): a one-District war_city keeps
#: the base materials it always had.
_DISTRICT_PALETTES: Dict[str, Dict[str, Tuple[Tuple[int, int, int], str]]] = {
    "war_city": {
        "floor": ((102, 92, 78), "battle-worn paved street stone, ash"),
        "wall":  ((124, 108, 90), "fortified city wall, banner hooks, scorch marks"),
    },
    "warren": {
        "floor": ((92, 78, 60), "packed earth floor, straw and droppings"),
        "wall":  ((108, 90, 68), "dug earthen burrow wall, roots"),
    },
    "corrupted_sanctum": {
        "floor": ((84, 66, 76), "defiled temple flagstone, dark stains"),
        "wall":  ((98, 74, 88), "blighted shrine stone, profane sigils"),
    },
    "mine_delve": {
        "floor": ((82, 76, 70), "rough-hewn mine floor, ore dust, cart ruts"),
        "wall":  ((96, 88, 78), "pick-scarred rock wall, timber props"),
    },
}

#: Every Purpose's palette, multi-District zones only.
PURPOSE_PALETTES: Dict[str, Dict[str, Tuple[Tuple[int, int, int], str]]] = {
    **_THEME_PALETTES, **_DISTRICT_PALETTES,
}

#: Variant levels: name (in the palette key), light mood, colour saturation and
#: value, light intensity, and how far the light leans to cold.
VARIANTS: Tuple[str, ...] = ("", "abandoned", "ruined")
LIGHT_MOODS: Tuple[str, ...] = ("lit", "dim", "faint")
_VARIANT_SAT = (1.0, 0.5, 0.25)
_VARIANT_VALUE = (1.0, 0.85, 0.7)
_VARIANT_LIGHT = (1.0, 0.65, 0.45)
_VARIANT_COLD = (0.0, 0.25, 0.45)
#: A Threshold whose two ends would still light the same: the child's scale.
_THRESHOLD_DIM = 0.8


def palette_key(purpose: str, level: int = 0) -> str:
    """A District's palette key: ``temple``, ``temple_abandoned``, ``temple_ruined``."""
    variant = VARIANTS[level % len(VARIANTS)]
    return f"{purpose}_{variant}" if variant else purpose


def palette_level(key: str) -> Tuple[str, int]:
    """``(purpose, level)`` of a palette key (inverse of :func:`palette_key`)."""
    for level in range(len(VARIANTS) - 1, 0, -1):
        suffix = "_" + VARIANTS[level]
        if key.endswith(suffix):
            return key[: -len(suffix)], level
    return key, 0


def set_district_palette(district: DistrictSpec, level: int) -> None:
    """Point *district* at its Purpose's palette and light mood at *level*."""
    level %= len(VARIANTS)
    district.palette = palette_key(district.purpose, level)
    district.light_mood = LIGHT_MOODS[level]


def _district_palette(district: DistrictSpec) -> Tuple[str, int]:
    """``(purpose, level)`` of a District, its Purpose at level 0 when unset."""
    if district.palette:
        return palette_level(district.palette)
    return district.purpose, 0


def separate_threshold_palettes(districts, pairs: Sequence[Tuple[int, int]]) -> None:
    """Umbrella 23.5 for the material sets: for each ``(parent, child)`` pair of
    District ids (parents first), a child whose palette equals its parent's
    takes the next variant level. *districts* maps id -> DistrictSpec (or is a
    list indexed by id). Draws nothing."""
    for p, c in pairs:
        parent, child = districts[p], districts[c]
        p_purpose, p_level = _district_palette(parent)
        c_purpose, c_level = _district_palette(child)
        if (p_purpose, p_level) == (c_purpose, c_level):
            set_district_palette(child, p_level + 1)
        elif not child.palette:
            set_district_palette(child, c_level)


def _desaturate(color: Tuple[int, int, int], level: int) -> Tuple[int, int, int]:
    grey = sum(color) / 3.0
    sat, val = _VARIANT_SAT[level], _VARIANT_VALUE[level]
    return tuple(max(0, min(255, int(round((grey + (c - grey) * sat) * val))))
                 for c in color)


def _district_light(rgb: Tuple[float, float, float], level: int) -> Tuple[float, float, float]:
    """A variant's light: leaned toward cold, then dimmed."""
    cold, k = _VARIANT_COLD[level], _VARIANT_LIGHT[level]
    return tuple((c * (1.0 - cold) + w * cold) * k for c, w in zip(rgb, _COLD))


def _label_districted(spec: ZoneSpec, rooms: List[RoomSpec], rng: random.Random,
                      districts: Sequence[DistrictSpec], race: str,
                      tint: Optional[str], overrides: Dict[str, str]) -> None:
    """``label_rooms`` with Districts: each room's arc is its District's
    Purpose, sampled by in-District depth.

    A District's entrance is its shallowest room (ties to the lowest index):
    the zone entrance for District 0, else the child side of its Threshold,
    since the Threshold is the only way in (archive decision 5). The same
    bridge makes in-District depth ``graph_depth`` less the entrance's. A
    District entrance takes its Purpose's entrance type (unless an override,
    its kind or the climax role says otherwise); the climax role, one per
    District, is set by pacing.
    """
    by_id = {d.id: d for d in districts}
    first = by_id[min(by_id)]
    archs = {d.id: ARCHETYPES.get((d.purpose or "").lower(), ARCHETYPES[DEFAULT_ARCHETYPE])
             for d in districts}

    zone_arch = archs[first.id]
    spec.dungeon_theme = zone_arch.name
    spec.dungeon_race = (race or "default").lower()
    spec.elemental_tint = zone_arch.tint if tint is None else tint

    def home(r: RoomSpec) -> int:
        return r.district if r.district in by_id else first.id

    start: Dict[int, int] = {}
    for i, r in enumerate(rooms):
        d = home(r)
        if d not in start or r.graph_depth < rooms[start[d]].graph_depth:
            start[d] = i
    depth = [r.graph_depth - rooms[start[home(r)]].graph_depth for r in rooms]
    max_depth: Dict[int, int] = {}
    for i, r in enumerate(rooms):
        d = home(r)
        max_depth[d] = max(max_depth.get(d, 0), depth[i])
    kmaps = {d: kind_types(a.name) for d, a in archs.items()}

    for i, r in enumerate(rooms):
        d = home(r)
        arch, kmap, md = archs[d], kmaps[d], max_depth[d]
        if r.id in overrides and overrides[r.id] in ROOM_TYPES:
            type_name = overrides[r.id]
        elif r.kind and r.kind in kmap:
            type_name = _pick_at(kmap[r.kind], depth[i], md, rng)
        elif r.role == "climax":
            type_name = arch.climax_type
        elif i == start[d] or r.role == "entrance":
            type_name = arch.entrance_type
        elif r.role == "hub":
            type_name = arch.hub_type
        elif arch.arc:
            type_name = _pick_at(arch.arc, depth[i], md, rng)
        else:
            type_name = "passage"
        rt = ROOM_TYPES.get(type_name, ROOM_TYPES["passage"])

        r.semantic_type = type_name
        r.room_theme = arch.name
        r.boss = r.role == "climax"
        r.prop_hints = list(rt.props)
        r.encounter_intent = rt.encounter
        _apply_shape(r, rt, race)


def _realize_districted(spec: ZoneSpec, districts: Sequence[DistrictSpec],
                        thresholds: Sequence[Tuple[int, int]]) -> None:
    """``realize_semantics`` with Districts (see there)."""
    by_id = {d.id: d for d in districts}
    first = by_id[min(by_id)]

    def home(room: RoomSpec) -> DistrictSpec:
        return by_id.get(room.district, first)

    ends = [(a, b) for a, b in thresholds
            if 0 <= a < len(spec.rooms) and 0 <= b < len(spec.rooms)]
    pairs = []
    for a, b in ends:
        pa, pb = home(spec.rooms[a]).id, home(spec.rooms[b]).id
        if pa != pb:
            pairs.append((pa, pb))
    separate_threshold_palettes(by_id, pairs)

    for room in spec.rooms:
        purpose, level = _district_palette(home(room))
        _apply_district_materials(spec, room, purpose, level)

    tint = spec.elemental_tint
    _, tint_rgb, tint_imult = _TINTS.get(tint, ("", None, 1.0))
    moods: List[Tuple[float, float, float]] = []
    for i, room in enumerate(spec.rooms):
        rt = ROOM_TYPES.get(room.semantic_type, ROOM_TYPES["passage"])
        if rt.region:
            _add_room_region(spec, room, rt.region, i)
        rgb = rt.light
        intensity = rt.intensity
        if tint_rgb is not None and rt.region:
            rgb = tint_rgb
            intensity *= tint_imult
        intensity *= max(0.5, 1.0 - room.graph_depth * 0.05)
        if room.role == "entrance":
            intensity = max(intensity, 0.95)
        _, level = _district_palette(home(room))
        moods.append(_district_light(tuple(c * intensity for c in rgb), level))

    # The light half of 23.5: the child end of a Threshold that would still
    # light like the parent end is dimmed (parents first, so a chain settles).
    for a, b in ends:
        if all(abs(x - y) < 1e-3 for x, y in zip(_clamp(moods[a]), _clamp(moods[b]))):
            moods[b] = tuple(c * _THRESHOLD_DIM for c in moods[b])

    for i, room in enumerate(spec.rooms):
        _set_room_light(spec, room, i, *moods[i])


def _clamp(rgb) -> Tuple[float, ...]:
    return tuple(max(0.0, min(1.0, c)) for c in rgb)


def _apply_district_materials(spec: ZoneSpec, room: RoomSpec, purpose: str,
                              level: int) -> None:
    """Point the room at its District's floor/wall variants (registered on
    first use). Ceiling keeps the shared material, as in ``_apply_materials``."""
    palette = PURPOSE_PALETTES.get(purpose)
    if not palette:
        return
    key = palette_key(purpose, level)
    for base in ("floor", "wall"):
        if base not in palette:
            continue
        name = material_name(texture_set(spec.zone_type, spec.dungeon_race, key), base)
        if name not in spec.materials:
            color, desc = palette[base]
            if level:
                color = _desaturate(color, level)
                desc = f"{VARIANTS[level]}, faded: {desc}"
            spec.add_material(name, f"{name}.dds", shader=SHADER_OPAQUE,
                              color=color, description=desc)
        if base == "floor":
            room.floor_material = name
        else:
            room.wall_material = name
