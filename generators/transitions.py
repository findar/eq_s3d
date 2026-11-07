"""What stands in a corridor between two rooms' wall styles (room layouts, Requirement 14).

Weights in ``rules/rooms/transitions.toml`` choose a form for each corridor, by its pair of styles
and each end room's type or kind: **none**, a **seam** where the look changes at a line, a **frame**
of the finer style with a Door_Spot for the SQL export, or a **breach** broken into the finer room.
A corridor draws from its own stream, so one corridor's choice can't move another's. A form that
can't stand gives way to a plainer one and says so in ``layout.transitions``: a build never fails
for a Transition.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .geometry import SEAM_END, MeshBuilder, bridge_layout
from .routing import corridor_route
from .semantics import ROOM_TYPES, body_height
from .topology.graph import ROOM_KINDS
from .topology.ruleset import _Checker, _is_number, _one_of, _read_toml
from .zone_spec import CorridorSpec, Transition, ZoneSpec

REPO_ROOT = Path(__file__).resolve().parent.parent
TRANSITIONS_FILE = REPO_ROOT / "rules" / "rooms" / "transitions.toml"
WALLS_DIR = REPO_ROOT / "rules" / "walls"

NONE, SEAM, FRAME, BREACH = "none", "seam", "frame", "breach"
FORMS: Tuple[str, ...] = (NONE, SEAM, FRAME, BREACH)
SAME = "same"

# All in body heights.
CLEAR_H = 2.0           # what a frame or breach must leave clear, as the gate asks
HEAD_H = 2.0
FRAME_JAMB_H = 0.25     # how far a jamb stands in from its wall
FRAME_LINTEL_H = (0.25, 0.5)    # how far a lintel drops from the ceiling: at least, at most
FRAME_DEPTH_H = 0.25    # how far either stands along the corridor, each side of the line
BREACH_JAMB_H = 0.5
BREACH_DEPTH_H = 0.3
LEAST_HEAD = 8.0        # the gate's least headroom in u, whatever the race
HEAD_SPARE = 1.0        # a lintel leaves this much more than the gate asks (u)
CLEAR_OF_END = 3.0      # a corridor's end can stand this far into its room, so a line keeps past that (u)


@dataclass(frozen=True)
class TransitionRules:
    pairs: Mapping[str, Mapping[str, float]]
    types: Mapping[str, Mapping[str, float]]
    kinds: Mapping[str, Mapping[str, float]]

    def pair(self, a: str, b: str) -> Mapping[str, float]:
        if a == b:
            return self.pairs[SAME]
        return self.pairs.get(f"{a}_{b}") or self.pairs[f"{b}_{a}"]

    def weights(self, a: str, b: str, ends: Sequence[Tuple[str, str]]) -> Dict[str, float]:
        """Each form's weight: the pair's, times each end room's type table, else its kind's."""
        pair = self.pair(a, b)
        out = {form: float(pair.get(form, 0.0)) for form in FORMS}
        for semantic_type, kind in ends:
            table = self.types.get(semantic_type) or self.kinds.get(kind) or {}
            for form, k in table.items():
                out[form] *= k
        return out


def _forms(chk: _Checker, raw, where: str) -> Dict[str, float]:
    tbl = chk.table(raw, "top level", where, "a table with forms = { ... }")
    if tbl is None:
        return {}
    chk.keys(tbl, where, ("forms",), required=("forms",))
    forms = tbl.get("forms", {})
    out: Dict[str, float] = {}
    if not isinstance(forms, dict):
        chk.fail(where, "forms", forms, "a table of form = weight")
        return out
    for form, weight in forms.items():
        if form not in FORMS:
            chk.fail(where, f"forms.{form}", "an unknown form", _one_of(FORMS), raw=True)
        elif not _is_number(weight) or weight < 0:
            chk.fail(where, f"forms.{form}", weight, "a number, 0 or more")
        else:
            out[form] = float(weight)
    return out


def _section(chk: _Checker, data, section: str, known: Sequence[str]) -> Dict[str, Dict[str, float]]:
    tbl = chk.table(data.get(section, {}), "top level", section, f"[{section}.<name>]") or {}
    out = {}
    for name, body in tbl.items():
        if name not in known:
            chk.fail(section, name, "an unknown name", _one_of(known), raw=True)
        out[name] = _forms(chk, body, f"{section}.{name}")
    return out


def load_transitions(path=TRANSITIONS_FILE, walls_dir=WALLS_DIR) -> TransitionRules:
    """Load and check the weights; raises ``RuleSetError`` with every failure. Every two wall
    styles need a pair, written either way round, and same-style corridors need ``same``."""
    path = Path(path)
    chk = _Checker(path.name)
    data = _read_toml(path, chk)
    chk.raise_if_failed()
    chk.keys(data, "top level", ("pairs", "types", "kinds"), required=("pairs",))
    styles = sorted(p.stem for p in Path(walls_dir).glob("*.toml"))
    names = [SAME] + [f"{a}_{b}" for a in styles for b in styles if a != b]
    pairs = _section(chk, data, "pairs", names)
    if SAME not in pairs:
        chk.fail("pairs", SAME, "nothing", "[pairs.same]", raw=True)
    for i, a in enumerate(styles):
        for b in styles[i + 1:]:
            if f"{a}_{b}" not in pairs and f"{b}_{a}" not in pairs:
                chk.fail("pairs", f"{a}_{b}", "nothing", "a pair for every two wall styles", raw=True)
    types = _section(chk, data, "types", sorted(ROOM_TYPES))
    kinds = _section(chk, data, "kinds", ROOM_KINDS)
    chk.raise_if_failed()
    return TransitionRules(pairs, types, kinds)


@dataclass(frozen=True)
class _Line:
    """A place across a corridor."""
    x: float
    y: float
    z: float
    along_x: bool
    grade: float = 0.0      # the floor's rise per u along the corridor there


def _on_leg(ends, z0: float, z1: float, along_x: bool, t: float) -> _Line:
    (x0, y0), (x1, y1) = ends
    grade = abs(z1 - z0) / max(_span(ends), 1e-9)
    x, y = (x0 + (x1 - x0) * t, y0) if along_x else (x0, y0 + (y1 - y0) * t)   # a leg runs on its first end's line
    return _Line(x, y, z0 + (z1 - z0) * t, along_x, grade)


def _legs(cor: CorridorSpec, rooms):
    """Each built leg, in order: (ends, z at each end, runs along X, can it take a Seam)."""
    route = corridor_route(cor, rooms)
    waypoints, axes = list(route.waypoints), list(route.axes)
    zs, carry = MeshBuilder._waypoint_zs(waypoints, None if route.carry < 0 else route.carry,
                                         cor.from_z, cor.to_z)
    bridge = bridge_layout(cor, rooms) if cor.bridge else None
    out = []
    for k in range(len(waypoints) - 1):
        ends = MeshBuilder._leg_ends(waypoints, k, cor.width / 2, zs)
        if ends is None:
            continue
        flight = cor.steps != 0 and k == carry
        out.append((ends, zs[k], zs[k + 1], axes[k], not flight and (bridge is None or k != bridge.leg)))
    return out


def _span(ends) -> float:
    (x0, y0), (x1, y1) = ends
    return abs(x1 - x0) + abs(y1 - y0)


def _middle_line(legs, depth: float, rng: random.Random) -> Optional[_Line]:
    """Somewhere about the middle of the longest leg with room: a level one if there is one."""
    inset = SEAM_END + depth + CLEAR_OF_END
    room = 2 * inset
    level = [g for g in legs if g[4] and _span(g[0]) >= room and abs(g[1] - g[2]) < 0.01]
    any_leg = level or [g for g in legs if g[4] and _span(g[0]) >= room]
    if not any_leg:
        return None
    ends, z0, z1, along_x, _ = max(any_leg, key=lambda g: _span(g[0]))
    least = inset / _span(ends)
    return _on_leg(ends, z0, z1, along_x, min(max(rng.uniform(0.35, 0.65), least), 1.0 - least))


def _door_line(legs, at_from: bool, depth: float) -> Optional[_Line]:
    """Just inside the corridor from one room's door, or None if that end's leg is too short."""
    if not legs:
        return None
    ends, z0, z1, along_x, _ = legs[0] if at_from else legs[-1]
    span = _span(ends)
    inset = SEAM_END + depth + CLEAR_OF_END
    if span < 2 * inset:
        return None
    return _on_leg(ends, z0, z1, along_x, inset / span if at_from else 1.0 - inset / span)


def _fits_width(cor: CorridorSpec, jamb: float, h: float) -> bool:
    return cor.width - 2 * jamb >= CLEAR_H * h


def _lintel(cor: CorridorSpec, h: float, rise: float = 0.0) -> Optional[float]:
    """As deep as the corridor's head can spare, or None if that's too little to read as one.
    ``rise`` is how far the floor climbs under it, on a ramp."""
    least, most = FRAME_LINTEL_H[0] * h, FRAME_LINTEL_H[1] * h
    spare = cor.height - max(HEAD_H * h, LEAST_HEAD) - HEAD_SPARE - rise
    return min(most, spare) if spare >= least else None


def _choose(weights: Mapping[str, float], rng: random.Random) -> str:
    forms = [f for f in FORMS if weights[f] > 0]
    return rng.choices(forms, [weights[f] for f in forms])[0] if forms else NONE


def draw_transition(cor: CorridorSpec, rooms, from_style, to_style, ends: Sequence[Tuple[str, str]],
                    rules: TransitionRules, seed: int, h: float) -> Dict[str, object]:
    """Choose this corridor's form and set ``cor.transition``. Returns its record, with ``asked``
    when the form it stands as isn't the one the weights chose."""
    rng = random.Random(f"{seed}:{cor.id}:transition")
    asked = _choose(rules.weights(from_style.name, to_style.name, ends), rng)
    form, line = asked, None
    legs = _legs(cor, rooms)
    plain = cor.steps == 0 and not cor.bridge
    differ = from_style.name != to_style.name
    # A form that can't stand here gives way to the next one that can.
    lintel = _lintel(cor, h)
    if form == BREACH and not _fits_width(cor, BREACH_JAMB_H * h, h):
        form = SEAM if differ else NONE
    if form == FRAME and (lintel is None or not _fits_width(cor, FRAME_JAMB_H * h, h)):
        form = SEAM if differ else NONE
    if form == SEAM and not plain:
        form = NONE                         # a stair or bridge has no Seam

    depth = {FRAME: FRAME_DEPTH_H * h, BREACH: BREACH_DEPTH_H * h}.get(form, 0.5)
    finer_is_from = from_style.finish >= to_style.finish
    if form == BREACH:
        line = _door_line(legs, finer_is_from, depth)
    elif form == FRAME and (not plain or not differ):
        line = _door_line(legs, True, depth) or _door_line(legs, False, depth)
    elif form in (SEAM, FRAME):
        line = _middle_line(legs, depth, rng) or _door_line(legs, finer_is_from, depth)
    if form != NONE and line is None:
        form = NONE
    # On a ramp the floor climbs under a lintel, so it has less to spare there.
    if form == FRAME:
        lintel = _lintel(cor, h, line.grade * depth)
        if lintel is None:
            form = SEAM if differ and plain else NONE
            line = line if form == SEAM else None

    record: Dict[str, object] = {"corridor": cor.id, "form": form}
    if asked != form:
        record["asked"] = asked
    if form == NONE:
        return record
    cor.transition = Transition(form, round(line.x, 3), round(line.y, 3), round(line.z, 3), line.along_x, depth)
    if form == FRAME:
        cor.transition.jamb, cor.transition.lintel = FRAME_JAMB_H * h, lintel
    elif form == BREACH:
        cor.transition.jamb = BREACH_JAMB_H * h
    record.update(x=cor.transition.x, y=cor.transition.y, z=cor.transition.z, along_x=line.along_x)
    return record


