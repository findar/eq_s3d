"""
generators/layout_engine.py
---------------------------
The Layout_Engine seam (graph-layout design "The seam"): the room-and-graph
step ("Job A") behind one interface, so a new engine can be added without
touching what comes after it ("Job B": pacing, themes, elevation, crossings,
conflicts, Envelope fit, corridors, gating; all in ``generators/layout.py``).

An engine gets a ``LayoutContext`` (the generator's rng, the room band, a
``separate`` callback and the build's description) and returns an
``EngineResult``: rooms in the plane, the graph's edges, and optionally an
entry point, a climax room and a record for the sidecar. Engines never see the
``LayoutGenerator``, so they can be tested alone.

``GraphEngine`` grows the graph by a rule set (``generators/topology``) and
places it with the set's placement (``generators/topology/embed.py``).

``ClassicEngine`` is the TinyKeep scheme that used to live in ``layout.py``
(scatter in an ellipse, separate, Delaunay, MST + ~12 % loop edges). It draws
from ``ctx.rng`` in exactly the order it did there; ``tests/test_layout_engine.py``
pins that byte for byte.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace
from pathlib import Path
from typing import (TYPE_CHECKING, Callable, Dict, List, NamedTuple, Optional,
                    Protocol, Tuple, Type, Union)

from .envelope import Envelope
from .zone_spec import RoomSpec

if TYPE_CHECKING:
    from .topology.rewrite import BuildContext
    from .topology.ruleset import RuleSet


def __getattr__(name: str):
    """``BuildContext`` is the topology package's (one class for the seam and
    the rule sets' ``when`` conditions; it has ``.get`` for them). Imported on
    first use: ``generators.topology`` reads ``ai.schema``, and ``ai`` imports
    ``generators.layout``, which imports this module."""
    if name == "BuildContext":
        from .topology.rewrite import BuildContext
        return BuildContext
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

Point = Tuple[float, float]

# Vertical relations an edge may carry (design "Vertical relations"). The
# relation says where the edge's SECOND room sits relative to its first:
# ``Edge(i, j, "above")`` puts room j's floor above room i's.
RELATIONS = ("any", "above", "below", "level")


class Edge(NamedTuple):
    """A graph edge between rooms ``i`` and ``j``, with a vertical relation.

    Job B works on plain ``(i, j)`` pairs (it splits and swaps edges, and
    keys corridors by pair); ``LayoutGenerator`` takes the relations off at
    the seam and hands them to the elevation pass alone."""
    i: int
    j: int
    rel: str = "any"


@dataclass
class LayoutContext:
    """Everything an engine may use from the generator."""
    rng: random.Random
    room_min: float                      # classic room side spread (after _apply_room_scale)
    room_max: float
    ceiling: float                       # classic room height
    corridor_width: float
    separate: Callable[[List[RoomSpec]], None]   # LayoutGenerator._separate_rooms
    build: BuildContext
    # The plan's Size control as a shift of the rooms' position in the race's
    # bands (``semantics.SIZE_SHIFT``); the graph engine sizes its classes
    # with it, the classic band (room_min/room_max/ceiling) already has it.
    size_shift: float = 0.0


@dataclass
class EngineResult:
    rooms: List[RoomSpec]
    edges: List[Edge]
    entry: Optional[Point] = None        # the graph's entrance room centre
    climax: Optional[int] = None         # the room the engine names the climax
                                         # (an index into rooms); None: deepest by hops
    record: Optional[dict] = None        # what the sidecar's layout block reports
    # Step 7 (task 4): each room's Level (index-aligned with ``rooms``; 0 is the
    # entrance's) and the floor-to-floor height between Levels, from an engine
    # that stacks. None: one Level, Job B places every floor as in step 6.
    levels: Optional[List[int]] = None
    level_height: Optional[float] = None


class LayoutEngine(Protocol):
    name: str
    sizes_rooms: bool                    # True: Job B's role bias leaves sizes alone

    def generate(self, ctx: LayoutContext, room_count: int,
                 envelope: Optional[Envelope]) -> EngineResult: ...


class ClassicEngine:
    """TinyKeep: scatter → separate → Delaunay → MST + a few loop edges."""

    name = "classic"
    sizes_rooms = False

    def generate(self, ctx: LayoutContext, room_count: int,
                 envelope: Optional[Envelope]) -> EngineResult:
        rooms = self._scatter_rooms(ctx, room_count, envelope)
        ctx.separate(rooms)
        edges = [Edge(i, j) for i, j in self._connect_rooms(ctx, rooms)]
        return EngineResult(rooms=rooms, edges=edges)

    def _scatter_rooms(self, ctx: LayoutContext, room_count: int,
                       envelope: Optional[Envelope] = None) -> List[RoomSpec]:
        """
        Scatter rooms inside an ellipse. Sizes drawn from a normal
        distribution around the theme's room scale so a few rooms are large
        (hubs) and most are smaller (connective), à la TinyKeep. With an
        Envelope the ellipse is centred on its footprint and no wider than it.
        """
        mean_side = (ctx.room_min + ctx.room_max) / 2
        std_side = (ctx.room_max - ctx.room_min) / 3
        # Ellipse radius grows with room count so rooms have space to separate.
        spread = mean_side * (0.8 + 0.5 * room_count)
        ox = oy = 0.0
        if envelope is not None:
            spread = min(spread, 2.0 * max(0.0, envelope.inradius - mean_side / 2))
            ox, oy = envelope.centre

        rooms: List[RoomSpec] = []
        for i in range(room_count):
            # Random point in an ellipse (slightly wider than tall for a
            # natural footprint ratio).
            px, py = self._rand_in_ellipse(ctx.rng, spread, spread * 0.75)
            w = max(ctx.room_min * 0.6, ctx.rng.gauss(mean_side, std_side))
            d = max(ctx.room_min * 0.6, ctx.rng.gauss(mean_side, std_side))
            rooms.append(RoomSpec(
                id=f"room_{i}",
                center_x=px + ox, center_y=py + oy, floor_z=0.0,
                width=w, depth=d, height=ctx.ceiling,
            ))
        return rooms

    @staticmethod
    def _rand_in_ellipse(rng: random.Random, rx: float, ry: float) -> Point:
        t = 2 * math.pi * rng.random()
        u = rng.random() + rng.random()
        r = (2 - u) if u > 1 else u
        return rx * r * math.cos(t) / 2, ry * r * math.sin(t) / 2

    def _connect_rooms(self, ctx: LayoutContext,
                       rooms: List[RoomSpec]) -> List[Tuple[int, int]]:
        """
        Build a connection graph via Delaunay triangulation, reduce it to a
        minimum spanning tree (guarantees reachability, mostly tree-shaped),
        then add back a few edges to create loops/alternate paths. Returns a
        list of (i, j) room-index edges.
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
        ctx.rng.shuffle(extra)
        n_add = max(0, int(len(extra) * 0.12))
        mst.extend(extra[:n_add])
        return mst

    @staticmethod
    def _delaunay_edges(pts: List[Point]) -> List[Tuple[int, int]]:
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


