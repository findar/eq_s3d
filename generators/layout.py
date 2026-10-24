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
    GateSpec,
)
from . import semantics
from .routing import plan_route, exit_axis_x

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


# Themes that use the box backend and therefore support the semantic layer.
# (Cave/outdoor backends are organic/heightfield and are out of scope here.)
_SEMANTIC_THEMES = {"dungeon", "city"}


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
        # Remember the seed so it can be recorded on the ZoneSpec. The geometry
        # backends (cave/terrain) seed from this rather than a hash of the
        # (always-unique, timestamped) name, so a pinned seed reproduces the
        # zone. None stays None → the spec records "no explicit seed".
        self.seed = seed
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

        # Walkability bound for elevation (corridor-connection task #2). The
        # elevation magnitude used to be picked with no regard to how long the
        # corridor between the two rooms' walls actually is, so close rooms with
        # a big Z delta produced unwalkable cliffs (seeds 1955208177, 678358326).
        #   max_grade — steepest floor slope (rise / run) allowed on a corridor
        #               ramp. 0.5 ≈ 26.6°, comfortably under the traversability
        #               agent's 40° walkable-slope cap.
        self.max_grade = 0.5

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
                 elevation: bool = True,
                 locks: int = 0,
                 dungeon_theme: str = "",
                 dungeon_race: str = "",
                 elemental_tint: Optional[str] = None,
                 room_type_overrides: Optional[dict] = None) -> ZoneSpec:
        """
        Generate a zone. *locks* > 0 produces a keyed dungeon with that many
        lock-and-key gates (solvability guaranteed); 0 is a fully open dungeon.

        Content / semantic layer (dungeon theme, Step 1): *dungeon_theme* picks
        the archetype arc (e.g. "fortress", "temple", "sunken_ruin");
        *dungeon_race* is a global scale multiplier ("giant", "froglok", …);
        *elemental_tint* overrides the archetype's default tint ("" forces none,
        None uses the default). *room_type_overrides* maps room id → semantic
        type for planner-driven assignment. Semantic labelling only runs for the
        box (dungeon/city) themes — cave/outdoor backends are untouched.
        """
        spec = ZoneSpec(name=name, theme=self.theme, style_profile=self.theme,
                        seed=self.seed)

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

        # Pacing: derive entrance / depth / roles from the graph, then bias
        # room geometry (and later lighting) by role & depth so the zone reads
        # as a progression rather than a flat set of equal rooms.
        entrance = self._apply_pacing(rooms, edges)

        # Content / semantic layer (box themes only): label rooms with a
        # semantic type + theme and apply the shape/proportion/ceiling/floor
        # biases BEFORE the re-separate + elevation passes, so the themed shapes
        # resolve for overlaps and elevation builds on the sunk/raised floors.
        themed = self.theme in _SEMANTIC_THEMES and (
            dungeon_theme or dungeon_race or elemental_tint is not None
            or room_type_overrides)
        if themed:
            semantics.label_rooms(
                spec, rooms, self.rng,
                archetype=dungeon_theme, race=dungeon_race,
                tint=elemental_tint, overrides=room_type_overrides)

        # Role biasing resized rooms (climax/hub grew, dead-ends shrank), so
        # re-separate to resolve any overlaps the new sizes introduced. Keep
        # the graph edges — only positions shift slightly.
        self._separate_rooms(rooms)

        if elevation:
            self._assign_elevation(rooms, edges, entrance)
        elif themed:
            # Elevation is off, but the semantic layer perturbed floor_z (sunk
            # arenas / sumps, raised thrones). Those biased floors never went
            # through _assign_elevation, so a sunk room next to a flat one over
            # a short run is a corridor steeper than max_grade — the historic
            # cliff-corridor failure mode, reachable with elevation OFF via the
            # semantic sink path. Run the relax pass alone (no random rises): it
            # pulls every room into its neighbours' walkable Z bands, so the
            # sink CHARACTER survives wherever the run can carry it while every
            # corridor stays within the grade cap.
            self._relax_semantic_floors(rooms, edges, entrance)

        for i, room in enumerate(rooms):
            spec.rooms.append(room)
            if add_lights:
                self._add_room_lights(spec, room, i)

        # Realize the semantic parts that need final geometry + the assembled
        # spec: per-room palette, elemental regions, and lighting mood.
        if themed:
            semantics.realize_semantics(spec, self.rng)

        self._build_corridors(spec, rooms, edges)

        # Safe point in the entrance room.
        if rooms:
            e = rooms[entrance]
            spec.safe_point = (e.center_x, e.center_y, e.floor_z + 5.0)

        # Optional lock-and-key gating (keyed dungeons). Runs after corridors
        # exist so gates can reference corridor ids. Solvability is guaranteed.
        if locks > 0:
            self._apply_gating(spec, rooms, edges, entrance, n_locks=locks)

        return spec

    # ------------------------------------------------------------------
    # Gating — solvability-guaranteed lock & key placement
    # ------------------------------------------------------------------

    def _apply_gating(self, spec: ZoneSpec, rooms: List[RoomSpec],
                      edges: List[Tuple[int, int]], entrance: int,
                      n_locks: int) -> None:
        """
        Place `n_locks` lock-and-key gates on the room graph such that the
        dungeon is ALWAYS solvable.

        Method (a constrained graph-rewrite): lock only edges of the BFS tree
        rooted at the entrance. Cutting a tree edge cleanly partitions rooms
        into a "near" set (containing the entrance) and a "far" subtree. The
        key for that lock is placed in a room in the near set, outside any
        deeper locked subtree. This guarantees every key is obtainable before
        the door it opens — nested or sequential, never a deadlock.
        """
        from collections import defaultdict, deque

        n = len(rooms)
        if n < 3 or not edges:
            return

        adj = defaultdict(list)
        for i, j in edges:
            adj[i].append(j)
            adj[j].append(i)

        # BFS tree from the entrance → parent[] + traversal order.
        parent = {entrance: None}
        order = [entrance]
        q = deque([entrance])
        while q:
            cur = q.popleft()
            for nxt in adj[cur]:
                if nxt not in parent:
                    parent[nxt] = cur
                    order.append(nxt)
                    q.append(nxt)

        children = defaultdict(list)
        for c in order:
            if parent[c] is not None:
                children[parent[c]].append(c)

        def subtree(node: int) -> set:
            s = set()
            stack = [node]
            while stack:
                cur = stack.pop()
                s.add(cur)
                stack.extend(children[cur])
            return s

        # Candidate lock edges: tree edges that gate a meaningful subtree.
        tree_edges = [(c, parent[c]) for c in order if parent[c] is not None]
        tree_edges.sort(key=lambda e: rooms[e[0]].graph_depth, reverse=True)

        corr_by_pair = {}
        for k, (i, j) in enumerate(edges):
            corr_by_pair[frozenset((i, j))] = f"corr_{k}"

        chosen = []
        for child, par in tree_edges:
            if len(chosen) >= n_locks:
                break
            far = subtree(child)
            if len(far) < 1 or len(far) >= n - 1:
                continue
            chosen.append((child, par, far))

        # Place locks shallow→deep (tier 0 = outermost).
        chosen.sort(key=lambda c: rooms[c[0]].graph_depth)
        locked_far: set = set()
        for tier, (child, par, far) in enumerate(chosen):
            corr_id = corr_by_pair.get(frozenset((child, par)))
            if corr_id is None:
                continue

            # Key goes in a room reachable before this lock: not behind this
            # lock, nor behind any deeper lock. Prefer closest to the entrance.
            forbidden = set(far) | locked_far
            candidates = [i for i in range(n) if i not in forbidden and i != entrance]
            if not candidates:
                candidates = [i for i in range(n) if i not in far]
            key_room = min(candidates, key=lambda i: rooms[i].graph_depth)

            cor = next(c for c in spec.corridors if c.id == corr_id)
            kr = rooms[key_room]
            spec.gates.append(GateSpec(
                id=f"gate_{tier}",
                corridor_id=corr_id,
                lock_x=(cor.from_x + cor.to_x) / 2,
                lock_y=(cor.from_y + cor.to_y) / 2,
                lock_z=(cor.from_z + cor.to_z) / 2,
                key_room_id=kr.id,
                key_x=kr.center_x, key_y=kr.center_y, key_z=kr.floor_z + 5.0,
                tier=tier,
            ))
            locked_far |= far

    # ------------------------------------------------------------------
    # Pacing — graph-derived roles & depth
    # ------------------------------------------------------------------

    def _apply_pacing(self, rooms: List[RoomSpec],
                      edges: List[Tuple[int, int]]) -> int:
        """
        Analyse the room graph to assign each room a role and depth:

          - entrance : a peripheral room (outermost from the layout centroid),
                       so players enter from the edge, not the middle.
          - depth    : graph hops from the entrance (BFS). The progression axis.
          - climax   : the room with the greatest graph depth (boss chamber).
          - hub      : a crossroads (graph degree >= 3).
          - deadend  : a leaf (degree 1) that isn't the entrance.
          - standard : everything else.

        Then bias room geometry by role & depth so the shape reflects the pacing.
        Returns the entrance room index.
        """
        n = len(rooms)
        if n == 0:
            return 0

        # Build adjacency and degree.
        from collections import defaultdict, deque
        adj = defaultdict(list)
        for i, j in edges:
            adj[i].append(j)
            adj[j].append(i)

        # Entrance = the room farthest from the layout centroid (peripheral).
        cx = sum(r.center_x for r in rooms) / n
        cy = sum(r.center_y for r in rooms) / n
        entrance = max(
            range(n),
            key=lambda i: (rooms[i].center_x - cx) ** 2 + (rooms[i].center_y - cy) ** 2,
        )

        # BFS graph-depth from the entrance.
        gdepth = {entrance: 0}
        q = deque([entrance])
        while q:
            cur = q.popleft()
            for nxt in adj[cur]:
                if nxt not in gdepth:
                    gdepth[nxt] = gdepth[cur] + 1
                    q.append(nxt)
        for i in range(n):
            rooms[i].graph_depth = gdepth.get(i, 0)

        # Climax = deepest room (ties broken by lowest index for determinism).
        climax = max(range(n), key=lambda i: (rooms[i].graph_depth, -i)) if n > 1 else entrance

        # Assign roles.
        for i in range(n):
            deg = len(adj[i])
            if i == entrance:
                rooms[i].role = "entrance"
            elif i == climax:
                rooms[i].role = "climax"
            elif deg >= 3:
                rooms[i].role = "hub"
            elif deg == 1:
                rooms[i].role = "deadend"
            else:
                rooms[i].role = "standard"

        self._bias_rooms_by_role(rooms)
        return entrance

    def _bias_rooms_by_role(self, rooms: List[RoomSpec]) -> None:
        """
        Scale room geometry by role so pacing is visible in the shape:
          - climax : grand — larger footprint, taller ceiling
          - hub    : spacious crossroads
          - deadend: intimate — smaller
          - entrance/standard: baseline
        """
        role_scale = {
            "climax":   (1.6, 1.5),   # (footprint, ceiling) multipliers
            "hub":      (1.3, 1.15),
            "entrance": (1.1, 1.0),
            "deadend":  (0.7, 0.85),
            "standard": (1.0, 1.0),
        }
        for r in rooms:
            fs, cs = role_scale.get(r.role, (1.0, 1.0))
            r.width *= fs
            r.depth *= fs
            r.height = max(40.0, r.height * cs)

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
                          edges: List[Tuple[int, int]],
                          entrance: int = 0) -> None:
        """
        Step 6: assign floor heights over the graph via BFS from the entrance,
        so connected rooms can sit at different Z and corridors ramp/step
        between them. Height changes propagate along edges (not arbitrarily),
        which keeps elevation coherent rather than random.
        """
        from collections import defaultdict, deque
        adj = defaultdict(list)
        for i, j in edges:
            adj[i].append(j)
            adj[j].append(i)

        visited = {entrance}
        q = deque([entrance])
        while q:
            cur = q.popleft()
            for nxt in adj[cur]:
                if nxt in visited:
                    continue
                visited.add(nxt)
                z = rooms[cur].floor_z
                if self.rng.random() < self.elevation_chance:
                    rise = self.rng.uniform(self.step_rise_min, self.step_rise_max)
                    # Bound the rise by what the corridor run can carry at a
                    # walkable grade. The geometry confines the rise to one leg;
                    # capping by the interior-jog length (the shortest leg a
                    # staircase could ride) keeps BOTH the stair case and the
                    # gentler ramp case within max_grade. A rise steeper than
                    # that would be a cliff — rooms end up closer in Z rather
                    # than unreachable.
                    run = self._elevation_run(rooms[cur], rooms[nxt])
                    rise = min(rise, run * self.max_grade)
                    if rise >= 1.0:
                        z += rise * self.rng.choice([1, -1])
                rooms[nxt].floor_z = z
                q.append(nxt)

        # The BFS caps only TREE edges. A loop (non-tree) edge connects two
        # rooms placed down separate tree paths, so its corridor can still be an
        # unwalkable cliff even though every tree step was capped (seed 4
        # corr_3). Relax the whole graph: pull every room into the walkable Z
        # band of ALL its neighbours until it settles, so every corridor — tree
        # or loop — ends up walkable.
        self._relax_elevation(rooms, adj, entrance)

    def _relax_semantic_floors(self, rooms: List[RoomSpec],
                               edges: List[Tuple[int, int]],
                               entrance: int = 0) -> None:
        """
        Relax semantic sink/raise floor biases into walkable bands WITHOUT the
        BFS random-rise pass. Used when elevation is off but the semantic layer
        moved floor_z: builds the same adjacency _assign_elevation uses and runs
        the proven _relax_elevation clamp so every corridor satisfies the grade
        cap while the sink character survives where the run can carry it.
        """
        from collections import defaultdict
        adj = defaultdict(list)
        for i, j in edges:
            adj[i].append(j)
            adj[j].append(i)
        self._relax_elevation(rooms, adj, entrance)

    def _relax_elevation(self, rooms: List[RoomSpec], adj, entrance: int,
                         iterations: int = 200) -> None:
        """
        Iteratively pull each room's floor_z into the intersection of its
        neighbours' walkable Z bands (|dz| <= run * max_grade per corridor).
        A room already inside every band doesn't move, so consistent verticality
        is preserved; only cliffs get compressed. The entrance stays fixed as
        the Z reference. Converges because each pass is a clamp toward feasibility.

        The pass is Gauss-Seidel: a room clamped against a neighbour read earlier
        in the SAME sweep can leave that neighbour a hair off-band, so the exit
        must settle well below the per-corridor cap's 0.01 tolerance. Exiting at
        `moved < 0.01` left a residual that pushed the occasional corridor a few
        thousandths past `run * max_grade + 0.01` (seed 3600, corr_2). Tighten the
        fixpoint to `moved < 1e-4` so the band constraint holds inside tolerance
        on every edge. (The cap's 0.01 tolerance itself is never widened.)
        """
        for _ in range(iterations):
            moved = 0.0
            for i in adj:
                if i == entrance:
                    continue
                lo, hi = float("-inf"), float("inf")
                for m in adj[i]:
                    cap = self._elevation_run(rooms[i], rooms[m]) * self.max_grade
                    lo = max(lo, rooms[m].floor_z - cap)
                    hi = min(hi, rooms[m].floor_z + cap)
                if lo <= hi:
                    newz = min(max(rooms[i].floor_z, lo), hi)
                else:
                    # Conflicting neighbours (rare): least-violating midpoint.
                    newz = (lo + hi) / 2
                moved = max(moved, abs(newz - rooms[i].floor_z))
                rooms[i].floor_z = newz
            if moved < 1e-4:
                break

    def _route_legs(self, a: RoomSpec, b: RoomSpec) -> List[float]:
        """
        Lengths of the axis-aligned legs of the corridor that will connect *a*
        and *b*, in order. Mirrors generators.geometry.add_corridor's routing:
        a single-element list for a straight corridor, or [stub, jog, stub] for
        a Z-corridor (parallel facing walls). Used to keep the elevation cap and
        the stair/ramp choice consistent with the geometry actually built.
        """
        fx, fy = self._wall_point(a, b)
        tx, ty = self._wall_point(b, a)
        # Route through the shared planner so the legs we measure match the
        # geometry actually built. The exit axes come from the footprint
        # separation, exactly as _wall_point cut the walls, computed per end so
        # a genuine cross-axis pair measures as an L. Corridors here always
        # record both rooms, so corridor_route resolves the same axes; planning
        # directly off the wall points keeps this independent of a CorridorSpec
        # (the corridor is not built yet when this is called).
        exit_from_x = self._exit_axis_x(a, b)
        exit_to_x = self._exit_axis_x(b, a)
        route = plan_route(
            (fx, fy), (tx, ty), exit_from_x, exit_to_x,
            self.corridor_width / 2, steps=0)
        wps, axes = route.waypoints, route.axes
        # Each leg runs along a single axis; measure only that axis's delta (a
        # straight leg carries a sub-slack cross offset we must not count, to
        # match the former _route_legs exactly).
        return [abs(wps[k + 1][0] - wps[k][0]) if axes[k]
                else abs(wps[k + 1][1] - wps[k][1])
                for k in range(len(wps) - 1)]

    def _elevation_run(self, a: RoomSpec, b: RoomSpec) -> float:
        """
        The run length the elevation cap is measured against: the interior jog
        of a Z-corridor (where a staircase rides and the steepest case lives),
        or the single leg of a straight corridor.
        """
        legs = self._route_legs(a, b)
        return legs[1] if len(legs) >= 3 else legs[0]

    def _build_corridors(self, spec: ZoneSpec, rooms: List[RoomSpec],
                         edges: List[Tuple[int, int]]) -> None:
        """
        Step 7: a wall-to-wall corridor for each graph edge, ramping/stepping
        where the two rooms differ in height.
        """
        for k, (i, j) in enumerate(edges):
            a, b = rooms[i], rooms[j]
            # Elevation is carried by a smooth ramp (steps=0). The geometry
            # backend subdivides the slope finely, so it is both walkable to the
            # per-triangle traversability agent (every face within a step of its
            # neighbour) and flush at both openings (the ramp floor reaches each
            # room's exact floor_z at its wall). A staircase would meet the
            # per-mesh step-up limit only with sub-player-height steps and exact
            # landings; the ramp is the robust choice and _assign_elevation has
            # already capped the grade to a walkable slope.
            fx, fy = self._wall_point(a, b)
            tx, ty = self._wall_point(b, a)
            spec.corridors.append(CorridorSpec(
                id=f"corr_{k}",
                from_x=fx, from_y=fy,
                to_x=tx, to_y=ty,
                from_z=a.floor_z, to_z=b.floor_z,
                width=self.corridor_width,
                height=self.corridor_height,
                steps=0,
                from_room=a.id, to_room=b.id,
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
        # Theme-appropriate base light colour
        colors = {
            "dungeon": (1.0, 0.55, 0.15),   # torch orange
            "outdoor": (1.0, 0.95, 0.85),   # daylight
            "city":    (1.0, 0.85, 0.6),    # warm lantern
        }
        r, g, b = colors.get(self.theme, (1.0, 0.6, 0.2))

        # Pacing-driven mood: deeper rooms are dimmer and cooler (more
        # ominous), the entrance is brightest, the climax gets a slightly
        # intensified/charged light. Outdoor zones keep daylight (depth doesn't
        # darken the sky).
        intensity = 1.0
        if self.theme != "outdoor":
            # Fade brightness with graph depth, floored so it never goes black.
            fade = max(0.45, 1.0 - room.graph_depth * 0.08)
            intensity = fade
            if room.role == "entrance":
                intensity = 1.0
            elif room.role == "climax":
                # Climax: restore brightness and push the colour toward a
                # charged/eerie tint so it reads as "the place".
                intensity = 0.9
                r, g, b = (min(1.0, r * 1.1), g * 0.8, min(1.0, b * 1.3))

        spec.lights.append(LightSpec(
            id=f"light_{idx}_{room.role}",
            x=room.center_x, y=room.center_y, z=room.floor_z + room.height * 0.75,
            r=r * intensity, g=g * intensity, b=b * intensity,
            radius=max(room.width, room.depth) * 0.9,
        ))

    def _exit_axis_x(self, room: RoomSpec, toward: RoomSpec) -> bool:
        """True when *room*'s corridor to *toward* exits an E/W wall (runs X).

        Delegates to `routing.exit_axis_x` so the wall this cuts and the leg
        `corridor_route`/`plan_route` plan agree on the same footprint-
        separation basis.
        """
        return exit_axis_x(
            room.center_x, room.center_y, room.width / 2, room.depth / 2,
            toward.center_x, toward.center_y, toward.width / 2, toward.depth / 2)

    def _wall_point(self, room: RoomSpec, toward: RoomSpec) -> Tuple[float, float]:
        """
        Return the (x, y) point on *room*'s wall that faces *toward*, where the
        corridor should connect. This is the midpoint of the facing wall, so
        the corridor meets the wall opening cleanly instead of driving to the
        room centre. A small inset keeps the corridor flush with the wall plane.

        The wall AXIS is chosen by the gap between the two footprints, not by
        the centre delta: whichever axis the rooms are cleanly SEPARATED on
        (positive gap) is the axis a corridor can exit along without the facing
        walls crossing. When the centre delta picked the axis instead, a pair
        that overlaps on that axis but is separated on the other produced an
        INVERTED stub — the from-opening ended up past the to-opening and the
        corridor had to run backwards to reach the jog (the `fx past tx` class,
        design suspect table). Picking by separation keeps both stubs pointing
        out of their rooms toward the real gap. `corridor_route` /
        `_exit_axis_x` mirror this basis so the routed legs match these walls.
        """
        exit_x = self._exit_axis_x(room, toward)
        dx = toward.center_x - room.center_x
        dy = toward.center_y - room.center_y
        hw, hd = room.width / 2, room.depth / 2
        # Small inset so the corridor overlaps the wall slightly (clean join).
        inset = 2.0
        if exit_x:
            # East/West wall
            x = room.center_x + (hw - inset) * (1 if dx >= 0 else -1)
            return x, room.center_y
        else:
            # North/South wall
            y = room.center_y + (hd - inset) * (1 if dy >= 0 else -1)
            return room.center_x, y

    def _open_facing_walls(self, room: RoomSpec, toward: RoomSpec) -> None:
        """Open the wall of *room* that faces *toward* so a corridor connects."""
        exit_x = self._exit_axis_x(room, toward)
        dx = toward.center_x - room.center_x
        dy = toward.center_y - room.center_y
        if exit_x:
            wall = "E" if dx >= 0 else "W"
        else:
            wall = "N" if dy >= 0 else "S"
        if wall not in room.open_walls:
            room.open_walls.append(wall)
