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
