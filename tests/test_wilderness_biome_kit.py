"""The plains biome kit and ground textures (wilderness spec task 7, Req 11).

A biome is a data entry in ``styles/biomes.json``; the wilderness TER takes its
materials from the kit (ground layered by slope, height and moisture), the
textures go through the provider seam, and the mesh carries real UVs.
"""

from __future__ import annotations

import json

import pytest

from generators.builder import ZoneBuilder
from generators.textures import factory
from generators.textures.base import TextureProvider
from generators.textures.procedural import ProceduralProvider
from generators.wilderness import biome
from generators.wilderness.biome import biome_names, load_biome_kit
from generators.wilderness.build import build_wilderness_ter, wilderness_spec
from generators.wilderness.water import WATER_SURFACE_MATERIAL


def test_plains_kit_resolves_from_the_table():
    assert "plains" in biome_names()
    kit = load_biome_kit("plains")
    assert kit.water is True
    assert kit.vegetation_kit == "plains_grassland"
    assert len(kit.sky_tint) == 3 and len(kit.fog_tint) == 3
    assert {"grass", "dirt", "rock"} <= set(kit.ground)
    with pytest.raises(KeyError, match="plains"):
        load_biome_kit("tundra")


def test_a_new_biome_is_data_only(tmp_path, monkeypatch):
    """Adding a biome is a table entry: a copied, renamed entry with water
    switched off builds a zone with no water plane."""
    table = json.loads(biome.BIOMES_PATH.read_text(encoding="utf-8"))
    table["steppe"] = {**table["plains"], "water": False, "vegetation_kit": "steppe_scrub"}
    path = tmp_path / "biomes.json"
    path.write_text(json.dumps(table), encoding="utf-8")
    monkeypatch.setattr(biome, "BIOMES_PATH", path)

    assert load_biome_kit("steppe").vegetation_kit == "steppe_scrub"
    spec = wilderness_spec("k", 2024, {"E": "river"}, biome="steppe")
    assert WATER_SURFACE_MATERIAL not in spec.materials
    ter = build_wilderness_ter(spec, "ter_k", 2)
    assert WATER_SURFACE_MATERIAL not in {m.name for m in ter.materials}


def test_ter_materials_come_from_the_kit_and_the_ground_is_layered():
    kit = load_biome_kit("plains")
    spec = wilderness_spec("k", 2024, {"N": "zoneline", "E": "river"})
    ter = build_wilderness_ter(spec, "ter_k", 2)
    names = {m.name for m in ter.materials}
    assert names <= set(kit.materials())
    ground = {m.material for m in kit.ground.values()}
    assert len(names & ground) >= 2, names
    for name, mat in spec.materials.items():
        assert mat.color == kit.materials()[name].color
    assert spec.ambient_light == kit.ambient_light


def test_ter_has_real_uvs():
    spec = wilderness_spec("k", 1337)
    ter = build_wilderness_ter(spec, "ter_k", 2)
    assert any(v.u != 0.0 for v in ter.vertices)
    assert any(v.v != 0.0 for v in ter.vertices)
    assert len({(round(v.u, 3), round(v.v, 3)) for v in ter.vertices}) > 1000


class _Recording(TextureProvider):
    name = "recording-task7"

    def __init__(self):
        self.calls = []

    def generate(self, spec):
        self.calls.append(spec)
        return ProceduralProvider().generate(spec)


def test_kit_textures_go_through_the_provider_seam(tmp_path):
    rec = _Recording()
    factory.set_provider(rec)
    try:
        spec = wilderness_spec("karana", 2024, {"E": "river"})
        ZoneBuilder(spec).build(output_dir=tmp_path)
    finally:
        factory.set_provider(None)
    requested = {s.name: s for s in rec.calls}
    assert set(requested) == set(spec.materials)
    assert requested["wild_plains"].kind == "grass"
    assert requested["wild_rock"].kind == "rock"
