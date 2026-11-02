"""
generators/textures/painters
----------------------------
Structured texture painters (interesting textures spec Requirement 4).

A painter draws one Texture_Family: ``paint(params, base_color, seed) ->
(256, 256, 3) uint8``. This module holds what the families share, all
vectorised numpy and all tileable (every pattern wraps at the tile edge):

* ``seed_for(name)`` — a crc32 seed (never the salted builtin ``hash()``);
* ``fbm`` — fractal tileable value noise;
* ``cells`` — tileable Worley cells (nearest and second-nearest feature
  distances and the owning cell) via a periodic KD-tree;
* ``ashlar`` — courses of blocks of varying width (dressed stone, brick);
* ``shade`` — turn a 0..1 tone field into RGB around a base colour;
* ``PAINTERS`` / ``paint(family, …)`` — the family registry.
"""

from __future__ import annotations

import zlib
from typing import Callable, Dict, Tuple

import numpy as np
from scipy.spatial import cKDTree

SIZE = 256

Painter = Callable[[dict, Tuple[int, int, int], int], np.ndarray]
PAINTERS: Dict[str, Painter] = {}


def register(family: str):
    def deco(fn: Painter) -> Painter:
        PAINTERS[family] = fn
        return fn
    return deco


def paint(family: str, params: dict, base_color, seed: int) -> np.ndarray:
    """Draw *family* with *params* in *base_color*; ``KeyError`` if unknown."""
    return PAINTERS[family](params, tuple(int(c) for c in base_color), int(seed))


def seed_for(name: str) -> int:
    """A stable 31-bit seed for a material name (same in every process)."""
    return zlib.crc32(name.encode("utf-8")) & 0x7FFFFFFF


# ---------------------------------------------------------------------------
# Noise
# ---------------------------------------------------------------------------

def _value_noise(size: int, period: int, rng: np.random.Generator) -> np.ndarray:
    """Tileable value noise on a ``period``-cell lattice, quintic-smoothed."""
    lattice = rng.random((period, period), dtype=np.float32)
    coords = np.arange(size, dtype=np.float32) * period / size
    i0 = np.floor(coords).astype(int)
    f = coords - i0
    s = f * f * f * (f * (f * 6 - 15) + 10)
    i0 %= period
    i1 = (i0 + 1) % period
    top = lattice[i0][:, i0] * (1 - s)[None, :] + lattice[i0][:, i1] * s[None, :]
    bot = lattice[i1][:, i0] * (1 - s)[None, :] + lattice[i1][:, i1] * s[None, :]
    return top * (1 - s)[:, None] + bot * s[:, None]


def fbm(rng: np.random.Generator, base_period: int = 4, octaves: int = 6,
        gain: float = 0.55, size: int = SIZE) -> np.ndarray:
    """Fractal tileable noise in [0, 1]. Periods double per octave and are
    capped at ``size`` (one lattice cell per pixel), so it always wraps."""
    total = np.zeros((size, size), dtype=np.float32)
    amp, norm, period = 1.0, 0.0, base_period
    for _ in range(octaves):
        total += amp * _value_noise(size, min(period, size), rng)
        norm += amp
        amp *= gain
        period *= 2
    total /= norm
    lo, hi = total.min(), total.max()
    return (total - lo) / max(hi - lo, 1e-6)


def speckle(rng: np.random.Generator, size: int = SIZE) -> np.ndarray:
    """Per-pixel noise in [-1, 1] (the classic textures' fine grit)."""
    return rng.random((size, size), dtype=np.float32) * 2 - 1


# ---------------------------------------------------------------------------
# Cells
# ---------------------------------------------------------------------------

