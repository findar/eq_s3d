"""
generators/layout.py
--------------------
Procedural zone layout. Generates a ZoneSpec (rooms + corridors + lights)
from high-level parameters, constrained by a style profile.

This is a deterministic, seedable layout generator. In Phase 3 the AI planner
will produce ZoneSpecs directly; this module provides the algorithmic fallback
and the building blocks the AI can call.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import List, Optional, Tuple

from .zone_spec import (
    ZoneSpec, RoomSpec, CorridorSpec, LightSpec, RegionSpec, MaterialSpec,
)

# ---------------------------------------------------------------------------
# Style profile loading
# ---------------------------------------------------------------------------

def load_style_profile(theme: str) -> dict:
    """Load a style profile JSON, or return sensible defaults."""
    candidates = [
        Path(f"styles/{theme}.json"),
        Path(__file__).parent.parent / "styles" / f"{theme}.json",
    ]
    for p in candidates:
        if p.exists():
            return json.loads(p.read_text())
    return {}


def _profile_mean(profile: dict, path: list, default: float) -> float:
    """Safely extract a nested mean value from a profile."""
    node = profile
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    if isinstance(node, dict) and "mean" in node:
        val = node["mean"]
        return val if val and val > 0 else default
    return default


# ---------------------------------------------------------------------------
# Layout generator
# ---------------------------------------------------------------------------

class LayoutGenerator:
    """
    Generates a ZoneSpec procedurally.

    Usage::

        gen = LayoutGenerator(theme="dungeon", seed=42)
        spec = gen.generate("myrealm", room_count=5)
    """

    def __init__(self, theme: str = "dungeon", seed: Optional[int] = None):
        self.theme = theme
        self.profile = load_style_profile(theme)
        self.rng = random.Random(seed)

        # Pull target dimensions from the style profile, with dungeon-sane fallbacks.
        # Note: profile floor_area/width are whole-zone; for a single room we
        # scale down to a reasonable per-room size.
        self.room_min = 150.0
        self.room_max = 400.0
        self.ceiling = max(40.0, min(120.0,
            _profile_mean(self.profile, ["geometry", "ceiling_height"], 60.0) / 20.0))
        self.corridor_width = 50.0
        self.corridor_height = max(40.0, self.ceiling * 0.8)

    # ------------------------------------------------------------------
    # Main generation
    # ------------------------------------------------------------------

    def generate(self,
                 name: str,
                 room_count: int = 5,
                 add_lights: bool = True) -> ZoneSpec:
        spec = ZoneSpec(name=name, theme=self.theme, style_profile=self.theme)

        self._add_default_materials(spec)

        # Lay out rooms along a rough grid walk to keep them connected.
        placed: List[RoomSpec] = []
        cx, cy = 0.0, 0.0
        direction_choices = [(1, 0), (-1, 0), (0, 1), (0, -1)]

        for i in range(room_count):
            w = self.rng.uniform(self.room_min, self.room_max)
            d = self.rng.uniform(self.room_min, self.room_max)
            h = self.ceiling

            room = RoomSpec(
                id=f"room_{i}",
                center_x=cx, center_y=cy, floor_z=0.0,
                width=w, depth=d, height=h,
            )
            placed.append(room)
            spec.rooms.append(room)

            if add_lights:
                self._add_room_lights(spec, room, i)

            # Walk to next room position
            if i < room_count - 1:
                dx, dy = self.rng.choice(direction_choices)
                step = self.rng.uniform(self.room_max, self.room_max * 1.8)
                cx += dx * step
                cy += dy * step

        # Connect consecutive rooms with corridors
        for i in range(len(placed) - 1):
            a, b = placed[i], placed[i + 1]
            spec.corridors.append(CorridorSpec(
                id=f"corr_{i}",
                from_x=a.center_x, from_y=a.center_y,
                to_x=b.center_x, to_y=b.center_y,
                floor_z=0.0,
                width=self.corridor_width,
                height=self.corridor_height,
            ))
            # Open the facing walls so the corridor connects into the rooms
            self._open_facing_walls(a, b)
            self._open_facing_walls(b, a)

        # Safe point in the first room
        if placed:
            r0 = placed[0]
            spec.safe_point = (r0.center_x, r0.center_y, r0.floor_z + 5.0)

        return spec

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _add_default_materials(self, spec: ZoneSpec) -> None:
        theme_palettes = {
            "dungeon": {
                "floor":   ((95, 88, 80),  "worn dungeon flagstone, dark grime in joints"),
                "wall":    ((110, 100, 92),"rough hewn stone blocks, medieval, faint moss"),
                "ceiling": ((60, 56, 52),  "dark rough rock cave ceiling"),
            },
            "outdoor": {
                "floor":   ((90, 110, 70), "grassy dirt ground, scattered pebbles"),
                "wall":    ((120, 115, 100),"weathered rock cliff face"),
                "ceiling": ((120, 140, 170),"overcast sky"),
            },
            "cave": {
                "floor":   ((80, 75, 70),  "damp cave floor, rocky"),
                "wall":    ((90, 82, 76),  "jagged cave rock wall, wet"),
                "ceiling": ((50, 46, 44),  "dark stalactite cave ceiling"),
            },
            "city": {
                "floor":   ((130, 125, 118),"paved stone street"),
                "wall":    ((150, 140, 125),"cut sandstone building wall"),
                "ceiling": ((120, 140, 170),"open sky"),
            },
        }
        palette = theme_palettes.get(self.theme, theme_palettes["dungeon"])
        shaders = self.profile.get("materials", {}).get("shaders", [])
        default_shader = shaders[0] if shaders else "Opaque_MaxCB1.fx"

        for name, (color, desc) in palette.items():
            spec.add_material(name, f"{name}.dds", shader=default_shader,
                              color=color, description=desc)

    def _add_room_lights(self, spec: ZoneSpec, room: RoomSpec, idx: int) -> None:
        # Theme-appropriate light colour
        colors = {
            "dungeon": (1.0, 0.55, 0.15),   # torch orange
            "cave":    (0.5, 0.6, 0.8),     # cool blue
            "outdoor": (1.0, 0.95, 0.85),   # daylight
            "city":    (1.0, 0.85, 0.6),    # warm lantern
        }
        r, g, b = colors.get(self.theme, (1.0, 0.6, 0.2))
        # One light near the ceiling centre of the room
        spec.lights.append(LightSpec(
            id=f"light_{idx}",
            x=room.center_x, y=room.center_y, z=room.floor_z + room.height * 0.75,
            r=r, g=g, b=b,
            radius=max(room.width, room.depth) * 0.9,
        ))

    def _open_facing_walls(self, room: RoomSpec, toward: RoomSpec) -> None:
        """Open the wall of *room* that faces *toward* so a corridor connects."""
        dx = toward.center_x - room.center_x
        dy = toward.center_y - room.center_y
        if abs(dx) >= abs(dy):
            wall = "E" if dx > 0 else "W"
        else:
            wall = "N" if dy > 0 else "S"
        if wall not in room.open_walls:
            room.open_walls.append(wall)
