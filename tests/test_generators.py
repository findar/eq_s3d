"""
tests/test_generators.py
------------------------
Tests for the Phase 2 procedural generators and the full build pipeline.
"""

import pytest
from pathlib import Path

from generators.zone_spec import ZoneSpec, RoomSpec, CorridorSpec, LightSpec, RegionSpec
from generators.geometry import build_mesh, MeshBuilder
from generators.layout import LayoutGenerator
from generators.builder import ZoneBuilder
from core.pfs import PfsArchive
from core.ter import TerFile
from core.zon import ZonFile


class TestZoneSpec:
    def test_roundtrip(self, tmp_path):
        spec = ZoneSpec(name="test", theme="dungeon")
        spec.add_material("wall", "wall.dds", color=(100, 90, 80))
        spec.rooms.append(RoomSpec("r0", 0, 0, width=200, depth=200, height=60))
        spec.lights.append(LightSpec("l0", 0, 0, 40))

        path = tmp_path / "test.json"
        spec.save(path)
        loaded = ZoneSpec.load(path)

        assert loaded.name == "test"
        assert loaded.theme == "dungeon"
        assert len(loaded.rooms) == 1
        assert len(loaded.lights) == 1
        assert loaded.materials["wall"].color == (100, 90, 80)

    def test_room_bounds(self):
        room = RoomSpec("r", center_x=100, center_y=50, floor_z=0,
                        width=200, depth=100, height=60)
        bmin, bmax = room.bounds
        assert bmin == (0, 0, 0)
        assert bmax == (200, 100, 60)


class TestGeometry:
    def test_single_room_mesh(self):
        spec = ZoneSpec(name="t")
        spec.add_material("floor", "floor.dds")
        spec.add_material("wall", "wall.dds")
        spec.add_material("ceiling", "ceiling.dds")
        spec.rooms.append(RoomSpec("r0", 0, 0, width=200, depth=200, height=60))

        mb = build_mesh(spec)
        # A closed box = 6 faces = 12 triangles = 24 vertices
        assert len(mb.polygons) == 12
        assert len(mb.vertices) == 24
        assert len(mb.materials) == 3

    def test_open_walls_reduce_faces(self):
        spec = ZoneSpec(name="t")
        spec.add_material("floor", "floor.dds")
        spec.add_material("wall", "wall.dds")
        spec.add_material("ceiling", "ceiling.dds")
        room = RoomSpec("r0", 0, 0, width=200, depth=200, height=60)
        room.open_walls = ["N", "S"]  # omit 2 walls
        spec.rooms.append(room)

        mb = build_mesh(spec)
        # 6 faces - 2 omitted = 4 faces = 8 triangles
        assert len(mb.polygons) == 8

    def test_ter_emission(self):
        spec = ZoneSpec(name="t")
        spec.add_material("floor", "floor.dds")
        spec.add_material("wall", "wall.dds")
        spec.add_material("ceiling", "ceiling.dds")
        spec.rooms.append(RoomSpec("r0", 0, 0, width=200, depth=200, height=60))

        ter = build_mesh(spec).to_ter("ter_t", version=2)
        assert isinstance(ter, TerFile)
        # TER should round-trip through binary
        ter2 = TerFile.from_bytes(ter.to_bytes(), "ter_t")
        assert len(ter2.vertices) == len(ter.vertices)
        assert len(ter2.polygons) == len(ter.polygons)


class TestLayout:
    def test_deterministic_seed(self):
        gen_a = LayoutGenerator(theme="dungeon", seed=123)
        gen_b = LayoutGenerator(theme="dungeon", seed=123)
        spec_a = gen_a.generate("z", room_count=4)
        spec_b = gen_b.generate("z", room_count=4)
        # Same seed → same room centres
        for ra, rb in zip(spec_a.rooms, spec_b.rooms):
            assert ra.center_x == rb.center_x
            assert ra.center_y == rb.center_y

    def test_room_count(self):
        gen = LayoutGenerator(theme="dungeon", seed=1)
        spec = gen.generate("z", room_count=6)
        assert len(spec.rooms) == 6
        # N rooms connected by N-1 corridors
        assert len(spec.corridors) == 5

    def test_lights_generated(self):
        gen = LayoutGenerator(theme="dungeon", seed=1)
        spec = gen.generate("z", room_count=3, add_lights=True)
        assert len(spec.lights) == 3

    def test_connected_rooms_open_walls(self):
        gen = LayoutGenerator(theme="dungeon", seed=1)
        spec = gen.generate("z", room_count=3)
        # Connected rooms should have at least one open wall each
        assert any(r.open_walls for r in spec.rooms)


