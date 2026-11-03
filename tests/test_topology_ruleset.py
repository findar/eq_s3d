"""Rule-set format, loader and checks (graph-layout task 3, Req 3.1-3.3, G2/G5).

Every check gets a minimal bad file in ``tmp_path`` and must name the file, the
rule or stage, and the field. The design's annotated example (with the rules
it leaves out filled in) must load, and merging a layer must leave the base
unchanged.
"""

from __future__ import annotations

import copy

import pytest

from generators.topology import ruleset as rs
from generators.topology.graph import Edge, Node, TopologyGraph
from generators.topology.ruleset import (
    RuleSetError, load_for_theme, load_layer, load_rule_set, load_theme_map, merge,
)

# The design's classic_eq example; passage, side_wing and loop filled in.
CLASSIC_EQ = '''
[set]
name        = "classic_eq"
description = "A classic EQ dungeon: a way through, side rooms, a deep end."
placement   = "spring"                  # a Placement name (registry in embed.py)

start_nodes = [ {id = "e", kind = "entrance", size = "medium"},
                {id = "a", kind = "Area"},
                {id = "d", kind = "deep",     size = "huge"} ]
start_edges = [ {a = "e", b = "a"},
                {a = "a", b = "d"} ]

[rules.lengthen]
description = "The way through gets longer"
match    = [ {id = "x", kind = "Area"} ]
replace  = [ {id = "x", kind = "Area"}, {id = "y", kind = "Area"} ]
edges    = [ {a = "x", b = "y"} ]
reattach = { x = ["x", "y"] }

[rules.passage]
description = "A narrow passage on the way, going down"
match    = [ {id = "x", kind = "Area"} ]
replace  = [ {id = "p", kind = "passage", size = "small"}, {id = "x", kind = "Area"} ]
edges    = [ {a = "p", b = "x", rel = "below"} ]
reattach = { x = ["p", "x"] }

[rules.branch]
description = "A dead-end side room off the way through"
match    = [ {id = "x", kind = "Area"} ]
replace  = [ {id = "x", kind = "Area"}, {id = "l", kind = "lair", size = "small"} ]
edges    = [ {a = "x", b = "l"} ]
reattach = { x = ["x"] }

[rules.side_wing]
description = "A passage to a chamber, a district of its own"
match    = [ {id = "x", kind = "Area"} ]
replace  = [ {id = "x", kind = "Area"},
             {id = "p", kind = "passage", size = "small", district = 1},
             {id = "c", kind = "chamber", size = "medium", district = 1} ]
edges    = [ {a = "x", b = "p", tags = ["threshold"]}, {a = "p", b = "c", rel = "level"} ]
reattach = { x = ["x"] }

[rules.great_hall]
description = "Big races get a great hall on the way"
when     = { race_scale = ">=1.5" }    # offered only in this context
match    = [ {id = "x", kind = "Area"} ]
replace  = [ {id = "x", kind = "Area"}, {id = "g", kind = "hall", size = "huge"} ]
edges    = [ {a = "x", b = "g"} ]
reattach = { x = ["g", "x"] }

[rules.loop]
description = "A ring of three rooms"
match    = [ {id = "x", kind = "Area"} ]
replace  = [ {id = "x", kind = "Area"}, {id = "a", kind = "chamber", size = "small"},
             {id = "b", kind = "chamber", size = "small"} ]
edges    = [ {a = "x", b = "a"}, {a = "a", b = "b"}, {a = "b", b = "x"} ]
reattach = { x = ["x"] }

[rules.shortcut]
description = "Join two finished chambers a few rooms apart"
match       = [ {id = "p", kind = "chamber"}, {id = "q", kind = "chamber"} ]
match_hops  = { p_q = [2, 3] }
replace     = [ {id = "p", kind = "chamber", size = "medium"},
                {id = "q", kind = "chamber", size = "medium"} ]
edges       = [ {a = "p", b = "q"} ]
reattach    = { p = ["p"], q = ["q"] }

[rules.finish]
description = "A placeholder becomes a chamber"
match    = [ {id = "x", kind = "Area"} ]
replace  = [ {id = "x", kind = "chamber", size = "medium"} ]
reattach = { x = ["x"] }

[[recipe]]
stage = "Main path"
apply = { lengthen = 3, passage = 1 }
share = 0.4

[[recipe]]
stage = "Side rooms"
apply = { branch = 3, side_wing = 1, great_hall = 1 }
share = 0.4

[[recipe]]
stage = "Loops"
apply = { loop = 1, shortcut = 1 }
share = 0.1

[[recipe]]
stage = "Finish"
apply = { finish = 1 }
share = "rest"
'''

