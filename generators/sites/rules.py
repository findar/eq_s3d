"""Site recipes as data (roadmap step 10, Req 5; design "Site recipes as data").

``rules/sites/`` holds three files, loaded and checked together:

- ``sites.toml``: the Structure models and each Site kind's recipe: its Structures, their
  arrangement, the ground it needs and likes, and its POIs;
- ``inhabitants.toml``: who builds Sites: a material set, model variants, swaps, and Weights
  over kinds;
- ``biomes.toml``: per biome, a density band, the Inhabitant mix and Weights over kinds.

A Site's kind is drawn from Layers multiplied, least specific first: biome x Inhabitant x
control, as step 9's Scales are (``generators/room_scales.combine``): the product, to the power
of one over how many Layers named the kind's table, and when written zeros leave nothing, the
most specific Layer with any weight decides. A kind's chance is its weight over the sum.

Every bad value is named by file, entry and field (``RuleSetError``), as step 9's loaders do.
Nothing here places anything: that is ``generators/sites/placement.py``.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from generators.topology.ruleset import CheckError, RuleSetError, _Checker, _is_number, _one_of, _read_toml, _type_name
from generators.wilderness.biome import biome_names

SITES_DIR = Path(__file__).resolve().parents[2] / "rules" / "sites"
SITES_FILE, INHABITANTS_FILE, BIOMES_FILE = "sites.toml", "inhabitants.toml", "biomes.toml"

#: The Site kinds every rule set must hold a recipe for (archive decision 3). More may be added
#: in the data alone.
SITE_KINDS: Tuple[str, ...] = ("camp", "hut", "farmstead", "watchtower", "shrine", "ruin")
#: The Structure models ``generators/sites/models.py`` builds; ``sites.toml`` describes them.
STRUCTURE_KINDS: Tuple[str, ...] = ("hut", "barn", "tent", "lean_to", "tower", "fire_ring", "fence",
                                    "standing_stone", "altar_stone", "monument", "ruin_wall")
ARRANGEMENTS: Tuple[str, ...] = ("ring", "row", "cluster", "lone", "perimeter")
CENTRE = "centre"
LINE_AT: Tuple[str, ...] = (CENTRE,) + ARRANGEMENTS
FACES: Tuple[str, ...] = ("in", "out", "any")
SIDES: Tuple[str, ...] = ("", "open")
LIKES: Tuple[str, ...] = ("near_water", "high_ground", "low_ground", "by_zoneline", "clearing")
POI_PURPOSES: Tuple[str, ...] = ("Light_Spot", "interior", "altar", "lookout", "gathering", "guard", "treasure")
ENTRANCE = "entrance"
POI_AT: Tuple[str, ...] = (CENTRE, ENTRANCE)
MAX_COUNT = 12

#: The Sites control -> its scale on a biome's density band (Req 8.1).
DENSITIES: Dict[str, float] = {"none": 0.0, "sparse": 0.5, "normal": 1.0, "dense": 2.0}
DEFAULT_DENSITY = "normal"

_NAME = re.compile(r"[a-z][a-z0-9_]*")
_STRUCTURE_NUMBERS = {"radius": (0.5, 100.0), "height": (0.5, 200.0)}
_GROUND_NUMBERS = {"radius": (4.0, 400.0), "slope_deg": (0.0, 40.0), "spacing": (0.0, 5000.0),
                   "margin": (0.0, 100.0)}
_LIKE_RANGE = (0.0, 10.0)


# ---------------------------------------------------------------------------
# Loaded data
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Structure:
    """One Structure model: its footprint's half-width and top (u), and whether it's walked into."""
    name: str
    radius: float
    height: float
    enterable: bool


@dataclass(frozen=True)
class Line:
    """One line of a recipe: stand this many of a Structure here."""
    kind: str
    count: Tuple[int, int] = (1, 1)
    at: str = CENTRE
    face: str = "any"
    side: str = ""
    chance: float = 1.0
    variant: str = ""               # the Inhabitant's model variant, once ``recipe_for`` names one


@dataclass(frozen=True)
class Ground:
    radius: float
    slope_deg: float
    spacing: float
    margin: float = 0.0


@dataclass(frozen=True)
class SitePOI:
    """A POI a Site names: a label, a purpose, and where (a Structure in the recipe, or the
    centre, or the way in). Advisory: sidecar only (Req 6.2)."""
    name: str
    purpose: str
    at: str


@dataclass(frozen=True)
class SiteRecipe:
    kind: str
    arrangement: str
    structures: Tuple[Line, ...]
    ground: Ground
    likes: Mapping[str, float]
    pois: Tuple[SitePOI, ...]


@dataclass(frozen=True)
class Inhabitant:
    name: str
    materials: str
    variants: Mapping[str, str] = field(default_factory=dict)
    swap: Mapping[str, str] = field(default_factory=dict)
    weights: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Biome:
    name: str
    density: Tuple[float, float]
    inhabitants: Mapping[str, float]
    weights: Mapping[str, float] = field(default_factory=dict)


Weights = Mapping[str, float]


def combine_weights(kinds: Sequence[str], layers: Sequence[Optional[Weights]]) -> Dict[str, float]:
    """Weights over ``kinds`` from Layers, least specific first, as step 9's ``combine``: a
    kind a Layer doesn't name it leaves alone (1); the product, to the power of one over how
    many Layers there are; and when the product is all zeros, which only written zeros can do,
    the most specific Layer with any weight decides. ``None`` Layers are skipped."""
    named = [layer for layer in layers if layer is not None]
    if not named:
        return {k: 1.0 for k in kinds}
    product = {k: 1.0 for k in kinds}
    for layer in named:
        for k in kinds:
            product[k] *= float(layer.get(k, 1.0))
    if any(product.values()):
        n = len(named)
        return {k: v ** (1.0 / n) for k, v in product.items()}
    for layer in reversed(named):
        w = {k: float(layer.get(k, 1.0)) for k in kinds}
        if any(w.values()):
            return w
    return {k: 1.0 for k in kinds}


def chances(weights: Weights) -> Dict[str, float]:
    """Each name's chance: its weight over the sum."""
    total = sum(weights.values())
    return {k: (v / total if total else 0.0) for k, v in weights.items()}


