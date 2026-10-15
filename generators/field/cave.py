"""
generators/field/cave.py
-------------------------
Carve an organic cave out of solid rock from a set of chambers (spheres) and
tunnels (capsules), then roughen the walls with FBM noise so they read as
natural rock rather than smooth tubes.

Produces a TerFile via marching cubes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from core.ter import TerFile
from .sdf import (
    FieldGrid, sdf_sphere, sdf_capsule, sdf_dome, carve, smooth_union_carve,
)
from .noise import fbm_field
from .mesh import field_to_ter, decimate_ter


# ---------------------------------------------------------------------------
# Cave description
# ---------------------------------------------------------------------------

@dataclass
class Chamber:
    """
    A chamber (open space). By default it has a FLAT walkable floor at
    `floor_z` and a rounded dome above — the navigable shape. `center` is the
    chamber's centre point and `radius` its horizontal/vertical reach.
    """
    center: Tuple[float, float, float]
    radius: float
    floor_z: Optional[float] = None   # if None, defaults to center_z - radius*0.5


@dataclass
class Tunnel:
    """A capsule-shaped passage between two points."""
    a: Tuple[float, float, float]
    b: Tuple[float, float, float]
    radius: float


@dataclass
class CaveSpec:
    """A cave to carve: chambers + tunnels, plus noise/roughness controls."""
    chambers: List[Chamber] = field(default_factory=list)
    tunnels: List[Tunnel] = field(default_factory=list)

    # Surface roughness
    noise_seed: int = 0
    noise_scale: float = 140.0     # world wavelength of wall bumps
    noise_amplitude: float = 22.0  # how far walls push in/out (world units)
    noise_octaves: int = 4

    # Walkability: noise is tapered to near-zero within `floor_flatten_height`
    # units above each chamber's floor, so floors stay navigable (gentle
    # undulation only) while walls and ceilings keep their full roughness.
    # `floor_undulation` is the residual noise amplitude left on the floor.
    floor_flatten_height: float = 45.0
    floor_undulation: float = 0.18   # fraction of noise_amplitude kept at floor

    # Meshing resolution — world units per voxel. Smaller = finer detail,
    # much higher poly count & memory. 8–16 is a good range for a zone.
    voxel: float = 12.0
    padding: float = 60.0          # solid-rock margin around the carved volume
    smooth_k: float = 25.0         # junction fillet size


# ---------------------------------------------------------------------------
# Carver
# ---------------------------------------------------------------------------

def build_cave(spec: CaveSpec, name: str,
               decimate: Optional[float] = None,
               features: Optional["FeatureParams"] = None) -> Optional[TerFile]:
    """
    Carve the cave and return a TerFile. Returns None if the spec is empty.

    Note: decimation is OFF by default. Quadric decimation collapses the flat
    walkable floor into a few huge triangles (destroying navigability), so we
    control poly count via `voxel` size instead. Only pass `decimate` if you
    specifically want fewer polys and can tolerate a rougher floor.

    If `features` is provided, stalactites / stalagmites / pillars are grown
    into the carved field before meshing so they fuse with the rock.
    """
    if not spec.chambers and not spec.tunnels:
        return None

    grid = _make_grid(spec)

    # Base FBM noise over the whole grid (world-aligned, computed once).
    base_noise = fbm_field(
        grid,
        seed=spec.noise_seed,
        scale=spec.noise_scale,
        octaves=spec.noise_octaves,
    ) * spec.noise_amplitude

    # World Z of every voxel — used to taper noise near chamber floors.
    _, _, Z = grid.world_coords()

    # Carve each chamber as a flat-bottomed dome with floor-tapered noise so
    # the floor is walkable while walls/ceiling stay rough.
    #
    # Near the floor the noise is both tapered (small amplitude) AND made
    # one-sided: it may raise gentle bumps but never carves BELOW the floor
    # plane (which would create pits/dips that break walkability). Higher up,
    # the full two-sided noise applies for rough walls and ceiling.
    for ch in spec.chambers:
        floor_z = ch.floor_z if ch.floor_z is not None else ch.center[2] - ch.radius * 0.5
        n = _floor_shaped_noise(Z, base_noise, floor_z, spec)
        s = sdf_dome(grid, ch.center, ch.radius, floor_z) + n
        smooth_union_carve(grid, s, k=spec.smooth_k)

    # Tunnels keep a flat-ish floor too.
    for tn in spec.tunnels:
        floor_z = min(tn.a[2], tn.b[2]) - tn.radius
        n = _floor_shaped_noise(Z, base_noise, floor_z, spec)
        s = sdf_capsule(grid, tn.a, tn.b, tn.radius) + n
        smooth_union_carve(grid, s, k=spec.smooth_k)

    # Grow natural features into the carved field before meshing so they
    # mesh continuously with the cave surface.
    if features is not None and spec.chambers:
        from .features import add_features
        add_features(grid, spec.chambers, features)

    ter = field_to_ter(grid, name=name)
    if ter is None:
        return None

    if decimate and decimate < 1.0:
        ter = decimate_ter(ter, target_ratio=decimate)

    return ter


# ---------------------------------------------------------------------------
# Floor noise taper
# ---------------------------------------------------------------------------

def _floor_shaped_noise(Z: np.ndarray, base_noise: np.ndarray,
                        floor_z: float, spec: "CaveSpec") -> np.ndarray:
    """
    Shape the wall noise so floors are walkable.

    - Above floor_z + flatten_height: full two-sided noise (rough walls/ceiling).
    - Near the floor: amplitude tapers down to `floor_undulation`.
    - At/below the floor: the residual noise is clamped to be ONE-SIDED
      (>= 0 in SDF terms), so it can raise gentle bumps but never carves a pit
      below the floor plane. This keeps the floor as a firm walkable lower bound
      with only mild natural undulation.

    Adding noise to a carve SDF: more-negative SDF = more air carved. A positive
    offset therefore *fills* (raises the floor); a negative offset *digs*. So
    clamping to >= 0 near the floor prevents digging below it.
    """
    h = np.clip((Z - floor_z) / max(spec.floor_flatten_height, 1e-6), 0.0, 1.0)
    smooth = h * h * (3.0 - 2.0 * h)
    taper = spec.floor_undulation + (1.0 - spec.floor_undulation) * smooth

    tapered = base_noise * taper

    # Near the floor clamp to non-negative so we never dig a pit below the
    # floor plane. The clamp is strong at the floor and releases higher up.
    # `clamp_strength` is 1 at the floor, 0 above flatten_height.
    clamp_strength = 1.0 - smooth
    non_dig = np.maximum(tapered, 0.0)
    return non_dig * clamp_strength + tapered * (1.0 - clamp_strength)


# ---------------------------------------------------------------------------
# Grid sizing
# ---------------------------------------------------------------------------

def _make_grid(spec: CaveSpec) -> FieldGrid:
    """Compute a grid that bounds all chambers/tunnels plus padding."""
    pts: List[Tuple[float, float, float]] = []
    max_r = 0.0
    for ch in spec.chambers:
        pts.append(ch.center)
        max_r = max(max_r, ch.radius)
    for tn in spec.tunnels:
        pts.append(tn.a)
        pts.append(tn.b)
        max_r = max(max_r, tn.radius)

    arr = np.array(pts, dtype=np.float32)
    margin = spec.padding + max_r + spec.noise_amplitude
    lo = arr.min(axis=0) - margin
    hi = arr.max(axis=0) + margin

    origin = (float(lo[0]), float(lo[1]), float(lo[2]))
    extent = hi - lo
    shape = tuple(int(np.ceil(e / spec.voxel)) + 1 for e in extent)

    return FieldGrid.solid(shape=shape, origin=origin, voxel=spec.voxel)
