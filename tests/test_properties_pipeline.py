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
