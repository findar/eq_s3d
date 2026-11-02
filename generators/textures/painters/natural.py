"""
generators/textures/painters/natural.py
---------------------------------------
The remaining dungeon and city families (interesting textures spec
Requirement 4): ``planks``, ``plaster``, ``ice`` and ``sky``.

Same contract as the stone families: ``paint(params, base_color, seed)`` gives
a seamless, pure 256x256 RGB image shaded around the base colour. Importing
this module registers the four families.
"""

from __future__ import annotations

import numpy as np

from . import SIZE, cells, fbm, per_cell, register, shade, speckle, to_uint8


def _noise_xy(rng: np.random.Generator, period_x: int, period_y: int) -> np.ndarray:
    """Tileable value noise with separate x and y lattice periods (stretched
    noise for wood grain), quintic-smoothed, in [0, 1]."""
    lattice = rng.random((period_y, period_x), dtype=np.float32)

    def axis(period):
        c = np.arange(SIZE, dtype=np.float32) * period / SIZE
        i0 = np.floor(c).astype(int)
        f = c - i0
        s = f * f * f * (f * (f * 6 - 15) + 10)
        return i0 % period, (i0 + 1) % period, s

    y0, y1, sy = axis(period_y)
    x0, x1, sx = axis(period_x)
    top = lattice[y0][:, x0] * (1 - sx)[None, :] + lattice[y0][:, x1] * sx[None, :]
    bot = lattice[y1][:, x0] * (1 - sx)[None, :] + lattice[y1][:, x1] * sx[None, :]
    return top * (1 - sy)[:, None] + bot * sy[:, None]


def _toroidal(dx: np.ndarray) -> np.ndarray:
    """Shortest signed offset on the wrapped tile."""
    return (dx + SIZE / 2) % SIZE - SIZE / 2


@register("planks")
def planks(params, base_color, seed):
    rng = np.random.default_rng(seed)
    rows = max(1, round(SIZE / params["width"]))
    h = SIZE / rows
    y = np.arange(SIZE, dtype=np.float32)
    x = np.arange(SIZE, dtype=np.float32)
    # Boards are offset half a board so the tile wraps mid-board, not on a seam.
    yb = (y + h / 2) % SIZE
    board = (yb // h).astype(int) % rows
    dy = yb - (yb // h) * h
    # Each board starts at its own butt joint, so boards get ids per segment.
    joints = rng.uniform(0, SIZE, rows)
    seg = ((x[None, :] - joints[board][:, None]) % SIZE < SIZE / 2).astype(int)
    ids = board[:, None] * 2 + seg
    tone = 0.5 + per_cell(ids, rng, 0.12)
    # Grain: long streaks along the board, warped into rings.
    streak = _noise_xy(rng, 4, 64)
    warp = _noise_xy(rng, 8, 16) * 6
    rings = np.sin((y[:, None] + warp) * 2 * np.pi / 7 + streak * 6) * 0.5 + 0.5
    tone = tone + (rings - 0.5) * 0.18 * params["grain"] + (streak - 0.5) * 0.3 * params["grain"]
    # Knots: a few dark ellipses with a ring, placed on the wrapped tile.
    yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    for _ in range(int(params["knots"])):
        ky, kx = rng.uniform(0, SIZE, 2)
        r = np.hypot(_toroidal(xx - kx) / 2.2, _toroidal(yy - ky)) / rng.uniform(3, 6)
        tone = tone - np.clip(1.2 - r, 0, 1) * 0.35 + np.clip(1 - abs(r - 1.6), 0, 1) * 0.06
    # Seams between boards and at the butt joints.
    seam = float(params["seam"])
    rel = x[None, :] - joints[board][:, None]
    butt = ((np.abs(_toroidal(rel)) < seam / 2 + 0.5)
            | (np.abs(_toroidal(rel - SIZE / 2)) < seam / 2 + 0.5))
    edge = (dy[:, None] < seam) | butt
    tone = np.where(edge, 0.12, tone)
    tone = tone + speckle(rng) * 0.06
    return to_uint8(shade(np.clip(tone, 0, 1), base_color, 0.6))


@register("plaster")
def plaster(params, base_color, seed):
    rng = np.random.default_rng(seed)
    # Smooth, faintly trowelled surface.
    tone = 0.5 + (fbm(rng, base_period=4, octaves=4) - 0.5) * 0.18
    tone = tone + (fbm(rng, base_period=16, octaves=3) - 0.5) * 0.12 * (1 + params["grain"])
    # Water stains: soft dark blotches.
    stain = fbm(rng, base_period=3, octaves=4)
    tone = tone - np.clip((stain - 0.6) / 0.4, 0, 1) * 0.35 * params["stains"] / 0.3
    # Hairline cracks: wandering lines where a noise field crosses its middle,
    # kept only where a second, coarse field allows (so they stay sparse).
    field = fbm(rng, base_period=6, octaves=4)
    mask = fbm(rng, base_period=2, octaves=2) > 0.55
    crack = (np.abs(field - 0.5) < 0.006) & mask
    tone = np.where(crack, tone - 0.35 * params["cracks"] / 0.2, tone)
    tone = tone + speckle(rng) * 0.05
    return to_uint8(shade(np.clip(tone, 0, 1), base_color, 0.5))


@register("ice")
def ice(params, base_color, seed):
    rng = np.random.default_rng(seed)
    # Depth: cloudy layers inside the ice.
    tone = 0.5 + (fbm(rng, base_period=4, octaves=5) - 0.5) * 0.3
    # Fractures: bright, sharp planes along a cell network.
    f1, f2, _ = cells(18, rng, relax=1)
    gap = f2 - f1
    tone = tone + np.clip(1 - gap / 2.0, 0, 1) * 0.45 * params["fractures"]
    tone = tone - np.clip(1 - np.abs(gap - 4) / 2.0, 0, 1) * 0.12 * params["fractures"]
    # Sheen: soft diagonal bands of light.
    yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    band = np.sin((xx + yy) * 2 * np.pi / SIZE * 2) * 0.5 + 0.5
    tone = tone + (band - 0.5) * 0.25 * params["sheen"]
    tone = tone + speckle(rng) * 0.05
    return to_uint8(shade(np.clip(tone, 0, 1), base_color, 0.45))


@register("sky")
def sky(params, base_color, seed):
    rng = np.random.default_rng(seed)
    clouds = fbm(rng, base_period=3, octaves=5)
    cover = np.clip((clouds - (1 - params["cloud"] * 0.8)) / 0.35, 0, 1)
    base = np.array(base_color, dtype=np.float32)
    white = np.array([235, 236, 238], dtype=np.float32)
    rgb = base * (1 - cover[..., None] * 0.85) + white * (cover[..., None] * 0.85)
    rgb = rgb * (1 + (fbm(rng, base_period=8, octaves=3)[..., None] - 0.5) * 0.08)
    return to_uint8(rgb + speckle(rng)[..., None] * 1.5)
