"""
generators/topology/embed.py
----------------------------
Placing a grown Topology_Graph in the plane (roadmap step 6, Requirement 6;
design "Size classes" and "Placement").

Three parts:

- :func:`room_size` turns a node's Size_Class into a footprint and height:
  the class's point in the race's room bands (``semantics``, step 7 task 17:
  room height 2.5-10 H, footprint side 8-20 H, tiny at the minimum and huge
  at the maximum), with the classic engine's spread (within 15 %) on the
  footprint. Rooms are placed at that final size; nothing scales them again.
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
a fixed number of fixed-size steps, and each edge's offset and spacing
(:func:`edge_jitter`, winding control task 8) are hashed from the build's salt
and the edge's ids, so the same graph and sizes always give the same positions.
"""

from __future__ import annotations

import functools
import hashlib
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

#: The classic engine's spread around the class side: a gaussian factor on
#: each axis, clamped to 1 +- SPREAD (and then to the race's band).
SPREAD = 0.15
_SPREAD_SIGMA = SPREAD / 2


def room_size(size: Optional[str], race: str, rng,
              shift: float = 0.0,
              height_shift: Optional[float] = None) -> Tuple[float, float, float]:
    """(width, depth, height) of a room of Size_Class ``size`` for ``race``
    (step 7 task 17): the class's point in the race's bands
    (``semantics.band_position``, after the Size control's ``shift``), the
    footprint spread by up to SPREAD on each axis and kept inside the band.

    Two rng draws (width, then depth). An unknown or missing class is medium.
    ``height_shift`` (None: ``shift``) places the height instead.
    """
    from generators import semantics
    t = semantics.band_position(size, shift)
    side = semantics.room_side(race, t)
    (s0, s1), _h = semantics.room_bands(race)
    w = side * min(1 + SPREAD, max(1 - SPREAD, rng.gauss(1.0, _SPREAD_SIGMA)))
    d = side * min(1 + SPREAD, max(1 - SPREAD, rng.gauss(1.0, _SPREAD_SIGMA)))
    th = t if height_shift is None else semantics.band_position(size, height_shift)
    return (min(s1, max(s0, w)), min(s1, max(s0, d)), semantics.room_height(race, th))


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
        return _Keys({r: storeys[r] for r in order})
    return _Keys({r: graph.node(r) for r in order})


class _Keys(dict):
    """:func:`_plan_keys`'s rooms, with the pairs of them that may overlap in
    plan (``over``), worked out once for the crossing tests (task 10)."""

    @functools.cached_property
    def over(self) -> frozenset:
        rooms = sorted(self)
        if len({getattr(self[r], "level", None) for r in rooms}) < 2:
            return frozenset()
        return frozenset((r, s) for r in rooms for s in rooms
                         if r != s and may_overlap_in_plan(self[r], self[s]))


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

#: The edge tag a rule puts on a Bridge (step 7 task 11): ``a``-``b`` on one
#: Level, crossing the lower room one of them is stair-joined to.
BRIDGE_TAG = "bridge"

#: Per-edge jitter (winding control task 8), for a placement whose corridors
#: are rough (``spring(jitter=True)``: a cave): without it every neighbour sits
#: centred one run past a wall and the springs hold it there, so rooms of
#: similar size fall on a lattice. Each edge gets a sideways offset along the
#: wall and a spacing factor on its run, SPACING_LO to SPACING_HI. The offset
#: is OFFSET_MIN to OFFSET, either way, of the edge's slack: the two rooms'
#: half-extents across less :data:`STRAIGHT_NEED` corridor widths, so the
#: rooms still share a span a straight corridor fits across (the layout puts
#: the doors there, ``LayoutGenerator._wall_point``) and :func:`_side_toward`
#: keeps the edge's side. Both are drawn per edge from the build's salt and
#: the two room ids (:func:`edge_jitter`), never from the shared rng. A stair
#: edge (across Levels) and a Bridge keep none: their overlap is placed on
#: purpose. The floor keeps an edge from landing centred; the spacing alone
#: moves no row or column (they are the centred offsets). The spacing runs
#: long because a straight rough corridor winds only with room to: at 0.75-
#: 1.25 half the cave's corridors wound and 28 % took a path (centred, the
#: Z corridors' cut bends gave 61 % and 56 %); at 1.25-1.75, 69 % and 60 %,
#: door to door p50 102 -> 118 u (measured over 40 cave graph builds).
OFFSET = 1.0
OFFSET_MIN = 0.4
SPACING_LO, SPACING_HI = 1.25, 1.75
#: The span two facing rooms keep in common, in corridor widths: the corridor
#: and a quarter-width pier each side of its doors.
STRAIGHT_NEED = 1.5
#: An Envelope build's jitter (an outdoor dungeon; random placement task 3):
#: (spacing low, spacing high, offset floor). ``fit_to_envelope`` scales a
#: layout down to the hill (median x0.74 at the cave spacing), shrinking each
#: offset with it, so a shorter spacing keeps more of the offset and a higher
#: floor keeps a shrunk one off the 10 u the grid score reads. Outdoor graph
#: seeds 2000-2039 (default / fortress), grid mean: 1.25-1.75 at 0.4 gave
#: 0.104 / 0.103, at 0.6 0.101 / 0.102; 0.75-1.25 at 0.6 0.098 / 0.098;
#: 1.0-1.5 at 0.4 0.103 / 0.104, at 0.6 0.090 / 0.095 (lattice 0.221 /
#: 0.214). Stair and Bridge pairs keep their alignment on purpose (about half
#: the stair pairs line up), which holds the floor near 0.09.
ENVELOPE_JITTER = (1.0, 1.5, 0.6)
#: A cave's bearing placement (random placement task 10, Requirement 7; the user
#: at the first look: "i would expect the potential for rooms to clump"). Each
#: edge keeps its wall side, but its far room stands at a drawn bearing off that
#: side's axis, uniform up to BEARING_MAX either way, not just slid along a shared
#: span, and at a drawn spacing BEARING_SPACING x a run (from close by the
#: separation gap to far): (spacing low, spacing high, offset floor) as
#: :func:`edge_jitter` reads them, the floor 0 so the share is uniform.
#: The bearing is clamped so the gap along the side's axis beats the gap
#: across it by BEARING_MARGIN corridor widths (:func:`_side_toward` keeps the
#: side, so each wall still holds one opening).
BEARING_SPACING = (0.25, 2.5, 0.0)
BEARING_MAX = math.radians(45.0)
BEARING_MARGIN = 2.0
#: The drawn share's power before it scales BEARING_MAX: under 1 leans the bearings
#: off the axes (the clamp above pulls some back toward them).
BEARING_POWER = 0.8
#: Unjoined rooms repel inside this many runs of each other in a bearing
#: placement (REPEL_RUNS elsewhere): at 1.5 runs no two chambers could clump.
BEARING_REPEL_RUNS = 1.0


class Jitter(NamedTuple):
    """A placement's per-edge jitter: ``edges`` {frozenset((a, b)): (spacing,
    offset share)} (:func:`edge_jitter`) and the span (u) facing rooms keep.
    ``bearing`` (radians, a cave's :data:`BEARING_MAX`; 0 otherwise) makes the
    share a bearing off the wall side's axis instead of a slide along the
    shared span; ``margin`` (u) is what the axis gap keeps over the cross gap."""

    edges: Dict[frozenset, Tuple[float, float]]
    need: float
    bearing: float = 0.0
    margin: float = 0.0

    def cross(self, across: float) -> float:
        """The offset a share of 1 moves across a wall: the slack."""
        return max(0.0, across - self.need)

    def offset(self, t: float, across: float, gap: float, ext: float) -> float:
        """How far across the wall a share ``t`` moves the far room: ``t`` x the
        slack, or (a bearing placement) the bearing ``t`` x :attr:`bearing` off
        the axis over the rest distance ``ext + gap``, kept short of turning
        the edge onto another wall side."""
        if not self.bearing:
            return t * self.cross(across)
        off = math.tan(abs(t) ** BEARING_POWER * self.bearing) * (ext + gap)
        off = min(off, max(0.0, across + gap - self.margin))
        return math.copysign(off, t)


