"""
generators/vegetation/placement.py
----------------------------------
Where the trees stand (trees spec task 4, Requirements 4 and 5).

:func:`place_trees` is a pure function of the landscape, its built TER, the
vegetation kit, the Density_Level and a seed (the caller salts the seed so the
terrain's random stream never moves, design Decision 4). It returns
Tree_Instances that:

- stand only on Eligible_Ground: TER quads whose two triangles are standable
  and at most 30° steep, whose four corner cells are ``plains`` and not Rim
  seal, and which lie outside Kept_Clear (the Spawn clearing, each zoneline gap
  plus two cells inward, and a one-cell band beside water, river and lava);
- keep every Trunk_Disc at least Tree_Clearance from every other Trunk_Disc and
  from all ineligible ground (Req 4.3). Since eligible ground is walkable,
  that leaves every trunk an island inside walkable ground, so trees can't cut
  the walkable region apart (design "Walkability");
- cluster into groves (a Thomas cluster process plus lone trees) so the
  Grove_Ratio reads like the measured Karanas (design "Research findings" 1);
- sit at the TER surface height under their XY, read from the triangle under
  the point.

Kit densities are trees per 1e6 u² of Eligible_Ground. If the ground can't hold
75 % of the target under the clearance rule, the result records
``capped`` (Req 5.5).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.ndimage import binary_dilation

from core.ter import TerFile
from generators.vegetation.kit import VegetationKit

#: Minimum free gap between Trunk_Discs, and from a disc to ineligible ground.
TREE_CLEARANCE = 8.0
#: Steepest ground a tree may stand on.
MAX_TREE_SLOPE_DEG = 30.0
#: Radius of the Spawn clearing.
SPAWN_CLEARING = 120.0
#: Fine cells kept clear inward of a zoneline gap, and beside water/river/lava.
ZONELINE_APPROACH_CELLS = 2
SHORE_CELLS = 1
#: Share of a grove's trees that are its dominant Species.
GROVE_DOMINANCE = 0.7
#: Grove spread: a grove tree is Gaussian around the centre with sigma the larger
#: of ``GROVE_SIGMA x`` the kit's grove radius and ``GROVE_SPREAD x
#: sqrt(n / (pi x density))``, the radius ``n`` trees would cover at the zone's
#: density. Scaling with density keeps the Grove_Ratio level-independent: tight
#: kit radii alone pack sparse zones far more than the Karanas (0.2-0.3 vs
#: 0.44-0.70, task 4 probe).
GROVE_SIGMA = 0.6
GROVE_SPREAD = 0.28
#: Grove_Ratio feedback: the ratio a pass aims for, the window that ends the
#: search, the most passes, and the fewest trees worth measuring (Req 5.2).
RATIO_TARGET = 0.65
RATIO_ACCEPT = (0.5, 0.8)
RATIO_PASSES = 8
RATIO_MIN_TREES = 40
#: Dart-throwing attempts per wanted tree.
ATTEMPTS_PER_TREE = 30
#: Below this share of the target, the result is marked capped.
CAP_SHARE = 0.75

_BUCKET = 32.0


@dataclass(frozen=True)
class TreeInstance:
    """One placed tree. ``radius`` is the Trunk_Disc radius (trunk x scale)."""

    species: str
    x: float
    y: float
    z: float
    yaw: float
    scale: float
    radius: float


@dataclass
class Placement:
    """The trees for one zone plus what the sidecar reports about them."""

    instances: List[TreeInstance]
    target: int
    eligible_area: float
    grove_count: int
    capped: bool = False
    counts: Dict[str, int] = field(default_factory=dict)

    @property
    def density(self) -> float:
        """Placed trees per 1e6 u² of Eligible_Ground."""
        return len(self.instances) / self.eligible_area * 1e6 if self.eligible_area else 0.0


# ---------------------------------------------------------------------------
# The ground
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Ground:
    """The TER's vertex heightfield and per-quad eligibility, in world frame.
    Vertex ``(i, j)`` sits at ``origin + (i + 0.5, j + 0.5) * res``."""

    heights: np.ndarray        # (nx, ny) vertex Z from the TER
    origin: Tuple[float, float]
    res: float
    eligible: np.ndarray       # (nx-1, ny-1) bool, quad (i, j) spans vertices i..i+1, j..j+1

    def quad_of(self, x: float, y: float) -> Tuple[int, int, float, float]:
        """Quad indices and the local (fx, fy) in [0, 1) of a world point."""
        gx = (x - self.origin[0]) / self.res - 0.5
        gy = (y - self.origin[1]) / self.res - 0.5
        i, j = int(math.floor(gx)), int(math.floor(gy))
        return i, j, gx - i, gy - j

    def surface_z(self, x: float, y: float) -> float:
        """Z of the TER triangle under (x, y): quads split a-b-c / a-c-d with
        a=(i,j), b=(i+1,j), c=(i+1,j+1), d=(i,j+1), as the TER is built."""
        i, j, fx, fy = self.quad_of(x, y)
        h = self.heights
        ha, hb, hc, hd = h[i, j], h[i + 1, j], h[i + 1, j + 1], h[i, j + 1]
        if fx >= fy:
            return float(ha + fx * (hb - ha) + fy * (hc - hb))
        return float(ha + fy * (hd - ha) + fx * (hc - hd))

    def quad_rect(self, i: int, j: int) -> Tuple[float, float, float, float]:
        x0 = self.origin[0] + (i + 0.5) * self.res
        y0 = self.origin[1] + (j + 0.5) * self.res
        return x0, y0, x0 + self.res, y0 + self.res

    def disc_on_eligible(self, x: float, y: float, r: float) -> bool:
        """True when the disc lies wholly on eligible quads (none of the quads
        it touches is ineligible or off the grid)."""
        nqx, nqy = self.eligible.shape
        i0, j0, _, _ = self.quad_of(x - r, y - r)
        i1, j1, _, _ = self.quad_of(x + r, y + r)
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                if 0 <= i < nqx and 0 <= j < nqy and self.eligible[i, j]:
                    continue
                qx0, qy0, qx1, qy1 = self.quad_rect(i, j)
                dx = max(qx0 - x, 0.0, x - qx1)
                dy = max(qy0 - y, 0.0, y - qy1)
                if dx * dx + dy * dy < r * r:
                    return False
        return True


def ter_heights(ter: TerFile, shape: Tuple[int, int]) -> np.ndarray:
    """The TER's grid vertex heights (the first nx*ny vertices, row-major i, j)."""
    nx, ny = shape
    z = np.fromiter((v.z for v in ter.vertices[:nx * ny]), dtype=np.float64, count=nx * ny)
    return z.reshape(nx, ny)


