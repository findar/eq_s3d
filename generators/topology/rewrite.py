"""
generators/topology/rewrite.py
------------------------------
Growing a Topology_Graph by rewrite rules (roadmap step 6, Requirement 4;
design "Growing the graph").

Three parts, each usable on its own:

- :func:`find_matches` lists every placement of a rule's match in a graph.
- :func:`apply_rule` rewrites one placement in place.
- :func:`grow` runs a rule set's recipe from its start graph to exactly n
  rooms, checking the invariants after every application, and records every
  application.

Same discipline as the wilderness rewrite (apply, check, commit, capped), but
no code is shared with ``generators/wilderness/rewrite.py`` (design).

Decisions the design leaves open (task 4):

- **Context.** ``when`` conditions read a :class:`BuildContext` (or any
  mapping with the same keys). :func:`grow` fills ``room_count`` with n when
  the context leaves it unset. With no context, a rule with a ``when`` never
  matches (a missing key fails its condition).
- **Matching.** A placement maps each match node, in match order, to a
  distinct graph node of the same kind. The placement is *induced*: the graph
  edges among the matched nodes are exactly the match edges, so no edge
  between two matched nodes is left for reattach to guess about. A match edge
  with ``rel = "any"`` (the default) accepts any graph relation; any other
  ``rel`` must equal the graph edge's relation read in the same direction
  (``{a = "x", b = "y", rel = "above"}`` needs y's node above x's). A match
  edge's tags must all be on the graph edge. ``match_hops`` distances are
  hop counts over the whole graph, Areas included. Placements come back
  sorted, so a symmetric match (two chambers) is listed once per order.
- **Applying.** A replacement node whose id is a match id keeps that graph
  node's id; if its kind is unchanged it also keeps the graph node's size,
  shape and district (a rule that joins two chambers doesn't resize them), and
  a kind change takes the replacement's attributes. Other replacement nodes
  get fresh ids (``n000``, ``n001``, ... from a counter, skipping ids in use).
- **Reattach.** A removed node's outside edges (to nodes outside the match),
  sorted by the outside neighbour's id, are cut into contiguous chunks, one per
  target in the listed order, earlier targets taking the larger chunks: edge i
  of E goes to target ``i * k // E`` of k. Each moved edge keeps its relation
  and tags, read from the new end (``rel`` still says where the outside node
  sits). If two moved edges would land on one node pair, the application is
  illegal and rejected.
- **Degree.** Every node, Areas included, has at most 4 neighbours, and Areas
  count toward a room's degree: an Area ends as at least one room that keeps
  every edge it has (``finish`` moves them all to one room).
- **Loops.** Every edge that lies on some cycle lies on a cycle of 4 to 5
  nodes (shortest cycle through the edge = BFS distance between its ends
  without it, plus one). Areas count as nodes: each becomes at least one
  room, so a loop through an Area can only grow, and the check rejects the
  application that would take it past 5. A ring of three is rejected even
  through an Area (task 18): corridors leave a room through the wall facing
  the other room, so a triangle puts two corridors on one wall and the build
  drops one of them. On the finished graph (no Areas) it reads in rooms.
  Checked over the whole graph after each application.
- **Budgets.** A stage's budget is round-half-up(share x n) plus what earlier
  stages left unspent when they ran out of matches. It is spent by growth in
  rooms + Areas (an Area is a room to come), so ``lengthen`` spends 1 and
  ``finish`` spends 0. The rest stage runs until the graph has n rooms and no
  Area; if no rule applies before that it raises :class:`TopologyError`.
- **Reaching n.** A result is rejected when rooms + Areas would pass n (each
  Area still needs a room), and when it takes away the last Area while short
  of n rooms if every growth rule left in the recipe needs an Area to match.
- **Picking.** Each step picks a rule by its ``apply`` weight among the
  stage's rules that have a legal placement, then a placement uniformly among
  that rule's legal ones. Done lazily and exactly: rules in name order, a
  weighted draw, the rule's sorted placements shuffled by the rng and tried
  in turn; a rule with no legal placement drops out and the draw repeats.
- **Step cap.** ``cap_factor x n`` applications per stage; needing another
  step past it raises :class:`TopologyError` naming the set, stage and cap.
- **Small n.** When the start graph has more nodes than n, it shrinks: the
  entrance, then the other nodes with rooms before Areas, farthest from the
  entrance first (ties by id), up to n. Edges among kept nodes stay; each
  other component joins the entrance by a new ``any`` edge to its node
  nearest the entrance. n = 1 is the entrance alone; for a start graph
  ``e - Area - deep`` n = 2 is ``e - deep``.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field, replace as dc_replace
from typing import (
    Any, Callable, Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple, Union,
)

from generators.topology.graph import ENTRANCE, Node, TopologyGraph
from generators.topology.ruleset import WHEN_KEYS, Rule, RuleSet, Stage

MAX_DEGREE = 4
LOOP_MIN = 4
LOOP_MAX = 5
CAP_FACTOR = 8


class TopologyError(RuntimeError):
    """Growing stopped: the step cap was reached, or the rest stage got stuck."""

    def __init__(self, set_name: str, stage: str, message: str, cap: Optional[int] = None):
        self.set_name = set_name
        self.stage = stage
        self.cap = cap
        super().__init__(f"rule set {set_name!r}, stage {stage!r}: {message}")


class RewriteConflict(ValueError):
    """Applying a placement would put two edges on one node pair."""


@dataclass(frozen=True)
class BuildContext:
    """What ``when`` conditions read. Unset keys fail every condition on them."""

    theme: Optional[str] = None
    race: Optional[str] = None
    race_scale: Optional[float] = None
    zone_type: Optional[str] = None
    room_count: Optional[int] = None

    def get(self, key: str, default: Any = None) -> Any:
        if key not in WHEN_KEYS:
            return default
        v = getattr(self, key)
        return default if v is None else v


Context = Union[BuildContext, Mapping[str, Any]]


class Application(NamedTuple):
    """One applied rule: the stage, the rule, the graph nodes it touched
    (matched nodes in match order, then new nodes in replacement order)."""

    stage: str
    rule: str
    nodes: Tuple[str, ...]


@dataclass
class GrowResult:
    graph: TopologyGraph
    applied: List[Application]
    stats: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def find_matches(graph: TopologyGraph, rule: Rule,
                 context: Optional[Context] = None) -> List[Tuple[str, ...]]:
    """Every placement of ``rule.match`` in ``graph``, sorted.

    A placement is a tuple of graph node ids in match order. Empty when the
    rule's ``when`` doesn't hold for ``context``.
    """
    if not rule.when_holds(context if context is not None else {}):
        return []
    match = rule.match
    ids = graph.node_ids()
    candidates = [[g for g in ids if graph.node(g).kind == m.kind] for m in match]
    pattern = {frozenset((e.a, e.b)): e for e in rule.match_edges}
    hops = {frozenset((h.a, h.b)): h for h in rule.match_hops}
    dist_cache: Dict[str, Dict[str, int]] = {}

    def fits(i: int, gid: str, partial: Sequence[str]) -> bool:
        mi = match[i].id
        for j, gj in enumerate(partial):
            mj = match[j].id
            pair = frozenset((mi, mj))
            pe = pattern.get(pair)
            ge = graph.edge(gj, gid)                     # read from gj
            if pe is None:
                if ge is not None:
                    return False                         # induced: no extra edges
            else:
                if ge is None:
                    return False
                want = pe if pe.a == mj else pe.reversed()   # read from mj
                if want.rel != "any" and ge.rel != want.rel:
                    return False
                if not want.tags <= ge.tags:
                    return False
            h = hops.get(pair)
            if h is not None:
                if gj not in dist_cache:
                    dist_cache[gj] = graph.distances(gj)
                d = dist_cache[gj].get(gid)
                if d is None or not h.lo <= d <= h.hi:
                    return False
        return True

    out: List[Tuple[str, ...]] = []

    def extend(partial: List[str]) -> None:
        i = len(partial)
        if i == len(match):
            out.append(tuple(partial))
            return
        for gid in candidates[i]:
            if gid in partial or not fits(i, gid, partial):
                continue
            partial.append(gid)
            extend(partial)
            partial.pop()

    extend([])
    return out


# ---------------------------------------------------------------------------
# Applying
# ---------------------------------------------------------------------------

def fresh_ids(graph: TopologyGraph, start: int = 0) -> Callable[[], str]:
    """An id source: ``n000``, ``n001``, ... skipping ids already in ``graph``."""
    state = [start]

    def nxt() -> str:
        while True:
            gid = f"n{state[0]:03d}"
            state[0] += 1
            if gid not in graph:
                return gid

    nxt.state = state          # type: ignore[attr-defined]  (the driver reads the counter)
    return nxt


def apply_rule(graph: TopologyGraph, rule: Rule, placement: Sequence[str],
               fresh: Optional[Callable[[], str]] = None) -> Tuple[str, ...]:
    """Rewrite ``placement`` (from :func:`find_matches`) in place.

    Returns the touched node ids: the matched ids in match order, then the
    new ids in replacement order. Raises :class:`RewriteConflict` if two
    moved edges would join the same pair (``graph`` is then half-rewritten;
    the driver works on a copy).
    """
    if fresh is None:
        fresh = fresh_ids(graph)
    m2g = {m.id: g for m, g in zip(rule.match, placement)}
    matched = set(placement)
    old = {g: graph.node(g) for g in placement}
    outside = {m.id: [e for e in graph.incident(m2g[m.id]) if e.b not in matched]
               for m in rule.match}
    for g in placement:
        graph.remove_node(g)

    r2g: Dict[str, str] = {}
    new_ids: List[str] = []
    for rn in rule.replace:
        if rn.id in m2g:
            gid = m2g[rn.id]
            prev = old[gid]
            node = prev if prev.kind == rn.kind else Node(gid, rn.kind, rn.size, rn.shape,
                                                          rn.district)
        else:
            gid = fresh()
            new_ids.append(gid)
            node = Node(gid, rn.kind, rn.size, rn.shape, rn.district)
        graph.add_node(node)
        r2g[rn.id] = gid
    for e in rule.edges:
        graph.add_edge(r2g[e.a], r2g[e.b], e.rel, e.tags)

    targets = rule.reattach_map()
    for m in rule.match:
        moved = outside[m.id]
        tl = targets[m.id]
        for i, e in enumerate(moved):
            t = r2g[tl[i * len(tl) // len(moved)]]
            if graph.has_edge(t, e.b):
                raise RewriteConflict(f"{rule.name}: two edges {t!r}-{e.b!r}")
            graph.add_edge(t, e.b, e.rel, e.tags)
    return tuple(placement) + tuple(new_ids)


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------

def shortest_cycle_through(graph: TopologyGraph, a: str, b: str) -> Optional[int]:
    """Nodes on the shortest cycle through edge a-b, or None for a bridge."""
    dist = {a: 0}
    queue = deque([a])
    while queue:
        u = queue.popleft()
        for v in graph.neighbours(u):
            if v in dist or (u == a and v == b):
                continue
            dist[v] = dist[u] + 1
            if v == b:
                return dist[v] + 1
            queue.append(v)
    return None


def invariant_violation(graph: TopologyGraph) -> Optional[str]:
    """Why ``graph`` breaks Req 4.2 (connected, degree <= 4, loops of 4-5), or None."""
    if not graph.connected():
        return "not connected"
    for n in graph.node_ids():
        if graph.degree(n) > MAX_DEGREE:
            return f"{n} has {graph.degree(n)} connections (max {MAX_DEGREE})"
    for e in graph.edges():
        c = shortest_cycle_through(graph, e.a, e.b)
        if c is not None and c > LOOP_MAX:
            return f"edge {e.a}-{e.b} is on a loop of {c} (max {LOOP_MAX})"
        if c is not None and c < LOOP_MIN:
            return f"edge {e.a}-{e.b} is on a loop of {c} (min {LOOP_MIN})"
    return None


# ---------------------------------------------------------------------------
# The driver
# ---------------------------------------------------------------------------

def start_graph_for(rule_set: RuleSet, n: int) -> TopologyGraph:
    """The set's start graph, shrunk to n nodes when it has more (module doc)."""
    g = rule_set.start_graph()
    if len(g) <= n:
        return g
    entrance = next(x.id for x in g.rooms() if x.kind == ENTRANCE)
    dist = g.distances(entrance)
    far = len(g) + 1
    others = sorted((x for x in g.nodes() if x.id != entrance),
                    key=lambda x: (not x.is_room, -dist.get(x.id, -1), x.id))
    keep = {entrance} | {x.id for x in others[:n - 1]}
    out = TopologyGraph([g.node(i) for i in sorted(keep)],
                        [e for e in g.edges() if e.a in keep and e.b in keep])
    for comp in out.components():
        if entrance not in comp:
            target = min(comp, key=lambda i: (dist.get(i, far), i))
            out.add_edge(entrance, target)
    return out


