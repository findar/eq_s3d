"""Step 35 task 5: the wide, flaring Mouth (Req 6). The width is drawn 32-96 u at the race's
scale (archive decision 2), its height 0.25-1.97 times that (stock mouths), the Tunnel flares
to both, and the Mouth is stitched to the terrain
grid with the Rock_Cover kept and every flare ramp subdivided. The built gate (every room from
the Spawn and back) runs in ``test_outdoor_dungeon_build.py`` and the gate sweeps."""

import collections
import statistics

import numpy as np
import pytest

from analyzer.traverse import (AgentModel, _faces_in_room, build_walk_surface, directed_reach,
                               find_drops, seed_face_for)
from generators import outdoor_dungeon as od
from generators.geometry import MAX_SEG_RISE

#: (seed, race): plans whose drawn Mouth fits wider than a cell.
CASES = [(1, ""), (2, ""), (3, ""), (4, "ogre"), (2, "giant")]


def test_width_is_drawn_in_stocks_range():
    """Archive decision 2: 48 u with no seed; drawn 32-96 u with 48 the median, at the race's
    scale where its Tunnel is taller (a giant's 55 u over 15 u), never smaller."""
    lo, hi = od.MOUTH_WIDTH_RANGE
    assert od.draw_mouth_width(None) == od.MOUTH_WIDTH == 48.0
    draws = [od.draw_mouth_width(s) for s in range(400)]
    assert all(lo <= w <= hi for w in draws)
    assert 44.0 <= statistics.median(draws) <= 52.0
    assert od.draw_mouth_width(7) == od.draw_mouth_width(7)
    assert od.mouth_scale("giant") == pytest.approx(55.0 / 15.0)
    assert od.mouth_scale("kobold") == 1.0
    assert od.draw_mouth_width(7, "giant") == pytest.approx(od.draw_mouth_width(7) * 55.0 / 15.0)


def _key(v):
    return (round(v.x, 3), round(v.y, 3), round(v.z, 3))


@pytest.fixture(scope="module", params=CASES, ids=lambda c: f"{c[0]}-{c[1] or 'human'}")
def built(request):
    seed, race = request.param
    kwargs = {"dungeon_race": race} if race else {}
    spec = od.outdoor_dungeon_spec("mouth", seed, **kwargs)
    host = od.build_wilderness_ter(spec, "mouth", 1)
    ter = od.build_outdoor_dungeon_ter(spec, "mouth", 1)
    grid = od._host_grid(spec, host)
    e = od.Entrance.from_dict(spec.wilderness[od.DUNGEON_KEY]["entrance"])
    return spec, host, ter, grid, e


def test_the_mouth_is_wide_and_recorded(built):
    """The Mouth is wider than the Tunnel that flares to it, inside the race's drawn range,
    and the sidecar records its width."""
    spec, _host, _ter, grid, e = built
    scale = od.mouth_scale(spec.dungeon_race or "")
    g = od.mouth_geometry(grid, e)
    assert e.mouth is not None
    assert g.width > g.door[1] - g.door[0]
    assert od.MOUTH_WIDTH_RANGE[0] * scale * od.MOUTH_SHRINK - od.MIN_CHEEK <= g.width
    assert g.width <= od.MOUTH_WIDTH_RANGE[1] * scale + 2 * od.MIN_CHEEK
    mouth = od.sidecar_block(spec)["entrances"][0]["mouth"]
    assert mouth["width"] == pytest.approx(g.width)
    assert mouth["tunnel_width"] == pytest.approx(g.door[1] - g.door[0])
    # The flare spreads at most MOUTH_FLARE a side.
    spread = max(g.door[0] - g.opening[0], g.opening[1] - g.door[1])
    assert spread <= od.MOUTH_FLARE * abs(g.portal - g.throat) + 1e-6


def test_the_mouth_is_stitched_and_covered(built):
    """Every edge of the Mouth's triangles is shared with exactly one other triangle
    (terrain, another Mouth piece or the flare's end); its floor and the Apron's edge sit at
    the Entrance floor; the portal's rock face keeps the Rock_Cover over the opening."""
    _spec, host, ter, grid, e = built
    count = collections.Counter()
    for p in ter.polygons:
        ks = [_key(ter.vertices[i]) for i in (p.v1, p.v2, p.v3)]
        for a, b in ((0, 1), (1, 2), (2, 0)):
            count[frozenset((ks[a], ks[b]))] += 1
    faces = od.mouth_faces(host, e, grid)
    for k in faces:
        p = ter.polygons[k]
        ks = [_key(ter.vertices[i]) for i in (p.v1, p.v2, p.v3)]
        for a, b in ((0, 1), (1, 2), (2, 0)):
            assert count[frozenset((ks[a], ks[b]))] == 2, (k, ks[a], ks[b])
    g = od.mouth_geometry(grid, e)
    lo, hi = g.cols
    for c in range(lo, hi + 1):
        v = ter.vertices[np.ravel_multi_index(grid.ij(e.axis, e.portal + e.outward, c),
                                              (grid.nx, grid.ny))]
        assert v.z == e.floor
        assert grid.z[grid.ij(e.axis, e.portal, c)] >= e.floor + g.heights[1] + od.ROCK_COVER - 1e-6
    assert od._tunnel_covered(grid, e, od.ROCK_COVER)


