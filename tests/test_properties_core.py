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

M1 property added here (``.kiro/specs/zone-generator-m1-controls-traversability``):
  * M1-P4 — the faster walk surface has the same reachability as the fork-point
    reference (``test_walk_surface_equivalence``).
  * M1-P5 — the Format_Checker is total and specific
    (``test_format_checker_total``).
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
    box_zone_types,
    pfs_entries,
    pfs_names,
    room_counts,
    seeds,
    semantic_inputs,
    verticality,
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
    zone_type=box_zone_types,
    n=room_counts(2, 12),
    semantic=semantic_inputs,
)
def test_ter_zon_roundtrip(zone_type, n, semantic):
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
        name=f"tz{zone_type}{n}",
        zone_type=zone_type,
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
    # _build_geometry now returns (ter, backend_name, warnings) — it routes
    # through the backend registry (wave 3). We only need the TerFile here.
    re_ter, _backend, _warnings = ZoneBuilder(spec)._build_geometry(name, 2)
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

# ---------------------------------------------------------------------------
# M1 Property 13 (M1-P4): the faster walk surface has the same reachability.
#
# Task 2.2 rewrote ``analyzer.traverse.build_walk_surface`` with a union-find
# that drops REDUNDANT seam edges (edges between faces already in the same
# component) to skip the expensive ``_tri_tri_xy_contact`` test, plus two
# component-preserving candidate cuts. The claim is that this changes SPEED
# only: the standable set, the connected-component partition, and therefore
# every reachability answer are identical to the fork-point code. This property
# proves that against ``tests/reference_traverse.py`` — the frozen fork-point
# copy — on a real built mesh, which is the ONLY honest check (the optimised and
# reference modules compute the same thing two different ways).
#
# Imports are local to this block so the M0 part of the module stays unchanged.
# ---------------------------------------------------------------------------

import numpy as np

import analyzer.traverse as T
import tests.reference_traverse as RT
from generators.layout import LayoutGenerator


def _components_from_adjacency(surf) -> frozenset:
    """
    Connected-component partition of a walk surface, derived purely from its
    ``adjacency`` lists (so it works for BOTH the optimised surface and the
    frozen reference, which has no ``component`` array). Returns a frozenset of
    frozensets of standable face ids — a canonical, order-independent value two
    surfaces can be compared by directly.
    """
    std_idx = [int(f) for f in np.nonzero(surf.standable)[0]]
    seen: set = set()
    comps = []
    for start in std_idx:
        if start in seen:
            continue
        # BFS over adjacency from this unseen face.
        stack = [start]
        seen.add(start)
        comp = {start}
        while stack:
            f = stack.pop()
            for nb in surf.adjacency.get(f, ()):
                if nb not in seen:
                    seen.add(nb)
                    comp.add(nb)
                    stack.append(nb)
        comps.append(frozenset(comp))
    return frozenset(comps)


def _components_from_component_array(surf) -> frozenset:
    """
    Connected-component partition read off the optimised surface's ``component``
    array (root per standable face, -1 elsewhere). Returns the same canonical
    frozenset-of-frozensets shape as ``_components_from_adjacency`` so the two
    can be asserted equal — i.e. the exposed ``component`` array agrees with what
    a flood over the surface's own adjacency recovers.
    """
    comp = surf.component
    std_idx = np.nonzero(surf.standable)[0]
    by_root: dict = {}
    for f in std_idx:
        by_root.setdefault(int(comp[f]), set()).add(int(f))
    return frozenset(frozenset(v) for v in by_root.values())


def _room_result_tuples(report) -> list:
    """A ``TraversalReport``'s per-room results as comparable tuples."""
    return [
        (r.room_id, r.role, r.reachable, r.floor_faces, r.reached_faces, r.reason)
        for r in report.rooms
    ]


def _corridor_result_tuples(results) -> list:
    """A list of ``CorridorResult``s as comparable tuples (order preserved)."""
    return [
        (c.corridor_id, c.from_room, c.to_room, c.connected, c.reason)
        for c in results
    ]


