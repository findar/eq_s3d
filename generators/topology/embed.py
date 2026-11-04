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
- :func:`spring`, the one step 6 placement: a breadth-first start that gives
  each of a room's neighbours its own wall side (the router leaves a room
  through the wall facing the other room, so two corridors on one wall
  overlap and Job B splits or drops one; task 18), spring iterations that keep
  every edge on its start side, then the layout's own separation
  (``ctx.separate``) and the Envelope's centring.

Every pair test goes through :func:`may_overlap_in_plan`. Step 7 (task 4)
gives it Levels: :func:`assign_levels` reads each room's Level off the grown
graph's vertical relations, :func:`storeys` turns Levels and room heights into
floor heights (one :func:`level_height` per build), and two rooms may overlap
in plan only on different Levels with at least the :data:`SLAB` between the
upper floor and the lower ceiling. A placement given ``storeys`` doesn't push
such pairs apart and pulls a stair edge (one across Levels) together so the
upper room sits partly over its partner (:data:`STAIR_REST`). Without
``storeys`` (the step 6 call) every room is a plain graph node and nothing
overlaps.

Nothing here draws from the rng except :func:`room_size`; the spring layout is
a fixed number of fixed-size steps, so the same graph and sizes always give
the same positions.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Sequence, Tuple

import numpy as np

from generators.topology.graph import ENTRANCE, Node, TopologyGraph
from generators.topology import ruleset as _ruleset
from generators.topology.ruleset import LEVEL_STEP, relative_levels

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
# Levels and the plan predicate (step 7, design "Levels", "Stacking")
# ---------------------------------------------------------------------------

#: The least solid thickness between a lower room's ceiling and the floor of
#: a room over it (design finding 7: the stock median, band 11-39 u).
SLAB = 14.0


class Storey(NamedTuple):
    """What :func:`may_overlap_in_plan` reads about a room: its Level, its
    floor height and its own height (at race scale)."""

    level: int
    floor: float
    height: float

    @property
    def ceiling(self) -> float:
        return self.floor + self.height


def assign_levels(graph: TopologyGraph) -> Dict[str, int]:
    """Each node's Level: breadth-first from the entrance (sorted neighbours),
    ``above`` +1, ``below`` -1, ``level`` 0 from the neighbour it is reached
    from; an ``any`` edge gives the room it reaches first its neighbour's Level
    (and with it every room tied to that one by the other relations, so they
    still agree). A part the entrance can't reach starts at Level 0 from its
    least id. The entrance is Level 0.

    Raises ValueError when the relations disagree round a loop (the rewrite
    driver never grows such a graph: ``rewrite.invariant_violation``).
    """
    rel, conflict = relative_levels(graph.edges())
    if conflict is not None:
        raise ValueError(conflict)
    ids = graph.node_ids()
    if not ids:
        return {}
    shift: Dict[str, int] = {}
    level: Dict[str, int] = {}

    def put(v: str, want: int) -> None:
        group, off = rel.get(v, (v, 0))
        if group not in shift:
            shift[group] = want - off
        level[v] = shift[group] + off

    entrance = next((n.id for n in graph.rooms() if n.kind == ENTRANCE), ids[0])
    for start in [entrance] + ids:
        if start in level:
            continue
        put(start, 0)
        queue = [start]
        while queue:
            u = queue.pop(0)
            for e in graph.incident(u):            # read from u, sorted by e.b
                if e.b in level:
                    continue
                put(e.b, level[u] + LEVEL_STEP.get(e.rel, 0))
                queue.append(e.b)
    return level


def level_height(heights: Sequence[float], slab: float = SLAB) -> float:
    """Floor to floor between two Levels: the tallest room plus the Slab
    (design finding 7; one per build, so any room fits under any other)."""
    return (max(heights) if heights else 0.0) + slab


def storeys(levels: Dict[str, int], heights: Dict[str, float],
            height: Optional[float] = None) -> Dict[str, Storey]:
    """Each room's :class:`Storey`, its floor at Level x ``height`` (the
    :func:`level_height` of these rooms when None)."""
    if height is None:
        height = level_height(list(heights.values()))
    return {r: Storey(levels[r], levels[r] * height, heights[r]) for r in heights}


