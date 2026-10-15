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
    smooth_min,
)
from .noise import fbm_field
from .mesh import field_to_ter, decimate_ter


# ---------------------------------------------------------------------------
# Cave description
# ---------------------------------------------------------------------------

@dataclass
class Chamber:
    """
    A chamber (open space). It has a FLAT walkable floor at `floor_z` and an
    irregular domed ceiling above. `center` is the chamber's centre point and
    `radius` its nominal horizontal/vertical reach.

    Rather than a single sphere (which reads as an artificial bubble), the
    chamber is carved as a cluster of several offset lobes smooth-unioned
    together — an organic blob with an irregular, non-circular footprint.
    `lobes` controls how many; `irregularity` how far they wander (as a
    fraction of radius). `shape_seed` makes the lobe placement deterministic
    yet unique per chamber.
    """
    center: Tuple[float, float, float]
    radius: float
    floor_z: Optional[float] = None   # if None, defaults to center_z - radius*0.5
    lobes: int = 3
    irregularity: float = 0.55
    shape_seed: int = 0


@dataclass
class Tunnel:
    """
    A passage between two points. Instead of a single straight capsule (which
    reads as a pipe), the tunnel meanders: it is built from several capsule
    segments through intermediate waypoints that are jittered off the straight
    A→B line, and its radius varies slightly along the way. `wander` is the
    perpendicular jitter as a fraction of the A→B length; `segments` the number
    of pieces; `shape_seed` makes the path deterministic yet unique.
    """
    a: Tuple[float, float, float]
    b: Tuple[float, float, float]
    radius: float
    wander: float = 0.18
    segments: int = 4
    shape_seed: int = 0


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

    # Carve each chamber as an irregular multi-lobe blob with a flat walkable
    # floor and floor-tapered noise so the floor is navigable while the walls
    # and ceiling stay rough.
    #
    # Near the floor the noise is both tapered (small amplitude) AND made
    # one-sided: it may raise gentle bumps but never carves BELOW the floor
    # plane (which would create pits/dips that break walkability). Higher up,
    # the full two-sided noise applies for rough walls and ceiling.
    for ch in spec.chambers:
        floor_z = ch.floor_z if ch.floor_z is not None else ch.center[2] - ch.radius * 0.5
        n = _floor_shaped_noise(Z, base_noise, floor_z, spec)
        s = _chamber_sdf(grid, ch, floor_z) + n
        smooth_union_carve(grid, s, k=spec.smooth_k)

    # Tunnels wind between rooms instead of running dead straight.
    for tn in spec.tunnels:
        floor_z = min(tn.a[2], tn.b[2]) - tn.radius
        n = _floor_shaped_noise(Z, base_noise, floor_z, spec)
        s = _tunnel_sdf(grid, tn) + n
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
# Organic chamber / tunnel shapes
# ---------------------------------------------------------------------------

def _chamber_sdf(grid: FieldGrid, ch: Chamber, floor_z: float) -> np.ndarray:
    """
    SDF of an irregular chamber: a cluster of offset dome lobes smooth-unioned
    together, so the chamber footprint is a lumpy blob rather than a circle.

    The first lobe is the full-radius dome at the chamber centre; the extra
    lobes are smaller, pushed out horizontally in varied directions and sizes,
    all sharing the same flat floor so the whole chamber stays walkable.
    """
    base = sdf_dome(grid, ch.center, ch.radius, floor_z)
    if ch.lobes <= 1 or ch.irregularity <= 0.0:
        return base

    rng = np.random.default_rng(ch.shape_seed or 1)
    cx, cy, cz = ch.center
    out = base
    for _ in range(ch.lobes - 1):
        ang = rng.uniform(0.0, 2.0 * np.pi)
        dist = ch.radius * ch.irregularity * rng.uniform(0.5, 1.0)
        lobe_r = ch.radius * rng.uniform(0.55, 0.9)
        lx = cx + np.cos(ang) * dist
        ly = cy + np.sin(ang) * dist
        # Keep the lobe centre at or above the chamber centre so its dome adds
        # width/ceiling variety without pulling the air volume below the floor.
        lz = cz + ch.radius * rng.uniform(0.0, 0.2)
        lobe = sdf_dome(grid, (lx, ly, lz), lobe_r, floor_z)
        # Fillet proportional to the smaller lobe so junctions read as one cave.
        out = smooth_min(out, lobe, k=max(12.0, lobe_r * 0.5))

    # The smooth-min fillet can bow the blended air volume slightly below the
    # floor plane at lobe junctions. Re-intersect with the half-space above the
    # floor so the chamber keeps a single flat walkable floor at floor_z.
    _, _, Z = grid.world_coords()
    above_floor = floor_z - Z   # <0 above the floor, >0 below
    return np.maximum(out, above_floor)


