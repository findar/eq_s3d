"""Step 35 task 12: the cliff opening (Req 6). The area draws its host hill a scarp at stock's
rate (``matrix.SCARP_SHARE``), a sheer face over level ground on the approach side; the
dungeon then opens straight out of that face, its height to width drawn as stock cliff
openings measure, and falls back to a Mouth when no wall gives one. The Mouth's own checks
(stitching, cover, subdivided flare) run on cliff openings too in
``test_outdoor_dungeon_mouth.py``, whose seeds 1 and 3 draw a scarp."""

import collections
import random
import statistics

import pytest

from analyzer.traverse import (AgentModel, _faces_in_room, build_walk_surface, directed_reach,
                               find_drops, seed_face_for)
from generators import mapview
from generators import outdoor_dungeon as od
from generators.wilderness import matrix as M

#: (seed, race): hosts whose seed draws a scarp.
CASES = [(1, ""), (3, ""), (1, "giant"), (7, "dragon")]


def test_scarp_is_drawn_at_stocks_share():
    """Archive decision 2's widest ways per interior: cliff opening 46 against mouth 85, so
    about 1 in 3, on a stream of its own; the default host asks for the draw."""
    assert M.SCARP_SHARE == pytest.approx(46 / 131)
    assert M.DEFAULT_HOST_HILL.scarp is None
    assert od.host_for(12, "giant")[0].scarp is None
    drawn = [random.Random(f"scarp:{s}").random() < M.SCARP_SHARE for s in range(1, 1001)]
    assert 0.30 <= statistics.mean(drawn) <= 0.40


def test_the_landform_records_its_scarp():
    """The placed Landform says whether it has a scarp; a record without one is as before."""
    placed = M.Landform(kind="hill", radius=250.0, relief=120.0, flank=300.0, approach="E",
                        scarp=True)
    assert M.Landform.from_dict(placed.to_dict()) == placed
    plain = M.Landform(kind="hill", radius=250.0, relief=120.0, flank=300.0, approach="E")
    assert "scarp" not in plain.to_dict()
    assert M.Landform.from_dict(plain.to_dict()).scarp is False
    assert M.Landform.from_dict(M.DEFAULT_HOST_HILL.to_dict()) == M.DEFAULT_HOST_HILL


@pytest.fixture(scope="module", params=CASES, ids=lambda c: f"{c[0]}-{c[1] or 'human'}")
def built(request):
    seed, race = request.param
    kwargs = {"dungeon_race": race} if race else {}
    spec = od.outdoor_dungeon_spec("cliff", seed, **kwargs)
    host = od.build_wilderness_ter(spec, "cliff", 1)
    ter = od.build_outdoor_dungeon_ter(spec, "cliff", 1)
    grid = od._host_grid(spec, host)
    e = od.Entrance.from_dict(spec.wilderness[od.DUNGEON_KEY]["entrance"])
    return spec, host, ter, grid, e


def test_a_scarp_host_gets_a_cliff_opening(built):
    """The host's scarp is recorded, the Entrance is a cliff opening, and the sidecar and
    the map say so."""
    spec, _host, _ter, _grid, e = built
    assert M.Landform.from_dict(spec.wilderness["landform"]).scarp is True
    assert e.kind == od.KIND_CLIFF
    assert spec.wilderness[od.DUNGEON_KEY]["entrance"]["kind"] == od.KIND_CLIFF
    assert od.sidecar_block(spec)["entrances"][0]["kind"] == od.KIND_CLIFF
    svg = mapview.render_map_svg(spec)
    assert 'class="way-in" data-kind="cliff_opening"' in svg and ">Cliff opening<" in svg


def test_it_opens_straight_out_of_a_sheer_face(built):
    """No approach trench: the Apron lowers nothing by more than CLIFF_DIG, the ground in
    front is level with the floor for three rows, and the face over the portal stands at
    least stock's p10 (90 u within 24 u of the opening) over the floor."""
    _spec, _host, _ter, grid, e = built
    dug = grid.z - od._apron(grid, e)[0]
    assert float(dug.max()) <= od.CLIFF_DIG
    g = od.mouth_geometry(grid, e)
    lo, hi = g.cols
    for c in range(lo, hi + 1):
        assert grid.z[grid.ij(e.axis, e.portal, c)] - e.floor >= 90.0
        for k in (1, 2, 3):
            assert abs(grid.z[grid.ij(e.axis, e.portal + k * e.outward, c)] - e.floor) <= 3.0
    assert e.height <= g.heights[1]
    assert od._tunnel_covered(grid, e, od.ROCK_COVER)


def test_cliff_opening_is_stitched(built):
    """Every edge of the opening's triangles is shared by exactly two triangles."""
    _spec, host, ter, grid, e = built

    def key(v):
        return (round(v.x, 3), round(v.y, 3), round(v.z, 3))

    count = collections.Counter()
    for p in ter.polygons:
        ks = [key(ter.vertices[i]) for i in (p.v1, p.v2, p.v3)]
        for a, b in ((0, 1), (1, 2), (2, 0)):
            count[frozenset((ks[a], ks[b]))] += 1
    for k in od.mouth_faces(host, e, grid):
        p = ter.polygons[k]
        ks = [key(ter.vertices[i]) for i in (p.v1, p.v2, p.v3)]
        for a, b in ((0, 1), (1, 2), (2, 0)):
            assert count[frozenset((ks[a], ks[b]))] == 2, (k, ks[a], ks[b])


def test_walkable_both_ways(built):
    """From the outdoor Spawn through the cliff opening to every room, and back out."""
    spec, _host, ter, _grid, _e = built
    agent = AgentModel()
    surf = build_walk_surface(ter, agent)
    seed = seed_face_for(surf, spec.safe_point)
    both, _forward = directed_reach(surf, seed, find_drops(surf, agent))
    for room in spec.rooms:
        assert set(_faces_in_room(surf, room).tolist()) & both, room.id


def test_cliff_ratio_is_drawn_in_stocks_range():
    """Stock cliff openings 32-96 u wide stand 0.48/1.65/4.43 of their width tall."""
    lo, hi = od.CLIFF_RATIO_RANGE
    assert od.draw_cliff_ratio(None) == od.CLIFF_RATIO == 1.65
    draws = [od.draw_cliff_ratio(s) for s in range(400)]
    assert all(lo <= r <= hi for r in draws)
    assert 1.5 <= statistics.median(draws) <= 1.8


def test_no_cliff_opening_falls_back_to_a_mouth(monkeypatch):
    """A scarp that gives no cliff opening (here none may dig at all, CLIFF_DIG below zero)
    gets a Mouth; a host with no scarp always does. A Mouth's record carries no kind."""
    monkeypatch.setattr(od, "CLIFF_DIG", -1.0)
    spec = od.outdoor_dungeon_spec("fallback", 1)
    assert M.Landform.from_dict(spec.wilderness["landform"]).scarp is True
    entrance = spec.wilderness[od.DUNGEON_KEY]["entrance"]
    assert "kind" not in entrance
    assert od.sidecar_block(spec)["entrances"][0]["kind"] == od.KIND_MOUTH
    monkeypatch.undo()
    plain = od.outdoor_dungeon_spec("plain", 2)
    assert M.Landform.from_dict(plain.wilderness["landform"]).scarp is False
    assert "kind" not in plain.wilderness[od.DUNGEON_KEY]["entrance"]
