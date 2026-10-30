"""
tests/test_properties_build.py
------------------------------
Build-level properties for the M0 Property_Suite. Every test in this module
drives a real zone BUILD (layout -> geometry -> .eqg) and is therefore
``@pytest.mark.slow`` with a ``build_settings(...)`` budget (design Req 1.5):
builds are slow and their generated input can be large, so these never run
under the fast default sweep budget.

Design reference: ``.kiro/specs/zone-generator-m0-hygiene/design.md``,
Correctness Properties 10-14.
"""

from __future__ import annotations

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

import analyzer.traverse as T
from generators.layout import LayoutGenerator

from ai.schema import ZonePlan
from ai.expand import plan_to_spec
from tests.strategies import (
    seeds,
    room_counts,
    room_counts_wide,
    box_zone_types,
    verticality_all,
)
from tests.pbt_helpers import (
    build_settings,
    build_raw,
    build_and_validate_raw,
    fresh_dir,
    M0_HUMAN_PASS,
    m0_human_spec,
)


@st.composite
def _raw_navigable_cases(draw):
    """
    A ``(spec, label, key)`` case for Property 1, built through the real plan
    path.

    Draws a box zone type (``dungeon``/``city``), a wide room count (biased so
    the large-zone band is hit about half the time, Req 5.1) and a verticality
    across the full domain (``verticality_all``: flat / moderate / dramatic —
    the elevation pass, task 8.1, now that the flat-first pass is signed off),
    then expands a ``ZonePlan`` through ``ai.expand.plan_to_spec`` — the same
    path the pipeline uses — so a passing property exercises an input the
    production path can genuinely see. ``elevation`` is set consistently
    (flat => off, otherwise on) so moderate/dramatic actually elevate corridors
    (Req 5.4). ``label`` carries the drawn parameters so a failure prints them;
    ``key`` is the stable ``(zone_type, seed, n, verticality)`` cache key for
    the shared P1/M1-P1 build (design budget lever 1) — ``test_raw_navigable``
    and ``test_corridor_continuity`` draw the same cases in the same order, so
    the two tests key identically and share one build.
    """
    s = draw(seeds)
    zone_type = draw(box_zone_types)
    n = draw(room_counts_wide)
    verticality = draw(verticality_all)
    plan = ZonePlan(
        name="navraw",
        zone_type=zone_type,
        room_count=n,
        verticality=verticality,
        elevation=verticality != "flat",
    )
    spec = plan_to_spec(plan, seed=s)
    label = f"seed={s}, zone_type={zone_type}, rooms={n}, verticality={verticality}"
    key = (zone_type, s, n, verticality)
    return spec, label, key


def _flat_human_case(entry):
    """An ``M0_HUMAN_PASS`` entry re-planned flat, as a ``(spec, label, key)``
    case."""
    spec = m0_human_spec(entry, verticality="flat")
    prompt, seed = entry
    label = f"M0 human pass (flat): {prompt!r} seed={seed}"
    key = ("m0_human_flat", prompt, seed)
    return spec, label, key


def _human_case(entry):
    """An ``M0_HUMAN_PASS`` entry re-planned with its OWN plan verticality (no
    flat override), as a ``(spec, label, key)`` case.

    This is the elevation pass's half of Decision 13: the same 30-room dungeons
    the human signed off on at the M0 3D pass, built as the rule planner would
    actually plan them (whatever verticality the prompt implies), so the wave-1
    fixes are proven to keep the known-good zones navigable with elevation on —
    not only when re-flattened. Keyed separately from the flat human case so the
    shared build cache never collides the two.
    """
    spec = m0_human_spec(entry, verticality=None)
    prompt, seed = entry
    label = f"M0 human pass: {prompt!r} seed={seed}"
    key = ("m0_human", prompt, seed)
    return spec, label, key


