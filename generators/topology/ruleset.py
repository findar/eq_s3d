"""
generators/topology/ruleset.py
------------------------------
Rule sets, theme layers and the theme map as checked TOML data (roadmap step 6,
Requirement 3; design "Rule-set files", "The vocabulary (checked on load)",
"Theme layers and the theme map").

Loading reads a file with ``tomllib`` and then runs every check, collecting
EVERY failure rather than stopping at the first. Each failure is a
:class:`CheckError` that prints as one line::

    classic_eq.toml › rules.branch › replace[1].size: found "big", expected one of tiny, small, medium, large, huge

and a file with any failure raises one :class:`RuleSetError` carrying all of
them (Req 3.3: a failing file is never used). The messages are written for a
language model fixing its own output as much as for a person, so ``expected``
always lists the allowed values.

Format decisions the design leaves open (task 3):

- Match nodes take ``id`` and ``kind`` only (matching is by kind); room nodes
  in ``start_nodes`` and ``replace`` take ``size`` (required), ``shape`` and
  ``district``. Match edges are ``match_edges``.
- ``match_hops`` keys are ``"<a>_<b>"`` naming two match nodes; the value is
  ``[lo, hi]`` with ``2 <= lo <= hi`` (the nodes are not adjacent).
- A start graph has exactly one ``entrance`` node (the shape measures and the
  placement start from it).
- ``[set] name`` must equal the file's stem, and a layer's ``[layer] name``
  its file's stem, because the theme map finds files by name.
- A layer may use the base vocabulary plus the kinds it declares in
  ``[layer] kinds``; to use a base set's extra kind it declares it too.
- A layer inserts a stage with ``[[insert]] after = "<stage>"`` plus the
  stage's ``stage``, ``apply`` and ``share``; several inserts after the same
  stage keep their file order.
- A layer's rule may not reuse a name already in the base or an earlier layer.
- (Step 7, task 4.) A rule's replacement edges, and a set's start edges, must
  agree on Levels: following ``above`` (+1), ``below`` (-1) and ``level`` (0)
  round any loop of them must come back to where it started
  (:func:`relative_levels`). ``any`` edges constrain nothing.
"""

from __future__ import annotations

import math
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from ai.schema import VALID_DUNGEON_RACES, VALID_DUNGEON_THEMES
from generators.topology.graph import (
    AREA, BASE_KINDS, ENTRANCE, RELATIONS, SHAPES, SIZE_CLASSES, TAGS,
    Edge, Node, TopologyGraph,
)
from generators.zone_types import DEFINED_ZONE_TYPES

#: Placement names a set may name. Read at check time, so the placement
#: module can extend it (``ruleset.PLACEMENTS += ("maze",)``).
PLACEMENTS: Tuple[str, ...] = ("spring",)

WHEN_KEYS: Tuple[str, ...] = ("theme", "race", "race_scale", "zone_type", "room_count")
COMPARISONS: Tuple[str, ...] = (">=", "<=", "==", "!=", ">", "<")
REST = "rest"
MAX_MATCH_NODES = 3
#: The theme map's fallback entry, used for themes it doesn't list.
DEFAULT_THEME = "default"

_WHEN_TEXT: Dict[str, Tuple[str, ...]] = {
    "theme": tuple(VALID_DUNGEON_THEMES),
    "race": tuple(VALID_DUNGEON_RACES),
    "zone_type": tuple(DEFINED_ZONE_TYPES),
}
_COMPARISON_RE = re.compile(r"\s*(>=|<=|==|!=|>|<)\s*(-?\d+(?:\.\d+)?)\s*")
_SHARE_TOLERANCE = 1e-9

_MISSING = object()


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CheckError:
    """One failed check: where it is, what was found, what was expected."""

    file: str
    where: str
    field: str
    found: str
    expected: str

    def __str__(self) -> str:
        return (f"{self.file} › {self.where} › {self.field}: "
                f"found {self.found}, expected {self.expected}")


class RuleSetError(ValueError):
    """Every check failure of a load or merge; ``str()`` is one line each."""

    def __init__(self, errors: Sequence[CheckError]):
        self.errors: Tuple[CheckError, ...] = tuple(errors)
        super().__init__("\n".join(str(e) for e in self.errors))


# ---------------------------------------------------------------------------
# Loaded data
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Condition:
    """One ``when`` entry: ``op`` is ``==``, ``in`` or a comparison."""

    key: str
    op: str
    value: Any

    def holds(self, actual: Any) -> bool:
        if actual is None:
            return False
        if self.op == "in":
            return actual in self.value
        if self.op == "==":
            return actual == self.value
        if self.op == "!=":
            return actual != self.value
        if self.op == ">=":
            return actual >= self.value
        if self.op == "<=":
            return actual <= self.value
        if self.op == ">":
            return actual > self.value
        return actual < self.value          # "<"


@dataclass(frozen=True)
class Hops:
    """``match_hops``: match nodes ``a`` and ``b`` are lo..hi hops apart."""

    a: str
    b: str
    lo: int
    hi: int