def jitter_salt(order: Sequence[str], half: Dict[str, Point], seed: Optional[int] = None,
                draw: int = 0) -> str:
    """The build's salt for :func:`edge_jitter`: ``seed`` when given, else the
    rooms' ids and sizes (drawn from the build's rng before placement, so a
    build seed always gives the same salt and two seeds almost never share
    one). ``draw`` > 0 is a further draw for the same build (an Envelope
    build whose first leaves its entrance room facing away from the way in:
    ``GraphEngine.generate``, random placement task 3). Reads nothing from the
    rng."""
    salt = (f"seed:{int(seed)}" if seed is not None else
            "size:" + ";".join(f"{r}={half[r][0]:.6f},{half[r][1]:.6f}" for r in order))
    return f"{salt}|draw:{int(draw)}" if draw else salt


def edge_jitter(salt: str, a: str, b: str,
                ranges: Optional[Tuple[float, float, float]] = None) -> Tuple[float, float]:
    """(spacing factor, sideways offset share) of edge ``a``-``b`` for
    ``salt``: the factor within :data:`SPACING_LO`-:data:`SPACING_HI`, the
    share :data:`OFFSET_MIN` to :data:`OFFSET` either way, as the displacement of the greater id's room from the
    lesser's (so either end reads the same edge). ``ranges`` (spacing low,
    spacing high, offset floor) replaces the three (:data:`ENVELOPE_JITTER`)."""
    s_lo, s_hi, o_min = (SPACING_LO, SPACING_HI, OFFSET_MIN) if ranges is None else ranges
    lo, hi = (a, b) if a <= b else (b, a)
    h = hashlib.blake2b(f"{salt}|{lo}|{hi}".encode(), digest_size=8).digest()
    u1 = int.from_bytes(h[:4], "little") / 2 ** 32
    u2 = int.from_bytes(h[4:], "little") / 2 ** 32
    v = 2 * u2 - 1
    t = math.copysign(o_min + (OFFSET - o_min) * abs(v), v)
    return s_lo + (s_hi - s_lo) * u1, t


def _jitter_table(graph: TopologyGraph, order: Sequence[str], half: Dict[str, Point],
                  storeys: Optional[Dict[str, Any]], seed: Optional[int],
                  corridor_width: float, draw: int = 0,
                  ranges: Optional[Tuple[float, float, float]] = None,
                  centred: Optional[str] = None,
                  bearing: bool = False) -> Optional[Jitter]:
    """The :class:`Jitter` of every edge between rooms of ``order`` that
    takes one (not a stair, not a Bridge); None when there's none to take.
    The edges of room ``centred`` keep their spacing but no offset.
    ``bearing`` draws a cave's bearing placement (:data:`BEARING_SPACING`,
    :data:`BEARING_MAX`) instead."""
    if bearing:
        ranges = BEARING_SPACING
    if OFFSET == 0 and SPACING_LO == SPACING_HI == 1:
        return None
    salt = jitter_salt(order, half, seed, draw)
    keys = _plan_keys(graph, order, storeys)
    inset = set(order)
    out: Dict[frozenset, Tuple[float, float]] = {}
    for e in graph.edges():
        if e.a not in inset or e.b not in inset or BRIDGE_TAG in e.tags:
            continue
        if is_stair(keys[e.a], keys[e.b]):
            continue
        f, t = edge_jitter(salt, e.a, e.b, ranges)
        if bearing:
            f = _bearing_spacing(f)
        out[frozenset((e.a, e.b))] = (f, 0.0 if centred in (e.a, e.b) else t)
    if bearing:
        return Jitter(out, STRAIGHT_NEED * corridor_width, BEARING_MAX,
                      BEARING_MARGIN * corridor_width)
    return Jitter(out, STRAIGHT_NEED * corridor_width)


#: A bearing placement's clumps: this share of edges (the lowest draws) rest at
#: BEARING_CLUMP[1] runs, the rest spread over the remainder of
#: BEARING_SPACING, so chambers sit close in knots and far between them
#: (nearest-neighbour spread, stock CV 0.38).
BEARING_CLUMP = (0.3, 0.27)


def _bearing_spacing(f: float) -> float:
    """A drawn spacing (uniform over :data:`BEARING_SPACING`) as a bearing
    placement's: the lowest :data:`BEARING_CLUMP` share of draws at the clump's
    spacing, the rest uniform from the middle of the range up."""
    lo, hi, _ = BEARING_SPACING
    u = (f - lo) / (hi - lo) if hi > lo else 0.0
    share, close = BEARING_CLUMP
    if u < share:
        return close
    mid = (lo + hi) / 2
    return mid + (hi - mid) * (u - share) / (1.0 - share)


def _jitter_of(jitter: Optional[Jitter], a: str, b: str) -> Tuple[float, float]:
    """(spacing, offset share) for the edge's ``b`` seen from ``a``: the share
    signed as b's displacement from a. (1, 0) for an edge without one."""
    if not jitter:
        return 1.0, 0.0
    f, t = jitter.edges.get(frozenset((a, b)), (1.0, 0.0))
    return f, (t if b > a else -t)


def bridge_twins(graph: TopologyGraph, order: Sequence[str],
                 storeys: Optional[Dict[str, Any]]) -> Dict[str, List[frozenset]]:
    """For each room q, the pairs ``{u, h}`` it lays a Bridge between: q-u is
    a ``bridge``-tagged edge on one Level and h is q's stair partner on a
    lower Level (the least id), the room the
    Bridge is meant to cross. The start puts u on q's wall facing h (so the
    springs leave q over h's near part and u one run on, over the hall's
    middle), and that shared wall is not a wall clash. Empty without
    ``storeys`` or without tagged edges, so other graphs place as before."""
    out: Dict[str, List[frozenset]] = {}
    if storeys is None:
        return out
    inset = set(order)
    for e in graph.edges():
        if BRIDGE_TAG not in e.tags or e.a not in inset or e.b not in inset:
            continue
        if storeys[e.a].level != storeys[e.b].level:
            continue
        for q, u in ((e.a, e.b), (e.b, e.a)):
            lower = [m for m in graph.neighbours(q)
                     if m in inset and m != u and storeys[m].level < storeys[q].level]
            if lower:
                out.setdefault(q, []).append(frozenset((u, min(lower))))
                break
    return out


def _twin(twins: Dict[str, List[frozenset]], q: str, x: str, y: Optional[str]) -> bool:
    """Do ``x`` and ``y`` share q's wall as a Bridge and the hall it crosses?"""
    return y is not None and x != y and frozenset((x, y)) in twins.get(q, ())


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
#: A bearing start (task 10) tries at most this many of the roots x side
#: orders: each counts its crossings, so all 64 cost a 30-room cave ~5x its
#: draw time.
BEARING_START_TRIES = 64
#: ... and past this many rooms, this many.
BEARING_BIG = (20, 64)
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
    twins = bridge_twins(graph, order, storeys)
    bad = 0
    for u in order:
        walls = [_side_toward(pos[u], half[u], pos[m], half[m])
                 for m in graph.neighbours(u) if m in inset]
        bad += len(walls) - len(set(walls))
        if u in twins:
            nb = [m for m in graph.neighbours(u) if m in inset]
            for pair in twins[u]:
                x, y = tuple(pair)
                if (x in nb and y in nb and walls[nb.index(x)] == walls[nb.index(y)]
                        and walls.count(walls[nb.index(x)]) == 2):
                    bad -= 1
    for i, a in enumerate(order):
        for b in order[i + 1:]:
            if (not may_overlap_in_plan(keys[a], keys[b])
                    and _box_gap(pos[a], half[a], pos[b], half[b]) < gap - 1e-6):
                bad += 1
    return bad