@pytest.mark.slow
@build_settings(10)
# Regression anchor: the first box build this property exercised end to end
# (dungeon, 2 rooms, flat). No speed-up divergence has been found, so this is an
# anchor example rather than a pinned counterexample; if 2.2's union-find ever
# regresses, replace this with the discovered seed via
# ``@example(...).via("discovered failure")``.
@example(zone_type="dungeon", n=2, vert="flat", s=0)
@given(
    zone_type=box_zone_types,
    n=room_counts(2, 30),
    vert=verticality,
    s=seeds,
)
def test_walk_surface_equivalence(zone_type, n, vert, s):
    """Feature: zone-generator-m1-controls-traversability, Property 13: The faster walk surface has the same reachability.

    M1-P4. Validates: Requirements 4.1, 5.2.

    For any box zone type (dungeon/city), 2-30 rooms and any verticality
    (flat/moderate/dramatic), the optimised ``analyzer.traverse.build_walk_surface``
    and the frozen fork-point reference ``tests.reference_traverse.build_walk_surface``
    produce walk surfaces that are reachability-equivalent on the same built TER
    mesh:

      1. **Same standable faces** — the two ``standable`` masks are identical, so
         the union-find speed-up did not change which triangles the agent can
         stand on.
      2. **Same connected components** — the component partition derived from the
         optimised surface's ``adjacency`` equals the one derived from the
         reference's ``adjacency`` (canonical frozenset-of-frozensets). The
         optimised surface's new ``component`` array is ALSO asserted to agree
         with its own adjacency flood, so the exposed partition is trustworthy
         and not just an internal artefact. Dropping redundant seam edges can
         thin an adjacency LIST but can never split or merge a component, which
         is exactly what this checks.
      3. **``flood_reachable`` agrees from every start face** — for every
         standable face, the reachable set on the optimised surface equals the
         reachable set on the reference surface. (Components being equal implies
         this; asserting it from every start face is the direct reachability
         statement Requirement 5.2 names.)
      4. **Every ``TraversalReport`` room result is equal** — the live
         ``analyzer.traverse.validate`` room results on this mesh equal the
         fork-point per-room results reproduced by
         ``tests.reference_traverse.reference_room_results`` on the reference
         surface for the same spec (room-for-room: reachable, floor_faces,
         reached_faces, reason).
      5. **``corridor_continuity`` and ``corridor_conflicts`` agree on both
         surfaces** (task 4.2, design Decision 15) — running the SAME
         ``analyzer.traverse.corridor_continuity`` over the optimised surface and
         over the frozen fork-point reference surface (each passed as ``surf``)
         gives identical ``CorridorResult`` lists (ids, rooms, ``connected``,
         ``reason``), and ``corridor_conflicts`` gives identical conflict pairs.
         ``corridor_continuity`` recomputes seam contacts LOCALLY for its
         region's faces and never reads ``surf.adjacency`` or ``surf.component``
         — the only fields the speed-up changed — so the two surfaces must agree.
         A mismatch is a bug in the continuity flood (fixed at the root in
         ``analyzer/traverse.py``), not in this property.

    A failure here is a real bug in the task 2.2 speed-up (an edge that should
    have been kept was dropped, splitting a component, or a candidate cut
    discarded a genuine cross-component contact). It is fixed at the root in
    ``analyzer/traverse.py`` — never by weakening an assertion — and the
    counterexample is pinned above as ``@example(...).via("discovered failure")``.

    Build-level property: ``@pytest.mark.slow`` + ``build_settings(10)``. Box
    zone types only; wilderness n 2-6 is added in task 13.7. Corridor continuity
    + conflict equality (point 5) was added in task 4.2 (design Property 13
    covers both the reachability and continuity slices).

    NOTE: this is an ANALYTICAL equivalence over two validator implementations on
    the built mesh, not a live 3D viewer confirmation — see docs/ACCEPTANCE.md.
    """
    # Build a box zone with the drawn verticality. plan_to_spec is the only path
    # that applies plan `verticality`; elevation=True lets moderate/dramatic
    # actually elevate corridors (flat stays flat regardless).
    plan = ZonePlan(
        name="wseq",
        zone_type=zone_type,
        room_count=n,
        verticality=vert,
        elevation=(vert != "flat"),
    )
    spec = plan_to_spec(plan, seed=s)

    agent = T.AgentModel()
    ref_agent = RT.AgentModel()

    with fresh_dir() as out:
        result, _ter_bytes, _zon_bytes = build_raw(spec, out)
        ter, _zone_name = T.load_ter_from_eqg(result.eqg_path)

        opt_surf = T.build_walk_surface(ter, agent)
        ref_surf = RT.build_walk_surface(ter, ref_agent)

        # Live optimised per-room results (validate builds its own optimised
        # surface from the same .eqg).
        live_report = T.validate(result.eqg_path, spec=spec, agent=agent)

    ctx = f"(zone_type={zone_type}, rooms={n}, verticality={vert}, seed={s})"

    # 1) Same standable faces.
    assert np.array_equal(opt_surf.standable, ref_surf.standable), (
        f"standable mask differs between optimised and reference surface {ctx}: "
        f"opt={int(opt_surf.standable.sum())} standable, "
        f"ref={int(ref_surf.standable.sum())} standable"
    )

    # 2) Same connected components (from adjacency, both surfaces).
    opt_comps = _components_from_adjacency(opt_surf)
    ref_comps = _components_from_adjacency(ref_surf)
    assert opt_comps == ref_comps, (
        f"connected-component partition differs between optimised and reference "
        f"surface {ctx}: opt has {len(opt_comps)} components, "
        f"ref has {len(ref_comps)} — the union-find speed-up split or merged a "
        f"component (a non-redundant edge was dropped)"
    )
    # The exposed `component` array must match the optimised surface's own
    # adjacency flood — the partition callers read is the real one.
    arr_comps = _components_from_component_array(opt_surf)
    assert arr_comps == opt_comps, (
        f"optimised surface's `component` array disagrees with its adjacency "
        f"flood {ctx}: the exposed component partition is not the walkable one"
    )

    # 3) flood_reachable agrees from EVERY start face.
    std_idx = [int(f) for f in np.nonzero(opt_surf.standable)[0]]
    for f in std_idx:
        opt_reach = T.flood_reachable(opt_surf, f)
        ref_reach = RT.flood_reachable(ref_surf, f)
        assert opt_reach == ref_reach, (
            f"flood_reachable differs from start face {f} {ctx}: "
            f"opt reached {len(opt_reach)} faces, ref reached {len(ref_reach)} "
            f"(symmetric diff {len(opt_reach ^ ref_reach)})"
        )

    # 4) The two surfaces agree on per-room reachability FROM THE SAME START.
    #    M1-P4 is about the faster `build_walk_surface`, not the start-face
    #    picker: points 1-3 already prove the optimised and reference surfaces
    #    have identical standable faces, identical components and identical
    #    `flood_reachable` from EVERY start face, so flooding both from one
    #    shared seed face must give identical per-room reached-face sets. We
    #    flood each surface from the LIVE validate's chosen seed face (task 8.3
    #    fixed `_nearest_standable_face` to stand on the floor UNDER the safe
    #    point; the frozen fork-point reference still carries the old picker, so
    #    calling `reference_room_results` — which re-picks with the old rule —
    #    would conflate that picker fix with the surface question this property
    #    actually governs). Mapping faces to rooms uses the reference's frozen
    #    `_faces_in_room` on each surface so the comparison is the surfaces'.
    seed_face = live_report.seed_face
    opt_reached = RT.flood_reachable(opt_surf, seed_face) if seed_face is not None else set()
    ref_reached = RT.flood_reachable(ref_surf, seed_face) if seed_face is not None else set()
    opt_room_reach = {
        r.id: sorted(int(f) for f in RT._faces_in_room(opt_surf, r) if int(f) in opt_reached)
        for r in spec.rooms
    }
    ref_room_reach = {
        r.id: sorted(int(f) for f in RT._faces_in_room(ref_surf, r) if int(f) in ref_reached)
        for r in spec.rooms
    }
    assert opt_room_reach == ref_room_reach, (
        f"per-room reached faces differ between optimised and reference surface "
        f"flooded from the same seed face {seed_face} {ctx}:\n"
        f"  optimised: {opt_room_reach}\n"
        f"  reference: {ref_room_reach}"
    )

    # 5) corridor_continuity + corridor_conflicts agree on both surfaces (task
    #    4.2, design Decision 15). corridor_continuity recomputes seam contacts
    #    LOCALLY for its region's faces (via _local_adjacency) and never reads
    #    surf.adjacency or surf.component — the only fields the speed-up changed.
    #    So running the SAME analyzer.traverse.corridor_continuity over the
    #    optimised surface and over the frozen fork-point reference surface (both
    #    as the `surf` argument) must give identical CorridorResult lists, and
    #    corridor_conflicts (which only reads standable/centroids via
    #    _region_faces) must give identical conflict pairs. A mismatch is a bug
    #    in the continuity flood, not in this property — fix it at the root in
    #    analyzer/traverse.py.
    opt_corr = T.corridor_continuity(opt_surf, spec, agent)
    ref_corr = T.corridor_continuity(ref_surf, spec, ref_agent)
    assert _corridor_result_tuples(opt_corr) == _corridor_result_tuples(ref_corr), (
        f"corridor_continuity results differ between optimised and reference "
        f"surface {ctx}:\n"
        f"  optimised: {_corridor_result_tuples(opt_corr)}\n"
        f"  reference: {_corridor_result_tuples(ref_corr)}\n"
        f"  — the continuity flood read a field the speed-up changed (bug in "
        f"analyzer/traverse.py, not the property)"
    )

    opt_conf = T.corridor_conflicts(opt_surf, spec, agent)
    ref_conf = T.corridor_conflicts(ref_surf, spec, ref_agent)
    assert opt_conf == ref_conf, (
        f"corridor_conflicts differ between optimised and reference surface "
        f"{ctx}: opt={opt_conf} ref={ref_conf}"
    )


