"""What decor knows about a room (roadmap step 11, design "Stages and the RoomContext").

The room stage hands decor one :class:`RoomContext` per room and per Site, and decor reads
nothing else: no ZoneSpec, no mesh, no zone (Req 13.1). A context is plain data with a
versioned JSON form whose text is stable (sorted keys, rounded floats), so a recorded room
corpus (``tests/fixtures/rooms/``, ``scripts/record_rooms.py``) diffs cleanly when it's
re-recorded.

What a room's context holds, all in world units, Z up:

- the floor on step 9's plan grid (``room_layouts.CELL``): each cell's floor height, read
  from the BUILT mesh (the highest floor under the cell's middle, so a dais's top counts),
  and which cells are reached: floor no solid Feature stands on, joined to a door by steps
  a player can climb;
- the ceiling's height over each cell, from the mesh (none under a Bridge's slot);
- wall faces sampled along the built wall mesh, not the Outline: rough and hewn walls lift
  and drop, so only the mesh says where a wall's foot and head are. Each is a point, the
  face's normal (level, pointing off the wall into the room), and the wall's bottom and top
  there. A wall over a doorway (a lintel) has its bottom at the door's top;
- doors: side, span, top, Throats (the strips of floor from the door to the Core) and clear
  zone (the door's own strip going in);
- the Spine (step 9), Features with their footprints, POIs;
- what the room is: type, kind, wall style, race, theme, zone type, Scales, the zone seed.

A Site's context is the same shape: its ground under the Site_Clear, its Structures as
Features, its POIs, the Site_Clear's pieces, and no walls, ceiling or doors.

Grids are stored by rows of the plan grid's X index (``grid[i][j]`` is the cell at
``origin + (i, j) * cell``). In JSON a height row is run-length coded (``[value, count]``
pairs, ``null`` for no floor), and a mask row is a string of ``#`` (set) and ``.``.
"""

from __future__ import annotations

import json
import math
from collections import deque
from dataclasses import dataclass, field
from itertools import groupby
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np

VERSION = 1
#: Floats in the JSON form are rounded to this many places.
DIGITS = 2
#: Wall faces are sampled at least this often along a wall (u).
WALL_STEP = 4.0
#: The highest step a player climbs between neighbouring cells (the gate's ``max_step_up``).
STEP_UP = 3.0
#: A triangle is floor (or ceiling) when its normal's Z is past this, wall when under WALL_NZ.
FLAT_NZ = 0.5
WALL_NZ = 0.2
_ON = 0.02          # how far a wall's foot may be off its line (u)

Rect = Tuple[float, float, float, float]


def _r(v: float) -> float:
    out = round(float(v), DIGITS)
    return 0.0 if out == 0 else out     # no "-0.0"


def _rr(seq: Iterable[float]) -> List[float]:
    return [_r(v) for v in seq]


# ---------------------------------------------------------------------------
# The context
# ---------------------------------------------------------------------------

@dataclass(eq=False)
class WallFace:
    x: float
    y: float
    nx: float           # level, off the wall into the room
    ny: float
    bottom: float
    top: float

    def to_list(self) -> list:
        return _rr((self.x, self.y, self.nx, self.ny, self.bottom, self.top))


@dataclass(eq=False)
class Door:
    side: str                           # N, S, E or W of the room's Box
    c0: float                           # its span along that side
    c1: float
    top: float                          # the opening's top (a lintel above it)
    throats: List[Rect] = field(default_factory=list)
    clear: Optional[Rect] = None        # the door's own strip going in

    def to_dict(self) -> dict:
        return {"side": self.side, "c0": _r(self.c0), "c1": _r(self.c1), "top": _r(self.top),
                "throats": [_rr(t) for t in self.throats], "clear": _rr(self.clear) if self.clear else None}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Door":
        return cls(d["side"], d["c0"], d["c1"], d["top"], [tuple(t) for t in d["throats"]],
                   tuple(d["clear"]) if d.get("clear") else None)


