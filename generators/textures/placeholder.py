"""
generators/textures/placeholder.py
----------------------------------
Placeholder textures that say what they are (placeholder textures spec Req 3).

``placeholder_rgb(name, base_color, surface_class)`` draws a 256×256 tile: the
material's base colour, a line pattern for its Surface_Class (floor tiles,
wall bricks, ceiling hatch, ground dots, liquid waves) and the Material_Name
stamped twice in a bitmap font on a plate chosen for contrast. Every pattern
period divides 256 and the labels stay clear of the edges, so the tile wraps
seamlessly. It is a pure function: no RNG and no ``hash()``, so the same
inputs give the same bytes in any process.
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np

from .base import TextureProvider, TextureSpec
from .dds import rgba_to_dds
from .font import GLYPH_H, GLYPH_W, text_mask

SIZE = 256
SURFACE_CLASSES = ("floor", "wall", "ceiling", "ground", "liquid")

LINE_DARKEN = 0.7          # pattern lines: base colour × this
MAX_NAME = 40              # Material_Names are at most 40 characters (Req 1.1)
SCALE = 2                  # glyphs drawn at 10×14 px
SPACING = 2                # px between glyphs
LINE_GAP = 4               # px between text lines
PAD = 6                    # px of plate around the text
MARGIN = 8                 # px every plate keeps clear of the tile edges
LABEL_ROWS = (64, 192)     # the two label centres (y)
MIN_CONTRAST = 4.5

_ADVANCE = GLYPH_W * SCALE + SPACING
MAX_LINE = (SIZE - 2 * MARGIN - 2 * PAD + SPACING) // _ADVANCE   # 19 characters


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

def pattern_mask(surface_class: str) -> np.ndarray:
    """The (256, 256) bool line mask for a Surface_Class. Every period divides
    256, so the mask tiles."""
    y, x = np.mgrid[0:SIZE, 0:SIZE]
    if surface_class == "floor":            # square tiles, 64 px
        return (x % 64 < 2) | (y % 64 < 2)
    if surface_class == "wall":             # running-bond bricks, 32 × 64 px
        shift = np.where((y // 32) % 2 == 1, 32, 0)
        return (y % 32 < 2) | ((x + shift) % 64 < 2)
    if surface_class == "ceiling":          # 45° hatch, 32 px apart
        return (x + y) % 32 < 2
    if surface_class == "ground":           # 4 px dots on a 32 px lattice
        shift = np.where((y // 32) % 2 == 1, 16, 0)
        return ((x + shift) % 32 < 4) & (y % 32 < 4)
    if surface_class == "liquid":           # sine waves, 32 px apart
        wave = 4.0 * np.sin(2.0 * np.pi * x / 64.0)
        return np.abs(((y - wave) % 32) - 16) < 1.0
    raise ValueError(f"unknown surface class {surface_class!r}")


# ---------------------------------------------------------------------------
# Contrast (WCAG relative luminance)
# ---------------------------------------------------------------------------

def _channel(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb) -> float:
    r, g, b = (_channel(float(v)) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


WHITE = (255, 255, 255)
INK_DARK = (16, 16, 16)


def label_colours(base) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
    """``(plate, text)``: the plate is the base colour moved as little as
    possible (darkened under white text, or lightened under dark text) until
    the text reads at ``MIN_CONTRAST``."""
    base = np.array(base, dtype=np.float64)
    options = []
    for text, target in ((WHITE, np.zeros(3)), (INK_DARK, np.full(3, 255.0))):
        for step in range(0, 101):
            t = step / 100.0
            plate = tuple(int(round(v)) for v in base * (1 - t) + target * t)
            if contrast(plate, text) >= MIN_CONTRAST:
                options.append((t, plate, text))
                break
    _, plate, text = min(options)
    return plate, text


# ---------------------------------------------------------------------------
# Label layout
# ---------------------------------------------------------------------------

def wrap_name(name: str) -> List[str]:
    """Upper-case *name* in lines of at most ``MAX_LINE`` characters, breaking
    after an ``_`` where it can and inside a word only when it must."""
    words = [w + "_" for w in name.upper().split("_")]
    words[-1] = words[-1][:-1]
    lines: List[str] = []
    cur = ""
    for w in words:
        while len(w) > MAX_LINE:                 # an overlong word: hard split
            if cur:
                lines.append(cur)
                cur = ""
            lines.append(w[:MAX_LINE])
            w = w[MAX_LINE:]
        if len(cur) + len(w) > MAX_LINE:
            lines.append(cur)
            cur = w
        else:
            cur += w
    if cur:
        lines.append(cur)
    return lines


def label_box(lines: List[str]) -> Tuple[int, int]:
    """(width, height) of the plate holding *lines*."""
    text_w = max(len(l) for l in lines) * _ADVANCE - SPACING
    text_h = len(lines) * (GLYPH_H * SCALE + LINE_GAP) - LINE_GAP
    return text_w + 2 * PAD, text_h + 2 * PAD


def _validate(name: str) -> None:
    if not name or len(name) > MAX_NAME:
        raise ValueError(f"placeholder name must be 1-{MAX_NAME} characters: {name!r}")


# ---------------------------------------------------------------------------
# The texture
# ---------------------------------------------------------------------------

def placeholder_rgb(name: str, base_color, surface_class: str) -> np.ndarray:
    """The (256, 256, 3) uint8 Placeholder for one material (Req 3.1)."""
    _validate(name)
    base = np.array(base_color, dtype=np.float64)
    img = np.empty((SIZE, SIZE, 3), dtype=np.float64)
    img[:] = base
    img[pattern_mask(surface_class)] = base * LINE_DARKEN

    lines = wrap_name(name)
    plate, text = label_colours(base_color)
    pw, ph = label_box(lines)
    x0 = (SIZE - pw) // 2
    for cy in LABEL_ROWS:
        y0 = cy - ph // 2
        img[y0:y0 + ph, x0:x0 + pw] = plate
        for i, line in enumerate(lines):
            mask = text_mask(line, SCALE, SPACING)
            ty = y0 + PAD + i * (GLYPH_H * SCALE + LINE_GAP)
            tx = x0 + (pw - mask.shape[1]) // 2
            region = img[ty:ty + mask.shape[0], tx:tx + mask.shape[1]]
            region[mask] = text
    return np.clip(np.rint(img), 0, 255).astype(np.uint8)


def placeholder_dds(name: str, base_color, surface_class: str) -> bytes:
    return rgba_to_dds(placeholder_rgb(name, base_color, surface_class))


class PlaceholderProvider(TextureProvider):
    """Texture_Mode ``placeholder``: draws every material as a labelled
    Placeholder. Needs the spec's ``surface_class`` (task 3 adds it to
    ``TextureSpec``); a spec without one draws as ``floor``."""

    name = "placeholder"

    def generate(self, spec: TextureSpec) -> bytes:
        surface_class = getattr(spec, "surface_class", "") or "floor"
        return placeholder_dds(spec.name, spec.base_color, surface_class)
