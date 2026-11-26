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
import math
import random
from functools import partial
from pathlib import Path
from typing import Dict, List, Mapping, NamedTuple, Optional, Sequence, Set, Tuple, Union

from .zone_spec import (
    ZoneSpec, RoomSpec, CorridorSpec, LightSpec, RegionSpec, MaterialSpec,
    GateSpec,
)
from core.ter import SHADER_OPAQUE

from . import districts as _districts
from . import semantics
from .envelope import Envelope, EnvelopeFitError
from .layout_engine import (ClassicEngine, ENGINES, RELATIONS,
                            LayoutContext, LayoutEngine)
from .geometry import AUTO_STAIRS, MIN_LANE, MeshBuilder, bridge_layout, stair_layout
from .routing import corridor_route, plan_route, exit_axis_x, route_footprint
from .zone_types import STYLE_PROFILE

# Overlap below this (u) is two faces touching, not one inside the other.
_TOUCH = 1e-6
#: A stacked build's corridor keeps this far (u) off a third room's walls on its Level: the
#: gate reads faces within ``analyzer.traverse.OUTLINE_TOL`` (0.05 u) of a room's wall as the
#: room's own, so a tube flush against one leaves its edges an open seam in that room (hall
#: length step 30, task 8: warren graph moderate 28 at Hall length 0.5, seed 625239587, corr_21
#: 0.04 u off room_15's east wall).
_ROOM_TOUCH = 0.06
#: The XY cell the gate compares two corridors' floors on (``analyzer.traverse.
#: _corridor_floor_z``: ``max(4 * adjacency_eps, 16)``). Two tubes 3 u apart on one cell read
#: as crossing there (random placement task 12: warren graph moderate 21, seed 1093450890,
#: corr_13's and corr_23's Switchback stairwells 3.3 u apart, a conflict on the gate).
CONFLICT_CELL = 16.0

# Fitting a layout inside an Envelope: the fewest rooms a build keeps, and how
# many fresh layouts are tried at each room count before dropping a room.
MIN_ENVELOPE_ROOMS = 3
ENVELOPE_ATTEMPTS = 6

# Districts (districts spec Req 3): the zone types they apply to (A2), and how
# many fresh Draws a districted generate makes when a crossing split would add a
# second link between two Districts (Req 3.3) before the error goes out.
DISTRICT_ZONE_TYPES = {"dungeon"}
DISTRICT_ATTEMPTS = 8
# Rounds of new breaches an intrusion zone tries after the crossing and conflict
# passes dropped some (``LayoutGenerator._add_breaches``; district races task 6).
BREACH_ROUNDS = 8
# A new breach's hall span at most, over the longest hall of its two Districts and their links.
BREACH_SPAN = 2.0

# A style profile's corridor run for the graph placement, in corridor widths
# (``LayoutContext.run_factor``; ``embed.RUN_FACTOR`` otherwise). Winding
# tunnels task 9: a cave's legs come out near the stock tunnels' span
# (``scripts/tunnel_survey.py``) so they are long enough to wind. Winding
# routes task 4: with whole routes winding, 4 is the lowest run that keeps
# half the cave's rough corridors winding (that spec's archive, decision 4).
PROFILE_RUN_FACTOR = {"cave": 4.0}

# Style profiles whose corridors are rough: the graph placement jitters each
# edge off the lattice (``LayoutContext.jitter``; winding control task 8). An
# Envelope build (an outdoor dungeon) jitters whatever its profile (random
# placement task 3); built and hewn dungeons keep the lattice (decision 2).
JITTER_PROFILES = frozenset({"cave"})

# Widths of run a profile's corridors gain per unit of Winding above 1
# (winding-control task 2, that spec's archive, decision 2). The tunnel's
# wander stops paying off by a Winding of about 1.25: each heading keeps
# within half a turn of the leg, so a run's stray tops out near 0.29 x its
# middle. Above 1 a longer run is what leaves room to stray. At a Winding of
# 1 or less the run is the profile's, so those zones keep their bytes.
WINDING_RUN = 2.0


def profile_run_factor(profile: Optional[str], winding: float = 1.0) -> Optional[float]:
    """The graph placement's corridor run, in corridor widths, for a style
    *profile* at a plan's *winding*: ``PROFILE_RUN_FACTOR``, plus
    ``WINDING_RUN`` per unit of winding above 1. None (``embed.RUN_FACTOR``)
    for a profile without a run of its own, at any winding."""
    base = PROFILE_RUN_FACTOR.get(profile or "")
    if base is None or winding <= 1.0:
        return base
    return base + WINDING_RUN * (winding - 1.0)


# Hall length (hall-length step 30; that spec's archive, decisions 2-3): a plan's
# ``hall_length`` L scales each layout's own spacing knob, which is affine in the
# door-to-door length it gives, not proportional (run x2 gives d2d x1.72 built, x1.81
# cave). At L = 1 every knob is 1 and nothing is touched, so zones keep their bytes.
# - The graph placement's run (built, warren, cave): ``hall_run_scale``, by profile.
# - The classic scatter ellipse's spread (classic fortress, city): ``hall_spread_scale``.
# - An Envelope build (an outdoor dungeon): the fit to the hill shrinks the run back, so
#   the separation gap after it carries the length (``hall_gap_scale``), never below
#   today's: rooms keep a full corridor width apart (Z-corridors need it).
# A throat's gap (``embed.THROAT_GAP``) is drawn in units of the run and so never scales.
# Below 1 each knob shortens as far as the separation floor lets it (decision 3).
HALL_RUN_SLOPE = {"cave": 1.25}
HALL_RUN_SLOPE_BUILT = 1.4
HALL_SPREAD_SLOPE = 0.65
#: The least the classic scatter's spread is scaled to: about where the separation floor
#: holds the halls (task 8: city halls 0.86-0.89 of L = 1's at 0.675 and at 0.75 alike).
#: Scattered tighter, the separation only packs the rooms closer, and the crowded corridors
#: clash (loops dropped, more dead ends) and run short jogs (rises capped by the run): city
#: classic moderate failed its bands 7.0% at Hall length 0.5, 2.5% here, as at 1.
HALL_SPREAD_FLOOR = 0.75
HALL_GAP_SLOPE = 1.2


def hall_run_scale(profile: Optional[str], hall_length: float = 1.0) -> float:
    """What the graph placement's run is multiplied by at a plan's *hall_length*, for a
    style *profile* (a cave's halls track the run more closely)."""
    slope = HALL_RUN_SLOPE.get(profile or "", HALL_RUN_SLOPE_BUILT)
    return max(0.25, 1.0 + slope * (hall_length - 1.0))


def hall_spread_scale(hall_length: float = 1.0) -> float:
    """What the classic scatter ellipse's spread is multiplied by at *hall_length*."""
    return max(HALL_SPREAD_FLOOR, 1.0 + HALL_SPREAD_SLOPE * (hall_length - 1.0))


def hall_gap_scale(hall_length: float = 1.0) -> float:
    """What an Envelope build's separation gap is multiplied by at *hall_length*: never
    under 1 (the gap is the separation floor)."""
    return max(1.0, 1.0 + HALL_GAP_SLOPE * (hall_length - 1.0))


#: How many halvings a scattered District's hall scale is found in
#: (``LayoutGenerator._apply_district_halls``; district races task 5).
HALL_K_BISECTIONS = 30
#: A spring placement's District hall relaxations at most, and how near its target
#: (a share) a District's median hall must come to stop early.
HALL_RELAX_ROUNDS = 4
HALL_RELAX_TOLERANCE = 0.05
#: Moves a Threshold's far Districts make at most to reach its length.
HALL_STRETCH_ROUNDS = 6

#: How many halvings an Envelope build spends finding the widest gap that fits its hill
#: (``LayoutGenerator._widest_fit``): (top - 1) / 8, a quarter at Hall length 3.
HALL_GAP_BISECTIONS = 3


class DistrictSplitError(ValueError):
    """A corridor split or swap left two Districts joined by more than their
    one Threshold (districts spec Req 3.3), or two corridors clashing that no
    swap within their Districts could part: the Draw is rejected."""

    def __init__(self) -> None:
        super().__init__("district threshold split")

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


# ---------------------------------------------------------------------------
# The gating rule (``LayoutGenerator._apply_gating`` and ``generators.edits``'s
# ``add_lock``): lock only edges of the BFS tree rooted at the entrance, and put
# each key in a room reachable before its lock.
# ---------------------------------------------------------------------------

def corridor_drop(cor) -> float:
    """A corridor's drop in u (step 31: ``CorridorSpec.drop``, the corridor entering its lower
    room that far up the wall), from a ``CorridorSpec`` or a saved spec's corridor dict; 0 when
    the corridor has none (or the field doesn't exist yet)."""
    d = cor.get("drop") if isinstance(cor, dict) else getattr(cor, "drop", 0)
    try:
        return float(d or 0.0)
    except (TypeError, ValueError):
        return 0.0


def drop_arc(drop: float, a: int, b: int, za: float, zb: float) -> Optional[Tuple[int, int]]:
    """The one way a drop corridor between rooms ``a`` (floor ``za``) and ``b`` (``zb``) can be
    walked, as ``(upper, lower)``: from the room whose floor is higher down to the other (the
    floor-height rule; equal floors, from ``a`` to ``b``: the corridor's own order). ``None``
    for a corridor with no drop: it goes both ways."""
    if drop <= 0:
        return None
    return (a, b) if za >= zb else (b, a)


def gate_oneway(edges: List[Tuple[int, int]], drops: Sequence[float],
                floors: Sequence[float]) -> Dict[int, Tuple[int, int]]:
    """The one-way edges of a room graph: edge index -> ``(upper, lower)`` (``drop_arc``) for
    each edge whose corridor drops (``drops[k]``), ``floors`` by room index. Empty when no
    corridor drops, and every gating helper then behaves as on the two-way graph."""
    out: Dict[int, Tuple[int, int]] = {}
    for k, (i, j) in enumerate(edges):
        arc = drop_arc(drops[k] if k < len(drops) else 0.0, i, j, floors[i], floors[j])
        if arc is not None:
            out[k] = arc
    return out


def gate_adjacency(edges: List[Tuple[int, int]],
                   oneway: Optional[Mapping[int, Tuple[int, int]]] = None):
    """``room -> [(next room, edge index)]``: both ways along a two-way edge, only
    ``upper -> lower`` along a one-way one (``oneway``)."""
    from collections import defaultdict
    out = defaultdict(list)
    for k, (i, j) in enumerate(edges):
        arc = oneway.get(k) if oneway else None
        if arc is None:
            out[i].append((j, k))
            out[j].append((i, k))
        else:
            out[arc[0]].append((arc[1], k))
    return out


def gate_solvable(edges: List[Tuple[int, int]], entrance: int,
                  locks: Mapping[int, Set[str]], keys: Mapping[int, Set[str]],
                  oneway: Optional[Mapping[int, Tuple[int, int]]] = None) -> bool:
    """Can the player never be stranded? ``locks``: edge index -> the gate ids locking it;
    ``keys``: room index -> the gate ids whose key lies there (picked up on entering). A state
    is (room, keys held); the zone is solvable when EVERY state the player can reach from the
    entrance can still reach every room the entrance reaches with no gates. On a two-way graph
    that is the usual "every key before its lock" (any step taken can be walked back); with a
    one-way edge (a drop) it also refuses a key that the player can only fetch by dropping
    somewhere with no way back to its lock."""
    from collections import deque

    out = gate_adjacency(edges, oneway)
    target = {entrance}
    q = deque([entrance])
    while q:
        cur = q.popleft()
        for nxt, _k in out[cur]:
            if nxt not in target:
                target.add(nxt)
                q.append(nxt)

    def moves(state):
        room, held = state
        for nxt, k in out[room]:
            if set(locks.get(k, ())) <= held:
                yield nxt, held | frozenset(keys.get(nxt, ()))

    start = (entrance, frozenset(keys.get(entrance, ())))
    seen = {start}
    q = deque([start])
    while q:
        for nxt in moves(q.popleft()):
            if nxt not in seen:
                seen.add(nxt)
                q.append(nxt)

    good: Set[tuple] = set()       # states known to reach every target room
    for s in seen:
        if s in good:
            continue
        rooms_hit, mine, hit_good = set(), {s}, False
        q = deque([s])
        while q:
            cur = q.popleft()
            rooms_hit.add(cur[0])
            for nxt in moves(cur):
                if nxt in good:
                    hit_good = True       # more keys never hurt; it reaches all from there
                    break
                if nxt not in mine:
                    mine.add(nxt)
                    q.append(nxt)
            if hit_good:
                break
        if not hit_good and not target <= rooms_hit:
            return False
        good.add(s)
    return True


def gate_tree(edges: List[Tuple[int, int]], entrance: int,
              oneway: Optional[Mapping[int, Tuple[int, int]]] = None):
    """The BFS tree of the room graph from ``entrance``: ``(parent, order,
    children)``. ``parent[entrance]`` is None; ``order`` is the visit order;
    ``children[i]`` lists room i's tree children in that order. Rooms the
    entrance can't reach are in none of them. ``oneway`` (``gate_oneway``):
    a drop edge is walked only from its upper room to its lower."""
    from collections import defaultdict, deque

    adj = defaultdict(list)
    for k, (i, j) in enumerate(edges):
        arc = oneway.get(k) if oneway else None
        if arc is None:
            adj[i].append(j)
            adj[j].append(i)
        else:
            adj[arc[0]].append(arc[1])

    parent: Dict[int, Optional[int]] = {entrance: None}
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
    return parent, order, children


def gate_subtree(children, node: int) -> set:
    """The rooms behind a lock on ``node``'s tree edge in: its subtree."""
    s = set()
    stack = [node]
    while stack:
        cur = stack.pop()
        s.add(cur)
        stack.extend(children[cur])
    return s


def gate_lockable(far: set, n: int) -> bool:
    """A lock gates a meaningful subtree: at least one room, and not all but
    the entrance's side of it."""
    return 1 <= len(far) < n - 1


def gate_key_room(depths: List[int], entrance: int, far: set,
                  locked_far: set) -> int:
    """The room a lock's key goes in: not behind this lock (``far``) nor any
    lock placed before it (``locked_far``), not the entrance if another will
    do; the one closest to the entrance (``depths``: each room's graph depth),
    first by index on a tie."""
    n = len(depths)
    forbidden = set(far) | locked_far
    candidates = [i for i in range(n) if i not in forbidden and i != entrance]
    if not candidates:
        candidates = [i for i in range(n) if i not in far]
    return min(candidates, key=lambda i: depths[i])


def gate_key_rooms(first: int, depths: List[int], entrance: int, far: set,
                   locked_far: set) -> List[int]:
    """The key rooms a lock may take on a graph with one-way edges, in the order to try them:
    ``first`` (``gate_key_room``'s pick), then every other room outside ``far`` and
    ``locked_far``, shallowest first (index on a tie), the entrance last. The caller keeps the
    first that ``gate_solvable`` accepts."""
    forbidden = set(far) | locked_far
    rest = sorted((i for i in range(len(depths)) if i not in forbidden and i != first),
                  key=lambda i: (i == entrance, depths[i], i))
    return [first] + rest


