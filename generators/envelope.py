"""
generators/envelope.py
----------------------
The 3D volume an outdoor dungeon's rooms and corridors must fit inside
(outdoor-dungeon design "Envelope"): within the Host_Hill's XY footprint,
above a floor limit, and under the hill's surface by at least the Rock_Cover.

It is a continuous predicate, not a voxel grid: ``surface`` is any callable
giving terrain height at XY (vectorised over numpy arrays), and a box is
tested by sampling its footprint every ``sample`` units, edges included.

``LayoutGenerator.generate(envelope=...)`` lays rooms out inside one; with no
Envelope the layout is exactly what it was before this module existed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Tuple

import numpy as np

Point = Tuple[float, float]


class EnvelopeFitError(ValueError):
    """Not even the minimum room count fits inside the Envelope."""


def _inside_polygon(poly: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Even-odd point-in-polygon over arrays of points (boundary counts in)."""
    inside = np.zeros(x.shape, bool)
    on_edge = np.zeros(x.shape, bool)
    n = len(poly)
    for k in range(n):
        x0, y0 = poly[k]
        x1, y1 = poly[(k + 1) % n]
        crosses = ((y0 > y) != (y1 > y))
        with np.errstate(divide="ignore", invalid="ignore"):
            xc = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
        inside ^= crosses & (x < xc)
        # Points on the edge itself (within a hair) are inside.
        ex, ey = x1 - x0, y1 - y0
        length2 = ex * ex + ey * ey
        if length2 > 0:
            t = np.clip(((x - x0) * ex + (y - y0) * ey) / length2, 0.0, 1.0)
            on_edge |= np.hypot(x - (x0 + t * ex), y - (y0 + t * ey)) < 1e-6
    return inside | on_edge


def _convex_halfplanes(poly):
    """A convex polygon's edges as inward half-planes ``(ox, oy, nx, ny)``
    (a point p is inside when ``(p - o) . n >= 0`` for every edge, ``n`` a
    unit inward normal), or None when the polygon isn't convex. Zero-length
    edges (a clip can leave repeated vertices) are skipped."""
    pts = np.asarray(poly, dtype=np.float64)
    nxt = np.roll(pts, -1, axis=0)
    e = nxt - pts
    length = np.hypot(e[:, 0], e[:, 1])
    keep = length > 1e-9
    pts, e, length = pts[keep], e[keep], length[keep]
    if len(pts) < 3:
        return None
    area2 = float(np.sum(pts[:, 0] * np.roll(pts[:, 1], -1) - np.roll(pts[:, 0], -1) * pts[:, 1]))
    if abs(area2) < 1e-9:
        return None
    sign = 1.0 if area2 > 0 else -1.0
    turn = e[:, 0] * np.roll(e[:, 1], -1) - e[:, 1] * np.roll(e[:, 0], -1)
    if np.any(sign * turn < -1e-9):
        return None
    # Inward normal: left of each edge for a counter-clockwise polygon.
    nx, ny = -sign * e[:, 1] / length, sign * e[:, 0] / length
    return pts[:, 0].copy(), pts[:, 1].copy(), nx, ny