def _flat_seed_case(zone_type, n, seed):
    """A flat ``(spec, label, key)`` case for a pinned regression seed.

    Built the same way ``_raw_navigable_cases`` builds its draws (``ZonePlan``
    -> ``plan_to_spec``, flat), so a pinned seed reproduces exactly the layout
    the connectivity sweep surfaced as a failure.
    """
    plan = ZonePlan(
        name="navraw",
        zone_type=zone_type,
        room_count=n,
        verticality="flat",
        elevation=False,
    )
    spec = plan_to_spec(plan, seed=seed)
    label = f"regression seed={seed}, zone_type={zone_type}, rooms={n}, verticality=flat"
    key = (zone_type, seed, n, "flat")
    return spec, label, key


def _seed_case(zone_type, n, seed, verticality):
    """A ``(spec, label, key)`` case for a pinned regression seed at a given
    verticality.

    Built the same way ``_raw_navigable_cases`` builds its draws (``ZonePlan``
    -> ``plan_to_spec``, elevation on for non-flat), so a pinned elevation seed
    reproduces exactly the layout the connectivity sweep surfaced as a failure.
    """
    plan = ZonePlan(
        name="navraw",
        zone_type=zone_type,
        room_count=n,
        verticality=verticality,
        elevation=verticality != "flat",
    )
    spec = plan_to_spec(plan, seed=seed)
    label = (f"regression seed={seed}, zone_type={zone_type}, rooms={n}, "
             f"verticality={verticality}")
    key = (zone_type, seed, n, verticality)
    return spec, label, key


@pytest.mark.slow
@build_settings(15)
@example(case=_flat_human_case(M0_HUMAN_PASS[0])).via("M0 human pass (flat)")
@example(case=_flat_human_case(M0_HUMAN_PASS[1])).via("M0 human pass (flat)")
@example(case=_human_case(M0_HUMAN_PASS[0])).via("M0 human pass")
@example(case=_human_case(M0_HUMAN_PASS[1])).via("M0 human pass")
@example(case=_seed_case("dungeon", 26, 2985, "dramatic")).via("discovered failure")
@given(case=_raw_navigable_cases())
def test_raw_navigable(case):
    """
    Feature: zone-generator-m1-controls-traversability, Property 1: Raw builds
    are navigable (umbrella P1), all verticalities.

    A raw box zone (dungeon or city) built with no validation gate
    (``ZonePlan`` -> ``ai.expand.plan_to_spec`` -> ``build_raw``) walks end to
    end on its real generated TER mesh: the traversability validator reaches
    every room from the entrance safe point. This is the analytical
    navigability bar from ``analyzer.traverse`` — the per-triangle walk surface
    the north-star "every room reachable on foot" MUST is measured on — now
    widened from M0's dungeon-only, ≤ 12-room domain to BOTH box zone types
    across the full M1 large-zone range (``room_counts_wide``, up to 30 rooms,
    Req 5.1) over ALL verticalities (``verticality_all``: flat / moderate /
    dramatic — the elevation pass, task 8.1; elevation is set consistently so
    moderate/dramatic actually raise corridors, Req 5.4). Both ``M0_HUMAN_PASS``
    inputs — the 30-room dungeons a human signed off on at the M0 3D pass — are
    pinned TWICE as ``@example``s: once re-planned flat and once with their own
    plan verticality (no override), so the wave-1 fixes are proven to keep those
    known-good zones navigable both flat and with elevation on (Req 5.3).
    Builder exceptions propagate as failures; this property never ``assume``s an
    input away (Req 4.1).

    NOTE: this is an ANALYTICAL check (the per-triangle walk surface on the real
    TER mesh), not a live 3D viewer confirmation — see docs/ACCEPTANCE.md.

    Validates: Requirements 4.1, 5.1, 5.2, 5.4; umbrella P1.
    """
    spec, label, key = case
    # Shared P1/M1-P1 build (design budget lever 1): build + validate once per
    # case, memoised; test_corridor_continuity reuses this same report. The
    # corridor check is a superset — report.passed is the same verdict a
    # check_corridors=False validate would give (Req 4.1) — so P1's assertion is
    # unchanged.
    report = build_and_validate_raw(spec, key)

    assert report.passed, (
        f"non-navigable box zone ({label}):\n{report.summary()}"
    )


