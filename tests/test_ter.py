"""
tests/test_ter.py
-----------------
Round-trip tests for TER/MOD binary serialisation.
"""

import struct
import pytest
from core.ter import (
    TerFile, Material, MaterialProperty, Vertex, Polygon,
    MAGIC_TERRAIN, MAGIC_MODEL, SHADER_OPAQUE,
    PROP_TYPE_FLOAT, PROP_TYPE_STRING, FLAG_PASSABLE,
)


def _make_simple_ter() -> TerFile:
    """Create a minimal valid TerFile (one quad = two triangles)."""
    ter = TerFile(name="test", magic=MAGIC_TERRAIN, version=2)

    mat = Material(index=0, name="stone_floor", shader=SHADER_OPAQUE)
    mat.add_diffuse("stone_floor_01.dds")
    mat.add_shininess(1.0)
    ter.materials.append(mat)

    # Four corners of a 100×100 floor quad
    ter.vertices = [
        Vertex(x=  0, y=  0, z=0, nx=0, ny=0, nz=1, u=0.0, v=0.0),
        Vertex(x=100, y=  0, z=0, nx=0, ny=0, nz=1, u=4.0, v=0.0),
        Vertex(x=100, y=100, z=0, nx=0, ny=0, nz=1, u=4.0, v=4.0),
        Vertex(x=  0, y=100, z=0, nx=0, ny=0, nz=1, u=0.0, v=4.0),
    ]

    ter.polygons = [
        Polygon(v1=0, v2=1, v3=2, material=0, flags=0),
        Polygon(v1=0, v2=2, v3=3, material=0, flags=0),
    ]
    return ter


class TestTerRoundTrip:
    def test_roundtrip_counts(self):
        ter = _make_simple_ter()
        data = ter.to_bytes()
        ter2 = TerFile.from_bytes(data, name="test")
        assert len(ter2.materials) == 1
        assert len(ter2.vertices)  == 4
        assert len(ter2.polygons)  == 2

    def test_roundtrip_vertex_positions(self):
        ter = _make_simple_ter()
        ter2 = TerFile.from_bytes(ter.to_bytes(), name="test")
        for orig, parsed in zip(ter.vertices, ter2.vertices):
            assert abs(orig.x - parsed.x) < 0.001
            assert abs(orig.y - parsed.y) < 0.001
            assert abs(orig.z - parsed.z) < 0.001

    def test_roundtrip_uvs(self):
        ter = _make_simple_ter()
        ter2 = TerFile.from_bytes(ter.to_bytes(), name="test")
        for orig, parsed in zip(ter.vertices, ter2.vertices):
            assert abs(orig.u - parsed.u) < 0.001
            assert abs(orig.v - parsed.v) < 0.001

    def test_roundtrip_material_name(self):
        ter = _make_simple_ter()
        ter2 = TerFile.from_bytes(ter.to_bytes(), name="test")
        assert ter2.materials[0].name == "stone_floor"
        assert ter2.materials[0].shader == SHADER_OPAQUE

    def test_roundtrip_diffuse_property(self):
        ter = _make_simple_ter()
        ter2 = TerFile.from_bytes(ter.to_bytes(), name="test")
        props = ter2.materials[0].properties
        diffuse = next((p for p in props if "Diffuse" in p.name), None)
        assert diffuse is not None
        assert diffuse.value_s == "stone_floor_01.dds"

    def test_roundtrip_polygon_flags(self):
        ter = _make_simple_ter()
        ter.polygons[1].flags = FLAG_PASSABLE
        ter2 = TerFile.from_bytes(ter.to_bytes(), name="test")
        assert ter2.polygons[1].flags == FLAG_PASSABLE

    def test_bounds(self):
        ter = _make_simple_ter()
        bmin, bmax = ter.bounds
        assert bmin == (0.0, 0.0, 0.0)
        assert bmax == (100.0, 100.0, 0.0)

    def test_multiple_materials(self):
        ter = _make_simple_ter()
        mat2 = Material(index=1, name="lava_floor", shader=SHADER_OPAQUE)
        mat2.add_diffuse("lava_01.dds")
        ter.materials.append(mat2)
        ter.polygons[1].material = 1
        ter2 = TerFile.from_bytes(ter.to_bytes(), name="test")
        assert len(ter2.materials) == 2
        assert ter2.polygons[1].material == 1

    def test_version3_vertex(self):
        ter = _make_simple_ter()
        ter.version = 3
        for v in ter.vertices:
            v.color = 0xFFAA8844
        ter2 = TerFile.from_bytes(ter.to_bytes(), name="test")
        assert ter2.version == 3
        assert ter2.vertices[0].color == 0xFFAA8844

    def test_magic_preserved(self):
        ter = _make_simple_ter()
        ter2 = TerFile.from_bytes(ter.to_bytes(), name="test")
        assert ter2.magic == MAGIC_TERRAIN
