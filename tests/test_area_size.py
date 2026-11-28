"""Area size from the plan (step 35 task 6, Req 2): a wilderness's extent comes from the
plan's Size within the stock bands (archive decision 2), random when unset, non-square."""

import pytest

from ai.expand import plan_to_spec
from ai.rule_planner import RulePlanner
from ai.schema import ZonePlan
from generators.wilderness.build import landscape_for
from generators.wilderness.matrix import (ASPECT_RANGE, DEFAULT_CELL_SIZE, SIZES,
                                          WILDERNESS_SIZE_BANDS, built_cell_size,
                                          built_extent, draw_zone_extent, zone_extent,
                                          zone_size_value)

SEEDS = range(300)
STOCK = (4000.0, 13900.0)


def _within(size, w, d):
    """The band holds the BUILT width (a 150 u matrix cell builds as 160 u)."""
    lo, hi = WILDERNESS_SIZE_BANDS[size] if size else STOCK
    bw, bd = built_extent((w, d))
    long_side, short_side = max(bw, bd), min(bw, bd)
    return (lo - built_cell_size() < long_side <= hi
            and ASPECT_RANGE[0] <= long_side / short_side <= ASPECT_RANGE[1])


@pytest.mark.parametrize("size", SIZES + ("",))
def test_extent_keeps_the_band_and_aspect_on_whole_cells(size):
    for seed in SEEDS:
        w, d = draw_zone_extent(size, seed)
        assert _within(size, w, d), (seed, w, d)
        assert w % DEFAULT_CELL_SIZE == 0 and d % DEFAULT_CELL_SIZE == 0
        assert draw_zone_extent(size, seed) == (w, d)


def test_extent_is_random_and_non_square():
    drawn = {draw_zone_extent("", s) for s in SEEDS}
    assert len(drawn) > 100
    assert sum(w != d for w, d in drawn) > 0.9 * len(drawn)
    assert {w > d for w, d in drawn} == {True, False}
    # Unset spreads over every band, as stock does.
    longs = [max(e) for e in drawn]
    assert min(longs) < 4800 and max(longs) > 10500


def test_unset_size_stays_unset_only_on_landscape_zones():
    assert ZonePlan(zone_type="wilderness").validate().size == ""
    assert ZonePlan(zone_type="dungeon").validate().size == "medium"
    assert ZonePlan(zone_type="city", size="").validate().size == "medium"
    assert ZonePlan(zone_type="wilderness", size="Huge").validate().size == "huge"
    assert ZonePlan(zone_type="wilderness", size="bogus").validate().size == "medium"


@pytest.mark.parametrize("prompt, size", [
    ("an open wilderness plain", ""), ("a vast wilderness plain", "huge"),
    ("a small wilderness meadow", "small"), ("a medium wilderness plain", "medium")])
def test_size_words_set_the_wilderness_size(prompt, size):
    plan = RulePlanner().plan(prompt).validate()
    assert plan.zone_type == "wilderness"
    assert plan.size == size


@pytest.mark.parametrize("size", ["small", ""])
def test_the_wilderness_is_built_at_the_plan_extent(size):
    plan = ZonePlan(name="t", zone_type="wilderness", size=size).validate()
    spec = plan_to_spec(plan, seed=11)
    w, d = draw_zone_extent(size, 11)
    assert zone_extent(spec.wilderness["zone_size"]) == (w, d)
    land = landscape_for(spec)
    assert land.matrix.shape == (round(w / DEFAULT_CELL_SIZE), round(d / DEFAULT_CELL_SIZE))
    # The terrain is built at the drawn extent, and that keeps the Size's band.
    nx, ny = land.synth.heights.shape
    built = (nx * land.synth.resolution, ny * land.synth.resolution)
    assert built == built_extent((w, d))
    if size:
        lo, hi = WILDERNESS_SIZE_BANDS[size]
        assert lo <= max(built) <= hi


def test_square_zones_keep_their_record():
    assert zone_size_value(1200.0) == 1200.0
    assert zone_size_value((1200.0, 1200.0)) == 1200.0
    assert zone_size_value((4800.0, 3000.0)) == [4800.0, 3000.0]


def test_aspect_follows_stock():
    """Archive decision 2's measure: stock open zones' aspect p10/p50/p90 1.02/1.21/1.96."""
    import numpy as np
    a = [max(e) / min(e) for e in (draw_zone_extent("", s) for s in range(2000))]
    for q, stock in ((10, 1.02), (50, 1.21), (90, 1.96)):
        assert abs(np.percentile(a, q) - stock) < 0.06, (q, np.percentile(a, q))
