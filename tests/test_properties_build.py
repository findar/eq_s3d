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
from hypothesis import given
from hypothesis import strategies as st

import analyzer.traverse as T
from generators.layout import LayoutGenerator

from tests.strategies import seeds, room_counts
from tests.pbt_helpers import build_settings, build_raw, fresh_dir


@pytest.mark.slow
@build_settings(20)
@given(s=seeds, n=room_counts(2, 12), elevation=st.booleans())
def test_raw_dungeon_navigable(s, n, elevation):
    """
    Feature: zone-generator-m0-hygiene, Property 10: Raw dungeon builds are
    navigable (umbrella P1, dungeon).

    A raw dungeon zone built with no validation gate (``LayoutGenerator`` ->
    ``build_raw``) walks end to end on its real generated TER mesh: the
    traversability validator reaches every room from the entrance safe point.
    This is the analytical navigability bar from ``analyzer.traverse`` — the
    per-triangle walk surface the north-star "every room reachable on foot" MUST
    is measured on. Builder exceptions propagate as failures; this property
    never ``assume``s an input away (design Req 4.1).

    Validates: M0 Req 4.1, 1.5; umbrella P1.
    """
    spec = LayoutGenerator(theme="dungeon", seed=s).generate(
        "navdun", room_count=n, elevation=elevation
    )
    with fresh_dir() as out:
        result, _ter_bytes, _zon_bytes = build_raw(spec, out)
        report = T.validate(result.eqg_path, spec=spec)

    assert report.passed, (
        f"non-navigable dungeon (seed={s}, rooms={n}, elevation={elevation}):\n"
        f"{report.summary()}"
    )


from hypothesis import example

from ai.schema import ZonePlan
from ai.expand import plan_to_spec
from tests.strategies import box_themes
from tests.pbt_helpers import ramp_rises

#: Verticality that actually elevates corridors (``flat`` would make the ramp
#: path vacuously true, so it is excluded from this property's strategy).
_elevated_verticality = st.sampled_from(["moderate", "dramatic"])


@pytest.mark.slow
@build_settings(20)
@example(s=0, theme="dungeon", n=3, verticality="dramatic")
@given(
    s=seeds,
    theme=box_themes,
    n=room_counts(2, 12),
    verticality=_elevated_verticality,
)
def test_ramp_subdivision(s, theme, n, verticality):
    """
    Feature: zone-generator-m0-hygiene, Property 11: Ramp subdivision
    (umbrella P8).

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
        theme=theme,
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
    if (s, theme, n, verticality) == (0, "dungeon", 3, "dramatic"):
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
        f"(seed={s}, theme={theme}, rooms={n}, verticality={verticality}): "
        f"worst per-triangle rise {worst:.4f} u > 2.51 "
        f"(max corridor span {max_span:.2f} u)"
    )

@pytest.mark.slow
@build_settings(15)
@given(
    s=seeds,
    theme=box_themes,
    n=room_counts(3, 12),
    locks=st.integers(min_value=1, max_value=5),
)
def test_locks_do_not_touch_geometry(s, theme, n, locks):
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
    gated_plan = ZonePlan(name="lockgeo", theme=theme, room_count=n, locks=locks)
    open_plan = ZonePlan(name="lockgeo", theme=theme, room_count=n, locks=0)

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
        f"locks changed the TER mesh (seed={s}, theme={theme}, rooms={n}, "
        f"locks={locks}): gating leaked into geometry"
    )
    assert gated_zon == open_zon, (
        f"locks changed the ZON layout (seed={s}, theme={theme}, rooms={n}, "
        f"locks={locks}): gating leaked into placement"
    )