def eligible_quads(heights: np.ndarray, node_type: np.ndarray, rim_seal: np.ndarray,
                   origin: Tuple[float, float], res: float,
                   spawn_xy: Tuple[float, float]) -> np.ndarray:
    """Eligible_Ground per quad (Req 4.1), shape ``(nx-1, ny-1)``."""
    h = heights
    ha, hb, hc, hd = h[:-1, :-1], h[1:, :-1], h[1:, 1:], h[:-1, 1:]
    # Triangle a-b-c normal ~ (-(hb-ha), -(hc-hb), res); a-c-d ~ (-(hc-hd), -(hd-ha), res).
    cos_max = math.cos(math.radians(MAX_TREE_SLOPE_DEG))

    def flat_enough(gx, gy):
        return res / np.sqrt(gx * gx + gy * gy + res * res) >= cos_max

    ok = flat_enough(hb - ha, hc - hb) & flat_enough(hc - hd, hd - ha)

    def corners_all(mask):
        return mask[:-1, :-1] & mask[1:, :-1] & mask[1:, 1:] & mask[:-1, 1:]

    def corners_any(mask):
        return mask[:-1, :-1] | mask[1:, :-1] | mask[1:, 1:] | mask[:-1, 1:]

    ok &= corners_all(node_type == "plains")
    ok &= ~corners_any(rim_seal.astype(bool))
    zl = node_type == "zoneline_gap"
    if zl.any():
        ok &= ~corners_any(binary_dilation(zl, iterations=ZONELINE_APPROACH_CELLS))
    wet = np.isin(node_type, ("water", "river", "lava"))
    if wet.any():
        ok &= ~corners_any(binary_dilation(wet, iterations=SHORE_CELLS))

    # Spawn clearing: the whole quad must lie outside the circle.
    nqx, nqy = ok.shape
    qi, qj = np.meshgrid(np.arange(nqx), np.arange(nqy), indexing="ij")
    x0 = origin[0] + (qi + 0.5) * res
    y0 = origin[1] + (qj + 0.5) * res
    sx, sy = spawn_xy
    dx = np.maximum(np.maximum(x0 - sx, 0.0), sx - (x0 + res))
    dy = np.maximum(np.maximum(y0 - sy, 0.0), sy - (y0 + res))
    ok &= dx * dx + dy * dy >= SPAWN_CLEARING ** 2
    return ok