@dataclass(frozen=True)
class SiteRules:
    structures: Mapping[str, Structure]
    kinds: Mapping[str, SiteRecipe]
    inhabitants: Mapping[str, Inhabitant]
    biomes: Mapping[str, Biome]

    def kind_layers(self, biome: str, inhabitant: str,
                    control: Optional[Weights] = None) -> Tuple[Optional[Weights], ...]:
        """A Site's Layers over kinds, least specific first: biome, Inhabitant, control."""
        b, i = self.biomes.get(biome), self.inhabitants.get(inhabitant)
        return (b.weights if b else None, i.weights if i else None, control)

    def kind_weights(self, biome: str, inhabitant: str, control: Optional[Weights] = None) -> Dict[str, float]:
        return combine_weights(tuple(self.kinds), self.kind_layers(biome, inhabitant, control))

    def kind_chances(self, biome: str, inhabitant: str, control: Optional[Weights] = None) -> Dict[str, float]:
        """Each kind's chance for a Site of this Inhabitant in this biome: its weight over the sum."""
        return chances(self.kind_weights(biome, inhabitant, control))

    def inhabitant_chances(self, biome: str) -> Dict[str, float]:
        return chances(self.biomes[biome].inhabitants)

    def draw_inhabitant(self, biome: str, rng: random.Random, pinned: str = "") -> str:
        """The Inhabitant control's one name, else a draw from the biome's mix."""
        if pinned:
            if pinned not in self.inhabitants:
                raise KeyError(f"unknown Inhabitant {pinned!r}; {_one_of(sorted(self.inhabitants))}")
            return pinned
        mix = self.biomes[biome].inhabitants
        names = sorted(mix)
        return rng.choices(names, weights=[mix[n] for n in names])[0]

    def draw_kind(self, biome: str, inhabitant: str, rng: random.Random,
                  control: Optional[Weights] = None) -> str:
        w = self.kind_weights(biome, inhabitant, control)
        names = sorted(w)
        return rng.choices(names, weights=[w[n] for n in names])[0]

    def recipe_for(self, kind: str, inhabitant: str) -> SiteRecipe:
        """The kind's recipe as this Inhabitant builds it: its swaps made (POIs follow them) and
        each line carrying its model variant."""
        recipe, who = self.kinds[kind], self.inhabitants.get(inhabitant)
        if who is None:
            return recipe
        lines = []
        for line in recipe.structures:
            k = who.swap.get(line.kind, line.kind)
            lines.append(replace(line, kind=k, variant=who.variants.get(k, "")))
        pois = tuple(replace(p, at=who.swap.get(p.at, p.at)) for p in recipe.pois)
        return replace(recipe, structures=tuple(lines), pois=pois)

    def density(self, biome: str, control: str = DEFAULT_DENSITY) -> Tuple[float, float]:
        """The biome's band of Sites per 1e6 u^2 of walkable ground, scaled by the Sites control."""
        lo, hi = self.biomes[biome].density
        k = DENSITIES[control]
        return lo * k, hi * k