def start_positions(graph: TopologyGraph, order: Sequence[str],
                    half: Dict[str, Point], run: float, gap: float,
                    storeys: Optional[Dict[str, Any]] = None,
                    jitter: Optional[Jitter] = None
                    ) -> Dict[str, Point]:
    """The best of :func:`start_once` over START_ROOTS roots (the first room,
    then the best-connected) and :data:`SIDE_ORDERS` (fewest
    :func:`layout_clashes`, the first on a tie; a clash-free start ends the
    search), then :func:`repair` if it still clashes. ``jitter`` goes to
    :func:`start_once`."""
    inset = set(order)
    deg = {r: sum(1 for m in graph.neighbours(r) if m in inset) for r in order}
    rank = {r: k for k, r in enumerate(order)}
    roots = list(order[:1]) + sorted(order[1:], key=lambda r: (-deg[r], rank[r]))[:START_ROOTS - 1]
    best = None
    bearing = jitter is not None and jitter.bearing
    tries = 0
    for root in roots:
        for sides in SIDE_ORDERS:
            tries += 1
            if bearing and tries > (BEARING_START_TRIES if len(order) <= BEARING_BIG[0]
                                    else BEARING_BIG[1]):
                break
            if bearing:
                # A bearing start (task 10) also counts its edges' crossings and
                # keeps the bearings it settled on for the springs.
                scales: Dict[frozenset, float] = {}
                pos = start_once(graph, order, half, run, gap, sides, root, storeys, jitter,
                                 scales)
                clashes = layout_clashes(graph, order, pos, half, gap, storeys)
                if best is not None and clashes > best[0][0]:
                    continue             # can't win: crossings only break a tie
                score = (clashes, plan_crossings(graph, order, pos, half,
                                                 jitter.need / STRAIGHT_NEED, storeys))
                done = score == (0, 0)
                pos = (pos, scales)
            else:
                pos = start_once(graph, order, half, run, gap, sides, root, storeys, jitter)
                score = layout_clashes(graph, order, pos, half, gap, storeys)
                done = score == 0
            if best is None or score < best[0]:
                best = (score, pos)
            if done:
                break
        if (best[0] == (0, 0)) if bearing else best[0] == 0:
            break
    pos = best[1]
    if bearing:
        pos, scales = pos
        for e, s in scales.items():
            if e not in jitter.edges:          # a stair or Bridge: no jitter
                continue
            f, t = jitter.edges[e]
            jitter.edges[e] = (f, t * s)
    if (best[0][0] if bearing else best[0]):
        repair(graph, order, pos, half, run, gap, storeys)
    return pos


#: The bearings a bearing start tries per wall side, as shares of the edge's
#: drawn one: the drawn bearing, then nearer the side's axis, when it would
#: cross a placed room or edge (:func:`_start_crossings`).
BEARING_FALLBACK = (1.0, -1.0)


#: Where a bearing placement's door may stand along its wall: a corridor width
#: and the inset from either end of the wall, and this far (u) more. A door's
#: stub reaches a half width round it and the inset plus a half width into the
#: room, so two doors on walls meeting at a corner keep their stubs apart (Job
#: B drops a corridor whose floor meets another's, ``_resolve_conflicts``).
DOOR_END_MARGIN = 1.0
#: The wall-point inset Job B cuts doors at (``LayoutGenerator._wall_point``).
DOOR_INSET = 2.0


def bearing_door(c: Point, h: Point, to: Point, exit_x: bool, width: float) -> Optional[float]:
    """A bearing placement's door along the wall of the room at ``c`` (half-
    extents ``h``) facing a room centred at ``to`` (task 10): where the line
    between the centres crosses the wall, kept a half ``width`` and
    :data:`DOOR_END_MARGIN` off the wall's ends. None when the wall is too short."""
    ax = 0 if exit_x else 1
    d_ax, d_cr = to[ax] - c[ax], to[1 - ax] - c[1 - ax]
    lo, hi = door_span(c[1 - ax] - h[1 - ax], c[1 - ax] + h[1 - ax], width)
    if hi < lo:
        return None
    slope = d_cr / d_ax if d_ax else 0.0
    return min(hi, max(lo, c[1 - ax] + slope * h[ax]))


def door_span(lo: float, hi: float, width: float) -> Tuple[float, float]:
    """Where a bearing placement's door centre may stand on a wall running
    ``lo``..``hi``: a corridor width, the inset and :data:`DOOR_END_MARGIN` in
    from each end (empty, hi < lo, on a short wall)."""
    m = width + DOOR_INSET + DOOR_END_MARGIN
    return lo + m, hi - m


def _edge_rects_drawn(pa: Point, ha: Point, pb: Point, hb: Point, width: float) -> List[Tuple[float, float, float, float]]:
    """The floor rects of the corridor Job B would route between two rooms of a
    bearing placement (doors straight across a shared span that holds
    :data:`STRAIGHT_NEED` widths, else at :func:`bearing_door`): what
    :func:`_start_crossings` tests."""
    from generators.routing import exit_axis_x, plan_route, route_footprint
    ex_a = exit_axis_x(pa[0], pa[1], ha[0], ha[1], pb[0], pb[1], hb[0], hb[1])
    ex_b = exit_axis_x(pb[0], pb[1], hb[0], hb[1], pa[0], pa[1], ha[0], ha[1])

    def door(c, h, oc, oh, ex):
        ax = 0 if ex else 1
        across = None
        if ex_a == ex_b:
            lo = max(c[1 - ax] - h[1 - ax], oc[1 - ax] - oh[1 - ax])
            hi = min(c[1 - ax] + h[1 - ax], oc[1 - ax] + oh[1 - ax])
            if hi - lo >= STRAIGHT_NEED * width:
                lo = max(lo, door_span(c[1 - ax] - h[1 - ax], c[1 - ax] + h[1 - ax], width)[0],
                         door_span(oc[1 - ax] - oh[1 - ax], oc[1 - ax] + oh[1 - ax], width)[0])
                hi = min(hi, door_span(c[1 - ax] - h[1 - ax], c[1 - ax] + h[1 - ax], width)[1],
                         door_span(oc[1 - ax] - oh[1 - ax], oc[1 - ax] + oh[1 - ax], width)[1])
                if hi >= lo:
                    across = (lo + hi) / 2
        if across is None:
            across = bearing_door(c, h, oc, ex, width)
        if across is None:
            across = c[1 - ax]
        wall = c[ax] + (h[ax] - DOOR_INSET) * (1 if oc[ax] >= c[ax] else -1)
        return (wall, across) if ex else (across, wall)

    route = plan_route(door(pa, ha, pb, hb, ex_a), door(pb, hb, pa, ha, ex_b), ex_a, ex_b,
                       width / 2, 0)
    return _Rects(route_footprint(route, width / 2))


#: Most entries :func:`_memo_rects` keeps before it starts afresh.
RECTS_MEMO_MAX = 200_000


