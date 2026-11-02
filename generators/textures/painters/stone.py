"""
generators/textures/painters/stone.py
-------------------------------------
The stone families (interesting textures spec Requirement 4):
``dressed_stone``, ``brick``, ``flagstone``, ``cobble`` and ``cave_rock``.

Each builds a tone field in [0, 1] (0.5 = the base colour): structure (blocks,
slabs, stones, rock faces), joints and bevels, a per-piece tone, then
mid-frequency grain and per-pixel grit for the fine detail classic textures
carry, and shades it around the material's base colour.
"""

from __future__ import annotations

import numpy as np

from . import ashlar, cells, fbm, per_cell, register, shade, speckle, to_uint8


def _finish(tone, rng, grain, base_color, grit=0.09, spread=0.55):
    """Add mid-frequency grain and per-pixel grit, then shade."""
    tone = tone + (fbm(rng, base_period=16, octaves=4) - 0.5) * 0.35 * grain
    tone = tone + speckle(rng) * grit
    return to_uint8(shade(np.clip(tone, 0, 1), base_color, spread))


def _blocks(params, base_color, seed, bond):
    rng = np.random.default_rng(seed)
    bw, bh = params["block"]
    joint, bevel = float(params["joint"]), float(params["bevel"])
    block_id, dx, dy, edge, width, h = ashlar(bw, bh, params["jitter"], rng, bond=bond)
    tone = 0.5 + per_cell(block_id, rng, 0.12 + params["jitter"])
    # Bevel: light catches the top/left edge, the bottom/right falls in shadow.
    rim = (edge >= joint) & (edge < joint + bevel)
    lit = np.minimum(dx, dy) < np.minimum(width - dx, h - dy)
    tone = np.where(rim & lit, tone + 0.14, tone)
    tone = np.where(rim & ~lit, tone - 0.14, tone)
    # Chipped block faces: a little low-frequency relief inside each block.
    tone = tone + (fbm(rng, base_period=8, octaves=3) - 0.5) * 0.18
    # Mortar joints, darker and rough.
    mortar = 0.18 + (fbm(rng, base_period=32, octaves=2) - 0.5) * 0.12
    tone = np.where(edge < joint, mortar, tone)
    return tone, rng


@register("dressed_stone")
def dressed_stone(params, base_color, seed):
    tone, rng = _blocks(params, base_color, seed, bond=True)
    return _finish(tone, rng, params["grain"], base_color)


@register("brick")
def brick(params, base_color, seed):
    tone, rng = _blocks(params, base_color, seed, bond=True)
    # Brick faces are smoother than stone, with a fired-clay mottle.
    tone = tone + (fbm(rng, base_period=32, octaves=3) - 0.5) * 0.1
    return _finish(tone, rng, params["grain"], base_color, grit=0.07)


@register("flagstone")
def flagstone(params, base_color, seed):
    rng = np.random.default_rng(seed)
    f1, f2, owner = cells(int(params["cells"]), rng, relax=2)
    tone = 0.5 + per_cell(owner, rng, 0.1 + params["jitter"])
    # Slab faces dip slightly toward their joints (worn edges).
    gap = f2 - f1
    tone = tone - np.clip(1 - gap / 14.0, 0, 1) * 0.12
    tone = tone + (fbm(rng, base_period=8, octaves=3) - 0.5) * 0.2
    tone = np.where(gap < float(params["joint"]), 0.16, tone)
    return _finish(tone, rng, params["grain"], base_color)


@register("cobble")
def cobble(params, base_color, seed):
    rng = np.random.default_rng(seed)
    f1, f2, owner = cells(int(params["cells"]), rng, relax=1)
    tone = 0.5 + per_cell(owner, rng, 0.1 + params["jitter"])
    # Rounded stones: lighter at the crown, darker toward the gaps.
    gap = f2 - f1
    crown = np.clip(gap / max(gap.max(), 1e-6), 0, 1) ** 0.6
    tone = tone + (crown - 0.5) * 0.4 * params["bulge"]
    tone = np.where(gap < float(params["joint"]) * 1.5, 0.1, tone)
    return _finish(tone, rng, 0.4, base_color, grit=0.08)


@register("cave_rock")
def cave_rock(params, base_color, seed):
    rng = np.random.default_rng(seed)
    n = int(params["scale"]) ** 2 * 2
    f1, f2, owner = cells(n, rng, relax=0)
    # Faceted rock: each facet a tone, facets ridged at their borders.
    tone = 0.5 + per_cell(owner, rng, 0.22)
    # Facets fall away from a lit ridge: brighter near the border on one side.
    ridge = np.clip(1 - (f2 - f1) / 10.0, 0, 1)
    tone = tone + ridge * 0.25 - np.clip(f1 / max(float(f1.max()), 1e-6), 0, 1) * 0.15
    # Strata: soft horizontal banding warped by noise.
    y = np.arange(256, dtype=np.float32)[:, None]
    warp = fbm(rng, base_period=4, octaves=3) * 24
    tone = tone + np.sin((y + warp) / 256 * 2 * np.pi * 6) * 0.12 * params["strata"]
    # Cracks: thin dark seams along a finer cell network.
    c1, c2, _ = cells(n * 4, rng, relax=0)
    tone = np.where((c2 - c1) < 1.5, tone - 0.3 * params["crack"], tone)
    tone = tone + (fbm(rng, base_period=8, octaves=4) - 0.5) * 0.25
    return _finish(tone, rng, params["grain"], base_color, grit=0.1)
