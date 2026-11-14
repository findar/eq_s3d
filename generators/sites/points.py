"""Where Sites may stand: the World's point Site Sockets (roadmap step 13, Requirement 2;
design "How the World chooses them", "What a point holds").

:func:`site_points` is a pure function of the World's own inputs (its terrain, Spawn and
seed), the biome, and the Site rules' ground needs and the biome's ``groups`` block. It
reads no Sites control, no Inhabitant and no room field (Req 2.1), and draws from its OWN
salted stream (``_salted_seed(seed, *POINTS_SALT)``), so the terrain's stream and the
trees' never move. In five steps:

1. **Ground**: placement's own ``_terrain`` with no Kept_Clear beyond the trees' (Spawn
   clearing, zoneline approaches, shores): Site-eligible quads (the trees' Eligible_Ground,
   reached from Spawn, playable, dry), their slope, height rank, water and zoneline
   distances. Per slope a recipe uses, the eligible mask at that slope.
2. **How many**: ``n_offer = max(2 * dense_top, MIN_OFFER)``, ``dense_top`` the Dense
   control's largest target on this ground (the biome's band, never the Sites control).
3. **Groups**: a size drawn from the biome's shares; its first point a uniform spot on
   eligible ground where some recipe fits, ``spacing`` from every other Group's points;
   each further point a ``within`` distance from a point of its Group, no nearer than
   ``within``'s low to any of them. Every point's smallest-outer disc keeps ``CLEAR_WIDTH``
   from every other's. A point not placed in ``TRIES`` tries ends its Group.
4. **Until** ``n_offer`` points or no Group can start. Given ``hill`` (a hillside Socket's
   footprint), points over it come last, as spares: they keep ``spacing`` from the Groups off
   the hill, not from each other (the hillside Attachment's Kept_Clear drops the ones over the
   dungeon).
5. Each point's Free radius per recipe slope, height rank, clearing, water and zoneline
   distances, read off step 1.

A point's **Free radius** at a slope is the radius of the largest disc round it whose ground
is all eligible at that slope: the distance to the nearest quad that isn't (or is off the
grid), the disc placement's ``Ground.disc_on_eligible`` tests, rounded down to ``FREE_STEP``
and capped at ``FREE_CAP``. A recipe fits a point when its ``radius + margin`` is within the
Free radius at its own slope.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.ndimage import distance_transform_edt, uniform_filter

from generators.sites.placement import CLEAR_WIDTH, CLEARING_QUADS, _terrain
from generators.sites.rules import DENSITIES, SiteRules, load_sites

#: The points' own stream: ``_salted_seed(seed, "sites", "points")``.
POINTS_SALT: Tuple[str, ...] = ("sites", "points")
#: The fewest points a World offers (design step 2).
MIN_OFFER = 6
#: Tries a point gets (a Group's first, or a further one) before its Group ends.
TRIES = 48
#: Tries a new Group's first point gets before no Group can start.
START_TRIES = 4 * TRIES
#: Free radii are measured out to this far (u; past every recipe's outer) and rounded down to
#: ``FREE_STEP``.
FREE_CAP = 160.0
FREE_STEP = 0.25
#: Points are rounded to this many decimals (u): their text stays short.
XY_DIGITS = 2


@dataclass(frozen=True)
class Point:
    """One point Socket's data (design "What a point holds"). ``free`` maps a recipe slope
    (``"8"`` for 8 degrees) to the Free radius there; ``hill`` says it stands over the
    hillside Socket's footprint (a spare)."""
    id: str
    x: float
    y: float
    z: float
    group: int
    rank: int
    free: Dict[str, float]
    height_rank: float
    clearing: float
    water_d: Optional[float]
    zoneline_d: Optional[float]
    hill: bool = False

    def ground(self) -> Dict[str, Any]:
        """The Socket's ``ground``: plain JSON."""
        return {"group": self.group, "rank": self.rank, "free": dict(self.free),
                "height_rank": self.height_rank, "clearing": self.clearing,
                "water_d": self.water_d, "zoneline_d": self.zoneline_d, "hill": self.hill}


