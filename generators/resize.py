"""
generators/resize.py
--------------------
The resize ops (zone-generator-edits Req 2.7, archive decisions 6 and 7): ``widen_room``,
``narrow_room``, ``taller_room`` and ``lower_room`` change one room's box in a saved spec and
redraw what hangs off it, built in full.

``resize_room(doc, room, op, by)``:

1. Scales the room's box about its centre by the op's factor (``1 + by`` for widen and taller,
   ``1 - by`` for narrow and lower): width and depth, or height. Its floor stays put, and
   elevation is never relaxed.
2. Moves each touching corridor's end on the room out or in by its wall's shift, keeping the
   end's position along the wall. The corridor's other end stays.
3. Clamps by bisection to the largest factor between 1 and the one asked for that passes
   ``_check``: no new 3D overlap between the room or its corridors and anything else; each door
   half a corridor and 1 u inside its wall; each touching corridor's route kind, axes and leg
   directions the same; a ramp's grade at most max(0.5, its old grade); every stair's
   ``stair_layout`` and every Bridge's ``bridge_layout`` still there, ``cramped`` unchanged;
   the room as tall as each touching corridor at its door. When nothing fits, it is refused.
4. Re-dresses the rooms (``wall_styles.apply_walls`` / ``apply_walls_by_finish``, then
   ``room_layouts.apply_features``, at ``rooms_seed or seed``), keeping each corridor's saved
   Transition look where its form is the same. Every room draws from its own stream, so a room
   whose doors and Bridge slots didn't move draws exactly what it had.
5. Works out the Affected_Set from the spec alone: the room, its corridors, every room whose
   ``geometry._door_openings`` or ``_bridge_slots`` changed, and every corridor whose
   ``bridge_layout`` or ``stair_layout`` changed. Task 2 measured that prediction against the
   built triangles of 162 resizes.

Pure: the input dict is never changed and nothing is built.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple

from generators import geometry as geo
from generators.routing import corridor_route, route_footprint
from generators.zone_spec import ZoneSpec

__all__ = ["OPS", "ResizeResult", "factor", "fit", "redress", "resize_room"]

#: op -> (verb, past tense, what it scales).
OPS = {"widen_room": ("widen", "widened", "plan"), "narrow_room": ("narrow", "narrowed", "plan"),
       "taller_room": ("heighten", "heightened", "height"),
       "lower_room": ("lower", "lowered", "height")}

#: The steepest ramp a resize may make, unless the corridor was steeper already (the layout's
#: ``max_grade``).
MAX_GRADE = 0.5
#: How far a corridor end may sit in from its room's wall (the layout insets ends by 2 u).
_ON_WALL = 2.5
#: A door keeps this much wall each side of it.
_DOOR_MARGIN = 1.0
#: Bisection steps between 1 and the factor asked for.
_STEPS = 14
#: A clamp this close to 1 is no change at all: refused.
_NO_CHANGE = 0.01
#: What a corridor's Transition keeps from the saved spec when re-dressing leaves its form.
_LOOK = ("floor_material", "wall_material", "ceiling_material", "rough", "material")
_EPS = 1e-6


class ResizeResult(NamedTuple):
    """``doc``: the edited spec dict (the input unchanged when ``applied`` is False).
    ``affected``: ``{rooms, corridors}``, in the spec's order. ``notes``: one line, the size asked
    for and the size applied, or why nothing fits."""
    doc: Dict[str, Any]
    applied: bool
    affected: Dict[str, List[str]]
    notes: List[str]


def factor(op: str, by: float) -> float:
    """The scale factor of ``op`` for ``by`` (archive decision 7): ``1 + by`` grows, ``1 - by``
    shrinks."""
    return 1.0 + by if op in ("widen_room", "taller_room") else 1.0 - by


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------

def _wall_of(room, x: float, y: float) -> Optional[str]:
    (x0, y0, _), (x1, y1, _) = room.bounds
    d = {"W": abs(x - x0), "E": abs(x - x1), "S": abs(y - y0), "N": abs(y - y1)}
    side = min(d, key=d.get)
    return side if d[side] <= _ON_WALL else None


def _carry_run(cor, route) -> float:
    """The run the rise is spread over: a Z or U route's middle leg less the corridor's width,
    else its longest leg."""
    wps, axes = route.waypoints, route.axes
    legs = [abs(wps[k + 1][0] - wps[k][0]) if axes[k] else abs(wps[k + 1][1] - wps[k][1])
            for k in range(len(wps) - 1)]
    if route.kind in ("z", "u"):
        return max(0.0, legs[1] - cor.width)
    return max(legs)


def _boxes_hit(a, b) -> bool:
    return all(min(a[i + 3], b[i + 3]) - max(a[i], b[i]) > 0.01 for i in range(3))


def _boxes(spec: ZoneSpec) -> Dict[str, list]:
    """Every room's and corridor's 3D boxes, by ``R:<id>`` / ``C:<id>``."""
    rooms = {r.id: r for r in spec.rooms}
    out = {}
    for r in spec.rooms:
        (x0, y0, z0), (x1, y1, z1) = r.bounds
        out["R:" + r.id] = [(x0, y0, z0, x1, y1, z1)]
    for c in spec.corridors:
        zlo, zhi = min(c.from_z, c.to_z), max(c.from_z, c.to_z) + c.height
        out["C:" + c.id] = [(x0, y0, zlo, x1, y1, zhi) for x0, y0, x1, y1
                            in route_footprint(corridor_route(c, rooms), c.width / 2)]
    return out


def _clashes(spec: ZoneSpec, ids: Sequence[str]) -> set:
    """The overlapping pairs that involve any element of ``ids``."""
    els = _boxes(spec)
    out = set()
    for a in ids:
        for b, bb in els.items():
            if a != b and any(_boxes_hit(x, y) for x in els[a] for y in bb):
                out.add(tuple(sorted((a, b))))
    return out


def _layouts(spec: ZoneSpec) -> Dict[str, Tuple[Any, Any]]:
    """Each corridor's (stair_layout, bridge_layout)."""
    rooms = {r.id: r for r in spec.rooms}
    return {c.id: (geo.stair_layout(c, rooms), geo.bridge_layout(c, rooms) if c.bridge else None)
            for c in spec.corridors}


