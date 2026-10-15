"""
tests/test_cave.py
------------------
Tests for the organic (SDF + marching cubes) cave geometry backend.
"""

import pytest

from generators.field.sdf import FieldGrid, sdf_sphere, carve
from generators.field.cave import CaveSpec, Chamber, Tunnel, build_cave
from generators.layout import LayoutGenerator
from generators.builder import ZoneBuilder
from core.pfs import PfsArchive
from core.ter import TerFile


class TestField:
    def test_solid_grid_init(self):
        grid = FieldGrid.solid(shape=(10, 10, 10), origin=(0, 0, 0), voxel=5.0)
        assert grid.density.shape == (10, 10, 10)
        assert float(grid.density.min()) > 0  # all solid

    def test_carve_creates_air(self):
        grid = FieldGrid.solid(shape=(20, 20, 20), origin=(-50, -50, -50), voxel=5.0)
        s = sdf_sphere(grid, center=(0, 0, 0), radius=30.0)
        carve(grid, s)
        # The centre voxel should now be air (negative)
        assert float(grid.density.min()) < 0


class TestCaveBuild:
    def test_single_chamber(self):
        spec = CaveSpec(chambers=[Chamber((0, 0, 0), 80)], voxel=14.0)
        ter = build_cave(spec, "ter_t", decimate=None)
        assert ter is not None
        assert len(ter.vertices) > 0
        assert len(ter.polygons) > 0

    def test_empty_spec_returns_none(self):
        spec = CaveSpec()
        assert build_cave(spec, "ter_empty") is None

    def test_chambers_and_tunnels(self):
        spec = CaveSpec(
            chambers=[Chamber((0, 0, 0), 80), Chamber((300, 0, 0), 70)],
            tunnels=[Tunnel((0, 0, 0), (300, 0, 0), 30)],
            voxel=16.0,
        )
        ter = build_cave(spec, "ter_t", decimate=None)
        assert ter is not None
        bmin, bmax = ter.bounds
        # The mesh should span roughly from first chamber to second
        assert bmax[0] - bmin[0] > 300

    def test_decimation_reduces_polys(self):
        spec = CaveSpec(chambers=[Chamber((0, 0, 0), 100)], voxel=10.0)
        full = build_cave(spec, "ter_full", decimate=None)
        reduced = build_cave(spec, "ter_red", decimate=0.4)
        assert len(reduced.polygons) < len(full.polygons)

    def test_organic_mesh_roundtrips(self):
        spec = CaveSpec(chambers=[Chamber((0, 0, 0), 80)], voxel=16.0)
        ter = build_cave(spec, "ter_t", decimate=0.5)
        ter2 = TerFile.from_bytes(ter.to_bytes(), "ter_t")
        assert len(ter2.vertices) == len(ter.vertices)
        assert len(ter2.polygons) == len(ter.polygons)


class TestCaveThemeRouting:
    def test_cave_theme_uses_organic_backend(self, tmp_path):
        gen = LayoutGenerator(theme="cave", seed=5)
        spec = gen.generate("cavetest", room_count=3)
        result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)

        # Organic cave meshes are dense — far more polys than a box zone
        assert result.polygon_count > 2000

        arc = PfsArchive.from_file(result.eqg_path)
        assert "ter_cavetest.ter" in [f.lower() for f in arc.list_files()]

    def test_dungeon_theme_uses_box_backend(self, tmp_path):
        gen = LayoutGenerator(theme="dungeon", seed=5)
        spec = gen.generate("boxtest", room_count=3)
        result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)

        # Box zones are sparse — a handful of quads per room/corridor
        assert result.polygon_count < 500
