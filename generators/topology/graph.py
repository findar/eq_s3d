"""
generators/topology/graph.py
----------------------------
The Topology_Graph: an abstract room graph with no coordinates (roadmap step 6,
design "Rule-set files" and "Growing the graph").

A node has a stable id, a ``kind`` (the placeholder ``Area`` or a room kind),
and, for rooms, a Size_Class, plus ``shape`` (``rect`` only in step 6) and a
``district`` label. An edge is undirected for connectivity but carries a
Vertical_Relation that reads in a direction: ``Edge(a, b, rel="above")`` means
"b is above a". The graph stores each edge once under its sorted id pair and
flips ``above``/``below`` when it has to swap the ends, so every accessor can
hand the edge back oriented from whichever end the caller asks from.

Everything iterates in sorted id order, so nothing that reads the graph sees
set or dict order (the rewrite driver's choices must not depend on it).

The shape measures are the survey's (Req 1.1): dead-end share, cycle rank,
deep-end distance and the Size_Class mix. They count room nodes only.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

#: The placeholder kind rules expand. Every other kind is a room.
AREA = "Area"
#: The room kind the shape measures and placement start from.
ENTRANCE = "entrance"
ROOM_KINDS: Tuple[str, ...] = ("entrance", "chamber", "passage", "hub", "lair", "hall", "deep")
#: Kinds every set knows; a set may declare more in ``[set] kinds``.
BASE_KINDS: Tuple[str, ...] = (AREA,) + ROOM_KINDS
SIZE_CLASSES: Tuple[str, ...] = ("tiny", "small", "medium", "large", "huge")
RELATIONS: Tuple[str, ...] = ("above", "below", "level", "any")
TAGS: Tuple[str, ...] = ("threshold", "bridge")
SHAPES: Tuple[str, ...] = ("rect",)

_FLIP = {"above": "below", "below": "above", "level": "level", "any": "any"}


@dataclass(frozen=True)
class Node:
    """One node. ``size`` is None on ``Area`` and required on rooms."""

    id: str
    kind: str
    size: Optional[str] = None
    shape: str = "rect"
    district: int = 0

    @property
    def is_room(self) -> bool:
        return self.kind != AREA


@dataclass(frozen=True)
class Edge:
    """An edge read from ``a``: ``rel`` says where ``b`` sits relative to ``a``."""

    a: str
    b: str
    rel: str = "any"
    tags: FrozenSet[str] = field(default_factory=frozenset)

    def reversed(self) -> "Edge":
        """The same edge read from ``b`` (``above`` and ``below`` swap)."""
        return Edge(self.b, self.a, _FLIP[self.rel], self.tags)

    def other(self, node_id: str) -> str:
        return self.b if node_id == self.a else self.a


class TopologyGraph:
    """A small undirected room graph; at most one edge per node pair, no self-loops."""

    def __init__(self, nodes: Iterable[Node] = (), edges: Iterable[Edge] = ()):
        self._nodes: Dict[str, Node] = {}
        self._adj: Dict[str, Set[str]] = {}
        self._edges: Dict[Tuple[str, str], Edge] = {}   # key sorted, edge stored with a < b
        for n in nodes:
            self.add_node(n)
        for e in edges:
            self.add_edge(e.a, e.b, e.rel, e.tags)

    # -- nodes ---------------------------------------------------------------

    def add_node(self, node: Node) -> None:
        if node.id in self._nodes:
            raise ValueError(f"node {node.id!r} already in the graph")
        self._nodes[node.id] = node
        self._adj[node.id] = set()

    def replace_node(self, node: Node) -> None:
        """Change an existing node's attributes; its edges stay."""
        if node.id not in self._nodes:
            raise KeyError(node.id)
        self._nodes[node.id] = node

    def remove_node(self, node_id: str) -> List[Edge]:
        """Remove a node and its edges; returns those edges read from the node."""
        removed = self.incident(node_id)
        for e in removed:
            self.remove_edge(e.a, e.b)
        del self._nodes[node_id]
        del self._adj[node_id]
        return removed

    def node(self, node_id: str) -> Node:
        return self._nodes[node_id]

    def __contains__(self, node_id: object) -> bool:
        return node_id in self._nodes

    def __len__(self) -> int:
        return len(self._nodes)

    def node_ids(self) -> List[str]:
        return sorted(self._nodes)

    def nodes(self) -> List[Node]:
        return [self._nodes[i] for i in sorted(self._nodes)]

    def rooms(self) -> List[Node]:
        return [n for n in self.nodes() if n.is_room]

    def areas(self) -> List[Node]:
        return [n for n in self.nodes() if not n.is_room]

    # -- edges ---------------------------------------------------------------

    def add_edge(self, a: str, b: str, rel: str = "any",
                 tags: Iterable[str] = ()) -> Edge:
        if a == b:
            raise ValueError(f"self-loop on {a!r}")
        for n in (a, b):
            if n not in self._nodes:
                raise KeyError(n)
        key = _key(a, b)
        if key in self._edges:
            raise ValueError(f"edge {a!r}-{b!r} already in the graph")
        if rel not in _FLIP:
            raise ValueError(f"unknown relation {rel!r}")
        e = Edge(a, b, rel, frozenset(tags))
        self._edges[key] = e if a < b else e.reversed()
        self._adj[a].add(b)
        self._adj[b].add(a)
        return e

    def remove_edge(self, a: str, b: str) -> Edge:
        """Remove the a-b edge; returns it read from ``a``."""
        e = self.edge(a, b)
        if e is None:
            raise KeyError((a, b))
        del self._edges[_key(a, b)]
        self._adj[a].discard(b)
        self._adj[b].discard(a)
        return e

    def has_edge(self, a: str, b: str) -> bool:
        return _key(a, b) in self._edges

    def edge(self, a: str, b: str) -> Optional[Edge]:
        """The a-b edge read from ``a``, or None."""
        e = self._edges.get(_key(a, b))
        if e is None:
            return None
        return e if e.a == a else e.reversed()

    def edges(self) -> List[Edge]:
        """Every edge once, stored orientation (``a < b``), sorted."""
        return [self._edges[k] for k in sorted(self._edges)]

    def incident(self, node_id: str) -> List[Edge]:
        """The node's edges read from it, sorted by the other end."""
        return [self.edge(node_id, m) for m in sorted(self._adj[node_id])]

    def neighbours(self, node_id: str) -> List[str]:
        return sorted(self._adj[node_id])

    def degree(self, node_id: str) -> int:
        return len(self._adj[node_id])

    # -- structure -----------------------------------------------------------

    def copy(self) -> "TopologyGraph":
        g = TopologyGraph()
        g._nodes = dict(self._nodes)
        g._adj = {k: set(v) for k, v in self._adj.items()}
        g._edges = dict(self._edges)
        return g

    def distances(self, source: str, rooms_only: bool = False) -> Dict[str, int]:
        """Hop counts from ``source`` by breadth-first search."""
        dist = {source: 0}
        queue = deque([source])
        while queue:
            u = queue.popleft()
            for v in sorted(self._adj[u]):
                if v in dist or (rooms_only and not self._nodes[v].is_room):
                    continue
                dist[v] = dist[u] + 1
                queue.append(v)
        return dist

    def components(self, rooms_only: bool = False) -> List[List[str]]:
        seen: Set[str] = set()
        out: List[List[str]] = []
        for n in self.node_ids():
            if n in seen or (rooms_only and not self._nodes[n].is_room):
                continue
            comp = sorted(self.distances(n, rooms_only))
            seen.update(comp)
            out.append(comp)
        return out

    def connected(self) -> bool:
        return len(self.components()) <= 1

    # -- shape measures (room nodes only) ------------------------------------

    def _room_degree(self, node_id: str) -> int:
        return sum(1 for m in self._adj[node_id] if self._nodes[m].is_room)

    def dead_end_share(self) -> float:
        """Rooms with exactly one room neighbour, over the room count."""
        rooms = self.rooms()
        if not rooms:
            return 0.0
        return sum(1 for r in rooms if self._room_degree(r.id) == 1) / len(rooms)

    def cycle_rank(self) -> int:
        """E - N + C over room nodes (E - N + 1 for a connected graph)."""
        rooms = self.rooms()
        if not rooms:
            return 0
        e = sum(1 for x in self.edges()
                if self._nodes[x.a].is_room and self._nodes[x.b].is_room)
        return e - len(rooms) + len(self.components(rooms_only=True))

    def deep_end_distance(self) -> float:
        """Longest shortest path (hops) from the entrance, over the room count.

        Uses the first ``entrance`` node by id; raises ValueError if none.
        """
        entrances = [r.id for r in self.rooms() if r.kind == ENTRANCE]
        if not entrances:
            raise ValueError("deep-end distance needs an 'entrance' node")
        dist = self.distances(entrances[0], rooms_only=True)
        return max(dist.values()) / len(self.rooms())

    def size_mix(self) -> Dict[str, float]:
        """Share of rooms per Size_Class (every class listed, in class order)."""
        rooms = self.rooms()
        mix = {c: 0.0 for c in SIZE_CLASSES}
        for r in rooms:
            if r.size in mix:
                mix[r.size] += 1
        return {c: (v / len(rooms) if rooms else 0.0) for c, v in mix.items()}


def _key(a: str, b: str) -> Tuple[str, str]:
    return (a, b) if a < b else (b, a)


__all__ = [
    "AREA", "ENTRANCE", "ROOM_KINDS", "BASE_KINDS", "SIZE_CLASSES", "RELATIONS",
    "TAGS", "SHAPES", "Node", "Edge", "TopologyGraph",
]
