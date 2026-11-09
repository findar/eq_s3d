"""What goes where in a room (roadmap step 9, design "The Spine and clearance").

Features come after everything else: the room's Box, walls and doors are final, and nothing
here changes them. A plan grid marks the floor. The Spine, the paths joining the doors, and
each door's approach, stays clear. Arrangements propose spots; a spot that doesn't fit is
dropped and recorded, so a room can be too full for its recipe but a build never fails for it.

After each placement the doors are checked again, as the gate will check them from the mesh.
"""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.ndimage import binary_dilation, label

from .room_features import BOULDER, DAIS, FEATURE_KINDS, PILLAR, PLINTH, POI, Feature, dais_plan, solid_plan
from .semantics import ROOM_TYPES
from .topology.graph import ROOM_KINDS
from .topology.ruleset import _Checker, _is_number, _one_of, _read_toml

CELL = 2.0              # the plan grid (u)
SPINE_HALF_H = 1.0      # the Spine's half width, in H: 2 H clear, a corridor's clear width
WALL_MARGIN_H = 1.0     # a solid stands this far from a wall, in H, so nothing snags behind it
BODY_RADIUS = 2.0       # a player's middle stays this far from a solid (u), as the gate has it
POCKET = 16.0           # free floor this big cut off from the doors is too much (u^2). Smaller than
                        # the gate's: this reckons a body wider, which shrinks what it sees
ARRANGEMENTS: Tuple[str, ...] = ("centre", "far_end", "ring", "rows", "corners", "along_wall",
                                 "scatter", "on_dais")
MIN_HEAD_H = 2.0        # a dais leaves this much headroom, in H
DAIS_RISE_H = 0.85      # a dais's rise, in H: stock's is 4-5 u, about two steps


@dataclass(frozen=True)
class Ask:
    """One line of a recipe: put these Features here."""
    kind: str
    at: str
    count: Tuple[int, int] = (1, 1)
    side_h: float = 1.5             # across, in H
    height_h: float = 0.0           # over the floor, in H; 0 is floor to ceiling
    spacing_h: float = 8.0          # between neighbours in rows and along walls
    radius: float = 0.35            # a ring, as a share of the room's short side
    share: float = 0.25             # a dais's floor, as a share of the room's
    chance: float = 1.0             # how likely this line is at all
    poi: str = ""                   # a POI this Feature carries
    by: str = "structure"           # the Scale that moves this line
    at_least: int = 0               # the line is there only from this value of it up


@dataclass
class Placed:
    features: List[Feature] = field(default_factory=list)
    pois: List[POI] = field(default_factory=list)
    dropped: List[str] = field(default_factory=list)


