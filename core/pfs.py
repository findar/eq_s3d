"""
core/pfs.py
-----------
PFS archive reader and writer.

PFS is EverQuest's custom container format used for .eqg, .s3d, .pak, and .pfs
archives. Files inside are individually zlib-deflated in 8192-byte blocks.

Binary layout (little-endian):
  [uint32]   dirOffset      — byte offset to the directory block
  [4 bytes]  'PFS '         — magic
  [uint32]   0x00020000     — version
  [...zlib-deflated file chunks...]
  [uint32]   fileCount
  [per entry: uint32 crc32 | uint32 offset | uint32 size]
  [5 bytes]  'STEVE'        — footer magic
  [uint32]   Unix timestamp

Filenames are stored in a separate deflated block (the last "file" in the
directory), keyed by CRC32 of the lowercased filename.

Reference: xackery/quail pfs/read.go + write.go (archived Oct 2025)
           EQEmu/zone-utilities src/common/pfs.cpp
"""

from __future__ import annotations

import io
import struct
import time
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PFS_MAGIC = b"PFS "
_PFS_VERSION = 0x00020000
_STEVE_MAGIC = b"STEVE"
_CHUNK_SIZE = 8192  # deflate block size used by the original tool chain

# Filename list CRC — this is the CRC of the special "directory name block"
# sentinel used by original EQ tools. Always 0x61580AC9 in known archives.
_DIR_SENTINEL_CRC = 0x61580AC9


# ---------------------------------------------------------------------------
# CRC helpers
# ---------------------------------------------------------------------------

def _filename_crc32(name: str) -> int:
    """Compute the EQ-style CRC32 for a filename (uppercase, null-terminated)."""
    # EQ tools uppercase the name before CRC'ing
    data = name.upper().encode("ascii") + b"\x00"
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc >>= 1
    return crc & 0xFFFFFFFF


# ---------------------------------------------------------------------------
# Deflate helpers
# ---------------------------------------------------------------------------

def _deflate_chunks(data: bytes, chunk_size: int = _CHUNK_SIZE) -> bytes:
    """
    Compress *data* in *chunk_size* blocks, prefixing each block with
    [uint32 deflated_size][uint32 inflated_size].
    """
    out = io.BytesIO()
    offset = 0
    while offset < len(data):
        chunk = data[offset : offset + chunk_size]
        compressed = zlib.compress(chunk, level=6)
        out.write(struct.pack("<II", len(compressed), len(chunk)))
        out.write(compressed)
        offset += chunk_size
    return out.getvalue()


def _inflate_chunks(data: bytes, expected_size: int) -> bytes:
    """
    Decompress a stream of [deflated_size][inflated_size][data] blocks
    until *expected_size* bytes have been recovered.
    """
    out = bytearray()
    buf = io.BytesIO(data)
    while len(out) < expected_size:
        header = buf.read(8)
        if len(header) < 8:
            break
        deflated_sz, inflated_sz = struct.unpack("<II", header)
        compressed = buf.read(deflated_sz)
        out.extend(zlib.decompress(compressed))
    return bytes(out)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class PfsFile:
    """A single file entry inside a PFS archive."""
    name: str   # original filename (case-preserved for display; CRC uses upper)
    data: bytes