def _memo_rects(draw):
    """``draw(pa, ha, pb, hb, width)`` remembered by its arguments' values: the
    bearing start asks again for most routes it drew (a placed corridor for each
    candidate, a pair at each try). The rects it returns are shared: read only."""
    memo: Dict[Tuple, Any] = {}

    @functools.wraps(draw)
    def rects(pa, ha, pb, hb, width):
        key = (float(pa[0]), float(pa[1]), float(ha[0]), float(ha[1]),
               float(pb[0]), float(pb[1]), float(hb[0]), float(hb[1]), float(width))
        got = memo.get(key)
        if got is None:
            if len(memo) >= RECTS_MEMO_MAX:
                memo.clear()
            got = memo[key] = draw(pa, ha, pb, hb, width)
        return got
    return rects


class _Rects(list):
    """A corridor's floor rects with their bounding box (``box``), so the
    crossing tests skip pairs that can't meet."""

    def __init__(self, rects=()):
        super().__init__(rects)
        self.box = ((min(r[0] for r in self), min(r[1] for r in self),
                     max(r[2] for r in self), max(r[3] for r in self)) if self else None)


def _rects_hit(rects, c: Point, h: Point, eps: float = 1.0) -> bool:
    x0, y0, x1, y1 = c[0] - h[0], c[1] - h[1], c[0] + h[0], c[1] + h[1]
    box = getattr(rects, "box", 0)
    if box is None or (box and (box[2] - x0 <= eps or x1 - box[0] <= eps
                                or box[3] - y0 <= eps or y1 - box[1] <= eps)):
        return False
    return any(min(r[2], x1) - max(r[0], x0) > eps and min(r[3], y1) - max(r[1], y0) > eps
               for r in rects)


def _rects_meet(ra, rb, eps: float = 1e-6, inside: Optional[Tuple[Point, Point]] = None) -> bool:
    """Do two corridors' rects overlap (outside the box ``inside``, (centre,
    half-extents): the room two corridors share)?"""
    ba, bb = getattr(ra, "box", 0), getattr(rb, "box", 0)
    if ba is None or bb is None or (ba and bb and (
            min(ba[2], bb[2]) - max(ba[0], bb[0]) <= eps or min(ba[3], bb[3]) - max(ba[1], bb[1]) <= eps)):
        return False
    for a in ra:
        for b in rb:
            x0, x1 = max(a[0], b[0]), min(a[2], b[2])
            y0, y1 = max(a[1], b[1]), min(a[3], b[3])
            if x1 - x0 <= eps or y1 - y0 <= eps:
                continue
            if inside is not None:
                (cx, cy), (hx, hy) = inside
                if x0 >= cx - hx - eps and x1 <= cx + hx + eps and \
                        y0 >= cy - hy - eps and y1 <= cy + hy + eps:
                    continue
            return True
    return False


def _corridor_rects(a: str, b: str, pos: Dict[str, Point], half: Dict[str, Point],
                    nodes: Dict[str, Any], width: float,
                    others: Sequence[Tuple[Tuple[str, str], list]] = ()
                    ) -> List[Tuple[float, float, float, float]]:
    """What :func:`crossing_edges` reads of edge a-b's corridor: Job B's route
    (:func:`_edge_rects`), or for a stair the first of its ways
    (:func:`_stair_rects`) that crosses the fewest rooms beside it and meets
    the fewest of the corridors ``others`` ((edge, rects)), as Job B takes
    the first clear one (``_stair_candidates``)."""
    if not is_stair(nodes[a], nodes[b]):
        return _edge_rects(pos[a], half[a], pos[b], half[b], width)
    best, fewest = _Rects(), None
    for rects in _stair_rects(pos[a], half[a], pos[b], half[b], width):
        hits = sum(1 for r in pos if r not in (a, b) and _rects_hit(rects, pos[r], half[r])
                   and _beside(nodes, r, a, b))
        for (c, d), theirs in others:
            if len({a, b} & {c, d}) > 1:
                continue
            shared = ({a, b} & {c, d}) or None
            inside = (pos[next(iter(shared))], half[next(iter(shared))]) if shared else None
            if _rects_meet(rects, theirs, inside=inside) and (
                    _beside(nodes, c, a, b) or _beside(nodes, d, a, b)):
                hits += 1
        if fewest is None or hits < fewest:
            best, fewest = rects, hits
            if not hits:
                break
    return best


def _stair_rects_drawn(pa: Point, ha: Point, pb: Point, hb: Point, width: float
                       ) -> List[List[Tuple[float, float, float, float]]]:
    """The floor rects of the ways Job B tries a stair between two rooms on
    different Levels (``LayoutGenerator._stair_candidates``), in its order:
    between their facing walls when they stand a corridor apart, then a
    U-route on each side (across the pair's offset first) with its doors at
    the walls' far ends."""
    from generators.geometry import MIN_LANE
    from generators.layout import U_CORNER_MARGIN
    from generators.routing import exit_axis_x, plan_u_route, route_footprint
    hw = width / 2
    out = []
    ex = exit_axis_x(pa[0], pa[1], ha[0], ha[1], pb[0], pb[1], hb[0], hb[1])
    ax = 0 if ex else 1
    if abs(pb[ax] - pa[ax]) - (ha[ax] + hb[ax]) >= width:
        out.append(_edge_rects(pa, ha, pb, hb, width))
    across_x = abs(pb[0] - pa[0]) >= abs(pb[1] - pa[1])
    for side in (("N", "S", "E", "W") if across_x else ("E", "W", "N", "S")):
        sx = side in ("E", "W")
        sign = 1.0 if side in ("N", "E") else -1.0
        w, t = (0, 1) if sx else (1, 0)
        reach_a, reach_b = ha[t] - hw - U_CORNER_MARGIN, hb[t] - hw - U_CORNER_MARGIN
        if reach_a < 0 or reach_b < 0:
            continue
        sgn = 1.0 if pb[t] >= pa[t] else -1.0
        da, db = pa[t] - sgn * reach_a, pb[t] + sgn * reach_b
        if abs(db - da) < 2 * hw + 2 * MIN_LANE:
            continue
        wa = pa[w] + sign * (ha[w] - DOOR_INSET)
        wb = pb[w] + sign * (hb[w] - DOOR_INSET)
        fa, fb = ((wa, da), (wb, db)) if sx else ((da, wa), (db, wb))
        out.append(_Rects(route_footprint(plan_u_route(fa, fb, side, width), hw)))
    return out


_edge_rects = _memo_rects(_edge_rects_drawn)
_stair_rects = _memo_rects(_stair_rects_drawn)


def _beside(nodes: Dict[str, Any], r: str, a: str, b: str) -> bool:
    """Is room (or a corridor's room) ``r`` on a Level corridor a-b passes,
    with no Slab between (it may stand in the way)?"""
    over = getattr(nodes, "over", None)
    if over is not None:
        return not ((r, a) in over and (r, b) in over)
    return not (may_overlap_in_plan(nodes[r], nodes[a]) and may_overlap_in_plan(nodes[r], nodes[b]))