class _Before(NamedTuple):
    ends: Dict[Tuple[str, str], str]     # (corridor id, "from"/"to") -> the wall it's on
    routes: Dict[str, Any]
    clashes: set
    layouts: Dict[str, Tuple[Any, Any]]
    ids: List[str]


def _before(spec: ZoneSpec, rid: str) -> _Before:
    rooms = {r.id: r for r in spec.rooms}
    room = rooms[rid]
    touching = [c for c in spec.corridors if rid in (c.from_room, c.to_room)
                and c.from_room != c.to_room]
    ends = {}
    for c in touching:
        for end in ("from", "to"):
            if getattr(c, f"{end}_room") == rid:
                side = _wall_of(room, getattr(c, f"{end}_x"), getattr(c, f"{end}_y"))
                if side is None:
                    raise ValueError(f"{c.id} doesn't end on a wall of {rid}")
                ends[(c.id, end)] = side
    ids = ["R:" + rid] + ["C:" + c.id for c in touching]
    return _Before(ends, {c.id: corridor_route(c, rooms) for c in touching},
                   _clashes(spec, ids), _layouts(spec), ids)


def _scaled(doc: Mapping[str, Any], rid: str, op: str, s: float, before: _Before
            ) -> Tuple[ZoneSpec, str]:
    """The spec with room ``rid`` scaled by ``s`` and its corridor ends moved, and the first
    check it fails ("" when it passes)."""
    spec = ZoneSpec.from_dict(copy.deepcopy(dict(doc)))
    rooms = {r.id: r for r in spec.rooms}
    room = rooms[rid]
    old_top = room.floor_z + room.height
    hw0, hd0 = room.width / 2, room.depth / 2
    if OPS[op][2] == "plan":
        room.width, room.depth = room.width * s, room.depth * s
    else:
        room.height = room.height * s
    dw, dd = room.width / 2 - hw0, room.depth / 2 - hd0
    by_id = {c.id: c for c in spec.corridors}
    for (cid, end), side in before.ends.items():
        c = by_id[cid]
        if side in "EW":
            setattr(c, f"{end}_x", getattr(c, f"{end}_x") + (dw if side == "E" else -dw))
            cross, centre, half = getattr(c, f"{end}_y"), room.center_y, room.depth / 2
        else:
            setattr(c, f"{end}_y", getattr(c, f"{end}_y") + (dd if side == "N" else -dd))
            cross, centre, half = getattr(c, f"{end}_x"), room.center_x, room.width / 2
        if abs(cross - centre) + c.width / 2 + _DOOR_MARGIN > half:
            return spec, f"{cid}'s door would come off the wall"
        need = getattr(c, f"{end}_z") + c.height
        if room.floor_z + room.height < min(need, old_top) - 0.01:
            return spec, f"the room would be lower than {cid}"
    for cid, r0 in before.routes.items():
        c = by_id[cid]
        r1 = corridor_route(c, rooms)
        if (r0.kind, r0.axes) != (r1.kind, r1.axes):
            return spec, f"{cid} would route another way"
        for k in range(len(r1.axes)):
            for i in (0, 1):
                p = r0.waypoints[k + 1][i] - r0.waypoints[k][i]
                q = r1.waypoints[k + 1][i] - r1.waypoints[k][i]
                if abs(p) > 0.5 and p * q <= 0:
                    return spec, f"{cid} would turn round"
        dz = abs(c.to_z - c.from_z)
        if c.steps == 0 and dz > 0.01:
            old = dz / max(_carry_run(c, r0), _EPS)
            new = dz / max(_carry_run(c, r1), _EPS)
            if new > max(MAX_GRADE, old) + 1e-6:
                return spec, f"{cid}'s ramp would be too steep (grade {new:.2f})"
    after = _layouts(spec)
    for cid, (st0, br0) in before.layouts.items():
        st1, br1 = after[cid]
        if st0 is not None and (st1 is None or st1.cramped != st0.cramped):
            return spec, f"{cid}'s stair would no longer fit"
        if br0 is not None and br1 is None:
            return spec, f"{cid}'s bridge would no longer fit"
    new = _clashes(spec, before.ids) - before.clashes
    if new:
        a, b = sorted(new)[0]
        return spec, f"{a[2:]} would overlap {b[2:]}"
    return spec, ""