# ---------------------------------------------------------------------------
# Checking
# ---------------------------------------------------------------------------

def _number(chk: _Checker, v: Any, where: str, fld: str, lo: float, hi: float) -> Optional[float]:
    if not _is_number(v) or not lo <= v <= hi:
        chk.fail(where, fld, v, f"a number from {lo:g} to {hi:g}")
        return None
    return float(v)


def _ident(chk: _Checker, v: Any, where: str, fld: str) -> str:
    if not isinstance(v, str) or not _NAME.fullmatch(v):
        chk.fail(where, fld, v if isinstance(v, str) else _type_name(v),
                 "a name in lower case: letters, digits and _", raw=not isinstance(v, str))
        return ""
    return v


def _named_table(chk: _Checker, data: Mapping[str, Any], section: str, example: str) -> Dict[str, Any]:
    raw = data.get(section, {})
    return chk.table(raw, "top level", section, example) or {}


def _kind_weights(chk: _Checker, raw: Any, where: str, kinds: Sequence[str]) -> Dict[str, float]:
    """``{ kind = weight }``: known kinds, numbers from 0 up, at least one above 0."""
    tbl = chk.table(raw, where, "weights", "{ camp = 2, hut = 1 }")
    if tbl is None:
        return {}
    out = {}
    for k, v in tbl.items():
        if k not in kinds:
            chk.fail(where, f"weights.{k}", "an unknown Site kind", _one_of(kinds), raw=True)
            continue
        if not _is_number(v) or v < 0:
            chk.fail(where, f"weights.{k}", v, "a number from 0 up")
            continue
        out[k] = float(v)
    if tbl and out and not any(out.values()) and len(out) == len(kinds):
        chk.fail(where, "weights", tbl, "at least one weight above 0")
    return out


def _structure(chk: _Checker, name: str, raw: Any) -> Optional[Structure]:
    where = f"structures.{name}"
    if name not in STRUCTURE_KINDS:
        chk.fail("structures", name, "an unknown Structure (no model builds it)", _one_of(STRUCTURE_KINDS), raw=True)
        return None
    tbl = chk.table(raw, "structures", name, "{ radius = 6, height = 10, enterable = false }")
    if tbl is None:
        return None
    chk.keys(tbl, where, ("radius", "height", "enterable"), required=("radius", "height", "enterable"))
    values = {k: _number(chk, tbl[k], where, k, lo, hi) for k, (lo, hi) in _STRUCTURE_NUMBERS.items() if k in tbl}
    enterable = tbl.get("enterable", False)
    if not isinstance(enterable, bool):
        chk.fail(where, "enterable", enterable, "true or false")
        return None
    if None in values.values() or len(values) < 2:
        return None
    return Structure(name, values["radius"], values["height"], enterable)


def _count(chk: _Checker, v: Any, where: str, fld: str) -> Tuple[int, int]:
    if isinstance(v, int) and not isinstance(v, bool):
        v = [v, v]
    if not (isinstance(v, list) and len(v) == 2 and all(isinstance(c, int) and not isinstance(c, bool) for c in v)
            and 0 <= v[0] <= v[1] <= MAX_COUNT):
        chk.fail(where, fld, v, f"a number or [low, high], from 0 to {MAX_COUNT}")
        return (1, 1)
    return (v[0], v[1])