@dataclass(eq=False)
class RoomContext:
    """One room (or Site) as decor sees it. ``floor`` and ``ceiling`` are (nx, ny) height
    grids with NaN where there's none; ``reached`` and ``spine`` are (nx, ny) masks."""
    id: str
    source: str                         # "room" or "site"
    zone_type: str
    theme: str
    race: str
    room_type: str                      # a room's semantic type; a Site's kind
    kind: str                           # the rule set's room kind; "" for classic and Sites
    style: str                          # the room's wall style; "" for a plain Box or a Site
    seed: int                           # the zone's seed
    body_height: float                  # H: the race's body height, the unit rooms are sized in
    scales: Dict[str, int]
    box: Tuple[float, float, float, float, float, float]    # x0, y0, z0, x1, y1, z1
    cell: float
    origin: Tuple[float, float]         # the middle of cell (0, 0)
    floor: np.ndarray
    reached: np.ndarray
    ceiling: Optional[np.ndarray]
    spine: np.ndarray
    walls: List[WallFace] = field(default_factory=list)
    doors: List[Door] = field(default_factory=list)
    features: List[dict] = field(default_factory=list)
    pois: List[dict] = field(default_factory=list)
    clear: List[dict] = field(default_factory=list)     # a Site's Site_Clear pieces

    # -- JSON ---------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "version": VERSION, "id": self.id, "source": self.source, "zone_type": self.zone_type,
            "theme": self.theme, "race": self.race, "room_type": self.room_type, "kind": self.kind,
            "style": self.style, "seed": int(self.seed), "body_height": _r(self.body_height),
            "scales": {k: int(v) for k, v in self.scales.items()},
            "box": _rr(self.box),
            "grid": {"cell": _r(self.cell), "origin": _rr(self.origin), "size": list(self.floor.shape),
                     "floor": _heights_out(self.floor), "reached": _mask_out(self.reached),
                     "ceiling": None if self.ceiling is None else _heights_out(self.ceiling),
                     "spine": _mask_out(self.spine)},
            "walls": [w.to_list() for w in self.walls],
            "doors": [d.to_dict() for d in self.doors],
            "features": [_clean(f) for f in self.features],
            "pois": [_clean(p) for p in self.pois],
            "clear": [_clean(c) for c in self.clear],
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "RoomContext":
        if d.get("version") != VERSION:
            raise ValueError(f"RoomContext version {d.get('version')!r}; this reads {VERSION}")
        g = d["grid"]
        shape = tuple(g["size"])
        return cls(
            id=d["id"], source=d["source"], zone_type=d["zone_type"], theme=d["theme"], race=d["race"],
            room_type=d["room_type"], kind=d["kind"], style=d["style"], seed=d["seed"],
            body_height=d["body_height"], scales=dict(d["scales"]), box=tuple(d["box"]),
            cell=g["cell"], origin=tuple(g["origin"]),
            floor=_heights_in(g["floor"], shape), reached=_mask_in(g["reached"], shape),
            ceiling=None if g["ceiling"] is None else _heights_in(g["ceiling"], shape),
            spine=_mask_in(g["spine"], shape),
            walls=[WallFace(*w) for w in d["walls"]],
            doors=[Door.from_dict(x) for x in d["doors"]],
            features=[dict(f) for f in d["features"]], pois=[dict(p) for p in d["pois"]],
            clear=[dict(c) for c in d["clear"]])

    def to_json(self) -> str:
        return dumps(self.to_dict())

    @classmethod
    def from_json(cls, text: str) -> "RoomContext":
        return cls.from_dict(json.loads(text))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, RoomContext) and self.to_dict() == other.to_dict()

    # -- what decor asks of it ---------------------------------------------

    def cell_xy(self, i: int, j: int) -> Tuple[float, float]:
        return self.origin[0] + i * self.cell, self.origin[1] + j * self.cell


#: Lists written one element to a line, each element on its line whole: a grid's rows, walls.
ROW_KEYS = frozenset({"floor", "ceiling", "reached", "spine", "walls"})
_SHORT = 100


