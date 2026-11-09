"""Decor recipes as data (roadmap step 11, Reqs 5 and 7; design "Decor recipes as data").

``rules/decor/`` holds two rule files, loaded and checked together:

- ``rooms.toml``: Decor_Recipes by default, room kind and room type (and by Site kind), each a
  list of lines asking for Props by Tag (a kind, or a Group of kinds) with an arrangement, a
  count, a chance and the Scale that moves them; the lines every room takes after its own
  (``every``); the Groups; Dressing by POI purpose; and the Weights by Layer;
- ``sets.toml``: which Sets a room takes, by race, theme and zone type, and which Sets may
  share a room.

**Lookup** is step 9's: a room takes its room type's recipe, else its kind's, else the
default (``recipe_for``), then the ``every`` lines. A Site takes its Site kind's recipe, or
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

Every bad value is named by file, entry and field (``RuleSetError``), as step 9's and step
10's loaders do. Nothing here places anything: that's ``generators/decor/placement.py``.
"""

from __future__ import annotations

import random
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

from ai.schema import VALID_DUNGEON_RACES, VALID_DUNGEON_THEMES, VALID_ZONE_TYPES, available_inhabitants
from generators.decor.catalogue import CATEGORIES, DECOR_DIR, TAGS_FILE, Catalogue, read_reviews
from generators.room_scales import SCALES, Layer, combine
from generators.semantics import ROOM_TYPES
from generators.sites.rules import POI_PURPOSES as SITE_POI_PURPOSES, SITE_KINDS, SITES_DIR, SITES_FILE
from generators.topology.graph import ROOM_KINDS
from generators.topology.ruleset import CheckError, RuleSetError, _Checker, _is_number, _one_of, _read_toml

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

    # -- lookup ---------------------------------------------------------------

    def recipe_for(self, room_type: str = "", kind: str = "", source: str = "room") -> Tuple[Recipe, ...]:
        """A room's recipes, in the order they're placed: its room type's, else its kind's, else
        the default, then ``every``. A Site's: its Site kind's, or none."""
        if source == "site":
            return (self.sites[room_type],) if room_type in self.sites else ()
        own = self.types.get(room_type) or self.kinds.get(kind) or self.default
        return (own, self.every)

    def which_recipe(self, room_type: str = "", kind: str = "") -> str:
        """The name of the recipe a room of this type and kind takes (``types.X``, ``kinds.X``
        or ``default``): what a room type without one falls back to."""
        return self.recipe_for(room_type, kind)[0].name

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
        for recipe in self.recipe_for(room_type, kind, source):
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
        for recipe in (self.default, *self.kinds.values(), *self.types.values(), *self.sites.values(), self.every):
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
          groups: Mapping[str, Any], file: str, fld: str = "props") -> Optional[Line]:
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
    return Line(names, group, at, count, chance, by, at_least, category, (file, where, f"{fld}[{i}]"))


def _lines(chk: _Checker, raw: Any, where: str, arrangements: Sequence[str], kinds: Mapping[str, str],
           groups: Mapping[str, Any], file: str) -> Tuple[Line, ...]:
    tbl = chk.table(raw, where.rpartition(".")[0] or "top level", where.rpartition(".")[2] or where,
                    '{ props = [ { kind = "torch", at = "on_wall" } ] }')
    if tbl is None:
        return ()
    chk.keys(tbl, where, ("props",), required=("props",))
    arr = chk.array(tbl.get("props", []), where, "props", '[ { kind = "torch", at = "on_wall" } ]')
    out = []
    for i, item in enumerate(arr or ()):
        got = _line(chk, item, where, i, arrangements, kinds, groups, file)
        if got is not None:
            out.append(got)
    return tuple(out)


def _group(chk: _Checker, name: str, raw: Any, kinds: Mapping[str, str]) -> Optional[Group]:
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
        elif at is not None and (at == "anchor") != (i == 0):
            chk.fail(where, p + "at", at, '"anchor" for the first member and only the first',
                     raw=False)
            at = None
        count = _count(chk, t["count"], where, p + "count") if "count" in t else (1, 1)
        if i == 0 and count not in (None, (1, 1)):
            chk.fail(where, p + "count", t["count"], "1: a Group has one anchor")
            count = None
        if names is None or at is None or count is None:
            ok = False
            continue
        members.append(Member(names, at, count, kinds[names[0]]))
    if not arr:
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
    sections = {"zone_types": VALID_ZONE_TYPES, "races": _races(), "themes": VALID_DUNGEON_THEMES,
                "kinds": ROOM_KINDS, "types": sorted(ROOM_TYPES)}
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


