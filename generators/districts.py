"""
generators/districts.py
-----------------------
Districts (districts spec Requirement 1, umbrella Requirement 23): a larger
dungeon split into 2-3 areas, each its own connected part of the room graph,
joined to its neighbour by exactly one corridor, the Threshold.

The partition is the umbrella design's tree cut. Take the BFS tree of the room
graph from the zone entrance (adjacency sorted by room index, so the tree does
not depend on edge order) and cut ``k - 1`` of its edges. Each cut node roots a
new District holding its subtree minus the subtrees of deeper cuts, so every
District is connected in the tree. Tree edges, plus any edge whose two ends
share a District, are kept; every other cross-District edge is dropped, which
leaves the cut edges as the only links between Districts: the Thresholds.

With ``k == 1`` (the switch off, fewer than 8 rooms, or no cut meeting the
sizes) nothing is drawn from the rng and the edges come back unchanged, so a
one-District zone is byte-identical to one built before Districts existed.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

# Districts need this many rooms before the switch does anything (umbrella 23.1).
MIN_ROOMS = 8
# From this many rooms the count is 3 (umbrella 23.1).
THREE_DISTRICT_ROOMS = 14
# Cut score bonus, in rooms, when the cut corridor leaves a hub: a crossroads
# makes a natural chokepoint between two areas.
HUB_BONUS = 1.0

Edge = Tuple[int, int]


@dataclass
class Partition:
    """The result of :func:`partition_districts`.

    ``k`` is the resolved District count and ``requested`` the count asked
    for; they differ when no cut met the sizes (the caller notes it).
    ``assign[i]`` is room ``i``'s District id: 0 holds the zone entrance, the
    rest are numbered by how shallow their cut is. ``edges`` is the pruned
    edge list (input order and orientation kept). ``thresholds[d - 1]`` is
    District ``d``'s Threshold as ``(parent side, child side)``.
    """
    k: int
    requested: int
    assign: List[int]
    edges: List[Edge]
    thresholds: List[Edge] = field(default_factory=list)


def district_count(n: int, on: bool) -> int:
    """Umbrella 23.1's District count for ``n`` rooms: 1 when the switch is
    off or the zone is small, 2 for 8-13 rooms, 3 from 14."""
    if not on or n < MIN_ROOMS:
        return 1
    return 2 if n < THREE_DISTRICT_ROOMS else 3


def min_district_size(n: int, k: int) -> int:
    """The smallest a District may be: max(3, n // (k + 1)) (umbrella 23.2)."""
    return max(3, n // (k + 1))


def _bfs_tree(n: int, edges: Sequence[Edge], entrance: int):
    """BFS tree from ``entrance`` with adjacency sorted by room index:
    ``(parent, order, adj)``. The same walk as ``layout.gate_tree`` but
    independent of edge order (copied rather than imported: ``layout`` will
    import this module)."""
    adj: Dict[int, List[int]] = {i: [] for i in range(n)}
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    for i in adj:
        adj[i].sort()
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
    return parent, order, adj


def _assign(n: int, order: List[int], parent, cuts: Sequence[int]) -> List[int]:
    """Room -> the cut that owns it (its deepest cut ancestor, itself
    included), or -1 for the entrance's District. Rooms the entrance can't
    reach stay with the entrance."""
    cut_set = set(cuts)
    owner = [-1] * n
    for room in order:
        if room in cut_set:
            owner[room] = room
        elif parent[room] is not None:
            owner[room] = owner[parent[room]]
    return owner


def _sizes_ok(n: int, order, parent, cuts: Sequence[int], min_size: int) -> bool:
    owner = _assign(n, order, parent, cuts)
    counts: Dict[int, int] = {}
    for o in owner:
        counts[o] = counts.get(o, 0) + 1
    return len(counts) == len(cuts) + 1 and min(counts.values()) >= min_size


def _candidates(n, order, parent, cuts, remaining, min_size) -> List[int]:
    """Cut nodes that keep every District at ``min_size`` or more and still
    leave room for the ``remaining - 1`` cuts after them."""
    out = []
    for c in order[1:]:
        if c in cuts:
            continue
        nxt = cuts + [c]
        if not _sizes_ok(n, order, parent, nxt, min_size):
            continue
        if remaining > 1 and not _candidates(n, order, parent, nxt, remaining - 1, min_size):
            continue
        out.append(c)
    return out


def partition_districts(rooms: Sequence, edges: Sequence[Edge], entrance: int,
                        k: int, rng: random.Random) -> Partition:
    """Split the room graph into ``k`` Districts by cutting its BFS tree from
    ``entrance`` (districts design "Partition").

    Each cut is the candidate whose new District is closest to ``n / k``
    rooms, less :data:`HUB_BONUS` when it leaves a hub (degree >= 3), ties by
    ``rng.random()``. When no ``k``-way cut keeps every District at
    :func:`min_district_size` rooms, ``k`` drops until one does (``k = 1``
    always does); the rng is drawn from only once a ``k >= 2`` is settled.
    """
    n = len(rooms)
    requested = k
    if k <= 1 or n == 0:
        return Partition(k=1, requested=requested, assign=[0] * n, edges=list(edges))

    parent, order, adj = _bfs_tree(n, edges, entrance)

    resolved = 1
    for kk in range(min(k, n), 1, -1):
        if _candidates(n, order, parent, [], kk - 1, min_district_size(n, kk)):
            resolved = kk
            break
    if resolved == 1:
        return Partition(k=1, requested=requested, assign=[0] * n, edges=list(edges))

    k = resolved
    min_size = min_district_size(n, k)
    target = n / k
    cuts: List[int] = []
    for step in range(k - 1):
        best = None
        for c in _candidates(n, order, parent, cuts, k - 1 - step, min_size):
            owner = _assign(n, order, parent, cuts + [c])
            size = owner.count(c)
            score = abs(size - target)
            if len(adj[parent[c]]) >= 3:
                score -= HUB_BONUS
            key = (score, rng.random())
            if best is None or key < best[0]:
                best = (key, c)
        cuts.append(best[1])

    # District ids: 0 for the entrance's, then by cut depth (BFS order).
    pos = {room: i for i, room in enumerate(order)}
    cuts.sort(key=lambda c: pos[c])
    dist_id = {c: i + 1 for i, c in enumerate(cuts)}
    owner = _assign(n, order, parent, cuts)
    assign = [0 if o == -1 else dist_id[o] for o in owner]
    thresholds = [(parent[c], c) for c in cuts]

    cut_edges = {frozenset(t) for t in thresholds}
    kept: List[Edge] = []
    seen_cut = set()
    for a, b in edges:
        e = frozenset((a, b))
        if e in cut_edges:
            if e in seen_cut:
                continue           # a duplicate of a Threshold would be a second link
            seen_cut.add(e)
            kept.append((a, b))
        elif assign[a] == assign[b]:
            kept.append((a, b))
    return Partition(k=k, requested=requested, assign=assign, edges=kept,
                     thresholds=thresholds)


def district_entrances(part: Partition, entrance: int) -> List[int]:
    """Each District's entrance: the zone entrance for District 0, else the
    child side of its Threshold (the only way in, umbrella 23.4)."""
    return [entrance] + [child for _, child in part.thresholds]


def district_climaxes(part: Partition, edges: Sequence[Edge], entrance: int) -> List[int]:
    """One climax per District (umbrella 23.4): the room farthest by
    in-District BFS from the District entrance, ties to the lowest index.
    ``edges`` is normally ``part.edges``; only edges inside a District count."""
    n = len(part.assign)
    adj: Dict[int, List[int]] = {i: [] for i in range(n)}
    for a, b in edges:
        if part.assign[a] == part.assign[b]:
            adj[a].append(b)
            adj[b].append(a)
    climaxes = []
    for start in district_entrances(part, entrance):
        dist = {start: 0}
        q = deque([start])
        while q:
            cur = q.popleft()
            for nxt in adj[cur]:
                if nxt not in dist:
                    dist[nxt] = dist[cur] + 1
                    q.append(nxt)
        climaxes.append(max(dist, key=lambda i: (dist[i], -i)))
    return climaxes