def _compact(v: Any) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _depth(v: Any) -> int:
    if isinstance(v, list):
        return 1 + max((_depth(x) for x in v), default=0)
    return 0


def dumps(obj: Any, indent: int = 0, rows: bool = False) -> str:
    """The stable JSON text: sorted keys, objects one key to a line, a short list on one
    line, a grid's rows and the walls one to a line. Parses as ordinary JSON."""
    pad, inner = " " * indent, " " * (indent + 1)
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        items = [f"{inner}{json.dumps(k)}: {dumps(obj[k], indent + 1, k in ROW_KEYS)}" for k in sorted(obj)]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if isinstance(obj, list) and obj:
        has_dict = any(isinstance(x, dict) for x in obj)
        text = _compact(obj)
        if rows:
            return "[\n" + ",\n".join(inner + _compact(x) for x in obj) + "\n" + pad + "]"
        if has_dict or _depth(obj) > 2 or (_depth(obj) == 2 and len(text) > _SHORT):
            return "[\n" + ",\n".join(inner + dumps(x, indent + 1) for x in obj) + "\n" + pad + "]"
        return text
    return _compact(obj)


def _clean(v: Any) -> Any:
    """Plain JSON data with floats rounded and tuples as lists."""
    if isinstance(v, Mapping):
        return {str(k): _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return _r(v)
    return v


def _heights_out(a: np.ndarray) -> List[list]:
    rows = []
    for row in (np.round(a, DIGITS) + 0.0).tolist():      # + 0.0: no "-0.0"
        runs: List[list] = []
        for v, run in groupby(None if v != v else v for v in row):
            runs.append([v, sum(1 for _ in run)])
        rows.append(runs)
    return rows


def _heights_in(rows: Sequence[Sequence], shape) -> np.ndarray:
    out = np.full(shape, np.nan)
    for i, runs in enumerate(rows):
        j = 0
        for v, n in runs:
            if v is not None:
                out[i, j:j + n] = v
            j += n
    return out


def _mask_out(m: np.ndarray) -> List[str]:
    return ["".join(row) for row in np.where(m, "#", ".")]


def _mask_in(rows: Sequence[str], shape) -> np.ndarray:
    out = np.zeros(shape, bool)
    for i, row in enumerate(rows):
        out[i] = np.frombuffer(row.encode("ascii"), dtype=np.uint8) == ord("#")
    return out


# ---------------------------------------------------------------------------
# Reading the built mesh
# ---------------------------------------------------------------------------

class _Mesh:
    """The TER's triangles as arrays: corners (M, 3, 3), declared normal Z, material names."""

    def __init__(self, ter):
        v = np.array([(p.x, p.y, p.z) for p in ter.vertices], dtype=np.float64)
        vn = np.array([(p.nx, p.ny, p.nz) for p in ter.vertices], dtype=np.float64)
        idx = np.array([(p.v1, p.v2, p.v3) for p in ter.polygons], dtype=np.int64).reshape(-1, 3)
        self.tri = v[idx]
        self.normal = vn[idx].mean(axis=1)
        names = [m.name for m in ter.materials]
        self.material = np.array([names[p.material] if 0 <= p.material < len(names) else ""
                                  for p in ter.polygons], dtype=object)
        self.lo = self.tri.min(axis=1)
        self.hi = self.tri.max(axis=1)

    def within(self, x0, y0, z0, x1, y1, z1) -> np.ndarray:
        return ((self.hi[:, 0] >= x0) & (self.lo[:, 0] <= x1) & (self.hi[:, 1] >= y0)
                & (self.lo[:, 1] <= y1) & (self.hi[:, 2] >= z0) & (self.lo[:, 2] <= z1))


def _sample(tris: np.ndarray, xs: np.ndarray, ys: np.ndarray, pick: str) -> np.ndarray:
    """Each grid cell's middle dropped onto ``tris``: the highest (``pick="max"``) or lowest
    surface over it, NaN where none is."""
    out = np.full((len(xs), len(ys)), np.nan)
    if len(xs) == 0 or len(ys) == 0:
        return out
    cell = xs[1] - xs[0] if len(xs) > 1 else (ys[1] - ys[0] if len(ys) > 1 else 1.0)
    for t in tris:
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = t
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(det) < 1e-12:
            continue
        i0 = max(0, int(math.floor((min(ax, bx, cx) - xs[0]) / cell)))
        i1 = min(len(xs) - 1, int(math.ceil((max(ax, bx, cx) - xs[0]) / cell)))
        j0 = max(0, int(math.floor((min(ay, by, cy) - ys[0]) / cell)))
        j1 = min(len(ys) - 1, int(math.ceil((max(ay, by, cy) - ys[0]) / cell)))
        if i1 < i0 or j1 < j0:
            continue
        gx, gy = np.meshgrid(xs[i0:i1 + 1], ys[j0:j1 + 1], indexing="ij")
        l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / det
        l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / det
        l3 = 1.0 - l1 - l2
        inside = (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
        if not inside.any():
            continue
        z = l1 * az + l2 * bz + l3 * cz
        block = out[i0:i1 + 1, j0:j1 + 1]
        if pick == "max":
            better = inside & (np.isnan(block) | (z > block))
        else:
            better = inside & (np.isnan(block) | (z < block))
        block[better] = z[better]
    return out


def _on_segment(px, py, a, b) -> bool:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    n = dx * dx + dy * dy
    t = 0.0 if n == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / n))
    return math.hypot(px - ax - t * dx, py - ay - t * dy) <= _ON