TEMPLE = '''
[layer]
name        = "temple"
description = "A nave with side chapels, before the deep end"
fits        = ["classic_eq"]

[rules.nave]
description = "A long hall with two chapels off its sides"
match    = [ {id = "x", kind = "Area"} ]
replace  = [ {id = "n", kind = "hall",    size = "large"},
             {id = "c1", kind = "lair",   size = "small"},
             {id = "c2", kind = "lair",   size = "small"},
             {id = "x", kind = "Area"} ]
edges    = [ {a = "n", b = "c1"}, {a = "n", b = "c2"}, {a = "n", b = "x"} ]
reattach = { x = ["n", "x"] }

[stages."Side rooms"]
apply = { nave = 2 }

[[insert]]
after = "Main path"
stage = "Chapels"
apply = { nave = 1 }
share = 0.05
'''

THEMES = '''
default = { base = "classic_eq" }
temple  = { base = "classic_eq", layers = ["temple"] }
'''

# The smallest valid set: each check below breaks one piece of it.
MINI = '''
[set]
name = "mini"
description = "Smallest valid set"
placement = "spring"
start_nodes = [ {id = "e", kind = "entrance", size = "medium"}, {id = "a", kind = "Area"} ]
start_edges = [ {a = "e", b = "a"} ]

[rules.grow]
description = "Add a side room"
match = [ {id = "x", kind = "Area"} ]
replace = [ {id = "x", kind = "Area"}, {id = "l", kind = "lair", size = "small"} ]
edges = [ {a = "x", b = "l"} ]
reattach = { x = ["x"] }

[rules.finish]
description = "Finish"
match = [ {id = "x", kind = "Area"} ]
replace = [ {id = "x", kind = "chamber", size = "medium"} ]
reattach = { x = ["x"] }

[[recipe]]
stage = "Grow"
apply = { grow = 1 }
share = 0.5

[[recipe]]
stage = "Finish"
apply = { finish = 1 }
share = "rest"
'''

MINI_LAYER = '''
[layer]
name = "chapel"
description = "One more room"
fits = ["mini"]

[rules.chapel]
description = "A chapel"
match = [ {id = "x", kind = "Area"} ]
replace = [ {id = "x", kind = "Area"}, {id = "c", kind = "hall", size = "large"} ]
edges = [ {a = "x", b = "c"} ]
reattach = { x = ["x"] }

[stages."Grow"]
apply = { chapel = 1 }
'''


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _mutate(text, *subs):
    for old, new in subs:
        assert old in text, old
        text = text.replace(old, new, 1)
    return text


def _errors(load, path):
    with pytest.raises(RuleSetError) as exc:
        load(path)
    return exc.value


def _assert_names(err, file, where, field, expected_has=""):
    """G2: one failure names the file, the rule or stage, and the field."""
    hits = [e for e in err.errors if e.where == where and e.field == field]
    assert hits, f"no failure at {where} › {field} in:\n{err}"
    assert f"{file} › {where} › {field}: found " in str(err)
    assert all(e.file == file for e in hits)
    if expected_has:
        assert any(expected_has in e.expected for e in hits), str(err)


# --- every check, one minimal bad file each ---------------------------------

