"""Placeholder textures (placeholder textures spec task 2, Req 3, property X5).

A Placeholder is a pure function of (name, base colour, Surface_Class): a
pattern per class, the name stamped legibly twice, seamless across the wrap,
the same bytes in a fresh process, and different bytes for different names.
"""

import hashlib
import subprocess
import sys

import numpy as np
import pytest
from hypothesis import given, settings, strategies as st

from generators.textures.font import GLYPH_H, glyph, text_mask
from generators.textures.placeholder import (
    LABEL_ROWS, MARGIN, MAX_LINE, MIN_CONTRAST, PAD, SCALE, SIZE,
    SURFACE_CLASSES, PlaceholderProvider, contrast, label_box, label_colours,
    placeholder_dds, placeholder_rgb, wrap_name)
from generators.textures.base import TextureSpec
from tests.pbt_helpers import scaled

NAMES = st.from_regex(r"[a-z0-9]{1,12}(_[a-z0-9]{1,12}){0,4}", fullmatch=True).filter(
    lambda n: len(n) <= 40)
COLOURS = st.tuples(*(st.integers(0, 255),) * 3)
CLASSES = st.sampled_from(SURFACE_CLASSES)


# ---------------------------------------------------------------------------
# Font
# ---------------------------------------------------------------------------

def test_font_covers_the_name_alphabet():
    for ch in "abcdefghijklmnopqrstuvwxyz0123456789_":
        g = glyph(ch)
        assert g.shape == (7, 5) and g.any()
    assert (glyph("a") == glyph("A")).all()


@pytest.mark.parametrize("ch", ["-", " ", ".", "é"])
def test_font_rejects_unknown_characters(ch):
    with pytest.raises(ValueError):
        glyph(ch)


def test_glyphs_are_distinct():
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
    shapes = {glyph(c).tobytes() for c in alphabet}
    assert len(shapes) == len(alphabet)


# ---------------------------------------------------------------------------
# X5: legible, whole, seamless, pure, distinct
# ---------------------------------------------------------------------------

def _label_layout(name):
    lines = wrap_name(name)
    pw, ph = label_box(lines)
    x0 = (SIZE - pw) // 2
    return lines, pw, ph, x0


def _wrap_ok(img):
    a = img.astype(int)
    for arr in (a, a.transpose(1, 0, 2)):
        inner = np.abs(np.diff(arr, axis=0)).max()
        wrap = np.abs(arr[-1] - arr[0]).max()
        if wrap > inner:
            return False
    return True


@settings(max_examples=scaled(60), deadline=None)
@given(name=NAMES, colour=COLOURS, surface_class=CLASSES)
def test_x5_placeholder_is_legible_whole_and_seamless(name, colour, surface_class):
    img = placeholder_rgb(name, colour, surface_class)
    assert img.shape == (SIZE, SIZE, 3) and img.dtype == np.uint8

    # Legible: glyphs at least 12 px tall, text against plate at 4.5:1.
    assert GLYPH_H * SCALE >= 12
    plate, text = label_colours(colour)
    assert contrast(plate, text) >= MIN_CONTRAST

    # Whole: both labels lie inside the tile, MARGIN px from every edge, and
    # each holds every character of the name (in order, uppercased).
    lines, pw, ph, x0 = _label_layout(name)
    assert "".join(lines) == name.upper()
    assert all(len(l) <= MAX_LINE for l in lines)
    assert x0 >= MARGIN and x0 + pw <= SIZE - MARGIN
    for cy in LABEL_ROWS:
        y0 = cy - ph // 2
        assert y0 >= MARGIN and y0 + ph <= SIZE - MARGIN
        for i, line in enumerate(lines):
            mask = text_mask(line, SCALE)
            ty = y0 + PAD + i * (GLYPH_H * SCALE + 4)
            tx = x0 + (pw - mask.shape[1]) // 2
            region = img[ty:ty + mask.shape[0], tx:tx + mask.shape[1]]
            assert (region[mask] == text).all()
            assert (region[~mask] == plate).all()

    # Seamless: the wrap is no harsher than the worst step inside the tile.
    assert _wrap_ok(img)


@settings(max_examples=scaled(30), deadline=None)
@given(a=NAMES, b=NAMES, colour=COLOURS, surface_class=CLASSES)
def test_x5_different_names_give_different_bytes(a, b, colour, surface_class):
    if a != b:
        assert placeholder_dds(a, colour, surface_class) != placeholder_dds(b, colour, surface_class)


def test_x5_same_bytes_in_a_fresh_process():
    cases = [("gnoll_temple_wall", (135, 122, 100), "wall"),
             ("lizardman_corrupted_sanctum_floor", (78, 74, 82), "floor"),
             ("wild_plains", (104, 132, 70), "ground"),
             ("liquid_water", (70, 140, 190), "liquid"),
             ("city_ceiling", (120, 140, 170), "ceiling")]
    here = [hashlib.sha256(placeholder_dds(*c)).hexdigest() for c in cases]
    code = (
        "import hashlib\n"
        "from generators.textures.placeholder import placeholder_dds\n"
        f"for c in {cases!r}:\n"
        "    print(hashlib.sha256(placeholder_dds(*c)).hexdigest())\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         check=True, env={**__import__("os").environ, "PYTHONHASHSEED": "12345"})
    assert out.stdout.split() == here


def test_the_five_patterns_differ():
    images = {placeholder_rgb("dungeon_wall", (110, 100, 92), c).tobytes()
              for c in SURFACE_CLASSES}
    assert len(images) == len(SURFACE_CLASSES)


@pytest.mark.parametrize("bad", ["", "x" * 41])
def test_name_length_is_checked(bad):
    with pytest.raises(ValueError):
        placeholder_rgb(bad, (100, 100, 100), "floor")


def test_unknown_surface_class_raises():
    with pytest.raises(ValueError):
        placeholder_rgb("dungeon_wall", (100, 100, 100), "roof")


def test_longest_real_name_wraps_on_underscores():
    assert wrap_name("lizardman_corrupted_sanctum_ceiling") == [
        "LIZARDMAN_", "CORRUPTED_SANCTUM_", "CEILING"]


def test_provider_wraps_as_dds():
    spec = TextureSpec(name="city_floor", base_color=(130, 125, 118))
    spec.surface_class = "floor"
    dds = PlaceholderProvider().generate(spec)
    assert dds[:4] == b"DDS " and len(dds) == 128 + SIZE * SIZE * 4
    assert dds == placeholder_dds("city_floor", (130, 125, 118), "floor")
