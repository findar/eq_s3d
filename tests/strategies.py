"""
tests/strategies.py
-------------------
Shared Hypothesis strategies for the M0 Property_Suite.

Everything the property modules draw from lives here so the generators stay in
one place and the per-test budgets (via ``pbt_helpers.scaled`` / ``build_settings``)
decide how hard to push them. The strategies deliberately mirror the real input
domains of the code under test — vocab fields draw from the actual ``ai.schema``
vocabularies, not ad-hoc literals — so a passing property exercises inputs the
production path can genuinely see.

Design reference: ``.kiro/specs/zone-generator-m0-hygiene/design.md`` section
"Strategies (tests/strategies.py)".
"""

from __future__ import annotations

import random

from hypothesis import strategies as st

from ai.schema import (
    VALID_DUNGEON_RACES,
    VALID_DUNGEON_THEMES,
    VALID_ELEMENTAL_TINTS,
    VALID_REGION_KINDS,
)

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

# The three zone types the generator ships (the Defined set). Post wave-2
# rename the open-air type is "wilderness" (was "outdoor"). Kept equal to
# generators.zone_types.DEFINED_ZONE_TYPES.
DEFINED_ZONE_TYPES = {"dungeon", "city", "wilderness"}

# Words that used to pick the `cave` theme and must now resolve to `dungeon`
# (Property 19 / Req 6.5).
CAVE_WORDS = ("cave", "cavern", "grotto", "underground", "tunnel")

# ---------------------------------------------------------------------------
# Scalar / vocab strategies
# ---------------------------------------------------------------------------

#: A valid generator seed (umbrella uses 31-bit non-negative ints).
seeds = st.integers(min_value=0, max_value=2**31 - 1)


def room_counts(lo: int, hi: int) -> st.SearchStrategy[int]:
    """Room counts in an inclusive ``[lo, hi]`` range (set per criterion)."""
    return st.integers(min_value=lo, max_value=hi)


#: Room counts across the M1 large-zone range, biased so ~half the draws land in
#: the big-zone band. The two disjoint ``one_of`` branches each get roughly equal
#: weight, so ``[13, 30]`` is hit about half the time even though it is the wider
#: interval (Req 5.1 — large-zone connectivity must be exercised, not just the
#: small-room tail a single uniform ``integers(2, 30)`` would favour less often).
room_counts_wide = st.one_of(st.integers(2, 12), st.integers(13, 30))

#: Verticality pinned to flat — the "flat first" pass (tasks 6.2/6.3) proves
#: connectivity with no elevation before the elevation draws return in task 8.
flat_only = st.just("flat")

#: All three verticalities, for the "then elevation" pass (task 8). Same domain
#: as ``verticality``; named separately so the flat-first tests read ``flat_only``
#: and the all-verticality tests read ``verticality_all`` at the call site.
verticality_all = st.sampled_from(["flat", "moderate", "dramatic"])


#: The box-geometry zone types (M0_Box_Themes): dungeon + city.
box_zone_types = st.sampled_from(["dungeon", "city"])

#: A valid Build_Name: lowercase ``[a-z0-9_]+`` (the umbrella Build_Name
#: alphabet, matching ``generators.builder.BUILD_NAME_RE`` — ``^[a-z0-9_]+$``).
#: Every artifact (archive, TER/ZON entries, ZON model ref, GLB, Sidecar, SVG)
#: is named from this stem, so the Format_Checker's ``name_consistent`` check is
#: exercised across many legal names rather than one fixed literal. Includes the
#: server zone-id shape ``gen_<ts>_<hex6>`` as an explicit sample so the generated
#: id form is covered too.
build_names = st.one_of(
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=1, max_size=24),
    st.sampled_from(["gen_1700000000_a1b2c3", "zone", "z0", "test_build_1"]),
)

# ---------------------------------------------------------------------------
# Enabled-set gating (Property 7 / Req 3.1, 3.3, 3.4)
# ---------------------------------------------------------------------------

