"""
tests/test_pfs.py
-----------------
Round-trip tests for the PFS archive reader/writer.

Tests that we can:
  1. Create an archive with known files
  2. Serialise it to bytes
  3. Deserialise it back
  4. Get identical file contents
"""

import pytest
from core.pfs import PfsArchive, _filename_crc32


class TestCrc32:
    def test_deterministic(self):
        assert _filename_crc32("gukbottom.ter") == _filename_crc32("gukbottom.ter")

    def test_case_insensitive(self):
        # EQ CRCs are computed on uppercase names
        assert _filename_crc32("MyZone.ter") == _filename_crc32("myzone.ter")


class TestPfsRoundTrip:
    def _make_archive(self) -> PfsArchive:
        arc = PfsArchive()
        arc.add("myzone.ter", b"fake ter data 1234567890")
        arc.add("myzone.zon", b"fake zon data abcdefghij")
        arc.add("stone_wall.dds", bytes(range(256)) * 4)
        return arc

    def test_roundtrip_filenames(self):
        arc = self._make_archive()
        data = arc.to_bytes()
        arc2 = PfsArchive.from_bytes(data)
        names = sorted(f.lower() for f in arc2.list_files())
        assert "myzone.ter" in names
        assert "myzone.zon" in names
        assert "stone_wall.dds" in names

    def test_roundtrip_data(self):
        arc = self._make_archive()
        data = arc.to_bytes()
        arc2 = PfsArchive.from_bytes(data)
        assert arc2.get("myzone.ter") == b"fake ter data 1234567890"
        assert arc2.get("myzone.zon") == b"fake zon data abcdefghij"

    def test_roundtrip_binary_data(self):
        arc = PfsArchive()
        payload = bytes(range(256)) * 64  # 16 KB of structured bytes
        arc.add("binary.ter", payload)
        arc2 = PfsArchive.from_bytes(arc.to_bytes())
        assert arc2.get("binary.ter") == payload

    def test_add_replace(self):
        arc = self._make_archive()
        arc.add("myzone.ter", b"replaced")
        assert arc.get("myzone.ter") == b"replaced"
        assert len(arc.files) == 3  # no duplicate

    def test_remove(self):
        arc = self._make_archive()
        assert arc.remove("myzone.zon") is True
        assert arc.get("myzone.zon") is None
        assert arc.remove("nonexistent.xyz") is False

    def test_get_by_extension(self):
        arc = self._make_archive()
        ter_files = arc.get_by_extension("ter")
        assert len(ter_files) == 1
        assert ter_files[0].name.endswith(".ter")

    def test_invalid_magic(self):
        with pytest.raises(ValueError, match="Not a PFS"):
            PfsArchive.from_bytes(b"NOTAPFSARCHIVE" + b"\x00" * 100)
