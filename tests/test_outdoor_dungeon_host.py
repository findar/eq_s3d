"""Step 35 task 4 (Req 5): the outdoor dungeon's host hill is sized from the plan (room
count, race) before the dungeon is laid in, and the zone grows to hold it."""

import math

import pytest

from generators.builder import ZoneBuilder

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators import outdoor_dungeon as od
from generators.wilderness.matrix import (DEFAULT_CELL_SIZE, DEFAULT_HOST_HILL, HOST_MARGIN,
                                          HOST_SIDE_RATIO, OUTDOOR_DUNGEON_ZONE_SIZE)


def test_default_plan_keeps_the_default_host():
    """Five human rooms fit the default hill: its zone and hill are as before."""
    hill, zone = od.host_for(5, "")
    assert hill == DEFAULT_HOST_HILL and zone == OUTDOOR_DUNGEON_ZONE_SIZE


@pytest.mark.parametrize("race,rooms", [("giant", 5), ("dragon", 5), ("", 30), ("ogre", 12)])
def test_host_is_stock_sized_and_inside_its_zone(race, rooms):
    """The hill region (radius + flank / 2) is the footprint plus the margin each side, at
    least 1.8 times it; the zone holds it with the default's approach and Rim (its reach
    grows the zone the same either side), in whole even cells."""
    side = od.interior_side(rooms, race)
    hill, zone = od.host_for(rooms, race)
    across = 2 * (hill.radius + hill.flank / 2)
    assert across >= max(side + 2 * HOST_MARGIN, HOST_SIDE_RATIO * side) - 1e-6
    assert (hill.relief, hill.flank) == (DEFAULT_HOST_HILL.relief, DEFAULT_HOST_HILL.flank)
    reach = hill.radius + hill.flank
    base = DEFAULT_HOST_HILL.radius + DEFAULT_HOST_HILL.flank
    assert zone / 2 - reach >= OUTDOOR_DUNGEON_ZONE_SIZE / 2 - base
    cells = zone / DEFAULT_CELL_SIZE
    assert cells == int(cells) and int(cells) % 2 == 0


def test_host_grows_with_race_and_room_count():
    assert od.host_for(5, "giant")[0].radius > od.host_for(5, "ogre")[0].radius
    assert od.host_for(12, "giant")[0].radius > od.host_for(5, "giant")[0].radius
    assert math.isclose(od.interior_side(20, "dragon") / od.interior_side(5, "dragon"), 2.0)


@pytest.mark.slow
@pytest.mark.parametrize("race,rooms,verticality,seed,zone", [
    ("", 5, "moderate", 8, 1200.0), ("troll", 8, "flat", 8, 1800.0),
    ("", 30, "flat", 4, 2400.0), ("giant", 5, "moderate", 2, 3300.0)])
def test_spawn_on_open_ground_walks_to_the_apron(tmp_path, race, rooms, verticality, seed, zone):
    """The outdoor-dungeon requirement at every host size: the Outdoor_Spawn is on open
    ground (off the hill, out past its half-relief disc) with a walkable path to the Apron:
    on the built mesh the gate walks from the Spawn through the Apron and Tunnel into the
    entrance room, and the bowl and every room pass."""
    plan = ZonePlan(name="odwalk", zone_type="outdoor_dungeon", room_count=rooms,
                    dungeon_race=race, dungeon_theme="fortress", layout="graph",
                    verticality=verticality, decor="none").validate()
    spec = plan_to_spec(plan, seed=seed)
    assert spec.wilderness["zone_size"] == zone
    hill = spec.wilderness["landform"]
    sx, sy, _sz = spec.safe_point
    cx, cy = hill["centre"]
    assert math.hypot(sx - cx, sy - cy) > hill["radius"] + hill["flank"] / 2
    result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)
    report = od.outdoor_dungeon_report(result.eqg_path, spec)
    assert report.passed, report.summary()
    first = od.Entrance.from_dict(spec.wilderness[od.DUNGEON_KEY]["entrance"]).room_id
    assert next(r for r in report.rooms if r.room_id == first).reachable


@pytest.mark.parametrize("race,seed", [("giant", 1), ("giant", 5), ("dragon", 6)])
def test_big_race_keeps_every_room(race, seed):
    """Seeds that dropped rooms on the default hill (giants 3 of 5, dragons 3) keep all
    five, and the spec records the hill and zone it was built on (the World key)."""
    plan = ZonePlan(name="odhost", zone_type="outdoor_dungeon", room_count=5,
                    dungeon_race=race, layout="graph").validate()
    spec = plan_to_spec(plan, seed=seed)
    assert len(spec.rooms) == 5
    hill, zone = od.host_for(5, race)
    assert spec.wilderness["zone_size"] == zone
    assert spec.wilderness["landform"]["radius"] == hill.radius
    assert od.area_world(spec) is getattr(spec, od.AREA_ATTR)
