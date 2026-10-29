"""
Wave-3 (task 7.1) BASELINE capture for generators/field/terrain.py.

Pins the existing FBM + thermal-erosion + _enforce_walkable plain-terrain path
with a fixed seed and records:
  (a) a deterministic checksum of the rounded height ndarray, and
  (b) the wall-clock timing of a full build_terrain().

Wave-3 tasks 7.2/7.3 add the matrix-subordinated Noise_Pass and the new
hydraulic erosion pass. They must prove ADDITIVE: re-running this script on the
plain-terrain path (no wilderness matrix) MUST reproduce the SAME checksum.

Run from the worktree root:  python capture_baseline.py
"""
from __future__ import annotations

import hashlib
import time

import numpy as np

from generators.field.terrain import (
    TerrainSpec,
    build_terrain,
    _generate_heightfield,
    _thermal_erosion,
    _enforce_walkable,
)

# Fixed, pinned inputs — the "one plain-terrain (wilderness/outdoor) spec".
SEED = 1337
SPEC = TerrainSpec(
    width=2400.0,
    depth=2400.0,
    resolution=40.0,
    seed=SEED,
    height_scale=220.0,
    noise_scale=900.0,
    octaves=5,
    erosion_iterations=25,
    talus_angle=0.6,
    max_walkable_grad=0.70,
    walkable_passes=4,
)


def _heights_through_pipeline(spec: TerrainSpec) -> np.ndarray:
    """Reproduce build_terrain's height stages (pre-triangulation)."""
    nx = max(2, int(spec.width / spec.resolution) + 1)
    ny = max(2, int(spec.depth / spec.resolution) + 1)
    heights = _generate_heightfield(spec, nx, ny)
    if spec.erosion_iterations > 0:
        heights = _thermal_erosion(heights, spec.talus_angle, spec.erosion_iterations)
    heights = _enforce_walkable(heights, spec)
    return heights


def height_checksum(heights: np.ndarray) -> str:
    """Deterministic checksum: round to 3 decimals, hash the raw float64 bytes."""
    rounded = np.round(heights.astype(np.float64), 3)
    rounded = np.ascontiguousarray(rounded)
    h = hashlib.sha256()
    h.update(str(rounded.shape).encode("ascii"))
    h.update(rounded.tobytes())
    return h.hexdigest()


def main() -> None:
    # Checksum (determinism check: run the pipeline twice, must agree).
    heights = _heights_through_pipeline(SPEC)
    checksum = height_checksum(heights)
    checksum2 = height_checksum(_heights_through_pipeline(SPEC))
    assert checksum == checksum2, "pipeline is non-deterministic for a pinned seed!"

    # Timing of a full build_terrain (height pipeline + triangulation).
    t0 = time.perf_counter()
    ter = build_terrain(SPEC, name="baseline_karana")
    elapsed = time.perf_counter() - t0

    nverts = len(ter.vertices) if ter is not None else 0
    npolys = len(ter.polygons) if ter is not None else 0

    print("=== Wave-3 task 7.1 terrain baseline ===")
    print(f"seed                 : {SEED}")
    print(f"grid shape (nx, ny)  : {heights.shape}")
    print(f"height min/max       : {float(heights.min()):.3f} / {float(heights.max()):.3f}")
    print(f"height checksum      : sha256:{checksum}")
    print(f"build_terrain time   : {elapsed:.4f} s")
    print(f"TER verts / polys    : {nverts} / {npolys}")
    print()
    print("invocation: build_terrain(TerrainSpec(width=2400, depth=2400,")
    print("            resolution=40, seed=1337, height_scale=220,")
    print("            noise_scale=900, octaves=5, erosion_iterations=25,")
    print("            talus_angle=0.6, max_walkable_grad=0.70,")
    print("            walkable_passes=4), name='baseline_karana')")
    print("checksum = sha256 of np.round(heights.astype(float64), 3).tobytes()")
    print("           prefixed with the array shape, over the")
    print("           _generate_heightfield -> _thermal_erosion -> _enforce_walkable stages")


if __name__ == "__main__":
    main()