@dataclass(frozen=True)
class Rule:
    name: str
    description: str
    match: Tuple[Node, ...]
    match_edges: Tuple[Edge, ...]
    match_hops: Tuple[Hops, ...]
    replace: Tuple[Node, ...]
    edges: Tuple[Edge, ...]
    reattach: Tuple[Tuple[str, Tuple[str, ...]], ...]   # (match id, targets), match order
    when: Tuple[Condition, ...]
    source: str                                         # the file the rule came from

    @property
    def rooms_added(self) -> int:
        """Net room nodes the rule adds (replacement rooms minus matched rooms)."""
        return (sum(1 for n in self.replace if n.is_room)
                - sum(1 for n in self.match if n.is_room))

    @property
    def finishes_area(self) -> bool:
        """Matches an ``Area`` and leaves none: it can finish a placeholder."""
        return (any(not n.is_room for n in self.match)
                and all(n.is_room for n in self.replace))

    def reattach_map(self) -> Dict[str, Tuple[str, ...]]:
        return dict(self.reattach)

    def when_holds(self, context: Mapping[str, Any]) -> bool:
        """True when every ``when`` condition holds for the build context."""
        return all(c.holds(context.get(c.key)) for c in self.when)


@dataclass(frozen=True)
class Stage:
    name: str
    apply: Mapping[str, float]          # rule name -> weight
    share: Union[float, str, None]      # a number in (0, 1], "rest", or None if unreadable

    @property
    def is_rest(self) -> bool:
        return self.share == REST


@dataclass(frozen=True)
class Insert:
    after: str
    stage: Stage


@dataclass(frozen=True)
class RuleSet:
    name: str
    description: str
    placement: str
    kinds: Tuple[str, ...]              # extra kinds beyond BASE_KINDS
    start_nodes: Tuple[Node, ...]
    start_edges: Tuple[Edge, ...]
    rules: Mapping[str, Rule]
    recipe: Tuple[Stage, ...]
    source: str
    layers: Tuple[str, ...] = ()

    @property
    def all_kinds(self) -> Tuple[str, ...]:
        return BASE_KINDS + self.kinds

    def start_graph(self) -> TopologyGraph:
        """A fresh graph of the start nodes and edges."""
        return TopologyGraph(self.start_nodes, self.start_edges)


@dataclass(frozen=True)
class ThemeLayer:
    name: str
    description: str
    fits: Tuple[str, ...]
    kinds: Tuple[str, ...]
    rules: Mapping[str, Rule]
    stage_weights: Mapping[str, Mapping[str, float]]   # base stage -> added weights
    inserts: Tuple[Insert, ...]
    source: str


@dataclass(frozen=True)
class ThemeEntry:
    base: str
    layers: Tuple[str, ...] = ()
    walls: str = "built"            # the theme's wall style (rules/walls/, step 8)


@dataclass(frozen=True)
class ThemeMap:
    entries: Mapping[str, ThemeEntry]
    source: str

    def entry_for(self, theme: Optional[str]) -> ThemeEntry:
        return self.entries.get(theme or DEFAULT_THEME, self.entries[DEFAULT_THEME])


# ---------------------------------------------------------------------------
# Levels from the vertical relations (step 7, design "Levels")
# ---------------------------------------------------------------------------

#: Level change from an edge's first node to its second, per relation
#: (``any`` is absent: it constrains nothing).
LEVEL_STEP: Dict[str, int] = {"above": 1, "below": -1, "level": 0}


def relative_levels(edges: Sequence[Edge]
                    ) -> Tuple[Dict[str, Tuple[str, int]], Optional[str]]:
    """Group the nodes joined by ``above`` / ``below`` / ``level`` edges.

    Returns ``({node: (group, offset)}, conflict)``: each node of a group
    (the nodes those edges join, ``group`` its least id) has the Level
    ``offset`` relative to that node. ``conflict`` is None when every such
    edge agrees, else one line naming the edge that disagrees with the
    others round a loop (e.g. a loop that goes down twice and up once).
    Nodes on ``any`` edges alone are not listed. Sorted throughout, so the
    result and the message don't depend on edge order.
    """
    adj: Dict[str, List[Tuple[str, int, str]]] = {}
    for e in edges:
        step = LEVEL_STEP.get(e.rel)
        if step is None:
            continue
        adj.setdefault(e.a, []).append((e.b, step, e.rel))
        adj.setdefault(e.b, []).append((e.a, -step, {"above": "below", "below": "above"}
                                        .get(e.rel, e.rel)))
    out: Dict[str, Tuple[str, int]] = {}
    for root in sorted(adj):
        if root in out:
            continue
        out[root] = (root, 0)
        stack = [root]
        while stack:
            u = stack.pop(0)
            lu = out[u][1]
            for v, step, rel in sorted(adj[u]):
                want = lu + step
                if v not in out:
                    out[v] = (root, want)
                    stack.append(v)
                elif out[v][1] != want:
                    return out, (f"the vertical relations disagree round a loop: "
                                 f"{v!r} is {rel} {u!r} (Level {want} from {root!r}), "
                                 f"but the other relations put it at Level {out[v][1]}")
    return out, None


# ---------------------------------------------------------------------------
# The checker
# ---------------------------------------------------------------------------

