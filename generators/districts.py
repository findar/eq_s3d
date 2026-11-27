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

An ``intrusion`` zone (district races Req 6) lifts that rule for each
Threshold's pair of Districts: up to ``links`` of the graph's edges between the
two are kept, the Threshold and the rest as **breaches**, where the intruder
broke into its host. The intruder is the Threshold's child side (the District
farther from the zone entrance, so the higher id): it came later and dug in.

With ``k == 1`` (the switch off, fewer than 8 rooms, or no cut meeting the
sizes) nothing is drawn from the rng and the edges come back unchanged, so a
one-District zone is byte-identical to one built before Districts existed.
"""

from __future__ import annotations

import itertools
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from . import semantics
from .zone_spec import DistrictSpec

# Districts need this many rooms before the switch does anything (umbrella 23.1).
MIN_ROOMS = 8
# From this many rooms the count is 3 (umbrella 23.1).
THREE_DISTRICT_ROOMS = 14
# Cut score bonus, in rooms, when the cut corridor leaves a hub: a crossroads
# makes a natural chokepoint between two areas.
HUB_BONUS = 1.0
#: An intrusion pair's links at most, its Threshold included (district races
#: task 1, archive decision 2: 13 stock zones mixing built and cave parts join
#: them by 3, the median).
INTRUSION_LINKS = 3

Edge = Tuple[int, int]


@dataclass
class Partition:
    """The result of :func:`partition_districts`.

    ``k`` is the resolved District count and ``requested`` the count asked
    for; they differ when no cut met the sizes (the caller notes it).
    ``assign[i]`` is room ``i``'s District id: 0 holds the zone entrance, the
    rest are numbered by how shallow their cut is. ``edges`` is the pruned
    edge list (input order and orientation kept). ``thresholds[d - 1]`` is
    District ``d``'s Threshold as ``(parent side, child side)``. ``breaches``
    (an intrusion zone) are the other kept edges between a Threshold's two
    Districts, as ``(host side, intruder side)``.
    """
    k: int
    requested: int
    assign: List[int]
    edges: List[Edge]
    thresholds: List[Edge] = field(default_factory=list)
    breaches: List[Edge] = field(default_factory=list)


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
                        k: int, rng: random.Random, links: int = 1) -> Partition:
    """Split the room graph into ``k`` Districts by cutting its BFS tree from
    ``entrance`` (districts design "Partition").

    Each cut is the candidate whose new District is closest to ``n / k``
    rooms, less :data:`HUB_BONUS` when it leaves a hub (degree >= 3), ties by
    ``rng.random()``. When no ``k``-way cut keeps every District at
    :func:`min_district_size` rooms, ``k`` drops until one does (``k = 1``
    always does); the rng is drawn from only once a ``k >= 2`` is settled.

    *links* over 1 (an ``intrusion`` zone, :data:`INTRUSION_LINKS`) keeps up
    to that many edges between each Threshold's two Districts
    (:func:`pick_breaches`); nothing more is drawn from the rng.
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
    breaches: List[Edge] = []
    if links > 1:
        breaches = pick_breaches(assign, edges, thresholds, links)
        chosen = {frozenset(e) for e in breaches}
        kept = [e for e in edges if frozenset(e) in cut_edges or frozenset(e) in chosen
                or assign[e[0]] == assign[e[1]]]
        # One copy of each cross edge (the first in input order).
        seen_cross: set = set()
        out: List[Edge] = []
        for a, b in kept:
            e = frozenset((a, b))
            if assign[a] != assign[b]:
                if e in seen_cross:
                    continue
                seen_cross.add(e)
            out.append((a, b))
        kept = out
    return Partition(k=k, requested=requested, assign=assign, edges=kept,
                     thresholds=thresholds, breaches=breaches)