#: Non-empty subsets of ``DEFINED_ZONE_TYPES`` to install as the Enabled set in
#: the availability property. Every subset INCLUDES ``dungeon`` because the
#: server substitutes a prompt-planned disabled zone type to ``dungeon``
#: (``DEFAULT_ZONE_TYPE``): if the substitution target were itself disabled the
#: prompt path could not yield an enabled zone. The members are canonical
#: ``DEFINED_ZONE_TYPES`` names, so the drawn set is a valid monkeypatch value
#: for ``generators.zone_types.ENABLED_ZONE_TYPES``. Emitted as a ``frozenset``
#: to match the production type (``is_enabled``/``zone_type_listing`` read it as
#: a membership set at call time).
_OPTIONAL_ZONE_TYPES = sorted(DEFINED_ZONE_TYPES - {"dungeon"})  # city, wilderness
enabled_subsets = st.sets(
    st.sampled_from(_OPTIONAL_ZONE_TYPES),
    max_size=len(_OPTIONAL_ZONE_TYPES),
).map(lambda extra: frozenset({"dungeon", *extra}))

#: Zone-type NAMES a stubbed planner / controls request may pick: the three
#: defined names plus the removed ``cave`` word (which ``canonical_zone_type``
#: maps to ``None`` — an undefined type that is never enabled) and the legacy
#: ``outdoor`` value (canonicalises to ``wilderness``). This spans in-domain,
#: legacy, and undefined names so the gate is exercised on all three.
zone_type_names = st.sampled_from(
    sorted(DEFINED_ZONE_TYPES) + ["cave", "outdoor"]
)

#: Every zone type a ZoneSpec may carry (post wave-2 rename).
spec_zone_types = st.sampled_from(["dungeon", "city", "wilderness"])

#: Floor-height variation, as ``ai.schema.ZonePlan.verticality`` accepts.
verticality = st.sampled_from(["flat", "moderate", "dramatic"])

#: Semantic / content-layer inputs. Each field includes its "unset" sentinel so
#: both the default and the realised-content paths are exercised.
semantic_inputs = st.fixed_dictionaries(
    {
        "dungeon_theme": st.sampled_from([""] + list(VALID_DUNGEON_THEMES)),
        "dungeon_race": st.sampled_from([""] + list(VALID_DUNGEON_RACES)),
        "elemental_tint": st.sampled_from(
            [None, ""] + list(VALID_ELEMENTAL_TINTS)
        ),
    }
)

# ---------------------------------------------------------------------------
# ZonePlan dicts (Property 12 / Req 3.5)
# ---------------------------------------------------------------------------

# A free-text field: a plain string, mixed with the valid vocabulary so both
# garbage and in-domain values are hit.
def _vocab_field(vocab) -> st.SearchStrategy:
    return st.one_of(st.text(), st.sampled_from(list(vocab)))


# Keys outside the ZonePlan schema that `from_dict` must ignore. ``rooms`` is
# excluded too: it is a control ALIAS (of ``room_count``) emitted on purpose
# below, so it must not also surface as a random junk key that `from_dict`
# silently drops.
_unknown_keys = st.text(min_size=1, max_size=12).filter(
    lambda k: k
    not in {
        "name",
        "zone_type",
        "theme",
        "room_count",
        "rooms",
        "size",
        "elevation",
        "verticality",
        "regions",
        "locks",
        "dungeon_theme",
        "dungeon_race",
        "elemental_tint",
        "mood",
        "prompt",
    }
)

