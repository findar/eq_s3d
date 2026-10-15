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


def sdf_dome(grid: FieldGrid, center, radius: float,
             floor_z: float) -> np.ndarray:
    """
    Signed distance to a flat-bottomed dome: a sphere intersected with the
    half-space above `floor_z`. Produces a chamber with a FLAT walkable floor
    at floor_z and a rounded dome of walls/ceiling above it.

    This is the walkable alternative to carving a pure sphere (which leaves a
    curved bowl floor the player would slide down).
    """
    X, Y, Z = grid.world_coords()
    cx, cy, cz = center
    sphere = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2 + (Z - cz) ** 2) - radius
    # Half-space: solid below floor_z. SDF of "above the plane" is (floor_z - Z);
    # negative above the floor, positive below.
    above_floor = floor_z - Z
    # Intersection of sphere-interior and above-floor = max of the two SDFs
    return np.maximum(sphere, above_floor)


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


def add_cone_local(grid: FieldGrid, tip, axis, height: float,
                   base_radius: float) -> None:
    """
    Add a cone as solid, computing the SDF only within a local bounding box
    around the cone (not the whole grid). This is the fast path for placing
    many small features (stalactites/stalagmites) into a large field.
    """
    tx, ty, tz = tip
    ax, ay, az = axis
    # The cone spans from tip to tip + axis*height, with max radius base_radius.
    end = (tx + ax * height, ty + ay * height, tz + az * height)
    lo = (min(tx, end[0]) - base_radius, min(ty, end[1]) - base_radius,
          min(tz, end[2]) - base_radius)
    hi = (max(tx, end[0]) + base_radius, max(ty, end[1]) + base_radius,
          max(tz, end[2]) + base_radius)
    sl, sub = _subgrid(grid, lo, hi)
    if sub is None:
        return
    X, Y, Z = sub
    px = X - tx; py = Y - ty; pz = Z - tz
    along = px * ax + py * ay + pz * az
    along_c = np.clip(along, 0.0, height)
    allowed = (along_c / height) * base_radius
    perp_x = px - along * ax
    perp_y = py - along * ay
    perp_z = pz - along * az
    radial = np.sqrt(perp_x ** 2 + perp_y ** 2 + perp_z ** 2)
    radial_d = radial - allowed
    cap_d = np.maximum(-along, along - height)
    sdf = np.maximum(radial_d, cap_d)
    np.maximum(grid.density[sl], -sdf, out=grid.density[sl])


def add_capsule_local(grid: FieldGrid, a, b, radius: float) -> None:
    """Add a capsule (pillar) as solid within a local bounding box."""
    ax, ay, az = a
    bx, by, bz = b
    lo = (min(ax, bx) - radius, min(ay, by) - radius, min(az, bz) - radius)
    hi = (max(ax, bx) + radius, max(ay, by) + radius, max(az, bz) + radius)
    sl, sub = _subgrid(grid, lo, hi)
    if sub is None:
        return
    X, Y, Z = sub
    ab = np.array([bx - ax, by - ay, bz - az], dtype=np.float32)
    ab_len2 = float(ab @ ab) or 1e-6
    px = X - ax; py = Y - ay; pz = Z - az
    t = np.clip((px * ab[0] + py * ab[1] + pz * ab[2]) / ab_len2, 0.0, 1.0)
    cx = ax + t * ab[0]; cy = ay + t * ab[1]; cz = az + t * ab[2]
    d = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2 + (Z - cz) ** 2) - radius
    np.maximum(grid.density[sl], -d, out=grid.density[sl])


def _subgrid(grid: FieldGrid, lo, hi):
    """
    Return (slices, (X,Y,Z)) for the voxel sub-box covering world bounds lo..hi,
    or (None, None) if the box is outside the grid. The coordinate arrays are
    world positions for just that sub-box.
    """
    ox, oy, oz = grid.origin
    v = grid.voxel
    i0 = max(0, int(np.floor((lo[0] - ox) / v)))
    j0 = max(0, int(np.floor((lo[1] - oy) / v)))
    k0 = max(0, int(np.floor((lo[2] - oz) / v)))
    i1 = min(grid.shape[0], int(np.ceil((hi[0] - ox) / v)) + 1)
    j1 = min(grid.shape[1], int(np.ceil((hi[1] - oy) / v)) + 1)
    k1 = min(grid.shape[2], int(np.ceil((hi[2] - oz) / v)) + 1)
    if i0 >= i1 or j0 >= j1 or k0 >= k1:
        return None, None
    sl = (slice(i0, i1), slice(j0, j1), slice(k0, k1))
    xi = np.arange(i0, i1, dtype=np.float32) * v + ox
    yi = np.arange(j0, j1, dtype=np.float32) * v + oy
    zi = np.arange(k0, k1, dtype=np.float32) * v + oz
    X, Y, Z = np.meshgrid(xi, yi, zi, indexing="ij")
    return sl, (X, Y, Z)


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
