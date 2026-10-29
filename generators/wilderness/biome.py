"""
generators/wilderness/biome.py
------------------------------
Biome kits (wilderness spec task 7, Requirement 11).

A biome is DATA, not a generator: ``styles/biomes.json`` names, per biome, the
ground-texture layers, the region materials, a water-presence flag, the
sky/fog tint and a vegetation-kit id. :func:`load_biome_kit` reads one entry;
:func:`ground_materials` applies it over the shared terrain core, choosing a
material per fine quad from the cell's region kind and, on the playable plains,
its slope, height and moisture (distance to water).

The vegetation-kit id is carried only (trees are roadmap step 2).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple

import numpy as np
from scipy.ndimage import binary_dilation

BIOMES_PATH = Path(__file__).resolve().parents[2] / "styles" / "biomes.json"

Color = Tuple[int, int, int]


@dataclass(frozen=True)
class KitMaterial:
    """One material a kit can put on the ground."""

    material: str
    color: Color
    description: str


@dataclass(frozen=True)
class BiomeKit:
    """One biome's entry from ``styles/biomes.json``."""

    name: str
    description: str
    water: bool
    sky_tint: Color
    fog_tint: Color
    fog_range: Tuple[float, float]
    ambient_light: Tuple[float, float, float]
    vegetation_kit: str
    ground: Mapping[str, KitMaterial]   # grass / dry / dirt / mud / rock
    regions: Mapping[str, KitMaterial]  # Node_Type (+ water_surface) -> material
    rules: Mapping[str, float]

    def materials(self) -> Dict[str, KitMaterial]:
        """Every material the kit can emit, by material name."""
        out: Dict[str, KitMaterial] = {}
        for m in (*self.ground.values(), *self.regions.values()):
            out.setdefault(m.material, m)
        return out

    def advisory(self) -> Dict[str, object]:
        """The look the binary can't carry (sky/fog tint, vegetation kit): advisory
        data, re-derived from the biome name rather than stored on the spec."""
        return {"sky_tint": list(self.sky_tint), "fog_tint": list(self.fog_tint),
                "fog_range": list(self.fog_range), "vegetation_kit": self.vegetation_kit}


def _material(d: Mapping) -> KitMaterial:
    return KitMaterial(material=d["material"], color=tuple(d["color"]),
                       description=d.get("description", ""))


@lru_cache(maxsize=None)
def _table(path: str) -> Dict[str, dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def biome_names(path: Optional[Path] = None) -> Tuple[str, ...]:
    return tuple(sorted(_table(str(path or BIOMES_PATH))))


def load_biome_kit(biome: str, path: Optional[Path] = None) -> BiomeKit:
    """The kit for ``biome`` (from ``BIOMES_PATH`` unless ``path`` is given).
    Raises ``KeyError`` naming the known biomes."""
    table = _table(str(path or BIOMES_PATH))
    if biome not in table:
        raise KeyError(f"no biome kit {biome!r}; known: {', '.join(sorted(table))}")
    d = table[biome]
    return BiomeKit(
        name=biome,
        description=d.get("description", ""),
        water=bool(d.get("water", False)),
        sky_tint=tuple(d["sky_tint"]),
        fog_tint=tuple(d["fog_tint"]),
        fog_range=tuple(float(x) for x in d["fog_range"]),
        ambient_light=tuple(float(x) for x in d["ambient_light"]),
        vegetation_kit=d["vegetation_kit"],
        ground={k: _material(v) for k, v in d["ground"].items()},
        regions={k: _material(v) for k, v in d["regions"].items()},
        rules={k: float(v) for k, v in d.get("rules", {}).items()},
    )


def ground_materials(kit: BiomeKit, node_type: np.ndarray, heights: np.ndarray,
                     resolution: float) -> np.ndarray:
    """Per fine QUAD (shape ``(nx-1, ny-1)``), the material name its two
    triangles use.

    Region kinds other than ``plains`` take the kit's region material. Plains
    quads are layered: rock above ``rock_slope``, dirt above ``dirt_slope``,
    mud within ``wet_distance`` cells of water, dry grass on the highest
    ``1 - dry_height_quantile`` of the plains, grass everywhere else.
    """
    h = np.asarray(heights, dtype=np.float64)
    node = node_type[:-1, :-1]
    # Quad slope: the steeper of its two triangles (a-b-c and a-c-d, the TER's
    # split), from the quad's own corners — a vertex gradient would bleed a
    # neighbouring rim wall onto the plains cell beside it.
    ha, hb, hc, hd = h[:-1, :-1], h[1:, :-1], h[1:, 1:], h[:-1, 1:]
    slope = np.maximum(np.hypot(hb - ha, hc - hb), np.hypot(hc - hd, hd - ha)) / resolution
    quad_h = (ha + hb + hc + hd) / 4.0

    out = np.empty(node.shape, dtype=object)
    fallback = kit.ground["grass"].material
    for kind in np.unique(node):
        mat = kit.regions.get(kind)
        out[node == kind] = mat.material if mat else fallback

    plains = node == "plains"
    if not plains.any():
        return out
    r = kit.rules
    wet_src = np.isin(node, ("water", "river"))
    wet_n = int(r.get("wet_distance", 0))
    wet = (binary_dilation(wet_src, iterations=wet_n) if wet_n > 0 and wet_src.any()
           else np.zeros_like(plains))
    dry_cut = np.quantile(quad_h[plains], r.get("dry_height_quantile", 1.0))

    layer = np.full(node.shape, "grass", dtype=object)
    layer[quad_h > dry_cut] = "dry"
    layer[wet] = "mud"
    layer[slope > r.get("dirt_slope", np.inf)] = "dirt"
    layer[slope > r.get("rock_slope", np.inf)] = "rock"
    for name, mat in kit.ground.items():
        out[plains & (layer == name)] = mat.material
    return out