def _start_crossings(u: str, c: Point, nbrs: Sequence[str], placed: Sequence[Tuple[str, str]],
                     pos: Dict[str, Point], half: Dict[str, Point], nodes: Dict[str, Any],
                     width: float, routes: Dict[Any, Any]) -> int:
    """Room ``u`` at ``c``: its corridors to placed ``nbrs`` (as Job B would
    route them, :func:`_corridor_rects`) through a placed room or across a
    placed corridor, plus placed corridors through u's box. ``routes`` caches
    the placed corridors' rects, and (as arrays, :class:`_Placed`) what one
    ``placed`` list reads, for every candidate of one room."""
    got = routes.get(_PLACED)
    if got is None or got.placed is not placed or got.n != len(pos):
        for a, b in placed:
            if (a, b) not in routes:
                routes[(a, b)] = _corridor_rects(a, b, pos, half, nodes, width,
                                                 [(e, r) for e, r in routes.items() if e is not _PLACED])
        got = routes[_PLACED] = _Placed(placed, pos, half, routes)
    bad = 0
    x0, y0, x1, y1 = c[0] - half[u][0], c[1] - half[u][1], c[0] + half[u][0], c[1] + half[u][1]
    R = got.rects
    if len(R):
        hit = (np.minimum(R[:, 2], x1) - np.maximum(R[:, 0], x0) > 1.0) & \
              (np.minimum(R[:, 3], y1) - np.maximum(R[:, 1], y0) > 1.0)
        for k in sorted(set(got.owner[hit].tolist())):
            a, b = placed[k]
            if _beside(nodes, u, a, b):
                bad += 1
    mine_all = []
    for m in nbrs:
        # As _corridor_rects would draw it (a stair: its first way that hits
        # least), counted as it counts a stair's ways.
        if is_stair(nodes[u], nodes[m]):
            mine, fewest = _Rects(), None
            for rects in _stair_rects(c, half[u], pos[m], half[m], width):
                n = got.score(rects, u, m, pos, half, nodes)
                if fewest is None or n < fewest:
                    mine, fewest = rects, n
                    if not n:
                        break
            bad += fewest or 0
        else:
            mine = _edge_rects(c, half[u], pos[m], half[m], width)
            bad += got.score(mine, u, m, pos, half, nodes)
        mine_all.append(mine)
    # u's own corridors meeting outside u.
    for k, ra in enumerate(mine_all):
        for rb in mine_all[k + 1:]:
            if _rects_meet(ra, rb, inside=(c, half[u])):
                bad += 1
    return bad


#: :func:`_start_crossings`'s key in its ``routes`` cache for :class:`_Placed`.
_PLACED = object()


class _Placed:
    """What :func:`_start_crossings` reads of one ``placed`` list, as arrays:
    every placed corridor's rects (``rects``, with ``owner`` the index of its
    edge in ``placed``) and the placed rooms' boxes (``boxes``, ``rooms``)."""

    def __init__(self, placed, pos, half, routes):
        self.placed = placed
        self.n = len(pos)
        rects, owner = [], []
        for k, e in enumerate(placed):
            for r in routes[e]:
                rects.append(r)
                owner.append(k)
        self.rects = np.array(rects, dtype=float).reshape(-1, 4)
        self.owner = np.array(owner, dtype=int)
        self.rooms = list(pos)
        self.boxes = np.array([(pos[r][0] - half[r][0], pos[r][1] - half[r][1],
                                pos[r][0] + half[r][0], pos[r][1] + half[r][1]) for r in self.rooms],
                              dtype=float).reshape(-1, 4)
        self._has: Dict[str, np.ndarray] = {}
        # Boxes then rects, to overlap with a corridor's rects in one pass.
        self.nb = len(self.boxes)
        self.both = np.vstack([self.boxes, self.rects])

    def score(self, rects, u: str, m: str, pos, half, nodes) -> int:
        """Room u's corridor to placed room m on ``rects``: the placed rooms
        (not m) it passes through on its Levels, plus the placed corridors it
        meets (outside m, when they leave m too)."""
        if not rects:
            return 0
        M = getattr(rects, "arr", None)
        if M is None:
            M = np.array(rects, dtype=float)
            if isinstance(rects, _Rects):
                rects.arr = M
        bad = 0
        A, nb = self.both, self.nb
        X0 = np.maximum(M[:, None, 0], A[None, :, 0])
        X1 = np.minimum(M[:, None, 2], A[None, :, 2])
        Y0 = np.maximum(M[:, None, 1], A[None, :, 1])
        Y1 = np.minimum(M[:, None, 3], A[None, :, 3])
        if nb:
            ox, oy = X1[:, :nb] - X0[:, :nb], Y1[:, :nb] - Y0[:, :nb]
            for j in np.nonzero(((ox > 1.0) & (oy > 1.0)).any(axis=0))[0].tolist():
                r = self.rooms[j]
                if r != m and _beside(nodes, r, u, m):
                    bad += 1
        if len(A) > nb:
            ix0, ix1, iy0, iy1 = X0[:, nb:], X1[:, nb:], Y0[:, nb:], Y1[:, nb:]
            meet = (ix1 - ix0 > 1e-6) & (iy1 - iy0 > 1e-6)
            if meet.any():
                (mx, my), (hx, hy) = pos[m], half[m]
                eps = 1e-6
                inside = (ix0 >= mx - hx - eps) & (ix1 <= mx + hx + eps) & \
                         (iy0 >= my - hy - eps) & (iy1 <= my + hy + eps)
                meet &= ~(inside & self.has(m)[None, :])
                for k in sorted(set(self.owner[meet.any(axis=0)].tolist())):
                    a, b = self.placed[k]
                    if _beside(nodes, a, u, m) or _beside(nodes, b, u, m):
                        bad += 1
        return bad

    def has(self, m: str) -> np.ndarray:
        """Per rect: is its corridor one of room m's?"""
        if m not in self._has:
            self._has[m] = np.array([m in self.placed[k] for k in self.owner.tolist()], dtype=bool)
        return self._has[m]


def plan_crossings(graph: TopologyGraph, order: Sequence[str], pos: Dict[str, Point],
                   half: Dict[str, Point], width: float,
                   storeys: Optional[Dict[str, Any]] = None) -> int:
    """Corridors (as Job B would route them in a bearing placement,
    :func:`_corridor_rects`) through a third room on their Levels, plus pairs
    of corridors that meet outside a room they share: what Job B splits or
    drops (``_resolve_crossings``, ``_resolve_conflicts``)."""
    return len(crossing_edges(graph, order, pos, half, width, storeys)[1])


