"""
core/ter.py
-----------
Reader and writer for EverQuest EQG terrain / model files.

Both .ter (terrain, magic 'EQGT') and .mod/.mds (models, magic 'EQGM') share
the same binary layout.  This module handles both.

Binary layout (little-endian, packed — no alignment padding):

  mod_header:
    char[4]   magic          'EQGT' (terrain) | 'EQGM' (model)
    uint32    version        1 = vertex v1/v2, 3 = vertex v3 (adds color + 2 unknowns)
    uint32    list_length    byte length of the string table that follows
    uint32    material_count
    uint32    vert_count
    uint32    tri_count

  [string table — list_length bytes]
    Null-terminated strings concatenated.  All name/shader/property values in
    the material section are byte offsets into this table.

  materials[material_count]:
    uint32  index           material index (0-based)
    uint32  name_offset     → string table
    uint32  shader_offset   → string table
    uint32  property_count

    properties[property_count]:
      uint32  name_offset   → string table
      uint32  type          0=float, 1=int, 2=string (offset into table)
      uint32  value         interpreted per type

  vertices[vert_count]  (version < 3):
    float  x, y, z         position
    float  i, j, k         normal
    float  u, v            UV

  vertices[vert_count]  (version >= 3):
    float   x, y, z
    float   i, j, k
    uint32  color           ARGB vertex color (typically 0xFFFFFFFF)
    float   unk036, unk040  unknown — write as 0.0
    float   u, v

  polygons[tri_count]:
    uint32  v1, v2, v3      vertex indices
    int32   material        index into materials (-1 = no material)
    uint32  flags           0x01 = non-collidable (passable)

Reference: EQEmu/zone-utilities src/common/eqg_structs.h + eqg_model_loader.cpp
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAGIC_TERRAIN = b"EQGT"
MAGIC_MODEL   = b"EQGM"

SHADER_OPAQUE   = "Opaque_MaxCB1.fx"
SHADER_ALPHA    = "Alpha_MaxCB1.fx"
SHADER_CHROMA   = "Chroma_MaxCB1.fx"
SHADER_BOUNDARY = "Boundary.fx"

PROP_DIFFUSE  = "e_TextureDiffuse0"   # type=2 (string — filename)
PROP_NORMAL   = "e_TextureNormal0"    # type=2
PROP_ENVMAP   = "e_TextureEnvironment0"  # type=2
PROP_SHINY    = "e_fShininess0"       # type=0 (float)
PROP_SLIDE1X  = "e_fSlide1X"          # type=0 — UV scroll X (water/lava)
PROP_SLIDE1Y  = "e_fSlide1Y"          # type=0 — UV scroll Y

PROP_TYPE_FLOAT  = 0
PROP_TYPE_INT    = 1
PROP_TYPE_STRING = 2

FLAG_PASSABLE = 0x01  # polygon is non-collidable

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class MaterialProperty:
    name: str
    type: int           # PROP_TYPE_*
    value_f: float = 0.0
    value_i: int   = 0
    value_s: str   = ""

    @classmethod
    def float(cls, name: str, value: float) -> "MaterialProperty":
        return cls(name=name, type=PROP_TYPE_FLOAT, value_f=value)

    @classmethod
    def int_(cls, name: str, value: int) -> "MaterialProperty":
        return cls(name=name, type=PROP_TYPE_INT, value_i=value)

    @classmethod
    def string(cls, name: str, value: str) -> "MaterialProperty":
        return cls(name=name, type=PROP_TYPE_STRING, value_s=value)


@dataclass
class Material:
    """A single material inside a TER/MOD file."""
    index: int
    name: str
    shader: str = SHADER_OPAQUE
    properties: List[MaterialProperty] = field(default_factory=list)

    def add_diffuse(self, filename: str) -> "Material":
        self.properties.append(MaterialProperty.string(PROP_DIFFUSE, filename))
        return self

    def add_normal(self, filename: str) -> "Material":
        self.properties.append(MaterialProperty.string(PROP_NORMAL, filename))
        return self

    def add_shininess(self, value: float = 1.0) -> "Material":
        self.properties.append(MaterialProperty.float(PROP_SHINY, value))
        return self


@dataclass
class Vertex:
    """A single vertex (position + normal + UV + optional color)."""
    x: float
    y: float
    z: float
    nx: float = 0.0
    ny: float = 0.0
    nz: float = 1.0
    u: float  = 0.0
    v: float  = 0.0
    color: int = 0xFFFFFFFF   # ARGB, only written in version 3


@dataclass
class Polygon:
    """A triangle referencing three vertex indices."""
    v1: int
    v2: int
    v3: int
    material: int = 0       # index into material list; -1 = none
    flags: int    = 0       # FLAG_PASSABLE etc.


@dataclass
class TerFile:
    """
    Complete in-memory representation of a .ter or .mod file.

    Usage::

        ter = TerFile(name="myzone", magic=MAGIC_TERRAIN)
        mat = Material(index=0, name="stone_wall", shader=SHADER_OPAQUE)
        mat.add_diffuse("stone_wall_01.dds")
        ter.materials.append(mat)

        ter.vertices.append(Vertex(0, 0, 0, u=0.0, v=0.0))
        ...
        ter.polygons.append(Polygon(0, 1, 2, material=0))

        data = ter.to_bytes()
    """

    name: str
    magic: bytes = MAGIC_TERRAIN
    version: int = 2
    materials: List[Material] = field(default_factory=list)
    vertices: List[Vertex]    = field(default_factory=list)
    polygons: List[Polygon]   = field(default_factory=list)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @classmethod
    def from_bytes(cls, data: bytes, name: str = "") -> "TerFile":
        """Parse a TER/MOD file from raw bytes."""
        pos = 0

        def read(fmt: str) -> tuple:
            nonlocal pos
            size = struct.calcsize(fmt)
            result = struct.unpack_from(fmt, data, pos)
            pos += size
            return result

        magic        = data[0:4]
        version,     = struct.unpack_from("<I", data, 4)
        list_length, = struct.unpack_from("<I", data, 8)
        mat_count,   = struct.unpack_from("<I", data, 12)
        vert_count,  = struct.unpack_from("<I", data, 16)
        tri_count,   = struct.unpack_from("<I", data, 20)
        pos = 24

        if magic not in (MAGIC_TERRAIN, MAGIC_MODEL):
            raise ValueError(f"Unrecognised TER magic: {magic!r}")

        # For 'EQGM' models there is an additional bone_count uint32
        if magic == MAGIC_MODEL:
            pos += 4  # skip bone_count

        # String table
        list_start = pos
        pos += list_length

        def str_at(offset: int) -> str:
            end = data.index(b"\x00", list_start + offset)
            return data[list_start + offset : end].decode("ascii", errors="replace")

        # Materials
        materials: List[Material] = []
        for _ in range(mat_count):
            idx, name_off, shader_off, prop_count = struct.unpack_from("<IIII", data, pos)
            pos += 16
            mat = Material(
                index=idx,
                name=str_at(name_off),
                shader=str_at(shader_off),
            )
            for _ in range(prop_count):
                pname_off, ptype, pval = struct.unpack_from("<III", data, pos)
                pos += 12
                prop = MaterialProperty(name=str_at(pname_off), type=ptype)
                if ptype == PROP_TYPE_STRING:
                    prop.value_s = str_at(pval)
                elif ptype == PROP_TYPE_FLOAT:
                    prop.value_f = struct.unpack_from("<f", struct.pack("<I", pval))[0]
                else:
                    prop.value_i = pval
                mat.properties.append(prop)
            materials.append(mat)

        # Vertices
        vertices: List[Vertex] = []
        if version < 3:
            for _ in range(vert_count):
                x, y, z, nx, ny, nz, u, v = struct.unpack_from("<ffffffff", data, pos)
                pos += 32
                vertices.append(Vertex(x=x, y=y, z=z, nx=nx, ny=ny, nz=nz, u=u, v=v))
        else:
            for _ in range(vert_count):
                x, y, z, nx, ny, nz, color, unk1, unk2, u, v = struct.unpack_from(
                    "<ffffffIffff", data, pos
                )
                pos += 44
                vertices.append(Vertex(x=x, y=y, z=z, nx=nx, ny=ny, nz=nz, u=u, v=v, color=color))

        # Polygons
        polygons: List[Polygon] = []
        for _ in range(tri_count):
            v1, v2, v3, mat, flags = struct.unpack_from("<IIIiI", data, pos)
            pos += 20
            polygons.append(Polygon(v1=v1, v2=v2, v3=v3, material=mat, flags=flags))

        ter = cls(name=name, magic=magic, version=version)
        ter.materials = materials
        ter.vertices  = vertices
        ter.polygons  = polygons
        return ter

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def to_bytes(self) -> bytes:
        """Serialise to bytes ready to embed in a PFS archive."""
        # --- Build string table -----------------------------------------
        string_table = bytearray()
        _offsets: dict[str, int] = {}

        def intern(s: str) -> int:
            """Add string to table if not present; return byte offset."""
            if s not in _offsets:
                _offsets[s] = len(string_table)
                string_table.extend(s.encode("ascii") + b"\x00")
            return _offsets[s]

        # Pre-intern all strings so we know their offsets before writing
        for mat in self.materials:
            intern(mat.name)
            intern(mat.shader)
            for prop in mat.properties:
                intern(prop.name)
                if prop.type == PROP_TYPE_STRING:
                    intern(prop.value_s)

        list_length = len(string_table)

        # --- Header -----------------------------------------------------
        out = bytearray()
        out += self.magic
        out += struct.pack("<IIIII",
            self.version,
            list_length,
            len(self.materials),
            len(self.vertices),
            len(self.polygons),
        )

        # Extra bone_count for model files
        if self.magic == MAGIC_MODEL:
            out += struct.pack("<I", 0)

        # String table
        out += bytes(string_table)

        # --- Materials --------------------------------------------------
        for mat in self.materials:
            out += struct.pack("<IIII",
                mat.index,
                intern(mat.name),
                intern(mat.shader),
                len(mat.properties),
            )
            for prop in mat.properties:
                if prop.type == PROP_TYPE_FLOAT:
                    raw_val = struct.unpack("<I", struct.pack("<f", prop.value_f))[0]
                elif prop.type == PROP_TYPE_STRING:
                    raw_val = intern(prop.value_s)
                else:
                    raw_val = prop.value_i
                out += struct.pack("<III", intern(prop.name), prop.type, raw_val)

        # --- Vertices ---------------------------------------------------
        if self.version < 3:
            for v in self.vertices:
                out += struct.pack("<ffffffff",
                    v.x, v.y, v.z, v.nx, v.ny, v.nz, v.u, v.v)
        else:
            for v in self.vertices:
                out += struct.pack("<ffffffIffff",
                    v.x, v.y, v.z, v.nx, v.ny, v.nz,
                    v.color, 0.0, 0.0,
                    v.u, v.v,
                )

        # --- Polygons ---------------------------------------------------
        for p in self.polygons:
            out += struct.pack("<IIIiI", p.v1, p.v2, p.v3, p.material, p.flags)

        return bytes(out)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @property
    def bounds(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        """Return (min_xyz, max_xyz) bounding box."""
        if not self.vertices:
            return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
        xs = [v.x for v in self.vertices]
        ys = [v.y for v in self.vertices]
        zs = [v.z for v in self.vertices]
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    def __repr__(self) -> str:
        return (
            f"TerFile({self.name!r}, "
            f"mats={len(self.materials)}, "
            f"verts={len(self.vertices)}, "
            f"polys={len(self.polygons)})"
        )