@pytest.mark.slow
@build_settings(15)
@example(case=_flat_human_case(M0_HUMAN_PASS[0])).via("M0 human pass (flat)")
@example(case=_flat_human_case(M0_HUMAN_PASS[1])).via("M0 human pass (flat)")
@example(case=_human_case(M0_HUMAN_PASS[0])).via("M0 human pass")
@example(case=_human_case(M0_HUMAN_PASS[1])).via("M0 human pass")
@example(case=_flat_seed_case("dungeon", 12, 27)).via("discovered failure")
@example(case=_flat_seed_case("dungeon", 12, 6)).via("discovered failure")
@example(case=_flat_seed_case("dungeon", 12, 22)).via("discovered failure")
@example(case=_flat_seed_case("dungeon", 30, 2)).via("discovered failure")
@example(case=_flat_seed_case("dungeon", 20, 143)).via("discovered failure")
@example(case=_flat_seed_case("dungeon", 30, 114)).via("discovered failure")
@example(case=_seed_case("dungeon", 30, 8, "dramatic")).via("discovered failure")
@given(case=_raw_navigable_cases())
def test_corridor_continuity(case):
    """
    Feature: zone-generator-m1-controls-traversability, Property 10: Corridor
    floor continuity (M1-P1), all verticalities.

    Every corridor on a raw box zone (dungeon or city) built with no validation
    gate (``ZonePlan`` -> ``ai.expand.plan_to_spec`` -> ``build_raw``) has
    CONTINUOUS walkable floor from its ``from_room`` to its ``to_room`` WITHIN
    the corridor's own region (its route footprint grown by the agent's
    adjacency tolerance, plus the two rooms' footprints, minus every OTHER
    room's footprint), and no two corridors conflict in Z. This is the
    corridor-level half of the north-star "every room reachable on foot" MUST:
    ``test_raw_navigable`` (task 6.2) proves rooms are reachable *somehow*; this
    proves the reachability runs THROUGH each corridor's own tube rather than by
    cutting through a third room's collidable geometry (reason
    ``"crosses room <id>"``) or by two corridor tubes passing too close to each
    other (a Z conflict, design decision 12/16).

    SAME domain and examples as ``test_raw_navigable``: box zone types
    (``box_zone_types``), the full M1 large-zone range (``room_counts_wide``, up to
    30 rooms, Req 5.1), built through ``ai.expand.plan_to_spec`` over ALL
    verticalities (``verticality_all``: flat / moderate / dramatic — the
    elevation pass, task 8.1, Req 5.4), budget 15. Both ``M0_HUMAN_PASS`` inputs
    are pinned TWICE as ``@example``s — once re-planned flat, once with their own
    plan verticality (the 30-room dungeons a human signed off on at the M0 3D
    pass).

    The verdict is read from ``analyzer.traverse.validate(..,
    check_corridors=True)``: every ``CorridorResult.connected`` must be True and
    there must be no conflicts (equivalently, ``report.corridors_passed``). On
    failure the message iterates ``report.corridors`` / ``report.conflicts`` and
    prints each failing corridor's id, endpoints and reason so the exact failure
    class (gap / crosses room / conflict) and seed are visible.

    NOTE: this is an ANALYTICAL check (corridor floor continuity on the real TER
    walk surface), not a live 3D viewer confirmation — see docs/ACCEPTANCE.md.

    Validates: Requirements 4.1, 5.1, 5.2, 5.4; M1-P1.
    """
    spec, label, key = case
    # Shared P1/M1-P1 build (design budget lever 1): reuse the report
    # test_raw_navigable built for this same case (validated with
    # check_corridors=True, so the corridor verdict is populated).
    report = build_and_validate_raw(spec, key)

    if not report.corridors_passed:
        broken = [c for c in report.corridors if not c.connected]
        detail_lines = [
            f"  {c.corridor_id} {c.from_room}->{c.to_room}: "
            f"{c.reason or 'not connected'}"
            for c in broken
        ]
        conflict_lines = [
            f"  CONFLICT {ci} <-> {cj}" for ci, cj in report.conflicts
        ]
        detail = "\n".join(detail_lines + conflict_lines) or "  (no detail)"
        pytest.fail(
            f"corridor floor continuity failed ({label}):\n"
            f"  {len(broken)}/{len(report.corridors)} corridors not connected, "
            f"{len(report.conflicts)} conflict(s)\n"
            f"{detail}"
        )


