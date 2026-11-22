"""What stands in a corridor between two rooms' wall styles (room layouts, Requirement 14).

Weights in ``rules/rooms/transitions.toml`` choose a form for each corridor, by its pair of styles
and each end room's type or kind: **none**, a **seam** where the look changes at a line, a **frame**
of the finer style with a Door_Spot for the SQL export, or a **breach** broken into the finer room.
A corridor draws from its own stream, so one corridor's choice can't move another's. A form that
can't stand gives way to a plainer one and says so in ``layout.transitions``: a build never fails
for a Transition.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .geometry import OPENING_INTO_WALL, SEAM_END, MeshBuilder, bridge_layout, stair_layout
from .routing import (Hold, corridor_route, hold_route, path_zs, route_footprint, route_seed, scaled_tunnel,
                      split_path, strip_corners, wind_leg, wind_route, wind_seed)
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
# Winding (step 23), in u.
PLAYER_HALF_WIDTH = 1.5     # a winding strip keeps this far off anything else (decor.placement's)
WIND_Z_SPARE = 2.0          # things nearer than this above or below a leg count as beside it
ROUTE_MAX_GRADE = 0.5       # a route line's rise over its length between the run-outs (layout's max_grade)


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


def _touches_a_room(cor: CorridorSpec, line: _Line, depth: float, rooms) -> bool:
    """Would a frame's or breach's pieces reach a room? A leg can run along a room's wall,
    and a piece standing in that wall would be part of the room's mesh, loose in it."""
    reach = cor.width / 2 + OPENING_INTO_WALL
    across, along = (line.y, line.x) if line.along_x else (line.x, line.y)
    for room in rooms.values():
        (x0, y0, _), (x1, y1, _) = room.bounds
        a0, a1, c0, c1 = (x0, x1, y0, y1) if line.along_x else (y0, y1, x0, x1)
        if along - depth <= a1 and along + depth >= a0 and across - reach <= c1 and across + reach >= c0:
            return True
    return False


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
    if form in (FRAME, BREACH) and _touches_a_room(cor, line, depth, rooms):
        form = SEAM if differ and plain else NONE
        line = line if form == SEAM else None
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
    tunnels = {}
    holds = {}
    winding = float(getattr(spec, "winding", 1.0))
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
        # The zone's Winding scales the tunnel's wander (winding-control Req 2): None at 0.
        tunnels[cor.id] = scaled_tunnel(getattr(style, "tunnel", None), winding)
        if t is not None and plain:
            # Its route line holds the line straight (winding-control Req 8). Each side winds
            # by its own look: past a line the corridor changes at, the to_room's.
            sides = (a, b) if t.floor_material else (style, style)
            held = scaled_tunnel(next((s.tunnel for s in sides if getattr(s, "tunnel", None)), None), winding)
            if held is not None:
                holds[cor.id] = (held, tuple(getattr(s, "tunnel", None) is not None for s in sides))
        holders.append((cor, style))
    spec.layout["transitions"] = written
    measure_winds(spec, tunnels, holds)
    return holders


# --- Winding (step 23, winding-tunnels Requirement 2) -----------------------------------

_Box = Tuple[float, float, float, float, float, float]      # x0, y0, x1, y1, z0, z1


def _corridor_boxes(cor: CorridorSpec, rooms) -> List[Tuple[int, _Box]]:
    """What a corridor takes up: (leg index or -1, box) for each of its route's legs and bend
    squares, and its stairwell if it has one. Each holds its own floors' heights and the
    headroom over them."""
    route = corridor_route(cor, rooms)
    waypoints = list(route.waypoints)
    zs, _ = MeshBuilder._waypoint_zs(waypoints, None if route.carry < 0 else route.carry,
                                     cor.from_z, cor.to_z)
    rects = route_footprint(route, cor.width / 2)
    n = len(waypoints) - 1
    out: List[Tuple[int, _Box]] = []
    for i, r in enumerate(rects):
        lo, hi = (min(zs[i], zs[i + 1]), max(zs[i], zs[i + 1])) if i < n else (zs[i - n + 1],) * 2
        out.append((i if i < n else -1, (*r, lo, hi + cor.height)))
    stair = stair_layout(cor, rooms)
    if stair is not None and stair.stairwell is not None:
        lo, hi = sorted((cor.from_z, cor.to_z))
        out.append((-1, (*stair.stairwell, lo, hi + cor.height)))
    return out


