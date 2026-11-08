"""
generators/textures/sites.py
----------------------------
Procedural textures for Site Structures (wilderness POIs spec task 4, Req 3.4):
timber, crude timber, thatch, hide, canvas and stone.

Procedural only (no provider, no key), seamless (every pattern wraps at the
tile edge), pure (same material and seed, same pixels in any process), and
graded toward the outdoor profile's classic look (``conformance.grade``).
The look is classic: broad tone, few large features, little fine grit.

Texel density
    Every Structure surface repeats at the outdoor profile's measured wall
    density (``styles/outdoor.json`` ``textures.texel_density.wall.p50``,
    31.2 u per repeat at the time of writing). A model's UVs are its surface
    position in world units times :func:`uv_scale`. Each material's features
    (a board, a thatch course, a hide panel, a stone) have a size in world
    units (``FEATURE_U``); the painter fits a whole number of them across the
    tile (:func:`features_per_tile`) so the tile wraps on the density.

UV convention (for the model builder)
    ``u`` runs along a wall (or across a roof or tent), ``v`` runs down it;
    texture rows run top-down (``v = 0`` is the top row), as in the
    vegetation cards. Boards and thatch courses run along ``u``, canvas
    panels run down ``v``.

Material sets
    An Inhabitant names a material set (``MATERIAL_SETS``); the set maps each
    Structure slot (``SLOTS``: wall, roof, tent, wood, stone) to a material.
    :func:`set_material` looks one up; :func:`site_texture_name` and
    :func:`site_texture` give the packed name and the DDS bytes.
"""

from __future__ import annotations

import json
import zlib
from functools import lru_cache
from typing import Callable, Dict, Tuple

import numpy as np

from .conformance import STYLES, grade
from .dds import rgba_to_dds
from .painters import SIZE, cells, fbm, per_cell, shade, speckle, to_uint8
from .painters.natural import _noise_xy, _toroidal

TEXTURE_SIZE = SIZE  # 256, as every generated texture
GRADE_THEME = "outdoor"

MATERIALS: Tuple[str, ...] = ("timber", "crude_timber", "thatch", "hide", "canvas", "stone")
SLOTS: Tuple[str, ...] = ("wall", "roof", "tent", "wood", "stone")

# Inhabitant material sets: slot -> material. ``wood`` is posts, fences and
# poles; ``stone`` is fire rings, standing stones, towers and ruin walls.
MATERIAL_SETS: Dict[str, Dict[str, str]] = {
    # human: plank walls under a thatch roof, canvas tents
    "timber_thatch": {"wall": "timber", "roof": "thatch", "tent": "canvas",
                      "wood": "timber", "stone": "stone"},
    # gnoll: rough logs, hide-covered roofs and tents
    "crude_timber": {"wall": "crude_timber", "roof": "hide", "tent": "hide",
                     "wood": "crude_timber", "stone": "stone"},
    # orc: hide everything, rough log frames
    "hide": {"wall": "hide", "roof": "hide", "tent": "hide",
             "wood": "crude_timber", "stone": "stone"},
    # centaur: hide walls, canvas roofs and tents (the canvas tent variant)
    "hide_canvas": {"wall": "hide", "roof": "canvas", "tent": "canvas",
                    "wood": "timber", "stone": "stone"},
}

# Base colour per material (sRGB), before the classic grade.
BASE_COLOR: Dict[str, Tuple[int, int, int]] = {
    "timber": (118, 86, 56),
    "crude_timber": (96, 76, 56),
    "thatch": (156, 132, 78),
    "hide": (132, 98, 66),
    "canvas": (178, 164, 132),
    "stone": (120, 116, 108),
}

# Feature size in world units: a board's height, a log's, a thatch course's,
# a hide panel's width, a canvas panel's width, a stone's width.
FEATURE_U: Dict[str, float] = {
    "timber": 2.6,
    "crude_timber": 3.1,
    "thatch": 3.9,
    "hide": 10.0,
    "canvas": 7.8,
    "stone": 6.5,
}


class SiteMaterialError(KeyError):
    """An unknown material, set or slot; the message names it."""


@lru_cache(maxsize=1)
def texel_density() -> float:
    """World units per texture repeat on a Structure: the outdoor profile's
    measured wall p50."""
    doc = json.loads((STYLES / f"{GRADE_THEME}.json").read_text(encoding="utf-8"))
    return float(doc["textures"]["texel_density"]["wall"]["p50"])


def uv_scale() -> float:
    """UV units per world unit (``1 / texel_density()``)."""
    return 1.0 / texel_density()


def features_per_tile(material: str) -> int:
    """How many of the material's features fit across one tile."""
    _check_material(material)
    return max(1, round(texel_density() / FEATURE_U[material]))