def pick_breaches(assign: Sequence[int], edges: Sequence[Edge], thresholds: Sequence[Edge],
                  links: int) -> List[Edge]:
    """An intrusion zone's breaches: for each Threshold, up to ``links - 1`` more of
    the graph's edges between its two Districts, as ``(host side, intruder side)``.
    The host is the Threshold's parent side; the intruder its child side. Edges
    whose two rooms are on no link of that pair yet come first (the intruder
    breaks in at several places), then the rest; each group in input order.
    Nothing is drawn from any rng."""
    out: List[Edge] = []
    cut = {frozenset(t) for t in thresholds}
    for p, c in thresholds:
        host, intruder = assign[p], assign[c]
        cands: List[Edge] = []
        seen = set()
        for a, b in edges:
            e = frozenset((a, b))
            if e in cut or e in seen or a == b:
                continue
            if {assign[a], assign[b]} != {host, intruder}:
                continue
            seen.add(e)
            cands.append((a, b) if assign[a] == host else (b, a))
        used = {p, c}
        mine: List[Edge] = []
        for fresh in (True, False):
            for h, t in cands:
                if len(mine) >= links - 1:
                    break
                if (h, t) in mine:
                    continue
                if fresh and (h in used or t in used):
                    continue
                mine.append((h, t))
                used |= {h, t}
        out.extend(mine)
    return out


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


# ---------------------------------------------------------------------------
# Purposes (districts spec Requirement 2, umbrella 23.8, 23.10-23.12)
# ---------------------------------------------------------------------------

RELATIONSHIPS: Tuple[str, ...] = ("sequential", "factional", "abandoned_vs_active", "intrusion")
INTRUSION = "intrusion"
DEFAULT_RELATIONSHIP = "sequential"

#: The compatibility table, as symmetric pairs (the lead's first cut; the
#: first look judges it). ``NEXT``: may sit next to each other, a plausible
#: walk from one into the other (``sequential``). ``CONTRAST``: opposed
#: factions or elements (``factional``). Every Purpose is in at least one
#: CONTRAST triangle, so three pairwise-contrasting Districts can start from
#: any of them. No pair is in both.
_NEXT_PAIRS: Tuple[Tuple[str, str], ...] = (
    ("fortress", "war_city"), ("fortress", "mine_delve"), ("fortress", "ice_keep"),
    ("fortress", "lava_forge"), ("fortress", "tomb"),
    ("war_city", "temple"), ("war_city", "lava_forge"), ("war_city", "mine_delve"),
    ("warren", "sunken_ruin"), ("warren", "ice_keep"),
    ("temple", "tomb"), ("temple", "sunken_ruin"), ("temple", "ice_keep"),
    ("tomb", "corrupted_sanctum"), ("tomb", "sunken_ruin"), ("tomb", "ice_keep"),
    ("wizard_lair", "lava_forge"), ("wizard_lair", "ice_keep"), ("wizard_lair", "mine_delve"),
    ("wizard_lair", "tomb"),
    ("corrupted_sanctum", "sunken_ruin"),
    ("mine_delve", "lava_forge"),
    # natural caves open onto what lives in, digs into, floods or is buried in them
    ("cave", "warren"), ("cave", "mine_delve"), ("cave", "sunken_ruin"),
    ("cave", "ice_keep"), ("cave", "lava_forge"), ("cave", "tomb"),
)
_CONTRAST_PAIRS: Tuple[Tuple[str, str], ...] = (
    # soldiers, vermin and a cult
    ("fortress", "warren"), ("fortress", "corrupted_sanctum"), ("warren", "corrupted_sanctum"),
    # faith, its corruption and the arcane
    ("temple", "corrupted_sanctum"), ("temple", "wizard_lair"), ("wizard_lair", "corrupted_sanctum"),
    # fire, ice and water
    ("lava_forge", "ice_keep"), ("lava_forge", "sunken_ruin"), ("ice_keep", "sunken_ruin"),
    # a living army, vermin and the dead
    ("war_city", "warren"), ("war_city", "tomb"), ("warren", "tomb"),
    # miners against what they dug into
    ("mine_delve", "warren"), ("mine_delve", "corrupted_sanctum"),
    # the wild cave against the built, the faithful and the arcane
    ("cave", "fortress"), ("cave", "temple"), ("cave", "wizard_lair"),
)