def _held_leg(cor: CorridorSpec, waypoints, zs) -> Optional[int]:
    """The leg a Transition's line stands on, as the mesh splits it (``_seam_leg``)."""
    t = cor.transition
    if t is None:
        return None
    return MeshBuilder._seam_leg(waypoints, ((t.x, t.y), None, None), cor.width / 2, zs)


def leg_clearance(ends, along_x: bool, hw: float, z0: float, z1: float, height: float, run_in: float,
                  others: Sequence[_Box]) -> float:
    """How far a leg's strip can move sideways, on either side, before it comes within the
    player's half-width of one of ``others``: over the part of the leg that may wind (all but
    ``run_in`` at each end, give or take a mitre's ``hw`` and the player), counting only what
    overlaps the leg in Z. 0 when something stands in the strip there; inf when nothing is
    beside it."""
    ax = 0 if along_x else 1
    a0, a1 = sorted((ends[0][ax], ends[1][ax]))
    reach = hw + PLAYER_HALF_WIDTH
    m0, m1 = a0 + run_in - reach, a1 - run_in + reach
    cross = ends[0][1 - ax]
    lo, hi = min(z0, z1) - WIND_Z_SPARE, max(z0, z1) + height + WIND_Z_SPARE
    if m1 <= m0:
        return 0.0
    room = float("inf")
    eps = 1e-6
    for x0, y0, x1, y1, bz0, bz1 in others:
        if bz1 <= lo or bz0 >= hi:
            continue                        # another Level's, over or under the leg
        o0, o1, c0, c1 = (x0, x1, y0, y1) if along_x else (y0, y1, x0, x1)
        if o1 <= m0 + eps or o0 >= m1 - eps:
            continue
        if c0 >= cross + hw - eps:
            room = min(room, c0 - (cross + hw))
        elif c1 <= cross - hw + eps:
            room = min(room, (cross - hw) - c1)
        else:
            return 0.0
    return max(room - PLAYER_HALF_WIDTH, 0.0)


def measure_winds(spec: ZoneSpec, tunnels: Mapping[str, object],
                  holds: Optional[Mapping[str, object]] = None) -> None:
    """Set each corridor's ``wind``: per leg of its route, how far that plain leg of a rough
    corridor may stray (``min(clearance, wander × span)``, floored to 0.01 u), 0 for a leg that
    stays straight. ``tunnels`` is corridor id -> its style's ``TunnelRules`` (None: no
    winding). Only reads the finished spec: routes, footprints, conflicts and Levels stay.

    A leg winds when it is plain (a corridor with a ``rough`` break, so no stair or bridge),
    has a part that may wind, and holds no Transition line; past a Seam it stays straight
    too. ``holds`` (corridor id -> (rules, (may it wander before the line, after it))) names
    the corridors holding a Transition line: ``measure_routes`` gives them a route line held
    straight there, winding by whichever of their two looks has a tunnel."""
    for cor in spec.corridors:
        cor.wind = []
        cor.path = []
    if not holds and not any(tunnels.get(cor.id) is not None and cor.rough > 0 for cor in spec.corridors):
        return
    rooms = {r.id: r for r in spec.rooms}
    boxes = {cor.id: _corridor_boxes(cor, rooms) for cor in spec.corridors}
    room_boxes = [(*r.bounds[0][:2], *r.bounds[1][:2], r.bounds[0][2], r.bounds[1][2]) for r in spec.rooms]
    for cor in spec.corridors:
        rules = tunnels.get(cor.id)
        if rules is None or cor.rough <= 0:
            continue
        hw = cor.width / 2
        route = corridor_route(cor, rooms)
        waypoints = list(route.waypoints)
        zs, _ = MeshBuilder._waypoint_zs(waypoints, None if route.carry < 0 else route.carry,
                                         cor.from_z, cor.to_z)
        held = _held_leg(cor, waypoints, zs)
        split = held is not None and bool(cor.transition.floor_material)
        others = room_boxes + [b for cid, bs in boxes.items() if cid != cor.id for _, b in bs]
        run_in = max(hw, rules.end)
        wind: List[float] = []
        for k in range(len(waypoints) - 1):
            ends = MeshBuilder._leg_ends(waypoints, k, hw, zs)
            if ends is None or (held is not None and (k == held or (split and k > held))):
                wind.append(0.0)
                continue
            own = [b for i, b in boxes[cor.id] if i != k]
            room = leg_clearance(ends, route.axes[k], hw, zs[k], zs[k + 1], cor.height, run_in, others + own)
            span = abs(ends[1][0] - ends[0][0]) + abs(ends[1][1] - ends[0][1])
            limit = math.floor(min(room, rules.wander * span) * 100) / 100
            line = wind_leg(ends[0], ends[1], route.axes[k], hw, limit, rules, wind_seed(cor, k, ends[0]))
            wind.append(limit if len(line) > 2 else 0.0)
        cor.wind = wind if any(wind) else []
    measure_routes(spec, tunnels, rooms, boxes, room_boxes, holds)


