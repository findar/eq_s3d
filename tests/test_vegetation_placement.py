"""Tree placement (trees spec task 4, Requirements 4 and 5).

Properties over seeds x Rim declarations x Density_Levels, on synthesized
landscapes and their built TERs (no full build):

- T2: every Trunk_Disc grown by Tree_Clearance lies on Eligible_Ground, and
  Trunk_Discs are at least Tree_Clearance apart (Req 4.1-4.3);
- T3: Grove_Ratio in [0.45, 0.85], density within +-25 % unless capped, species
  share within +-15 points, on zones with >= 40 trees (Req 5.2, 5.5, 5.6);
- T4: Z is the TER surface under the tree, and the buried trunk reaches 2 u
  below the surface across the whole disc (Req 5.3).

The checks re-derive what they test (triangle planes, node types, distances)
rather than reusing the placement's own helpers.
"""

import math

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from scipy.spatial import cKDTree

from generators.vegetation.kit import load_vegetation_kit
from generators.vegetation.placement import (
    SPAWN_CLEARING,
    TREE_CLEARANCE,
    grove_ratio,
    place_trees,
)
from generators.wilderness.build import (
    build_wilderness_ter,
    synthesize_landscape,
    wilderness_spec,
)
from tests.pbt_helpers import scaled

#: models.TRUNK_SINK: the trunk reaches this far below the origin at scale 1.
TRUNK_SINK = 12.0

KIT = load_vegetation_kit("plains_grassland")
EDGES = [None, {"N": "zoneline", "E": "river"},
         {"N": "mountain", "S": "zoneline", "W": "river"},
         {"E": "zoneline", "W": "zoneline"}]

PLACE_SETTINGS = settings(max_examples=scaled(15), deadline=None,
                          suppress_health_check=[HealthCheck.too_slow])

zones = st.tuples(st.integers(0, 2**31 - 1), st.sampled_from(EDGES),
                  st.sampled_from(["sparse", "normal", "dense"]))


def _zone(seed, edges, level):
    spec = wilderness_spec("t", seed, edges)
    ter = build_wilderness_ter(spec, "ter_t.ter", 2)
    land = synthesize_landscape(seed, edges)
    p = place_trees(land, ter, KIT, level, seed ^ 0x5EED)
    return spec, ter, land, p


def _grid(land):
    s = land.synth
    return np.asarray(s.node_type), float(s.resolution), s.origin, s.heights.shape


def _plane_z(ter, ny, x, y, res, origin):
    """Z of the TER triangle containing (x, y), from that polygon's own corners."""
    gx, gy = (x - origin[0]) / res - 0.5, (y - origin[1]) / res - 0.5
    i, j = int(math.floor(gx)), int(math.floor(gy))
    q = i * (ny - 1) + j
    for poly in ter.polygons[2 * q: 2 * q + 2]:
        P = np.array([[ter.vertices[k].x, ter.vertices[k].y, ter.vertices[k].z]
                      for k in (poly.v1, poly.v2, poly.v3)])
        a, b, c = P
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        l1 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / den
        l2 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / den
        l3 = 1 - l1 - l2
        if min(l1, l2, l3) >= -1e-9:
            n = np.cross(b - a, c - a)
            return float(l1 * a[2] + l2 * b[2] + l3 * c[2]), abs(n[2]) / np.linalg.norm(n)
    raise AssertionError(f"no TER triangle under ({x}, {y})")


