"""Site Structure textures (wilderness POIs spec task 4, Req 3.4): each
material renders, tiles seamlessly, sits at the measured texel density, and is
pure in its seed."""

import json

import numpy as np
import pytest

from generators.textures.conformance import STYLES, look_stats, out_of_band
from generators.textures.dds import dds_header
from generators.textures.sites import (
    MATERIAL_SETS, MATERIALS, SLOTS, features_per_tile, set_material,
    site_rgb, site_texture, site_texture_name, texel_density, uv_scale)


@pytest.fixture(scope="module")
def images():
    return {m: site_rgb(m, 7) for m in MATERIALS}


@pytest.mark.parametrize("material", MATERIALS)
def test_renders_as_classic_dds(material, images):
    dds = site_texture(material, 7)
    assert dds[:128] == dds_header(256, 256)
    assert len(dds) == 128 + 256 * 256 * 4
    assert site_texture_name(material) == f"site_{material}.dds"
    assert not list(out_of_band(look_stats(images[material]), "outdoor", material))


@pytest.mark.parametrize("material", MATERIALS)
def test_tiles_seamlessly(material, images):
    """The step across the wrap is no bigger than any step inside the tile."""
    f = images[material].astype(np.float64)
    for axis in (0, 1):
        wrapped = np.concatenate([f, np.take(f, [0], axis=axis)], axis=axis)
        steps = np.abs(np.diff(wrapped, axis=axis)).mean(axis=(1 - axis, 2))
        assert steps[-1] <= steps[:-1].max(), (material, axis)


def test_at_the_measured_density():
    doc = json.loads((STYLES / "outdoor.json").read_text(encoding="utf-8"))
    assert texel_density() == doc["textures"]["texel_density"]["wall"]["p50"]
    assert uv_scale() == pytest.approx(1 / texel_density())


@pytest.mark.parametrize("material,axis", [("timber", 0), ("crude_timber", 0),
                                           ("thatch", 0), ("canvas", 1)])
def test_features_repeat_at_the_density(material, axis, images):
    """A coursed material repeats at its feature size at the density: most of
    its profile's power sits at multiples of the features-per-tile frequency."""
    lum = images[material].astype(np.float64).mean(-1)
    profile = lum.mean(axis=1 - axis)
    power = np.abs(np.fft.rfft(profile - profile.mean())) ** 2
    n = features_per_tile(material)
    assert power[n::n].sum() > 0.5 * power[1:].sum()


def test_same_seed_same_pixels():
    for m in MATERIALS:
        assert site_texture(m, 11) == site_texture(m, 11)
        assert site_texture(m, 11) != site_texture(m, 12)


def test_every_set_names_a_material_per_slot():
    for name, slots in MATERIAL_SETS.items():
        assert tuple(slots) == SLOTS
        assert all(set_material(name, s) in MATERIALS for s in SLOTS)
    with pytest.raises(KeyError, match="orc"):
        set_material("orc", "wall")
