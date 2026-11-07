"""Scales (roadmap step 9): what a room is like, as weights in the rules.

Finish, structure and clutter run from 0 to 10. A source of weights is a Layer: the
default, a race, a theme, an overlay, a room kind or type, a rule's wing, and later a control.
A value's chance is its weight over the sum, and a room's weights are its Layers
multiplied, so an ogre temple is a real blend and not whichever was named last. Layers
that disagree never fail a build: when the product is all zeros, the most specific Layer
with any weight decides.

``rules/rooms/scales.toml`` holds them, checked like the other rule files. The guide is
``docs/TOPOLOGY_RULES.md``.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence, Tuple

from ai.schema import VALID_DUNGEON_RACES, VALID_DUNGEON_THEMES

from .semantics import ROOM_TYPES
from .topology.graph import ROOM_KINDS
from .topology.ruleset import _Checker, _is_number, _one_of, _read_toml, _type_name

SCALES_FILE = Path(__file__).resolve().parent.parent / "rules" / "rooms" / "scales.toml"
FINISH, STRUCTURE, CLUTTER = "finish", "structure", "clutter"
SCALES: Tuple[str, ...] = (FINISH, STRUCTURE, CLUTTER)
VALUES = 11     # 0 to 10
FLAT: Tuple[float, ...] = (1.0,) * VALUES
Weights = Tuple[float, ...]


def peak_weights(peak: float, spread: float) -> Weights:
    """The shorthand: 1 at the peak, falling to 0 just past ``spread`` either side."""
    return tuple(max(0.0, 1.0 - abs(v - peak) / (spread + 1.0)) for v in range(VALUES))


@dataclass(frozen=True)
class Layer:
    """One source of weights. A scale it doesn't name, it leaves alone."""

    weights: Mapping[str, Weights] = field(default_factory=dict)
    overrides: Tuple[str, ...] = ()     # scales that replace every less specific Layer


def combine(scale: str, layers: Sequence[Layer]) -> Weights:
    """A room's weights on one scale, from its Layers, least specific first."""
    product = FLAT
    specific: Optional[Weights] = None
    for layer in layers:
        w = layer.weights.get(scale)
        if w is None:
            continue
        specific = w
        product = w if scale in layer.overrides else tuple(a * b for a, b in zip(product, w))
    if any(product) or specific is None:
        return product
    return specific


@dataclass(frozen=True)
class RoomScales:
    default: Layer
    coherence: Mapping[str, float]
    races: Mapping[str, Layer]
    themes: Mapping[str, Layer]
    overlays: Mapping[str, Layer]
    kinds: Mapping[str, Layer]
    types: Mapping[str, Layer]
    wings: Mapping[str, Layer] = field(default_factory=dict)

    def layers_for(self, race: str = "", theme: str = "", overlay: str = "", kind: str = "",
                   room_type: str = "", wing: str = "") -> Tuple[Layer, ...]:
        """A room's Layers from the rules, least specific first. A name with no table has none."""
        found = (self.races.get(race), self.themes.get(theme), self.overlays.get(overlay),
                 self.kinds.get(kind), self.types.get(room_type), self.wings.get(wing))
        return (self.default,) + tuple(x for x in found if x is not None)


def lean(weights: Weights, neighbours: Sequence[int], coherence: float) -> Weights:
    """``weights`` leaning toward the mean of the values next door. At coherence 0, or
    with none drawn yet, they stand as they are."""
    if not coherence or not neighbours:
        return weights
    mean, sigma = sum(neighbours) / len(neighbours), 10.0 / coherence
    leaned = tuple(w * math.exp(-(((v - mean) / sigma) ** 2) / 2) for v, w in enumerate(weights))
    # So far out that it rounds to nothing: what the room's weights say is all that's left.
    return leaned if any(leaned) else weights


def draw_room_scales(spec, seed: int, overlay: str = "", rules: Optional[RoomScales] = None) -> None:
    """Each room's value on each Scale, into ``layout.rooms.<id>.scales``. Rooms draw from
    the entrance outward, each from its own stream, so this moves nothing about the layout."""
    rules = rules or load_scales()
    records = spec.layout["rooms"]
    coherence = spec.layout.get("coherence") or {}
    next_door: Dict[str, list] = {room.id: [] for room in spec.rooms}
    for cor in spec.corridors:
        if cor.from_room in next_door and cor.to_room in next_door:
            next_door[cor.from_room].append(cor.to_room)
            next_door[cor.to_room].append(cor.from_room)
    drawn: Dict[str, Dict[str, int]] = {}
    for room in sorted(spec.rooms, key=lambda r: r.graph_depth):    # stable: the spec's order within a depth
        record = records.setdefault(room.id, {})
        wing = record.get("wing", "")
        layers = rules.layers_for(spec.dungeon_race, spec.dungeon_theme, overlay, record.get("kind", room.kind),
                                  room.semantic_type, wing)
        values = {}
        for scale in SCALES:
            # A room leans only within its wing: that's what gives a wing its hard edge.
            near = [drawn[n][scale] for n in next_door[room.id]
                    if n in drawn and records.get(n, {}).get("wing", "") == wing]
            weights = lean(combine(scale, layers), near, coherence.get(scale, rules.coherence[scale]))
            rng = random.Random(f"{seed}:{room.id}:{scale}")
            values[scale] = rng.choices(range(VALUES), weights=weights)[0]
        drawn[room.id] = values
        record["scales"] = values