@dataclass(frozen=True)
class Envelope:
    """Where the dungeon may go.

    footprint
        The Host_Hill's area as an XY polygon (vertices in order, not closed).
    floor_limit
        The lowest floor (box bottom) allowed.
    surface
        Terrain height at XY; called with numpy arrays.
    rock_cover
        Minimum terrain thickness left above any ceiling.
    sample
        Spacing (u) of the footprint samples a box is tested at.
    entry
        Where the dungeon is entered from (XY), or ``None``. The layout makes
        the room nearest it the entrance room, so the pacing (depth, climax,
        keys) runs from the side the way in is dug from.
    """
    footprint: Tuple[Point, ...]
    floor_limit: float
    surface: Callable[[np.ndarray, np.ndarray], np.ndarray]
    rock_cover: float
    sample: float = 8.0
    entry: Optional[Point] = None

    def __post_init__(self):
        if len(self.footprint) < 3:
            raise ValueError("Envelope footprint needs at least 3 vertices")
        object.__setattr__(self, "footprint",
                           tuple((float(x), float(y)) for x, y in self.footprint))
        if self.entry is not None:
            object.__setattr__(self, "entry", (float(self.entry[0]), float(self.entry[1])))
        object.__setattr__(self, "_halfplanes", _convex_halfplanes(self.footprint))

    # -- footprint ---------------------------------------------------------

    @property
    def centre(self) -> Point:
        """The footprint's vertex centroid (where the layout is centred)."""
        pts = np.asarray(self.footprint)
        cx, cy = pts.mean(axis=0)
        return float(cx), float(cy)

    @property
    def inradius(self) -> float:
        """Distance from ``centre`` to the nearest footprint edge."""
        cx, cy = self.centre
        pts = np.asarray(self.footprint)
        best = math.inf
        for k in range(len(pts)):
            (x0, y0), (x1, y1) = pts[k], pts[(k + 1) % len(pts)]
            ex, ey = x1 - x0, y1 - y0
            length2 = ex * ex + ey * ey
            t = 0.0 if length2 == 0 else min(1.0, max(0.0, ((cx - x0) * ex + (cy - y0) * ey) / length2))
            best = min(best, math.hypot(cx - (x0 + t * ex), cy - (y0 + t * ey)))
        return best

    def _grid(self, x0: float, y0: float, x1: float, y1: float):
        nx = max(2, int(math.ceil((x1 - x0) / self.sample)) + 1)
        ny = max(2, int(math.ceil((y1 - y0) / self.sample)) + 1)
        gx, gy = np.meshgrid(np.linspace(x0, x1, nx), np.linspace(y0, y1, ny))
        return gx.ravel(), gy.ravel()

    def covers(self, x0: float, y0: float, x1: float, y1: float) -> bool:
        """Does the footprint cover the rectangle (sampled, edges included)?

        A convex footprint (a disc, or one clipped to the bowl interior)
        covers it exactly when it covers its four corners, tested against
        every edge at once; the layout asks this of every stair route it
        tries (step 7 task 19), so the sampled test was its hot spot."""
        hp = self._halfplanes
        if hp is not None:
            ox, oy, nx, ny = hp
            px = np.array([x0, x1, x0, x1])
            py = np.array([y0, y0, y1, y1])
            d = (px[None, :] - ox[:, None]) * nx[:, None] + (py[None, :] - oy[:, None]) * ny[:, None]
            return bool((d >= -1e-6).all())
        gx, gy = self._grid(x0, y0, x1, y1)
        return bool(_inside_polygon(np.asarray(self.footprint), gx, gy).all())

    # -- heights -----------------------------------------------------------

    def top_at(self, x, y):
        """The highest a ceiling may reach at XY: surface minus Rock_Cover."""
        return np.asarray(self.surface(np.asarray(x, float), np.asarray(y, float))) - self.rock_cover

    def ceiling_over(self, x0: float, y0: float, x1: float, y1: float) -> float:
        """The lowest ``top_at`` over the rectangle (sampled, edges included)."""
        gx, gy = self._grid(x0, y0, x1, y1)
        return float(np.min(self.top_at(gx, gy)))

    def contains_box(self, x0: float, y0: float, z0: float,
                     x1: float, y1: float, z1: float) -> bool:
        """Is the box ``[x0, x1] x [y0, y1] x [z0, z1]`` inside the Envelope?"""
        if z0 < self.floor_limit - 1e-6:
            return False
        if not self.covers(x0, y0, x1, y1):
            return False
        return z1 <= self.ceiling_over(x0, y0, x1, y1) + 1e-6

    # -- construction helpers ----------------------------------------------

    @classmethod
    def disc(cls, centre: Point, radius: float, *, floor_limit: float,
             surface: Callable, rock_cover: float, sides: int = 64,
             sample: float = 8.0) -> "Envelope":
        """An Envelope over a regular ``sides``-gon approximating a disc."""
        cx, cy = centre
        pts: Sequence[Point] = tuple(
            (cx + radius * math.cos(2 * math.pi * k / sides),
             cy + radius * math.sin(2 * math.pi * k / sides))
            for k in range(sides))
        return cls(pts, floor_limit, surface, rock_cover, sample)
