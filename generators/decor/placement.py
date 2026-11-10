"""Decor placement in rooms (roadmap step 11, Reqs 5, 6, 8, 13.4; design "Placement").

``place(context, ...)`` decorates one :class:`~generators.room_context.RoomContext` and reads
nothing else from the room stage (Req 13.1, P13): no ZoneSpec, mesh or zone. Its inputs are
the context, the decor rules (``generators/decor/rules.py``) and the catalogue
(``generators/decor/catalogue.py``); its output is a :class:`Decorated`: the Props, with every
line that couldn't be met recorded as a :class:`Drop` and a reason. Placement never fails.

**Order** (design "Placement"), each room on its own random stream salted with ``decor``, the
seed and the room's id, so geometry never depends on Props (Req 6.4): **Dressing** at each POI
(Req 8), then the recipe's **Groups**, then single **Props**, then **debris** (the lines Clutter
moves). A room drawn ``bare`` (rules ``bare``) takes only its Dressing.

**Models.** A line asks for a kind, or alternatives best first, at a Mount; the placer takes a
``use = "yes"`` static model of the first kind that has one, from the room's Sets best first
(race, theme, zone type, then neutral: ``SetRules.sets_for``). The first culture a room takes
binds it: after that, only Sets that may share a room with every Set already in it
(``SetRules.may_share``) are eligible (Req 5). One model is chosen per line (a row of benches
matches), and per Group member.

**Spots** come from the context's grid and wall faces:

- **floor** Props stand on reached floor, inside the room, off the Spine, every Throat and door
  clear zone, and off Features, except a recipe's ``on_dais`` line and a POI's Dressing when the
  POI stands on a dais (Req 6.1). A footprint is the model's plan (``measured`` w along its own
  X, d along Y), turned by its yaw. Its floor may rise at most ``FLAT`` across it; it stands at
  the lowest. It must fit under the ceiling;
- **along the wall** (``along_wall``, ``corners``, ``by_door``, ``rows``): backed to a wall face,
  its back half a plan-depth off it, turned so its front faces the room;
- **wall** Props hang on a wall face at the height stock uses for the model (observed ``over``,
  its p50) and stock's distance off the wall (observed ``wall``), never within ``FRAME`` of a
  door's clear zone and never on a lintel (a wall face whose foot is above the floor in front of
  it). Wall faces are the context's samples of the BUILT wall mesh, with each sample's own
  bottom and top, so a torch on a rough wall sits where that wall stands (design Risks). Wall
  lights keep ``LIGHT_SPACING`` (finding 1: 38 u dungeon, 26 u city; a room keeps
  ``ROOM_LIGHT_GAP`` of it);
- **ceiling** Props hang where the ceiling is at least the model's length plus ``HEAD_HEIGHT``
  over the floor, so they never block (Req 6.2);
- **Groups** are placed whole or dropped whole (Req 6.3): the anchor at its arrangement, its
  members round it, in a row with it, beside it or stacked on it (raised).

**Yaw** is step 10's decision 10: radians counter-clockwise from +X, and a model's front faces
+X at yaw 0. A wall or along-wall Prop's yaw is its wall's into-room normal, so its back (-X)
is to the wall: stock's own wall torches agree (TORCHPOINT in Qeynos catacombs and Sol A stand
with the wall at local -X and the flame 2.3 u off it).

**The room check** (Req 13.4): decor checks its own result against the context, by the gate's
rules (``analyzer/footprints.py``, mirrored here, not imported): a Prop blocks where it is
collidable between ``STEP_UP`` and ``HEAD_HEIGHT`` over the floor, grown by the player's
half-width; reached floor must stay joined to the doors (nothing cut off), each door must stay
reached, and each POI keeps reached floor within ``POI_REACH``. Every placement is checked
before it's kept (``check`` runs the same test on a finished result).

**Corridors** get wall lights by spacing and nothing else (design "Placement"): a context with
``source = "corridor"`` takes a light every ``LIGHT_SPACING`` along its walls.
"""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

from generators.decor.catalogue import Catalogue, Model
from generators.decor.rules import (BARE, DEFAULT_CONTROL, MOUNTS_FILLING, NEUTRAL, DecorRules, Group, Line,
                                    draw_count)
from generators.room_context import STEP_UP, RoomContext, WallFace

#: The gate's figures (archive decision 9 of step 10, ``analyzer/footprints.py``), mirrored.
PLAYER_HALF_WIDTH = 1.5
HEAD_HEIGHT = 8.0
POI_REACH = PLAYER_HALF_WIDTH + 2.0
#: A wall is kept clear this far each side of a door's clear zone (u): the opening's frame.
FRAME = 3.0
#: Wall lights' spacing (finding 1: a wall light's nearest wall light, p50 over zones).
LIGHT_SPACING: Dict[str, float] = {"city": 26.0}
DEFAULT_LIGHT_SPACING = 38.0
#: In a room, wall lights stand at least this share of the spacing apart.
ROOM_LIGHT_GAP = 0.8
#: The most a floor Prop's ground may rise across its footprint (u).
FLAT = 2.0
#: Spots tried per item before it drops; anchor spots tried per Group.
TRIES = 24
GROUP_TRIES = 8
#: Smaller models tried when an item's model finds no spot, before it drops.
FALLBACKS = 2
#: Gap between a Prop's back and its wall (u), and between neighbours in a row or Group.
WALL_GAP = 0.5
GAP = 1.0
#: Defaults for a model the survey never saw placed: height of a wall Prop over the floor.
WALL_HEIGHT = {"light": 5.5, "hanging": 8.0}
DEFAULT_WALL_HEIGHT = 6.0
#: Steps, in the order a room takes them.
STEPS: Tuple[str, ...] = ("dressing", "group", "prop", "debris")
CORRIDOR = "corridor"


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Prop:
    """One placed model. ``x, y, z`` is its origin (world units), ``yaw`` radians CCW from +X
    (front faces +X at 0). ``w, d, h, below`` are its measured plan and height, scaled.
    ``blocks``: it stands in the player's way (collidable between step and head height)."""
    key: str
    kind: str
    category: str
    mount: str              # floor, wall, ceiling or raised
    set: str
    x: float
    y: float
    z: float
    yaw: float
    scale: float
    w: float
    d: float
    h: float
    below: float
    blocks: bool
    step: str               # dressing, group, prop, debris (a corridor's lights: prop)
    line: str               # the recipe line it fills: "rooms.toml types.barracks props[0]"
    at: str                 # the line's arrangement
    poi: Optional[int] = None
    group: Optional[int] = None

    @property
    def light(self) -> bool:
        return self.category == "light"

    def to_dict(self) -> dict:
        out = asdict(self)
        for k in ("x", "y", "z", "yaw", "scale", "w", "d", "h", "below"):
            out[k] = round(float(out[k]), 3)
        return out


