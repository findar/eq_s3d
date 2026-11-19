"""Districts in the layout (districts spec Requirement 3, task 3).

``LayoutGenerator.generate(..., districts=True)`` partitions a dungeon's room
graph before pacing, paces it with one climax per District, flags the Threshold
corridors, fills ``spec.districts`` and gates the Thresholds first. With the
switch off, or one District resolved, the spec is the one built without it.
"""

import random
from collections import deque
from pathlib import Path

import pytest

from generators.districts import min_district_size
from generators.layout import DistrictSplitError, LayoutGenerator
from tests.pbt_helpers import solvable_walk

LAYOUTS = ("classic", "graph")


def _case(seed):
    """Room count (8-30) and locks (0-3) for a seed."""
    r = random.Random(seed)
    return r.randint(8, 30), r.randint(0, 3)


def _districted(layout, seed, n, locks, **kw):
    gen = LayoutGenerator("dungeon", seed=seed, engine=layout)
    spec = gen.generate(f"dl_{layout}_{seed}", room_count=n, locks=locks,
                        districts=True, **kw)
    return gen, spec


def _adjacency(spec, same_district_only=False):
    district = {r.id: r.district for r in spec.rooms}
    adj = {r.id: set() for r in spec.rooms}
    for c in spec.corridors:
        if same_district_only and district[c.from_room] != district[c.to_room]:
            continue
        adj[c.from_room].add(c.to_room)
        adj[c.to_room].add(c.from_room)
    return adj


def _reach(adj, start, allowed):
    seen = {start}
    q = deque([start])
    while q:
        cur = q.popleft()
        for nxt in adj[cur]:
            if nxt in allowed and nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    return seen


def _check_districts(spec, locks):
    rooms = {r.id: r for r in spec.rooms}
    n = len(spec.rooms)
    k = len(spec.districts)
    assert 2 <= k <= 3
    assert [d.id for d in spec.districts] == list(range(k))

    # Req 1: every room in exactly one District, each connected, sized.
    owned = [rid for d in spec.districts for rid in d.room_ids]
    assert sorted(owned) == sorted(rooms)
    inner = _adjacency(spec, same_district_only=True)
    for d in spec.districts:
        assert all(rooms[rid].district == d.id for rid in d.room_ids)
        assert len(d.room_ids) >= min_district_size(n, k)
        members = set(d.room_ids)
        assert _reach(inner, d.entrance_room, members) == members

    # Thresholds: exactly the cross-District corridors, one per District past 0.
    cross = [c for c in spec.corridors
             if rooms[c.from_room].district != rooms[c.to_room].district]
    flagged = [c for c in spec.corridors if c.threshold]
    assert {c.id for c in cross} == {c.id for c in flagged}
    assert len(flagged) == k - 1
    pairs = {frozenset((rooms[c.from_room].district, rooms[c.to_room].district))
             for c in flagged}
    assert len(pairs) == k - 1
    by_id = {c.id: c for c in spec.corridors}
    parent = {}
    assert spec.districts[0].threshold_corridor is None
    for d in spec.districts[1:]:
        c = by_id[d.threshold_corridor]
        assert c.threshold
        ends = {c.from_room, c.to_room}
        assert d.entrance_room in ends and rooms[d.entrance_room].district == d.id
        (other,) = ends - {d.entrance_room}
        parent[d.id] = rooms[other].district

    # One entrance; one climax per District, and it is the District's.
    entrances = [r for r in spec.rooms if r.role == "entrance"]
    assert len(entrances) == 1
    assert entrances[0].id == spec.districts[0].entrance_room
    for d in spec.districts:
        boss = [rid for rid in d.room_ids if rooms[rid].role == "climax"]
        assert boss == [d.climax_room]
        assert rooms[d.climax_room].room_theme == d.purpose

    # The whole graph is joined and every key can be had before its lock.
    adj = _adjacency(spec)
    assert _reach(adj, entrances[0].id, set(rooms)) == set(rooms)
    assert solvable_walk(spec) == set(rooms)

    # Gates: the Thresholds first (23.7), keys on the entrance side.
    gated = {g.corridor_id: g for g in spec.gates}
    assert len(spec.gates) <= locks
    on_thresholds = [cid for cid in gated if by_id[cid].threshold]
    assert len(on_thresholds) == min(locks, k - 1)
    for d in spec.districts[1:]:
        g = gated.get(d.threshold_corridor)
        if g is None:
            continue
        beyond, grew = {d.id}, True
        while grew:
            grew = False
            for child, par in parent.items():
                if par in beyond and child not in beyond:
                    beyond.add(child)
                    grew = True
        assert rooms[g.key_room_id].district not in beyond


@pytest.mark.parametrize("layout", LAYOUTS)
@pytest.mark.parametrize("seed", range(12))
def test_districted_dungeon(layout, seed):
    n, locks = _case(seed)
    gen, spec = _districted(layout, 500 + seed, n, locks)
    if not spec.districts:
        # No cut met the sizes: k fell to 1, with the note.
        assert any(w.startswith("districts_reduced") for w in gen.warnings)
        assert not any(c.threshold for c in spec.corridors)
        return
    _check_districts(spec, locks)
    # A Draw a crossing split broke was redrawn, not returned.
    assert spec.to_dict()["districts"]


