"""Stone painters (interesting textures spec task 4, Req 4, property Y4).

Each stone family paints a 256x256 image that wraps seamlessly, is the same in
any process (crc32 seeds, never the salted ``hash()``), differs from every
other family, and carries classic-level fine detail (edge energy >= 0.02 at a
mid-grey base, against 0.007 for today's noise textures).
"""

import hashlib
import os
import subprocess
import sys
import zlib

import numpy as np
import pytest

from generators.textures.painters import PAINTERS, paint, seed_for

# The family defaults in styles/texture_recipes.json (task 3), so the
# painters are tested on the parameters builds will pass.
STONE = {
    "dressed_stone": {"block": [64, 32], "joint": 3, "bevel": 2, "jitter": 0.12, "grain": 0.35},
    "brick":         {"block": [32, 16], "joint": 2, "bevel": 1, "jitter": 0.15, "grain": 0.25},
    "flagstone":     {"cells": 9, "joint": 3, "jitter": 0.15, "grain": 0.3},
    "cobble":        {"cells": 40, "joint": 3, "jitter": 0.2, "bulge": 0.6},
    "cave_rock":     {"scale": 4, "strata": 0.3, "grain": 0.5, "crack": 0.4},
}
MID_GREY = (128, 128, 128)


def _lum(rgb):
    f = rgb.astype(np.float64) / 255.0
    return 0.2126 * f[..., 0] + 0.7152 * f[..., 1] + 0.0722 * f[..., 2]


def edge_energy(rgb):
    lum = _lum(rgb)
    return (np.abs(np.diff(lum, axis=1)).mean() + np.abs(np.diff(lum, axis=0)).mean()) / 2


@pytest.fixture(scope="module")
def images():
    return {fam: paint(fam, params, MID_GREY, seed_for(f"test_{fam}"))
            for fam, params in STONE.items()}


def test_every_stone_family_is_registered():
    assert set(STONE) <= set(PAINTERS)


@pytest.mark.parametrize("family", sorted(STONE))
def test_shape_and_type(images, family):
    img = images[family]
    assert img.shape == (256, 256, 3) and img.dtype == np.uint8


@pytest.mark.parametrize("family", sorted(STONE))
def test_wraps_seamlessly(images, family):
    """The step across the wrap looks like any step inside the tile: its mean
    is no more than 1.5x the mean step between neighbouring rows/columns."""
    lum = _lum(images[family])
    for arr in (lum, lum.T):
        inner = np.abs(np.diff(arr, axis=0)).mean()
        wrap = np.abs(arr[-1] - arr[0]).mean()
        assert wrap <= 1.5 * inner, (family, wrap, inner)


@pytest.mark.parametrize("family", sorted(STONE))
def test_classic_level_fine_detail(images, family):
    assert edge_energy(images[family]) >= 0.02


def test_families_differ(images):
    blobs = {img.tobytes() for img in images.values()}
    assert len(blobs) == len(STONE)


@pytest.mark.parametrize("family", sorted(STONE))
def test_colour_follows_the_base(family):
    """A warm base gives a warm texture: the mean colour keeps the base's
    channel order."""
    img = paint(family, STONE[family], (150, 90, 60), 11).reshape(-1, 3).mean(0)
    assert img[0] > img[1] > img[2]


def test_seed_for_is_crc32():
    assert seed_for("gnoll_temple_wall") == zlib.crc32(b"gnoll_temple_wall") & 0x7FFFFFFF


def test_same_bytes_in_a_fresh_process(images):
    here = {f: hashlib.sha256(img.tobytes()).hexdigest() for f, img in images.items()}
    code = (
        "import hashlib\n"
        "from generators.textures.painters import paint, seed_for\n"
        f"for fam, params in {STONE!r}.items():\n"
        f"    img = paint(fam, params, {MID_GREY!r}, seed_for('test_' + fam))\n"
        "    print(fam, hashlib.sha256(img.tobytes()).hexdigest())\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         check=True, env={**os.environ, "PYTHONHASHSEED": "4242"})
    there = dict(line.split() for line in out.stdout.splitlines())
    assert there == here


def test_unknown_family_raises():
    with pytest.raises(KeyError):
        paint("marble", {}, MID_GREY, 1)
