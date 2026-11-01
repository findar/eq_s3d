"""
generators/vegetation/textures.py
---------------------------------
Bark and leaf textures for the tree models (trees spec task 3, Req 2.5).

Bark goes through the normal texture path (``generate_texture``: procedural by
default, the AI provider when a key is set). Leaves need an alpha silhouette
the providers don't make, so :func:`leaf_texture` takes the provider's RGB and
replaces its alpha with a procedural mask: a rounded, lumpy crown with leaf
gaps for a broadleaf card, a jagged triangle for a conifer tier. The canopy
material uses the chroma (alpha-tested) shader, so the mask is binary.

Texture rows run top-down (``v = 0`` is the top row), matching the card UVs in
``models.py``.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import zoom

from generators.textures.dds import rgba_to_dds
from generators.textures.factory import generate_texture
from generators.vegetation.kit import Species

TEXTURE_SIZE = 256
_DDS_HEADER = 128  # 4-byte magic + 124-byte header (``dds.dds_header``)


def bark_texture_name(species: Species) -> str:
    return f"veg_{species.name}_bark.dds"


def leaf_texture_name(species: Species) -> str:
    return f"veg_{species.name}_leaf.dds"


def bark_texture(species: Species, seed: int, size: int = TEXTURE_SIZE) -> bytes:
    """The trunk's bark texture (opaque)."""
    return generate_texture(species.bark_description, species.bark, size=size,
                            name=f"veg_{species.name}_bark", seed=seed)


def _lumps(size: int, cells: int, rng: np.random.Generator) -> np.ndarray:
    """Smooth value noise in [0, 1] on a ``size`` square, ``cells`` lumps across."""
    lattice = rng.random((cells + 1, cells + 1))
    field = zoom(lattice, size / (cells + 1), order=3)[:size, :size]
    lo, hi = float(field.min()), float(field.max())
    return (field - lo) / (hi - lo) if hi > lo else np.zeros((size, size))


def leaf_alpha(form: str, size: int, seed: int) -> np.ndarray:
    """The canopy card's binary alpha mask (uint8, 0 or 255), rows top-down."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:size, 0:size] / (size - 1.0)  # y = 0 at the top row
    edge = _lumps(size, 6, rng)
    holes = _lumps(size, 14, rng)
    if form == "conifer":
        # A jagged triangle, apex at the top: half-width grows with depth.
        half = 0.48 * y * (0.82 + 0.3 * edge)
        inside = (np.abs(x - 0.5) < half) & (y > 0.03) & (y < 0.97)
        inside &= holes > 0.12
    else:
        # A rounded crown with a lumpy edge and leaf gaps inside.
        r = np.hypot(x - 0.5, y - 0.5)
        inside = r < 0.36 + 0.12 * edge
        inside &= holes > 0.2
    return np.where(inside, 255, 0).astype(np.uint8)


def leaf_texture(species: Species, seed: int, size: int = TEXTURE_SIZE) -> bytes:
    """The canopy's leaf texture: provider RGB with a procedural alpha mask."""
    dds = generate_texture(species.leaf_description, species.leaf, size=size,
                           name=f"veg_{species.name}_leaf", seed=seed)
    bgra = np.frombuffer(dds, dtype=np.uint8, offset=_DDS_HEADER).reshape(size, size, 4)
    rgb = bgra[..., [2, 1, 0]]
    return rgba_to_dds(np.ascontiguousarray(rgb), leaf_alpha(species.form, size, seed))