def set_material(material_set: str, slot: str) -> str:
    """The material a set uses for a slot."""
    if material_set not in MATERIAL_SETS:
        raise SiteMaterialError(f"unknown material set {material_set!r}; "
                                f"known: {', '.join(MATERIAL_SETS)}")
    if slot not in SLOTS:
        raise SiteMaterialError(f"unknown slot {slot!r}; known: {', '.join(SLOTS)}")
    return MATERIAL_SETS[material_set][slot]


def site_texture_name(material: str) -> str:
    _check_material(material)
    return f"site_{material}.dds"


def site_rgb(material: str, seed: int) -> np.ndarray:
    """The graded (256, 256, 3) uint8 image for *material* at *seed*."""
    _check_material(material)
    rng = np.random.default_rng([int(seed) & 0xFFFFFFFF,
                                 zlib.crc32(material.encode("utf-8"))])
    tone = _PAINTERS[material](features_per_tile(material), rng)
    rgb = to_uint8(shade(np.clip(tone, 0, 1), BASE_COLOR[material], _SPREAD[material]))
    rgb = _tint(material, rgb, rng)
    return grade(rgb, GRADE_THEME, material)


def site_texture(material: str, seed: int) -> bytes:
    """The material's texture as DDS bytes (opaque A8R8G8B8, 256x256)."""
    return rgba_to_dds(site_rgb(material, seed))


def _check_material(material: str) -> None:
    if material not in MATERIALS:
        raise SiteMaterialError(f"unknown site material {material!r}; "
                                f"known: {', '.join(MATERIALS)}")


# ---------------------------------------------------------------------------
# Painters: (features per tile, rng) -> tone field in [0, 1]
# ---------------------------------------------------------------------------

_Y = np.arange(SIZE, dtype=np.float32)[:, None] * np.ones((1, SIZE), np.float32)
_X = np.ones((SIZE, 1), np.float32) * np.arange(SIZE, dtype=np.float32)[None, :]


def _soft(f: np.ndarray, passes: int = 1) -> np.ndarray:
    """A wrapped 3x3 box blur (painterly softening that keeps the tile seamless)."""
    for _ in range(passes):
        out = np.zeros_like(f)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                out += np.roll(np.roll(f, dy, axis=0), dx, axis=1)
        f = out / 9.0
    return f