def _show(v: Any) -> str:
    """A TOML-ish rendering of a found value, kept short."""
    if v is _MISSING:
        return "nothing"
    if isinstance(v, bool):
        s = "true" if v else "false"
    elif isinstance(v, str):
        s = '"' + v.replace('"', '\\"') + '"'
    elif isinstance(v, list):
        s = "[" + ", ".join(_show(x) for x in v) + "]"
    elif isinstance(v, dict):
        s = "{" + ", ".join(f"{k} = {_show(x)}" for k, x in v.items()) + "}"
    else:
        s = str(v)
    return s if len(s) <= 80 else s[:77] + "..."


def _one_of(values: Sequence[str]) -> str:
    return "one of " + ", ".join(values)


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _type_name(v: Any) -> str:
    return {bool: "a boolean", int: "an integer", float: "a number", str: "a string",
            list: "an array", dict: "a table"}.get(type(v), type(v).__name__)


class _Checker:
    def __init__(self, file: str):
        self.file = file
        self.errors: List[CheckError] = []

    def fail(self, where: str, fld: str, found: Any, expected: str, raw: bool = False) -> None:
        self.errors.append(CheckError(self.file, where, fld,
                                      found if raw else _show(found), expected))

    def raise_if_failed(self) -> None:
        if self.errors:
            raise RuleSetError(self.errors)

    # -- generic fields --------------------------------------------------------

    def keys(self, tbl: Mapping[str, Any], where: str, allowed: Sequence[str],
             required: Sequence[str] = (), prefix: str = "") -> None:
        for k in tbl:
            if k not in allowed:
                self.fail(where, prefix + k, "an unknown field", _one_of(allowed), raw=True)
        for k in required:
            if k not in tbl:
                self.fail(where, prefix + k, _MISSING, f"the field (required; fields: {', '.join(allowed)})")

    def text(self, tbl: Mapping[str, Any], key: str, where: str, required: bool = True,
             prefix: str = "", default: str = "") -> str:
        v = tbl.get(key, _MISSING)
        if v is _MISSING:
            if required:
                self.fail(where, prefix + key, v, "a string")
            return default
        if not isinstance(v, str) or not v.strip():
            self.fail(where, prefix + key, v if isinstance(v, str) else _type_name(v),
                      "a non-empty string", raw=not isinstance(v, str))
            return default
        return v

    def table(self, v: Any, where: str, fld: str, example: str) -> Optional[Dict[str, Any]]:
        if isinstance(v, dict):
            return v
        self.fail(where, fld, _type_name(v) if v is not _MISSING else "nothing",
                  f"a table like {example}", raw=True)
        return None

    def array(self, v: Any, where: str, fld: str, example: str) -> Optional[List[Any]]:
        if isinstance(v, list):
            return v
        self.fail(where, fld, _type_name(v) if v is not _MISSING else "nothing",
                  f"an array like {example}", raw=True)
        return None

    def names(self, v: Any, where: str, fld: str, what: str) -> Tuple[str, ...]:
        """An array of non-empty strings."""
        arr = self.array(v, where, fld, f'["{what}"]')
        if arr is None:
            return ()
        out = []
        for i, x in enumerate(arr):
            if isinstance(x, str) and x.strip():
                out.append(x)
            else:
                self.fail(where, f"{fld}[{i}]", x, f"a {what} name (a non-empty string)")
        return tuple(out)

    # -- nodes and edges -------------------------------------------------------

    def node(self, raw: Any, where: str, fld: str, kinds: Sequence[str], role: str) -> Optional[Node]:
        """``role`` is ``start``, ``match`` or ``replace``."""
        tbl = self.table(raw, where, fld, '{id = "x", kind = "Area"}')
        if tbl is None:
            return None
        p = fld + "."
        allowed = ("id", "kind") if role == "match" else ("id", "kind", "size", "shape", "district")
        self.keys(tbl, where, allowed, prefix=p)
        nid = self.text(tbl, "id", where, prefix=p)
        kind = tbl.get("kind", _MISSING)
        if kind not in kinds:
            self.fail(where, p + "kind", kind, _one_of(kinds))
            kind = kind if isinstance(kind, str) else AREA
        if role == "match":
            return Node(nid, kind)
        size = tbl.get("size", _MISSING)
        if kind == AREA:
            if size is not _MISSING:
                self.fail(where, p + "size", size, "nothing (an Area takes no size; rooms do)")
            size = None
        elif size is _MISSING:
            self.fail(where, p + "size", size,
                      f"a size class on the {kind} room node: {_one_of(SIZE_CLASSES)}")
            size = None
        elif size not in SIZE_CLASSES:
            self.fail(where, p + "size", size, _one_of(SIZE_CLASSES))
            size = None
        shape = tbl.get("shape", "auto")
        if shape not in SHAPES:
            self.fail(where, p + "shape", shape, _one_of(SHAPES))
            shape = "auto"
        district = tbl.get("district", 0)
        if not isinstance(district, int) or isinstance(district, bool) or district < 0:
            self.fail(where, p + "district", district, "a whole number 0 or more (a district label)")
            district = 0
        return Node(nid, kind, size, shape, district)

    def nodes(self, raw: Any, where: str, fld: str, kinds: Sequence[str], role: str,
              lo: int = 1, hi: Optional[int] = None) -> List[Node]:
        arr = self.array(raw, where, fld, '[ {id = "x", kind = "Area"} ]')
        if arr is None:
            return []
        if len(arr) < lo or (hi is not None and len(arr) > hi):
            span = f"{lo} to {hi}" if hi is not None else f"at least {lo}"
            self.fail(where, fld, f"{len(arr)} nodes", f"{span} nodes", raw=True)
        out: List[Node] = []
        seen: set = set()
        for i, x in enumerate(arr):
            n = self.node(x, where, f"{fld}[{i}]", kinds, role)
            if n is None:
                continue
            if n.id and n.id in seen:
                self.fail(where, f"{fld}[{i}].id", f'"{n.id}" again', raw=True,
                          expected="node ids unique within the rule (or the start graph)")
            seen.add(n.id)
            out.append(n)
        return out

    def edges(self, raw: Any, where: str, fld: str, ids: Sequence[str]) -> List[Edge]:
        arr = self.array(raw, where, fld, '[ {a = "x", b = "y"} ]')
        if arr is None:
            return []
        ids = sorted(set(i for i in ids if i))
        idlist = _one_of(ids) if ids else "a node id (there are none)"
        out: List[Edge] = []
        pairs: set = set()
        for i, x in enumerate(arr):
            p = f"{fld}[{i}]"
            tbl = self.table(x, where, p, '{a = "x", b = "y", rel = "above"}')
            if tbl is None:
                continue
            p += "."
            self.keys(tbl, where, ("a", "b", "rel", "tags"), prefix=p)
            ends = []
            for end in ("a", "b"):
                v = tbl.get(end, _MISSING)
                if v not in ids:
                    self.fail(where, p + end, v, f"a node id of this {_node_scope(fld)}: {idlist}")
                ends.append(v if isinstance(v, str) else "")
            a, b = ends
            if a and a == b:
                self.fail(where, p + "b", b, "a different node from a (no self-loops)")
            pair = tuple(sorted((a, b)))
            if a and b and a != b:
                if pair in pairs:
                    self.fail(where, p + "b", f'"{a}"-"{b}" again', raw=True,
                              expected="one edge per node pair")
                pairs.add(pair)
            rel = tbl.get("rel", "any")
            if rel not in RELATIONS:
                self.fail(where, p + "rel", rel, _one_of(RELATIONS) + ' (b relative to a; default "any")')
                rel = "any"
            tags = tbl.get("tags", [])
            good_tags = []
            if not isinstance(tags, list):
                self.fail(where, p + "tags", tags, f"an array of tags, each {_one_of(TAGS)}")
            else:
                for j, t in enumerate(tags):
                    if t in TAGS:
                        good_tags.append(t)
                    else:
                        self.fail(where, f"{p}tags[{j}]", t, _one_of(TAGS))
            out.append(Edge(a, b, rel, frozenset(good_tags)))
        return out

    # -- when ------------------------------------------------------------------

    def when(self, raw: Any, where: str) -> List[Condition]:
        tbl = self.table(raw, where, "when", '{ race_scale = ">=1.5" }')
        if tbl is None:
            return []
        out = []
        for key, v in tbl.items():
            if key not in WHEN_KEYS:
                self.fail(where, f"when.{key}", "an unknown condition key", _one_of(WHEN_KEYS), raw=True)
                continue
            c = self._condition(key, v, where)
            if c is not None:
                out.append(c)
        return out

    def _condition(self, key: str, v: Any, where: str) -> Optional[Condition]:
        fld = f"when.{key}"
        if key in _WHEN_TEXT:
            allowed = _WHEN_TEXT[key]
            expected = f"a {key} or an array of them, each {_one_of(allowed)}"
            if isinstance(v, list) and v and all(x in allowed for x in v):
                return Condition(key, "in", tuple(v))
            if isinstance(v, str) and v in allowed:
                return Condition(key, "==", v)
            self.fail(where, fld, v, expected)
            return None
        whole = key == "room_count"
        kind = "whole number" if whole else "number"
        expected = (f'a {kind}, an array of {kind}s, or a comparison string like '
                    f'">={"10" if whole else "1.5"}" (operators {", ".join(COMPARISONS)})')

        def ok(x: Any) -> bool:
            return _is_number(x) and (not whole or isinstance(x, int))

        if isinstance(v, list) and v and all(ok(x) for x in v):
            return Condition(key, "in", tuple(v))
        if ok(v):
            return Condition(key, "==", v)
        if isinstance(v, str):
            m = _COMPARISON_RE.fullmatch(v)
            if m:
                return Condition(key, m.group(1), float(m.group(2)))
        self.fail(where, fld, v, expected)
        return None

    # -- rules -----------------------------------------------------------------

    def rule(self, name: str, raw: Any, kinds: Sequence[str]) -> Optional[Rule]:
        where = f"rules.{name}"
        tbl = self.table(raw, where, "rule", '[rules.name] with description, match, replace, reattach')
        if tbl is None:
            return None
        allowed = ("description", "when", "match", "match_edges", "match_hops",
                   "replace", "edges", "reattach")
        self.keys(tbl, where, allowed, required=("description", "match", "replace", "reattach"))
        desc = self.text(tbl, "description", where, required=False)
        when = self.when(tbl["when"], where) if "when" in tbl else []
        match = self.nodes(tbl.get("match", []), where, "match", kinds, "match",
                           lo=1, hi=MAX_MATCH_NODES) if "match" in tbl else []
        match_ids = [n.id for n in match]
        match_edges = (self.edges(tbl["match_edges"], where, "match_edges", match_ids)
                       if "match_edges" in tbl else [])
        hops = self.hops(tbl["match_hops"], where, match_ids, match_edges) if "match_hops" in tbl else []
        repl = self.nodes(tbl.get("replace", []), where, "replace", kinds, "replace") \
            if "replace" in tbl else []
        repl_ids = [n.id for n in repl]
        edges = self.edges(tbl["edges"], where, "edges", repl_ids) if "edges" in tbl else []
        self.levels_agree(edges, where, "edges")
        reattach = self.reattach(tbl["reattach"], where, match_ids, repl_ids) if "reattach" in tbl else []
        return Rule(name, desc, tuple(match), tuple(match_edges), tuple(hops), tuple(repl),
                    tuple(edges), tuple(reattach), tuple(when), self.file)

    def levels_agree(self, edges: Sequence[Edge], where: str, fld: str) -> None:
        """Step 7: the edges' vertical relations must agree round every loop."""
        conflict = relative_levels(edges)[1]
        if conflict is not None:
            self.fail(where, fld, conflict, raw=True,
                      expected="above / below / level relations that agree round every "
                               "loop (going round, the Levels must come back to the start)")

    def hops(self, raw: Any, where: str, match_ids: Sequence[str],
             match_edges: Sequence[Edge]) -> List[Hops]:
        tbl = self.table(raw, where, "match_hops", "{ p_q = [2, 3] }")
        if tbl is None:
            return []
        pairs = {f"{a}_{b}": (a, b) for a in match_ids for b in match_ids if a and b and a != b}
        adjacent = {tuple(sorted((e.a, e.b))) for e in match_edges}
        out = []
        for key, v in tbl.items():
            fld = f"match_hops.{key}"
            if key not in pairs:
                names = ", ".join(sorted(f'"{k}"' for k in pairs)) or "none (needs two match nodes)"
                self.fail(where, fld, "a key naming no pair of match nodes", raw=True,
                          expected=f"a key \"<a>_<b>\" naming two match nodes: {names}")
                continue
            a, b = pairs[key]
            if not (isinstance(v, list) and len(v) == 2 and all(isinstance(x, int)
                    and not isinstance(x, bool) for x in v) and 2 <= v[0] <= v[1]):
                self.fail(where, fld, v, "[lo, hi], whole numbers with 2 <= lo <= hi "
                          "(the two nodes are lo to hi hops apart, not adjacent)")
                continue
            if tuple(sorted((a, b))) in adjacent:
                self.fail(where, fld, v, f"no match edge between {a} and {b} "
                          "(match_hops nodes are not adjacent)")
                continue
            out.append(Hops(a, b, v[0], v[1]))
        return out

    def reattach(self, raw: Any, where: str, match_ids: Sequence[str],
                 repl_ids: Sequence[str]) -> List[Tuple[str, Tuple[str, ...]]]:
        tbl = self.table(raw, where, "reattach", '{ x = ["x"] }')
        if tbl is None:
            return []
        targets = sorted(set(i for i in repl_ids if i))
        tlist = _one_of(targets) if targets else "a replacement node id (there are none)"
        mlist = _one_of(sorted(set(i for i in match_ids if i))) if match_ids else "a match node id"
        for key in tbl:
            if key not in match_ids:
                self.fail(where, f"reattach.{key}", f'"{key}"', raw=True,
                          expected=f"a match node id as the key: {mlist}")
        out = []
        for m in match_ids:
            if not m:
                continue
            fld = f"reattach.{m}"
            v = tbl.get(m, _MISSING)
            expected = (f"a non-empty array of replacement node ids taking {m}'s outside "
                        f"edges in order, each {tlist}")
            if not isinstance(v, list) or not v:
                self.fail(where, fld, v, expected)
                continue
            bad = [x for x in v if x not in targets]
            if bad:
                for x in bad:
                    self.fail(where, fld, x, expected)
                continue
            out.append((m, tuple(v)))
        return out

    def rules(self, raw: Any, kinds: Sequence[str], required: bool) -> Dict[str, Rule]:
        if raw is _MISSING:
            if required:
                self.fail("top level", "rules", raw, "at least one [rules.<name>] table")
            return {}
        tbl = self.table(raw, "top level", "rules", "[rules.<name>]")
        if tbl is None:
            return {}
        if required and not tbl:
            self.fail("top level", "rules", "no rules", "at least one [rules.<name>] table", raw=True)
        out = {}
        for name, r in tbl.items():
            rule = self.rule(name, r, kinds)
            if rule is not None:
                out[name] = rule
        return out

    # -- recipe ----------------------------------------------------------------

    def apply(self, raw: Any, where: str) -> Dict[str, float]:
        tbl = self.table(raw, where, "apply", "{ lengthen = 3, passage = 1 }")
        if tbl is None:
            return {}
        if not tbl:
            self.fail(where, "apply", "no rules", "at least one rule name with a weight", raw=True)
        out = {}
        for k, w in tbl.items():
            if _is_number(w) and w > 0:
                out[k] = w
            else:
                self.fail(where, f"apply.{k}", w, "a weight, a number above 0")
        return out

    def stage(self, raw: Any, idx: int, label: str = "recipe",
              extra: Sequence[str] = ()) -> Optional[Stage]:
        where = f"{label}[{idx}]"
        tbl = self.table(raw, where, "stage", '[[recipe]] with stage, apply, share')
        if tbl is None:
            return None
        name = tbl.get("stage")
        if isinstance(name, str) and name.strip():
            where = f'{label} "{name}"'
        allowed = tuple(extra) + ("stage", "apply", "share")
        self.keys(tbl, where, allowed, required=allowed)
        name = self.text(tbl, "stage", where, required=False)
        apply = self.apply(tbl["apply"], where) if "apply" in tbl else {}
        share: Union[float, str, None] = None
        if "share" in tbl:
            v = tbl["share"]
            if v == REST or (_is_number(v) and 0 < v <= 1):
                share = v
            else:
                self.fail(where, "share", v, 'a number in (0, 1] (the stage\'s part of the '
                          'room budget), or "rest" on the last stage')
        return Stage(name, apply, share)

    def recipe(self, raw: Any) -> List[Stage]:
        if raw is _MISSING:
            self.fail("top level", "recipe", raw, "an array of [[recipe]] stages")
            return []
        arr = self.array(raw, "top level", "recipe", "[[recipe]] tables")
        if arr is None:
            return []
        return [s for i, x in enumerate(arr) if (s := self.stage(x, i)) is not None]

    def check_recipe(self, recipe: Sequence[Stage], rules: Mapping[str, Rule]) -> None:
        """Rule names, stage names, shares, the rest stage and its finishing rule."""
        if not recipe:
            self.fail("recipe", "stages", "none", "at least one [[recipe]] stage, the last "
                      'with share = "rest"', raw=True)
            return
        known = sorted(rules)
        seen: set = set()
        for i, s in enumerate(recipe):
            where = f'recipe "{s.name}"' if s.name else f"recipe[{i}]"
            if s.name and s.name in seen:
                self.fail(where, "stage", s.name, "a stage name not used by another stage")
            seen.add(s.name)
            for r in s.apply:
                if r not in rules:
                    self.fail(where, f"apply.{r}", "a rule not in the set", raw=True,
                              expected=f"a rule of the set (or its layers): {_one_of(known)}")
            if s.is_rest and i != len(recipe) - 1:
                self.fail(where, "share", REST, 'a number in (0, 1]; only the last stage takes "rest"')
        numeric = [s.share for s in recipe if _is_number(s.share)]
        total = sum(numeric)
        if total > 1 + _SHARE_TOLERANCE:
            parts = " + ".join(f"{x:g}" for x in numeric)
            self.fail("recipe", "share", f"shares summing to {total:g} ({parts})", raw=True,
                      expected="numeric shares summing to at most 1")
        last = recipe[-1]
        where = f'recipe "{last.name}"' if last.name else f"recipe[{len(recipe) - 1}]"
        if not last.is_rest and last.share is not None:
            self.fail(where, "share", last.share, '"rest" on the last stage (it takes the '
                      'rest of the room budget and finishes every Area)')
        finishers = sorted(n for n, r in rules.items() if r.finishes_area)
        if not any(r in rules and rules[r].finishes_area for r in last.apply):
            self.fail(where, "apply", "no rule that turns an Area into a room", raw=True,
                      expected="a rule whose match has an Area and whose replace has none"
                      + (f": {_one_of(finishers)}" if finishers else ""))


