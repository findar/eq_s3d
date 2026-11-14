"""Decor recipes as data (roadmap step 11, Reqs 5 and 7; design "Decor recipes as data").

``rules/decor/`` holds two rule files, loaded and checked together:

- ``rooms.toml``: Decor_Recipes by default, room kind and room type (and by Site kind), each a
  list of lines asking for Props by Tag (a kind, or a Group of kinds) with an arrangement, a
  count, a chance and the Scale that moves them; the lines every room takes after its own
  (``every``); the Groups; Dressing by POI purpose; and the Weights by Layer;
- ``sets.toml``: which Sets a room takes, by race, theme and zone type, and which Sets may
  share a room.

**Lookup** is step 9's: a room takes its room type's recipe, else its kind's, else its zone
type's (``[zones.<zone type>]``: a city's rooms have neither type nor kind), else the default
(``recipe_for``), then the ``every`` lines. A Site takes its Site kind's recipe, or
nothing, and no ``every`` lines.

**Mount** comes from where a line stands (``at``): ``on_wall`` and ``wall`` ask for wall
models, ``ceiling`` for ceiling ones, ``stack`` (in a Group) for one that stands on another,
and the rest for floor models. A line's kind may be one kind or a list of alternatives, best
first ("a throne or a seat").

**Weights by Layer** (Req 7.4) move how many Props a room gets, by Category: each is a
multiplier on the recipe's counts. A room's Layers are default, zone type, race, theme, room
kind, room type, least specific first, and they combine with step 9's arithmetic
(``room_scales.combine``): the geometric mean of the Layers that name the Category, so a race
and a theme blend; ``override = true`` replaces every less specific Layer; and when written
zeros leave nothing, the most specific Layer that names it decides. The Decor control is
applied on top of the blend (as a Scale control is), not as one more voice in it. ``bare`` is
the chance a room takes only its Dressing (design finding 1: about a quarter of dungeon rooms
hold nothing). A line's Scale (``by``, else the Category's entry in ``moves``: Clutter moves
debris, Structure furniture) scales it as step 9's do: 5 is the line as written, 0 nothing,
10 twice as much, and under ``from`` the line isn't there.

**The usable-model check** (Req 7.3): every kind a line asks for, at its Mount, should have at
least one ``use = "yes"`` model in the catalogue; ``unmet`` names each line with none. At
build time such a line drops (archive decision 14), so an unmet line is a report, not a load
failure: ``scripts/topology_rules.py check rules/decor`` prints them, and fails on them only
with ``--strict`` (meant for after the tag review, task 4).

**Decor layers** (step 15): ``layers/<name>.toml`` files, each a ``[layer]`` header (``name``,
``description``) and any of ``rooms.toml``'s sections but ``default`` and ``moves``, merged onto
the base at load time (``load_decor``'s ``layers``; the merge rules are in its docstring).
``themes.toml`` says which layers a dungeon theme, and a race, takes (``layers_for``);
``layer_names`` lists the folder.

Every bad value is named by file, entry and field (``RuleSetError``), as step 9's and step
10's loaders do. Nothing here places anything: that's ``generators/decor/placement.py``.
"""

from __future__ import annotations

import copy
import random
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, FrozenSet, Iterator, List, Mapping, Optional, Sequence, Tuple

from ai.schema import VALID_DUNGEON_RACES, VALID_DUNGEON_THEMES, VALID_ZONE_TYPES, available_inhabitants
from generators.decor.catalogue import CATEGORIES, DECOR_DIR, TAGS_FILE, Catalogue, read_reviews
from generators.room_scales import SCALES, Layer, combine
from generators.semantics import ROOM_TYPES
from generators.sites.rules import POI_PURPOSES as SITE_POI_PURPOSES, SITE_KINDS, SITES_DIR, SITES_FILE
from generators.topology.graph import ROOM_KINDS
from generators.topology.ruleset import CheckError, RuleSetError, _Checker, _is_number, _one_of, _read_toml, _show

ROOMS_FILE, SETS_FILE = "rooms.toml", "sets.toml"

#: Where a room line stands. The Mount follows (``MOUNT_OF``).
ARRANGEMENTS: Tuple[str, ...] = ("on_wall", "along_wall", "corners", "centre", "far_end", "scatter", "rows",
                                 "by_door", "ceiling", "on_dais")
#: Where a Dressing line stands, round its POI (never on the POI's own spot, Req 8.2).
DRESSING_AT: Tuple[str, ...] = ("beside", "behind", "flank", "round", "wall")
#: Where a Group's member stands: the first is the ``anchor``, the rest round, in a row with,
#: beside or on top of it.
MEMBER_AT: Tuple[str, ...] = ("anchor", "round", "row", "beside", "stack")
MOUNT_OF: Dict[str, str] = {"on_wall": "wall", "wall": "wall", "ceiling": "ceiling", "stack": "raised"}
#: The Mounts a model may carry to fill a line of each Mount: a crate on a crate is a floor crate.
MOUNTS_FILLING: Dict[str, Tuple[str, ...]] = {"floor": ("floor",), "wall": ("wall",), "ceiling": ("ceiling",),
                                              "raised": ("raised", "floor")}
#: Room POI purposes (``room_layouts.POI_PURPOSES``) and Site ones (``sites.rules.POI_PURPOSES``).
ROOM_POI_PURPOSES: Tuple[str, ...] = ("boss", "treasure", "altar", "guard", "ambush", "view")
POI_PURPOSES: Tuple[str, ...] = tuple(dict.fromkeys(ROOM_POI_PURPOSES + SITE_POI_PURPOSES))
#: The Decor control (Req 10.1).
CONTROLS: Tuple[str, ...] = ("none", "sparse", "normal", "dense")
DEFAULT_CONTROL = "normal"
AS_WRITTEN = 5          # the value of a Scale at which a line stands as written (as step 9's)
MAX_COUNT = 12
BARE = "bare"
NEUTRAL = "neutral"


def mount_of(at: str) -> str:
    return MOUNT_OF.get(at, "floor")


# ---------------------------------------------------------------------------
# Loaded data
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Member:
    """One member of a Group: a kind (or alternatives, best first), where it stands, how many."""
    kinds: Tuple[str, ...]
    at: str
    count: Tuple[int, int] = (1, 1)
    category: str = "other"
    #: Where it was written, for reports, when a decor layer touched its Group (else
    #: ``("", "", "")``: ``rooms.toml``, ``groups.<name>``, ``members[i]``).
    where: Tuple[str, str, str] = ("", "", "")

    @property
    def mount(self) -> str:
        return mount_of(self.at)