def load_decor(path=DECOR_DIR, tags: Optional[Path] = None) -> DecorRules:
    """Load and check ``rooms.toml`` and ``sets.toml`` from ``path`` (a folder); raises
    ``RuleSetError`` with every failure of both. Kinds and Sets are the catalogue's
    (``generators/decor/catalogue.py``) with whatever ``tags`` (default: the folder's
    ``tags.toml``, else the shipped one) adds. The usable-model check is ``unmet``."""
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

    # rooms.toml
    chk = r_chk
    chk.keys(rooms, "top level", ("default", "every", "kinds", "types", "sites", "groups", "dressing", "weights",
                                  "moves"),
             required=("default", "every", "dressing", "weights"))
    raw_groups = chk.table(rooms.get("groups", {}), "top level", "groups", "[groups.<name>]") or {}
    groups: Dict[str, Any] = {}
    for name, body in raw_groups.items():
        got = _group(chk, name, body, kinds)
        # A bad Group's own error names it: lines naming it shouldn't fail twice.
        groups[name] = got if got is not None else name
    default = Recipe("default", _lines(chk, rooms.get("default", {}), "default", ARRANGEMENTS, kinds, groups,
                                       ROOMS_FILE))
    every = Recipe("every", _lines(chk, rooms.get("every", {}), "every", ARRANGEMENTS, kinds, groups, ROOMS_FILE))
    named: Dict[str, Dict[str, Recipe]] = {}
    for section, known in (("kinds", ROOM_KINDS), ("types", sorted(ROOM_TYPES)), ("sites", _site_kinds())):
        tbl = chk.table(rooms.get(section, {}), "top level", section, f"[{section}.<name>]") or {}
        out = {}
        for name, body in tbl.items():
            if name not in known:
                chk.fail(section, name, "an unknown name", _one_of(known), raw=True)
                continue
            out[name] = Recipe(f"{section}.{name}", _lines(chk, body, f"{section}.{name}", ARRANGEMENTS, kinds,
                                                           groups, ROOMS_FILE))
        named[section] = out
    dressing: Dict[str, Tuple[Line, ...]] = {}
    tbl = chk.table(rooms.get("dressing", {}), "top level", "dressing", "[dressing.<POI purpose>]") or {}
    for purpose, body in tbl.items():
        if purpose not in POI_PURPOSES:
            chk.fail("dressing", purpose, "an unknown POI purpose", _one_of(POI_PURPOSES), raw=True)
            continue
        dressing[purpose] = _lines(chk, body, f"dressing.{purpose}", DRESSING_AT, kinds, groups, ROOMS_FILE)
    for purpose in ("boss", "treasure", "altar", "guard"):     # Req 8.1 names their Dressing
        if purpose not in tbl:
            chk.fail("dressing", purpose, "nothing", "Dressing for every POI Req 8.1 names (boss, treasure, "
                     "altar, guard)", raw=True)
    weights, controls = _weights(chk, rooms.get("weights", {}))
    moves = _moves(chk, rooms.get("moves", {}))

    # sets.toml
    set_rules = _sets(s_chk, set_data, sets)

    raise_all()
    return DecorRules(default, named["kinds"], named["types"], named["sites"], every,
                      {k: g for k, g in groups.items() if isinstance(g, Group)}, dressing, weights, controls, moves,
                      set_rules)


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
            yield (ROOMS_FILE, f"groups.{name}", f"members[{i}]"), m.kinds, m.mount


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


__all__ = ["ARRANGEMENTS", "AS_WRITTEN", "BARE", "CONTROLS", "DEFAULT_CONTROL", "DRESSING_AT", "DecorRules", "Group",
           "Line", "MEMBER_AT", "MOUNTS_FILLING", "Member", "NEUTRAL", "POI_PURPOSES", "ROOMS_FILE", "Recipe",
           "SETS_FILE", "SetRules", "asks", "coverage", "draw_count", "load_decor", "mount_of", "unmet", "usable_kinds"]
