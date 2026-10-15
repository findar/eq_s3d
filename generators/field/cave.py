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
from .sdf import FieldGrid, sdf_sphere, sdf_capsule, carve, smooth_union_carve
from .noise import fbm_field
from .mesh import field_to_ter, decimate_ter


# ---------------------------------------------------------------------------
# Cave description
# ---------------------------------------------------------------------------

@dataclass
class Chamber:
    """A roughly spherical open space."""
    center: Tuple[float, float, float]
    radius: float


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

    # Meshing resolution — world units per voxel. Smaller = finer detail,
    # much higher poly count & memory. 8–16 is a good range for a zone.
    voxel: float = 12.0
    padding: float = 60.0          # solid-rock margin around the carved volume
    smooth_k: float = 25.0         # junction fillet size


# ---------------------------------------------------------------------------
# Carver
# ---------------------------------------------------------------------------

def build_cave(spec: CaveSpec, name: str,
               decimate: float = 0.5) -> Optional[TerFile]:
    """
    Carve the cave and return a TerFile. Returns None if the spec is empty.
    """
    if not spec.chambers and not spec.tunnels:
        return None

    grid = _make_grid(spec)

    # Precompute the FBM noise once over the whole grid; we offset carved
    # SDFs by this so the air boundary is displaced organically.
    noise = fbm_field(
        grid,
        seed=spec.noise_seed,
        scale=spec.noise_scale,
        octaves=spec.noise_octaves,
    ) * spec.noise_amplitude

    # Carve each chamber and tunnel. Adding the noise to the SDF before carving
    # perturbs the resulting wall surface.
    for ch in spec.chambers:
        s = sdf_sphere(grid, ch.center, ch.radius) + noise
        smooth_union_carve(grid, s, k=spec.smooth_k)

    for tn in spec.tunnels:
        s = sdf_capsule(grid, tn.a, tn.b, tn.radius) + noise
        smooth_union_carve(grid, s, k=spec.smooth_k)

    ter = field_to_ter(grid, name=name)
    if ter is None:
        return None

    if decimate and decimate < 1.0:
        ter = decimate_ter(ter, target_ratio=decimate)

    return ter


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
