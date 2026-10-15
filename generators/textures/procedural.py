"""
generators/textures/procedural.py
----------------------------------
Procedural texture generation — no network, deterministic, always available.

Produces stone / rock / dirt / grass surfaces by layering tileable value noise
at multiple frequencies, modulating a base colour. The output is seamlessly
tileable and anchored to EQ's muted palette via the spec's base_color.

This is the default provider: every generated zone gets a plausible surface
texture with zero external calls. The AIProvider is a drop-in upgrade.
"""

from __future__ import annotations

import numpy as np

from .base import TextureProvider, TextureSpec
from .dds import rgba_to_dds, make_tileable


class ProceduralProvider(TextureProvider):
    name = "procedural"

    def available(self) -> bool:
        return True

    def generate(self, spec: TextureSpec) -> bytes:
        size = spec.size
        rng = np.random.default_rng(spec.seed if spec.seed else _seed_from(spec))

        # Layered tileable noise → a grayscale detail field in [0, 1]
        detail = _layered_tileable_noise(size, rng, kind=spec.kind)

        # Map the detail onto the base colour with kind-specific character.
        rgb = _colourise(detail, spec.base_color, spec.kind, rng)

        if spec.tileable:
            rgb = make_tileable(rgb.astype(np.float32), blend=0.18)

        rgb = np.clip(rgb, 0, 255).astype(np.uint8)
        return rgba_to_dds(rgb)


# ---------------------------------------------------------------------------
# Noise
# ---------------------------------------------------------------------------

def _seed_from(spec: TextureSpec) -> int:
    return abs(hash((spec.name, spec.description, spec.kind))) % (2 ** 31)


def _tileable_value_noise(size: int, period: int, rng: np.random.Generator) -> np.ndarray:
    """
    Tileable value noise: random values on a lattice of `period` cells that
    wraps around the edges, upsampled to `size` with smooth interpolation.
    """
    # Lattice of random values, wrapping (last col/row == first)
    lattice = rng.random((period + 1, period + 1), dtype=np.float32)
    lattice[-1, :] = lattice[0, :]
    lattice[:, -1] = lattice[:, 0]

    # Sample coordinates
    coords = np.linspace(0, period, size, endpoint=False, dtype=np.float32)
    x0 = np.floor(coords).astype(int)
    fx = coords - x0
    x1 = (x0 + 1)

    # Quintic smoothing
    sx = fx * fx * fx * (fx * (fx * 6 - 15) + 10)

    # Bilinear over the lattice, separable
    # Rows
    top = lattice[x0][:, x0] * (1 - sx)[None, :] + lattice[x0][:, x1] * sx[None, :]
    bot = lattice[x1][:, x0] * (1 - sx)[None, :] + lattice[x1][:, x1] * sx[None, :]
    out = top * (1 - sx)[:, None] + bot * sx[:, None]
    return out.astype(np.float32)


def _layered_tileable_noise(size: int, rng: np.random.Generator, kind: str) -> np.ndarray:
    """FBM of tileable value noise. Returns [0,1]."""
    # kind tweaks the frequency content / roughness
    base_period = {"grass": 6, "dirt": 5, "stone": 4, "rock": 3, "organic": 4}.get(kind, 4)
    octaves = 5
    total = np.zeros((size, size), dtype=np.float32)
    amp = 1.0
    period = base_period
    norm = 0.0
    for _ in range(octaves):
        total += amp * _tileable_value_noise(size, period, rng)
        norm += amp
        amp *= 0.55
        period *= 2
    total /= max(norm, 1e-6)

    # Contrast shaping per kind
    if kind in ("rock", "stone"):
        total = _contrast(total, 1.4)
    elif kind == "grass":
        total = _contrast(total, 0.9)
    return np.clip(total, 0.0, 1.0)


def _contrast(x: np.ndarray, k: float) -> np.ndarray:
    """Push values away from 0.5 by factor k (k>1 = more contrast)."""
    return np.clip((x - 0.5) * k + 0.5, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Colourising
# ---------------------------------------------------------------------------

def _colourise(detail: np.ndarray, base_color, kind: str,
               rng: np.random.Generator) -> np.ndarray:
    """Turn a grayscale detail field into an RGB image around base_color."""
    br, bg, bb = base_color
    base = np.array([br, bg, bb], dtype=np.float32)

    # Light/dark variation range per kind (how much the noise shifts value)
    swing = {
        "stone": 55.0, "rock": 70.0, "dirt": 45.0,
        "grass": 40.0, "organic": 50.0, "flat": 10.0,
    }.get(kind, 50.0)

    # Shift brightness by (detail - 0.5) * swing
    shift = (detail - 0.5) * 2.0 * swing   # [-swing, +swing]
    rgb = base[None, None, :] + shift[:, :, None]

    # Kind-specific tinting for a touch of realism
    if kind == "grass":
        # Add green modulation on brighter patches
        rgb[..., 1] += detail * 25.0
    elif kind in ("rock", "stone"):
        # Add a subtle second noise for mineral speckle
        speckle = _tileable_value_noise(detail.shape[0], detail.shape[0] // 4, rng)
        dark = (speckle < 0.15)
        rgb[dark] *= 0.75
    elif kind == "dirt":
        # Warm the midtones slightly
        rgb[..., 0] += 8.0

    return rgb
