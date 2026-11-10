"""Texture mode and texture manifest (placeholder textures spec task 3).

Req 4: zone surfaces are labelled Placeholders by default and
``EQ_S3D_TEXTURE_PROVIDER`` picks any mode; tree textures keep their own path.
Req 5 / X6: the sidecar's ``textures`` list has one entry per material, sorted,
with polygon counts that add up to the meshes they describe.
"""

import json
from collections import Counter

import pytest

from ai.expand import plan_to_spec
from ai.planner import make_plan
from ai.schema import ZonePlan
from core.pfs import PfsArchive
from core.ter import TerFile
from generators.builder import ZoneBuilder, surface_of
from generators.textures.placeholder import placeholder_dds

SPECS = {
    "dungeon": lambda: plan_to_spec(make_plan("a gnoll temple dungeon with 8 rooms", name="tex"), seed=7),
    "city": lambda: plan_to_spec(ZonePlan(name="tex", zone_type="city"), seed=7),
    "wilderness": lambda: plan_to_spec(ZonePlan(name="tex", zone_type="wilderness"), seed=7,
                                       edges={"N": "zoneline", "E": "river"}),
}


def _build(tmp_path, kind, sub="a"):
    spec = SPECS[kind]()
    result = ZoneBuilder(spec).build(output_dir=tmp_path / f"{kind}_{sub}", write_glb=False)
    arc = PfsArchive.from_file(result.eqg_path)
    side = json.loads(result.sidecar_path.read_text(encoding="utf-8"))
    return spec, arc, side


@pytest.mark.parametrize("kind", ["wilderness"])
def test_default_mode_draws_surfaces_as_placeholders(tmp_path, no_api_keys, kind):
    """Wilderness surfaces are still Placeholders by default. Dungeon and city
    surfaces are drawn from their recipes since interesting textures task 6
    (tests/test_texture_conformance.py covers that default)."""
    spec, arc, side = _build(tmp_path, kind)
    surfaces = [e for e in side["textures"] if e["surface_class"]]
    assert surfaces
    for e in surfaces:
        assert e["texture_mode"] == "placeholder"
        colour = spec.materials[e["material"]].color
        assert arc.get(e["texture"]) == placeholder_dds(e["material"], colour, e["surface_class"])


@pytest.mark.parametrize("kind", sorted(SPECS))
def test_x6_manifest_lists_every_material_once_with_its_polygons(tmp_path, no_api_keys, kind):
    _, arc, side = _build(tmp_path, kind)
    manifest = side["textures"]
    names = [e["material"] for e in manifest]
    assert names == sorted(names) and len(names) == len(set(names))

    meshes = [TerFile.from_bytes(arc.get("ter_tex.ter"))]
    meshes += [TerFile.from_bytes(arc.get(n)) for n in arc.list_files() if n.endswith(".mod")]
    expected = Counter()
    for mesh in meshes:
        counts = Counter(p.material for p in mesh.polygons)
        for mat in mesh.materials:
            expected[mat.name] += counts.get(mat.index, 0)
    assert {e["material"]: e["polygons"] for e in manifest} == dict(expected)
    assert sum(e["polygons"] for e in manifest) == sum(len(m.polygons) for m in meshes)

    packed = set(arc.list_files())
    for e in manifest:
        assert e["texture"] in packed
        assert (e["texture_set"], e["surface"], e["surface_class"]) == surface_of(e["material"])
        assert e["texture_mode"] in ("placeholder", "procedural", "ai", "vegetation", "sites",
                                     "decor")


@pytest.mark.slow
def test_decor_textures_are_listed_as_decor(tmp_path, no_api_keys, monkeypatch):
    """Room-decor task 9: a decorated build's stock models are in the manifest,
    their materials' Texture_Mode ``decor``, each texture packed, and the
    polygons still add up (needs the install; skips without it)."""
    from generators.decor.stock import eq_path_from_env

    eq = eq_path_from_env()
    if eq is None:
        pytest.skip("EQ_PATH is not set (no EQ install to read)")
    monkeypatch.setenv("EQ_PATH", str(eq))
    spec = SPECS["dungeon"]()
    spec.decor = "normal"
    result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)
    arc = PfsArchive.from_file(result.eqg_path)
    manifest = json.loads(result.sidecar_path.read_text(encoding="utf-8"))["textures"]
    stock = [n for n in arc.list_files() if n.startswith("stock_") and n.endswith(".mod")]
    assert stock
    names = set()
    expected = Counter()
    for n in stock:
        model = TerFile.from_bytes(arc.get(n))
        counts = Counter(p.material for p in model.polygons)
        for mat in model.materials:
            names.add(mat.name)
            expected[mat.name] += counts.get(mat.index, 0)
    decor = {e["material"]: e for e in manifest if e["texture_mode"] == "decor"}
    assert set(decor) == names
    assert {k: e["polygons"] for k, e in decor.items()} == dict(expected)
    packed = set(arc.list_files())
    assert all(e["texture"] in packed for e in decor.values())


