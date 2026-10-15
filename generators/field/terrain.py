"""
generators/field/terrain.py
----------------------------
Outdoor terrain generation: a 2D heightfield turned into a walkable ground mesh.

Unlike caves (a volume carved from solid rock via marching cubes), terrain is a
*surface* — a grid of elevations. We:

  1. Generate a base heightfield from FBM noise (rolling hills).
  2. Optionally run thermal erosion so slopes slump to a natural angle of repose
     and ridgelines/valleys read as weathered rather than blobby.
  3. Clamp local gradient so the ground stays walkable (no cliffs the player
     can't climb) — steep spots are relaxed toward their neighbours.
  4. Triangulate the grid into a TerFile ground surface.

The result is a single ground mesh with gentle hills and valleys, navigable
end to end.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from core.ter import TerFile, Material, Vertex, Polygon, MAGIC_TERRAIN
from .noise import _value_noise_3d  # reuse the vectorised value noise


@dataclass
class TerrainSpec:
    """Parameters for an outdoor terrain patch."""
    width: float = 2000.0          # X extent in world units
    depth: float = 2000.0          # Y extent in world units
    resolution: float = 40.0       # world units per grid cell (smaller = finer)

    seed: int = 0
    height_scale: float = 220.0    # max hill height (world units)
    noise_scale: float = 900.0     # wavelength of the broadest hills
    octaves: int = 5

    erosion_iterations: int = 25   # thermal erosion passes (0 = none)
    talus_angle: float = 0.6       # max stable slope (height/cell) before slumping

    # Walkability: cap the per-cell gradient so the ground stays navigable.
    # Expressed as max rise per horizontal unit (tan of the max walkable angle).
    # tan(35deg) ~= 0.70. Steeper cells are relaxed toward neighbours.
    max_walkable_grad: float = 0.70
    walkable_passes: int = 4


def build_terrain(spec: TerrainSpec, name: str,
                  material_name: str = "ground",
                  texture: str = "ground.dds",
                  shader: str = "Opaque_MaxCB1.fx") -> Optional[TerFile]:
    """Generate a terrain heightfield and return it as a TerFile ground mesh."""
    nx = max(2, int(spec.width / spec.resolution) + 1)
    ny = max(2, int(spec.depth / spec.resolution) + 1)

    heights = _generate_heightfield(spec, nx, ny)

    if spec.erosion_iterations > 0:
        heights = _thermal_erosion(heights, spec.talus_angle,
                                   spec.erosion_iterations)

    heights = _enforce_walkable(heights, spec)

    return _heightfield_to_ter(
        heights, spec, name, material_name, texture, shader
    )


# ---------------------------------------------------------------------------
# Heightfield generation
# ---------------------------------------------------------------------------

def _generate_heightfield(spec: TerrainSpec, nx: int, ny: int) -> np.ndarray:
    """FBM heightfield over the grid, normalised to [0, height_scale]."""
    xs = np.arange(nx, dtype=np.float32) * spec.resolution
    ys = np.arange(ny, dtype=np.float32) * spec.resolution
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    Z0 = np.zeros_like(X)  # value noise is 3D; keep z plane at 0

    total = np.zeros((nx, ny), dtype=np.float32)
    amp = 1.0
    freq = 1.0 / spec.noise_scale
    norm = 0.0
    for o in range(spec.octaves):
        n = _value_noise_3d(X * freq, Y * freq, Z0, spec.seed + o * 1013)
        # ridge-ish shaping on higher octaves adds hill character
        total += amp * n
        norm += amp
        amp *= 0.5
        freq *= 2.0
    total /= max(norm, 1e-6)

    # Normalise to [0, 1] then scale to height
    hmin, hmax = float(total.min()), float(total.max())
    if hmax - hmin > 1e-6:
        total = (total - hmin) / (hmax - hmin)
    return (total * spec.height_scale).astype(np.float32)


# ---------------------------------------------------------------------------
# Thermal erosion — slopes above the talus angle slump to neighbours
# ---------------------------------------------------------------------------

def _thermal_erosion(h: np.ndarray, talus: float, iterations: int) -> np.ndarray:
    """
    Simple thermal erosion: material above the talus angle moves downhill to
    the lowest neighbour, smoothing cliffs into natural slopes.
    """
    h = h.copy()
    for _ in range(iterations):
        # Differences to the 4 orthogonal neighbours
        d_up    = np.zeros_like(h); d_up[1:, :]  = h[1:, :]  - h[:-1, :]
        d_down  = np.zeros_like(h); d_down[:-1,:] = h[:-1, :] - h[1:, :]
        d_left  = np.zeros_like(h); d_left[:,1:]  = h[:, 1:]  - h[:, :-1]
        d_right = np.zeros_like(h); d_right[:,:-1]= h[:, :-1] - h[:, 1:]

        # Amount over talus that should move (per neighbour)
        def over(d):
            return np.maximum(0.0, d - talus)

        move = 0.25 * 0.5  # distribute a fraction each pass for stability
        total_out = (over(d_up) + over(d_down) + over(d_left) + over(d_right)) * move
        h -= total_out

        # Deposit into neighbours (shift the outgoing amounts the opposite way)
        inc = np.zeros_like(h)
        inc[:-1, :] += over(d_up)[1:, :]   * move
        inc[1:, :]  += over(d_down)[:-1,:] * move
        inc[:, :-1] += over(d_left)[:,1:]  * move
        inc[:, 1:]  += over(d_right)[:,:-1]* move
        h += inc
    return h


# ---------------------------------------------------------------------------
# Walkability — relax cells whose gradient exceeds the walkable cap
# ---------------------------------------------------------------------------

def _enforce_walkable(h: np.ndarray, spec: TerrainSpec) -> np.ndarray:
    """
    Iteratively relax any cell whose height differs from a neighbour by more
    than max_walkable_grad * resolution, pulling it toward the neighbour mean.
    Keeps the ground navigable while preserving broad hill shape.
    """
    h = h.copy()
    max_step = spec.max_walkable_grad * spec.resolution
    for _ in range(spec.walkable_passes):
        # 4-neighbour average
        avg = np.zeros_like(h)
        cnt = np.zeros_like(h)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            shifted = np.roll(h, shift=(dx, dy), axis=(0, 1))
            avg += shifted
            cnt += 1
        avg /= cnt

        # Where the cell is too far above/below its neighbour average, pull in
        diff = h - avg
        too_steep = np.abs(diff) > max_step
        h = np.where(too_steep, avg + np.sign(diff) * max_step, h)
    return h


# ---------------------------------------------------------------------------
# Triangulate the heightfield into a ground mesh
# ---------------------------------------------------------------------------

def _heightfield_to_ter(h: np.ndarray, spec: TerrainSpec, name: str,
                        material_name: str, texture: str,
                        shader: str) -> TerFile:
    nx, ny = h.shape
    res = spec.resolution

    ter = TerFile(name=name, magic=MAGIC_TERRAIN, version=2)
    mat = Material(index=0, name=material_name, shader=shader)
    mat.add_diffuse(texture)
    ter.materials.append(mat)

    # Vertex normals from the height gradient (central differences)
    gx, gy = np.gradient(h, res)
    # Normal = (-dz/dx, -dz/dy, 1) normalised
    nz = np.ones_like(h)
    nlen = np.sqrt(gx ** 2 + gy ** 2 + 1.0)
    nx_n = -gx / nlen
    ny_n = -gy / nlen
    nz_n = nz / nlen

    uv_scale = 1.0 / spec.noise_scale * 4.0

    def vid(i, j):
        return i * ny + j

    for i in range(nx):
        for j in range(ny):
            x = i * res
            y = j * res
            ter.vertices.append(Vertex(
                x=float(x), y=float(y), z=float(h[i, j]),
                nx=float(nx_n[i, j]), ny=float(ny_n[i, j]), nz=float(nz_n[i, j]),
                u=float(x) * uv_scale, v=float(y) * uv_scale,
            ))

    # Two triangles per grid quad, wound CCW when viewed from above (+Z up)
    for i in range(nx - 1):
        for j in range(ny - 1):
            a = vid(i, j)
            b = vid(i + 1, j)
            c = vid(i + 1, j + 1)
            d = vid(i, j + 1)
            ter.polygons.append(Polygon(a, b, c, material=0, flags=0))
            ter.polygons.append(Polygon(a, c, d, material=0, flags=0))

    return ter
