"""
generators/field/features.py
-----------------------------
Natural cave features: stalactites (ceiling), stalagmites (floor), and
pillars (floor-to-ceiling columns), placed with surface awareness and fused
into the density field so they read as grown-from-the-rock, not glued-on props.

Placement strategy:
  - After the cave volume is carved, sample the field to find air voxels that
    sit just below a ceiling (for stalactites) or just above a floor (for
    stalagmites). These are candidate anchor points.
  - Keep features out of the central walkable path by preferring anchors away
    from chamber centres (stalagmites/pillars especially — they're obstacles).
  - Add each feature as a cone (or capsule for pillars) back into the field via
    add_solid, so marching cubes meshes them continuously with the cave.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from .sdf import FieldGrid, sdf_cone, sdf_capsule, add_solid


@dataclass
class FeatureParams:
    """Controls for natural feature placement."""
    seed: int = 0

    stalactite_count: int = 12      # hang from ceiling
    stalactite_len: Tuple[float, float] = (25.0, 70.0)
    stalactite_radius: Tuple[float, float] = (8.0, 18.0)

    stalagmite_count: int = 8       # rise from floor
    stalagmite_len: Tuple[float, float] = (20.0, 55.0)
    stalagmite_radius: Tuple[float, float] = (10.0, 22.0)

    pillar_count: int = 2           # floor-to-ceiling columns
    pillar_radius: Tuple[float, float] = (18.0, 32.0)

    # Keep floor features this far from chamber centres so the walkable core
    # stays clear (fraction of chamber radius; 0 = anywhere, 1 = only at edge).
    floor_feature_margin: float = 0.45


def add_features(grid: FieldGrid,
                 chambers: List,          # list of cave.Chamber
                 params: FeatureParams) -> None:
    """
    Add stalactites, stalagmites, and pillars into the carved field (in place).

    Must be called AFTER the cave volume is carved but BEFORE meshing.
    """
    rng = random.Random(params.seed)

    # Precompute an air mask and the ceiling/floor height at each (x,y) column
    # by scanning each voxel column along Z.
    density = grid.density
    nx, ny, nz = grid.shape
    ox, oy, oz = grid.origin
    vox = grid.voxel

    for ch in chambers:
        cx, cy, cz = ch.center
        floor_z = ch.floor_z if ch.floor_z is not None else cz - ch.radius * 0.5
        ceil_z = cz + ch.radius

        # --- Stalactites: cones from the ceiling pointing down ---
        n_stal = _scaled_count(params.stalactite_count, ch.radius, rng)
        for _ in range(n_stal):
            px, py = _rand_in_disc(rng, cx, cy, ch.radius * 0.85)
            tip_z = _ceiling_at(grid, px, py, cz, ceil_z)
            if tip_z is None:
                continue
            length = rng.uniform(*params.stalactite_len)
            base_r = rng.uniform(*params.stalactite_radius)
            # A stalactite is widest at the ceiling and tapers to a point
            # downward. sdf_cone has its point at `tip` and widens along `axis`,
            # so put the tip (point) at the bottom and grow upward (+Z) to the
            # wide base at the ceiling.
            bottom = tip_z - length
            cone = sdf_cone(grid, tip=(px, py, bottom), axis=(0, 0, 1),
                            height=length, base_radius=base_r)
            add_solid(grid, cone)

        # --- Stalagmites: cones from the floor pointing up ---
        n_mite = _scaled_count(params.stalagmite_count, ch.radius, rng)
        for _ in range(n_mite):
            # Keep stalagmites toward the chamber edges (walkable core clear)
            r_min = ch.radius * params.floor_feature_margin
            px, py = _rand_in_annulus(rng, cx, cy, r_min, ch.radius * 0.9)
            base_z = _floor_at(grid, px, py, cz, floor_z)
            if base_z is None:
                continue
            length = rng.uniform(*params.stalagmite_len)
            base_r = rng.uniform(*params.stalagmite_radius)
            # Tip at the base (floor), widening... stalagmite is widest at floor,
            # narrowing upward: tip at top, base at floor.
            cone = sdf_cone(grid, tip=(px, py, base_z + length), axis=(0, 0, -1),
                            height=length, base_radius=base_r)
            add_solid(grid, cone)

        # --- Pillars: capsules from floor to ceiling, near edges ---
        n_pillar = min(params.pillar_count, max(0, int(ch.radius / 70)))
        for _ in range(n_pillar):
            r_min = ch.radius * params.floor_feature_margin
            px, py = _rand_in_annulus(rng, cx, cy, r_min, ch.radius * 0.85)
            base_z = _floor_at(grid, px, py, cz, floor_z)
            top_z = _ceiling_at(grid, px, py, cz, ceil_z)
            if base_z is None or top_z is None or top_z <= base_z:
                continue
            pr = rng.uniform(*params.pillar_radius)
            # Slight waist: thinner in the middle reads as a natural column.
            col = sdf_capsule(grid, (px, py, base_z), (px, py, top_z), pr)
            add_solid(grid, col)


# ---------------------------------------------------------------------------
# Surface sampling helpers
# ---------------------------------------------------------------------------

def _ceiling_at(grid: FieldGrid, x: float, y: float,
                mid_z: float, max_z: float) -> Optional[float]:
    """
    Find the ceiling height (first solid above mid_z) in the voxel column at
    (x, y). Returns world Z of the air→rock transition, or None if not found.
    """
    i, j = _col_index(grid, x, y)
    if i is None:
        return None
    nz = grid.shape[2]
    k_mid = int((mid_z - grid.origin[2]) / grid.voxel)
    k_max = min(nz - 1, int((max_z - grid.origin[2]) / grid.voxel) + 2)
    k_mid = max(0, min(nz - 1, k_mid))
    prev_air = grid.density[i, j, k_mid] < 0
    for k in range(k_mid + 1, k_max + 1):
        solid = grid.density[i, j, k] >= 0
        if prev_air and solid:
            return grid.origin[2] + k * grid.voxel
        prev_air = not solid
    return None


def _floor_at(grid: FieldGrid, x: float, y: float,
              mid_z: float, min_z: float) -> Optional[float]:
    """Find the floor height (first solid below mid_z) in the column at (x,y)."""
    i, j = _col_index(grid, x, y)
    if i is None:
        return None
    k_mid = int((mid_z - grid.origin[2]) / grid.voxel)
    k_min = max(0, int((min_z - grid.origin[2]) / grid.voxel) - 2)
    k_mid = max(0, min(grid.shape[2] - 1, k_mid))
    prev_air = grid.density[i, j, k_mid] < 0
    for k in range(k_mid - 1, k_min - 1, -1):
        solid = grid.density[i, j, k] >= 0
        if prev_air and solid:
            return grid.origin[2] + k * grid.voxel
        prev_air = not solid
    return None


def _col_index(grid: FieldGrid, x: float, y: float):
    i = int(round((x - grid.origin[0]) / grid.voxel))
    j = int(round((y - grid.origin[1]) / grid.voxel))
    if 0 <= i < grid.shape[0] and 0 <= j < grid.shape[1]:
        return i, j
    return None, None


# ---------------------------------------------------------------------------
# Random placement helpers
# ---------------------------------------------------------------------------

def _rand_in_disc(rng, cx, cy, radius):
    t = rng.uniform(0, 2 * np.pi)
    r = radius * np.sqrt(rng.random())
    return cx + r * np.cos(t), cy + r * np.sin(t)


def _rand_in_annulus(rng, cx, cy, r_min, r_max):
    t = rng.uniform(0, 2 * np.pi)
    r = np.sqrt(rng.uniform(r_min ** 2, r_max ** 2))
    return cx + r * np.cos(t), cy + r * np.sin(t)


def _scaled_count(base: int, radius: float, rng) -> int:
    """Scale a feature count by chamber size, with a little randomness."""
    factor = max(0.4, radius / 100.0)
    n = int(round(base * factor))
    return max(0, n + rng.randint(-2, 2))