def ground_for(land, ter: TerFile, spawn_xy: Tuple[float, float]) -> Ground:
    """The placement ground for a synthesized landscape and its built TER."""
    synth = land.synth
    h = ter_heights(ter, synth.heights.shape)
    res = float(synth.resolution)
    elig = eligible_quads(h, synth.node_type, synth.rim_seal_mask, synth.origin, res, spawn_xy)
    return Ground(heights=h, origin=tuple(synth.origin), res=res, eligible=elig)


# ---------------------------------------------------------------------------
# Spacing
# ---------------------------------------------------------------------------

class _Spacing:
    """Spatial hash over accepted Trunk_Discs for the clearance test."""

    def __init__(self):
        self._cells: Dict[Tuple[int, int], List[Tuple[float, float, float]]] = {}
        self._max_r = 0.0

    def fits(self, x: float, y: float, r: float) -> bool:
        reach = r + self._max_r + TREE_CLEARANCE
        span = int(math.ceil(reach / _BUCKET))
        ci, cj = int(math.floor(x / _BUCKET)), int(math.floor(y / _BUCKET))
        for i in range(ci - span, ci + span + 1):
            for j in range(cj - span, cj + span + 1):
                for (ox, oy, orad) in self._cells.get((i, j), ()):
                    gap = r + orad + TREE_CLEARANCE
                    if (x - ox) ** 2 + (y - oy) ** 2 < gap * gap:
                        return False
        return True

    def add(self, x: float, y: float, r: float) -> None:
        key = (int(math.floor(x / _BUCKET)), int(math.floor(y / _BUCKET)))
        self._cells.setdefault(key, []).append((x, y, r))
        self._max_r = max(self._max_r, r)


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------

def place_trees(land, ter: TerFile, kit: Optional[VegetationKit], level: str, seed: int,
                spawn_xy: Optional[Tuple[float, float]] = None) -> Placement:
    """The Tree_Instances for one zone (Requirements 4 and 5). Pure."""
    if spawn_xy is None:
        from generators.wilderness.bowl import _spawn_world_point
        sx, sy, _ = _spawn_world_point(land.synth, land.matrix, land.bowl.heights)
        spawn_xy = (sx, sy)
    ground = ground_for(land, ter, spawn_xy)
    area = float(ground.eligible.sum()) * ground.res ** 2
    if kit is None or level == "none" or area <= 0:
        return Placement(instances=[], target=0, eligible_area=area, grove_count=0)
    target = int(round(kit.density_for(level) * area / 1e6))
    if target <= 0:
        return Placement(instances=[], target=0, eligible_area=area, grove_count=0)

    # Feedback on the Grove_Ratio: one pass is noisy (sparse zones hold ~45
    # trees), so a pass outside RATIO_ACCEPT is redone with the spread scaled
    # toward RATIO_TARGET, keeping the pass closest to it. Each pass is ~10 ms.
    spread_factor = GROVE_SPREAD
    best: Optional[Placement] = None
    best_err = math.inf
    for attempt in range(RATIO_PASSES):
        p = _place(ground, area, target, kit, level, spread_factor,
                   np.random.default_rng([seed, attempt]))
        ratio = grove_ratio(p.instances, area)
        if ratio is None or len(p.instances) < RATIO_MIN_TREES:
            return p
        err = abs(ratio - RATIO_TARGET)
        if err < best_err:
            best, best_err = p, err
        if RATIO_ACCEPT[0] <= ratio <= RATIO_ACCEPT[1]:
            break
        # A low ratio is too clustered: widen the groves (and vice versa).
        spread_factor *= (RATIO_TARGET / ratio) ** 0.5
    return best


