"""
generators/textures/conformance.py
----------------------------------
Measure and grade textures against the classic look (interesting textures
spec Requirement 5).

``look_stats`` gives a 256x256 image's Look_Stats (the same four numbers the
analyzer writes into each theme's Texture_Profile). ``grade`` moves a painted
texture toward its theme's classic look: brightness and saturation are pulled
part-way to the profile median, then brightness, saturation and contrast are
held just inside the profile's p10-p90 band. Edge energy (fine detail) comes
from the painter and is only checked. Families whose look is outside the
classic band by nature (``EXEMPT``) keep those statistics as painted.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Tuple

import numpy as np

STYLES = Path(__file__).resolve().parent.parent.parent / "styles"
LOOK_KEYS = ("lum_mean", "lum_std", "saturation", "edge_energy")
PULL = 0.5        # how far brightness and saturation move toward the median
INSET = 0.05      # keep this fraction of the band clear at each end

# Statistics a family may leave outside the classic band (Req 5.1): ice is
# bright and pale by nature; sky is bright, pale and smooth.
EXEMPT: Dict[str, Tuple[str, ...]] = {
    "ice": ("lum_mean", "saturation"),
    "sky": ("lum_mean", "lum_std", "saturation", "edge_energy"),
}

_W = np.array([0.2126, 0.7152, 0.0722], dtype=np.float64)


def look_stats(rgb: np.ndarray) -> Dict[str, float]:
    """Look_Stats of an (H, W, 3) uint8 image."""
    f = rgb.astype(np.float64) / 255.0
    lum = f @ _W
    mx, mn = f.max(-1), f.min(-1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    edge = (np.abs(np.diff(lum, axis=1)).mean() + np.abs(np.diff(lum, axis=0)).mean()) / 2
    return {"lum_mean": float(lum.mean()), "lum_std": float(lum.std()),
            "saturation": float(sat.mean()), "edge_energy": float(edge)}


@lru_cache(maxsize=8)
def look_band(theme: str) -> Dict[str, Dict[str, float]]:
    """The theme's measured Look_Stats band (p10/p50/p90 per statistic)."""
    doc = json.loads((STYLES / f"{theme}.json").read_text(encoding="utf-8"))
    return doc["textures"]["look"]


def theme_for(material: str) -> str:
    """Which profile judges a room-graph material: city sets are ``city``,
    everything else a dungeon."""
    return "city" if material == "city" or material.startswith("city_") else "dungeon"


def _inner(band: Dict[str, float]) -> Tuple[float, float]:
    lo, hi = band["p10"], band["p90"]
    pad = (hi - lo) * INSET
    return lo + pad, hi - pad


def _to8(f: np.ndarray) -> np.ndarray:
    return np.rint(np.clip(f, 0.0, 1.0) * 255).astype(np.uint8)


def _blur(f: np.ndarray) -> np.ndarray:
    """3x3 box blur that wraps (keeps the tile seamless)."""
    out = np.zeros_like(f)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            out += np.roll(np.roll(f, dy, axis=0), dx, axis=1)
    return out / 9.0


def _set_saturation(f, current, target):
    lum = (f @ _W)[..., None]
    return lum + (f - lum) * (target / max(current, 1e-6))


def _set_contrast(f, current, target):
    mean = (f @ _W).mean()
    return mean + (f - mean) * (target / max(current, 1e-6))


def _set_brightness(f, current, target):
    return f * (target / max(current, 1e-6))


def _set_detail(f, current, target):
    soft = _blur(f)
    return soft + (f - soft) * (target / max(current, 1e-6))


_ADJUST = {"saturation": _set_saturation, "lum_std": _set_contrast,
           "lum_mean": _set_brightness, "edge_energy": _set_detail}


def grade(rgb: np.ndarray, theme: str, family: str) -> np.ndarray:
    """Move *rgb* toward *theme*'s classic look (see module docstring)."""
    band = look_band(theme)
    exempt = set(EXEMPT.get(family, ()))
    f = rgb.astype(np.float64) / 255.0

    # Once: pull saturation and brightness part-way to the classic median.
    for key in ("saturation", "lum_mean"):
        if key in exempt:
            continue
        cur = look_stats(_to8(f))[key]
        lo, hi = _inner(band[key])
        target = min(max(cur + (band[key]["p50"] - cur) * PULL, lo), hi)
        f = np.clip(_ADJUST[key](f, cur, target), 0.0, 1.0)

    # Then: correct whatever is still outside the band. Clipping at black or
    # white can push one statistic out while fixing another, so repeat.
    for _ in range(12):
        s = look_stats(_to8(f))
        outside = [k for k in LOOK_KEYS if k not in exempt
                   and not band[k]["p10"] <= s[k] <= band[k]["p90"]]
        if not outside:
            break
        for key in outside:
            cur = look_stats(_to8(f))[key]
            lo, hi = _inner(band[key])
            f = np.clip(_ADJUST[key](f, cur, min(max(cur, lo), hi)), 0.0, 1.0)
    return _to8(f)


def out_of_band(stats: Dict[str, float], theme: str, family: str) -> Iterable[str]:
    """The statistics of *stats* outside *theme*'s p10-p90 band, other than
    the family's exemptions."""
    band = look_band(theme)
    exempt = set(EXEMPT.get(family, ()))
    for key in LOOK_KEYS:
        if key in exempt:
            continue
        if not band[key]["p10"] <= stats[key] <= band[key]["p90"]:
            yield key