def _weights(chk: _Checker, raw, where: str, fld: str) -> Optional[Tuple[Weights, bool]]:
    """(weights, override) from an array, ``{ peak, spread }`` or ``{ weights }``."""
    override = False
    expected = f"{VALUES} numbers from 0 up, or {{ peak = 5, spread = 2 }}"
    if isinstance(raw, dict):
        chk.keys(raw, where, ("weights", "peak", "spread", "override"), prefix=f"{fld}.")
        override = raw.get("override", False)
        if not isinstance(override, bool):
            chk.fail(where, f"{fld}.override", override, "true or false")
            return None
        if "weights" in raw:
            if "peak" in raw or "spread" in raw:
                chk.fail(where, fld, "both weights and peak", "one or the other", raw=True)
                return None
            raw = raw["weights"]
        else:
            peak, spread = raw.get("peak"), raw.get("spread")
            bad = False
            if not _is_number(peak) or not 0 <= peak <= VALUES - 1:
                chk.fail(where, f"{fld}.peak", peak if peak is not None else "nothing",
                         "a number from 0 to 10", raw=peak is None)
                bad = True
            if not _is_number(spread) or not 0 <= spread <= VALUES - 1:
                chk.fail(where, f"{fld}.spread", spread if spread is not None else "nothing",
                         "a number from 0 to 10", raw=spread is None)
                bad = True
            return None if bad else (peak_weights(float(peak), float(spread)), override)
    if not isinstance(raw, list):
        chk.fail(where, fld, _type_name(raw), expected, raw=True)
        return None
    if len(raw) != VALUES or not all(_is_number(x) and x >= 0 for x in raw):
        chk.fail(where, fld, raw, expected)
        return None
    if not any(raw):
        chk.fail(where, fld, raw, "at least one weight above 0")
        return None
    return tuple(float(x) for x in raw), override


def _layer(chk: _Checker, raw, where: str) -> Layer:
    tbl = chk.table(raw, where.rpartition(".")[0] or "top level", where.rpartition(".")[2],
                    "{ finish = { peak = 5, spread = 2 } }")
    if tbl is None:
        return Layer()
    allowed = SCALES + ("coherence",) if where == "default" else SCALES
    chk.keys(tbl, where, allowed)
    weights, overrides = {}, []
    for scale in SCALES:
        if scale not in tbl:
            continue
        got = _weights(chk, tbl[scale], where, scale)
        if got is not None:
            weights[scale] = got[0]
            if got[1]:
                overrides.append(scale)
    return Layer(weights, tuple(overrides))


def _coherence(chk: _Checker, raw) -> Dict[str, float]:
    tbl = chk.table(raw, "default", "coherence", "{ finish = 4, structure = 3, clutter = 3 }")
    if tbl is None:
        return {}
    chk.keys(tbl, "default", SCALES, required=SCALES, prefix="coherence.")
    out = {}
    for scale in SCALES:
        v = tbl.get(scale)
        if v is None:
            continue
        if not _is_number(v) or not 0 <= v <= 10:
            chk.fail("default", f"coherence.{scale}", v, "a number from 0 to 10")
        else:
            out[scale] = float(v)
    return out


def _named(chk: _Checker, data, section: str, known: Optional[Sequence[str]]) -> Dict[str, Layer]:
    raw = data.get(section, {})
    tbl = chk.table(raw, "top level", section, "[" + section + ".<name>]")
    out = {}
    for name, body in (tbl or {}).items():
        if known is not None and name not in known:
            chk.fail(section, name, "an unknown name", _one_of(known), raw=True)
        out[name] = _layer(chk, body, f"{section}.{name}")
    return out


def load_scales(path=SCALES_FILE) -> RoomScales:
    """Load and check the weights; raises ``RuleSetError`` with every failure."""
    path = Path(path)
    chk = _Checker(path.name)
    data = _read_toml(path, chk)
    chk.raise_if_failed()
    chk.keys(data, "top level", ("default", "races", "themes", "overlays", "kinds", "types", "wings"),
             required=("default",))
    raw_default = data.get("default", {})
    default = _layer(chk, raw_default, "default")
    if isinstance(raw_default, dict):
        for scale in SCALES:
            if scale not in raw_default:
                chk.fail("default", scale, "nothing", "weights: every room starts from the default", raw=True)
        if "coherence" not in raw_default:
            chk.fail("default", "coherence", "nothing", "{ finish = 4, structure = 3, clutter = 3 }", raw=True)
    coherence = _coherence(chk, raw_default.get("coherence", {})) if isinstance(raw_default, dict) else {}
    if default.overrides:
        chk.fail("default", "override", "true", "nothing: the default has no less specific Layer", raw=True)
    races = _named(chk, data, "races", VALID_DUNGEON_RACES)
    themes = _named(chk, data, "themes", VALID_DUNGEON_THEMES)
    overlays = _named(chk, data, "overlays", None)
    kinds = _named(chk, data, "kinds", ROOM_KINDS)
    types = _named(chk, data, "types", sorted(ROOM_TYPES))
    wings = _named(chk, data, "wings", None)
    chk.raise_if_failed()
    return RoomScales(default, coherence, races, themes, overlays, kinds, types, wings)