SET_CASES = {
    "unknown top-level key": (
        [("[[recipe]]\nstage = \"Grow\"", "[extra]\nx = 1\n\n[[recipe]]\nstage = \"Grow\"")],
        "top level", "extra", "set, rules, recipe"),
    "unknown field in a rule": (
        [("reattach = { x = [\"x\"] }\n\n[rules.finish]",
          "reattach = { x = [\"x\"] }\nrepalce = 1\n\n[rules.finish]")],
        "rules.grow", "repalce", "replace"),
    "wrong type": (
        [('description = "Add a side room"', "description = 5")],
        "rules.grow", "description", "a non-empty string"),
    "unknown kind": (
        [('{id = "l", kind = "lair", size = "small"}', '{id = "l", kind = "crypt", size = "small"}')],
        "rules.grow", "replace[1].kind", "chamber"),
    "room without size": (
        [('{id = "l", kind = "lair", size = "small"}', '{id = "l", kind = "lair"}')],
        "rules.grow", "replace[1].size", "medium"),
    "size on Area": (
        [('replace = [ {id = "x", kind = "Area"},', 'replace = [ {id = "x", kind = "Area", size = "small"},')],
        "rules.grow", "replace[0].size", "no size"),
    "unknown size class": (
        [('{id = "l", kind = "lair", size = "small"}', '{id = "l", kind = "lair", size = "big"}')],
        "rules.grow", "replace[1].size", "tiny, small, medium, large, huge"),
    "unknown shape": (
        [('{id = "l", kind = "lair", size = "small"}', '{id = "l", kind = "lair", size = "small", shape = "blob"}')],
        "rules.grow", "replace[1].shape", "rect"),
    "bad district": (
        [('{id = "l", kind = "lair", size = "small"}', '{id = "l", kind = "lair", size = "small", district = -1}')],
        "rules.grow", "replace[1].district", "0 or more"),
    "size on a match node": (
        [('match = [ {id = "x", kind = "Area"} ]\nreplace = [ {id = "x", kind = "Area"}, {id = "l"',
          'match = [ {id = "x", kind = "Area", size = "small"} ]\nreplace = [ {id = "x", kind = "Area"}, {id = "l"')],
        "rules.grow", "match[0].size", "id, kind"),
    "too many match nodes": (
        [('match = [ {id = "x", kind = "Area"} ]\nreplace = [ {id = "x", kind = "Area"}, {id = "l"',
          'match = [ {id = "x", kind = "Area"}, {id = "y", kind = "Area"}, {id = "z", kind = "Area"}, '
          '{id = "w", kind = "Area"} ]\nreplace = [ {id = "x", kind = "Area"}, {id = "l"')],
        "rules.grow", "match", "1 to 3"),
    "duplicate node id": (
        [('{id = "l", kind = "lair", size = "small"}', '{id = "x", kind = "lair", size = "small"}'),
         ('edges = [ {a = "x", b = "l"} ]', 'edges = []')],
        "rules.grow", "replace[1].id", "unique"),
    "edge naming an unknown node": (
        [('edges = [ {a = "x", b = "l"} ]', 'edges = [ {a = "x", b = "q"} ]')],
        "rules.grow", "edges[0].b", "l, x"),
    "self-loop": (
        [('edges = [ {a = "x", b = "l"} ]', 'edges = [ {a = "x", b = "x"} ]')],
        "rules.grow", "edges[0].b", "no self-loops"),
    "unknown relation": (
        [('edges = [ {a = "x", b = "l"} ]', 'edges = [ {a = "x", b = "l", rel = "up"} ]')],
        "rules.grow", "edges[0].rel", "above, below, level, any"),
    "unknown tag": (
        [('edges = [ {a = "x", b = "l"} ]', 'edges = [ {a = "x", b = "l", tags = ["door"]} ]')],
        "rules.grow", "edges[0].tags[0]", "threshold"),
    "start edge naming an unknown node": (
        [('start_edges = [ {a = "e", b = "a"} ]', 'start_edges = [ {a = "e", b = "z"} ]')],
        "set", "start_edges[0].b", "a, e"),
    "no entrance in the start graph": (
        [('{id = "e", kind = "entrance", size = "medium"}', '{id = "e", kind = "chamber", size = "medium"}')],
        "set", "start_nodes", 'kind = "entrance"'),
    "unknown when key": (
        [('description = "Add a side room"', 'description = "Add a side room"\nwhen = { mood = "grim" }')],
        "rules.grow", "when.mood", "theme, race, race_scale, zone_type, room_count"),
    "bad when comparison": (
        [('description = "Add a side room"', 'description = "Add a side room"\nwhen = { race_scale = "big" }')],
        "rules.grow", "when.race_scale", '">=1.5"'),
    "bad when value": (
        [('description = "Add a side room"', 'description = "Add a side room"\nwhen = { theme = "castle" }')],
        "rules.grow", "when.theme", "temple"),
    "comparison on a text key": (
        [('description = "Add a side room"', 'description = "Add a side room"\nwhen = { race = ">=2" }')],
        "rules.grow", "when.race", "ogre"),
    "bad match_hops key": (
        [('match = [ {id = "x", kind = "Area"} ]\nreplace = [ {id = "x", kind = "Area"}, {id = "l"',
          'match = [ {id = "x", kind = "Area"} ]\nmatch_hops = { x_y = [2, 3] }\n'
          'replace = [ {id = "x", kind = "Area"}, {id = "l"')],
        "rules.grow", "match_hops.x_y", "<a>_<b>"),
    "reattach missing a match node": (
        [('edges = [ {a = "x", b = "l"} ]\nreattach = { x = ["x"] }',
          'edges = [ {a = "x", b = "l"} ]\nreattach = {}')],
        "rules.grow", "reattach.x", "replacement node ids"),
    "reattach key not a match node": (
        [('edges = [ {a = "x", b = "l"} ]\nreattach = { x = ["x"] }',
          'edges = [ {a = "x", b = "l"} ]\nreattach = { x = ["x"], l = ["x"] }')],
        "rules.grow", "reattach.l", "match node id"),
    "reattach to a missing node": (
        [('edges = [ {a = "x", b = "l"} ]\nreattach = { x = ["x"] }',
          'edges = [ {a = "x", b = "l"} ]\nreattach = { x = ["z"] }')],
        "rules.grow", "reattach.x", "l, x"),
    "reattach to nothing": (
        [('edges = [ {a = "x", b = "l"} ]\nreattach = { x = ["x"] }',
          'edges = [ {a = "x", b = "l"} ]\nreattach = { x = [] }')],
        "rules.grow", "reattach.x", "non-empty"),
    "stage naming an unknown rule": (
        [("apply = { grow = 1 }", "apply = { grow = 1, sprawl = 2 }")],
        'recipe "Grow"', "apply.sprawl", "finish, grow"),
    "share out of range": (
        [("share = 0.5", "share = 1.5")],
        'recipe "Grow"', "share", "(0, 1]"),
    "shares sum above 1": (
        [("share = 0.5", "share = 0.7"),
         ('[[recipe]]\nstage = "Finish"', '[[recipe]]\nstage = "More"\napply = { grow = 1 }\nshare = 0.6\n\n'
          '[[recipe]]\nstage = "Finish"')],
        "recipe", "share", "at most 1"),
    "last stage not rest": (
        [('share = "rest"', "share = 0.2")],
        'recipe "Finish"', "share", '"rest"'),
    "last stage cannot finish an Area": (
        [("apply = { finish = 1 }", "apply = { grow = 1 }")],
        'recipe "Finish"', "apply", "finish"),
    "unknown placement": (
        [('placement = "spring"', 'placement = "maze"')],
        "set", "placement", "spring"),
    "set name not the file name": (
        [('name = "mini"', 'name = "other"')],
        "set", "name", '"mini"'),
}


