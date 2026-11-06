"""Wall styles (roadmap step 8): how a zone's rooms are drawn, as checked TOML data.

Each file in ``rules/walls/`` is one style. It says how a room's Box is divided
into Cells, how much floor stays, which shapes each room kind may take, how far
floors and ceilings move, and what the walls should look like. Lengths are in H,
the race's body height, so an ogre's cave has bigger bends for its bigger body.

Failures are collected and named by file, table and field, in the same form as
the topology rules (``generators/topology/ruleset.py``). These files will one day
be written by a prompt; a wrong value must say what was expected. The guide is
``docs/TOPOLOGY_RULES.md``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple, Union

from .geometry import _bridge_slots, room_doors
from .outline import (COMPLEXES, SHAPES as OUTLINE_SHAPES, Door, Outline, Rect, add_relief,
                      draw_outline)
from .semantics import body_height
from .topology.graph import ROOM_KINDS
from .topology.ruleset import (RuleSetError, _Checker, _MISSING, _is_number, _one_of, _read_toml,
                               _type_name, load_theme_map)
from .textures.recipes import resolve as resolve_recipe
from .zone_spec import ZoneSpec

WALLS_DIR = Path(__file__).resolve().parent.parent / "rules" / "walls"
RECT = "rect"
#: A shape a style may name: an Outline's, or the plain Box.
STYLE_SHAPES: Tuple[str, ...] = (RECT,) + OUTLINE_SHAPES
DEFAULT_KIND = "default"
#: What a style asks the texture layer for: the theme's own look, or rock.
LOOKS: Tuple[str, ...] = ("theme", "rock")
SURFACES: Tuple[str, ...] = ("wall", "floor", "ceiling")
#: The texture families that read as laid stone or carpentry, not rock.
MASONRY: Tuple[str, ...] = ("dressed_stone", "brick", "flagstone", "cobble", "planks", "plaster")
Band = Tuple[float, float]
MIN_HEAD_H = 2.0        # the least headroom, in body heights
MIN_HEAD = 8.0          # and in u: the player is 6 u tall
RELIEF_SCALE_H = 5.0    # how far apart a floor's or ceiling's rises and falls are, in H


@dataclass(frozen=True)
class WallStyle:
    name: str
    description: str
    complex: str
    cell_size_h: float                  # 0 for a complex with no Cell size
    wobble_h: float                     # how far a wall vertex wanders inward
    fill: Band                          # floor over Box (a facet room ignores it)
    floor_relief_h: Band                # how far a floor rises
    ceiling_spread: Band                # how far a ceiling falls, over the room's height
    corridor_break: float               # how far a corridor's walls come in, over its width
    shapes: Mapping[str, Mapping[str, float]]   # kind -> shape -> weight
    look: Mapping[str, str]             # surface -> look

    def pick_shape(self, kind: str, rng: random.Random) -> str:
        """A shape for a room of this kind, by the style's weights."""
        table = self.shapes.get(kind, self.shapes[DEFAULT_KIND])
        names = sorted(table)
        return rng.choices(names, weights=[table[n] for n in names])[0]

    def draw(self, box: Rect, doors: List[Door], slots: List[Rect], shape: str, body_height: float,
             rng: random.Random, room_height: float = 0.0) -> Optional[Outline]:
        """The room's Outline, or None for a plain Box. With a ``room_height`` its floor
        and ceiling move as the style says."""
        if shape == RECT:
            return None
        outline = draw_outline(box, doors, slots, complex=self.complex,
                               cell_size=self.cell_size_h * body_height, shape=shape,
                               fill=rng.uniform(*self.fill), rng=rng,
                               wobble=self.wobble_h * body_height)
        if room_height > 0:
            add_relief(outline, room_height,
                       floor_rise=rng.uniform(*self.floor_relief_h) * body_height,
                       ceiling_fall=rng.uniform(*self.ceiling_spread) * room_height,
                       min_head=max(MIN_HEAD_H * body_height, MIN_HEAD),
                       scale=RELIEF_SCALE_H * body_height, rng=rng)
        return outline


