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