@dataclass(frozen=True)
class Drop:
    """A line (or one item of it) that couldn't be placed, and why: ``no model`` (no usable
    model of its kinds at its Mount in the room's Sets), ``no spot``, ``no wall``,
    ``no ceiling``."""
    step: str
    line: str
    what: str               # its kinds ("torch|lantern") or "group:<name>"
    reason: str
    poi: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Decorated:
    room: str
    props: List[Prop] = field(default_factory=list)
    drops: List[Drop] = field(default_factory=list)
    bare: bool = False
    sets: Tuple[str, ...] = ()          # the Sets the room drew from, best first

    def cultures(self) -> Tuple[str, ...]:
        return tuple(sorted({p.set for p in self.props if p.set != NEUTRAL}))

    def to_dict(self) -> dict:
        return {"room": self.room, "bare": self.bare, "props": [p.to_dict() for p in self.props],
                "drops": [d.to_dict() for d in self.drops]}


# ---------------------------------------------------------------------------
# A model's size
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Size:
    w: float                # along the model's X (its front), scaled
    d: float                # along its Y
    h: float
    below: float
    scale: float
    over: Optional[float]   # stock's height over the floor (p50), scaled with the room: as stock
    wall: Optional[float]   # stock's distance off the wall (p50)


def size_of(model: Model) -> Size:
    m = model.measured or {}
    obs = model.observed or {}
    sc = obs.get("scale") or [1.0, 1.0, 1.0]
    s = float(min(2.0, max(0.5, sc[1] if len(sc) > 1 else 1.0)))
    over = obs.get("over")
    wall = obs.get("wall")
    return Size(w=max(0.2, float(m.get("w", 2.0))) * s, d=max(0.2, float(m.get("d", 2.0))) * s,
                h=max(0.1, float(m.get("h", 2.0))) * s, below=max(0.0, float(m.get("below", 0.0))) * s,
                scale=s, over=float(over[1]) if over and len(over) > 1 else None,
                wall=float(wall[1]) if wall and len(wall) > 1 else None)


def _blocking(model: Model) -> bool:
    return model.tags.collision != "passable"


# ---------------------------------------------------------------------------
# The room as decor sees it
# ---------------------------------------------------------------------------

@dataclass
class _Face:
    face: WallFace
    floor: float            # the reached floor in front of it
    door: bool              # within FRAME of a door's clear zone
    corner: bool
    by_door: bool           # near a door but clear of its frame


def _in_rect(gx, gy, r, grow=0.0):
    x0, y0, x1, y1 = r
    return (gx >= x0 - grow) & (gx <= x1 + grow) & (gy >= y0 - grow) & (gy <= y1 + grow)


def _rect_dist(x, y, r) -> float:
    x0, y0, x1, y1 = r
    dx = max(x0 - x, 0.0, x - x1)
    dy = max(y0 - y, 0.0, y - y1)
    return math.hypot(dx, dy)


def _in_polygon(gx, gy, plan) -> np.ndarray:
    inside = np.zeros(gx.shape, bool)
    n = len(plan)
    for k in range(n):
        (ax, ay), (bx, by) = plan[k], plan[(k + 1) % n]
        cross = (ay > gy) != (by > gy)
        with np.errstate(divide="ignore", invalid="ignore"):
            at = (bx - ax) * (gy - ay) / (by - ay) + ax
        inside ^= cross & (gx < at)
    return inside