def fit(doc: Mapping[str, Any], rid: str, op: str, want: float
        ) -> Tuple[Optional[ZoneSpec], float, str]:
    """``(spec, factor, why)``: the spec at the largest factor between 1 and ``want`` that passes
    every check (``factor == want`` and ``why == ""`` when ``want`` does), or ``(None, 1.0, why)``
    when nothing does. ``why`` is the check ``want`` failed."""
    before = _before(ZoneSpec.from_dict(copy.deepcopy(dict(doc))), rid)
    spec, why = _scaled(doc, rid, op, want, before)
    if not why:
        return spec, want, ""
    lo, hi, best = 1.0, want, None
    for _ in range(_STEPS):
        mid = (lo + hi) / 2
        cand, fails = _scaled(doc, rid, op, mid, before)
        if fails:
            hi = mid
        else:
            lo, best = mid, cand
    if best is None or abs(lo - 1.0) < _NO_CHANGE:
        return None, 1.0, why
    return best, lo, why


# ---------------------------------------------------------------------------
# Re-dressing and the Affected_Set
# ---------------------------------------------------------------------------

def redress(spec: ZoneSpec) -> None:
    """Draw every room's walls and features again, as the plan did (a spec with no grown layout
    has none to draw). Each corridor keeps its saved Transition look where its form is the same,
    so re-dressing an unchanged spec changes nothing."""
    if spec.layout is None or "walls" not in spec.layout:
        return
    from generators.room_layouts import apply_features
    from generators.wall_styles import PLAN_RULES, apply_walls, apply_walls_by_finish, load_styles
    old = {c.id: c.transition for c in spec.corridors}
    seed = spec.rooms_seed if spec.rooms_seed is not None else spec.seed
    if spec.layout["walls"] == PLAN_RULES:
        apply_walls_by_finish(spec, seed)
    else:
        apply_walls(spec, load_styles()[spec.layout["walls"]], seed)
    apply_features(spec, "", seed, spec.layout.get("features", "normal"))
    for c in spec.corridors:
        t0, t1 = old.get(c.id), c.transition
        if t0 is not None and t1 is not None and t0.form == t1.form:
            for k in _LOOK:
                setattr(t1, k, getattr(t0, k))