def cells(n: int, rng: np.random.Generator, size: int = SIZE,
          relax: int = 1) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Tileable Worley cells over ``n`` feature points: ``(f1, f2, owner)``,
    the distances in pixels to the nearest and second-nearest point and the
    nearest point's index. ``relax`` Lloyd steps even out the cell sizes."""
    pts = rng.random((n, 2)) * size
    yy, xx = np.mgrid[0:size, 0:size]
    pix = np.stack([yy.ravel(), xx.ravel()], axis=1).astype(np.float64) + 0.5
    for _ in range(relax):
        _, idx = cKDTree(pts, boxsize=size).query(pix, k=1)
        for i in range(n):
            mine = pix[idx == i]
            if len(mine):
                # Circular mean keeps a cell that straddles the wrap whole.
                ang = mine / size * 2 * np.pi
                pts[i] = (np.arctan2(np.sin(ang).mean(0), np.cos(ang).mean(0))
                          / (2 * np.pi) * size) % size
    dist, idx = cKDTree(pts, boxsize=size).query(pix, k=2)
    shape = (size, size)
    return (dist[:, 0].reshape(shape).astype(np.float32),
            dist[:, 1].reshape(shape).astype(np.float32),
            idx[:, 0].reshape(shape))


# ---------------------------------------------------------------------------
# Block layouts
# ---------------------------------------------------------------------------

def ashlar(block_w: int, block_h: int, jitter: float, rng: np.random.Generator,
           bond: bool = True, size: int = SIZE):
    """Courses of blocks: ``(block_id, dist_x, dist_y, dist_edge)``.

    Courses are ``block_h`` tall (rounded so they divide ``size``); within a
    course, block widths vary by ``jitter`` around ``block_w`` and the
    course's joints wrap round the tile. With ``bond`` alternate courses start
    roughly half a block along (a running bond). ``dist_x``/``dist_y`` are the
    signed offsets (pixels) to the block's left/top edge."""
    rows = max(1, round(size / block_h))
    h = size / rows
    block_id = np.zeros((size, size), dtype=np.int64)
    dx = np.zeros((size, size), dtype=np.float32)    # from the block's left edge
    width = np.ones((size, size), dtype=np.float32)
    next_id = 0
    x = np.arange(size, dtype=np.float64)
    for r in range(rows):
        y0, y1 = int(round(r * h)), int(round((r + 1) * h))
        widths = []
        while sum(widths) < size:
            widths.append(max(4.0, block_w * (1 + jitter * rng.uniform(-1, 1))))
        scale = size / sum(widths)
        widths = np.array(widths) * scale
        start = ((r % 2) * block_w * 0.5 if bond else 0.0) + rng.uniform(-0.15, 0.15) * block_w
        edges = start + np.concatenate([[0.0], np.cumsum(widths)])
        rel = (x - edges[0]) % size
        k = np.searchsorted(edges[1:] - edges[0], rel, side="right")
        k = np.minimum(k, len(widths) - 1)
        left = (edges[k] - edges[0])
        block_id[y0:y1] = (next_id + k)[None, :]
        dx[y0:y1] = (rel - left)[None, :]
        width[y0:y1] = widths[k][None, :]
        next_id += len(widths)
    yy = np.arange(size, dtype=np.float64)
    dy = ((yy % h)[:, None] * np.ones((1, size))).astype(np.float32)
    edge = np.minimum.reduce([dx, width - dx, dy, np.float32(h) - dy])
    return block_id, dx, dy, edge, width, np.float32(h)


# ---------------------------------------------------------------------------
# Colour
# ---------------------------------------------------------------------------

def shade(tone: np.ndarray, base_color, spread: float = 0.55) -> np.ndarray:
    """RGB from a tone field (0.5 = the base colour): darker below, lighter
    above, by up to ``spread`` of the base colour either way."""
    base = np.array(base_color, dtype=np.float32)
    k = 1.0 + (tone[..., None] - 0.5) * 2.0 * spread
    return np.clip(base * k, 0, 255)


def to_uint8(rgb: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(rgb), 0, 255).astype(np.uint8)


def per_cell(ids: np.ndarray, rng: np.random.Generator, amount: float) -> np.ndarray:
    """A random tone offset in [-amount, amount] per cell id."""
    offsets = rng.uniform(-amount, amount, int(ids.max()) + 1).astype(np.float32)
    return offsets[ids]


# Families register themselves on import.
from . import stone  # noqa: E402,F401
