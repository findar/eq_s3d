"""District races task 6: the ``intrusion`` relationship (Req 6).

An intrusion zone keeps up to ``INTRUSION_LINKS`` of the graph's edges between
each Threshold's two Districts: the Threshold and its breaches. The intruder is
the Threshold's child side (the higher District id). A breach asks for a
``breach`` transition at its host room's door, rough, sized by the smaller race.
Every other relationship keeps exactly one link per pair.
"""

import random
from collections import Counter

import pytest
from hypothesis import given, settings, strategies as st

from generators.districts import (
    INTRUSION, INTRUSION_LINKS, RELATIONSHIPS, assign_district_purposes, CONTRASTS,
    partition_districts, pick_breaches,
)
from generators.layout import DistrictSplitError, LayoutGenerator
from generators.transitions import BREACH, breach_hosts
from generators.zone_spec import CorridorSpec, DistrictSpec, RoomSpec, ZoneSpec
from tests.pbt_helpers import scaled
from tests.test_districts import _graph

PLAN = [{"purpose": "fortress", "race": "giant"}, {"purpose": "warren", "race": "goblin"}]


def test_intrusion_is_a_relationship():
    assert INTRUSION in RELATIONSHIPS and INTRUSION_LINKS == 3


@pytest.mark.parametrize("layout", ["classic", "graph"])
def test_new_breaches_fill_most_pairs(layout):
    """Where the graph offers too few cross edges, new ones are added (the lead's call
    at the task 6 review): many pairs end with 2-3 links, none longer than
    BREACH_SPAN times the longest hall of its two Districts. Since task 17 a goblin
    breach into giants is bounded by goblin halls (archive decision 21), which cost
    breaches where the giant rooms stand far apart (a bare Graph build kept 5 of these
    12 pairs at 2+ links); since step 32 the intruder is seated against its host
    (``_seat_intruders``): Graph 12 of 12, classic 11 of 12."""
    from generators.layout import BREACH_SPAN
    pairs = multi = 0
    for seed in range(2000, 2006):
        gen = LayoutGenerator("dungeon", seed=seed, engine=layout)
        spec = gen.generate("t", room_count=16, districts=True, district_plan=PLAN,
                            district_relationship=INTRUSION)
        by = {r.id: r for r in spec.rooms}
        per = Counter()
        for c in spec.corridors:
            a, b = by[c.from_room], by[c.to_room]
            if a.district != b.district:
                per[frozenset((a.district, b.district))] += 1
                inner = [LayoutGenerator._hall_span(by[x.from_room], by[x.to_room])
                         for x in spec.corridors
                         if {by[x.from_room].district, by[x.to_room].district} <= {a.district, b.district}]
                assert LayoutGenerator._hall_span(a, b) <= BREACH_SPAN * max(inner) * 1.5
        pairs += len(per)
        multi += sum(v >= 2 for v in per.values())
        assert max(per.values()) <= INTRUSION_LINKS
    assert multi >= 0.8 * pairs


def test_a_seat_moves_the_intruder_whole(monkeypatch):
    """Step 32 task 1 (bare Graph seed 2001: both pairs joined by their Threshold
    alone): the intruder District is moved by a rigid motion to where its rooms face
    host rooms within the breach bound. The host stays where it was, the intruder's own
    halls keep their spans, and more of its rooms are in reach than before."""
    seen = []
    seat = LayoutGenerator._seat_intruder

    def spy(self, rooms, edges, part, n, near, levels):
        p, c = part.thresholds[n]
        host, intr = rooms[p].district, rooms[c].district

        def snap():
            inner = sorted(self._hall_span(rooms[i], rooms[j]) for i, j in edges
                           if rooms[i].district == rooms[j].district == intr)
            bound = self._breach_bound(rooms, edges, part.assign, {host, intr})
            reach = {r for r in range(len(rooms)) if rooms[r].district == intr
                     and any(rooms[h].district == host
                             and self._link_span(rooms[h], rooms[r]) <= bound
                             for h in range(len(rooms)))}
            return ({r.id: (r.center_x, r.center_y) for r in rooms if r.district == host},
                    inner, len(reach))
        before = snap()
        moved = seat(self, rooms, edges, part, n, near, levels)
        seen.append((moved, before, snap()))
        return moved

    monkeypatch.setattr(LayoutGenerator, "_seat_intruder", spy)
    LayoutGenerator("dungeon", seed=2001, engine="graph").generate(
        "t", room_count=16, districts=True, district_plan=PLAN, district_relationship=INTRUSION)
    moves = [(b, a) for moved, b, a in seen if moved]
    assert moves
    for (host0, inner0, reach0), (host1, inner1, reach1) in moves:
        assert host1 == host0
        assert inner1 == pytest.approx(inner0)
        assert reach1 > reach0


