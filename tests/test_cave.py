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


class TestWalkableFloor:
    def _floor_walkable_pct(self, ter, band_frac=0.3, up_thresh=0.5):
        import numpy as np, math
        verts = np.array([[v.x, v.y, v.z] for v in ter.vertices])
        zmin = verts[:, 2].min(); zmax = verts[:, 2].max()
        band = zmin + (zmax - zmin) * band_frac
        slopes = []
        for p in ter.polygons:
            a, b, c = verts[p.v1], verts[p.v2], verts[p.v3]
            if (a[2] + b[2] + c[2]) / 3 > band:
                continue
            n = np.cross(b - a, c - a)
            ln = np.linalg.norm(n)
            if ln < 1e-6:
                continue
            n = n / ln
            if n[2] > up_thresh:
                slopes.append(math.degrees(math.acos(min(1.0, abs(n[2])))))
        if not slopes:
            return 0.0, zmin
        s = np.array(slopes)
        return 100.0 * (s < 30).mean(), zmin

    def test_dome_floor_is_mostly_walkable(self):
        spec = CaveSpec(
            chambers=[Chamber((0, 0, 0), 110, floor_z=-45)],
            voxel=10.0, noise_amplitude=24, noise_scale=120, noise_seed=3,
        )
        ter = build_cave(spec, "ter_walk", decimate=None)
        walkable, zmin = self._floor_walkable_pct(ter)
        # A navigable cave floor: majority of floor triangles under 30deg slope
        assert walkable > 55, f"only {walkable:.0f}% walkable"

    def test_floor_does_not_dip_far_below_plane(self):
        import numpy as np
        floor_z = -45
        spec = CaveSpec(
            chambers=[Chamber((0, 0, 0), 110, floor_z=floor_z)],
            voxel=10.0, noise_amplitude=24, noise_seed=3,
        )
        ter = build_cave(spec, "ter_walk", decimate=None)
        verts = np.array([[v.x, v.y, v.z] for v in ter.vertices])
        # The floor should not dig far below the target plane (one-sided clamp).
        # Allow a small margin for voxel resolution.
        assert verts[:, 2].min() >= floor_z - 15


class TestFeatures:
    def test_features_add_geometry(self):
        from generators.field.features import FeatureParams
        base = CaveSpec(chambers=[Chamber((0, 0, 0), 120, floor_z=-50)],
                        voxel=10.0, noise_seed=5)
        plain = build_cave(base, "ter_plain", decimate=None)

        feats = FeatureParams(seed=5, stalactite_count=14,
                              stalagmite_count=9, pillar_count=2)
        with_feats = build_cave(base, "ter_feat", decimate=None, features=feats)

        # Features grow extra solid into the field → more surface geometry
        assert len(with_feats.polygons) > len(plain.polygons)

    def test_cave_theme_includes_features(self, tmp_path):
        gen = LayoutGenerator(theme="cave", seed=9)
        spec = gen.generate("featzone", room_count=3)
        result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)
        # Dense organic + features
        assert result.polygon_count > 3000


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