#: Loosely-typed dicts covering every ``ZonePlan`` field (plus junk keys), used
#: to prove normalisation lands every field in its valid domain (Property 12)
#: and the legacy-vocabulary load round-trip (M1-P3, task 10.10).
#:
#: The zone type can be keyed the NEW way (``zone_type``) or the LEGACY way
#: (``theme``), or both. Task 10.9 left this strategy emitting only the legacy
#: ``theme`` key and deferred ``zone_type`` to task 10.10; both are optional
#: here, so a drawn dict may carry ``zone_type`` alone, ``theme`` alone, both
#: (possibly disagreeing — the load boundary must let ``zone_type`` win), or
#: neither (the default applies). ``theme`` draws the legacy value set (which
#: includes ``outdoor`` and the removed ``cave``); ``zone_type`` draws the
#: current ``DEFINED_ZONE_TYPES`` plus the legacy ``outdoor`` so the mapping is
#: exercised from both keys.
#:
#: Task 17.3 also emits the two CONTROL-ALIAS keys the controls path
#: (``ZonePlan.from_controls``) understands, so both entry paths (P12) see
#: undefined/legacy/alias values:
#:   * ``rooms`` — alias of ``room_count`` (same loosely-typed integer domain);
#:   * ``elevation`` — the legacy boolean (already drawn above). ``from_controls``
#:     reads ``elevation: false`` without a ``verticality`` as ``flat``; emitting
#:     it as a plain boolean next to an optional ``verticality`` exercises both
#:     the translation and the "verticality present wins" branch.
#: ``rooms`` and ``room_count`` are both optional, so a draw may carry the alias
#: alone (from_controls folds it in; from_dict never sees it), the plan key alone,
#: or both (the plan key must win on both paths).
zone_plan_dicts = st.builds(
    lambda base, extra: {**base, **extra},
    st.fixed_dictionaries(
        {},
        optional={
            "name": st.text(),
            "zone_type": _vocab_field(sorted(DEFINED_ZONE_TYPES) + ["outdoor"]),
            "theme": _vocab_field(["dungeon", "outdoor", "cave", "city"]),
            "room_count": st.integers(),
            "rooms": st.integers(),
            "size": _vocab_field(["small", "medium", "large", "huge"]),
            "elevation": st.booleans(),
            "verticality": _vocab_field(["flat", "moderate", "dramatic"]),
            "regions": st.lists(
                st.one_of(st.text(), st.sampled_from(list(VALID_REGION_KINDS)))
            ),
            "locks": st.integers(),
            "dungeon_theme": _vocab_field(VALID_DUNGEON_THEMES),
            "dungeon_race": _vocab_field(VALID_DUNGEON_RACES),
            "elemental_tint": _vocab_field(VALID_ELEMENTAL_TINTS),
            "mood": st.text(),
            "prompt": st.text(),
        },
    ),
    st.dictionaries(
        _unknown_keys,
        st.one_of(st.none(), st.integers(), st.text()),
    ),
)

# ---------------------------------------------------------------------------
# PFS archive strategies (Properties 13 / 14)
# ---------------------------------------------------------------------------

# Printable ASCII filenames minus the path separators. 1..64 chars.
_PFS_ALPHABET = "".join(
    c
    for c in (chr(i) for i in range(0x20, 0x7F))
    if c not in ("/", "\\")
)

#: A single PFS filename.
pfs_names = st.text(alphabet=_PFS_ALPHABET, min_size=1, max_size=64)

# Payload descriptor: (length, byte_seed). The actual bytes are expanded
# deterministically from byte_seed so the Hypothesis byte buffer stays small
# (design finding 7 — drawing 24 KiB byte-by-byte blows the buffer).
_payload_length = st.one_of(
    st.sampled_from([0, 1, 8191, 8192, 8193, 16384, 16385, 24576, 24577]),
    st.integers(min_value=0, max_value=24577),
)
_payload_desc = st.tuples(_payload_length, st.integers(min_value=0, max_value=2**32 - 1))

_MAX_ENTRIES = 2000


def _bytes_for(length: int, byte_seed: int) -> bytes:
    """Deterministic payload bytes for a descriptor."""
    return random.Random(byte_seed).randbytes(length)


