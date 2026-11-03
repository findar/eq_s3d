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
entry point and a record for the sidecar. Engines never see the
``LayoutGenerator``, so they can be tested alone.

``ClassicEngine`` is the TinyKeep scheme that used to live in ``layout.py``
(scatter in an ellipse, separate, Delaunay, MST + ~12 % loop edges). It draws
from ``ctx.rng`` in exactly the order it did there; ``tests/test_layout_engine.py``
pins that byte for byte.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import (Callable, Dict, List, NamedTuple, Optional, Protocol,
                    Tuple, Type)

from .envelope import Envelope
from .zone_spec import RoomSpec

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
class BuildContext:
    """What is being built, for engines whose choices depend on it."""
    zone_type: str
    theme: str = ""
    race: str = ""
    race_scale: float = 1.0
    room_count: int = 0


@dataclass
class LayoutContext:
    """Everything an engine may use from the generator."""
    rng: random.Random
    room_min: float                      # room side band (after _apply_room_scale)
    room_max: float
    ceiling: float
    corridor_width: float
    separate: Callable[[List[RoomSpec]], None]   # LayoutGenerator._separate_rooms
    build: BuildContext


@dataclass
class EngineResult:
    rooms: List[RoomSpec]
    edges: List[Edge]
    entry: Optional[Point] = None        # the graph's entrance room centre
    record: Optional[dict] = None        # what the sidecar's layout block reports


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


# The one place engine names map to engines.
ENGINES: Dict[str, Type[LayoutEngine]] = {"classic": ClassicEngine}
