"""
Host terrain: a Landform on the Design_Matrix (outdoor dungeon, task 3).

A hill (or pit) is one connected region of plains cells carrying a relief
offset, centred away from an open approach where Spawn sits. The wilderness
property tests are reused on host-hill builds by pointing their shared
``build_matrix`` at a host-hill build (1200 u zone) for a sample of seeds;
without a Landform, wilderness builds are unchanged (pinned below on the
matrix, the heights and the spec).
"""

from __future__ import annotations

import functools
import json

import numpy as np
import pytest

import tests.test_wilderness_matrix as wm
from generators.wilderness import build_matrix as package_build_matrix
from generators.wilderness.build import synthesize_landscape, wilderness_spec
from generators.wilderness.matrix import (
    DEFAULT_HOST_HILL,
    DEFAULT_SIDES,
    OUTDOOR_DUNGEON_ZONE_SIZE,
    DesignMatrix,
    EdgeConnection,
    Landform,
)
from tests import test_wilderness_bowl as wb
from tests import test_wilderness_rewrite as wr
from tests import test_wilderness_synth as ws

SEEDS = (0, 1, 7, 42, 1955208177)
EDGES = ([], [EdgeConnection("N", "zoneline")],
         [EdgeConnection("E", "river"), EdgeConnection("S", "zoneline")],
         [EdgeConnection(s, "zoneline") for s in DEFAULT_SIDES])
PIT = Landform("pit", radius=200.0, relief=-80.0, flank=200.0)


def _host(seed, edges=(), landform=DEFAULT_HOST_HILL) -> DesignMatrix:
    return package_build_matrix("plains", list(edges), seed, landform=landform,
                                zone_size=OUTDOOR_DUNGEON_ZONE_SIZE)


def _components(coords):
    coords, comps = set(coords), []
    while coords:
        stack, comp = [coords.pop()], set()
        while stack:
            c = stack.pop()
            comp.add(c)
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (c[0] + di, c[1] + dj)
                if nb in coords:
                    coords.discard(nb)
                    stack.append(nb)
        comps.append(comp)
    return comps


# ---------------------------------------------------------------------------
# The Landform itself
# ---------------------------------------------------------------------------

def test_landform_validates_kind_and_sign():
    with pytest.raises(ValueError):
        Landform("hill", radius=100, relief=-10, flank=50)
    with pytest.raises(ValueError):
        Landform("pit", radius=100, relief=10, flank=50)
    with pytest.raises(ValueError):
        Landform("mesa", radius=100, relief=10, flank=50)
    with pytest.raises(ValueError):
        Landform("hill", radius=100, relief=10, flank=50, approach="X")


def test_relief_is_full_inside_and_tapers_across_the_flank():
    lf = Landform("hill", radius=100, relief=80, flank=100)
    assert lf.relief_at(50, 0) == 80
    assert 0 < lf.relief_at(150, 0) < 80
    assert lf.relief_at(200, 0) == 0
    assert lf.relief_at(0, 300) == 0


# ---------------------------------------------------------------------------
# The matrix: one connected Landform, an open approach, Spawn facing it
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("edges", EDGES, ids=["sealed", "zoneline", "river", "open"])
def test_host_hill_is_one_connected_region_with_an_open_approach(seed, edges):
    m = _host(seed, edges)
    lf = m.landform
    assert lf is not None and lf.approach in DEFAULT_SIDES
    hill = m.landform_cells()
    assert len(_components(hill)) == 1
    # Every interior cell whose centre is inside the requested footprint is
    # raised; with a sealed rim (nothing frozen flat to taper away from) by
    # the full relief. The flank adds the margin around it.
    for i in range(1, m.nx - 1):
        for j in range(1, m.ny - 1):
            x, y = m.cell_world_center(i, j)
            if np.hypot(x - lf.centre[0], y - lf.centre[1]) <= lf.radius:
                assert m.cells[i, j].relief > 0, (i, j)
                if not edges:
                    assert m.cells[i, j].relief == lf.relief, (i, j)
    assert len(hill) > sum(
        np.hypot(*(np.subtract(m.cell_world_center(i, j), lf.centre))) <= lf.radius
        for i in range(1, m.nx - 1) for j in range(1, m.ny - 1))
    for (i, j) in hill:
        c = m.cells[i, j]
        assert c.node_type in ("plains", "cliff") and c.relief > 0
    # Spawn is on the approach side, on flat ground, with nothing in its way.
    si, sj = m.spawn
    assert m.cells[si, sj].relief == 0
    di, dj = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}[lf.approach]
    sx, sy = m.cell_world_center(si, sj)
    assert (sx - lf.centre[0]) * di + (sy - lf.centre[1]) * dj > 0
    k = 0
    while True:
        i, j = si - di * k, sj - dj * k
        if (i, j) in hill or not (0 < i < m.nx - 1 and 0 < j < m.ny - 1):
            break
        assert m.cells[i, j].node_type not in ("cliff", "lava"), (i, j)
        k += 1
    assert (i, j) in hill, "the approach from Spawn never reaches the hill"


def test_size_scales_the_grid_not_the_cell():
    m = _host(3)
    assert m.cell_size == 150.0 and m.shape == (8, 8)


