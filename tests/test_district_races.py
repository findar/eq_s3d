"""A race per District (district races spec Requirement 4, task 4).

A District may carry its own race (``DistrictSpec.race``, written only when set):
its rooms and corridors are sized by that race's body height H, and a corridor
between two Districts (the Threshold) by the smaller H. Districts without a race
of their own, and an unknown race, leave the zone as it was.
"""

import pytest

from generators import semantics
from generators.districts import district_races
from generators.layout import LayoutGenerator
from generators.zone_spec import DistrictSpec, ZoneSpec

GIANT_GOBLIN = [{"purpose": "fortress", "race": "giant"},
                {"purpose": "warren", "race": "goblin"}]


def _gen(layout, seed, plan, n=10):
    gen = LayoutGenerator("dungeon", seed=seed, engine=layout)
    spec = gen.generate(f"dr_{layout}_{seed}", room_count=n, districts=True,
                        district_plan=plan)
    return gen, spec


def test_race_written_only_when_set():
    spec = ZoneSpec(name="z")
    spec.districts = [DistrictSpec(id=0, purpose="fortress"),
                      DistrictSpec(id=1, purpose="warren", race="goblin")]
    out = spec.to_dict()["districts"]
    assert "race" not in out[0]
    assert out[1]["race"] == "goblin"
    back = ZoneSpec.from_dict(spec.to_dict())
    assert [d.race for d in back.districts] == ["", "goblin"]


def test_unknown_race_is_noted_and_falls_back():
    races, notes = district_races(["fortress", {"purpose": "warren", "race": "Giant"},
                                   {"purpose": "tomb", "race": "elf"}], 3)
    assert races == ["", "giant", ""]
    assert len(notes) == 1 and notes[0].startswith("district_race_unknown: 'elf'")


@pytest.mark.parametrize("layout", ["classic", "graph"])
def test_unknown_race_builds_the_raceless_zone(layout):
    _, plain = _gen(layout, 2001, ["fortress", "warren"])
    gen, odd = _gen(layout, 2001, [{"purpose": "fortress", "race": "elf"}, "warren"])
    assert odd.to_dict() == plain.to_dict()
    assert any(w.startswith("district_race_unknown") for w in gen.warnings)


@pytest.mark.parametrize("layout,seed", [("classic", 2000), ("graph", 2003)])
def test_district_rooms_and_corridors_take_their_race(layout, seed):
    _, spec = _gen(layout, seed, GIANT_GOBLIN)
    race = {d.id: d.race or "default" for d in spec.districts}
    assert race[0] == "giant" and race[1] == "goblin"
    rooms = {r.id: r for r in spec.rooms}
    for r in spec.rooms:
        (s0, s1), (h0, h1) = semantics.room_bands(race[r.district])
        assert s0 - 1e-6 <= min(r.width, r.depth) and max(r.width, r.depth) <= s1 + 1e-6
        assert h0 - 1e-6 <= r.height <= h1 + 1e-6
    for c in spec.corridors:
        a, b = rooms[c.from_room], rooms[c.to_room]
        small = min((race[a.district], race[b.district]), key=semantics.body_height)
        assert (c.width, c.height) == pytest.approx(semantics.corridor_size(small))
        assert c.threshold == (a.district != b.district)
        # The corridor clears both doorways: no taller than either room.
        assert c.height <= min(a.height, b.height) + 1e-6
    assert any(c.threshold for c in spec.corridors)


# --- Hall length per District (Req 5, task 5) ---------------------------------

def test_only_giants_carry_a_hall_default():
    assert semantics.race_hall_length("giant") == 3.0
    assert semantics.race_hall_length("Giant") == 3.0
    for race in ("", "default", "goblin", "ogre", "dragon", "elf"):
        assert semantics.race_hall_length(race) == 1.0


def test_spring_runs_none_and_shared_run_are_today():
    from generators.topology import embed
    order = ["a", "b", "c"]
    edges = [("a", "b"), ("b", "c")]
    pos = {"a": (0.0, 0.0), "b": (60.0, 0.0), "c": (60.0, 70.0)}
    half = {r: (10.0, 10.0) for r in order}
    nodes = {r: embed.Storey(0, 0.0, 15.0) for r in order}
    plain = embed.spring_relax(order, edges, pos, half, nodes, 36.0, 19.0)
    same = embed.spring_relax(order, edges, pos, half, nodes, 36.0, 19.0,
                              runs={frozenset(e): 36.0 for e in edges})
    assert plain == same
    long = embed.spring_relax(order, edges, pos, half, nodes, 36.0, 19.0,
                              runs={frozenset(("a", "b")): 108.0})
    # a-b runs east: its rooms rest one run of their own apart, b-c at the shared one.
    assert abs(long["b"][0] - long["a"][0]) - 20.0 == pytest.approx(108.0, abs=1.0)
    assert long["c"][1] - long["b"][1] - 20.0 == pytest.approx(36.0, abs=1.0)


def _halls(spec):
    by = {r.id: r for r in spec.rooms}
    race = {d.id: d.race for d in spec.districts}
    out = {}
    for c in spec.corridors:
        a, b = by[c.from_room], by[c.to_room]
        if a.district == b.district:
            out.setdefault(race[a.district], []).append(c)
    return out


@pytest.mark.parametrize("layout,seed", [("classic", 2000), ("graph", 2000)])
def test_giant_district_halls_lengthen_goblin_halls_hold(layout, seed, monkeypatch):
    import statistics
    from scripts.grid_score import corridor_length
    _, spec = _gen(layout, seed, GIANT_GOBLIN, n=16)
    monkeypatch.setitem(semantics.RACE_HALL_LENGTH, "giant", 1.0)
    _, flat = _gen(layout, seed, GIANT_GOBLIN, n=16)
    assert spec.to_dict() != flat.to_dict()

    def p50(s, race):
        by = {r.id: r for r in s.rooms}
        return statistics.median(corridor_length(c, by) for c in _halls(s)[race])
    assert p50(spec, "giant") > 2.0 * p50(flat, "giant")


def test_no_default_leaves_a_raced_zone_alone(monkeypatch):
    """Every default 1: the hall pass draws nothing and moves nothing."""
    calls = []
    monkeypatch.setattr(LayoutGenerator, "_apply_district_halls",
                        lambda *a, **k: calls.append(a))
    _gen("graph", 2003, [{"purpose": "fortress", "race": "ogre"},
                         {"purpose": "warren", "race": "goblin"}])
    assert not calls