class Room:
    """One context's grid, masks and walls, and what's been placed on them so far."""

    def __init__(self, ctx: RoomContext):
        self.ctx = ctx
        nx, ny = ctx.floor.shape
        self.shape = (nx, ny)
        self.cell = float(ctx.cell)
        self.xs = ctx.origin[0] + np.arange(nx) * self.cell
        self.ys = ctx.origin[1] + np.arange(ny) * self.cell
        self.gx, self.gy = np.meshgrid(self.xs, self.ys, indexing="ij")
        self.floor = ctx.floor
        self.ok = ctx.reached & ~np.isnan(ctx.floor)
        self.ceiling = ctx.ceiling
        door_cells = np.zeros(self.shape, bool)
        throats = np.zeros(self.shape, bool)
        for d in ctx.doors:
            for t in d.throats:
                throats |= _in_rect(self.gx, self.gy, t)
            if d.clear:
                door_cells |= _in_rect(self.gx, self.gy, d.clear)
        #: Kept clear of every floor Prop: the Spine, the Throats and the doors' clear zones;
        #: of Dressing, the Spine and the clear zones (a POI at a Throat's end is dressed there).
        self.keep = ctx.spine | throats | door_cells
        self.keep_dressing = ctx.spine | door_cells
        self.feature = np.zeros(self.shape, bool)
        self.dais = np.zeros(self.shape, bool)
        self.feature_masks: List[np.ndarray] = []
        for f in ctx.features:
            m = _in_polygon(self.gx, self.gy, f["plan"]) if len(f.get("plan") or ()) >= 3 else \
                np.zeros(self.shape, bool)
            self.feature_masks.append(m)
            if f.get("kind") == "dais":
                self.dais |= m
            self.feature |= m
        # POIs' own spots: no footprint (grown by the player) covers one.
        self.poi_spot = np.zeros(self.shape, bool)
        for p in ctx.pois:
            self.poi_spot |= np.hypot(self.gx - p["x"], self.gy - p["y"]) <= self.cell * 0.75
        self.occupied = np.zeros(self.shape, bool)
        self.blocked = np.zeros(self.shape, bool)
        self.wall_props: List[Tuple[float, float, float, bool]] = []     # x, y, half-span, light
        self.ceiling_props: List[Tuple[float, float]] = []
        self._graph()
        self.starts = self._starts(door_cells)
        self.before = self._joined(np.zeros(self.shape, bool))
        self.faces = self._faces()

    # -- connectivity (the gate's "reached floor stays joined") ----------------

    def _graph(self) -> None:
        nx, ny = self.shape
        idx = np.arange(nx * ny).reshape(nx, ny)
        f = np.where(self.ok, self.floor, np.nan)
        a, b = [], []
        with np.errstate(invalid="ignore"):
            right = self.ok[:-1, :] & self.ok[1:, :] & (np.abs(f[:-1, :] - f[1:, :]) <= STEP_UP)
            up = self.ok[:, :-1] & self.ok[:, 1:] & (np.abs(f[:, :-1] - f[:, 1:]) <= STEP_UP)
        a.append(idx[:-1, :][right]); b.append(idx[1:, :][right])
        a.append(idx[:, :-1][up]); b.append(idx[:, 1:][up])
        self._ea = np.concatenate(a)
        self._eb = np.concatenate(b)

    def _starts(self, door_cells: np.ndarray) -> np.ndarray:
        s = door_cells & self.ok
        if s.any():
            return s
        for c in self.ctx.clear:            # a Site: reached from its approach's far end
            if c.get("what") == "approach":
                pts = np.argwhere(self.ok)
                if len(pts):
                    d = np.hypot(self.xs[pts[:, 0]] - c["x1"], self.ys[pts[:, 1]] - c["y1"])
                    out = np.zeros(self.shape, bool)
                    out[tuple(pts[int(d.argmin())])] = True
                    return out
        if not self.ok.any():
            return self.ok.copy()
        # No door and no approach: the largest reached piece.
        n, lab = self._components(np.zeros(self.shape, bool))
        lab = lab.reshape(self.shape)
        counts = np.bincount(lab[self.ok])
        return self.ok & (lab == int(counts.argmax()))

    def _components(self, blocked: np.ndarray):
        nx, ny = self.shape
        free = (self.ok & ~blocked).ravel()
        keep = free[self._ea] & free[self._eb]
        m = csr_matrix((np.ones(int(keep.sum()), np.int8), (self._ea[keep], self._eb[keep])),
                       shape=(nx * ny, nx * ny))
        return connected_components(m, directed=False)

    def _joined(self, blocked: np.ndarray) -> np.ndarray:
        """Reached floor not blocked and joined to a door (or a Site's approach)."""
        _n, lab = self._components(blocked)
        lab = lab.reshape(self.shape)
        free = self.ok & ~blocked
        good = np.unique(lab[self.starts & free])
        return free & np.isin(lab, good)

    def problems(self, blocked: np.ndarray) -> List[str]:
        """What a blocked mask breaks: floor cut off, a door or a POI no longer reached."""
        after = self._joined(blocked)
        out = []
        cut = self.before & ~blocked & ~after
        if cut.any():
            i, j = (int(v[0]) for v in np.nonzero(cut))
            out.append(f"cuts off {int(cut.sum())} floor cells at ({self.xs[i]:.0f}, {self.ys[j]:.0f})")
        for k, d in enumerate(self.ctx.doors):
            if d.clear is None:
                continue
            c = _in_rect(self.gx, self.gy, d.clear) & self.before
            if c.any() and not (c & after).any():
                out.append(f"door {k} ({d.side}) no longer reached")
        for k, p in enumerate(self.ctx.pois):
            near = np.hypot(self.gx - p["x"], self.gy - p["y"]) <= POI_REACH + self.cell / 2
            if (near & self.before).any() and not (near & after).any():
                out.append(f"POI {k} ({p.get('purpose')}) no longer reached")
        return out

    # -- footprints -------------------------------------------------------------

    def rect_cells(self, x: float, y: float, yaw: float, w: float, d: float, grow: float = 0.0,
                   clip: bool = False):
        """The grid cells whose middles lie in a w x d plan centred at (x, y), turned by
        ``yaw`` and grown by ``grow``; None when any of it lies off the grid (``clip``: the
        cells on it, None only when its middle is off it)."""
        a, b = w / 2 + grow, d / 2 + grow
        r = math.hypot(a, b) + self.cell
        i0 = int(math.floor((x - r - self.xs[0]) / self.cell))
        i1 = int(math.ceil((x + r - self.xs[0]) / self.cell))
        j0 = int(math.floor((y - r - self.ys[0]) / self.cell))
        j1 = int(math.ceil((y + r - self.ys[0]) / self.cell))
        nx, ny = self.shape
        c, s = math.cos(yaw), math.sin(yaw)
        ci, cj = int(round((x - self.xs[0]) / self.cell)), int(round((y - self.ys[0]) / self.cell))
        if not (0 <= ci < nx and 0 <= cj < ny):
            return None
        li0, li1, lj0, lj1 = max(i0, 0), min(i1, nx - 1), max(j0, 0), min(j1, ny - 1)
        gx = self.gx[li0:li1 + 1, lj0:lj1 + 1] - x
        gy = self.gy[li0:li1 + 1, lj0:lj1 + 1] - y
        lx, ly = c * gx + s * gy, -s * gx + c * gy
        inside = (np.abs(lx) <= a) & (np.abs(ly) <= b)
        # Would any of it fall off the grid? Then it's outside the room.
        if not clip and (i0 < 0 or j0 < 0 or i1 > nx - 1 or j1 > ny - 1):
            corners = [(sx * a, sy * b) for sx in (-1, 1) for sy in (-1, 1)]
            for px, py in corners:
                wx, wy = x + c * px - s * py, y + s * px + c * py
                if not (self.xs[0] - self.cell / 2 <= wx <= self.xs[-1] + self.cell / 2
                        and self.ys[0] - self.cell / 2 <= wy <= self.ys[-1] + self.cell / 2):
                    return None
        ii, jj = np.nonzero(inside)
        ii, jj = ii + li0, jj + lj0
        if not len(ii):
            ii, jj = np.array([ci]), np.array([cj])
        return ii, jj

    def mask_of(self, cells) -> np.ndarray:
        m = np.zeros(self.shape, bool)
        m[cells] = True
        return m

    # -- walls ------------------------------------------------------------------

    def _floor_in_front(self, f: WallFace) -> Optional[float]:
        nx, ny = self.shape
        for k in (0.5, 1.0, 1.5, 2.5):
            px, py = f.x + f.nx * self.cell * k, f.y + f.ny * self.cell * k
            i = int(round((px - self.xs[0]) / self.cell))
            j = int(round((py - self.ys[0]) / self.cell))
            if 0 <= i < nx and 0 <= j < ny and self.ok[i, j]:
                return float(self.floor[i, j])
        return None

    def _faces(self) -> List[_Face]:
        walls = self.ctx.walls
        if not walls:
            return []
        pts = np.array([(w.x, w.y) for w in walls])
        nrm = np.array([(w.nx, w.ny) for w in walls])
        out = []
        for k, w in enumerate(walls):
            floor = self._floor_in_front(w)
            if floor is None or w.bottom > floor + 1.0:      # no floor before it, or a lintel
                continue
            dist = [_rect_dist(w.x, w.y, d.clear) for d in self.ctx.doors if d.clear]
            near = min(dist, default=1e9)
            d2 = np.hypot(pts[:, 0] - w.x, pts[:, 1] - w.y)
            turn = (d2 <= 8.0) & (nrm @ np.array([w.nx, w.ny]) < 0.5)
            out.append(_Face(w, floor, near < FRAME, bool(turn.any()), FRAME <= near <= 16.0))
        return out