# --- Winding routes (step 25, winding-routes Requirement 2) -----------------------------

_Poly = List[Tuple[float, float]]
#: (x0, y0, x1, y1) bounds, the convex polygon, z0, z1, and the room id it is ("" if none).
_Solid = Tuple[Tuple[float, float, float, float], _Poly, float, float, str]


def _solid(poly: _Poly, z0: float, z1: float, room: str = "") -> _Solid:
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    return (min(xs), min(ys), max(xs), max(ys)), poly, z0, z1, room


def _box_solid(box: _Box, room: str = "") -> _Solid:
    x0, y0, x1, y1, z0, z1 = box
    return _solid([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z0, z1, room)


def _separated(a: _Poly, b: _Poly) -> bool:
    """Do two convex polygons stand apart (an axis across one's edges splits them)?"""
    for poly in (a, b):
        for i in range(len(poly)):
            (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % len(poly)]
            nx, ny = y0 - y1, x1 - x0
            pa = [nx * x + ny * y for x, y in a]
            pb = [nx * x + ny * y for x, y in b]
            if max(pa) < min(pb) or max(pb) < min(pa):
                return True
    return False


def _point_seg(p, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    d2 = dx * dx + dy * dy
    t = 0.0 if d2 < 1e-12 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / d2))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def poly_gap(a: _Poly, b: _Poly) -> float:
    """The distance between two convex polygons in plan, 0 when they overlap."""
    if not _separated(a, b):
        return 0.0
    gap = float("inf")
    for p, q in ((a, b), (b, a)):
        for pt in p:
            for i in range(len(q)):
                gap = min(gap, _point_seg(pt, q[i], q[(i + 1) % len(q)]))
    return gap


def path_pieces(line, hw: float, from_z: float, to_z: float) -> Optional[List[Tuple[_Poly, float, float]]]:
    """A route line's strip, one (quad, z at its start, z at its end) per run of the line,
    mitred as ``_add_winding_leg`` builds it: flat at ``from_z`` over the first run-out, at
    ``to_z`` over the last, the rise spread by length between. None when the strip folds."""
    corners = strip_corners(line, hw)
    if corners is None:
        return None
    seg = [math.hypot(line[j + 1][0] - line[j][0], line[j + 1][1] - line[j][1]) for j in range(len(line) - 1)]
    s0, s1 = seg[0], sum(seg) - seg[-1]

    def z_at(s):
        if s <= s0 or s1 <= s0:
            return from_z
        return to_z if s >= s1 else from_z + (to_z - from_z) * (s - s0) / (s1 - s0)

    out, done = [], 0.0
    for j in range(len(seg)):
        (la, ra), (lb, rb) = corners[j], corners[j + 1]
        out.append(([la, lb, rb, ra], z_at(done), z_at(done + seg[j])))
        done += seg[j]
    return out


