"""Rewrite driver, recipes and layers (graph-layout task 4, Req 4, G3-G5).

Small rule sets are written to ``tmp_path``; the shipped ``rules/topology``
sets belong to tasks 5 and 6.
"""

from __future__ import annotations

import copy
import random

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from generators.topology.graph import AREA, Edge, Node, TopologyGraph
from generators.topology.rewrite import (
    BuildContext, TopologyError, apply_rule, find_matches, grow, invariant_violation,
    shortest_cycle_through, start_graph_for,
)
from generators.topology.ruleset import load_for_theme, load_rule_set

# A set every n in 1..30 can finish: the rest stage can still lengthen.
GROW = '''
[set]
name = "grow"
description = "Test set"
placement = "spring"
start_nodes = [ {id = "e", kind = "entrance", size = "medium"},
                {id = "a", kind = "Area"},
                {id = "d", kind = "deep", size = "huge"} ]
start_edges = [ {a = "e", b = "a"}, {a = "a", b = "d"} ]

[rules.lengthen]
description = "Longer way"
match = [ {id = "x", kind = "Area"} ]
replace = [ {id = "x", kind = "Area"}, {id = "y", kind = "Area"} ]
edges = [ {a = "x", b = "y"} ]
reattach = { x = ["x", "y"] }

[rules.passage]
description = "A passage going down"
match = [ {id = "x", kind = "Area"} ]
replace = [ {id = "p", kind = "passage", size = "small"}, {id = "x", kind = "Area"} ]
edges = [ {a = "p", b = "x", rel = "below"} ]
reattach = { x = ["p", "x"] }

[rules.branch]
description = "A dead end"
match = [ {id = "x", kind = "Area"} ]
replace = [ {id = "x", kind = "Area"}, {id = "l", kind = "lair", size = "small"} ]
edges = [ {a = "x", b = "l"} ]
reattach = { x = ["x"] }

[rules.loop]
description = "A ring of three"
match = [ {id = "x", kind = "Area"} ]
replace = [ {id = "x", kind = "Area"}, {id = "a", kind = "chamber", size = "small"},
            {id = "b", kind = "chamber", size = "small"} ]
edges = [ {a = "x", b = "a"}, {a = "a", b = "b"}, {a = "b", b = "x"} ]
reattach = { x = ["x"] }

[rules.shortcut]
description = "Join two chambers"
match = [ {id = "p", kind = "chamber"}, {id = "q", kind = "chamber"} ]
match_hops = { p_q = [2, 3] }
replace = [ {id = "p", kind = "chamber", size = "medium"},
            {id = "q", kind = "chamber", size = "medium"} ]
edges = [ {a = "p", b = "q"} ]
reattach = { p = ["p"], q = ["q"] }

[rules.great_hall]
description = "Big races"
when = { race_scale = ">=1.5" }
match = [ {id = "x", kind = "Area"} ]
replace = [ {id = "x", kind = "Area"}, {id = "g", kind = "hall", size = "huge"} ]
edges = [ {a = "x", b = "g"} ]
reattach = { x = ["g", "x"] }

[rules.finish]
description = "Finish"
match = [ {id = "x", kind = "Area"} ]
replace = [ {id = "x", kind = "chamber", size = "medium"} ]
reattach = { x = ["x"] }

[[recipe]]
stage = "Main path"
apply = { lengthen = 3, passage = 1 }
share = 0.4

[[recipe]]
stage = "Side rooms"
apply = { branch = 3, loop = 1, great_hall = 1 }
share = 0.4

[[recipe]]
stage = "Loops"
apply = { shortcut = 1 }
share = 0.1

[[recipe]]
stage = "Finish"
apply = { finish = 1, lengthen = 1, branch = 1 }
share = "rest"
'''

# Churn never spends its budget: chamber <-> hub forever.
CHURN = '''
[set]
name = "churn"
description = "Never stops"
placement = "spring"
start_nodes = [ {id = "e", kind = "entrance", size = "medium"},
                {id = "c", kind = "chamber", size = "small"} ]
start_edges = [ {a = "e", b = "c"} ]

[rules.flip]
description = "chamber to hub"
match = [ {id = "x", kind = "chamber"} ]
replace = [ {id = "x", kind = "hub", size = "small"} ]
reattach = { x = ["x"] }

[rules.flop]
description = "hub to chamber"
match = [ {id = "x", kind = "hub"} ]
replace = [ {id = "x", kind = "chamber", size = "small"} ]
reattach = { x = ["x"] }

[rules.finish]
description = "Finish"
match = [ {id = "x", kind = "Area"} ]
replace = [ {id = "x", kind = "chamber", size = "medium"} ]
reattach = { x = ["x"] }

[[recipe]]
stage = "Churn"
apply = { flip = 1, flop = 1 }
share = 0.5

[[recipe]]
stage = "Finish"
apply = { finish = 1 }
share = "rest"
'''