# ---------------------------------------------------------------------------
# Choosing a model
# ---------------------------------------------------------------------------

class _Chooser:
    """Models by (kind, Mount filled, Set), and the room's culture as it binds."""

    def __init__(self, catalogue: Catalogue, rules: DecorRules, ctx: RoomContext, rng: random.Random):
        self.rules = rules
        self.rng = rng
        self.sets = rules.sets.sets_for(ctx.zone_type, ctx.race, ctx.theme)
        self.used: List[str] = []
        self.by: Dict[Tuple[str, str, str], List[Model]] = {}
        for key in sorted(catalogue.models):
            m = catalogue.models[key]
            t = m.tags
            if t.use != "yes" or m.animation == "skeletal" or t.set not in self.sets:
                continue
            self.by.setdefault((t.kind, t.mount, t.set), []).append(m)

    def fits(self, s: str) -> bool:
        return all(self.rules.sets.may_share(s, u) for u in self.used)

    def choose(self, kinds: Sequence[str], mount: str) -> Optional[Model]:
        for kind in kinds:
            for s in self.sets:
                if not self.fits(s):
                    continue
                pool = [m for mt in MOUNTS_FILLING[mount] for m in self.by.get((kind, mt, s), ())]
                if pool:
                    wts = [1.0 + math.log1p(m.placed_total) for m in pool]
                    return self.rng.choices(pool, weights=wts)[0]
        return None

    def smaller(self, kinds: Sequence[str], mount: str, than: Model) -> List[Model]:
        """When ``than`` finds no spot: the smallest model of each kind asked for, best kind
        first, each smaller in plan than ``than`` (a stool where a throne won't go)."""
        def area(m: Model) -> float:
            sz = size_of(m)
            return sz.w * sz.d
        limit = area(than)
        out = []
        for kind in kinds:
            pool = [m for s in self.sets if self.fits(s) for mt in MOUNTS_FILLING[mount]
                    for m in self.by.get((kind, mt, s), ()) if area(m) < limit - 1e-9]
            if pool:
                out.append(min(pool, key=lambda m: (area(m), m.key)))
        return out[:FALLBACKS]

    def bind(self, model: Model) -> None:
        s = model.tags.set
        if s != NEUTRAL and s not in self.used:
            self.used.append(s)


# ---------------------------------------------------------------------------
# Placing
# ---------------------------------------------------------------------------

def _where(line: Line) -> str:
    f, w, fld = line.where
    return " ".join(x for x in (f, w, fld) if x)


def _what(line: Line) -> str:
    return f"group:{line.group}" if line.group else "|".join(line.kinds)


def _spacing(ctx: RoomContext) -> float:
    return LIGHT_SPACING.get(ctx.zone_type, DEFAULT_LIGHT_SPACING)