def route_clear(cor: CorridorSpec, line, solids: Sequence[_Solid]) -> bool:
    """Amendment A2: does ``line``'s strip keep the player's half-width from every one of
    ``solids`` beside it in Z (room boxes, other corridors), except the two rooms ``cor``
    joins, which only its run-outs (its first and last runs) may reach? Also False when the
    strip folds or climbs steeper than ``ROUTE_MAX_GRADE`` between the run-outs."""
    hw = cor.width / 2
    pieces = path_pieces(line, hw, cor.from_z, cor.to_z)
    if pieces is None:
        return False
    seg = [math.hypot(line[j + 1][0] - line[j][0], line[j + 1][1] - line[j][1]) for j in range(len(line) - 1)]
    middle = sum(seg[1:-1])
    rise = abs(cor.to_z - cor.from_z)
    if rise > 0.01 and (middle <= 0 or rise / middle > ROUTE_MAX_GRADE):
        return False
    last = len(pieces) - 1
    for j, (quad, za, zb) in enumerate(pieces):
        lo, hi = min(za, zb) - WIND_Z_SPARE, max(za, zb) + cor.height + WIND_Z_SPARE
        xs, ys = [p[0] for p in quad], [p[1] for p in quad]
        qx0, qy0 = min(xs) - PLAYER_HALF_WIDTH, min(ys) - PLAYER_HALF_WIDTH
        qx1, qy1 = max(xs) + PLAYER_HALF_WIDTH, max(ys) + PLAYER_HALF_WIDTH
        for (bx0, by0, bx1, by1), poly, z0, z1, room in solids:
            if bx1 < qx0 or bx0 > qx1 or by1 < qy0 or by0 > qy1 or z1 <= lo or z0 >= hi:
                continue
            if (j == 0 and room == cor.from_room) or (j == last and room == cor.to_room):
                continue
            if poly_gap(quad, poly) < PLAYER_HALF_WIDTH:
                return False
    return True