def crossing_edges(graph: TopologyGraph, order: Sequence[str], pos: Dict[str, Point],
                   half: Dict[str, Point], width: float,
                   storeys: Optional[Dict[str, Any]] = None
                   ) -> Tuple[set, List[Tuple]]:
    """(the edges in a crossing, the crossings) of :func:`plan_crossings`."""
    keys = _plan_keys(graph, order, storeys)
    inset = set(order)
    segs = [(e.a, e.b) for e in graph.edges() if e.a in inset and e.b in inset
            and e.a in pos and e.b in pos]
    # Level corridors first, then each stair on its way clear of them.
    rects = {s: _corridor_rects(s[0], s[1], pos, half, keys, width) for s in segs
             if not is_stair(keys[s[0]], keys[s[1]])}
    for s in segs:
        if s not in rects:
            rects[s] = _corridor_rects(s[0], s[1], pos, half, keys, width, list(rects.items()))
    hits: List[Tuple] = []
    # Which pairs could meet at all, by bounding box (with the eps _rects_hit
    # and _rects_meet allow), before the exact tests, in the same order.
    rooms = list(pos)
    rb = np.array([(pos[r][0] - half[r][0], pos[r][1] - half[r][1],
                    pos[r][0] + half[r][0], pos[r][1] + half[r][1]) for r in rooms],
                  dtype=float).reshape(-1, 4)
    cb = np.array([rects[s].box if getattr(rects[s], "box", None) else (np.inf, np.inf, -np.inf, -np.inf)
                   for s in segs], dtype=float).reshape(-1, 4)
    near_room = ((np.minimum(cb[:, None, 2], rb[None, :, 2]) - np.maximum(cb[:, None, 0], rb[None, :, 0]) > 1.0)
                 & (np.minimum(cb[:, None, 3], rb[None, :, 3]) - np.maximum(cb[:, None, 1], rb[None, :, 1]) > 1.0))
    near_cor = ((np.minimum(cb[:, None, 2], cb[None, :, 2]) - np.maximum(cb[:, None, 0], cb[None, :, 0]) > 1e-6)
                & (np.minimum(cb[:, None, 3], cb[None, :, 3]) - np.maximum(cb[:, None, 1], cb[None, :, 1]) > 1e-6))
    for k, (a, b) in enumerate(segs):
        for j in np.nonzero(near_room[k])[0].tolist():
            r = rooms[j]
            if r not in (a, b) and _rects_hit(rects[(a, b)], pos[r], half[r]) \
                    and _beside(keys, r, a, b):
                hits.append(((a, b), r))
    for k, (a, b) in enumerate(segs):
        for m in np.nonzero(near_cor[k, k + 1:])[0].tolist():
            c, d = segs[k + 1 + m]
            shared = {a, b} & {c, d}
            if len(shared) > 1:
                continue
            inside = None
            if shared:
                (s,) = shared
                inside = (pos[s], half[s])
            if _rects_meet(rects[(a, b)], rects[(c, d)], inside=inside) and (
                    _beside(keys, c, a, b) or _beside(keys, d, a, b)):
                hits.append(((a, b), (c, d)))
    edges = set()
    for x, y in hits:
        edges.add(frozenset(x))
        if isinstance(y, tuple):
            edges.add(frozenset(y))
    return edges, hits


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
    twins = bridge_twins(graph, order, storeys)
    dirs = dict(SIDES)

    def side(a: str, pa: Point, b: str, pb: Point) -> str:
        return _side_toward(pa, half[a], pb, half[b])

    def local(u: str, c: Point) -> int:
        bad = 0
        mine = [side(u, c, m, pos[m]) for m in nbrs[u]]
        bad += len(mine) - len(set(mine))
        for pair in twins.get(u, ()):
            x, y = tuple(pair)
            if (x in nbrs[u] and y in nbrs[u] and mine[nbrs[u].index(x)] == mine[nbrs[u].index(y)]
                    and mine.count(mine[nbrs[u].index(x)]) == 2):
                bad -= 1
        for m in nbrs[u]:
            sm = side(m, pos[m], u, c)
            bad += sum(1 for x in nbrs[m] if x != u and side(m, pos[m], x, pos[x]) == sm
                       and not _twin(twins, m, u, x))
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
               storeys: Optional[Dict[str, Any]] = None,
               jitter: Optional[Jitter] = None,
               scales: Optional[Dict[frozenset, float]] = None
               ) -> Dict[str, Point]:
    """Breadth-first start: each room beside a placed neighbour on a free wall
    side, or in the corner where two placed neighbours' free sides meet.
    ``jitter`` (:func:`_jitter_table`) moves "beside" by each edge's spacing
    and offset; None places every neighbour centred one run off the wall.

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
    twins = bridge_twins(graph, order, storeys)
    dirs = dict(SIDES)

    bearing = jitter is not None and jitter.bearing
    routes: Dict[Tuple[str, str], list] = {}      # placed corridors' rects (bearing)

    def beside(q: str, u: str, d: Point, scale: float = 1.0) -> Point:
        # One run (times the edge's spacing) past q's wall, moved along it
        # by the edge's offset share of the two rooms' half-extents across
        # (a bearing placement: its bearing, times ``scale`` toward the axis).
        dx, dy = d
        f, t = _jitter_of(jitter, q, u)
        ext = abs(dx) * (half[q][0] + half[u][0]) + abs(dy) * (half[q][1] + half[u][1])
        across = abs(dx) * (half[q][1] + half[u][1]) + abs(dy) * (half[q][0] + half[u][0])
        off = jitter.offset(t * scale if bearing else t, across, run * f, ext) if jitter else 0.0
        return (pos[q][0] + dx * (ext + run * f) + abs(dy) * off,
                pos[q][1] + dy * (ext + run * f) + abs(dx) * off)

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
        # A Bridge's far room and the hall it crosses share q's wall: each
        # may take the wall facing the other (bridge_twins).
        twin_side = {q: _side_toward(pos[q], half[q], pos[w], half[w])
                     for q in placed_nbrs for w in pos if _twin(twins, q, u, w)}
        for qk, q in enumerate(placed_nbrs):
            sides = free[q] or (list(side_order) if qk == 0 else [])
            if q in twin_side and twin_side[q] not in sides:
                sides = sides + [twin_side[q]]
            for k, sd in enumerate(sides):
                if bearing:
                    # The drawn bearing first, then nearer the axis (task 10).
                    for si, s in enumerate(BEARING_FALLBACK):
                        cands.append(((qk, k, si), beside(q, u, dirs[sd], s), (q, s)))
                else:
                    cands.append(((qk, k), beside(q, u, dirs[sd]), None))
        npl = len(placed_nbrs)
        for qk, q in enumerate(placed_nbrs):
            for rk, r in enumerate(placed_nbrs):
                if r == q:
                    continue
                for sx in (sd for sd in free[q] if sd in "EW"):
                    for sy in (sd for sd in free[r] if sd in "NS"):
                        c = (beside(q, u, dirs[sx])[0], beside(r, u, dirs[sy])[1])
                        cands.append(((npl + qk, rk), c, None))
        if bearing:
            # Edges already placed, and the placed rooms u's own edges may pass.
            placed_edges = [(e.a, e.b) for e in graph.edges()
                            if e.a in pos and e.b in pos]
        best = None
        for tie, c, how in cands:
            walls = 0
            miss = 0
            mine = set()
            for m in placed_nbrs:
                sm = _side_toward(pos[m], half[m], c, half[u])
                su = _side_toward(c, half[u], pos[m], half[m])
                walls += (sm in used[m] and not _twin(twins, m, u, used[m][sm])) + (su in mine)
                mine.add(su)
                miss += m in twin_side and sm != twin_side[m]
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
            if bearing:
                if best is not None and (2 * walls + clashes, clashes) > best[0][:2]:
                    continue        # can't win: skip counting its crossings
                cross = _start_crossings(u, c, placed_nbrs, placed_edges, pos, half, nodes,
                                         jitter.need / STRAIGHT_NEED, routes)
                key = (2 * walls + clashes, clashes, cross, miss, rings, round(close, 6), -room,
                       tie)
            else:
                key = (2 * walls + clashes, clashes, miss, rings, round(close, 6), -room, tie)
            if best is None or key < best[0]:
                best = (key, c, how)
        pos[u] = best[1]
        if scales is not None and best[2] is not None:
            q, s = best[2]
            scales[frozenset((q, u))] = s
        for m in placed_nbrs:
            used[m].setdefault(_side_toward(pos[m], half[m], pos[u], half[u]), u)
            used[u].setdefault(_side_toward(pos[u], half[u], pos[m], half[m]), m)
    return pos


def _overlap_matrix(rooms: Sequence[Any], slab: float = SLAB) -> np.ndarray:
    """:func:`may_overlap_in_plan` of every pair of ``rooms``, as a matrix."""
    n = len(rooms)
    lv = [getattr(r, "level", None) for r in rooms]
    if n == 0 or any(v is None for v in lv):
        out = np.zeros((n, n), dtype=bool)
        known = [k for k, v in enumerate(lv) if v is not None]
        if len(known) > 1:
            sub = _overlap_matrix([rooms[k] for k in known], slab)
            out[np.ix_(known, known)] = sub
        return out
    L = np.array(lv, dtype=float)
    F = np.array([r.floor for r in rooms], dtype=float)
    C = np.array([r.ceiling for r in rooms], dtype=float)
    up = L[:, None] < L[None, :]          # a below b: b's floor less a's ceiling
    gap = np.where(up, F[None, :] - C[:, None], F[:, None] - C[None, :])
    return (L[:, None] != L[None, :]) & (gap >= slab - 1e-9)


def spring_relax(order: Sequence[str], edges: Sequence[Tuple[str, str]],
                 pos: Dict[str, Point], half: Dict[str, Point], nodes: Dict[str, Any],
                 run: float, gap: float,
                 iterations: Optional[int] = None,
                 jitter: Optional[Jitter] = None
                 ) -> Dict[str, Point]:
    """Spring iterations: each edge keeps the wall side it starts on (b rests
    one run past a's wall on that axis, times the edge's ``jitter`` spacing,
    and moved along the wall by its offset, as :func:`start_once` put it: an
    offset under 1 keeps the rooms facing, so the side holds); every other pair repels, more
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
    # Each edge's spacing on its run and offset along the wall (b's from a),
    # on the axis across S.
    J = np.array([_jitter_of(jitter, a, b) for a, b in edges], dtype=float).reshape(-1, 2)
    T = S[:, ::-1].copy()
    T[:] = np.abs(T)
    joined = np.zeros((n, n), dtype=bool)
    if len(E):
        joined[E[:, 0], E[:, 1]] = True
        joined[E[:, 1], E[:, 0]] = True
    apart = ~_overlap_matrix([nodes[r] for r in order])
    np.fill_diagonal(apart, False)
    # Joined rooms repel only inside the separation gap (their spring does the
    # rest); others inside REPEL_RUNS runs.
    repel = BEARING_REPEL_RUNS if jitter is not None and jitter.bearing else REPEL_RUNS
    reach = np.where(joined, gap, gap + repel * run)
    np.fill_diagonal(reach, 0.0)
    iu = np.triu_indices(n, 1)
    # A bearing placement's edges on one Level, held on their sides outright.
    hold = (~stair) if jitter is not None and jitter.bearing and len(E) else None

    # What the loop reads that no step changes, worked out once, by the same
    # expressions (so the same floats) the loop used to work out each step.
    if len(E):
        a, b = E[:, 0], E[:, 1]
        ext = (np.abs(S[:, 0]) * (H[a, 0] + H[b, 0])
               + np.abs(S[:, 1]) * (H[a, 1] + H[b, 1]))
        rest = ext + run * J[:, 0]
        if stair.any():
            # (rest less the run, not ext: the same floats as before jitter.)
            rest = np.where(stair, (rest - run * J[:, 0]) * STAIR_REST, rest)
        across = (np.abs(S[:, 0]) * (H[a, 1] + H[b, 1])
                  + np.abs(S[:, 1]) * (H[a, 0] + H[b, 0]))
        if jitter is not None and jitter.bearing:
            # A cave's bearing (task 10): the far room off the side's axis by
            # its drawn angle over the rest distance, short of the other side.
            gapv = rest - ext
            slack = np.minimum(np.tan(np.abs(J[:, 1]) ** BEARING_POWER * jitter.bearing) * rest,
                               np.maximum(0.0, across + gapv - jitter.margin))
            slack = np.where(stair, 0.0, np.copysign(slack, J[:, 1]))
            pull_s, pull_t = S * rest[:, None], T * slack[:, None]
        else:
            slack = np.maximum(0.0, across - (jitter.need if jitter else 0.0))
            pull_s, pull_t = S * rest[:, None], T * (J[:, 1] * slack)[:, None]
    ri, rj = iu
    hx, hy = H[ri, 0] + H[rj, 0], H[ri, 1] + H[rj, 1]
    want_all = reach[ri, rj]
    # Coincident centres: a fixed direction by index, deterministic.
    fall_all = np.stack([np.cos(ri + 0.5 * rj), np.sin(ri + 0.5 * rj)], axis=1)
    apart_all = apart[ri, rj]
    held = _HoldSums(H, E, S, T) if hold is not None else None

    for it in range(iterations):
        step = STEP_START + (STEP_END - STEP_START) * it / max(1, iterations - 1)
        F = np.zeros_like(P)
        if len(E):
            d = P[b] - P[a]
            f = K_SPRING * (d - pull_s - pull_t)
            at, push = [a, b], [f, -f]
        else:
            at, push = [], []
        # Repulsion over every pair kept apart in plan.
        d = P[rj] - P[ri]
        gx = np.abs(d[:, 0]) - hx
        gy = np.abs(d[:, 1]) - hy
        g = np.maximum(gx, gy)
        hit = apart_all & (g < want_all)
        if hit.any():
            i, j, d, g, want = ri[hit], rj[hit], d[hit], g[hit], want_all[hit]
            dist = np.hypot(d[:, 0], d[:, 1])
            fallback = fall_all[hit]
            u = np.where(dist[:, None] < 1e-6, fallback, d / np.maximum(dist, 1e-6)[:, None])
            depth = (want - g) / np.maximum(want, 1e-6)        # 0 at reach, 1 at touching
            mag = K_REPEL * (want - g) * (1.0 + depth)
            f = mag[:, None] * u
            at += [i, j]
            push += [-f, f]
        if at:
            # Summed per room in the order np.add.at would (springs' a then b, then
            # the repulsions' i then j), from zero: the same floats, in one pass.
            k = np.concatenate(at)
            w = np.concatenate(push)
            F[:, 0] = np.bincount(k, weights=w[:, 0], minlength=n)
            F[:, 1] = np.bincount(k, weights=w[:, 1], minlength=n)
        P += step * F
        if hold is not None and it % HOLD_EVERY == 0:
            _hold_sides(P, H, E, S, T, hold, held)
    if hold is not None:
        # The last step's pushes can tip a neighbour; settle (task 10).
        for _ in range(HOLD_PASSES):
            if not _hold_sides(P, H, E, S, T, hold, held):
                break
    return {r: (float(P[k, 0]), float(P[k, 1])) for k, r in enumerate(order)}


