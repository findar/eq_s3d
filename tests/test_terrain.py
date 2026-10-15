"""
tests/test_terrain.py
---------------------
Tests for the heightfield terrain backend (outdoor theme).
"""

import math
import numpy as np
import pytest

from generators.field.terrain import TerrainSpec, build_terrain
from generators.layout import LayoutGenerator
from generators.builder import ZoneBuilder
from core.pfs import PfsArchive
from core.ter import TerFile


def _slopes(ter):
    verts = np.array([[v.x, v.y, v.z] for v in ter.vertices])
    out = []
    for p in ter.polygons:
        a, b, c = verts[p.v1], verts[p.v2], verts[p.v3]
        n = np.cross(b - a, c - a)
        ln = np.linalg.norm(n)
        if ln < 1e-6:
            continue
        n = n / ln
        out.append(math.degrees(math.acos(min(1.0, abs(n[2])))))
    return np.array(out)


class TestTerrainBuild:
    def test_produces_mesh(self):
        spec = TerrainSpec(width=1000, depth=1000, resolution=50, seed=1)
        ter = build_terrain(spec, "ter_t")
        assert ter is not None
        assert len(ter.vertices) > 0
        assert len(ter.polygons) > 0

    def test_grid_dimensions(self):
        spec = TerrainSpec(width=1000, depth=1000, resolution=50, seed=1)
        ter = build_terrain(spec, "ter_t")
        # (nx*ny) verts where nx = width/res + 1
        nx = int(1000 / 50) + 1
        ny = int(1000 / 50) + 1
        assert len(ter.vertices) == nx * ny
        # 2 triangles per quad
        assert len(ter.polygons) == (nx - 1) * (ny - 1) * 2

    def test_terrain_is_walkable(self):
        spec = TerrainSpec(width=2000, depth=2000, resolution=50, seed=4,
                           height_scale=360, noise_scale=800, max_walkable_grad=0.85)
        ter = build_terrain(spec, "ter_t")
        s = _slopes(ter)
        # The walkable cap should keep essentially all terrain navigable
        assert (s < 40).mean() > 0.98, f"max slope {s.max():.1f}"

    def test_has_height_variation(self):
        spec = TerrainSpec(width=2000, depth=2000, resolution=50, seed=4,
                           height_scale=360, noise_scale=800)
        ter = build_terrain(spec, "ter_t")
        zs = [v.z for v in ter.vertices]
        # Real hills: a meaningful vertical range
        assert max(zs) - min(zs) > 80

    def test_roundtrips(self):
        spec = TerrainSpec(width=1000, depth=1000, resolution=60, seed=2)
        ter = build_terrain(spec, "ter_t")
        ter2 = TerFile.from_bytes(ter.to_bytes(), "ter_t")
        assert len(ter2.vertices) == len(ter.vertices)
        assert len(ter2.polygons) == len(ter.polygons)

    def test_deterministic_seed(self):
        s1 = build_terrain(TerrainSpec(width=800, depth=800, resolution=50, seed=7), "a")
        s2 = build_terrain(TerrainSpec(width=800, depth=800, resolution=50, seed=7), "b")
        z1 = [v.z for v in s1.vertices]
        z2 = [v.z for v in s2.vertices]
        assert z1 == z2


class TestOutdoorThemeRouting:
    def test_outdoor_uses_terrain_backend(self, tmp_path):
        gen = LayoutGenerator(theme="outdoor", seed=3)
        spec = gen.generate("outzone", room_count=4)
        result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)

        arc = PfsArchive.from_file(result.eqg_path)
        ter = TerFile.from_bytes(arc.get("ter_outzone.ter"))

        # Terrain is a regular grid — a single flat-ish normal convention and
        # many near-horizontal triangles. Check it's walkable overall.
        s = _slopes(ter)
        assert (s < 45).mean() > 0.95