def _box_gap_xy(p: Tuple[float, float], room: RoomSpec) -> float:
    """How far point ``p`` stands outside ``room``'s plan box (Chebyshev; negative inside)."""
    return max(abs(p[0] - room.center_x) - room.width / 2, abs(p[1] - room.center_y) - room.depth / 2)


def _line_clear(line, cor: CorridorSpec, rooms: List[RoomSpec], step: float = 2.0) -> bool:
    """Does an angled corridor's line (``routing.entry_line``) keep a half width clear of
    every room's plan box, and its strip (``routing.strip_corners``: an angled end's cap runs
    wider along the wall) ``ENTRY_SPARE`` clear, bar its own two rooms over its first and
    last runs (where it leaves and enters them)? Sampled every ``step`` u."""
    import math
    from .routing import strip_corners

    def samples(p, q):
        n = max(1, int(math.ceil(math.dist(p, q) / step)))
        return [(p[0] + (q[0] - p[0]) * i / n, p[1] + (q[1] - p[1]) * i / n) for i in range(n + 1)]

    hw = cor.width / 2
    corners = strip_corners(line, hw)
    if corners is None:
        return False
    last = len(line) - 2
    for j in range(len(line) - 1):
        pts = samples(line[j], line[j + 1])
        (l0, r0), (l1, r1) = corners[j], corners[j + 1]
        edge = samples(l0, l1) + samples(r0, r1) + samples(l0, r0) + samples(l1, r1)
        for r in rooms:
            if (j == 0 and r.id == cor.from_room) or (j == last and r.id == cor.to_room):
                continue
            if any(_box_gap_xy(q, r) < hw - 1e-6 for q in pts) or                     any(_box_gap_xy(q, r) < ENTRY_SPARE - 1e-6 for q in edge):
                return False
    return True


def _centre_span(wps, room: RoomSpec, eps: float = 2.0) -> float:
    """The longest run of a route's centreline (``wps``) inside ``room``'s plan box shrunk by
    ``eps``: the gate's measure of a room a corridor genuinely cuts through
    (``analyzer.traverse._route_penetration_span``, the room shrunk by the agent's
    ``adjacency_eps``), as ``_crossed_room_centreline`` measures it."""
    hw_, hd_ = room.width / 2, room.depth / 2
    rx0, ry0 = room.center_x - hw_ + eps, room.center_y - hd_ + eps
    rx1, ry1 = room.center_x + hw_ - eps, room.center_y + hd_ - eps
    if rx0 > rx1 or ry0 > ry1:
        rx0, ry0, rx1, ry1 = rx0 - eps, ry0 - eps, rx1 + eps, ry1 + eps
    best = 0.0
    for (x0, y0), (x1, y1) in zip(wps, wps[1:]):
        dx, dy = x1 - x0, y1 - y0
        t0, t1, ok = 0.0, 1.0, True
        for p, q in ((-dx, x0 - rx0), (dx, rx1 - x0), (-dy, y0 - ry0), (dy, ry1 - y0)):
            if abs(p) < 1e-9:
                if q < 0:
                    ok = False
                    break
                continue
            t = q / p
            if p < 0:
                if t > t1:
                    ok = False
                    break
                t0 = max(t0, t)
            else:
                if t < t0:
                    ok = False
                    break
                t1 = min(t1, t)
        if ok and t1 > t0:
            best = max(best, math.hypot(dx, dy) * (t1 - t0))
    return best


def _line_solids(line, cor: CorridorSpec) -> list:
    """An angled corridor's line as ``transitions`` solids: its strip's runs, floor to
    headroom (``_entry_clear``)."""
    from .transitions import _solid, path_pieces
    return [_solid(quad, min(za, zb), max(za, zb) + cor.height)
            for quad, za, zb in path_pieces(line, cor.width / 2, cor.from_z, cor.to_z) or ()]