def _context(context: Optional[Context], n: int) -> Context:
    if context is None:
        return BuildContext(room_count=n)
    if isinstance(context, BuildContext):
        return context if context.room_count is not None else dc_replace(context, room_count=n)
    ctx = dict(context)
    ctx.setdefault("room_count", n)
    return ctx


def _growth(rule: Rule) -> int:
    """Change in rooms + Areas."""
    return len(rule.replace) - len(rule.match)


def _needs_area_from(rule_set: RuleSet, ctx: Context) -> List[bool]:
    """Per stage index: every growth rule of this stage and later ones needs an Area."""
    out = []
    for i in range(len(rule_set.recipe)):
        names = {r for s in rule_set.recipe[i:] for r in s.apply}
        free = any(_growth(rule_set.rules[r]) > 0 and rule_set.rules[r].when_holds(ctx)
                   and all(m.is_room for m in rule_set.rules[r].match) for r in names)
        out.append(not free)
    return out


def grow(rule_set: RuleSet, room_count: int, rng: Union[random.Random, int, None],
         context: Optional[Context] = None, *, cap_factor: int = CAP_FACTOR) -> GrowResult:
    """Grow a graph of exactly ``room_count`` rooms by ``rule_set``'s recipe.

    ``rng`` is a ``random.Random`` (or a seed for one). Raises
    :class:`TopologyError` when a stage reaches ``cap_factor x n`` steps or
    the rest stage can't finish.
    """
    n = room_count
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError(f"room_count must be a whole number of at least 1, got {n!r}")
    if not isinstance(rng, random.Random):
        rng = random.Random(rng)
    ctx = _context(context, n)
    cap = cap_factor * n
    graph = start_graph_for(rule_set, n)
    counter = 0
    applied: List[Application] = []
    stage_stats: List[Dict[str, Any]] = []
    needs_area = _needs_area_from(rule_set, ctx)
    carry = 0

    for si, stage in enumerate(rule_set.recipe):
        rules = [(name, rule_set.rules[name], float(w)) for name, w in sorted(stage.apply.items())
                 if rule_set.rules[name].when_holds(ctx)]
        at_start = len(graph)
        budget = n - at_start if stage.is_rest else int(stage.share * n + 0.5) + carry
        steps = rejected = 0
        while True:
            spent = len(graph) - at_start
            if stage.is_rest:
                if len(graph) == n and not graph.areas():
                    ended = "done"
                    break
            elif spent >= budget:
                ended = "budget"
                break
            if steps >= cap:
                raise TopologyError(rule_set.name, stage.name,
                                    f"reached the step cap of {cap} ({cap_factor} x {n} rooms) "
                                    f"with {spent} of a budget of {budget} spent", cap)
            pick, r = _pick(graph, rules, rng, n, ctx, needs_area[si], counter)
            rejected += r
            if pick is None:
                if stage.is_rest:
                    raise TopologyError(
                        rule_set.name, stage.name,
                        f"no rule applies with {len(graph.rooms())} rooms and "
                        f"{len(graph.areas())} Areas; {n} rooms and no Area needed")
                ended = "no match"
                break
            graph, name, touched, counter = pick
            applied.append(Application(stage.name, name, touched))
            steps += 1
        spent = len(graph) - at_start
        carry = 0 if stage.is_rest else max(0, budget - spent)
        stage_stats.append({"stage": stage.name, "budget": budget, "spent": spent,
                            "steps": steps, "rejected": rejected, "ended": ended})

    stats = {"rooms": len(graph.rooms()), "stages": stage_stats,
             "rejected": sum(s["rejected"] for s in stage_stats),
             "steps": sum(s["steps"] for s in stage_stats)}
    return GrowResult(graph, applied, stats)