def may_overlap_in_plan(a: Any, b: Any, slab: float = SLAB) -> bool:
    """May rooms ``a`` and ``b`` overlap in plan (one above the other)?

    Only two :class:`Storey` values on different Levels whose vertical gap
    (the upper floor less the lower ceiling) is at least ``slab``. Anything
    without a Level (a plain graph ``Node``, as step 6 passed) never may.
    """
    la, lb = getattr(a, "level", None), getattr(b, "level", None)
    if la is None or lb is None or la == lb:
        return False
    lo, hi = (a, b) if la < lb else (b, a)
    return hi.floor - lo.ceiling >= slab - 1e-9


def is_stair(a: Any, b: Any) -> bool:
    """An edge between these rooms crosses Levels (a Vertical_Connector)."""
    la, lb = getattr(a, "level", None), getattr(b, "level", None)
    return la is not None and lb is not None and la != lb


def _plan_keys(graph: TopologyGraph, order: Sequence[str],
               storeys: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """What the pair tests read per room: its Storey, or its graph node."""
    if storeys is not None:
        return {r: storeys[r] for r in order}
    return {r: graph.node(r) for r in order}


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
#: A stair edge's rest distance, as a share of the two rooms' extents along
#: the edge (no corridor run): 0.5 puts the upper room's centre over the lower
#: room's wall, about half of each footprint over the other.
STAIR_REST = 0.5


def _ring_mates(graph: TopologyGraph, rooms: Sequence[str]) -> Dict[str, Dict[frozenset, int]]:
    """For each room p, its neighbour pairs that share a short loop through p:
    ``mates[p][frozenset((u, w))]`` = hops from u to w without p (2 for a ring
    of four, 3 for a ring of five). Such a pair wants perpendicular walls of p
    (the ring drawn round a corner); on opposite walls the loop has to wrap
    round p and its corridors land on walls already taken."""
    inset = set(rooms)
    mates: Dict[str, Dict[frozenset, int]] = {}
    for p in rooms:
        nb = [m for m in graph.neighbours(p) if m in inset]
        out: Dict[frozenset, int] = {}
        for i, u in enumerate(nb):
            dist = {u: 0}
            frontier = [u]
            for d in range(1, 4):
                nxt = []
                for x in frontier:
                    for y in graph.neighbours(x):
                        if y in inset and y != p and y not in dist:
                            dist[y] = d
                            nxt.append(y)
                frontier = nxt
            for w in nb[i + 1:]:
                if w in dist:
                    out[frozenset((u, w))] = dist[w]
        mates[p] = out
    return mates


def _placing_order(graph: TopologyGraph, order: Sequence[str],
                   mates: Dict[str, Dict[frozenset, int]],
                   root: Optional[str] = None) -> List[str]:
    """Breadth-first from the first room; each room's unplaced neighbours are
    taken ring members first (rooms on a short loop through it, so they get
    the corner sides), dead ends last, then in ``order``."""
    if not order:
        return []
    rank = {r: k for k, r in enumerate(order)}
    inset = set(order)
    root = order[0] if root is None else root
    seen = {root}
    out = [root]
    k = 0
    while len(out) < len(order):
        if k == len(out):                    # a room nothing reaches: start there
            r = next(r for r in order if r not in seen)
            seen.add(r)
            out.append(r)
        p = out[k]
        k += 1
        on_ring = {x for pair in mates[p] for x in pair}
        nxt = sorted((m for m in graph.neighbours(p) if m in inset and m not in seen),
                     key=lambda m: (m not in on_ring,
                                    sum(1 for x in graph.neighbours(m) if x in inset) == 1,
                                    rank[m]))
        for m in nxt:
            seen.add(m)
            out.append(m)
    return out


#: Side tie-break orders the start tries (the first is SIDES' own): rotations
#: and mirror images of E, N, W, S. START_ROOTS: rooms the start may place
#: first. The start keeps the first try with the fewest wall and footprint
#: clashes.
START_ROOTS = 8
SIDE_ORDERS: Tuple[Tuple[str, ...], ...] = (
    ("E", "N", "W", "S"), ("N", "W", "S", "E"), ("W", "S", "E", "N"), ("S", "E", "N", "W"),
    ("E", "S", "W", "N"), ("S", "W", "N", "E"), ("W", "N", "E", "S"), ("N", "E", "S", "W"))


def layout_clashes(graph: TopologyGraph, order: Sequence[str], pos: Dict[str, Point],
                   half: Dict[str, Point], gap: float,
                   storeys: Optional[Dict[str, Any]] = None) -> int:
    """Wall clashes (a room's corridors sharing a wall, as the router picks
    walls) plus pairs of rooms kept apart in plan that sit within ``gap``."""
    inset = set(order)
    keys = _plan_keys(graph, order, storeys)
    bad = 0
    for u in order:
        walls = [_side_toward(pos[u], half[u], pos[m], half[m])
                 for m in graph.neighbours(u) if m in inset]
        bad += len(walls) - len(set(walls))
    for i, a in enumerate(order):
        for b in order[i + 1:]:
            if (not may_overlap_in_plan(keys[a], keys[b])
                    and _box_gap(pos[a], half[a], pos[b], half[b]) < gap - 1e-6):
                bad += 1
    return bad


def start_positions(graph: TopologyGraph, order: Sequence[str],
                    half: Dict[str, Point], run: float, gap: float,
                    storeys: Optional[Dict[str, Any]] = None) -> Dict[str, Point]:
    """The best of :func:`start_once` over START_ROOTS roots (the first room,
    then the best-connected) and :data:`SIDE_ORDERS` (fewest
    :func:`layout_clashes`, the first on a tie; a clash-free start ends the
    search), then :func:`repair` if it still clashes."""
    inset = set(order)
    deg = {r: sum(1 for m in graph.neighbours(r) if m in inset) for r in order}
    rank = {r: k for k, r in enumerate(order)}
    roots = list(order[:1]) + sorted(order[1:], key=lambda r: (-deg[r], rank[r]))[:START_ROOTS - 1]
    best = None
    for root in roots:
        for sides in SIDE_ORDERS:
            pos = start_once(graph, order, half, run, gap, sides, root, storeys)
            score = layout_clashes(graph, order, pos, half, gap, storeys)
            if best is None or score < best[0]:
                best = (score, pos)
            if score == 0:
                break
        if best[0] == 0:
            break
    pos = best[1]
    if best[0]:
        repair(graph, order, pos, half, run, gap, storeys)
    return pos


#: Sweeps of :func:`repair` at most.
REPAIR_SWEEPS = 4
#: Shifts across a wall that :func:`repair` tries, in the two rooms' half-extents.
REPAIR_SHIFTS = (0.0, -0.5, 0.5, -1.0, 1.0)


def repair(graph: TopologyGraph, order: Sequence[str], pos: Dict[str, Point],
           half: Dict[str, Point], run: float, gap: float,
           storeys: Optional[Dict[str, Any]] = None) -> None:
    """Move rooms, one at a time, to the spot beside or in the corner of their
    neighbours that leaves fewer clashes (:func:`layout_clashes`, counted
    locally), until a sweep moves nothing. In place."""
    inset = set(order)
    nbrs = {u: [m for m in graph.neighbours(u) if m in inset] for u in order}
    nodes = _plan_keys(graph, order, storeys)
    dirs = dict(SIDES)

    def side(a: str, pa: Point, b: str, pb: Point) -> str:
        return _side_toward(pa, half[a], pb, half[b])

    def local(u: str, c: Point) -> int:
        bad = 0
        mine = [side(u, c, m, pos[m]) for m in nbrs[u]]
        bad += len(mine) - len(set(mine))
        for m in nbrs[u]:
            sm = side(m, pos[m], u, c)
            bad += sum(1 for x in nbrs[m] if x != u and side(m, pos[m], x, pos[x]) == sm)
        for r in order:
            if (r != u and not may_overlap_in_plan(nodes[u], nodes[r])
                    and _box_gap(c, half[u], pos[r], half[r]) < gap - 1e-6):
                bad += 1
        return bad

    def spread(u: str, c: Point) -> float:
        return sum(max(0.0, _box_gap(c, half[u], pos[m], half[m])) for m in nbrs[u])

    def beside(q: str, u: str, sd: str, shift: float = 0.0) -> Point:
        """u one run past q's ``sd`` wall, moved across it by ``shift`` times
        the two rooms' half-extents across (still on that wall up to 1)."""
        dx, dy = dirs[sd]
        ext = abs(dx) * (half[q][0] + half[u][0]) + abs(dy) * (half[q][1] + half[u][1])
        across = abs(dy) * (half[q][0] + half[u][0]) + abs(dx) * (half[q][1] + half[u][1])
        return (pos[q][0] + dx * (ext + run) + abs(dy) * shift * across,
                pos[q][1] + dy * (ext + run) + abs(dx) * shift * across)

    for _sweep in range(REPAIR_SWEEPS):
        moved = False
        for u in order:
            now = local(u, pos[u])
            if now == 0 or not nbrs[u]:
                continue
            cands = [beside(q, u, sd, f) for q in nbrs[u] for sd, _d in SIDES
                     for f in REPAIR_SHIFTS]
            cands += [(beside(q, u, sx)[0], beside(r, u, sy)[1])
                      for q in nbrs[u] for r in nbrs[u] if r != q
                      for sx in ("E", "W") for sy in ("N", "S")]
            best = (now, spread(u, pos[u]), pos[u])
            for c in cands:
                b = local(u, c)
                if b < best[0] or (b == best[0] and b < now and spread(u, c) < best[1]):
                    best = (b, spread(u, c), c)
            if best[0] < now:
                pos[u] = best[2]
                moved = True
        if not moved:
            break


def start_once(graph: TopologyGraph, order: Sequence[str],
               half: Dict[str, Point], run: float, gap: float,
               side_order: Sequence[str] = ("E", "N", "W", "S"),
               root: Optional[str] = None,
               storeys: Optional[Dict[str, Any]] = None) -> Dict[str, Point]:
    """Breadth-first start: each room beside a placed neighbour on a free wall
    side, or in the corner where two placed neighbours' free sides meet.

    Candidates are ranked by (twice the wall clashes plus footprint clashes,
    footprint clashes, ring-mate sides, distance to its placed neighbours and
    to the placed rooms a loop through it will close on, room left, then a
    fixed order); springs and separation clear a footprint clash, a wall
    clash stays. A wall clash is a corridor that would leave a room
    through a wall another of its corridors uses: the router exits a room
    through the wall facing the other room, so two corridors on one wall
    overlap past the doorway and Job B splits or drops one (finding 1: one
    opening per wall side; degree <= 4 makes it possible)."""
    pos: Dict[str, Point] = {}
    used: Dict[str, Dict[str, str]] = {r: {} for r in order}   # side -> neighbour
    rank = {r: k for k, r in enumerate(order)}
    nodes = _plan_keys(graph, order, storeys)
    mates = _ring_mates(graph, order)
    dirs = dict(SIDES)

    def beside(q: str, u: str, d: Point) -> Point:
        dx, dy = d
        ext = abs(dx) * (half[q][0] + half[u][0]) + abs(dy) * (half[q][1] + half[u][1])
        return (pos[q][0] + dx * (ext + run), pos[q][1] + dy * (ext + run))

    def ring_bad(u: str, q: str, side: str) -> int:
        """u on q's ``side``: ring mates of u at q on the opposite side, or
        left without a perpendicular side of q to take."""
        bad = 0
        for pair in mates.get(q, {}):
            if u not in pair:
                continue
            (w,) = tuple(pair - {u})
            if w in pos:
                sw = next((sd for sd, m in used[q].items() if m == w), None)
                bad += sw == _OPPOSITE[side]
            else:
                perp = ("N", "S") if side in "EW" else ("E", "W")
                bad += all(sd in used[q] for sd in perp)
        return bad

    for u in _placing_order(graph, order, mates, root):
        placed_nbrs = sorted((m for m in graph.neighbours(u) if m in pos), key=rank.get)
        if not placed_nbrs:
            # The entrance (or a room nothing placed reaches): beside the layout.
            if not pos:
                pos[u] = (0.0, 0.0)
            else:
                x1 = max(p[0] + half[r][0] for r, p in pos.items())
                pos[u] = (x1 + run + half[u][0], 0.0)
            continue
        # Placed rooms a loop through u will close on later, through rooms not
        # placed yet (2 or 3 hops away): u leans toward them.
        pending: Dict[str, int] = {}
        frontier = [x for x in graph.neighbours(u) if x in rank and x not in pos]
        seen_x = set(frontier) | {u}
        for hops in (2, 3):
            nxt = []
            for x in frontier:
                for y in graph.neighbours(x):
                    if y not in rank or y in seen_x:
                        continue
                    seen_x.add(y)
                    if y in pos:
                        if y not in placed_nbrs:
                            pending.setdefault(y, hops)
                    else:
                        nxt.append(y)
            frontier = nxt
        free = {q: [sd for sd in side_order if sd not in used[q]] for q in placed_nbrs}
        cands = []
        for qk, q in enumerate(placed_nbrs):
            sides = free[q] or (list(side_order) if qk == 0 else [])
            for k, sd in enumerate(sides):
                cands.append(((qk, k), beside(q, u, dirs[sd])))
        npl = len(placed_nbrs)
        for qk, q in enumerate(placed_nbrs):
            for rk, r in enumerate(placed_nbrs):
                if r == q:
                    continue
                for sx in (sd for sd in free[q] if sd in "EW"):
                    for sy in (sd for sd in free[r] if sd in "NS"):
                        c = (beside(q, u, dirs[sx])[0], beside(r, u, dirs[sy])[1])
                        cands.append(((npl + qk, rk), c))
        best = None
        for tie, c in cands:
            walls = 0
            mine = set()
            for m in placed_nbrs:
                sm = _side_toward(pos[m], half[m], c, half[u])
                su = _side_toward(c, half[u], pos[m], half[m])
                walls += (sm in used[m]) + (su in mine)
                mine.add(su)
            clashes = 0
            room = math.inf
            for r, qq in pos.items():
                if may_overlap_in_plan(nodes[u], nodes[r]):
                    continue
                g = _box_gap(c, half[u], qq, half[r])
                if g < gap:
                    clashes += 1
                if r not in placed_nbrs:
                    room = min(room, g)
            rings = sum(ring_bad(u, m, _side_toward(pos[m], half[m], c, half[u]))
                        for m in placed_nbrs)
            # A room closing a loop sits as near its other placed neighbours
            # as the free sides allow, so the loop is drawn locally.
            close = sum(max(0.0, _box_gap(c, half[u], pos[m], half[m]))
                        for m in placed_nbrs)
            close += sum(max(0.0, _box_gap(c, half[u], pos[m], half[m])) / (h - 1)
                         for m, h in pending.items())
            key = (2 * walls + clashes, clashes, rings, round(close, 6), -room, tie)
            if best is None or key < best[0]:
                best = (key, c)
        pos[u] = best[1]
        for m in placed_nbrs:
            used[m].setdefault(_side_toward(pos[m], half[m], pos[u], half[u]), u)
            used[u].setdefault(_side_toward(pos[u], half[u], pos[m], half[m]), m)
    return pos


def spring_relax(order: Sequence[str], edges: Sequence[Tuple[str, str]],
                 pos: Dict[str, Point], half: Dict[str, Point], nodes: Dict[str, Any],
                 run: float, gap: float,
                 iterations: Optional[int] = None) -> Dict[str, Point]:
    """Spring iterations: each edge keeps the wall side it starts on (b rests
    one run past a's wall on that axis, centred across it, so its corridor
    runs straight and stays on that wall); every other pair repels, more
    strongly the nearer their footprints. ``nodes`` are what the pair tests
    read (graph nodes, or Storeys): a pair that may overlap in plan doesn't
    repel, and a stair edge (across Levels) rests :data:`STAIR_REST` of the
    two rooms' extents apart, with no run, so the upper room sits partly over
    its partner."""
    n = len(order)
    if n < 2:
        return dict(pos)
    iterations = ITERATIONS if iterations is None else iterations
    idx = {r: k for k, r in enumerate(order)}
    P = np.array([pos[r] for r in order], dtype=float)
    H = np.array([half[r] for r in order], dtype=float)
    E = np.array([(idx[a], idx[b]) for a, b in edges], dtype=int).reshape(-1, 2)
    stair = np.array([is_stair(nodes[a], nodes[b]) for a, b in edges], dtype=bool)
    # The side each edge starts on, as a unit axis from a to b. Every edge
    # keeps it (task 18): a loop edge left to pull toward a bare rest
    # distance could swing onto a wall another corridor uses.
    dirs = dict(SIDES)
    S = np.array([dirs[_side_toward(pos[a], half[a], pos[b], half[b])] for a, b in edges],
                 dtype=float).reshape(-1, 2)
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
            rest = (np.abs(S[:, 0]) * (H[a, 0] + H[b, 0])
                    + np.abs(S[:, 1]) * (H[a, 1] + H[b, 1]) + run)
            if stair.any():
                rest = np.where(stair, (rest - run) * STAIR_REST, rest)
            f = K_SPRING * (d - S * rest[:, None])
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
           corridor_width: float, gap: float,
           storeys: Optional[Dict[str, Storey]] = None) -> Dict[str, Point]:
    """The ``spring`` placement: room centres for ``order`` (before separation
    and the Envelope; :func:`place` does those). With ``storeys`` (step 7)
    rooms on different Levels may overlap and stair edges pull together."""
    run = RUN_FACTOR * corridor_width
    pos = start_positions(graph, order, half, run, gap, storeys)
    edges = [(e.a, e.b) for e in graph.edges()
             if graph.node(e.a).is_room and graph.node(e.b).is_room]
    nodes = _plan_keys(graph, order, storeys)
    return spring_relax(order, edges, pos, half, nodes, run, gap)