class TestBuilder:
    def test_full_build(self, tmp_path):
        gen = LayoutGenerator(theme="dungeon", seed=42)
        spec = gen.generate("buildtest", room_count=4)
        result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)

        assert result.eqg_path.exists()
        assert result.vertex_count > 0
        assert result.polygon_count > 0

    def test_build_produces_valid_eqg(self, tmp_path):
        gen = LayoutGenerator(theme="dungeon", seed=42)
        spec = gen.generate("validtest", room_count=3)
        result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)

        # Read the generated EQG back
        arc = PfsArchive.from_file(result.eqg_path)
        files = arc.list_files()

        assert "ter_validtest.ter" in [f.lower() for f in files]
        assert "validtest.zon" in [f.lower() for f in files]

        # TER parses
        ter_data = arc.get("ter_validtest.ter")
        ter = TerFile.from_bytes(ter_data)
        assert len(ter.vertices) > 0

        # ZON parses and references the terrain as model[0]
        zon_data = arc.get("validtest.zon")
        zon = ZonFile.from_bytes(zon_data)
        assert len(zon.models) >= 1
        assert "TER_VALIDTEST" in zon.models[0].upper()

    def test_zon_has_lights(self, tmp_path):
        gen = LayoutGenerator(theme="dungeon", seed=42)
        spec = gen.generate("lighttest", room_count=3)
        result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)

        arc = PfsArchive.from_file(result.eqg_path)
        zon = ZonFile.from_bytes(arc.get("lighttest.zon"))
        assert len(zon.lights) == 3


class TestElevation:
    def test_corridor_floor_z_backcompat(self):
        # The floor_z property sets both from_z and to_z
        c = CorridorSpec("c", 0, 0, 100, 0)
        c.floor_z = 50.0
        assert c.from_z == 50.0
        assert c.to_z == 50.0
        assert c.floor_z == 50.0

    def test_ramp_corridor_spans_heights(self):
        spec = ZoneSpec(name="t")
        spec.add_material("floor", "floor.dds")
        spec.add_material("wall", "wall.dds")
        spec.add_material("ceiling", "ceiling.dds")
        # A corridor that ramps from z=0 to z=100 along X
        spec.corridors.append(CorridorSpec(
            "ramp", from_x=0, from_y=0, to_x=400, to_y=0,
            from_z=0.0, to_z=100.0, width=50, height=50,
        ))
        mb = build_mesh(spec)
        ter = mb.to_ter("t")
        zs = [v.z for v in ter.vertices]
        # Floor should span from 0 up to 100; ceiling adds height on top
        assert min(zs) == 0.0
        assert max(zs) >= 100.0

    def test_stepped_corridor_more_geometry(self):
        spec = ZoneSpec(name="t")
        spec.add_material("floor", "floor.dds")
        spec.add_material("wall", "wall.dds")
        spec.add_material("ceiling", "ceiling.dds")
        spec.corridors.append(CorridorSpec(
            "stairs", from_x=0, from_y=0, to_x=400, to_y=0,
            from_z=0.0, to_z=100.0, width=50, height=50, steps=5,
        ))
        mb = build_mesh(spec)
        # Stepped corridors produce more polygons than a flat tube (treads + risers)
        assert len(mb.polygons) > 8

    def test_elevation_layout_varies_z(self):
        gen = LayoutGenerator(theme="dungeon", seed=7)
        spec = gen.generate("ev", room_count=8, elevation=True)
        floor_zs = {r.floor_z for r in spec.rooms}
        # With elevation on and 8 rooms, we expect multiple distinct heights
        assert len(floor_zs) > 1

    def test_elevation_off_keeps_flat(self):
        gen = LayoutGenerator(theme="dungeon", seed=7)
        spec = gen.generate("flat", room_count=8, elevation=False)
        floor_zs = {r.floor_z for r in spec.rooms}
        assert floor_zs == {0.0}

    def test_elevated_zone_builds(self, tmp_path):
        gen = LayoutGenerator(theme="dungeon", seed=7)
        spec = gen.generate("evbuild", room_count=6, elevation=True)
        result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)
        assert result.eqg_path.exists()

        # Verify Z span is non-trivial
        arc = PfsArchive.from_file(result.eqg_path)
        ter = TerFile.from_bytes(arc.get("ter_evbuild.ter"))
        zs = [v.z for v in ter.vertices]
        assert max(zs) - min(zs) > 50  # has real verticality
