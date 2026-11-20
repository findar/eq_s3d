"""Districts spec task 2: Purposes, palettes and lights (Req 2)."""

import itertools
import random

import pytest

from generators import semantics
from generators.districts import (
    COMPATIBLE, CONTRASTS, PURPOSES, RELATIONSHIPS, Partition,
    assign_district_purposes, fill_district_rooms,
)
from generators.zone_spec import DistrictSpec, LightSpec, RoomSpec, ZoneSpec

# Partitions by hand: rooms 0..n-1 in a chain, entrance 0.
CHAIN_EDGES = [(i, i + 1) for i in range(11)]
# k = 2: rooms 0-5 | 6-11, Threshold (5, 6).
TWO = Partition(k=2, requested=2, assign=[0] * 6 + [1] * 6, edges=CHAIN_EDGES,
                thresholds=[(5, 6)])
# k = 3 in a chain: 0-3 | 4-7 | 8-11; District 2 hangs off District 1.
CHAIN3 = Partition(k=3, requested=3, assign=[0] * 4 + [1] * 4 + [2] * 4,
                   edges=CHAIN_EDGES, thresholds=[(3, 4), (7, 8)])
# k = 3 as a star: room 0 joins 1-3 (District 0), 4-7 (District 1), 8-11 (District 2).
STAR_EDGES = [(0, 1), (1, 2), (2, 3), (0, 4), (4, 5), (5, 6), (6, 7),
              (0, 8), (8, 9), (9, 10), (10, 11)]
STAR3 = Partition(k=3, requested=3, assign=[0] * 4 + [1] * 4 + [2] * 4,
                  edges=STAR_EDGES, thresholds=[(0, 4), (0, 8)])
PARTS = [TWO, CHAIN3, STAR3]


def _parent(part, d):
    return part.assign[part.thresholds[d - 1][0]]


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------

def test_table_covers_every_archetype_symmetric_and_disjoint():
    assert set(PURPOSES) == set(semantics.ARCHETYPES)
    for table in (COMPATIBLE, CONTRASTS):
        assert set(table) == set(PURPOSES)
        for p, others in table.items():
            assert p not in others
            for q in others:
                assert p in table[q]
    for p in PURPOSES:
        assert not set(COMPATIBLE[p]) & set(CONTRASTS[p]), p


def test_table_lets_every_purpose_start_three_districts():
    for p in PURPOSES:
        assert any(c in CONTRASTS[a] and c in CONTRASTS[p]
                   for a in CONTRASTS[p] for c in CONTRASTS[a]), p
        assert any(set(COMPATIBLE[a]) - {p} for a in COMPATIBLE[p]), p


def test_cave_neighbours_and_contrasts():
    """Cave sits next to what lives in, digs into, floods or is buried in it, and
    contrasts with the built, the faithful and the arcane (step 21 design)."""
    assert set(COMPATIBLE["cave"]) == {"warren", "mine_delve", "sunken_ruin", "ice_keep",
                                       "lava_forge", "tomb"}
    assert set(CONTRASTS["cave"]) == {"fortress", "temple", "wizard_lair"}


@pytest.mark.parametrize("rel", ["sequential", "factional"])
def test_drawn_districts_can_be_cave(rel):
    drawn = {d.purpose for seed in range(200)
             for d in assign_district_purposes(CHAIN3, "", None, rel, random.Random(seed))[0]}
    assert "cave" in drawn

def test_every_purpose_has_a_palette():
    assert set(semantics.PURPOSE_PALETTES) == set(semantics.ARCHETYPES)
    colours = [tuple(v["floor"][0]) for v in semantics.PURPOSE_PALETTES.values()]
    assert len(set(colours)) == len(colours)


# ---------------------------------------------------------------------------
# Choosing Purposes
# ---------------------------------------------------------------------------

def test_one_district_draws_nothing():
    rng = random.Random(5)
    one = Partition(k=1, requested=2, assign=[0] * 6, edges=CHAIN_EDGES[:5])
    assert assign_district_purposes(one, "tomb", ["temple"], "factional", rng) == ([], [])
    assert rng.random() == random.Random(5).random()


@pytest.mark.parametrize("part", PARTS, ids=["two", "chain3", "star3"])
@pytest.mark.parametrize("purpose", ["", "tomb", "warren", "cave"])
def test_sequential_distinct_and_compatible_across_thresholds(part, purpose):
    for seed in range(40):
        ds, notes = assign_district_purposes(part, purpose, None, "", random.Random(seed))
        purposes = [d.purpose for d in ds]
        assert len(ds) == part.k and not notes
        assert len(set(purposes)) == part.k
        if purpose:
            assert purposes[0] == purpose
        for d in range(1, part.k):
            assert purposes[d] in COMPATIBLE[purposes[_parent(part, d)]]
        assert all(d.relationship == "sequential" for d in ds)


