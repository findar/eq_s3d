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
from typing import List, Optional, Dict, Any

VALID_THEMES = ["dungeon", "outdoor", "cave", "city"]
VALID_REGION_KINDS = ["water", "lava", "ice", "pvp", "zoneline", "generic"]


@dataclass
class ZonePlan:
    """
    A high-level zone plan. Every field has a sane default so a partial plan
    (from a terse prompt or a sparse LLM response) still yields a valid zone.
    """
    name: str = "zone"
    theme: str = "dungeon"            # one of VALID_THEMES
    room_count: int = 5              # 1..30
    size: str = "medium"             # small | medium | large | huge
    elevation: bool = True           # multi-level layout
    verticality: str = "moderate"    # flat | moderate | dramatic

    # Named special regions to add (water pools, lava, etc.)
    regions: List[str] = field(default_factory=list)   # kinds from VALID_REGION_KINDS

    # Lock-and-key gating: number of locked gates (0 = open dungeon).
    locks: int = 0

    # Free-text mood/notes, passed through for texture descriptions / future use
    mood: str = ""

    # The original prompt, retained for provenance
    prompt: str = ""

    def validate(self) -> "ZonePlan":
        """Clamp/normalise fields to valid ranges. Returns self."""
        if self.theme not in VALID_THEMES:
            self.theme = "dungeon"
        self.room_count = max(1, min(30, int(self.room_count)))
        if self.size not in ("small", "medium", "large", "huge"):
            self.size = "medium"
        if self.verticality not in ("flat", "moderate", "dramatic"):
            self.verticality = "moderate"
        self.regions = [r for r in self.regions if r in VALID_REGION_KINDS]
        self.locks = max(0, min(5, int(self.locks)))
        return self

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ZonePlan":
        allowed = {f for f in cls.__dataclass_fields__}
        clean = {k: v for k, v in d.items() if k in allowed}
        return cls(**clean).validate()


# JSON schema an LLM is asked to fill (structured output / tool use).
ZONE_PLAN_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "theme": {
            "type": "string",
            "enum": VALID_THEMES,
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
    },
    "required": ["theme", "room_count", "size"],
}
