"""Outdoor-dungeon task 4: the Envelope under the built host terrain."""

import math

import numpy as np
import pytest

from generators import outdoor_dungeon as od
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
    assert env.centre == pytest.approx((cx, cy), abs=1e-6)
    for x, y in env.footprint:
        assert math.hypot(x - cx, y - cy) == pytest.approx(reach)
    fx, fy = od.approach_foot(lf)
    assert env.floor_limit == pytest.approx(float(env.surface(fx, fy)) - od.FLOOR_DEPTH)
    # The hill stands over its foot: there is a room's height of band at its middle.
    assert float(env.top_at(cx, cy)) - env.floor_limit > od.ROOM_HEIGHT


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