@pytest.mark.parametrize("case", sorted(SET_CASES))
def test_each_check_names_file_where_and_field(tmp_path, case):
    subs, where, field, expected_has = SET_CASES[case]
    path = _write(tmp_path, "mini.toml", _mutate(MINI, *subs))
    _assert_names(_errors(load_rule_set, path), "mini.toml", where, field, expected_has)


def test_invalid_toml_is_reported(tmp_path):
    # An inline table split over lines is not TOML 1.0.
    path = _write(tmp_path, "mini.toml", MINI.replace('reattach = { x = ["x"] }',
                                                      'reattach = {\n x = ["x"] }', 1))
    _assert_names(_errors(load_rule_set, path), "mini.toml", "file", "toml", "TOML 1.0")


def test_declared_kinds_are_accepted(tmp_path):
    text = _mutate(MINI, ('placement = "spring"', 'placement = "spring"\nkinds = ["crypt"]'),
                   ('{id = "l", kind = "lair", size = "small"}', '{id = "l", kind = "crypt", size = "small"}'))
    s = load_rule_set(_write(tmp_path, "mini.toml", text))
    assert s.kinds == ("crypt",) and "crypt" in s.all_kinds


def test_placement_registry_is_read_at_check_time(tmp_path, monkeypatch):
    path = _write(tmp_path, "mini.toml", MINI.replace('"spring"', '"maze"', 1))
    monkeypatch.setattr(rs, "PLACEMENTS", rs.PLACEMENTS + ("maze",))
    assert load_rule_set(path).placement == "maze"


