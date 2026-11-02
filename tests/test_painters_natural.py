"""Timber, plaster, ice and sky painters (interesting textures spec task 5,
Req 4, property Y4).

Same contract as the stone families: each paints a 256x256 image that wraps
seamlessly, is the same in any process and differs from every other family.
"""

import hashlib
import os
import subprocess
import sys

import numpy as np
import pytest

import generators.textures.painters.natural  # noqa: F401  (registers the families)
from generators.textures.painters import PAINTERS, paint, seed_for

# The family defaults in styles/texture_recipes.json (task 3).
NATURAL = {
    "planks":  {"width": 32, "seam": 2, "grain": 0.6, "knots": 3},
    "plaster": {"stains": 0.3, "cracks": 0.2, "grain": 0.2},
    "ice":     {"fractures": 0.5, "sheen": 0.3},
    "sky":     {"cloud": 0.6},
}
STONE_DEFAULTS = {
    "dressed_stone": {"block": [64, 32], "joint": 3, "bevel": 2, "jitter": 0.12, "grain": 0.35},
    "flagstone": {"cells": 9, "joint": 3, "jitter": 0.15, "grain": 0.3},
}
BASE = (128, 112, 96)


def _lum(rgb):
    f = rgb.astype(np.float64) / 255.0
    return 0.2126 * f[..., 0] + 0.7152 * f[..., 1] + 0.0722 * f[..., 2]


@pytest.fixture(scope="module")
def images():
    return {fam: paint(fam, params, BASE, seed_for(f"test_{fam}"))
            for fam, params in NATURAL.items()}


def test_families_are_registered():
    assert set(NATURAL) <= set(PAINTERS)


@pytest.mark.parametrize("family", sorted(NATURAL))
def test_shape_and_type(images, family):
    img = images[family]
    assert img.shape == (256, 256, 3) and img.dtype == np.uint8


@pytest.mark.parametrize("family", sorted(NATURAL))
def test_wraps_seamlessly(images, family):
    lum = _lum(images[family])
    for arr in (lum, lum.T):
        inner = np.abs(np.diff(arr, axis=0)).mean()
        wrap = np.abs(arr[-1] - arr[0]).mean()
        assert wrap <= 1.5 * inner, (family, wrap, inner)


def test_families_differ_from_each_other_and_from_stone(images):
    stone = [paint(f, p, BASE, seed_for(f"test_{f}")) for f, p in STONE_DEFAULTS.items()]
    blobs = {img.tobytes() for img in list(images.values()) + stone}
    assert len(blobs) == len(NATURAL) + len(STONE_DEFAULTS)


@pytest.mark.parametrize("family", ["planks", "plaster", "ice"])
def test_colour_follows_the_base(family):
    mean = paint(family, NATURAL[family], (150, 90, 60), 11).reshape(-1, 3).mean(0)
    assert mean[0] > mean[1] > mean[2]


def test_sky_is_mostly_its_base_colour_with_clouds():
    img = paint("sky", NATURAL["sky"], (120, 140, 170), 5).reshape(-1, 3).astype(int)
    bluish = (img[:, 2] > img[:, 0]).mean()
    white = (img.min(axis=1) > 200).mean()
    assert bluish > 0.5 and 0.02 < white < 0.5


def test_planks_have_seams_between_boards(images):
    rows = _lum(images["planks"]).mean(axis=1)
    dark = rows < rows.mean() - 2 * rows.std()
    assert 4 <= dark.sum() <= 32      # ~8 boards, 2 px seams


def test_same_bytes_in_a_fresh_process(images):
    here = {f: hashlib.sha256(img.tobytes()).hexdigest() for f, img in images.items()}
    code = (
        "import hashlib\n"
        "import generators.textures.painters.natural\n"
        "from generators.textures.painters import paint, seed_for\n"
        f"for fam, params in {NATURAL!r}.items():\n"
        f"    img = paint(fam, params, {BASE!r}, seed_for('test_' + fam))\n"
        "    print(fam, hashlib.sha256(img.tobytes()).hexdigest())\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         check=True, env={**os.environ, "PYTHONHASHSEED": "777"})
    assert dict(line.split() for line in out.stdout.splitlines()) == here
