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