def test_procedural_override_restores_noise_textures(tmp_path, no_api_keys, monkeypatch):
    monkeypatch.setenv("EQ_S3D_TEXTURE_PROVIDER", "procedural")
    spec, arc, side = _build(tmp_path, "city")
    for e in side["textures"]:
        assert e["texture_mode"] == "procedural"
        colour = spec.materials[e["material"]].color
        assert arc.get(e["texture"]) != placeholder_dds(e["material"], colour, e["surface_class"])


def test_ai_override_without_a_key_falls_back_to_procedural(tmp_path, no_api_keys, monkeypatch):
    monkeypatch.setenv("EQ_S3D_TEXTURE_PROVIDER", "ai")
    _, _, side = _build(tmp_path, "city")
    assert {e["texture_mode"] for e in side["textures"]} == {"procedural"}


def test_tree_textures_keep_their_own_path(tmp_path, no_api_keys, monkeypatch):
    """Bark and leaf carry no Surface_Class, so the default mode leaves them on
    the procedural path: identical to a build forced to ``procedural``."""
    _, default_arc, side = _build(tmp_path, "wilderness", "default")
    monkeypatch.setenv("EQ_S3D_TEXTURE_PROVIDER", "procedural")
    _, procedural_arc, _ = _build(tmp_path, "wilderness", "procedural")
    trees = [e for e in side["textures"] if e["texture_mode"] == "vegetation"]
    assert trees and all(e["surface_class"] is None for e in trees)
    for e in trees:
        assert default_arc.get(e["texture"]) == procedural_arc.get(e["texture"])


@pytest.mark.parametrize("name, expected", [
    ("gnoll_temple_wall", ("gnoll_temple", "wall", "wall")),
    ("dungeon_ceiling", ("dungeon", "ceiling", "ceiling")),
    ("city_floor", ("city", "floor", "floor")),
    ("wild_plains", ("wild", "plains", "ground")),
    ("liquid_water", ("liquid", "water", "liquid")),
    ("veg_conifer_leaf", ("veg_conifer", "leaf", None)),
    ("floor", ("", "floor", "floor")),
])
def test_surface_of(name, expected):
    assert surface_of(name) == expected


# ---------------------------------------------------------------------------
# Task 8: placeholders + preview textures add at most 2 s (Req 8, X8)
# ---------------------------------------------------------------------------

TEXTURE_BUDGET_S = 2.0


def _dense_wilderness():
    spec = plan_to_spec(ZonePlan(name="tex", zone_type="wilderness"), seed=1955208177,
                        edges={"N": "zoneline", "E": "river"})
    spec.wilderness["trees"] = "dense"
    return spec


def _timed_build(tmp_path, sub):
    import time

    import generators.textures.factory as factory

    factory._cache.clear()
    t0 = time.perf_counter()
    ZoneBuilder(_dense_wilderness()).build(output_dir=tmp_path / sub)
    return time.perf_counter() - t0


@pytest.mark.slow
def test_x8_placeholders_and_preview_textures_add_at_most_2s(tmp_path, no_api_keys, monkeypatch):
    """Today's default (Placeholders, textures embedded in the GLB) against the
    step 2 behaviour (procedural textures, base-colour GLB), on a dense
    wilderness build with the landscape cache warm. Best of two each."""
    from core.eqg import EqgZone

    _timed_build(tmp_path, "warm")
    now = min(_timed_build(tmp_path, f"now{i}") for i in range(2))

    plain_glb = EqgZone.write_glb

    def without_textures(self, *args, **kwargs):
        kwargs.pop("textures", None)
        return plain_glb(self, *args, **kwargs)

    monkeypatch.setenv("EQ_S3D_TEXTURE_PROVIDER", "procedural")
    monkeypatch.setattr(EqgZone, "write_glb", without_textures)
    before = min(_timed_build(tmp_path, f"before{i}") for i in range(2))
    assert now - before <= TEXTURE_BUDGET_S, (
        f"default build {now:.2f}s vs step 2 behaviour {before:.2f}s: "
        f"{now - before:.2f}s added (budget {TEXTURE_BUDGET_S:g}s)")
