"""
core/wld.py
-----------
Minimal WLD reader for Classic–PoP era zones (the .s3d / WLD format).

Scope: GEOMETRY ONLY. This reader extracts zone mesh geometry (vertices,
polygons) and the texture/material list from the 0x36 Mesh and 0x31 Texture
List fragments. It does NOT handle skeletons, animations, mob models, BSP
trees, lights, or object placement — those aren't needed for the current goal
(measuring geometric fidelity of real zones to calibrate the generator).

A WLD lives inside an .s3d PFS archive (which our existing core.pfs reads).

Format reference: Windcatcher's WLD File Reference. Old-format files use
16-bit texture coords; new-format use 32-bit. We detect via the version field.

Fragment layout (all little-endian):
  Header (28 bytes): magic, version, fragment_count, bsp_region_count,
                     unknown, string_hash_size, unknown2
  String hash (string_hash_size bytes, XOR-encoded)
  Fragments: each is [uint32 size][uint32 id][uint32 name_ref][...payload...]
             (size counts the bytes AFTER the size field's... actually after
              id+name onward — see _iter_fragments for the exact stride)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

WLD_MAGIC = 0x54503D02
VERSION_OLD = 0x00015500   # 16-bit texture coords
VERSION_NEW = 0x1000C800   # 32-bit texture coords

FRAG_TEXTURE_NAMES = 0x03
FRAG_TEXTURE_LIST  = 0x31
FRAG_MESH          = 0x36


@dataclass
class WldMesh:
    """Geometry extracted from one 0x36 Mesh fragment (world-space)."""
    vertices: List[Tuple[float, float, float]] = field(default_factory=list)
    polygons: List[Tuple[int, int, int, int]] = field(default_factory=list)  # v1,v2,v3,flag

    @property
    def polygon_count(self) -> int:
        return len(self.polygons)


@dataclass
class WldZone:
    """All zone meshes + texture names from a WLD file."""
    meshes: List[WldMesh] = field(default_factory=list)
    texture_names: List[str] = field(default_factory=list)
    is_old_format: bool = True

    @property
    def total_vertices(self) -> int:
        return sum(len(m.vertices) for m in self.meshes)

    @property
    def total_polygons(self) -> int:
        return sum(m.polygon_count for m in self.meshes)

    def all_triangles(self) -> List[Tuple]:
        """Return every triangle as (p0, p1, p2) world-space point tuples."""
        tris = []
        for m in self.meshes:
            for v1, v2, v3, _flag in m.polygons:
                if v1 < len(m.vertices) and v2 < len(m.vertices) and v3 < len(m.vertices):
                    tris.append((m.vertices[v1], m.vertices[v2], m.vertices[v3]))
        return tris


# ---------------------------------------------------------------------------
# String hash (XOR-encoded)
# ---------------------------------------------------------------------------

_XOR_KEY = bytes([0x95, 0x3A, 0xC5, 0x2A, 0x95, 0x7A, 0x95, 0x6A])


def _decode_string_hash(data: bytes) -> bytes:
    out = bytearray(len(data))
    for i, b in enumerate(data):
        out[i] = b ^ _XOR_KEY[i % 8]
    return bytes(out)


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

def load_wld(data: bytes) -> WldZone:
    """Parse a WLD byte buffer into a WldZone (geometry + texture names)."""
    magic, version, frag_count, _bsp, _u1, hash_size, _u2 = struct.unpack_from(
        "<IIIIIII", data, 0
    )
    if magic != WLD_MAGIC:
        raise ValueError(f"Not a WLD file (magic=0x{magic:08X})")

    is_old = (version == VERSION_OLD)
    zone = WldZone(is_old_format=is_old)

    # String hash (decoded, used for texture filenames)
    hash_start = 28
    string_hash = _decode_string_hash(data[hash_start:hash_start + hash_size])

    pos = hash_start + hash_size
    for _ in range(frag_count):
        if pos + 8 > len(data):
            break
        size, frag_id = struct.unpack_from("<II", data, pos)
        # Fragment body begins after size+id; `size` counts bytes from the
        # name_ref field (inclusive) to the fragment's end.
        body_start = pos + 8
        body_end = body_start + size

        if frag_id == FRAG_MESH:
            mesh = _parse_mesh(data, body_start, body_end, is_old)
            if mesh is not None:
                zone.meshes.append(mesh)
        elif frag_id == FRAG_TEXTURE_NAMES:
            name = _parse_texture_name(data, body_start, body_end, string_hash)
            if name:
                zone.texture_names.append(name)

        pos = body_end

    return zone


def _parse_texture_name(data: bytes, start: int, end: int, string_hash: bytes) -> Optional[str]:
    """
    0x03: contains encoded bitmap filename(s). Return the first name.

    Body layout: name_ref (DWORD) | count-1 (DWORD) | per name: len (WORD) +
    XOR-encoded bytes.
    """
    try:
        pos = start
        pos += 4  # name_ref
        pos += 4  # count field (number of names, minus 1)
        name_len = struct.unpack_from("<H", data, pos)[0]
        pos += 2
        raw = data[pos:pos + name_len]
        decoded = _decode_string_hash(raw)
        return decoded.rstrip(b"\x00").decode("ascii", errors="replace")
    except Exception:
        return None


def _parse_mesh(data: bytes, start: int, end: int, is_old: bool) -> Optional[WldMesh]:
    """
    Parse a 0x36 Mesh fragment's geometry.

    Layout after the name_ref (which is the first DWORD of the body):
      name_ref (DWORD)
      flags (DWORD)
      fragment1..4 (4 x DWORD)
      centerX/Y/Z (3 x FLOAT)
      params2[0..2] (3 x DWORD)
      maxDist (FLOAT), min/max XYZ (6 x FLOAT)
      vertexCount, texCoordCount, normalCount, colorCount, polygonCount,
      vertexPieceCount, polygonTexCount, vertexTexCount, size9, scale  (10 x WORD)
      vertices[vertexCount]:  3 x SIGNED WORD  (×1/(1<<scale), + center)
      texcoords[texCoordCount]: 2 x (SWORD old / SDWORD new)
      normals[normalCount]: 3 x SIGNED BYTE
      colors[colorCount]: DWORD
      polygons[polygonCount]: WORD flag + 3 x WORD vertex index
      ...(texture/piece groupings follow; not needed)
    """
    try:
        pos = start
        pos += 4  # name_ref
        pos += 4  # flags
        pos += 16  # fragment1..4
        cx, cy, cz = struct.unpack_from("<fff", data, pos); pos += 12
        pos += 12  # params2[0..2]
        pos += 4   # maxDist
        pos += 24  # min/max XYZ (6 floats)

        (vcount, tcount, ncount, ccount, pcount,
         vpcount, ptcount, vtcount, size9, scale) = struct.unpack_from("<HHHHHHHHHH", data, pos)
        pos += 20

        inv_scale = 1.0 / float(1 << scale) if scale < 31 else 1.0

        # Vertices
        verts: List[Tuple[float, float, float]] = []
        for _ in range(vcount):
            x, y, z = struct.unpack_from("<hhh", data, pos)
            pos += 6
            verts.append((x * inv_scale + cx, y * inv_scale + cy, z * inv_scale + cz))

        # Texcoords (skip — not needed for fidelity)
        tc_stride = 8 if not is_old else 4
        pos += tcount * tc_stride

        # Normals (skip)
        pos += ncount * 3

        # Colors (skip)
        pos += ccount * 4

        # Polygons
        polys: List[Tuple[int, int, int, int]] = []
        for _ in range(pcount):
            flag, v1, v2, v3 = struct.unpack_from("<HHHH", data, pos)
            pos += 8
            polys.append((v1, v2, v3, flag))

        mesh = WldMesh(vertices=verts, polygons=polys)
        return mesh
    except Exception:
        return None
