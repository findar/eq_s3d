"""
tests/test_properties_pipeline.py
----------------------------------
Pipeline-level properties for the M0 Property_Suite. These drive the real
validated-generation entry point (``generators.pipeline.generate_validated``) —
the single guarantee shared by the server and the CLI that a gated-theme zone is
never returned unless it passed the traversability gate.

Every test here drives at least one real zone BUILD per attempt, so it is
``@pytest.mark.slow`` with a ``build_settings(...)`` budget (design Req 1.5).

Design reference: ``.kiro/specs/zone-generator-m0-hygiene/design.md``,
Correctness Property 15 (umbrella P2).
"""

from __future__ import annotations

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from generators.layout import LayoutGenerator
from generators.pipeline import generate_validated, GenerationFailed, ValidatedBuild

from tests.pbt_helpers import build_settings, fresh_dir

# A known-navigable dungeon seed. The spy factory ignores the seed the pipeline
# hands it for GEOMETRY (it always builds this flat, connected dungeon) so the
# traversability gate passes on the first attempt — while still recording which
# seed the pipeline asked for. This is the established `test_pipeline._good_*`
# idiom: the factory decides the outcome, the pipeline owns seed selection.
_NAVIGABLE_SEED = 1


@pytest.mark.slow
@build_settings(15)
@given(
    max_attempts=st.integers(min_value=1, max_value=8),
    rng=st.randoms(use_true_random=False),
)
def test_returned_build_is_validated(max_attempts, rng):
    """
    Feature: zone-generator-m0-hygiene, Property 15: Returned builds passed the
    gate (umbrella P2).

    When ``generate_validated`` RETURNS a build for a gated theme (dungeon), that
    build carries ``validated=True`` — the traversability gate ran and passed —
    and its provenance is internally consistent: the pipeline made between one
    and ``max_attempts`` factory calls, and the ``seed`` stamped on the returned
    build is exactly the last seed the factory was handed (the one that produced
    the passing geometry). Exhaustion / failure is out of scope here — a raised
    ``GenerationFailed`` is assumed away (covered by Property 16, task 12.2).

    Validates: M0 Req 5.1, 1.5; umbrella P2.
    """
    seeds_seen: list[int] = []
    calls = {"n": 0}

    def spec_factory(seed: int):
        # Record what the pipeline asked for, then build a genuinely navigable
        # dungeon (fixed good seed) so the gate passes.
        seeds_seen.append(seed)
        calls["n"] += 1
        return LayoutGenerator(theme="dungeon", seed=_NAVIGABLE_SEED).generate(
            "p15", room_count=3
        )

    with fresh_dir() as out:
        try:
            result = generate_validated(
                spec_factory,
                theme="dungeon",
                zone_id="p15",
                output_dir=out,
                write_glb=False,
                max_attempts=max_attempts,
                rng=rng,
                failure_log=None,
            )
        except GenerationFailed:
            # Only RETURNING calls are in scope for this property.
            assume(False)

    assert isinstance(result, ValidatedBuild)
    assert result.validated, "returned gated build did not pass the gate"
    assert 1 <= calls["n"] <= max_attempts, (
        f"factory called {calls['n']} times, outside [1, {max_attempts}]"
    )
    assert seeds_seen, "factory was never called"
    assert result.seed == seeds_seen[-1], (
        f"returned seed {result.seed} != last seed handed to factory "
        f"{seeds_seen[-1]}"
    )


# A dungeon that is navigable EXCEPT for one isolated room with no corridor —
# unreachable regardless of corridor routing, so the traversability gate always
# rejects it (the established `tests/test_pipeline._broken_spec` pattern). The
# room count stays small (n 2-4) so an 8-attempt unpinned example is cheap.
from generators.zone_spec import RoomSpec  # noqa: E402  (grouped with its use)


def _forced_fail_factory(rooms: int):
    """A spec_factory(seed) that always builds a guaranteed-failing dungeon.

    It honours the seed the pipeline hands it for the base dungeon geometry
    (keyed on the seed, as required), then appends one far-away isolated room so
    the Traversal_Validator rejects every attempt no matter the seed.
    """

    def factory(seed: int):
        spec = LayoutGenerator(theme="dungeon", seed=seed).generate(
            "p16", room_count=rooms
        )
        spec.rooms.append(RoomSpec(
            id="isolated", center_x=100_000.0, center_y=100_000.0, floor_z=0.0,
            width=200, depth=200, height=100,
        ))
        return spec

    return factory