from tests.pbt_helpers import ramp_rises

#: Verticality that actually elevates corridors (``flat`` would make the ramp
#: path vacuously true, so it is excluded from this property's strategy).
_elevated_verticality = st.sampled_from(["moderate", "dramatic"])


@pytest.mark.slow
@build_settings(20)
@example(s=0, zone_type="dungeon", n=3, verticality="dramatic")
@given(
    s=seeds,
    zone_type=box_zone_types,
    n=room_counts_wide,
    verticality=_elevated_verticality,
)
def test_ramp_subdivision(s, zone_type, n, verticality):
    """
    Feature: zone-generator-m1-controls-traversability, Property 4: Ramp
    subdivision through 30 rooms (umbrella P8).

    Every upward (walkable) triangle on a built box-theme zone's TER rises at
    most ``MAX_SEG_RISE`` (2.5 u, with a 0.01 u tolerance -> 2.51). A sloped
    corridor is built by ``geometry._add_ramp_corridor``, which subdivides the
    run into segments that each rise <= 2.5 u. Without that subdivision a single
    ramp quad would present a ~dz/3 step between its two triangles, which the
    per-triangle traversability agent reads as an unclimbable gap (every room
    beyond the ramp becomes an island). This property is driven through
    ``ai.expand.plan_to_spec`` because that is the only path that applies plan
    ``verticality`` (``_VERTICALITY`` -> elevation chance + rise magnitude);
    ``moderate``/``dramatic`` with elevation on is what actually produces
    elevated corridors.

    Widened in M1 (task 8.2) from the M0 ``room_counts(2, 12)`` domain to
    ``room_counts_wide`` (2-30, biased ~half into the big-zone band, Req 5.1),
    so ramp subdivision is proven to hold across the large-zone range where more
    corridors ramp and the segment cap is exercised harder. Zone types stay box
    (``box_zone_types``: dungeon/city); verticality stays moderate/dramatic (flat
    would make the ramp path vacuously true), budget 20.

    The pinned ``@example`` (seed 0, dungeon, 3 rooms, dramatic) has a corridor
    whose total rise is ~71 u, far above 2.5 u, so the subdivision path is
    genuinely exercised rather than vacuously satisfied. The test asserts that
    precondition (an elevated corridor span > 2.5 u) on every example and that
    no single upward triangle rises past the segment cap.

    NOTE: this is an ANALYTICAL check (per-triangle rise on the TER mesh), not a
    live 3D viewer confirmation — see docs/ACCEPTANCE.md.

    Validates: M0 Req 4.2, 4.6, 1.5; umbrella Req 1.6.
    """
    plan = ZonePlan(
        name="rampsub",
        zone_type=zone_type,
        room_count=n,
        verticality=verticality,
        elevation=True,
    )
    spec = plan_to_spec(plan, seed=s)

    # Precondition: at least one corridor actually ramps (total rise > 2.5 u),
    # so the subdivision path under test is genuinely exercised. For the pinned
    # @example (seed 0, dungeon, 3 rooms, dramatic) elevation is deterministic
    # and the span is ~71 u, so we assert it hard — this proves the subdivision
    # path ran and the <= 2.51 assertion below is not vacuously true. For the
    # random elevated-verticality draws the elevation roll is probabilistic, so
    # a flat draw is a legitimate (vacuous) pass rather than a failure; we don't
    # `assume` it away (never call assume in a build property).
    spans = [abs(c.from_z - c.to_z) for c in spec.corridors]
    max_span = max(spans) if spans else 0.0
    if (s, zone_type, n, verticality) == (0, "dungeon", 3, "dramatic"):
        assert max_span > 2.5, (
            "pinned subdivision example no longer produces an elevated corridor "
            f"(max corridor span {max_span:.2f} u <= 2.5) — the subdivision path "
            "would be exercised only vacuously; re-pin a known-elevated example"
        )

    with fresh_dir() as out:
        _result, ter_bytes, _zon_bytes = build_raw(spec, out)
        rises = ramp_rises(ter_bytes)

    worst = max(rises) if rises else 0.0
    assert worst <= 2.51, (
        f"ramp segment rises above MAX_SEG_RISE "
        f"(seed={s}, theme={zone_type}, rooms={n}, verticality={verticality}): "
        f"worst per-triangle rise {worst:.4f} u > 2.51 "
        f"(max corridor span {max_span:.2f} u)"
    )

