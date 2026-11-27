"""
ai/schema.py
------------
The JSON contract between a planner (rule-based or LLM) and the generators.

A planner's job is to turn a text prompt into a *plan* — a compact, high-level
description of the zone — NOT geometry. The plan is then expanded into a full
ZoneSpec by `ai.plan_to_spec`, which runs the same LayoutGenerator the dropdowns
use, applying the plan's parameters.

Keeping the plan small and declarative makes it reliable to produce (an LLM only
has to fill a handful of fields) and easy to validate.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any, Mapping, Tuple

from generators.zone_types import (
    DEFINED_ZONE_TYPES, DEFAULT_ZONE_TYPE, canonical_zone_type, read_zone_type,
)

# The canonical zone-type vocabulary, sourced from the single source of truth
# (generators/zone_types.py). New code uses ``zone_type`` / ``wilderness``; the
# legacy ``theme`` key and the ``outdoor`` value are accepted on load and mapped
# forward via ``canonical_zone_type`` (umbrella decision 19; Req 11.1, 11.2).
VALID_ZONE_TYPES = list(DEFINED_ZONE_TYPES)

VALID_REGION_KINDS = ["water", "lava", "ice", "pvp", "zoneline", "generic"]

# Content / semantic layer (dungeon theme). Archetypes mirror
# generators.semantics.ARCHETYPES; races mirror generators.semantics.RACE_HEIGHT
# (each race's body height sizes its rooms; the default race is a human).
VALID_DUNGEON_THEMES = [
    "fortress", "war_city", "warren", "temple", "tomb", "wizard_lair",
    "corrupted_sanctum", "mine_delve", "sunken_ruin", "lava_forge", "ice_keep",
    "cave",
]
VALID_DUNGEON_RACES = [
    "goblin", "froglok", "kobold", "lizardman", "gnoll", "sarnak", "troll",
    "ogre", "giant", "dragon",
]
VALID_ELEMENTAL_TINTS = ["lava", "ice", "water"]

# Districts (districts spec Req 4.1, umbrella 23): off by default (A1); a plan
# proposes up to three District Purposes (``{"purpose": name}``, an archetype
# from VALID_DUNGEON_THEMES, or "" for a District the relationship chooses) and
# one relationship ("" is the default, sequential). The relationships mirror
# generators.districts.RELATIONSHIPS (written out, as the archetypes are; a
# test keeps the two equal). Dungeons only (A2): ``plan_to_spec`` ignores them
# on any other zone type with a note.
VALID_DISTRICT_RELATIONSHIPS = ["sequential", "factional", "abandoned_vs_active", "intrusion"]
MAX_DISTRICT_PROPOSALS = 3
DISTRICT_ZONE_TYPES = ("dungeon",)

# Layout engine (graph-layout Req 7): ``classic`` is the TinyKeep layout,
# ``graph`` grows the room graph by a rule set. Only these zone types take it;
# every other type ignores the two fields.
#
# Defaults (graph-layout task 21, decision 26: "graph should be the default
# going forward"). A NEW request that doesn't name a layout gets
# ``DEFAULT_LAYOUT`` (graph) on a dungeon / outdoor dungeon; other zone types
# resolve to ``classic``, which they ignore, so their plans are unchanged. A
# plan SAVED before step 6 has no ``layout`` key and was built classic, so
# ``ZonePlan.from_saved`` reads a missing key as ``LEGACY_LAYOUT`` (classic):
# the same saved plan and pinned seed keep rebuilding the same zone.
VALID_LAYOUTS = ["classic", "graph"]
DEFAULT_LAYOUT = "graph"
LEGACY_LAYOUT = "classic"
LAYOUT_ZONE_TYPES = ("dungeon", "outdoor_dungeon")

# The base rule sets ship as rules/topology/<name>.toml (themes.toml is the
# theme map, layers/ hold theme layers). Discovered from the folder, so a new
# base set needs no code change. Read with a plain glob: generators.topology
# imports this module, so importing it here would be a cycle.
RULES_TOPOLOGY_DIR = Path(__file__).resolve().parent.parent / "rules" / "topology"


VALID_FEATURES = ["none", "sparse", "normal", "dense"]


SCALE_CONTROLS = ("finish", "structure", "clutter")

# Sites in the wilderness (step 10): how many (generators.sites.rules.DENSITIES)
# and who builds them ("" = the biome's mix). Wilderness and outdoor dungeon only.
VALID_SITES = ["none", "sparse", "normal", "dense"]
DEFAULT_SITES = "normal"
SITES_ZONE_TYPES = ("wilderness", "outdoor_dungeon")

# Props in rooms (room-decor step 11, Req 10.1, 10.2): the Decor control
# (generators.decor.rules.CONTROLS; that module imports this one, so the list
# is written out here and a test keeps the two equal) and a decor seed. A plan
# decor of "" is not chosen: the pipeline builds the default, normal
# (generators.pipeline._with_decor). The room-graph zone types, and the
# wilderness for its Sites' Props (room-decor task 20).
VALID_DECOR = ["none", "sparse", "normal", "dense"]
DEFAULT_DECOR = "normal"
DECOR_ZONE_TYPES = ("dungeon", "city", "wilderness", "outdoor_dungeon")
SEED_MAX = 2_147_483_647

# Decor layers (decor-rules step 15, Req 2): rules/decor/layers/<name>.toml, merged
# onto rooms.toml by generators.decor.rules.load_decor. Read with a plain glob, as
# the rule sets are: that module imports this one. The builder reads the folder
# from here too, so the two agree.
RULES_DECOR_DIR = Path(__file__).resolve().parent.parent / "rules" / "decor"


def available_decor_layers(rules_dir: Optional[Path] = None) -> List[str]:
    """The decor layer names in ``rules/decor/layers/`` (sorted)."""
    d = Path(rules_dir) if rules_dir is not None else RULES_DECOR_DIR
    return sorted(p.stem for p in (d / "layers").glob("*.toml"))


def decor_layers(value: Any, rules_dir: Optional[Path] = None) -> Tuple[str, ...]:
    """A request's extra decor layers: None, "" or [] for none; a name or a list of
    names, each a file in ``rules/decor/layers/``, each kept once where it first
    stands. Anything else raises ``ValueError`` naming the known layers."""
    if value is None or value == "":
        return ()
    names = [value] if isinstance(value, str) else value
    if not isinstance(names, (list, tuple)) or any(not isinstance(n, str) for n in names):
        raise ValueError(f"decor_layers {value!r} is not a list of decor layer names")
    names = [n.strip() for n in names if n.strip()]
    known = available_decor_layers(rules_dir)
    for n in names:
        if n not in known:
            raise ValueError(f"decor_layers {n!r} is not one of: "
                             + (", ".join(known) if known else "none (rules/decor/layers/ holds no layer yet)"))
    return tuple(dict.fromkeys(names))


def decor_seed(value: Any, name: str = "decor_seed") -> Optional[int]:
    """A stage seed (``decor_seed``, ``rooms_seed``): None (the zone's seed stands in), or a
    whole 0..2^31-1. ``name`` is the field the error names."""
    if value is None or value == "":
        return None
    number = value if isinstance(value, int) and not isinstance(value, bool) else None
    if number is None or not 0 <= number <= SEED_MAX:
        raise ValueError(f"{name} {value!r} is not a whole number from 0 to {SEED_MAX}")
    return number


def rooms_seed(value: Any) -> Optional[int]:
    """A rooms seed: None (the zone's seed lays the rooms and Sites out), or a whole
    0..2^31-1 (world-sockets Req 4.1)."""
    return decor_seed(value, "rooms_seed")


# Winding (winding-control step 26, Req 1): how far rough corridors stray, a multiple of the
# stock-measured tunnel's wander (``rules/walls/rough.toml`` ``[tunnel]``). 0 builds them
# straight, 1 is stock. Above 1 a cave's run grows with it (``layout.profile_run_factor``).
# The top is measured (task 2, that spec's archive, decision 2): stray still rises to 2, and
# at 3 the longer run breaks the gate.
WINDING_MAX = 2.0
DEFAULT_WINDING = 1.0


def winding_value(value: Any) -> float:
    """A plan's winding: a number clamped to ``[0, WINDING_MAX]``; anything else (None, a
    bool, text that isn't a number, NaN) falls back to 1.0, as an unknown verticality does."""
    if isinstance(value, bool):
        return DEFAULT_WINDING
    try:
        number = float(value)
    except (TypeError, ValueError):
        return DEFAULT_WINDING
    if number != number:                    # NaN
        return DEFAULT_WINDING
    return max(0.0, min(WINDING_MAX, number))


# Hall length (hall-length step 30, Req 1): how long the halls between joined rooms run, a
# multiple of today's door-to-door length (``layout.hall_run_scale`` and friends turn it
# into each layout's spacing). 1 is today's zones, byte for byte. The range is measured
# (task 1, that spec's archive, decisions 2-3): stock's zone medians span about 0.5-3x ours;
# below 1 a layout shortens only as far as its separation floor allows.
HALL_MIN = 0.5
HALL_MAX = 3.0
DEFAULT_HALL_LENGTH = 1.0


def hall_length_value(value: Any) -> float:
    """A plan's hall length: a number clamped to ``[HALL_MIN, HALL_MAX]``; anything else
    (None, a bool, text that isn't a number, NaN) falls back to 1.0, as ``winding`` does."""
    if isinstance(value, bool):
        return DEFAULT_HALL_LENGTH
    try:
        number = float(value)
    except (TypeError, ValueError):
        return DEFAULT_HALL_LENGTH
    if number != number:                    # NaN
        return DEFAULT_HALL_LENGTH
    return max(HALL_MIN, min(HALL_MAX, number))


def district_switch(value: Any) -> bool:
    """The Districts switch: a bool, or a form-style string ("true"/"on"/"1")."""
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def district_plan(value: Any, warnings: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """A plan's District proposals (umbrella 23.9, 23.11, 23.12): None or "" for none, else
    a list of Purposes, each a name or a ``{"purpose": name}`` mapping, in District id
    order. Each comes back as ``{"purpose": name}``; "" leaves that District to the
    relationship. An unknown Purpose is ignored (its District left open) and anything past
    ``MAX_DISTRICT_PROPOSALS`` dropped, each with a note in *warnings*. A value that is not
    a list raises ``ValueError``."""
    if value is None or value == "":
        return []
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"district_plan {value!r} is not a list of District Purposes")
    out: List[Dict[str, str]] = []
    for d, item in enumerate(value):
        if d >= MAX_DISTRICT_PROPOSALS:
            if warnings is not None:
                warnings.append(f"district_plan_truncated: {len(value)} proposed, "
                                f"the first {MAX_DISTRICT_PROPOSALS} kept")
            break
        raw = item.get("purpose", "") if isinstance(item, Mapping) else item
        name = raw.strip().lower() if isinstance(raw, str) else ""
        known = raw is None or (isinstance(raw, str) and (not name or name in VALID_DUNGEON_THEMES))
        if not known:
            if warnings is not None:
                warnings.append(f"district_purpose_unknown: {raw!r} ignored (District {d})")
            name = ""
        out.append({"purpose": name})
    return out


def district_relationship(value: Any, warnings: Optional[List[str]] = None) -> str:
    """A plan's District relationship: "" (the default, sequential) or one of
    ``VALID_DISTRICT_RELATIONSHIPS``; anything else is ignored with a note (23.12)."""
    if value is None:
        return ""
    name = value.strip().lower() if isinstance(value, str) else ""
    if not isinstance(value, str) or (name and name not in VALID_DISTRICT_RELATIONSHIPS):
        if warnings is not None:
            warnings.append(f"district_relationship_unknown: {value!r} ignored, "
                            f"using {VALID_DISTRICT_RELATIONSHIPS[0]}")
        name = ""
    return name


class RoomSeeds(dict):
    """A plan's ``room_decor_seeds``: a read-only dict that hashes by its items, so a plan's
    fields stay hashable values (the test sweeps key builds on ``asdict(plan)``)."""

    def __hash__(self):
        return hash(frozenset(self.items()))

    def __reduce__(self):
        return (RoomSeeds, (dict(self),))

    def _read_only(self, *_a, **_k):
        raise TypeError("room_decor_seeds is read-only; validate a new plan")

    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _read_only


def room_decor_seeds(value: Any) -> "RoomSeeds":
    """Rooms that keep their own decor seed (partial-rebuild Req 3): None or {} for none, else
    a mapping of room id (a safe name: letters, digits, ``_ . -``) to a whole 0..2^31-1.
    Anything else raises ``ValueError``."""
    import re
    if value is None or value == "":
        return RoomSeeds()
    if not isinstance(value, Mapping):
        raise ValueError(f"room_decor_seeds {value!r} is not a mapping of room id to decor seed")
    out: Dict[str, int] = {}
    for room, seed in value.items():
        if not isinstance(room, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", room):
            raise ValueError(f"room_decor_seeds key {room!r} is not a room id")
        out[room] = decor_seed(seed, f"room_decor_seeds[{room!r}]")
        if out[room] is None:
            raise ValueError(f"room_decor_seeds[{room!r}] must be a whole number from 0 to {SEED_MAX}")
    return RoomSeeds(out)


def available_inhabitants(inhabitants_file: Optional[Path] = None) -> List[str]:
    """The Inhabitant names in ``rules/sites/inhabitants.toml`` (sorted)."""
    path = inhabitants_file or Path(__file__).resolve().parent.parent / "rules" / "sites" / "inhabitants.toml"
    with open(path, "rb") as f:
        return sorted(tomllib.load(f).get("inhabitants", {}))


def scale_control(name: str, value: Any) -> Optional[int]:
    """A Scale control's value: None for the rules alone ("" reads the same), or a whole 0-10."""
    if value is None or value == "":
        return None
    try:
        number = int(value) if not isinstance(value, (bool, float)) else None
    except (TypeError, ValueError):
        number = None
    if number is None or not 0 <= number <= 10:
        raise ValueError(f"{name} {value!r} is not a whole number from 0 to 10 (or \"\" for the rules alone)")
    return number


def available_overlays(scales_file: Optional[Path] = None) -> List[str]:
    """The overlay names in ``rules/rooms/scales.toml`` (sorted)."""
    path = scales_file or Path(__file__).resolve().parent.parent / "rules" / "rooms" / "scales.toml"
    with open(path, "rb") as f:
        return sorted(tomllib.load(f).get("overlays", {}))


def available_wall_styles(rules_dir: Optional[Path] = None) -> List[str]:
    """The wall style names under ``rules/walls/`` (sorted)."""
    folder = rules_dir or Path(__file__).resolve().parent.parent / "rules" / "walls"
    return sorted(p.stem for p in folder.glob("*.toml"))


def available_rule_sets(rules_dir: Optional[Path] = None) -> List[str]:
    """The base rule-set names under ``rules/topology/`` (sorted)."""
    d = Path(rules_dir) if rules_dir is not None else RULES_TOPOLOGY_DIR
    return sorted(p.stem for p in d.glob("*.toml") if p.stem != "themes")

# Control-key aliases for the geometry-slice controls path (Req 1.2, 2.3, 2.4).
# Each key is a flat control name that maps to its ZonePlan field. A plan key
# present in the dict WINS over its alias (if both ``room_count`` and ``rooms``
# appear, ``room_count`` wins; same for ``zone_type`` vs ``theme``). This is the
# only layer ``from_controls`` adds over ``from_dict`` besides the legacy
# ``elevation: false`` -> ``verticality: "flat"`` translation below.
CONTROL_ALIASES = {"rooms": "room_count", "theme": "zone_type"}


@dataclass
class ZonePlan:
    """
    A high-level zone plan. Every field has a sane default so a partial plan
    (from a terse prompt or a sparse LLM response) still yields a valid zone.
    """
    name: str = "zone"
    zone_type: str = "dungeon"       # one of VALID_ZONE_TYPES
    room_count: int = 5              # 1..30
    size: str = "medium"             # small | medium | large | huge
    elevation: bool = True           # multi-level layout
    verticality: str = "moderate"    # flat | moderate | dramatic
    # How far rough corridors stray (step 26): 0 straight .. WINDING_MAX; 1 the stock tunnel.
    # ``to_dict`` leaves it out at 1.
    winding: float = DEFAULT_WINDING
    # How long the halls between rooms run (step 30): HALL_MIN .. HALL_MAX, a multiple of
    # today's length; 1 today's zones. ``to_dict`` leaves it out at 1.
    hall_length: float = DEFAULT_HALL_LENGTH

    # Named special regions to add (water pools, lava, etc.)
    regions: List[str] = field(default_factory=list)   # kinds from VALID_REGION_KINDS

    # Lock-and-key gating: number of locked gates (0 = open dungeon).
    locks: int = 0

    # Content / semantic layer (dungeon theme). All optional — a terse prompt
    # or sparse plan still yields a valid zone (the generator falls back to a
    # deterministic default archetype).
    dungeon_theme: str = ""          # archetype, from VALID_DUNGEON_THEMES
    dungeon_race: str = ""           # inhabiting race, from VALID_DUNGEON_RACES
    elemental_tint: str = ""         # from VALID_ELEMENTAL_TINTS ("" = default)

    # Layout engine (dungeon / outdoor_dungeon only; other types ignore it).
    # "" means "not chosen": ``validate()`` resolves it to ``DEFAULT_LAYOUT``
    # (graph) on a dungeon / outdoor dungeon and to ``classic`` elsewhere.
    # ``rule_set`` "" takes the set from the dungeon theme (themes.toml); a
    # base set name picks that set (the theme's layers still apply if they fit).
    layout: str = ""                 # "" or one of VALID_LAYOUTS
    rule_set: str = ""               # "" or one of available_rule_sets()
    # A grown dungeon's wall style (rules/walls/); "" takes the theme's.
    walls: str = ""                  # "" or one of available_wall_styles()
    # How much stands in a grown dungeon's rooms (rules/rooms/layouts.toml).
    features: str = "normal"         # one of VALID_FEATURES
    # Leans on each room's draw (rules/rooms/scales.toml): None is the rules alone, 0-10 multiplies in.
    finish: Optional[int] = None
    structure: Optional[int] = None
    clutter: Optional[int] = None
    overlay: str = ""                # "" or one of available_overlays()
    # Sites (wilderness / outdoor dungeon only; other types ignore them).
    sites: str = DEFAULT_SITES       # one of VALID_SITES
    inhabitant: str = ""             # "" (the biome's mix) or one of available_inhabitants()
    # Props in rooms (dungeon, city, outdoor dungeon; wilderness ignores them).
    decor: str = ""                  # "" (the default, normal) or one of VALID_DECOR
    decor_seed: Optional[int] = None # None: the zone's seed salts them; else rerolls the Props alone
    # Decor layers on top of the theme's (rules/decor/themes.toml). Only Decor reads them: they
    # never reach the Zone_Spec's fields (generators.builder.with_decor_layers carries them),
    # and ``to_dict`` leaves them out while empty.
    decor_layers: Tuple[str, ...] = ()
    # The Attach stage's seed: None is the zone's seed; else rerolls the rooms and Sites alone.
    rooms_seed: Optional[int] = None
    # Rooms that keep their own decor seed (room id -> seed); their bare decision is still the
    # zone's. ``to_dict`` leaves it out while empty.
    room_decor_seeds: Dict[str, int] = field(default_factory=lambda: RoomSeeds())

    # Districts (districts spec Req 4.1; dungeons only, A2). Off by default (A1). The
    # proposals are ``{"purpose": name}`` in District id order ("" leaves one to the
    # relationship); two or more naming one Purpose and nothing else pin it (23.10).
    # ``to_dict`` leaves all three out while they are at their defaults, so a plan
    # without them is the dict it always was, and a saved one loads with them off.
    districts: bool = False
    district_plan: List[Dict[str, str]] = field(default_factory=list)
    district_relationship: str = ""          # "" (sequential) or VALID_DISTRICT_RELATIONSHIPS

    # Free-text mood/notes, passed through for texture descriptions / future use
    mood: str = ""

    # The original prompt, retained for provenance
    prompt: str = ""

    def validate(self, warnings: Optional[List[str]] = None) -> "ZonePlan":
        """Clamp/normalise fields to valid ranges. Returns self.

        ``warnings`` is an optional accumulator the Server/CLI pass so the
        shared ``cls(**clean).validate(warnings)`` path can record normalisation
        notes (e.g. a substituted zone type) for the response/Sidecar. It is
        kept optional so the many bare ``.validate()`` callers (planners,
        ``plan_to_spec``) are unaffected; normalisation itself is identical
        whether or not an accumulator is supplied.
        """
        # Normalise + legacy-map the zone type: an undefined value (or the
        # legacy "outdoor") falls back through canonical_zone_type to the
        # default (Req 11.2).
        self.zone_type = canonical_zone_type(self.zone_type) or DEFAULT_ZONE_TYPE
        self.room_count = max(1, min(30, int(self.room_count)))
        if self.size not in ("small", "medium", "large", "huge"):
            self.size = "medium"
        if self.verticality not in ("flat", "moderate", "dramatic"):
            self.verticality = "moderate"
        self.winding = winding_value(self.winding)
        self.hall_length = hall_length_value(self.hall_length)
        self.regions = [r for r in self.regions if r in VALID_REGION_KINDS]
        self.locks = max(0, min(5, int(self.locks)))
        if self.dungeon_theme and self.dungeon_theme not in VALID_DUNGEON_THEMES:
            self.dungeon_theme = ""
        if self.dungeon_race and self.dungeon_race not in VALID_DUNGEON_RACES:
            self.dungeon_race = ""
        if self.elemental_tint and self.elemental_tint not in VALID_ELEMENTAL_TINTS:
            self.elemental_tint = ""
        # The layout fields are an error when unknown, not a silent fallback
        # (graph-layout design "Selection and the sidecar"): a wrong engine or
        # rule set would otherwise build a different zone than asked for.
        # An unchosen layout takes the new-request default on the zone types
        # that have an engine; a saved pre-step-6 plan never reaches here
        # unchosen (``from_saved`` fills in classic first).
        self.layout = str(self.layout or "").strip().lower()
        if not self.layout:
            self.layout = (DEFAULT_LAYOUT if self.zone_type in LAYOUT_ZONE_TYPES
                           else LEGACY_LAYOUT)
        if self.layout not in VALID_LAYOUTS:
            raise ValueError(f"layout {self.layout!r} is not one of: "
                             f"{', '.join(VALID_LAYOUTS)}")
        self.rule_set = str(self.rule_set or "").strip()
        if self.rule_set:
            sets = available_rule_sets()
            if self.rule_set not in sets:
                raise ValueError(f"rule_set {self.rule_set!r} is not one of: "
                                 f"{', '.join(sets)} (or \"\" for the theme's set)")
        self.features = str(self.features or "normal").strip().lower()
        if self.features not in VALID_FEATURES:
            raise ValueError(f"features {self.features!r} is not one of: {', '.join(VALID_FEATURES)}")
        self.walls = str(self.walls or "").strip().lower()
        if self.walls:
            styles = available_wall_styles()
            if self.walls not in styles:
                raise ValueError(f"walls {self.walls!r} is not one of: "
                                 f"{', '.join(styles)} (or \"\" for the theme's style)")
        for name in SCALE_CONTROLS:
            setattr(self, name, scale_control(name, getattr(self, name)))
        self.overlay = str(self.overlay or "").strip().lower()
        if self.overlay and self.overlay not in available_overlays():
            raise ValueError(f"overlay {self.overlay!r} is not one of: "
                             f"{', '.join(available_overlays())} (or \"\" for the rules alone)")
        self.sites = str(self.sites or DEFAULT_SITES).strip().lower()
        if self.sites not in VALID_SITES:
            raise ValueError(f"sites {self.sites!r} is not one of: {', '.join(VALID_SITES)}")
        self.inhabitant = str(self.inhabitant or "").strip().lower()
        if self.inhabitant and self.inhabitant not in available_inhabitants():
            raise ValueError(f"inhabitant {self.inhabitant!r} is not one of: "
                             f"{', '.join(available_inhabitants())} (or \"\" for the biome's mix)")
        self.decor = str(self.decor or "").strip().lower()
        if self.decor and self.decor not in VALID_DECOR:
            raise ValueError(f"decor {self.decor!r} is not one of: {', '.join(VALID_DECOR)} "
                             f"(or \"\" for the default, {DEFAULT_DECOR})")
        self.decor_seed = decor_seed(self.decor_seed)
        self.decor_layers = decor_layers(self.decor_layers)
        self.rooms_seed = rooms_seed(self.rooms_seed)
        self.room_decor_seeds = room_decor_seeds(self.room_decor_seeds)
        self.districts = district_switch(self.districts)
        self.district_plan = district_plan(self.district_plan, warnings)
        self.district_relationship = district_relationship(self.district_relationship, warnings)
        return self

    def pinned_purpose(self) -> str:
        """The Purpose this plan pins on every District (umbrella 23.10), or "": two or more
        proposals, all naming the same Purpose, none left open."""
        names = [p["purpose"] for p in self.district_plan]
        if len(names) >= 2 and names[0] and all(n == names[0] for n in names):
            return names[0]
        return ""

    def to_dict(self) -> Dict[str, Any]:
        # The emitted dict carries ``zone_type`` and never a legacy ``theme``
        # key (Req 11.1). ``decor_layers`` only when some are named, so a plan
        # naming none is the dict it always was.
        out = asdict(self)
        if out.get("winding") == DEFAULT_WINDING:
            out.pop("winding", None)
        if out.get("hall_length") == DEFAULT_HALL_LENGTH:
            out.pop("hall_length", None)
        layers = out.pop("decor_layers", ())
        if layers:
            out["decor_layers"] = list(layers)
        seeds = out.pop("room_decor_seeds", None)
        if seeds:
            out["room_decor_seeds"] = dict(seeds)
        if not (self.districts or self.district_plan or self.district_relationship):
            for key in ("districts", "district_plan", "district_relationship"):
                out.pop(key, None)
        return out

    @classmethod
    def from_dict(cls, d: Mapping[str, Any],
                  warnings: Optional[List[str]] = None) -> "ZonePlan":
        # Legacy LOAD boundary (Req 11.1 / Property 12): a stored plan may still
        # carry the legacy ``theme`` key and/or the ``outdoor`` value. Both are
        # accepted here and mapped forward; ``zone_type`` wins when both keys
        # are present. Every other unknown key (``target_shortname`` and
        # friends, Req 8.1) is dropped.
        #
        # The dict is read as a NEW request (controls, the LLM planner's JSON):
        # a missing ``layout`` takes the new-request default. Rebuilding a plan
        # saved before step 6 goes through ``from_saved``, which reads a
        # missing ``layout`` as classic (graph-layout task 21).
        allowed = {f for f in cls.__dataclass_fields__}
        clean = {k: v for k, v in d.items() if k in allowed and k != "theme"}
        clean.pop("zone_type", None)
        clean["zone_type"] = canonical_zone_type(read_zone_type(d)) or DEFAULT_ZONE_TYPE
        return cls(**clean).validate(warnings)

    @classmethod
    def from_saved(cls, d: Mapping[str, Any],
                   warnings: Optional[List[str]] = None) -> "ZonePlan":
        """A plan dict saved by an earlier build (a response's or sidecar's
        ``plan``) -> ZonePlan, for rebuilding it.

        ``from_dict`` treats its dict as a NEW request, so a missing ``layout``
        takes the current default (graph). A plan saved before graph-layout
        step 6 has no ``layout`` key at all, and every such plan was built
        with the classic engine (classic was the only one, then the default
        until task 21). This is the load boundary that knows the dict is old,
        so here a missing key means ``LEGACY_LAYOUT`` (classic): the saved
        plan and its seed rebuild the same zone, byte for byte, as before the
        default changed. A saved plan that names its layout keeps it.
        """
        merged: Dict[str, Any] = dict(d)
        if not merged.get("layout"):
            merged["layout"] = LEGACY_LAYOUT
        return cls.from_dict(merged, warnings)

    @classmethod
    def from_controls(cls, d: Mapping[str, Any],
                      warnings: Optional[List[str]] = None) -> "ZonePlan":
        """Controls dict -> ZonePlan through the same ``validate()`` as
        ``from_dict`` (Req 1.2, 2.3, 2.4).

        ``from_controls`` is just ``from_dict`` with two extra layers on top, so
        on every key both paths name directly they agree by construction
        (Property 5 / umbrella P12):

        1. **Control aliases** (``CONTROL_ALIASES``): a flat control name maps to
           its plan field (``rooms`` -> ``room_count``, ``theme`` -> ``zone_type``).
           A plan key present in ``d`` WINS over its alias, so if both
           ``room_count`` and ``rooms`` (or ``zone_type`` and ``theme``) appear,
           the plan key is kept and the alias ignored.
        2. **Legacy ``elevation`` translation**: a legacy ``elevation: false``
           WITHOUT a ``verticality`` key means ``verticality = "flat"`` — the
           boolean is translated into the verticality vocabulary. ``verticality``
           present always wins, and ``elevation: true`` leaves verticality at its
           default.

        Content fields (``dungeon_theme``, ``dungeon_race``, ``elemental_tint``,
        …) keep their names and rules — they flow through unchanged and are
        normalised by ``validate()`` exactly as in ``from_dict``. Unknown keys
        (target/topology/district and any other non-plan key) are dropped by the
        shared ``from_dict`` filter, so ``from_controls`` never carries them
        (enforced by the surface guards in task 17.10).
        """
        merged: Dict[str, Any] = dict(d)

        # (1) Control aliases: fold each alias into its plan field unless the
        # plan key is already present (plan key wins), then drop the alias so it
        # doesn't survive as an unknown key.
        for alias, field_name in CONTROL_ALIASES.items():
            if alias in merged:
                if field_name not in merged:
                    merged[field_name] = merged[alias]
                merged.pop(alias, None)

        # (2) Legacy elevation -> verticality: ``elevation: false`` with no
        # explicit ``verticality`` means flat. ``elevation`` itself is still a
        # real plan field, so it stays; only the derived verticality is set.
        if "verticality" not in merged and merged.get("elevation") is False:
            merged["verticality"] = "flat"

        # Funnel into the SAME path as from_dict so the two agree by
        # construction and share one normalisation/validate step.
        return cls.from_dict(merged, warnings)


# JSON schema an LLM is asked to fill (structured output / tool use).
ZONE_PLAN_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "zone_type": {
            "type": "string",
            "enum": VALID_ZONE_TYPES,
            "description": "The zone's environment type.",
        },
        "room_count": {
            "type": "integer",
            "minimum": 1,
            "maximum": 30,
            "description": "How many distinct rooms/chambers/clearings.",
        },
        "size": {
            "type": "string",
            "enum": ["small", "medium", "large", "huge"],
            "description": "Overall footprint of the zone.",
        },
        "elevation": {
            "type": "boolean",
            "description": "Whether the zone has multiple vertical levels.",
        },
        "verticality": {
            "type": "string",
            "enum": ["flat", "moderate", "dramatic"],
            "description": "How much the floor height varies between rooms.",
        },
        "regions": {
            "type": "array",
            "items": {"type": "string", "enum": VALID_REGION_KINDS},
            "description": "Special region volumes to include (e.g. water pools, lava).",
        },
        "locks": {
            "type": "integer",
            "minimum": 0,
            "maximum": 5,
            "description": "Number of locked gates for a keyed dungeon (0 = open/explorable).",
        },
        "mood": {
            "type": "string",
            "description": "Short mood/atmosphere note, e.g. 'dark and damp'.",
        },
        "dungeon_theme": {
            "type": "string",
            "enum": VALID_DUNGEON_THEMES,
            "description": "Semantic archetype for a dungeon: what kind of place "
                           "it is (a fortress, a temple, a flooded ruin, a mad "
                           "wizard's lair, a tomb, a forge, an ice keep, …).",
        },
        "dungeon_race": {
            "type": "string",
            "enum": VALID_DUNGEON_RACES,
            "description": "The race that built/inhabits the place. Sizes rooms "
                           "and corridors to its body height (e.g. 'giant' or "
                           "'dragon' = vast halls, "
                           "'froglok'/'goblin' = smaller).",
        },
        "elemental_tint": {
            "type": "string",
            "enum": VALID_ELEMENTAL_TINTS,
            "description": "Optional elemental overlay: lava, ice, or water "
                           "regions + matching light mood.",
        },
        "sites": {
            "type": "string",
            "enum": VALID_SITES,
            "description": "Wilderness / outdoor dungeon: how many Sites (camps, "
                           "huts, farmsteads, towers, shrines, ruins) stand in "
                           "the landscape.",
        },
        "inhabitant": {
            "type": "string",
            "enum": available_inhabitants(),
            "description": "Wilderness / outdoor dungeon: who builds every Site; "
                           "omit for the biome's mix.",
        },
        "decor": {
            "type": "string",
            "enum": VALID_DECOR,
            "description": "How much furniture, lights and clutter stand in the "
                           "rooms and at the Sites (bare rooms: "
                           "sparse; cluttered or richly furnished: dense); omit "
                           "for normal.",
        },
        "districts": {
            "type": "boolean",
            "description": "Dungeon only: split the dungeon into 2-3 contrasting "
                           "areas (Districts) joined by one corridor each. Set it "
                           "when the description names contrasting areas (the "
                           "living and the dead, two factions, upper and lower "
                           "halls, a temple fallen to the dead); omit otherwise.",
        },
        "district_plan": {
            "type": "array",
            "maxItems": MAX_DISTRICT_PROPOSALS,
            "items": {
                "type": "object",
                "properties": {"purpose": {"type": "string",
                                           "enum": VALID_DUNGEON_THEMES + [""]}},
                "required": ["purpose"],
            },
            "description": "With districts: one entry per named area (2-3), the "
                           "entrance's area first, each the dungeon_theme the "
                           "words name for that area, or an empty string when "
                           "they name none. The same purpose in every entry "
                           "gives every area that purpose.",
        },
        "district_relationship": {
            "type": "string",
            "enum": VALID_DISTRICT_RELATIONSHIPS,
            "description": "With districts: sequential (one area leads into the "
                           "next), factional (opposed sides), or "
                           "abandoned_vs_active (the areas past the entrance's "
                           "have fallen, been overrun or abandoned).",
        },
    },
    "required": ["zone_type", "room_count", "size"],
}