def _entry_clear(line, cor: CorridorSpec, every: List[CorridorSpec], by_id,
                 taken: Dict[str, list]) -> bool:
    """Does an angled corridor's line keep the player's half-width off every other corridor
    beside it in Z (``transitions.strip_clear``): one already angled by its line (``taken``),
    any other by its legs, bends and Switchback stairwell? With a corridor sharing a room, the
    line's run-out at that room may meet it, and the line may meet its doorway stub and first
    bend there on a Z route (``_resolve_conflicts``' rule for two corridors from one room). The line cuts
    straight across its route's bends, so a long Z or U route's line strays far from the legs
    the layout cleared: hall length step 30, task 8, cave graph at Hall length 3 (seeds
    473448209, 680460140, 839608415, 1855383429: a line across another corridor's stairwell;
    1704093923: two lines crossing)."""
    from .transitions import _corridor_boxes, _solid, path_pieces, strip_clear
    pieces = path_pieces(line, cor.width / 2, cor.from_z, cor.to_z)
    if pieces is None:
        return False
    solids = []
    for other in every:
        if other.id == cor.id:
            continue
        own = taken.get(other.id)
        if own is None:
            boxes = _corridor_boxes(other, by_id)
            n = sum(1 for k, _ in boxes if k >= 0)        # legs, then bends, then a stairwell
            # A Z route's stub and bend at each end are pinned to that room (``floor_pieces``).
            pins = {0: other.from_room, n: other.from_room, n - 1: other.to_room,
                    2 * n - 2: other.to_room} if corridor_route(other, by_id).kind == "z" else {}
            own = taken[other.id] = [
                _solid([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z0, z1, pins.get(p, ""))
                for p, (_, (x0, y0, x1, y1, z0, z1)) in enumerate(boxes)]
        shared = ({other.from_room, other.to_room} & {cor.from_room, cor.to_room})
        tag = (cor.from_room if cor.from_room in shared else cor.to_room) if shared else ""
        solids.extend(s[:4] + (tag,) for s in own if not s[4] or s[4] not in shared)
    return strip_clear(cor, pieces, solids)


def gate_spec(gate_id: str, cor: CorridorSpec, key_room: RoomSpec,
              tier: int) -> "GateSpec":
    """A Gate: its lock at the middle of ``cor``, its key 5 u over
    ``key_room``'s floor at its centre."""
    return GateSpec(
        id=gate_id,
        corridor_id=cor.id,
        lock_x=(cor.from_x + cor.to_x) / 2,
        lock_y=(cor.from_y + cor.to_y) / 2,
        lock_z=(cor.from_z + cor.to_z) / 2,
        key_room_id=key_room.id,
        key_x=key_room.center_x, key_y=key_room.center_y,
        key_z=key_room.floor_z + 5.0,
        tier=tier,
    )


# Stacked builds (step 7): the floor variation ramps give WITHIN a Level, as a
# band this wide centred on the Level's height. Job B's floor-to-floor height
# grows by it, so two Levels keep the Slab whatever the variation does
# (design "Levels": "bounded so two Levels never meet"). Two Slabs: small next
# to the ~135 u Level, like step 6's gentlest ramps.
LEVEL_VARIATION = 28.0

# How far a U-route stair's door sits in from the end of its wall, and the
# pier between two doors on one wall (``_doors_clash``).
U_DOOR_MARGIN = 2.0
# A jittered layout's (winding control task 8) U-route doors sit this far in:
# past the 2 u a corridor's end runs into the room beside it (``_wall_point``'s
# inset) and the gate's THROAT_CLEAR, so a corridor leaving the wall round
# the corner never stands in the door's Throat (s7 cave 14 moderate, room_2:
# wall across throat). Other layouts keep U_DOOR_MARGIN and their bytes.
U_CORNER_MARGIN = 3.0
# A bearing placement's entry angles (random placement task 10,
# ``LayoutGenerator._set_entries``): a run-out leaves its opening at most
# ENTRY_MAX degrees off the wall's normal, and square under ENTRY_MIN.
ENTRY_MAX = 40.0
ENTRY_MIN = 1.0
# The least a straight route's run-outs leave square (its openings face each other).
ENTRY_SWEEP = 25.0
# The shares of its target an entry angle tries before the corridor runs out square.
ENTRY_SHARES = (1.0, 0.5, 0.25)
# How far an angled corridor's strip keeps off any room but the two it joins (the player's
# half width, transitions.PLAYER_HALF_WIDTH).
ENTRY_SPARE = 1.5
# The least wall (u) an angled opening leaves to the next door on its wall.
ENTRY_PIER = 2.0
# Where a U-route's doors may stand along their walls once the two ends have
# been tried (LayoutGenerator._u_cor). A finer grid found no more loops.
U_DOOR_STOPS = (-1.0, -0.5, 0.0, 0.5, 1.0)
# A stacked build's rounds of re-judging corridors after a relax moved floors.
SETTLE_PASSES = 4


class _Stack(NamedTuple):
    """What Job B knows of a stacked build: each room's Level and the
    floor-to-floor height it places them at. ``offset`` moves the whole
    stack up or down (an outdoor dungeon's ``_fit_floors`` sinks it under the
    hill), keeping each Level's band and the Slab between them."""
    levels: List[int]
    level_height: float
    variation: float
    offset: float = 0.0

    def base(self, k: int) -> float:
        return self.levels[k] * self.level_height + self.offset

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

#: The classic engine's footprint spread round the medium side in a
#: room-graph zone: the split log-normal's ln sd below and above it and its
#: ln offset (``semantics.room_footprint``; random placement task 11). The
#: pacing roles' sizes (``_bias_rooms_by_role``) already spread a zone's
#: sides, so the draw adds the rest of stock's.
CLASSIC_SPREAD: Tuple[float, float, float] = (0.08, 0.7, -0.17)

#: An outdoor dungeon's greatest room side, in H (random placement task 11): one
#: big hall under the hill takes the ground Sites need (``stages.dungeon_keep_clear``
#: covers a room's corners with a capsule), so the footprint limit's 26 H top is
#: lowered under a hill.
ENVELOPE_SIDE_TOP = 22.0

#: The outdoor-dungeon entrance room's greatest long/short side ratio.
ENTRANCE_ASPECT = 1.5


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

    # Room index -> District id during a districted pass (set per pass).
    _district_assign: Optional[List[int]] = None
    # Room id -> its District's race when some District carries a race of its own
    # (district races Req 4; set per pass), else None: every room and corridor is
    # then sized by the zone's race (``self.race``), as before.
    _room_race: Optional[Dict[str, str]] = None

    def __init__(self, zone_type: str = "dungeon", seed: Optional[int] = None,
                 engine: Union[LayoutEngine, str, None] = None,
                 profile: Optional[str] = None, winding: float = 1.0,
                 hall_length: float = 1.0):
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
        # *profile* names another measured profile (a ``cave`` Purpose:
        # styles/cave.json; cave spec Req 3). A room-graph zone sizes its rooms
        # from its race's bands, so the profile's floor_area reaches them as a
        # band shift: the side ratio sqrt(area / zone type's area) as a
        # position in the side band, as an outdoor dungeon's scale does
        # (``outdoor_dungeon``). ``generate`` reads ``size_shift``; a plan's
        # Size control adds to ``profile_shift``. No profile: 0.0, as before.
        self.profile_shift = 0.0
        # The graph placement's corridor run, in corridor widths, for this
        # profile (``PROFILE_RUN_FACTOR``), longer at a *winding* above 1
        # (``profile_run_factor``); None: ``embed.RUN_FACTOR``.
        self.run_factor = profile_run_factor(profile, winding)
        self.jitter = (profile or "") in JITTER_PROFILES
        # The plan's Hall length (step 30): each layout's spacing knob scales by it
        # (``hall_run_scale``, ``hall_spread_scale``, ``hall_gap_scale``); 1 leaves all alone.
        self.hall_length = float(hall_length)
        self._hall_profile = profile or ""
        # An Envelope build's separation gap multiplier for the pass running (``generate``
        # finds the widest up to ``hall_gap_scale`` that fits the hill: ``_widest_fit``).
        self._hall_gap = 1.0
        # Set per generate from the engine (``EngineResult.jittered``, ``.bearing``).
        self._straight_doors = False
        self._bearing_doors = False
        # A bearing placement's throats (``EngineResult.throats``, as room id
        # pairs), set per generate: the separation holds them (cave clumps task 3).
        self._throats: set = set()
        if profile:
            import math
            base_area = _profile_mean(self.profile, ["geometry", "floor_area"], 2_000_000.0)
            self.profile = load_style_profile(profile)
            area = _profile_mean(self.profile, ["geometry", "floor_area"], base_area)
            lo, hi = semantics.ROOM_SIDE_BAND
            self.profile_shift = math.log((area / base_area) ** 0.5) / math.log(hi / lo)
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

        # Optional overall size multiplier (small/large/huge from a plan),
        # applied on top of the theme-accurate base in _apply_room_scale.
        # Heightfield zones only: a room-graph zone (dungeon, city) sizes its
        # rooms from its race's bands, and the plan's Size control shifts its
        # rooms' position in them instead (``size_shift``,
        # ``semantics.SIZE_SHIFT``; step 7 task 17).
        self.size_multiplier = 1.0
        self.size_shift = self.profile_shift
        # The build's race (``generate``'s ``dungeon_race``): its body height
        # sizes a room-graph zone's rooms, corridors and rises.
        self.race = ""
        # Elevation rises, in body heights (room-graph zones): the plan's
        # Verticality sets them (``ai.expand._VERTICALITY``);
        # ``_apply_room_scale`` turns them into ``step_rise_min/max``.
        self.rise_h = (1.0, 3.5)

        # Placeholder room-size band; refined per generate() by room count.
        self.room_min = 150.0
        self.room_max = 400.0
        self._apply_room_scale(room_count=5)

        # Elevation parameters. elevation_chance is the probability that a
        # connection between two rooms changes height. step_rise is the Z change
        # per elevated connection (room-graph zones: ``rise_h`` x H, set by
        # _apply_room_scale).
        self.elevation_chance = 0.5
        if not self.corridor_clearance:
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
        # The Envelope the layout pass fits (outdoor dungeons), or None: a
        # stair route leaving its footprint is the last one tried.
        self._envelope: Optional[Envelope] = None
        # An Envelope build's least entrance-room side (u; ``outdoor_dungeon.
        # layout_in_envelope`` sets it to ``tunnel_wall``), whatever the engine.
        self.entrance_side = 0.0
        # A stair's route as the conflict pass re-routed it (an index into
        # its ``_stair_candidates``), kept while the floors move.
        self._stair_route: Dict[Tuple[int, int], int] = {}

    def _apply_room_scale(self, room_count: int) -> None:
        """
        Room-graph zones (dungeon, city; step 7 task 17): the room band, the
        rooms' height, the corridors and the elevation rises from the build's
        race (``self.race``) through ``semantics``: the classic engine scatters
        around the band's medium side (``size_shift`` moves it) in stock's proportions. The
        room count no longer sizes rooms: a zone's total size follows from its
        rooms.

        Heightfield zones: set room_min/room_max (and corridor width) from the
        theme's measured floor area divided across `room_count` rooms, so the
        assembled zone's footprint tracks the real indoor-vs-outdoor
        proportions.
        """
        if self.corridor_clearance:
            t = semantics.band_position("medium", self.size_shift)
            side = semantics.room_side(self.race, t)
            # The classic engine draws each footprint round the medium side
            # (``LayoutContext.footprint_spread``: ``CLASSIC_SPREAD``).
            self.room_min = self.room_max = side
            # A profile's shift sizes footprints only; heights keep the
            # Size control's position (district-looks task 4).
            self.ceiling = semantics.room_height(
                self.race, semantics.band_position("medium", self.size_shift - self.profile_shift))
            self.corridor_width, self.corridor_height = semantics.corridor_size(self.race)
            h = semantics.body_height(self.race)
            self.step_rise_min, self.step_rise_max = self.rise_h[0] * h, self.rise_h[1] * h
            return
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
                 envelope: Optional[Envelope] = None,
                 districts: bool = False,
                 district_plan: Optional[list] = None,
                 district_relationship: str = "",
                 drop_rooms: bool = True) -> ZoneSpec:
        """
        Generate a zone. *locks* > 0 produces a keyed dungeon with that many
        lock-and-key gates (solvability guaranteed); 0 is a fully open dungeon.

        Content / semantic layer (dungeon theme, Step 1): *dungeon_theme* picks
        the archetype arc (e.g. "fortress", "temple", "sunken_ruin");
        *dungeon_race* sizes the rooms and corridors ("giant", "froglok", …;
        ``semantics.RACE_HEIGHT``);
        *elemental_tint* overrides the archetype's default tint ("" forces none,
        None uses the default). *room_type_overrides* maps room id → semantic
        type for planner-driven assignment. Semantic labelling only runs for the
        box (dungeon/city) zone types — cave/wilderness backends are untouched.

        *envelope* (outdoor dungeons) confines the layout: every room box and
        every corridor's swept box lies inside it. A layout that doesn't fit is
        redrawn; after ``ENVELOPE_ATTEMPTS`` misses a room is dropped, down to
        ``MIN_ENVELOPE_ROOMS``, with a ``rooms_reduced`` warning in
        ``self.warnings``. If even that many don't fit, ``EnvelopeFitError``.
        With *drop_rooms* off no room is dropped: ``EnvelopeFitError`` after
        the attempts at the full count, which are the same layouts the
        dropping run starts with (``outdoor_dungeon.plan_dungeon`` asks for
        the full count everywhere first; random placement task 8).
        Without an Envelope the layout is exactly as before.

        *districts* (districts spec Req 3) splits a dungeon of 8 or more rooms
        into 2-3 Districts joined by one Threshold corridor each
        (``generators.districts``): *district_plan* proposes their Purposes in
        id order, *district_relationship* is ``sequential`` (default),
        ``factional`` or ``abandoned_vs_active``. Only a ``dungeon`` without an
        Envelope takes them (A2); for anything else the switch is ignored. The
        partition's notes (fewer Districts than asked, a Purpose or
        relationship ignored) go to ``self.warnings``. A Draw whose crossing
        split would join two Districts twice is redrawn, up to
        ``DISTRICT_ATTEMPTS`` times, then :class:`DistrictSplitError`. With the
        switch off, or one District resolved, nothing changes (Req 3.4).
        """
        self.warnings = []
        self.race = dungeon_race or ""
        args = (name, add_lights, elevation, locks, dungeon_theme,
                dungeon_race, elemental_tint, room_type_overrides)
        if envelope is None:
            if not (districts and self.zone_type in DISTRICT_ZONE_TYPES):
                return self._generate_once(room_count, *args)
            plan = (list(district_plan or []), district_relationship or "")
            for attempt in range(DISTRICT_ATTEMPTS):
                kept = len(self.warnings)
                try:
                    return self._generate_once(room_count, *args, districts=plan)
                except DistrictSplitError:
                    del self.warnings[kept:]
                    if attempt == DISTRICT_ATTEMPTS - 1:
                        raise
        floor = min(room_count, MIN_ENVELOPE_ROOMS) if drop_rooms else room_count
        self._apply_room_scale(room_count)
        top = hall_gap_scale(self.hall_length)
        for count in range(room_count, floor - 1, -1):
            for _ in range(ENVELOPE_ATTEMPTS):
                if top > 1.0:
                    spec = self._widest_fit(top, count, args, envelope)
                else:
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

    def _widest_fit(self, top: float, count: int, args: tuple,
                    envelope: Envelope) -> ZoneSpec:
        """One Envelope attempt at a Hall length over 1 (step 30). First the attempt a Hall
        length of 1 makes (today's gap): if it doesn't fit, that is the attempt, as at 1, so
        the next draw is the one 1 makes too. If it fits, the widest separation gap
        multiplier up to *top* whose layout still fits, found by bisection on the same draw
        (the rng as it was before the attempt), then laid out once more at it, so the
        generator's state is that layout's. Either way the draw, so the grown graph, Levels
        and room count, is the one a Hall length of 1 keeps."""
        state = self.rng.getstate()
        kept = len(self.warnings)

        def once(g: float) -> ZoneSpec:
            self.rng.setstate(state)
            del self.warnings[kept:]
            self._hall_gap = g
            try:
                return self._generate_once(count, *args, envelope=envelope)
            finally:
                self._hall_gap = 1.0

        spec = once(1.0)
        if not self.fits(spec, envelope):
            return spec
        spec = once(top)
        if self.fits(spec, envelope):
            return spec
        lo, hi = 1.0, top
        for _ in range(HALL_GAP_BISECTIONS):
            mid = (lo + hi) / 2
            if self.fits(once(mid), envelope):
                lo = mid
            else:
                hi = mid
        return once(lo)

    def _generate_once(self, room_count: int, name: str, add_lights: bool,
                       elevation: bool, locks: int, dungeon_theme: str,
                       dungeon_race: str, elemental_tint: Optional[str],
                       room_type_overrides: Optional[dict],
                       envelope: Optional[Envelope] = None,
                       districts: Optional[Tuple[list, str]] = None) -> ZoneSpec:
        """One layout pass (``generate`` without the Envelope retry loop).
        *districts* is ``(district_plan, district_relationship)`` when the
        switch is on for this zone, else None."""
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
        self._envelope = envelope
        self._shapes = {}
        self._stair_route = {}
        # Room index -> District id while a districted pass runs Job B, else
        # None (the crossing and conflict passes keep Districts apart).
        self._district_assign = None
        self._room_race = None

        # --- Job A: the rooms and their graph, from the Layout_Engine ----
        # (classic: scatter in an ellipse, separate, Delaunay, MST + a few
        # loop edges). Then Job B: pacing, elevation over the graph,
        # wall-to-wall corridors.
        ctx = self._layout_context(room_count, dungeon_theme, dungeon_race)
        if envelope is not None:
            # An Envelope build (an outdoor dungeon) leaves the lattice too,
            # whatever its walls (random placement task 3).
            ctx.jitter = True
        result = self.engine.generate(ctx, room_count, envelope)
        self._straight_doors = getattr(result, "jittered", False)
        self._bearing_doors = getattr(result, "bearing", False)
        rooms = result.rooms
        throat_ix = list(getattr(result, "throats", None) or ())
        self._throats = {frozenset((rooms[i].id, rooms[j].id)) for i, j in throat_ix}
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
        # Under a hill the Tunnel enters at the top Level, so a stacked layout's
        # entrance is the room nearest the way in on that Level (random
        # placement task 11: sized in stock's proportions, a deeper room's
        # centre could lie nearer the way in on every facing, outdoor seed 2037).
        among = None
        if envelope is not None and result.levels is not None and len(set(result.levels)) > 1:
            top = max(result.levels)
            among = [i for i, lv in enumerate(result.levels) if lv == top]

        # Districts (districts spec A4): find the zone entrance by pacing's
        # rule (no rng), cut the graph into Districts and drop the
        # cross-District edges but the Thresholds, then pace ONCE on the
        # pruned graph with one climax per District. One District (the switch
        # off, fewer than 8 rooms, or no cut meeting the sizes) draws nothing
        # and leaves the edges alone, so the zone is as before (Req 3.4).
        part = None
        climaxes = None
        links = 1
        k = _districts.district_count(len(rooms), districts is not None)
        if k >= 2:
            first = self._find_entrance(rooms, entry, among)
            # An intrusion zone keeps up to INTRUSION_LINKS links per Threshold pair
            # (district races Req 6): the Threshold and its breaches.
            links = (_districts.INTRUSION_LINKS
                     if (districts[1] or "").strip().lower() == _districts.INTRUSION else 1)
            part = _districts.partition_districts(rooms, edges, first, k, self.rng,
                                                  links=links)
            if part.k < part.requested:
                self.warnings.append(
                    f"districts_reduced: {part.requested} requested, {part.k} "
                    f"fit the room graph")
            if part.k >= 2:
                edges[:] = part.edges
                for i, room in enumerate(rooms):
                    room.district = part.assign[i]
                self._district_assign = part.assign
                climaxes = _districts.district_climaxes(part, part.edges, first)
            else:
                part = None
        entrance = self._apply_pacing(rooms, edges, entry, among=among,
                                      size_bias=not self.engine.sizes_rooms,
                                      climax=result.climax, climaxes=climaxes)

        # Content / semantic layer (box themes only): label rooms with a
        # semantic type + theme and apply the shape/proportion/ceiling/floor
        # biases BEFORE the re-separate + elevation passes, so the themed shapes
        # resolve for overlaps and elevation builds on the sunk/raised floors.
        # Districts need their Purposes, so a districted dungeon is themed
        # whether or not a theme was asked for (District 0 takes the asked
        # theme, if any; otherwise the Purposes are drawn).
        themed = self.zone_type in _SEMANTIC_ZONE_TYPES and (
            dungeon_theme or dungeon_race or elemental_tint is not None
            or room_type_overrides or part is not None)
        district_specs = None
        if part is not None:
            district_specs, notes = _districts.assign_district_purposes(
                part, dungeon_theme, districts[0], districts[1], self.rng)
            self.warnings.extend(notes)
            spec.districts = district_specs
            # A District with a race of its own takes that race's sizes (Req 4).
            self._apply_district_races(rooms, district_specs, edges, result)
        if themed:
            semantics.label_rooms(
                spec, rooms, self.rng,
                archetype=dungeon_theme, race=dungeon_race,
                tint=elemental_tint, overrides=room_type_overrides,
                districts=district_specs)
        # Every room-graph room ends inside its race's bands (Req 10): the
        # role and room-type biases can push one past either end.
        if self.corridor_clearance:
            for room in rooms:
                semantics.fit_to_band(room, self._race_of(room))
        # An outdoor dungeon's entrance room must fit a Tunnel under the hill
        # (``outdoor_dungeon.plan_entrance``): its footprint is capped at the
        # medium class side (after the Size control's shift), aspect 1.5, so
        # the size draw's big halls land deeper in, and no side is under
        # ``entrance_side`` (``outdoor_dungeon.tunnel_wall``: the wall facing
        # the way in must hold a terrain cell) (random placement task 11).
        if envelope is not None and self.corridor_clearance:
            top = ENVELOPE_SIDE_TOP * semantics.body_height(self.race)
            for room in rooms:
                semantics.cap_footprint(room, top, float("inf"))
            least = self.entrance_side
            side = semantics.room_side(self.race, semantics.band_position("medium", self.size_shift))
            room = rooms[entrance]
            semantics.cap_footprint(room, max(side, least), ENTRANCE_ASPECT)
            room.width, room.depth = max(room.width, least), max(room.depth, least)

        # A stacked build (an engine gave rooms on more than one Level) runs
        # Job B in 3D from here: rooms on different Levels may overlap in plan,
        # floors sit at their Level, an edge across Levels is a stair.
        self._stack = self._stack_for(result, rooms)

        # Role biasing resized rooms (climax/hub grew, dead-ends shrank), so
        # re-separate to resolve any overlaps the new sizes introduced. Keep
        # the graph edges — only positions shift slightly.
        self._separate_rooms(rooms, storeys=self._storeys(rooms), throats=self._throats)

        # A throat's rooms keep one floor where the graph asks nothing else of
        # them (its 12 u run carries little rise; cave clumps task 3).
        elev_rel = relations
        if throat_ix:
            elev_rel = dict(relations)
            for i, j in throat_ix:
                if (i, j) not in relations and (j, i) not in relations:
                    elev_rel[(i, j)] = "level"
        if self._stack is not None:
            self._assign_stacked_elevation(rooms, edges, entrance, elev_rel,
                                           elevation, themed)
        elif elevation:
            self._assign_elevation(rooms, edges, entrance, elev_rel)
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
            if part is not None:
                semantics.realize_semantics(spec, self.rng, districts=district_specs,
                                            thresholds=part.thresholds)
            else:
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
        # An intrusion pair the graph joins by fewer than its links gets new
        # breaches on the final rooms (district races Req 6), as loop edges the
        # crossing and conflict passes below judge like any other.
        breach = part is not None and links > 1
        tried: set = set()
        added = breach and self._add_breaches(rooms, edges, part, links, tried)
        graph_changed = self._resolve_crossings(rooms, edges)
        graph_changed = graph_changed or added
        # Drop a loop edge from any pair of corridors that would cross too close
        # in Z (the residual open-space conflict class the through-room split
        # can't reach). Only loop edges fall, so the graph stays connected.
        graph_changed = self._resolve_conflicts(rooms, edges) or graph_changed
        # A breach those passes dropped gives way to the next candidate.
        for _ in range(BREACH_ROUNDS if breach else 0):
            self._shapes = {}
            if not self._add_breaches(rooms, edges, part, links, tried):
                break
            self._resolve_crossings(rooms, edges)
            self._resolve_conflicts(rooms, edges)
        if graph_changed and (elevation or themed):
            from collections import defaultdict

            def relax():
                adj = defaultdict(list)
                for i, j in edges:
                    adj[i].append(j)
                    adj[j].append(i)
                self._relax_elevation(rooms, adj, entrance)

            relax()
            if self._stack is not None:
                # The relax moved floors, and with them what clears what: judge
                # the corridors again on the floors they will be built on.
                for _ in range(SETTLE_PASSES):
                    self._shapes = {}
                    if not self._resolve_conflicts(rooms, edges):
                        break
                    relax()

        # Req 3.3: the splits and swaps above may have joined two Districts a
        # second time (an intrusion pair: more than its links); that Draw is
        # rejected. Else the Thresholds are the cross-District edges as they
        # now stand, and an intrusion pair's others its breaches.
        if part is not None:
            part.thresholds = self._district_thresholds(part, edges, links)
            if links > 1:
                part.breaches = self._district_breaches(part, edges)
            part.edges = list(edges)

        if envelope is not None:
            self._fit_floors(rooms, edges, entrance, envelope)

        self._shapes = {}
        self._build_corridors(spec, rooms, edges)
        threshold_ids: List[str] = []
        if part is not None:
            threshold_ids = self._record_districts(spec, part, rooms, edges, entrance)
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
        # Floors moved after the semantic pass; flooded rooms' water follows them.
        semantics.settle_floods(spec)

        # Optional lock-and-key gating (keyed dungeons). Runs after corridors
        # exist so gates can reference corridor ids. Solvability is guaranteed.
        if locks > 0:
            self._apply_gating(spec, rooms, edges, entrance, n_locks=locks,
                               thresholds=threshold_ids)

        return spec

    # ------------------------------------------------------------------
    # Districts (districts spec Req 3)
    # ------------------------------------------------------------------

    def _apply_district_races(self, rooms: List[RoomSpec], districts: list,
                              edges: Optional[List[Tuple[int, int]]] = None,
                              result=None) -> None:
        """District races (Req 4): a District with a race of its own is laid out
        at that race's scale. The engine laid every room out at the zone's race
        (the partition needs its graph first), and every size there is a multiple
        of H, so each of the District's rooms grows by ``H(race) / H(zone race)``,
        footprint, height and its offset from the District's centre alike: the
        same band positions and the same spacing in its own H. Then the Districts
        are pushed apart whole (:meth:`_separate_districts`), and from here every
        room is fitted to its own race's bands and every corridor sized by the
        smaller race of its two rooms (:meth:`_corridor_dims`). No District with
        a race: nothing changes, and nothing is drawn."""
        if not any(d.race for d in districts):
            return
        race_of = {d.id: (d.race or self.race) for d in districts}
        halls = (self._district_halls(districts)
                 if edges is not None and self._envelope is None else None)
        self._room_race = {r.id: race_of.get(r.district, self.race) for r in rooms}
        before = None
        if halls is not None:
            # A raced District's halls (Req 5): first the Thresholds as they would
            # stand without them, then its own halls at the zone's sizes.
            before = [dataclasses.replace(r) for r in rooms]
            self._scale_district_races(before, race_of)
            self._apply_district_halls(rooms, edges, result, halls)
        self._scale_district_races(rooms, race_of)
        if halls is not None:
            # Then the Thresholds, at the Districts' own sizes.
            self._stretch_thresholds(rooms, edges, halls, before)

    def _scale_district_races(self, rooms: List[RoomSpec], race_of: Dict[int, str]) -> None:
        """:meth:`_apply_district_races`'s scaling: each raced District's rooms by
        ``H(race) / H(zone race)`` about its centre, then the Districts apart."""
        h0 = semantics.body_height(self.race)
        for d, race in race_of.items():
            s = semantics.body_height(race) / h0
            mine = [r for r in rooms if r.district == d]
            if s == 1.0 or not mine:
                continue
            cx = sum(r.center_x for r in mine) / len(mine)
            cy = sum(r.center_y for r in mine) / len(mine)
            for r in mine:
                r.center_x = cx + (r.center_x - cx) * s
                r.center_y = cy + (r.center_y - cy) * s
                r.width *= s
                r.depth *= s
                r.height *= s
        self._separate_districts(rooms)

    # District hall lengths (district races Req 5; archive decision 4). A District
    # carrying a race of its own with a hall length default
    # (``semantics.race_hall_length``: giants 3.0) has halls that much longer than
    # the plan's Hall length gives the zone; a Threshold takes the mean of its two
    # ends. Every length is set as a share of the one the layout drew (measured
    # by :meth:`_hall_span`), so a District's halls at 1 are left as they stand
    # and the zone's Hall length (step 30) carries through. An Envelope build (an
    # outdoor dungeon) is left alone: the fit to the hill shrinks any run back
    # (step 30 decision 2).

    @staticmethod
    def _district_halls(districts: list) -> Optional[Dict[int, float]]:
        """Each District's hall length default (1 without a race of its own), or
        None when every one is 1: then nothing is moved."""
        halls = {d.id: semantics.race_hall_length(d.race) if d.race else 1.0
                 for d in districts}
        return None if all(v == 1.0 for v in halls.values()) else halls

    @staticmethod
    def _hall_span(a: RoomSpec, b: RoomSpec, k: float = 1.0) -> float:
        """About how long the hall between *a* and *b* runs door to door, their
        centres' offset scaled by *k*: the wall gap on the axis it leaves by (the
        wider gap, as ``routing.exit_axis_x`` picks) and the jog across it
        between the two walls' middles."""
        cx, cy = k * abs(b.center_x - a.center_x), k * abs(b.center_y - a.center_y)
        gx, gy = cx - (a.width + b.width) / 2, cy - (a.depth + b.depth) / 2
        return max(0.0, gx) + cy if gx >= gy else max(0.0, gy) + cx

    def _median_span(self, pairs, k: float = 1.0) -> float:
        """The median :meth:`_hall_span` of *pairs* (room pairs) at offset scale *k*."""
        g = sorted(self._hall_span(a, b, k) for a, b in pairs)
        return g[len(g) // 2]

    def _apply_district_halls(self, rooms: List[RoomSpec], edges: List[Tuple[int, int]],
                              result, halls: Dict[int, float]) -> None:
        """The halls inside each District with a default ``f`` != 1: their median
        :meth:`_hall_span` f times the drawn one.

        - A spring placement (the graph engine, not jittered) is relaxed again from
          where it stands (``embed.spring_relax``) with a run per edge (``runs``):
          the edge's wall gap along its side, times f in such a District (its own
          gap elsewhere, so it holds). Each edge keeps its wall side, so the
          graph's drawing holds. Loops fight a uniform stretch (the rooms keep
          their sizes), so the District's runs are scaled again by what it fell
          short, up to ``HALL_RELAX_ROUNDS`` relaxations; then the rooms are
          separated as the engine does.
        - A scatter (classic) or a jittered placement (a cave's offsets and throats,
          which a plain relax would pull back to centred) scales the District's
          offsets from its centre, as a District race does (task 4), by the k that
          gives it. Rooms a throat joins (step 29) move as one, so a throat keeps
          its gap and is left out of the median."""
        rec = getattr(result, "record", None) or {}
        if (rec.get("engine") == "graph" and rec.get("placement") == "spring"
                and not getattr(result, "jittered", False)):
            self._relax_district_halls(rooms, edges, result, halls)
            return
        throats = self._throats
        for d, f in halls.items():
            mine = [k for k, r in enumerate(rooms) if r.district == d]
            inside = set(mine)
            joined = [(i, j) for i, j in edges if i in inside and j in inside]
            pairs = [(rooms[i], rooms[j]) for i, j in joined
                     if frozenset((rooms[i].id, rooms[j].id)) not in throats]
            if f == 1.0 or not pairs:
                continue
            want = f * self._median_span(pairs)
            lo, hi = 1.0, max(1.0, f)        # k = f makes every span at least f-fold
            for _ in range(HALL_K_BISECTIONS):
                mid = (lo + hi) / 2
                lo, hi = (mid, hi) if self._median_span(pairs, mid) < want else (lo, mid)
            k = (lo + hi) / 2
            ox = sum(rooms[i].center_x for i in mine) / len(mine)
            oy = sum(rooms[i].center_y for i in mine) / len(mine)
            # Throat clumps (rooms a throat joins) move by their centroid's shift.
            clump = {i: i for i in mine}

            def root(x: int) -> int:
                while clump[x] != x:
                    x = clump[x]
                return x
            for i, j in joined:
                if frozenset((rooms[i].id, rooms[j].id)) in throats:
                    clump[root(i)] = root(j)
            groups: Dict[int, List[int]] = {}
            for i in mine:
                groups.setdefault(root(i), []).append(i)
            for g in groups.values():
                gx = sum(rooms[i].center_x for i in g) / len(g)
                gy = sum(rooms[i].center_y for i in g) / len(g)
                dx, dy = (gx - ox) * (k - 1.0), (gy - oy) * (k - 1.0)
                for i in g:
                    rooms[i].center_x += dx
                    rooms[i].center_y += dy
        self._separate_districts(rooms)

    def _relax_district_halls(self, rooms: List[RoomSpec], edges: List[Tuple[int, int]],
                              result, halls: Dict[int, float]) -> None:
        """:meth:`_apply_district_halls` for a spring placement."""
        from .topology.embed import RUN_FACTOR, Storey, spring_relax
        ids = [r.id for r in rooms]
        by_d: Dict[int, List[Tuple[int, int]]] = {}
        gaps: Dict[frozenset, float] = {}
        for i, j in edges:
            a, b = rooms[i], rooms[j]
            gx = abs(b.center_x - a.center_x) - (a.width + b.width) / 2
            gy = abs(b.center_y - a.center_y) - (a.depth + b.depth) / 2
            gaps[frozenset((a.id, b.id))] = max(gx, gy, 1.0)
            # A Threshold holds here; :meth:`_stretch_thresholds` lengthens it.
            if a.district == b.district and halls[a.district] != 1.0:
                by_d.setdefault(a.district, []).append((i, j))
        if not by_d:
            return
        levels, lh = result.levels, result.level_height or 0.0
        nodes = {r.id: Storey(levels[k] if levels else 0, (levels[k] * lh) if levels else 0.0,
                              r.height) for k, r in enumerate(rooms)}
        pos = {r.id: (r.center_x, r.center_y) for r in rooms}
        half = {r.id: (r.width / 2, r.depth / 2) for r in rooms}
        # The engine's run (``_layout_context``), which sets how far rooms repel.
        run = ((RUN_FACTOR if self.run_factor is None else self.run_factor)
               * hall_run_scale(self._hall_profile, self.hall_length) * self.corridor_width)
        pairs = {d: [(rooms[i], rooms[j]) for i, j in es] for d, es in by_d.items()}
        drawn = {d: self._median_span(ps) for d, ps in pairs.items()}
        scale = {d: halls[d] for d in by_d}
        best = None
        for _round in range(HALL_RELAX_ROUNDS):
            runs = dict(gaps)
            for d, es in by_d.items():
                for i, j in es:
                    e = frozenset((ids[i], ids[j]))
                    runs[e] = gaps[e] * scale[d]
            out = spring_relax(ids, [(ids[i], ids[j]) for i, j in edges], pos, half, nodes,
                               run, self.corridor_width + 1.0, runs=runs)
            for r in rooms:
                r.center_x, r.center_y = out[r.id]
            got = {d: self._median_span(ps) / max(drawn[d], 1e-9) for d, ps in pairs.items()}
            miss = max(abs(got[d] / halls[d] - 1.0) for d in got)
            if best is None or miss < best[0]:
                best = (miss, out)
            if miss <= HALL_RELAX_TOLERANCE:
                break
            for d in scale:
                scale[d] *= halls[d] / max(got[d], 1e-9)
        for r in rooms:
            r.center_x, r.center_y = best[1][r.id]
        if not levels:
            self._separate_rooms(rooms)
        else:
            for lv in sorted(set(levels)):
                self._separate_rooms([r for k, r in enumerate(rooms) if levels[k] == lv])

    def _district_span(self, rooms: List[RoomSpec], d: int, e: int) -> float:
        """The :meth:`_hall_span` of the nearest pair (by centres) of a room of
        District *d* and one of *e*: the pair ``_district_swap`` tries first."""
        mine = [r for r in rooms if r.district == d]
        a, b = min(((a, b) for a in mine for b in rooms if b.district == e),
                   key=lambda p: (p[0].center_x - p[1].center_x) ** 2
                   + (p[0].center_y - p[1].center_y) ** 2)
        return self._hall_span(a, b)

    def _stretch_thresholds(self, rooms: List[RoomSpec], edges: List[Tuple[int, int]],
                            halls: Dict[int, float], before: List[RoomSpec]) -> None:
        """Each Threshold whose two Districts' defaults average ``f`` != 1, f times
        as long as in *before* (the rooms as they would stand without District hall
        lengths): the Districts beyond it (away from the entrance's, District 0)
        move together along the axis it leaves by, so no hall inside a District
        changes; then the Districts are pushed apart again. A Threshold is measured
        by :meth:`_district_span`, not its own rooms: one crossing a room is
        swapped for the nearest clear pair later (``_district_swap``), and after
        the hall lengths it often does. One already that long is left alone."""
        near: Dict[int, List[Tuple[int, int]]] = {}
        for i, j in edges:
            di, dj = rooms[i].district, rooms[j].district
            if di != dj:
                near.setdefault(di, []).append((i, j))
                near.setdefault(dj, []).append((j, i))
        seen, queue, moved = {0}, [0], False
        while queue:
            d = queue.pop(0)
            for i, j in near.get(d, ()):
                dj = rooms[j].district
                if dj in seen:
                    continue
                seen.add(dj)
                queue.append(dj)
                f = (halls.get(d, 1.0) + halls.get(dj, 1.0)) / 2
                if f == 1.0:
                    continue
                want = f * self._district_span(before, d, dj)
                if self._district_span(rooms, d, dj) >= want:
                    continue
                # The Districts beyond the Threshold: those reached from dj not via d.
                beyond, stack = {dj}, [dj]
                while stack:
                    x = stack.pop()
                    for _p, q in near.get(x, ()):
                        dq = rooms[q].district
                        if dq != d and dq not in beyond:
                            beyond.add(dq)
                            stack.append(dq)
                a, b = rooms[i], rooms[j]
                gx = abs(b.center_x - a.center_x) - (a.width + b.width) / 2
                gy = abs(b.center_y - a.center_y) - (a.depth + b.depth) / 2
                ux, uy = ((math.copysign(1.0, b.center_x - a.center_x), 0.0) if gx >= gy
                          else (0.0, math.copysign(1.0, b.center_y - a.center_y)))
                mine = [r for r in rooms if r.district in beyond]
                for _ in range(HALL_STRETCH_ROUNDS):
                    short = want - self._district_span(rooms, d, dj)
                    if short <= 1e-6:
                        break
                    for r in mine:
                        r.center_x += ux * short
                        r.center_y += uy * short
                moved = True
        if moved:
            self._separate_districts(rooms)

    def _separate_districts(self, rooms: List[RoomSpec], iterations: int = 400) -> None:
        """Push Districts apart whole until no room of one overlaps a room of
        another (with :meth:`_room_gap` between), each District moving as one so
        its own layout keeps its shape; :meth:`_separate_rooms` settles the rest."""
        groups: Dict[int, List[RoomSpec]] = {}
        for r in rooms:
            groups.setdefault(r.district, []).append(r)
        for _ in range(iterations):
            moved = False
            for a in range(len(rooms)):
                for b in range(a + 1, len(rooms)):
                    ra, rb = rooms[a], rooms[b]
                    if ra.district == rb.district:
                        continue
                    gap = self._room_gap(ra, rb)
                    dx = rb.center_x - ra.center_x
                    dy = rb.center_y - ra.center_y
                    ox = (ra.width + rb.width) / 2 + gap - abs(dx)
                    oy = (ra.depth + rb.depth) / 2 + gap - abs(dy)
                    if ox > 1e-9 and oy > 1e-9:
                        if ox < oy:
                            push, attr = ox / 2 * (1 if dx >= 0 else -1), "center_x"
                        else:
                            push, attr = oy / 2 * (1 if dy >= 0 else -1), "center_y"
                        for r in groups[ra.district]:
                            setattr(r, attr, getattr(r, attr) - push)
                        for r in groups[rb.district]:
                            setattr(r, attr, getattr(r, attr) + push)
                        moved = True
            if not moved:
                return

    def _race_of(self, room: RoomSpec) -> str:
        """The race that sizes *room*: its District's own, else the zone's."""
        if self._room_race is None:
            return self.race
        return self._room_race.get(room.id, self.race)

    def _pair_race(self, a: RoomSpec, b: RoomSpec) -> str:
        """The race that sizes the corridor between *a* and *b*: the smaller (by
        H) of their two races, so a Threshold between a giant and a goblin
        District is the goblins' hole (Req 4)."""
        ra, rb = self._race_of(a), self._race_of(b)
        return ra if semantics.body_height(ra) <= semantics.body_height(rb) else rb

    def _corridor_dims(self, a: RoomSpec, b: RoomSpec) -> Tuple[float, float]:
        """``(width, height)`` of the corridor between *a* and *b*."""
        if self._room_race is None:
            return self.corridor_width, self.corridor_height
        return semantics.corridor_size(self._pair_race(a, b))

    def _cw(self, a: RoomSpec, b: RoomSpec) -> float:
        """The width of the corridor between *a* and *b*."""
        return self._corridor_dims(a, b)[0]

    def _room_gap(self, a: RoomSpec, b: RoomSpec) -> float:
        """The separation gap between *a* and *b*: a full corridor width plus 1
        (:meth:`_separate_rooms`), the wider of their two races' corridors when
        Districts carry races, so a corridor of either fits between them."""
        if self._room_race is None:
            return self.corridor_width + 1.0
        return max(semantics.corridor_size(self._race_of(a))[0],
                   semantics.corridor_size(self._race_of(b))[0]) + 1.0

    def _rise_scale(self, a: RoomSpec, b: RoomSpec) -> float:
        """The elevation rise's scale on the edge *a*-*b*: the corridor's race's H
        over the zone race's (rises are drawn in H, ``rise_h``); 1 with no
        District races."""
        if self._room_race is None:
            return 1.0
        return semantics.body_height(self._pair_race(a, b)) / semantics.body_height(self.race)

    @staticmethod
    def _district_thresholds(part, edges: List[Tuple[int, int]],
                             links: int = 1) -> List[Tuple[int, int]]:
        """The Thresholds after the crossing and conflict passes, as
        ``(parent side, child side)`` in District order, or
        :class:`DistrictSplitError` when those passes joined two Districts by
        anything but one edge per original Threshold (Req 3.3), or, with
        *links* over 1 (an intrusion zone, district races Req 6), by more than
        *links* edges per Threshold pair. A split of a Threshold through a room
        of one of its own two Districts just moves it to that room's other
        edge. Of an intrusion pair's edges the Threshold is the one it was,
        else one still entering its child room, else the first."""
        assign = part.assign
        if len(set(LayoutGenerator._components(len(assign), edges))) > 1:
            raise DistrictSplitError()
        cross: Dict[frozenset, List[Tuple[int, int]]] = {}
        for i, j in edges:
            a, b = assign[i], assign[j]
            if a == b:
                continue
            pair = frozenset((a, b))
            if len(cross.get(pair, ())) >= links:
                raise DistrictSplitError()
            cross.setdefault(pair, []).append((i, j))
        wanted = [frozenset((assign[p], assign[c])) for p, c in part.thresholds]
        if set(cross) != set(wanted):
            raise DistrictSplitError()
        out = []
        for (p, c), pair in zip(part.thresholds, wanted):
            got = cross[pair]
            i, j = (next((e for e in got if frozenset(e) == frozenset((p, c))), None)
                    or next((e for e in got if c in e), None) or got[0])
            out.append((i, j) if assign[i] == assign[p] else (j, i))
        return out

    def _add_breaches(self, rooms: List[RoomSpec], edges: List[Tuple[int, int]],
                      part, links: int, tried: set) -> bool:
        """New breaches for each Threshold pair joined by fewer than *links*
        edges (district races Req 6, the lead's call at the task 6 review): a
        host room and an intruder room not yet joined, nearest first by hall
        span, rooms on no link of the pair (nor next to one in their District)
        before the rest, so the breaches spread along the boundary. A pair is
        taken only where its corridor could stand: a run no longer than the
        longest hall of its two Districts or their links, its rooms on one
        Level and within the run's grade, and no third room in its way.
        Appended to *edges* (loop edges: the passes after may still drop them,
        and the next round takes the next candidate; *tried* holds those already
        added once); True when any was. Draws nothing."""
        assign = part.assign
        if self._stack is not None:
            def blocked(i, j):
                return self._shape(rooms, i, j).blocked is not None
        else:
            crossed = self._crossed_room if self.corridor_clearance else self._crossed_room_centreline

            def blocked(i, j):
                return crossed(rooms, i, j) is not None
        have = {frozenset(e) for e in edges}
        nbrs: Dict[int, set] = {i: set() for i in range(len(rooms))}
        for i, j in edges:
            if assign[i] == assign[j]:
                nbrs[i].add(j)
                nbrs[j].add(i)
        added = False
        for p, c in part.thresholds:
            host, intruder = assign[p], assign[c]
            pair = {host, intruder}
            cross = [e for e in edges if {assign[e[0]], assign[e[1]]} == pair]
            want = links - len(cross)
            if want <= 0:
                continue
            spans = [self._hall_span(rooms[i], rooms[j]) for i, j in edges
                     if assign[i] in pair and assign[j] in pair]
            bound = BREACH_SPAN * max(spans) if spans else 0.0
            used = {r for e in cross for r in e}
            near = set(used) | {n for r in used for n in nbrs[r]}
            cands = []
            for h in (i for i in range(len(rooms)) if assign[i] == host):
                for t in (j for j in range(len(rooms)) if assign[j] == intruder):
                    if frozenset((h, t)) in have:
                        continue
                    span = self._hall_span(rooms[h], rooms[t])
                    if span > bound:
                        continue
                    cands.append((span, h, t))
            cands.sort()
            for tier in (0, 1, 2):
                for span, h, t in cands:
                    if want <= 0:
                        break
                    if frozenset((h, t)) in have or frozenset((h, t)) in tried:
                        continue
                    if tier == 0 and (h in near or t in near):
                        continue
                    if tier == 1 and (h in used or t in used):
                        continue
                    if self._is_stair(h, t):
                        continue
                    if abs(rooms[h].floor_z - rooms[t].floor_z) > self._edge_cap(rooms, h, t) + 1e-6:
                        continue
                    if blocked(h, t):
                        continue
                    edges.append((h, t))
                    have.add(frozenset((h, t)))
                    tried.add(frozenset((h, t)))
                    used |= {h, t}
                    near |= {h, t} | nbrs[h] | nbrs[t]
                    want -= 1
                    added = True
        return added

    @staticmethod
    def _district_breaches(part, edges: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """An intrusion zone's breaches as the edges now stand: every edge
        between two Districts but the Thresholds, as ``(host side, intruder
        side)``, the host being the lower District id (the Threshold's parent
        side: ids follow cut depth)."""
        assign = part.assign
        thresholds = {frozenset(t) for t in part.thresholds}
        out = []
        for i, j in edges:
            if assign[i] == assign[j] or frozenset((i, j)) in thresholds:
                continue
            out.append((i, j) if assign[i] < assign[j] else (j, i))
        return out

    @staticmethod
    def _record_districts(spec: ZoneSpec, part, rooms: List[RoomSpec],
                          edges: List[Tuple[int, int]], entrance: int) -> List[str]:
        """Fill ``spec.districts`` (rooms, entrance, climax, Threshold
        corridor) and flag the Threshold corridors. Returns the Threshold
        corridor ids in District order (District 1's first). A District's
        climax is the room pacing made its climax."""
        _districts.fill_district_rooms(spec.districts, part, rooms, entrance)
        cor_by_pair = {frozenset(e): f"corr_{k}" for k, e in enumerate(edges)}
        cors = {c.id: c for c in spec.corridors}
        ids = []
        for d, (p, c) in enumerate(part.thresholds, start=1):
            cid = cor_by_pair[frozenset((p, c))]
            cors[cid].threshold = True
            spec.districts[d].threshold_corridor = cid
            ids.append(cid)
        for dist in spec.districts:
            boss = [r.id for r in rooms if r.district == dist.id and r.role == "climax"]
            if boss:
                dist.climax_room = boss[0]
        return ids

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
        if getattr(result, "jittered", False):
            # The placement jittered its edges and Job B ran facing pairs
            # straight across their shared span (winding control task 8).
            rec["jitter"] = True
        return rec

    def _layout_context(self, room_count: int, theme: str,
                        race: str) -> LayoutContext:
        """The seam's one coupling to this generator (design "The seam")."""
        from .topology.rewrite import BuildContext   # see layout_engine.__getattr__
        # Hall length (step 30): a longer or shorter run for the graph placement and a
        # wider or narrower scatter for the classic one. An Envelope build lengthens its
        # halls in the separation instead (``_separate_rooms``).
        run_factor, spread = self.run_factor, 1.0
        if self.hall_length != 1.0 and self._envelope is None:
            from .topology.embed import RUN_FACTOR
            base = RUN_FACTOR if run_factor is None else run_factor
            run_factor = base * hall_run_scale(self._hall_profile, self.hall_length)
            spread = hall_spread_scale(self.hall_length)
        return LayoutContext(
            rng=self.rng,
            room_min=self.room_min, room_max=self.room_max,
            ceiling=self.ceiling, corridor_width=self.corridor_width,
            separate=self._separate_rooms,
            footprint_spread=CLASSIC_SPREAD if self.corridor_clearance else None,
            build=BuildContext(zone_type=self.zone_type, theme=theme, race=race,
                               race_scale=semantics.race_scale(race),
                               room_count=room_count),
            size_shift=self.size_shift,
            height_shift=self.size_shift - self.profile_shift,
            run_factor=run_factor, jitter=self.jitter, seed=self.seed,
            bearing=self.jitter, hall_spread=spread)

    # ------------------------------------------------------------------
    # Gating — solvability-guaranteed lock & key placement
    # ------------------------------------------------------------------

    def _apply_gating(self, spec: ZoneSpec, rooms: List[RoomSpec],
                      edges: List[Tuple[int, int]], entrance: int,
                      n_locks: int, thresholds: Optional[List[str]] = None) -> None:
        """
        Place `n_locks` lock-and-key gates on the room graph such that the
        dungeon is ALWAYS solvable.

        Method (a constrained graph-rewrite): lock only edges of the BFS tree
        rooted at the entrance. Cutting a tree edge cleanly partitions rooms
        into a "near" set (containing the entrance) and a "far" subtree. The
        key for that lock is placed in a room in the near set, outside any
        deeper locked subtree. This guarantees every key is obtainable before
        the door it opens — nested or sequential, never a deadlock.

        *thresholds* (a districted zone: the Threshold corridor ids, shallow
        to deep) are locked first (umbrella 23.7), then the tree edges as
        usual. Each Threshold is a bridge, so it is a tree edge and its far
        side is its District and the Districts beyond; its key goes on the
        near side by the same rule. (An intrusion pair's breaches make its
        Threshold a loop edge: it is locked first only while the tree runs
        through it.)

        A corridor with a ``drop`` (step 31) is one-way, from its upper room
        to its lower (``drop_arc``). The tree then follows the one-way edges,
        and each key is the first room (``gate_key_rooms``) that keeps the
        player from ever being stranded (``gate_solvable``): never past a drop
        with no way back to its lock. A lock no key room can serve is left
        out. With no drop this is exactly the two-way rule above.
        """
        n = len(rooms)
        if n < 3 or not edges:
            return

        by_id = {c.id: c for c in spec.corridors}
        drops = [corridor_drop(by_id[f"corr_{k}"]) if f"corr_{k}" in by_id else 0.0
                 for k in range(len(edges))]
        oneway = gate_oneway(edges, drops, [r.floor_z for r in rooms])

        parent, order, children = gate_tree(edges, entrance, oneway)
        depths = [r.graph_depth for r in rooms]

        # Candidate lock edges: tree edges that gate a meaningful subtree.
        tree_edges = [(c, parent[c]) for c in order if parent[c] is not None]
        tree_edges.sort(key=lambda e: rooms[e[0]].graph_depth, reverse=True)

        corr_by_pair = {}
        for k, (i, j) in enumerate(edges):
            corr_by_pair[frozenset((i, j))] = f"corr_{k}"

        if thresholds:
            pair_by_corr = {c: p for p, c in corr_by_pair.items()}
            first = []
            for cid in thresholds:
                a, b = tuple(pair_by_corr[cid])
                if parent.get(a) != b and parent.get(b) != a:
                    # An intrusion pair's breaches (district races Req 6) can
                    # carry the tree past its Threshold: no longer a bridge, it
                    # is no tree edge to lock first.
                    continue
                child = a if parent.get(a) == b else b
                first.append((child, parent[child]))
            first.sort(key=lambda e: rooms[e[0]].graph_depth)
            taken = {frozenset(e) for e in first}
            tree_edges = first + [e for e in tree_edges if frozenset(e) not in taken]

        chosen = []
        for child, par in tree_edges:
            if len(chosen) >= n_locks:
                break
            far = gate_subtree(children, child)
            if not gate_lockable(far, n):
                continue
            chosen.append((child, par, far))

        # Place locks shallow→deep (tier 0 = outermost).
        chosen.sort(key=lambda c: rooms[c[0]].graph_depth)
        locked_far: set = set()
        edge_of = {f"corr_{k}": k for k in range(len(edges))}
        locks: Dict[int, Set[str]] = {}
        keys: Dict[int, Set[str]] = {}
        for tier, (child, par, far) in enumerate(chosen):
            corr_id = corr_by_pair.get(frozenset((child, par)))
            if corr_id is None:
                continue

            key_room = gate_key_room(depths, entrance, far, locked_far)
            if oneway:
                gid, k = f"gate_{tier}", edge_of[corr_id]
                for cand in gate_key_rooms(key_room, depths, entrance, far, locked_far):
                    trial_keys = {**keys, cand: keys.get(cand, set()) | {gid}}
                    trial_locks = {**locks, k: locks.get(k, set()) | {gid}}
                    if gate_solvable(edges, entrance, trial_locks, trial_keys, oneway):
                        key_room, keys, locks = cand, trial_keys, trial_locks
                        break
                else:
                    continue

            cor = next(c for c in spec.corridors if c.id == corr_id)
            spec.gates.append(gate_spec(f"gate_{tier}", cor, rooms[key_room], tier))
            locked_far |= far

    # ------------------------------------------------------------------
    # Pacing — graph-derived roles & depth
    # ------------------------------------------------------------------

    def _apply_pacing(self, rooms: List[RoomSpec],
                      edges: List[Tuple[int, int]],
                      entry: Optional[Tuple[float, float]] = None,
                      size_bias: bool = True,
                      climax: Optional[int] = None,
                      climaxes: Optional[List[int]] = None,
                      among: Optional[List[int]] = None,
                      oneway: Optional[Mapping[int, Tuple[int, int]]] = None) -> int:
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

        *climaxes* (a districted zone, one per District): those rooms are the
        climaxes and the single-climax rule above is skipped. Depth stays BFS
        from the zone entrance.

        *oneway* (``gate_oneway``: edge index -> (upper, lower), the drop
        corridors of step 31): depth is then hops walked from the entrance,
        a drop only downward. Roles still count every corridor at a room.
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
        walk = adj
        if oneway:
            walk = defaultdict(list)
            for room, pairs in gate_adjacency(edges, oneway).items():
                walk[room] = [m for m, _k in pairs]

        entrance = self._find_entrance(rooms, entry, among)

        # BFS graph-depth from the entrance.
        gdepth = {entrance: 0}
        q = deque([entrance])
        while q:
            cur = q.popleft()
            for nxt in walk[cur]:
                if nxt not in gdepth:
                    gdepth[nxt] = gdepth[cur] + 1
                    q.append(nxt)
        for i in range(n):
            rooms[i].graph_depth = gdepth.get(i, 0)

        # Climax = the engine's pick, else the deepest room (ties broken by
        # lowest index for determinism). Depth stays BFS from the entrance.
        if climaxes is not None:
            peaks = set(climaxes)
        elif n == 1:
            peaks = {entrance}
        else:
            if climax is None or not 0 <= climax < n or climax == entrance:
                climax = max(range(n), key=lambda i: (rooms[i].graph_depth, -i))
            peaks = {climax}

        # Assign roles.
        for i in range(n):
            deg = len(adj[i])
            if i == entrance:
                rooms[i].role = "entrance"
            elif i in peaks:
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

    @staticmethod
    def _find_entrance(rooms: List[RoomSpec],
                       entry: Optional[Tuple[float, float]] = None,
                       among: Optional[List[int]] = None) -> int:
        """Pacing's zone entrance (no rng): the room nearest *entry* when
        there is a way in (of the rooms ``among``, when given), else the one
        farthest from the layout centroid."""
        n = len(rooms)
        if entry is not None:
            # Entrance = the room nearest the way in.
            ex, ey = entry
            return min(
                among or range(n),
                key=lambda i: (rooms[i].center_x - ex) ** 2 + (rooms[i].center_y - ey) ** 2,
            )
        # Entrance = the room farthest from the layout centroid (peripheral).
        cx = sum(r.center_x for r in rooms) / n
        cy = sum(r.center_y for r in rooms) / n
        return max(
            range(n),
            key=lambda i: (rooms[i].center_x - cx) ** 2 + (rooms[i].center_y - cy) ** 2,
        )

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
            # Room-graph zones are clamped to the race's bands afterwards.
            r.height = r.height * cs if self.corridor_clearance else max(40.0, r.height * cs)

    # ------------------------------------------------------------------
    # Separation (engines reach it through LayoutContext.separate)
    # ------------------------------------------------------------------

    def _separate_rooms(self, rooms: List[RoomSpec],
                        iterations: Optional[int] = None,
                        storeys: Optional[list] = None,
                        throats: Optional[set] = None) -> None:
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

        *throats* (a cave's bearing placement, cave clumps task 3): room id
        pairs (frozensets) to hold ``embed.THROAT_GAP`` apart with their doors
        in line (:meth:`_separate_with_throats`). None or empty: as before.
        """
        stacked = None
        if storeys is not None:
            from .topology.embed import may_overlap_in_plan
            stacked = {(a, b) for a in range(len(rooms)) for b in range(a + 1, len(rooms))
                       if may_overlap_in_plan(storeys[a], storeys[b])}
        if throats and self.corridor_clearance:
            self._separate_with_throats(rooms, throats, stacked, iterations or 200)
            return
        if self.corridor_clearance:
            # (Before stock scale this read max(width, 30): corridors were at
            # least 40 u, so the 30 never applied. Stock corridors are 3 H.)
            gap = self.corridor_width + 1.0
            # An Envelope build's halls lengthen here (hall length step 30): the fit to
            # the hill shrinks any longer run back, so the gap after it carries them.
            if self._envelope is not None and self._hall_gap != 1.0:
                gap *= self._hall_gap
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
                    g = gap if self._room_race is None else self._room_gap(ra, rb)
                    # Required half-separation on each axis (AABB + gap)
                    min_dx = (ra.width + rb.width) / 2 + g
                    min_dy = (ra.depth + rb.depth) / 2 + g
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

    def _pair_gap(self, a: RoomSpec, b: RoomSpec, gap: float) -> float:
        """*gap* (the zone's corridor width plus 1), or with District races the
        pair's own (:meth:`_room_gap`), as :meth:`_separate_rooms` takes it."""
        return gap if self._room_race is None else self._room_gap(a, b)

    def _separate_with_throats(self, rooms: List[RoomSpec], throats: set,
                               stacked: Optional[set], iterations: int) -> None:
        """:meth:`_separate_rooms` for a cave's bearing placement with throats
        (cave clumps task 3; that spec's archive decision 2). First each
        throat's far room is squared up off its partner's wall
        (:meth:`_snap_throats`): ``embed.THROAT_GAP`` wall to wall, slid along
        the wall no further than both doors still stand on one line
        (``embed.throat_slack``), so its short corridor runs straight. Then
        pairs are pushed apart as before, a throat's to THROAT_GAP, every
        other pair's to a corridor width plus 1; rooms joined by throats move
        together when pushed by another, so the throats hold. With District
        races (district races Req 4) the corridor width is the pair's race's,
        in the slack and the gap alike (THROAT_GAP stays: it never scales)."""
        from .topology.embed import THROAT_GAP
        gap = self.corridor_width + 1.0
        at = {r.id: k for k, r in enumerate(rooms)}
        pairs = sorted({tuple(sorted((at[a], at[b]))) for a, b in (tuple(p) for p in throats)
                        if a in at and b in at})
        pairs = [p for p in pairs if not (stacked and p in stacked)]
        kept = self._snap_throats(rooms, pairs, gap, THROAT_GAP)
        # The rooms each throat-joined group moves together.
        root = list(range(len(rooms)))

        def find(x: int) -> int:
            while root[x] != x:
                root[x] = root[root[x]]
                x = root[x]
            return x
        for a, b in sorted(kept):
            ra_, rb_ = find(a), find(b)
            if ra_ != rb_:
                root[max(ra_, rb_)] = min(ra_, rb_)
        group: Dict[int, List[int]] = {}
        for k in range(len(rooms)):
            group.setdefault(find(k), []).append(k)
        # Groups pushed whole first; if that hasn't settled (a group wedged
        # between others can rock back and forth), room by room, a throat
        # that no longer stands as one (:meth:`_throat_stands`) then kept a
        # corridor width plus 1 apart like any pair.
        if self._push_apart(rooms, stacked, iterations, gap, THROAT_GAP, kept,
                            lambda k: group[find(k)]):
            return
        self._push_apart(rooms, stacked, iterations, gap, THROAT_GAP, kept, None)

    def _push_apart(self, rooms: List[RoomSpec], stacked: Optional[set], iterations: int,
                    gap: float, tgap: float, kept: set, group) -> bool:
        """:meth:`_separate_with_throats`'s pushes: pairs of *kept* ``tgap``
        apart, others *gap*. With *group* (room index -> the rooms that move
        with it) a pair in two groups moves both groups; without, rooms move
        alone and a throat counts only while it stands. True when settled."""
        for _ in range(iterations):
            moved = False
            held = kept if group is not None else {
                (a, b) for a, b in kept if self._throat_stands(rooms[a], rooms[b], tgap)}
            for a in range(len(rooms)):
                for b in range(a + 1, len(rooms)):
                    if stacked and (a, b) in stacked:
                        continue
                    ra, rb = rooms[a], rooms[b]
                    g = tgap if (a, b) in held else self._pair_gap(ra, rb, gap)
                    dx = rb.center_x - ra.center_x
                    dy = rb.center_y - ra.center_y
                    ox = (ra.width + rb.width) / 2 + g - abs(dx)
                    oy = (ra.depth + rb.depth) / 2 + g - abs(dy)
                    if ox > 1e-9 and oy > 1e-9:
                        ga = group(a) if group is not None else [a]
                        gb = group(b) if group is not None else [b]
                        movers = (ga, gb) if ga is not gb else ([a], [b])
                        if ox < oy:
                            push = ox / 2 * (1 if dx >= 0 else -1)
                            for k in movers[0]:
                                rooms[k].center_x -= push
                            for k in movers[1]:
                                rooms[k].center_x += push
                        else:
                            push = oy / 2 * (1 if dy >= 0 else -1)
                            for k in movers[0]:
                                rooms[k].center_y -= push
                            for k in movers[1]:
                                rooms[k].center_y += push
                        moved = True
            if not moved:
                return True
        return False

    def _snap_throats(self, rooms: List[RoomSpec], pairs: List[Tuple[int, int]],
                      gap: float, tgap: float) -> set:
        """Square each throat up (:meth:`_square_throat`), over each tree of
        throats breadth first from its lowest room; returns the throats that
        stand (index pairs). A far room that would come within the separation
        gap of another room of its tree stays where it was, and its throat
        is an ordinary corridor; so is a throat closing a loop of throats
        unless it already stands as one."""
        nbrs: Dict[int, List[int]] = {}
        for a, b in pairs:
            nbrs.setdefault(a, []).append(b)
            nbrs.setdefault(b, []).append(a)
        is_pair = set(pairs)
        kept: set = set()
        done: set = set()

        def box_gap(p: RoomSpec, q: RoomSpec) -> float:
            return max(abs(q.center_x - p.center_x) - (p.width + q.width) / 2,
                       abs(q.center_y - p.center_y) - (p.depth + q.depth) / 2)
        for start in sorted(nbrs):
            if start in done:
                continue
            done.add(start)
            tree = [start]
            queue = [start]
            while queue:
                a = queue.pop(0)
                for b in sorted(nbrs[a]):
                    pair = (min(a, b), max(a, b))
                    if b in done:
                        if pair not in kept and self._throat_stands(rooms[a], rooms[b], tgap):
                            kept.add(pair)
                        continue
                    done.add(b)
                    queue.append(b)
                    rb = rooms[b]
                    was = (rb.center_x, rb.center_y)
                    self._square_throat(rooms[a], rb, tgap)
                    if any(box_gap(rb, rooms[c]) < (tgap if (min(b, c), max(b, c)) in is_pair
                                                    else self._pair_gap(rb, rooms[c], gap)) - 1e-6
                           for c in tree if c != a):
                        rb.center_x, rb.center_y = was
                    else:
                        kept.add(pair)
                    tree.append(b)
        return kept

    def _square_throat(self, ra: RoomSpec, rb: RoomSpec, tgap: float) -> None:
        """Put *rb* ``tgap`` off *ra*'s wall facing it (the axis they're most
        apart on), slid along that wall as it stood, up to
        ``embed.throat_slack`` either way. In place on *rb*."""
        from .topology.embed import throat_slack
        gx = abs(rb.center_x - ra.center_x) - (ra.width + rb.width) / 2
        gy = abs(rb.center_y - ra.center_y) - (ra.depth + rb.depth) / 2
        if gx >= gy:
            lim = throat_slack((ra.depth + rb.depth) / 2, self._cw(ra, rb))
            sx = 1.0 if rb.center_x >= ra.center_x else -1.0
            rb.center_x = ra.center_x + sx * ((ra.width + rb.width) / 2 + tgap)
            rb.center_y = ra.center_y + max(-lim, min(lim, rb.center_y - ra.center_y))
        else:
            lim = throat_slack((ra.width + rb.width) / 2, self._cw(ra, rb))
            sy = 1.0 if rb.center_y >= ra.center_y else -1.0
            rb.center_y = ra.center_y + sy * ((ra.depth + rb.depth) / 2 + tgap)
            rb.center_x = ra.center_x + max(-lim, min(lim, rb.center_x - ra.center_x))

    def _throat_stands(self, ra: RoomSpec, rb: RoomSpec, tgap: float) -> bool:
        """Do *ra* and *rb* already stand as a throat: ``tgap`` apart (within
        a unit) on the axis they're most apart on, slid within
        ``embed.throat_slack``?"""
        from .topology.embed import throat_slack
        gx = abs(rb.center_x - ra.center_x) - (ra.width + rb.width) / 2
        gy = abs(rb.center_y - ra.center_y) - (ra.depth + rb.depth) / 2
        if gx >= gy:
            lim = throat_slack((ra.depth + rb.depth) / 2, self._cw(ra, rb))
            off = abs(rb.center_y - ra.center_y)
        else:
            lim = throat_slack((ra.width + rb.width) / 2, self._cw(ra, rb))
            off = abs(rb.center_x - ra.center_x)
        return abs(max(gx, gy) - tgap) <= 1.0 and off <= lim + 1e-6

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

        Districted (``self._district_assign``, districts spec Req 3.3): a split
        whose waypoint would join two Districts by a new edge drops A–B
        instead when the graph stays whole without it (a loop edge, as the
        partition drops). A bridge is swapped for the shortest edge on the
        same District pair that rejoins its two halves crossing no room (as
        `_resolve_conflicts` swaps a clashing bridge); with none, it is split
        anyway and the District check after this pass rejects the Draw.
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
                # is split once; met again it is kept, for _resolve_conflicts
                # to drop or swap (_clear_blocked).
                if key in split:
                    c = None
                else:
                    split.add(key)
            if c is None:
                if key not in seen:
                    seen.add(key)
                    resolved.append((i, j))
                continue
            if (self._district_assign is not None
                    and self._joins_districts(i, j, c)):
                rest = resolved + pending
                if self._connected_without(len(rooms), rest, i, j):
                    changed = True
                    continue
                swap = self._district_swap(rooms, rest, i, j, crossed_room)
                if swap is not None:
                    changed = True
                    pending.append(swap)
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

    def _joins_districts(self, i: int, j: int, c: int) -> bool:
        """Would splitting edge i–j through room c add a District pair the
        edge didn't have? (Within a District, c must be in it; a Threshold
        may move to c on either of its two sides.)"""
        a = self._district_assign
        return a[c] not in (a[i], a[j])

    @staticmethod
    def _components(n: int, edges: List[Tuple[int, int]]) -> List[int]:
        """Each room's union-find root over *edges*."""
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for u, v in edges:
            ru, rv = find(u), find(v)
            if ru != rv:
                parent[ru] = rv
        return [find(x) for x in range(n)]

    def _connected_without(self, n: int, edges: List[Tuple[int, int]], i: int, j: int) -> bool:
        """Are rooms i and j joined by *edges* (which leave out the i–j edge
        being judged)?"""
        roots = self._components(n, edges)
        return roots[i] == roots[j]

    def _district_swap(self, rooms: List[RoomSpec], rest: List[Tuple[int, int]],
                       i: int, j: int, crossed_room) -> Optional[Tuple[int, int]]:
        """Districted: a stand-in for bridge i–j (*rest* is the graph without
        it): the shortest edge joining its two halves on the same District
        pair (one District, or the Threshold's two) that crosses no room, or
        None. (One crossing a room of its own Districts would be split again,
        and could be swapped back: no fixpoint.)"""
        da = self._district_assign
        roots = self._components(len(rooms), rest)
        pair = frozenset((da[i], da[j]))
        near, far = roots[i], roots[j]
        cands = sorted(
            ((u, v) for u in range(len(rooms)) if roots[u] == near
             for v in range(len(rooms)) if roots[v] == far
             if frozenset((da[u], da[v])) == pair),
            key=lambda e: (rooms[e[0]].center_x - rooms[e[1]].center_x) ** 2
            + (rooms[e[0]].center_y - rooms[e[1]].center_y) ** 2)
        for u, v in cands:
            if crossed_room(u, v) is None:
                return (u, v)
        return None

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
        a, b = rooms[i], rooms[j]
        hw = self._cw(a, b) / 2
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
        def hw_of(i: int, j: int) -> float:
            """Half the width of edge i-j's corridor (its race's, with District races)."""
            return self._cw(rooms[i], rooms[j]) / 2

        def route_for(i: int, j: int):
            a, b = rooms[i], rooms[j]
            fx, fy = self._wall_point(a, b)
            tx, ty = self._wall_point(b, a)
            return plan_route((fx, fy), (tx, ty),
                              self._exit_axis_x(a, b), self._exit_axis_x(b, a),
                              hw_of(i, j), steps=0)

        def leg_rects(route, hw):
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
            hw = hw_of(i, j)
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
                cache[e] = (leg_rects(rt, hw_of(*e)), floor_pieces(e[0], e[1], rt))
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
            # Districted: the stand-in joins the same District pair (one
            # District, or the Threshold's two), so no new link appears.
            da = self._district_assign
            pair = (frozenset((da[es[idx][0]], da[es[idx][1]]))
                    if da is not None else None)
            cands = sorted(
                ((u, v) for u in range(len(rooms)) if roots[u] == side
                 for v in range(len(rooms)) if roots[v] != side
                 if pair is None or frozenset((da[u], da[v])) == pair),
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

        def clear_blocked() -> bool:
            """Stacked: an edge a third room still blocks, on every route it
            has, after its one split (``_resolve_crossings``) can't be built
            clear: its stub or leg would stand in that room. It goes the way a
            clash does: a loop edge is dropped, a tree edge swapped for a clear
            one. Kept and reported (``crosses_room``) only when nothing clear
            rejoins the graph."""
            changed = False
            for k in range(len(edges) - 1, -1, -1):
                i, j = edges[k]
                blocked = self._shape(rooms, i, j).blocked
                if blocked is None or blocked in (i, j):
                    continue
                if is_removable(k, edges):
                    del edges[k]
                else:
                    e = substitute(k, edges)
                    if e is None:
                        self.warnings.append(
                            f"crosses_room: {rooms[i].id}-{rooms[j].id}")
                        continue
                    edges[k] = e
                changed = True
            return changed

        def restore_dropped(before: List[Tuple[int, int]]) -> None:
            """Stacked: an edge dropped for a clash comes back when it now
            clears every room and corridor (the corridor it met may have moved
            or gone too), a stair on any of its routes. A clash drops the
            first edge of its pair that can go, so this is often a loop that
            needn't have fallen."""
            have = {frozenset(e) for e in edges}
            for e in before:
                if frozenset(e) in have:
                    continue
                edges.append(e)
                k = len(edges) - 1
                if self._is_stair(*e):
                    clear = self._reroute_stair(rooms, edges, (k,))
                else:
                    clear = (self._shape(rooms, *e).blocked is None
                             and not any(self._clash_3d(rooms, e, o)
                                         for o in edges[:k]))
                if clear:
                    have.add(frozenset(e))
                else:
                    edges.pop()

        # No Z clearance exemption: two corridors whose floors overlap in XY
        # are stacked floors (or intersecting ones) at ANY height difference,
        # and a box build must have one depth band (task 14). Flat floors all
        # sit at 0, so for them this is the same footprint test as before.
        # A conflict between two tree edges (neither can drop) is resolved by
        # swapping one for another edge that rejoins the graph cleanly.
        before = list(edges)
        removed_any = False
        if self._stack is not None:
            removed_any = clear_blocked()
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

        # Districted: a stand-in must join the same District pair, so two tree
        # edges can clash with nothing to swap in, and the corridors would be
        # built through each other (district-looks task 5, seed 1867829545).
        # That Draw is redrawn, as a second link between Districts is.
        if self._district_assign is not None and any(
                a in edges and b in edges and clash(a, b) for a, b in stuck):
            raise DistrictSplitError()

        if self._stack is not None:
            restore_dropped(before)
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
                    if self._room_race is not None:
                        rise *= self._rise_scale(rooms[cur], rooms[nxt])
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

        A stacked build (step 7 task 7) shifts the whole stack: its offset
        moves with the floors, so the relax keeps each room in its Level's
        band at the new height (it pulled them back to where the engine put
        them before) and the Slab between Levels holds; a room's band is then
        its Envelope band within its Level's.
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
        if self._stack is not None:
            self._stack = self._stack._replace(offset=self._stack.offset + shift)
            for k, (lo, hi) in enumerate(bands):
                blo, bhi = self._stack.band(k)
                if max(lo, blo) <= min(hi, bhi):
                    bands[k] = (max(lo, blo), min(hi, bhi))
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
        spanning from the lower floor to the higher floor plus its height,
        and a Switchback's stairwell (``stair_layout``, the box the builder
        folds the stair into beside its leg) over the same heights: a
        stairwell past the footprint's edge puts stair floor under the map's
        edge (step 7 task 19)."""
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
            pieces = list(route_footprint(corridor_route(c, rooms), c.width / 2))
            lay = stair_layout(c, rooms)
            if lay is not None and lay.stairwell is not None:
                pieces.append(lay.stairwell)
            for x0, y0, x1, y1 in pieces:
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
            self._cw(a, b) / 2, steps=0)
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
            return max(0.0, legs[1] - self._cw(a, b))
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
            self._mark_bridges(spec.corridors[len(spec.corridors) - len(edges):],
                               rooms, edges)
            self._set_entries(spec.corridors[len(spec.corridors) - len(edges):], rooms,
                              spec.corridors)
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
            width, height = self._corridor_dims(a, b)
            spec.corridors.append(CorridorSpec(
                id=f"corr_{k}",
                from_x=fx, from_y=fy,
                to_x=tx, to_y=ty,
                from_z=a.floor_z, to_z=b.floor_z,
                width=width,
                height=height,
                steps=0,
                from_room=a.id, to_room=b.id,
            ))
            self._open_facing_walls(a, b)
            self._open_facing_walls(b, a)
        self._set_entries(spec.corridors[len(spec.corridors) - len(edges):], rooms,
                          spec.corridors)

    def _set_entries(self, corridors: List[CorridorSpec], rooms: List[RoomSpec],
                     every: List[CorridorSpec]) -> None:
        """A bearing placement's entry angles (random placement task 10): each
        plain corridor's run-outs leave their openings toward the other opening,
        up to ``ENTRY_MAX`` off the wall's normal (``CorridorSpec.entry``), so a
        corridor meets a room at an angle as the room stands. Left square when
        both angles are under ``ENTRY_MIN`` or the angled line would fold
        (``routing.entry_line``), or when its wider opening would come within
        ``ENTRY_PIER`` of another door on its wall (``every``: all the build's
        corridors). Nothing without a bearing placement."""
        if not self._bearing_doors:
            return
        import math
        from .routing import ENTRY_RUN, entry_line
        by_id = {r.id: r for r in rooms}
        cap = math.radians(ENTRY_MAX)
        # What every corridor takes up, for ``_entry_clear``: its legs, bends and stairwell
        # until it is angled, then its angled line's strip.
        taken: Dict[str, list] = {}
        for cor in corridors:
            if cor.steps != 0 or cor.side or cor.bridge:
                continue
            wps = corridor_route(cor, by_id).waypoints
            fr, to = by_id[cor.from_room], by_id[cor.to_room]
            # Toward the other opening; when the openings face each other square (a
            # straight route through a shared span), toward the other room's centre, so
            # the tunnel sweeps across between rooms that stand at an angle.
            target = [0.0, 0.0]
            for fars in ((wps[-1], wps[0]), ((to.center_x, to.center_y), (fr.center_x, fr.center_y))):
                for e, (p, q, far) in enumerate(((wps[0], wps[1], fars[0]), (wps[-1], wps[-2], fars[1]))):
                    nx, ny = q[0] - p[0], q[1] - p[1]
                    tx, ty = far[0] - p[0], far[1] - p[1]
                    a = math.atan2(nx * ty - ny * tx, nx * tx + ny * ty)
                    target[e] = max(-cap, min(cap, a))
                if any(abs(math.degrees(a)) >= ENTRY_MIN for a in target):
                    break
            if len(wps) == 2 and math.dist(wps[0], wps[1]) >= 2 * ENTRY_RUN:
                # A straight route long enough to sweep across leaves at least ENTRY_SWEEP
                # off square, toward the other room's side (left when they stand square on).
                sweep = math.radians(ENTRY_SWEEP)
                target = [math.copysign(max(abs(a), sweep), a) for a in target]
            if len(wps) > 2:
                # A bend closer than 3/4 of a corridor width to its opening leaves no room to angle.
                target = [a if math.dist(p, q) >= 0.75 * cor.width else 0.0
                          for a, (p, q) in zip(target, ((wps[0], wps[1]), (wps[-1], wps[-2])))]
            # The first that keeps clear: both ends, then one end alone, at full, half and a
            # quarter of the target; an angled line can fold, bend within a half width of a
            # room (rooms close together: the run-outs overshoot), or leave its rise too
            # short a run between its flat run-outs (steeper than max_grade).
            angles = []
            for share in ENTRY_SHARES:
                for keep in ((1, 1), (1, 0), (0, 1)):
                    tried = [round(math.degrees(a * share * k), 2) for a, k in zip(target, keep)]
                    tried = [a if abs(a) >= ENTRY_MIN else 0.0 for a in tried]
                    if not any(tried):
                        continue
                    cor.entry = tried
                    line = entry_line(corridor_route(cor, by_id), cor.width / 2, ENTRY_RUN)
                    if line is None or not _line_clear(line, cor, rooms):
                        continue
                    seg = [math.dist(line[k], line[k + 1]) for k in range(len(line) - 1)]
                    carry = sum(seg) - seg[0] - seg[-1]
                    if abs(cor.to_z - cor.from_z) <= max(carry, 0.0) * self.max_grade \
                            and _entry_clear(line, cor, every, by_id, taken):
                        angles = tried
                        break
                if angles:
                    break
            cor.entry = angles
            if angles:
                taken[cor.id] = _line_solids(line, cor)
        # A wider, shifted opening must keep a pier to the doors beside it.
        from types import SimpleNamespace
        from .geometry import _door_openings
        build = SimpleNamespace(rooms=rooms, corridors=every)

        def pier(room: RoomSpec) -> float:
            """The least wall between two doors on one of the room's walls."""
            least = math.inf
            for cuts in _door_openings(room, build).values():
                cuts = sorted(cuts)
                least = min([least] + [b[0] - a[1] for a, b in zip(cuts, cuts[1:])])
            return least

        for cor in corridors:
            if not cor.entry:
                continue
            for rid in (cor.from_room, cor.to_room):
                angled = pier(by_id[rid])
                if angled >= ENTRY_PIER:
                    continue
                kept, cor.entry = cor.entry, []
                if pier(by_id[rid]) <= angled:
                    cor.entry = kept        # as tight square: not the angle's doing
                else:
                    break

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
        Level's band instead (``_Stack.band``). A throat (cave clumps task 3)
        keeps its two rooms level: its 12 u run is too short a ramp to read as
        one room opening into the next."""
        if self._is_stair(i, m):
            return float("inf")
        if self._throats and frozenset((rooms[i].id, rooms[m].id)) in self._throats:
            return 0.0
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
                        if self._room_race is not None:
                            rise *= self._rise_scale(rooms[cur], rooms[nxt])
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

    def _mark_bridges(self, corridors: List[CorridorSpec], rooms: List[RoomSpec],
                      edges: List[Tuple[int, int]]) -> None:
        """Step 7 task 11: a corridor within a Level that passes over a room
        on a lower Level becomes a Bridge over it (``CorridorSpec.bridge``)
        wherever ``geometry.bridge_layout`` can place one: the deck stays
        where the corridor already runs (the Slab over the lower ceiling, so
        the crossing split and the conflict pass left it alone), and the
        lower room's ceiling opens in a slot under it. The slot's shaft
        (the slot, from the lower ceiling to the corridor's ceiling) must be
        clear of every other room, every other corridor and every other
        Bridge's shaft; one Bridge per lower room. Corridors and rooms keep
        their routes, floors and sizes, so nothing else moves, and a build
        with no such corridor is unchanged. No rng draws."""
        levels = self._stack.levels
        by_id = {r.id: r for r in rooms}
        shafts: List[Tuple[Tuple[float, float, float, float], float, float]] = []
        bridged = set()
        for k, (i, j) in enumerate(edges):
            if levels[i] != levels[j]:
                continue
            cor = corridors[k]
            for m, hall in enumerate(rooms):
                if levels[m] >= levels[i] or m in bridged:
                    continue
                for cand in (dataclasses.replace(cor, bridge=hall.id),
                             self._straight_cor(rooms, edges, k, cor, hall)):
                    bl = cand and bridge_layout(cand, by_id)
                    if not bl:
                        continue
                    if self._straight_doors and self._slot_meets_door(bl.slot, hall, corridors, k):
                        continue
                    shaft = (bl.slot, bl.ceiling, bl.top)
                    if self._shaft_clear(rooms, edges, k, m, shaft, shafts):
                        for f in ("from_x", "from_y", "to_x", "to_y", "bridge"):
                            setattr(cor, f, getattr(cand, f))
                        self._shapes[(i, j)] = self._make_shape(rooms, i, j, cor)
                        bridged.add(m)
                        shafts.append(shaft)
                        break
                if cor.bridge:
                    break

    def _straight_cor(self, rooms: List[RoomSpec], edges: List[Tuple[int, int]],
                      k: int, cor: CorridorSpec, hall: RoomSpec
                      ) -> Optional[CorridorSpec]:
        """Corridor ``k`` as a Bridge over ``hall`` on one straight leg: both
        doors on the same cross line, inside both rooms' facing walls (and as
        near the hall's middle as they allow), so the deck needn't turn. None
        when the walls share too little, when it is the route already, or
        when the new route meets a room or another corridor (the planned
        pieces, with the Slab between)."""
        i, j = edges[k]
        a, b = rooms[i], rooms[j]
        hw = cor.width / 2
        along_x = self._exit_axis_x(a, b)
        (ax0, ay0, _), (ax1, ay1, _) = a.bounds
        (bx0, by0, _), (bx1, by1, _) = b.bounds
        lo, hi = (max(ay0, by0), min(ay1, by1)) if along_x else (max(ax0, bx0), min(ax1, bx1))
        lo, hi = lo + 2 * hw, hi - 2 * hw
        if hi < lo:
            return None
        mid = hall.center_y if along_x else hall.center_x
        c = min(hi, max(lo, mid))
        if along_x:
            if abs(cor.from_y - c) < 1e-6 and abs(cor.to_y - c) < 1e-6:
                return None
            new = dataclasses.replace(cor, from_y=c, to_y=c, bridge=hall.id)
        else:
            if abs(cor.from_x - c) < 1e-6 and abs(cor.to_x - c) < 1e-6:
                return None
            new = dataclasses.replace(cor, from_x=c, to_x=c, bridge=hall.id)
        shape = self._make_shape(rooms, i, j, new)
        if shape.blocked is not None:
            return None
        # Every other corridor, those leaving i or j too: moving the doors can
        # put one into a door already on that wall (seed 432395022, Winding 2:
        # room_6-room_2 straightened onto room_2's west-wall stair door, the
        # two openings 14 u apart at 18 u wide, an open seam). As
        # ``_clash_3d``, a stub pinned to a shared room may share it.
        for q, e in enumerate(edges):
            if q == k:
                continue
            shared = set(e) & {i, j}
            other = self._shape(rooms, *e)
            if self._pieces_clash(shape.pieces, other.pieces, shared):
                return None
            if any(self._doors_clash(new, other.cor, rooms[m]) for m in shared):
                return None
        return new

    @classmethod
    def _slot_meets_door(cls, slot, hall: RoomSpec, corridors: List[CorridorSpec],
                         k: int) -> bool:
        """Does a Bridge's ``slot`` in ``hall`` overlap the piece of a door's corridor inside
        ``hall`` (from the wall to ``_wall_point``'s inset)? The slot is a Throat of the
        hall's floor, and that piece's side walls would stand in it (winding control task 10:
        seed 2071938654, Winding 2, room_5's straight west door 2 u into corr_8's slot, "wall
        across throat"). ``_shaft_clear`` reads the shaft only from the hall's ceiling up."""
        (x0, y0, _), (x1, y1, _) = hall.bounds
        inset = 2.0                      # _wall_point's inset
        for q, other in enumerate(corridors):
            if q == k:
                continue
            at = cls._door_on_wall(other, hall)
            if at is None:
                continue
            wall, c = at
            hw = other.width / 2
            piece = {"W": (x0, c - hw, x0 + inset, c + hw), "E": (x1 - inset, c - hw, x1, c + hw),
                     "S": (c - hw, y0, c + hw, y0 + inset), "N": (c - hw, y1 - inset, c + hw, y1)}[wall]
            if (min(slot[2], piece[2]) - max(slot[0], piece[0]) > _TOUCH
                    and min(slot[3], piece[3]) - max(slot[1], piece[1]) > _TOUCH):
                return True
        return False

    @staticmethod
    def _pieces_clash(pa, pb, shared) -> bool:
        """Do two corridors' planned pieces overlap without the Slab between?
        A piece pinned to a room both corridors leave (``shared``) may meet
        the other's piece pinned there: they share that doorway's stub."""
        from .topology.embed import SLAB

        def cells(r):
            return (math.floor(r[0] / CONFLICT_CELL), math.floor(r[1] / CONFLICT_CELL),
                    math.floor((r[2] - _TOUCH) / CONFLICT_CELL), math.floor((r[3] - _TOUCH) / CONFLICT_CELL))

        for (ra, za0, za1, ka) in pa:
            for (rb, zb0, zb1, kb) in pb:
                if ka is not None and ka == kb and ka in shared:
                    continue
                if not (zb0 - za1 < SLAB and za0 - zb1 < SLAB):
                    continue
                if (min(ra[2], rb[2]) - max(ra[0], rb[0]) > _TOUCH
                        and min(ra[3], rb[3]) - max(ra[1], rb[1]) > _TOUCH):
                    return True
                if not shared:
                    # The gate compares two corridors sharing no room cell by cell on its
                    # CONFLICT_CELL grid, so pieces apart in plan but on one cell clash too.
                    a, b = cells(ra), cells(rb)
                    if a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]:
                        return True
        return False

    @staticmethod
    def _door_on_wall(cor: CorridorSpec, room: RoomSpec):
        """``(wall, along)``: the wall of ``room`` that ``cor``'s door is on
        (N, S, E or W) and the door's centre along it; None when ``cor``
        doesn't leave ``room`` or its door isn't on a wall line."""
        if cor.from_room == room.id:
            x, y = cor.from_x, cor.from_y
        elif cor.to_room == room.id:
            x, y = cor.to_x, cor.to_y
        else:
            return None
        inset, tol = 2.0, 0.5            # _wall_point's inset
        hx, hy = room.width / 2 - inset, room.depth / 2 - inset
        if abs(x - (room.center_x + hx)) < tol:
            return "E", y
        if abs(x - (room.center_x - hx)) < tol:
            return "W", y
        if abs(y - (room.center_y + hy)) < tol:
            return "N", x
        if abs(y - (room.center_y - hy)) < tol:
            return "S", x
        return None

    @classmethod
    def _doors_clash(cls, a: CorridorSpec, b: CorridorSpec, room: RoomSpec) -> bool:
        """Do ``a``'s and ``b``'s doors on one wall of ``room`` overlap, or
        stand closer than a pier of ``U_DOOR_MARGIN`` between them? Two doors
        at one point share the opening (facing corridors out of one wall)."""
        da, db = cls._door_on_wall(a, room), cls._door_on_wall(b, room)
        if da is None or db is None or da[0] != db[0]:
            return False
        gap = abs(da[1] - db[1])
        return 1e-6 < gap < (a.width + b.width) / 2 + U_DOOR_MARGIN

    def _shaft_clear(self, rooms: List[RoomSpec], edges: List[Tuple[int, int]],
                     k: int, m: int, shaft, shafts) -> bool:
        """Is a Bridge's shaft (``(slot, zlo, zhi)``) for corridor ``k`` over
        room ``m`` clear of every other room, every other corridor's planned
        pieces and the ``shafts`` already kept? Touching is clear."""
        (x0, y0, x1, y1), zlo, zhi = shaft
        tol = 1e-6

        def hits(rect, z0, z1) -> bool:
            return (min(x1, rect[2]) - max(x0, rect[0]) > _TOUCH
                    and min(y1, rect[3]) - max(y0, rect[1]) > _TOUCH
                    and z0 < zhi - tol and zlo < z1 - tol)

        for q, r in enumerate(rooms):
            if q == m:
                continue
            (rx0, ry0, _), (rx1, ry1, _) = r.bounds
            if hits((rx0, ry0, rx1, ry1), r.floor_z, r.floor_z + r.height):
                return False
        for q, e in enumerate(edges):
            if q == k:
                continue
            for rect, z0, z1, _pin in self._shape(rooms, *e).pieces:
                if hits(rect, z0, z1):
                    return False
        return not any(hits(rect, z0, z1) for rect, z0, z1 in shafts)

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
        width, height = self._corridor_dims(a, b)
        return CorridorSpec(id="", from_x=fx, from_y=fy, to_x=tx, to_y=ty,
                            from_z=a.floor_z, to_z=b.floor_z,
                            width=width, height=height,
                            steps=steps, from_room=a.id, to_room=b.id)

    def _u_cor(self, a: RoomSpec, b: RoomSpec, side: str, a_at: float = -1.0,
               b_at: float = 1.0) -> Optional[CorridorSpec]:
        """A stair on a U-route out of the walls of *a* and *b* facing *side*.
        ``a_at`` and ``b_at`` place each door along its wall, -1 to 1 in the
        direction from a to b: a's -1 and b's 1 are the ends away from the
        other room (the middle leg then runs the length of both), a's 1 and
        b's -1 the ends toward it (the middle leg stays clear of a corridor
        leaving the far part of that wall). None when a wall can't hold the
        door or the middle leg is too short to fold a Switchback."""
        width, height = self._corridor_dims(a, b)
        hw = width / 2
        inset = 2.0                      # as _wall_point
        exit_x = side in ("E", "W")
        sign = 1.0 if side in ("N", "E") else -1.0

        def wall(r: RoomSpec) -> float:
            if exit_x:
                return r.center_x + sign * (r.width / 2 - inset)
            return r.center_y + sign * (r.depth / 2 - inset)

        ta, tb = (a.center_y, b.center_y) if exit_x else (a.center_x, b.center_x)
        ha, hb = (a.depth / 2, b.depth / 2) if exit_x else (a.width / 2, b.width / 2)
        # A jittered layout keeps its stair doors U_CORNER_MARGIN off the wall's end.
        margin = U_CORNER_MARGIN if self._straight_doors else U_DOOR_MARGIN
        reach_a, reach_b = ha - hw - margin, hb - hw - margin
        if reach_a < 0 or reach_b < 0:
            return None
        sgn = 1.0 if tb >= ta else -1.0
        da = ta + sgn * reach_a * a_at
        db = tb + sgn * reach_b * b_at
        if abs(db - da) < 2 * hw + 2 * MIN_LANE:
            return None
        (fx, fy), (tx, ty) = (((wall(a), da), (wall(b), db)) if exit_x
                              else ((da, wall(a)), (db, wall(b))))
        return CorridorSpec(id="", from_x=fx, from_y=fy, to_x=tx, to_y=ty,
                            from_z=a.floor_z, to_z=b.floor_z,
                            width=width, height=height,
                            steps=AUTO_STAIRS, from_room=a.id, to_room=b.id,
                            side=side)

    def _stair_candidates(self, rooms: List[RoomSpec], i: int, j: int
                          ) -> List[CorridorSpec]:
        """The ways a stair between rooms i and j (on different Levels) may
        go, in the order tried: between their facing walls when the rooms
        stand a corridor apart on that axis (as separation leaves two rooms
        on one Level), then U-routes on the four sides, the two across the
        pair's offset first (the longest middle legs), each with its doors at
        the far ends of the walls, then the near end of one or both, then
        along the walls (``U_DOOR_STOPS``), so a stair the ends can't place
        still has a way past a room's corner or a corridor beside it."""
        a, b = rooms[i], rooms[j]
        out = []
        ex = self._exit_axis_x(a, b)
        sep = (abs(b.center_x - a.center_x) - (a.width + b.width) / 2 if ex
               else abs(b.center_y - a.center_y) - (a.depth + b.depth) / 2)
        if sep >= self._cw(a, b):
            out.append(self._facing_cor(a, b, AUTO_STAIRS))
        across_x = abs(b.center_x - a.center_x) >= abs(b.center_y - a.center_y)
        sides = ("N", "S", "E", "W") if across_x else ("E", "W", "N", "S")
        ends = [(-1.0, 1.0), (1.0, 1.0), (-1.0, -1.0), (1.0, -1.0)]
        along = [(p, q) for p in U_DOOR_STOPS for q in U_DOOR_STOPS
                 if abs(p) != 1.0 or abs(q) != 1.0]
        for a_at, b_at in ends + along:
            for side in sides:
                cor = self._u_cor(a, b, side, a_at, b_at)
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
            # A third room's band: the lowest floor and highest top of the legs over it.
            band = [math.inf, -math.inf]
            for p, ((x0, y0, x1, y1), zlo, zhi, _pin) in enumerate(pieces):
                if own and ((k == i and p == 0) or (k == j and p == n - 1)):
                    continue
                ox, oy = min(x1, rx1) - max(x0, rx0), min(y1, ry1) - max(y0, ry0)
                if not own and p < n and ox > _TOUCH and oy > _TOUCH:
                    band = [min(band[0], zlo), max(band[1], zhi)]
                gap = _TOUCH if own else -_ROOM_TOUCH
                if ox > gap and oy > gap and not self._z_clear(zlo, zhi, r):
                    blocked = k
                    break
            if (blocked is None and band[0] <= band[1] and not self._z_clear(*band, r)
                    and _centre_span(wps, r) > hw):
                # Legs over and under a room the centreline cuts through, each clear alone:
                # the gate judges the band of all the legs over such a room
                # (``analyzer.traverse.stacked_rooms``), so the route must clear that whole
                # band (hall length step 30, task 8: cave graph dramatic 18 at Hall length
                # 0.5, seed 1068169087, corr_10's U-route over room_11 at 116 and under it
                # at -190).
                blocked = k
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
            # Routes inside the Envelope's footprint first (step 7 task 19).
            inside = [s for s in shapes if self._in_envelope(s)]
            shape = None
            for pool in (inside, shapes):
                shape = (next((s for s in pool if s.blocked is None), None)
                         or next((s for s in pool if s.blocked not in (i, j)), None))
                if shape is not None:
                    break
            if shape is None and shapes:
                shape = shapes[0]
            if shape is None:
                shape = self._make_shape(rooms, i, j, self._facing_cor(a, b, AUTO_STAIRS))
                shape = shape._replace(blocked=i)
        self._shapes[key] = shape
        return shape

    def _in_envelope(self, shape: _Shape) -> bool:
        """Is every piece of ``shape`` (legs, bends, a Switchback's
        stairwell) inside the Envelope's footprint? True with no Envelope.
        Outdoors a stair route past it runs under the map's edge (step 7
        task 19): the other routes are tried first, and ``fits`` rejects a
        layout left with one."""
        env = self._envelope
        return env is None or all(env.covers(*p[0]) for p in shape.pieces)

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
                if shape.blocked is not None or not self._in_envelope(shape):
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

        The clearance between two tubes is the Slab, from the lower tube's
        top to the upper's floor (pieces run floor to top). The gate
        (``analyzer.traverse.corridor_conflicts``, design decision 16) wants
        a corridor height + 1 between the two floors, which that gives: it
        reads floors only (task 18)."""
        shared = set(ea) & set(eb)
        sa, sb = self._shape(rooms, *ea), self._shape(rooms, *eb)
        return self._pieces_clash(sa.pieces, sb.pieces, shared)

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
        across = self._straight_across(room, toward, exit_x)
        if across is None:
            across = self._bearing_across(room, toward, exit_x)
        if exit_x:
            # East/West wall
            x = room.center_x + (hw - inset) * (1 if dx >= 0 else -1)
            return x, room.center_y if across is None else across
        else:
            # North/South wall
            y = room.center_y + (hd - inset) * (1 if dy >= 0 else -1)
            return room.center_x if across is None else across, y

    def _straight_across(self, room: RoomSpec, toward: RoomSpec,
                         exit_x: bool) -> Optional[float]:
        """A jittered placement's door across the wall (winding control task
        8): the middle of the span two facing rooms share, when it holds the
        corridor and a quarter-width pier each side
        (``embed.STRAIGHT_NEED``), so the corridor runs straight; None (the
        wall's midpoint) otherwise, and always without jitter. The same for
        both ends, so both doors land on one line."""
        if not self._straight_doors or exit_x != self._exit_axis_x(toward, room):
            return None
        from .topology.embed import STRAIGHT_NEED
        # Only rooms apart across the wall (a stair's rooms overlap in plan:
        # its doors are planned with the stair).
        if exit_x:
            apart = abs(toward.center_x - room.center_x) - (room.width + toward.width) / 2
        else:
            apart = abs(toward.center_y - room.center_y) - (room.depth + toward.depth) / 2
        if apart <= 0:
            return None
        if exit_x:
            a0, a1 = room.center_y - room.depth / 2, room.center_y + room.depth / 2
            b0, b1 = toward.center_y - toward.depth / 2, toward.center_y + toward.depth / 2
        else:
            a0, a1 = room.center_x - room.width / 2, room.center_x + room.width / 2
            b0, b1 = toward.center_x - toward.width / 2, toward.center_x + toward.width / 2
        lo, hi = max(a0, b0), min(a1, b1)
        cw = self._cw(room, toward)
        if hi - lo < STRAIGHT_NEED * cw:
            return None
        if self._bearing_doors:
            # A bearing placement's doors keep off the walls' ends as its
            # bearing doors do (``embed.door_span``), or the stubs of two
            # corridors round a corner meet.
            from .topology.embed import door_span
            lo, hi = max(lo, door_span(a0, a1, cw)[0],
                         door_span(b0, b1, cw)[0]), \
                min(hi, door_span(a0, a1, cw)[1],
                    door_span(b0, b1, cw)[1])
            if hi < lo:
                return None
        return (lo + hi) / 2

    def _bearing_across(self, room: RoomSpec, toward: RoomSpec,
                        exit_x: bool) -> Optional[float]:
        """A bearing placement's door off a shared span (random placement task
        10): where the line between the two rooms' centres crosses the wall,
        kept ``embed.door_span`` in from the wall's ends, so a
        room met at an angle is met there and not at the wall's middle. None
        (the middle) without a bearing placement, or when the rooms aren't
        apart across the wall (a stair's are: its doors are planned with it)."""
        if not self._bearing_doors:
            return None
        if exit_x:
            apart = abs(toward.center_x - room.center_x) - (room.width + toward.width) / 2
        else:
            apart = abs(toward.center_y - room.center_y) - (room.depth + toward.depth) / 2
        if apart <= 0:
            return None
        from .topology.embed import bearing_door
        return bearing_door((room.center_x, room.center_y), (room.width / 2, room.depth / 2),
                            (toward.center_x, toward.center_y), exit_x, self._cw(room, toward))

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
