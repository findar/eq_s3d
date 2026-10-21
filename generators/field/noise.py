"""
generators/field/noise.py
--------------------------
Fast vectorised value noise used to perturb terrain heightfields so surfaces
are irregular and organic rather than smoothly interpolated.

Implementation is fully vectorised numpy gradient/value noise — no per-voxel
Python loops — so a ~100k-voxel grid evaluates in milliseconds. (The previous
opensimplex.noise3array path was pure-Python and took ~26s for the same grid.)
"""

from __future__ import annotations

import numpy as np


# ---------------------------------------------------------------------------
# Vectorised 3D value noise with smooth (quintic) interpolation.
# ---------------------------------------------------------------------------

def _hash3(ix, iy, iz, seed):
    """Deterministic hash of integer lattice coords → pseudo-random [0,1)."""
    # Large primes; wrap in uint32 to keep it fast and deterministic.
    h = (ix.astype(np.int64) * 374761393
         + iy.astype(np.int64) * 668265263
         + iz.astype(np.int64) * 2147483647
         + np.int64(seed) * 69069)
    h = (h ^ (h >> np.int64(13))) * np.int64(1274126177)
    h = h ^ (h >> np.int64(16))
    return (h & np.int64(0xFFFFFF)).astype(np.float32) / float(0xFFFFFF)


def _quintic(t):
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def _value_noise_3d(x, y, z, seed):
    """Trilinear value noise with quintic smoothing, fully vectorised."""
    x0 = np.floor(x); y0 = np.floor(y); z0 = np.floor(z)
    fx = x - x0; fy = y - y0; fz = z - z0

    ix = x0.astype(np.int64); iy = y0.astype(np.int64); iz = z0.astype(np.int64)

    # Corner values
    c000 = _hash3(ix,     iy,     iz,     seed)
    c100 = _hash3(ix + 1, iy,     iz,     seed)
    c010 = _hash3(ix,     iy + 1, iz,     seed)
    c110 = _hash3(ix + 1, iy + 1, iz,     seed)
    c001 = _hash3(ix,     iy,     iz + 1, seed)
    c101 = _hash3(ix + 1, iy,     iz + 1, seed)
    c011 = _hash3(ix,     iy + 1, iz + 1, seed)
    c111 = _hash3(ix + 1, iy + 1, iz + 1, seed)

    ux = _quintic(fx); uy = _quintic(fy); uz = _quintic(fz)

    # Trilinear blend
    x00 = c000 * (1 - ux) + c100 * ux
    x10 = c010 * (1 - ux) + c110 * ux
    x01 = c001 * (1 - ux) + c101 * ux
    x11 = c011 * (1 - ux) + c111 * ux
    y0_ = x00 * (1 - uy) + x10 * uy
    y1_ = x01 * (1 - uy) + x11 * uy
    val = y0_ * (1 - uz) + y1_ * uz

    # Map [0,1] → [-1,1]
    return (val * 2.0 - 1.0).astype(np.float32)