@pytest.mark.slow
@build_settings(15)
@given(
    s=seeds,
    zone_type=box_zone_types,
    n=room_counts(3, 12),
    locks=st.integers(min_value=1, max_value=5),
)
def test_locks_do_not_touch_geometry(s, zone_type, n, locks):
    """
    Feature: zone-generator-m0-hygiene, Property 12: Locks never touch geometry
    (umbrella P5, locks).

    Lock-and-key gating is ADVISORY metadata for a manual finishing pass — it
    rides in the ``.zone.json`` sidecar and the EQEmu ``doors`` table, never in
    the binary geometry. So for one fixed plan and one fixed seed, the number of
    locked gates MUST NOT change what gets built: a build with ``locks`` in
    [1, 5] and a build with ``locks=0`` produce the exact same mesh (TER) and
    the exact same zone layout (ZON). This asserts the north-star "layouts are
    suggestions ... they must not alter geometry or collision" invariant
    directly — if gating leaked into the mesh or placement, the two builds would
    diverge. (The ``.eqg`` bytes themselves are NOT compared: the PFS footer
    stamps ``int(time.time())`` and would differ between two archives even when
    their contents are identical — ``build_raw`` reads the TER/ZON members back
    out for exactly this reason.)

    NOTE: this is an ANALYTICAL byte-equality check on the built TER/ZON, not a
    live 3D viewer confirmation — see docs/ACCEPTANCE.md.

    Validates: M0 Req 4.3, 1.5; umbrella Req 1.6.
    """
    gated_plan = ZonePlan(name="lockgeo", zone_type=zone_type, room_count=n, locks=locks)
    open_plan = ZonePlan(name="lockgeo", zone_type=zone_type, room_count=n, locks=0)

    # Same name, same seed; the ONLY varied input is `locks`. plan_to_spec uses
    # the explicit seed (no fresh random is drawn), so both specs derive from an
    # identical RNG stream apart from gating.
    gated_spec = plan_to_spec(gated_plan, seed=s)
    open_spec = plan_to_spec(open_plan, seed=s)

    with fresh_dir() as out_gated:
        _r1, gated_ter, gated_zon = build_raw(gated_spec, out_gated)
    with fresh_dir() as out_open:
        _r2, open_ter, open_zon = build_raw(open_spec, out_open)

    assert gated_ter == open_ter, (
        f"locks changed the TER mesh (seed={s}, theme={zone_type}, rooms={n}, "
        f"locks={locks}): gating leaked into geometry"
    )
    assert gated_zon == open_zon, (
        f"locks changed the ZON layout (seed={s}, theme={zone_type}, rooms={n}, "
        f"locks={locks}): gating leaked into placement"
    )

from tests.strategies import spec_zone_types


