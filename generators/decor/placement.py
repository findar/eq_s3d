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
  its p50), the side of the model stock puts to a wall turned to it (catalogue ``wall_side``,
  measured on stock's placements) and its back flush with the face (its own reach to that side
  off it), never within ``FRAME`` of a door's clear zone and never on a lintel (a wall face
  whose foot is above the floor in front of it). Wall faces are the context's samples of the
  BUILT wall mesh, with each sample's own bottom and top; the build then sets each wall Prop on
  the wall mesh at its own height (``generators/builder.py``), so a torch on a rough wall sits
  where that wall stands (design Risks). Wall
  lights keep ``LIGHT_SPACING`` (finding 1: 38 u dungeon, 26 u city; a room keeps
  ``ROOM_LIGHT_GAP`` of it);
- **ceiling** Props hang where the ceiling is at least the model's length plus ``HEAD_HEIGHT``
  over the floor, so they never block (Req 6.2);
- **Groups** are placed whole or dropped whole (Req 6.3): the anchor at its arrangement, its
  members round it, in a row with it, beside it or stacked on it (raised).

**Yaw** is step 10's decision 10: radians counter-clockwise from +X, and a model's front faces
+X at yaw 0. An along-wall floor Prop's yaw is its wall's into-room normal, so its back (-X)
is to the wall. A wall Prop turns its measured side to the wall instead: stock differs by model
(TORCHPOINT has the wall at its -X, WALLTORCH200 at +X, GKTORCH701 at +Y), and a model stock
never hangs keeps -X.