@PLACE_SETTINGS
@given(zone=zones)
def test_property_t2_discs_on_eligible_ground_and_clear_of_each_other(zone):
    spec, ter, land, p = _zone(*zone)
    node, res, origin, (nx, ny) = _grid(land)
    trees = p.instances
    assert trees, "every probed zone has room for trees"
    spawn = np.array(spec.safe_point[:2])

    cells = np.argwhere(np.ones_like(node, dtype=bool))
    centres = np.column_stack([origin[0] + (cells[:, 0] + 0.5) * res,
                               origin[1] + (cells[:, 1] + 0.5) * res])
    kinds = node[cells[:, 0], cells[:, 1]]
    wet = cKDTree(centres[np.isin(kinds, ("water", "river", "lava"))])
    zl_pts = centres[kinds == "zoneline_gap"]
    zl = cKDTree(zl_pts) if len(zl_pts) else None
    not_plains = cKDTree(centres[kinds != "plains"])

    for t in trees:
        reach = t.radius + TREE_CLEARANCE
        # Every point of the grown disc stands on a 30°-or-flatter TER triangle
        # whose surrounding cells are all plains.
        for a in np.linspace(0, 2 * math.pi, 16, endpoint=False):
            for rr in (0.0, reach):
                x, y = t.x + rr * math.cos(a), t.y + rr * math.sin(a)
                _, cos_slope = _plane_z(ter, ny, x, y, res, origin)
                assert cos_slope >= math.cos(math.radians(30)) - 1e-9
        assert not_plains.query([t.x, t.y])[0] >= res / 2 + reach - 1e-6
        assert np.linalg.norm(np.array([t.x, t.y]) - spawn) >= SPAWN_CLEARING
        assert wet.query([t.x, t.y])[0] >= res
        if zl is not None:
            assert zl.query([t.x, t.y])[0] >= 2 * res

    pts = np.array([[t.x, t.y] for t in trees])
    rad = np.array([t.radius for t in trees])
    for a, b in cKDTree(pts).query_pairs(2 * rad.max() + TREE_CLEARANCE):
        gap = np.linalg.norm(pts[a] - pts[b]) - rad[a] - rad[b]
        assert gap >= TREE_CLEARANCE - 1e-9


@PLACE_SETTINGS
@given(zone=zones)
def test_property_t3_groves_density_and_species_mix(zone):
    _, _, _, p = _zone(*zone)
    n = len(p.instances)
    level = zone[2]
    want = KIT.density_for(level)
    if p.capped:
        assert n < 0.75 * p.target
    else:
        assert abs(p.density - want) <= 0.25 * want
    if n >= 40:
        assert 0.45 <= grove_ratio(p.instances, p.eligible_area) <= 0.85
        wsum = sum(sp.weight for sp in KIT.species.values())
        for name, sp in KIT.species.items():
            share = sum(1 for t in p.instances if t.species == name) / n
            assert abs(share - sp.weight / wsum) <= 0.15, (name, share)


@PLACE_SETTINGS
@given(zone=zones)
def test_property_t4_trees_stand_on_the_surface_with_buried_trunks(zone):
    _, ter, land, p = _zone(*zone)
    _, res, origin, (_, ny) = _grid(land)
    for t in p.instances:
        z, _ = _plane_z(ter, ny, t.x, t.y, res, origin)
        assert t.z == pytest.approx(z, abs=1e-6)
        bottom = t.z - TRUNK_SINK * t.scale
        for a in np.linspace(0, 2 * math.pi, 12, endpoint=False):
            sz, _ = _plane_z(ter, ny, t.x + t.radius * math.cos(a),
                             t.y + t.radius * math.sin(a), res, origin)
            assert bottom <= sz - 2.0
        sp = KIT.species[t.species]
        assert sp.scale[0] <= t.scale <= sp.scale[1]
        assert -math.pi <= t.yaw < math.pi


def test_none_level_and_missing_kit_place_nothing():
    spec = wilderness_spec("t", 5, None)
    ter = build_wilderness_ter(spec, "ter_t.ter", 2)
    land = synthesize_landscape(5, None)
    assert place_trees(land, ter, KIT, "none", 1).instances == []
    assert place_trees(land, ter, None, "normal", 1).instances == []


def test_placement_is_pure_and_leaves_the_ter_alone():
    spec = wilderness_spec("t", 9, {"N": "zoneline"})
    ter = build_wilderness_ter(spec, "ter_t.ter", 2)
    land = synthesize_landscape(9, {"N": "zoneline"})
    before = ter.to_bytes()
    a = place_trees(land, ter, KIT, "dense", 42)
    b = place_trees(land, ter, KIT, "dense", 42)
    assert a.instances == b.instances
    assert place_trees(land, ter, KIT, "dense", 43).instances != a.instances
    assert ter.to_bytes() == before


def test_denser_levels_place_more_trees():
    spec = wilderness_spec("t", 3, None)
    ter = build_wilderness_ter(spec, "ter_t.ter", 2)
    land = synthesize_landscape(3, None)
    counts = [len(place_trees(land, ter, KIT, lv, 7).instances)
              for lv in ("none", "sparse", "normal", "dense")]
    assert counts == sorted(counts) and counts[0] == 0 and counts[1] > 0