def test_several_problems_are_all_reported(tmp_path):
    text = _mutate(MINI,
                   ('placement = "spring"', 'placement = "maze"'),
                   ('{id = "l", kind = "lair", size = "small"}', '{id = "l", kind = "crypt", size = "big"}'),
                   ('edges = [ {a = "x", b = "l"} ]', 'edges = [ {a = "x", b = "l", rel = "up"} ]'),
                   ("share = 0.5", "share = 0"))
    err = _errors(load_rule_set, _write(tmp_path, "mini.toml", text))
    fields = {(e.where, e.field) for e in err.errors}
    assert {("set", "placement"), ("rules.grow", "replace[1].kind"),
            ("rules.grow", "replace[1].size"), ("rules.grow", "edges[0].rel"),
            ('recipe "Grow"', "share")} <= fields
    assert len(str(err).splitlines()) == len(err.errors) >= 5


# --- layers and the theme map ------------------------------------------------

LAYER_CASES = {
    "fits not including the base": (
        [('fits = ["mini"]', 'fits = ["warren"]')], "layer", "fits", '"mini"'),
    "stage addition to an unknown stage": (
        [('[stages."Grow"]', '[stages."Sprawl"]')], 'stages."Sprawl"', "stage", "Grow, Finish"),
    "insert after an unknown stage": (
        [("", '\n[[insert]]\nafter = "Nowhere"\nstage = "Extra"\napply = { chapel = 1 }\nshare = 0.1\n')],
        'insert "Extra"', "after", "Grow, Finish"),
    "rule name already in the base": (
        [("[rules.chapel]", "[rules.grow]"), ("apply = { chapel = 1 }", "apply = { grow = 1 }")],
        "rules.grow", "name", "mini.toml"),
}


@pytest.mark.parametrize("case", sorted(LAYER_CASES))
def test_layer_checks_on_merge(tmp_path, case):
    subs, where, field, expected_has = LAYER_CASES[case]
    text = MINI_LAYER + subs[0][1] if subs[0][0] == "" else _mutate(MINI_LAYER, *subs)
    base = load_rule_set(_write(tmp_path, "mini.toml", MINI))
    layer = load_layer(_write(tmp_path, "layers/chapel.toml", text))
    with pytest.raises(RuleSetError) as exc:
        merge(base, [layer])
    _assert_names(exc.value, "chapel.toml", where, field, expected_has)


def test_layer_file_checks(tmp_path):
    text = _mutate(MINI_LAYER, ('fits = ["mini"]', "fits = []"),
                   ('kind = "hall", size = "large"', 'kind = "hall"'),
                   ("apply = { chapel = 1 }", "apply = { chapel = 0 }"))
    err = _errors(load_layer, _write(tmp_path, "chapel.toml", text))
    _assert_names(err, "chapel.toml", "layer", "fits", "base set")
    _assert_names(err, "chapel.toml", "rules.chapel", "replace[1].size", "small")
    _assert_names(err, "chapel.toml", 'stages."Grow"', "apply.chapel", "above 0")


def test_merged_recipe_is_rechecked(tmp_path):
    base = load_rule_set(_write(tmp_path, "mini.toml", MINI))
    text = MINI_LAYER + '\n[[insert]]\nafter = "Grow"\nstage = "Big"\napply = { chapel = 1 }\nshare = 0.6\n'
    layer = load_layer(_write(tmp_path, "chapel.toml", text))
    with pytest.raises(RuleSetError) as exc:
        merge(base, [layer])
    _assert_names(exc.value, "mini.toml + chapel.toml", "recipe", "share", "at most 1")


def test_theme_map_checks(tmp_path):
    err = _errors(load_theme_map, _write(tmp_path, "themes.toml",
                                         'castle = { base = "classic_eq" }\n'
                                         'temple = { base = "classic_eq", layer = ["temple"] }\n'))
    _assert_names(err, "themes.toml", "top level", "castle", "fortress")
    _assert_names(err, "themes.toml", "temple", "layer", "base, layers")
    _assert_names(err, "themes.toml", "top level", "default", "default")


# --- the design's example ----------------------------------------------------

@pytest.fixture
def rules_dir(tmp_path):
    _write(tmp_path, "classic_eq.toml", CLASSIC_EQ)
    _write(tmp_path, "layers/temple.toml", TEMPLE)
    _write(tmp_path, "themes.toml", THEMES)
    return tmp_path