@pytest.mark.slow
@build_settings(15)
@given(
    pinned=st.booleans(),
    seed=st.integers(min_value=0, max_value=2 ** 31 - 1),
    max_attempts=st.integers(min_value=1, max_value=8),
    rooms=st.integers(min_value=2, max_value=4),
)
def test_forced_failure_reported(pinned, seed, max_attempts, rooms):
    """
    Feature: zone-generator-m0-hygiene, Property 16: Forced failures are
    reported, never swapped (umbrella P2, pinned + exhaustion).

    When every Raw_Build of a gated (dungeon) zone fails the traversability
    gate, ``generate_validated`` raises ``GenerationFailed`` rather than ever
    returning a broken zone — and the failure it raises tells the honest story
    of what was tried:

    * PINNED (a ``seed`` is passed): the pipeline respects the explicit request,
      so it builds exactly once and errors out with ``pinned=True``,
      ``attempts == 1``, and the single recorded failure carrying that EXACT
      pinned seed — never swapped for another.
    * UNPINNED (no ``seed``, ``max_attempts`` 1-8, a non-binding timeout): the
      pipeline exhausts all its attempts picking fresh seeds, then reports
      ``pinned=False``, ``timed_out=False`` and ``attempts == max_attempts``.

    Validates: M0 Req 5.2, 5.6, 1.5; umbrella Req 1.6.
    """
    factory = _forced_fail_factory(rooms)

    with fresh_dir() as out:
        with pytest.raises(GenerationFailed) as excinfo:
            generate_validated(
                factory,
                theme="dungeon",
                zone_id="p16",
                seed=seed if pinned else None,
                output_dir=out,
                write_glb=False,
                max_attempts=max_attempts,
                timeout_s=1e9,  # non-binding: exhaustion, never timeout
                rng=None,
                failure_log=None,
            )

    err = excinfo.value

    if pinned:
        assert err.pinned is True, "pinned failure not flagged pinned"
        assert err.attempts == 1, (
            f"pinned seed retried: attempts={err.attempts}, expected 1"
        )
        assert err.failures, "no failure recorded"
        assert err.failures[0].seed == seed, (
            f"reported seed {err.failures[0].seed} != pinned seed {seed} "
            "(the pinned seed was swapped)"
        )
    else:
        assert err.pinned is False, "unpinned failure flagged pinned"
        assert err.timed_out is False, (
            "exhaustion reported as a timeout (timeout was non-binding)"
        )
        assert err.attempts == max_attempts, (
            f"attempts={err.attempts}, expected all {max_attempts} exhausted"
        )


@pytest.mark.slow
@build_settings(10)
@given(k=st.integers(min_value=3, max_value=10))
def test_fresh_seeds_vary(k):
    """
    Feature: zone-generator-m0-hygiene, Property 17: Fresh seeds vary
    (umbrella P10).

    When ``generate_validated`` is called repeatedly with NO pinned ``seed`` and
    NO explicit ``rng``, the pipeline draws a brand-new seed for each build via
    ``_fresh_seed(None)`` — the "randomness is a feature" path: same inputs must
    not give the same output. Across ``k`` (3-10) such unpinned calls on the same
    navigable 2-room dungeon, a spy ``spec_factory`` records every seed the
    pipeline hands it. Two invariants hold: every recorded seed is a valid 31-bit
    seed in ``[0, 2147483647]``, and the recorded seeds are NOT all identical.
    (A rare collision between two of the k draws is acceptable — "not all equal"
    is the bar, not "all distinct"; all k identical would mean the pipeline isn't
    actually drawing fresh seeds.) ``_fresh_seed(None)`` uses the module ``random``
    generator, which is independent of Hypothesis's (derandomized) INPUT draws, so
    the seeds still vary across the k calls within one example.

    Validates: M0 Req 5.3, 1.5; umbrella Req 1.6.
    """
    seeds_seen: list[int] = []

    def spec_factory(seed: int):
        # Record the seed the pipeline drew, then build a genuinely navigable
        # 2-room dungeon (fixed good seed) so the gate passes on the first
        # attempt and the call returns — same 12.1 spy idiom.
        seeds_seen.append(seed)
        return LayoutGenerator(theme="dungeon", seed=_NAVIGABLE_SEED).generate(
            "p17", room_count=2
        )

    with fresh_dir() as out:
        for _ in range(k):
            result = generate_validated(
                spec_factory,
                theme="dungeon",
                zone_id="p17",
                # rng OMITTED and seed OMITTED: each call draws a fresh seed via
                # _fresh_seed(None) off the module random generator.
                output_dir=out,
                write_glb=False,
                failure_log=None,
            )
            assert isinstance(result, ValidatedBuild)

    assert len(seeds_seen) == k, (
        f"factory called {len(seeds_seen)} times, expected {k}"
    )
    assert all(0 <= s <= 2_147_483_647 for s in seeds_seen), (
        f"a drawn seed is outside [0, 2147483647]: {seeds_seen}"
    )
    assert len(set(seeds_seen)) > 1, (
        f"all {k} fresh seeds were identical ({seeds_seen[0]}) — the pipeline "
        "is not drawing fresh seeds (randomness-is-a-feature regression)"
    )
