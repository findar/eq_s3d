"""
generators/textures/dds.py
---------------------------
DDS encoding. Writes uncompressed A8R8G8B8 DDS, which the RoF2 client loads
directly. (DXT1/DXT5 compression is a future optimisation; uncompressed is
simplest and correct.)

Also provides the seamless-tiling helper used by the procedural provider.
"""

from __future__ import annotations

import struct
from typing import Optional

import numpy as np

_DDS_MAGIC = b"DDS "
_DDSD_CAPS        = 0x1
_DDSD_HEIGHT      = 0x2
_DDSD_WIDTH       = 0x4
_DDSD_PIXELFORMAT = 0x1000
_DDSD_PITCH       = 0x8
_DDPF_RGB         = 0x40
_DDPF_ALPHAPIXELS = 0x1
_DDSCAPS_TEXTURE  = 0x1000


def dds_header(width: int, height: int) -> bytes:
    """128-byte DDS header for uncompressed A8R8G8B8."""
    pitch = width * 4
    flags = _DDSD_CAPS | _DDSD_HEIGHT | _DDSD_WIDTH | _DDSD_PIXELFORMAT | _DDSD_PITCH

    header = bytearray(124)
    struct.pack_into("<I", header, 0, 124)
    struct.pack_into("<I", header, 4, flags)
    struct.pack_into("<I", header, 8, height)
    struct.pack_into("<I", header, 12, width)
    struct.pack_into("<I", header, 16, pitch)

    pf = 72
    struct.pack_into("<I", header, pf, 32)
    struct.pack_into("<I", header, pf + 4, _DDPF_RGB | _DDPF_ALPHAPIXELS)
    struct.pack_into("<I", header, pf + 8, 0)
    struct.pack_into("<I", header, pf + 12, 32)
    struct.pack_into("<I", header, pf + 16, 0x00FF0000)   # R
    struct.pack_into("<I", header, pf + 20, 0x0000FF00)   # G
    struct.pack_into("<I", header, pf + 24, 0x000000FF)   # B
    struct.pack_into("<I", header, pf + 28, 0xFF000000)   # A

    struct.pack_into("<I", header, 104, _DDSCAPS_TEXTURE)
    return _DDS_MAGIC + bytes(header)


def rgba_to_dds(rgb: np.ndarray, alpha: Optional[np.ndarray] = None) -> bytes:
    """
    Encode an (H, W, 3) uint8 RGB array (optionally with an (H, W) alpha array)
    into an uncompressed A8R8G8B8 DDS. Stored little-endian B, G, R, A per pixel.
    """
    h, w = rgb.shape[0], rgb.shape[1]
    out = np.empty((h, w, 4), dtype=np.uint8)
    out[..., 0] = rgb[..., 2]  # B
    out[..., 1] = rgb[..., 1]  # G
    out[..., 2] = rgb[..., 0]  # R
    out[..., 3] = alpha if alpha is not None else 255
    return dds_header(w, h) + out.tobytes()


def make_tileable(img: np.ndarray, blend: float = 0.25) -> np.ndarray:
    """
    Make an (H, W, C) float image seamlessly tileable using the offset-and-blend
    method: shift by half, then cross-fade the seams with a mirrored copy so the
    edges match their opposite edges.

    Returns a float array in the same range as the input.
    """
    h, w = img.shape[0], img.shape[1]

    # Horizontal blend: feather the left edge with a mirrored right edge.
    bw = max(1, int(w * blend))
    ramp_x = np.linspace(0.0, 1.0, bw, dtype=np.float32)
    out = img.astype(np.float32).copy()

    # Blend left strip with the mirror of the right strip
    left = out[:, :bw]
    right_mirror = out[:, -bw:][:, ::-1]
    for c in range(out.shape[2]):
        out[:, :bw, c] = left[:, :, c] * ramp_x[None, :] + right_mirror[:, :, c] * (1 - ramp_x)[None, :]

    # Vertical blend
    bh = max(1, int(h * blend))
    ramp_y = np.linspace(0.0, 1.0, bh, dtype=np.float32)
    top = out[:bh, :]
    bottom_mirror = out[-bh:, :][::-1, :]
    for c in range(out.shape[2]):
        out[:bh, :, c] = top[:, :, c] * ramp_y[:, None] + bottom_mirror[:, :, c] * (1 - ramp_y)[:, None]

    return out