def test_design_example_loads(rules_dir):
    s = load_rule_set(rules_dir / "classic_eq.toml")
    assert s.name == "classic_eq" and s.placement == "spring"
    assert [st.name for st in s.recipe] == ["Main path", "Side rooms", "Loops", "Finish"]
    assert s.rules["lengthen"].reattach_map() == {"x": ("x", "y")}
    assert s.rules["shortcut"].match_hops[0] == rs.Hops("p", "q", 2, 3)
    assert s.rules["great_hall"].when == (rs.Condition("race_scale", ">=", 1.5),)
    assert s.rules["great_hall"].when_holds({"race_scale": 2.0})
    assert not s.rules["great_hall"].when_holds({"race_scale": 1.0})
    assert {n: r.rooms_added for n, r in s.rules.items()} == {
        "lengthen": 0, "passage": 1, "branch": 1, "side_wing": 2, "great_hall": 1,
        "loop": 2, "shortcut": 0, "finish": 1}
    g = s.start_graph()
    assert g.node_ids() == ["a", "d", "e"] and g.connected()


def test_merge_leaves_base_unchanged(rules_dir):
    base = load_rule_set(rules_dir / "classic_eq.toml")
    before = copy.deepcopy(base)
    merged = merge(base, [load_layer(rules_dir / "layers" / "temple.toml")])
    assert base == before
    assert "nave" in merged.rules and "nave" not in base.rules
    assert [st.name for st in merged.recipe] == ["Main path", "Chapels", "Side rooms", "Loops", "Finish"]
    assert merged.recipe[2].apply["nave"] == 2 and "nave" not in base.recipe[1].apply
    assert merged.layers == ("temple",)


def test_load_for_theme(rules_dir):
    assert "nave" in load_for_theme(rules_dir, "temple").rules
    assert "nave" not in load_for_theme(rules_dir, "tomb").rules       # falls back to default
    with pytest.raises(RuleSetError) as exc:
        load_for_theme(rules_dir, "temple", rule_set="warren")
    _assert_names(exc.value, "themes.toml", "request", "base", "classic_eq")


# --- TopologyGraph -----------------------------------------------------------

def _graph(kinds_sizes, edges):
    nodes = [Node(i, k, s) for i, (k, s) in kinds_sizes.items()]
    return TopologyGraph(nodes, [Edge(a, b) for a, b in edges])


def test_measures_on_a_path_with_a_branch():
    # e - c1 - c2 - d, plus l off c1: dead ends e, d and l.
    g = _graph({"e": ("entrance", "medium"), "c1": ("chamber", "medium"),
                "c2": ("chamber", "large"), "d": ("deep", "huge"), "l": ("lair", "small")},
               [("e", "c1"), ("c1", "c2"), ("c2", "d"), ("c1", "l")])
    assert g.dead_end_share() == pytest.approx(3 / 5)      # e, d, l
    assert g.cycle_rank() == 0
    assert g.deep_end_distance() == pytest.approx(3 / 5)   # e -> d is 3 hops
    assert g.size_mix() == {"tiny": 0.0, "small": 0.2, "medium": 0.4, "large": 0.2, "huge": 0.2}


def test_measures_on_a_loop_ignore_areas():
    g = _graph({"e": ("entrance", "small"), "a": ("chamber", "small"), "b": ("chamber", "small"),
                "c": ("chamber", "small"), "x": ("Area", None)},
               [("e", "a"), ("a", "b"), ("b", "c"), ("c", "a"), ("c", "x")])
    assert g.cycle_rank() == 1
    assert g.dead_end_share() == pytest.approx(1 / 4)      # e only; x is not a room
    assert g.deep_end_distance() == pytest.approx(2 / 4)


def test_edges_keep_direction_and_graph_edits():
    g = _graph({"a": ("Area", None), "b": ("chamber", "small")}, [])
    g.add_edge("b", "a", rel="above")                       # a is above b
    assert g.edge("b", "a").rel == "above" and g.edge("a", "b").rel == "below"
    assert g.edges()[0] == Edge("a", "b", "below")
    h = g.copy()
    removed = h.remove_node("a")
    assert removed == [Edge("a", "b", "below")] and g.degree("b") == 1 and h.degree("b") == 0
    g.replace_node(Node("a", "hall", "huge"))
    assert g.has_edge("a", "b") and g.node("a").kind == "hall"
    with pytest.raises(ValueError):
        g.add_edge("a", "b")