@pytest.mark.slow
@build_settings(15)
@given(
    s=seeds,
    zone_type=spec_zone_types,
    n=room_counts(2, 12),
    locks=st.integers(min_value=0, max_value=5),
    elevation=st.booleans(),
)
def test_seed_determinism(s, zone_type, n, locks, elevation):
    """
    Feature: zone-generator-m0-hygiene, Property 13: Seed determinism
    (umbrella P9, no map artifacts).

    The same inputs (same name, same explicit seed, same plan) run through
    ``plan_to_spec`` + ``build_raw`` twice MUST produce the same zone. Given an
    explicit seed, ``plan_to_spec`` draws no fresh random (it only falls back to
    ``random.randint`` when ``seed is None``), so the whole layout/geometry/
    placement pipeline is a pure function of (plan, seed). This property asserts
    that directly: two independent passes into two separate ``fresh_dir()``s
    yield EQUAL ``ZoneSpec`` dicts and BYTE-IDENTICAL TER (geometry) and ZON
    (placement). This is the "same inputs reproduce the same zone" bar the
    north-star "randomness is a feature" rule depends on (a pinned seed must
    replay exactly).

    Scope note: TER/ZON only — NOT the ``.eqg`` bytes (the PFS footer stamps
    ``int(time.time())`` and would differ between two archives) and NOT any
    texture / ``.glb`` output (procedural texture seeds use a salted ``hash()``
    that can vary across processes; see lessons-learned). ``build_raw`` reads
    the TER/ZON members back out of the archive for exactly this reason, so the
    comparison is unaffected by texture salting. Geometry + placement are what
    seed determinism governs, and that is what is compared here.

    NOTE: this is an ANALYTICAL byte-equality check on the built TER/ZON, not a
    live 3D viewer confirmation — see docs/ACCEPTANCE.md.

    Validates: M0 Req 4.4, 1.5; umbrella Req 1.6.
    """
    plan = ZonePlan(
        name="seeddet",
        zone_type=zone_type,
        room_count=n,
        locks=locks,
        elevation=elevation,
        verticality="moderate",
    )

    # Two passes, SAME name + SAME explicit seed, into separate output dirs.
    # plan_to_spec with an explicit seed draws no fresh random, so both specs
    # derive from an identical RNG stream.
    spec1 = plan_to_spec(plan, seed=s)
    spec2 = plan_to_spec(plan, seed=s)

    assert spec1.to_dict() == spec2.to_dict(), (
        f"same-seed ZoneSpec dicts diverged "
        f"(seed={s}, theme={zone_type}, rooms={n}, locks={locks}, "
        f"elevation={elevation}): non-deterministic spec"
    )

    with fresh_dir() as out1:
        _r1, ter1, zon1 = build_raw(spec1, out1)
    with fresh_dir() as out2:
        _r2, ter2, zon2 = build_raw(spec2, out2)

    assert ter1 == ter2, (
        f"same-seed TER meshes diverged "
        f"(seed={s}, theme={zone_type}, rooms={n}, locks={locks}, "
        f"elevation={elevation}): non-deterministic geometry"
    )
    assert zon1 == zon2, (
        f"same-seed ZON layouts diverged "
        f"(seed={s}, theme={zone_type}, rooms={n}, locks={locks}, "
        f"elevation={elevation}): non-deterministic placement"
    )

from tests.strategies import semantic_inputs
from tests.pbt_helpers import clear_advisory