class _Placer:
    def __init__(self, ctx: RoomContext, rules: DecorRules, catalogue: Catalogue, rng: random.Random):
        self.ctx = ctx
        self.rules = rules
        self.rng = rng
        self.room = Room(ctx)
        self.chooser = _Chooser(catalogue, rules, ctx, rng)
        self.out = Decorated(ctx.id, sets=self.chooser.sets)
        self.groups = 0

    # -- state, for Groups' all-or-nothing ---------------------------------------

    def _save(self):
        r = self.room
        return (r.occupied.copy(), r.blocked.copy(), list(r.wall_props), list(r.ceiling_props),
                list(self.chooser.used), len(self.out.props))

    def _restore(self, s) -> None:
        r = self.room
        r.occupied, r.blocked = s[0].copy(), s[1].copy()
        r.wall_props, r.ceiling_props, self.chooser.used, n = list(s[2]), list(s[3]), list(s[4]), s[5]
        del self.out.props[n:]

    def _prop(self, model: Model, sz: Size, x, y, z, yaw, mount, blocks, step, line: Line, at: str,
              poi=None, group=None) -> Prop:
        t = model.tags
        p = Prop(model.key, t.kind, t.category, mount, t.set, float(x), float(y), float(z),
                 float(yaw) % (2 * math.pi), sz.scale, sz.w, sz.d, sz.h, sz.below, blocks, step,
                 _where(line), at, poi, group)
        self.out.props.append(p)
        self.chooser.bind(model)
        return p

    # -- floor ------------------------------------------------------------------

    def _floor_ok(self, model: Model, sz: Size, x, y, yaw, allow: Optional[np.ndarray] = None,
                  dressing: bool = False):
        """(cells, z, blocked mask) if the model can stand here, else None. ``allow``: Feature
        cells it may stand on (a dais); ``dressing``: it may stand in a Throat."""
        r = self.room
        cells = r.rect_cells(x, y, yaw, sz.w, sz.d, 0.25)
        if cells is None:
            return None
        if not r.ok[cells].all() or r.occupied[cells].any():
            return None
        keep = r.keep_dressing if dressing else r.keep
        off = keep[cells] | r.feature[cells]
        if allow is not None:
            off = keep[cells] | (r.feature[cells] & ~allow[cells])
        if off.any():
            return None
        fl = r.floor[cells]
        if float(fl.max() - fl.min()) > FLAT:
            return None
        z = float(fl.min())
        if r.ceiling is not None:
            ce = r.ceiling[cells]
            ce = ce[~np.isnan(ce)]
            if len(ce) and float(ce.min()) < z + sz.h + 0.5:
                return None
        grown = r.rect_cells(x, y, yaw, sz.w, sz.d, PLAYER_HALF_WIDTH, clip=True)
        if r.poi_spot[grown].any():
            return None
        blocked = r.blocked
        if _blocking(model) and sz.h > STEP_UP:
            blocked = r.blocked | r.mask_of(grown)
            if r.problems(blocked):
                return None
        return cells, z, blocked

    def _put_floor(self, model, sz, spots, step, line, at, allow=None, poi=None, group=None,
                   mount="floor") -> Optional[Prop]:
        for x, y, yaw in spots:
            got = self._floor_ok(model, sz, x, y, yaw, allow, step == "dressing")
            if got is None:
                continue
            cells, z, blocked = got
            self.room.occupied[cells] = True
            self.room.blocked = blocked
            return self._prop(model, sz, x, y, z, yaw, mount,
                              _blocking(model) and sz.h > STEP_UP, step, line, at, poi, group)
        return None

    # -- spots ---------------------------------------------------------------------

    def _free(self, allow: Optional[np.ndarray] = None) -> np.ndarray:
        r = self.room
        m = r.ok & ~r.keep & ~r.occupied
        m &= ~r.feature if allow is None else ~(r.feature & ~allow)
        return np.argwhere(m)

    def _noisy(self, cells: np.ndarray, key: np.ndarray, noise: float) -> np.ndarray:
        if not len(cells):
            return cells
        k = key + np.array([self.rng.uniform(0, noise) for _ in range(len(cells))])
        return cells[np.argsort(k, kind="stable")]

    def _axis_yaw(self) -> float:
        return self.rng.choice((0.0, math.pi / 2, math.pi, 3 * math.pi / 2))

    def _door_xy(self) -> Tuple[float, float]:
        r = self.room
        s = np.argwhere(r.starts)
        if not len(s):
            return float(r.gx[r.ok].mean()), float(r.gy[r.ok].mean())
        return float(r.xs[s[:, 0]].mean()), float(r.ys[s[:, 1]].mean())

    def floor_spots(self, at: str, sz: Size, allow=None) -> List[Tuple[float, float, float]]:
        r = self.room
        if at in ("along_wall", "corners", "by_door", "rows"):
            return self.wall_spots_floor(at, sz)
        if at == "on_dais":
            cells = np.argwhere(r.ok & r.dais & ~r.keep & ~r.occupied)
            if not len(cells):
                return self.wall_spots_floor("corners", sz)
            cells = cells[self.rng.sample(range(len(cells)), len(cells))][:TRIES]
            return [(r.xs[i], r.ys[j], self.rng.uniform(0, 2 * math.pi)) for i, j in cells]
        cells = self._free(allow)
        if not len(cells):
            return []
        px, py = r.xs[cells[:, 0]], r.ys[cells[:, 1]]
        if at == "centre":
            cx, cy = float(r.gx[r.ok].mean()), float(r.gy[r.ok].mean())
            cells = self._noisy(cells, np.hypot(px - cx, py - cy), 6.0)[:TRIES]
            return [(r.xs[i], r.ys[j], self._axis_yaw()) for i, j in cells]
        if at == "far_end":
            dx, dy = self._door_xy()
            cells = self._noisy(cells, -np.hypot(px - dx, py - dy), 8.0)[:TRIES]
            return [(r.xs[i], r.ys[j], math.atan2(dy - r.ys[j], dx - r.xs[i])) for i, j in cells]
        # scatter (and anything else on the floor)
        order = self.rng.sample(range(len(cells)), min(len(cells), TRIES * 2))
        return [(r.xs[cells[k, 0]], r.ys[cells[k, 1]], self.rng.uniform(0, 2 * math.pi)) for k in order]

    def _faces(self, at: str) -> List[_Face]:
        faces = [f for f in self.room.faces if not f.door]
        if at == "corners":
            pick = [f for f in faces if f.corner]
            faces = pick or faces
        elif at == "by_door":
            pick = [f for f in faces if f.by_door]
            faces = pick or faces
        return self.rng.sample(faces, len(faces))

    def wall_spots_floor(self, at: str, sz: Size) -> List[Tuple[float, float, float]]:
        out = []
        off = sz.w / 2 + WALL_GAP
        for f in self._faces(at)[:TRIES * 2]:
            w = f.face
            out.append((w.x + w.nx * off, w.y + w.ny * off, math.atan2(w.ny, w.nx)))
        return out

    def row_spots(self, prev: Prop, sz: Size) -> List[Tuple[float, float, float]]:
        """Next to ``prev`` along its own Y (a row), either side."""
        step = (prev.d + sz.d) / 2 + GAP
        c, s = math.cos(prev.yaw), math.sin(prev.yaw)
        sides = [1, -1] if self.rng.random() < 0.5 else [-1, 1]
        # keep the back in line with prev's back
        back = (sz.w - prev.w) / 2
        return [(prev.x - s * step * k + c * back, prev.y + c * step * k + s * back, prev.yaw) for k in sides]

    # -- wall -------------------------------------------------------------------

    def _put_wall(self, model: Model, sz: Size, faces: Iterable[_Face], step, line, at, spacing: float,
                  poi=None) -> Optional[Prop]:
        r = self.room
        light = model.tags.category == "light"
        over = sz.over if sz.over is not None and 0.5 <= sz.over <= 40 else \
            WALL_HEIGHT.get(model.tags.category, DEFAULT_WALL_HEIGHT)
        off = sz.wall if sz.wall is not None and sz.wall <= sz.w + 1.0 else sz.w / 2 + 0.1
        half = sz.d / 2
        for f in faces:
            w = f.face
            z = f.floor + over
            if z + sz.h > w.top - 0.25 or z - sz.below < w.bottom - 0.01:
                continue
            x, y = w.x + w.nx * off, w.y + w.ny * off
            if any(math.hypot(x - px, y - py) < (spacing if light and plight else half + ph + GAP)
                   for px, py, ph, plight in r.wall_props):
                continue
            yaw = math.atan2(w.ny, w.nx)
            blocks = _blocking(model) and z - sz.below < f.floor + HEAD_HEIGHT and z + sz.h > f.floor + STEP_UP
            blocked = r.blocked
            if blocks:
                grown = r.rect_cells(x, y, yaw, sz.w, sz.d, PLAYER_HALF_WIDTH, clip=True)
                if grown is None or r.poi_spot[grown].any():
                    continue
                blocked = r.blocked | r.mask_of(grown)
                if r.problems(blocked):
                    continue
            r.blocked = blocked
            r.wall_props.append((x, y, half, light))
            return self._prop(model, sz, x, y, z, yaw, "wall", blocks, step, line, at, poi)
        return None

    # -- ceiling ----------------------------------------------------------------

    def _put_ceiling(self, model, sz, step, line, at) -> Optional[Prop]:
        r = self.room
        if r.ceiling is None:
            return None
        length = sz.h + sz.below
        with np.errstate(invalid="ignore"):
            room = r.ceiling - r.floor >= length + HEAD_HEIGHT
        cells = np.argwhere(r.ok & room)
        if not len(cells):
            return None
        for k in self.rng.sample(range(len(cells)), min(len(cells), TRIES * 2)):
            i, j = cells[k]
            x, y = float(r.xs[i]), float(r.ys[j])
            if any(math.hypot(x - px, y - py) < max(sz.w, sz.d) + 4.0 for px, py in r.ceiling_props):
                continue
            r.ceiling_props.append((x, y))
            z = float(r.ceiling[i, j]) - sz.h
            return self._prop(model, sz, x, y, z, self.rng.uniform(0, 2 * math.pi), "ceiling", False, step,
                              line, at)
        return None

    # -- one item of a line ---------------------------------------------------------

    def _item(self, model: Model, line: Line, step: str, prev: Optional[Prop] = None) -> Tuple[Optional[Prop], str]:
        sz = size_of(model)
        mount = line.mount
        if mount == "wall":
            if not self.room.faces:
                return None, "no wall"
            spacing = _spacing(self.ctx) * ROOM_LIGHT_GAP
            faces = self._faces("by_door" if line.at == "by_door" else "on_wall")
            return self._put_wall(model, sz, faces, step, line, line.at, spacing), "no spot"
        if mount == "ceiling":
            if self.room.ceiling is None or np.isnan(self.room.ceiling).all():
                return None, "no ceiling"
            return self._put_ceiling(model, sz, step, line, line.at), "no spot"
        if line.at in ("along_wall", "corners", "by_door", "rows") and not self.room.faces:
            return None, "no wall"
        allow = self.room.dais if line.at == "on_dais" else None
        spots = self.floor_spots(line.at, sz, allow)
        if prev is not None and line.at == "rows":
            spots = self.row_spots(prev, sz) + spots
        return self._put_floor(model, sz, spots, step, line, line.at, allow), "no spot"

    def line(self, line: Line, step: str, factor: float) -> None:
        n = draw_count(line, factor, self.rng)
        if n <= 0:
            return
        if line.group:
            for _ in range(n):
                self.group(line, self.rules.groups[line.group], step)
            return
        model = self.chooser.choose(line.kinds, line.mount)
        if model is None:
            self.out.drops.append(Drop(step, _where(line), _what(line), "no model"))
            return
        prev = None
        for _ in range(n):
            got, why = self._item(model, line, step, prev)
            for other in (self.chooser.smaller(line.kinds, line.mount, model) if got is None and why == "no spot"
                          else ()):
                got, why = self._item(other, line, step, prev)
                if got is not None:
                    break
            if got is None:
                self.out.drops.append(Drop(step, _where(line), _what(line), why))
            else:
                prev = got

    # -- Groups -----------------------------------------------------------------------

    def group(self, line: Line, g: Group, step: str) -> None:
        save = self._save()
        drawn = []
        for m in g.members:
            n = self.rng.randint(*m.count)
            if n <= 0:
                continue
            model = self.chooser.choose(m.kinds, m.mount)
            if model is None:
                self.out.drops.append(Drop(step, _where(line), _what(line),
                                           f"no model for member {'|'.join(m.kinds)}"))
                self._restore(save)
                return
            self.chooser.bind(model)            # the members keep to the anchor's culture
            drawn.append((m, model, n))
        self._restore(save)
        anchor_m, anchor_model, _ = drawn[0]
        asz = size_of(anchor_model)
        gid = self.groups
        spots = self.floor_spots(line.at, asz)[:GROUP_TRIES]
        for spot in spots:
            save = self._save()
            a = self._put_floor(anchor_model, asz, [spot], step, line, line.at, group=gid)
            if a is not None and self._members(a, drawn[1:], step, line, gid):
                self.groups += 1
                return
            self._restore(save)
        self.out.drops.append(Drop(step, _where(line), _what(line), "no spot"))

    def _members(self, a: Prop, drawn, step, line, gid) -> bool:
        prev = a
        for m, model, n in drawn:
            sz = size_of(model)
            for k in range(n):
                if m.at == "stack":
                    got = self._stack(a, model, sz, step, line, gid)
                elif m.at == "row":
                    got = self._put_floor(model, sz, self.row_spots(prev, sz), step, line, "row", group=gid)
                    prev = got or prev
                else:
                    got = self._put_floor(model, sz, self._round(a, sz, m.at, k, n), step, line, m.at, group=gid)
                if got is None:
                    return False
        return True

    def _round(self, a: Prop, sz: Size, at: str, k: int, n: int) -> List[Tuple[float, float, float]]:
        """Spots round the anchor (``round``: facing it, spread about it; ``beside``: at its sides)."""
        out = []
        reach = max(a.w, a.d) / 2 + max(sz.w, sz.d) / 2 + (0.3 if at == "round" else GAP)
        if at == "beside":
            base = [a.yaw + math.pi / 2, a.yaw - math.pi / 2]
            self.rng.shuffle(base)
            angles = base + [a.yaw + math.pi / 2 + self.rng.uniform(-0.6, 0.6) for _ in range(4)]
            angles += [a.yaw - math.pi / 2 + self.rng.uniform(-0.6, 0.6) for _ in range(4)]
        else:
            start = self.rng.uniform(0, 2 * math.pi)
            angles = [start + 2 * math.pi * (k + t / 4) / max(n, 1) for t in range(4)]
            angles += [self.rng.uniform(0, 2 * math.pi) for _ in range(8)]
        for ang in angles:
            # a footprint's reach along this way (rectangles are wider on the diagonal)
            x, y = a.x + math.cos(ang) * reach, a.y + math.sin(ang) * reach
            yaw = math.atan2(a.y - y, a.x - x) if at == "round" else a.yaw
            out.append((x, y, yaw))
        return out

    def _stack(self, a: Prop, model: Model, sz: Size, step, line, gid) -> Optional[Prop]:
        if sz.w > a.w + 0.01 or sz.d > a.d + 0.01:
            return None
        z = a.z + a.h
        r = self.room
        if r.ceiling is not None:
            i = int(round((a.x - r.xs[0]) / r.cell))
            j = int(round((a.y - r.ys[0]) / r.cell))
            ce = r.ceiling[i, j]
            if not np.isnan(ce) and ce < z + sz.h + 0.5:
                return None
        jx = self.rng.uniform(-1, 1) * (a.w - sz.w) / 2
        jy = self.rng.uniform(-1, 1) * (a.d - sz.d) / 2
        c, s = math.cos(a.yaw), math.sin(a.yaw)
        return self._prop(model, sz, a.x + c * jx - s * jy, a.y + s * jx + c * jy, z,
                          a.yaw + self.rng.uniform(-0.4, 0.4), "raised", False, step, line, "stack", group=gid)

    # -- Dressing -------------------------------------------------------------------

    def dressing(self) -> None:
        for k, poi in enumerate(self.ctx.pois):
            for line in self.rules.dressing_for(poi.get("purpose", "")):
                n = draw_count(line, 1.0, self.rng)
                if n <= 0:
                    continue
                if line.group:              # a Dressing Group: placed round the POI as a recipe's
                    for _ in range(n):
                        self.group(line, self.rules.groups[line.group], "dressing")
                    continue
                model = self.chooser.choose(line.kinds, line.mount)
                if model is None:
                    self.out.drops.append(Drop("dressing", _where(line), _what(line), "no model", k))
                    continue
                for t in range(n):
                    got, why = self._dress(k, poi, model, line, t)
                    for other in (self.chooser.smaller(line.kinds, line.mount, model)
                                  if got is None and why == "no spot" else ()):
                        got, why = self._dress(k, poi, other, line, t)
                        if got is not None:
                            break
                    if got is None:
                        self.out.drops.append(Drop("dressing", _where(line), _what(line), why, k))

    def _dress(self, k: int, poi: dict, model: Model, line: Line, t: int) -> Tuple[Optional[Prop], str]:
        sz = size_of(model)
        r = self.room
        px, py = float(poi["x"]), float(poi["y"])
        if line.mount == "wall":
            if not r.faces:
                return None, "no wall"
            faces = sorted((f for f in r.faces if not f.door), key=lambda f: math.hypot(f.face.x - px, f.face.y - py))
            return self._put_wall(model, sz, faces[:TRIES * 2], "dressing", line, line.at,
                                  _spacing(self.ctx) * ROOM_LIGHT_GAP, poi=k), "no spot"
        allow = None
        fi = poi.get("feature")
        if isinstance(fi, int) and 0 <= fi < len(self.ctx.features) and \
                self.ctx.features[fi].get("kind") == "dais":
            allow = r.feature_masks[fi]
        dx, dy = self._door_xy()
        away = math.atan2(py - dy, px - dx) if math.hypot(px - dx, py - dy) > 1e-6 else 0.0
        reach0 = max(sz.w, sz.d) / 2 + PLAYER_HALF_WIDTH + r.cell
        spots = []
        for ring in range(9):
            reach = reach0 + (ring % 6) * 2.0
            if ring >= 6:                                   # a wall where it asks: round it
                angs = [self.rng.uniform(0, 2 * math.pi) for _ in range(6)]
            elif line.at == "behind":
                angs = [away + self.rng.uniform(-0.5, 0.5) * (1 + ring * 0.3) for _ in range(3)]
            elif line.at == "flank":
                side = math.pi / 2 if t % 2 == 0 else -math.pi / 2
                angs = [away + side + self.rng.uniform(-0.4, 0.4) for _ in range(3)]
            else:                                           # beside, round
                angs = [self.rng.uniform(0, 2 * math.pi) for _ in range(4)]
            for ang in angs:
                x, y = px + math.cos(ang) * reach, py + math.sin(ang) * reach
                if line.at == "flank":
                    yaw = away + math.pi            # facing the way in, as the POI does
                else:
                    yaw = math.atan2(py - y, px - x)
                spots.append((x, y, yaw))
        return self._put_floor(model, sz, spots, "dressing", line, line.at, allow, poi=k), "no spot"

    # -- a corridor --------------------------------------------------------------------

    def corridor(self, factor: float) -> None:
        """Wall lights every ``LIGHT_SPACING`` along the walls, from the room's ``every`` light
        line (the first on_wall light it asks for)."""
        lines = [ln for ln in self.rules.every.lines if ln.mount == "wall" and ln.category == "light"]
        if not lines or factor <= 0:
            return
        line = lines[0]
        model = self.chooser.choose(line.kinds, "wall")
        if model is None:
            self.out.drops.append(Drop("prop", _where(line), _what(line), "no model"))
            return
        faces = [f for f in self.room.faces if not f.door]
        if not faces:
            self.out.drops.append(Drop("prop", _where(line), _what(line), "no wall"))
            return
        pts = np.array([(f.face.x, f.face.y) for f in faces])
        centred = pts - pts.mean(axis=0)
        axis = np.linalg.svd(centred, full_matrices=False)[2][0] if len(pts) > 1 else np.array([1.0, 0.0])
        along = centred @ axis
        order = np.argsort(along, kind="stable")
        spacing = _spacing(self.ctx) / max(factor, 0.25)
        start = float(along[order[0]]) + self.rng.uniform(0, spacing / 2)
        sz = size_of(model)
        for idx in order:
            if along[idx] < start:
                continue
            self._put_wall(model, sz, [faces[idx]], "prop", line, line.at, spacing)