def _tunnel_waypoints(tn: Tunnel) -> List[Tuple[float, float, float]]:
    """
    Build a meandering polyline from a→b: evenly spaced points along the
    straight line, each (except the endpoints) jittered perpendicular to the
    line so the passage curves naturally. Jitter is in the horizontal plane
    (plus a little vertical) and tapers to zero at both ends so the tunnel
    still meets its rooms squarely.
    """
    import math

    ax, ay, az = tn.a
    bx, by, bz = tn.b
    dx, dy, dz = bx - ax, by - ay, bz - az
    length = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0

    # Horizontal perpendicular (unit) to the a→b direction.
    hx, hy = -dy, dx
    hlen = math.sqrt(hx * hx + hy * hy) or 1.0
    hx, hy = hx / hlen, hy / hlen

    seg = max(2, tn.segments)
    rng = np.random.default_rng(tn.shape_seed or 1)
    amp = tn.wander * length

    pts: List[Tuple[float, float, float]] = [tn.a]
    for i in range(1, seg):
        t = i / seg
        # Base point on the straight line.
        px = ax + dx * t
        py = ay + dy * t
        pz = az + dz * t
        # Taper the offset so it is 0 at both ends and max in the middle.
        taper = math.sin(math.pi * t)
        off = float(rng.uniform(-1.0, 1.0)) * amp * taper
        px += hx * off
        py += hy * off
        pz += float(rng.uniform(-0.08, 0.08)) * amp * taper
        pts.append((px, py, pz))
    pts.append(tn.b)
    return pts


def _tunnel_sdf(grid: FieldGrid, tn: Tunnel) -> np.ndarray:
    """
    SDF of a winding tunnel: a chain of capsule segments through jittered
    waypoints, smooth-unioned so the bends are rounded. Segment radius varies
    mildly along the length so the passage pinches and widens like a real cave.
    """
    pts = _tunnel_waypoints(tn)
    rng = np.random.default_rng((tn.shape_seed or 1) + 7)

    def seg_radius(i: int) -> float:
        return tn.radius * float(rng.uniform(0.82, 1.18))

    out = sdf_capsule(grid, pts[0], pts[1], seg_radius(0))
    for i in range(1, len(pts) - 1):
        s = sdf_capsule(grid, pts[i], pts[i + 1], seg_radius(i))
        out = smooth_min(out, s, k=max(14.0, tn.radius * 0.6))
    return out


# ---------------------------------------------------------------------------
# Grid sizing
# ---------------------------------------------------------------------------

# Cap total voxels so large/sprawling caves stay fast and bounded in memory.
# ~2.5M voxels keeps generation well under a second; beyond that we coarsen
# the voxel size automatically.
_MAX_VOXELS = 2_500_000


def _make_grid(spec: CaveSpec) -> FieldGrid:
    """
    Compute a grid that bounds all chambers/tunnels plus padding.

    If the requested voxel size would exceed the voxel budget (sprawling zones),
    the voxel size is automatically coarsened so generation stays fast. Finer
    detail is traded for feasibility on very large footprints.
    """
    pts: List[Tuple[float, float, float]] = []
    max_r = 0.0
    for ch in spec.chambers:
        pts.append(ch.center)
        # Lobes push the footprint out past the nominal radius.
        max_r = max(max_r, ch.radius * (1.0 + ch.irregularity))
    for tn in spec.tunnels:
        # Include the meander waypoints so wandering tunnels stay inside the grid.
        pts.extend(_tunnel_waypoints(tn))
        max_r = max(max_r, tn.radius)

    arr = np.array(pts, dtype=np.float32)
    margin = spec.padding + max_r + spec.noise_amplitude
    lo = arr.min(axis=0) - margin
    hi = arr.max(axis=0) + margin

    origin = (float(lo[0]), float(lo[1]), float(lo[2]))
    extent = hi - lo

    voxel = spec.voxel
    while True:
        shape = tuple(int(np.ceil(e / voxel)) + 1 for e in extent)
        total = shape[0] * shape[1] * shape[2]
        if total <= _MAX_VOXELS:
            break
        # Coarsen by the cube-root ratio to get back under budget in one or two steps
        ratio = (total / _MAX_VOXELS) ** (1.0 / 3.0)
        voxel *= max(1.1, ratio)

    return FieldGrid.solid(shape=shape, origin=origin, voxel=voxel)