@pytest.mark.slow
@build_settings(15)
@given(
    s=seeds,
    zone_type=box_zone_types,
    n=room_counts(3, 12),
    locks=st.integers(min_value=1, max_value=5),
    semantic=semantic_inputs,
)
def test_advisory_clearing(s, zone_type, n, locks, semantic):
    """
    Feature: zone-generator-m0-hygiene, Property 14: Advisory clearing leaves
    the TER unchanged (umbrella P5, advisory clearing).

    Pacing and gating are ADVISORY metadata for a manual finishing pass — room
    roles, graph depth, semantic type, district, prop hints, encounter intent,
    the boss flag, and lock gates ride in the ``.zone.json`` sidecar (and the
    EQEmu ``doors`` table), never in the binary geometry. So stripping every
    advisory field off a fully-realised spec MUST NOT change what gets built:
    the TER mesh of ``spec`` is BYTE-IDENTICAL to the TER of
    ``clear_advisory(spec)``. This asserts the north-star "layouts are
    suggestions ... they must not alter geometry or collision" invariant head-on
    — if any advisory datum bled into the mesh, the two builds would diverge.

    The spec is built through ``ai.expand.plan_to_spec`` with ``semantic_inputs``
    (``dungeon_theme`` / ``dungeon_race`` / ``elemental_tint``) so there IS
    advisory content to clear: the semantic layer realises room roles,
    graph_depth, semantic_type, prop_hints, encounter_intent and the boss flag,
    and ``locks`` in [1, 5] realises lock gates. ``clear_advisory`` deep-copies
    (the original ``spec`` is never mutated) and resets those advisory fields
    while KEEPING ``room_theme`` and the spec-level ``dungeon_theme`` /
    ``dungeon_race`` / ``elemental_tint`` — those are realised content (they
    drive materials/textures), not suggestions — so textures/materials are
    unaffected too and the TER comparison isolates the advisory->geometry
    question.

    Scope: the TER is the asserted invariant (per the task). The ``.eqg`` bytes
    are NOT compared (the PFS footer stamps ``int(time.time())`` and would differ
    between two archives even when their contents match); ``build_raw`` reads the
    TER member back out for exactly that reason. The two builds go into separate
    ``fresh_dir()``s.

    NOTE: this is an ANALYTICAL byte-equality check on the built TER, not a live
    3D viewer confirmation — see docs/ACCEPTANCE.md.

    Validates: M0 Req 4.5, 1.5; umbrella Req 1.6.
    """
    plan = ZonePlan(
        name="advclear",
        zone_type=zone_type,
        room_count=n,
        locks=locks,
        dungeon_theme=semantic["dungeon_theme"],
        dungeon_race=semantic["dungeon_race"],
        elemental_tint=semantic["elemental_tint"],
    )
    spec = plan_to_spec(plan, seed=s)
    cleared = clear_advisory(spec)

    with fresh_dir() as out_original:
        _r1, ter_original, _zon_original = build_raw(spec, out_original)
    with fresh_dir() as out_cleared:
        _r2, ter_cleared, _zon_cleared = build_raw(cleared, out_cleared)

    assert ter_original == ter_cleared, (
        f"advisory clearing changed the TER mesh "
        f"(seed={s}, theme={zone_type}, rooms={n}, locks={locks}, "
        f"semantic={semantic}): advisory (pacing/gating) data leaked into "
        f"geometry — this is a real bug, advisory data is suggestions-only"
    )


from pathlib import Path

from analyzer.rof2check import check_eqg
from generators.zone_types import ENABLED_ZONE_TYPES
from tests.strategies import build_names

#: The enabled box zone types, as a sorted sampling domain: ``{dungeon, city}``.
#: Wilderness is enabled but builds from its own pipeline (no rooms, the bowl
#: gate), so it is excluded here; its properties live in tests/test_wilderness_*.
#: Read from the production set so if the gate ever changes, this follows.
_enabled_zone_types = st.sampled_from(sorted(ENABLED_ZONE_TYPES - {"wilderness"}))


def _format_case(zone_type, n, name, verticality="flat", size="medium"):
    """A ``(spec, label)`` case for Property 8, built through the real plan path.

    Expands a ``ZonePlan`` (whose ``name`` is the drawn Build_Name) through
    ``ai.expand.plan_to_spec`` — the same path the pipeline uses — so a passing
    property exercises an input the production path can genuinely see. The
    Build_Name flows unchanged into ``ZoneBuilder`` (``validate()`` never
    touches ``name``), so every artifact is stemmed from it and
    ``name_consistent`` is exercised on a real legal name.
    """
    plan = ZonePlan(
        name=name,
        zone_type=zone_type,
        room_count=n,
        size=size,
        verticality=verticality,
        elevation=verticality != "flat",
    )
    # Build the spec OUTSIDE the budget-sensitive path; seed is derived from the
    # drawn inputs so the case is reproducible without a separate seed draw.
    return plan, f"zone_type={zone_type}, rooms={n}, name={name!r}, size={size}"