@pytest.mark.parametrize("layout", LAYOUTS)
def test_districts_need_no_theme_and_honour_one(layout):
    """With Districts on, rooms are labelled even when no theme was given; a
    theme becomes District 0's Purpose."""
    _, spec = _districted(layout, 41, 20, 0)
    assert spec.districts and all(r.room_theme for r in spec.rooms)
    _, spec = _districted(layout, 41, 20, 0, dungeon_theme="tomb")
    assert spec.districts[0].purpose == "tomb"
    assert spec.dungeon_theme == "tomb"


def test_proposals_and_relationship_reach_the_districts():
    _, spec = _districted("classic", 7, 22, 0, district_plan=["temple", "tomb", "warren"],
                          district_relationship="factional")
    k = len(spec.districts)
    assert [d.purpose for d in spec.districts] == ["temple", "tomb", "warren"][:k]
    assert {d.relationship for d in spec.districts} == {"factional"}


def test_unknown_relationship_is_a_warning():
    gen, spec = _districted("classic", 7, 22, 0, district_relationship="feuding")
    assert spec.districts
    assert any(w.startswith("district_relationship_unknown") for w in gen.warnings)


def _spec_json(spec):
    return spec.to_dict()


@pytest.mark.parametrize("layout", LAYOUTS)
@pytest.mark.parametrize("zone_type,n", [("dungeon", 7), ("dungeon", 5), ("city", 20)])
def test_one_district_is_byte_identical(layout, zone_type, n):
    """Below 8 rooms, or on a zone type other than dungeon, the switch changes
    nothing (Req 3.4, A2): the same spec and the same rng afterwards."""
    for seed in (3, 19):
        off = LayoutGenerator(zone_type, seed=seed, engine=layout)
        a = off.generate("same", room_count=n, locks=1)
        on = LayoutGenerator(zone_type, seed=seed, engine=layout)
        b = on.generate("same", room_count=n, locks=1, districts=True,
                        district_plan=["tomb"], district_relationship="factional")
        assert _spec_json(a) == _spec_json(b)
        assert off.rng.random() == on.rng.random()
        assert not b.districts and on.warnings == off.warnings


class _StarEngine:
    """A hub and eight spokes: no cut leaves 3 rooms on both sides, so k
    falls to 1."""
    name = "star"
    sizes_rooms = False

    def generate(self, ctx, room_count, envelope):
        import math
        from generators.layout_engine import EngineResult, Edge
        from generators.zone_spec import RoomSpec
        rooms = [RoomSpec(id="room_0", center_x=0.0, center_y=0.0, floor_z=0.0,
                          width=200.0, depth=200.0, height=ctx.ceiling)]
        for k in range(8):
            a = 2 * math.pi * k / 8
            rooms.append(RoomSpec(id=f"room_{k + 1}", center_x=900 * math.cos(a),
                                  center_y=900 * math.sin(a), floor_z=0.0,
                                  width=150.0, depth=150.0, height=ctx.ceiling))
        ctx.separate(rooms)
        return EngineResult(rooms=rooms, edges=[Edge(0, k + 1) for k in range(8)])


def test_k_falls_to_one_with_a_note_and_no_change():
    off = LayoutGenerator("dungeon", seed=5, engine=_StarEngine())
    a = off.generate("star", room_count=9)
    on = LayoutGenerator("dungeon", seed=5, engine=_StarEngine())
    b = on.generate("star", room_count=9, districts=True)
    assert _spec_json(a) == _spec_json(b)
    assert on.warnings == ["districts_reduced: 2 requested, 1 fit the room graph"]


class _Part:
    def __init__(self, assign, thresholds):
        self.assign = assign
        self.thresholds = thresholds


def test_threshold_check():
    """After the crossing and conflict passes: one edge per Threshold pair
    passes (a Threshold that moved is followed); a second link, a new pair or
    a split graph fails the Draw (Req 3.3)."""
    part = _Part([0, 0, 0, 1, 1, 1], [(2, 3)])
    check = LayoutGenerator._district_thresholds
    assert check(part, [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]) == [(2, 3)]
    # A split of the Threshold through room 1 moved it to 1-3.
    assert check(part, [(0, 1), (1, 2), (3, 1), (3, 4), (4, 5)]) == [(1, 3)]
    with pytest.raises(DistrictSplitError, match="district threshold split"):
        check(part, [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (0, 5)])
    with pytest.raises(ValueError):
        check(part, [(0, 1), (1, 2), (3, 4), (4, 5)])
    part3 = _Part([0, 0, 1, 1, 2, 2], [(1, 2), (3, 4)])
    with pytest.raises(DistrictSplitError):
        check(part3, [(0, 1), (1, 2), (2, 3), (1, 4), (4, 5)])


@pytest.mark.slow
@pytest.mark.parametrize("layout", LAYOUTS)
@pytest.mark.parametrize("seed", range(3))
def test_districted_dungeon_walkable(layout, seed, tmp_path):
    """The walkability gate on the built zone: every room reached, every
    corridor continuous (Req 3.5)."""
    import analyzer.traverse as traverse
    from generators.builder import ZoneBuilder

    n, locks = _case(100 + seed)
    _, spec = _districted(layout, 900 + seed, max(n, 14), locks)
    assert spec.districts
    result = ZoneBuilder(spec).build(output_dir=Path(tmp_path), write_glb=False)
    report = traverse.validate(result.eqg_path, spec=spec, check_corridors=True)
    assert report.passed and report.corridors_passed