**Floor and raised** Props stand on their bottom (``measured.below`` under the origin, which
some models draw far from: GENMETCRATE700's mesh lies wholly under its origin), ``LIFT`` over
the lowest floor under their footprint or the top of what they stack on.

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
from scipy.ndimage import binary_dilation, distance_transform_edt, label
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

from generators.decor.catalogue import UNKNOWN, WALL_SIDES, Catalogue, Model
from generators.decor.rules import (BARE, DEFAULT_CONTROL, MOUNTS_FILLING, NEUTRAL, DecorRules, Group, Line,
                                    draw_count)
from generators.room_context import STEP_UP, RoomContext, WallFace

#: The gate's figures (archive decision 9 of step 10, ``analyzer/footprints.py``), mirrored.
PLAYER_HALF_WIDTH = 1.5
HEAD_HEIGHT = 8.0
POI_REACH = PLAYER_HALF_WIDTH + 2.0
#: The gate's clear width: a body this wide still goes from each door to the room's Core
#: (``throat_narrow``), read on a 1 u grid, so its middle keeps this far from anything.
CLEAR_WIDTH = 8.0
WIDE_RADIUS = CLEAR_WIDTH / 2 - 1.0 / math.sqrt(2.0)
#: The gate's band starts AT a step over the floor (a triangle touching it counts), and a
#: model's measured height is rounded: a floor Prop this near a step tall is in the way.
BAND_SLACK = 0.1
#: The gate's walled-off pocket (``analyzer.traverse.WALLED_OFF``): free floor this big (u^2)
#: cut off and not inside one model's plan fails ``footprint_cut``.
WALLED_OFF = 64.0
#: Layers of a blocked mask (``Room.footprint``).
LAYERS = 4
#: A wall is kept clear this far each side of a door's clear zone (u): the opening's frame.
FRAME = 3.0
#: Wall lights' spacing (finding 1: a wall light's nearest wall light, p50 over zones).
LIGHT_SPACING: Dict[str, float] = {"city": 26.0}
DEFAULT_LIGHT_SPACING = 38.0
#: In a room, wall lights stand at least this share of the spacing apart.
ROOM_LIGHT_GAP = 0.8
#: The most a floor Prop's ground may rise across its footprint (u).
FLAT = 2.0
#: A floor or raised Prop's bottom stands this far over what it stands on (u).
LIFT = 0.05
#: Spots tried per item before it drops; anchor spots tried per Group.
TRIES = 24
GROUP_TRIES = 8
#: Smaller models tried when an item's model finds no spot, before it drops.
FALLBACKS = 2
#: Gap between a Prop's back and its wall (u), and between neighbours in a row or Group.
WALL_GAP = 0.5
GAP = 1.0
#: The gap the gate surely leaves open between two blocking Props' plans: any gap from 5.83 u
#: (``analyzer.footprints``: 2 x the half-width plus a raster step's diagonal). A nearer gap
#: can be shut or open on the gate's raster, so the floor behind it (by a wall) can be a pocket
#: the gate cuts off that decor's grid reads as blocked (task 21: two rocks 2.5 u apart by a
#: wall, 64 u^2): ``Room.spaced``. The gap after a blocking Prop in a row.
BLOCKING_GAP = 6.0
ROW_GAP_BLOCKING = BLOCKING_GAP
#: Cells (2 u each) round a lane of floor the strict reading doesn't join that a blocking Prop
#: keeps off: 6 u, about the gate's clear width less a cell.
LANE_NEAR = 3
#: A wall Prop's back stands this far off its wall (u).
WALL_FLUSH = 0.05
#: The gate's walkable slope (``AgentModel.walkable_slope_deg``, 40°) as a grade.
WALK_GRADE = math.tan(math.radians(40.0))
#: How near (u) a wall sample turned from a wall Prop's own face must be to its plan's corner
#: to stop it there: about the samples' spacing.
WALL_TURN_NEAR = 3.0
#: A wall model whose own reach to its wall side is more than this past stock's standoff (model
#: units) has a part stock sinks into the wall (DNTORCH101: reach 5.14, stock's origin 2.89 off);
#: hung flush it stands that much further out than stock ever shows it, so a wall line takes
#: such a model only when its kind has nothing stock hangs flush (task 14).
WALL_EMBED = 1.5
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
    h: float                # its top over its origin, scaled (below it when negative)
    below: float            # its bottom under its origin, scaled (over it when negative)
    scale: float
    over: Optional[float]   # stock's height over the floor (p50), scaled with the room: as stock
    wall: Optional[float]   # stock's distance off the wall (p50)
    #: A wall model's side to its wall (catalogue ``wall_side``; ``-x`` when unmeasured): the
    #: model-frame unit vector pointing at the wall, and the model's reach from its origin to
    #: that side, scaled (None when unmeasured).
    side: Tuple[float, float] = (-1.0, 0.0)
    back: Optional[float] = None


def size_of(model: Model) -> Size:
    """A model's measured size at the scale stock gives it. ``h`` and ``below`` are the mesh's
    own top and bottom about its origin, so a model drawn under its origin (GENMETCRATE700:
    -22.8 to -4.6) keeps that and stands on its bottom, not its origin."""
    m = model.measured or {}
    obs = model.observed or {}
    sc = obs.get("scale") or [1.0, 1.0, 1.0]
    s = float(min(2.0, max(0.5, sc[1] if len(sc) > 1 else 1.0)))
    over = obs.get("over")
    wall = obs.get("wall")
    top = float(m.get("h", 2.0))
    bottom = float(m.get("below", 0.0))
    if top + bottom < 0.1:                  # flat (a rug): a sliver of height, over its bottom
        top = 0.1 - bottom
    ws = model.wall_side or {}
    side = WALL_SIDES.get(ws.get("side", "-x"), (-1.0, 0.0))
    back = float(ws["back"]) * s if "back" in ws else None
    return Size(w=max(0.2, float(m.get("w", 2.0))) * s, d=max(0.2, float(m.get("d", 2.0))) * s,
                h=top * s, below=bottom * s,
                scale=s, over=float(over[1]) if over and len(over) > 1 else None,
                wall=float(wall[1]) if wall and len(wall) > 1 else None, side=side, back=back)


def _sunk(model: Model) -> bool:
    """Whether stock hangs this wall model with part of it inside the wall (``WALL_EMBED``)."""
    ws = model.wall_side or {}
    return ws.get("standoff") is not None and float(ws["back"]) - float(ws["standoff"]) > WALL_EMBED


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


def _polygon_distance(gx, gy, plan) -> np.ndarray:
    """Each point's plan distance to a polygon (0 inside it)."""
    d = np.full(gx.shape, np.inf)
    n = len(plan)
    for k in range(n):
        (ax, ay), (bx, by) = plan[k], plan[(k + 1) % n]
        dx, dy = bx - ax, by - ay
        ln = dx * dx + dy * dy
        t = np.zeros(gx.shape) if ln == 0 else np.clip(((gx - ax) * dx + (gy - ay) * dy) / ln, 0.0, 1.0)
        d = np.minimum(d, np.hypot(gx - ax - t * dx, gy - ay - t * dy))
    return np.where(_in_polygon(gx, gy, plan), 0.0, d)


def _hull(points: np.ndarray) -> np.ndarray:
    """The convex hull of plan points, counter-clockwise (Andrew's monotone chain)."""
    pts = sorted(set(map(tuple, np.round(np.asarray(points, dtype=np.float64), 6))))
    if len(pts) < 3:
        return np.array(pts, dtype=np.float64)

    def turn(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list = []
    for p in pts:
        while len(lower) >= 2 and turn(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list = []
    for p in reversed(pts):
        while len(upper) >= 2 and turn(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return np.array(lower[:-1] + upper[:-1], dtype=np.float64)


def _near_rise(ctx: RoomContext, ok: np.ndarray) -> np.ndarray:
    """Cells within the player's half-width of something he can't walk into, as the
    gate's walls cover floor (``analyzer.footprints.cover_samples``): a wall (no floor; a
    Site's ground has no walls, so not there), a solid Feature (floor not reached), or
    floor more than ``STEP_UP`` above the cell. With cells ``CELL`` (2 u) across, any of
    those in the 8 cells round a cell lies within 1.5 u of its middle, or near it."""
    floor = ctx.floor
    nx, ny = floor.shape
    reach = max(1, int(math.ceil((PLAYER_HALF_WIDTH - ctx.cell / 2) / ctx.cell + 0.5)))
    wall = np.isnan(floor) if ctx.source != "site" else np.zeros(floor.shape, bool)
    solid = ~np.isnan(floor) & ~ok
    pad = reach
    edge = np.pad(wall | solid, pad, constant_values=ctx.source != "site")
    hi = np.pad(np.where(np.isnan(floor), -np.inf, floor), pad, constant_values=-np.inf)
    out = np.zeros(floor.shape, bool)
    base = np.where(np.isnan(floor), np.inf, floor)
    for di in range(-reach, reach + 1):
        for dj in range(-reach, reach + 1):
            if di == 0 and dj == 0:
                continue
            e = edge[pad + di:pad + di + nx, pad + dj:pad + dj + ny]
            h = hi[pad + di:pad + di + nx, pad + dj:pad + dj + ny]
            out |= e | (h > base + STEP_UP)
    return out


def _edge_distance(ctx: RoomContext, ok: np.ndarray, reach: float = 0.0) -> np.ndarray:
    """Each cell's distance (u, middle to middle) to the nearest cell a body can't stand
    in: a wall (no floor; not round a Site), a solid Feature, or the foot of a rise more
    than ``STEP_UP``. Within ``reach`` it is also the distance to any floor more than
    ``STEP_UP`` over the cell's own, as the gate reads it (``cover_samples``: anything a step
    to a head over a sample, within the radius): a stair or ramp rises past a step a few cells
    off, with no one rise of a cell more than a step (task 21: the foot of a dais's stair)."""
    floor = ctx.floor
    site = ctx.source == "site"
    edge = (np.isnan(floor) & (not site)) | (~np.isnan(floor) & ~ok)
    f = np.where(np.isnan(floor), -np.inf, floor)
    with np.errstate(invalid="ignore"):
        edge[:-1, :] |= f[1:, :] > f[:-1, :] + STEP_UP
        edge[1:, :] |= f[:-1, :] > f[1:, :] + STEP_UP
        edge[:, :-1] |= f[:, 1:] > f[:, :-1] + STEP_UP
        edge[:, 1:] |= f[:, :-1] > f[:, 1:] + STEP_UP
    padded = np.pad(edge, 1, constant_values=not site)
    out = distance_transform_edt(~padded)[1:-1, 1:-1] * ctx.cell
    n = int(math.floor(reach / ctx.cell))
    if n < 1:
        return out
    nx, ny = floor.shape
    hi = np.pad(f, n, constant_values=-np.inf)
    base = np.where(np.isnan(floor), np.inf, floor)
    for di in range(-n, n + 1):
        for dj in range(-n, n + 1):
            d = math.hypot(di, dj) * ctx.cell
            if (di == 0 and dj == 0) or d > reach:
                continue
            h = hi[n + di:n + di + nx, n + dj:n + dj + ny]
            with np.errstate(invalid="ignore"):
                out = np.where(h > base + STEP_UP, np.minimum(out, d), out)
    return out


def _in_capsule(gx, gy, x0, y0, x1, y1, r) -> np.ndarray:
    dx, dy = x1 - x0, y1 - y0
    n = dx * dx + dy * dy
    t = np.zeros(gx.shape) if n == 0 else np.clip(((gx - x0) * dx + (gy - y0) * dy) / n, 0.0, 1.0)
    return np.hypot(gx - x0 - t * dx, gy - y0 - t * dy) <= r


#: How far inside the edge of a Site's ``ground`` piece its own ground ends: the largest
#: ``ground.margin`` a Sites recipe gives (``rules/sites/sites.toml``: 8-10 u; a test keeps
#: this honest). Props stand inside it, so the margin, part of the Site_Clear, stays free.
SITE_MARGIN = 10.0
#: The least plan gap between a Site's Prop and any Structure or other Prop (u; a Group's
#: members may stand closer to one another). The gate covers ground
#: within the player's half-width of either, and keeps a free strip joined on its 2 u raster
#: only from 2.83 u wide: 2 x 1.5 + 2.83 rounded up. Decor's own grid can't see that strip
#: (it erodes floor beside a Structure away), so without the gap a Prop could close a pocket
#: against a Structure that the gate counts as ground cut off.
SITE_GAP = 6.0
#: A Group's members at a Site stand within this of one another (u), so the gate covers the
#: ground between them whole, or ``SITE_GAP`` apart: a gap between leaves a strip the gate's
#: raster can read as a pocket cut off.
SITE_TOUCH = 2.0
#: A Site's floor Prop keeps its top at least this far over or under a step above the
#: ground round it (u): the gate's ground and the Site's floor differ by a few tenths.
SITE_STEP_SLACK = 0.25


class _SiteBounds:
    """A Site's Site_Clear and Structures exactly, for a floor Prop's plan (the grid's cells
    only see cell middles): the plan stays inside the Site's own ground (the ``ground``
    piece's reach less ``SITE_MARGIN``), off the approach and every apron, and ``SITE_GAP``
    from every Structure."""

    def __init__(self, ctx: RoomContext):
        self.inner: List[Tuple[float, float, float]] = []
        self.out: List[Tuple[float, float, float, float, float]] = []
        for c in ctx.clear:
            if c.get("what") == "ground":
                self.inner.append((c["x0"], c["y0"], c["r"] - SITE_MARGIN))
            elif c.get("what") in ("approach", "apron"):
                self.out.append((c["x0"], c["y0"], c["x1"], c["y1"], c["r"]))
        self.plans = [np.asarray(f["plan"], dtype=np.float64) for f in ctx.features
                      if len(f.get("plan") or ()) >= 3]
        #: The floor Props placed so far: (plan corners, Group or None).
        self.props: List[Tuple[np.ndarray, Optional[int]]] = []

    @staticmethod
    def corners(x: float, y: float, yaw: float, w: float, d: float) -> np.ndarray:
        c, s = math.cos(yaw), math.sin(yaw)
        return np.array([(x + c * a - s * b, y + s * a + c * b)
                         for a, b in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2))])

    def add(self, x: float, y: float, yaw: float, w: float, d: float, group: Optional[int]) -> None:
        self.props.append((self.corners(x, y, yaw, w, d), group))

    def fits(self, x: float, y: float, yaw: float, w: float, d: float, group: Optional[int] = None) -> bool:
        """``group``: a Group's members may stand closer to one another than ``SITE_GAP``."""
        c, s = math.cos(yaw), math.sin(yaw)
        n = max(2, int(math.ceil(max(w, d) / 0.5)) + 1)
        t = np.linspace(-0.5, 0.5, n)
        a = np.concatenate([t * w, t * w, np.full(n, -w / 2), np.full(n, w / 2), [0.0]])
        b = np.concatenate([np.full(n, -d / 2), np.full(n, d / 2), t * d, t * d, [0.0]])
        px, py = x + c * a - s * b, y + s * a + c * b
        for cx, cy, r in self.inner:
            if (np.hypot(px - cx, py - cy) > r).any():
                return False
        for x0, y0, x1, y1, r in self.out:
            if _in_capsule(px, py, x0, y0, x1, y1, r).any():
                return False
            # a capsule wholly inside the plan: its ends
            lx = np.array([x0, x1]) - x
            ly = np.array([y0, y1]) - y
            if ((np.abs(c * lx + s * ly) <= w / 2) & (np.abs(-s * lx + c * ly) <= d / 2)).any():
                return False
        others = self.plans + [poly for poly, g in self.props if group is None or g != group]
        for plan in others:
            if (_polygon_distance(px, py, plan) < SITE_GAP).any():
                return False
            # a plan wholly inside this one: its corners
            lx, ly = plan[:, 0] - x, plan[:, 1] - y
            if ((np.abs(c * lx + s * ly) <= w / 2) & (np.abs(-s * lx + c * ly) <= d / 2)).any():
                return False
        for poly, g in self.props:      # a Group's own members: touching, or a way apart
            if group is not None and g == group:
                gap = float(_polygon_distance(px, py, poly).min())
                if SITE_TOUCH < gap < SITE_GAP:
                    return False
        return True


def _site_clear(ctx: RoomContext, gx: np.ndarray, gy: np.ndarray) -> np.ndarray:
    """A Site's Site_Clear on its grid (step 10, design "Sites"): its approach and each
    opening's apron, and the margin round its own ground (the ``ground`` piece's reach less
    ``SITE_MARGIN``). Grown by half a cell, so no Prop's plan reaches into it from a cell
    whose middle lies just outside. Trees stand beyond the margin, so a Prop inside it is at
    least the margin from any trunk."""
    half = float(ctx.cell) / 2
    out = np.zeros(gx.shape, bool)
    for c in ctx.clear:
        what = c.get("what")
        if what == "ground":
            out |= ~_in_capsule(gx, gy, c["x0"], c["y0"], c["x1"], c["y1"], c["r"] - SITE_MARGIN - half)
        elif what in ("approach", "apron"):
            out |= _in_capsule(gx, gy, c["x0"], c["y0"], c["x1"], c["y1"], c["r"] + half)
    return out


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
        #: Where a player's middle can be: reached floor at least the player's half-width
        #: from a wall and from the foot of a rise he can't step (a dais's side, a solid
        #: Feature), as the gate reads it. Props stand on ``ok``; the room's connectivity
        #: (``problems``, ``check``) is judged on ``walk``.
        self.walk = self.ok & ~_near_rise(ctx, self.ok)
        # A solid Feature's plan is known exactly: off it by the half-width and half the
        # gate's own 2 u sample spacing (its samples needn't fall on these cells).
        for f in ctx.features:
            if f.get("kind") != "dais" and len(f.get("plan") or ()) >= 3:
                self.walk &= _polygon_distance(self.gx, self.gy, f["plan"]) >= PLAYER_HALF_WIDTH + 1.0
        #: How far a blocking Prop's plan is grown to take the floor it shuts: the player's
        #: half-width, and half a cell more, since the gate samples floor on its own 2 u grid,
        #: not this one, and a gap open on one can be shut on the other.
        self.grow = PLAYER_HALF_WIDTH + self.cell / 2
        #: Where the middle of a body ``CLEAR_WIDTH`` wide can be (a wall stands about half a
        #: cell short of the middle of the cell beyond it), and how far a blocking Prop's plan
        #: is grown to take it (the gate's 1 u samples read within half a cell).
        self.wide = self.ok & (_edge_distance(ctx, self.ok, WIDE_RADIUS + self.cell / 2)
                               >= WIDE_RADIUS + self.cell / 2)
        self.grow_wide = WIDE_RADIUS + self.cell / 2
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
        #: A Site's Props keep off its Site_Clear too, Dressing included (Req 11, P11).
        site_clear = _site_clear(ctx, self.gx, self.gy) if ctx.source == "site" else np.zeros(self.shape, bool)
        self.site = _SiteBounds(ctx) if ctx.source == "site" else None
        self.keep = ctx.spine | throats | door_cells | site_clear
        self.keep_dressing = ctx.spine | door_cells | site_clear
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
        #: The floor round the daises (the gate reads it under them too), and the dais cells a
        #: head or more over it (under those, it's floor a player stands on in the gate's view).
        self.under_dais: Optional[float] = None
        self.tall_dais = np.zeros(self.shape, bool)
        if self.dais.any():
            ring = binary_dilation(self.dais, np.ones((3, 3), bool), iterations=2) & self.ok & ~self.feature
            if ring.any():
                self.under_dais = float(np.nanmin(self.floor[ring]))
                with np.errstate(invalid="ignore"):
                    self.tall_dais = self.dais & (self.floor >= self.under_dais + HEAD_HEIGHT)
        # POIs' own spots: no footprint (grown by the player) covers one.
        self.poi_spot = np.zeros(self.shape, bool)
        for p in ctx.pois:
            self.poi_spot |= np.hypot(self.gx - p["x"], self.gy - p["y"]) <= self.cell * 0.75
        self.occupied = np.zeros(self.shape, bool)
        #: Blocking Props' plans grown by ``grow`` (layer 0), by ``grow_wide`` (layer 1), by
        #: the least the gate's clear width may take (layer 2), and not grown (layer 3).
        self.blocked = np.zeros((LAYERS,) + self.shape, bool)
        #: The same, as ``check`` reads them back: a wall Prop's plan about its origin, not its
        #: middle (the Prop doesn't record its reach off the wall). Placement keeps both clear,
        #: so its own room check can't find what placement let through (task 14).
        self.as_read = np.zeros((LAYERS,) + self.shape, bool)
        self.wall_props: List[Tuple[float, float, float, bool]] = []     # x, y, half-span, light
        self.ceiling_props: List[Tuple[float, float]] = []
        #: Blocking floor Props' plans (corners) and Groups, for ``BLOCKING_GAP``.
        self.plans: List[Tuple[np.ndarray, Optional[int]]] = []
        self._ea, self._eb = self._graph(self.walk)
        self.starts = self._starts(door_cells, self.walk, self._ea, self._eb)
        #: Where the way in is, for aiming Props: the doors' reached floor (else the starts).
        self.entry = door_cells & self.ok if (door_cells & self.ok).any() else self.starts
        self.before = self._joined(np.zeros(self.shape, bool))
        #: Reached floor beside the joined floor, and reached floor with no wall (or solid
        #: Feature) side by side with it: the gate's walls cover floor within the half-width of
        #: them, so a cell beside one may be covered, and one clear of them is free (``_pockets``).
        self.near_before = binary_dilation(self.before, np.ones((3, 3), bool))
        bad = np.pad(~self.ok, 1, constant_values=True)
        self.open = self.ok & ~(bad[:-2, 1:-1] | bad[2:, 1:-1] | bad[1:-1, :-2] | bad[1:-1, 2:])
        #: The same on all reached floor, uneroded: a neck ``walk`` reads shut can be open
        #: on the gate's own samples, so floor beyond it must stay joined on this one too.
        self._loose = (self.ok,) + self._graph(self.ok)
        self._loose_starts = self._starts(door_cells, *self._loose)
        self.loose_before = self._joined(np.zeros(self.shape, bool), loose=True)
        #: The strict reading joined only where a cell's rise to the next is a walkable slope
        #: (no steeper than the gate's 40° over a cell): a rise of 2-3 u over 2 u can be a step
        #: the gate takes or a bank it has no floor on. Floor joined this way before a Prop
        #: must stay joined this way (task 14: a barrel shut a terrace whose other way down was
        #: a 45° bank; a brazier shut a gutter below a rise). Floor joined only over such rises
        #: is judged on the other readings.
        self._gentle = (self.walk,) + self._graph(self.walk, self.cell * WALK_GRADE)
        self.gentle_before = self._joined(np.zeros(self.shape, bool), graph=self._gentle)
        #: Walkable floor the strict reading doesn't join (a gutter below a rise, a strip by a
        #: wall), and the cells within ``LANE_NEAR`` of it: whether such a lane is a way through
        #: and where it opens only the gate's own samples tell, so no blocking Prop stands on
        #: or by one (task 14: a torch over a dais's gutter, a brazier by a gutter's mouth,
        #: each cut it off).
        lane = self.walk & ~self.before
        self.by_lane = binary_dilation(lane, np.ones((3, 3), bool), iterations=LANE_NEAR)             if lane.any() else lane
        self.door_masks = [_in_rect(self.gx, self.gy, d.clear) for d in ctx.doors if d.clear]
        self.wide_doors = self._wide_doors(np.zeros(self.shape, bool))
        self.faces = self._faces()
        self.wall_xy = np.array([(w.x, w.y) for w in ctx.walls]).reshape(-1, 2)
        self.wall_n = np.array([(w.nx, w.ny) for w in ctx.walls]).reshape(-1, 2)

    # -- connectivity (the gate's "reached floor stays joined") ----------------

    def _graph(self, mask: np.ndarray, rise: float = STEP_UP) -> Tuple[np.ndarray, np.ndarray]:
        """The steps between side-by-side cells of ``mask`` a player takes (both ends),
        rising at most ``rise``."""
        nx, ny = self.shape
        idx = np.arange(nx * ny).reshape(nx, ny)
        f = np.where(mask, self.floor, np.nan)
        a, b = [], []
        with np.errstate(invalid="ignore"):
            right = mask[:-1, :] & mask[1:, :] & (np.abs(f[:-1, :] - f[1:, :]) <= rise)
            up = mask[:, :-1] & mask[:, 1:] & (np.abs(f[:, :-1] - f[:, 1:]) <= rise)
        a.append(idx[:-1, :][right]); b.append(idx[1:, :][right])
        a.append(idx[:, :-1][up]); b.append(idx[:, 1:][up])
        return np.concatenate(a), np.concatenate(b)

    def _starts(self, door_cells: np.ndarray, mask, ea, eb) -> np.ndarray:
        s = door_cells & mask
        if s.any():
            return s
        for c in self.ctx.clear:            # a Site: reached from its approach's far end
            if c.get("what") == "approach":
                pts = np.argwhere(mask)
                if len(pts):
                    d = np.hypot(self.xs[pts[:, 0]] - c["x1"], self.ys[pts[:, 1]] - c["y1"])
                    out = np.zeros(self.shape, bool)
                    out[tuple(pts[int(d.argmin())])] = True
                    return out
        if not mask.any():
            return mask.copy()
        # No door and no approach: the largest reached piece.
        n, lab = self._components(np.zeros(self.shape, bool), mask, ea, eb)
        lab = lab.reshape(self.shape)
        counts = np.bincount(lab[mask])
        return mask & (lab == int(counts.argmax()))

    def _components(self, blocked: np.ndarray, mask, ea, eb):
        nx, ny = self.shape
        free = (mask & ~blocked).ravel()
        keep = free[ea] & free[eb]
        m = csr_matrix((np.ones(int(keep.sum()), np.int8), (ea[keep], eb[keep])),
                       shape=(nx * ny, nx * ny))
        return connected_components(m, directed=False)

    def _joined(self, blocked: np.ndarray, loose: bool = False, graph=None) -> np.ndarray:
        """Reached floor (``walk``; ``loose``: all of ``ok``; or ``graph``'s) not blocked and
        joined to a door (or a Site's approach)."""
        mask, ea, eb = graph or (self._loose if loose else (self.walk, self._ea, self._eb))
        starts = self._loose_starts if loose else self.starts
        _n, lab = self._components(blocked, mask, ea, eb)
        lab = lab.reshape(self.shape)
        free = mask & ~blocked
        good = np.unique(lab[starts & free])
        return free & np.isin(lab, good)

    def _wide_doors(self, blocked: np.ndarray, maybe: Optional[np.ndarray] = None) -> List[bool]:
        """Which doors a body ``CLEAR_WIDTH`` wide walks from to the room's middle, read as
        the gate does: to the free wide floor nearest the middle. On the gate's own samples
        that can be any wide cell about as near that may be free (``maybe`` blocked: Props'
        plans grown the least they may be), a pocket among Props too, so then every one of
        those must be free and joined (else any free one)."""
        nx, ny = self.shape
        free = (self.wide & ~blocked).ravel()
        if self.ctx.source != "room" or not free.any():
            return [False] * len(self.door_masks)
        x0, y0, _z0, x1, y1, _z1 = self.ctx.box
        mid = np.hypot(self.gx - (x0 + x1) / 2, self.gy - (y0 + y1) / 2).ravel()
        may = free if maybe is None else (self.wide & ~maybe).ravel()
        d = np.where(may, mid, np.inf)
        targets = np.nonzero(d <= d.min() + 1.5 * self.cell)[0]
        strict = maybe is not None
        keep = free[self._ea] & free[self._eb]
        m = csr_matrix((np.ones(int(keep.sum()), np.int8), (self._ea[keep], self._eb[keep])),
                       shape=(nx * ny, nx * ny))
        lab = np.where(free, connected_components(m, directed=False)[1], -1)
        labels = np.unique(lab[targets[free[targets]]])
        # A target that may be free but reads blocked here goes with the free floor beside it.
        grid = lab.reshape(self.shape)
        pad = np.pad(grid, 1, constant_values=-1)
        beside = [set(int(v) for v in (pad[i, j + 1], pad[i + 2, j + 1], pad[i + 1, j], pad[i + 1, j + 2])
                      if v >= 0) for i, j in zip(*np.unravel_index(targets, self.shape))]
        out = []
        for door in self.door_masks:
            at = set(int(v) for v in np.unique(grid[door & (grid >= 0)]))
            if strict:
                out.append(all((lab[t] in at) if lab[t] >= 0 else bool(b & at)
                               for t, b in zip(targets, beside)))
            else:
                out.append(bool(at & set(int(v) for v in labels)))
        return out

    def footprint(self, x, y, yaw, w, d):
        """A blocking Prop's grown plan: (the cells grown by ``grow``, the ``LAYERS``-layer mask
        of it, of the plan grown by ``grow_wide``, of it grown the least the gate's clear width
        may take, and of the bare plan); None when its middle is off the grid."""
        # The yaw as the Prop records it, so ``check`` reads the same cells: a plan edge on a
        # cell's middle flips with the last bit of cos/sin (task 14).
        yaw = float(yaw) % (2 * math.pi)
        grown = self.rect_cells(x, y, yaw, w, d, self.grow, clip=True)
        wide = self.rect_cells(x, y, yaw, w, d, self.grow_wide, clip=True)
        least = self.rect_cells(x, y, yaw, w, d, max(0.0, WIDE_RADIUS - self.cell / 2), clip=True)
        bare = self.rect_cells(x, y, yaw, w, d, 0.0, clip=True)
        if grown is None or wide is None or least is None or bare is None:
            return None
        m = np.zeros((LAYERS,) + self.shape, bool)
        m[0][grown] = True
        m[1][wide] = True
        m[2][least] = True
        m[3][bare] = True
        return grown, m

    def _pockets(self, plans: np.ndarray) -> np.ndarray:
        """Reached floor outside every blocking Prop's plan that was beside the floor joined to
        the doors and, with the bare plans in the way, no longer is, where some of it is clear
        of the walls (no wall beside it) and it and the plans it lies against make
        ``WALLED_OFF`` or more. The gate reads a model only where it stands in its band, so
        floor under an overhang can join such a strip into a pocket no one model's plan holds,
        while the grown plans read the strip as blocked (task 21: a brazier's bowl over the
        strip between it and a notch in the wall, 64 u^2)."""
        ring = np.ones((3, 3), bool)
        pocket = self.loose_before & self.near_before & ~plans & \
            ~binary_dilation(self._joined(plans), ring)
        if not (pocket & self.open).any():
            return np.zeros(self.shape, bool)
        lab, _n = label(pocket | plans)
        out = np.zeros(self.shape, bool)
        for k in np.unique(lab[pocket & self.open]):
            piece = lab == k
            if piece.sum() * self.cell ** 2 >= WALLED_OFF:
                out |= piece & pocket
        return out

    def problems(self, blocked: np.ndarray) -> List[str]:
        """What a blocked mask (``LAYERS`` layers, as ``self.blocked``) breaks: floor cut off, a
        door or a POI no longer reached, a door's way narrower than ``CLEAR_WIDTH``."""
        wide_blocked, maybe, plans = blocked[1], blocked[2], blocked[3]
        blocked = blocked[0]
        after = self._joined(blocked)
        out = []
        cut = self.before & ~blocked & ~after
        loose_after = self._joined(blocked, loose=True)
        if not cut.any():
            cut = self.loose_before & self.walk & ~blocked & ~loose_after
        if not cut.any():
            cut = self.gentle_before & ~blocked & ~self._joined(blocked, graph=self._gentle)
        if not cut.any() and plans.any():
            cut = self._pockets(plans)
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
            # Floor round it at its own level (the gate's step), on either reading: the gate's
            # samples needn't fall on these cells, so it keeps a cell surely in reach (half a
            # cell in) where it had one, else loses none that may be.
            with np.errstate(invalid="ignore"):
                level = np.abs(self.floor - float(p.get("z", 0.0))) <= STEP_UP
            dist = np.hypot(self.gx - p["x"], self.gy - p["y"])
            near = (dist <= POI_REACH + self.cell / 2) & level
            sure = (dist <= POI_REACH - self.cell / 2) & level
            if any((near & was).any() and (not (sure & now).any() if (sure & was).any()
                                           else (near & was & ~now).any())
                   for was, now in ((self.before, after), (self.loose_before, loose_after))):
                out.append(f"POI {k} ({p.get('purpose')}) no longer reached")
        if any(self.wide_doors) and wide_blocked.any():
            for k, (was, now) in enumerate(zip(self.wide_doors, self._wide_doors(wide_blocked, maybe))):
                if was and not now:
                    out.append(f"door {k}'s way under {CLEAR_WIDTH:g} u clear")
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

    def into_a_wall(self, w: WallFace, across: float, half: float) -> bool:
        """A wall Prop's plan on face ``w`` (``across`` off it, ``half`` either way along it)
        crosses another wall turned from it: at an inside corner its side would stand in the
        wall beside it (task 14: a torch 0.68 u into the next wall)."""
        if not len(self.wall_xy):
            return False
        n = np.array([w.nx, w.ny])
        t = np.array([-w.ny, w.nx])
        o = np.array([w.x, w.y])
        corners = np.array([o + n * a + t * s for a in (0.0, across) for s in (-half, half)])
        reach = half + across + WALL_TURN_NEAR
        near = (np.hypot(*(self.wall_xy - o).T) <= reach) & (self.wall_n @ n < 0.5)
        if not near.any():
            return False
        q, m = self.wall_xy[near], self.wall_n[near]
        # each corner against each turned face near it (within the samples' step of it)
        rel = corners[:, None, :] - q[None, :, :]
        close = np.hypot(rel[..., 0], rel[..., 1]) <= WALL_TURN_NEAR
        behind = np.einsum("cqk,qk->cq", rel, m) < -WALL_FLUSH
        return bool((close & behind).any())

    def spaced(self, x: float, y: float, yaw: float, w: float, d: float, group: Optional[int],
               plans: np.ndarray) -> bool:
        """A blocking floor Prop's plan keeps ``BLOCKING_GAP`` off every other blocking floor
        Prop's plan (its own Group's members excepted), or the gaps nearer shut no pocket: with
        them closed (each pair's hull in the way, on top of ``plans``, every blocking plan with
        this one) ``_pockets`` finds none. Plans that nearly touch are no exception: a model's
        body can stand well inside its plan (task 21: two rocks' plans 1.2 u apart, their
        bodies further, by a wall). Plans never overlap (``occupied``), so a gap is the least
        distance from a corner of one to the other."""
        if not self.plans:
            return True
        mine = _SiteBounds.corners(x, y, float(yaw) % (2 * math.pi), w, d)
        seams = []
        for plan, g in self.plans:
            if group is not None and g == group:
                continue
            gap = min(float(_polygon_distance(mine[:, 0], mine[:, 1], plan).min()),
                      float(_polygon_distance(plan[:, 0], plan[:, 1], mine).min()))
            if gap < BLOCKING_GAP - 0.01:
                seams.append(plan)
        if not seams:
            return True
        shut = plans.copy()
        for plan in seams:
            shut |= _in_polygon(self.gx, self.gy, _hull(np.vstack([mine, plan])))
        return not self._pockets(shut).any()

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
    """Models by (kind, Mount filled, Set), and the room's culture and condition as they bind.

    **Condition** (archive decision 25): a room's Props never mix ``ruined`` and ``pristine``.
    The first Prop placed with either binds the room to it, so the choice falls on the room's
    own stream with no draw of its own; ``unknown`` goes with either. With every model
    ``unknown`` nothing is filtered and the draws are the same as without the rule."""

    def __init__(self, catalogue: Catalogue, rules: DecorRules, ctx: RoomContext, rng: random.Random):
        self.rules = rules
        self.rng = rng
        self.sets = rules.sets.sets_for(ctx.zone_type, ctx.race, ctx.theme)
        self.used: List[str] = []
        self.condition: Optional[str] = None
        self.by: Dict[Tuple[str, str, str], List[Model]] = {}
        # A Site stands on open ground the wilderness gate judges: only models its screen
        # takes (the catalogue's ``open_ground``, measured once by prop_catalogue.py screen).
        site = ctx.source == "site"
        for key in sorted(catalogue.models):
            m = catalogue.models[key]
            t = m.tags
            if t.use != "yes" or m.animation == "skeletal" or t.set not in self.sets:
                continue
            if site and m.open_ground is not True:
                continue
            self.by.setdefault((t.kind, t.mount, t.set), []).append(m)

    def fits(self, s: str) -> bool:
        return all(self.rules.sets.may_share(s, u) for u in self.used)

    def suits(self, m: Model) -> bool:
        """The model's condition goes with the room's (``unknown`` with any)."""
        c = m.tags.condition
        return c == UNKNOWN or self.condition is None or c == self.condition

    def choose(self, kinds: Sequence[str], mount: str) -> Optional[Model]:
        for kind in kinds:
            for s in self.sets:
                if not self.fits(s):
                    continue
                pool = [m for mt in MOUNTS_FILLING[mount] for m in self.by.get((kind, mt, s), ())
                        if self.suits(m)]
                if mount == "wall":
                    pool = [m for m in pool if not _sunk(m)] or pool
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
                    for m in self.by.get((kind, mt, s), ()) if area(m) < limit - 1e-9 and self.suits(m)]
            if pool:
                out.append(min(pool, key=lambda m: (area(m), m.key)))
        return out[:FALLBACKS]

    def bind(self, model: Model) -> None:
        s = model.tags.set
        if s != NEUTRAL and s not in self.used:
            self.used.append(s)
        if self.condition is None and model.tags.condition != UNKNOWN:
            self.condition = model.tags.condition


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
                list(self.chooser.used), len(self.out.props), self.chooser.condition,
                len(r.site.props) if r.site is not None else 0, r.as_read.copy(), len(r.plans))

    def _restore(self, s) -> None:
        r = self.room
        r.occupied, r.blocked, r.as_read = s[0].copy(), s[1].copy(), s[8].copy()
        del r.plans[s[9]:]
        r.wall_props, r.ceiling_props, self.chooser.used, n = list(s[2]), list(s[3]), list(s[4]), s[5]
        self.chooser.condition = s[6]
        del self.out.props[n:]
        if r.site is not None:
            del r.site.props[s[7]:]

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
                  dressing: bool = False, group: Optional[int] = None):
        """(cells, z, blocked mask, blocks) if the model can stand here, else None. ``allow``: Feature
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
        if r.site is not None and not r.site.fits(x, y, yaw, sz.w, sz.d, group):
            return None
        fl = r.floor[cells]
        if float(fl.max() - fl.min()) > FLAT:
            return None
        # Its bottom on the lowest floor under its plan (just over it: a flat rug would
        # flicker in it), not under the margin round it: that would sink it.
        under = r.rect_cells(x, y, yaw, sz.w, sz.d)
        under = r.floor[under] if under is not None else fl
        under = under[~np.isnan(under)]
        z = float(under.min() if len(under) else fl.min()) + sz.below + LIFT
        if r.ceiling is not None:
            ce = r.ceiling[cells]
            ce = ce[~np.isnan(ce)]
            if len(ce) and float(ce.min()) < z + sz.h + 0.5:
                return None
        foot = r.footprint(x, y, yaw, sz.w, sz.d)
        if foot is None:
            return None
        grown, mask = foot
        if r.poi_spot[grown].any():
            return None
        # Over a dais a head or more tall the gate reads the room's floor under it too, open
        # where a stair's lowest steps are under the band: a model sunk into the dais's edge
        # (on a stair's top step) stands in that floor's band and cuts it (task 21: a throne,
        # 192 u^2). Its bottom stays a head over the floor under the dais.
        if _blocking(model) and r.under_dais is not None and \
                r.tall_dais[grown].any() and z - sz.below < r.under_dais + HEAD_HEIGHT + BAND_SLACK:
            return None
        # It's in the way where its top stands more than a step over the floor round it
        # (the gate's band, read from the floor the player stands on, not the Prop's).
        ground = r.floor[grown]
        ground = ground[~np.isnan(ground)]
        low = float(ground.min()) if len(ground) else z
        blocks = _blocking(model) and z + sz.h >= low + STEP_UP - BAND_SLACK
        # At a Site, a top about a step over the ground round it is half in the gate's band
        # and half not: the part out of it reads as ground a player stands on, walled in by
        # the part in it (a pocket cut off, room-decor task 13). Over or under it, clearly.
        if r.site is not None and _blocking(model) and len(ground) and \
                z + sz.h - float(ground.max()) < STEP_UP + SITE_STEP_SLACK and \
                z + sz.h - low > STEP_UP - SITE_STEP_SLACK:
            return None
        blocked, as_read = r.blocked, r.as_read
        if blocks:
            if not dressing and (mask[0] & r.by_lane).any():     # a POI's own dressing may
                return None
            if not r.spaced(x, y, yaw, sz.w, sz.d, group, r.blocked[3] | mask[3]):
                return None
            blocked, as_read = r.blocked | mask, r.as_read | mask
            if r.problems(blocked) or r.problems(as_read):
                return None
        return cells, z, (blocked, as_read), blocks

    def _put_floor(self, model, sz, spots, step, line, at, allow=None, poi=None, group=None,
                   mount="floor") -> Optional[Prop]:
        for x, y, yaw in spots:
            got = self._floor_ok(model, sz, x, y, yaw, allow, step == "dressing", group)
            if got is None:
                continue
            cells, z, blocked, blocks = got
            self.room.occupied[cells] = True
            if self.room.site is not None:
                self.room.site.add(x, y, yaw, sz.w, sz.d, group)
            self.room.blocked, self.room.as_read = blocked
            if blocks:
                self.room.plans.append((_SiteBounds.corners(x, y, float(yaw) % (2 * math.pi), sz.w, sz.d), group))
            return self._prop(model, sz, x, y, z, yaw, mount, blocks, step, line, at, poi, group)
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
        s = np.argwhere(r.entry)
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
        """Next to ``prev`` along its own Y (a row), either side. After a blocking Prop the gap
        is ``ROW_GAP_BLOCKING``: two round models a step apart shut the floor between their
        curves off from the room, a pocket in neither one's plan that the gate fails (task 14:
        braziers 1 u apart in a row, 68-76 u^2 each)."""
        step = (prev.d + sz.d) / 2 + (ROW_GAP_BLOCKING if prev.blocks else GAP)
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
        # Its measured side to the wall, its own reach to that side off the wall (flush;
        # the build then sets it on the wall mesh itself), else stock's distance.
        across = sz.w if sz.side[1] == 0.0 else sz.d          # its depth off the wall
        if sz.back is not None:
            off = sz.back + WALL_FLUSH
        else:
            off = sz.wall if sz.wall is not None and sz.wall <= across + 1.0 else across / 2 + 0.1
        half = (sz.d if sz.side[1] == 0.0 else sz.w) / 2
        turn = math.pi - math.atan2(sz.side[1], sz.side[0])
        for f in faces:
            w = f.face
            z = f.floor + over
            if z + sz.h > w.top - 0.25 or z - sz.below < w.bottom - 0.01:
                continue
            if r.into_a_wall(w, across, half):
                continue
            x, y = w.x + w.nx * off, w.y + w.ny * off
            if any(math.hypot(x - px, y - py) < (spacing if light and plight else half + ph + GAP)
                   for px, py, ph, plight in r.wall_props):
                continue
            yaw = math.atan2(w.ny, w.nx) + turn
            blocks = _blocking(model) and z - sz.below < f.floor + HEAD_HEIGHT and z + sz.h > f.floor + STEP_UP
            blocked, as_read = r.blocked, r.as_read
            if blocks:
                # Its plan about its middle: a model's depth off the wall from its back.
                mid = across / 2 - off
                foot = r.footprint(x + w.nx * mid, y + w.ny * mid, yaw, sz.w, sz.d)
                seen = r.footprint(x, y, yaw, sz.w, sz.d)
                if foot is None or seen is None or r.poi_spot[foot[0]].any():
                    continue
                # Not across a lane of floor the strict reading doesn't join (walk, not in
                # ``before``): whether it is a way through only the gate's own samples tell.
                # A torch over a 3 u gutter between a dais and its wall cut the gutter off
                # (task 14, dungeon seed 11).
                if (foot[1][0] & r.by_lane).any():
                    continue
                blocked, as_read = r.blocked | foot[1], r.as_read | seen[1]
                if r.problems(blocked) or r.problems(as_read):
                    continue
            r.blocked, r.as_read = blocked, as_read
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
                    # On the anchor's top: a smaller model of the kinds when this one overhangs
                    # it, and none when nothing fits (a laid table may stand bare; task 14).
                    for pick in [model] + self.chooser.smaller(m.kinds, m.mount, model):
                        got = self._stack(a, pick, size_of(pick), step, line, gid)
                        if got is not None:
                            break
                    continue
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
        z = a.z + a.h + sz.below + LIFT     # its bottom on the anchor's top
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
        x, y = a.x + c * jx - s * jy, a.y + s * jx + c * jy
        yaw = a.yaw + self.rng.uniform(-0.4, 0.4)
        # On a low anchor (a table under a step tall) a stacked model can stand in the gate's
        # band, a step to a head over the floor round it: then it's in the way as a floor Prop
        # is (task 21: a candle on a table narrowed a door's way under the clear width).
        blocks = False
        if _blocking(model):
            foot = r.footprint(x, y, yaw, sz.w, sz.d)
            if foot is None:
                return None
            grown, mask = foot
            ground = r.floor[grown]
            ground = ground[~np.isnan(ground)]
            lo = float(ground.min()) if len(ground) else a.z - a.below
            hi = float(ground.max()) if len(ground) else lo
            blocks = z - sz.below < hi + HEAD_HEIGHT and z + sz.h >= lo + STEP_UP - BAND_SLACK
            if blocks:
                if r.poi_spot[grown].any() or (step != "dressing" and (mask[0] & r.by_lane).any()):
                    return None
                blocked, as_read = r.blocked | mask, r.as_read | mask
                if r.problems(blocked) or r.problems(as_read):
                    return None
                r.blocked, r.as_read = blocked, as_read
        return self._prop(model, sz, x, y, z, yaw, "raised", blocks, step, line, "stack", group=gid)

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
          control: str = DEFAULT_CONTROL, decor_seed: Optional[int] = None,
          may_be_bare: bool = True) -> Decorated:
    """Decorate one room (or Site, or corridor) from its context alone. ``rules`` and
    ``catalogue`` default to the shipped ones; ``control`` is the Decor control (``none``
    places nothing); ``decor_seed`` salts the stream (default: the context's seed).
    ``may_be_bare=False`` places the room in full even when it draws ``bare`` (the draw is
    still made, so the rest of the stream is the same): the build's cap on a zone's bare rooms
    (``generators.builder.decor_for``)."""
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
    p.out.bare = rng.random() < weights[BARE] and may_be_bare
    if p.out.bare:
        return p.out
    lines = [ln for recipe in rules.recipe_for(context.room_type, context.kind, context.source, context.zone_type)
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
    blocked = np.zeros((LAYERS,) + room.shape, bool)
    for p in decorated.props:
        if not p.blocks:
            continue
        foot = room.footprint(p.x, p.y, p.yaw, p.w, p.d)
        if foot is None:
            return [f"{p.key} at ({p.x:.0f}, {p.y:.0f}) stands outside the room"]
        blocked |= foot[1]
    return room.problems(blocked)


__all__ = ["CORRIDOR", "Decorated", "Drop", "FRAME", "HEAD_HEIGHT", "LIGHT_SPACING", "PLAYER_HALF_WIDTH",
           "POI_REACH", "Prop", "Room", "SITE_MARGIN", "STEPS", "Size", "check", "place", "size_of", "stream"]