@pytest.mark.slow
@build_settings(15)
@example(
    zone_type="dungeon", n=30, name="huge_dungeon", seed=0, size="huge",
).via("huge 30-room enabled box zone (design risk table)")
@given(
    zone_type=_enabled_zone_types,
    n=room_counts(2, 30),
    name=build_names,
    seed=seeds,
    size=st.just("medium"),
)
def test_enabled_builds_pass_format(zone_type, n, name, seed, size):
    """
    Feature: zone-generator-m1-controls-traversability, Property 8: Every
    enabled build passes the Format_Checker (umbrella P20).

    For any room-graph zone type in ``ENABLED_ZONE_TYPES`` ({dungeon, city} —
    wilderness has its own pipeline and is not drawn), seed, room count (box 2-30)
    and Build_Name (``build_names``, ``^[a-z0-9_]+$``), the Raw_Build
    (``ZonePlan`` -> ``ai.expand.plan_to_spec`` -> ``build_raw``) clears the real
    RoF2 Format_Checker: ``analyzer.rof2check.check_eqg`` on the built ``.eqg``
    returns a report with ``report.passed is True`` — every one of the eleven
    format checks (archive reads, required files, TER/ZON round-trip, ZON model
    ref, material indices, diffuse textures, collision policy, safe point,
    bounds sane, name consistent) holds on a normal enabled build.

    Three things are asserted head-on:

    * ``report.passed`` — the whole gate (Req 9.1): an enabled build is a build
      the Tier-1 format gate (task 20.3) accepts.
    * ``name_consistent`` specifically passes (its ``FormatCheck`` is present and
      ``passed``) — the archive stem, the TER/ZON entry names, the ZON model ref
      (``TER_<NAME>.TER``) and the ``.zone.json`` Sidecar's ``name`` all agree on
      the drawn Build_Name. The Sidecar is passed to ``check_eqg`` so its name is
      actually compared, not skipped (umbrella Req 9.7, build half).
    * NO ``normals_resolve`` check — M1 deliberately drops the umbrella's
      ``normals_resolve`` check (Req 9.4); its name must be absent from the
      report's check names. (The dedicated totality/absence hygiene lives in
      Property 14 / task 20.8; this property pins the exclusion on a real enabled
      build too.)

    Domain note: the design's Property 8 also covers wilderness 2-12, but
    wilderness builds from its own pipeline, so it is not drawn and the design's
    wilderness ``@example`` does not apply. Per the design risk table ("one
    pinned ``huge`` 30-room example in P20 shows whether the bound holds"), one
    ``huge`` 30-room example is pinned — for an ENABLED box zone type (dungeon),
    not wilderness — so ``bounds_sane`` is exercised at the largest footprint M1
    builds. If a normal enabled build fails a format check that is a REAL finding
    (fix the root — the builder packs what's missing, or the check is corrected
    to the true RoF2 policy — never weaken the assertion or disable the check),
    pinned here as a Regression_Example.

    NOTE: this is an ANALYTICAL check (the structural RoF2 format gate on the
    built ``.eqg``), not a live 3D viewer confirmation — see docs/ACCEPTANCE.md.

    Validates: Requirements 9.1, 9.4; umbrella P20.
    """
    plan, label = _format_case(zone_type, n, name, verticality="flat", size=size)
    spec = plan_to_spec(plan, seed=seed)

    with fresh_dir() as out:
        result, _ter_bytes, _zon_bytes = build_raw(spec, out)
        report = check_eqg(
            Path(result.eqg_path), spec, sidecar_path=result.sidecar_path
        )

        check_names = [c.name for c in report.checks]

        assert report.passed, (
            f"enabled build failed the Format_Checker ({label}):\n"
            f"  failed checks: {report.failed_checks}\n"
            + "\n".join(f"  {m}" for m in report.messages)
        )

        name_consistent = next(
            (c for c in report.checks if c.name == "name_consistent"), None
        )
        assert name_consistent is not None, (
            f"report has no name_consistent check ({label}): {check_names}"
        )
        assert name_consistent.passed, (
            f"name_consistent failed ({label}): "
            + "; ".join(name_consistent.messages)
        )

        assert "normals_resolve" not in check_names, (
            f"report must NOT carry a normals_resolve check (Req 9.4), but it "
            f"did ({label}): {check_names}"
        )