def _affected(old: ZoneSpec, new: ZoneSpec, rid: str) -> Dict[str, List[str]]:
    rooms_new = {r.id: r for r in new.rooms}
    rooms = [r.id for r in old.rooms
             if r.id == rid
             or geo._door_openings(r, old) != geo._door_openings(rooms_new[r.id], new)
             or geo._bridge_slots(r, old) != geo._bridge_slots(rooms_new[r.id], new)]
    before, after = _layouts(old), _layouts(new)
    corridors = [c.id for c in old.corridors
                 if rid in (c.from_room, c.to_room) or before[c.id] != after[c.id]]
    return {"rooms": rooms, "corridors": corridors}


def _note(op: str, rid: str, want: float, got: float) -> str:
    verb = OPS[op][1]
    if abs(got - want) < 1e-9:
        return f"{verb} {rid} by {_pct(want)}"
    return f"{verb} {rid} by {_pct(got)} of the {_pct(want)} asked"


def _pct(s: float) -> str:
    """A factor as the share of the room's size added or taken away (``by``)."""
    return f"{abs(s - 1.0) * 100:.0f}%"


def resize_room(doc: Mapping[str, Any], room: str, op: str, by: float) -> ResizeResult:
    """Resize ``room`` of the saved spec ``doc`` (``ZoneSpec.to_dict`` plus any extra keys, such
    as ``decor_layers``, which are kept). ``by`` is decision 7's fraction. Returns a
    ``ResizeResult``; when nothing fits, ``applied`` is False, ``doc`` is an unchanged copy and
    the note says why."""
    want = factor(op, by)
    nothing = {"rooms": [], "corridors": []}
    verb = OPS[op][0]
    if doc.get("zone_type") == "outdoor_dungeon":
        return ResizeResult(copy.deepcopy(dict(doc)), False, nothing,
                            [f"{op}: rooms under a hill can't be resized yet"])
    try:
        spec, got, why = fit(doc, room, op, want)
    except ValueError as exc:
        return ResizeResult(copy.deepcopy(dict(doc)), False, nothing,
                            [f"{op}: can't {verb} {room}: {exc}"])
    if spec is None:
        return ResizeResult(copy.deepcopy(dict(doc)), False, nothing,
                            [f"{op}: can't {verb} {room} at all ({_pct(want)} asked): {why}"])
    old = ZoneSpec.from_dict(copy.deepcopy(dict(doc)))
    affected = _affected(old, spec, room)
    redress(spec)
    out = copy.deepcopy(dict(doc))
    out.update(json.loads(json.dumps(spec.to_dict())))     # as saved: lists, not tuples
    note = _note(op, room, want, got)
    if why:
        note += f"; any more and {why}"
    return ResizeResult(out, True, affected, [note])