@dataclass(frozen=True)
class Group:
    """Props placed together as one, whole or not at all (Req 6.3)."""
    name: str
    members: Tuple[Member, ...]

    @property
    def category(self) -> str:
        return self.members[0].category if self.members else "other"


@dataclass(frozen=True)
class Line:
    """One line of a recipe or a Dressing: this many of a kind (or a Group) here.
    ``where`` names it for reports: ``("rooms.toml", "types.barracks", "props[1]")``."""
    kinds: Tuple[str, ...]
    group: str
    at: str
    count: Tuple[int, int]
    chance: float
    by: str                         # the Scale that moves it ("" for none)
    at_least: int                   # under this value of ``by``, the line isn't there
    category: str
    where: Tuple[str, str, str] = ("", "", "")

    @property
    def mount(self) -> str:
        return mount_of(self.at)


@dataclass(frozen=True)
class Recipe:
    name: str                       # "types.barracks", "kinds.hall", "default", "sites.camp", "every"
    lines: Tuple[Line, ...]


@dataclass(frozen=True)
class SetRules:
    races: Mapping[str, Tuple[str, ...]]
    themes: Mapping[str, Tuple[str, ...]]
    zone_types: Mapping[str, Tuple[str, ...]]
    allows: Mapping[str, Tuple[str, ...]]           # symmetric once loaded

    def sets_for(self, zone_type: str = "", race: str = "", theme: str = "") -> Tuple[str, ...]:
        """The room's Sets, best first: its race's, then its theme's, then its zone type's, and
        neutral last, which fills any room (Req 5)."""
        out = (tuple(self.races.get(race, ())) + tuple(self.themes.get(theme, ()))
               + tuple(self.zone_types.get(zone_type, ())) + (NEUTRAL,))
        return tuple(dict.fromkeys(out))

    def may_share(self, a: str, b: str) -> bool:
        """Whether Props of Sets ``a`` and ``b`` may stand in one room: the same Set, neutral,
        or a pair ``allows`` names (either way round)."""
        return a == b or NEUTRAL in (a, b) or b in self.allows.get(a, ())


@dataclass(frozen=True)
class DecorRules:
    default: Recipe
    kinds: Mapping[str, Recipe]
    types: Mapping[str, Recipe]
    sites: Mapping[str, Recipe]
    every: Recipe
    groups: Mapping[str, Group]
    dressing: Mapping[str, Tuple[Line, ...]]
    weights: Mapping[str, Any]          # "default" -> Layer; the rest -> {name: Layer}
    controls: Mapping[str, Mapping[str, float]]
    moves: Mapping[str, str]            # Category -> the Scale that moves its lines
    sets: SetRules
    #: A zone type's own recipe for its rooms with no room type or kind (``[zones.<zone type>]``:
    #: a city's rooms, which have neither), in place of the default.
    zones: Mapping[str, Recipe] = field(default_factory=dict)
    #: Kinds a room holds at most once (``once``, task 22: what stock rooms hold once).
    once: FrozenSet[str] = frozenset()
    #: The decor layers merged onto the base, in merge order (``load_decor``'s ``layers``).
    layers: Tuple[str, ...] = ()

    # -- lookup ---------------------------------------------------------------

    def recipe_for(self, room_type: str = "", kind: str = "", source: str = "room",
                   zone_type: str = "") -> Tuple[Recipe, ...]:
        """A room's recipes, in the order they're placed: its room type's, else its kind's, else
        its zone type's, else the default, then ``every``. A Site's: its Site kind's, or none."""
        if source == "site":
            return (self.sites[room_type],) if room_type in self.sites else ()
        own = self.types.get(room_type) or self.kinds.get(kind) or self.zones.get(zone_type) or self.default
        return (own, self.every)

    def which_recipe(self, room_type: str = "", kind: str = "", zone_type: str = "") -> str:
        """The name of the recipe a room of this type and kind takes (``types.X``, ``kinds.X``,
        ``zones.X`` or ``default``): what a room type without one falls back to."""
        return self.recipe_for(room_type, kind, zone_type=zone_type)[0].name

    def dressing_for(self, purpose: str) -> Tuple[Line, ...]:
        return self.dressing.get(purpose, ())

    # -- Weights by Layer -----------------------------------------------------

    def layers_for(self, zone_type: str = "", race: str = "", theme: str = "", kind: str = "",
                   room_type: str = "") -> Tuple[Layer, ...]:
        """A room's Layers, least specific first. A name with no table has none."""
        w = self.weights
        found = (w["zone_types"].get(zone_type), w["races"].get(race), w["themes"].get(theme),
                 w["kinds"].get(kind), w["types"].get(room_type))
        return (w["default"],) + tuple(x for x in found if x is not None)

    def weights_for(self, zone_type: str = "", race: str = "", theme: str = "", kind: str = "",
                    room_type: str = "", control: str = DEFAULT_CONTROL) -> Dict[str, float]:
        """Each Category's multiplier for this room (and ``bare``, its chance of taking only
        its Dressing): the Layers' blend, the control on top."""
        layers = self.layers_for(zone_type, race, theme, kind, room_type)
        on_top = self.controls[control]
        out = {c: combine(c, layers)[0] * on_top.get(c, 1.0) for c in CATEGORIES}
        out[BARE] = min(1.0, combine(BARE, layers)[0])
        return out

    def line_by(self, line: Line) -> str:
        return line.by or self.moves.get(line.category, "")

    def factor(self, line: Line, weights: Mapping[str, float],
               scales: Optional[Mapping[str, int]] = None) -> float:
        """How much of the line as written a room takes: its Category's weight times its Scale's."""
        by = self.line_by(line)
        if not by:
            return weights.get(line.category, 1.0)
        value = (scales or {}).get(by, AS_WRITTEN)
        if value < line.at_least:
            return 0.0
        return weights.get(line.category, 1.0) * value / AS_WRITTEN

    def group_size(self, line: Line) -> float:
        """The mean Props one of the line's items is: 1, or a Group's members."""
        if not line.group:
            return 1.0
        return sum((m.count[0] + m.count[1]) / 2 for m in self.groups[line.group].members)

    def expected(self, zone_type: str = "dungeon", race: str = "", theme: str = "", kind: str = "",
                 room_type: str = "", scales: Optional[Mapping[str, int]] = None,
                 control: str = DEFAULT_CONTROL, source: str = "room") -> Dict[str, float]:
        """The mean Props a room takes by Category (Dressing aside), as ``draw_count`` draws them:
        what design finding 1's bands are checked against."""
        weights = self.weights_for(zone_type, race, theme, kind, room_type, control)
        out = {c: 0.0 for c in CATEGORIES}
        for recipe in self.recipe_for(room_type, kind, source, zone_type):
            for line in recipe.lines:
                mean = line.chance * (line.count[0] + line.count[1]) / 2 * self.factor(line, weights, scales)
                if line.group:
                    for m in self.groups[line.group].members:
                        out[m.category] += mean * (m.count[0] + m.count[1]) / 2
                else:
                    out[line.category] += mean
        keep = 1.0 - weights[BARE]
        return {c: v * keep for c, v in out.items()}

    # -- every line, for checks and drawings -------------------------------------

    def lines(self) -> Iterator[Line]:
        """Every recipe and Dressing line."""
        for recipe in (self.default, *self.kinds.values(), *self.types.values(), *self.zones.values(),
                       *self.sites.values(), self.every):
            yield from recipe.lines
        for lines in self.dressing.values():
            yield from lines