CHAPEL_LAYER = '''
[layer]
name = "chapel"
description = "A chapel stage"
fits = ["grow"]

[rules.chapel]
description = "A chapel off the way"
match = [ {id = "x", kind = "Area"} ]
replace = [ {id = "x", kind = "Area"}, {id = "c", kind = "hall", size = "large"} ]
edges = [ {a = "x", b = "c"} ]
reattach = { x = ["x"] }

[stages."Side rooms"]
apply = { chapel = 1 }

[[insert]]
after = "Main path"
stage = "Chapels"
apply = { chapel = 1 }
share = 0.05
'''

THEMES = '''
default = { base = "grow" }
temple  = { base = "grow", layers = ["chapel"] }
'''


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


@pytest.fixture(scope="module")
def grow_set(tmp_path_factory):
    return load_rule_set(_write(tmp_path_factory.mktemp("sets"), "grow.toml", GROW))


def _g(nodes, edges):
    """nodes: {id: kind}; edges: (a, b) or (a, b, rel)."""
    ns = [Node(i, k, None if k == AREA else "small") for i, k in nodes.items()]
    return TopologyGraph(ns, [Edge(*e) for e in edges])


def _rule_set(tmp_path, rules, name="t"):
    """A set wrapping extra rule TOML, for the matcher tests."""
    text = f'''
[set]
name = "{name}"
description = "matcher"
placement = "spring"
start_nodes = [ {{id = "e", kind = "entrance", size = "medium"}} ]
{rules}
[rules.finish]
description = "Finish"
match = [ {{id = "x", kind = "Area"}} ]
replace = [ {{id = "x", kind = "chamber", size = "medium"}} ]
reattach = {{ x = ["x"] }}

[[recipe]]
stage = "Finish"
apply = {{ finish = 1 }}
share = "rest"
'''
    return load_rule_set(_write(tmp_path, f"{name}.toml", text))


# --- the matcher -------------------------------------------------------------

def test_one_node_match_lists_every_kind_match_sorted(grow_set):
    g = _g({"e": "entrance", "b": AREA, "a": AREA, "c": "chamber"},
           [("e", "a"), ("a", "b"), ("b", "c")])
    assert find_matches(g, grow_set.rules["lengthen"]) == [("a",), ("b",)]
    assert find_matches(g, grow_set.rules["shortcut"]) == []


def test_two_node_match_with_hops(grow_set):
    # c1 - c2 - c3 - c4 - c5, plus c1 - x: shortcut wants chambers 2-3 hops apart.
    g = _g({f"c{i}": "chamber" for i in range(1, 6)} | {"x": AREA},
           [("c1", "c2"), ("c2", "c3"), ("c3", "c4"), ("c4", "c5"), ("c1", "x")])
    got = find_matches(g, grow_set.rules["shortcut"])
    pairs = {("c1", "c3"), ("c1", "c4"), ("c2", "c4"), ("c2", "c5"), ("c3", "c5")}
    assert got == sorted(pairs | {(b, a) for a, b in pairs})


def test_three_node_match_with_edges_is_induced_and_directed(tmp_path):
    s = _rule_set(tmp_path, '''
[rules.chain]
description = "Three chambers in a row, the middle one above the first"
match = [ {id = "x", kind = "chamber"}, {id = "y", kind = "hub"}, {id = "z", kind = "chamber"} ]
match_edges = [ {a = "x", b = "y", rel = "above"}, {a = "y", b = "z"} ]
replace = [ {id = "x", kind = "chamber", size = "small"}, {id = "y", kind = "hub", size = "small"},
            {id = "z", kind = "chamber", size = "small"} ]
edges = [ {a = "x", b = "y"}, {a = "y", b = "z"} ]
reattach = { x = ["x"], y = ["y"], z = ["z"] }
''')
    rule = s.rules["chain"]
    # h is above a and above b; c sits level with h; a-b-h is a triangle.
    g = _g({"a": "chamber", "b": "chamber", "c": "chamber", "h": "hub"},
           [("a", "h", "above"), ("b", "h", "above"), ("h", "c", "level"), ("a", "b")])
    # (a, h, b) and (b, h, a) are not induced (a-b edge); c-h is level, so c can't be x.
    assert find_matches(g, rule) == [("a", "h", "c"), ("b", "h", "c")]
    g.remove_edge("a", "b")
    assert find_matches(g, rule) == [("a", "h", "b"), ("a", "h", "c"),
                                     ("b", "h", "a"), ("b", "h", "c")]
    g.remove_edge("a", "h")
    g.add_edge("a", "h", rel="below")              # h is now below a
    assert find_matches(g, rule) == [("b", "h", "a"), ("b", "h", "c")]