def _lines(chk: _Checker, raw: Any, where: str, arrangement: str, structures: Mapping[str, Structure]) -> List[Line]:
    arr = chk.array(raw, where, "structures", '[ { kind = "tent", count = [2, 4] } ]')
    if arr is None:
        return []
    if not arr:
        chk.fail(where, "structures", arr, "at least one line: a Site is built of Structures")
    out = []
    allowed = ("kind", "count", "at", "face", "side", "chance")
    for i, item in enumerate(arr):
        p = f"structures[{i}]."
        t = chk.table(item, where, f"structures[{i}]", '{ kind = "tent", count = [2, 4] }')
        if t is None:
            continue
        chk.keys(t, where, allowed, required=("kind",), prefix=p)
        ok = True
        kind = t.get("kind")
        if kind is not None and kind not in structures:
            chk.fail(where, p + "kind", kind, _one_of(sorted(structures)))
            ok = False
        at = t.get("at", arrangement)
        if at not in LINE_AT:
            chk.fail(where, p + "at", at, _one_of(LINE_AT))
            ok = False
        face = t.get("face", "any")
        if face not in FACES:
            chk.fail(where, p + "face", face, _one_of(FACES))
            ok = False
        side = t.get("side", "")
        if side not in SIDES:
            chk.fail(where, p + "side", side, 'one of "" (anywhere) or "open"')
            ok = False
        count = _count(chk, t["count"], where, p + "count") if "count" in t else (1, 1)
        chance = _number(chk, t["chance"], where, p + "chance", 0.0, 1.0) if "chance" in t else 1.0
        if chance is None:
            ok = False
        if ok and kind is not None:
            out.append(Line(kind, count, at, face, side, chance))
    return out


def _ground(chk: _Checker, raw: Any, where: str) -> Optional[Ground]:
    tbl = chk.table(raw, where, "ground", "{ radius = 24, slope_deg = 8, spacing = 400, margin = 8 }")
    if tbl is None:
        return None
    chk.keys(tbl, where, tuple(_GROUND_NUMBERS), required=("radius", "slope_deg", "spacing"), prefix="ground.")
    values = {}
    for k, (lo, hi) in _GROUND_NUMBERS.items():
        if k in tbl:
            values[k] = _number(chk, tbl[k], where, f"ground.{k}", lo, hi)
    if None in values.values() or not {"radius", "slope_deg", "spacing"} <= set(values):
        return None
    return Ground(**values)


def _likes(chk: _Checker, raw: Any, where: str) -> Dict[str, float]:
    tbl = chk.table(raw, where, "likes", "{ near_water = 3 }")
    if tbl is None:
        return {}
    out = {}
    for k, v in tbl.items():
        if k not in LIKES:
            chk.fail(where, f"likes.{k}", "an unknown like", _one_of(LIKES), raw=True)
            continue
        got = _number(chk, v, where, f"likes.{k}", *_LIKE_RANGE)
        if got is not None:
            out[k] = got
    return out


def _pois(chk: _Checker, raw: Any, where: str, lines: Sequence[Line],
          structures: Mapping[str, Structure]) -> List[SitePOI]:
    arr = chk.array(raw, where, "pois", '[ { name = "camp fire", purpose = "Light_Spot", at = "fire_ring" } ]')
    if arr is None:
        return []
    if not arr:
        chk.fail(where, "pois", arr, "at least one POI: every Site names one (Req 6.1)")
    used = {line.kind for line in lines}
    out = []
    for i, item in enumerate(arr):
        p = f"pois[{i}]."
        t = chk.table(item, where, f"pois[{i}]", '{ name = "camp fire", purpose = "Light_Spot", at = "fire_ring" }')
        if t is None:
            continue
        chk.keys(t, where, ("name", "purpose", "at"), required=("name", "purpose", "at"), prefix=p)
        name = chk.text(t, "name", where, required=False, prefix=p) if "name" in t else ""
        purpose, at = t.get("purpose"), t.get("at")
        ok = bool(name)
        if purpose is not None and purpose not in POI_PURPOSES:
            chk.fail(where, p + "purpose", purpose, _one_of(POI_PURPOSES))
            ok = False
        if at is not None and at not in used and at not in POI_AT:
            chk.fail(where, p + "at", at, _one_of(POI_AT + tuple(sorted(used))) + " (a Structure in this recipe)")
            ok = False
        elif purpose == "interior" and at is not None and not (at in structures and structures[at].enterable):
            chk.fail(where, p + "at", at, "an Enterable Structure: an interior is walked into")
            ok = False
        if ok and purpose is not None and at is not None:
            out.append(SitePOI(name, purpose, at))
    return out


