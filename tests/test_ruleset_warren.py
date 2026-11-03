"""The shipped warren set and its theme entry (graph-layout task 6, Req 5.1 and
5.2, G6).

The warren bands rest on one stock zone (blackburrow; design.md finding 5), so
each of its values is widened by +-0.05 into a band, as the finding says to.
Judged like the classic test, as a sweep over seeds and 5-30 rooms: mean and
median inside each band, p10-p90 overlapping it, and the graphs of 20 rooms
or more (closest to the stock zone's 37 chambers) with their mean in each
shape band. Then warren against classic_eq over the same seeds, in finding 5's
direction: more loops per room, a shallower deep end, more small rooms, and a
dead-end share no higher than classic's.

The sweep is the file's whole point as an extensibility test: warren.toml is
data only, grown by the same loader and driver as classic_eq.
"""

from __future__ import annotations

import statistics
from pathlib import Path

import pytest

from generators.topology.graph import SIZE_CLASSES
from generators.topology.rewrite import BuildContext, grow, invariant_violation
from generators.topology.ruleset import load_for_theme, load_rule_set

RULES = Path(__file__).resolve().parents[1] / "rules" / "topology"
WARREN = RULES / "warren.toml"
CLASSIC = RULES / "classic_eq.toml"

SEEDS = range(20)
ROOMS = range(5, 31)
WIDEN = 0.05

# design.md finding 5, "Bands", warren column (blackburrow alone).
BLACKBURROW = {
    "dead_end": 0.16, "cycles_per_room": 0.24, "deep_end": 0.22,
    "tiny": 0.03, "small": 0.41, "medium": 0.30, "large": 0.14, "huge": 0.14,
}
SHAPES = ("dead_end", "cycles_per_room", "deep_end")
BANDS = {m: (max(0.0, v - WIDEN), v + WIDEN) for m, v in BLACKBURROW.items()}


def _measures(graph, n):
    out = {"n": n, "dead_end": graph.dead_end_share(),
           "cycles_per_room": graph.cycle_rank() / n,
           "deep_end": graph.deep_end_distance()}
    out.update(graph.size_mix())
    return out


def _sweep(rule_set):
    ctx = BuildContext(race_scale=1.0)
    rows = []
    for seed in SEEDS:
        for n in ROOMS:
            g = grow(rule_set, n, seed * 1000 + n, ctx).graph
            assert len(g.rooms()) == n and not g.areas()
            assert invariant_violation(g) is None
            rows.append(_measures(g, n))
    return rows


def _summary(values):
    dec = statistics.quantiles(values, n=10, method="inclusive")
    return statistics.fmean(values), statistics.median(values), dec[0], dec[-1]


@pytest.fixture(scope="module")
def warren():
    return load_rule_set(WARREN)


@pytest.fixture(scope="module")
def warren_rows(warren):
    return _sweep(warren)


# ---------------------------------------------------------------------------
# The file loads, reads as an example, and the theme points at it
# ---------------------------------------------------------------------------

def test_warren_loads_and_reads_as_specified(warren):
    assert warren.name == "warren" and warren.placement == "spring"
    assert warren.kinds == (), "warren uses only the base room kinds"
    assert sum(n.kind == "entrance" for n in warren.start_nodes) == 1
    used = {r for s in warren.recipe for r in s.apply}
    assert used == set(warren.rules), "every rule takes part in some stage"
    assert warren.recipe[-1].is_rest
    rest = [warren.rules[r] for r in warren.recipe[-1].apply]
    assert any(r.finishes_area for r in rest)
    assert any(r.rooms_added > 0 for r in rest), "the rest stage must still grow"
    assert all(r.description for r in warren.rules.values())


def test_warren_is_commented():
    text = WARREN.read_text(encoding="utf-8")
    assert sum(1 for x in text.splitlines() if x.lstrip().startswith("#")) >= 20
    for name in load_rule_set(WARREN).rules:
        block = text.split(f"[rules.{name}]")[0].rstrip().splitlines()
        assert block and block[-1].lstrip().startswith("#"), f"rule {name} has no comment"


def test_warren_theme(warren):
    via_theme = load_for_theme(RULES, "warren")
    assert via_theme.name == "warren" and via_theme.layers == ()
    assert via_theme.rules == warren.rules and via_theme.recipe == warren.recipe


# ---------------------------------------------------------------------------
# G6: the warren bands, and the difference from classic_eq
# ---------------------------------------------------------------------------

def test_g6_warren_grows_into_the_warren_bands(warren_rows):
    rows = warren_rows
    bad = []
    for m in SHAPES:
        lo, hi = BANDS[m]
        mean, p50, p10, p90 = _summary([r[m] for r in rows])
        big = statistics.fmean(r[m] for r in rows if r["n"] >= 20)
        if not (lo <= mean <= hi and lo <= p50 <= hi and p10 <= hi and p90 >= lo
                and lo <= big <= hi):
            bad.append(f"{m}: mean {mean:.3f} p50 {p50:.3f} p10-p90 {p10:.3f}-{p90:.3f} "
                       f"mean(n>=20) {big:.3f}; band {lo:.2f}-{hi:.2f}")
    for size in SIZE_CLASSES:
        lo, hi = BANDS[size]
        mean, _, p10, p90 = _summary([r[size] for r in rows])
        if not (lo <= mean <= hi and p10 <= hi and p90 >= lo):
            bad.append(f"{size} share: mean {mean:.3f} p10-p90 {p10:.3f}-{p90:.3f}; "
                       f"band {lo:.2f}-{hi:.2f}")
    assert not bad, "\n".join(bad)


def test_g6_warren_differs_from_classic_eq_as_finding_5_says(warren_rows):
    classic = _sweep(load_rule_set(CLASSIC))

    def mean(rows, m):
        return statistics.fmean(r[m] for r in rows)

    w = {m: mean(warren_rows, m) for m in BLACKBURROW}
    c = {m: mean(classic, m) for m in BLACKBURROW}
    report = ", ".join(f"{m} {w[m]:.3f} vs {c[m]:.3f}" for m in BLACKBURROW)
    assert w["cycles_per_room"] > c["cycles_per_room"] + 0.05, report   # more loops
    assert w["deep_end"] < c["deep_end"] - 0.05, report                 # shallower
    assert w["small"] > c["small"] + 0.05, report                       # more small rooms
    assert w["tiny"] > c["tiny"], report
    assert w["dead_end"] <= c["dead_end"], report                       # low end of classic
