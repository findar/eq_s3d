"""
tests/test_topology_levels.py
-----------------------------
Dungeon verticality task 4 (Requirements 4.1, 4.2; design "Levels",
"Stacking"): Levels in the graph engine.

V3  over grown graphs the Levels agree with every ``above`` / ``below`` /
    ``level`` edge; the rewrite driver rejects an application that makes the
    relations disagree round a loop, and the checker a rule (or start graph)
    that disagrees with itself.
V4  (the engine's half) ``may_overlap_in_plan`` is true only for rooms on
    different Levels with at least the Slab between them; placement leaves
    stair pairs overlapping in plan and never overlaps any other pair.

Goldens: sha256 of the Zone_Spec JSON for pinned graph builds, captured on
the step 6 code BEFORE Levels landed. Levels must not move a build that
doesn't stack. A mismatch is a regression, never a reason to recapture
(rule out a numpy/scipy bump first, as ``tests/test_layout_engine.py`` says).

The vertical rule sets here are small test sets written to ``tmp_path``; the
shipped sets' vertical rules are task 6's.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.layout import LayoutGenerator
from generators.layout_engine import GraphEngine
from generators.topology import embed
from generators.topology.graph import Edge, Node, TopologyGraph
from generators.topology.rewrite import BuildContext, apply_rule, grow, invariant_violation
from generators.topology.ruleset import (
    LEVEL_STEP, RuleSetError, load_rule_set, relative_levels,
)


def _spec_hash(spec) -> str:
    return hashlib.sha256(
        json.dumps(spec.to_dict(), sort_keys=True).encode()).hexdigest()


# label -> (ZonePlan fields, seed, Zone_Spec sha256). Graph engine (the default
# layout), the shipped rule sets as the themes and races pick them.
GOLDENS = {
    # Three "below" edges (the shipped passage rule).
    "classic_eq": (dict(zone_type="dungeon", room_count=12, layout="graph"), 2,
                   "cd96fa096171ac02ef38cfb1ddfb0ffddc1a69f10223b7dfc755286786b7bf13"),
    # One "below" edge (the shipped tunnel rule).
    "warren": (dict(zone_type="dungeon", room_count=12, layout="graph",
                    rule_set="warren"), 2,
               "61f3b588a6a5737a3004c49d607f83947a7601ffe314386ef9195ab73106c77d"),
    "temple": (dict(zone_type="dungeon", room_count=10, layout="graph",
                    dungeon_theme="temple", verticality="dramatic"), 3,
               "1e37db5eb23657f20015c0b6b0e08dfb7939f8c9352fa283afbfe2175bf002fe"),
    "ogre": (dict(zone_type="dungeon", room_count=9, layout="graph",
                  dungeon_race="ogre", locks=1), 21,
             "5f1cfecfa159b7f6fec58a55f7e3675b89b9da276b14fbc6ce757d65941790ec"),
}


@pytest.mark.parametrize("label", sorted(GOLDENS))
def test_graph_build_matches_step6_golden(label):
    fields, seed, golden = GOLDENS[label]
    spec = plan_to_spec(ZonePlan(name=f"lv_{label}", **fields).validate(), seed=seed)
    assert _spec_hash(spec) == golden, "graph-engine Zone_Spec changed"


# ---------------------------------------------------------------------------
# A vertical test rule set
# ---------------------------------------------------------------------------

# Goes down (descent), up (tower, a gallery over a hall), a ring whose
# relations agree among themselves, and a "level" shortcut that can close a
# loop across Levels (the driver must reject those placements).
VERT = '''
[set]
name = "vert"
description = "Vertical test set"
placement = "spring"
start_nodes = [ {id = "e", kind = "entrance", size = "medium"},
                {id = "a", kind = "Area"},
                {id = "d", kind = "deep", size = "large"} ]
start_edges = [ {a = "e", b = "a"}, {a = "a", b = "d"} ]

[rules.lengthen]
description = "Longer way"
match = [ {id = "x", kind = "Area"} ]
replace = [ {id = "x", kind = "Area"}, {id = "y", kind = "Area"} ]
edges = [ {a = "x", b = "y"} ]
reattach = { x = ["x", "y"] }

[rules.descent]
description = "The way on goes down a Level"
match = [ {id = "x", kind = "Area"} ]
replace = [ {id = "p", kind = "chamber", size = "medium"}, {id = "x", kind = "Area"} ]
edges = [ {a = "p", b = "x", rel = "below"} ]
reattach = { x = ["p", "x"] }

[rules.tower]
description = "A room up a stair, a dead end"
match = [ {id = "x", kind = "Area"} ]
replace = [ {id = "x", kind = "Area"}, {id = "t", kind = "lair", size = "small"} ]
edges = [ {a = "x", b = "t", rel = "above"} ]
reattach = { x = ["x"] }

[rules.gallery]
description = "A hall with a gallery over it"
match = [ {id = "x", kind = "Area"} ]
replace = [ {id = "x", kind = "Area"}, {id = "h", kind = "hall", size = "large"},
            {id = "g", kind = "chamber", size = "small"} ]
edges = [ {a = "x", b = "h", rel = "level"}, {a = "h", b = "g", rel = "above"} ]
reattach = { x = ["x"] }

[rules.ring]
description = "A ring of four that goes up and comes back down"
match = [ {id = "x", kind = "Area"} ]
replace = [ {id = "x", kind = "Area"}, {id = "a", kind = "chamber", size = "small"},
            {id = "b", kind = "chamber", size = "small"}, {id = "c", kind = "chamber", size = "small"} ]
edges = [ {a = "x", b = "a", rel = "above"}, {a = "a", b = "b", rel = "level"},
          {a = "b", b = "c", rel = "below"}, {a = "c", b = "x", rel = "level"} ]
reattach = { x = ["x"] }

[rules.shortcut]
description = "Join two chambers on one Level"
match = [ {id = "p", kind = "chamber"}, {id = "q", kind = "chamber"} ]
match_hops = { p_q = [3, 3] }
replace = [ {id = "p", kind = "chamber", size = "medium"},
            {id = "q", kind = "chamber", size = "medium"} ]
edges = [ {a = "p", b = "q", rel = "level"} ]
reattach = { p = ["p"], q = ["q"] }

[rules.annex]
description = "A small room off a chamber"
match = [ {id = "c", kind = "chamber"} ]
replace = [ {id = "c", kind = "chamber", size = "medium"}, {id = "l", kind = "lair", size = "small"} ]
edges = [ {a = "c", b = "l"} ]
reattach = { c = ["c"] }

[rules.finish]
description = "Finish"
match = [ {id = "x", kind = "Area"} ]
replace = [ {id = "x", kind = "chamber", size = "medium"} ]
reattach = { x = ["x"] }

[[recipe]]
stage = "Main path"
apply = { lengthen = 2, descent = 2 }
share = 0.3

[[recipe]]
stage = "Side rooms"
apply = { tower = 2, gallery = 1, ring = 1 }
share = 0.4

[[recipe]]
stage = "Loops"
apply = { shortcut = 1 }
share = 0.1

[[recipe]]
stage = "Finish"
apply = { finish = 1, lengthen = 0.5, tower = 0.5, annex = 0.5 }
share = "rest"
'''

START_EDGES = 'start_edges = [ {a = "e", b = "a"}, {a = "a", b = "d"} ]'


def _write(tmp_path, text: str):
    p = tmp_path / "vert.toml"
    p.write_text(text, encoding="utf-8")
    return p


@pytest.fixture
def vert(tmp_path):
    return load_rule_set(_write(tmp_path, VERT))


def _disagree(graph: TopologyGraph, levels) -> list:
    """Edges whose relation the Levels break."""
    return [(e.a, e.b, e.rel) for e in graph.edges()
            if e.rel in LEVEL_STEP and levels[e.b] - levels[e.a] != LEVEL_STEP[e.rel]]


# ---------------------------------------------------------------------------
# V3: Levels agree with every above / below / level edge
# ---------------------------------------------------------------------------

def test_v3_levels_agree_over_grown_graphs(vert):
    spans = set()
    for n in (4, 7, 10, 14, 20, 26):
        for seed in range(12):
            g = grow(vert, n, seed, BuildContext(zone_type="dungeon")).graph
            assert invariant_violation(g) is None
            lv = embed.assign_levels(g)
            assert set(lv) == set(g.node_ids())
            entrance = next(r.id for r in g.rooms() if r.kind == "entrance")
            assert lv[entrance] == 0
            assert _disagree(g, lv) == [], (n, seed)
            spans.add(max(lv.values()) - min(lv.values()))
    assert max(spans) >= 2, "the vertical test set never left one Level"


def test_any_edge_takes_the_first_reached_level():
    # c is reached from e by an "any" edge, but c is tied to b (one Level
    # under a) by "below": the group {a, b, c} is placed from a, the first of
    # it reached, so c sits level with a rather than taking e's Level blindly.
    g = TopologyGraph([Node("e", "entrance", "medium"), Node("a", "chamber", "small"),
                       Node("b", "chamber", "small"), Node("c", "chamber", "small"),
                       Node("z", "lair", "small"), Node("u", "lair", "small")],
                      [Edge("e", "a", "above"), Edge("a", "b", "below"), Edge("e", "c"),
                       Edge("c", "b", "below"), Edge("b", "z"), Edge("u", "e")])
    lv = embed.assign_levels(g)
    assert lv == {"e": 0, "a": 1, "b": 0, "c": 1, "z": 0, "u": 0}
    assert _disagree(g, lv) == []


def test_levels_independent_of_insertion_order():
    nodes = [Node("e", "entrance", "medium"), Node("a", "chamber", "small"),
             Node("b", "chamber", "small"), Node("c", "lair", "small")]
    edges = [Edge("e", "a", "above"), Edge("a", "b", "any"), Edge("b", "c", "below")]
    one = embed.assign_levels(TopologyGraph(nodes, edges))
    two = embed.assign_levels(TopologyGraph(nodes[::-1], edges[::-1]))
    assert one == two == {"e": 0, "a": 1, "b": 1, "c": 0}


def test_assign_levels_refuses_a_disagreeing_graph():
    g = TopologyGraph([Node("e", "entrance", "medium"), Node("a", "chamber", "small"),
                       Node("b", "chamber", "small"), Node("c", "chamber", "small")],
                      [Edge("e", "a", "below"), Edge("a", "b", "below"),
                       Edge("b", "c", "above"), Edge("c", "e", "level")])
    with pytest.raises(ValueError, match="disagree round a loop"):
        embed.assign_levels(g)


# ---------------------------------------------------------------------------
# The driver's new invariant and the checker
# ---------------------------------------------------------------------------

def test_driver_rejects_an_application_that_disagrees(vert):
    # p and q are 3 hops apart and p -> m goes down: a "level" shortcut p-q
    # closes a loop that goes down once and never comes back up.
    nodes = [Node("e", "entrance", "medium"), Node("p", "chamber", "medium"),
             Node("m", "chamber", "medium"), Node("k", "chamber", "medium"),
             Node("q", "chamber", "medium")]
    rule = vert.rules["shortcut"]
    g = TopologyGraph(nodes, [Edge("e", "p"), Edge("p", "m", "below"),
                              Edge("m", "k", "level"), Edge("k", "q", "level")])
    assert invariant_violation(g) is None
    apply_rule(g, rule, ("p", "q"))
    why = invariant_violation(g)
    assert why is not None and "disagree round a loop" in why
    # Through an "any" edge the same shortcut is free: no constraint to break.
    g = TopologyGraph(nodes, [Edge("e", "p"), Edge("p", "m", "below"), Edge("m", "k"),
                              Edge("k", "q")])
    apply_rule(g, rule, ("p", "q"))
    assert invariant_violation(g) is None


def test_driver_grows_round_disagreeing_placements(tmp_path):
    """A set whose only loop rule can disagree: every grown graph still agrees,
    and the driver had to reject placements to get there."""
    text = VERT.replace("apply = { shortcut = 1 }\nshare = 0.1",
                        "apply = { shortcut = 1 }\nshare = 0.25")
    rs = load_rule_set(_write(tmp_path, text))
    rejected = 0
    for seed in range(20):
        res = grow(rs, 18, seed, BuildContext(zone_type="dungeon"))
        assert relative_levels(res.graph.edges())[1] is None
        rejected += res.stats["rejected"]
    assert rejected > 0


def test_relative_levels_names_the_disagreeing_edge():
    _rel, why = relative_levels([Edge("a", "b", "below"), Edge("b", "c", "below"),
                                 Edge("c", "a", "below")])
    assert why is not None and "disagree round a loop" in why
    rel, why = relative_levels([Edge("a", "b", "below"), Edge("b", "c", "above"),
                                Edge("c", "a", "level"), Edge("c", "d", "any")])
    assert why is None and "d" not in rel
    assert rel["b"] == ("a", -1) and rel["c"] == ("a", 0)


def test_checker_rejects_a_replacement_that_disagrees(tmp_path):
    bad = VERT.replace('{a = "c", b = "x", rel = "level"}', '{a = "c", b = "x", rel = "above"}')
    with pytest.raises(RuleSetError) as exc:
        load_rule_set(_write(tmp_path, bad))
    msg = str(exc.value)
    assert "rules.ring › edges" in msg and "disagree round a loop" in msg
    assert "agree round every loop" in msg
    assert len(exc.value.errors) == 1


def test_checker_rejects_start_edges_that_disagree(tmp_path):
    bad = VERT.replace(START_EDGES, 'start_edges = [ {a = "e", b = "a", rel = "below"}, '
                                    '{a = "a", b = "d", rel = "below"}, '
                                    '{a = "e", b = "d", rel = "level"} ]')
    with pytest.raises(RuleSetError) as exc:
        load_rule_set(_write(tmp_path, bad))
    assert "set › start_edges" in str(exc.value)


# ---------------------------------------------------------------------------
# may_overlap_in_plan
# ---------------------------------------------------------------------------

def test_may_overlap_in_plan_cases():
    S = embed.Storey
    lh = embed.level_height([120.0, 90.0])
    assert lh == 120.0 + embed.SLAB
    low, up = S(0, 0.0, 120.0), S(1, lh, 90.0)
    assert embed.may_overlap_in_plan(low, up) and embed.may_overlap_in_plan(up, low)
    assert embed.may_overlap_in_plan(S(-1, -lh, 120.0), S(1, lh, 120.0))
    # Same Level: never, whatever the heights.
    assert not embed.may_overlap_in_plan(S(0, 0.0, 10.0), S(0, 500.0, 10.0))
    # Different Levels but less than the Slab between them: no.
    assert not embed.may_overlap_in_plan(S(0, 0.0, 120.0), S(1, 120.0 + embed.SLAB - 1, 90.0))
    assert embed.may_overlap_in_plan(S(0, 0.0, 120.0), S(1, 120.0 + embed.SLAB, 90.0))
    # Plain graph nodes (step 6's call) never.
    assert not embed.may_overlap_in_plan(Node("a", "chamber", "medium"),
                                         Node("b", "chamber", "medium"))
    st = embed.storeys({"a": 0, "b": -1}, {"a": 100.0, "b": 140.0})
    assert st["b"].floor == -(140.0 + embed.SLAB)
    assert embed.may_overlap_in_plan(st["a"], st["b"])


# ---------------------------------------------------------------------------
# Placement: stair pairs stay over each other, nothing else overlaps
# ---------------------------------------------------------------------------

def _engine_run(rs, n, seed, stacking=True, race=""):
    gen = LayoutGenerator("dungeon", seed=seed, engine=GraphEngine(rs, stacking=stacking))
    gen._apply_room_scale(n)
    ctx = gen._layout_context(n, "", race)
    return gen.engine.generate(ctx, n, None)


def _gap(a, b) -> float:
    return max(abs(a.center_x - b.center_x) - (a.width + b.width) / 2,
               abs(a.center_y - b.center_y) - (a.depth + b.depth) / 2)


@pytest.mark.parametrize("race", ["", "ogre"])
def test_placement_stacks_stair_pairs(vert, race):
    stairs = overlapping = 0
    for n in (8, 12, 18):
        for seed in range(6):
            res = _engine_run(vert, n, seed, race=race)
            rooms, lv = res.rooms, res.levels
            assert lv is not None and res.level_height > max(r.height for r in rooms)
            assert res.record["levels"] == {r.id: v for r, v in zip(rooms, lv)}
            for e in res.edges:
                if e.rel in LEVEL_STEP:
                    assert lv[e.j] - lv[e.i] == LEVEL_STEP[e.rel]
            st = [embed.Storey(v, v * res.level_height, r.height) for r, v in zip(rooms, lv)]
            for i in range(len(rooms)):
                for j in range(i + 1, len(rooms)):
                    if _gap(rooms[i], rooms[j]) < -1e-6:
                        assert embed.may_overlap_in_plan(st[i], st[j]), (n, seed, i, j)
            for e in res.edges:
                if lv[e.i] != lv[e.j]:
                    stairs += 1
                    overlapping += _gap(rooms[e.i], rooms[e.j]) < 0
    assert stairs > 20
    # Stair pairs are pulled over each other (92 % overlap straight out of the
    # springs); separation within a Level then moves some off. Measured on
    # this sweep: 0.81 (no race), 0.93 (ogre).
    assert overlapping >= 0.7 * stairs, (overlapping, stairs)


def test_stacking_off_ignores_levels(vert):
    res = _engine_run(vert, 12, 3, stacking=False)
    assert res.levels is None and res.level_height is None and "levels" not in res.record
    assert all(_gap(a, b) > 0 for k, a in enumerate(res.rooms) for b in res.rooms[k + 1:])


def test_one_level_stacking_is_step6(tmp_path):
    """No vertical relations: stacking on places exactly as stacking off."""
    flat = VERT
    for rel in ("above", "below", "level"):
        flat = flat.replace(f', rel = "{rel}"', "")
    rs = load_rule_set(_write(tmp_path, flat))
    for seed in range(4):
        on, off = _engine_run(rs, 14, seed, True), _engine_run(rs, 14, seed, False)
        assert set(on.levels) == {0}
        assert ([dataclasses.asdict(r) for r in on.rooms]
                == [dataclasses.asdict(r) for r in off.rooms])
        assert on.edges == off.edges