def test_a_breach_may_climb_between_levels():
    """Step 32 task 1 (step 31 decision 20: prompt seed 2023's goblin pairs sat on
    other Levels, so it joined the goblins by its Threshold alone): on a stacked build
    a breach between two Levels is a planned stair, as any edge across Levels."""
    from ai.expand import plan_to_spec
    from ai.planner import make_plan
    plan = make_plan("a towering giant fortress the goblins tunnelled into, with 16 rooms",
                     name="gf2023")
    spec = plan_to_spec(plan, seed=2023, warnings=[])
    by = {r.id: r for r in spec.rooms}
    race = {d.id: d.race for d in spec.districts}
    cors = {c.id: c for c in spec.corridors}
    goblin = [cors[cid] for cid in breach_hosts(spec)
              if "goblin" in (race[by[cors[cid].from_room].district],
                              race[by[cors[cid].to_room].district])]
    assert goblin and any(c.steps for c in goblin)


def test_breaches_keep_to_the_degree_band(monkeypatch):
    """A new breach never takes a room past the quality bands' max_degree (task 10: graph
    intrusion zones failed max_degree on 5.6 % of Draws), read from the band table."""
    from generators import quality
    gen = LayoutGenerator("dungeon", seed=2000, engine="graph")
    assert gen._breach_degree_cap(16, 3) == quality.bands_for("dungeon", "graph", 16, "moderate", 3)["max_degree"][1]
    assert LayoutGenerator("dungeon", seed=2000, engine="classic")._breach_degree_cap(16, 3) is None

    def links(cap):
        monkeypatch.setattr(LayoutGenerator, "_breach_degree_cap", lambda self, n, k: cap)
        spec = LayoutGenerator("dungeon", seed=2003, engine="graph").generate(
            "t", room_count=16, districts=True, district_plan=PLAN, district_relationship=INTRUSION)
        by = {r.id: r.district for r in spec.rooms}
        return sum(by[c.from_room] != by[c.to_room] for c in spec.corridors)

    assert links(0) < links(None)       # at cap 0 no room can take a new breach

graphs = st.integers(8, 30).flatmap(
    lambda n: st.tuples(st.just(n), st.integers(0, 2**31), st.integers(0, n - 1),
                        st.integers(2, 3), st.integers(0, 2**31)))


@settings(max_examples=scaled(60), deadline=None)
@given(graphs)
def test_partition_keeps_breaches_on_threshold_pairs_only(case):
    """The cut is the one a single link makes (same Districts, Thresholds and rng
    draws); only edges between a Threshold's two Districts are added back, up to
    INTRUSION_LINKS per pair, the Threshold among them."""
    n, gseed, entrance, k, seed = case
    edges = _graph(n, gseed)
    one = partition_districts(list(range(n)), edges, entrance, k, random.Random(seed))
    rng = random.Random(seed)
    many = partition_districts(list(range(n)), edges, entrance, k, rng, links=INTRUSION_LINKS)
    after = random.Random(seed)
    partition_districts(list(range(n)), edges, entrance, k, after)
    assert rng.random() == after.random()
    assert (many.k, many.assign, many.thresholds) == (one.k, one.assign, one.thresholds)
    assert set(one.edges) <= set(many.edges)
    assert {frozenset(e) for e in many.edges} <= {frozenset(e) for e in edges}

    pairs = {frozenset((many.assign[p], many.assign[c])) for p, c in many.thresholds}
    links = Counter()
    for a, b in many.edges:
        da, db = many.assign[a], many.assign[b]
        if da != db:
            links[frozenset((da, db))] += 1
    assert set(links) == pairs
    assert all(1 <= v <= INTRUSION_LINKS for v in links.values())
    assert len(many.edges) - len(one.edges) == len(many.breaches)
    for h, t in many.breaches:
        assert many.assign[h] < many.assign[t]          # host first: the parent side


def test_breaches_prefer_rooms_on_no_link_yet():
    #  Districts: 0 = {0, 1, 2}, 1 = {3, 4, 5}; Threshold 2-3.
    assign = [0, 0, 0, 1, 1, 1]
    edges = [(2, 4), (1, 5), (0, 3), (2, 5)]
    # 2-4 reuses room 2 (on the Threshold); 1-5 is fresh; then 0-3 reuses 3, so the
    # second pass takes 2-4.
    assert pick_breaches(assign, edges, [(2, 3)], 3) == [(1, 5), (2, 4)]
    assert pick_breaches(assign, edges, [(2, 3)], 2) == [(1, 5)]
    assert pick_breaches(assign, [(4, 2)], [(2, 3)], 3) == [(2, 4)]   # host side first


class _Part:
    def __init__(self, assign, thresholds):
        self.assign = assign
        self.thresholds = thresholds