def _door_spot(cor: CorridorSpec, finishes) -> Dict[str, object]:
    t = cor.transition
    return {"x": t.x, "y": t.y, "z": t.z, "facing": "E" if t.along_x else "N",
            "width": round(cor.width - 2 * t.jamb, 3), "height": round(cor.height - t.lintel, 3),
            "finishes": finishes}


def draw_transitions(spec: ZoneSpec, styles: Mapping[str, object], seed: int) -> List[Tuple[object, object]]:
    """Each corridor's form, look and break: returns (holder, style) for everything that has to
    take a style's look. Flat and ramp corridors take a style's break; stairs and bridges stay as
    built. A corridor that changes at a line is its from_room's up to it and its to_room's past it;
    any other between two styles is the rougher room's."""
    rules = load_transitions()
    h = body_height(spec.dungeon_race)
    rooms = {r.id: r for r in spec.rooms}
    records = spec.layout["rooms"]
    holders: List[Tuple[object, object]] = []
    written: List[Dict[str, object]] = []
    for cor in spec.corridors:
        cor.transition = None
        a, b = styles.get(cor.from_room), styles.get(cor.to_room)
        ends_styles = [s for s in (a, b) if s is not None] or list(styles.values())
        style = min(ends_styles, key=lambda s: s.finish)
        plain = cor.steps == 0 and not cor.bridge
        if a is not None and b is not None:
            ends = [(rooms[i].semantic_type, records.get(i, {}).get("kind", rooms[i].kind))
                    for i in (cor.from_room, cor.to_room)]
            written.append(draw_transition(cor, rooms, a, b, ends, rules, seed, h))
        t = cor.transition
        if t is not None and t.form in (SEAM, FRAME) and plain and a.name != b.name:
            style = a
            t.floor_material, t.wall_material, t.ceiling_material = (cor.floor_material, cor.wall_material,
                                                                     cor.ceiling_material)
            t.rough = b.corridor_break
            holders.append((t, b))
        cor.rough = style.corridor_break if plain else 0.0
        holders.append((cor, style))
    spec.layout["transitions"] = written
    return holders


def finish_transitions(spec: ZoneSpec, styles: Mapping[str, object]) -> None:
    """Once every surface has its look: what each frame and breach is made of, and the Door_Spots."""
    rooms = {r.id: r for r in spec.rooms}
    records = spec.layout["rooms"]
    written = {w["corridor"]: w for w in spec.layout["transitions"]}
    for cor in spec.corridors:
        t = cor.transition
        if t is None or t.form == SEAM:
            continue
        if t.form == BREACH:
            t.material = cor.wall_material
            continue
        finer = max((cor.from_room, cor.to_room), key=lambda i: styles[i].finish)
        t.material = rooms[finer].wall_material
        finishes = [records.get(i, {}).get("scales", {}).get("finish") for i in (cor.from_room, cor.to_room)]
        written[cor.id]["door_spot"] = _door_spot(cor, finishes)


__all__ = ["BREACH", "FORMS", "FRAME", "NONE", "SAME", "SEAM", "TRANSITIONS_FILE", "TransitionRules",
           "draw_transition", "draw_transitions", "finish_transitions", "load_transitions"]