def draw_count(line: Line, factor: float, rng: random.Random) -> int:
    """How many of a line a room takes: the line's chance, a count in its range, times
    ``factor`` (``DecorRules.factor``) with the fraction kept by chance, so the mean is exact."""
    if factor <= 0 or rng.random() >= line.chance:
        return 0
    n = rng.randint(*line.count) * factor
    whole = int(n)
    return whole + (1 if rng.random() < n - whole else 0)


# ---------------------------------------------------------------------------
# Checking
# ---------------------------------------------------------------------------

def _count(chk: _Checker, v: Any, where: str, fld: str) -> Optional[Tuple[int, int]]:
    if isinstance(v, int) and not isinstance(v, bool):
        v = [v, v]
    if not (isinstance(v, list) and len(v) == 2 and all(isinstance(c, int) and not isinstance(c, bool) for c in v)
            and 0 <= v[0] <= v[1] <= MAX_COUNT and v[1] > 0):
        chk.fail(where, fld, v, f"a number or [low, high], from 0 to {MAX_COUNT}, above 0 at the top")
        return None
    return (v[0], v[1])


def _number(chk: _Checker, v: Any, where: str, fld: str, lo: float, hi: Optional[float]) -> Optional[float]:
    if not _is_number(v) or v < lo or (hi is not None and v > hi):
        chk.fail(where, fld, v, f"a number from {lo:g} to {hi:g}" if hi is not None else f"a number from {lo:g} up")
        return None
    return float(v)


def _kinds(chk: _Checker, v: Any, where: str, fld: str, kinds: Mapping[str, str]) -> Optional[Tuple[str, ...]]:
    """One kind or a list of alternatives, best first."""
    vals = [v] if isinstance(v, str) else v
    if not isinstance(vals, list) or not vals:
        chk.fail(where, fld, v, 'a kind, or a list of kinds best first, like ["throne", "chair"]')
        return None
    bad = [x for x in vals if not isinstance(x, str) or x not in kinds]
    if bad:
        chk.fail(where, fld, bad[0], "a kind of generators/decor/catalogue.py KINDS or tags.toml's kinds "
                 f"(e.g. {', '.join(sorted(kinds)[:6])}, ...)")
        return None
    return tuple(dict.fromkeys(vals))


def _line(chk: _Checker, item: Any, where: str, i: int, arrangements: Sequence[str], kinds: Mapping[str, str],
          groups: Mapping[str, Any], file: str, fld: str = "props",
          origin: Optional[Tuple[str, int]] = None) -> Optional[Line]:
    """``origin`` is the (file, index) the line was written at, when a layer merged it."""
    p = f"{fld}[{i}]."
    t = chk.table(item, where, f"{fld}[{i}]", '{ kind = "torch", at = "on_wall", count = [1, 2] }')
    if t is None:
        return None
    chk.keys(t, where, ("kind", "group", "at", "count", "chance", "by", "from"), required=("at",), prefix=p)
    ok = True
    names: Tuple[str, ...] = ()
    group = ""
    if ("kind" in t) == ("group" in t):
        chk.fail(where, p + "kind", "both kind and group" if "kind" in t else "neither kind nor group",
                 "one of them: a kind (or kinds) or a Group", raw=True)
        ok = False
    elif "kind" in t:
        got = _kinds(chk, t["kind"], where, p + "kind", kinds)
        ok = got is not None
        names = got or ()
    else:
        group = t["group"]
        if group not in groups:
            chk.fail(where, p + "group", group, _one_of(sorted(groups)) if groups else "a Group in [groups]")
            ok = False
    at = t.get("at")
    if at is not None and at not in arrangements:
        chk.fail(where, p + "at", at, _one_of(arrangements))
        ok = False
    elif group and mount_of(at) != "floor":
        chk.fail(where, p + "at", at, "a floor arrangement: a Group stands on the floor")
        ok = False
    count = _count(chk, t["count"], where, p + "count") if "count" in t else (1, 1)
    chance = _number(chk, t["chance"], where, p + "chance", 0.0, 1.0) if "chance" in t else 1.0
    by = t.get("by", "")
    if by and by not in SCALES:
        chk.fail(where, p + "by", by, _one_of(SCALES))
        ok = False
    at_least = t.get("from", 0)
    if not (isinstance(at_least, int) and not isinstance(at_least, bool) and 0 <= at_least <= 10):
        chk.fail(where, p + "from", at_least, "a whole number from 0 to 10")
        ok = False
    if not ok or count is None or chance is None or at is None:
        return None
    if names:
        category = kinds[names[0]]
    else:
        g = groups[group]
        category = g.category if isinstance(g, Group) else "other"
    src, idx = origin if origin is not None else (file, i)
    return Line(names, group, at, count, chance, by, at_least, category, (src, where, f"{fld}[{idx}]"))


