"""Outdoor-dungeon task 4: the Envelope under the built host terrain."""

import math

import numpy as np
import pytest

from generators import outdoor_dungeon as od
from generators import semantics
from generators.layout import LayoutGenerator
from generators.wilderness.build import build_wilderness_ter, landscape_for, wilderness_spec
from generators.wilderness.matrix import DEFAULT_HOST_HILL, OUTDOOR_DUNGEON_ZONE_SIZE

EDGE_SETS = (None, {"N": "zoneline"}, {"E": "river", "S": "zoneline"})


def _host(seed, edges=None):
    spec = wilderness_spec("hill", seed, edges, landform=DEFAULT_HOST_HILL,
                           zone_size=OUTDOOR_DUNGEON_ZONE_SIZE)
    return spec, build_wilderness_ter(spec, "hill", 1)


def _ter_height(ter, x, y):
    """Height of the TER triangle under (x, y), by brute force over every
    polygon (independent of the grid indexing ``ter_surface`` uses)."""
    v = np.array([(p.x, p.y, p.z) for p in ter.vertices])
    tri = np.array([(p.v1, p.v2, p.v3) for p in ter.polygons])
    a, b, c = v[tri[:, 0]], v[tri[:, 1]], v[tri[:, 2]]
    det = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    l1 = ((b[:, 1] - c[:, 1]) * (x - c[:, 0]) + (c[:, 0] - b[:, 0]) * (y - c[:, 1])) / det
    l2 = ((c[:, 1] - a[:, 1]) * (x - c[:, 0]) + (a[:, 0] - c[:, 0]) * (y - c[:, 1])) / det
    l3 = 1.0 - l1 - l2
    hit = np.flatnonzero((l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9))
    k = hit[0]
    return float(l1[k] * a[k, 2] + l2[k] * b[k, 2] + l3[k] * c[k, 2])


@pytest.mark.parametrize("seed", [0, 3])
def test_surface_is_the_ter_and_footprint_the_hill(seed):
    spec, ter = _host(seed)
    env = od.host_envelope(spec, ter)
    lf = landscape_for(spec).matrix.landform
    cx, cy = lf.centre

    rng = np.random.default_rng(seed)
    reach = lf.radius + lf.flank / 2
    for _ in range(40):
        ang, rad = rng.uniform(0, 2 * math.pi), reach * math.sqrt(rng.uniform())
        x, y = cx + rad * math.cos(ang), cy + rad * math.sin(ang)
        assert float(env.surface(x, y)) == pytest.approx(_ter_height(ter, x, y), abs=1e-6)
        assert float(env.top_at(x, y)) == pytest.approx(float(env.surface(x, y)) - od.ROCK_COVER)

    assert env.rock_cover == od.ROCK_COVER
    # The footprint is the hill's disc (centre and radius from the Landform)
    # clipped to the bowl's interior: every vertex is on the circle inside
    # the interior, or on a clip line inside the circle, and no vertex lies
    # in a boundary strip (graph-layout task 12: a room under the map's edge
    # reads to the bowl gate as the flood escaping).
    x0, y0, x1, y1 = od.bowl_interior(landscape_for(spec))
    on_clip = 0
    for x, y in env.footprint:
        assert x0 - 1e-6 <= x <= x1 + 1e-6 and y0 - 1e-6 <= y <= y1 + 1e-6
        d = math.hypot(x - cx, y - cy)
        clipped = min(abs(x - x0), abs(x - x1), abs(y - y0), abs(y - y1)) < 1e-6
        assert d == pytest.approx(reach) or (clipped and d < reach + 1e-6), (x, y)
        on_clip += clipped and d < reach - 1e-6
    # The default hill reaches past one side's strip on these seeds.
    assert on_clip >= 2
    fx, fy = od.approach_foot(lf)
    assert env.floor_limit == pytest.approx(float(env.surface(fx, fy)) - od.FLOOR_DEPTH)
    # The hill stands over its foot: there is a room's height of band at its
    # middle (a human's tallest room; od.ROOM_HEIGHT's 80 u before stock scale).
    tallest = semantics.room_bands("")[1][1]
    assert float(env.top_at(cx, cy)) - env.floor_limit > tallest


def test_envelope_needs_a_landform():
    spec = wilderness_spec("plain", 1, None)
    with pytest.raises(ValueError):
        od.host_envelope(spec, build_wilderness_ter(spec, "plain", 1))


def test_default_room_count_fits_every_sampled_seed():
    for seed in range(10):
        for edges in EDGE_SETS:
            spec, ter = _host(seed, edges)
            env = od.host_envelope(spec, ter)
            layout, warnings = od.layout_in_envelope("d", seed * 7 + 1, env)
            assert warnings == [], (seed, edges, warnings)
            assert len(layout.rooms) >= od.DEFAULT_ROOMS
            assert LayoutGenerator.fits(layout, env)


@pytest.mark.parametrize("seed", [8])
def test_themed_dungeon_shrinks_rooms_to_plan(seed, monkeypatch):
    """A fortress's room types and climax outgrow the Envelope's sizing; this
    seed fails to plan (rooms miss the hill, or the sunk entrance room gets
    no Tunnel) unless rooms are shrunk to a size that plans. Every room asked
    for is kept, the Tunnel opens into the entrance room. (At stock room
    scale, step 7 task 17, it is the only one of seeds 0-59 that needs the
    shrink; step 5's seeds 1, 2, 9, 10 and 12 now plan without it.)"""
    with monkeypatch.context() as m:
        m.setattr(od, "FIT_SHRINKS", 0)
        try:
            unshrunk = od.outdoor_dungeon_spec("fort", seed, room_count=4,
                                               dungeon_theme="fortress")
        except od.PLAN_ERRORS:
            unshrunk = None
        assert unshrunk is None or len(unshrunk.rooms) < 4, "seed plans without shrinking"
    spec = od.outdoor_dungeon_spec("fort", seed, room_count=4, dungeon_theme="fortress")
    assert len(spec.rooms) == 4
    data = spec.wilderness[od.DUNGEON_KEY]
    assert data["warnings"] == []
    room = od.Entrance.from_dict(data["entrance"]).room_id
    assert next(r for r in spec.rooms if r.id == room).role == "entrance"
