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
from ai.rule_planner import RulePlanner, _ZONE_TYPE_WORDS
from ai.schema import ZonePlan
from generators.geometry import MAX_SEG_RISE, build_mesh
from generators.layout import LayoutGenerator
from generators.zone_spec import ZoneSpec

from .pbt_helpers import (
    scaled,
    room_graph,
    solvable_walk,
    run_for,
    opening_floor_z,
    _entrance_id,
)
from .strategies import (
    seeds,
    room_counts,
    room_counts_wide,
    spec_zone_types,
    box_zone_types,
    verticality,
    verticality_all,
    semantic_inputs,
    zone_plan_dicts,
    CAVE_WORDS,
    DEFINED_ZONE_TYPES,
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
    zone_type=spec_zone_types,
    n=room_counts(1, 30),
    locks=st.integers(min_value=0, max_value=5),
    elevation=st.booleans(),
    semantic=semantic_inputs,
)
def test_zonespec_json_roundtrip(seed, zone_type, n, locks, elevation, semantic):
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
        zone_type=zone_type,
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
    zone_type=box_zone_types,
    n=room_counts(1, 30),
    semantic=semantic_inputs,
)
def test_connectivity_and_roles(seed, zone_type, n, semantic):
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
        zone_type=zone_type,
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
    zone_type="dungeon",
    n=5,
    locks=4,
    semantic={"dungeon_theme": "", "dungeon_race": "", "elemental_tint": None},
    expect_fallback=True,
)
@given(
    seed=seeds,
    zone_type=box_zone_types,
    n=room_counts(3, 30),
    locks=st.integers(min_value=1, max_value=5),
    semantic=semantic_inputs,
    expect_fallback=st.just(False),
)
def test_gating_solvable(seed, zone_type, n, locks, semantic, expect_fallback):
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
    spec = LayoutGenerator(zone_type, seed=seed).generate(
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
        f"{sorted(room_ids - visited)} (seed={seed}, theme={zone_type}, "
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


# Same cold-call reasoning as the tests above: a full layout for up to 30 rooms
# with the semantic + elevation layer can brush the Default_Profile's 200 ms
# per-example deadline on a cold call (warmup) -- timing variance, not a property
# failure -- so disable the deadline and keep the 100-example budget (scaled by
# the active profile, per design Req 1.3). Layout-tier only (`plan_to_spec`
# drives the Layout_Generator, never a binary build and never geometry), so no
# `slow` marker and no `build_settings`.
#
# The known suspect (per task 10.5 / 13.1) is a semantic `sink` with elevation
# OFF. The semantic layer is drawn in full on purpose: dropping it, weakening
# the bound, or assuming the sink case away would defeat the whole point of this
# property, which exists to catch exactly that. If any input fails, that is a
# REAL elevation bug to report, never a reason to loosen the assertion.
@settings(deadline=None, max_examples=scaled(100))
@given(
    seed=seeds,
    zone_type=box_zone_types,
    n=room_counts(2, 30),
    vert=verticality,
    elevation=st.booleans(),
    semantic=semantic_inputs,
)
def test_elevation_grade_cap(seed, zone_type, n, vert, elevation, semantic):
    """Feature: zone-generator-m0-hygiene, Property 7: Elevation grade cap.

    Umbrella P6. For any Zone_Spec `ai.expand.plan_to_spec` produces on a box
    theme (dungeon/city), room counts 2-30, any verticality
    (flat/moderate/dramatic), elevation on or off, and with non-default semantic
    content: EVERY corridor -- tree edges AND loop (non-tree) edges alike --
    rises no more steeply than the generator's walkable grade cap. Concretely,
    for each corridor connecting rooms ``a`` and ``b``::

        abs(from_z - to_z) <= run_for(..., a, b) * 0.5 + 0.01

    where ``run_for`` calls the production ``LayoutGenerator._elevation_run`` for
    that corridor's two rooms, ``0.5`` is ``max_grade`` (a slope of ~26.6 deg,
    comfortably under the traversability agent's 40 deg walkable-slope cap), and
    ``0.01`` is a float tolerance. Loop edges are explicitly in scope: a loop
    corridor joins two rooms placed down separate BFS paths, so its own run never
    constrained their Z gap during ``_assign_elevation`` -- the historic
    cliff-corridor bug -- and ``_relax_elevation`` must have pulled both ends back
    into every neighbour's walkable band. Checking every corridor, not just tree
    edges, is what proves that relaxation held.

    Validates: M0 Req 3.3; umbrella Req 1.6.
    """
    plan = ZonePlan(
        name=f"grade{seed}",
        zone_type=zone_type,
        room_count=n,
        elevation=elevation,
        verticality=vert,
        dungeon_theme=semantic["dungeon_theme"],
        dungeon_race=semantic["dungeon_race"],
        elemental_tint=(semantic["elemental_tint"] or ""),
    )
    spec = plan_to_spec(plan, seed=seed)

    # Resolve each corridor's two endpoint rooms by id so the run is computed
    # from the SAME RoomSpecs the generator used. `plan.size` (default "medium")
    # is the footprint scale plan_to_spec applied via _SIZE_SCALE.
    rooms_by_id = {r.id: r for r in spec.rooms}

    for c in spec.corridors:
        a = rooms_by_id.get(c.from_room)
        b = rooms_by_id.get(c.to_room)
        # Corridors in this layout always join two real rooms; if that ever
        # changes the lookup guards it rather than crashing the property.
        assert a is not None and b is not None, (
            f"corridor {c.id} references unknown room(s) "
            f"{c.from_room!r}/{c.to_room!r}"
        )

        run = run_for(spec, zone_type, n, plan.size, a, b)
        dz = abs(c.from_z - c.to_z)
        cap = run * 0.5 + 0.01

        # If this fails it is a REAL elevation grade bug (umbrella P6) -- the
        # corridor is a cliff steeper than the walkable cap. Report the
        # counterexample (per task 13.1); do NOT weaken the bound.
        assert dz <= cap, (
            f"corridor {c.id} exceeds the grade cap: |dz|={dz:.4f} > "
            f"run*0.5+0.01={cap:.4f} (run={run:.4f}); seed={seed}, "
            f"theme={zone_type}, n={n}, verticality={vert!r}, "
            f"elevation={elevation}, semantic={semantic}, "
            f"rooms {c.from_room!r}->{c.to_room!r}"
        )

# --- Property 7 (constructed conflict case): relax-conflict fallback ----------
#
# This is an EXAMPLE test, not a `@given` property. Generation has no observable
# that forces `_relax_elevation`'s conflicting-neighbours (midpoint) branch, so
# per design "Fallback-path examples -> Relax conflict fallback (Req 3.7)" the
# branch is driven directly on a constructed room set. No `@settings`/`@given`,
# no binary build, no `slow` marker.
#
# Construction mirrors the design exactly: `LayoutGenerator("dungeon", seed=0)`
# with `_apply_room_scale(3)`, three 200x200 rooms strung along +X with 40 u
# wall gaps (so each corridor is straight and `_elevation_run` is the single
# leg; here run = 44, cap = run * max_grade = 22). Rooms: E (entrance, z 0),
# B (z 0), C (z 200). `adj = {B: [E, C], C: [B], E: [B]}` with B inserted FIRST,
# because B is then the first non-entrance node the sweep visits, so the
# `lo > hi` midpoint branch runs on pass 1.
def test_relax_conflict_fallback():
    """Feature: zone-generator-m0-hygiene, Property 7: Elevation grade cap (constructed conflict case).

    Umbrella P6. Drives `LayoutGenerator._relax_elevation`'s conflicting-
    neighbours fallback -- the ``lo > hi`` midpoint branch -- on a constructed
    room set, because generation exposes no input that forces it. Three 200x200
    rooms sit on the X axis with 40 u wall gaps (straight corridors, run 44,
    cap ``run * max_grade`` = 22): E (entrance, z 0), B (z 0) and C (z 200), with
    ``adj`` listing B first so B is the first non-entrance node the sweep visits.

    Precondition (proves the branch runs): with B at its initial z, the two
    walkable Z bands B must satisfy -- ``[E.z - cap, E.z + cap]`` from the E-B
    corridor and ``[C.z - cap, C.z + cap]`` from the B-C corridor -- are
    DISJOINT, so no single z can satisfy both neighbours and ``_relax_elevation``
    must take the ``lo > hi`` midpoint branch.

    Postcondition: after ``gen._relax_elevation(rooms, adj, entrance)`` every
    adjacent pair satisfies ``abs(dz) <= run * 0.5 + 0.01``, run being
    ``gen._elevation_run`` for that pair. The relaxation compresses the conflict
    down to within the grade cap's thin tolerance -- the exact case Req 3.7
    calls out. A failure here is a REAL fallback bug; the fix goes at the root of
    the relaxation, never by widening the 0.01 tolerance.

    Validates: M0 Req 3.7; umbrella Req 1.6.
    """
    from generators.zone_spec import RoomSpec

    gen = LayoutGenerator("dungeon", seed=0)
    gen._apply_room_scale(3)

    # Three 200x200 rooms strung along +X with 40 u wall gaps (centre spacing
    # 200 + 40 = 240), all on y = 0 so every corridor is a straight single leg.
    entrance = 0
    e_room = RoomSpec(id="E", center_x=0.0, center_y=0.0, floor_z=0.0,
                      width=200.0, depth=200.0, height=gen.ceiling)
    b_room = RoomSpec(id="B", center_x=240.0, center_y=0.0, floor_z=0.0,
                      width=200.0, depth=200.0, height=gen.ceiling)
    c_room = RoomSpec(id="C", center_x=480.0, center_y=0.0, floor_z=200.0,
                      width=200.0, depth=200.0, height=gen.ceiling)
    rooms = [e_room, b_room, c_room]  # indices: E=0, B=1, C=2

    # B inserted FIRST so B (index 1) is the first non-entrance node visited and
    # the midpoint branch runs on pass 1. Mirrors the design's
    # `adj = {B: [E, C], C: [B], E: [B]}`.
    adj = {1: [0, 2], 2: [1], 0: [1]}

    # --- Precondition: B's two walkable bands are DISJOINT at the initial z ---
    # Run is symmetric for these endpoints; compute each corridor's cap from the
    # production _elevation_run so the bands match what _relax_elevation uses.
    cap_eb = gen._elevation_run(e_room, b_room) * gen.max_grade
    cap_bc = gen._elevation_run(b_room, c_room) * gen.max_grade
    band_from_e = (e_room.floor_z - cap_eb, e_room.floor_z + cap_eb)
    band_from_c = (c_room.floor_z - cap_bc, c_room.floor_z + cap_bc)
    # Disjoint iff one band ends entirely below the other begins. If this ever
    # fails the constructed geometry stopped forcing the conflict -- fix the
    # construction, never the assertion.
    assert band_from_e[1] < band_from_c[0] or band_from_c[1] < band_from_e[0], (
        f"precondition failed: B's bands {band_from_e} and {band_from_c} "
        f"overlap, so the midpoint branch would not run"
    )

    # --- Drive the fallback exactly as the generator calls it ---
    gen._relax_elevation(rooms, adj, entrance)

    # --- Postcondition: every adjacent pair is within the grade cap ----------
    for i in adj:
        for m in adj[i]:
            if i >= m:
                continue  # check each undirected pair once
            run = gen._elevation_run(rooms[i], rooms[m])
            dz = abs(rooms[i].floor_z - rooms[m].floor_z)
            cap = run * 0.5 + 0.01
            assert dz <= cap, (
                f"relax fallback left corridor {rooms[i].id}->{rooms[m].id} "
                f"over the grade cap: |dz|={dz:.4f} > run*0.5+0.01={cap:.4f} "
                f"(run={run:.4f})"
            )


# --- Property 3: Flush openings (umbrella P7) ---------------------------------
#
# Widened in M1 (task 6.4) to `room_counts_wide` (2-30, biased ~half into the
# big-zone band). Task 8.2 then RESTORED the elevation draw: verticality is
# drawn across `verticality_all` (flat / moderate / dramatic), with elevation
# set consistently (flat => off, moderate/dramatic => on). Flush openings must
# hold with elevation on too -- the opening is cut at the room floor even when
# the corridor ramps, because the rise happens away from the opening and the far
# leg of a Z-corridor is excluded by the MAX_SEG_RISE seam band.
#
# Budget scaled(50): the design pins 50, bounded by mesh cost -- this builds the
# Box_Backend mesh in memory for every example (no binary archive), which is
# heavier than the pure-spec layout properties above, so the per-test budget is
# halved relative to them. Still layout/geometry only (no ZoneBuilder, no .eqg),
# so no `slow` marker and no `build_settings`; `deadline=None` because the
# in-memory mesh build for up to 30 rooms can brush the Default_Profile's 200 ms
# per-example deadline on a cold call (import/JIT warmup) -- timing variance, not
# a property failure.
#
# The probe band is scoped TIGHT to the seam: `band=MAX_SEG_RISE` (2.5 u, the
# step-up / per-segment-rise limit from generators.geometry). The design's
# `opening_floor_z(..., band)` window `z_ref +/- band` exists precisely to scope
# the probe to the SEAM, not to the whole corridor-height column. Using the
# corridor height (~97 u) as the band is too wide: on a Z-corridor the far,
# legitimately-elevated leg can overhang the opening XY, and that distant
# walkable ramp -- correctly within the grade cap -- would be swept into the
# probe and read as non-flush even though the opening itself sits exactly on the
# floor. A band of MAX_SEG_RISE admits only faces at the seam: P7/Req 3.4 is "the
# opening sits at the room floor", so any real step at the seam is <= 2.5 u off
# and is STILL caught by the strict 0.01 u assertion below, while the far end of
# a Z-corridor is correctly excluded. This is correct probe scoping, not a
# loosened assertion. An EMPTY return means the probe XY missed every upward face
# within the seam band, which (per the design) should not happen -- the opening
# point is exactly the corridor endpoint, which sits on the room's floor quad
# edge AND the corridor floor -- so an empty list is itself a failure (a
# misplaced opening), asserted non-empty rather than tolerated.
#
# Task 8.3 added the FAR-END exemption (`opening_floor_z(..., far_z=...)`): when
# a corridor's TOTAL rise is itself under the MAX_SEG_RISE band -- a SHORT ramped
# corridor -- the far room's flat floor slab (and the ramp top meeting it)
# overhangs the near opening XY in projection and lands inside `z_ref +/- band`,
# even though the near opening sits exactly on its own floor. That far face is
# reached by walking UP the within-grade-cap ramp, not by a step at THIS
# threshold, so it is not a non-flush opening. Passing the FAR room's floor_z as
# `far_z` scopes the window to the corridor's own near-end floor: faces at the
# far floor level (and != z_ref) are exempted. This is the seed-13 class (seed
# 13, dungeon, 13 rooms, dramatic, corr_13 room_1->room_11: corridor rise 0.989 u
# < 2.5, build genuinely navigable, both openings flush at their own floor, but
# the old symmetric band swept in the far slab 0.989 u away). It is a correctness
# SCOPING fix of the PROBE, not a weakening: the 0.01 u tolerance and the
# strategy are untouched, and a genuinely non-flush opening (threshold floor cut
# above/below z_ref at a height that is NOT the far room's floor) is STILL caught
# -- confirmed against an injected 1.5 u lip, which the probe still flags.
@settings(deadline=None, max_examples=scaled(50))
@example(seed=13, zone_type="dungeon", n=13, verticality="dramatic").via("discovered failure")
@given(
    seed=seeds,
    zone_type=box_zone_types,
    n=room_counts_wide,
    verticality=verticality_all,
)
def test_flush_openings(seed, zone_type, n, verticality):
    """Feature: zone-generator-m1-controls-traversability, Property 3: Flush openings.

    Umbrella P7. For any seed, box theme (dungeon/city), room count across the
    M1 large-zone range (2-30, ``room_counts_wide``) and any verticality
    (``verticality_all``: flat / moderate / dramatic -- the elevation draw
    restored in task 8.2; elevation is set consistently, flat => off and
    moderate/dramatic => on, so the elevated draws actually ramp corridors),
    every corridor meets both its rooms flush at the floor:

    1. The corridor's ``from_z`` / ``to_z`` EQUAL the respective rooms'
       ``floor_z`` -- the opening is cut at the room floor, never above or below
       it.
    2. At each opening XY -- ``(from_x, from_y)`` on the ``from_room`` wall and
       ``(to_x, to_y)`` on the ``to_room`` wall -- every upward face of the
       Box_Backend mesh within ``MAX_SEG_RISE`` (2.5 u, the step-up /
       segment-rise limit) of that room's floor, scoped to the corridor's
       NEAR-END floor, lies within 0.01 u of ``floor_z``. The band is scoped to
       the SEAM, not the whole corridor-height column: that is what the design's
       ``z_ref +/- band`` window expresses. A real step at the opening would be
       <= 2.5 u off and is still caught by the strict 0.01 u assertion, while the
       far, legitimately-elevated leg of a Z-corridor -- a walkable ramp within
       the grade cap -- is correctly excluded. The probe is additionally passed
       the FAR room's ``floor_z`` (``far_z``): on a SHORT ramped corridor whose
       total rise is itself under the band, the far room's flat floor slab
       overhangs the near opening XY and falls inside ``z_ref +/- band`` even
       though the near opening is flush; such far-floor faces are reached by
       walking the within-grade-cap ramp, not by a step at this threshold, so
       they are exempted (task 8.3, the seed-13 class). The probe must find at
       least one upward face at each opening (an empty result means the opening
       XY is misplaced, which is itself a flush failure).

    The mesh is built in memory via ``geometry.build_mesh(spec).to_ter(...)`` --
    no binary archive. If this fails it is a REAL geometry bug (an opening not
    flush at the floor); report the counterexample and fix the geometry at the
    root -- do NOT widen the 0.01 u band or narrow the strategy.

    Validates: Requirements 5.1, 5.5.
    """
    # Elevation draw restored (task 8.2): flat => elevation off, moderate /
    # dramatic => on, so the elevated draws actually ramp corridors. The flush
    # invariant holds regardless: the opening is cut at the room floor even when
    # the corridor ramps -- the rise happens AWAY from the opening (and the far
    # leg of a Z-corridor is excluded by the MAX_SEG_RISE seam band below).
    plan = ZonePlan(
        name=f"flush{seed}",
        zone_type=zone_type,
        room_count=n,
        verticality=verticality,
        elevation=verticality != "flat",
    )
    spec = plan_to_spec(plan, seed=seed)

    # Build the Box_Backend mesh in memory (no ZoneBuilder, no .eqg write).
    ter = build_mesh(spec).to_ter(spec.name.lower())

    rooms_by_id = {r.id: r for r in spec.rooms}

    for c in spec.corridors:
        from_room = rooms_by_id.get(c.from_room)
        to_room = rooms_by_id.get(c.to_room)
        # The layout always wires corridors between two real rooms; guard the
        # lookup rather than crash if that ever changes.
        assert from_room is not None and to_room is not None, (
            f"corridor {c.id} references unknown room(s) "
            f"{c.from_room!r}/{c.to_room!r} (seed={seed}, theme={zone_type}, n={n}, "
            f"verticality={verticality!r})"
        )

        # (1) The opening Z equals the room floor at each end. Exact equality:
        # the layout sets from_z/to_z directly from the rooms' floor_z, so any
        # drift here is a real bug, not float noise.
        assert c.from_z == from_room.floor_z, (
            f"corridor {c.id} from_z {c.from_z!r} != from_room floor_z "
            f"{from_room.floor_z!r} (seed={seed}, theme={zone_type}, n={n}, "
            f"verticality={verticality!r})"
        )
        assert c.to_z == to_room.floor_z, (
            f"corridor {c.id} to_z {c.to_z!r} != to_room floor_z "
            f"{to_room.floor_z!r} (seed={seed}, theme={zone_type}, n={n}, "
            f"verticality={verticality!r})"
        )

        # (2) Every upward face under each opening point, within MAX_SEG_RISE
        # (2.5 u, the step-up/segment-rise limit) of that floor, is flush with
        # the room floor to within 0.01 u. The band is scoped to the SEAM so the
        # far, legitimately-elevated leg of a Z-corridor is excluded; a real step
        # at the opening is <= 2.5 u off and still caught by the 0.01 u check.
        # `far_z` (the OTHER room's floor_z) scopes the probe to this corridor's
        # near-end floor: on a short ramped corridor whose total rise is under
        # the band, the far room's floor slab overhangs the near opening XY and
        # would otherwise read as non-flush (task 8.3, seed-13 class).
        for label, (ox, oy), floor_z, far_z in (
            ("from", (c.from_x, c.from_y), from_room.floor_z, to_room.floor_z),
            ("to", (c.to_x, c.to_y), to_room.floor_z, from_room.floor_z),
        ):
            zs = opening_floor_z(ter, ox, oy, z_ref=floor_z, band=MAX_SEG_RISE,
                                 far_z=far_z)
            # The opening point is the corridor endpoint, which lies on the room
            # floor quad's edge AND the corridor floor -- so an upward face MUST
            # be found there. An empty result means the opening XY is off, which
            # is a flush failure in itself.
            assert zs, (
                f"corridor {c.id} {label} opening ({ox:.3f}, {oy:.3f}) found no "
                f"upward floor face within {MAX_SEG_RISE} u of floor_z "
                f"{floor_z:.3f} (seed={seed}, theme={zone_type}, n={n}, "
                f"verticality={verticality!r})"
            )
            for z in zs:
                assert abs(z - floor_z) <= 0.01, (
                    f"corridor {c.id} {label} opening ({ox:.3f}, {oy:.3f}) has a "
                    f"floor face at z={z:.5f}, off floor_z {floor_z:.3f} by "
                    f"{abs(z - floor_z):.5f} u > 0.01 (seed={seed}, "
                    f"theme={zone_type}, n={n}, verticality={verticality!r})"
                )


# --- Property 9: ZonePlan normalisation (umbrella P12) ------------------------
#
# Layout-tier, no binary build and no controls path: `ZonePlan.from_dict` is pure
# dataclass/clamp logic (`ai.schema`), so no `slow` marker and no
# `build_settings`. Budget 100 per the design (default profile). `deadline=None`
# for parity with the other layout-tier tests -- the work is trivial, but a cold
# import of `ai.schema` on the first example can brush the 200 ms deadline
# (warmup), which is timing variance, not a property failure.
#
# The normalisation entry is `ZonePlan.from_dict(d)`: it drops keys outside the
# dataclass, constructs the plan from the survivors, then calls `.validate()`,
# which clamps/filters every field in place and returns self (verified in
# ai/schema.py). So `from_dict` IS the normalisation, and `validate()` is the
# fixpoint step -- calling it again on an already-normalised plan must leave it
# equal. The `zone_plan_dicts` strategy deliberately keeps "cave" in its theme
# vocab (task 2.4) so cave->dungeon normalisation is exercised; the real
# `validate()` maps ANY out-of-vocab value -- "cave" included -- to "dungeon",
# so the domain assertion below simply requires the normalised zone_type to be
# one of VALID_ZONE_TYPES, which covers the cave case without special-casing it.
@settings(deadline=None, max_examples=scaled(100))
@given(d=zone_plan_dicts)
def test_zoneplan_normalisation(d):
    """Feature: zone-generator-m0-hygiene, Property 9: ZonePlan normalisation.

    Umbrella P12 (no controls path). For any loosely-typed dict covering every
    `ZonePlan` field (plus junk keys), `ZonePlan.from_dict(d)` lands every field
    inside its valid domain -- the umbrella Req 2.3/2.4/2.8 vocabularies and
    clamp ranges:

    * ``zone_type`` in VALID_ZONE_TYPES (an out-of-vocab value, "cave" included,
      maps to "dungeon");
    * ``room_count`` clamped to ``[1, 30]``; ``locks`` clamped to ``[0, 5]``;
    * ``size`` in {small, medium, large, huge}; ``verticality`` in
      {flat, moderate, dramatic};
    * ``regions`` a list whose every kind is in VALID_REGION_KINDS;
    * ``dungeon_theme`` / ``dungeon_race`` / ``elemental_tint`` each in their
      vocabulary or the empty string;
    * ``elevation`` a bool.

    And normalisation is idempotent: a second ``validate()`` on the already-
    normalised plan returns an equal plan (a fixpoint). `from_dict` runs
    `validate()` once internally, so re-validating must not move any field.

    If any field escapes its domain for some input, that is a REAL normalisation
    bug in `ZonePlan.validate` -- report the counterexample and fix the clamp at
    the root; do NOT narrow the strategy.

    Validates: M0 Req 3.5; umbrella Req 1.6.
    """
    from ai.schema import (
        VALID_ZONE_TYPES,
        VALID_REGION_KINDS,
        VALID_DUNGEON_THEMES,
        VALID_DUNGEON_RACES,
        VALID_ELEMENTAL_TINTS,
    )

    plan = ZonePlan.from_dict(d)

    # --- (1) Every field is inside its valid domain -------------------------
    assert plan.zone_type in VALID_ZONE_TYPES, (
        f"theme {plan.zone_type!r} not in {VALID_ZONE_TYPES} (input {d.get('theme')!r})"
    )
    assert isinstance(plan.room_count, int) and 1 <= plan.room_count <= 30, (
        f"room_count {plan.room_count!r} outside [1, 30] "
        f"(input {d.get('room_count')!r})"
    )
    assert plan.size in ("small", "medium", "large", "huge"), (
        f"size {plan.size!r} outside its vocab (input {d.get('size')!r})"
    )
    assert plan.verticality in ("flat", "moderate", "dramatic"), (
        f"verticality {plan.verticality!r} outside its vocab "
        f"(input {d.get('verticality')!r})"
    )
    assert isinstance(plan.regions, list)
    for r in plan.regions:
        assert r in VALID_REGION_KINDS, (
            f"region kind {r!r} not in {VALID_REGION_KINDS} "
            f"(input regions {d.get('regions')!r})"
        )
    assert isinstance(plan.locks, int) and 0 <= plan.locks <= 5, (
        f"locks {plan.locks!r} outside [0, 5] (input {d.get('locks')!r})"
    )
    assert plan.dungeon_theme == "" or plan.dungeon_theme in VALID_DUNGEON_THEMES, (
        f"dungeon_theme {plan.dungeon_theme!r} not empty and not in "
        f"{VALID_DUNGEON_THEMES} (input {d.get('dungeon_theme')!r})"
    )
    assert plan.dungeon_race == "" or plan.dungeon_race in VALID_DUNGEON_RACES, (
        f"dungeon_race {plan.dungeon_race!r} not empty and not in "
        f"{VALID_DUNGEON_RACES} (input {d.get('dungeon_race')!r})"
    )
    assert plan.elemental_tint == "" or plan.elemental_tint in VALID_ELEMENTAL_TINTS, (
        f"elemental_tint {plan.elemental_tint!r} not empty and not in "
        f"{VALID_ELEMENTAL_TINTS} (input {d.get('elemental_tint')!r})"
    )
    assert isinstance(plan.elevation, bool), (
        f"elevation {plan.elevation!r} is not a bool (input {d.get('elevation')!r})"
    )

    # --- (2) Idempotence: re-normalising a normalised plan is a fixpoint ----
    # `from_dict` already called `validate()` once; calling it again must leave
    # every field equal. Compare through `to_dict()` so the check is field-for-
    # field and does not depend on dataclass identity.
    before = plan.to_dict()
    again = plan.validate().to_dict()
    assert again == before, (
        f"normalisation is not idempotent: a second validate() changed the "
        f"plan from {before!r} to {again!r} (input {d!r})"
    )


# --- Property 19: Cave words never yield a cave theme (M0-only) ---------------
#
# Layout-tier, no binary build: `RulePlanner().plan(prompt)` is pure keyword
# scoring (`ai.rule_planner`), so no `slow` marker and no `build_settings`.
# Budget 100 per the design (default profile, scaled by the active profile).
# `deadline=None` for parity with the other layout-tier tests -- the work is
# trivial, but a cold import of `ai.rule_planner` on the first example can brush
# the 200 ms deadline (warmup), which is timing variance, not a property failure.
#
# `cave_prompts` builds a prompt that ALWAYS contains >= 1 Cave_Word
# (`CAVE_WORDS`), mixes in `st.text()` filler, and optionally salts in 0-3 words
# drawn from the OTHER `_THEME_WORDS` buckets (the outdoor/city words plus the
# non-cave dungeon words), then shuffles every token into a single string. The
# cave words were folded into the dungeon bucket post-5.2, so a cave word
# contributes to the dungeon score exactly as the planner counts it.
#
# The strictly-greater premise is computed IN THE TEST by mirroring the
# planner's scoring verbatim: `sum(prompt_lower.count(w) for w in bucket)` for
# each of the dungeon / outdoor / city buckets of `_THEME_WORDS` -- the same
# `str.count` substring counting `RulePlanner._match_theme` uses. When the
# dungeon score is strictly greater than BOTH the outdoor and city scores, the
# theme must be `dungeon`; otherwise (ties, or outdoor/city outscoring) we only
# assert theme in Defined_Themes, because the planner's tie rule -- unchanged in
# M0 -- lets outdoor/city win ties, and over-constraining ties would be wrong.
_OTHER_ZONE_TYPE_WORDS = sorted(
    {
        w
        for bucket, words in _ZONE_TYPE_WORDS.items()
        for w in words
        if w not in set(CAVE_WORDS)
    }
)


@st.composite
def cave_prompts(draw) -> str:
    """A prompt that always carries >= 1 Cave_Word, plus filler and optional
    other-bucket salt, shuffled into one string."""
    cave_picks = draw(
        st.lists(st.sampled_from(CAVE_WORDS), min_size=1, max_size=3)
    )
    other_picks = draw(
        st.lists(st.sampled_from(_OTHER_ZONE_TYPE_WORDS), min_size=0, max_size=3)
    )
    filler = draw(st.text(max_size=40))
    tokens = cave_picks + other_picks + ([filler] if filler else [])
    order = draw(st.permutations(tokens))
    return " ".join(order)


def _bucket_score(text_lower: str, bucket: list) -> int:
    """Mirror `RulePlanner._match_theme` scoring: substring `str.count` per
    bucket word, summed."""
    return sum(text_lower.count(w) for w in bucket)


@settings(deadline=None, max_examples=scaled(100))
@given(prompt=cave_prompts())
def test_cave_words_mean_dungeon(prompt):
    """Feature: zone-generator-m0-hygiene, Property 19: Cave words never yield a cave theme (M0-only).

    For any prompt containing one or more Cave_Words (mixed with random filler
    and, optionally, outdoor/city/dungeon keywords), the rule planner's chosen
    theme is always one of the Defined_Themes {dungeon, outdoor, city} and NEVER
    "cave" -- the cave theme was removed from the surface in M0, and the cave
    words were folded into the dungeon bucket. Beyond that, the theme EQUALS
    "dungeon" whenever the prompt's dungeon-bucket score (Cave_Words included,
    counted with `str.count` exactly as `RulePlanner._match_theme` does) is
    STRICTLY GREATER than both its outdoor score and its city score. When the
    dungeon score is not strictly greater (a tie, or outdoor/city outscoring),
    only the Defined_Themes membership is asserted: the planner's tie rule is
    unchanged in M0 and outdoor/city win ties, so over-constraining ties would
    be wrong.

    The dungeon/wilderness/city scores are computed in the test directly from
    `ai.rule_planner._ZONE_TYPE_WORDS`, mirroring the planner's substring
    counting, which is the design's "scores computed in the test from the word
    buckets for the strictly greater premise". If a cave-word prompt ever yields
    "cave" (or any out-of-domain value), or the strictly-greater-dungeon premise
    fails to
    give "dungeon", that is a REAL planner bug -- report the counterexample and
    fix the planner at the root; do NOT narrow the strategy.

    Validates: M0 Req 6.5.
    """
    zone_type = RulePlanner().plan(prompt).zone_type

    # (1) The theme is always a Defined_Theme and never "cave".
    assert zone_type in DEFINED_ZONE_TYPES, (
        f"planner theme {zone_type!r} not in Defined_Themes {DEFINED_ZONE_TYPES} "
        f"for prompt {prompt!r}"
    )

    # (2) Strictly-greater dungeon score -> theme must be dungeon. Scores are
    # computed here from _THEME_WORDS with the planner's own str.count scoring.
    text_lower = prompt.lower()
    dungeon_score = _bucket_score(text_lower, _ZONE_TYPE_WORDS["dungeon"])
    # The open-air bucket key is "wilderness" post-rename (word list unchanged).
    outdoor_score = _bucket_score(text_lower, _ZONE_TYPE_WORDS["wilderness"])
    city_score = _bucket_score(text_lower, _ZONE_TYPE_WORDS["city"])

    if dungeon_score > outdoor_score and dungeon_score > city_score:
        assert zone_type == "dungeon", (
            f"dungeon score {dungeon_score} strictly beats outdoor "
            f"{outdoor_score} and city {city_score}, but planner chose "
            f"{zone_type!r} for prompt {prompt!r}"
        )


# --- Property 12: Legacy vocabulary load round-trip (M1-P3) ------------------
#
# Layout-tier: `ZonePlan.from_dict` / `ZoneSpec.from_dict` are pure dataclass +
# `canonical_zone_type` / `read_zone_type` logic (`ai.schema`,
# `generators.zone_spec`, `generators.zone_types`), and `plan_to_spec` drives
# the LayoutGenerator -- no binary build and no geometry -- so no `slow` marker
# and no `build_settings`. Budget 100 per the task (default profile, scaled by
# the active profile via `scaled`). `deadline=None` for parity with the other
# layout-tier tests: the full layout for up to 30 rooms can brush the
# Default_Profile's 200 ms deadline on a cold call (import/JIT warmup), which is
# timing variance, not a property failure.
#
# The load boundaries this pins -- `from_dict` reading the legacy `theme` key
# and `outdoor` value, and `zone_type` winning when both keys are present --
# are already implemented (tasks 10.3 / 10.4, confirmed by 10.9). This property
# PINS that behaviour across all three zone types. If it fails, it is a REAL bug
# in `from_dict` / `canonical_zone_type` -- fix it at the root (never weaken the
# assertion) and pin the counterexample as a Regression_Example via
# `@example(...).via("discovered failure")`.
@settings(deadline=None, max_examples=scaled(100))
@given(
    seed=seeds,
    zone_type=spec_zone_types,
    n=room_counts(1, 30),
    elevation=st.booleans(),
    semantic=semantic_inputs,
)
def test_legacy_vocabulary_round_trip(seed, zone_type, n, elevation, semantic):
    """Feature: zone-generator-m1-controls-traversability, Property 12: Legacy vocabulary load round-trip.

    M1-P3. For a plan loaded via ``ZonePlan.from_dict`` and a spec expanded via
    ``ai.expand.plan_to_spec`` on each of the three canonical zone types
    (dungeon, city, wilderness -- ``spec_zone_types``), the current vocabulary
    serialises and reloads losslessly through the LEGACY vocabulary:

    1. ``to_dict()`` -- for both the plan and the spec -- contains a
       ``zone_type`` key, contains NO legacy ``theme`` key anywhere, and
       contains NO ``outdoor`` value anywhere (the open-air type is spelled
       ``wilderness`` on the way out; ``outdoor`` only ever appears as an input).
    2. Renaming the serialised ``zone_type`` key back to the legacy ``theme``
       key (and, for wilderness, the value ``wilderness`` back to the legacy
       ``outdoor``) and reloading via ``from_dict`` yields a canonical
       ``zone_type`` EQUAL to the original -- the forward round-trip through the
       legacy vocabulary is lossless.
    3. When BOTH a ``zone_type`` key and a ``theme`` key are present and they
       name DIFFERENT zone types, the loader honours ``zone_type`` (the current
       key wins over the legacy key).

    All three checks run against both the plan (``ZonePlan``) and the spec
    (``ZoneSpec``) load boundaries. A failure is a REAL bug in ``from_dict`` /
    ``canonical_zone_type`` (the legacy-mapping or the key-precedence rule), to
    be fixed at the root and pinned as a Regression_Example -- never a reason to
    weaken the assertion or narrow the strategy.

    Validates: Requirements 11.1, 11.2, 11.5.
    """
    # The legacy spelling of each canonical zone type on the LOAD side. Only the
    # open-air type was renamed (outdoor -> wilderness); the others are their own
    # legacy value. This is the value a legacy `theme`-keyed dict would carry.
    legacy_value = {"dungeon": "dungeon", "city": "city", "wilderness": "outdoor"}
    legacy = legacy_value[zone_type]

    # Build a plan for this zone type (loaded through the new `zone_type` key)
    # and expand it to a spec. The semantic layer is drawn in full so the
    # content block travels through both serialisers alongside the zone type.
    plan = ZonePlan.from_dict(
        {
            "name": f"leg{seed}",
            "zone_type": zone_type,
            "room_count": n,
            "elevation": elevation,
            "dungeon_theme": semantic["dungeon_theme"],
            "dungeon_race": semantic["dungeon_race"],
            "elemental_tint": (semantic["elemental_tint"] or ""),
        }
    )
    assert plan.zone_type == zone_type
    spec = plan_to_spec(plan, seed=seed)
    assert spec.zone_type == zone_type

    plan_d = plan.to_dict()
    spec_d = spec.to_dict()

    # --- (1) to_dict() carries zone_type, never `theme`, never `outdoor` -----
    for label, d in (("plan", plan_d), ("spec", spec_d)):
        assert "zone_type" in d, (
            f"{label}.to_dict() is missing the 'zone_type' key: {d!r}"
        )
        assert d["zone_type"] == zone_type, (
            f"{label}.to_dict()['zone_type'] {d['zone_type']!r} != {zone_type!r}"
        )
        # No legacy `theme` key anywhere in the serialised dict (top level is
        # where the zone type lives; the content block keeps its own names).
        assert "theme" not in d, (
            f"{label}.to_dict() still carries a legacy 'theme' key: {d!r}"
        )
        # The legacy open-air VALUE must never be emitted as the zone type:
        # wilderness is the only way out, `outdoor` is only ever an input. Scan
        # every top-level value EXCEPT `style_profile`, which legitimately names
        # the measured profile file `styles/outdoor.json` -- `style_profile` is
        # provenance (a profile name), not the zone-type vocabulary, and the
        # file deliberately keeps the `outdoor` name (generators/zone_types.py
        # STYLE_PROFILE: wilderness -> "outdoor").
        zone_type_values = {
            k: v for k, v in d.items() if k != "style_profile"
        }.values()
        assert "outdoor" not in zone_type_values, (
            f"{label}.to_dict() emits a legacy 'outdoor' value outside "
            f"style_profile: {d!r}"
        )

    # --- (2) Forward round-trip THROUGH the legacy vocabulary is lossless ----
    # Rename the serialised `zone_type` key to the legacy `theme` key and map the
    # value back to its legacy spelling, then reload. The loader must recover the
    # same canonical zone type.
    for label, d, loader, read in (
        ("plan", plan_d, ZonePlan.from_dict, lambda o: o.zone_type),
        ("spec", spec_d, ZoneSpec.from_dict, lambda o: o.zone_type),
    ):
        legacy_d = dict(d)
        legacy_d.pop("zone_type")
        legacy_d["theme"] = legacy
        recovered = read(loader(legacy_d))
        assert recovered == zone_type, (
            f"{label} legacy round-trip lost the zone type: reloaded "
            f"theme={legacy!r} -> {recovered!r}, expected {zone_type!r}"
        )

    # --- (3) When both keys are present and differ, `zone_type` wins ---------
    # Pick a DIFFERENT canonical zone type and plant it in the legacy `theme`
    # key alongside the correct `zone_type`. The loader must honour `zone_type`.
    others = [z for z in DEFINED_ZONE_TYPES if z != zone_type]
    for other in others:
        other_legacy = legacy_value[other]
        for label, d, loader, read in (
            ("plan", plan_d, ZonePlan.from_dict, lambda o: o.zone_type),
            ("spec", spec_d, ZoneSpec.from_dict, lambda o: o.zone_type),
        ):
            both = dict(d)
            both["zone_type"] = zone_type
            both["theme"] = other_legacy  # legacy key naming a DIFFERENT type
            won = read(loader(both))
            assert won == zone_type, (
                f"{label}: with zone_type={zone_type!r} and legacy "
                f"theme={other_legacy!r} both present, loader chose {won!r} -- "
                f"zone_type must win"
            )