def _lines(chk: _Checker, raw: Any, where: str, arrangements: Sequence[str], kinds: Mapping[str, str],
           groups: Mapping[str, Any], file: str,
           origins: Optional[Sequence[Tuple[str, int]]] = None) -> Tuple[Line, ...]:
    tbl = chk.table(raw, where.rpartition(".")[0] or "top level", where.rpartition(".")[2] or where,
                    '{ props = [ { kind = "torch", at = "on_wall" } ] }')
    if tbl is None:
        return ()
    chk.keys(tbl, where, ("props",), required=("props",))
    arr = chk.array(tbl.get("props", []), where, "props", '[ { kind = "torch", at = "on_wall" } ]')
    out = []
    for i, item in enumerate(arr or ()):
        origin = origins[i] if origins is not None and i < len(origins) else None
        got = _line(chk, item, where, i, arrangements, kinds, groups, file, origin=origin)
        if got is not None:
            out.append(got)
    return tuple(out)


def _group(chk: _Checker, name: str, raw: Any, kinds: Mapping[str, str], start: int = 0,
           origins: Optional[Sequence[Tuple[str, int]]] = None) -> Optional[Group]:
    """``start``: members already in the Group before these (a layer's ``mode = "add"``), so
    the anchor rule holds across both. ``origins``: each member's (file, index), when a layer
    touched the Group."""
    where = f"groups.{name}"
    tbl = chk.table(raw, "groups", name, '{ members = [ { kind = "table", at = "anchor" }, ... ] }')
    if tbl is None:
        return None
    chk.keys(tbl, where, ("members",), required=("members",))
    arr = chk.array(tbl.get("members", []), where, "members", '[ { kind = "table", at = "anchor" } ]')
    if arr is None:
        return None
    members = []
    ok = True
    for i, item in enumerate(arr):
        p = f"members[{i}]."
        t = chk.table(item, where, f"members[{i}]", '{ kind = "chair", at = "round", count = [1, 3] }')
        if t is None:
            ok = False
            continue
        chk.keys(t, where, ("kind", "at", "count"), required=("kind", "at"), prefix=p)
        names = _kinds(chk, t["kind"], where, p + "kind", kinds) if "kind" in t else None
        at = t.get("at")
        if at is not None and at not in MEMBER_AT:
            chk.fail(where, p + "at", at, _one_of(MEMBER_AT))
            at = None
        elif at is not None and (at == "anchor") != (i + start == 0):
            chk.fail(where, p + "at", at, '"anchor" for the first member and only the first',
                     raw=False)
            at = None
        count = _count(chk, t["count"], where, p + "count") if "count" in t else (1, 1)
        if i + start == 0 and count not in (None, (1, 1)):
            chk.fail(where, p + "count", t["count"], "1: a Group has one anchor")
            count = None
        if names is None or at is None or count is None:
            ok = False
            continue
        src: Tuple[str, str, str] = ("", "", "")
        if origins is not None and i < len(origins):
            src = (origins[i][0], where, f"members[{origins[i][1]}]")
        members.append(Member(names, at, count, kinds[names[0]], src))
    if not arr and not start:
        chk.fail(where, "members", arr, "at least one member, the anchor first")
        return None
    return Group(name, tuple(members)) if ok else None


def _layer(chk: _Checker, raw: Any, where: str, allow_bare: bool = True) -> Layer:
    tbl = chk.table(raw, where.rpartition(".")[0] or "weights", where.rpartition(".")[2],
                    "{ light = 1.2, debris = 0.5 }")
    if tbl is None:
        return Layer()
    allowed = CATEGORIES + ((BARE,) if allow_bare else ())
    chk.keys(tbl, where, allowed)
    weights, overrides = {}, []
    for name in allowed:
        if name not in tbl:
            continue
        v, override = tbl[name], False
        if isinstance(v, dict):
            chk.keys(v, where, ("value", "override"), required=("value",), prefix=f"{name}.")
            override = v.get("override", False)
            if not isinstance(override, bool):
                chk.fail(where, f"{name}.override", override, "true or false")
                continue
            v = v.get("value")
        hi = 1.0 if name == BARE else None
        got = _number(chk, v, where, name, 0.0, hi) if v is not None else None
        if got is None:
            continue
        weights[name] = (got,)
        if override:
            overrides.append(name)
    return Layer(weights, tuple(overrides))


def _weights(chk: _Checker, raw: Any) -> Tuple[Dict[str, Any], Dict[str, Dict[str, float]]]:
    tbl = chk.table(raw, "top level", "weights", "[weights.default]") or {}
    sections = _weight_sections()
    chk.keys(tbl, "weights", ("default", "controls") + tuple(sections), required=("default", "controls"))
    out: Dict[str, Any] = {"default": Layer()}
    if "default" in tbl:
        default = _layer(chk, tbl["default"], "weights.default")
        for name in CATEGORIES + (BARE,):
            if isinstance(tbl["default"], dict) and name not in tbl["default"]:
                chk.fail("weights.default", name, "nothing", "a weight: every room starts from the default", raw=True)
        if default.overrides:
            chk.fail("weights.default", "override", "true", "nothing: the default has no less specific Layer",
                     raw=True)
        out["default"] = default
    for section, known in sections.items():
        sub = chk.table(tbl.get(section, {}), "weights", section, f"[weights.{section}.<name>]") or {}
        layers = {}
        for name, body in sub.items():
            if name not in known:
                chk.fail(f"weights.{section}", name, "an unknown name", _one_of(known), raw=True)
                continue
            layers[name] = _layer(chk, body, f"weights.{section}.{name}")
        out[section] = layers
    controls: Dict[str, Dict[str, float]] = {}
    sub = chk.table(tbl.get("controls", {}), "weights", "controls", "[weights.controls.<name>]") or {}
    for name, body in sub.items():
        if name not in CONTROLS:
            chk.fail("weights.controls", name, "an unknown control", _one_of(CONTROLS), raw=True)
            continue
        layer = _layer(chk, body, f"weights.controls.{name}", allow_bare=False)
        if layer.overrides:
            chk.fail(f"weights.controls.{name}", "override", "true", "nothing: a control is on top of the blend",
                     raw=True)
        controls[name] = {c: w[0] for c, w in layer.weights.items()}
    for name in CONTROLS:
        if name not in sub:
            chk.fail("weights.controls", name, "nothing", "an entry for every Decor control (" + ", ".join(CONTROLS)
                     + ")", raw=True)
    return out, controls


def _weight_sections() -> Dict[str, Sequence[str]]:
    """The named Weights sections (Layers by name) and the names each may hold."""
    return {"zone_types": VALID_ZONE_TYPES, "races": _races(), "themes": VALID_DUNGEON_THEMES,
            "kinds": ROOM_KINDS, "types": sorted(ROOM_TYPES)}


