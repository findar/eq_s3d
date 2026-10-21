"""
tests/test_properties_layout.py
--------------------------------
Layout-tier properties of the M0 Property_Suite: properties of the Zone_Spec the
Layout_Generator produces, proven without a full binary build (no `ZoneBuilder`).

Design reference: `.kiro/specs/zone-generator-m0-hygiene/design.md`,
"Correctness Properties" (P4 here) and "Property modules". Each test carries a
Property_Docstring: the design property tag, the umbrella Pn, and the M0 +
umbrella requirement ids it validates.
"""

from __future__ import annotations

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.zone_spec import ZoneSpec

from .pbt_helpers import scaled
from .strategies import seeds, room_counts, spec_themes, semantic_inputs


# A full layout for up to 30 rooms with the semantic layer can exceed the
# Default_Profile's 200 ms per-example deadline on a cold call (import/JIT
# warmup) -- that's timing variance, not a property failure, so this
# layout-tier test disables the deadline while keeping the 100-example budget
# (scaled by the active profile, per design Req 1.3). It is NOT a build-tier
# test, so no `slow` marker and no `build_settings`.
@settings(deadline=None, max_examples=scaled(100))
@given(
    seed=seeds,
    theme=spec_themes,
    n=room_counts(1, 30),
    locks=st.integers(min_value=0, max_value=5),
    elevation=st.booleans(),
    semantic=semantic_inputs,
)
def test_zonespec_json_roundtrip(seed, theme, n, locks, elevation, semantic):
    """Feature: zone-generator-m0-hygiene, Property 4: ZoneSpec JSON round-trip.

    Umbrella P11. For any Zone_Spec the Layout_Generator produces (themes
    dungeon/city/outdoor, room counts 1-30, locks 0-5, elevation on/off, with
    non-default semantic fields), serialising to JSON and loading it back
    produces a dictionary equal to the JSON-loaded original -- field for field,
    with exact float equality. Because the comparison runs THROUGH JSON on both
    sides, the normalisation is a fixpoint: no tuple-vs-list or float drift
    survives the round-trip.

    Validates: M0 Req 2.4; umbrella Req 11.4.
    """
    plan = ZonePlan(
        name=f"rt{seed}",
        theme=theme,
        room_count=n,
        elevation=elevation,
        locks=locks,
        dungeon_theme=semantic["dungeon_theme"],
        dungeon_race=semantic["dungeon_race"],
        elemental_tint=(semantic["elemental_tint"] or ""),
    )
    spec = plan_to_spec(plan, seed=seed)

    j = json.dumps(spec.to_dict())
    loaded = json.loads(j)
    reserialised = ZoneSpec.from_dict(loaded).to_dict()

    # Normalise the reserialised dict THROUGH JSON too, so both sides are in the
    # same (list-not-tuple) shape and the comparison is a pure fixpoint check
    # with exact float equality (JSON already serialised the floats).
    assert json.loads(json.dumps(reserialised)) == loaded
