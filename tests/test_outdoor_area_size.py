"""Step 35 task 6, the outdoor dungeon's half (Req 2): its zone from the plan's Size, never
smaller than the host it holds (archive decision 4), non-square at stock's aspect; and a
non-square host zone keeps task 12's scarp and cliff opening (the face read on the
terrain's own grid, where a matrix cell is 160 u, not the matrix's 150)."""

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from analyzer.traverse import (AgentModel, _faces_in_room, build_walk_surface, directed_reach,
                               find_drops, seed_face_for)
from generators import outdoor_dungeon as od
from generators.wilderness import matrix as M
from generators.wilderness.build import landscape_for

HOST = M.host_zone_size(M.DEFAULT_HOST_HILL)


@pytest.mark.parametrize("size", M.SIZES + ("",))
def test_zone_holds_the_host_on_even_cells(size):
    for host in (HOST, 1800.0, 3300.0, 7500.0):
        for seed in range(200):
            w, d = M.draw_outdoor_zone_extent(size, host, seed)
            assert min(w, d) >= host
            assert (w / M.DEFAULT_CELL_SIZE) % 2 == 0 and (d / M.DEFAULT_CELL_SIZE) % 2 == 0
            if size:
                assert max(w, d) >= M.OUTDOOR_DUNGEON_SIZES[size]
            if host > M.OUTDOOR_DUNGEON_SIZES["huge"]:
                assert w == d == host     # past stock's largest: square, no extra terrain


def test_zone_is_non_square_as_stock_is():
    drawn = [M.draw_outdoor_zone_extent("", HOST, s) for s in range(400)]
    aspects = [max(e) / min(e) for e in drawn]
    lo, hi = M.OUTDOOR_DUNGEON_ASPECT_QUANTILES[0], M.OUTDOOR_DUNGEON_ASPECT_QUANTILES[-1]
    assert all(1.0 <= a <= hi + 0.1 for a in aspects)
    assert 0.4 <= sum(a > lo for a in aspects) / len(aspects) <= 0.9
    assert {e[0] > e[1] for e in drawn if e[0] != e[1]} == {True, False}


def test_the_plan_size_sets_the_zone():
    plan = ZonePlan(name="t", zone_type="outdoor_dungeon", size="huge").validate()
    spec = plan_to_spec(plan, seed=5)
    w, d = M.zone_extent(spec.wilderness["zone_size"])
    assert (w, d) == M.draw_outdoor_zone_extent("huge", HOST, 5)
    assert landscape_for(spec).matrix.shape == (round(w / 150), round(d / 150))
    # Left None (a direct call), the zone is the least that holds the host, as before.
    assert od.outdoor_dungeon_spec("t", 5).wilderness["zone_size"] == HOST


#: (seed, zone) for unset plans whose host draws a scarp, on non-square zones, the long
#: side across or along the approach: 1 E on 1200 x 1800, 3 W on 1800 x 1200, 37 N on
#: 1500 x 1200, 32 W on 1800 x 2700.
NON_SQUARE = [1, 3, 37, 32]


@pytest.fixture(scope="module", params=NON_SQUARE)
def built(request):
    seed = request.param
    spec = od.outdoor_dungeon_spec("cliff", seed, size="")
    host = od.build_wilderness_ter(spec, "cliff", 1)
    ter = od.build_outdoor_dungeon_ter(spec, "cliff", 1)
    grid = od._host_grid(spec, host)
    e = od.Entrance.from_dict(spec.wilderness[od.DUNGEON_KEY]["entrance"])
    return spec, ter, grid, e


def test_non_square_scarp_host_opens_out_of_its_face(built):
    """Task 12's cliff-opening checks on a non-square zone: the scarp is drawn and the
    Entrance is a cliff opening whose face stands 90 u over a floor level with the ground
    for three rows out, the foot read where the face is on the terrain."""
    spec, _ter, grid, e = built
    w, d = M.zone_extent(spec.wilderness["zone_size"])
    assert w != d
    land = landscape_for(spec)
    assert land.synth.node_type.shape == (round(w / 150) * 4, round(d / 150) * 4)
    assert M.Landform.from_dict(spec.wilderness["landform"]).scarp is True
    assert e.kind == od.KIND_CLIFF
    # The foot: off the face, and a cliff cell within two fine cells back toward the hill.
    lf = land.matrix.landform
    dx, dy = od._SIDE_STEP[lf.approach]
    fx, fy = od.scarp_foot(land)
    (ox, oy), res = land.synth.origin, land.synth.resolution
    nt = land.synth.node_type
    i, j = int((fx - ox) // res), int((fy - oy) // res)
    assert nt[i, j] != "cliff"
    assert any(nt[i - k * int(dx), j - k * int(dy)] == "cliff" for k in (1, 2))
    assert float((grid.z - od._apron(grid, e)[0]).max()) <= od.CLIFF_DIG
    lo, hi = od.mouth_geometry(grid, e).cols
    for c in range(lo, hi + 1):
        assert grid.z[grid.ij(e.axis, e.portal, c)] - e.floor >= 90.0
        for k in (1, 2, 3):
            assert abs(grid.z[grid.ij(e.axis, e.portal + k * e.outward, c)] - e.floor) <= 3.0


def test_non_square_scarp_host_is_walkable_both_ways(built):
    spec, ter, _grid, _e = built
    agent = AgentModel()
    surf = build_walk_surface(ter, agent)
    both, _forward = directed_reach(surf, seed_face_for(surf, spec.safe_point),
                                    find_drops(surf, agent))
    for room in spec.rooms:
        assert set(_faces_in_room(surf, room).tolist()) & both, room.id