def _races() -> List[str]:
    """Races a room or a Site names: the dungeon races and the Site Inhabitants."""
    return list(dict.fromkeys(list(VALID_DUNGEON_RACES) + available_inhabitants()))


def _site_kinds() -> Tuple[str, ...]:
    """The Site kinds: those every rule set holds and any more ``rules/sites/sites.toml`` adds."""
    try:
        with open(SITES_DIR / SITES_FILE, "rb") as f:
            extra = tuple(tomllib.load(f).get("kinds", {}))
    except (OSError, tomllib.TOMLDecodeError):
        extra = ()
    return tuple(dict.fromkeys(SITE_KINDS + extra))


def _set_names(chk: _Checker, v: Any, where: str, fld: str, sets: Sequence[str]) -> Tuple[str, ...]:
    if not isinstance(v, list) or any(not isinstance(x, str) for x in v):
        chk.fail(where, fld, v, 'a list of Sets, like ["goblin"]')
        return ()
    bad = [x for x in v if x not in sets]
    if bad:
        chk.fail(where, fld, bad[0], "a Set of generators/decor/catalogue.py SETS or tags.toml's sets ("
                 + ", ".join(sets) + ")")
        return ()
    return tuple(dict.fromkeys(v))


def _sets(chk: _Checker, data: Mapping[str, Any], sets: Sequence[str]) -> SetRules:
    sections = {"races": _races(), "themes": VALID_DUNGEON_THEMES, "zone_types": VALID_ZONE_TYPES,
                "allows": tuple(sets)}
    chk.keys(data, "top level", tuple(sections), required=("races", "themes", "zone_types"))
    out: Dict[str, Dict[str, Tuple[str, ...]]] = {}
    for section, known in sections.items():
        tbl = chk.table(data.get(section, {}), "top level", section, f"[{section}]") or {}
        got = {}
        for name, v in tbl.items():
            if name not in known:
                chk.fail(section, name, "an unknown name", _one_of(known), raw=True)
                continue
            names = _set_names(chk, v, section, name, sets)
            if section == "allows" and name in names:
                chk.fail(section, name, name, "other Sets: a Set always shares a room with itself")
                continue
            got[name] = names
        out[section] = got
    allows: Dict[str, set] = {}
    for a, bs in out["allows"].items():
        for b in bs:
            allows.setdefault(a, set()).add(b)
            allows.setdefault(b, set()).add(a)
    return SetRules(out["races"], out["themes"], out["zone_types"],
                    {k: tuple(sorted(v)) for k, v in allows.items()})


def _moves(chk: _Checker, raw: Any) -> Dict[str, str]:
    tbl = chk.table(raw, "top level", "moves", '{ debris = "clutter", furniture = "structure" }') or {}
    out = {}
    for c, scale in tbl.items():
        if c not in CATEGORIES:
            chk.fail("moves", c, "an unknown Category", _one_of(CATEGORIES), raw=True)
        elif scale not in SCALES:
            chk.fail("moves", c, scale, _one_of(SCALES))
        else:
            out[c] = scale
    return out


def _once(chk: _Checker, raw: Any, kinds: Mapping[str, str]) -> FrozenSet[str]:
    if not isinstance(raw, list):
        chk.fail("top level", "once", raw, 'a list of kinds: ["forge", "anvil"]')
        return frozenset()
    out = set()
    for k in raw:
        if k not in kinds:
            chk.fail("once", k, "an unknown kind", _one_of(sorted(kinds)), raw=True)
        else:
            out.add(k)
    return frozenset(out)


def _recipe_sections() -> Tuple[Tuple[str, Sequence[str]], ...]:
    """The named recipe sections of ``rooms.toml`` and the names each may hold."""
    return (("kinds", ROOM_KINDS), ("types", sorted(ROOM_TYPES)), ("zones", VALID_ZONE_TYPES),
            ("sites", _site_kinds()))


Origins = Mapping[str, Sequence[Tuple[str, int]]]


def _parse_rooms(chk: _Checker, rooms: Mapping[str, Any], kinds: Mapping[str, str],
                 origins: Optional[Origins] = None) -> Tuple[Any, ...]:
    """``rooms.toml``'s raw tables (or a merged set's) into recipes, Groups, Dressing, Weights,
    moves and once. ``origins``: entry -> each line's (file, index), for entries a layer touched."""
    origins = origins or {}
    chk.keys(rooms, "top level", ("default", "every", "kinds", "types", "zones", "sites", "groups", "dressing",
                                  "weights", "moves", "once"),
             required=("default", "every", "dressing", "weights"))
    raw_groups = chk.table(rooms.get("groups", {}), "top level", "groups", "[groups.<name>]") or {}
    groups: Dict[str, Any] = {}
    for name, body in raw_groups.items():
        got = _group(chk, name, body, kinds, origins=origins.get(f"groups.{name}"))
        # A bad Group's own error names it: lines naming it shouldn't fail twice.
        groups[name] = got if got is not None else name
    default = Recipe("default", _lines(chk, rooms.get("default", {}), "default", ARRANGEMENTS, kinds, groups,
                                       ROOMS_FILE))
    every = Recipe("every", _lines(chk, rooms.get("every", {}), "every", ARRANGEMENTS, kinds, groups, ROOMS_FILE,
                                   origins.get("every")))
    named: Dict[str, Dict[str, Recipe]] = {}
    for section, known in _recipe_sections():
        tbl = chk.table(rooms.get(section, {}), "top level", section, f"[{section}.<name>]") or {}
        out = {}
        for name, body in tbl.items():
            if name not in known:
                chk.fail(section, name, "an unknown name", _one_of(known), raw=True)
                continue
            where = f"{section}.{name}"
            out[name] = Recipe(where, _lines(chk, body, where, ARRANGEMENTS, kinds, groups, ROOMS_FILE,
                                             origins.get(where)))
        named[section] = out
    dressing: Dict[str, Tuple[Line, ...]] = {}
    tbl = chk.table(rooms.get("dressing", {}), "top level", "dressing", "[dressing.<POI purpose>]") or {}
    for purpose, body in tbl.items():
        if purpose not in POI_PURPOSES:
            chk.fail("dressing", purpose, "an unknown POI purpose", _one_of(POI_PURPOSES), raw=True)
            continue
        where = f"dressing.{purpose}"
        dressing[purpose] = _lines(chk, body, where, DRESSING_AT, kinds, groups, ROOMS_FILE, origins.get(where))
    for purpose in ("boss", "treasure", "altar", "guard"):     # Req 8.1 names their Dressing
        if purpose not in tbl:
            chk.fail("dressing", purpose, "nothing", "Dressing for every POI Req 8.1 names (boss, treasure, "
                     "altar, guard)", raw=True)
    weights, controls = _weights(chk, rooms.get("weights", {}))
    moves = _moves(chk, rooms.get("moves", {}))
    once = _once(chk, rooms.get("once", []), kinds)
    return default, named, every, groups, dressing, weights, controls, moves, once


