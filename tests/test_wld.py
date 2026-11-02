"""
tests/test_wld.py
-----------------
Tests for the WLD reader (Classic-PoP .s3d zone geometry).

These require a real RoF2 install. They are skipped if the install (and a
known classic zone) isn't present, so the suite stays green on CI / machines
without the game.
"""

import os
from pathlib import Path

import pytest

from core.pfs import PfsArchive
from core.wld import load_wld, WLD_MAGIC, VERSION_OLD

EQ = Path(os.environ.get("EQ_PATH", r"F:\everquest_rof2"))
_GFAYDARK = EQ / "gfaydark.s3d"

requires_eq = pytest.mark.skipif(
    not _GFAYDARK.exists(),
    reason="RoF2 install (gfaydark.s3d) not available",
)


@requires_eq
class TestWldReader:
    def _load(self):
        arc = PfsArchive.from_file(_GFAYDARK)
        return load_wld(arc.get("gfaydark.wld"))

    def test_opens_s3d_container(self):
        arc = PfsArchive.from_file(_GFAYDARK)
        assert "gfaydark.wld" in [f.lower() for f in arc.list_files()]

    def test_detects_old_format(self):
        wld = self._load()
        assert wld.is_old_format is True

    def test_extracts_geometry(self):
        wld = self._load()
        assert len(wld.meshes) > 100
        assert wld.total_vertices > 10000
        assert wld.total_polygons > 10000

    def test_geometry_bounds_sane(self):
        wld = self._load()
        tris = wld.all_triangles()
        assert len(tris) > 0
        xs = [p[0] for t in tris for p in t]
        ys = [p[1] for t in tris for p in t]
        # Greater Faydark spans a few thousand units each way
        assert max(xs) - min(xs) > 1000
        assert max(ys) - min(ys) > 1000

    def test_extracts_texture_names(self):
        wld = self._load()
        assert len(wld.texture_names) > 10
        # Names are decoded bitmap filenames
        assert all(isinstance(n, str) for n in wld.texture_names)
        assert any(n.lower().endswith(".bmp") for n in wld.texture_names)

    def test_triangles_index_valid_vertices(self):
        wld = self._load()
        for m in wld.meshes[:50]:
            for v1, v2, v3, _flag in m.polygons:
                assert 0 <= v1 < len(m.vertices)
                assert 0 <= v2 < len(m.vertices)
                assert 0 <= v3 < len(m.vertices)


class TestWldErrors:
    def test_rejects_non_wld(self):
        with pytest.raises(ValueError, match="Not a WLD"):
            load_wld(b"NOTAWLD\x00" + b"\x00" * 64)


# ---------------------------------------------------------------------------
# Interesting textures task 1: UVs and polygon textures (Req 1, Y1)
# ---------------------------------------------------------------------------

import math
import statistics

# Per-zone median world units per texture repeat on walls, from the step 4
# design's research table (measured with a scratch probe before this reader
# kept UVs).
WALL_REPEAT = {"befallen": 14.0, "unrest": 14.0, "najena": 14.0,
               "mistmoore": 12.2, "qeynos2": 14.0}


def wall_repeat_median(wld) -> float:
    """Median world units per UV unit along the edges of wall triangles
    (|nz| < 0.3), skipping edges with no UV or world length."""
    vals = []
    for m in wld.meshes:
        if not m.uvs:
            continue
        for a, b, c, _flag in m.polygons:
            pa, pb, pc = m.vertices[a], m.vertices[b], m.vertices[c]
            n = [(pb[1] - pa[1]) * (pc[2] - pa[2]) - (pb[2] - pa[2]) * (pc[1] - pa[1]),
                 (pb[2] - pa[2]) * (pc[0] - pa[0]) - (pb[0] - pa[0]) * (pc[2] - pa[2]),
                 (pb[0] - pa[0]) * (pc[1] - pa[1]) - (pb[1] - pa[1]) * (pc[0] - pa[0])]
            length = math.sqrt(sum(x * x for x in n))
            if length == 0 or abs(n[2] / length) >= 0.3:
                continue
            for i, j in ((a, b), (b, c), (c, a)):
                dw = math.dist(m.vertices[i], m.vertices[j])
                du = math.dist(m.uvs[i], m.uvs[j])
                if du > 1e-4 and dw > 0.5:
                    vals.append(dw / du)
    return statistics.median(vals)


@pytest.mark.parametrize("zone", sorted(WALL_REPEAT))
def test_y1_uvs_measure_classic_texel_density(zone):
    path = EQ / f"{zone}.s3d"
    if not path.exists():
        pytest.skip(f"RoF2 install ({zone}.s3d) not available")
    wld = load_wld(PfsArchive.from_file(path).get(f"{zone}.wld"))
    assert wld.meshes and all(len(m.uvs) == len(m.vertices) for m in wld.meshes)
    assert all(len(m.polygon_textures) == len(m.polygons) for m in wld.meshes)
    assert wall_repeat_median(wld) == pytest.approx(WALL_REPEAT[zone], abs=0.5)


@requires_eq
def test_polygon_textures_index_the_zone_textures():
    wld = load_wld(PfsArchive.from_file(_GFAYDARK).get("gfaydark.wld"))
    used = {t for m in wld.meshes for t in m.polygon_textures}
    assert used and min(used) >= 0
    assert all(len(m.polygon_textures) == len(m.polygons) for m in wld.meshes)
    # Some outdoor meshes carry no texcoords at all; a mesh's UVs are either
    # complete or absent, never partial.
    assert all(len(m.uvs) in (0, len(m.vertices)) for m in wld.meshes)
    assert sum(1 for m in wld.meshes if m.uvs) > len(wld.meshes) // 2
