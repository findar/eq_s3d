"""
generators/topology/embed.py
----------------------------
Placing a grown Topology_Graph in the plane (roadmap step 6, Requirement 6;
design "Size classes" and "Placement").

Three parts:

- :func:`room_size` turns a node's Size_Class into a footprint and height:
  the zone type's base side (area-matched over the graph's classes,
  :func:`area_matched_base`) times the class multiplier, with the classic
  engine's spread (within 15 %), and the ceiling times the class's height
  multiplier. The race scale comes later, in ``semantics``, as for classic
  rooms.
- :data:`PLACEMENT_FUNCS`, the Placement registry: a rule set names its
  placement (``[set] placement``), the checker reads the names from
  ``ruleset.PLACEMENTS`` and this module registers the callables under the
  same names. A placement module may extend both
  (``ruleset.PLACEMENTS += ("maze",)``; ``PLACEMENT_FUNCS["maze"] = ...``).
  ``ruleset`` never imports this module, so there is no cycle.
- :func:`spring`, the one step 6 placement: a breadth-first start beside each
  room's first placed neighbour on a free wall side, spring iterations, then
  the layout's own separation (``ctx.separate``) and the Envelope's centring.

Every pair test goes through :func:`may_overlap_in_plan` (always False in
step 6: no room sits over another). Step 7's stacking changes that function
alone.

Nothing here draws from the rng except :func:`room_size`; the spring layout is
a fixed number of fixed-size steps, so the same graph and sizes always give
the same positions.
"""

from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from generators.topology.graph import ENTRANCE, Node, TopologyGraph
from generators.topology import ruleset as _ruleset

Point = Tuple[float, float]

# ---------------------------------------------------------------------------
# Size classes (design "Size classes")
# ---------------------------------------------------------------------------

#: Size_Class -> (footprint multiplier, height multiplier).
SIZE_SCALE: Dict[str, Tuple[float, float]] = {
    "tiny": (0.5, 0.8),
    "small": (0.75, 0.9),
    "medium": (1.0, 1.0),
    "large": (1.4, 1.2),
    "huge": (1.9, 1.5),
}
#: The classic engine's spread around the class side: a gaussian factor on
#: each axis, clamped to 1 +- SPREAD.
SPREAD = 0.15
_SPREAD_SIGMA = SPREAD / 2


def base_side(room_min: float, room_max: float) -> float:
    """The zone type's base room side for the requested count."""
    return (room_min + room_max) / 2


def area_matched_base(base: float, sizes: Sequence[Optional[str]]) -> float:
    """The class base side that gives these rooms the floor area as many
    classic rooms of side ``base`` would have: ``base`` over the RMS footprint
    multiplier. ``_apply_room_scale`` sizes rooms so the zone's floor matches
    the measured profile; the classes share that floor out instead of adding
    to it (a classic_eq mix averages 1.5x medium's area otherwise, and grown
    rooms fit an Envelope far worse than classic ones)."""
    if not sizes:
        return base
    mean_sq = sum(SIZE_SCALE.get(z or "medium", SIZE_SCALE["medium"])[0] ** 2
                  for z in sizes) / len(sizes)
    return base / math.sqrt(mean_sq)


def room_size(size: Optional[str], base: float, ceiling: float,
              rng) -> Tuple[float, float, float]:
    """(width, depth, height) of a room of Size_Class ``size``.

    Two rng draws (width, then depth). An unknown or missing class is medium.
    """
    foot, tall = SIZE_SCALE.get(size or "medium", SIZE_SCALE["medium"])
    side = base * foot
    w = side * min(1 + SPREAD, max(1 - SPREAD, rng.gauss(1.0, _SPREAD_SIGMA)))
    d = side * min(1 + SPREAD, max(1 - SPREAD, rng.gauss(1.0, _SPREAD_SIGMA)))
    return w, d, ceiling * tall


# ---------------------------------------------------------------------------
# The plan predicate (step 7 changes only this)
# ---------------------------------------------------------------------------