def test_threshold_check_allows_an_intrusion_pairs_links():
    part = _Part([0, 0, 0, 1, 1, 1], [(2, 3)])
    check = LayoutGenerator._district_thresholds
    base = [(0, 1), (1, 2), (3, 4), (4, 5)]
    assert check(part, base + [(0, 5), (2, 3), (1, 4)], 3) == [(2, 3)]
    # The Threshold gone: one still entering its child room, else the first.
    assert check(part, base + [(0, 5), (1, 3)], 3) == [(1, 3)]
    assert check(part, base + [(0, 5), (1, 4)], 3) == [(0, 5)]
    with pytest.raises(DistrictSplitError):
        check(part, base + [(0, 5), (2, 3), (1, 4), (0, 4)], 3)
    with pytest.raises(DistrictSplitError):
        check(part, base + [(0, 5), (2, 3)])                 # one link elsewhere
    assert LayoutGenerator._district_breaches(part, base + [(5, 0), (2, 3)]) == [(0, 5)]


def test_intruder_contrasts_its_host():
    part = _Part([0] * 4 + [1] * 4 + [2] * 4, [(3, 4), (7, 8)])
    part.k = 3
    for seed in range(20):
        ds, notes = assign_district_purposes(part, "", ["fortress"], INTRUSION, random.Random(seed))
        assert not notes
        assert {d.relationship for d in ds} == {INTRUSION}
        assert len({d.purpose for d in ds}) == 3
        assert ds[1].purpose in CONTRASTS["fortress"]
        assert ds[2].purpose in CONTRASTS[ds[1].purpose]


def test_breach_hosts():
    rooms = [RoomSpec(f"r{i}", i * 100.0, 0.0) for i in range(4)]
    for r, d in zip(rooms, (0, 0, 1, 1)):
        r.district = d
    spec = ZoneSpec(name="t", rooms=rooms, districts=[DistrictSpec(0, "fortress", relationship=INTRUSION),
                                                    DistrictSpec(1, "warren", relationship=INTRUSION)])
    def cor(cid, a, b, **kw):
        return CorridorSpec(cid, 0.0, 0.0, 0.0, 0.0, from_room=a, to_room=b, **kw)
    spec.corridors = [cor("corr_0", "r1", "r2", threshold=True), cor("corr_1", "r3", "r0"),
                      cor("corr_2", "r0", "r1")]
    assert breach_hosts(spec) == {"corr_1": "r0"}
    for d in spec.districts:
        d.relationship = "factional"
    assert breach_hosts(spec) == {}


@pytest.mark.parametrize("layout,seed", [("classic", 23), ("graph", 25)])
def test_intrusion_layout(layout, seed):
    """An intrusion zone joins its Districts by up to three links, one Threshold
    each; the breaches are sized by the smaller race (the goblins')."""
    gen = LayoutGenerator("dungeon", seed=seed, engine=layout)
    spec = gen.generate("t", room_count=16, districts=True, district_plan=PLAN,
                        district_relationship=INTRUSION)
    by = {r.id: r for r in spec.rooms}
    cross = [c for c in spec.corridors if by[c.from_room].district != by[c.to_room].district]
    per = Counter(frozenset((by[c.from_room].district, by[c.to_room].district)) for c in cross)
    assert max(per.values()) >= 2 and max(per.values()) <= INTRUSION_LINKS
    assert sum(c.threshold for c in cross) == len(spec.districts) - 1 == len(per)
    goblin = [c for c in cross if {by[c.from_room].district, by[c.to_room].district} == {0, 1}]
    widths = {c.width for c in goblin}
    assert len(widths) == 1 and widths == {min(c.width for c in spec.corridors
                                               if by[c.from_room].district == 1 == by[c.to_room].district)}


def test_breaches_are_rough_breaches(monkeypatch):
    """Through the plan (graph walls are drawn there): each breach asks for a breach
    at its host's door, and a plain one runs rough."""
    import ai.expand as ex
    from ai.schema import ZonePlan
    monkeypatch.setattr(ex, "layout_proposals", lambda plan, s: [dict(p) for p in PLAN])
    plan = ZonePlan.from_controls({"zone_type": "dungeon", "room_count": 24, "layout": "graph",
                                   "verticality": "flat", "districts": True,
                                   "district_plan": ["fortress", "warren"],
                                   "district_relationship": INTRUSION}, [])
    spec = ex.plan_to_spec(plan, seed=2013, warnings=[])
    hosts = breach_hosts(spec)
    assert hosts
    cors = {c.id: c for c in spec.corridors}
    by = {r.id: r for r in spec.rooms}
    records = {t["corridor"]: t for t in spec.layout["transitions"]}
    for cid, host in hosts.items():
        cor, rec = cors[cid], records[cid]
        assert rec["breach_into"] == host and host in (cor.from_room, cor.to_room)
        assert rec["form"] == BREACH or rec.get("asked") == BREACH
        if cor.steps == 0 and not cor.bridge:
            assert cor.rough > 0
        other = cor.to_room if host == cor.from_room else cor.from_room
        assert by[host].district < by[other].district
