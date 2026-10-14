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
    The corridor is axis-aligned-ish; it is built as a box between the points.
    """
    id: str
    from_x: float
    from_y: float
    to_x: float
    to_y: float
    floor_z: float = 0.0
    width: float = 50.0
    height: float = 50.0

    floor_material: str = "floor"
    wall_material: str = "wall"
    ceiling_material: str = "ceiling"


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

        spec = ZoneSpec(name="myrealm", theme="dungeon")
        spec.materials["wall"] = MaterialSpec("wall", "stone_wall.dds", color=(90,85,80))
        spec.rooms.append(RoomSpec("entry", 0, 0, width=300, depth=300, height=80))
        spec.save("myrealm.json")
    """
    name: str
    theme: str = "dungeon"
    style_profile: str = "dungeon"

    ambient_light: Tuple[float, float, float] = (0.1, 0.1, 0.12)
    safe_point: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    materials: Dict[str, MaterialSpec] = field(default_factory=dict)
    rooms: List[RoomSpec]       = field(default_factory=list)
    corridors: List[CorridorSpec] = field(default_factory=list)
    lights: List[LightSpec]     = field(default_factory=list)
    regions: List[RegionSpec]   = field(default_factory=list)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "theme": self.theme,
            "style_profile": self.style_profile,
            "ambient_light": list(self.ambient_light),
            "safe_point": list(self.safe_point),
            "materials": {k: asdict(v) for k, v in self.materials.items()},
            "rooms": [asdict(r) for r in self.rooms],
            "corridors": [asdict(c) for c in self.corridors],
            "lights": [asdict(l) for l in self.lights],
            "regions": [asdict(r) for r in self.regions],
        }

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2))
        return p

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ZoneSpec":
        spec = cls(
            name=d["name"],
            theme=d.get("theme", "dungeon"),
            style_profile=d.get("style_profile", "dungeon"),
            ambient_light=tuple(d.get("ambient_light", (0.1, 0.1, 0.12))),
            safe_point=tuple(d.get("safe_point", (0.0, 0.0, 0.0))),
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
            f"ZoneSpec({self.name!r}, theme={self.theme!r}, "
            f"rooms={len(self.rooms)}, corridors={len(self.corridors)}, "
            f"lights={len(self.lights)}, regions={len(self.regions)})"
        )