def _number(chk: _Checker, tbl: Mapping, key: str, where: str, lo: float, hi: float,
            default: Optional[float] = None) -> float:
    v = tbl.get(key, _MISSING)
    if v is _MISSING:
        if default is None:
            chk.fail(where, key, v, f"a number from {lo} to {hi}")
            return 0.0
        return default
    if not _is_number(v) or not lo <= v <= hi:
        chk.fail(where, key, v if _is_number(v) else _type_name(v), f"a number from {lo} to {hi}",
                 raw=not _is_number(v))
        return default if default is not None else 0.0
    return float(v)


def _band(chk: _Checker, tbl: Mapping, key: str, where: str, lo: float, hi: float) -> Band:
    v = tbl.get(key, _MISSING)
    ok = (isinstance(v, list) and len(v) == 2 and all(_is_number(x) for x in v)
          and lo <= v[0] <= v[1] <= hi)
    if not ok:
        chk.fail(where, key, v, f"[low, high], low <= high, both from {lo} to {hi}")
        return (lo, lo)
    return (float(v[0]), float(v[1]))


def _shapes(chk: _Checker, raw, kinds: Sequence[str]) -> Dict[str, Dict[str, float]]:
    tbl = chk.table(raw, "top level", "shapes", "[shapes] with default = { blob = 1 }") \
        if raw is not _MISSING else None
    if raw is _MISSING:
        chk.fail("top level", "shapes", raw, "a table of room kind -> shape weights")
    if tbl is None:
        return {}
    out: Dict[str, Dict[str, float]] = {}
    allowed = tuple(kinds) + (DEFAULT_KIND,)
    chk.keys(tbl, "shapes", allowed, required=(DEFAULT_KIND,))
    for kind, weights in tbl.items():
        if kind not in allowed:
            continue
        w = chk.table(weights, "shapes", kind, "{ blob = 2, long = 1 }")
        if w is None:
            continue
        if not w:
            chk.fail("shapes", kind, "an empty table", "at least one shape", raw=True)
        row: Dict[str, float] = {}
        for shape, weight in w.items():
            if shape not in STYLE_SHAPES:
                chk.fail("shapes", f"{kind}.{shape}", "an unknown shape", _one_of(STYLE_SHAPES), raw=True)
            elif not _is_number(weight) or weight <= 0:
                chk.fail("shapes", f"{kind}.{shape}", weight, "a weight above 0")
            else:
                row[shape] = float(weight)
        out[kind] = row
    return out


def load_style(path: Union[str, Path]) -> WallStyle:
    """Load and check one style; raises ``RuleSetError`` with every failure."""
    path = Path(path)
    chk = _Checker(path.name)
    data = _read_toml(path, chk)
    chk.raise_if_failed()
    chk.keys(data, "top level", ("style", "shapes", "look"), required=("style", "shapes", "look"))
    st = chk.table(data.get("style", {}), "top level", "style", "[style] with name, complex") or {}
    chk.keys(st, "style", ("name", "description", "complex", "cell_size_h", "wobble_h", "fill",
                           "floor_relief_h", "ceiling_spread", "corridor_break"),
             required=("name", "description", "complex", "floor_relief_h", "ceiling_spread",
                       "corridor_break"))
    name = chk.text(st, "name", "style", required=False)
    if name and name != path.stem:
        chk.fail("style", "name", name, f'"{path.stem}" (the file\'s name, so a theme finds it)')
    desc = chk.text(st, "description", "style", required=False)
    complex_ = st.get("complex", _MISSING)
    if complex_ is not _MISSING and complex_ not in COMPLEXES:
        chk.fail("style", "complex", complex_, _one_of(COMPLEXES))
    facet = complex_ == "facet"
    if facet:
        for key in ("cell_size_h", "fill"):
            if key in st:
                chk.fail("style", key, st[key], "nothing: a facet room is its corner cuts")
        cell, fill = 0.0, (0.0, 0.0)
    else:
        cell = _number(chk, st, "cell_size_h", "style", 1.0, 20.0)
        fill = _band(chk, st, "fill", "style", 0.65, 1.0)
    wobble = _number(chk, st, "wobble_h", "style", 0.0, 5.0, default=0.0)
    relief = _band(chk, st, "floor_relief_h", "style", 0.0, 2.0)
    spread = _band(chk, st, "ceiling_spread", "style", 0.0, 0.75)
    broken = _number(chk, st, "corridor_break", "style", 0.0, 0.3)
    shapes = _shapes(chk, data.get("shapes", _MISSING), ROOM_KINDS)
    lk = chk.table(data.get("look", {}), "top level", "look", "[look] with wall, floor, ceiling") or {}
    chk.keys(lk, "look", SURFACES, required=SURFACES)
    for surface, value in lk.items():
        if surface in SURFACES and value not in LOOKS:
            chk.fail("look", surface, value, _one_of(LOOKS))
    chk.raise_if_failed()
    return WallStyle(name, desc, complex_, cell, wobble, fill, relief, spread, broken, shapes, dict(lk))


