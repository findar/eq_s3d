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

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Mapping

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
        # The emitted dict carries ``zone_type`` and never a legacy ``theme``
        # key (Req 11.1).
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any],
                  warnings: Optional[List[str]] = None) -> "ZonePlan":
        # Legacy LOAD boundary (Req 11.1 / Property 12): a stored plan may still
        # carry the legacy ``theme`` key and/or the ``outdoor`` value. Both are
        # accepted here and mapped forward; ``zone_type`` wins when both keys
        # are present. Every other unknown key (``target_shortname`` and
        # friends, Req 8.1) is dropped.
        allowed = {f for f in cls.__dataclass_fields__}
        clean = {k: v for k, v in d.items() if k in allowed and k != "theme"}
        clean.pop("zone_type", None)
        clean["zone_type"] = canonical_zone_type(read_zone_type(d)) or DEFAULT_ZONE_TYPE
        return cls(**clean).validate(warnings)

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