def measure_routes(spec: ZoneSpec, tunnels: Mapping[str, object], rooms=None, boxes=None,
                   room_boxes=None, holds: Optional[Mapping[str, object]] = None) -> None:
    """Set each rough plain corridor's ``path``: ``routing.wind_route``'s line, opening to
    opening, when its strip clears everything else (``route_clear``); else ``[]``. Checked
    against every room, every other corridor's route boxes, the legs step 23 winds and the
    paths already set, so no two lines meet. A line that wanders and fails is tried again
    without the wander (its bends still cut).

    A corridor holding a Transition line (``holds``, winding-control Requirement 8) takes
    ``routing.hold_route``'s line instead, after every other: straight on its leg's line for
    the line's depth and a half-width either side, so the frame, breach or seam stands
    square across it, and the Transition's ``z`` is the path's floor there (a frame's lintel
    judged again on the path's grade). Failing everything, it keeps its legs.

    Its ``wind`` stays as step 23 measured it, so the mesh, which reads only ``wind`` until
    winding-routes task 2, is unchanged (the design has ``wind = []`` alongside a path)."""
    for cor in spec.corridors:
        cor.path = []
    holds = holds or {}
    eligible = [cor for cor in spec.corridors
                if tunnels.get(cor.id) is not None and cor.rough > 0 and cor.steps == 0
                and not cor.bridge and cor.transition is None]
    held = [cor for cor in spec.corridors
            if cor.id in holds and cor.transition is not None and cor.steps == 0 and not cor.bridge]
    if not eligible and not held:
        return
    if rooms is None:
        rooms = {r.id: r for r in spec.rooms}
        boxes = {cor.id: _corridor_boxes(cor, rooms) for cor in spec.corridors}
        room_boxes = [(*r.bounds[0][:2], *r.bounds[1][:2], r.bounds[0][2], r.bounds[1][2]) for r in spec.rooms]
    solids: Dict[str, List[_Solid]] = {"": [_box_solid(b, r.id) for b, r in zip(room_boxes, spec.rooms)]}
    for cor in spec.corridors:
        mine = solids[cor.id] = [_box_solid(b) for _, b in boxes[cor.id]]
        rules = tunnels.get(cor.id)
        if not cor.wind or rules is None:
            continue
        # The legs step 23 winds stray past their boxes.
        route = corridor_route(cor, rooms)
        waypoints = list(route.waypoints)
        zs, _ = MeshBuilder._waypoint_zs(waypoints, None if route.carry < 0 else route.carry,
                                         cor.from_z, cor.to_z)
        hw = cor.width / 2
        for k, limit in enumerate(cor.wind):
            ends = MeshBuilder._leg_ends(waypoints, k, hw, zs)
            if limit <= 0 or ends is None:
                continue
            leg = wind_leg(ends[0], ends[1], route.axes[k], hw, limit, rules, wind_seed(cor, k, ends[0]))
            for quad, _, _ in path_pieces(leg, hw, zs[k], zs[k]) or ():
                mine.append(_solid(quad, min(zs[k], zs[k + 1]), max(zs[k], zs[k + 1]) + cor.height))
    for cor in eligible:
        rules = tunnels[cor.id]
        others = [s for cid, ss in solids.items() if cid != cor.id for s in ss]
        route = corridor_route(cor, rooms)
        for wander in (True, False):
            line = wind_route(route, cor.width / 2, rules, route_seed(cor), wander)
            if line is not None and route_clear(cor, line, others):
                cor.path = [(float(x), float(y)) for x, y in line]
                for quad, za, zb in path_pieces(line, cor.width / 2, cor.from_z, cor.to_z):
                    solids[cor.id].append(_solid(quad, min(za, zb), max(za, zb) + cor.height))
                break
    h = body_height(spec.dungeon_race)
    written = {w["corridor"]: w for w in spec.layout.get("transitions", ())}
    for cor in held:
        rules, sides = holds[cor.id]
        t = cor.transition
        hw = cor.width / 2
        route = corridor_route(cor, rooms)
        waypoints = list(route.waypoints)
        zs, _ = MeshBuilder._waypoint_zs(waypoints, None if route.carry < 0 else route.carry,
                                         cor.from_z, cor.to_z)
        leg = _held_leg(cor, waypoints, zs)
        if leg is None:
            continue
        hold = Hold(leg, (t.x, t.y), t.depth + hw, sides)
        others = [s for cid, ss in solids.items() if cid != cor.id for s in ss]
        for wander in (True, False):
            line = hold_route(route, hw, rules, route_seed(cor), hold, wander)
            if line is None or not route_clear(cor, line, others):
                continue
            cut = split_path(line, path_zs(line, cor.from_z, cor.to_z), (t.x, t.y))
            if cut is None:
                continue
            past, past_zs = cut[2], cut[3]
            z = round(past_zs[0], 3)
            lintel = t.lintel
            if t.form == FRAME:
                run = math.hypot(past[1][0] - past[0][0], past[1][1] - past[0][1])
                lintel = _lintel(cor, h, abs(past_zs[1] - past_zs[0]) / max(run, 1e-9) * t.depth)
                if lintel is None:
                    continue
            cor.path = [(float(x), float(y)) for x, y in line]
            t.z, t.lintel = z, lintel
            if cor.id in written:
                written[cor.id]["z"] = z
            for quad, za, zb in path_pieces(line, hw, cor.from_z, cor.to_z):
                solids[cor.id].append(_solid(quad, min(za, zb), max(za, zb) + cor.height))
            break


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
           "draw_transition", "draw_transitions", "finish_transitions", "leg_clearance", "load_transitions",
           "measure_routes", "measure_winds", "path_pieces", "poly_gap", "route_clear"]