@st.composite
def pfs_entries(draw) -> dict:
    """A PFS archive as a name -> bytes map.

    Two tiers keep the Hypothesis buffer small while still reaching the
    2000-entry / multi-chunk-name-block regime:

    * *explicit* entries draw a (name, payload-descriptor) list directly, so
      shrinking can minimise individual names and payloads;
    * *bulk* entries draw only a count and a seed, then synthesise names and
      small payloads from a seeded RNG, deduplicating case-insensitively against
      everything drawn so far.
    """
    explicit = draw(
        st.lists(
            st.tuples(pfs_names, _payload_desc),
            max_size=20,
            unique_by=lambda e: e[0].lower(),
        )
    )

    entries: dict[str, bytes] = {}
    seen_lower: set[str] = set()
    for name, (length, byte_seed) in explicit:
        entries[name] = _bytes_for(length, byte_seed)
        seen_lower.add(name.lower())

    remaining = _MAX_ENTRIES - len(entries)
    bulk_n = draw(
        st.integers(min_value=0, max_value=max(0, remaining)).map(int)
        if remaining <= 0
        else st.one_of(
            st.just(0),
            st.just(1),
            st.just(remaining),
            st.integers(min_value=0, max_value=remaining),
        )
    )
    bulk_seed = draw(st.integers(min_value=0, max_value=2**32 - 1))

    rng = random.Random(bulk_seed)
    attempts = 0
    added = 0
    # Generate names from the same alphabet, lengths 1..64, dedup
    # case-insensitively. Bounded attempts so a pathological collision run
    # can't spin forever.
    while added < bulk_n and attempts < bulk_n * 4 + 16:
        attempts += 1
        length = rng.randint(1, 64)
        name = "".join(rng.choice(_PFS_ALPHABET) for _ in range(length))
        if name.lower() in seen_lower:
            continue
        seen_lower.add(name.lower())
        payload_len = rng.randint(0, 64)
        entries[name] = rng.randbytes(payload_len)
        added += 1

    return entries


# ---------------------------------------------------------------------------
# CORS origins (Property 18 / Req 9.3)
# ---------------------------------------------------------------------------

