"""
core/zon.py
-----------
Reader and writer for EverQuest EQG zone placement files (.zon).

The ZON file defines what models exist in a zone and where they are placed,
along with region volumes and point lights.

Binary layout (little-endian, packed):

  zon_header:
    char[4]   magic          'EQGZ'
    uint32    version        1 or 2
    uint32    list_length    byte length of string table
    uint32    model_count
    uint32    object_count
    uint32    region_count
    uint32    light_count

  [string table — list_length bytes]
    Null-terminated strings.  All loc/name fields are offsets into this table.

  models[model_count]:
    uint32  name_offset      → filename of the model (e.g. "rock01.mod")

  objects[object_count]:
    int32   id               index into models list
    uint32  loc              name offset in string table (instance name)
    float   x, y, z          position
    float   rx, ry, rz       rotation in EQ heading units (0–512 = 360°)
    float   scale
    [version > 1: uint32 unk_count; unk_count × uint32 unknown data]

  regions[region_count]:
    uint32  loc              name offset (prefix encodes type — see below)
    float   center_x/y/z    center of the region AABB
    float   rotation         EQ heading units
    uint32  flag_unk020
    uint32  flag_unk024
    float   extend_x/y/z    half-extents of the AABB

  lights[light_count]:
    uint32  loc              name offset
    float   x, y, z
    float   r, g, b          0.0–1.0
    float   radius

Region name prefixes (determines client behaviour):
    AWT_   water
    ALV_   lava
    APK_   PvP
    ATP_   zoneline
    ASL_   ice
    APV_   generic volume

Reference: EQEmu/zone-utilities src/common/eqg_structs.h + eqg_loader.cpp
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ZON_MAGIC   = b"EQGZ"
ZON_VERSION = 2

# Region type name prefixes
REGION_WATER    = "AWT"
REGION_LAVA     = "ALV"
REGION_PVP      = "APK"
REGION_ZONELINE = "ATP"
REGION_ICE      = "ASL"
REGION_GENERIC  = "APV"

_HEADING_TO_DEG = 360.0 / 512.0
_DEG_TO_HEADING = 512.0 / 360.0

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ZonObject:
    """A placed instance of a model in the zone."""
    name: str               # instance name (arbitrary, must be unique)
    model_id: int           # index into ZonFile.models
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    rx: float = 0.0         # rotation in degrees (converted on write)
    ry: float = 0.0
    rz: float = 0.0
    scale: float = 1.0


@dataclass
class ZonRegion:
    """
    An axis-aligned bounding box that marks a special game region.

    *name* should begin with one of the REGION_* prefix constants followed
    by an underscore and a descriptive label, e.g. "AWT_entrance_pool".
    """
    name: str
    center_x: float = 0.0
    center_y: float = 0.0
    center_z: float = 0.0
    rotation: float = 0.0   # degrees (converted on write)
    extend_x: float = 10.0  # half-width
    extend_y: float = 10.0  # half-depth
    extend_z: float = 5.0   # half-height

    @classmethod
    def water(cls, name: str, **kwargs) -> "ZonRegion":
        return cls(name=f"AWT_{name}", **kwargs)

    @classmethod
    def lava(cls, name: str, **kwargs) -> "ZonRegion":
        return cls(name=f"ALV_{name}", **kwargs)

    @classmethod
    def zoneline(cls, name: str, **kwargs) -> "ZonRegion":
        return cls(name=f"ATP_{name}", **kwargs)


@dataclass
class ZonLight:
    """A point light source in the zone."""
    name: str
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    r: float = 1.0    # 0.0–1.0
    g: float = 0.8
    b: float = 0.5
    radius: float = 50.0


@dataclass
class ZonFile:
    """
    Complete in-memory representation of a .zon file.

    Usage::

        zon = ZonFile()
        zon.models.append("myrock.mod")
        zon.objects.append(ZonObject("rock01", model_id=0, x=100, y=50, z=0))
        zon.regions.append(ZonRegion.water("pool", center_x=50, center_y=50, center_z=2))
        zon.lights.append(ZonLight("torch01", x=0, y=0, z=30, r=1.0, g=0.6, b=0.2, radius=40))
        data = zon.to_bytes()
    """

    models: List[str]         = field(default_factory=list)
    objects: List[ZonObject]  = field(default_factory=list)
    regions: List[ZonRegion]  = field(default_factory=list)
    lights: List[ZonLight]    = field(default_factory=list)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @classmethod
    def from_bytes(cls, data: bytes) -> "ZonFile":
        """Parse a ZON file from raw bytes."""
        magic = data[0:4]
        if magic != ZON_MAGIC:
            raise ValueError(f"Not an EQGZ file (magic={magic!r})")

        (
            version,
            list_length,
            model_count,
            object_count,
            region_count,
            light_count,
        ) = struct.unpack_from("<IIIIII", data, 4)

        pos = 28  # after 4-byte magic + 6 × uint32

        list_start = pos
        pos += list_length

        def str_at(offset: int) -> str:
            end = data.index(b"\x00", list_start + offset)
            return data[list_start + offset : end].decode("ascii", errors="replace")

        zon = cls()

        # Models
        for _ in range(model_count):
            (name_off,) = struct.unpack_from("<I", data, pos)
            pos += 4
            zon.models.append(str_at(name_off))

        # Objects
        for _ in range(object_count):
            model_id, loc, x, y, z, rx, ry, rz, scale = struct.unpack_from(
                "<iIfffffff", data, pos
            )
            pos += 36
            obj = ZonObject(
                name=str_at(loc),
                model_id=model_id,
                x=x, y=y, z=z,
                rx=rx * _HEADING_TO_DEG,
                ry=ry * _HEADING_TO_DEG,
                rz=rz * _HEADING_TO_DEG,
                scale=scale,
            )
            if version > 1:
                (unk_count,) = struct.unpack_from("<I", data, pos)
                pos += 4
                pos += unk_count * 4
            zon.objects.append(obj)

        # Regions
        for _ in range(region_count):
            loc, cx, cy, cz, rot, fu020, fu024, ex, ey, ez = struct.unpack_from(
                "<IfffIIIfff", data, pos
            )
            pos += 40
            # Note: rot stored as EQ heading (0-512), convert to degrees
            zon.regions.append(ZonRegion(
                name=str_at(loc),
                center_x=cx, center_y=cy, center_z=cz,
                rotation=rot / 512.0 * 360.0,
                extend_x=ex, extend_y=ey, extend_z=ez,
            ))

        # Lights
        for _ in range(light_count):
            loc, x, y, z, r, g, b, radius = struct.unpack_from(
                "<Ifffffff", data, pos
            )
            pos += 32
            zon.lights.append(ZonLight(
                name=str_at(loc),
                x=x, y=y, z=z,
                r=r, g=g, b=b,
                radius=radius,
            ))

        return zon

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def to_bytes(self) -> bytes:
        """Serialise to bytes ready to embed in a PFS archive."""
        string_table = bytearray()
        _offsets: dict[str, int] = {}

        def intern(s: str) -> int:
            if s not in _offsets:
                _offsets[s] = len(string_table)
                string_table.extend(s.encode("ascii") + b"\x00")
            return _offsets[s]

        # Pre-intern all strings
        for m in self.models:
            intern(m)
        for obj in self.objects:
            intern(obj.name)
        for reg in self.regions:
            intern(reg.name)
        for lt in self.lights:
            intern(lt.name)

        list_length = len(string_table)

        out = bytearray()

        # Header
        out += ZON_MAGIC
        out += struct.pack("<IIIIII",
            ZON_VERSION,
            list_length,
            len(self.models),
            len(self.objects),
            len(self.regions),
            len(self.lights),
        )

        # String table
        out += bytes(string_table)

        # Models
        for m in self.models:
            out += struct.pack("<I", intern(m))

        # Objects
        for obj in self.objects:
            out += struct.pack("<iIfffffff",
                obj.model_id,
                intern(obj.name),
                obj.x, obj.y, obj.z,
                obj.rx * _DEG_TO_HEADING,
                obj.ry * _DEG_TO_HEADING,
                obj.rz * _DEG_TO_HEADING,
                obj.scale,
            )
            # version 2: unk_count = 0
            out += struct.pack("<I", 0)

        # Regions
        for reg in self.regions:
            out += struct.pack("<IfffIIIfff",
                intern(reg.name),
                reg.center_x, reg.center_y, reg.center_z,
                int(reg.rotation * _DEG_TO_HEADING),
                0, 0,   # flag_unk020, flag_unk024
                reg.extend_x, reg.extend_y, reg.extend_z,
            )

        # Lights
        for lt in self.lights:
            out += struct.pack("<Ifffffff",
                intern(lt.name),
                lt.x, lt.y, lt.z,
                lt.r, lt.g, lt.b,
                lt.radius,
            )

        return bytes(out)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def add_model(self, filename: str) -> int:
        """Register a model filename and return its index."""
        if filename not in self.models:
            self.models.append(filename)
        return self.models.index(filename)

    def place(self,
              name: str,
              model_file: str,
              x: float, y: float, z: float,
              rz: float = 0.0,
              scale: float = 1.0) -> ZonObject:
        """Convenience: register model and add a placed instance."""
        mid = self.add_model(model_file)
        obj = ZonObject(name=name, model_id=mid, x=x, y=y, z=z, rz=rz, scale=scale)
        self.objects.append(obj)
        return obj

    def __repr__(self) -> str:
        return (
            f"ZonFile(models={len(self.models)}, "
            f"objects={len(self.objects)}, "
            f"regions={len(self.regions)}, "
            f"lights={len(self.lights)})"
        )
