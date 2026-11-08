"""Wilderness POIs task 3 (Req 3; design P3): generated Structure models.

P3: every model is closed and wound outward where it's solid, round-trips through the ``.mod`` writer and reader
exactly, sits at finding 1's triangle counts with its origin at ground and a buried skirt, and an
Enterable model's opening, measured by the gate (``analyzer.footprints.measure_opening``) on its
own collidable triangles, is at least the clear width and head height. Plus: the sizes in ``rules/sites/sites.toml`` hold the models.
"""

from collections import Counter

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from analyzer.footprints import collidable_triangles, measure_opening
from core.ter import FLAG_PASSABLE, MAGIC_MODEL, TerFile
from generators.sites.models import (CLEAR_WIDTH, HEAD_HEIGHT, VARIANTS, WARP, SiteModelError, model_name,
                                     structure_model)
from generators.sites.placement import RUN_HALF_THICK, RUN_STRUCTURES
from generators.sites.rules import STRUCTURE_KINDS, load_sites
from generators.textures.sites import MATERIAL_SETS, site_texture_name
from tests.pbt_helpers import scaled

#: Finding 1's stock triangle counts per kind (a burial mound is BURIAL's own band).
TRIS = {"hut": (48, 219), "barn": (72, 219), "tent": (20, 110), "lean_to": (32, 60), "tower": (42, 254),
        "fire_ring": (44, 80), "fence": (12, 288), "standing_stone": (28, 52), "altar_stone": (28, 52),
        "monument": (39, 216), "ruin_wall": (52, 70)}
TRIS_VARIANT = {("monument", "burial_mound"): (60, 72)}

MODELS = [(k, v) for k in VARIANTS for v in VARIANTS[k]]
P3 = settings(max_examples=scaled(60), deadline=None, suppress_health_check=[HealthCheck.too_slow])


def _tris(ter, solid=True):
    v = ter.vertices
    return np.array([[[v[i].x, v[i].y, v[i].z] for i in (p.v1, p.v2, p.v3)]
                     for p in ter.polygons if bool(p.flags & FLAG_PASSABLE) != solid])


def _unbalanced_edges(tris):
    """Directed edges without a matching reverse edge: zero for closed, consistently wound solids."""
    e = Counter()
    for t in np.round(tris, 4):
        k = [tuple(p) for p in t]
        for a, b in ((0, 1), (1, 2), (2, 0)):
            e[(k[a], k[b])] += 1
    return [ab for ab, n in e.items() if e[(ab[1], ab[0])] != n]


def _pieces_volume(tris):
    """Signed volume of each closed piece (triangles joined by shared corners): positive when
    wound outward, as the gate reads "inside a solid"."""
    keys = [tuple(p) for p in np.round(tris, 4).reshape(-1, 3)]
    ids = {k: i for i, k in enumerate(dict.fromkeys(keys))}
    parent = list(range(len(ids)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    corners = np.array([ids[k] for k in keys]).reshape(-1, 3)
    for a, b, c in corners:
        parent[root(b)] = root(a)
        parent[root(c)] = root(a)
    vol = Counter()
    for t, (a, _, _) in zip(tris, corners):
        vol[root(a)] += float(np.dot(t[0], np.cross(t[1], t[2]))) / 6
    return list(vol.values())


@P3
@given(kv=st.sampled_from(MODELS), material_set=st.sampled_from(sorted(MATERIAL_SETS)),
       seed=st.integers(0, 2**31 - 1))
def test_property_p3_closed_round_trips_counts_skirt_and_openings(kv, material_set, seed):
    kind, variant = kv
    m = structure_model(kind, variant, material_set, seed)
    ter = m.ter
    assert ter.magic == MAGIC_MODEL and ter.name == model_name(kind, variant, material_set)

    # Round-trips exactly.
    assert TerFile.from_bytes(ter.to_bytes(), name=ter.name) == ter

    # Finding 1's triangle counts.
    lo, hi = TRIS_VARIANT.get(kv, TRIS[kind])
    assert lo <= len(ter.polygons) <= hi, len(ter.polygons)

    # Closed where solid.
    solid = _tris(ter)
    assert len(solid) and not _unbalanced_edges(solid)
    assert min(_pieces_volume(solid)) > 0

    # Origin at ground: solid stands on z = 0 and goes down to the buried skirt.
    z = solid[:, :, 2]
    assert z.min() == pytest.approx(-m.sink, abs=0.5)
    assert ((z.min(axis=1) < 0) & (z.max(axis=1) > 0)).any()

    # Enterable openings: the gate's own measure on the model's collidable triangles. A hut and
    # a lean-to let a player in through a way at least the clear width and head height; nothing
    # else encloses ground (a ruin's court is the gap placement leaves between its runs).
    assert m.enterable == (kind in ("hut", "lean_to", "ruin_wall"))
    got = measure_opening(collidable_triangles(ter))
    assert got.enterable == (kind in ("hut", "lean_to"))
    assert not got.narrow and not got.low
    for o in m.openings:
        assert o.width >= CLEAR_WIDTH and o.height >= HEAD_HEIGHT


def test_materials_come_from_the_set_by_slot():
    m = structure_model("hut", "timber", "timber_thatch", 3)
    assert {mt.name for mt in m.ter.materials} == {"site_timber", "site_thatch"}
    for mt in m.ter.materials:
        assert mt.properties[0].value_s == site_texture_name(mt.name[len("site_"):])
    hide = structure_model("tent", "hide", "hide", 3)
    assert {mt.name for mt in hide.ter.materials} == {"site_hide", "site_crude_timber"}


def test_pure_in_its_inputs_and_unknown_names_fail():
    assert structure_model("tent", "", "hide", 5).ter == structure_model("tent", "canvas", "hide", 5).ter
    assert structure_model("tent", "", "hide", 5).ter.vertices != structure_model("tent", "", "hide", 6).ter.vertices
    with pytest.raises(SiteModelError, match="yurt"):
        structure_model("tent", "yurt")
    with pytest.raises(SiteModelError, match="castle"):
        structure_model("castle")


def test_every_rules_structure_and_variant_has_a_model_and_its_size_holds_them():
    rules = load_sites()
    assert set(VARIANTS) == set(STRUCTURE_KINDS) == set(rules.structures)
    for who in rules.inhabitants.values():
        for kind, variant in who.variants.items():
            assert variant in VARIANTS[kind], (kind, variant)
    for kind, st_ in rules.structures.items():
        built = [structure_model(kind, v, "timber_thatch", s) for v in VARIANTS[kind] for s in range(6)]
        assert st_.enterable == built[0].enterable
        if kind in RUN_STRUCTURES:
            # A run along local y, as placement lays it: radius its half-length, 1 u thick.
            xyz = np.array([(q.x, q.y) for b in built for q in b.ter.vertices])
            assert abs(xyz[:, 1]).max() <= st_.radius + RUN_HALF_THICK + WARP, kind
            assert abs(xyz[:, 0]).max() <= RUN_HALF_THICK + WARP, kind
            continue
        assert max(b.radius for b in built) <= st_.radius, kind
        top = max(b.height for b in built)
        assert top <= st_.height <= top + 2.0, kind
