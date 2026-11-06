"""What stands inside a room (roadmap step 9, design "Features").

A Feature is a solid part of the room's structure, built into its mesh: a pillar, a plinth,
a boulder or a raised dais. It stands on an unbroken floor, so nothing about the room
underneath changes. A POI is a named point in a room with a purpose: advisory, sidecar only,
never touching geometry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

PILLAR, PLINTH, BOULDER, DAIS = "pillar", "plinth", "boulder", "dais"
FEATURE_KINDS: Tuple[str, ...] = (PILLAR, PLINTH, BOULDER, DAIS)


@dataclass
class Feature:
    kind: str
    plan: List[Tuple[float, float]]     # its footprint, counter-clockwise from above
    height: float = 0.0                 # over the room's floor; 0 reaches the ceiling
    steps_side: str = ""                # a dais: which side (N/S/E/W) its way up is on

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Feature":
        return cls(kind=d["kind"], plan=[tuple(p) for p in d["plan"]], height=d.get("height", 0.0),
                   steps_side=d.get("steps_side", ""))


@dataclass
class POI:
    purpose: str                        # boss, treasure, altar, guard, ambush, view
    x: float
    y: float
    z: float
    name: str = ""
    feature: Optional[int] = None       # index into the room's features, if it stands on one

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "POI":
        return cls(purpose=d["purpose"], x=d["x"], y=d["y"], z=d["z"], name=d.get("name", ""),
                   feature=d.get("feature"))