#: A bearing placement holds each edge's wall side outright (task 10): when
#: the gap across the side's axis comes within HOLD_MARGIN u of the gap along
#: it, the pair is pushed apart along the axis. Settled after the springs in
#: at most HOLD_PASSES passes.
HOLD_MARGIN = 2.0
#: ... checked every HOLD_EVERY spring iterations (and settled after them).
HOLD_EVERY = 1
HOLD_PASSES = 50


def _HoldSums(H: np.ndarray, E: np.ndarray, S: np.ndarray, T: np.ndarray
              ) -> Tuple[np.ndarray, np.ndarray]:
    """What :func:`_hold_sides` reads of the rooms' half-extents, per edge: the
    two rooms' extents along its side's axis and across it."""
    a, b = E[:, 0], E[:, 1]
    return (np.abs(S) * (H[a] + H[b])).sum(axis=1), (T * (H[a] + H[b])).sum(axis=1)


def _hold_sides(P: np.ndarray, H: np.ndarray, E: np.ndarray, S: np.ndarray, T: np.ndarray,
                hold: np.ndarray, sums: Optional[Tuple[np.ndarray, np.ndarray]] = None) -> bool:
    """Push apart, along its side's axis, each held edge (``hold``) whose gap
    along that axis is not HOLD_MARGIN past its gap across it, so
    :func:`_side_toward` keeps the side. True when any edge was pushed.
    ``sums``: :func:`_HoldSums` of the same H, E, S, T, when worked out."""
    if sums is None:
        sums = _HoldSums(H, E, S, T)
    a, b = E[:, 0], E[:, 1]
    d = P[b] - P[a]
    along = (S * d).sum(axis=1) - sums[0]
    across = np.abs((T * d).sum(axis=1)) - sums[1]
    short = across + HOLD_MARGIN - along
    push = hold & (short > 0)
    if not push.any():
        return False
    f = S[push] * (short[push] / 2)[:, None]
    np.add.at(P, b[push], f)
    np.add.at(P, a[push], -f)
    return True


