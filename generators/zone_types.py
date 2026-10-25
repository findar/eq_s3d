"""Single source of truth for the zone-type vocabulary (wave 2).

The plan, spec, builder, pipeline, server, CLI and web list all read the
constants and helpers defined here, so the set of zone types, the default, the
legacy value mapping and the style-profile mapping live in exactly one place.

Umbrella decision 19: new code uses ``zone_type`` / ``wilderness``; the legacy
``theme`` key and the legacy ``outdoor`` value are accepted on load and mapped
forward here (Req 11.1, 11.2).

This module imports nothing project-level beyond the standard library on
purpose: it is the leaf every other module depends on, so it must have no
inbound coupling of its own. The Enabled set and availability reasons arrive in
wave 4 (see ``design.md`` "Gate and availability").
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