def _recipe(chk: _Checker, name: str, raw: Any, structures: Mapping[str, Structure]) -> Optional[SiteRecipe]:
    where = f"kinds.{name}"
    tbl = chk.table(raw, "kinds", name, '{ arrangement = "ring", structures = [...], ground = {...}, pois = [...] }')
    if tbl is None:
        return None
    if not _NAME.fullmatch(name):
        _ident(chk, name, "kinds", name)
    chk.keys(tbl, where, ("arrangement", "structures", "ground", "likes", "pois"),
             required=("arrangement", "structures", "ground", "pois"))
    arrangement = tbl.get("arrangement")
    if arrangement is not None and arrangement not in ARRANGEMENTS:
        chk.fail(where, "arrangement", arrangement, _one_of(ARRANGEMENTS))
        arrangement = None
    lines = _lines(chk, tbl.get("structures", []), where, arrangement or "lone", structures)
    ground = _ground(chk, tbl["ground"], where) if "ground" in tbl else None
    likes = _likes(chk, tbl["likes"], where) if "likes" in tbl else {}
    pois = _pois(chk, tbl.get("pois", []), where, lines, structures)
    if arrangement is None or ground is None:
        return None
    return SiteRecipe(name, arrangement, tuple(lines), ground, likes, tuple(pois))


def _inhabitant(chk: _Checker, name: str, raw: Any, structures: Mapping[str, Structure],
                kinds: Sequence[str]) -> Optional[Inhabitant]:
    where = f"inhabitants.{name}"
    tbl = chk.table(raw, "inhabitants", name, '{ materials = "human", weights = { camp = 2 } }')
    if tbl is None:
        return None
    if not _NAME.fullmatch(name):
        _ident(chk, name, "inhabitants", name)
    chk.keys(tbl, where, ("materials", "variants", "swap", "weights"), required=("materials", "weights"))
    materials = _ident(chk, tbl["materials"], where, "materials") if "materials" in tbl else ""
    maps: Dict[str, Dict[str, str]] = {}
    for fld in ("variants", "swap"):
        out: Dict[str, str] = {}
        t = chk.table(tbl[fld], where, fld, "{ tent = \"hide\" }") if fld in tbl else {}
        for k, v in (t or {}).items():
            if k not in structures:
                chk.fail(where, f"{fld}.{k}", "an unknown Structure", _one_of(sorted(structures)), raw=True)
                continue
            if fld == "swap":
                if v not in structures:
                    chk.fail(where, f"swap.{k}", v, _one_of(sorted(structures)))
                    continue
                out[k] = v
            else:
                got = _ident(chk, v, where, f"variants.{k}")
                if got:
                    out[k] = got
        maps[fld] = out
    weights = _kind_weights(chk, tbl["weights"], where, kinds) if "weights" in tbl else {}
    if not materials:
        return None
    return Inhabitant(name, materials, maps["variants"], maps["swap"], weights)


def _biome(chk: _Checker, name: str, raw: Any, inhabitants: Sequence[str], kinds: Sequence[str]) -> Optional[Biome]:
    where = f"biomes.{name}"
    tbl = chk.table(raw, "biomes", name, '{ density = [0.8, 2], inhabitants = { human = 1 }, weights = {...} }')
    if tbl is None:
        return None
    chk.keys(tbl, where, ("density", "inhabitants", "weights"), required=("density", "inhabitants"))
    density = tbl.get("density")
    band = None
    if density is not None:
        if (isinstance(density, list) and len(density) == 2 and all(_is_number(x) for x in density)
                and 0 <= density[0] <= density[1] <= 100):
            band = (float(density[0]), float(density[1]))
        else:
            chk.fail(where, "density", density, "[low, high] Sites per 1e6 u^2, from 0 to 100")
    mix: Dict[str, float] = {}
    t = chk.table(tbl["inhabitants"], where, "inhabitants", "{ human = 4, orc = 1 }") if "inhabitants" in tbl else None
    for k, v in (t or {}).items():
        if k not in inhabitants:
            chk.fail(where, f"inhabitants.{k}", "an unknown Inhabitant", _one_of(sorted(inhabitants)), raw=True)
            continue
        if not _is_number(v) or v < 0:
            chk.fail(where, f"inhabitants.{k}", v, "a number from 0 up")
            continue
        mix[k] = float(v)
    if t is not None and not any(mix.values()):
        chk.fail(where, "inhabitants", t, "at least one Inhabitant with a weight above 0")
    weights = _kind_weights(chk, tbl["weights"], where, kinds) if "weights" in tbl else {}
    if band is None or not any(mix.values()):
        return None
    return Biome(name, band, mix, weights)