# The set of origins the server will grant CORS to. `server.app.WEB_APP_ORIGINS`
# is introduced in task 7.1; until that lands it may not exist, so fall back to
# the design's literal tuple. The `origins_outside` strategy only needs it to
# filter out legitimate origins, and a late import keeps strategies.py importable
# before 7.1.
#
# DEPENDENCY NOTE (for task 7.1): server/app.py must expose WEB_APP_ORIGINS with
# exactly this membership, or the filter below drifts from the real allow-list.
_WEB_APP_ORIGINS_FALLBACK = (
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def _web_app_origins() -> frozenset[str]:
    try:
        from server.app import WEB_APP_ORIGINS  # type: ignore

        return frozenset(WEB_APP_ORIGINS)
    except Exception:
        return frozenset(_WEB_APP_ORIGINS_FALLBACK)


# Near-miss origins: right host/port/scheme family but subtly wrong (different
# port, scheme, host case, trailing slash, literal "null", IPv6 loopback).
_ORIGIN_NEAR_MISSES = [
    "http://localhost:5174",
    "https://localhost:5173",
    "http://localhost:5173/",
    "http://LOCALHOST:5173",
    "null",
    "http://[::1]:8000",
]

_ORIGIN_ALPHABET = "".join(chr(i) for i in range(0x21, 0x7F)) + " "

#: Origin values that must NOT receive a CORS grant: random printable strings
#: plus deliberate near-misses, filtered of anything actually allowed.
origins_outside = st.one_of(
    st.text(alphabet=_ORIGIN_ALPHABET, min_size=1, max_size=64),
    st.sampled_from(_ORIGIN_NEAR_MISSES),
).filter(lambda o: o not in _web_app_origins())


# ---------------------------------------------------------------------------
# Archive corruptions (Property 14 / M1-P5 / Req 9.3)
# ---------------------------------------------------------------------------
#
# A corruption is a transform applied to a VALID built ``.eqg``'s bytes to make
# the RoF2 Format_Checker (``analyzer.rof2check.check_eqg``) see a damaged
# archive. ``archive_corruptions`` draws one such transform; the Property-14
# test (``test_properties_core.py::test_format_checker_total``) applies it to a
# freshly built small dungeon and asserts the checker is TOTAL (never raises,
# one entry per check name) and SPECIFIC (a failed check names itself; a check
# whose inputs the corruption did not touch reports the same verdict as on the
# clean archive).
#
# Each corruption carries the set of check names its damage may legitimately
# reach (``affected``), so the "untouched checks unchanged" assertion can be
# scoped: a corruption that makes the archive / TER / ZON unreadable also flips
# that input's DEPENDENTS to skipped, which is a legitimate change — those
# dependents are listed in ``affected`` too. A corruption marked with the
# sentinel ``ALL_CHECKS`` (generic byte garbage that can cascade anywhere) is
# exempt from the untouched-check comparison entirely; it still exercises
# totality + presence + self-naming.
#
# The set mirrors the design's Property-14 list
# (``.kiro/specs/zone-generator-m1-controls-traversability/design.md``):
#   truncate at an offset, flip bytes in a range, drop an entry, rename an
#   entry, set a wrong CRC, replace the TER or ZON entry with random bytes,
#   shrink a DDS dimension to a non-power-of-two, set a polygon's material to −1
#   or past the end — plus a few neighbours that each pin a specific check
#   (zero the header, break the ZON model ref, push a coordinate past MAX_COORD,
#   break name consistency via the Sidecar).

import struct as _struct

from core.pfs import (
    PfsArchive as _PfsArchive,
    RawEntry as _RawEntry,
    _DIR_SENTINEL_CRC as _PFS_SENTINEL_CRC,
    _PFS_MAGIC as _PFS_MAGIC_BYTES,
    read_directory as _read_directory,
)
from core.ter import (
    PROP_DIFFUSE as _PROP_DIFFUSE,
    PROP_TYPE_STRING as _PROP_TYPE_STRING,
    TerFile as _TerFile,
)
from core.zon import ZonFile as _ZonFile

#: Sentinel ``affected`` value: this corruption may cascade to ANY check, so the
#: untouched-check comparison is skipped for it (totality / presence / naming
#: are still asserted).
ALL_CHECKS = frozenset({"*"})


def _ter_entry_name(build: str) -> str:
    return f"ter_{build.lower()}.ter"


def _zon_entry_name(build: str) -> str:
    return f"{build.lower()}.zon"


def _rebuild_with(build: str, mutate) -> "callable":
    """Return a transform that parses the eqg to a ``PfsArchive``, lets
    ``mutate(arc)`` change it, and re-serialises. ``mutate`` may return a new
    archive or mutate in place."""

    def _xf(data: bytes) -> bytes:
        arc = _PfsArchive.from_bytes(data)
        result = mutate(arc)
        if result is not None:
            arc = result
        return arc.to_bytes()

    return _xf


# --- Archive-level byte corruptions (generic / specific pfs_reads) ----------

def _c_truncate(frac: float):
    def _xf(data: bytes) -> bytes:
        n = max(0, int(len(data) * frac))
        return data[:n]
    # A truncation lands somewhere in the deflated payload / directory: the
    # archive no longer reads cleanly, so everything may cascade.
    return ("truncate", _xf, ALL_CHECKS)


def _c_zero_header():
    def _xf(data: bytes) -> bytes:
        b = bytearray(data)
        for i in range(min(12, len(b))):
            b[i] = 0
        return bytes(b)
    # Zeroed magic/version/dir-offset: pfs_reads fails, every dependent skips.
    return ("zero_header", _xf, ALL_CHECKS)


def _c_flip_bytes(seed: int):
    def _xf(data: bytes) -> bytes:
        if len(data) <= 16:
            return data
        b = bytearray(data)
        rng = random.Random(seed)
        # Flip a short run of bytes somewhere in the deflated body (after the
        # 12-byte header, before the final footer) so a payload/stream is hit.
        lo = 12
        hi = max(13, len(b) - 9)
        start = rng.randrange(lo, hi)
        for i in range(start, min(start + 8, len(b))):
            b[i] ^= 0xFF
        return bytes(b)
    return ("flip_bytes", _xf, ALL_CHECKS)


# --- Directory / entry corruptions ------------------------------------------

def _c_drop_entry(which: str):
    """Drop a required member (the TER or the ZON) from the archive."""

    def _mutate(build):
        target = _ter_entry_name(build) if which == "ter" else _zon_entry_name(build)

        def _m(arc: _PfsArchive):
            arc.remove(target)
        return _m

    # Dropping the TER makes required_files + name_consistent fail and every
    # TER-dependent check skip; dropping the ZON hits required_files,
    # zon_roundtrip, zon_model_ref and name_consistent.
    if which == "ter":
        affected = frozenset({
            "required_files", "ter_roundtrip", "material_indices",
            "diffuse_textures", "collision_policy", "safe_point",
            "bounds_sane", "name_consistent",
        })
    else:
        affected = frozenset({
            "required_files", "zon_roundtrip", "zon_model_ref", "name_consistent",
        })
    return (f"drop_{which}_entry", _mutate, affected)


def _c_rename_entry(which: str):
    """Rename a required member so required_files/name_consistent see it gone."""

    def _mutate(build):
        target = _ter_entry_name(build) if which == "ter" else _zon_entry_name(build)

        def _m(arc: _PfsArchive):
            for f in arc.files:
                if f.name.lower() == target:
                    f.name = "renamed_" + f.name
                    break
        return _m

    if which == "ter":
        affected = frozenset({
            "required_files", "ter_roundtrip", "material_indices",
            "diffuse_textures", "collision_policy", "safe_point",
            "bounds_sane", "name_consistent",
        })
    else:
        affected = frozenset({
            "required_files", "zon_roundtrip", "zon_model_ref", "name_consistent",
        })
    return (f"rename_{which}_entry", _mutate, affected)


def _c_wrong_crc():
    """Set a directory record's CRC to a value that matches no name, so the
    entry survives as data but loses its name (name block has no entry for it).
    Done at the raw byte level on the directory block."""

    def _xf(data: bytes) -> bytes:
        entries, errors = _read_directory(data)
        if errors or not entries:
            return data
        (dir_offset,) = _struct.unpack_from("<I", data, 0)
        (file_count,) = _struct.unpack_from("<I", data, dir_offset)
        b = bytearray(data)
        # Flip the CRC of the first NON-sentinel directory record to a value no
        # filename hashes to. Record i sits at dir_offset + 4 + i*12.
        for i in range(file_count):
            rec_at = dir_offset + 4 + i * 12
            (crc,) = _struct.unpack_from("<I", b, rec_at)
            if crc != _PFS_SENTINEL_CRC:
                _struct.pack_into("<I", b, rec_at, crc ^ 0xA5A5A5A5)
                break
        return bytes(b)

    # A record whose CRC matches no name: that member is unnamed, so
    # required_files and name_consistent notice the required file "missing",
    # and its TER/ZON-dependent checks skip. Scope to all members' dependents.
    affected = frozenset({
        "required_files", "ter_roundtrip", "zon_roundtrip", "zon_model_ref",
        "material_indices", "diffuse_textures", "collision_policy",
        "safe_point", "bounds_sane", "name_consistent",
    })
    return ("wrong_crc", ("raw", _xf), affected)


def _c_replace_member_random(which: str, seed: int):
    """Replace the TER or ZON member's payload with random bytes."""

    def _mutate(build):
        target = _ter_entry_name(build) if which == "ter" else _zon_entry_name(build)
        rng = random.Random(seed)
        blob = rng.randbytes(256)

        def _m(arc: _PfsArchive):
            arc.add(target, blob)
        return _m

    if which == "ter":
        # Random TER: it no longer parses -> ter_roundtrip fails and every
        # TER-derived check skips. required_files/zon unaffected.
        affected = frozenset({
            "ter_roundtrip", "material_indices", "diffuse_textures",
            "collision_policy", "safe_point", "bounds_sane",
        })
    else:
        # Random ZON: zon_roundtrip fails, zon_model_ref skips, name_consistent
        # can no longer read the model ref.
        affected = frozenset({"zon_roundtrip", "zon_model_ref", "name_consistent"})
    return (f"replace_{which}_random", _mutate, affected)


# --- TER-content corruptions (parse, mutate the model, re-serialise) --------

def _c_bad_material_index(build_rel: int):
    """Set a polygon's material index to −1 or past the end of the material
    list, so material_indices fails but the TER still round-trips."""

    def _mutate(build):
        target = _ter_entry_name(build)

        def _m(arc: _PfsArchive):
            raw = arc.get(target)
            ter = _TerFile.from_bytes(raw, name=build.lower())
            if ter.polygons:
                if build_rel < 0:
                    ter.polygons[0].material = -1
                else:
                    ter.polygons[0].material = len(ter.materials) + 5
            arc.add(target, ter.to_bytes())
        return _m

    # Only material_indices should flip (and collision_policy reads the material
    # name of a passable poly — a bad index can change its lookup, so scope it
    # in too, conservatively).
    affected = frozenset({"material_indices", "collision_policy"})
    kind = "neg" if build_rel < 0 else "over"
    return (f"material_index_{kind}", _mutate, affected)


def _c_coord_past_max():
    """Push a TER vertex coordinate past MAX_COORD so bounds_sane fails while
    the TER still round-trips and materials stay valid."""

    def _mutate(build):
        target = _ter_entry_name(build)

        def _m(arc: _PfsArchive):
            raw = arc.get(target)
            ter = _TerFile.from_bytes(raw, name=build.lower())
            if ter.vertices:
                ter.vertices[0].x = 40000.0  # > MAX_COORD (30000)
            arc.add(target, ter.to_bytes())
        return _m

    # Moving a vertex far out can also drag the safe-point floor and the DDS /
    # collision are untouched. safe_point reads geometry near the spec safe
    # point, which is unlikely to be vertex 0, but scope it in conservatively.
    affected = frozenset({"bounds_sane", "safe_point"})
    return ("coord_past_max", _mutate, affected)


def _c_shrink_dds_dimension():
    """Rewrite a diffuse DDS member's width to a non-power-of-two so
    diffuse_textures fails. The DDS entry is a packed member named by the
    material's e_TextureDiffuse0 property."""

    def _mutate(build):
        ter_name = _ter_entry_name(build)

        def _m(arc: _PfsArchive):
            raw = arc.get(ter_name)
            ter = _TerFile.from_bytes(raw, name=build.lower())
            dds_name = None
            for mat in ter.materials:
                for prop in mat.properties:
                    if prop.name == _PROP_DIFFUSE and prop.type == _PROP_TYPE_STRING:
                        dds_name = prop.value_s
                        break
                if dds_name:
                    break
            if not dds_name:
                return
            dds = arc.get(dds_name)
            if dds is None or len(dds) < 20 or dds[:4] != b"DDS ":
                return
            b = bytearray(dds)
            # width is at file offset 16 (after 4-byte magic + 12 into the
            # 124-byte header). Set it to 130 (not a power of two).
            _struct.pack_into("<I", b, 16, 130)
            arc.add(dds_name, bytes(b))
        return _m

    affected = frozenset({"diffuse_textures"})
    return ("shrink_dds_dimension", _mutate, affected)


# --- ZON-content corruptions ------------------------------------------------

def _c_break_model_ref():
    """Change the ZON models[0] away from TER_<NAME>.TER so zon_model_ref and
    name_consistent fail while zon_roundtrip still holds."""

    def _mutate(build):
        target = _zon_entry_name(build)

        def _m(arc: _PfsArchive):
            raw = arc.get(target)
            zon = _ZonFile.from_bytes(raw)
            if zon.models:
                zon.models[0] = "WRONG_MODEL.TER"
            arc.add(target, zon.to_bytes())
        return _m

    affected = frozenset({"zon_model_ref", "name_consistent"})
    return ("break_model_ref", _mutate, affected)


# --- Sidecar corruption (name_consistent) -----------------------------------

def _c_break_sidecar_name():
    """A Sidecar-side corruption: the test rewrites the Sidecar ``name`` to a
    mismatching value. Expressed as a sentinel the test recognises (the eqg
    bytes are returned unchanged)."""

    def _xf(data: bytes) -> bytes:
        return data

    # The test detects the "sidecar" kind and edits the .zone.json instead.
    return ("break_sidecar_name", ("sidecar", _xf), frozenset({"name_consistent"}))


def _corruption_list(build: str) -> list:
    """Materialise every corruption for a given Build_Name as
    ``(label, apply, affected)`` where ``apply(eqg_bytes) -> eqg_bytes`` (or a
    special ``("sidecar", fn)`` the test handles)."""
    out: list = []

    # Archive-level byte corruptions.
    for label, xf, aff in (
        _c_truncate(0.5),
        _c_truncate(0.9),
        _c_zero_header(),
        _c_flip_bytes(1),
        _c_flip_bytes(2),
    ):
        out.append((label, xf, aff))

    # Directory / entry corruptions that need the Build_Name.
    for maker in (
        _c_drop_entry("ter"),
        _c_drop_entry("zon"),
        _c_rename_entry("ter"),
        _c_rename_entry("zon"),
        _c_replace_member_random("ter", 11),
        _c_replace_member_random("zon", 12),
        _c_bad_material_index(-1),
        _c_bad_material_index(1),
        _c_coord_past_max(),
        _c_shrink_dds_dimension(),
        _c_break_model_ref(),
    ):
        label, mutate, aff = maker
        out.append((label, _rebuild_with(build, mutate(build)), aff))

    # wrong_crc operates on raw bytes (directory record), not via a rebuild.
    label, (kind, xf), aff = _c_wrong_crc()
    out.append((label, xf, aff))

    # Sidecar-name corruption: the test edits the .zone.json, not the eqg.
    label, (kind, xf), aff = _c_break_sidecar_name()
    out.append(("__sidecar__" + label, xf, aff))

    return out


def archive_corruptions(build: str) -> st.SearchStrategy:
    """A Hypothesis strategy over the Property-14 corruption set for a given
    Build_Name ``build``. Draws one ``(label, apply, affected)`` tuple:

      * ``label`` — a stable id for the corruption (for diagnostics / events);
        a ``__sidecar__`` prefix marks the Sidecar-name corruption the test
        must apply to the ``.zone.json`` instead of the ``.eqg`` bytes.
      * ``apply`` — ``apply(eqg_bytes) -> eqg_bytes`` (for the ``__sidecar__``
        one it is the identity; the test edits the Sidecar directly).
      * ``affected`` — the set of check names whose verdict the corruption may
        legitimately change. ``ALL_CHECKS`` (``{"*"}``) means "may cascade
        anywhere" — the test then skips the untouched-check comparison for that
        draw but still asserts totality, presence and self-naming.

    The build is passed in because the TER/ZON entry names and the ZON model
    ref are all derived from the Build_Name, so the entry-targeting corruptions
    need it.
    """
    return st.sampled_from(_corruption_list(build))