def _node_scope(fld: str) -> str:
    return {"match_edges": "match", "edges": "replacement",
            "start_edges": "start graph"}.get(fld, "rule")


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

def _read_toml(path: Path, chk: _Checker) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        chk.fail("file", "path", str(path), "an existing rule file", raw=False)
    except tomllib.TOMLDecodeError as exc:
        chk.fail("file", "toml", str(exc), "valid TOML 1.0 (inline tables on one line; "
                 "arrays may span lines)", raw=False)
    return None


def _kinds(chk: _Checker, raw: Any, where: str) -> Tuple[str, ...]:
    if raw is _MISSING:
        return ()
    names = chk.names(raw, where, "kinds", "kind")
    out = []
    for i, k in enumerate(names):
        if k in BASE_KINDS or k in out:
            chk.fail(where, f"kinds[{i}]", k, "a new kind name, not already one of "
                     + ", ".join(BASE_KINDS + tuple(out)))
        elif not re.fullmatch(r"[a-z][a-z0-9_]*", k):
            chk.fail(where, f"kinds[{i}]", k, "a lower-case name (letters, digits, _)")
        else:
            out.append(k)
    return tuple(out)


def load_rule_set(path: Union[str, Path]) -> RuleSet:
    """Load and check one base set; raises :class:`RuleSetError` with every failure."""
    path = Path(path)
    chk = _Checker(path.name)
    data = _read_toml(path, chk)
    chk.raise_if_failed()
    chk.keys(data, "top level", ("set", "rules", "recipe"), required=("set", "rules", "recipe"))
    st = (chk.table(data["set"], "top level", "set", "[set] with name, description, placement")
          if "set" in data else None)
    if st is not None:
        chk.keys(st, "set", ("name", "description", "placement", "kinds", "start_nodes",
                             "start_edges"),
                 required=("name", "description", "placement", "start_nodes"))
    st = st or {}
    name = chk.text(st, "name", "set", required=False)
    if name and name != path.stem:
        chk.fail("set", "name", name, f'"{path.stem}" (the file\'s name, so the theme map finds it)')
    desc = chk.text(st, "description", "set", required=False)
    placement = st.get("placement", _MISSING)
    if placement is not _MISSING and placement not in PLACEMENTS:
        chk.fail("set", "placement", placement, _one_of(PLACEMENTS))
    kinds = _kinds(chk, st.get("kinds", _MISSING), "set")
    all_kinds = BASE_KINDS + kinds
    start = chk.nodes(st["start_nodes"], "set", "start_nodes", all_kinds, "start") \
        if "start_nodes" in st else []
    entrances = [n.id for n in start if n.kind == ENTRANCE]
    if "start_nodes" in st and len(entrances) != 1:
        chk.fail("set", "start_nodes", f"{len(entrances)} entrance nodes", raw=True,
                 expected='exactly one node with kind = "entrance"')
    start_edges = chk.edges(st["start_edges"], "set", "start_edges", [n.id for n in start]) \
        if "start_edges" in st else []
    chk.levels_agree(start_edges, "set", "start_edges")
    rules = chk.rules(data.get("rules", _MISSING), all_kinds, required=True)
    recipe = chk.recipe(data.get("recipe", _MISSING)) if "recipe" in data else []
    if "recipe" in data:
        chk.check_recipe(recipe, rules)
    chk.raise_if_failed()
    return RuleSet(name, desc, placement, kinds, tuple(start), tuple(start_edges),
                   rules, tuple(recipe), path.name)


