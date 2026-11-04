"""The shipped classic_eq set, the temple layer and the theme map (graph-layout
task 5, Req 5.1 and 5.3, G6).

G6 compares the grown graphs with design.md finding 5's classic bands (p10-p90
over the five stock dungeons kept). Our graphs have 5-30 rooms where those
zones have 24-77 chambers, and a small graph can't show the shape (with 5
rooms the entrance and the deep end are usually 2 of the dead ends, and the
deep end is at least 2 hops = 0.4 away). So the sweep is judged as a whole,
not graph by graph: its mean and median sit inside each band and its p10-p90
spread overlaps it. The graphs of 20 rooms or more, closest to the stock
zones' size, must also have their mean inside each shape band.
"""

from __future__ import annotations

import copy
import statistics
from pathlib import Path

import pytest

from generators.topology.graph import SIZE_CLASSES
from generators.topology.rewrite import BuildContext, grow, invariant_violation
from generators.topology.ruleset import (
    load_for_theme, load_layer, load_rule_set, load_theme_map,
)

RULES = Path(__file__).resolve().parents[1] / "rules" / "topology"
BASE = RULES / "classic_eq.toml"
TEMPLE = RULES / "layers" / "temple.toml"

SEEDS = range(40)
ROOMS = range(5, 31)

# design.md finding 5, "Bands (p10-p90 over the zones kept)", classic_eq column.
SHAPE_BANDS = {
    "dead_end": (0.12, 0.35),
    "cycles_per_room": (0.07, 0.25),
    "deep_end": (0.26, 0.39),
}
SIZE_BANDS = {
    "tiny": (0.0, 0.0),
    "small": (0.17, 0.38),
    "medium": (0.23, 0.52),
    "large": (0.20, 0.24),
    "huge": (0.09, 0.18),
}
# The rules the design names for the base set.
NAMED_RULES = ("lengthen", "passage", "branch", "side_wing", "crossroads", "loop",
               "shortcut", "finish", "great_hall")


def _seed(seed: int, n: int) -> int:
    return seed * 1000 + n


def _measures(graph, n):
    mix = graph.size_mix()
    out = {"n": n, "dead_end": graph.dead_end_share(),
           "cycles_per_room": graph.cycle_rank() / n,
           "deep_end": graph.deep_end_distance()}
    out.update(mix)
    return out


def _g3(graph, n):
    assert len(graph.rooms()) == n and not graph.areas()
    assert invariant_violation(graph) is None


@pytest.fixture(scope="module")
def classic():
    return load_rule_set(BASE)


# ---------------------------------------------------------------------------
# The files load and say what they should
# ---------------------------------------------------------------------------

def test_every_shipped_file_loads():
    sets = sorted(p for p in RULES.glob("*.toml") if p.stem != "themes")
    layers = sorted((RULES / "layers").glob("*.toml"))
    assert BASE in sets and TEMPLE in layers
    for p in sets:
        load_rule_set(p)
    for p in layers:
        load_layer(p)
    tmap = load_theme_map(RULES / "themes.toml")
    for theme, entry in tmap.entries.items():
        assert (RULES / f"{entry.base}.toml").is_file(), theme
        for layer in entry.layers:
            assert (RULES / "layers" / f"{layer}.toml").is_file(), (theme, layer)


def test_classic_eq_reads_as_specified(classic):
    assert classic.name == "classic_eq" and classic.placement == "spring"
    assert [(n.id, n.kind, n.size) for n in classic.start_nodes] == [
        ("e", "entrance", "medium"), ("a", "Area", None), ("d", "deep", "huge")]
    assert [(e.a, e.b) for e in classic.start_edges] == [("e", "a"), ("a", "d")]
    assert set(NAMED_RULES) <= set(classic.rules)
    gh = classic.rules["great_hall"].when
    assert [(c.key, c.op, c.value) for c in gh] == [("race_scale", ">=", 1.4)]
    used = {r for s in classic.recipe for r in s.apply}
    assert used == set(classic.rules), "every rule takes part in some stage"
    assert classic.recipe[-1].is_rest
    rest = [classic.rules[r] for r in classic.recipe[-1].apply]
    assert any(r.finishes_area for r in rest)
    assert any(r.rooms_added > 0 for r in rest), "the rest stage must still grow"
    assert all(r.description for r in classic.rules.values())