def test_when_conditions(grow_set):
    rule = grow_set.rules["great_hall"]
    g = _g({"e": "entrance", "a": AREA}, [("e", "a")])
    assert find_matches(g, rule) == []
    assert find_matches(g, rule, BuildContext(race_scale=1.0)) == []
    assert find_matches(g, rule, BuildContext(race_scale=2.0)) == [("a",)]
    assert find_matches(g, rule, {"race_scale": 1.5}) == [("a",)]


# --- applying ----------------------------------------------------------------

def test_reattach_one_target_and_fresh_ids(grow_set):
    g = _g({"e": "entrance", "a": AREA, "d": "deep"}, [("e", "a"), ("a", "d", "above")])
    touched = apply_rule(g, grow_set.rules["branch"], ("a",))
    assert touched == ("a", "n000")
    assert g.node("n000").kind == "lair" and g.node("a").kind == AREA
    assert g.neighbours("a") == ["d", "e", "n000"]
    assert g.edge("a", "d").rel == "above"


def test_reattach_splits_in_order_and_keeps_direction(grow_set):
    # Outside edges of a, by neighbour id: b, c, d. Contiguous chunks: x <- b, c; y <- d.
    g = _g({"a": AREA, "b": "chamber", "c": "chamber", "d": "chamber"},
           [("a", "b", "above"), ("c", "a", "above"), ("a", "d", "level")])
    touched = apply_rule(g, grow_set.rules["lengthen"], ("a",))
    assert touched == ("a", "n000")
    assert g.neighbours("a") == ["b", "c", "n000"]
    assert g.neighbours("n000") == ["a", "d"]
    assert g.edge("a", "b").rel == "above"            # b still above
    assert g.edge("c", "a").rel == "above"            # a still above c
    assert g.edge("n000", "d").rel == "level"
    # passage: p takes the single outside edge first, and p - x is "x below p".
    g = _g({"e": "entrance", "a": AREA}, [("e", "a", "level")])
    apply_rule(g, grow_set.rules["passage"], ("a",))
    assert g.neighbours("n000") == ["a", "e"] and g.neighbours("a") == ["n000"]
    assert g.edge("n000", "a").rel == "below" and g.edge("n000", "e").rel == "level"


def test_kept_nodes_keep_attributes_unless_the_kind_changes(grow_set):
    g = TopologyGraph([Node("p", "chamber", "huge", district=2), Node("m", "lair", "small"),
                       Node("q", "chamber", "tiny"), Node("a", AREA)],
                      [Edge("p", "m"), Edge("m", "q"), Edge("q", "a")])
    apply_rule(g, grow_set.rules["shortcut"], ("p", "q"))
    assert g.node("p") == Node("p", "chamber", "huge", district=2)
    assert g.has_edge("p", "q") and g.has_edge("p", "m") and g.has_edge("q", "a")
    apply_rule(g, grow_set.rules["finish"], ("a",))
    assert g.node("a") == Node("a", "chamber", "medium")


def test_invariants():
    ring = lambda k: _g({f"r{i}": "chamber" for i in range(k)},
                        [(f"r{i}", f"r{(i + 1) % k}") for i in range(k)])
    assert invariant_violation(ring(5)) is None
    assert shortest_cycle_through(ring(5), "r0", "r1") == 5
    assert "loop of 6" in invariant_violation(ring(6))
    star = _g({"h": "hub"} | {f"s{i}": "lair" for i in range(5)}, [("h", f"s{i}") for i in range(5)])
    assert "5 connections" in invariant_violation(star)
    assert invariant_violation(_g({"a": "chamber", "b": "chamber"}, [])) == "not connected"
    assert shortest_cycle_through(_g({"a": "chamber", "b": "chamber"}, [("a", "b")]), "a", "b") is None


# --- the driver --------------------------------------------------------------

