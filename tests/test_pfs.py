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

import struct

import pytest
from core.pfs import PfsArchive, RawEntry, read_directory, _filename_crc32


class TestCrc32:
    def test_deterministic(self):
        assert _filename_crc32("gukbottom.ter") == _filename_crc32("gukbottom.ter")

    def test_case_sensitive(self):
        # EQ CRC is case-sensitive (no uppercase conversion) — filenames are stored as-is
        # Different case produces different CRC
        assert _filename_crc32("MyZone.ter") != _filename_crc32("myzone.ter")

    def test_known_value(self):
        # Verified against real broodlands.eqg directory entry
        assert _filename_crc32("ab_caveblack_c.dds") == 0x029F137F


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


class TestReadDirectory:
    """
    Tests for the non-raising directory reader (Req 9.3). read_directory must be
    TOTAL: on a valid archive it recovers the entries and reports no errors; on
    any corrupt input it returns gracefully with recorded archive_errors and
    NEVER raises.
    """

    def _make_archive_bytes(self) -> bytes:
        arc = PfsArchive()
        arc.add("myzone.ter", b"fake ter data 1234567890")
        arc.add("myzone.zon", b"fake zon data abcdefghij")
        arc.add("stone_wall.dds", bytes(range(256)) * 4)
        return arc.to_bytes()

    def test_valid_archive_recovers_entries_no_errors(self):
        data = self._make_archive_bytes()
        entries, archive_errors = read_directory(data)

        assert archive_errors == []
        # Every recovered entry decoded cleanly.
        assert all(e.error is None for e in entries), [e.error for e in entries]

        # Named entries match the archive (the name-block sentinel is nameless).
        named = {e.name: e for e in entries if e.name is not None}
        assert set(named) == {"myzone.ter", "myzone.zon", "stone_wall.dds"}

        # Payloads and sizes round-trip.
        assert named["myzone.ter"].data == b"fake ter data 1234567890"
        assert named["myzone.zon"].data == b"fake zon data abcdefghij"
        assert named["stone_wall.dds"].data == bytes(range(256)) * 4
        for e in named.values():
            assert e.size == len(e.data)
            assert isinstance(e, RawEntry)

        # CRCs key the recovered names.
        assert named["myzone.ter"].crc == _filename_crc32("myzone.ter")

    def test_valid_archive_matches_from_bytes(self):
        """read_directory's named payloads agree with the trusting from_bytes path."""
        data = self._make_archive_bytes()
        arc = PfsArchive.from_bytes(data)
        entries, _ = read_directory(data)

        by_name = {e.name: e.data for e in entries if e.name is not None}
        for pf in arc.files:
            assert by_name.get(pf.name) == pf.data

    @pytest.mark.parametrize(
        "label, payload",
        [
            ("empty", b""),
            ("too_short", b"\x00\x08\x00\x00PFS"),  # < 12 bytes
            ("zeroed_header", b"\x00" * 64),  # bad magic
            ("garbage", bytes(range(256)) * 4),
            ("bad_magic", struct.pack("<I", 12) + b"NOPE" + struct.pack("<I", 0x00020000)),
            (
                "bad_version",
                struct.pack("<I", 12) + b"PFS " + struct.pack("<I", 0xDEADBEEF),
            ),
            (
                "dir_offset_oob",
                struct.pack("<I", 0xFFFFFF) + b"PFS " + struct.pack("<I", 0x00020000),
            ),
            (
                "impossible_count",
                # valid header, directory right after it claiming a huge count
                struct.pack("<I", 12) + b"PFS " + struct.pack("<I", 0x00020000)
                + struct.pack("<I", 0x7FFFFFFF),
            ),
        ],
    )
    def test_corrupt_inputs_never_raise(self, label, payload):
        # Must not raise for any malformed input.
        entries, archive_errors = read_directory(payload)
        assert isinstance(entries, list)
        assert isinstance(archive_errors, list)
        # Every corruption above prevents a clean read, so an error is recorded.
        assert archive_errors, f"{label}: expected a recorded archive error"

    def test_truncated_valid_archive_records_errors(self):
        """Chop a real archive mid-stream: entries still return, faults recorded."""
        data = self._make_archive_bytes()
        truncated = data[: len(data) // 2]
        entries, archive_errors = read_directory(truncated)
        # The function returns (never raises); the damage is surfaced as either
        # an archive-level error or a per-entry error.
        assert isinstance(entries, list)
        assert archive_errors or any(e.error is not None for e in entries)

    def test_corrupt_entry_payload_is_recorded_not_raised(self):
        """Flip bytes inside a file's deflate stream; that entry carries an error."""
        data = bytearray(self._make_archive_bytes())
        # Corrupt a byte well past the 12-byte header (inside the first chunk).
        data[40] ^= 0xFF
        entries, archive_errors = read_directory(bytes(data))
        # Still returns; at least something is flagged.
        assert isinstance(entries, list)
        assert archive_errors or any(e.error is not None for e in entries)