def may_overlap_in_plan(a: Node, b: Node) -> bool:
    """May rooms ``a`` and ``b`` overlap in plan (one above the other)?

    Always False in step 6: every pair of footprints stays apart.
    """
    return False


# ---------------------------------------------------------------------------
# Order and sides
# ---------------------------------------------------------------------------

def bfs_order(graph: TopologyGraph) -> List[str]:
    """Room ids breadth-first from the entrance (sorted neighbours), then any
    room it can't reach in id order (a grown graph is connected, so none)."""
    rooms = [n.id for n in graph.rooms()]
    if not rooms:
        return []
    start = next((n.id for n in graph.rooms() if n.kind == ENTRANCE), rooms[0])
    order = list(graph.distances(start, rooms_only=True))
    seen = set(order)
    order += [r for r in rooms if r not in seen]
    return order


# Wall sides as unit directions, in tie-break order (finding 1: one opening
# per wall side, so a room's neighbours want distinct sides).
SIDES: Tuple[Tuple[str, Point], ...] = (
    ("E", (1.0, 0.0)), ("N", (0.0, 1.0)), ("W", (-1.0, 0.0)), ("S", (0.0, -1.0)))
_OPPOSITE = {"E": "W", "W": "E", "N": "S", "S": "N"}


def _side_toward(pa: Point, ha: Point, pb: Point, hb: Point) -> str:
    """The wall of box a that faces box b, by the axis they're most separated
    on (as ``routing.exit_axis_x`` picks it)."""
    dx, dy = pb[0] - pa[0], pb[1] - pa[1]
    gx = abs(dx) - (ha[0] + hb[0])
    gy = abs(dy) - (ha[1] + hb[1])
    if gx >= gy:
        return "E" if dx >= 0 else "W"
    return "N" if dy >= 0 else "S"


def _box_gap(pa: Point, ha: Point, pb: Point, hb: Point) -> float:
    """Chebyshev gap between two boxes (negative when they overlap)."""
    return max(abs(pb[0] - pa[0]) - (ha[0] + hb[0]),
               abs(pb[1] - pa[1]) - (ha[1] + hb[1]))


# ---------------------------------------------------------------------------
# spring
# ---------------------------------------------------------------------------

#: Spring layout constants (task 8). One corridor run is RUN_FACTOR corridor
#: widths; edges rest at the two rooms' extents along the edge plus one run;
#: unjoined rooms repel inside REPEL_RUNS runs of each other.
RUN_FACTOR = 2.0
REPEL_RUNS = 1.5
ITERATIONS = 300
STEP_START = 0.5
STEP_END = 0.05
K_SPRING = 0.5
K_REPEL = 0.6


def start_positions(graph: TopologyGraph, order: Sequence[str],
                    half: Dict[str, Point], run: float, gap: float,
                    anchored: Optional[set] = None) -> Dict[str, Point]:
    """Breadth-first start: each room beside its first placed neighbour on a
    free wall side: the side that clashes with the fewest placed rooms, then
    (for a room that closes a loop) lies nearest its other placed neighbours,
    then leaves the most room to the rest (so it points away from them)."""
    pos: Dict[str, Point] = {}
    used: Dict[str, set] = {r: set() for r in order}
    rank = {r: k for k, r in enumerate(order)}
    nodes = {r: graph.node(r) for r in order}
    for u in order:
        placed_nbrs = sorted((m for m in graph.neighbours(u) if m in pos), key=rank.get)
        if not placed_nbrs:
            # The entrance (or a room nothing placed reaches): beside the layout.
            if not pos:
                pos[u] = (0.0, 0.0)
            else:
                x1 = max(p[0] + half[r][0] for r, p in pos.items())
                pos[u] = (x1 + run + half[u][0], 0.0)
            continue
        p = placed_nbrs[0]
        free = [s for s in SIDES if s[0] not in used[p]] or list(SIDES)
        best = None
        for k, (name, (dx, dy)) in enumerate(free):
            ext = abs(dx) * (half[p][0] + half[u][0]) + abs(dy) * (half[p][1] + half[u][1])
            c = (pos[p][0] + dx * (ext + run), pos[p][1] + dy * (ext + run))
            clashes = 0
            room = math.inf
            for r, q in pos.items():
                if r == p or may_overlap_in_plan(nodes[u], nodes[r]):
                    continue
                g = _box_gap(c, half[u], q, half[r])
                if g < gap:
                    clashes += 1
                room = min(room, g)
            # A room closing a loop sits as near its other placed neighbours
            # as the free sides allow, so the loop is drawn locally.
            close = sum(max(0.0, _box_gap(c, half[u], pos[m], half[m]))
                        for m in placed_nbrs[1:])
            key = (clashes, round(close, 6), -room, k)
            if best is None or key < best[0]:
                best = (key, c)
        pos[u] = best[1]
        if anchored is not None:
            anchored.add(frozenset((p, u)))
        for m in placed_nbrs:
            used[m].add(_side_toward(pos[m], half[m], pos[u], half[u]))
            used[u].add(_side_toward(pos[u], half[u], pos[m], half[m]))
    return pos


