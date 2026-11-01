"""
generators/vegetation/kit.py
----------------------------
Vegetation kits (trees spec task 2, Requirement 1).

A biome's trees are DATA, not a generator: ``styles/vegetation.json`` names,
per kit id, the Species (form, weight, size ranges, colours), the density for
each Density_Level and the grove parameters. A biome points at its kit by the
``vegetation_kit`` id in ``styles/biomes.json``. :func:`load_vegetation_kit`
reads and validates one entry; a malformed entry raises naming the field, and
an unknown id returns ``None`` (the build then places no trees, Req 1.3).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple

VEGETATION_PATH = Path(__file__).resolve().parents[2] / "styles" / "vegetation.json"

#: The Density_Levels, sparsest first. ``none`` has no density entry.
DENSITY_LEVELS: Tuple[str, ...] = ("none", "sparse", "normal", "dense")

#: The tree forms the model generator can build.
FORMS: frozenset = frozenset({"broadleaf", "conifer"})

Color = Tuple[int, int, int]
Range = Tuple[float, float]


@dataclass(frozen=True)
class Species:
    """One tree form in a kit. Sizes are world units at scale 1."""

    name: str
    form: str
    weight: float
    height: Range
    canopy: Range
    trunk_radius: float
    scale: Range
    bark: Color
    leaf: Color
    bark_description: str
    leaf_description: str


@dataclass(frozen=True)
class Groves:
    """How trees cluster: ``lone_share`` stand alone, the rest grow in groves."""

    lone_share: float
    radius: Range
    trees_per_grove: Tuple[int, int]


@dataclass(frozen=True)
class VegetationKit:
    """One kit's entry from ``styles/vegetation.json``."""

    name: str
    description: str
    density: Mapping[str, float]      # level -> trees per 1e6 u² (no "none")
    groves: Groves
    species: Mapping[str, Species]

    def density_for(self, level: str) -> float:
        """Trees per 1e6 u² of Eligible_Ground for ``level`` (0 for ``none``)."""
        if level not in DENSITY_LEVELS:
            raise ValueError(f"unknown density level {level!r}; "
                             f"expected one of {', '.join(DENSITY_LEVELS)}")
        return 0.0 if level == "none" else self.density[level]


class KitError(ValueError):
    """A malformed vegetation kit entry; the message names the field."""


def _field(d: Mapping, key: str, where: str):
    if key not in d:
        raise KitError(f"{where}.{key}: missing")
    return d[key]


def _range(d: Mapping, key: str, where: str, *, positive: bool = True) -> Range:
    v = _field(d, key, where)
    if not (isinstance(v, (list, tuple)) and len(v) == 2):
        raise KitError(f"{where}.{key}: expected [low, high], got {v!r}")
    lo, hi = float(v[0]), float(v[1])
    if lo > hi or (positive and lo <= 0):
        raise KitError(f"{where}.{key}: expected 0 < low <= high, got {v!r}")
    return lo, hi


def _color(d: Mapping, key: str, where: str) -> Color:
    v = _field(d, key, where)
    if not (isinstance(v, (list, tuple)) and len(v) == 3
            and all(isinstance(c, int) and 0 <= c <= 255 for c in v)):
        raise KitError(f"{where}.{key}: expected [r, g, b] in 0-255, got {v!r}")
    return tuple(v)


def _positive(d: Mapping, key: str, where: str) -> float:
    v = float(_field(d, key, where))
    if v <= 0:
        raise KitError(f"{where}.{key}: must be positive, got {v!r}")
    return v


def _species(name: str, d: Mapping, where: str) -> Species:
    where = f"{where}.species.{name}"
    form = _field(d, "form", where)
    if form not in FORMS:
        raise KitError(f"{where}.form: {form!r} is not one of {', '.join(sorted(FORMS))}")
    return Species(
        name=name,
        form=form,
        weight=_positive(d, "weight", where),
        height=_range(d, "height", where),
        canopy=_range(d, "canopy", where),
        trunk_radius=_positive(d, "trunk_radius", where),
        scale=_range(d, "scale", where),
        bark=_color(d, "bark", where),
        leaf=_color(d, "leaf", where),
        bark_description=str(d.get("bark_description", "tree bark")),
        leaf_description=str(d.get("leaf_description", "leaves")),
    )


def _groves(d: Mapping, where: str) -> Groves:
    where = f"{where}.groves"
    lone = float(_field(d, "lone_share", where))
    if not 0.0 <= lone <= 1.0:
        raise KitError(f"{where}.lone_share: must be within 0-1, got {lone!r}")
    lo, hi = _range(d, "trees_per_grove", where)
    if lo != int(lo) or hi != int(hi):
        raise KitError(f"{where}.trees_per_grove: expected whole numbers")
    return Groves(lone_share=lone, radius=_range(d, "radius", where),
                  trees_per_grove=(int(lo), int(hi)))


def parse_kit(kit_id: str, d: Mapping) -> VegetationKit:
    """Validate one raw kit entry (Req 1.1). Raises ``KitError`` naming the field."""
    where = kit_id
    raw_density = _field(d, "density", where)
    density: Dict[str, float] = {}
    for level in DENSITY_LEVELS[1:]:
        density[level] = _positive(raw_density, level, f"{where}.density")
    raw_species = _field(d, "species", where)
    if not raw_species:
        raise KitError(f"{where}.species: at least one Species is required")
    species = {name: _species(name, sd, where) for name, sd in raw_species.items()}
    return VegetationKit(
        name=kit_id,
        description=str(d.get("description", "")),
        density=density,
        groves=_groves(_field(d, "groves", where), where),
        species=species,
    )


@lru_cache(maxsize=None)
def _table(path: str) -> Dict[str, dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def kit_ids(path: Optional[Path] = None) -> Tuple[str, ...]:
    return tuple(sorted(_table(str(path or VEGETATION_PATH))))


def load_vegetation_kit(kit_id: str, path: Optional[Path] = None) -> Optional[VegetationKit]:
    """The kit for ``kit_id`` (from ``VEGETATION_PATH`` unless ``path`` is given),
    or ``None`` when there is no such entry (Req 1.3)."""
    table = _table(str(path or VEGETATION_PATH))
    if kit_id not in table:
        return None
    return parse_kit(kit_id, table[kit_id])
