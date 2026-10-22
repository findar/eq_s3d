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

from .pbt_helpers import scaled, room_graph, solvable_walk, run_for, _entrance_id
from .strategies import (
    seeds,
    room_counts,
    spec_themes,
    box_themes,
    verticality,
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
    theme=box_themes,
    n=room_counts(2, 30),
    vert=verticality,
    elevation=st.booleans(),
    semantic=semantic_inputs,
)
def test_elevation_grade_cap(seed, theme, n, vert, elevation, semantic):
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
        theme=theme,
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

        run = run_for(spec, theme, n, plan.size, a, b)
        dz = abs(c.from_z - c.to_z)
        cap = run * 0.5 + 0.01

        # If this fails it is a REAL elevation grade bug (umbrella P6) -- the
        # corridor is a cliff steeper than the walkable cap. Report the
        # counterexample (per task 13.1); do NOT weaken the bound.
        assert dz <= cap, (
            f"corridor {c.id} exceeds the grade cap: |dz|={dz:.4f} > "
            f"run*0.5+0.01={cap:.4f} (run={run:.4f}); seed={seed}, "
            f"theme={theme}, n={n}, verticality={vert!r}, "
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