#: The Placement registry: name -> callable(graph, order, half, corridor_width,
#: gap, storeys=None) -> {room id: centre}. Names must be the checker's
#: ``ruleset.PLACEMENTS``. ``storeys`` (step 7) is passed only when the build
#: stacks, so a placement written before it still works on one Level.
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


#: The eight plan symmetries that keep a box layout's walls axis-aligned:
#: (quarter turns counter-clockwise, mirrored in x first). Identity first,
#: unmirrored before mirrored, so a tie keeps the least change.
FACINGS: Tuple[Tuple[int, bool], ...] = tuple(
    (k, m) for m in (False, True) for k in range(4))


def _facing(p: Point, k: int, mirror: bool) -> Point:
    x, y = (-p[0], p[1]) if mirror else p
    for _ in range(k):
        x, y = -y, x
    return x, y


def face_entry(centres: Dict[str, Point], half: Dict[str, Point], envelope,
               entrance: Optional[str], rank: int = 0
               ) -> Tuple[Dict[str, Point], Dict[str, Point], bool]:
    """Fit the layout to ``envelope`` with its *entrance* room facing the
    Envelope's way in (``envelope.entry``), so the room the pacing makes the
    entrance (the one nearest the way in) is the rules' entrance room.

    Tries the eight :data:`FACINGS` (quarter turns and a mirror: rooms stay
    axis-aligned boxes and every edge keeps its wall side, turned with the
    layout, so the layout is congruent and stays clash-free) and keeps the
    first that, after :func:`fit_to_envelope`, puts the entrance room nearest
    the way in, closest to it; *rank* ``k`` keeps the ``k``-th best instead
    (modulo eight: a caller whose first choice doesn't work out, such as an
    Entrance that doesn't plan, tries the next). Returns the fitted centres, the half-extents
    (width and depth swapped on an odd number of quarter turns) and whether
    they were swapped. Without an entry or an entrance room it is
    :func:`fit_to_envelope` unchanged."""
    if getattr(envelope, "entry", None) is None or entrance not in centres:
        return fit_to_envelope(centres, half, envelope), half, False
    ex, ey = envelope.entry
    ranked = []
    for n, (k, mirror) in enumerate(FACINGS):
        swap = k % 2 == 1
        c = {r: _facing(p, k, mirror) for r, p in centres.items()}
        h = {r: (v[1], v[0]) for r, v in half.items()} if swap else half
        fitted = fit_to_envelope(c, h, envelope)
        dist = {r: math.hypot(p[0] - ex, p[1] - ey) for r, p in fitted.items()}
        nearest = min(dist.values())
        key = (dist[entrance] > nearest + 1e-9, round(dist[entrance], 6), n)
        ranked.append((key, fitted, h, swap))
    ranked.sort(key=lambda t: t[0])
    _key, fitted, h, swap = ranked[rank % len(ranked)]
    return fitted, h, swap


__all__ = [
    "SIZE_SCALE", "SPREAD", "base_side", "area_matched_base", "room_size", "may_overlap_in_plan",
    "SLAB", "Storey", "assign_levels", "level_height", "storeys", "is_stair", "STAIR_REST",
    "bfs_order", "SIDES", "SIDE_ORDERS", "START_ROOTS", "layout_clashes", "start_positions",
    "start_once", "repair", "spring_relax", "spring",
    "PLACEMENT_FUNCS", "fit_to_envelope", "FACINGS", "face_entry",
    "RUN_FACTOR", "REPEL_RUNS", "ITERATIONS", "K_SPRING", "K_REPEL",
]
