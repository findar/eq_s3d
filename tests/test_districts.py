"""Districts spec task 1: the partition (Req 1) and the spec fields."""

import itertools
import random
from collections import deque

from hypothesis import given, settings, strategies as st

from tests.pbt_helpers import scaled

from generators.districts import (
    Partition, district_climaxes, district_count, min_district_size,
    partition_districts,
)
from generators.zone_spec import CorridorSpec, DistrictSpec, RoomSpec, ZoneSpec


def _graph(n, seed):
    """A random connected graph on n rooms: a random tree plus a few extra edges."""
    r = random.Random(seed)
    edges = [(r.randrange(i), i) for i in range(1, n)]
    have = {frozenset(e) for e in edges}
    for _ in range(r.randint(0, n)):
        a, b = r.randrange(n), r.randrange(n)
        if a != b and frozenset((a, b)) not in have:
            have.add(frozenset((a, b)))
            edges.append((a, b))
    r.shuffle(edges)
    return edges


def _components(nodes, edges):
    nodes = set(nodes)
    adj = {i: [] for i in nodes}
    for a, b in edges:
        if a in nodes and b in nodes:
            adj[a].append(b)
            adj[b].append(a)
    seen, comps = set(), 0
    for s in nodes:
        if s in seen:
            continue
        comps += 1
        q = deque([s])
        seen.add(s)
        while q:
            cur = q.popleft()
            for nxt in adj[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    q.append(nxt)
    return comps


def _tree_cut_exists(n, edges, entrance, k):
    """Brute force: is there a k-way cut of the sorted-BFS tree meeting the sizes?"""
    adj = {i: sorted({b for a, b in edges if a == i} | {a for a, b in edges if b == i})
           for i in range(n)}
    parent, order, q = {entrance: None}, [entrance], deque([entrance])
    while q:
        cur = q.popleft()
        for nxt in adj[cur]:
            if nxt not in parent:
                parent[nxt] = cur
                order.append(nxt)
                q.append(nxt)
    m = min_district_size(n, k)
    for cuts in itertools.combinations(order[1:], k - 1):
        owner = {}
        for room in order:
            owner[room] = room if room in cuts else (owner[parent[room]] if parent[room] is not None else -1)
        sizes = [list(owner.values()).count(o) for o in set(owner.values())]
        if len(sizes) == k and min(sizes) >= m:
            return True
    return False


graphs = st.integers(1, 30).flatmap(
    lambda n: st.tuples(st.just(n), st.integers(0, 2**31), st.integers(0, n - 1),
                        st.integers(1, 3), st.integers(0, 2**31)))


@settings(max_examples=scaled(60), deadline=None)
@given(graphs)
def test_partition_properties(case):
    n, gseed, entrance, k, seed = case
    edges = _graph(n, gseed)
    part = partition_districts(list(range(n)), edges, entrance, k, random.Random(seed))

    assert part.requested == k and 1 <= part.k <= k
    assert len(part.assign) == n and set(part.assign) == set(range(part.k))
    assert part.assign[entrance] == 0
    # k drops only when no cut meets the sizes.
    for kk in range(part.k + 1, k + 1):
        assert not _tree_cut_exists(n, edges, entrance, kk)

    kept = {frozenset(e) for e in part.edges}
    assert kept <= {frozenset(e) for e in edges}
    assert len(kept) == len(part.edges)
    assert _components(range(n), part.edges) == 1

    if part.k >= 2:
        m = min_district_size(n, part.k)
        for d in range(part.k):
            members = [i for i in range(n) if part.assign[i] == d]
            assert len(members) >= m
            assert _components(members, part.edges) == 1

    # Exactly one kept edge between adjacent Districts, and it is the Threshold.
    assert len(part.thresholds) == part.k - 1
    links = {}
    for a, b in part.edges:
        da, db = part.assign[a], part.assign[b]
        if da != db:
            links.setdefault(frozenset((da, db)), []).append(frozenset((a, b)))
    assert all(len(v) == 1 for v in links.values())
    assert {v[0] for v in links.values()} == {frozenset(t) for t in part.thresholds}
    for d, (p, c) in enumerate(part.thresholds, start=1):
        assert part.assign[c] == d and part.assign[p] != d

    # Same inputs, same partition.
    again = partition_districts(list(range(n)), edges, entrance, k, random.Random(seed))
    assert again == part

    # One climax per District: deepest by in-District BFS from its entrance (23.4).
    climaxes = district_climaxes(part, part.edges, entrance)
    starts = [entrance] + [c for _, c in part.thresholds]
    assert len(climaxes) == part.k
    for d, (start, cl) in enumerate(zip(starts, climaxes)):
        members = {i for i in range(n) if part.assign[i] == d}
        dist, q = {start: 0}, deque([start])
        while q:
            cur = q.popleft()
            for a, b in part.edges:
                for x, y in ((a, b), (b, a)):
                    if x == cur and y in members and y not in dist:
                        dist[y] = dist[cur] + 1
                        q.append(y)
        assert set(dist) == members
        assert cl == min(members, key=lambda i: (-dist[i], i))


@settings(max_examples=scaled(40), deadline=None)
@given(graphs)
def test_one_district_draws_nothing(case):
    n, gseed, entrance, k, seed = case
    edges = _graph(n, gseed)
    rng = random.Random(seed)
    before = rng.getstate()
    part = partition_districts(list(range(n)), edges, entrance, 1, rng)
    assert rng.getstate() == before
    assert part.edges == edges and part.assign == [0] * n and part.thresholds == []
    # A k that resolves to 1 draws nothing either.
    part = partition_districts(list(range(n)), edges, entrance, k, rng)
    if part.k == 1:
        assert rng.getstate() == before and part.edges == edges


def test_district_count():
    assert [district_count(n, False) for n in (1, 8, 20)] == [1, 1, 1]
    assert [district_count(n, True) for n in (1, 7, 8, 13, 14, 30)] == [1, 1, 2, 2, 3, 3]


def test_chain_too_short_drops_k():
    # 5 rooms can't hold two Districts of 3.
    edges = [(i, i + 1) for i in range(4)]
    part = partition_districts(range(5), edges, 0, 2, random.Random(1))
    assert (part.k, part.requested) == (1, 2)


def test_chain_cut_in_the_middle():
    edges = [(i, i + 1) for i in range(9)]
    part = partition_districts(range(10), edges, 0, 2, random.Random(1))
    assert part.k == 2 and part.thresholds == [(4, 5)]
    assert part.assign == [0] * 5 + [1] * 5
    assert district_climaxes(part, part.edges, 0) == [4, 9]


def _spec():
    spec = ZoneSpec(name="d")
    spec.rooms = [RoomSpec(id=f"room_{i}", center_x=0, center_y=0) for i in range(2)]
    spec.corridors = [CorridorSpec(id="corr_0", from_x=0, from_y=0, to_x=1, to_y=0,
                                   from_room="room_0", to_room="room_1", threshold=True)]
    spec.districts = [
        DistrictSpec(id=0, purpose="fortress", entrance_room="room_0", climax_room="room_0",
                     room_ids=["room_0"], relationship="factional", palette="fortress",
                     light_mood="warm"),
        DistrictSpec(id=1, purpose="tomb", entrance_room="room_1", climax_room="room_1",
                     room_ids=["room_1"], threshold_corridor="corr_0",
                     relationship="factional"),
    ]
    return spec


def test_spec_round_trip():
    spec = _spec()
    back = ZoneSpec.from_dict(spec.to_dict())
    assert back.districts == spec.districts
    assert back.corridors[0].threshold is True
    assert back.to_dict() == spec.to_dict()


def test_old_spec_loads_with_defaults():
    d = _spec().to_dict()
    d.pop("districts")
    d["corridors"][0].pop("threshold")
    back = ZoneSpec.from_dict(d)
    assert back.districts == [] and back.corridors[0].threshold is False
    # Defaults stay out of the JSON, so one-District spec JSON is unchanged.
    out = back.to_dict()
    assert "districts" not in out and "threshold" not in out["corridors"][0]