def load_styles(folder: Union[str, Path] = WALLS_DIR) -> Dict[str, WallStyle]:
    """Every style in ``folder`` by name; raises with all of their failures."""
    styles: Dict[str, WallStyle] = {}
    errors = []
    for p in sorted(Path(folder).glob("*.toml")):
        try:
            s = load_style(p)
            styles[s.name] = s
        except RuleSetError as exc:
            errors.extend(exc.errors)
    if errors:
        raise RuleSetError(errors)
    return styles


THEMES_FILE = WALLS_DIR.parent / "topology" / "themes.toml"
AUTO = "auto"


def style_for_theme(theme: str) -> WallStyle:
    """The wall style ``themes.toml`` gives a dungeon theme."""
    return load_styles()[load_theme_map(THEMES_FILE).entry_for(theme or None).walls]


def _apply_look(spec: ZoneSpec, style: WallStyle) -> None:
    """Give each surface the look the style asks for. ``rock`` moves masonry onto a
    ``<set>_rock_<surface>`` material with the same colour, so a theme's tint carries
    over; a surface that isn't masonry (a lava forge's basalt, an ice keep's ice) keeps
    its own character. Materials nothing uses any more go, so they aren't packed."""
    holders = list(spec.rooms) + list(spec.corridors)
    for surface in SURFACES:
        if style.look[surface] != "rock":
            continue
        field = f"{surface}_material"
        for old in sorted({getattr(h, field) for h in holders}):
            recipe = resolve_recipe(old)
            if recipe is None or recipe.family not in MASONRY:
                continue
            new = f"{old[: -len(surface) - 1]}_rock_{surface}"
            if new not in spec.materials:
                m = spec.materials[old]
                spec.add_material(new, f"{new}.dds", shader=m.shader, color=m.color,
                                  description=f"rough cave rock {surface}")
            for h in holders:
                if getattr(h, field) == old:
                    setattr(h, field, new)
    used = {getattr(h, f"{s}_material") for h in holders for s in SURFACES}
    for name in [n for n in spec.materials if n not in used]:
        del spec.materials[name]


def apply_walls(spec: ZoneSpec, style: WallStyle, seed: int) -> None:
    """Draw each room's Outline, last, once every door is known. Only ``room.outline``
    and the sidecar record change, so a style can't move a layout. Each room draws from
    its own stream, so one room's shape can't shift another's."""
    height = body_height(spec.dungeon_race)
    records = spec.layout["rooms"]
    for room in spec.rooms:
        rng = random.Random(f"{seed}:{room.id}")
        record = records.get(room.id, {})
        # What the rule asked for: applying a style again chooses afresh.
        shape = record.setdefault("rule_shape", record.get("shape", AUTO))
        if shape == AUTO:
            shape = style.pick_shape(record.get("kind", room.kind), rng)
        (x0, y0, _), (x1, y1, _) = room.bounds
        box = (x0, y0, x1, y1)
        room.outline = style.draw(box, room_doors(room, spec), _bridge_slots(room, spec),
                                  shape, height, rng, room_height=room.height)
        if records:
            record["shape"] = shape
            record["fill"] = 1.0 if room.outline is None else round(room.outline.fill(box), 3)
            record["outline"] = None if room.outline is None else [
                [[round(x, 1), round(y, 1)] for x, y in (room.outline.verts[i] for i in loop)]
                for loop in room.outline.wall_loops()]
    # Flat and ramp corridors take the style's break; stairs and bridges stay as built.
    for cor in spec.corridors:
        cor.rough = style.corridor_break if cor.steps == 0 and not cor.bridge else 0.0
    spec.layout["walls"] = style.name
    _apply_look(spec, style)

