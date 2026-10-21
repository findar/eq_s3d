"""
tests/test_properties_core.py
-----------------------------
Core property module for the M0 Property_Suite — the pure, no-build properties
over the binary I/O layer (``core/pfs.py``, ``core/ter.py``, ``core/zon.py``).

Design reference: ``.kiro/specs/zone-generator-m0-hygiene/design.md``,
"Property modules" and "Correctness Properties". Each test carries a
Property_Docstring beginning ``Feature: zone-generator-m0-hygiene, Property N:
<title>`` and naming its umbrella Pn plus the requirement ids it validates.

Properties in this module:
  * P13 — PFS archive round-trip (this file's ``test_pfs_roundtrip``)
  * P14 — PFS filename CRC matches the reference (``test_pfs_crc_matches_reference``)
"""

from __future__ import annotations

import random
import zlib

from hypothesis import event, example, given, settings

from core.pfs import PfsArchive, _filename_crc32

from tests.pbt_helpers import ref_crc, scaled
from tests.strategies import pfs_entries, pfs_names


# ---------------------------------------------------------------------------
# A pinned bulk example: 600 names of length 60.
#
# The serialized name block is  [uint32 count] + per name [uint32 len][name+\0].
# With 600 names of 60 chars each that is 4 + 600 * (4 + 61) = 39,004 bytes,
# well over the 8192-byte deflate chunk size, so this example exercises the
# multi-chunk name-block path on both write (`_deflate_chunks`) and read
# (`_inflate_chunks`). Names are drawn deterministically from the same
# printable-ASCII alphabet the `pfs_entries` strategy uses, deduplicated
# case-insensitively, so the example is a value the strategy could itself
# produce. Built once at import time.
# ---------------------------------------------------------------------------

def _bulk_example(n: int, name_len: int, seed: int = 0) -> dict:
    """``n`` distinct printable-ASCII names of ``name_len`` chars, small payloads."""
    alphabet = "".join(
        c for c in (chr(i) for i in range(0x20, 0x7F)) if c not in ("/", "\\")
    )
    rng = random.Random(seed)
    entries: dict[str, bytes] = {}
    seen_lower: set[str] = set()
    while len(entries) < n:
        name = "".join(rng.choice(alphabet) for _ in range(name_len))
        if name.lower() in seen_lower:
            continue
        seen_lower.add(name.lower())
        entries[name] = rng.randbytes(rng.randint(0, 64))
    return entries


_BULK_600x60 = _bulk_example(600, 60)


# deadline=None: a large archive (up to 2000 entries, and the pinned ~39 KB
# multi-chunk name-block @example) takes a few hundred ms to serialize+parse.
# That cost scales with entry count and is not a correctness signal, so the
# per-example wall-clock deadline would flake on the big cases. The budget
# (scaled(100)) and the property itself are unchanged.
@settings(max_examples=scaled(100), deadline=None)
@given(entries=pfs_entries())
@example(entries=_BULK_600x60)
def test_pfs_roundtrip(entries):
    """Feature: zone-generator-m0-hygiene, Property 1: PFS archive round-trip.

    Umbrella P13. Validates: M0 Req 2.1; umbrella Req 1.6.

    For any name->bytes map with distinct (case-insensitive) printable-ASCII
    names and arbitrary payloads, serializing a PfsArchive built from it and
    parsing the result back yields exactly the same map: identical keys with
    case PRESERVED, identical payload bytes, and no extra entries.

    The pinned @example (600 names of length 60, a ~39 KB name block) also
    exercises the multi-chunk deflate path through the name block.
    """
    arc = PfsArchive()
    for name, data in entries.items():
        arc.add(name, data)

    parsed = PfsArchive.from_bytes(arc.to_bytes())

    # Build the round-tripped name->bytes map straight off `.files` (not `.get`,
    # which is case-insensitive) so case preservation is actually tested.
    round_tripped = {f.name: f.data for f in parsed.files}

    # Same keys, case-preserved, and no extra entries.
    assert set(round_tripped) == set(entries), (
        "round-tripped names differ from input "
        f"(missing={set(entries) - set(round_tripped)}, "
        f"extra={set(round_tripped) - set(entries)})"
    )
    # No collapsed names (a CRC collision or sentinel clash would drop entries).
    assert len(parsed.files) == len(entries), (
        f"entry count changed: {len(entries)} in, {len(parsed.files)} out"
    )
    # Same bytes for every name.
    for name, data in entries.items():
        assert round_tripped[name] == data, f"payload mismatch for {name!r}"

# ---------------------------------------------------------------------------
# Property 2: PFS filename CRC matches the reference (umbrella P14).
# ---------------------------------------------------------------------------

@settings(max_examples=scaled(100))
@given(name=pfs_names)
# Two pinned existence claims (the lessons-learned facts this property guards):
#   * EQ's CRC is NOT a reflected zlib CRC32 — "gukbottom.ter" must differ.
#   * EQ's CRC is case-sensitive — "Ab" and "aB" must differ.
@example(name="gukbottom.ter")
@example(name="Ab")
@example(name="aB")
def test_pfs_crc_matches_reference(name):
    """Feature: zone-generator-m0-hygiene, Property 2: PFS filename CRC matches the reference.

    Umbrella P14. Validates: M0 Req 2.2; umbrella Req 1.6.

    For any printable-ASCII filename, ``core.pfs``'s production filename CRC
    (``_filename_crc32``) equals an independent bitwise reference derivation
    (``ref_crc`` — poly 0x04C11DB7, init 0, no final XOR, over name+NUL,
    written without ``core.pfs``'s precomputed table). The two pinned
    @examples assert the two existence claims from lessons-learned: EQ's CRC
    is NOT the reflected zlib CRC32 (``gukbottom.ter`` differs from
    ``zlib.crc32``), and it is case-sensitive (``Ab`` differs from ``aB``).
    """
    produced = _filename_crc32(name)
    reference = ref_crc(name)

    # Core assertion: production CRC agrees with the independent reference.
    assert produced == reference, (
        f"CRC mismatch for {name!r}: _filename_crc32={produced:#010x} "
        f"ref_crc={reference:#010x}"
    )

    # Make the two "differs" existence claims visible in Hypothesis statistics.
    differs_from_zlib = produced != (zlib.crc32(name.encode("ascii")) & 0xFFFFFFFF)
    event(f"differs from zlib.crc32: {differs_from_zlib}")
    event(f"crc parity: {'odd' if produced & 1 else 'even'}")

    # Existence claim 1: EQ's CRC is NOT the reflected zlib CRC32.
    if name == "gukbottom.ter":
        assert produced != (zlib.crc32(name.encode("ascii")) & 0xFFFFFFFF), (
            "EQ PFS CRC must not equal the reflected zlib CRC32 for "
            "'gukbottom.ter' (lessons-learned: EQ CRC is its own big-endian CRC)"
        )

    # Existence claim 2: EQ's CRC is case-sensitive.
    if name == "Ab":
        assert _filename_crc32("Ab") != _filename_crc32("aB"), (
            "EQ PFS CRC must be case-sensitive ('Ab' != 'aB')"
        )
