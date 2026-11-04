"""
generators/layout.py
--------------------
Procedural zone layout. Generates a ZoneSpec (rooms + corridors + lights) from
high-level parameters, constrained by a style profile.

The rooms and their graph come from a Layout_Engine (``generators/layout_engine.py``);
the default ``ClassicEngine`` is TinyKeep (scatter → separate → Delaunay → MST +
loop edges). Everything after it lives here: pacing, themes, graph-based
elevation, crossing and conflict fixes, wall-to-wall corridors, gating. The
result is a composed hub-and-branch dungeon without overlaps or tangling. Room
sizes track the theme's measured footprint; the result feeds all three geometry
backends (box, organic cave, heightfield terrain) unchanged.

Deterministic and seedable. The AI planner produces a ZonePlan which
ai.expand.plan_to_spec drives through this generator.
"""

from __future__ import annotations

import dataclasses
import json
import random
from functools import partial
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple, Union

from .zone_spec import (
    ZoneSpec, RoomSpec, CorridorSpec, LightSpec, RegionSpec, MaterialSpec,
    GateSpec,
)
from core.ter import SHADER_OPAQUE

from . import semantics
from .envelope import Envelope, EnvelopeFitError
from .layout_engine import (ClassicEngine, ENGINES, RELATIONS,
                            LayoutContext, LayoutEngine)
from .geometry import AUTO_STAIRS, MIN_LANE, MeshBuilder, stair_layout
from .routing import corridor_route, plan_route, exit_axis_x, route_footprint
from .zone_types import STYLE_PROFILE

# Overlap below this (u) is two faces touching, not one inside the other.
_TOUCH = 1e-6

# Fitting a layout inside an Envelope: the fewest rooms a build keeps, and how
# many fresh layouts are tried at each room count before dropping a room.
MIN_ENVELOPE_ROOMS = 3
ENVELOPE_ATTEMPTS = 6

# ---------------------------------------------------------------------------
# Style profile loading
# ---------------------------------------------------------------------------