@pytest.mark.parametrize("part", PARTS, ids=["two", "chain3", "star3"])
@pytest.mark.parametrize("purpose", ["", "fortress", "mine_delve", "cave"])
def test_factional_pairwise_distinct_contrasting(part, purpose):
    for seed in range(40):
        ds, notes = assign_district_purposes(part, purpose, None, "factional",
                                             random.Random(seed))
        purposes = [d.purpose for d in ds]
        assert not notes
        assert len(set(purposes)) == part.k
        for a, b in itertools.combinations(purposes, 2):
            assert b in CONTRASTS[a], purposes


@pytest.mark.parametrize("part", PARTS, ids=["two", "chain3", "star3"])
def test_abandoned_vs_active_one_purpose_variant_off_the_entrance(part):
    for seed in range(20):
        ds, _ = assign_district_purposes(part, "", None, "abandoned_vs_active",
                                         random.Random(seed))
        assert len({d.purpose for d in ds}) == 1
        assert ds[0].palette == ds[0].purpose and ds[0].light_mood == "lit"
        for d in ds[1:]:
            _, level = semantics.palette_level(d.palette)
            assert level >= 1 and d.light_mood != "lit"
        for d in range(1, part.k):
            assert ds[d].palette != ds[_parent(part, d)].palette


def test_proposals_fill_the_first_k():
    ds, notes = assign_district_purposes(TWO, "fortress",
                                         ["tomb", {"purpose": "temple"}, "warren"], "",
                                         random.Random(1))
    assert [d.purpose for d in ds] == ["tomb", "temple"] and not notes
    for seed in range(20):
        ds, _ = assign_district_purposes(CHAIN3, "", ["lava_forge"], "sequential",
                                         random.Random(seed))
        assert ds[0].purpose == "lava_forge"
        assert ds[1].purpose in COMPATIBLE["lava_forge"]
        assert ds[2].purpose in COMPATIBLE[ds[1].purpose]


def test_unknown_values_fall_back_with_a_note():
    ds, notes = assign_district_purposes(TWO, "dragonhold", ["bogus", "tomb"], "frenemies",
                                         random.Random(3))
    text = " ".join(notes)
    assert "'dragonhold'" in text and "'bogus'" in text and "'frenemies'" in text
    assert all(d.relationship == "sequential" for d in ds)
    assert ds[1].purpose == "tomb" and ds[0].purpose in COMPATIBLE["tomb"]


@pytest.mark.parametrize("part", PARTS, ids=["two", "chain3", "star3"])
@pytest.mark.parametrize("rel", RELATIONSHIPS)
@pytest.mark.parametrize("purpose", ["temple", "cave"])
def test_pinned_purpose_everywhere_with_variants(part, rel, purpose):
    ds, notes = assign_district_purposes(part, purpose, ["tomb"], rel, random.Random(0),
                                         pinned=True)
    assert [d.purpose for d in ds] == [purpose] * part.k
    assert any("pinned" in n for n in notes)
    for d in range(1, part.k):
        assert ds[d].palette != ds[_parent(part, d)].palette
        assert ds[d].light_mood != ds[_parent(part, d)].light_mood


def test_fill_district_rooms():
    rooms = [RoomSpec(f"r{i}", 0, 0) for i in range(12)]
    ds, _ = assign_district_purposes(CHAIN3, "fortress", None, "", random.Random(0))
    fill_district_rooms(ds, CHAIN3, rooms, 0)
    assert [d.entrance_room for d in ds] == ["r0", "r4", "r8"]
    assert [d.climax_room for d in ds] == ["r3", "r7", "r11"]
    assert ds[1].room_ids == ["r4", "r5", "r6", "r7"]


# ---------------------------------------------------------------------------
# Labelling and realising a hand-built two-District spec
# ---------------------------------------------------------------------------

def _rooms():
    """Eight rooms in a chain, 0-3 District 0 and 4-7 District 1, paced as the
    layout would (one climax per District)."""
    rooms = []
    for i in range(8):
        r = RoomSpec(f"room_{i}", center_x=i * 300.0, center_y=0.0)
        r.graph_depth = i
        r.district = 0 if i < 4 else 1
        r.role = {0: "entrance", 3: "climax", 7: "climax"}.get(i, "standard")
        rooms.append(r)
    return rooms


def _build(districts, thresholds=((3, 4),), overrides=None, rooms=None):
    spec = ZoneSpec(name="t")
    rooms = rooms or _rooms()
    rng = random.Random(7)
    semantics.label_rooms(spec, rooms, rng, archetype="fortress",
                          overrides=overrides, districts=districts)
    for i, r in enumerate(rooms):
        spec.rooms.append(r)
        spec.lights.append(LightSpec(f"l{i}", r.center_x, r.center_y, 20.0))
    semantics.realize_semantics(spec, rng, districts=districts,
                                thresholds=list(thresholds))
    return spec


def _ends_differ(spec, a, b):
    ra, rb = spec.rooms[a], spec.rooms[b]
    la, lb = spec.lights[a], spec.lights[b]
    mats = {ra.floor_material, ra.wall_material} != {rb.floor_material, rb.wall_material}
    light = any(abs(x - y) > 1e-6 for x, y in zip((la.r, la.g, la.b), (lb.r, lb.g, lb.b)))
    return mats, light