def spring_relax(order: Sequence[str], edges: Sequence[Tuple[str, str]],
                 pos: Dict[str, Point], half: Dict[str, Point], nodes: Dict[str, Node],
                 run: float, gap: float, anchored=None,
                 iterations: Optional[int] = None) -> Dict[str, Point]:
    """Spring iterations: each edge pulls its rooms toward its rest length
    (the rooms' extents along the edge plus one run) and toward a shared axis
    (so its corridor runs straight); every other pair repels, more strongly
    the nearer their footprints."""
    n = len(order)
    if n < 2:
        return dict(pos)
    iterations = ITERATIONS if iterations is None else iterations
    idx = {r: k for k, r in enumerate(order)}
    P = np.array([pos[r] for r in order], dtype=float)
    H = np.array([half[r] for r in order], dtype=float)
    E = np.array([(idx[a], idx[b]) for a, b in edges], dtype=int).reshape(-1, 2)
    # The side each edge starts on, as a unit axis from a to b; T marks the
    # edges rooms were placed along.
    dirs = dict(SIDES)
    S = np.array([dirs[_side_toward(pos[a], half[a], pos[b], half[b])] for a, b in edges],
                 dtype=float).reshape(-1, 2)
    T = np.array([frozenset(e) in (anchored or ()) for e in edges], dtype=bool)
    joined = np.zeros((n, n), dtype=bool)
    if len(E):
        joined[E[:, 0], E[:, 1]] = True
        joined[E[:, 1], E[:, 0]] = True
    apart = np.ones((n, n), dtype=bool)
    for a in range(n):
        for b in range(n):
            if a == b or may_overlap_in_plan(nodes[order[a]], nodes[order[b]]):
                apart[a, b] = False
    # Joined rooms repel only inside the separation gap (their spring does the
    # rest); others inside REPEL_RUNS runs.
    reach = np.where(joined, gap, gap + REPEL_RUNS * run)
    np.fill_diagonal(reach, 0.0)
    iu = np.triu_indices(n, 1)

    for it in range(iterations):
        step = STEP_START + (STEP_END - STEP_START) * it / max(1, iterations - 1)
        F = np.zeros_like(P)
        if len(E):
            a, b = E[:, 0], E[:, 1]
            d = P[b] - P[a]
            # Edges a room was placed along keep their wall side: b rests one
            # run past a's wall on that axis, centred across it.
            rest = (np.abs(S[:, 0]) * (H[a, 0] + H[b, 0])
                    + np.abs(S[:, 1]) * (H[a, 1] + H[b, 1]) + run)
            f_dir = K_SPRING * (d - S * rest[:, None])
            # The others (loop-closing edges) pull toward their rest distance.
            dist = np.hypot(d[:, 0], d[:, 1])
            dist = np.where(dist < 1e-6, 1e-6, dist)
            u = d / dist[:, None]
            rest = (np.abs(u[:, 0]) * (H[a, 0] + H[b, 0])
                    + np.abs(u[:, 1]) * (H[a, 1] + H[b, 1]) + run)
            f_len = (K_SPRING * (dist - rest))[:, None] * u
            f = np.where(T[:, None], f_dir, f_len)
            np.add.at(F, a, f)
            np.add.at(F, b, -f)
        # Repulsion over every pair kept apart in plan.
        i, j = iu
        d = P[j] - P[i]
        gx = np.abs(d[:, 0]) - (H[i, 0] + H[j, 0])
        gy = np.abs(d[:, 1]) - (H[i, 1] + H[j, 1])
        g = np.maximum(gx, gy)
        want = reach[i, j]
        hit = apart[i, j] & (g < want)
        if hit.any():
            i, j, d, g, want = i[hit], j[hit], d[hit], g[hit], want[hit]
            dist = np.hypot(d[:, 0], d[:, 1])
            # Coincident centres: a fixed direction by index, deterministic.
            fallback = np.stack([np.cos(i + 0.5 * j), np.sin(i + 0.5 * j)], axis=1)
            u = np.where(dist[:, None] < 1e-6, fallback, d / np.maximum(dist, 1e-6)[:, None])
            depth = (want - g) / np.maximum(want, 1e-6)        # 0 at reach, 1 at touching
            mag = K_REPEL * (want - g) * (1.0 + depth)
            f = mag[:, None] * u
            np.add.at(F, i, -f)
            np.add.at(F, j, f)
        P += step * F
    return {r: (float(P[k, 0]), float(P[k, 1])) for k, r in enumerate(order)}