def load_style_profile(profile_name: str) -> dict:
    """Load a style profile JSON by measured-profile name, or return defaults.

    ``profile_name`` is a measured style-profile name (``styles/<name>.json``),
    NOT a zone type — callers map a zone type through
    ``zone_types.STYLE_PROFILE`` first (wilderness -> "outdoor").
    """
    candidates = [
        Path(f"styles/{profile_name}.json"),
        Path(__file__).parent.parent / "styles" / f"{profile_name}.json",
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


# An ``above`` / ``below`` edge holds when the floors differ by at least this
# much in its direction; ``level`` when they're within LEVEL_TOL.
RELATION_RISE = 1.0
LEVEL_TOL = 1e-3


def relations_broken(rooms: List[RoomSpec],
                     relations: Dict[Tuple[int, int], str]) -> int:
    """How many vertical relations the final floors don't hold. ``(i, j):
    "above"`` wants room j's floor above room i's (design "Vertical
    relations")."""
    broken = 0
    for (i, j), rel in relations.items():
        dz = rooms[j].floor_z - rooms[i].floor_z
        if rel == "above":
            ok = dz >= RELATION_RISE - LEVEL_TOL
        elif rel == "below":
            ok = dz <= -RELATION_RISE + LEVEL_TOL
        elif rel == "level":
            ok = abs(dz) <= LEVEL_TOL
        else:
            ok = True
        broken += not ok
    return broken


# Stacked builds (step 7): the floor variation ramps give WITHIN a Level, as a
# band this wide centred on the Level's height. Job B's floor-to-floor height
# grows by it, so two Levels keep the Slab whatever the variation does
# (design "Levels": "bounded so two Levels never meet"). Two Slabs: small next
# to the ~135 u Level, like step 6's gentlest ramps.
LEVEL_VARIATION = 28.0

# How far a U-route stair's door sits in from the end of its wall.
U_DOOR_MARGIN = 2.0


class _Stack(NamedTuple):
    """What Job B knows of a stacked build: each room's Level and the
    floor-to-floor height it places them at."""
    levels: List[int]
    level_height: float
    variation: float

    def base(self, k: int) -> float:
        return self.levels[k] * self.level_height

    def band(self, k: int) -> Tuple[float, float]:
        h = self.variation / 2
        return self.base(k) - h, self.base(k) + h


class _Shape(NamedTuple):
    """An edge's corridor as Job B plans it on a stacked build: the corridor
    (``id`` still blank), its route, its floor as ``(rect, zlo, zhi, pin)``
    pieces (``zhi`` is the tube's top; ``pin`` the room a Z-corridor's stub
    and bend stay level with), and the first room it passes through without
    the Slab's clearance (None: clear)."""
    cor: CorridorSpec
    route: object
    pieces: List[Tuple[Tuple[float, float, float, float], float, float, Optional[int]]]
    blocked: Optional[int]


# Zone types that use the box backend and therefore support the semantic layer.
# (Cave/wilderness backends are organic/heightfield and out of scope here.)
_SEMANTIC_ZONE_TYPES = {"dungeon", "city"}


# ---------------------------------------------------------------------------
# Layout generator
# ---------------------------------------------------------------------------

class LayoutGenerator:
    """
    Generates a ZoneSpec procedurally.

    Usage::

        gen = LayoutGenerator(zone_type="dungeon", seed=42)
        spec = gen.generate("myrealm", room_count=5)
    """

    def __init__(self, zone_type: str = "dungeon", seed: Optional[int] = None,
                 engine: Union[LayoutEngine, str, None] = None):
        # The Layout_Engine that lays out the rooms and their graph (Job A);
        # ``None`` is the classic TinyKeep engine, a string names one in
        # ``layout_engine.ENGINES``.
        if engine is None:
            engine = ClassicEngine()
        elif isinstance(engine, str):
            engine = ENGINES[engine]()
        self.engine: LayoutEngine = engine
        # Normalise / legacy-map the zone type (``outdoor`` -> ``wilderness``)
        # so the backend registry and terrain routing always see the current
        # vocabulary, whatever a caller hands in.
        from .zone_types import canonical_zone_type
        self.zone_type = canonical_zone_type(zone_type) or zone_type
        # Box zones (dungeon/city) build walled rooms and corridor tubes, so
        # their corridors must stay clear of rooms and of each other (task 14):
        # a full-corridor-width room gap, footprint crossings, and no
        # overlapping corridors. Heightfield zones keep the earlier layout,
        # byte for byte (tests/test_hygiene.py pins it).
        self.corridor_clearance = self.zone_type in _SEMANTIC_ZONE_TYPES
        # ``profile`` loads the MEASURED style profile for this zone type
        # (wilderness -> styles/outdoor.json); the profile file name is a style
        # profile, not a zone type (zone_types "Zone-type vocabulary").
        self.profile = load_style_profile(
            STYLE_PROFILE.get(self.zone_type, self.zone_type))
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

        # The engine's record of the last layout (None for classic), with
        # Job B's edge_fidelity and relations_broken added. What the sidecar's
        # layout block reports.
        self.layout_record: Optional[dict] = None

        # Advisory warnings from the last generate() (e.g. ``rooms_reduced``
        # when an Envelope could not hold every requested room).
        self.warnings: List[str] = []

        # A stacked build's Levels (step 7), or None: Job B then runs as in
        # step 6, byte for byte. Set per layout pass by ``_generate_once``.
        self._stack: Optional[_Stack] = None
        self._shapes: Dict[Tuple[int, int], _Shape] = {}
        # A stair's route as the conflict pass re-routed it (an index into
        # its ``_stair_candidates``), kept while the floors move.
        self._stair_route: Dict[Tuple[int, int], int] = {}

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
                 room_type_overrides: Optional[dict] = None,
                 envelope: Optional[Envelope] = None) -> ZoneSpec:
        """
        Generate a zone. *locks* > 0 produces a keyed dungeon with that many
        lock-and-key gates (solvability guaranteed); 0 is a fully open dungeon.

        Content / semantic layer (dungeon theme, Step 1): *dungeon_theme* picks
        the archetype arc (e.g. "fortress", "temple", "sunken_ruin");
        *dungeon_race* is a global scale multiplier ("giant", "froglok", …);
        *elemental_tint* overrides the archetype's default tint ("" forces none,
        None uses the default). *room_type_overrides* maps room id → semantic
        type for planner-driven assignment. Semantic labelling only runs for the
        box (dungeon/city) zone types — cave/wilderness backends are untouched.

        *envelope* (outdoor dungeons) confines the layout: every room box and
        every corridor's swept box lies inside it. A layout that doesn't fit is
        redrawn; after ``ENVELOPE_ATTEMPTS`` misses a room is dropped, down to
        ``MIN_ENVELOPE_ROOMS``, with a ``rooms_reduced`` warning in
        ``self.warnings``. If even that many don't fit, ``EnvelopeFitError``.
        Without an Envelope the layout is exactly as before.
        """
        self.warnings = []
        args = (name, add_lights, elevation, locks, dungeon_theme,
                dungeon_race, elemental_tint, room_type_overrides)
        if envelope is None:
            return self._generate_once(room_count, *args)
        floor = min(room_count, MIN_ENVELOPE_ROOMS)
        self._apply_room_scale(room_count)
        for count in range(room_count, floor - 1, -1):
            for _ in range(ENVELOPE_ATTEMPTS):
                spec = self._generate_once(count, *args, envelope=envelope)
                if self.fits(spec, envelope):
                    if count < room_count:
                        self.warnings.append(
                            f"rooms_reduced: {room_count} requested, "
                            f"{count} fit the envelope")
                    return spec
        raise EnvelopeFitError(
            f"{floor} rooms do not fit the envelope after "
            f"{ENVELOPE_ATTEMPTS} attempts")

    def _generate_once(self, room_count: int, name: str, add_lights: bool,
                       elevation: bool, locks: int, dungeon_theme: str,
                       dungeon_race: str, elemental_tint: Optional[str],
                       room_type_overrides: Optional[dict],
                       envelope: Optional[Envelope] = None) -> ZoneSpec:
        """One layout pass (``generate`` without the Envelope retry loop)."""
        spec = ZoneSpec(name=name, zone_type=self.zone_type,
                        style_profile=STYLE_PROFILE.get(self.zone_type, self.zone_type),
                        seed=self.seed)

        # Scale rooms to the theme's measured footprint divided across the
        # requested room count, so total zone size matches real proportions.
        # (An Envelope build scales once, by the count asked for: dropping a
        # room must not make the rest bigger.)
        if envelope is None:
            self._apply_room_scale(room_count)
        shared = self._add_default_materials(spec, dungeon_race)
        self._stack = None
        self._shapes = {}
        self._stair_route = {}

        # --- Job A: the rooms and their graph, from the Layout_Engine ----
        # (classic: scatter in an ellipse, separate, Delaunay, MST + a few
        # loop edges). Then Job B: pacing, elevation over the graph,
        # wall-to-wall corridors.
        result = self.engine.generate(
            self._layout_context(room_count, dungeon_theme, dungeon_race),
            room_count, envelope)
        rooms = result.rooms
        # Job B works on plain (i, j) pairs; the vertical relations go to the
        # elevation pass alone (only the ones that constrain anything).
        edges = [(e[0], e[1]) for e in result.edges]
        relations = {(e[0], e[1]): e[2] for e in result.edges
                     if len(e) > 2 and e[2] != "any"}
        bad = sorted(set(relations.values()) - set(RELATIONS))
        if bad:
            raise ValueError(f"{self.engine.name}: unknown edge relation(s) {bad}; "
                             f"expected one of {RELATIONS}")

        # Pacing: derive entrance / depth / roles from the graph, then bias
        # room geometry (and later lighting) by role & depth so the zone reads
        # as a progression rather than a flat set of equal rooms. The way in
        # is the Envelope's when it has one (the hill's side), else the
        # engine's; an engine that sizes its own rooms skips the role bias.
        entry = envelope.entry if envelope is not None else None
        if entry is None:
            entry = result.entry
        entrance = self._apply_pacing(rooms, edges, entry,
                                      size_bias=not self.engine.sizes_rooms,
                                      climax=result.climax)

        # Content / semantic layer (box themes only): label rooms with a
        # semantic type + theme and apply the shape/proportion/ceiling/floor
        # biases BEFORE the re-separate + elevation passes, so the themed shapes
        # resolve for overlaps and elevation builds on the sunk/raised floors.
        themed = self.zone_type in _SEMANTIC_ZONE_TYPES and (
            dungeon_theme or dungeon_race or elemental_tint is not None
            or room_type_overrides)
        if themed:
            semantics.label_rooms(
                spec, rooms, self.rng,
                archetype=dungeon_theme, race=dungeon_race,
                tint=elemental_tint, overrides=room_type_overrides)

        # A stacked build (an engine gave rooms on more than one Level) runs
        # Job B in 3D from here: rooms on different Levels may overlap in plan,
        # floors sit at their Level, an edge across Levels is a stair.
        self._stack = self._stack_for(result, rooms)

        # Role biasing resized rooms (climax/hub grew, dead-ends shrank), so
        # re-separate to resolve any overlaps the new sizes introduced. Keep
        # the graph edges — only positions shift slightly.
        self._separate_rooms(rooms, storeys=self._storeys(rooms))

        if self._stack is not None:
            self._assign_stacked_elevation(rooms, edges, entrance, relations,
                                           elevation, themed)
        elif elevation:
            self._assign_elevation(rooms, edges, entrance, relations)
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

        # Resolve corridors that would cut through a third room by splitting the
        # edge A–B into A–C–B (C becomes a waypoint room; design option (a) for
        # the `crosses room` class). Runs on the FINAL room geometry so the
        # splits match the built mesh. A split changes the graph, so when a
        # build has elevation (or semantic floors moved) re-relax Z over the new
        # adjacency: the new A–C / C–B edges join rooms whose heights were set
        # against the OLD graph, so a split could otherwise leave a cliff. On a
        # flat zone every floor_z is 0 and the relax is a no-op.
        self._shapes = {}
        graph_changed = self._resolve_crossings(rooms, edges)
        # Drop a loop edge from any pair of corridors that would cross too close
        # in Z (the residual open-space conflict class the through-room split
        # can't reach). Only loop edges fall, so the graph stays connected.
        graph_changed = self._resolve_conflicts(rooms, edges) or graph_changed
        if graph_changed and (elevation or themed):
            from collections import defaultdict
            adj = defaultdict(list)
            for i, j in edges:
                adj[i].append(j)
                adj[j].append(i)
            self._relax_elevation(rooms, adj, entrance)

        if envelope is not None:
            self._fit_floors(rooms, edges, entrance, envelope)

        self._shapes = {}
        self._build_corridors(spec, rooms, edges)
        self.layout_record = self._layout_record(result, rooms, edges, relations,
                                                 elevation)
        if self._stack is not None and self.layout_record is not None:
            # The floor-to-floor height the floors were placed at (the
            # engine's, grown to hold the rooms as themed, plus the variation).
            self.layout_record["level_height"] = self._stack.level_height

        # Point every surface still on the bare default name at the shared
        # Material_Name (themed rooms already carry their own; Req 1.3).
        for part in (*spec.rooms, *spec.corridors):
            part.floor_material = shared.get(part.floor_material, part.floor_material)
            part.wall_material = shared.get(part.wall_material, part.wall_material)
            part.ceiling_material = shared.get(part.ceiling_material, part.ceiling_material)
        self._match_corridors_to_rooms(spec, shared)

        # Safe point in the entrance room.
        if rooms:
            e = rooms[entrance]
            spec.safe_point = (e.center_x, e.center_y, e.floor_z + 5.0)

        # Optional lock-and-key gating (keyed dungeons). Runs after corridors
        # exist so gates can reference corridor ids. Solvability is guaranteed.
        if locks > 0:
            self._apply_gating(spec, rooms, edges, entrance, n_locks=locks)

        return spec

    @staticmethod
    def _layout_record(result, rooms: List[RoomSpec], edges: List[Tuple[int, int]],
                       relations: Dict[Tuple[int, int], str],
                       elevation: bool) -> Optional[dict]:
        """The engine's record plus what Job B did to its graph:
        ``edge_fidelity`` (the engine's edges still present as corridors, over
        their count) and ``relations_broken`` (``above`` / ``below`` / ``level``
        edges whose final floors don't hold the relation; None with elevation
        off, where relations don't act)."""
        if result.record is None:
            return None
        rec = dict(result.record)
        grammar = {frozenset((e[0], e[1])) for e in result.edges}
        final = {frozenset(e) for e in edges}
        rec["edge_fidelity"] = (len(grammar & final) / len(grammar)) if grammar else 1.0
        rec["relations_broken"] = (relations_broken(rooms, relations)
                                   if elevation else None)
        return rec

    def _layout_context(self, room_count: int, theme: str,
                        race: str) -> LayoutContext:
        """The seam's one coupling to this generator (design "The seam")."""
        from .topology.rewrite import BuildContext   # see layout_engine.__getattr__
        return LayoutContext(
            rng=self.rng,
            room_min=self.room_min, room_max=self.room_max,
            ceiling=self.ceiling, corridor_width=self.corridor_width,
            separate=self._separate_rooms,
            build=BuildContext(zone_type=self.zone_type, theme=theme, race=race,
                               race_scale=semantics.race_scale(race),
                               room_count=room_count))

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
                      edges: List[Tuple[int, int]],
                      entry: Optional[Tuple[float, float]] = None,
                      size_bias: bool = True,
                      climax: Optional[int] = None) -> int:
        """
        Analyse the room graph to assign each room a role and depth:

          - entrance : a peripheral room (outermost from the layout centroid),
                       so players enter from the edge, not the middle. With an
                       *entry* point (an Envelope's way in), the room nearest
                       it instead.
          - depth    : graph hops from the entrance (BFS). The progression axis.
          - climax   : the room with the greatest graph depth (boss chamber),
                       or the *climax* room an engine names (the graph
                       engine's ``deep`` room). The entrance wins if the two
                       coincide (an Envelope's way in can pick the deep room);
                       the climax then falls back to the deepest by hops. One
                       room has no climax.
          - hub      : a crossroads (graph degree >= 3).
          - deadend  : a leaf (degree 1) that isn't the entrance.
          - standard : everything else.

        Then bias room geometry by role & depth so the shape reflects the pacing
        (unless *size_bias* is False: an engine that sizes its own rooms).
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

        if entry is not None:
            # Entrance = the room nearest the way in.
            ex, ey = entry
            entrance = min(
                range(n),
                key=lambda i: (rooms[i].center_x - ex) ** 2 + (rooms[i].center_y - ey) ** 2,
            )
        else:
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

        # Climax = the engine's pick, else the deepest room (ties broken by
        # lowest index for determinism). Depth stays BFS from the entrance.
        if n == 1:
            climax = entrance
        elif climax is None or not 0 <= climax < n or climax == entrance:
            climax = max(range(n), key=lambda i: (rooms[i].graph_depth, -i))

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

        if size_bias:
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
    # Separation (engines reach it through LayoutContext.separate)
    # ------------------------------------------------------------------

    def _separate_rooms(self, rooms: List[RoomSpec],
                        iterations: Optional[int] = None,
                        storeys: Optional[list] = None) -> None:
        """
        Step 2: push overlapping rooms apart (no physics engine needed). Each
        iteration nudges any overlapping pair apart along their centre-to-centre
        vector until the layout settles with a gap between rooms.

        The gap is a FULL corridor width: a Z-corridor's middle leg is a whole
        corridor wide and sits centred in the gap between the two facing walls,
        so a narrower gap put that leg (the ramp, when elevated) inside both
        rooms (task 14, seed 1955208177 corr_4). One unit of slack on top lets
        the iterative push stop a hair short and still clear the corridor.
        Heightfield zones keep the earlier half-width gap.

        *storeys* (a stacked build, step 7): each room's ``embed.Storey``. A
        pair that ``embed.may_overlap_in_plan`` (different Levels, the Slab
        between them) is left where it is, one over the other.
        """
        stacked = None
        if storeys is not None:
            from .topology.embed import may_overlap_in_plan
            stacked = {(a, b) for a in range(len(rooms)) for b in range(a + 1, len(rooms))
                       if may_overlap_in_plan(storeys[a], storeys[b])}
        if self.corridor_clearance:
            gap = max(self.corridor_width, 30.0) + 1.0
            iterations = iterations or 200
        else:
            gap = max(self.corridor_width * 0.5, 30.0)
            iterations = iterations or 60
        for _ in range(iterations):
            moved = False
            for a in range(len(rooms)):
                for b in range(a + 1, len(rooms)):
                    if stacked and (a, b) in stacked:
                        continue
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

    def _resolve_crossings(self, rooms: List[RoomSpec],
                           edges: List[Tuple[int, int]]) -> bool:
        """Split any edge whose corridor floor overlaps a third room.

        Design option (a) for the `crosses room` class (suspect table): when the
        A–B corridor's route footprint penetrates a third room C, replace the
        edge A–B with A–C and C–B so C becomes a WAYPOINT room. A player then
        walks A → (through C's floor, a real room) → B instead of the corridor
        cutting through C's collidable walls. The graph stays connected (A and B
        were joined and still are, now via C), so P3/P4/P6 hold on the new graph.

        Operates on the FINAL room geometry (called after the last
        `_separate_rooms`), so the crossings it resolves are the ones the built
        mesh and `corridor_continuity` actually see. Runs to a fixpoint because a
        fresh A–C or C–B sub-edge can itself cross a different room. Edges that
        become duplicates or self-loops after a split are dropped. Returns True
        if any edge changed (the caller re-relaxes elevation on the new graph).
        """
        if self._stack is not None:
            # Stacked: judged in 3D, a corridor over or under a room with the
            # Slab's clearance doesn't cross it (step 7).
            crossed_room = partial(self._crossed_room_3d, rooms)
        else:
            crossed_room = partial(
                self._crossed_room if self.corridor_clearance
                else self._crossed_room_centreline, rooms)

        stacked = self._stack is not None
        split = set()
        changed = False
        # Work queue of edges to (re)check; splitting pushes the two halves back.
        pending = list(edges)
        resolved: List[Tuple[int, int]] = []
        seen = set()
        # Bound iterations: each split adds C as a waypoint; with n rooms the
        # chain through distinct waypoints can't exceed n edges, so cap at n^2.
        budget = max(64, len(rooms) * len(rooms))
        while pending and budget > 0:
            budget -= 1
            i, j = pending.pop()
            if i == j:
                changed = True
                continue
            key = (min(i, j), max(i, j))
            c = crossed_room(i, j)
            if c is not None and stacked:
                # Stacked: a split's halves may each be blocked by the other's
                # room (a stair round a corner of its own Level), so an edge
                # is split once; met again it is kept and reported.
                if key in split:
                    note = f"crosses_room: {rooms[i].id}-{rooms[j].id}"
                    if note not in self.warnings:
                        self.warnings.append(note)
                    c = None
                else:
                    split.add(key)
            if c is None:
                if key not in seen:
                    seen.add(key)
                    resolved.append((i, j))
                continue
            # Split A–B into A–C and C–B; re-check both halves.
            changed = True
            pending.append((i, c))
            pending.append((c, j))

        if stacked:
            # Never drop an edge for want of budget (the graph must stay whole).
            for i, j in pending:
                key = (min(i, j), max(i, j))
                if i != j and key not in seen:
                    seen.add(key)
                    resolved.append((i, j))
        if changed:
            edges[:] = resolved
        return changed

    def _crossed_room_centreline(self, rooms: List[RoomSpec], i: int, j: int
                                 ) -> Optional[int]:
        """The first third room the i–j corridor's CENTRELINE passes through
        for more than a corridor width, or None. Heightfield zones split on
        this; box zones use the stricter footprint test (`_crossed_room`)."""
        hw = self.corridor_width / 2
        eps = 2.0  # match analyzer.traverse AgentModel.adjacency_eps default

        def _seg_enters_rect(p0, p1, rx0, ry0, rx1, ry1) -> bool:
            """True when the segment p0→p1 passes through the rect INTERIOR for
            a non-trivial span (Liang–Barsky clip; the clipped length must
            exceed one corridor width, so a centreline grazing a wall or just
            clipping a corner is not counted as a crossing)."""
            x0, y0 = p0
            x1, y1 = p1
            dx, dy = x1 - x0, y1 - y0
            t0, t1 = 0.0, 1.0
            for p, q in ((-dx, x0 - rx0), (dx, rx1 - x0),
                         (-dy, y0 - ry0), (dy, ry1 - y0)):
                if abs(p) < 1e-9:
                    if q < 0:
                        return False  # parallel to this edge and outside it
                    continue
                t = q / p
                if p < 0:
                    if t > t1:
                        return False
                    if t > t0:
                        t0 = t
                else:
                    if t < t0:
                        return False
                    if t < t1:
                        t1 = t
            if t1 <= t0:
                return False
            span = ((dx * (t1 - t0)) ** 2 + (dy * (t1 - t0)) ** 2) ** 0.5
            return span > hw

        a, b = rooms[i], rooms[j]
        fx, fy = self._wall_point(a, b)
        tx, ty = self._wall_point(b, a)
        route = plan_route((fx, fy), (tx, ty),
                           self._exit_axis_x(a, b), self._exit_axis_x(b, a),
                           hw, steps=0)
        wps = route.waypoints
        for k, r in enumerate(rooms):
            if k == i or k == j:
                continue
            rhw, rhd = r.width / 2, r.depth / 2
            # Shrink by eps so a centreline merely running ALONG a wall face
            # (never entering the interior) isn't counted; only a centreline
            # that passes THROUGH the room's interior is a real cut.
            x0, y0 = r.center_x - rhw + eps, r.center_y - rhd + eps
            x1, y1 = r.center_x + rhw - eps, r.center_y + rhd - eps
            if x0 >= x1 or y0 >= y1:
                continue
            for s in range(len(wps) - 1):
                if _seg_enters_rect(wps[s], wps[s + 1], x0, y0, x1, y1):
                    return k
        return None

    def _crossed_room(self, rooms: List[RoomSpec], i: int, j: int
                      ) -> Optional[int]:
        """The first third room the i–j corridor's FLOOR overlaps, or None.

        The whole footprint counts, not just the centreline: a corridor whose
        edge clips a room's corner still stacks its floor on (or, elevated,
        under) that room's and runs its walls through it (task 14).
        """
        hw = self.corridor_width / 2
        a, b = rooms[i], rooms[j]
        fx, fy = self._wall_point(a, b)
        tx, ty = self._wall_point(b, a)
        route = plan_route((fx, fy), (tx, ty),
                           self._exit_axis_x(a, b), self._exit_axis_x(b, a),
                           hw, steps=0)
        rects = route_footprint(route, hw)
        for k, r in enumerate(rooms):
            if k == i or k == j:
                continue
            rx0, ry0 = r.center_x - r.width / 2, r.center_y - r.depth / 2
            rx1, ry1 = r.center_x + r.width / 2, r.center_y + r.depth / 2
            for (x0, y0, x1, y1) in rects:
                if (min(x1, rx1) - max(x0, rx0) > _TOUCH
                        and min(y1, ry1) - max(y0, ry0) > _TOUCH):
                    return k
        return None

    def _resolve_conflicts(self, rooms: List[RoomSpec],
                           edges: List[Tuple[int, int]]) -> bool:
        """Remove every pair of corridors whose floors overlap.

        Design suspect-table conflict row / option (b): two corridors whose
        route footprints overlap in XY conflict at any height — over or under,
        the result is stacked floors, and a box build has one depth band (task
        14 dropped the old Z-clearance exemption). Two corridors from the SAME
        room may share that room's doorway stub and bend; anywhere else they
        conflict too (seed 7, 30 rooms: corr_8's far stub crossed corr_2's jog
        19 u higher). The through-room split (`_resolve_crossings`) removes most
        conflicts; a pair that crosses in open space survives it.

        A conflict drops a REMOVABLE loop (non-tree) edge when either corridor
        is one, so the graph stays connected. When both are tree edges, one is
        swapped for the shortest edge that rejoins the two halves without
        crossing a room or clashing with another corridor.

        Runs after `_resolve_crossings` on the final geometry. A change can
        clear several conflicts at once, so it re-detects after each one.
        Returns True if any edge changed (the caller re-relaxes elevation).
        """
        hw = self.corridor_width / 2

        def route_for(i: int, j: int):
            a, b = rooms[i], rooms[j]
            fx, fy = self._wall_point(a, b)
            tx, ty = self._wall_point(b, a)
            return plan_route((fx, fy), (tx, ty),
                              self._exit_axis_x(a, b), self._exit_axis_x(b, a),
                              hw, steps=0)

        def leg_rects(route):
            wps = route.waypoints
            rects = []
            for k in range(len(wps) - 1):
                (x0, y0), (x1, y1) = wps[k], wps[k + 1]
                rects.append((min(x0, x1) - hw, min(y0, y1) - hw,
                              max(x0, x1) + hw, max(y0, y1) + hw))
            return rects

        def overlaps(ra, rb) -> bool:
            for (ax0, ay0, ax1, ay1) in ra:
                for (bx0, by0, bx1, by1) in rb:
                    if ax0 <= bx1 and bx0 <= ax1 and ay0 <= by1 and by0 <= ay1:
                        return True
            return False

        def floor_pieces(i: int, j: int, route):
            """The route's floor as built, as (rect, room) pieces: `room` is the
            room whose floor a piece is pinned to (a Z-corridor's stub and bend
            square at each end stay flat at that room's height, whatever the
            later relax does), or None for floor that may slope."""
            wps = route.waypoints
            if route.kind != "z":
                return [(r, None) for r in route_footprint(route, hw)]

            def box(p, q):
                return (min(p[0], q[0]) - hw, min(p[1], q[1]) - hw,
                        max(p[0], q[0]) + hw, max(p[1], q[1]) + hw)
            return [(box(wps[0], wps[1]), i), (box(wps[1], wps[1]), i),
                    (box(wps[1], wps[2]), None),
                    (box(wps[2], wps[2]), j), (box(wps[2], wps[3]), j)]

        def shared_clash(pa, pb, shared: set) -> bool:
            """Two corridors from the same room may share that room's doorway
            stub; anywhere else their floors must not overlap."""
            for (ra, ka) in pa:
                for (rb, kb) in pb:
                    if ka is not None and ka == kb and ka in shared:
                        continue
                    if (min(ra[2], rb[2]) - max(ra[0], rb[0]) > _TOUCH
                            and min(ra[3], rb[3]) - max(ra[1], rb[1]) > _TOUCH):
                        return True
            return False

        def components_without(idx: int, es: List[Tuple[int, int]]):
            """Union-find roots of the graph with edge es[idx] left out."""
            parent = list(range(len(rooms)))

            def find(x):
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x

            for k, (u, v) in enumerate(es):
                if k == idx:
                    continue
                ru, rv = find(u), find(v)
                if ru != rv:
                    parent[ru] = rv
            return [find(x) for x in range(len(rooms))]

        def is_removable(idx: int, es: List[Tuple[int, int]]) -> bool:
            """True when edge es[idx] is a loop edge: its two endpoints stay
            connected after removing it (so dropping it keeps the graph whole)."""
            roots = components_without(idx, es)
            ei, ej = es[idx]
            return roots[ei] == roots[ej]

        cache = {}

        def shape(e):
            """(leg rects, floor pieces) of edge e's corridor, cached."""
            if e not in cache:
                rt = route_for(*e)
                cache[e] = (leg_rects(rt), floor_pieces(e[0], e[1], rt))
            return cache[e]

        # Heightfield zones keep the earlier rule: corridors sharing a room may
        # meet anywhere, and a pair whose endpoint Z bands sit more than the
        # clearance apart (matches analyzer.traverse.corridor_conflicts) may
        # pass over one another.
        clearance = max(self.corridor_height + 1.0, 6.0)

        def clash(ea, eb) -> bool:
            """Do the corridors of edges ea and eb overlap where they mustn't?"""
            if self._stack is not None:
                return self._clash_3d(rooms, ea, eb)
            shared = set(ea) & set(eb)
            if not self.corridor_clearance:
                if shared:
                    return False
                za = [rooms[ea[0]].floor_z, rooms[ea[1]].floor_z]
                zb = [rooms[eb[0]].floor_z, rooms[eb[1]].floor_z]
                if (min(za) - clearance > max(zb)
                        or min(zb) - clearance > max(za)):
                    return False
                return overlaps(shape(ea)[0], shape(eb)[0])
            if shared:
                # Corridors from one room meet at its doorway; they conflict
                # only where they overlap beyond it.
                return shared_clash(shape(ea)[1], shape(eb)[1], shared)
            return overlaps(shape(ea)[0], shape(eb)[0])

        def substitute(idx: int, es: List[Tuple[int, int]]):
            """A replacement for bridge es[idx]: the shortest edge joining the
            two halves its removal leaves that crosses no room and clashes with
            no other corridor, or None."""
            roots = components_without(idx, es)
            side = roots[es[idx][0]]
            rest = [e for k, e in enumerate(es) if k != idx]
            cands = sorted(
                ((u, v) for u in range(len(rooms)) if roots[u] == side
                 for v in range(len(rooms)) if roots[v] != side),
                key=lambda e: (rooms[e[0]].center_x - rooms[e[1]].center_x) ** 2
                + (rooms[e[0]].center_y - rooms[e[1]].center_y) ** 2)
            # (Stacked: a stand-in must be clear of every room, its own
            # included, judged in 3D.)
            crossed = ((lambda rs, i, j: self._shape(rs, i, j).blocked)
                       if self._stack is not None else self._crossed_room)
            for e in cands:
                if (crossed(rooms, *e) is None
                        and not any(clash(e, o) for o in rest)):
                    return e
            return None

        # No Z clearance exemption: two corridors whose floors overlap in XY
        # are stacked floors (or intersecting ones) at ANY height difference,
        # and a box build must have one depth band (task 14). Flat floors all
        # sit at 0, so for them this is the same footprint test as before.
        # A conflict between two tree edges (neither can drop) is resolved by
        # swapping one for another edge that rejoins the graph cleanly.
        removed_any = False
        stuck = set()
        safety = (4 * len(edges) + 8 if self.corridor_clearance
                  else len(edges) + 4)
        while safety > 0:
            pair = next(((a, b) for a in range(len(edges))
                         for b in range(a + 1, len(edges))
                         if (edges[a], edges[b]) not in stuck
                         and clash(edges[a], edges[b])), None)
            if pair is None:
                break
            a, b = pair
            if self._stack is not None and self._reroute_stair(rooms, edges, (a, b)):
                # Stacked: a stair moved to another of its routes, clear of
                # every room and corridor; the graph is unchanged.
                safety -= 1
                continue
            if is_removable(a, edges):
                del edges[a]
            elif is_removable(b, edges):
                del edges[b]
            else:
                for k in ((b, a) if self.corridor_clearance else ()):
                    e = substitute(k, edges)
                    if e is not None:
                        edges[k] = e
                        break
                else:
                    stuck.add((edges[a], edges[b]))
                    continue
            safety -= 1
            removed_any = True

        return removed_any

    def _assign_elevation(self, rooms: List[RoomSpec],
                          edges: List[Tuple[int, int]],
                          entrance: int = 0,
                          relations: Optional[Dict[Tuple[int, int], str]] = None
                          ) -> None:
        """
        Step 6: assign floor heights over the graph via BFS from the entrance,
        so connected rooms can sit at different Z and corridors ramp/step
        between them. Height changes propagate along edges (not arbitrarily),
        which keeps elevation coherent rather than random.

        *relations* maps an edge ``(i, j)`` to where room j sits relative to
        room i (design "Vertical relations"); an edge not in it is ``any``:
          - ``any``: the change happens with ``elevation_chance``, up or down
            at random (rng draws: chance, rise, sign; the rise and sign only
            when the chance hits and the rise survives the cap).
          - ``above`` / ``below``: the change always happens, in that
            direction (rng draws: rise only).
          - ``level``: no change (no rng draws).
        The rise is bounded by the run the same way for all of them, so
        ``_relax_elevation`` may still pull a room to keep a loop walkable.
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
                rel = self._relation(relations, cur, nxt)
                z = rooms[cur].floor_z
                if rel == "level":
                    pass
                elif rel != "any" or self.rng.random() < self.elevation_chance:
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
                        if rel == "any":
                            sign = self.rng.choice([1, -1])
                        else:
                            sign = 1 if rel == "above" else -1
                        z += rise * sign
                rooms[nxt].floor_z = z
                q.append(nxt)

        # The BFS caps only TREE edges. A loop (non-tree) edge connects two
        # rooms placed down separate tree paths, so its corridor can still be an
        # unwalkable cliff even though every tree step was capped (seed 4
        # corr_3). Relax the whole graph: pull every room into the walkable Z
        # band of ALL its neighbours until it settles, so every corridor — tree
        # or loop — ends up walkable.
        self._relax_elevation(rooms, adj, entrance)

    @staticmethod
    def _relation(relations: Optional[Dict[Tuple[int, int], str]],
                  i: int, j: int) -> str:
        """Where room j sits relative to room i: the relation of edge (i, j),
        or of (j, i) turned round; ``any`` when neither carries one."""
        if not relations:
            return "any"
        rel = relations.get((i, j))
        if rel is not None:
            return rel
        rel = relations.get((j, i), "any")
        return {"above": "below", "below": "above"}.get(rel, rel)

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
                    cap = self._edge_cap(rooms, i, m)
                    lo = max(lo, rooms[m].floor_z - cap)
                    hi = min(hi, rooms[m].floor_z + cap)
                if self._stack is not None:
                    # Stacked: the room stays in its Level's band.
                    blo, bhi = self._stack.band(i)
                    lo, hi = max(lo, blo), min(hi, bhi)
                if lo <= hi:
                    newz = min(max(rooms[i].floor_z, lo), hi)
                else:
                    # Conflicting neighbours (rare): least-violating midpoint.
                    newz = (lo + hi) / 2
                moved = max(moved, abs(newz - rooms[i].floor_z))
                rooms[i].floor_z = newz
            if moved < 1e-4:
                break
        self._project_elevation(rooms, adj, entrance)

    def _project_elevation(self, rooms: List[RoomSpec], adj, entrance: int,
                           tol: float = 1e-3) -> None:
        """
        Exact fallback for the relax pass. Tight bands (a zero-run Z jog pins
        its two rooms level) can leave the clamp stuck at the conflicting-
        neighbours midpoint, a few hundredths over the cap around a cycle
        (seed 22, 22 rooms, dramatic). When any corridor is still over its cap
        by more than `tol`, replace each floor by the lowest neighbour-reachable
        height, ``min_k(z_k + d(k, i))`` with ``d`` the shortest path over the
        per-corridor caps. That is 1-Lipschitz in ``d``, so every corridor is
        within its cap, and a room already consistent keeps its height. The
        result is shifted so the entrance keeps its floor as the Z reference.
        """
        nodes = list(adj)
        caps = {}
        worst = 0.0
        for i in nodes:
            for m in adj[i]:
                cap = self._edge_cap(rooms, i, m)
                caps[(i, m)] = cap
                worst = max(worst,
                            abs(rooms[i].floor_z - rooms[m].floor_z) - cap)
        if worst <= tol:
            return
        inf = float("inf")
        d = {i: {j: (0.0 if i == j else inf) for j in nodes} for i in nodes}
        for (i, m), cap in caps.items():
            d[i][m] = min(d[i][m], cap)
        for k in nodes:
            dk = d[k]
            for i in nodes:
                dik = d[i][k]
                if dik == inf:
                    continue
                di = d[i]
                for j in nodes:
                    if dik + dk[j] < di[j]:
                        di[j] = dik + dk[j]
        z = {i: rooms[i].floor_z for i in nodes}
        low = {i: min(z[k] + d[k][i] for k in nodes) for i in nodes}
        shift = z[entrance] - low[entrance] if entrance in low else 0.0
        for i in nodes:
            rooms[i].floor_z = low[i] + shift
            if self._stack is not None:
                blo, bhi = self._stack.band(i)
                rooms[i].floor_z = min(max(rooms[i].floor_z, blo), bhi)

    def _fit_floors(self, rooms: List[RoomSpec], edges: List[Tuple[int, int]],
                    entrance: int, envelope: Envelope, passes: int = 4) -> None:
        """
        Move floors into the Envelope's height band. Each room may sit between
        the floor limit and the lowest ceiling over its footprint less its own
        height. The whole layout first shifts by the smallest headroom, so it
        sits as high as it can (nearest the surface, where the Entrance will
        reach it) with every room at or under its band's top and the relative
        heights kept; then rooms are clamped into their bands and the grade
        relax re-run, a few times. Whatever still misses is left for ``fits``
        to reject. (Shifting the entrance to ITS top instead left rooms under
        a lower surface — a hill's flank — above theirs, and the relax pulled
        them back up through the rock: a third of host-hill builds dropped
        rooms.)
        """
        from collections import defaultdict
        bands = []
        for r in rooms:
            top = envelope.ceiling_over(r.center_x - r.width / 2, r.center_y - r.depth / 2,
                                        r.center_x + r.width / 2, r.center_y + r.depth / 2)
            bands.append((envelope.floor_limit, top - r.height))
        shift = min(hi - r.floor_z for r, (_lo, hi) in zip(rooms, bands))
        for r in rooms:
            r.floor_z += shift
        adj = defaultdict(list)
        for i, j in edges:
            adj[i].append(j)
            adj[j].append(i)
        for _ in range(passes):
            for r, (lo, hi) in zip(rooms, bands):
                r.floor_z = min(max(r.floor_z, lo), hi)
            self._relax_elevation(rooms, adj, entrance)

    @staticmethod
    def fits(spec: ZoneSpec, envelope: Envelope) -> bool:
        """Does every room box and corridor swept box lie inside *envelope*?

        A corridor is tested leg by leg (``route_footprint``), each leg's box
        spanning from the lower floor to the higher floor plus its height."""
        for r in spec.rooms:
            if not envelope.contains_box(
                    r.center_x - r.width / 2, r.center_y - r.depth / 2, r.floor_z,
                    r.center_x + r.width / 2, r.center_y + r.depth / 2,
                    r.floor_z + r.height):
                return False
        rooms = {r.id: r for r in spec.rooms}
        for c in spec.corridors:
            z0 = min(c.from_z, c.to_z)
            z1 = max(c.from_z, c.to_z) + c.height
            for x0, y0, x1, y1 in route_footprint(corridor_route(c, rooms), c.width / 2):
                if not envelope.contains_box(x0, y0, z0, x1, y1, z1):
                    return False
        return True

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
        The run length the elevation cap is measured against: the length of
        floor that actually slopes. A Z-corridor's middle leg carries the rise,
        but its two ends lie inside the flat bend squares (a corridor width
        each), so only the stretch between them ramps; a straight corridor
        ramps along its single leg. A jog shorter than a corridor width has no
        ramp at all and its two rooms sit level.
        """
        legs = self._route_legs(a, b)
        if len(legs) >= 3:
            if not self.corridor_clearance:
                return legs[1]   # heightfield zones: the earlier whole-jog cap
            return max(0.0, legs[1] - self.corridor_width)
        return legs[0]

    def _build_corridors(self, spec: ZoneSpec, rooms: List[RoomSpec],
                         edges: List[Tuple[int, int]]) -> None:
        """
        Step 7: a wall-to-wall corridor for each graph edge, ramping/stepping
        where the two rooms differ in height.

        A stacked build takes each corridor from its planned shape
        (``_shape``): an edge across Levels is a planned stair
        (``steps = AUTO_STAIRS``), on facing walls or a U-route.
        """
        if self._stack is not None:
            for k, (i, j) in enumerate(edges):
                cor = dataclasses.replace(self._shape(rooms, i, j).cor, id=f"corr_{k}")
                spec.corridors.append(cor)
                a, b = rooms[i], rooms[j]
                if cor.side:
                    for r in (a, b):
                        if cor.side not in r.open_walls:
                            r.open_walls.append(cor.side)
                else:
                    self._open_facing_walls(a, b)
                    self._open_facing_walls(b, a)
            return
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
    # Stacked builds (step 7): Job B in 3D
    # ------------------------------------------------------------------

    @staticmethod
    def _stack_for(result, rooms: List[RoomSpec]) -> Optional[_Stack]:
        """The build's ``_Stack`` when the engine gave rooms on more than one
        Level, else None (one Level is step 6's Job B, unchanged). The
        floor-to-floor height is the engine's, grown so the tallest room as
        themed still has the Slab over it, plus ``LEVEL_VARIATION``."""
        levels = result.levels
        if levels is None or len(set(levels)) < 2:
            return None
        from .topology.embed import SLAB
        lh = max(result.level_height or 0.0, max(r.height for r in rooms) + SLAB)
        return _Stack(list(levels), lh + LEVEL_VARIATION, LEVEL_VARIATION)

    def _storeys(self, rooms: List[RoomSpec]) -> Optional[list]:
        """Each room's ``embed.Storey`` at its Level's height (None unstacked)."""
        if self._stack is None:
            return None
        from .topology.embed import Storey
        return [Storey(lv, self._stack.base(k), r.height)
                for k, (lv, r) in enumerate(zip(self._stack.levels, rooms))]

    def _is_stair(self, i: int, j: int) -> bool:
        return self._stack is not None and self._stack.levels[i] != self._stack.levels[j]

    def _edge_cap(self, rooms: List[RoomSpec], i: int, m: int) -> float:
        """How far apart the floors of an edge's two rooms may be: its ramp's
        run times ``max_grade``. A stair edge (across Levels) is carried by a
        planned stair at the stair grade (RISER_CAP / TREAD_DEPTH), which
        folds into a Switchback when its leg is short, so any rise its Levels
        ask for fits: its band is unbounded and each room keeps to its own
        Level's band instead (``_Stack.band``)."""
        if self._is_stair(i, m):
            return float("inf")
        return self._elevation_run(rooms[i], rooms[m]) * self.max_grade

    def _assign_stacked_elevation(self, rooms: List[RoomSpec],
                                  edges: List[Tuple[int, int]], entrance: int,
                                  relations: Optional[Dict[Tuple[int, int], str]],
                                  elevation: bool, themed: bool) -> None:
        """Floors of a stacked build: Level x level height, plus a variation
        inside ``_Stack.band`` (the semantic sink/raise, then step 6's random
        rises over the edges within a Level, capped by the run as there). A
        stair edge passes its room's variation on unchanged. Then the relax
        pass, which keeps every room in its band."""
        from collections import defaultdict, deque
        st = self._stack
        half = st.variation / 2
        adj = defaultdict(list)
        for i, j in edges:
            adj[i].append(j)
            adj[j].append(i)
        delta = [min(max(r.floor_z, -half), half) for r in rooms]
        if elevation:
            visited = {entrance}
            q = deque([entrance])
            while q:
                cur = q.popleft()
                for nxt in adj[cur]:
                    if nxt in visited:
                        continue
                    visited.add(nxt)
                    z = delta[cur]
                    rel = self._relation(relations, cur, nxt)
                    if not self._is_stair(cur, nxt) and rel != "level" and (
                            rel != "any" or self.rng.random() < self.elevation_chance):
                        rise = self.rng.uniform(self.step_rise_min, self.step_rise_max)
                        rise = min(rise, self._elevation_run(rooms[cur], rooms[nxt])
                                   * self.max_grade)
                        if rise >= 1.0:
                            z += rise * self.rng.choice([1, -1])
                    delta[nxt] = min(max(z, -half), half)
                    q.append(nxt)
        for k, r in enumerate(rooms):
            r.floor_z = st.base(k) + delta[k]
        if elevation or themed:
            self._relax_elevation(rooms, adj, entrance)

    @staticmethod
    def _z_clear(zlo: float, zhi: float, room: RoomSpec) -> bool:
        """Is a corridor tube from ``zlo`` (its lowest floor) to ``zhi`` (its
        highest ceiling) over or under ``room`` with the Slab between?"""
        from .topology.embed import SLAB
        return (zlo >= room.floor_z + room.height + SLAB - 1e-6
                or zhi + SLAB <= room.floor_z + 1e-6)

    def _facing_cor(self, a: RoomSpec, b: RoomSpec, steps: int) -> CorridorSpec:
        """The step 6 corridor between the facing walls of *a* and *b*."""
        fx, fy = self._wall_point(a, b)
        tx, ty = self._wall_point(b, a)
        return CorridorSpec(id="", from_x=fx, from_y=fy, to_x=tx, to_y=ty,
                            from_z=a.floor_z, to_z=b.floor_z,
                            width=self.corridor_width, height=self.corridor_height,
                            steps=steps, from_room=a.id, to_room=b.id)

    def _u_cor(self, a: RoomSpec, b: RoomSpec, side: str, a_far: bool = True,
               b_far: bool = True) -> Optional[CorridorSpec]:
        """A stair on a U-route out of the walls of *a* and *b* facing *side*,
        each door at one end of its wall: the end away from the other room
        (``*_far``, the middle leg then runs the length of both) or the end
        toward it (the middle leg stays clear of a corridor leaving the far
        part of that wall). None when a wall can't hold the door or the middle
        leg is too short to fold a Switchback."""
        hw = self.corridor_width / 2
        inset = 2.0                      # as _wall_point
        exit_x = side in ("E", "W")
        sign = 1.0 if side in ("N", "E") else -1.0

        def wall(r: RoomSpec) -> float:
            if exit_x:
                return r.center_x + sign * (r.width / 2 - inset)
            return r.center_y + sign * (r.depth / 2 - inset)

        ta, tb = (a.center_y, b.center_y) if exit_x else (a.center_x, b.center_x)
        ha, hb = (a.depth / 2, b.depth / 2) if exit_x else (a.width / 2, b.width / 2)
        reach_a, reach_b = ha - hw - U_DOOR_MARGIN, hb - hw - U_DOOR_MARGIN
        if reach_a < 0 or reach_b < 0:
            return None
        sgn = 1.0 if tb >= ta else -1.0
        da = ta - sgn * reach_a if a_far else ta + sgn * reach_a
        db = tb + sgn * reach_b if b_far else tb - sgn * reach_b
        if abs(db - da) < 2 * hw + 2 * MIN_LANE:
            return None
        (fx, fy), (tx, ty) = (((wall(a), da), (wall(b), db)) if exit_x
                              else ((da, wall(a)), (db, wall(b))))
        return CorridorSpec(id="", from_x=fx, from_y=fy, to_x=tx, to_y=ty,
                            from_z=a.floor_z, to_z=b.floor_z,
                            width=self.corridor_width, height=self.corridor_height,
                            steps=AUTO_STAIRS, from_room=a.id, to_room=b.id,
                            side=side)

    def _stair_candidates(self, rooms: List[RoomSpec], i: int, j: int
                          ) -> List[CorridorSpec]:
        """The ways a stair between rooms i and j (on different Levels) may
        go, in the order tried: between their facing walls when the rooms
        stand a corridor apart on that axis (as separation leaves two rooms
        on one Level), then U-routes on the four sides, the two across the
        pair's offset first (the longest middle legs), each with its doors at
        the far ends of the walls, then the near end of one or both."""
        a, b = rooms[i], rooms[j]
        out = []
        ex = self._exit_axis_x(a, b)
        sep = (abs(b.center_x - a.center_x) - (a.width + b.width) / 2 if ex
               else abs(b.center_y - a.center_y) - (a.depth + b.depth) / 2)
        if sep >= self.corridor_width:
            out.append(self._facing_cor(a, b, AUTO_STAIRS))
        across_x = abs(b.center_x - a.center_x) >= abs(b.center_y - a.center_y)
        sides = ("N", "S", "E", "W") if across_x else ("E", "W", "N", "S")
        for a_far, b_far in ((True, True), (False, True), (True, False), (False, False)):
            for side in sides:
                cor = self._u_cor(a, b, side, a_far, b_far)
                if cor is not None:
                    out.append(cor)
        return out

    def _make_shape(self, rooms: List[RoomSpec], i: int, j: int,
                    cor: CorridorSpec) -> _Shape:
        """``cor``'s planned floor as pieces, and the first room it passes
        through without the Slab's clearance. A stair is judged against its
        own two rooms too (only its end stubs may enter them, through their
        doors); a corridor within a Level only against third rooms, as
        ``_crossed_room``. A stair the builder can't fold (``cramped``) is
        blocked by its own first room."""
        by_id = {r.id: r for r in rooms}
        route = corridor_route(cor, by_id)
        wps = list(route.waypoints)
        n = len(wps) - 1
        zs, _carry = MeshBuilder._waypoint_zs(
            wps, None if route.carry < 0 else route.carry, cor.from_z, cor.to_z)
        hw, H = cor.width / 2, cor.height
        z_kind = route.kind == "z"
        pieces = []
        for k in range(n):
            (x0, y0), (x1, y1) = wps[k], wps[k + 1]
            pin = (i if k == 0 else j if k == n - 1 else None) if z_kind else None
            pieces.append(((min(x0, x1) - hw, min(y0, y1) - hw,
                            max(x0, x1) + hw, max(y0, y1) + hw),
                           min(zs[k], zs[k + 1]), max(zs[k], zs[k + 1]) + H, pin))
        for w in range(1, n):
            cx, cy = wps[w]
            pin = (i if w == 1 else j if w == n - 1 else None) if z_kind else None
            pieces.append(((cx - hw, cy - hw, cx + hw, cy + hw), zs[w], zs[w] + H, pin))
        stair = cor.steps < 0
        if stair:
            lay = stair_layout(cor, by_id)
            if lay is None or lay.cramped:
                return _Shape(cor, route, pieces, i)
            if lay.stairwell is not None:
                pieces.append((lay.stairwell, min(cor.from_z, cor.to_z),
                               max(cor.from_z, cor.to_z) + H, None))
        blocked = None
        for k, r in enumerate(rooms):
            own = k in (i, j)
            if own and not stair:
                continue
            rx0, ry0 = r.center_x - r.width / 2, r.center_y - r.depth / 2
            rx1, ry1 = r.center_x + r.width / 2, r.center_y + r.depth / 2
            for p, ((x0, y0, x1, y1), zlo, zhi, _pin) in enumerate(pieces):
                if own and ((k == i and p == 0) or (k == j and p == n - 1)):
                    continue
                if (min(x1, rx1) - max(x0, rx0) > _TOUCH
                        and min(y1, ry1) - max(y0, ry0) > _TOUCH
                        and not self._z_clear(zlo, zhi, r)):
                    blocked = k
                    break
            if blocked is not None:
                break
        return _Shape(cor, route, pieces, blocked)

    def _shape(self, rooms: List[RoomSpec], i: int, j: int) -> _Shape:
        """Edge i-j's planned corridor on a stacked build (cached until the
        floors move). Within a Level it is step 6's facing-wall corridor; an
        edge across Levels is a planned stair on the first candidate route
        (``_stair_candidates``) that is clear of every room, its Switchback's
        stairwell included, else the first one only a third room blocks (the
        crossing split can route round that room), else the first."""
        key = (i, j)
        if key in self._shapes:
            return self._shapes[key]
        a, b = rooms[i], rooms[j]
        if not self._is_stair(i, j):
            shape = self._make_shape(rooms, i, j, self._facing_cor(a, b, 0))
        else:
            shapes = [self._make_shape(rooms, i, j, c)
                      for c in self._stair_candidates(rooms, i, j)]
            pick = self._stair_route.get(key)
            if pick is not None and pick < len(shapes) and shapes[pick].blocked is None:
                shapes.insert(0, shapes.pop(pick))
            shape = (next((s for s in shapes if s.blocked is None), None)
                     or next((s for s in shapes if s.blocked not in (i, j)), None)
                     or (shapes[0] if shapes else None))
            if shape is None:
                shape = self._make_shape(rooms, i, j, self._facing_cor(a, b, AUTO_STAIRS))
                shape = shape._replace(blocked=i)
        self._shapes[key] = shape
        return shape

    def _reroute_stair(self, rooms: List[RoomSpec], edges: List[Tuple[int, int]],
                       pair: Tuple[int, int]) -> bool:
        """Two corridors clash: move whichever of them is a stair to another
        of its routes that is clear of every room and clashes with no other
        corridor. False when neither can move."""
        for idx in pair:
            i, j = edges[idx]
            if not self._is_stair(i, j):
                continue
            old = self._shapes.get((i, j))
            for n, cor in enumerate(self._stair_candidates(rooms, i, j)):
                shape = self._make_shape(rooms, i, j, cor)
                if shape.blocked is not None:
                    continue
                self._shapes[(i, j)] = shape
                if not any(self._clash_3d(rooms, (i, j), e)
                           for k, e in enumerate(edges) if k != idx):
                    self._stair_route[(i, j)] = n
                    return True
            if old is not None:
                self._shapes[(i, j)] = old
            else:
                self._shapes.pop((i, j), None)
        return False

    def _crossed_room_3d(self, rooms: List[RoomSpec], i: int, j: int
                         ) -> Optional[int]:
        """``_crossed_room`` on a stacked build: the third room edge i-j's
        planned corridor passes through without the Slab's clearance, or
        None. A stair no route can place clear of its own rooms can't be
        split; it is kept and reported in ``warnings`` (``stair_unplaced``)."""
        blocked = self._shape(rooms, i, j).blocked
        if blocked is None:
            return None
        if blocked in (i, j):
            note = f"stair_unplaced: {rooms[i].id}-{rooms[j].id}"
            if note not in self.warnings:
                self.warnings.append(note)
            return None
        return blocked

    def _clash_3d(self, rooms: List[RoomSpec], ea: Tuple[int, int],
                  eb: Tuple[int, int]) -> bool:
        """Do the planned corridors of edges ea and eb overlap without the
        clearance between them? Two from the same room may share its doorway
        stub and bend (``_resolve_conflicts``); stairwells count as floor.

        The clearance between two tubes is the Slab, but at least a corridor
        height + 1: the gate (``analyzer.traverse.corridor_conflicts``, design
        decision 16) wants that much between two floors, and it reads a
        tube's ceiling with its floor (the walk surface takes ceilings as
        floor), so it measures from the lower tube's ceiling."""
        from .topology.embed import SLAB
        shared = set(ea) & set(eb)
        sa, sb = self._shape(rooms, *ea), self._shape(rooms, *eb)
        clear = max(SLAB, min(sa.cor.height, sb.cor.height) + 1.0)
        pa, pb = sa.pieces, sb.pieces
        for (ra, za0, za1, ka) in pa:
            for (rb, zb0, zb1, kb) in pb:
                if ka is not None and ka == kb and ka in shared:
                    continue
                if (min(ra[2], rb[2]) - max(ra[0], rb[0]) > _TOUCH
                        and min(ra[3], rb[3]) - max(ra[1], rb[1]) > _TOUCH
                        and zb0 - za1 < clear and za0 - zb1 < clear):
                    return True
        return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _match_corridors_to_rooms(spec: ZoneSpec, shared: Dict[str, str]) -> None:
        """Hallways match the rooms they join (interesting textures task 9):
        each corridor takes its floor and wall material from the room it
        leaves, or the room it enters when that one is themed and the first
        isn't. Rooms the layout inserted at crossings (no theme of their own)
        then take their corridors' material. Shared materials nothing uses
        any more are dropped, so no unused texture is packed."""
        rooms = {r.id: r for r in spec.rooms}

        def themed(part) -> bool:
            return part.floor_material != shared.get("floor")

        for cor in spec.corridors:
            ends = [rooms.get(cor.from_room), rooms.get(cor.to_room)]
            src = next((r for r in ends if r is not None and themed(r)), None)
            if src is not None:
                cor.floor_material = src.floor_material
                cor.wall_material = src.wall_material
        for room in spec.rooms:
            if themed(room):
                continue
            src = next((c for c in spec.corridors if themed(c)
                        and room.id in (c.from_room, c.to_room)), None)
            if src is not None:
                room.floor_material = src.floor_material
                room.wall_material = src.wall_material

        used = {m for part in (*spec.rooms, *spec.corridors)
                for m in (part.floor_material, part.wall_material, part.ceiling_material)}
        for name in list(shared.values()):
            if name not in used:
                spec.materials.pop(name, None)

    def _add_default_materials(self, spec: ZoneSpec, race: str = "") -> Dict[str, str]:
        """Register the shared floor/wall/ceiling materials under their
        Material_Names (``<race>_dungeon_wall``, ``city_floor``…) and return
        the map from bare surface to that name."""
        theme_palettes = {
            "dungeon": {
                "floor":   ((95, 88, 80),  "worn dungeon flagstone, dark grime in joints"),
                "wall":    ((110, 100, 92),"rough hewn stone blocks, medieval, faint moss"),
                "ceiling": ((60, 56, 52),  "dark rough rock cave ceiling"),
            },
            "wilderness": {
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
        palette = theme_palettes.get(self.zone_type, theme_palettes["dungeon"])
        # The measured profiles list "<fixed-function>" (the pre-shader .s3d
        # era), which isn't a shader the client knows (Req 2.1).
        shaders = self.profile.get("materials", {}).get("shaders", [])
        default_shader = (shaders[0] if shaders and shaders[0].endswith(".fx")
                          else SHADER_OPAQUE)

        tex_set = semantics.texture_set(self.zone_type, race)
        shared: Dict[str, str] = {}
        for surface, (color, desc) in palette.items():
            name = semantics.material_name(tex_set, surface)
            spec.add_material(name, f"{name}.dds", shader=default_shader,
                              color=color, description=desc)
            shared[surface] = name
        return shared

    def _add_room_lights(self, spec: ZoneSpec, room: RoomSpec, idx: int) -> None:
        # Theme-appropriate base light colour
        colors = {
            "dungeon": (1.0, 0.55, 0.15),   # torch orange
            "wilderness": (1.0, 0.95, 0.85),   # daylight
            "city":    (1.0, 0.85, 0.6),    # warm lantern
        }
        r, g, b = colors.get(self.zone_type, (1.0, 0.6, 0.2))

        # Pacing-driven mood: deeper rooms are dimmer and cooler (more
        # ominous), the entrance is brightest, the climax gets a slightly
        # intensified/charged light. Wilderness zones keep daylight (depth
        # doesn't darken the sky).
        intensity = 1.0
        if self.zone_type != "wilderness":
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