class RoomGrid:
    """The room's floor on a plan grid, with what must stay clear."""

    def __init__(self, room, doors: Sequence, slots: Sequence, body_height: float):
        (self.x0, self.y0, self.z0), (self.x1, self.y1, self.z1) = room.bounds
        self.room, self.h = room, body_height
        self.xs = np.arange(self.x0 + CELL / 2, self.x1, CELL)
        self.ys = np.arange(self.y0 + CELL / 2, self.y1, CELL)
        gx, gy = np.meshgrid(self.xs, self.ys, indexing="ij")
        self.gx, self.gy = gx, gy
        self.floor = (room.outline.contains(np.c_[gx.ravel(), gy.ravel()]).reshape(gx.shape)
                      if room.outline is not None else np.ones(gx.shape, bool))
        self.taken = np.zeros(gx.shape, bool)
        self.raised = np.zeros(gx.shape, bool)      # what's taken by a dais you can walk over
        for s in slots:
            self.taken |= self.rect(s)
        self.door_cells = [self._door_cell(d) for d in doors]
        self.spine = self._spine(doors)

    def rect(self, r) -> np.ndarray:
        return (self.gx >= r[0]) & (self.gx <= r[2]) & (self.gy >= r[1]) & (self.gy <= r[3])

    def _door_cell(self, door) -> Tuple[int, int]:
        side, c0, c1 = door
        mid = (c0 + c1) / 2
        px, py = {"N": (mid, self.y1), "S": (mid, self.y0), "E": (self.x1, mid), "W": (self.x0, mid)}[side]
        cand = np.argwhere(self.floor)
        d = np.hypot(self.xs[cand[:, 0]] - px, self.ys[cand[:, 1]] - py)
        c = cand[int(d.argmin())]
        return int(c[0]), int(c[1])

    def _path(self, a: Tuple[int, int], b: Tuple[int, int]) -> List[Tuple[int, int]]:
        """A shortest way over the floor from cell a to cell b."""
        came: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {a: None}
        queue = deque([a])
        nx, ny = self.floor.shape
        while queue:
            cur = queue.popleft()
            if cur == b:
                break
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (cur[0] + dx, cur[1] + dy)
                if 0 <= nb[0] < nx and 0 <= nb[1] < ny and self.floor[nb] and nb not in came:
                    came[nb] = cur
                    queue.append(nb)
        out = []
        cur = b if b in came else None
        while cur is not None:
            out.append(cur)
            cur = came[cur]
        return out

    def _spine(self, doors) -> np.ndarray:
        """Paths joining the doors, a corridor's clear width wide, and each door's own strip
        going in. The entrance room keeps its middle clear too: the spawn stands there."""
        spine = np.zeros(self.floor.shape, bool)
        for a, b in zip(self.door_cells, self.door_cells[1:]):
            for c in self._path(a, b):
                spine[c] = True
        for c in self.door_cells:
            spine[c] = True
        if self.room.role == "entrance":
            cx, cy = (self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2
            cand = np.argwhere(self.floor)
            mid = cand[int(np.hypot(self.xs[cand[:, 0]] - cx, self.ys[cand[:, 1]] - cy).argmin())]
            spine[int(mid[0]), int(mid[1])] = True
        reach = max(1, int(round(SPINE_HALF_H * self.h / CELL)))
        spine = binary_dilation(spine, iterations=reach)
        for door in doors:
            spine |= self.rect(self.door_clear(door))
        return spine & self.floor

    def door_clear(self, door) -> Tuple[float, float, float, float]:
        """A door's own strip going in, (x0, y0, x1, y1): the door's width, two bodies and a
        step deep. Part of the Spine."""
        side, c0, c1 = door
        depth = 2 * self.h + 2.0
        if side in "NS":
            y = self.y1 - depth if side == "N" else self.y0
            return (c0, y, c1, y + depth)
        x = self.x1 - depth if side == "E" else self.x0
        return (x, c0, x + depth, c1)

    def footprint(self, plan) -> np.ndarray:
        pts = np.array(plan)
        lo, hi = pts.min(axis=0), pts.max(axis=0)
        return self.rect((lo[0], lo[1], hi[0], hi[1]))

    def clear_for(self, cells: np.ndarray) -> bool:
        """Do these cells stand on floor, clear of walls, the Spine and what's placed?"""
        if not cells.any():
            return False
        margin = max(1, int(round(WALL_MARGIN_H * self.h / CELL)))
        inner = ~binary_dilation(np.pad(~self.floor, 1, constant_values=True), iterations=margin)[1:-1, 1:-1]
        return bool((cells <= inner).all() and not (cells & (self.spine | self.taken)).any())

    def doors_stay_joined(self, cells: np.ndarray, raised: bool = False) -> bool:
        """With these cells taken too, are the doors joined, and no floor cut off? As the
        gate has it: a body's radius from walls and solids. Floor behind a dais isn't cut off,
        since you can walk over the dais to it."""
        reach = int(math.ceil(BODY_RADIUS / CELL)) + 1      # a cell stricter than the gate
        walls = np.pad(~self.floor, 1, constant_values=True)
        placed = binary_dilation(self.taken | cells, iterations=reach)
        # The Spine reaches the doors, which stand in the wall's own margin.
        free = (self.floor & ~placed) & (~binary_dilation(walls, iterations=reach)[1:-1, 1:-1] | self.spine)
        labels, _n = label(free)
        marks = {int(labels[c]) for c in self.door_cells}
        if len(marks) > 1 or 0 in marks:
            return False
        over = self.raised | cells if raised else self.raised
        labels, n = label(free | (binary_dilation(over, iterations=reach) & self.floor) if over.any() else free)
        marks = {int(labels[c]) for c in self.door_cells}
        joined = next(iter(marks), 0)
        sizes = np.bincount(labels[free], minlength=n + 1)
        return not any(sizes[k] * CELL * CELL >= POCKET for k in range(1, n + 1) if k != joined)


def _door_side(grid: RoomGrid) -> Tuple[float, float]:
    """A unit vector from the doors toward the far side of the room."""
    cx, cy = (grid.x0 + grid.x1) / 2, (grid.y0 + grid.y1) / 2
    if not grid.door_cells:
        return (0.0, 1.0)
    dx = np.mean([grid.xs[c[0]] for c in grid.door_cells]) - cx
    dy = np.mean([grid.ys[c[1]] for c in grid.door_cells]) - cy
    n = math.hypot(dx, dy)
    return (-dx / n, -dy / n) if n > 1e-6 else (0.0, 1.0)


def _spots(grid: RoomGrid, ask: Ask, count: int, rng: random.Random) -> List[Tuple[float, float]]:
    """Where an arrangement would put ``count`` things, best first."""
    cx, cy = (grid.x0 + grid.x1) / 2, (grid.y0 + grid.y1) / 2
    w, d = grid.x1 - grid.x0, grid.y1 - grid.y0
    if ask.at == "centre":
        # As near the middle as the way through allows.
        step = ask.side_h * grid.h
        return [(cx, cy)] + [(cx + sx * step, cy + sy * step) for sx, sy in
                             ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, 1), (1, -1), (-1, -1))]
    if ask.at == "far_end":
        fx, fy = _door_side(grid)
        return [(cx + fx * w * s / 2, cy + fy * d * s / 2) for s in (0.7, 0.55, 0.4, 0.25)]
    if ask.at == "ring":
        r = ask.radius * min(w, d)
        start = rng.uniform(0.0, 2 * math.pi / max(count, 1))
        return [(cx + r * math.cos(start + 2 * math.pi * k / count),
                 cy + r * math.sin(start + 2 * math.pi * k / count)) for k in range(count)]
    if ask.at == "corners":
        # Further in if a shaped room has no floor that far out.
        return [(cx + sx * w * s, cy + sy * d * s) for s in (0.32, 0.25, 0.18)
                for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    if ask.at == "rows":
        step = ask.spacing_h * grid.h
        if w >= d:
            n = max(1, int(w * 0.8 // step))
            run = [cx + (k - (n - 1) / 2) * step for k in range(n)]
            return [(x, cy + s * d * 0.28) for x in run for s in (-1, 1)]
        n = max(1, int(d * 0.8 // step))
        run = [cy + (k - (n - 1) / 2) * step for k in range(n)]
        return [(cx + s * w * 0.28, y) for y in run for s in (-1, 1)]
    if ask.at == "along_wall":
        step = ask.spacing_h * grid.h
        fx, fy = _door_side(grid)
        if abs(fx) >= abs(fy):
            x = cx + math.copysign(w * 0.36, fx)
            n = max(1, int(d * 0.8 // step))
            return [(x, cy + (k - (n - 1) / 2) * step) for k in range(n)]
        y = cy + math.copysign(d * 0.36, fy)
        n = max(1, int(w * 0.8 // step))
        return [(cx + (k - (n - 1) / 2) * step, y) for k in range(n)]
    # scatter: any floor; more tries than asked, since many won't fit
    cand = np.argwhere(grid.floor & ~grid.spine & ~grid.taken)
    if len(cand) == 0:
        return []
    picks = [cand[rng.randrange(len(cand))] for _ in range(count * 6)]
    return [(float(grid.xs[p[0]]), float(grid.ys[p[1]])) for p in picks]


def _open_floor_near(grid: RoomGrid, x: float, y: float) -> Optional[Tuple[float, float]]:
    """The open floor nearest a point, a body's radius from walls and what's placed."""
    reach = int(math.ceil(BODY_RADIUS / CELL)) + 1
    walls = binary_dilation(np.pad(~grid.floor, 1, constant_values=True), iterations=reach)[1:-1, 1:-1]
    free = grid.floor & ~walls & ~binary_dilation(grid.taken, iterations=reach)
    cand = np.argwhere(free)
    if len(cand) == 0:
        return None
    k = int(np.hypot(grid.xs[cand[:, 0]] - x, grid.ys[cand[:, 1]] - y).argmin())
    return float(grid.xs[cand[k, 0]]), float(grid.ys[cand[k, 1]])


def _lift_at(room, x: float, y: float) -> float:
    """The floor's rise at a point."""
    return 0.0 if room.outline is None else float(room.outline.rise_at(x, y))


def _local_lift(room, plan) -> float:
    """The most a moving floor rises under this footprint: a solid's top is measured from there."""
    o = room.outline
    if o is None or not o.lift:
        return 0.0
    pts = np.array(plan)
    lo, hi = pts.min(axis=0) - 16.0, pts.max(axis=0) + 16.0
    v = np.array(o.verts)
    near = (v[:, 0] >= lo[0]) & (v[:, 0] <= hi[0]) & (v[:, 1] >= lo[1]) & (v[:, 1] <= hi[1])
    return float(np.array(o.lift)[near].max()) if near.any() else 0.0


def _local_drop(room, plan) -> float:
    o = room.outline
    if o is None or not o.drop:
        return 0.0
    pts = np.array(plan)
    lo, hi = pts.min(axis=0) - 16.0, pts.max(axis=0) + 16.0
    v = np.array(o.verts)
    near = (v[:, 0] >= lo[0]) & (v[:, 0] <= hi[0]) & (v[:, 1] >= lo[1]) & (v[:, 1] <= hi[1])
    return float(np.array(o.drop)[near].max()) if near.any() else 0.0


def _dais(grid: RoomGrid, ask: Ask, form: str, rng: random.Random) -> Optional[Feature]:
    """A raised floor against a wall, its steps toward the room, on the side furthest from the
    doors that it fits. Shrinks to fit."""
    fx, fy = _door_side(grid)
    w, d = grid.x1 - grid.x0, grid.y1 - grid.y0
    cx, cy = (grid.x0 + grid.x1) / 2, (grid.y0 + grid.y1) / 2
    rise = (ask.height_h or DAIS_RISE_H) * grid.h
    margin = WALL_MARGIN_H * grid.h
    door_x = [grid.xs[c[0]] for c in grid.door_cells] or [cx]
    door_y = [grid.ys[c[1]] for c in grid.door_cells] or [cy]

    def clearance(side: str) -> float:
        """How far this side's wall stands from the nearest door."""
        if side in "NS":
            y = grid.y1 if side == "N" else grid.y0
            return float(min(abs(y - v) for v in door_y))
        x = grid.x1 if side == "E" else grid.x0
        return float(min(abs(x - v) for v in door_x))

    tries = [(far, inset, scale) for far in sorted("NSEW", key=lambda f: (-clearance(f), f))
             for inset in (1, 2, 3) for scale in (1.0, 0.8, 0.65, 0.5, 0.35)]
    for far, inset, scale in sorted(tries, key=lambda t: t[1]):
        along_x = far in "NS"
        toward = {"N": "S", "S": "N", "E": "W", "W": "E"}[far]
        area = ask.share * w * d * scale
        run = (w if along_x else d) * 0.6 * math.sqrt(scale)
        deep = area / run
        off = margin * inset        # further in if a shaped room's wall is in the way
        if along_x:
            a = grid.y1 - off if far == "N" else grid.y0 + off + deep
            box = (cx - run / 2, a - deep, cx + run / 2, a)
        else:
            a = grid.x1 - off if far == "E" else grid.x0 + off + deep
            box = (a - deep, cy - run / 2, a, cy + run / 2)
        plan = dais_plan(form, box, toward, rng)
        height = _local_lift(grid.room, plan) + rise
        if grid.room.height - _local_drop(grid.room, plan) - height < MIN_HEAD_H * grid.h:
            continue
        # Its steps need floor too: the footprint grows toward the room by their run.
        run_out = _steps_run(height)
        grown = (box[0] - (run_out if toward == "W" else 0), box[1] - (run_out if toward == "S" else 0),
                 box[2] + (run_out if toward == "E" else 0), box[3] + (run_out if toward == "N" else 0))
        cells = grid.rect(grown)
        if grid.clear_for(cells) and grid.doors_stay_joined(cells, raised=True):
            grid.taken |= cells
            grid.raised |= cells
            return Feature(DAIS, plan, height=round(height, 3), steps_side=toward)
    return None


def _steps_run(height: float) -> float:
    from .geometry import RISER_CAP, TREAD_DEPTH, dais_steps
    return dais_steps(height) * TREAD_DEPTH if height > RISER_CAP else 0.0


def place(room, doors: Sequence, slots: Sequence, asks: Sequence[Ask], body_height: float,
          form: str, rng: random.Random) -> Placed:
    """Stand a recipe's Features in a finished room. Touches nothing else about it."""
    grid = RoomGrid(room, doors, slots, body_height)
    out = Placed()
    dais_at: Optional[Tuple[float, float, float, int]] = None
    for ask in asks:
        if ask.chance < 1.0 and rng.random() >= ask.chance:
            continue
        count = rng.randint(*ask.count)
        if count <= 0:
            continue
        if ask.kind == DAIS:
            feat = _dais(grid, ask, form, rng)
            if feat is None:
                out.dropped.append(f"{ask.kind} at {ask.at}")
                continue
            out.features.append(feat)
            pts = np.array(feat.plan)
            mx, my = pts.mean(axis=0)
            dais_at = (float(mx), float(my), feat.height, len(out.features) - 1)
            if ask.poi:
                out.pois.append(POI(ask.poi, float(mx), float(my), grid.z0 + feat.height,
                                    feature=len(out.features) - 1))
            continue
        side = ask.side_h * body_height
        placed = 0
        if ask.at == "on_dais":
            spots = [] if dais_at is None else [(dais_at[0], dais_at[1])]
        else:
            spots = _spots(grid, ask, count, rng)
        for x, y in spots:
            if placed >= count:
                break
            plan = solid_plan(form, x, y, side, rng)
            if ask.at == "on_dais":
                # A dais's floor is its own: it stands on the top, and rises from there.
                base = dais_at[2]
                height = base + (ask.height_h * body_height or body_height)
                out.features.append(Feature(ask.kind, plan, height=round(height, 3)))
                placed += 1
                continue
            cells = grid.footprint(plan)
            if not grid.clear_for(cells) or not grid.doors_stay_joined(cells):
                continue
            height = 0.0 if ask.kind == PILLAR or not ask.height_h else \
                _local_lift(room, plan) + ask.height_h * body_height
            if ask.kind != PILLAR and height <= 0:
                height = _local_lift(room, plan) + body_height
            grid.taken |= cells
            out.features.append(Feature(ask.kind, plan, height=round(height, 3)))
            placed += 1
            if ask.poi:
                # A solid's top isn't floor: its POI stands on open floor beside it.
                beside = _open_floor_near(grid, x, y)
                if beside is None:
                    out.dropped.append(f"{ask.poi} POI at {ask.at}")
                else:
                    out.pois.append(POI(ask.poi, beside[0], beside[1], grid.z0 + _lift_at(room, *beside),
                                        feature=len(out.features) - 1))
        if placed < count and ask.at not in ("scatter", "corners", "rows", "along_wall"):
            out.dropped.append(f"{count - placed} {ask.kind} at {ask.at}")
    return out


# ---------------------------------------------------------------------------
# Recipes as data (rules/rooms/layouts.toml)
# ---------------------------------------------------------------------------

LAYOUTS_FILE = Path(__file__).resolve().parent.parent / "rules" / "rooms" / "layouts.toml"
AS_MANY_AS_FIT = 24
POI_PURPOSES: Tuple[str, ...] = ("boss", "treasure", "altar", "guard", "ambush", "view")
_NUMBERS = {"side_h": (0.5, 8.0), "height_h": (0.0, 4.0), "spacing_h": (2.0, 30.0), "radius": (0.05, 0.5),
            "share": (0.05, 0.5), "chance": (0.0, 1.0)}


@dataclass(frozen=True)
class RoomLayouts:
    types: Dict[str, Tuple[Ask, ...]]
    kinds: Dict[str, Tuple[Ask, ...]]
    default: Tuple[Ask, ...]
    clutter: Tuple[Ask, ...] = ()       # lines every room takes after its own

    def recipe_for(self, semantic_type: str, kind: str) -> Tuple[str, Tuple[Ask, ...]]:
        """(which recipe, its lines): the room type's, else the kind's, else the default."""
        if semantic_type in self.types:
            return f"type:{semantic_type}", self.types[semantic_type] + self.clutter
        if kind in self.kinds:
            return f"kind:{kind}", self.kinds[kind] + self.clutter
        return "default", self.default + self.clutter


def _asks(chk, raw, where: str) -> Tuple[Ask, ...]:
    tbl = chk.table(raw, "recipes", where, "{ features = [ { kind = \"pillar\", at = \"rows\" } ] }")
    if tbl is None:
        return ()
    chk.keys(tbl, where, ("features",), required=("features",))
    lines = chk.array(tbl.get("features", []), where, "features", "[ { kind = \"pillar\", at = \"rows\" } ]") or []
    allowed = ("kind", "at", "count", "poi", "by", "from") + tuple(_NUMBERS)
    out = []
    for i, line in enumerate(lines):
        p = f"features[{i}]."
        t = chk.table(line, where, f"features[{i}]", "{ kind = \"pillar\", at = \"rows\" }")
        if t is None:
            continue
        chk.keys(t, where, allowed, required=("kind", "at"), prefix=p)
        kind, at = t.get("kind"), t.get("at")
        if kind is not None and kind not in FEATURE_KINDS:
            chk.fail(where, p + "kind", kind, _one_of(FEATURE_KINDS))
        if at is not None and at not in ARRANGEMENTS:
            chk.fail(where, p + "at", at, _one_of(ARRANGEMENTS))
        # Rows and walls fill their length unless a recipe says how many.
        count = t.get("count", AS_MANY_AS_FIT if at in ("rows", "along_wall") else 1)
        if isinstance(count, int) and not isinstance(count, bool):
            count = [count, count]
        if not (isinstance(count, list) and len(count) == 2 and all(isinstance(c, int) for c in count)
                and 0 <= count[0] <= count[1] <= 24):
            chk.fail(where, p + "count", t.get("count"), "a number or [low, high], from 0 to 24")
            count = [1, 1]
        values = {}
        for key, (lo, hi) in _NUMBERS.items():
            if key in t:
                if not _is_number(t[key]) or not lo <= t[key] <= hi:
                    chk.fail(where, p + key, t[key], f"a number from {lo} to {hi}")
                else:
                    values[key] = float(t[key])
        poi = t.get("poi", "")
        if poi and poi not in POI_PURPOSES:
            chk.fail(where, p + "poi", poi, _one_of(POI_PURPOSES))
        by = t.get("by", STRUCTURE)
        if by not in READ_BY:
            chk.fail(where, p + "by", by, _one_of(READ_BY))
        least = t.get("from", 0)
        if not isinstance(least, int) or isinstance(least, bool) or not 0 <= least <= 10:
            chk.fail(where, p + "from", least, "a whole number from 0 to 10")
            least = 0
        if kind in FEATURE_KINDS and at in ARRANGEMENTS:
            out.append(Ask(kind, at, count=tuple(count), poi=poi, by=by, at_least=least, **values))
    return tuple(out)


def load_layouts(path=LAYOUTS_FILE) -> RoomLayouts:
    """Load and check the recipes; raises ``RuleSetError`` with every failure."""
    path = Path(path)
    chk = _Checker(path.name)
    data = _read_toml(path, chk)
    chk.raise_if_failed()
    chk.keys(data, "top level", ("default", "kinds", "types", "clutter"), required=("default", "types"))
    kinds = {}
    for name, raw in (data.get("kinds") or {}).items():
        if name not in ROOM_KINDS:
            chk.fail("kinds", name, "an unknown kind", _one_of(ROOM_KINDS), raw=True)
        kinds[name] = _asks(chk, raw, f"kinds.{name}")
    types = {}
    for name, raw in (data.get("types") or {}).items():
        if name not in ROOM_TYPES:
            chk.fail("types", name, "an unknown room type", _one_of(sorted(ROOM_TYPES)), raw=True)
        types[name] = _asks(chk, raw, f"types.{name}")
    for name in sorted(set(ROOM_TYPES) - set(types)):
        chk.fail("types", name, "nothing", "a recipe for every room type (features = [] is one)", raw=True)
    default = _asks(chk, data.get("default", {}), "default")
    clutter = _asks(chk, data["clutter"], "clutter") if "clutter" in data else ()
    chk.raise_if_failed()
    return RoomLayouts(types, kinds, default, clutter)


# ---------------------------------------------------------------------------
# Standing them in a build
# ---------------------------------------------------------------------------

#: Features control -> (scale on a line's chance, scale on its count).
DENSITIES: Dict[str, Tuple[float, float]] = {"none": (0.0, 0.0), "sparse": (0.5, 0.5), "normal": (1.0, 1.0),
                                             "dense": (1.5, 1.5)}
DEFAULT_DENSITY = "normal"
AS_WRITTEN = 5       # the value of a Scale at which a recipe stands as written
STRUCTURE, CLUTTER = "structure", "clutter"
READ_BY: Tuple[str, ...] = (STRUCTURE, CLUTTER)
#: The form a solid takes in each wall style's complex.
FORM_OF_COMPLEX: Dict[str, str] = {"grid": "square", "facet": "cut", "voronoi": "rough"}
#: Prop hints that name structure a Feature now stands for.
STRUCTURAL: Dict[str, Tuple[str, ...]] = {DAIS: ("dais", "platform"), PILLAR: ("pillar",),
                                          PLINTH: ("altar", "slab", "forge", "sarcophag", "pedestal")}


def _scaled(asks: Sequence[Ask], density: str, scales: Optional[Mapping[str, int]] = None) -> List[Ask]:
    """The recipe for this room: a value of ``AS_WRITTEN`` on a line's Scale is the line as
    written, 0 nothing, 10 twice as much. A line under its threshold isn't there at all."""
    chance, count = DENSITIES[density]
    out = []
    for a in asks:
        value = (scales or {}).get(a.by, AS_WRITTEN)
        if value < a.at_least:
            continue
        k = value / AS_WRITTEN
        lo, hi = a.count
        out.append(replace(a, chance=min(1.0, a.chance * chance * k),
                           count=(int(round(lo * count * k)) if lo > 1 else lo,
                                  max(1, int(round(hi * count * k))) if hi else 0)))
    return out


def _floor_poi(grid: RoomGrid, purpose: str, taken: Sequence[Feature]) -> Optional[POI]:
    """A POI on open floor, as far from the doors as the room allows."""
    solid = grid.taken.copy()
    for f in taken:
        solid |= grid.footprint(f.plan)
    free = grid.floor & ~binary_dilation(solid, iterations=max(1, int(math.ceil(BODY_RADIUS / CELL))))
    cand = np.argwhere(free)
    if len(cand) == 0:
        return None
    door_x = np.array([grid.xs[c[0]] for c in grid.door_cells] or [(grid.x0 + grid.x1) / 2])
    door_y = np.array([grid.ys[c[1]] for c in grid.door_cells] or [(grid.y0 + grid.y1) / 2])
    d = np.min(np.hypot(grid.xs[cand[:, 0]][:, None] - door_x, grid.ys[cand[:, 1]][:, None] - door_y), axis=1)
    x, y = grid.xs[cand[int(d.argmax()), 0]], grid.ys[cand[int(d.argmax()), 1]]
    return POI(purpose, float(x), float(y), grid.z0 + _lift_at(grid.room, x, y))


def apply_features(spec, complex_name: str, seed: int, density: str = DEFAULT_DENSITY,
                   extra_doors=None) -> None:
    """Stand each room's recipe in it, last, after its walls. Each room draws from its own
    stream, so this moves nothing about the layout, and ``none`` adds nothing at all.
    ``layout.rooms`` records what each room took and what it dropped."""
    from .geometry import _bridge_slots, room_doors
    from .semantics import body_height

    layouts = load_layouts()
    height = body_height(spec.dungeon_race)
    records = spec.layout["rooms"]
    spec.layout["features"] = density
    if density == "none":
        return
    deepest = max((r.graph_depth for r in spec.rooms if r.role == "deadend"), default=-1)
    for room in spec.rooms:
        record = records.setdefault(room.id, {})
        form = FORM_OF_COMPLEX[record.get("complex", complex_name)]
        name, asks = layouts.recipe_for(room.semantic_type, record.get("kind", room.kind))
        rng = random.Random(f"{seed}:{room.id}:features")
        doors = room_doors(room, spec, (extra_doors or {}).get(room.id))
        placed = place(room, doors, _bridge_slots(room, spec), _scaled(asks, density, record.get("scales")), height, form, rng)
        room.features, room.pois = placed.features, placed.pois
        grid = RoomGrid(room, doors, _bridge_slots(room, spec), height)
        want = []
        if room.role == "climax" and not any(p.purpose == "boss" for p in room.pois):
            want.append("boss")
        if room.role == "deadend" and room.graph_depth == deepest and deepest >= 0 \
                and not any(p.purpose == "treasure" for p in room.pois):
            want.append("treasure")
        for purpose in want:
            poi = _floor_poi(grid, purpose, room.features)
            if poi is not None:
                room.pois.append(poi)
        kinds = {f.kind for f in room.features}
        room.prop_hints = [h for h in room.prop_hints
                           if not any(w in h for k in kinds for w in STRUCTURAL.get(k, ()))]
        record.update(room_layout=name, features=[f.kind for f in room.features], dropped=placed.dropped,
                      pois=[{"purpose": p.purpose, "x": round(p.x, 1), "y": round(p.y, 1), "z": round(p.z, 1),
                             "feature": p.feature} for p in room.pois])


__all__ = ["ARRANGEMENTS", "Ask", "DENSITIES", "DEFAULT_DENSITY", "FORM_OF_COMPLEX", "apply_features", "BOULDER", "LAYOUTS_FILE", "PILLAR", "PLINTH", "POI_PURPOSES", "Placed",
           "RoomGrid", "RoomLayouts", "load_layouts", "place"]
