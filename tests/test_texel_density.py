"""Texel density from the profile (interesting textures spec task 7, Req 6,
property Y6).

Dungeon and city surfaces repeat their texture at the theme profile's median
texel density in the default (recipe) mode, and at step 3's 100 u in
placeholder mode; the density is recorded on each material in the spec; the
wilderness is untouched; and only UVs move (X3's goldens cover geometry).
"""

import json
import math
import statistics

import pytest

from ai.expand import plan_to_spec
from ai.planner import make_plan
from ai.schema import ZonePlan
from core.pfs import PfsArchive
from core.ter import TerFile
from generators.builder import ZoneBuilder, surface_of, texel_density
from generators.zone_spec import MaterialSpec, ZoneSpec

SPECS = {
    "dungeon": lambda: plan_to_spec(make_plan("a gnoll temple dungeon with 8 rooms", name="tex7"), seed=7),
    "city": lambda: plan_to_spec(ZonePlan(name="tex7", zone_type="city"), seed=7),
}


def _build(tmp_path, spec, sub):
    r = ZoneBuilder(spec).build(output_dir=tmp_path / sub, write_glb=False)
    return TerFile.from_bytes(PfsArchive.from_file(r.eqg_path).get(f"ter_{spec.name}.ter"))


def repeat_lengths(ter):
    """{material name: median world units per UV unit along its edges}."""
    per = {}
    for p in ter.polygons:
        vs = [ter.vertices[i] for i in (p.v1, p.v2, p.v3)]
        for a, b in ((vs[0], vs[1]), (vs[1], vs[2])):
            dw = math.dist((a.x, a.y, a.z), (b.x, b.y, b.z))
            du = math.hypot(a.u - b.u, a.v - b.v)
            if du > 1e-6:
                per.setdefault(ter.materials[p.material].name, []).append(dw / du)
    return {k: statistics.median(v) for k, v in per.items()}


@pytest.mark.parametrize("kind, theme", [("dungeon", "dungeon"), ("city", "city")])
def test_y6_default_mode_repeats_at_the_profile_density(tmp_path, no_api_keys, kind, theme):
    spec = SPECS[kind]()
    lengths = repeat_lengths(_build(tmp_path, spec, kind))
    assert lengths
    for name, length in lengths.items():
        surface = surface_of(name)[1]
        want = texel_density(theme, surface)
        assert spec.materials[name].texel_density == want
        assert length == pytest.approx(want, rel=1e-3), name


@pytest.mark.parametrize("kind", sorted(SPECS))
def test_y6_placeholder_mode_keeps_100u(tmp_path, no_api_keys, monkeypatch, kind):
    monkeypatch.setenv("EQ_S3D_TEXTURE_PROVIDER", "placeholder")
    spec = SPECS[kind]()
    lengths = repeat_lengths(_build(tmp_path, spec, kind))
    assert all(m.texel_density is None for m in spec.materials.values())
    assert all(length == pytest.approx(100.0, rel=1e-3) for length in lengths.values())


def test_wilderness_uvs_are_untouched(tmp_path, no_api_keys, monkeypatch):
    def build(sub):
        spec = plan_to_spec(ZonePlan(name="tex7", zone_type="wilderness"), seed=7,
                            edges={"N": "zoneline"})
        return spec, _build(tmp_path, spec, sub).to_bytes()

    spec, default = build("default")
    monkeypatch.setenv("EQ_S3D_TEXTURE_PROVIDER", "placeholder")
    _, placeholder = build("placeholder")
    assert default == placeholder
    assert all(m.texel_density is None for m in spec.materials.values())


def test_an_explicit_density_is_respected(tmp_path, no_api_keys):
    spec = SPECS["city"]()
    spec.materials["city_wall"].texel_density = 50.0
    lengths = repeat_lengths(_build(tmp_path, spec, "explicit"))
    assert lengths["city_wall"] == pytest.approx(50.0, rel=1e-3)
    assert lengths["city_floor"] == pytest.approx(texel_density("city", "floor"), rel=1e-3)


def test_density_is_saved_with_the_spec_and_old_specs_still_load():
    spec = ZoneSpec(name="rt", zone_type="dungeon")
    spec.materials["dungeon_wall"] = MaterialSpec("dungeon_wall", "dungeon_wall.dds",
                                                  texel_density=24.1)
    back = ZoneSpec.from_dict(json.loads(json.dumps(spec.to_dict())))
    assert back.materials["dungeon_wall"].texel_density == 24.1
    old = spec.to_dict()
    del old["materials"]["dungeon_wall"]["texel_density"]
    assert ZoneSpec.from_dict(old).materials["dungeon_wall"].texel_density is None


def test_profile_densities_are_the_classic_ones():
    assert 12 <= texel_density("dungeon", "wall") <= 30
    assert 12 <= texel_density("city", "floor") <= 30