def load_layer(path: Union[str, Path]) -> ThemeLayer:
    """Load and check one theme layer (what can be checked without its base)."""
    path = Path(path)
    chk = _Checker(path.name)
    data = _read_toml(path, chk)
    chk.raise_if_failed()
    chk.keys(data, "top level", ("layer", "rules", "stages", "insert"), required=("layer",))
    ly = (chk.table(data["layer"], "top level", "layer", "[layer] with name, description, fits")
          if "layer" in data else None)
    if ly is not None:
        chk.keys(ly, "layer", ("name", "description", "fits", "kinds"),
                 required=("name", "description", "fits"))
    ly = ly or {}
    name = chk.text(ly, "name", "layer", required=False)
    if name and name != path.stem:
        chk.fail("layer", "name", name, f'"{path.stem}" (the file\'s name, so the theme map finds it)')
    desc = chk.text(ly, "description", "layer", required=False)
    fits: Tuple[str, ...] = ()
    if "fits" in ly:
        fits = chk.names(ly["fits"], "layer", "fits", "base set")
        if not fits and isinstance(ly["fits"], list):
            chk.fail("layer", "fits", "[]", "at least one base set name", raw=True)
    kinds = _kinds(chk, ly.get("kinds", _MISSING), "layer")
    rules = chk.rules(data.get("rules", _MISSING), BASE_KINDS + kinds, required=False)
    weights: Dict[str, Dict[str, float]] = {}
    if "stages" in data:
        stbl = chk.table(data["stages"], "top level", "stages", '[stages."Side rooms"]') or {}
        for sname, raw in stbl.items():
            where = f'stages."{sname}"'
            t = chk.table(raw, where, "stage", "{ apply = { nave = 2 } }")
            if t is None:
                continue
            chk.keys(t, where, ("apply",), required=("apply",))
            if "apply" in t:
                weights[sname] = chk.apply(t["apply"], where)
    inserts: List[Insert] = []
    if "insert" in data:
        arr = chk.array(data["insert"], "top level", "insert", "[[insert]] tables") or []
        for i, raw in enumerate(arr):
            s = chk.stage(raw, i, label="insert", extra=("after",))
            if s is None:
                continue
            where = f'insert "{s.name}"' if s.name else f"insert[{i}]"
            after = chk.text(raw, "after", where, required=False)
            inserts.append(Insert(after, s))
    chk.raise_if_failed()
    return ThemeLayer(name, desc, fits, kinds, rules, weights, tuple(inserts), path.name)