def test_files_are_commented():
    for p in (BASE, TEMPLE, RULES / "themes.toml"):
        lines = p.read_text(encoding="utf-8").splitlines()
        assert sum(1 for x in lines if x.lstrip().startswith("#")) >= 5, p.name
    text = BASE.read_text(encoding="utf-8")
    for name in load_rule_set(BASE).rules:
        block = text.split(f"[rules.{name}]")[0].rstrip().splitlines()
        assert block and block[-1].lstrip().startswith("#"), f"rule {name} has no comment"


def test_theme_map():
    default = load_for_theme(RULES, None)
    assert default.name == "classic_eq" and default.layers == ()
    assert load_for_theme(RULES, "tomb").layers == ()           # unlisted: default
    temple = load_for_theme(RULES, "temple")
    assert temple.name == "classic_eq" and temple.layers == ("temple",)
    assert "nave" in temple.rules
    assert [s.name for s in temple.recipe] == ["Main path", "Nave", "Side rooms", "Loops",
                                               "Finish"]
    side = next(s for s in temple.recipe if s.name == "Side rooms")
    assert side.apply["nave"] == 1


# ---------------------------------------------------------------------------
# G6: the classic bands
# ---------------------------------------------------------------------------

def _summary(values):
    dec = statistics.quantiles(values, n=10, method="inclusive")
    return statistics.fmean(values), statistics.median(values), dec[0], dec[-1]


def test_g6_classic_eq_grows_into_the_classic_bands(classic):
    """One sweep, every measure; failures are collected so one run shows them all."""
    ctx = BuildContext(race_scale=1.0)
    rows = []
    for seed in SEEDS:
        for n in ROOMS:
            g = grow(classic, n, _seed(seed, n), ctx).graph
            _g3(g, n)
            rows.append(_measures(g, n))
    bad = []
    for measure, (lo, hi) in SHAPE_BANDS.items():
        mean, p50, p10, p90 = _summary([r[measure] for r in rows])
        big = statistics.fmean(r[measure] for r in rows if r["n"] >= 20)
        if not (lo <= mean <= hi and lo <= p50 <= hi and p10 <= hi and p90 >= lo
                and lo <= big <= hi):
            bad.append(f"{measure}: mean {mean:.3f} p50 {p50:.3f} p10-p90 {p10:.3f}-{p90:.3f} "
                       f"mean(n>=20) {big:.3f}; band {lo}-{hi}")
    for size in SIZE_CLASSES:
        lo, hi = SIZE_BANDS[size]
        mean, _, p10, p90 = _summary([r[size] for r in rows])
        if not (lo <= mean <= hi and p10 <= hi and p90 >= lo):
            bad.append(f"{size} share: mean {mean:.3f} p10-p90 {p10:.3f}-{p90:.3f}; band {lo}-{hi}")
    assert not bad, "\n".join(bad)


def test_great_hall_only_for_big_races(classic):
    # Ogres (1.4) and giants (2.2) are the big races; trolls (1.15) are not.
    small = 0
    big = {1.4: 0, 2.2: 0}
    for seed in range(10):
        small += sum(a.rule == "great_hall"
                     for a in grow(classic, 20, seed, BuildContext(race_scale=1.15)).applied)
        for scale in big:
            res = grow(classic, 20, seed, BuildContext(race_scale=scale))
            _g3(res.graph, 20)
            big[scale] += sum(a.rule == "great_hall" for a in res.applied)
    assert small == 0 and all(big.values()), big


# ---------------------------------------------------------------------------
# The temple layer
# ---------------------------------------------------------------------------

def test_temple_builds_apply_nave_and_leave_the_base_alone(classic):
    before_bytes = BASE.read_bytes()
    before = copy.deepcopy(classic)
    temple = load_for_theme(RULES, "temple")
    naves = 0
    for seed in range(10):
        # From 7 rooms: the nave adds 3 to the entrance, the deep end and the
        # main path, so a smaller temple has no room for it (task 14 found the
        # nave missing below 10 rooms when its stage share rounded to 0).
        for n in (7, 8, 9, 10, 15, 20, 25, 30):
            res = grow(temple, n, _seed(seed, n), BuildContext(theme="temple", race_scale=1.0))
            _g3(res.graph, n)
            naves += any(a.rule == "nave" for a in res.applied)
    assert naves == 80, f"nave in only {naves} of 80 temple builds of 7+ rooms"
    assert classic == before
    assert load_rule_set(BASE) == before
    assert BASE.read_bytes() == before_bytes
    assert "nave" not in classic.rules