def _rules(parsed: Tuple[Any, ...], set_rules: SetRules, layers: Tuple[str, ...] = ()) -> DecorRules:
    default, named, every, groups, dressing, weights, controls, moves, once = parsed
    return DecorRules(default, named["kinds"], named["types"], named["sites"], every,
                      {k: g for k, g in groups.items() if isinstance(g, Group)}, dressing, weights, controls, moves,
                      set_rules, named["zones"], once, layers)


def load_decor(path=DECOR_DIR, tags: Optional[Path] = None, layers: Sequence[str] = ()) -> DecorRules:
    """Load and check ``rooms.toml`` and ``sets.toml`` from ``path`` (a folder), with the decor
    ``layers`` named (``path/layers/<name>.toml``) merged onto ``rooms.toml``; raises
    ``RuleSetError`` with every failure. Kinds and Sets are the catalogue's
    (``generators/decor/catalogue.py``) with whatever ``tags`` (default: the folder's
    ``tags.toml``, else the shipped one) adds. The usable-model check is ``unmet``.

    **Layers** merge in the order given (a name given twice counts once, where it first
    stands). A build's order is the theme's layers, then its race's (both from
    ``themes.toml``, ``layers_for``), then the request's extra ones. The base is checked on its
    own, then each layer file on its own (named by its file), then the merged set as a whole
    (named ``rooms.toml + <layer>.toml ...``), every failure by file, entry and field.

    A layer's entry (a recipe, a Group, a Dressing, a Weights entry) that is new is added. One
    that the base or an earlier layer already has is refused, naming both files, unless the
    entry says ``mode = "add"`` (its lines, or a Group's members, join the existing ones; a
    Weights entry's Categories join the entry's, and a Category already there is refused) or
    ``mode = "replace"`` (it stands instead). A ``mode`` on a new entry is allowed: there is
    nothing to join or replace, so the entry is simply added. ``once`` kinds join the base's.
    With no layers this is the base alone, as before layers existed."""
    path = Path(path)
    if tags is None:
        tags = path / TAGS_FILE if (path / TAGS_FILE).is_file() else DECOR_DIR / TAGS_FILE
    t_chk = _Checker(TAGS_FILE)
    _, kinds, sets = read_reviews(Path(tags), None, t_chk)
    if t_chk.errors:
        raise RuleSetError(t_chk.errors)
    r_chk, s_chk = _Checker(ROOMS_FILE), _Checker(SETS_FILE)
    rooms, set_data = _read_toml(path / ROOMS_FILE, r_chk), _read_toml(path / SETS_FILE, s_chk)

    def raise_all() -> None:
        errors: List[CheckError] = r_chk.errors + s_chk.errors
        if errors:
            raise RuleSetError(errors)
    raise_all()

    parsed = _parse_rooms(r_chk, rooms, kinds)
    set_rules = _sets(s_chk, set_data, sets)
    raise_all()
    names = tuple(dict.fromkeys(layers))
    if not names:
        return _rules(parsed, set_rules)

    known = layer_names(path)
    merge = _Merge(rooms)
    groups: Dict[str, Any] = dict(parsed[3])
    errors: List[CheckError] = []
    for n in names:
        file = path / LAYERS_DIR / f"{n}.toml" if isinstance(n, str) and n else None
        if file is None or not file.is_file():
            errors.append(CheckError(f"{n}.toml", "layer", "name", _show(n),
                                     f"a decor layer in {path.name}/{LAYERS_DIR}/: "
                                     + (_one_of(sorted(known)) if known else "none yet")))
            continue
        errors.extend(_apply_layer(merge, file, kinds, groups))
    if errors:
        raise RuleSetError(errors)
    chk = _Checker(" + ".join([ROOMS_FILE] + [f"{n}.toml" for n in names]))
    merged = _parse_rooms(chk, merge.raw, kinds, merge.origins)
    chk.raise_if_failed()
    return _rules(merged, set_rules, names)


# ---------------------------------------------------------------------------
# Decor layers (step 15, Reqs 1 and 2.1; design "Decor layers")
# ---------------------------------------------------------------------------

LAYERS_DIR = "layers"
THEMES_FILE = "themes.toml"
#: What a layer's entry may do to one already there (archive decision 1).
MODES: Tuple[str, ...] = ("add", "replace")
#: The sections a layer may hold (Req 1.1): the base's, but ``default`` and ``moves``.
LAYER_SECTIONS: Tuple[str, ...] = ("kinds", "types", "zones", "sites", "groups", "dressing", "every", "weights",
                                   "once")