def _pick(graph: TopologyGraph, rules: Sequence[Tuple[str, Rule, float]], rng: random.Random,
          n: int, ctx: Context, needs_area: bool, counter: int):
    """One legal application, or None; also the number of rejected placements."""
    live = []
    for name, rule, w in rules:
        if len(graph) + _growth(rule) > n:
            continue                                   # can't reach exactly n any more
        ms = find_matches(graph, rule, ctx)
        if ms:
            live.append((name, rule, w, ms))
    rejected = 0
    had_area = bool(graph.areas())
    while live:
        x = rng.random() * sum(w for _, _, w, _ in live)
        idx = len(live) - 1
        for i, (_, _, w, _) in enumerate(live):
            if x < w:
                idx = i
                break
            x -= w
        name, rule, _, ms = live[idx]
        order = list(ms)
        rng.shuffle(order)
        for placement in order:
            g2 = graph.copy()
            fresh = fresh_ids(g2, counter)
            try:
                touched = apply_rule(g2, rule, placement, fresh)
            except RewriteConflict:
                rejected += 1
                continue
            if invariant_violation(g2) is not None or (
                    needs_area and had_area and not g2.areas() and len(g2) < n):
                rejected += 1
                continue
            return (g2, name, touched, fresh.state[0]), rejected   # type: ignore[attr-defined]
        del live[idx]
    return None, rejected


__all__ = [
    "MAX_DEGREE", "LOOP_MIN", "LOOP_MAX", "CAP_FACTOR",
    "TopologyError", "RewriteConflict", "BuildContext", "Application", "GrowResult",
    "find_matches", "apply_rule", "fresh_ids", "shortest_cycle_through",
    "invariant_violation", "start_graph_for", "grow",
]
