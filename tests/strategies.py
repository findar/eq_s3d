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
# generators.zone_types.DEFINED_ZONE_TYPES; task 10.9 renames the identifier.
DEFINED_THEMES = {"dungeon", "city", "wilderness"}

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


#: The box-geometry themes (M0_Box_Themes): dungeon + city.
box_themes = st.sampled_from(["dungeon", "city"])

#: Every zone type a ZoneSpec may carry (post wave-2 rename).
spec_themes = st.sampled_from(["dungeon", "city", "wilderness"])

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


# Keys outside the ZonePlan schema that `from_dict` must ignore.
_unknown_keys = st.text(min_size=1, max_size=12).filter(
    lambda k: k
    not in {
        "name",
        "theme",
        "room_count",
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
#: to prove normalisation lands every field in its valid domain (Property 12).
zone_plan_dicts = st.builds(
    lambda base, extra: {**base, **extra},
    st.fixed_dictionaries(
        {},
        optional={
            "name": st.text(),
            "theme": _vocab_field(["dungeon", "outdoor", "cave", "city"]),
            "room_count": st.integers(),
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