def test_the_flare_ramp_is_subdivided(built):
    """Every floor triangle of the Tunnel and its flare rises at most MAX_SEG_RISE, so the
    traverse agent can climb it (lessons-learned "A ramp must be SUBDIVIDED")."""
    _spec, host, ter, grid, e = built
    g = od.mouth_geometry(grid, e)
    lo_t, hi_t = sorted((e.wall, g.portal))
    start = od.mouth_faces(host, e, grid).stop
    floors = 0
    for p in ter.polygons[start:]:
        vs = [ter.vertices[i] for i in (p.v1, p.v2, p.v3)]
        run = [(v.x, v.y)[e.axis] for v in vs]
        across = [(v.x, v.y)[1 - e.axis] for v in vs]
        if not (min(run) >= lo_t - 1e-6 and max(run) <= hi_t + 1e-6
                and min(across) >= g.opening[0] - 1e-6 and max(across) <= g.opening[1] + 1e-6):
            continue
        if not all(v.nz > 0.5 for v in vs):
            continue                                     # a wall or a ceiling
        floors += 1
        assert max(v.z for v in vs) - min(v.z for v in vs) <= MAX_SEG_RISE + 1e-6
    assert floors


def test_walkable_both_ways(built):
    """The agent walks from the outdoor Spawn through the Mouth to every room, and back out
    (the gate's both-ways reach)."""
    spec, _host, ter, _grid, _e = built
    agent = AgentModel()
    surf = build_walk_surface(ter, agent)
    seed = seed_face_for(surf, spec.safe_point)
    both, _forward = directed_reach(surf, seed, find_drops(surf, agent))
    for room in spec.rooms:
        assert set(_faces_in_room(surf, room).tolist()) & both, room.id


def test_height_is_drawn_in_stocks_range():
    """Stock rock mouths 32-96 u wide stand 0.25/0.61/1.97 of their width tall (p10/p50/p90):
    0.61 with no seed, else drawn in that range with 0.61 the median."""
    lo, hi = od.MOUTH_RATIO_RANGE
    assert od.draw_mouth_ratio(None) == od.MOUTH_RATIO == 0.61
    draws = [od.draw_mouth_ratio(s) for s in range(400)]
    assert all(lo <= r <= hi for r in draws)
    assert 0.55 <= statistics.median(draws) <= 0.67
    # Tallest first, never under the Tunnel's height; the one-cell Mouth keeps the Tunnel's.
    assert od._mouth_heights(48.0, 0.61, 15.0) == [pytest.approx(29.28),
                                                     pytest.approx(22.14), None]
    assert od._mouth_heights(48.0, 0.25, 15.0) == [None]
    assert od._mouth_heights(None, 0.61, 15.0) == [None]


def test_the_ceiling_flares_to_the_mouths_height(built):
    """The Mouth stands its drawn height (or lower, where the hill can't cover it), never
    under the Tunnel's; the ceiling rises from the Tunnel's height at the throat to it at the
    portal, at most MOUTH_FLARE a unit of run; the sidecar records both."""
    spec, _host, ter, grid, e = built
    g = od.mouth_geometry(grid, e)
    tunnel, portal = g.heights
    assert tunnel == e.height and portal >= tunnel
    mouth = od.sidecar_block(spec)["entrances"][0]["mouth"]
    assert mouth["height"] == pytest.approx(portal) and mouth["tunnel_height"] == e.height
    assert portal - tunnel <= od.MOUTH_FLARE * abs(g.portal - g.throat) + 1e-6
    assert g.height(g.throat) == pytest.approx(tunnel) and g.height(g.portal) == portal
    # The flare's ceiling meets the portal's lintel: a ceiling vertex at the opening's height.
    lintel = e.floor + portal
    assert any(abs((v.x, v.y)[e.axis] - g.portal) < 1e-6 and abs(v.z - lintel) < 1e-6
               and v.nz < -0.5 for v in ter.vertices)


def test_a_portal_the_hill_cant_cover_is_lowered():
    """The cover fallback: asked for a Mouth five times its width tall (no hill covers that),
    the planner lowers it until the Rock_Cover holds, never under the Tunnel's height."""
    import importlib.util
    from pathlib import Path

    from generators import stages

    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("record_worlds", root / "scripts" / "record_worlds.py")
    rw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rw)
    world = rw.load_world("outdoor_w")
    hill = world.socket("hill0")
    fields = {"name": "d", "room_count": od.DEFAULT_ROOMS, "mouth_width": 48.0,
              "mouth_ratio": 5.0}
    att = stages.attach_rooms(world, hill, fields, world.recipe["seed"])
    e = att.entrance
    grid = od.socket_grid(hill, world.terrain)
    g = od.mouth_geometry(grid, e)
    assert e.height <= g.heights[1] < 5.0 * g.width
    assert od._tunnel_covered(grid, e, hill.ground["rock_cover"])
    lo, hi = g.cols
    assert all(grid.z[grid.ij(e.axis, e.portal, c)] >= e.floor + g.heights[1] + od.ROCK_COVER - 1e-6
               for c in range(lo, hi + 1))