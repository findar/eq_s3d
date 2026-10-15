"""
generators/field/sdf.py
-----------------------
Signed Distance Field (SDF) primitives and operations on a 3D voxel grid.

Convention: the field stores *density*. We use the convention

    density > 0   → solid rock
    density < 0   → open air (walkable)
    density == 0  → the surface (what marching cubes extracts)

A cave is built by starting with a solid block (all positive) and *carving*
air into it (pushing values negative) along the mission-graph volume, then
perturbing the surface with noise so walls are irregular rather than flat.

Everything operates on numpy arrays for speed. The grid maps to world space
via an origin and a uniform voxel size.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Grid
# ---------------------------------------------------------------------------

@dataclass
class FieldGrid:
    """
    A 3D scalar field sampled on a regular voxel grid.

    The field is indexed [i, j, k] → world (x, y, z) via:
        world = origin + (i, j, k) * voxel

    density starts at +solid everywhere (solid rock); carving subtracts.
    """
    shape: Tuple[int, int, int]
    origin: Tuple[float, float, float]
    voxel: float
    density: np.ndarray  # float32, shape == shape

    @classmethod
    def solid(cls, shape, origin, voxel, solid_value: float = 1.0) -> "FieldGrid":
        density = np.full(shape, solid_value, dtype=np.float32)
        return cls(shape=shape, origin=origin, voxel=voxel, density=density)

    def world_coords(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return 3 meshgrid arrays of world X, Y, Z for every voxel."""
        ox, oy, oz = self.origin
        i = np.arange(self.shape[0], dtype=np.float32) * self.voxel + ox
        j = np.arange(self.shape[1], dtype=np.float32) * self.voxel + oy
        k = np.arange(self.shape[2], dtype=np.float32) * self.voxel + oz
        X, Y, Z = np.meshgrid(i, j, k, indexing="ij")
        return X, Y, Z


# ---------------------------------------------------------------------------
# Primitive SDFs — each returns a signed distance array over the grid.
# Negative inside the shape, positive outside.
# ---------------------------------------------------------------------------

def sdf_sphere(grid: FieldGrid, center, radius: float) -> np.ndarray:
    X, Y, Z = grid.world_coords()
    cx, cy, cz = center
    d = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2 + (Z - cz) ** 2)
    return d - radius


def sdf_capsule(grid: FieldGrid, a, b, radius: float) -> np.ndarray:
    """Signed distance to a capsule (line segment a→b with rounded radius)."""
    X, Y, Z = grid.world_coords()
    ax, ay, az = a
    bx, by, bz = b
    ab = np.array([bx - ax, by - ay, bz - az], dtype=np.float32)
    ab_len2 = float(ab @ ab) or 1e-6

    px = X - ax
    py = Y - ay
    pz = Z - az
    # t = clamp( (p·ab) / |ab|^2 , 0, 1 )
    t = (px * ab[0] + py * ab[1] + pz * ab[2]) / ab_len2
    t = np.clip(t, 0.0, 1.0)
    # closest point on segment
    cx = ax + t * ab[0]
    cy = ay + t * ab[1]
    cz = az + t * ab[2]
    d = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2 + (Z - cz) ** 2)
    return d - radius


def sdf_cone(grid: FieldGrid, tip, axis, height: float, base_radius: float) -> np.ndarray:
    """
    Approximate signed distance to a cone, tip at `tip`, growing along `axis`
    (unit vector) for `height`, widening to `base_radius`.

    Used for stalactites (axis pointing down) and stalagmites (axis up).
    Approximation is adequate for carving/adding into a density field.
    """
    X, Y, Z = grid.world_coords()
    tx, ty, tz = tip
    ax, ay, az = axis
    # distance along axis from tip
    px = X - tx
    py = Y - ty
    pz = Z - tz
    along = px * ax + py * ay + pz * az          # projection onto axis
    along_c = np.clip(along, 0.0, height)
    # radius allowed at this height (0 at tip → base_radius at height)
    allowed = (along_c / height) * base_radius
    # perpendicular distance from axis
    perp_x = px - along * ax
    perp_y = py - along * ay
    perp_z = pz - along * az
    radial = np.sqrt(perp_x ** 2 + perp_y ** 2 + perp_z ** 2)
    # inside if within allowed radius AND within [0, height] along axis
    radial_d = radial - allowed
    cap_d = np.maximum(-along, along - height)   # distance outside the length range
    return np.maximum(radial_d, cap_d)


# ---------------------------------------------------------------------------
# Boolean / carving operations on the density field
# ---------------------------------------------------------------------------

def carve(grid: FieldGrid, sdf: np.ndarray) -> None:
    """
    Carve the shape described by *sdf* out of the solid (make it air).

    Air is negative density. For voxels inside the shape (sdf < 0) we drive
    density negative. Implemented as density = min(density, sdf) so the carved
    region becomes air and the surface sits at the shape boundary.
    """
    np.minimum(grid.density, sdf, out=grid.density)


def add_solid(grid: FieldGrid, sdf: np.ndarray) -> None:
    """
    Add solid material in the shape described by *sdf* (e.g. a stalactite).

    Union of solids: density = max(density, -sdf) so the shape interior
    (sdf < 0 → -sdf > 0) becomes solid, filling previously-carved air.
    """
    np.maximum(grid.density, -sdf, out=grid.density)


def smooth_union_carve(grid: FieldGrid, sdf: np.ndarray, k: float = 20.0) -> None:
    """
    Smooth-blend carve — rounds the junction between carved volumes so tunnels
    meet chambers with organic fillets instead of hard intersections.

    Uses a polynomial smooth-min on the air side.
    """
    a = grid.density
    b = sdf
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    blended = b * h + a * (1.0 - h) - k * h * (1.0 - h)
    np.minimum(grid.density, blended, out=grid.density)
