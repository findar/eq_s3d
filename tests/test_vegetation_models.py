"""Procedural tree models and leaf/bark textures (trees spec task 3, Req 2).

Property T1: every Tree_Model has 24-96 triangles, a collidable trunk and a
walk-through canopy, a trunk buried at least 2 u, and round-trips through
``core.ter`` exactly. Plus the canopy is double-sided, faces point along their
normals, and the leaf texture's alpha is a real silhouette.
"""

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from core.ter import FLAG_PASSABLE, MAGIC_MODEL, SHADER_CHROMA, SHADER_OPAQUE, TerFile
from generators.vegetation.kit import FORMS, Species, load_vegetation_kit
from generators.vegetation.models import model_name, tree_model
from generators.vegetation.textures import (
    TEXTURE_SIZE,
    bark_texture,
    leaf_alpha,
    leaf_texture,
)
from tests.pbt_helpers import scaled


def _range(lo, hi):
    return st.tuples(st.floats(lo, hi), st.floats(lo, hi)).map(lambda t: tuple(sorted(t)))


species_strategy = st.builds(
    Species,
    name=st.sampled_from(["broadleaf", "conifer", "sapling", "oak_2"]),
    form=st.sampled_from(sorted(FORMS)),
    weight=st.just(1.0),
    height=_range(20.0, 320.0),
    canopy=_range(10.0, 210.0),
    trunk_radius=st.floats(0.5, 10.0),
    scale=st.just((0.5, 1.5)),
    bark=st.just((90, 70, 50)),
    leaf=st.just((80, 120, 60)),
    bark_description=st.just("bark"),
    leaf_description=st.just("leaves"),
)

T1_SETTINGS = settings(max_examples=scaled(200), deadline=None,
                       suppress_health_check=[HealthCheck.too_slow])


def _xyz(model, poly):
    v = model.vertices
    return np.array([[v[i].x, v[i].y, v[i].z] for i in (poly.v1, poly.v2, poly.v3)])


@T1_SETTINGS
@given(species=species_strategy, seed=st.integers(0, 2**31 - 1))
def test_property_t1_tree_model_shape_flags_sink_and_round_trip(species, seed):
    m = tree_model(species, seed)
    assert m.magic == MAGIC_MODEL and m.name == model_name(species)
    assert 24 <= len(m.polygons) <= 96

    trunk = [p for p in m.polygons if not p.flags & FLAG_PASSABLE]
    canopy = [p for p in m.polygons if p.flags & FLAG_PASSABLE]
    assert trunk and canopy
    assert {p.material for p in trunk} == {0} and {p.material for p in canopy} == {1}
    assert min(m.vertices[i].z for p in trunk for i in (p.v1, p.v2, p.v3)) <= -2.0

    back = TerFile.from_bytes(m.to_bytes(), name=m.name)
    assert back == m


@T1_SETTINGS
@given(species=species_strategy, seed=st.integers(0, 2**31 - 1))
def test_faces_point_along_their_normals_and_canopy_is_double_sided(species, seed):
    m = tree_model(species, seed)
    for p in m.polygons:
        a, b, c = _xyz(m, p)
        geo = np.cross(b - a, c - a)
        stored = np.array([[m.vertices[i].nx, m.vertices[i].ny, m.vertices[i].nz]
                           for i in (p.v1, p.v2, p.v3)])
        assert np.allclose(np.linalg.norm(stored, axis=1), 1.0, atol=1e-5)
        assert np.linalg.norm(geo) > 0
        assert (stored @ geo > 0).all()

    # Every canopy face has a twin over the same corners, wound the other way.
    def key(p):
        return frozenset(tuple(r) for r in _xyz(m, p).round(4))
    canopy = [p for p in m.polygons if p.flags & FLAG_PASSABLE]
    faces = {}
    for p in canopy:
        a, b, c = _xyz(m, p)
        faces.setdefault(key(p), []).append(np.cross(b - a, c - a))
    for normals in faces.values():
        assert len(normals) == 2 and np.dot(normals[0], normals[1]) < 0


def test_materials_use_the_designed_shaders_and_textures():
    kit = load_vegetation_kit("plains_grassland")
    for sp in kit.species.values():
        m = tree_model(sp, 7)
        bark, leaf = m.materials
        assert bark.shader == SHADER_OPAQUE and leaf.shader == SHADER_CHROMA
        assert bark.properties[0].value_s == f"veg_{sp.name}_bark.dds"
        assert leaf.properties[0].value_s == f"veg_{sp.name}_leaf.dds"


def test_plains_models_are_close_to_the_karana_poly_counts():
    kit = load_vegetation_kit("plains_grassland")
    counts = {name: len(tree_model(sp, 1).polygons) for name, sp in kit.species.items()}
    assert counts == {"broadleaf": 32, "conifer": 40, "sapling": 32}


def test_different_seeds_give_different_trees_same_seed_same_tree():
    sp = load_vegetation_kit("plains_grassland").species["broadleaf"]
    assert tree_model(sp, 3) == tree_model(sp, 3)
    assert tree_model(sp, 3).vertices != tree_model(sp, 4).vertices


def _dds_alpha(dds):
    px = np.frombuffer(dds, dtype=np.uint8, offset=128).reshape(TEXTURE_SIZE, TEXTURE_SIZE, 4)
    return px[..., 3]


@pytest.mark.parametrize("name", ["broadleaf", "conifer", "sapling"])
def test_leaf_texture_alpha_is_a_silhouette(name):
    sp = load_vegetation_kit("plains_grassland").species[name]
    alpha = _dds_alpha(leaf_texture(sp, 11))
    assert set(np.unique(alpha)) == {0, 255}
    q = TEXTURE_SIZE // 4
    corners = [alpha[:q // 2, :q // 2], alpha[:q // 2, -q // 2:]]
    assert all((c == 0).all() for c in corners), "top corners must be clear"
    top, bottom = (alpha[:q] > 0).mean(), (alpha[-q:] > 0).mean()
    if sp.form == "conifer":
        assert top < 0.5 * bottom  # a triangle: narrow at the top
    else:
        assert abs(top - bottom) < 0.15  # a rounded crown


def test_leaf_alpha_shapes_differ_by_form_and_bark_is_opaque():
    assert (leaf_alpha("conifer", 64, 1) != leaf_alpha("broadleaf", 64, 1)).any()
    sp = load_vegetation_kit("plains_grassland").species["broadleaf"]
    assert (_dds_alpha(bark_texture(sp, 2)) == 255).all()
