"""Single source of truth for the zone-type vocabulary (wave 2).

The plan, spec, builder, pipeline, server, CLI and web list all read the
constants and helpers defined here, so the set of zone types, the default, the
legacy value mapping and the style-profile mapping live in exactly one place.

Umbrella decision 19: new code uses ``zone_type`` / ``wilderness``; the legacy
``theme`` key and the legacy ``outdoor`` value are accepted on load and mapped
forward here (Req 11.1, 11.2).

This module imports nothing project-level beyond the standard library on
purpose: it is the leaf every other module depends on, so it must have no
inbound coupling of its own. The Enabled set and availability reasons (wave 4,
``design.md`` "Gate and availability") live here too: ``is_enabled`` reads
``ENABLED_ZONE_TYPES`` at call time so tests can monkeypatch the set (Req 3.1),
and ``zone_type_listing`` is what the server's ``/api/zone_types`` serves.
"""

from __future__ import annotations

from typing import Mapping

# The three defined zone types, in canonical listing order. Everything that
# enumerates zone types (schema, web options, CLI choices, server listing)
# derives its order from this tuple.
DEFINED_ZONE_TYPES: tuple[str, ...] = ("dungeon", "city", "wilderness")

# The zone type used when none is supplied (Req 11.2).
DEFAULT_ZONE_TYPE = "dungeon"

# Legacy values accepted on load and mapped forward to the current vocabulary.
# The pre-rename vocabulary spelled wilderness as "outdoor".
LEGACY_ZONE_TYPE_VALUES = {"outdoor": "wilderness"}

# zone_type -> measured style-profile name (styles/<profile>.json). The profile
# file stays styles/outdoor.json: style_profile names a measured profile, not a
# zone type (design "Zone-type vocabulary").
STYLE_PROFILE = {"dungeon": "dungeon", "city": "city", "wilderness": "outdoor"}


def canonical_zone_type(value: object) -> str | None:
    """Lower-cased, legacy-mapped member of ``DEFINED_ZONE_TYPES``, or ``None``.

    Non-string input, or a string that is neither a defined zone type nor a
    known legacy value, yields ``None`` so callers can fall back to the default
    (umbrella Req 11.9).
    """
    if not isinstance(value, str):
        return None
    lowered = value.lower()
    mapped = LEGACY_ZONE_TYPE_VALUES.get(lowered, lowered)
    if mapped in DEFINED_ZONE_TYPES:
        return mapped
    return None


def read_zone_type(d: Mapping[str, object]) -> object:
    """Prefer ``zone_type``, then legacy ``theme``, then the default (Req 11.2).

    Returns the raw stored value unchanged; callers pass it through
    ``canonical_zone_type`` to normalise and validate it.
    """
    if "zone_type" in d:
        return d["zone_type"]
    if "theme" in d:
        return d["theme"]
    return DEFAULT_ZONE_TYPE

# --- Gate and availability (wave 4, Req 3.1, 3.2) --------------------------
#
# A zone type is *offered* only if it is in ENABLED_ZONE_TYPES. Everything that
# gates a zone type (CLI, server, pipeline) reads this one set; there is no
# second "gated" set (Req 3.1). Wilderness joined the set when the open-world
# wilderness milestone closed (zone-generator-wilderness task 11).

# The zone types offered. Kept a frozenset so it can't be mutated in place; a
# test that needs a different gate monkeypatches this whole name, which is why
# is_enabled() re-reads it at call time rather than capturing it.
ENABLED_ZONE_TYPES: frozenset[str] = frozenset({"dungeon", "city", "wilderness"})

# Human-readable reason per DISABLED zone type, explaining why it is unavailable.
# Only disabled zone types need an entry; enabled ones never show a reason.
ZONE_TYPE_REASONS: dict[str, str] = {}

# Fallback reason for a defined-but-disabled zone type with no specific entry in
# ZONE_TYPE_REASONS.
DISABLED_REASON = "Not yet offered: its builds don't pass the traversability sweep."

def enabled_zone_types() -> frozenset[str]:
    """The zone types offered right now. Reads ``ENABLED_ZONE_TYPES`` at call
    time, so a monkeypatched set is honoured."""
    return ENABLED_ZONE_TYPES


def is_enabled(zone_type: object) -> bool:
    """Whether ``zone_type`` is currently offered (Req 3.1).

    Canonicalises the input first (so legacy values and casing resolve), then
    reads ``ENABLED_ZONE_TYPES`` AT CALL TIME — never a value captured at import
    — so a test can monkeypatch the set to a subset and this reflects it.
    Undefined or non-string input is not enabled.
    """
    canonical = canonical_zone_type(zone_type)
    if canonical is None:
        return False
    return canonical in enabled_zone_types()


def zone_type_listing() -> list[dict]:
    """Availability listing for every defined zone type, in canonical order.

    One entry per member of ``DEFINED_ZONE_TYPES`` (canonical listing order),
    each a dict with ``name``, ``enabled`` and ``reason``. Enabled zone types
    carry ``reason = None``; disabled ones carry their ``ZONE_TYPE_REASONS``
    entry, falling back to ``DISABLED_REASON``. This is what the server's
    ``/api/zone_types`` serves (Req 3.2).
    """
    listing: list[dict] = []
    for name in DEFINED_ZONE_TYPES:
        enabled = name in enabled_zone_types()
        reason = None if enabled else ZONE_TYPE_REASONS.get(name, DISABLED_REASON)
        listing.append({"name": name, "enabled": enabled, "reason": reason})
    return listing