def _place(ground: Ground, area: float, target: int, kit: VegetationKit, level: str,
           spread_factor: float, rng: np.random.Generator) -> Placement:
    """One placement pass at a given grove spread."""
    weights = {k: sp.weight for k, sp in kit.species.items()}
    g = kit.groves

    eq = np.argwhere(ground.eligible)

    def random_eligible_point() -> Tuple[float, float]:
        i, j = eq[rng.integers(len(eq))]
        x0, y0, _, _ = ground.quad_rect(int(i), int(j))
        return x0 + rng.random() * ground.res, y0 + rng.random() * ground.res

    # Grove centres: spaced 2 x the largest grove radius, on eligible ground.
    mean_size = (g.trees_per_grove[0] + g.trees_per_grove[1]) / 2.0
    want_groves = int(round((1.0 - g.lone_share) * target / mean_size))
    if target >= g.trees_per_grove[0]:
        want_groves = max(1, want_groves)
    lam = kit.density_for(level) / 1e6

    def spread(n: float, radius: float) -> float:
        return max(GROVE_SIGMA * radius, spread_factor * math.sqrt(n / (math.pi * lam)))

    centres: List[Tuple[float, float]] = []
    min_sep = 2.0 * max(g.radius[1], 1.5 * spread(mean_size, 0.0))
    for _ in range(ATTEMPTS_PER_TREE * max(want_groves, 1)):
        if len(centres) >= want_groves:
            break
        cx, cy = random_eligible_point()
        if all((cx - ox) ** 2 + (cy - oy) ** 2 >= min_sep ** 2 for ox, oy in centres):
            centres.append((cx, cy))

    # Grove sizes and dominants: dominants are apportioned by weight across
    # groves (not drawn independently), so a zone with few groves still gets
    # the kit's species mix (Req 5.6).
    sizes = [int(rng.integers(g.trees_per_grove[0], g.trees_per_grove[1] + 1)) for _ in centres]
    # Groves hold at most their share of the target, so the lone trees (which
    # go to the neediest Species) always have room to even out the mix.
    grove_cap = int(round((1.0 - g.lone_share) * target))
    while sizes and sum(sizes) > grove_cap:
        k = int(np.argmax(sizes))
        sizes[k] -= 1
        if sizes[k] == 0:
            sizes.pop(k)
            centres.pop(k)
    # Dominants go by trees, not groves: largest grove first, each to the
    # Species furthest below its share of the grove trees (sizes vary 4-14, so
    # counting groves alone can hand a big grove to a minor Species).
    wsum = sum(weights.values())
    grove_total = sum(sizes)
    led = {k: 0.0 for k in weights}
    dominants = [""] * len(sizes)
    for k in sorted(range(len(sizes)), key=lambda i: -sizes[i]):
        pick = max(sorted(weights), key=lambda s: weights[s] / wsum * grove_total - led[s])
        dominants[k] = pick
        led[pick] += sizes[k]
    radii = [float(rng.uniform(*g.radius)) for _ in centres]

    spacing = _Spacing()
    placed: List[TreeInstance] = []
    counts = {k: 0 for k in weights}
    names = sorted(weights)

    def neediest() -> str:
        """The Species furthest below its share of what's placed so far."""
        n = len(placed) + 1
        return max(names, key=lambda k: weights[k] / wsum * n - counts[k])

    def try_place(species_name: str, x: float, y: float) -> bool:
        sp = kit.species[species_name]
        scale = float(rng.uniform(*sp.scale))
        r = sp.trunk_radius * scale
        if not ground.disc_on_eligible(x, y, r + TREE_CLEARANCE):
            return False
        if not spacing.fits(x, y, r):
            return False
        spacing.add(x, y, r)
        placed.append(TreeInstance(
            species=species_name, x=float(x), y=float(y), z=ground.surface_z(x, y),
            yaw=float(rng.uniform(-math.pi, math.pi)), scale=scale, radius=r))
        counts[species_name] += 1
        return True

    for (cx, cy), size, dom, rad in zip(centres, sizes, dominants, radii):
        sigma = spread(size, rad)
        for _ in range(size):
            name = dom if rng.random() < GROVE_DOMINANCE else neediest()
            for _ in range(ATTEMPTS_PER_TREE):
                x, y = cx + rng.normal(0.0, sigma), cy + rng.normal(0.0, sigma)
                if try_place(name, x, y):
                    break

    lone_target = target - len(placed)
    for _ in range(max(lone_target, 0)):
        name = neediest()
        for _ in range(ATTEMPTS_PER_TREE):
            x, y = random_eligible_point()
            if try_place(name, x, y):
                break

    return Placement(instances=placed, target=target, eligible_area=area,
                     grove_count=len(centres),
                     capped=len(placed) < CAP_SHARE * target, counts=counts)


def grove_ratio(instances: List[TreeInstance], eligible_area: float) -> Optional[float]:
    """Median nearest-neighbour distance over the uniform-scatter expectation at
    the same density, ``sqrt(ln 2 / (pi * density))`` (requirements glossary)."""
    if len(instances) < 2 or eligible_area <= 0:
        return None
    from scipy.spatial import cKDTree
    pts = np.array([[t.x, t.y] for t in instances])
    d, _ = cKDTree(pts).query(pts, k=2)
    density = len(instances) / eligible_area
    return float(np.median(d[:, 1]) / math.sqrt(math.log(2) / (math.pi * density)))
