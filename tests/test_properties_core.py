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
  * P15 — built TER/ZON round-trip (``test_ter_zon_roundtrip``)
"""

from __future__ import annotations

import random
import zlib

import pytest
from hypothesis import assume, event, example, given, settings

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from core.pfs import PfsArchive, _filename_crc32
from core.ter import TerFile
from core.zon import ZonFile
from generators.builder import ZoneBuilder

from tests.pbt_helpers import (
    build_raw,
    build_settings,
    fresh_dir,
    f32,
    ref_crc,
    scaled,
)
from tests.strategies import (
    box_themes,
    pfs_entries,
    pfs_names,
    room_counts,
    semantic_inputs,
)


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


# ---------------------------------------------------------------------------
# PFS filename-CRC collision — a FORMAT LIMIT, not a code bug (user decision,
# option (a)).
#
# The PFS container keys every file by EQ's 32-bit filename CRC
# (`core.pfs._filename_crc32`): one directory slot per CRC value. Two DISTINCT
# names that hash to the same CRC therefore cannot coexist in one archive — the
# second overwrites the first, so the round-trip drops one name. This is a
# property of the on-disk format, not of our writer; there is no code change
# that lets two CRC-colliding names survive in a single PFS archive.
#
# The thorough-profile run surfaced such a collision in the adversarial
# ~60-random-name set. Real EverQuest zones use a small FIXED set of controlled
# filenames that never collide, so the physically-unstorable colliding case is
# not a scenario the format can represent. Per the user's decision the
# round-trip property is scoped to collision-free name sets (see the `assume`
# guard at the top of `test_pfs_roundtrip`). This EXCLUDES an input the format
# cannot represent — it is NOT a narrowing of the name alphabet (the
# `pfs_entries` strategy in tests/strategies.py keeps its full alphabet).
#
# A concrete collision pair, demonstrated below so the format limit is real and
# checkable: both names below hash to CRC 0x23a58563 under the production
# `_filename_crc32`, so a PfsArchive containing both collapses to one file.
_PFS_CRC_COLLISION_A = "R,YF%a"
_PFS_CRC_COLLISION_B = "po}(]x19"
assert (
    _filename_crc32(_PFS_CRC_COLLISION_A)
    == _filename_crc32(_PFS_CRC_COLLISION_B)
    == 0x23A58563
), (
    "expected the documented PFS filename-CRC collision pair to share CRC "
    "0x23a58563 under the production _filename_crc32 (format limit — one slot "
    "per 32-bit CRC)"
)


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

    Collision-free precondition (format limit, user decision — see the module
    comment above): the PFS container keys files by the 32-bit filename CRC, one
    slot per CRC value, so two distinct names sharing a CRC cannot coexist in one
    archive. We compute the CRCs with the REAL production `_filename_crc32` (the
    function the archive itself keys by — not `tests.pbt_helpers.ref_crc`) and
    `assume` away any drawn set with an intra-set CRC collision. That input is
    physically unstorable in the on-disk format, so excluding it is NOT a
    narrowing of the name space; the property holds for every archive the format
    can actually represent.
    """
    names = list(entries)
    crcs = [_filename_crc32(name) for name in names]
    assume(len(set(crcs)) == len(names))

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

# ---------------------------------------------------------------------------
# Property 3: Built TER and ZON round-trip (umbrella P15).
#
# DESIGN DEVIATION (verified against the real code, recorded here):
#   The design's field list for this property names
#   "vertices, polygons, materials, objects, lights and regions" as TerFile
#   fields. The real `core.ter.TerFile` (read at authoring time) carries ONLY
#   `vertices`, `polygons` and `materials` (plus `name`/`magic`/`version`).
#   `objects`, `lights` and `regions` do NOT live on the TER at all -- they are
#   `core.zon.ZonFile` fields. The design conflated the two binaries.
#
#   The property's INTENT is that the builder's geometry+placement serialisation
#   round-trips into the archive, and that semantic tints (which yield ZON
#   regions) survive. So this test asserts the round-trip on BOTH binaries:
#     * TER: re-derived `ZoneBuilder._build_geometry` bytes == archived TER, then
#       field-wise vertices/polygons/materials (floats bit-equal via `f32`);
#     * ZON: re-derived `ZoneBuilder._build_zon` bytes == archived ZON, then
#       field-wise models/objects/lights/regions (floats bit-equal via `f32`) --
#       which is where the design's "objects, lights and regions" (and the
#       elemental-tint regions) actually are.
#   This realises the design's intent exactly, against the structures the code
#   actually exposes.
#
# Builder call shapes, verified against generators/builder.py:
#   `ZoneBuilder.build` serialises geometry via
#   `self._build_geometry(spec.name.lower(), ter_version=2)` and placement via
#   `self._build_zon(f"ter_{spec.name.lower()}.ter")`, so the re-derivation here
#   uses those exact arguments. `build_raw` archives the TER under
#   `ter_<name>.ter` and the ZON under `<name>.zon` (name = spec.name.lower()).
# ---------------------------------------------------------------------------

def _f32_vertex(v):
    """A Vertex's comparable tuple with every float snapped to f32."""
    return (
        f32(v.x), f32(v.y), f32(v.z),
        f32(v.nx), f32(v.ny), f32(v.nz),
        f32(v.u), f32(v.v),
        v.color,
    )


def _prop_tuple(p):
    """A MaterialProperty's comparable tuple (its one float snapped to f32)."""
    return (p.name, p.type, f32(p.value_f), p.value_i, p.value_s)


def _material_tuple(m):
    """A Material's comparable tuple (name/shader/index + its properties)."""
    return (m.index, m.name, m.shader, tuple(_prop_tuple(p) for p in m.properties))