@dataclass
class PfsArchive:
    """
    In-memory representation of a PFS archive.

    Usage::

        # Read
        arc = PfsArchive.from_file("gukbottom.eqg")
        ter_data = arc.get("gukbottom.ter")

        # Write
        arc = PfsArchive()
        arc.add("myzone.ter", ter_bytes)
        arc.add("myzone.zon", zon_bytes)
        arc.write_file("myzone.eqg")
    """

    files: List[PfsFile] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @classmethod
    def from_bytes(cls, data: bytes) -> "PfsArchive":
        """Parse a PFS archive from raw bytes."""
        arc = cls()
        buf = io.BytesIO(data)

        # First 4 bytes: offset to the directory block
        (dir_offset,) = struct.unpack("<I", buf.read(4))

        # Next 4 bytes: magic 'PFS '
        magic = buf.read(4)
        if magic != _PFS_MAGIC:
            raise ValueError(f"Not a PFS archive (magic={magic!r})")

        # Version
        (version,) = struct.unpack("<I", buf.read(4))
        if version != _PFS_VERSION:
            raise ValueError(f"Unsupported PFS version: 0x{version:08X}")

        # Jump to directory
        buf.seek(dir_offset)
        (file_count,) = struct.unpack("<I", buf.read(4))

        @dataclass
        class _DirEntry:
            crc: int
            offset: int
            size: int  # decompressed size

        dir_entries: List[_DirEntry] = []
        for _ in range(file_count):
            crc, offset, size = struct.unpack("<III", buf.read(12))
            dir_entries.append(_DirEntry(crc, offset, size))

        # Collect raw compressed data for each entry
        raw_by_crc: Dict[int, bytes] = {}
        for entry in dir_entries:
            buf.seek(entry.offset)
            # Read enough bytes to cover the chunk stream
            # We read the compressed chunks until we have entry.size decompressed bytes
            chunk_data = buf.read(dir_offset - entry.offset)
            raw_by_crc[entry.crc] = (chunk_data, entry.size)

        # One of the entries is the filename block (CRC == _DIR_SENTINEL_CRC or
        # the entry whose decompressed data starts with a file-count that matches).
        # We identify it by trying to parse it as the name list.
        name_by_crc: Dict[int, str] = {}
        file_data_by_crc: Dict[int, bytes] = {}

        for entry in dir_entries:
            compressed_stream, decomp_size = raw_by_crc[entry.crc]
            decompressed = _inflate_chunks(compressed_stream, decomp_size)

            # Try to interpret as the filename block
            if len(decompressed) >= 4:
                (name_count,) = struct.unpack("<I", decompressed[:4])
                if name_count == file_count - 1:
                    # This is the name block
                    pos = 4
                    for _ in range(name_count):
                        if pos + 4 > len(decompressed):
                            break
                        (name_len,) = struct.unpack("<I", decompressed[pos : pos + 4])
                        pos += 4
                        raw_name = decompressed[pos : pos + name_len]
                        pos += name_len
                        # Strip null terminator
                        fname = raw_name.rstrip(b"\x00").decode("ascii", errors="replace")
                        name_by_crc[_filename_crc32(fname)] = fname
                    continue

            file_data_by_crc[entry.crc] = decompressed

        # Match files to names
        for crc, data in file_data_by_crc.items():
            name = name_by_crc.get(crc, f"unknown_{crc:08x}")
            arc.files.append(PfsFile(name=name, data=data))

        return arc

    @classmethod
    def from_file(cls, path: str | Path) -> "PfsArchive":
        """Load a PFS archive from disk."""
        return cls.from_bytes(Path(path).read_bytes())

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get(self, name: str) -> Optional[bytes]:
        """Return the data for a file by name (case-insensitive)."""
        name_lower = name.lower()
        for f in self.files:
            if f.name.lower() == name_lower:
                return f.data
        return None

    def get_by_extension(self, ext: str) -> List[PfsFile]:
        """Return all files matching a given extension (e.g. 'ter')."""
        ext = ext.lower().lstrip(".")
        return [f for f in self.files if f.name.lower().endswith(f".{ext}")]

    def list_files(self) -> List[str]:
        """Return all filenames in the archive."""
        return [f.name for f in self.files]

    # ------------------------------------------------------------------
    # Mutate
    # ------------------------------------------------------------------

    def add(self, name: str, data: bytes) -> None:
        """Add or replace a file in the archive."""
        name_lower = name.lower()
        for existing in self.files:
            if existing.name.lower() == name_lower:
                existing.data = data
                return
        self.files.append(PfsFile(name=name, data=data))

    def remove(self, name: str) -> bool:
        """Remove a file by name. Returns True if found and removed."""
        name_lower = name.lower()
        before = len(self.files)
        self.files = [f for f in self.files if f.name.lower() != name_lower]
        return len(self.files) < before

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def to_bytes(self) -> bytes:
        """Serialize the archive to bytes."""
        out = io.BytesIO()

        # Placeholder for dirOffset (will backfill)
        out.write(struct.pack("<I", 0))
        out.write(_PFS_MAGIC)
        out.write(struct.pack("<I", _PFS_VERSION))

        # Sort files by CRC for consistent ordering (mirrors original toolchain)
        sorted_files = sorted(self.files, key=lambda f: _filename_crc32(f.name))

        dir_entries: List[tuple] = []  # (crc, offset, decompressed_size)

        # Write each file as compressed chunks
        for pf in sorted_files:
            offset = out.tell()
            compressed = _deflate_chunks(pf.data)
            out.write(compressed)
            dir_entries.append((_filename_crc32(pf.name), offset, len(pf.data)))

        # Build and write the filename block
        name_block = io.BytesIO()
        name_block.write(struct.pack("<I", len(sorted_files)))
        for pf in sorted_files:
            encoded = pf.name.encode("ascii") + b"\x00"
            name_block.write(struct.pack("<I", len(encoded)))
            name_block.write(encoded)

        name_block_bytes = name_block.getvalue()
        name_block_offset = out.tell()
        out.write(_deflate_chunks(name_block_bytes))

        dir_entries.append((_DIR_SENTINEL_CRC, name_block_offset, len(name_block_bytes)))

        # Write directory block
        dir_offset = out.tell()
        out.write(struct.pack("<I", len(dir_entries)))
        for crc, offset, size in dir_entries:
            out.write(struct.pack("<III", crc, offset, size))

        # STEVE footer
        out.write(_STEVE_MAGIC)
        out.write(struct.pack("<I", int(time.time())))

        # Backfill dirOffset at position 0
        out.seek(0)
        out.write(struct.pack("<I", dir_offset))

        return out.getvalue()

    def write_file(self, path: str | Path) -> None:
        """Write the archive to disk."""
        Path(path).write_bytes(self.to_bytes())

    def __repr__(self) -> str:
        names = ", ".join(f.name for f in self.files[:5])
        if len(self.files) > 5:
            names += f", … (+{len(self.files) - 5} more)"
        return f"PfsArchive({len(self.files)} files: {names})"