def _wall_lines(room) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    (x0, y0, _), (x1, y1, _) = room.bounds
    if room.outline is None:
        return [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    v = room.outline.verts
    return [(tuple(v[i]), tuple(v[j])) for loop in room.outline.wall_loops() for i, j in zip(loop, loop[1:] + loop[:1])]


def _walls(mesh: _Mesh, room, pick: np.ndarray) -> List[WallFace]:
    """Wall faces along the built walls: every level-facing triangle of the room's wall
    material whose foot lies on one of the room's wall lines, grouped by the wall piece it
    belongs to, sampled every ``WALL_STEP`` along it."""
    lines = _wall_lines(room)
    pieces: Dict[tuple, dict] = {}
    for k in np.nonzero(pick)[0]:
        t = mesh.tri[k]
        pts = sorted({(round(float(x), 3), round(float(y), 3)) for x, y, _z in t})
        if len(pts) != 2:
            continue
        a, b = pts
        if not any(_on_segment(*a, *ln) and _on_segment(*b, *ln) for ln in lines):
            continue
        piece = pieces.setdefault((a, b), {"z": {a: [], b: []}, "n": []})
        for x, y, z in t:
            piece["z"][(round(float(x), 3), round(float(y), 3))].append(float(z))
        piece["n"].append(mesh.normal[k][:2])
    out = []
    for (a, b), piece in sorted(pieces.items()):
        n = np.mean(piece["n"], axis=0)
        ln = float(np.hypot(*n))
        if ln < 1e-9:
            continue
        nx, ny = n / ln
        za, zb = piece["z"][a], piece["z"][b]
        run = math.hypot(b[0] - a[0], b[1] - a[1])
        steps = max(1, int(math.ceil(run / WALL_STEP)))
        for s in range(steps):
            f = (s + 0.5) / steps
            out.append(WallFace(_r(a[0] + (b[0] - a[0]) * f), _r(a[1] + (b[1] - a[1]) * f), _r(nx), _r(ny),
                                _r(min(za) + (min(zb) - min(za)) * f), _r(max(za) + (max(zb) - max(za)) * f)))
    return out


def _reached(floor: np.ndarray, solid: np.ndarray, starts: Sequence[Tuple[int, int]]) -> np.ndarray:
    """Floor cells joined to a door by steps a player climbs, none a solid stands on."""
    ok = ~np.isnan(floor) & ~solid
    seen = np.zeros(floor.shape, bool)
    queue = deque()
    for c in starts:
        if ok[c] and not seen[c]:
            seen[c] = True
            queue.append(c)
    nx, ny = floor.shape
    while queue:
        i, j = queue.popleft()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = i + di, j + dj
            if 0 <= a < nx and 0 <= b < ny and ok[a, b] and not seen[a, b] \
                    and abs(floor[a, b] - floor[i, j]) <= STEP_UP:
                seen[a, b] = True
                queue.append((a, b))
    return seen


def _in_polygon(gx: np.ndarray, gy: np.ndarray, plan: Sequence[Tuple[float, float]]) -> np.ndarray:
    inside = np.zeros(gx.shape, bool)
    n = len(plan)
    for k in range(n):
        (ax, ay), (bx, by) = plan[k], plan[(k + 1) % n]
        cross = (ay > gy) != (by > gy)
        with np.errstate(divide="ignore", invalid="ignore"):
            at = (bx - ax) * (gy - ay) / (by - ay) + ax
        inside ^= cross & (gx < at)
    return inside


def _rounded(a: np.ndarray) -> np.ndarray:
    out = np.round(a, DIGITS)
    out[out == 0] = 0.0
    return out


# ---------------------------------------------------------------------------
# Rooms
# ---------------------------------------------------------------------------

def _extra_doors(spec) -> Dict[str, Dict[str, list]]:
    if spec.wilderness is not None and "dungeon" in spec.wilderness:
        from generators.outdoor_dungeon import tunnel_doors
        return tunnel_doors(spec)
    return {}


def contexts(spec, mesh) -> List[RoomContext]:
    """Every room of a built dungeon, city or outdoor dungeon, from its spec and its built
    TER (``mesh``). Reads them; changes neither."""
    from generators.geometry import _bridge_slots, _door_openings, _merge_openings
    from generators.outline import _core_rect, _door_throats
    from generators.room_layouts import CELL, RoomGrid
    from generators.semantics import body_height

    m = mesh if isinstance(mesh, _Mesh) else _Mesh(mesh)
    h = body_height(spec.dungeon_race)
    records = (spec.layout or {}).get("rooms", {})
    extra = _extra_doors(spec)
    out = []
    for room in spec.rooms:
        record = records.get(room.id, {})
        (x0, y0, z0), (x1, y1, z1) = room.bounds
        box = (x0, y0, x1, y1)
        # Doors as the mesh cuts them: merged per side, with the opening's top.
        openings = _door_openings(room, spec)
        for side, cuts in (extra.get(room.id) or {}).items():
            openings.setdefault(side, []).extend(cuts)
        extents = {"S": (x0, x1), "N": (x0, x1), "W": (y0, y1), "E": (y0, y1)}
        merged = [(side, c0, c1, top) for side in sorted(openings)
                  for c0, c1, top in _merge_openings(openings[side], *extents[side])]
        doors = [(side, c0, c1) for side, c0, c1, _top in merged]
        slots = _bridge_slots(room, spec)
        grid = RoomGrid(room, doors, slots, h)
        core = room.outline.core if room.outline is not None else \
            _core_rect(box, max([c1 - c0 for _s, c0, c1 in doors], default=0.0))

        near = m.within(x0 - 0.05, y0 - 0.05, z0 - 2.0, x1 + 0.05, y1 + 0.05, z1 + 1.0)
        up = near & (m.normal[:, 2] > FLAT_NZ) & (m.hi[:, 2] <= z1 - 0.5)
        floor = _sample(m.tri[up], grid.xs, grid.ys, "max")
        floor[~grid.floor] = np.nan
        down = near & (m.normal[:, 2] < -FLAT_NZ) & (m.material == room.ceiling_material)
        ceiling = _sample(m.tri[down], grid.xs, grid.ys, "min")
        ceiling[np.isnan(floor) | ~(ceiling > floor + 0.5)] = np.nan
        solid = np.zeros(floor.shape, bool)
        for f in room.features:
            if f.kind != "dais":
                solid |= _in_polygon(grid.gx, grid.gy, f.plan)
        floor, ceiling = _rounded(floor), _rounded(ceiling)
        reached = _reached(floor, solid, grid.door_cells)
        # A wall row stands in the room's height: a Bridge's shaft above the ceiling isn't its wall.
        level = near & (np.abs(m.normal[:, 2]) < WALL_NZ) & (m.material == room.wall_material) \
            & (m.lo[:, 2] < z1 - 0.1) & (m.hi[:, 2] <= z1 + 0.5)

        ctx_doors = []
        for side, c0, c1, top in merged:
            throats = [(max(t[0], x0), max(t[1], y0), min(t[2], x1), min(t[3], y1))
                       for t in _door_throats(box, (side, c0, c1), core)]
            ctx_doors.append(Door(side, _r(c0), _r(c1), _r(top), [tuple(_rr(t)) for t in throats],
                                  tuple(_rr(grid.door_clear((side, c0, c1))))))
        out.append(RoomContext(
            id=room.id, source="room", zone_type=spec.zone_type,
            theme=room.room_theme or spec.dungeon_theme or "", race=spec.dungeon_race or "",
            room_type=room.semantic_type or "", kind=record.get("kind", room.kind) or "",
            style=record.get("style", "") or "", seed=int(spec.seed or 0), body_height=_r(h),
            scales=dict(record.get("scales") or {}), box=tuple(_rr((x0, y0, z0, x1, y1, z1))),
            cell=CELL, origin=(_r(grid.xs[0]), _r(grid.ys[0])),
            floor=floor, reached=reached, ceiling=ceiling, spine=grid.spine.copy(),
            walls=_walls(m, room, level), doors=ctx_doors,
            features=[_clean({"kind": f.kind, "plan": f.plan, "height": f.height, "steps_side": f.steps_side})
                      for f in room.features],
            pois=[_clean({"purpose": p.purpose, "name": p.name, "x": p.x, "y": p.y, "z": p.z,
                          "feature": p.feature}) for p in room.pois]))
    return out


# ---------------------------------------------------------------------------
# Sites
# ---------------------------------------------------------------------------

CAPSULE_SIDES = 12      # a Structure's footprint as a polygon: a capsule round this many ways


def _capsule_plan(x0, y0, x1, y1, r) -> List[Tuple[float, float]]:
    """A capsule as a counter-clockwise polygon: two half circles round its ends."""
    a = math.atan2(y1 - y0, x1 - x0) if (x1, y1) != (x0, y0) else 0.0
    half = CAPSULE_SIDES // 2
    pts = [(x1 + r * math.cos(a - math.pi / 2 + math.pi * k / half),
            y1 + r * math.sin(a - math.pi / 2 + math.pi * k / half)) for k in range(half + 1)]
    pts += [(x0 + r * math.cos(a + math.pi / 2 + math.pi * k / half),
             y0 + r * math.sin(a + math.pi / 2 + math.pi * k / half)) for k in range(half + 1)]
    return pts


def _in_capsule(gx, gy, s) -> np.ndarray:
    x0, y0, x1, y1, r = s
    dx, dy = x1 - x0, y1 - y0
    n = dx * dx + dy * dy
    t = np.zeros(gx.shape) if n == 0 else np.clip(((gx - x0) * dx + (gy - y0) * dy) / n, 0.0, 1.0)
    return np.hypot(gx - x0 - t * dx, gy - y0 - t * dy) <= r


def site_contexts(spec, mesh, placement=None) -> List[RoomContext]:
    """Every Site of a built wilderness or outdoor dungeon: its ground under the Site_Clear
    (heights from the built TER), its Structures as Features, its POIs, the Site_Clear's
    pieces. No walls, ceiling or doors. ``placement`` is the zone's ``SitePlacement``;
    left out, it's the build's own (``wilderness.build.sites_for``)."""
    from generators.room_layouts import CELL
    from generators.semantics import body_height

    if placement is None:
        from generators.wilderness.build import sites_for
        placement = sites_for(spec, mesh).placement
    m = mesh if isinstance(mesh, _Mesh) else _Mesh(mesh)
    theme = (spec.wilderness or {}).get("biome", "") or ""
    out = []
    for n, site in enumerate(placement.sites):
        shapes = [c.shape for c in site.clear]
        x0 = min(min(s[0], s[2]) - s[4] for s in shapes)
        y0 = min(min(s[1], s[3]) - s[4] for s in shapes)
        x1 = max(max(s[0], s[2]) + s[4] for s in shapes)
        y1 = max(max(s[1], s[3]) + s[4] for s in shapes)
        xs = np.arange(x0 + CELL / 2, x1, CELL)
        ys = np.arange(y0 + CELL / 2, y1, CELL)
        gx, gy = np.meshgrid(xs, ys, indexing="ij")
        ground = np.zeros(gx.shape, bool)
        for s in shapes:
            ground |= _in_capsule(gx, gy, s)
        near = m.within(x0, y0, -1e9, x1, y1, 1e9) & (m.normal[:, 2] > FLAT_NZ)
        floor = _sample(m.tri[near], xs, ys, "max")
        floor[~ground] = np.nan
        floor = _rounded(floor)
        solid = np.zeros(gx.shape, bool)
        for st in site.structures:
            solid |= _in_capsule(gx, gy, st.footprint())
        # Reached from the approach's far end, else from the Site's middle.
        approach = [c for c in site.clear if c.what == "approach"]
        sx, sy = (approach[0].x1, approach[0].y1) if approach else (site.x, site.y)
        free = np.argwhere(~np.isnan(floor) & ~solid)
        starts = []
        if len(free):
            d = np.hypot(xs[free[:, 0]] - sx, ys[free[:, 1]] - sy)
            starts = [tuple(int(v) for v in free[int(d.argmin())])]
        reached = _reached(floor, solid, starts)
        zs = [v for v in floor[~np.isnan(floor)]] or [site.z]
        features = []
        for st in site.structures:
            features.append(_clean({"kind": st.kind, "plan": _capsule_plan(*st.footprint()), "height": 0.0,
                                    "steps_side": "", "variant": st.variant, "x": st.x, "y": st.y, "z": st.z,
                                    "yaw": st.yaw, "radius": st.radius, "run": st.run,
                                    "enterable": st.enterable}))
        out.append(RoomContext(
            id=f"site{n}", source="site", zone_type=spec.zone_type, theme=theme, race=site.inhabitant or "",
            room_type=site.kind, kind="", style="", seed=int(spec.seed or 0), body_height=_r(body_height("")), scales={},
            box=tuple(_rr((x0, y0, min(zs), x1, y1, max(zs)))), cell=CELL, origin=(_r(xs[0]), _r(ys[0])),
            floor=floor, reached=reached, ceiling=None, spine=np.zeros(gx.shape, bool),
            features=features,
            pois=[_clean({"purpose": p.purpose, "name": p.name, "x": p.x, "y": p.y, "z": p.z, "at": p.at})
                  for p in site.pois],
            clear=[_clean({"what": c.what, "x0": c.x0, "y0": c.y0, "x1": c.x1, "y1": c.y1, "r": c.r})
                   for c in site.clear]))
    return out


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

def save(path, recipe: Mapping[str, Any], rooms: Sequence[RoomContext]) -> None:
    """One recording: how it was made (``recipe``) and its contexts, as stable JSON text."""
    text = dumps({"version": VERSION, "recipe": _clean(dict(recipe)), "rooms": [c.to_dict() for c in rooms]})
    Path(path).write_text(text + "\n", encoding="utf-8", newline="\n")


def load(path) -> Tuple[dict, List[RoomContext]]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("version") != VERSION:
        raise ValueError(f"{path}: recording version {doc.get('version')!r}; this reads {VERSION}")
    return doc["recipe"], [RoomContext.from_dict(d) for d in doc["rooms"]]


__all__ = ["CAPSULE_SIDES", "DIGITS", "Door", "RoomContext", "STEP_UP", "VERSION", "WALL_STEP", "WallFace",
           "contexts", "dumps", "load", "save", "site_contexts"]