def test_landform_round_trips_through_the_matrix_dict():
    m = _host(5)
    back = DesignMatrix.from_dict(json.loads(json.dumps(m.to_dict())))
    assert back.landform == m.landform
    assert back.landform_cells() == m.landform_cells()


def test_hill_backs_onto_a_mountain_side():
    edges = [EdgeConnection("N", "zoneline"), EdgeConnection("E", "river")]
    for seed in SEEDS:
        # Backed by S or W (mountains): the approach is N or E.
        assert _host(seed, edges).landform.approach in ("N", "E")


def test_approach_can_be_pinned():
    lf = Landform("hill", radius=250, relief=120, flank=200, approach="E")
    for seed in SEEDS:
        assert _host(seed, landform=lf).landform.approach == "E"


# ---------------------------------------------------------------------------
# Synth keeps the hill where the matrix put it
# ---------------------------------------------------------------------------

def _core_and_open(land):
    lf, syn, h = land.matrix.landform, land.synth, land.bowl.heights
    ii, jj = np.meshgrid(np.arange(h.shape[0]), np.arange(h.shape[1]), indexing="ij")
    x = syn.origin[0] + (ii + 0.5) * syn.resolution
    y = syn.origin[1] + (jj + 0.5) * syn.resolution
    d = np.hypot(x - lf.centre[0], y - lf.centre[1])
    core = h[d <= lf.radius]
    open_ground = h[(d > lf.radius + lf.flank) & syn.playable_interior_mask]
    return lf, core, open_ground


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("landform", [DEFAULT_HOST_HILL, PIT], ids=["hill", "pit"])
def test_synth_raises_or_sinks_the_landform_footprint(seed, landform):
    land = synthesize_landscape(seed, None, landform=landform,
                                zone_size=OUTDOOR_DUNGEON_ZONE_SIZE)
    lf, core, open_ground = _core_and_open(land)
    lift = np.median(core) - np.median(open_ground)
    # At least half the requested relief survives noise, erosion and the
    # walkability relax, in the requested direction.
    assert lift * np.sign(lf.relief) >= 0.5 * abs(lf.relief), lift


# ---------------------------------------------------------------------------
# The wilderness properties hold for host-hill builds
# ---------------------------------------------------------------------------

@pytest.fixture
def host_hill_builds(monkeypatch):
    """Point the wilderness tests' shared ``build_matrix`` at host-hill builds."""
    monkeypatch.setattr(wm, "_build_matrix", functools.partial(
        package_build_matrix, landform=DEFAULT_HOST_HILL,
        zone_size=OUTDOOR_DUNGEON_ZONE_SIZE))


_MATRIX_PROPERTIES = [
    wm.test_property1_every_cell_one_node_type_one_intent,
    wm.test_property2_plains_led_interior,
    wm.test_property3_water_is_single_connected_region,
    wm.test_property4_every_perimeter_cell_is_rim_typed_by_edge,
    wm.test_property5_playable_regions_reachable_from_spawn,
    wr.test_property9_generative_matrices_have_no_stranded_playable,
    ws.test_property10_noise_masked_at_frozen_and_blended_at_soft_edges,
    ws.test_property11_zonelines_flat_rivers_below_banks,
    ws.test_property12_erosion_never_breaches_the_rim,
    ws.test_property14_interior_slopes_within_agent_cap,
]


@pytest.mark.parametrize("prop", _MATRIX_PROPERTIES, ids=lambda f: f.__name__[5:16])
@pytest.mark.parametrize("edges", EDGES, ids=["sealed", "zoneline", "river", "open"])
def test_wilderness_properties_hold_for_host_hills(host_hill_builds, prop, edges):
    for seed in SEEDS:
        prop.hypothesis.inner_test(inp={"biome": "plains", "edges": list(edges),
                                        "seed": seed})


@pytest.mark.slow
@pytest.mark.parametrize("edges", EDGES, ids=["sealed", "zoneline", "river", "open"])
def test_bowl_holds_on_host_hill_meshes(host_hill_builds, edges):
    for seed in SEEDS[:3]:
        wb.test_property15_bowl_holds_on_built_mesh.hypothesis.inner_test(
            biome="plains", edges=list(edges), seed=seed)


# ---------------------------------------------------------------------------
# Without a Landform, nothing changes
# ---------------------------------------------------------------------------

def test_plain_wilderness_records_no_landform():
    spec = wilderness_spec("w", 11, None)
    assert set(spec.wilderness) == {"biome", "edges"}
    m = package_build_matrix("plains", [], 11)
    assert m.landform is None and m.landform_cells() == []
    assert "landform" not in m.to_dict()
    assert all("relief" not in c for col in m.to_dict()["cells"] for c in col)


def test_host_hill_spec_records_the_placed_landform():
    spec = wilderness_spec("h", 11, None, landform=DEFAULT_HOST_HILL,
                           zone_size=OUTDOOR_DUNGEON_ZONE_SIZE)
    placed = Landform.from_dict(spec.wilderness["landform"])
    assert placed.approach in DEFAULT_SIDES
    assert spec.wilderness["zone_size"] == OUTDOOR_DUNGEON_ZONE_SIZE