def _check_g3(res, n):
    g = res.graph
    assert len(g.rooms()) == n and not g.areas()
    assert invariant_violation(g) is None             # connected, degree <= 4, loops 3-5
    assert max((g.degree(x) for x in g.node_ids()), default=0) <= 4
    for e in g.edges():
        c = shortest_cycle_through(g, e.a, e.b)
        assert c is None or 3 <= c <= 5


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(seed=st.integers(0, 2**32 - 1), n=st.integers(1, 30),
       scale=st.sampled_from([1.0, 2.0]))
def test_g3_g4_grown_graphs(grow_set, seed, n, scale):
    ctx = BuildContext(race_scale=scale)
    res = grow(grow_set, n, random.Random(seed), ctx)
    _check_g3(res, n)
    again = grow(grow_set, n, random.Random(seed), ctx)
    assert again.graph.nodes() == res.graph.nodes() and again.graph.edges() == res.graph.edges()
    assert again.applied == res.applied
    assert all(a.stage in {s.name for s in grow_set.recipe} for a in res.applied)


def test_every_n_with_a_fixed_seed(grow_set):
    for n in range(1, 31):
        _check_g3(grow(grow_set, n, n * 7919), n)


def test_small_n_shrinks_the_start_graph(grow_set):
    assert start_graph_for(grow_set, 1).node_ids() == ["e"]
    g2 = start_graph_for(grow_set, 2)
    assert g2.node_ids() == ["d", "e"] and g2.has_edge("e", "d")
    assert grow(grow_set, 1, 0).graph.nodes() == [Node("e", "entrance", "medium")]
    assert grow(grow_set, 2, 0).applied == []
    assert start_graph_for(grow_set, 3).node_ids() == ["a", "d", "e"]


def test_records_every_application(grow_set):
    res = grow(grow_set, 12, 5, BuildContext(race_scale=2.0))
    stages = [s.name for s in grow_set.recipe]
    assert res.applied and [stages.index(a.stage) for a in res.applied] == sorted(
        stages.index(a.stage) for a in res.applied)
    assert all(a.rule in grow_set.rules for a in res.applied)
    assert res.stats["steps"] == len(res.applied)
    # Replaying the record from the start graph rebuilds the same graph.
    g = start_graph_for(grow_set, 12)
    k = 0
    for a in res.applied:
        rule = grow_set.rules[a.rule]
        placement = a.nodes[:len(rule.match)]
        new = list(a.nodes[len(rule.match):])
        apply_rule(g, rule, placement, lambda: new.pop(0))
    assert g.nodes() == res.graph.nodes() and g.edges() == res.graph.edges()


def test_step_cap_raises_naming_set_stage_and_cap(tmp_path):
    churn = load_rule_set(_write(tmp_path, "churn.toml", CHURN))
    with pytest.raises(TopologyError) as exc:
        grow(churn, 4, 1)
    err = exc.value
    assert (err.set_name, err.stage, err.cap) == ("churn", "Churn", 32)
    assert "churn" in str(err) and "Churn" in str(err) and "32" in str(err)
    with pytest.raises(TopologyError) as exc:
        grow(churn, 4, 1, cap_factor=2)
    assert exc.value.cap == 8


def test_rest_stage_that_cannot_finish_raises(tmp_path):
    # Only finish in the rest stage and nothing earlier that grows: 5 rooms are unreachable.
    text = CHURN.replace('apply = { flip = 1, flop = 1 }', 'apply = { flip = 1 }')
    churn = load_rule_set(_write(tmp_path, "churn.toml", text))
    with pytest.raises(TopologyError) as exc:
        grow(churn, 5, 1)
    assert exc.value.stage == "Finish" and exc.value.cap is None


# --- layers (G5) -------------------------------------------------------------

def test_layer_takes_part_and_base_is_unchanged(tmp_path):
    base_path = _write(tmp_path, "grow.toml", GROW)
    _write(tmp_path, "layers/chapel.toml", CHAPEL_LAYER)
    _write(tmp_path, "themes.toml", THEMES)
    before_bytes = base_path.read_bytes()
    base = load_rule_set(base_path)
    before = copy.deepcopy(base)
    merged = load_for_theme(tmp_path, "temple")
    used = set()
    for seed in range(5):
        res = grow(merged, 15, seed)
        _check_g3(res, 15)
        used |= {(a.stage, a.rule) for a in res.applied}
    assert ("Chapels", "chapel") in used
    assert base == before and base_path.read_bytes() == before_bytes
    assert load_rule_set(base_path) == before
    plain = grow(load_for_theme(tmp_path, "tomb"), 15, 0)
    assert all(a.rule != "chapel" for a in plain.applied)