def spring(graph: TopologyGraph, order: Sequence[str], half: Dict[str, Point],
           corridor_width: float, gap: float) -> Dict[str, Point]:
    """The ``spring`` placement: room centres for ``order`` (before separation
    and the Envelope; :func:`place` does those)."""
    run = RUN_FACTOR * corridor_width
    anchored: set = set()
    pos = start_positions(graph, order, half, run, gap, anchored)
    edges = [(e.a, e.b) for e in graph.edges()
             if graph.node(e.a).is_room and graph.node(e.b).is_room]
    nodes = {r: graph.node(r) for r in order}
    return spring_relax(order, edges, pos, half, nodes, run, gap, anchored)


#: The Placement registry: name -> callable(graph, order, half, corridor_width,
#: gap) -> {room id: centre}. Names must be the checker's ``ruleset.PLACEMENTS``.
PLACEMENT_FUNCS: Dict[str, Callable[..., Dict[str, Point]]] = {"spring": spring}

_missing = set(_ruleset.PLACEMENTS) - set(PLACEMENT_FUNCS)
if _missing:                                       # pragma: no cover (a wiring bug)
    raise RuntimeError(f"placements {sorted(_missing)} are checked but not registered")


def fit_to_envelope(centres: Dict[str, Point], half: Dict[str, Point],
                    envelope) -> Dict[str, Point]:
    """Scale the layout's centres about their centroid so every room's far
    corner lies within the Envelope's inradius (only ever shrinking), then
    move the centroid to the Envelope's centre. Separation runs after."""
    if not centres:
        return {}
    cx = sum(p[0] for p in centres.values()) / len(centres)
    cy = sum(p[1] for p in centres.values()) / len(centres)
    reach = max(math.hypot(abs(p[0] - cx) + half[r][0], abs(p[1] - cy) + half[r][1])
                for r, p in centres.items())
    biggest = max(math.hypot(*half[r]) for r in centres)
    room = max(0.0, envelope.inradius - biggest)
    span = max(1e-6, reach - biggest)
    s = min(1.0, room / span)
    ox, oy = envelope.centre
    return {r: (ox + (p[0] - cx) * s, oy + (p[1] - cy) * s) for r, p in centres.items()}


__all__ = [
    "SIZE_SCALE", "SPREAD", "base_side", "area_matched_base", "room_size", "may_overlap_in_plan",
    "bfs_order", "SIDES", "start_positions", "spring_relax", "spring",
    "PLACEMENT_FUNCS", "fit_to_envelope",
    "RUN_FACTOR", "REPEL_RUNS", "ITERATIONS", "K_SPRING", "K_REPEL",
]