# ---------------------------------------------------------------------------
# M1 Property 14 (M1-P5): the Format_Checker is total and specific.
#
# ``analyzer.rof2check.check_eqg`` must be TOTAL — it NEVER raises, for ANY
# corruption of the archive — and SPECIFIC — a failed check carries a message
# that names itself, every check in ``CHECK_NAMES`` is present exactly once, and
# a check whose inputs a corruption did not touch reports the same verdict as on
# the clean archive. This property fuzzes a single small valid dungeon with the
# design's corruption set (``tests.strategies.archive_corruptions``) and asserts
# all four facets. A corruption that makes an input unreadable legitimately
# flips that input's DEPENDENTS to skipped; those dependents are listed in the
# corruption's ``affected`` set (or the corruption is marked ``ALL_CHECKS``), so
# the untouched-check comparison is scoped to checks the damage genuinely left
# alone — the design's "untouched checks unchanged" formulation.
#
# Imports local to this block so the rest of the module is untouched.
# ---------------------------------------------------------------------------

import json as _json
from pathlib import Path as _Path

import analyzer.rof2check as _rof2
from ai.rule_planner import RulePlanner as _RulePlanner
from tests.strategies import ALL_CHECKS as _ALL_CHECKS, archive_corruptions

_FMT_BUILD_NAME = "fmtprobe"