def load_theme_map(path: Union[str, Path]) -> ThemeMap:
    """Load and check ``themes.toml``: theme -> {base, layers, walls}; ``default`` required."""
    path = Path(path)
    chk = _Checker(path.name)
    data = _read_toml(path, chk)
    chk.raise_if_failed()
    themes = (DEFAULT_THEME,) + tuple(VALID_DUNGEON_THEMES)
    entries: Dict[str, ThemeEntry] = {}
    # By file, not by loading: a style's own checks run when the style is loaded.
    styles = tuple(sorted(p.stem for p in (path.parent.parent / "walls").glob("*.toml"))) or ("built",)
    for theme, raw in data.items():
        if theme not in themes:
            chk.fail("top level", theme, "an unknown theme", _one_of(themes), raw=True)
            continue
        t = chk.table(raw, theme, "entry", '{ base = "classic_eq", layers = ["temple"] }')
        if t is None:
            continue
        chk.keys(t, theme, ("base", "layers", "walls"), required=("base",))
        base = chk.text(t, "base", theme, required=False)
        layers = chk.names(t["layers"], theme, "layers", "layer") if "layers" in t else ()
        walls = chk.text(t, "walls", theme, required=False, default="built")
        if walls not in styles:
            chk.fail(theme, "walls", walls, _one_of(styles))
            walls = "built"
        entries[theme] = ThemeEntry(base, layers, walls)
    if DEFAULT_THEME not in data:
        chk.fail("top level", DEFAULT_THEME, _MISSING,
                 'a default entry, e.g. default = { base = "classic_eq" }')
    chk.raise_if_failed()
    return ThemeMap(entries, path.name)