def _two(p0, p1):
    two = Partition(k=2, requested=2, assign=[0] * 4 + [1] * 4,
                    edges=[(i, i + 1) for i in range(7)], thresholds=[(3, 4)])
    ds, _ = assign_district_purposes(two, p0, [p0, p1], "", random.Random(0))
    return ds


@pytest.mark.parametrize("p0", sorted(semantics.ARCHETYPES))
def test_threshold_ends_differ_for_every_purpose_pair(p0):
    for p1 in sorted(semantics.ARCHETYPES):
        spec = _build(_two(p0, p1))
        assert _ends_differ(spec, 3, 4) == (True, True), (p0, p1)
        assert spec.rooms[0].room_theme == p0 and spec.rooms[4].room_theme == p1


@pytest.mark.parametrize("purpose", sorted(semantics.ARCHETYPES))
def test_threshold_ends_differ_with_a_pinned_purpose(purpose):
    two = Partition(k=2, requested=2, assign=[0] * 4 + [1] * 4,
                    edges=[(i, i + 1) for i in range(7)], thresholds=[(3, 4)])
    ds, _ = assign_district_purposes(two, purpose, None, "", random.Random(0), pinned=True)
    spec = _build(ds)
    assert _ends_differ(spec, 3, 4) == (True, True)
    assert spec.rooms[4].floor_material.endswith(f"{purpose}_abandoned_floor")


def test_hand_built_districts_with_one_palette_are_separated():
    ds = [DistrictSpec(id=0, purpose="tomb"), DistrictSpec(id=1, purpose="tomb")]
    spec = _build(ds)
    assert _ends_differ(spec, 3, 4) == (True, True)
    assert ds[1].palette == "tomb_abandoned" and ds[1].light_mood == "dim"


def test_threshold_light_rule_dims_a_matching_child():
    """Different palettes, but the two end rooms would light the same: the
    child end is dimmed."""
    rooms = _rooms()
    rooms[4].graph_depth = rooms[3].graph_depth
    rooms[3].role = "standard"
    overrides = {"room_3": "passage", "room_4": "passage"}
    spec = _build(_two("temple", "tomb"), overrides=overrides, rooms=rooms)
    assert _ends_differ(spec, 3, 4) == (True, True)
    assert spec.lights[4].r < spec.lights[3].r


def test_label_rooms_per_district_by_in_district_depth():
    spec = _build(_two("fortress", "temple"))
    types = [r.semantic_type for r in spec.rooms]
    assert spec.dungeon_theme == "fortress"
    assert types[0] == "gatehouse" and types[3] == "throne"
    assert types[4] == "entry_hall"           # District 1's entrance
    assert types[7] == "inner_sanctum"        # District 1's climax
    assert [r.boss for r in spec.rooms] == [i in (3, 7) for i in range(8)]
    assert all(t in semantics.ARCHETYPES["temple"].arc for t in types[5:7])


def test_abandoned_variant_material_is_distinct_and_desaturated():
    spec = _build([DistrictSpec(id=0, purpose="fortress"),
                   DistrictSpec(id=1, purpose="fortress", palette="fortress_abandoned")])
    base = spec.materials[spec.rooms[0].floor_material]
    var = spec.materials[spec.rooms[4].floor_material]
    assert base.name != var.name and base.texture != var.texture
    spread = lambda c: max(c) - min(c)
    assert spread(var.color) < spread(base.color)
    assert sum(var.color) < sum(base.color)


# ---------------------------------------------------------------------------
# One District: unchanged (Req 7)
# ---------------------------------------------------------------------------

def _single(districts_arg, realize_arg, archetype):
    spec = ZoneSpec(name="t")
    rooms = _rooms()
    for r in rooms:
        r.district = 0
    rooms[3].role = "standard"
    rng = random.Random(11)
    kw = {} if districts_arg == "absent" else {"districts": districts_arg}
    semantics.label_rooms(spec, rooms, rng, archetype=archetype, **kw)
    for i, r in enumerate(rooms):
        spec.rooms.append(r)
        spec.lights.append(LightSpec(f"l{i}", r.center_x, r.center_y, 20.0))
    kw = {} if realize_arg == "absent" else {"districts": realize_arg}
    semantics.realize_semantics(spec, rng, **kw)
    return spec.to_dict(), rng.random()


@pytest.mark.parametrize("archetype", ["fortress", "war_city", "sunken_ruin"])
def test_one_district_is_unchanged(archetype):
    want = _single("absent", "absent", archetype)
    assert _single(None, None, archetype) == want
    one = [DistrictSpec(id=0, purpose="tomb")]
    assert _single(one, one, archetype) == want


def test_new_palettes_only_in_multi_district_zones():
    for name in ("war_city", "warren", "corrupted_sanctum", "mine_delve"):
        assert name not in semantics._THEME_PALETTES
        d, _ = _single("absent", "absent", name)
        assert not any(name in m for m in d["materials"])
