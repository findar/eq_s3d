"""Vegetation kit data and loader (trees spec task 2, Requirement 1)."""

import copy
import json

import pytest

from generators.vegetation.kit import (
    DENSITY_LEVELS,
    KitError,
    VEGETATION_PATH,
    kit_ids,
    load_vegetation_kit,
    parse_kit,
)
from generators.wilderness.biome import biome_names, load_biome_kit


def _raw(kit_id="plains_grassland"):
    with open(VEGETATION_PATH, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)[kit_id])


def test_every_biome_vegetation_kit_resolves():
    for biome in biome_names():
        kit_id = load_biome_kit(biome).vegetation_kit
        assert load_vegetation_kit(kit_id) is not None, (biome, kit_id)


def test_plains_kit_has_three_species_in_the_karana_height_range():
    kit = load_vegetation_kit("plains_grassland")
    assert set(kit.species) == {"broadleaf", "conifer", "sapling"}
    assert kit.species["conifer"].form == "conifer"
    assert kit.species["broadleaf"].form == "broadleaf"
    for sp in kit.species.values():
        lo, hi = sp.height
        assert 46 <= lo <= hi <= 130, (sp.name, sp.height)
        assert 0.5 <= sp.scale[0] <= sp.scale[1] <= 1.75, (sp.name, sp.scale)


def test_every_kit_has_species_densities_and_groves():
    for kit_id in kit_ids():
        kit = load_vegetation_kit(kit_id)
        assert kit.species and all(sp.weight > 0 for sp in kit.species.values())
        assert [kit.density_for(lv) for lv in DENSITY_LEVELS][0] == 0.0
        dens = [kit.density_for(lv) for lv in DENSITY_LEVELS[1:]]
        assert dens == sorted(dens) and dens[0] > 0, (kit_id, dens)
        assert 0 <= kit.groves.lone_share <= 1


def test_unknown_kit_is_none_and_unknown_level_raises():
    assert load_vegetation_kit("no_such_kit") is None
    with pytest.raises(ValueError, match="density level"):
        load_vegetation_kit("plains_grassland").density_for("jungle")


@pytest.mark.parametrize("mutate, field", [
    (lambda d: d.pop("density"), "density"),
    (lambda d: d["density"].pop("dense"), "density.dense"),
    (lambda d: d["species"].clear(), "species"),
    (lambda d: d["species"]["conifer"].update(form="palm"), "conifer.form"),
    (lambda d: d["species"]["broadleaf"].update(height=[110, 70]), "broadleaf.height"),
    (lambda d: d["species"]["sapling"].update(leaf=[0, 300, 0]), "sapling.leaf"),
    (lambda d: d["species"]["sapling"].update(weight=0), "sapling.weight"),
    (lambda d: d["groves"].update(lone_share=1.5), "groves.lone_share"),
    (lambda d: d["groves"].pop("radius"), "groves"),
])
def test_malformed_kit_raises_naming_the_field(mutate, field):
    raw = _raw()
    mutate(raw)
    with pytest.raises(KitError, match=field.replace(".", r"\.")):
        parse_kit("plains_grassland", raw)