def _polygon_tuple(p):
    """A Polygon's comparable tuple (all-integer; no float fields)."""
    return (p.v1, p.v2, p.v3, p.material, p.flags)


def _ter_fields(ter):
    """(vertices, polygons, materials) of a TerFile as f32-snapped tuples."""
    return (
        tuple(_f32_vertex(v) for v in ter.vertices),
        tuple(_polygon_tuple(p) for p in ter.polygons),
        tuple(_material_tuple(m) for m in ter.materials),
    )


def _zon_object_tuple(o):
    """A ZonObject's comparable tuple (floats snapped to f32)."""
    return (
        o.name, o.model_id,
        f32(o.x), f32(o.y), f32(o.z),
        f32(o.rx), f32(o.ry), f32(o.rz),
        f32(o.scale),
    )


def _zon_region_tuple(r):
    """A ZonRegion's comparable tuple (floats snapped to f32)."""
    return (
        r.name,
        f32(r.center_x), f32(r.center_y), f32(r.center_z),
        f32(r.rotation),
        f32(r.extend_x), f32(r.extend_y), f32(r.extend_z),
    )


def _zon_light_tuple(lt):
    """A ZonLight's comparable tuple (floats snapped to f32)."""
    return (
        lt.name,
        f32(lt.x), f32(lt.y), f32(lt.z),
        f32(lt.r), f32(lt.g), f32(lt.b),
        f32(lt.radius),
    )


def _zon_fields(zon):
    """(models, objects, regions, lights) of a ZonFile as f32-snapped tuples."""
    return (
        tuple(zon.models),
        tuple(_zon_object_tuple(o) for o in zon.objects),
        tuple(_zon_region_tuple(r) for r in zon.regions),
        tuple(_zon_light_tuple(lt) for lt in zon.lights),
    )


@pytest.mark.slow
@build_settings(20)
@given(
    theme=box_themes,
    n=room_counts(2, 12),
    semantic=semantic_inputs,
)
def test_ter_zon_roundtrip(theme, n, semantic):
    """Feature: zone-generator-m0-hygiene, Property 3: Built TER and ZON round-trip.

    Umbrella P15. Validates: M0 Req 2.3, 1.5; umbrella Req 1.6.

    For any box-theme build (dungeon/city, 2-12 rooms, with the semantic content
    layer active so elemental tints realise ZON regions), the geometry and
    placement the builder serialises into the ``.eqg`` round-trip exactly:

      1. The TER bytes re-derived in memory from ``ZoneBuilder._build_geometry``
         for the same spec EQUAL the TER archived in the ``.eqg`` -- the
         builder's geometry serialisation is stable and byte-identical to what
         it stored.
      2. Parsing those archived TER bytes back yields a ``TerFile`` whose
         vertices, polygons and materials are field-for-field equal to the
         re-derived one, with every float bit-equal (snapped to IEEE-754 single
         precision via ``f32``).
      3. The same two checks hold for the ZON (``ZoneBuilder._build_zon``):
         re-derived bytes equal the archived ZON, and parsing it back gives
         models, objects, regions and lights field-for-field equal with floats
         bit-equal. The ZON is where ``objects``, ``lights`` and ``regions``
         (including the elemental-tint regions) actually live -- see the module
         comment above for the design-vs-code field-list deviation.

    Building goes through ``ai.expand.plan_to_spec`` so ``dungeon_theme`` /
    ``dungeon_race`` / ``elemental_tint`` are realised exactly as the production
    content path would realise them.
    """
    plan = ZonePlan(
        name=f"tz{theme}{n}",
        theme=theme,
        room_count=n,
        dungeon_theme=semantic["dungeon_theme"],
        dungeon_race=semantic["dungeon_race"],
        elemental_tint=(semantic["elemental_tint"] or ""),
    )
    spec = plan_to_spec(plan, seed=0x7E51)

    with fresh_dir() as out:
        _result, ter_bytes, zon_bytes = build_raw(spec, out)

    name = spec.name.lower()

    # --- TER round-trip -------------------------------------------------
    # Re-derive the in-memory TerFile for the same spec, using the exact
    # arguments ZoneBuilder.build feeds _build_geometry (lowercased name,
    # ter_version=2). Its serialisation must reproduce the archived TER byte for
    # byte.
    re_ter = ZoneBuilder(spec)._build_geometry(name, 2)
    assert re_ter.to_bytes() == ter_bytes, (
        "re-derived TER bytes differ from the TER archived in the .eqg "
        "(builder geometry serialisation is not stable)"
    )

    # Field-wise equality against the TerFile parsed back from the archive.
    parsed_ter = TerFile.from_bytes(ter_bytes)
    re_v, re_p, re_m = _ter_fields(re_ter)
    pa_v, pa_p, pa_m = _ter_fields(parsed_ter)
    assert re_v == pa_v, "TER vertices differ after round-trip"
    assert re_p == pa_p, "TER polygons differ after round-trip"
    assert re_m == pa_m, "TER materials differ after round-trip"

    # --- ZON round-trip -------------------------------------------------
    # Re-derive the in-memory ZonFile the same way build() does, then assert the
    # same byte + field-wise round-trip. This covers the design's "objects,
    # lights and regions" -- the ZON is where those actually live -- and the
    # elemental-tint regions the semantic layer emits.
    re_zon = ZoneBuilder(spec)._build_zon(f"ter_{name}.ter")
    assert re_zon.to_bytes() == zon_bytes, (
        "re-derived ZON bytes differ from the ZON archived in the .eqg "
        "(builder placement serialisation is not stable)"
    )

    parsed_zon = ZonFile.from_bytes(zon_bytes)
    assert _zon_fields(re_zon) == _zon_fields(parsed_zon), (
        "ZON models/objects/regions/lights differ after round-trip"
    )