def _courses(n: int, wobble: np.ndarray):
    """Horizontal courses ``n`` to a tile, edges displaced by *wobble* (pixels):
    ``(course index, 0..1 position down the course)``. Offset half a course so
    the tile edge falls mid-course."""
    h = SIZE / n
    y = (_Y + h / 2 + wobble) % SIZE
    idx = (y // h).astype(int) % n
    return idx, (y - (y // h) * h) / h


def _timber(n: int, rng: np.random.Generator, crude: bool = False) -> np.ndarray:
    wobble = (_noise_xy(rng, 6, 1) - 0.5) * (5.0 if crude else 1.0)
    board, t = _courses(n, wobble)
    # Butt joints: each board breaks once at its own x, so tone goes per segment.
    joints = rng.uniform(0, SIZE, n)
    rel = (_X - joints[board]) % SIZE
    seg = board if crude else board * 2 + (rel < SIZE / 2)  # a log runs whole
    tone = 0.5 + per_cell(seg, rng, 0.16 if crude else 0.1)
    # Grain: streaks long along the board.
    streak = _noise_xy(rng, 3, n * 6)
    tone += (streak - 0.5) * (0.32 if crude else 0.24)
    if crude:
        # Round logs: dark toward both edges, lit along the top third.
        tone += (0.18 - 0.55 * (t - 0.4) ** 2)
        # Bark left on in soft patches.
        bark = fbm(rng, base_period=6, octaves=4)
        tone -= np.clip((bark - 0.64) / 0.14, 0, 1) * 0.18
    else:
        # Bevelled boards: a lit top edge, a shaded lower one.
        tone += np.where(t < 0.18, 0.08, 0.0) - np.clip((t - 0.75) / 0.25, 0, 1) * 0.16
        # Butt joint lines.
        butt = (np.abs(_toroidal(rel)) < 1.0) | (np.abs(_toroidal(rel - SIZE / 2)) < 1.0)
        tone = np.where(butt, 0.14, tone)
    # Weathering: broad lighter and darker patches.
    tone += (fbm(rng, base_period=3, octaves=3) - 0.5) * 0.2
    gap = (t > 1 - (0.13 if crude else 0.09))
    tone = np.where(gap, 0.08, tone)
    return _soft(tone) + speckle(rng) * 0.025


def _thatch(n: int, rng: np.random.Generator) -> np.ndarray:
    wobble = (_noise_xy(rng, 16, 1) - 0.5) * 7.0
    course, t = _courses(n, wobble)
    # Straw strands running down each course, varying per course.
    strands = _noise_xy(rng, 64, n * 2)
    strands2 = _noise_xy(rng, 32, n * 3)
    tone = 0.52 + (strands - 0.5) * 0.42 + (strands2 - 0.5) * 0.2
    tone += per_cell(course, rng, 0.06)
    # Each course overlaps the one below: lit at its top, shaded at its lip.
    tone += 0.12 - 0.34 * t ** 2
    # Age: broad dark, slightly greyed patches.
    tone -= np.clip(fbm(rng, base_period=3, octaves=3) - 0.55, 0, 1) * 0.5
    return _soft(tone) + speckle(rng) * 0.03


def _cell_count(n: int) -> int:
    return max(2, n * n)


def _hide(n: int, rng: np.random.Generator) -> np.ndarray:
    f1, f2, owner = cells(_cell_count(n), rng, relax=2)
    gap = f2 - f1
    tone = 0.5 + per_cell(owner, rng, 0.12)
    # Mottling and darker blotches across each skin.
    tone += (fbm(rng, base_period=4, octaves=4) - 0.5) * 0.3
    tone -= np.clip(fbm(rng, base_period=6, octaves=3) - 0.62, 0, 1) * 0.6
    # Skins pucker toward the seams.
    tone -= np.clip(1 - gap / 14.0, 0, 1) * 0.16
    seam = gap < 2.2
    # Stitches: short dark ticks crossing the seam band.
    stitch = (gap < 5.0) & (((_X + _Y) // 4) % 2 == 0) & ~seam
    tone = np.where(seam, 0.1, tone)
    tone = np.where(stitch, tone - 0.2, tone)
    return _soft(tone) + speckle(rng) * 0.02


def _canvas(n: int, rng: np.random.Generator) -> np.ndarray:
    w = SIZE / n
    # Panels run down v; the tile edge falls mid-panel.
    xp = (_X + w / 2) % SIZE
    panel = (xp // w).astype(int) % n
    s = (xp - (xp // w) * w) / w
    tone = 0.55 + per_cell(panel, rng, 0.05)
    # Sag: each panel's cloth bellies, lit in the middle.
    tone += 0.08 * np.cos((s - 0.5) * np.pi) - 0.04
    # Faint weave and broad grime.
    tone += (_noise_xy(rng, 128, 8) - 0.5) * 0.06
    tone -= np.clip(fbm(rng, base_period=3, octaves=4) - 0.5, 0, 1) * 0.55
    # Seams with a double stitch line either side.
    edge = np.minimum(s, 1 - s) * w
    tone = np.where(edge < 1.2, 0.2, tone)
    stitch = (np.abs(edge - 3.5) < 0.7) & ((_Y // 4) % 2 == 0)
    tone = np.where(stitch, tone - 0.15, tone)
    return _soft(tone) + speckle(rng) * 0.02


def _stone(n: int, rng: np.random.Generator) -> np.ndarray:
    f1, f2, owner = cells(_cell_count(n), rng, relax=2)
    gap = f2 - f1
    size = SIZE / n
    tone = 0.5 + per_cell(owner, rng, 0.14)
    # Rounded fieldstones: lit in the middle, dark at the rim.
    tone += np.clip(gap / (size * 0.5), 0, 1) * 0.22 - 0.1
    tone += (fbm(rng, base_period=8, octaves=4) - 0.5) * 0.22
    # Dark packed earth between the stones.
    tone = np.where(gap < 3.0, 0.1 + gap * 0.03, tone)
    return _soft(tone) + speckle(rng) * 0.03


_PAINTERS: Dict[str, Callable[[int, np.random.Generator], np.ndarray]] = {
    "timber": _timber,
    "crude_timber": lambda n, rng: _timber(n, rng, crude=True),
    "thatch": _thatch,
    "hide": _hide,
    "canvas": _canvas,
    "stone": _stone,
}

_SPREAD: Dict[str, float] = {
    "timber": 0.6, "crude_timber": 0.65, "thatch": 0.55,
    "hide": 0.55, "canvas": 0.45, "stone": 0.55,
}


def _tint(material: str, rgb: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """A broad second hue: moss on stone and thatch, soot on canvas."""
    if material not in ("stone", "thatch", "canvas"):
        return rgb
    patch = np.clip((fbm(rng, base_period=3, octaves=3) - 0.55) / 0.3, 0, 1)[..., None]
    hue = {"stone": (86, 100, 66), "thatch": (104, 100, 72), "canvas": (120, 108, 90)}[material]
    out = rgb.astype(np.float32) * (1 - 0.45 * patch) + np.array(hue, np.float32) * 0.45 * patch
    return to_uint8(out)
