"""
generators/textures.py
----------------------
Placeholder texture generation (Phase 2) and the hook for AI texture
generation (Phase 3).

For Phase 2 we emit simple solid-colour / noise DDS textures so generated
zones are visually distinguishable in the preview without needing an image
model. Phase 3 replaces `generate_texture` with a call to an image model.
"""

from __future__ import annotations

import struct
from typing import Tuple

# ---------------------------------------------------------------------------
# Minimal DDS (uncompressed BGRA) writer
# ---------------------------------------------------------------------------
# The RoF2 client supports uncompressed 32-bit DDS as well as DXT. We emit
# uncompressed A8R8G8B8 which is the simplest valid format and loads fine.

_DDS_MAGIC = b"DDS "
_DDSD_CAPS        = 0x1
_DDSD_HEIGHT      = 0x2
_DDSD_WIDTH       = 0x4
_DDSD_PIXELFORMAT = 0x1000
_DDSD_PITCH       = 0x8
_DDPF_RGB         = 0x40
_DDPF_ALPHAPIXELS = 0x1
_DDSCAPS_TEXTURE  = 0x1000


def _dds_header(width: int, height: int) -> bytes:
    """Build a 128-byte DDS header for uncompressed A8R8G8B8."""
    pitch = width * 4
    flags = _DDSD_CAPS | _DDSD_HEIGHT | _DDSD_WIDTH | _DDSD_PIXELFORMAT | _DDSD_PITCH

    header = bytearray(124)
    struct.pack_into("<I", header, 0, 124)          # dwSize
    struct.pack_into("<I", header, 4, flags)         # dwFlags
    struct.pack_into("<I", header, 8, height)        # dwHeight
    struct.pack_into("<I", header, 12, width)        # dwWidth
    struct.pack_into("<I", header, 16, pitch)        # dwPitchOrLinearSize
    # dwDepth (20), dwMipMapCount (24) left zero

    # Pixel format (offset 72 within the 124-byte header, 32 bytes)
    pf = 72
    struct.pack_into("<I", header, pf, 32)                                # dwSize
    struct.pack_into("<I", header, pf + 4, _DDPF_RGB | _DDPF_ALPHAPIXELS) # dwFlags
    struct.pack_into("<I", header, pf + 8, 0)                             # dwFourCC
    struct.pack_into("<I", header, pf + 12, 32)                           # dwRGBBitCount
    struct.pack_into("<I", header, pf + 16, 0x00FF0000)                   # R mask
    struct.pack_into("<I", header, pf + 20, 0x0000FF00)                   # G mask
    struct.pack_into("<I", header, pf + 24, 0x000000FF)                   # B mask
    struct.pack_into("<I", header, pf + 28, 0xFF000000)                   # A mask

    # Caps (offset 104)
    struct.pack_into("<I", header, 104, _DDSCAPS_TEXTURE)

    return _DDS_MAGIC + bytes(header)


def make_placeholder_dds(color: Tuple[int, int, int],
                         size: int = 64,
                         noise: int = 20) -> bytes:
    """
    Create a simple solid-colour DDS with slight per-pixel noise so surfaces
    aren't flat and texture tiling is visible in the preview.
    """
    import random
    rng = random.Random(sum(color))
    r, g, b = color

    header = _dds_header(size, size)
    pixels = bytearray(size * size * 4)
    for i in range(size * size):
        jitter = rng.randint(-noise, noise)
        pr = max(0, min(255, r + jitter))
        pg = max(0, min(255, g + jitter))
        pb = max(0, min(255, b + jitter))
        # A8R8G8B8 stored little-endian → bytes are B, G, R, A
        off = i * 4
        pixels[off + 0] = pb
        pixels[off + 1] = pg
        pixels[off + 2] = pr
        pixels[off + 3] = 255

    return header + bytes(pixels)


def generate_texture(description: str,
                     color: Tuple[int, int, int],
                     size: int = 64) -> bytes:
    """
    Phase 2: returns a placeholder DDS keyed on the material colour.

    Phase 3 will replace this with an image-model call that uses *description*
    to synthesise a real tileable texture, then encodes it to DXT1/DXT5 DDS.
    """
    return make_placeholder_dds(color, size=size)