def _table(pairs) -> Dict[str, Tuple[str, ...]]:
    out: Dict[str, set] = {p: set() for p in semantics.ARCHETYPES}
    for a, b in pairs:
        out[a].add(b)
        out[b].add(a)
    return {p: tuple(sorted(v)) for p, v in out.items()}


#: Purpose -> the Purposes it may sit next to / contrasts with.
COMPATIBLE: Dict[str, Tuple[str, ...]] = _table(_NEXT_PAIRS)
CONTRASTS: Dict[str, Tuple[str, ...]] = _table(_CONTRAST_PAIRS)
PURPOSES: Tuple[str, ...] = tuple(sorted(semantics.ARCHETYPES))


def _purpose_name(value) -> str:
    """A proposal's Purpose: a string, or a dict's ``purpose``."""
    if isinstance(value, dict):
        value = value.get("purpose", "")
    return str(value or "").strip().lower()


def _race_name(value) -> str:
    """A proposal's race: a dict's ``race`` (a string proposal names none)."""
    if isinstance(value, dict):
        return str(value.get("race") or "").strip().lower()
    return ""


def district_races(proposals: Optional[Sequence], k: int) -> Tuple[List[str], List[str]]:
    """Each District's own race from *proposals* (district races Req 4): a dict
    proposal's ``race`` in District id order, the first *k* used; "" where none is
    named (the zone's race). A race not in ``semantics.RACE_HEIGHT`` is ignored with
    a ``district_race_unknown`` note, so that District takes the zone's race.
    Returns ``(races, notes)``; nothing is drawn from any rng."""
    races = [""] * k
    notes: List[str] = []
    for d, value in enumerate(list(proposals or [])[:k]):
        name = _race_name(value)
        if not name:
            continue
        if name in semantics.RACE_HEIGHT:
            races[d] = name
        else:
            notes.append(f"district_race_unknown: '{name}' ignored (District {d}), "
                         f"using the zone's race")
    return races, notes


def _parents(part: Partition) -> List[Optional[int]]:
    """District id -> the District on the parent side of its Threshold."""
    return [None] + [part.assign[p] for p, _ in part.thresholds]


def _solutions(k: int, fixed: List[Optional[str]], ok) -> List[List[str]]:
    """Every assignment of the free Districts (``fixed[d] is None``), in id
    order, where each free District's Purpose is used by no other District and
    ``ok(cur)`` holds. Fixed Districts (proposals) are taken as given."""
    free = [d for d in range(k) if fixed[d] is None]
    out = []
    for combo in itertools.product(PURPOSES, repeat=len(free)):
        cur = list(fixed)
        for d, p in zip(free, combo):
            cur[d] = p
        if any(cur[d] in [cur[e] for e in range(k) if e != d] for d in free):
            continue
        if ok(cur):
            out.append(cur)
    return out