class _Merge:
    """The base's raw tables with layers merged onto them, and who wrote what."""

    def __init__(self, rooms: Mapping[str, Any]):
        self.raw: Dict[str, Any] = copy.deepcopy(dict(rooms))
        self.owner: Dict[str, str] = {}                     # entry -> the file that wrote it (else rooms.toml)
        self.origins: Dict[str, List[Tuple[str, int]]] = {}  # entry -> each line's (file, index)
        self.cats: Dict[Tuple[str, str], str] = {}          # (Weights entry, Category) -> file

    def _slot(self, path: Sequence[str]) -> Tuple[Dict[str, Any], Any]:
        parent = self.raw
        for k in path[:-1]:
            if not isinstance(parent.get(k), dict):
                parent[k] = {}
            parent = parent[k]
        return parent, parent.get(path[-1])

    def entry(self, chk: _Checker, path: Sequence[str], body: Dict[str, Any], mode: Optional[str],
              items: str) -> None:
        """A recipe, Dressing (``items = "props"``) or Group (``"members"``)."""
        where = ".".join(path)
        parent, have = self._slot(path)
        new = body.get(items) if isinstance(body.get(items), list) else []
        mine = [(chk.file, i) for i in range(len(new))]
        if have is None or mode == "replace":
            parent[path[-1]] = body
            self.owner[where], self.origins[where] = chk.file, mine
            return
        if mode != "add":
            chk.fail(where, "mode", "nothing", f'mode = "add" (its {items} join the existing ones) or "replace" '
                     f"(they stand instead): {where} is already in {self.owner.get(where, ROOMS_FILE)}", raw=True)
            return
        old = have.get(items) if isinstance(have.get(items), list) else []
        self.origins[where] = list(self.origins.get(where, [(ROOMS_FILE, i) for i in range(len(old))])) + mine
        parent[path[-1]] = {**have, items: list(old) + list(new)}

    def weights(self, chk: _Checker, path: Sequence[str], body: Dict[str, Any], mode: Optional[str]) -> None:
        where = ".".join(path)
        parent, have = self._slot(path)
        if have is None or mode == "replace":
            parent[path[-1]] = body
            self.owner[where] = chk.file
            for c in body:
                self.cats[(where, c)] = chk.file
            return
        if mode != "add":
            chk.fail(where, "mode", "nothing", 'mode = "add" (its Categories join the entry\'s) or "replace" '
                     f"(it stands instead): {where} is already in {self.owner.get(where, ROOMS_FILE)}", raw=True)
            return
        out = dict(have)
        for c, v in body.items():
            if c in have:
                chk.fail(where, c, v, f"a Category not already in {where} "
                         f"({self.cats.get((where, c), self.owner.get(where, ROOMS_FILE))} has it); "
                         'mode = "replace" stands for the whole entry')
            else:
                out[c] = v
                self.cats[(where, c)] = chk.file
        parent[path[-1]] = out


def _mode(chk: _Checker, raw: Any, where: str, fld: str, example: str
          ) -> Tuple[Optional[Dict[str, Any]], Optional[str], bool]:
    """A layer entry's table without its ``mode``, the mode, and whether the mode is good."""
    parent, _, name = where.rpartition(".")
    tbl = chk.table(raw, parent or "top level", fld or name, example)
    if tbl is None:
        return None, None, False
    mode = tbl.get("mode")
    if "mode" in tbl and mode not in MODES:
        chk.fail(where, "mode", mode, _one_of(MODES) + " (or no mode: a new entry)")
        return {k: v for k, v in tbl.items() if k != "mode"}, None, False
    return {k: v for k, v in tbl.items() if k != "mode"}, mode, True


def _apply_layer(merge: _Merge, file: Path, kinds: Mapping[str, str], groups: Dict[str, Any]) -> List[CheckError]:
    """Check one layer file on its own and merge it into ``merge``; its failures, by its file.
    ``groups`` (the Groups so far, by name) gains the layer's, so later lines may name them."""
    chk = _Checker(file.name)
    data = _read_toml(file, chk)
    if data is None:
        return chk.errors
    chk.keys(data, "top level", ("layer",) + LAYER_SECTIONS, required=("layer",))
    ly = (chk.table(data["layer"], "top level", "layer", "[layer] with name, description")
          if "layer" in data else None)
    if ly is not None:
        chk.keys(ly, "layer", ("name", "description"), required=("name", "description"))
        name = chk.text(ly, "name", "layer", required=False)
        if name and name != file.stem:
            chk.fail("layer", "name", name, f'"{file.stem}" (the file\'s name, so the theme map finds it)')
        chk.text(ly, "description", "layer", required=False)

    def entries(section: str) -> List[Tuple[str, Any]]:
        if section not in data:
            return []
        return list((chk.table(data[section], "top level", section, f"[{section}.<name>]") or {}).items())

    # Groups first, so lines may name them.
    for gname, raw in entries("groups"):
        where = f"groups.{gname}"
        body, mode, ok = _mode(chk, raw, where, gname, '{ members = [ { kind = "table", at = "anchor" } ] }')
        if body is None:
            continue
        _, have = merge._slot(("groups", gname))
        start = len(have["members"]) if (mode == "add" and isinstance(have, dict)
                                         and isinstance(have.get("members"), list)) else 0
        got = _group(chk, gname, body, kinds, start=start)
        if not (mode == "add" and gname in groups):
            groups[gname] = got if got is not None else gname
        if ok:
            merge.entry(chk, ("groups", gname), body, mode, "members")

    def recipe(path: Tuple[str, ...], raw: Any, arrangements: Sequence[str]) -> None:
        where = ".".join(path)
        body, mode, ok = _mode(chk, raw, where, path[-1], '{ props = [ { kind = "torch", at = "on_wall" } ] }')
        if body is None:
            return
        _lines(chk, body, where, arrangements, kinds, groups, file.name)
        if ok:
            merge.entry(chk, path, body, mode, "props")

    if "every" in data:
        recipe(("every",), data["every"], ARRANGEMENTS)
    for section, known in _recipe_sections():
        for name, raw in entries(section):
            if name not in known:
                chk.fail(section, name, "an unknown name", _one_of(known), raw=True)
                continue
            recipe((section, name), raw, ARRANGEMENTS)
    for purpose, raw in entries("dressing"):
        if purpose not in POI_PURPOSES:
            chk.fail("dressing", purpose, "an unknown POI purpose", _one_of(POI_PURPOSES), raw=True)
            continue
        recipe(("dressing", purpose), raw, DRESSING_AT)

    if "weights" in data:
        tbl = chk.table(data["weights"], "top level", "weights", "[weights.themes.<theme>]") or {}
        sections = _weight_sections()
        chk.keys(tbl, "weights", ("default", "controls") + tuple(sections))

        def weight(path: Tuple[str, ...], raw: Any, allow_bare: bool = True) -> None:
            where = ".".join(path)
            body, mode, ok = _mode(chk, raw, where, path[-1], "{ light = 1.2, debris = 0.5 }")
            if body is None:
                return
            layer = _layer(chk, body, where, allow_bare=allow_bare)
            if layer.overrides and path[1] in ("default", "controls"):
                chk.fail(where, "override", "true", "nothing: " + ("the default has no less specific Layer"
                         if path[1] == "default" else "a control is on top of the blend"), raw=True)
            if ok:
                merge.weights(chk, path, body, mode)

        if "default" in tbl:
            weight(("weights", "default"), tbl["default"])
        for section in ("controls",) + tuple(sections):
            if section not in tbl:
                continue
            known = CONTROLS if section == "controls" else sections[section]
            sub = chk.table(tbl[section], "weights", section, f"[weights.{section}.<name>]") or {}
            for name, raw in sub.items():
                if name not in known:
                    chk.fail(f"weights.{section}", name, "an unknown " + ("control" if section == "controls"
                             else "name"), _one_of(known), raw=True)
                    continue
                weight(("weights", section, name), raw, allow_bare=section != "controls")

    if "once" in data:
        added = _once(chk, data["once"], kinds)
        base = merge.raw.get("once", [])
        merge.raw["once"] = list(dict.fromkeys(list(base if isinstance(base, list) else [])
                                               + [k for k in data["once"] if k in added]))
    return chk.errors