# ---------------------------------------------------------------------------
# Merging
# ---------------------------------------------------------------------------

def merge(base: RuleSet, layers: Sequence[ThemeLayer]) -> RuleSet:
    """The base set with its layers' rules and stages added; checks the result.

    ``base`` and the layers are not changed. Every failure, across all layers
    and the merged recipe, raises one :class:`RuleSetError`.
    """
    if not layers:
        return base
    errors: List[CheckError] = []
    rules: Dict[str, Rule] = dict(base.rules)
    recipe: List[Stage] = [Stage(s.name, dict(s.apply), s.share) for s in base.recipe]
    inserted_after: Dict[int, str] = {}       # id(stage) -> the stage it was inserted after
    kinds = list(base.kinds)
    for layer in layers:
        chk = _Checker(layer.source)
        if base.name not in layer.fits:
            chk.fail("layer", "fits", list(layer.fits),
                     f'a list including "{base.name}" (the base set it is merged onto)')
        for k in layer.kinds:
            if k not in kinds:
                kinds.append(k)
        for name, rule in layer.rules.items():
            if name in rules:
                chk.fail(f"rules.{name}", "name", name, "a rule name not already in "
                         f"{rules[name].source} (rules: {', '.join(sorted(rules))})")
            else:
                rules[name] = rule
        stage_names = [s.name for s in recipe]
        for sname, added in layer.stage_weights.items():
            if sname not in stage_names:
                chk.fail(f'stages."{sname}"', "stage", sname,
                         f"a stage of {base.name}: {_one_of(stage_names)}")
                continue
            i = stage_names.index(sname)
            apply = dict(recipe[i].apply)
            for r, w in added.items():
                apply[r] = apply.get(r, 0) + w
            recipe[i] = Stage(recipe[i].name, apply, recipe[i].share)
        for ins in layer.inserts:
            stage_names = [s.name for s in recipe]
            where = f'insert "{ins.stage.name}"'
            if ins.after not in stage_names:
                chk.fail(where, "after", ins.after, f"a stage to insert after: {_one_of(stage_names)}")
                continue
            pos = stage_names.index(ins.after) + 1
            while pos < len(recipe) and inserted_after.get(id(recipe[pos])) == ins.after:
                pos += 1
            stage = Stage(ins.stage.name, dict(ins.stage.apply), ins.stage.share)
            recipe.insert(pos, stage)
            inserted_after[id(stage)] = ins.after
        errors.extend(chk.errors)
    if errors:
        raise RuleSetError(errors)
    source = " + ".join([base.source] + [l.source for l in layers])
    chk = _Checker(source)
    chk.check_recipe(recipe, rules)
    chk.raise_if_failed()
    return RuleSet(base.name, base.description, base.placement, tuple(kinds),
                   base.start_nodes, base.start_edges, rules, tuple(recipe), source,
                   base.layers + tuple(l.name for l in layers))