# ---------------------------------------------------------------------------
# The entry points
# ---------------------------------------------------------------------------

def stream(ctx: RoomContext, decor_seed: Optional[int] = None) -> random.Random:
    """The room's own random stream: salted with ``decor``, so it draws nothing the room stage
    draws, and keyed by the room, so rooms don't share draws."""
    seed = ctx.seed if decor_seed is None else decor_seed
    return random.Random(f"decor/{int(seed)}/{ctx.source}/{ctx.id}")


def place(context: RoomContext, rules: Optional[DecorRules] = None, catalogue: Optional[Catalogue] = None,
          control: str = DEFAULT_CONTROL, decor_seed: Optional[int] = None) -> Decorated:
    """Decorate one room (or Site, or corridor) from its context alone. ``rules`` and
    ``catalogue`` default to the shipped ones; ``control`` is the Decor control (``none``
    places nothing); ``decor_seed`` salts the stream (default: the context's seed)."""
    if rules is None:
        from generators.decor.rules import load_decor
        rules = load_decor()
    if catalogue is None:
        from generators.decor.catalogue import load
        catalogue = load()
    rng = stream(context, decor_seed)
    p = _Placer(context, rules, catalogue, rng)
    if control == "none":
        return p.out
    weights = rules.weights_for(context.zone_type, context.race, context.theme, context.kind,
                                context.room_type, control)
    if context.source == CORRIDOR:
        p.corridor(weights.get("light", 1.0))
        return p.out
    p.dressing()
    p.out.bare = rng.random() < weights[BARE]
    if p.out.bare:
        return p.out
    lines = [ln for recipe in rules.recipe_for(context.room_type, context.kind, context.source)
             for ln in recipe.lines]
    groups = [ln for ln in lines if ln.group]
    debris = [ln for ln in lines if not ln.group and ln.category == "debris"]
    single = [ln for ln in lines if not ln.group and ln.category != "debris"]
    for step, todo in (("group", groups), ("prop", single), ("debris", debris)):
        for ln in todo:
            p.line(ln, step, rules.factor(ln, weights, context.scales))
    return p.out


def check(context: RoomContext, decorated: Decorated) -> List[str]:
    """Decor's own room check (Req 13.4) on a finished result: with every blocking Prop's
    footprint (grown by the player's half-width) taken out, reached floor stays joined to the
    doors, each door is reached and each POI keeps reached floor near it. [] when it holds."""
    room = Room(context)
    blocked = np.zeros(room.shape, bool)
    for p in decorated.props:
        if not p.blocks:
            continue
        cells = room.rect_cells(p.x, p.y, p.yaw, p.w, p.d, PLAYER_HALF_WIDTH, clip=True)
        if cells is None:
            return [f"{p.key} at ({p.x:.0f}, {p.y:.0f}) stands outside the room"]
        blocked[cells] = True
    return room.problems(blocked)


__all__ = ["CORRIDOR", "Decorated", "Drop", "FRAME", "HEAD_HEIGHT", "LIGHT_SPACING", "PLAYER_HALF_WIDTH",
           "POI_REACH", "Prop", "Room", "STEPS", "Size", "check", "place", "size_of", "stream"]