def layer_names(path=DECOR_DIR) -> Dict[str, str]:
    """The decor layers in ``path/layers/``: name -> description, by name. Read from the folder,
    so a dropped-in file shows up; a file that can't be read is listed with no description
    (loading it names what's wrong)."""
    out: Dict[str, str] = {}
    for p in sorted((Path(path) / LAYERS_DIR).glob("*.toml")):
        desc = ""
        try:
            with open(p, "rb") as f:
                ly = tomllib.load(f).get("layer")
            if isinstance(ly, dict) and isinstance(ly.get("description"), str):
                desc = ly["description"]
        except (OSError, tomllib.TOMLDecodeError):
            pass
        out[p.stem] = desc
    return out


@dataclass(frozen=True)
class DecorThemes:
    """``themes.toml``: the decor layers each dungeon theme, and each race, takes."""
    themes: Mapping[str, Tuple[str, ...]]
    races: Mapping[str, Tuple[str, ...]]


def load_decor_themes(path=DECOR_DIR) -> DecorThemes:
    """Load and check ``path/themes.toml`` (no file: no theme takes a layer). A theme is a top-level
    key, ``tomb = { layers = ["tomb"] }``; races go in ``[races]`` the same way. Every layer named
    must be a file in ``path/layers/``."""
    path = Path(path)
    file = path / THEMES_FILE
    if not file.is_file():
        return DecorThemes({}, {})
    chk = _Checker(THEMES_FILE)
    data = _read_toml(file, chk)
    chk.raise_if_failed()
    known = layer_names(path)

    def entries(tbl: Mapping[str, Any], where: str, names: Sequence[str]) -> Dict[str, Tuple[str, ...]]:
        out = {}
        for name, raw in tbl.items():
            if name not in names:
                chk.fail(where, name, "an unknown name", _one_of(names), raw=True)
                continue
            t = chk.table(raw, where, name, '{ layers = ["tomb"] }')
            if t is None:
                continue
            at = name if where == "top level" else f"{where}.{name}"
            chk.keys(t, at, ("layers",), required=("layers",))
            got = chk.names(t["layers"], at, "layers", "layer") if "layers" in t else ()
            for i, n in enumerate(got):
                if n not in known:
                    chk.fail(at, f"layers[{i}]", n, f"a decor layer in {path.name}/{LAYERS_DIR}/: "
                             + (_one_of(sorted(known)) if known else "none yet"))
            out[name] = tuple(dict.fromkeys(got))
        return out

    themes = entries({k: v for k, v in data.items() if k != "races"}, "top level", VALID_DUNGEON_THEMES)
    races = entries(chk.table(data["races"], "top level", "races", '[races] goblin = { layers = ["x"] }') or {}
                    if "races" in data else {}, "races", _races())
    chk.raise_if_failed()
    return DecorThemes(themes, races)


def layers_for(theme: str = "", race: str = "", extra: Sequence[str] = (), path=DECOR_DIR) -> Tuple[str, ...]:
    """The decor layers a build takes, in merge order: its theme's, then its race's (both from
    ``themes.toml``), then ``extra`` (the request's), each name once, where it first stands."""
    m = load_decor_themes(path)
    return tuple(dict.fromkeys(tuple(m.themes.get(theme or "", ())) + tuple(m.races.get(race or "", ()))
                               + tuple(extra)))


# ---------------------------------------------------------------------------
# The usable-model check (Req 7.3)
# ---------------------------------------------------------------------------

def asks(rules: DecorRules) -> Iterator[Tuple[Tuple[str, str, str], Tuple[str, ...], str]]:
    """(where, kinds, Mount) for every line that asks for a kind, and every Group member."""
    for line in rules.lines():
        if line.kinds:
            yield line.where, line.kinds, line.mount
    for name, g in sorted(rules.groups.items()):
        for i, m in enumerate(g.members):
            yield (m.where if m.where[0] else (ROOMS_FILE, f"groups.{name}", f"members[{i}]")), m.kinds, m.mount


def usable_kinds(catalogue: Catalogue) -> Dict[str, set]:
    """Mount -> the kinds with at least one ``use = "yes"`` model there."""
    out: Dict[str, set] = {}
    for m in catalogue.usable().values():
        out.setdefault(m.tags.mount, set()).add(m.tags.kind)
    return out


def unmet(rules: DecorRules, catalogue: Catalogue) -> List[CheckError]:
    """Every line (and Group member) none of whose kinds has a ``use = "yes"`` model at its
    Mount, named by file, entry and field. Such a line drops at build time (archive
    decision 14); the tag review (task 4) is what meets it."""
    have = usable_kinds(catalogue)
    out = []
    for (file, where, fld), kinds, mount in asks(rules):
        ok = set().union(*(have.get(m, set()) for m in MOUNTS_FILLING[mount]))
        if not any(k in ok for k in kinds):
            found = " or ".join(kinds) + f" ({mount})"
            out.append(CheckError(file, where, fld + ".kind", found,
                                  f'a kind with a use = "yes" model at Mount {mount} (rules/decor/tags.toml)'))
    return out


def coverage(rules: DecorRules, room_types: Sequence[str], kind: str = "") -> Dict[str, str]:
    """Room type -> the recipe it takes: its own (``types.X``) or what it falls back to."""
    return {t: rules.which_recipe(t, kind) for t in room_types}


__all__ = ["ARRANGEMENTS", "AS_WRITTEN", "BARE", "CONTROLS", "DEFAULT_CONTROL", "DRESSING_AT", "DecorRules",
           "DecorThemes", "Group", "LAYERS_DIR", "LAYER_SECTIONS", "Line", "MEMBER_AT", "MODES", "MOUNTS_FILLING",
           "Member", "NEUTRAL", "POI_PURPOSES", "ROOMS_FILE", "Recipe", "SETS_FILE", "SetRules", "THEMES_FILE", "asks",
           "coverage", "draw_count", "layer_names", "layers_for", "load_decor", "load_decor_themes", "mount_of",
           "unmet", "usable_kinds"]
