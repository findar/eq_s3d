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

from hypothesis import example, given, settings
from hypothesis import strategies as st

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.layout import LayoutGenerator
from generators.zone_spec import ZoneSpec

from .pbt_helpers import scaled, room_graph, solvable_walk, _entrance_id
from .strategies import (
    seeds,
    room_counts,
    spec_themes,
    box_themes,
    semantic_inputs,
)


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


def _connected(adj, nodes):
    """Is the adjacency map one connected component over ``nodes``?"""
    if not nodes:
        return True
    start = next(iter(nodes))
    seen = {start}
    stack = [start]
    while stack:
        cur = stack.pop()
        for nxt in adj.get(cur, ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen == set(nodes)


# Same cold-call reasoning as test_zonespec_json_roundtrip: a full layout for up
# to 30 rooms with the semantic layer can brush the Default_Profile's 200 ms
# deadline on a cold call (warmup), which is timing variance rather than a
# property failure. Disable the deadline, keep the 100-example budget (scaled by
# the active profile). Layout-tier (no binary build), so no `slow` marker and no
# `build_settings`.
@settings(deadline=None, max_examples=scaled(100))
@given(
    seed=seeds,
    theme=box_themes,
    n=room_counts(1, 30),
    semantic=semantic_inputs,
)
def test_connectivity_and_roles(seed, theme, n, semantic):
    """Feature: zone-generator-m0-hygiene, Property 5: Layout connectivity and pacing roles.

    Umbrella P3 (single District). For any Zone_Spec the Layout_Generator
    produces on a box theme (dungeon/city), room counts 1-30, with non-default
    semantic fields: the Room_Graph (adjacency derived from the corridors) is a
    single connected component holding exactly ``n`` rooms; exactly one room is
    the entrance; and for ``n >= 2`` exactly one room is the climax and it is a
    different room from the entrance. (At ``n == 1`` the layout makes the single
    room the entrance with no climax, so the climax check only applies for
    ``n >= 2``.)

    Validates: M0 Req 3.1; umbrella Req 1.6.
    """
    plan = ZonePlan(
        name=f"conn{seed}",
        theme=theme,
        room_count=n,
        dungeon_theme=semantic["dungeon_theme"],
        dungeon_race=semantic["dungeon_race"],
        elemental_tint=(semantic["elemental_tint"] or ""),
    )
    spec = plan_to_spec(plan, seed=seed)

    # Exactly n rooms, and the Room_Graph is one connected component over them.
    assert len(spec.rooms) == n
    adj = room_graph(spec)
    room_ids = [r.id for r in spec.rooms]
    assert set(adj) == set(room_ids)
    assert _connected(adj, room_ids)

    # Exactly one entrance.
    entrances = [r for r in spec.rooms if r.role == "entrance"]
    assert len(entrances) == 1

    # For n >= 2: exactly one climax, distinct from the entrance.
    climaxes = [r for r in spec.rooms if r.role == "climax"]
    if n >= 2:
        assert len(climaxes) == 1
        assert climaxes[0].id != entrances[0].id
    else:
        assert climaxes == []

# Same cold-call reasoning as the two tests above: a full gated layout for up to
# 30 rooms with the semantic layer can brush the Default_Profile's 200 ms
# per-example deadline on a cold call (warmup) -- timing variance, not a property
# failure -- so disable the deadline and keep the 100-example budget (scaled by
# the active profile). Layout-tier only (gating never builds the binary and
# never touches geometry, per umbrella P5), so no `slow` marker and no
# `build_settings`. This drives the SAME gated path task 10.3 verified:
# `LayoutGenerator(theme, seed=s).generate(name, room_count=n, locks=k)` runs
# `_apply_gating` internally when locks > 0.
#
# The pinned `@example` is the input task 10.3 found by scanning the real
# generator (the first case where a gate's key_room_id lands on the entrance id,
# i.e. the key-room FALLBACK path): seed=16, dungeon, 5 rooms, 4 locks. For that
# case (expect_fallback=True) the test additionally asserts that at least one
# gate.key_room_id == the entrance id, proving the fallback is exercised and the
# keyed dungeon is still solvable from the entrance.
# The pinned 10.3 input. Its param names match `@given` (`n` for the room
# count), and it carries a neutral `semantic` (empty theme/race, no tint) so it
# reproduces the plain `generate(name, room_count=5, locks=4)` call 10.3 scanned
# -- the case where a gate's key_room_id lands on the entrance id.
@settings(deadline=None, max_examples=scaled(100))
@example(
    seed=16,
    theme="dungeon",
    n=5,
    locks=4,
    semantic={"dungeon_theme": "", "dungeon_race": "", "elemental_tint": None},
    expect_fallback=True,
)
@given(
    seed=seeds,
    theme=box_themes,
    n=room_counts(3, 30),
    locks=st.integers(min_value=1, max_value=5),
    semantic=semantic_inputs,
    expect_fallback=st.just(False),
)
def test_gating_solvable(seed, theme, n, locks, semantic, expect_fallback):
    """Feature: zone-generator-m0-hygiene, Property 6: Gating is solvable.

    Umbrella P4 (single District). For any keyed dungeon the Layout_Generator
    produces on a box theme (dungeon/city), room counts 3-30, 1-5 locks, with
    non-default semantic fields: the gate set is non-empty and no larger than
    the requested lock count (``1 <= len(gates) <= locks``), and a fixpoint walk
    from the entrance -- crossing a gated corridor only once its key room has
    been reached -- visits EVERY room. That is the gating invariant: every key
    sits on the path before its own lock, so the keyed dungeon is always
    solvable.

    The pinned ``@example`` (seed 16 / dungeon / 5 rooms / 4 locks) is the input
    task 10.3 found that drives the key-room FALLBACK: at least one gate keys off
    the entrance room itself. For that case (``expect_fallback=True``) the test
    also asserts ``key_room_id == entrance_id`` for some gate, so the fallback
    path is covered and shown to remain solvable.

    Validates: M0 Req 3.2, 3.6; umbrella Req 1.6.
    """
    # Same gated path task 10.3 verified: locks > 0 triggers `_apply_gating`.
    spec = LayoutGenerator(theme, seed=seed).generate(
        name=f"gate{seed}",
        room_count=n,
        locks=locks,
        dungeon_theme=semantic["dungeon_theme"],
        dungeon_race=semantic["dungeon_race"],
        elemental_tint=(semantic["elemental_tint"] or ""),
    )

    # A keyed dungeon has at least one gate and never more than the requested
    # number of locks.
    gates = spec.gates
    assert 1 <= len(gates) <= locks

    # The gating invariant: every room is reachable from the entrance, crossing
    # each gated corridor only after its key room has been visited. If this ever
    # fails for a generated input it is a REAL gating-solvability bug (umbrella
    # P4), never a reason to weaken the assertion.
    entrance_id = _entrance_id(spec)
    visited = solvable_walk(spec)
    room_ids = {r.id for r in spec.rooms}
    assert visited == room_ids, (
        f"gating not solvable: unreached rooms "
        f"{sorted(room_ids - visited)} (seed={seed}, theme={theme}, "
        f"n={n}, locks={locks})"
    )

    # The pinned fallback case: prove the key-room fallback path is exercised --
    # at least one gate keys off the entrance room itself -- and that the
    # dungeon is still solvable (asserted above).
    if expect_fallback:
        assert any(g.key_room_id == entrance_id for g in gates), (
            "expected the key-room fallback (a gate keyed on the entrance "
            f"id {entrance_id!r}), got key rooms "
            f"{[g.key_room_id for g in gates]}"
        )