def assign_district_purposes(part: Partition, purpose: str = "",
                             proposals: Optional[Sequence] = None,
                             relationship: str = "",
                             rng: Optional[random.Random] = None,
                             *, pinned: bool = False
                             ) -> Tuple[List[DistrictSpec], List[str]]:
    """Each District's Purpose, palette and light mood (umbrella 23.8, 23.10-23.12).

    *purpose* is the plan's archetype (District 0's when no proposal names
    one); *proposals* (strings or ``{"purpose": ...}`` dicts) fill Districts in
    id order, the first ``k`` used; *relationship* is ``sequential`` (default),
    ``factional``, ``abandoned_vs_active`` or ``intrusion``. *pinned* (with a known *purpose*)
    gives every District that Purpose. Unknown values are ignored with a note.
    A dict proposal may also name the District's own ``race`` (:func:`district_races`).

    ``sequential``: pairwise-distinct Purposes, each compatible with the
    District across its Threshold. ``factional``: pairwise-distinct Purposes,
    every pair contrasting where the table allows it, else each contrasting
    with the District across its Threshold. ``abandoned_vs_active``: District
    0's Purpose everywhere, every other District at the ``abandoned`` variant.
    ``intrusion``: pairwise-distinct Purposes, each intruder contrasting with
    the host across its Threshold (a rival that dug in; the partition keeps its
    breaches, :func:`partition_districts`).
    A Threshold whose two Districts would share a palette gives the child the
    next variant (23.5, 23.10).

    Returns ``(districts, notes)``; ``districts`` is empty (and nothing is
    drawn from *rng*) when ``part.k`` is 1. Room ids, entrance and climax are
    left for :func:`fill_district_rooms`; the Threshold corridor id is the
    layout's to set.
    """
    k = part.k
    if k <= 1:
        return [], []
    rng = rng or random.Random()
    notes: List[str] = []

    rel = (relationship or "").strip().lower()
    if not rel:
        rel = DEFAULT_RELATIONSHIP
    elif rel not in RELATIONSHIPS:
        notes.append(f"district_relationship_unknown: '{relationship}' ignored, "
                     f"using {DEFAULT_RELATIONSHIP}")
        rel = DEFAULT_RELATIONSHIP

    first = _purpose_name(purpose)
    if first and first not in semantics.ARCHETYPES:
        notes.append(f"district_purpose_unknown: '{purpose}' ignored")
        first = ""

    fixed: List[Optional[str]] = [None] * k
    for d, value in enumerate(list(proposals or [])[:k]):
        name = _purpose_name(value)
        if name in semantics.ARCHETYPES:
            fixed[d] = name
        else:
            notes.append(f"district_purpose_unknown: '{name}' ignored (District {d})")
    if fixed[0] is None and first:
        fixed[0] = first

    parents = _parents(part)
    levels = [0] * k
    if pinned and first:
        purposes = [first] * k
        notes.append(f"district_purpose_pinned: every District is {first}")
    elif rel == "abandoned_vs_active":
        base = fixed[0] or rng.choice(PURPOSES)
        purposes = [fixed[d] or base for d in range(k)]
        levels = [0] + [1] * (k - 1)
    else:
        table = COMPATIBLE if rel == "sequential" else CONTRASTS
        # Pairs to check: those with a free end (two proposals are taken as given).
        threshold_pairs = [(parents[d], d) for d in range(1, k)
                           if fixed[d] is None or fixed[parents[d]] is None]
        all_pairs = [(a, b) for a, b in itertools.combinations(range(k), 2)
                     if fixed[a] is None or fixed[b] is None]

        def near(cur):
            return all(cur[a] in table[cur[b]] for a, b in threshold_pairs)

        if rel in ("sequential", INTRUSION):
            tiers = [near]
        else:
            def every(cur):
                return all(cur[a] in CONTRASTS[cur[b]] for a, b in all_pairs)
            tiers = [every, near]
        tiers.append(lambda cur: True)
        for i, ok in enumerate(tiers):
            found = _solutions(k, fixed, ok)
            if found:
                break
        if i == len(tiers) - 1:
            notes.append(f"district_purposes_relaxed: no {rel} set fits "
                         f"{[p for p in fixed if p]}; Purposes only distinct")
        purposes = found[rng.randrange(len(found))]

    races, race_notes = district_races(proposals, k)
    notes.extend(race_notes)
    districts = [DistrictSpec(id=d, purpose=purposes[d], relationship=rel, race=races[d])
                 for d in range(k)]
    for d in range(k):
        semantics.set_district_palette(districts[d], levels[d])
    semantics.separate_threshold_palettes(
        districts, [(parents[d], d) for d in range(1, k)])
    return districts, notes


def fill_district_rooms(districts: Sequence[DistrictSpec], part: Partition,
                        rooms: Sequence, entrance: int) -> None:
    """Fill each District's ``room_ids``, ``entrance_room`` and ``climax_room``
    from the partition (room ids from *rooms*, indexed as ``part.assign``)."""
    entrances = district_entrances(part, entrance)
    climaxes = district_climaxes(part, part.edges, entrance)
    for d in districts:
        d.room_ids = [rooms[i].id for i, a in enumerate(part.assign) if a == d.id]
        d.entrance_room = rooms[entrances[d.id]].id
        d.climax_room = rooms[climaxes[d.id]].id