def slope_key(slope_deg: float) -> str:
    """A recipe slope as a ``free`` key: ``8.0`` -> ``"8"``."""
    return f"{slope_deg:g}"


def _needs(rules: SiteRules) -> List[Tuple[float, float]]:
    """Each recipe's (slope, outer), outer = ground radius + margin, deduplicated, sorted."""
    return sorted({(r.ground.slope_deg, r.ground.radius + r.ground.margin) for r in rules.kinds.values()})


def offer_count(rules: SiteRules, biome: str, area: float) -> int:
    """``n_offer``: twice the Dense control's largest target on ``area`` u^2 of reached ground,
    at least ``MIN_OFFER``."""
    hi = rules.biomes[biome].density[1] * DENSITIES["dense"]
    return max(2 * int(math.ceil(hi * area / 1e6 - 1e-9)), MIN_OFFER)


def _inside(poly: Sequence[Sequence[float]], x: float, y: float) -> bool:
    """Point in polygon (even-odd)."""
    inside = False
    for k in range(len(poly)):
        x0, y0 = poly[k - 1]
        x1, y1 = poly[k]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def _inside_grid(poly: Sequence[Sequence[float]], xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """:func:`_inside` at every ``(xs[i], ys[j])``."""
    x, y = xs[:, None], ys[None, :]
    inside = np.zeros((len(xs), len(ys)), dtype=bool)
    for k in range(len(poly)):
        x0, y0 = poly[k - 1]
        x1, y1 = poly[k]
        if y0 == y1:
            continue
        inside ^= ((y0 > y) != (y1 > y)) & (x < x0 + (y - y0) * (x1 - x0) / (y1 - y0))
    return inside


class _Hill:
    """Whether a spot stands over the hill's footprint: read off the quad where all its
    corners agree and no footprint vertex lies in it, else tested exactly."""

    def __init__(self, poly: Sequence[Sequence[float]], shape: Tuple[int, int],
                 origin: Tuple[float, float], res: float):
        self.poly = [(float(p[0]), float(p[1])) for p in poly]
        ox, oy = origin
        vx = ox + (np.arange(shape[0] + 1) + 0.5) * res
        vy = oy + (np.arange(shape[1] + 1) + 0.5) * res
        over = _inside_grid(self.poly, vx, vy)
        self.any = over[:-1, :-1] | over[1:, :-1] | over[1:, 1:] | over[:-1, 1:]
        self.all = over[:-1, :-1] & over[1:, :-1] & over[1:, 1:] & over[:-1, 1:]
        self.exact = self.any & ~self.all
        for px, py in self.poly:
            i, j = int(math.floor((px - ox) / res - 0.5)), int(math.floor((py - oy) / res - 0.5))
            if 0 <= i < shape[0] and 0 <= j < shape[1]:
                self.exact[i, j] = True

    def over(self, q: Tuple[int, int], x: float, y: float) -> bool:
        if self.exact[q]:
            return _inside(self.poly, x, y)
        return bool(self.all[q])


class _Free:
    """Free radii on a quad grid: each quad's slope where it is Site-eligible (infinite where
    not), padded with infinite quads past the grid, so a window is a slice."""

    def __init__(self, base: np.ndarray, slope: np.ndarray, keys: Dict[str, float],
                 origin: Tuple[float, float], res: float):
        self.keys = keys
        self.origin, self.res = origin, res
        self.pad = int(math.ceil(FREE_CAP / res)) + 2
        self.level = np.pad(np.where(base, slope, np.inf), self.pad, constant_values=np.inf)

    def at(self, x: float, y: float) -> Dict[str, float]:
        """Per slope key, the Free radius at ``(x, y)``: the distance to the nearest quad not
        eligible at that slope (off the grid counts), measured as ``disc_on_eligible`` does."""
        ox, oy = self.origin
        res, pad = self.res, self.pad
        i0 = int(math.floor((x - FREE_CAP - ox) / res - 0.5))
        i1 = int(math.floor((x + FREE_CAP - ox) / res - 0.5))
        j0 = int(math.floor((y - FREE_CAP - oy) / res - 0.5))
        j1 = int(math.floor((y + FREE_CAP - oy) / res - 0.5))
        qx0 = ox + (np.arange(i0, i1 + 1) + 0.5) * res
        qy0 = oy + (np.arange(j0, j1 + 1) + 0.5) * res
        dx = np.maximum(np.maximum(qx0 - x, 0.0), x - (qx0 + res))
        dy = np.maximum(np.maximum(qy0 - y, 0.0), y - (qy0 + res))
        d2 = dx[:, None] * dx[:, None] + dy[None, :] * dy[None, :]
        win = self.level[i0 + pad:i1 + 1 + pad, j0 + pad:j1 + 1 + pad]
        out = {}
        for k, s in self.keys.items():
            bad = d2[win > s]
            d = FREE_CAP if not len(bad) else min(math.sqrt(float(bad.min())), FREE_CAP)
            # Strictly inside the distance, so ``disc_on_eligible`` (a strict test) agrees.
            out[k] = max(math.floor(d / FREE_STEP - 1e-6) * FREE_STEP, 0.0)
        return out


def site_points(terrain, spawn: Sequence[float], seed: int, biome: str = "plains",
                rules: Optional[SiteRules] = None,
                hill: Optional[Sequence[Sequence[float]]] = None) -> List[Point]:
    """The World's point Site Sockets, in rank order (Requirement 2). Pure.

    ``terrain`` is the World's ``Terrain``; ``spawn`` its Spawn (``x, y[, z]``); ``seed`` the
    World's seed (the points salt their own stream from it); ``biome`` names the Site rules'
    biome, whose ``groups`` block shapes the Groups; ``hill`` a hillside Socket's footprint
    polygon, whose points come last as spares."""
    rules = rules or load_sites()
    groups = rules.biomes[biome].groups
    if groups is None:
        raise ValueError(f"biome {biome!r} has no groups block in its Site rules")
    from generators.wilderness.build import _salted_seed

    spawn_xy = (float(spawn[0]), float(spawn[1]))
    t = _terrain(terrain, spawn_xy, ())
    g = t.ground
    res = g.res
    needs = _needs(rules)
    slopes = sorted({s for s, _ in needs})
    masks = {slope_key(s): t.base & (t.slope <= s) for s in slopes}
    free = _Free(t.base, t.slope, {slope_key(s): s for s in slopes}, g.origin, res)
    area = float(t.reached.sum()) * res * res
    n_offer = offer_count(rules, biome, area)

    # Quads where some recipe could fit at some spot: a necessary test (a spot in the quad is
    # at most res/sqrt(2) from its centre), so sampling wastes few tries.
    could = np.zeros(t.base.shape, dtype=bool)
    for s, outer in needs:
        m = masks[slope_key(s)]
        edt = distance_transform_edt(np.pad(m, 1))[1:-1, 1:-1] * res
        could |= m & (edt + res / math.sqrt(2.0) >= outer)
    clearing = uniform_filter(t.base.astype(np.float64), size=2 * CLEARING_QUADS + 1, mode="constant")

    rng = random.Random(_salted_seed(int(seed) & 0x7FFFFFFF, *POINTS_SALT))
    sizes = sorted(groups.sizes)
    shares = [groups.sizes[k] for k in sizes]
    lo, hi = groups.within

    # Placed points: x, y, smallest outer, Group, over the hill, free.
    px: List[float] = []
    py: List[float] = []
    p_outer: List[float] = []
    p_group: List[int] = []
    p_hill: List[bool] = []
    p_free: List[Dict[str, float]] = []

    def fit(x: float, y: float, on_hill: bool) -> Optional[Tuple[float, Dict[str, float]]]:
        """The smallest outer of the recipes that fit at ``(x, y)``, and its Free radii."""
        q = t.quad_at(x, y)
        if q is None or not could[q]:
            return None
        if over is not None and over.over(q, x, y) != on_hill:
            return None
        f = free.at(x, y)
        outers = [outer for s, outer in needs if f[slope_key(s)] >= outer]
        return (min(outers), f) if outers else None

    def accept(x: float, y: float, group: int, on_hill: bool) -> Optional[Tuple[float, Dict[str, float]]]:
        got = fit(x, y, on_hill)
        if got is None:
            return None
        outer, _ = got
        if px:
            ax, ay = np.asarray(px), np.asarray(py)
            d = np.hypot(ax - x, ay - y)
            if np.any(d < outer + np.asarray(p_outer) + CLEAR_WIDTH):
                return None
            mine = np.asarray(p_group) == group
            if np.any(d[mine] < lo):
                return None
            others = ~mine
            if on_hill:     # spares keep spacing from the Groups off the hill only
                others &= ~np.asarray(p_hill)
            if np.any(d[others] < groups.spacing):
                return None
        return got

    def add(x: float, y: float, group: int, on_hill: bool, got) -> None:
        px.append(x)
        py.append(y)
        p_outer.append(got[0])
        p_group.append(group)
        p_hill.append(on_hill)
        p_free.append(got[1])

    over = None if hill is None else _Hill(hill, could.shape, g.origin, res)
    if over is not None:
        phases = ((False, could & ~over.all), (True, could & over.any))
    else:
        phases = ((False, could),)
    group = 0
    for on_hill, where in phases:
        cells = np.argwhere(where)
        while len(px) < n_offer and len(cells):
            size = rng.choices(sizes, weights=shares)[0]
            start = None
            for _ in range(START_TRIES):
                i, j = cells[rng.randrange(len(cells))]
                x0, y0, _, _ = g.quad_rect(int(i), int(j))
                x = round(x0 + rng.random() * res, XY_DIGITS)
                y = round(y0 + rng.random() * res, XY_DIGITS)
                got = accept(x, y, group, on_hill)
                if got is not None:
                    start = (x, y, got)
                    break
            if start is None:
                break
            add(start[0], start[1], group, on_hill, start[2])
            members = [len(px) - 1]
            while len(members) < size and len(px) < n_offer:
                placed = False
                for _ in range(TRIES):
                    m = members[rng.randrange(len(members))]
                    d = rng.uniform(lo, hi)
                    a = rng.uniform(0.0, 2.0 * math.pi)
                    x = round(px[m] + d * math.cos(a), XY_DIGITS)
                    y = round(py[m] + d * math.sin(a), XY_DIGITS)
                    if math.hypot(x - px[m], y - py[m]) > hi:
                        continue
                    got = accept(x, y, group, on_hill)
                    if got is not None:
                        add(x, y, group, on_hill, got)
                        members.append(len(px) - 1)
                        placed = True
                        break
                if not placed:
                    break
            group += 1

    out = []
    for k in range(len(px)):
        x, y = float(px[k]), float(py[k])
        i, j = t.quad_at(x, y)
        out.append(Point(
            id=f"site{k}", x=x, y=y, z=g.surface_z(x, y), group=p_group[k], rank=k,
            free=p_free[k], height_rank=round(float(t.height_rank[i, j]), 4),
            clearing=round(float(clearing[i, j]), 4),
            water_d=None if t.water_d is None else round(float(t.water_d[i, j]), 1),
            zoneline_d=None if t.zoneline_d is None else round(float(t.zoneline_d[i, j]), 1),
            hill=p_hill[k]))
    return out


__all__ = ["FREE_CAP", "FREE_STEP", "MIN_OFFER", "POINTS_SALT", "Point", "TRIES", "offer_count",
           "site_points", "slope_key"]