def load_sites(path=SITES_DIR, biomes: Optional[Sequence[str]] = None) -> SiteRules:
    """Load and check ``sites.toml``, ``inhabitants.toml`` and ``biomes.toml`` from ``path`` (a
    folder); raises ``RuleSetError`` with every failure of all three. ``biomes`` is the biome
    names that need an entry (default: every biome in ``styles/biomes.json``)."""
    path = Path(path)
    s_chk, i_chk, b_chk = _Checker(SITES_FILE), _Checker(INHABITANTS_FILE), _Checker(BIOMES_FILE)
    checkers = (s_chk, i_chk, b_chk)
    raw = {c.file: _read_toml(path / c.file, c) for c in checkers}

    def raise_all() -> None:
        errors: List[CheckError] = [e for c in checkers for e in c.errors]
        if errors:
            raise RuleSetError(errors)
    raise_all()

    # sites.toml
    data = raw[SITES_FILE]
    s_chk.keys(data, "top level", ("structures", "kinds"), required=("structures", "kinds"))
    s_table = _named_table(s_chk, data, "structures", "[structures.<name>]")
    k_table = _named_table(s_chk, data, "kinds", "[kinds.<name>]")
    structures = {}
    for name, body in s_table.items():
        got = _structure(s_chk, name, body)
        if got is not None:
            structures[name] = got
    # A bad Structure's own error names it: lines naming it shouldn't fail twice.
    named_structures = {n: structures.get(n) or Structure(n, 1.0, 1.0, True) for n in s_table if n in STRUCTURE_KINDS}
    kinds = {}
    for name, body in k_table.items():
        got = _recipe(s_chk, name, body, named_structures)
        if got is not None:
            kinds[name] = got
    for name in SITE_KINDS:
        if name not in k_table:
            s_chk.fail("kinds", name, "nothing", "a recipe for every Site kind (" + ", ".join(SITE_KINDS) + ")",
                       raw=True)
    kind_names = tuple(k_table)

    # inhabitants.toml
    data = raw[INHABITANTS_FILE]
    i_chk.keys(data, "top level", ("inhabitants",), required=("inhabitants",))
    w_table = _named_table(i_chk, data, "inhabitants", "[inhabitants.<name>]")
    who_names = tuple(w_table)
    inhabitants = {}
    for name, body in w_table.items():
        got = _inhabitant(i_chk, name, body, named_structures, kind_names)
        if got is not None:
            inhabitants[name] = got
    if not who_names and isinstance(data.get("inhabitants"), dict):
        i_chk.fail("top level", "inhabitants", "nothing", "at least one Inhabitant", raw=True)
    # A swap must keep every interior an interior: the gate checks it walks in (Req 2.1).
    for who in inhabitants.values():
        for recipe in kinds.values():
            for poi in recipe.pois:
                if poi.purpose != "interior" or poi.at not in who.swap:
                    continue
                to = who.swap[poi.at]
                if to in structures and not structures[to].enterable:
                    i_chk.fail(f"inhabitants.{who.name}", f"swap.{poi.at}", to,
                               f"an Enterable Structure: kinds.{recipe.kind} has an interior in its {poi.at}")

    # biomes.toml
    data = raw[BIOMES_FILE]
    b_chk.keys(data, "top level", ("biomes",), required=("biomes",))
    need = tuple(biome_names()) if biomes is None else tuple(biomes)
    out_biomes = {}
    table = _named_table(b_chk, data, "biomes", "[biomes.<name>]")
    for name, body in table.items():
        if name not in need:
            b_chk.fail("biomes", name, "an unknown biome", _one_of(need), raw=True)
        got = _biome(b_chk, name, body, who_names, kind_names)
        if got is not None:
            out_biomes[name] = got
    for name in need:
        if name not in table:
            b_chk.fail("biomes", name, "nothing", "an entry for every biome in styles/biomes.json", raw=True)

    raise_all()
    return SiteRules(structures, kinds, inhabitants, out_biomes)


__all__ = ["ARRANGEMENTS", "Biome", "CENTRE", "DEFAULT_DENSITY", "DENSITIES", "ENTRANCE", "FACES", "Ground",
           "Inhabitant", "LIKES", "Line", "POI_PURPOSES", "SITES_DIR", "SITE_KINDS", "STRUCTURE_KINDS",
           "SitePOI", "SiteRecipe", "SiteRules", "Structure", "chances", "combine_weights", "load_sites"]
