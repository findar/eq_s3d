"""
generators/layout.py
--------------------
Procedural zone layout. Generates a ZoneSpec (rooms + corridors + lights) from
high-level parameters, constrained by a style profile.

Layout uses a TinyKeep-style spatial algorithm (scatter → separate → Delaunay →
MST + loop edges → graph-based elevation → wall-to-wall corridors), which
produces composed hub-and-branch dungeons without overlaps or tangling. Room
sizes track the theme's measured footprint; the result feeds all three geometry
backends (box, organic cave, heightfield terrain) unchanged.

Deterministic and seedable. The AI planner produces a ZonePlan which
ai.expand.plan_to_spec drives through this generator.
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

        # ------------------------------------------------------------------
        # Per-theme scale, derived from the measured style profile.
        #
        # The profile stores the mean whole-zone floor_area for this theme
        # (e.g. ~2M u² for dungeons, ~94M u² for outdoor — outdoor zones are
        # ~40× the footprint). We size individual rooms so the assembled zone
        # lands near that real footprint: each room covers roughly
        # floor_area / room_count, so a room's side ≈ sqrt(area / count).
        #
        # The default room_count assumption here (used only to set the base
        # per-room size) is refined per-generate by _room_size_for(count).
        # ------------------------------------------------------------------
        self._target_floor_area = _profile_mean(
            self.profile, ["geometry", "floor_area"], 2_000_000.0)

        # Ceiling comes straight from the measured mean, clamped to sane bounds.
        # Indoor ceilings ~300-470u, outdoor "ceiling" (hill vertical range)
        # ~1100u — but a single room shouldn't be a kilometre tall, so cap it.
        measured_ceiling = _profile_mean(
            self.profile, ["geometry", "ceiling_height"], 300.0)
        self.ceiling = max(50.0, min(400.0, measured_ceiling * 0.4))

        # Corridor scale tracks room scale (set in _apply_room_scale).
        self.corridor_width = 50.0
        self.corridor_height = max(40.0, self.ceiling * 0.8)

        # Optional overall size multiplier (small/large/huge from a plan).
        # Applied on top of the theme-accurate base in _apply_room_scale.
        self.size_multiplier = 1.0

        # Placeholder room-size band; refined per generate() by room count.
        self.room_min = 150.0
        self.room_max = 400.0
        self._apply_room_scale(room_count=5)

        # Elevation parameters. elevation_chance is the probability that a
        # connection between two rooms changes height. step_rise is the Z change
        # per elevated connection.
        self.elevation_chance = 0.5
        self.step_rise_min = 20.0
        self.step_rise_max = 80.0

    def _apply_room_scale(self, room_count: int) -> None:
        """
        Set room_min/room_max (and corridor width) from the theme's measured
        floor area divided across `room_count` rooms, so the assembled zone's
        footprint tracks the real indoor-vs-outdoor proportions.
        """
        count = max(1, room_count)
        # Rooms don't tile perfectly (gaps, corridors), so target ~55% of the
        # per-room area share as actual room floor; the rest is spacing.
        per_room_area = (self._target_floor_area / count) * 0.55
        side = max(120.0, per_room_area ** 0.5) * self.size_multiplier
        # Allow natural variation around the target side length.
        self.room_min = side * 0.7
        self.room_max = side * 1.3
        # Corridors scale with rooms but stay walkable-narrow relative to them.
        self.corridor_width = max(40.0, min(side * 0.25, 400.0))
        self.corridor_height = max(40.0, self.ceiling * 0.8)

    # ------------------------------------------------------------------
    # Main generation
    # ------------------------------------------------------------------

    def generate(self,
                 name: str,
                 room_count: int = 5,
                 add_lights: bool = True,
                 elevation: bool = True) -> ZoneSpec:
        spec = ZoneSpec(name=name, theme=self.theme, style_profile=self.theme)

        # Scale rooms to the theme's measured footprint divided across the
        # requested room count, so total zone size matches real proportions.
        self._apply_room_scale(room_count)
        self._add_default_materials(spec)

        # --- TinyKeep-style layout -------------------------------------
        # 1. Scatter rooms in an ellipse, 2. separate them, 3. classify
        #    main/filler, 4. Delaunay graph, 5. MST + a few loop edges,
        #    6. assign elevation over the graph, 7. wall-to-wall corridors.
        rooms = self._scatter_rooms(room_count)
        self._separate_rooms(rooms)
        edges = self._connect_rooms(rooms)          # list of (i, j) index pairs
        if elevation:
            self._assign_elevation(rooms, edges)

        for i, room in enumerate(rooms):
            spec.rooms.append(room)
            if add_lights:
                self._add_room_lights(spec, room, i)

        self._build_corridors(spec, rooms, edges)

        # Safe point in the entrance room (room 0).
        if rooms:
            r0 = rooms[0]
            spec.safe_point = (r0.center_x, r0.center_y, r0.floor_z + 5.0)

        return spec

    # ------------------------------------------------------------------
    # TinyKeep layout steps
    # ------------------------------------------------------------------

    def _scatter_rooms(self, room_count: int) -> List[RoomSpec]:
        """
        Step 1: scatter rooms inside an ellipse. Sizes drawn from a normal
        distribution around the theme's room scale so a few rooms are large
        (hubs) and most are smaller (connective), à la TinyKeep.
        """
        mean_side = (self.room_min + self.room_max) / 2
        std_side = (self.room_max - self.room_min) / 3
        # Ellipse radius grows with room count so rooms have space to separate.
        spread = mean_side * (0.8 + 0.5 * room_count)

        rooms: List[RoomSpec] = []
        for i in range(room_count):
            # Random point in an ellipse (slightly wider than tall for a
            # natural footprint ratio).
            px, py = self._rand_in_ellipse(spread, spread * 0.75)
            w = max(self.room_min * 0.6, self.rng.gauss(mean_side, std_side))
            d = max(self.room_min * 0.6, self.rng.gauss(mean_side, std_side))
            rooms.append(RoomSpec(
                id=f"room_{i}",
                center_x=px, center_y=py, floor_z=0.0,
                width=w, depth=d, height=self.ceiling,
            ))
        return rooms

    def _rand_in_ellipse(self, rx: float, ry: float) -> Tuple[float, float]:
        import math
        t = 2 * math.pi * self.rng.random()
        u = self.rng.random() + self.rng.random()
        r = (2 - u) if u > 1 else u
        return rx * r * math.cos(t) / 2, ry * r * math.sin(t) / 2

    def _separate_rooms(self, rooms: List[RoomSpec], iterations: int = 60) -> None:
        """
        Step 2: push overlapping rooms apart (no physics engine needed). Each
        iteration nudges any overlapping pair apart along their centre-to-centre
        vector until the layout settles with a small gap between rooms.
        """
        gap = max(self.corridor_width * 0.5, 30.0)
        for _ in range(iterations):
            moved = False
            for a in range(len(rooms)):
                for b in range(a + 1, len(rooms)):
                    ra, rb = rooms[a], rooms[b]
                    # Required half-separation on each axis (AABB + gap)
                    min_dx = (ra.width + rb.width) / 2 + gap
                    min_dy = (ra.depth + rb.depth) / 2 + gap
                    dx = rb.center_x - ra.center_x
                    dy = rb.center_y - ra.center_y
                    ox = min_dx - abs(dx)   # overlap on X
                    oy = min_dy - abs(dy)   # overlap on Y
                    if ox > 0 and oy > 0:
                        # Resolve along the axis of least penetration
                        if ox < oy:
                            push = ox / 2 * (1 if dx >= 0 else -1)
                            ra.center_x -= push
                            rb.center_x += push
                        else:
                            push = oy / 2 * (1 if dy >= 0 else -1)
                            ra.center_y -= push
                            rb.center_y += push
                        moved = True
            if not moved:
                break

    def _connect_rooms(self, rooms: List[RoomSpec]) -> List[Tuple[int, int]]:
        """
        Steps 3–5: build a connection graph via Delaunay triangulation, reduce
        it to a minimum spanning tree (guarantees reachability, mostly tree-
        shaped), then add back a few edges to create loops/alternate paths.
        Returns a list of (i, j) room-index edges.
        """
        n = len(rooms)
        if n <= 1:
            return []
        if n == 2:
            return [(0, 1)]

        pts = [(r.center_x, r.center_y) for r in rooms]

        # Candidate edges from Delaunay triangulation (fall back to a chain if
        # scipy/Delaunay is unavailable or degenerate — e.g. collinear points).
        candidate = self._delaunay_edges(pts)
        if not candidate:
            return [(i, i + 1) for i in range(n - 1)]

        # Minimum spanning tree over candidate edges (Kruskal).
        import math
        weighted = sorted(
            candidate,
            key=lambda e: (pts[e[0]][0] - pts[e[1]][0]) ** 2
                          + (pts[e[0]][1] - pts[e[1]][1]) ** 2,
        )
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        mst: List[Tuple[int, int]] = []
        extra: List[Tuple[int, int]] = []
        for i, j in weighted:
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[ri] = rj
                mst.append((i, j))
            else:
                extra.append((i, j))

        # Add back ~12% of the non-tree edges for loops/alternate routes.
        self.rng.shuffle(extra)
        n_add = max(0, int(len(extra) * 0.12))
        mst.extend(extra[:n_add])
        return mst

    def _delaunay_edges(self, pts: List[Tuple[float, float]]) -> List[Tuple[int, int]]:
        """Delaunay triangulation edges via scipy; empty list on failure."""
        try:
            import numpy as np
            from scipy.spatial import Delaunay
            tri = Delaunay(np.array(pts))
            edges = set()
            for simplex in tri.simplices:
                for a in range(3):
                    for b in range(a + 1, 3):
                        i, j = int(simplex[a]), int(simplex[b])
                        edges.add((min(i, j), max(i, j)))
            return list(edges)
        except Exception:
            return []

    def _assign_elevation(self, rooms: List[RoomSpec],
                          edges: List[Tuple[int, int]]) -> None:
        """
        Step 6: assign floor heights over the graph via BFS from room 0, so
        connected rooms can sit at different Z and corridors ramp/step between
        them. Height changes propagate along edges (not arbitrarily), which
        keeps elevation coherent rather than random.
        """
        from collections import defaultdict, deque
        adj = defaultdict(list)
        for i, j in edges:
            adj[i].append(j)
            adj[j].append(i)

        visited = {0}
        q = deque([0])
        while q:
            cur = q.popleft()
            for nxt in adj[cur]:
                if nxt in visited:
                    continue
                visited.add(nxt)
                z = rooms[cur].floor_z
                if self.rng.random() < self.elevation_chance:
                    rise = self.rng.uniform(self.step_rise_min, self.step_rise_max)
                    z += rise * self.rng.choice([1, -1])
                rooms[nxt].floor_z = z
                q.append(nxt)

    def _build_corridors(self, spec: ZoneSpec, rooms: List[RoomSpec],
                         edges: List[Tuple[int, int]]) -> None:
        """
        Step 7: a wall-to-wall corridor for each graph edge, ramping/stepping
        where the two rooms differ in height.
        """
        for k, (i, j) in enumerate(edges):
            a, b = rooms[i], rooms[j]
            use_steps = abs(b.floor_z - a.floor_z) > 1.0 and self.rng.random() < 0.5
            fx, fy = self._wall_point(a, b)
            tx, ty = self._wall_point(b, a)
            spec.corridors.append(CorridorSpec(
                id=f"corr_{k}",
                from_x=fx, from_y=fy,
                to_x=tx, to_y=ty,
                from_z=a.floor_z, to_z=b.floor_z,
                width=self.corridor_width,
                height=self.corridor_height,
                steps=self.rng.randint(4, 8) if use_steps else 0,
            ))
            self._open_facing_walls(a, b)
            self._open_facing_walls(b, a)

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

    def _wall_point(self, room: RoomSpec, toward: RoomSpec) -> Tuple[float, float]:
        """
        Return the (x, y) point on *room*'s wall that faces *toward*, where the
        corridor should connect. This is the midpoint of the facing wall, so
        the corridor meets the wall opening cleanly instead of driving to the
        room centre. A small inset keeps the corridor flush with the wall plane.
        """
        dx = toward.center_x - room.center_x
        dy = toward.center_y - room.center_y
        hw, hd = room.width / 2, room.depth / 2
        # Small inset so the corridor overlaps the wall slightly (clean join).
        inset = 2.0
        if abs(dx) >= abs(dy):
            # East/West wall
            x = room.center_x + (hw - inset) * (1 if dx > 0 else -1)
            return x, room.center_y
        else:
            # North/South wall
            y = room.center_y + (hd - inset) * (1 if dy > 0 else -1)
            return room.center_x, y

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