# Rule sets ship here (rules/topology/: base sets, layers/, themes.toml).
RULES_DIR = Path(__file__).resolve().parent.parent / "rules" / "topology"


def is_vertical(rule) -> bool:
    """A vertical rule (design "Rule format"): its replacement has an
    ``above`` / ``below`` edge."""
    return any(e.rel in ("above", "below") for e in rule.edges)


def scale_vertical(rule_set: "RuleSet", factor: float) -> "RuleSet":
    """*rule_set* with every vertical rule's recipe weight times *factor*; a
    weight of 0 takes the rule out of its stages. Factor 1 is the set as is."""
    if factor == 1.0:
        return rule_set
    vertical = {name for name, r in rule_set.rules.items() if is_vertical(r)}
    recipe = tuple(
        replace(stage, apply={k: w * factor if k in vertical else w
                              for k, w in stage.apply.items()
                              if not (k in vertical and w * factor <= 0)})
        for stage in rule_set.recipe)
    return replace(rule_set, recipe=recipe)


class GraphEngine:
    """Graph rewriting (design "Placement"): a rule set grows a Topology_Graph
    of exactly n rooms, its placement lays the rooms out, and each grammar
    edge becomes an edge with its vertical relation.

    ``rule_set`` is a loaded ``RuleSet`` (used as is) or a base set's name
    (the theme's layers still apply when they fit it); ``theme`` overrides
    the build's dungeon theme. With neither, the set comes from
    ``ctx.build.theme`` through ``rules/topology/themes.toml``.

    Two options for a placement inside an Envelope (the outdoor dungeon sets
    them per attempt; an Envelope-free layout ignores both):
    ``facing`` picks which of ``embed.face_entry``'s ranked turns/mirrors
    faces the entrance room toward the way in (0 the best; ``facings`` of
    them), and ``entrance_side`` is the least width and depth of the rules'
    entrance room (the wall facing the way in has to hold a Tunnel), whatever
    the zone's room scale.

    ``stacking`` (step 7, task 4; off by default) gives the rooms Levels from
    the rules' vertical relations (``embed.assign_levels``) and places them
    in 3D: rooms on different Levels may overlap in plan, stair edges pull
    together, and separation runs within each Level. The result then carries
    ``levels`` and ``level_height``. Vertical rules need Levels (task 6):
    with stacking off the set's vertical rules are left out
    (``scale_vertical`` x 0, the Verticality control's ``flat``), so every
    room is on one Level; with it on their weights are times
    ``vertical_weight`` (``moderate`` 1, ``dramatic`` 2; ``ai/expand.py``).
    An explicit ``vertical_weight`` applies with stacking off too (the
    outdoor dungeon keeps them as ramp hints at ``flat``).
    A build with one Level is the same with stacking on or off.

    ``descend`` (step 7 task 7, the outdoor dungeon: its Tunnel enters at the
    top Level, and it should use more than one) keeps every Level at or
    below the entrance's. The graph is grown again, up to
    ``DESCEND_TRIES`` times in all, until its Levels go one way only and
    there are at least two; one whose Levels all go up is turned over
    (every Level negated and every edge's relation flipped: towers become
    cellars). Out of tries, the first one-way graph is kept (else the last,
    turned the way most of it goes with the rest pulled up to the
    entrance's Level), and a graph on one Level puts its deep end (the
    ``deep`` room, else the last room placed) a Level down.
    """

    name = "graph"
    sizes_rooms = True
    facings = 8              # len(embed.FACINGS)
    facing: int = 0
    entrance_side: float = 0.0
    DESCEND_TRIES = 8

    def __init__(self, rule_set: Union[str, "RuleSet", None] = None,
                 theme: Optional[str] = None,
                 rules_dir: Union[str, Path, None] = None, stacking: bool = False,
                 vertical_weight: Optional[float] = None, descend: bool = False):
        self.rule_set = rule_set
        self.stacking = stacking
        self.vertical_weight = vertical_weight
        self.descend = descend
        self.theme = theme
        self.rules_dir = Path(rules_dir) if rules_dir is not None else RULES_DIR
        self._loaded: Dict[Tuple[Optional[str], Optional[str]], "RuleSet"] = {}

    def rules_for(self, theme: Optional[str]) -> "RuleSet":
        from .topology.ruleset import RuleSet, load_for_theme
        if isinstance(self.rule_set, RuleSet):
            return self.rule_set
        theme = self.theme if self.theme is not None else theme
        key = (theme or None, self.rule_set or None)
        if key not in self._loaded:
            self._loaded[key] = load_for_theme(self.rules_dir, theme, self.rule_set or None)
        return self._loaded[key]

    def generate(self, ctx: LayoutContext, room_count: int,
                 envelope: Optional[Envelope]) -> EngineResult:
        from .topology import embed
        from .topology.rewrite import grow

        weight = self.vertical_weight
        if weight is None:
            weight = 1.0 if self.stacking else 0.0
        rs = scale_vertical(self.rules_for(ctx.build.theme), weight)
        if room_count < 1:
            return EngineResult(rooms=[], edges=[], record=self._record(rs, None, [], {}, []))
        grown = grow(rs, room_count, rng=ctx.rng, context=ctx.build)
        flip = False
        if self.stacking and self.descend:
            grown = self._descending(rs, room_count, ctx, grown)
            lv = embed.assign_levels(grown.graph).values()
            flip = max(lv) > -min(lv)
        graph = grown.graph
        order = embed.bfs_order(graph)
        # Rooms are placed at their final size: each class's point in the
        # race's bands (step 7 task 17), before placement, and nothing scales
        # them again (step 6 task 20: scaled after placement, the rooms pushed
        # into each other, re-separation moved them onto shared walls and Job
        # B split or dropped the loops).
        race = ctx.build.race or ""
        sizes = {r: embed.room_size(graph.node(r).size, race, ctx.rng, ctx.size_shift)
                 for r in order}
        entrance = next((n.id for n in graph.rooms() if n.kind == "entrance"), None)
        if envelope is not None and entrance is not None and self.entrance_side > 0:
            w, d, h = sizes[entrance]
            sizes[entrance] = (max(w, self.entrance_side), max(d, self.entrance_side), h)
        half = {r: (w / 2, d / 2) for r, (w, d, _h) in sizes.items()}
        place = embed.PLACEMENT_FUNCS[rs.placement]
        gap = ctx.corridor_width + 1.0
        # Levels go in before placement (step 7): heights as the rooms are
        # placed.
        levels = level_h = storeys = None
        if self.stacking:
            levels = embed.assign_levels(graph)
            if flip:
                levels = {r: -lv for r, lv in levels.items()}
            if self.descend:
                levels = {r: min(lv, 0) for r, lv in levels.items()}
                if len(set(levels.values())) == 1 and len(order) > 1:
                    deep = next((n.id for n in graph.rooms() if n.kind == "deep"), order[-1])
                    if deep == entrance:
                        deep = order[-1]
                    levels[deep] = -1
            heights = {r: sizes[r][2] for r in order}
            level_h = embed.level_height(list(heights.values()))
            storeys = embed.storeys(levels, heights, level_h)
            centres = place(graph, order, half, ctx.corridor_width, gap, storeys=storeys)
        else:
            centres = place(graph, order, half, ctx.corridor_width, gap)
        if envelope is not None:
            # Face the rules' entrance room toward the Envelope's way in (a
            # quarter turn / mirror of the whole layout), so the pacing's
            # entrance, the room nearest the way in, is that room.
            centres, half, swapped = embed.face_entry(centres, half, envelope, entrance,
                                                      rank=self.facing)
            if swapped:
                sizes = {r: (d, w, h) for r, (w, d, h) in sizes.items()}

        rooms: List[RoomSpec] = []
        for k, r in enumerate(order):
            w, d, h = sizes[r]
            x, y = centres[r]
            rooms.append(RoomSpec(id=f"room_{k}", center_x=x, center_y=y, floor_z=0.0,
                                  width=w, depth=d, height=h,
                                  district=graph.node(r).district,
                                  kind=graph.node(r).kind))
        # (Separation pushes pairs symmetrically, so an Envelope layout stays
        # centred on the footprint.) Stacked, each Level separates on its own:
        # ``ctx.separate`` (Job B's ``_separate_rooms``) is a plan test, and
        # rooms on different Levels may overlap.
        if levels is None:
            ctx.separate(rooms)
        else:
            for lv in sorted({levels[r] for r in order}):
                ctx.separate([rooms[k] for k, r in enumerate(order) if levels[r] == lv])

        idx = {r: k for k, r in enumerate(order)}
        edges: List[Edge] = []
        for e in graph.edges():
            i, j = idx[e.a], idx[e.b]
            # graph.edge(a, b).rel says where b sits relative to a, as Edge does.
            rel = graph.edge(e.a, e.b).rel
            if flip:
                rel = _FLIP_REL.get(rel, rel)
            edges.append(Edge(i, j, rel))
        entrance = next((idx[n.id] for n in graph.rooms() if n.kind == "entrance"), 0)
        entry = (rooms[entrance].center_x, rooms[entrance].center_y)
        # The rules' deep end is the climax (None when the set grew none, as
        # for one room: pacing then takes the deepest by hops).
        climax = next((idx[n.id] for n in graph.rooms() if n.kind == "deep"), None)
        record = self._record(rs, grown, order, idx, edges, graph, rooms)
        room_levels = None
        if levels is not None:
            room_levels = [levels[r] for r in order]
            record["levels"] = {rooms[k].id: lv for k, lv in enumerate(room_levels)}
            record["level_height"] = level_h
        return EngineResult(rooms=rooms, edges=edges, entry=entry, climax=climax,
                            record=record, levels=room_levels, level_height=level_h)

    def _descending(self, rs, room_count: int, ctx: LayoutContext, grown):
        """``grown``, or a graph grown again (``descend``): the first whose
        Levels go one way from the entrance and number at least two, within
        ``DESCEND_TRIES`` graphs in all; else the first one-way graph; else
        the last."""
        from .topology import embed
        from .topology.rewrite import grow

        fallback = None
        for k in range(self.DESCEND_TRIES):
            if k:
                grown = grow(rs, room_count, rng=ctx.rng, context=ctx.build)
            lv = list(embed.assign_levels(grown.graph).values())
            if min(lv) >= 0 or max(lv) <= 0:
                if min(lv) < max(lv):
                    return grown
                fallback = fallback or grown
        return fallback or grown

    @staticmethod
    def _record(rs, grown, order, idx, edges, graph=None, rooms=None) -> dict:
        rec = {
            "engine": "graph",
            "rule_set": rs.name,
            "layers": list(rs.layers),
            "placement": rs.placement,
            "applied": [[a.stage, a.rule] for a in grown.applied] if grown else [],
            "rooms": {},
            "edges": [],
        }
        if graph is not None:
            for r in order:
                n = graph.node(r)
                rec["rooms"][rooms[idx[r]].id] = {
                    "kind": n.kind, "size": n.size, "district": n.district, "node": r}
            rec["edges"] = [[rooms[e.i].id, rooms[e.j].id, e.rel] for e in edges]
        return rec


# A relation read the other way up (``GraphEngine.descend`` turning a graph over).
_FLIP_REL = {"above": "below", "below": "above"}


# The one place engine names map to engines.
ENGINES: Dict[str, Type[LayoutEngine]] = {"classic": ClassicEngine, "graph": GraphEngine}
