"""Grown room graphs for the graph layout engine (roadmap step 6).

``graph`` holds the Topology_Graph and its shape measures; ``ruleset`` loads
and checks rule sets, theme layers and the theme map (``rules/topology/``);
``rewrite`` grows a graph by a set's recipe.
"""

from generators.topology.graph import (
    AREA, BASE_KINDS, RELATIONS, ROOM_KINDS, SHAPES, SIZE_CLASSES, TAGS,
    Edge, Node, TopologyGraph,
)
from generators.topology.ruleset import (
    PLACEMENTS, CheckError, Rule, RuleSet, RuleSetError, Stage, ThemeLayer, ThemeMap,
    load_for_theme, load_layer, load_rule_set, load_theme_map, merge,
)
from generators.topology.rewrite import (
    Application, BuildContext, GrowResult, TopologyError, apply_rule, find_matches, grow,
)

__all__ = [
    "AREA", "BASE_KINDS", "RELATIONS", "ROOM_KINDS", "SHAPES", "SIZE_CLASSES", "TAGS",
    "Edge", "Node", "TopologyGraph",
    "PLACEMENTS", "CheckError", "Rule", "RuleSet", "RuleSetError", "Stage", "ThemeLayer",
    "ThemeMap", "load_for_theme", "load_layer", "load_rule_set", "load_theme_map", "merge",
    "Application", "BuildContext", "GrowResult", "TopologyError", "apply_rule", "find_matches", "grow",
]