def load_for_theme(rules_dir: Union[str, Path], theme: Optional[str],
                   rule_set: Optional[str] = None) -> RuleSet:
    """The merged rule set for a theme, from ``rules_dir/themes.toml``.

    ``rule_set`` names a base set instead of the theme's; the theme's layers
    still apply when they fit it (and are skipped when they don't).
    """
    rules_dir = Path(rules_dir)
    tmap = load_theme_map(rules_dir / "themes.toml")
    entry = tmap.entry_for(theme)
    base_name = rule_set or entry.base
    base_path = rules_dir / f"{base_name}.toml"
    if not base_path.is_file():
        sets = sorted(p.stem for p in rules_dir.glob("*.toml") if p.stem != "themes")
        where = "request" if rule_set else (theme if theme in tmap.entries else DEFAULT_THEME)
        raise RuleSetError([CheckError(tmap.source, where, "base", _show(base_name),
                                       f"a rule set in {rules_dir.name}/: {_one_of(sets)}")])
    base = load_rule_set(base_path)
    layers = [load_layer(rules_dir / "layers" / f"{n}.toml") for n in entry.layers]
    if rule_set is not None:
        layers = [l for l in layers if base.name in l.fits]
    return merge(base, layers)


__all__ = [
    "PLACEMENTS", "WHEN_KEYS", "COMPARISONS", "REST", "DEFAULT_THEME",
    "LEVEL_STEP", "relative_levels",
    "CheckError", "RuleSetError", "Condition", "Hops", "Rule", "Stage", "Insert",
    "RuleSet", "ThemeLayer", "ThemeEntry", "ThemeMap",
    "load_rule_set", "load_layer", "load_theme_map", "merge", "load_for_theme",
]
