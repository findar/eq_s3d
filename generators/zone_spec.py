"""
generators/zone_spec.py
-----------------------
The ZoneSpec: a structured, serialisable description of a zone that sits
between the AI planner (Phase 3) and the binary generators (Phase 2).

The AI produces a ZoneSpec from a prompt; the generators turn it into TER/ZON
binary. The spec is also hand-editable JSON, so a user can tweak it directly.

Coordinate system: EverQuest units. 1 unit ≈ 1 foot. A player is ~6 units tall.
EQ uses a right-handed system where Z is up.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

from .zone_types import canonical_zone_type, read_zone_type, DEFAULT_ZONE_TYPE

# ---------------------------------------------------------------------------
# Spec components
# ---------------------------------------------------------------------------

@dataclass
class RoomSpec:
    """
    A rectangular room (box) in the zone.

    Position is the room's centre on the XY plane; floor_z is the floor height.
    The room extends `width`/`depth` horizontally and `height` vertically.
    """
    id: str
    center_x: float
    center_y: float
    floor_z: float = 0.0
    width: float = 200.0        # X extent
    depth: float = 200.0        # Y extent
    height: float = 60.0        # Z extent (floor to ceiling)

    # Material names (keys into ZoneSpec.materials)
    floor_material: str = "floor"
    wall_material: str = "wall"
    ceiling_material: str = "ceiling"

    # Which walls to omit (for openings into corridors): any of N/S/E/W
    open_walls: List[str] = field(default_factory=list)

    # Pacing (derived from the room graph):
    #   role        — entrance | hub | deadend | climax | standard
    #   graph_depth — hops from the entrance (0 = entrance). Progression axis.
    # NOTE: named graph_depth to avoid colliding with `depth` (the Y-extent).
    role: str = "standard"
    graph_depth: int = 0

    # Content / semantic layer (assigned on top of the pacing graph).
    #   semantic_type    — what the room *is* (e.g. "barracks", "flooded_crypt").
    #   room_theme       — the zone archetype label this room belongs to (e.g.
    #                       "fortress"); same across every room of a district.
    #   district         — which district this room belongs to (0 = the only
    #                       district for single-theme zones). Set by Step 2.
    # Suggestion fields (DATA / NOTES ONLY — never placed as geometry):
    #   prop_hints       — set-dressing suggestions ("submerged altar", "braziers").
    #   encounter_intent — spawn/encounter note ("undead ambush, medium").
    #   boss             — whether this room is a suggested boss/climax chamber.
    semantic_type: str = ""
    room_theme: str = ""
    district: int = 0
    prop_hints: List[str] = field(default_factory=list)
    encounter_intent: str = ""
    boss: bool = False

    @property
    def bounds(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        hw, hd = self.width / 2, self.depth / 2
        return (
            (self.center_x - hw, self.center_y - hd, self.floor_z),
            (self.center_x + hw, self.center_y + hd, self.floor_z + self.height),
        )


@dataclass
class CorridorSpec:
    """
    A straight corridor connecting two rooms (or arbitrary points).

    Defined by two endpoints on the XY plane plus a width and height.
    The corridor is axis-aligned: it runs along whichever axis (X or Y) has
    the larger horizontal delta between the endpoints.

    Elevation: if from_z != to_z the corridor ramps (slopes) between the two
    heights. The player walks up/down the slope. Set `steps` > 0 to build a
    stepped staircase instead of a smooth ramp.
    """
    id: str
    from_x: float
    from_y: float
    to_x: float
    to_y: float
    from_z: float = 0.0         # floor height at the `from` end
    to_z: float = 0.0           # floor height at the `to` end
    width: float = 50.0
    height: float = 50.0        # clearance from floor to ceiling
    steps: int = 0              # 0 = smooth ramp; >0 = number of stair steps

    floor_material: str = "floor"
    wall_material: str = "wall"
    ceiling_material: str = "ceiling"

    # Which rooms this corridor connects (room ids). Optional for hand-authored
    # specs; the layout sets them so backends know the exact endpoints rather
    # than guessing from wall-point proximity (the cave backend needs this to
    # anchor tunnels to the right two chambers).
    from_room: str = ""
    to_room: str = ""

    # Back-compat: `floor_z` as an alias that sets both ends flat
    @property
    def floor_z(self) -> float:
        return self.from_z

    @floor_z.setter
    def floor_z(self, value: float) -> None:
        self.from_z = value
        self.to_z = value


@dataclass
class LightSpec:
    """A point light."""
    id: str
    x: float
    y: float
    z: float
    r: float = 1.0
    g: float = 0.6
    b: float = 0.2
    radius: float = 40.0


@dataclass
class RegionSpec:
    """
    A region volume (water, lava, zoneline, etc).

    *kind* is one of: water, lava, pvp, zoneline, ice, generic.
    """
    id: str
    kind: str                   # water | lava | pvp | zoneline | ice | generic
    center_x: float
    center_y: float
    center_z: float
    extent_x: float = 30.0      # half-widths
    extent_y: float = 30.0
    extent_z: float = 10.0


@dataclass
class GateSpec:
    """
    A lock-and-key gate: a locked door on a corridor, and the key that opens
    it placed in a room reachable before the lock. Guarantees solvable
    progression (the key is always obtainable before the door that needs it).

    This is carried as data for the EQEmu export (a door object + a key item);
    the geometry backend can also place a visible door MOD at the lock point.
    """
    id: str
    corridor_id: str            # which corridor this door sits on
    lock_x: float               # world position of the locked door
    lock_y: float
    lock_z: float
    key_room_id: str            # room where the key is found
    key_x: float                # world position of the key placement
    key_y: float
    key_z: float
    tier: int = 0               # nesting depth (0 = outermost lock)


@dataclass
class MaterialSpec:
    """
    A material definition. The *texture* is a DDS filename that will be
    generated (Phase 3) or supplied as a placeholder.
    """
    name: str                   # logical name referenced by rooms/corridors
    texture: str                # DDS filename, e.g. "stone_wall.dds"
    shader: str = "Opaque_MaxCB1.fx"
    description: str = ""        # AI prompt hint for texture generation
    # Placeholder solid colour (RGBA 0-255) used until a real texture exists
    color: Tuple[int, int, int] = (128, 128, 128)


# ---------------------------------------------------------------------------
# Top-level spec
# ---------------------------------------------------------------------------

@dataclass
class ZoneSpec:
    """
    Complete description of a zone to generate.

    Usage::

        spec = ZoneSpec(name="myrealm", zone_type="dungeon")
        spec.materials["wall"] = MaterialSpec("wall", "stone_wall.dds", color=(90,85,80))
        spec.rooms.append(RoomSpec("entry", 0, 0, width=300, depth=300, height=80))
        spec.save("myrealm.json")
    """
    name: str
    zone_type: str = "dungeon"
    style_profile: str = "dungeon"

    # The random seed this spec was generated from. Threaded through so the
    # geometry backends (cave/terrain) seed from the *user seed* rather than a
    # hash of the (timestamped, always-unique) name — otherwise pinning a seed
    # couldn't reproduce an organic/outdoor zone. None = hand-authored spec with
    # no recorded seed; backends then fall back to a stable hash of the name.
    seed: Optional[int] = None

    # Content / semantic layer (dungeon theme). A theme is archetype × race ×
    # elemental tint; these are advisory metadata realised by the pipeline.
    #   dungeon_theme  — archetype label ("fortress", "temple", "sunken_ruin"…).
    #   dungeon_race   — inhabiting race, a global scale multiplier ("giant"…).
    #   elemental_tint — optional overlay ("lava" | "ice" | "water" | "").
    dungeon_theme: str = ""
    dungeon_race: str = ""
    elemental_tint: str = ""

    ambient_light: Tuple[float, float, float] = (0.1, 0.1, 0.12)
    safe_point: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    materials: Dict[str, MaterialSpec] = field(default_factory=dict)
    rooms: List[RoomSpec]       = field(default_factory=list)
    corridors: List[CorridorSpec] = field(default_factory=list)
    lights: List[LightSpec]     = field(default_factory=list)
    regions: List[RegionSpec]   = field(default_factory=list)
    gates: List["GateSpec"]     = field(default_factory=list)

    # Open-world wilderness payload (wilderness spec task 2). ``None`` for every
    # room-graph zone. When set it carries the inputs the wilderness pipeline
    # rebuilds the landscape from: ``{"biome": str, "edges": {side: type}}``.
    # Omitted from ``to_dict()`` when unset so dungeon/city output is unchanged.
    wilderness: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "zone_type": self.zone_type,
            "style_profile": self.style_profile,
            "seed": self.seed,
            "dungeon_theme": self.dungeon_theme,
            "dungeon_race": self.dungeon_race,
            "elemental_tint": self.elemental_tint,
            "ambient_light": list(self.ambient_light),
            "safe_point": list(self.safe_point),
            "materials": {k: asdict(v) for k, v in self.materials.items()},
            "rooms": [asdict(r) for r in self.rooms],
            "corridors": [asdict(c) for c in self.corridors],
            "lights": [asdict(l) for l in self.lights],
            "regions": [asdict(r) for r in self.regions],
            "gates": [asdict(g) for g in self.gates],
            **({"wilderness": self.wilderness} if self.wilderness is not None else {}),
        }

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2))
        return p

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ZoneSpec":
        # Legacy LOAD boundary (Req 11.1, 11.2 / Property 12): prefer
        # ``zone_type``, accept the legacy ``theme`` key, map the legacy
        # ``outdoor`` value to ``wilderness`` and any undefined value (including
        # the removed-in-M0 "cave" theme) to ``dungeon``.
        zone_type = canonical_zone_type(read_zone_type(d)) or DEFAULT_ZONE_TYPE
        spec = cls(
            name=d["name"],
            zone_type=zone_type,
            style_profile=d.get("style_profile", "dungeon"),
            seed=d.get("seed"),
            dungeon_theme=d.get("dungeon_theme", ""),
            dungeon_race=d.get("dungeon_race", ""),
            elemental_tint=d.get("elemental_tint", ""),
            ambient_light=tuple(d.get("ambient_light", (0.1, 0.1, 0.12))),
            safe_point=tuple(d.get("safe_point", (0.0, 0.0, 0.0))),
            wilderness=d.get("wilderness"),
        )
        for k, mv in d.get("materials", {}).items():
            mv = dict(mv)
            if "color" in mv:
                mv["color"] = tuple(mv["color"])
            spec.materials[k] = MaterialSpec(**mv)
        for r in d.get("rooms", []):
            spec.rooms.append(RoomSpec(**r))
        for c in d.get("corridors", []):
            spec.corridors.append(CorridorSpec(**c))
        for l in d.get("lights", []):
            spec.lights.append(LightSpec(**l))
        for rg in d.get("regions", []):
            spec.regions.append(RegionSpec(**rg))
        for g in d.get("gates", []):
            spec.gates.append(GateSpec(**g))
        return spec

    @classmethod
    def load(cls, path: str | Path) -> "ZoneSpec":
        return cls.from_dict(json.loads(Path(path).read_text()))

    # ------------------------------------------------------------------
    # Convenience builders
    # ------------------------------------------------------------------

    def add_material(self, name: str, texture: str, shader: str = "Opaque_MaxCB1.fx",
                     color: Tuple[int, int, int] = (128, 128, 128),
                     description: str = "") -> MaterialSpec:
        m = MaterialSpec(name=name, texture=texture, shader=shader, color=color,
                         description=description)
        self.materials[name] = m
        return m

    def __repr__(self) -> str:
        return (
            f"ZoneSpec({self.name!r}, zone_type={self.zone_type!r}, "
            f"rooms={len(self.rooms)}, corridors={len(self.corridors)}, "
            f"lights={len(self.lights)}, regions={len(self.regions)}, "
            f"gates={len(self.gates)})"
        )