def spring(graph: TopologyGraph, order: Sequence[str], half: Dict[str, Point],
           corridor_width: float, gap: float,
           storeys: Optional[Dict[str, Storey]] = None,
           run_factor: Optional[float] = None,
           jitter: bool = False, seed: Optional[int] = None,
           draw: int = 0,
           ranges: Optional[Tuple[float, float, float]] = None,
           centred: Optional[str] = None, bearing: bool = False) -> Dict[str, Point]:
    """The ``spring`` placement: room centres for ``order`` (before separation
    and the Envelope; :func:`place` does those). With ``storeys`` (step 7)
    rooms on different Levels may overlap and stair edges pull together.
    ``run_factor`` (None: :data:`RUN_FACTOR`) is one corridor run in corridor
    widths; a style profile sets its own (winding tunnels task 9: a cave's).
    ``jitter`` (a zone whose corridors are rough: winding control task 8)
    gives each edge its spacing and offset (:func:`edge_jitter`, salted with
    the build's ``seed``, the rooms' sizes when None; ``draw`` a further
    draw, :func:`jitter_salt`; ``ranges`` its spacing and offset floor,
    :func:`edge_jitter`; room ``centred``'s neighbours sit centred on its
    walls); off, every neighbour sits centred one run off a wall. ``bearing``
    (a cave, random placement task 10) jitters by bearing and a wide spacing
    instead (:data:`BEARING_SPACING`, :class:`Jitter`)."""
    run = (RUN_FACTOR if run_factor is None else run_factor) * corridor_width
    table = (_jitter_table(graph, order, half, storeys, seed, corridor_width, draw, ranges,
                           centred, bearing)
             if jitter else None)
    pos = start_positions(graph, order, half, run, gap, storeys, table)
    edges = [(e.a, e.b) for e in graph.edges()
             if graph.node(e.a).is_room and graph.node(e.b).is_room]
    nodes = _plan_keys(graph, order, storeys)
    out = spring_relax(order, edges, pos, half, nodes, run, gap, jitter=table)
    if table is not None and table.bearing:
        out = _untangle(graph, order, edges, pos, out, half, nodes, run, gap, table, storeys)
    return out


#: Rounds of :func:`_untangle` at most, and the share of its bearing an edge in
#: a crossing keeps each round.
UNTANGLE_ROUNDS = 8
UNTANGLE_KEEP = 0.7


def _untangle(graph, order, edges, start, out, half, nodes, run, gap, table: Jitter,
              storeys) -> Dict[str, Point]:
    """A bearing placement after its springs (task 10): while a corridor would
    cross a room or another corridor (:func:`crossing_edges`), turn the
    bearings of the edges in each crossing toward their axes
    (:data:`UNTANGLE_KEEP`) and relax again from the start, up to
    :data:`UNTANGLE_ROUNDS` times; keep the placement with fewest crossings
    (the first on a tie). In place on ``table``'s edges."""
    width = table.need / STRAIGHT_NEED
    bad, _ = crossing_edges(graph, order, out, half, width, storeys)
    best = (len(_), out, dict(table.edges))
    for _round in range(UNTANGLE_ROUNDS):
        if not bad:
            break
        moved = False
        # The first round mirrors each bearing about its axis (as steep, the
        # other way); later rounds turn it toward the axis.
        keep = -1.0 if _round == 0 else UNTANGLE_KEEP
        for e in sorted(bad, key=sorted):
            if e in table.edges:
                f, t = table.edges[e]
                if t:
                    table.edges[e] = (f, t * keep if abs(t) > 0.05 else 0.0)
                    moved = True
        if not moved:
            break
        out = spring_relax(order, edges, start, half, nodes, run, gap, jitter=table)
        bad, hits = crossing_edges(graph, order, out, half, width, storeys)
        if len(hits) < best[0]:
            best = (len(hits), out, dict(table.edges))
    table.edges.clear()
    table.edges.update(best[2])
    # Then one edge at a time: each edge still in a crossing tries its mirror,
    # half its bearing, the axis and a longer spacing in turn, relaxed from
    # where the layout stands, and keeps the first that leaves fewer crossings.
    count, out = best[0], best[1]
    for _sweep in range(UNTANGLE_SWEEPS):
        if not count:
            break
        bad, _hits = crossing_edges(graph, order, out, half, width, storeys)
        better = False
        for e in sorted(bad, key=sorted):
            if e not in table.edges:
                continue
            f, t = table.edges[e]
            for alt in ((f, -t), (f, t * 0.5), (f, 0.0), (f * UNTANGLE_STRETCH, t)):
                if alt == (f, t):
                    continue
                table.edges[e] = alt
                cand = spring_relax(order, edges, out, half, nodes, run, gap,
                                    iterations=UNTANGLE_ITERS, jitter=table)
                n = len(crossing_edges(graph, order, cand, half, width, storeys)[1])
                if n < count:
                    count, out, better = n, cand, True
                    break
                table.edges[e] = (f, t)
            if not count:
                break
        if not better:
            break
    return out


#: Sweeps of the one-edge search, the spring iterations of each try, and the
#: spacing a try stretches an edge by.
UNTANGLE_SWEEPS = 3
UNTANGLE_ITERS = 100
UNTANGLE_STRETCH = 1.4


#: The Placement registry: name -> callable(graph, order, half, corridor_width,
#: gap, storeys=None, run_factor=None, jitter=False, seed=None) -> {room id: centre}. Names must be the checker's
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


def entry_faced(centres: Dict[str, Point], half: Dict[str, Point], envelope,
                entrance: Optional[str]) -> bool:
    """Does one of :func:`face_entry`'s facings put the *entrance* room
    nearest the Envelope's way in? True without an entry or an entrance room
    (nothing to face)."""
    if getattr(envelope, "entry", None) is None or entrance not in centres:
        return True
    fitted, _h, _swap = face_entry(centres, half, envelope, entrance)
    ex, ey = envelope.entry
    dist = {r: math.hypot(p[0] - ex, p[1] - ey) for r, p in fitted.items()}
    return dist[entrance] <= min(dist.values()) + 1e-9


def entry_flanked(graph: TopologyGraph, centres: Dict[str, Point], half: Dict[str, Point],
                  entrance: Optional[str]) -> bool:
    """Do the *entrance* room's neighbours take two opposite walls of it?
    Then the wall a facing turns toward the way in has a neighbour level
    with it either side, one of which the fit to the hill (centred on the
    layout) leaves nearer the way in: such a draw almost never faces it
    (:func:`entry_faced`; 5 of 1234 jitter draws of outdoor graph builds,
    against 2341 of 4940 unflanked; a warren's entrance, three ways out,
    always is). Random placement task 8."""
    if entrance not in centres:
        return False
    walls = {_side_toward(centres[entrance], half[entrance], centres[m], half[m])
             for m in graph.neighbours(entrance) if m in centres}
    return {"E", "W"} <= walls or {"N", "S"} <= walls


__all__ = [
    "SPREAD", "room_size", "may_overlap_in_plan",
    "SLAB", "Storey", "assign_levels", "level_height", "storeys", "is_stair", "STAIR_REST",
    "bfs_order", "SIDES", "SIDE_ORDERS", "START_ROOTS", "layout_clashes", "start_positions",
    "start_once", "repair", "spring_relax", "spring",
    "PLACEMENT_FUNCS", "fit_to_envelope", "FACINGS", "face_entry", "entry_faced", "entry_flanked",
    "RUN_FACTOR", "REPEL_RUNS", "ITERATIONS", "K_SPRING", "K_REPEL",
    "OFFSET", "OFFSET_MIN", "SPACING_LO", "SPACING_HI", "STRAIGHT_NEED", "ENVELOPE_JITTER", "Jitter", "jitter_salt", "edge_jitter",
]
