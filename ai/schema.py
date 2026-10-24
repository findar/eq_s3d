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

from dataclasses import dataclass, field, asdict, InitVar
from typing import List, Optional, Dict, Any

from generators.zone_types import (
    DEFINED_ZONE_TYPES, DEFAULT_ZONE_TYPE, canonical_zone_type, read_zone_type,
)

# The canonical zone-type vocabulary, sourced from the single source of truth
# (generators/zone_types.py). New code uses ``zone_type`` / ``wilderness``; the
# legacy ``theme`` key and the ``outdoor`` value are accepted on load and mapped
# forward via ``canonical_zone_type`` (umbrella decision 19; Req 11.1, 11.2).
VALID_ZONE_TYPES = list(DEFINED_ZONE_TYPES)

# Legacy alias of ``VALID_ZONE_TYPES`` for pre-rename importers. Task 10.9
# retargets the test-side references and drops this alias.
VALID_THEMES = VALID_ZONE_TYPES

VALID_REGION_KINDS = ["water", "lava", "ice", "pvp", "zoneline", "generic"]

# Content / semantic layer (dungeon theme). Archetypes mirror
# generators.semantics.ARCHETYPES; races mirror generators.semantics.RACE_SCALE.
VALID_DUNGEON_THEMES = [
    "fortress", "war_city", "warren", "temple", "tomb", "wizard_lair",
    "corrupted_sanctum", "mine_delve", "sunken_ruin", "lava_forge", "ice_keep",
]
VALID_DUNGEON_RACES = [
    "goblin", "froglok", "kobold", "lizardman", "gnoll", "sarnak", "troll",
    "ogre", "giant",
]
VALID_ELEMENTAL_TINTS = ["lava", "ice", "water"]


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

    # Free-text mood/notes, passed through for texture descriptions / future use
    mood: str = ""

    # The original prompt, retained for provenance
    prompt: str = ""

    # Legacy constructor alias: pre-rename callers passed ``theme=``. It is an
    # InitVar (accepted as a kwarg, never stored and never emitted by
    # ``to_dict()``) that folds forward into ``zone_type`` when given. New code
    # should pass ``zone_type=`` directly. ``from_dict`` handles the legacy
    # ``theme`` JSON key separately via ``read_zone_type``.
    theme: InitVar[Optional[str]] = None

    def __post_init__(self, theme: Optional[str]) -> None:
        # A legacy ``theme=`` kwarg wins and is mapped forward immediately
        # (``outdoor`` -> ``wilderness``), so even an unvalidated plan carries a
        # current value. An unknown value is left as-is for ``validate()`` to
        # fold to the default.
        if theme is not None:
            self.zone_type = canonical_zone_type(theme) or theme

    # ``theme`` is a live read/write alias for ``zone_type`` (pre-rename
    # attribute). Implemented via __getattr__/__setattr__ (not a property, which
    # would collide with the InitVar name): reads return the current
    # ``zone_type`` and writes forward to it, so ``plan.theme`` always tracks
    # ``zone_type`` — including after ``validate()``. ``theme`` is not a
    # dataclass field, so ``to_dict()`` never emits it (Req 11.1). The leftover
    # class-level InitVar sentinel is deleted just after the class body so
    # instance ``.theme`` reads fall through to __getattr__.
    def __getattr__(self, name: str):
        if name == "theme":
            return self.__dict__["zone_type"]
        raise AttributeError(name)

    def __setattr__(self, name: str, value) -> None:
        if name == "theme":
            name = "zone_type"
        super().__setattr__(name, value)

    def validate(self) -> "ZonePlan":
        """Clamp/normalise fields to valid ranges. Returns self."""
        # Normalise + legacy-map the zone type: an undefined value (or the
        # legacy "outdoor") falls back through canonical_zone_type to the
        # default (Req 11.2).
        self.zone_type = canonical_zone_type(self.zone_type) or DEFAULT_ZONE_TYPE
        self.room_count = max(1, min(30, int(self.room_count)))
        if self.size not in ("small", "medium", "large", "huge"):
            self.size = "medium"
        if self.verticality not in ("flat", "moderate", "dramatic"):
            self.verticality = "moderate"
        self.regions = [r for r in self.regions if r in VALID_REGION_KINDS]
        self.locks = max(0, min(5, int(self.locks)))
        if self.dungeon_theme and self.dungeon_theme not in VALID_DUNGEON_THEMES:
            self.dungeon_theme = ""
        if self.dungeon_race and self.dungeon_race not in VALID_DUNGEON_RACES:
            self.dungeon_race = ""
        if self.elemental_tint and self.elemental_tint not in VALID_ELEMENTAL_TINTS:
            self.elemental_tint = ""
        return self

    def to_dict(self) -> Dict[str, Any]:
        # ``asdict`` already omits the ``theme`` InitVar (InitVars are not
        # stored fields), so the emitted dict carries ``zone_type`` and never a
        # legacy ``theme`` key (Req 11.1).
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ZonePlan":
        allowed = {f for f in cls.__dataclass_fields__}
        clean = {k: v for k, v in d.items() if k in allowed and k != "theme"}
        # Read the zone type preferring ``zone_type``, then the legacy ``theme``
        # key, then the default; normalise/legacy-map it (Req 11.2). A JSON
        # ``theme`` key is consumed here, never forwarded as the constructor
        # InitVar, so it can't shadow ``zone_type``.
        clean.pop("zone_type", None)
        zt = canonical_zone_type(read_zone_type(d)) or DEFAULT_ZONE_TYPE
        return cls(zone_type=zt, **clean).validate()


# Drop the leftover class-level ``theme`` InitVar sentinel (its default ``None``
# would otherwise shadow the __getattr__ alias on instance reads). The InitVar
# was already consumed by @dataclass to build __init__/__post_init__, so the
# constructor still accepts ``theme=``.
del ZonePlan.theme


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
            "description": "The race that built/inhabits the place. Scales room "
                           "and corridor size (e.g. 'giant' = huge halls, "
                           "'froglok'/'goblin' = smaller).",
        },
        "elemental_tint": {
            "type": "string",
            "enum": VALID_ELEMENTAL_TINTS,
            "description": "Optional elemental overlay: lava, ice, or water "
                           "regions + matching light mood.",
        },
    },
    "required": ["zone_type", "room_count", "size"],
}