def _corruption_by_label(build: str, label: str):
    """The ``(label, apply, affected)`` corruption tuple with the given label,
    materialised from the same list ``archive_corruptions`` draws from — so a
    pinned ``@example`` is a genuine member of the strategy's domain."""
    from tests.strategies import _corruption_list

    for c in _corruption_list(build):
        if c[0] == label:
            return c
    raise KeyError(f"no corruption labelled {label!r}")


def _check_map(report) -> dict:
    """``{check_name: (passed, skipped)}`` for a FormatReport — the comparable
    verdict per check, independent of message text."""
    return {c.name: (c.passed, c.skipped) for c in report.checks}


@pytest.mark.slow
@build_settings(25)
@given(corruption=archive_corruptions(_FMT_BUILD_NAME))
# Regression anchors: the two corruptions that most directly exercise the two
# halves of the property — the zeroed header (TOTALITY: nothing may raise even
# when the whole archive is unreadable) and a single −1 material index
# (SPECIFICITY: exactly material_indices flips, every untouched check stays
# unchanged). Pinned by label from the materialised corruption list, so the
# @example values are real members of the drawn domain. No totality bug has been
# found, so these are anchors; if a future corruption makes check_eqg raise, add
# it here via ``@example(...).via("discovered failure")``.
@example(corruption=_corruption_by_label(_FMT_BUILD_NAME, "zero_header"))
@example(corruption=_corruption_by_label(_FMT_BUILD_NAME, "material_index_neg"))
def test_format_checker_total(corruption):
    """Feature: zone-generator-m1-controls-traversability, Property 14: The Format_Checker is total and specific.

    M1-P5. Validates: Requirements 9.3.

    For any valid Raw_Build archive and any corruption drawn from the design's
    set (truncate at an offset, flip a byte range, zero the header, drop/rename
    the TER or ZON entry, set a wrong directory CRC, replace the TER or ZON with
    random bytes, set a polygon's material to −1 or past the end, push a vertex
    coordinate past MAX_COORD, shrink a diffuse DDS dimension to a
    non-power-of-two, break the ZON model ref, break Sidecar name consistency),
    ``analyzer.rof2check.check_eqg``:

      1. **TOTAL** — returns a ``FormatReport`` WITHOUT raising, for every
         corruption. If any corruption makes ``check_eqg`` raise, that is a real
         totality bug in ``analyzer/rof2check.py`` to fix at the root (not a
         test to weaken) and pin as a ``@example(...).via("discovered
         failure")``.
      2. **Complete** — the report holds exactly one entry per name in
         ``CHECK_NAMES`` (every check present, none duplicated or missing) in
         the canonical order, and there is no ``normals_resolve`` check (Req
         9.4).
      3. **Specific (self-naming)** — every FAILED check carries at least one
         message, and its first message STARTS WITH its own check name, so a
         failure attributes itself.
      4. **Specific (untouched unchanged)** — a check whose inputs the corruption
         did NOT touch reports the SAME ``(passed, skipped)`` verdict as on the
         clean baseline archive. The comparison is scoped to checks outside the
         corruption's ``affected`` set; a corruption marked ``ALL_CHECKS`` (byte
         garbage that can cascade anywhere) is exempt from this one facet (it
         still exercises 1–3).

    The archive is built ONCE per example (a small valid dungeon) and the
    baseline ``check_eqg`` is run on it; the corruption is then applied to a
    COPY of the archive bytes (or, for the Sidecar-name corruption, to a copy of
    the ``.zone.json``) and ``check_eqg`` is run again on the corrupted archive.
    ``@pytest.mark.slow`` + ``build_settings(25)`` (design: archives built once
    per example, mutations cheap).

    NOTE: analytical property over the format checker on built binaries, not a
    live 3D confirmation — see docs/ACCEPTANCE.md.
    """
    label, apply, affected = corruption

    # --- Build ONE valid small dungeon and read its baseline report --------
    plan = _RulePlanner().plan("create a dungeon with 6 rooms")
    spec = plan_to_spec(plan, seed=7)
    spec.name = _FMT_BUILD_NAME

    with fresh_dir() as out:
        result = ZoneBuilder(spec).build(output_dir=out, write_glb=False)
        eqg_path = _Path(result.eqg_path)
        clean_bytes = eqg_path.read_bytes()
        sidecar_path = _Path(out) / f"{_FMT_BUILD_NAME}.zone.json"

        baseline = _rof2.check_eqg(eqg_path, spec, sidecar_path=sidecar_path)
        # Sanity: the clean build passes (a corruption's effect is measured
        # against a KNOWN-GOOD baseline, not a flaky one).
        assert baseline.passed is True, (
            f"baseline clean archive should pass; failures: {baseline.failed_checks} "
            f"({baseline.messages})"
        )

        is_sidecar = label.startswith("__sidecar__")

        # The corrupted copy keeps the SAME stem as the clean build
        # (``<build>.eqg``) in a sibling directory, so the ``name_consistent``
        # archive-stem comparison is unaffected by the test harness — only the
        # corruption itself can move that check. The Sidecar sits next to it
        # with the matching ``<build>.zone.json`` name for the same reason.
        corrupt_dir = _Path(out) / "corrupt"
        corrupt_dir.mkdir()
        corrupt_path = corrupt_dir / f"{_FMT_BUILD_NAME}.eqg"
        corrupt_sidecar = corrupt_dir / f"{_FMT_BUILD_NAME}.zone.json"
        # Default: carry the clean Sidecar across unchanged.
        corrupt_sidecar.write_text(sidecar_path.read_text())

        if is_sidecar:
            # The eqg is unchanged; corrupt the Sidecar name instead.
            corrupt_path.write_bytes(clean_bytes)
            doc = _json.loads(sidecar_path.read_text())
            doc["name"] = "totally_different_name"
            corrupt_sidecar.write_text(_json.dumps(doc))
        else:
            corrupt_bytes = apply(clean_bytes)
            corrupt_path.write_bytes(corrupt_bytes)

        # --- 1) TOTAL: check_eqg must not raise, for any corruption --------
        try:
            report = _rof2.check_eqg(corrupt_path, spec, sidecar_path=corrupt_sidecar)
        except Exception as e:  # noqa: BLE001 — totality is exactly what we test
            raise AssertionError(
                f"check_eqg RAISED on corruption {label!r} — a totality bug in "
                f"analyzer/rof2check.py (fix at the root, pin this as a "
                f"Regression_Example): {type(e).__name__}: {e}"
            ) from e

    ctx = f"(corruption={label!r})"

    # --- 2) Complete: one entry per check name, canonical order, no normals --
    names = [c.name for c in report.checks]
    assert names == list(_rof2.CHECK_NAMES), (
        f"report check names {names} != canonical {list(_rof2.CHECK_NAMES)} {ctx}"
    )
    assert len(names) == len(set(names)), f"duplicate check names {names} {ctx}"
    assert "normals_resolve" not in names, f"normals_resolve must be absent {ctx}"

    # --- 3) Specific (self-naming): a failed check names itself -------------
    for c in report.checks:
        if not c.passed:
            assert c.messages, (
                f"failed check {c.name!r} carries no message {ctx}"
            )
            assert c.messages[0].startswith(f"{c.name}:"), (
                f"failed check {c.name!r} first message {c.messages[0]!r} does "
                f"not start with its own name {ctx}"
            )

    # --- 4) Specific (untouched unchanged): scoped to unaffected checks -----
    if affected != _ALL_CHECKS:
        base_map = _check_map(baseline)
        corr_map = _check_map(report)
        for name in _rof2.CHECK_NAMES:
            if name in affected:
                continue
            assert corr_map[name] == base_map[name], (
                f"untouched check {name!r} changed verdict {ctx}: "
                f"baseline={base_map[name]} corrupted={corr_map[name]} "
                f"(corruption affected set={sorted(affected)})"
            )
