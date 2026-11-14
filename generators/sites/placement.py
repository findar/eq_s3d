"""Where Sites stand (roadmap step 10, Requirements 4 and 6; design "Sites").

:func:`place_sites` is a pure function of the World's terrain (with earlier Attachments'
Terrain edits applied), its ``ground`` Socket (world-sockets task 5) and its point Site
Sockets (step 13), the Site rules (``generators/sites/rules.py``), the biome, the Sites
control and the seed. It draws
from its OWN salted stream (``_salted_seed(seed, *SITES_SALT)``), so the terrain's stream
never moves and the TER is never touched (archive decision 1: Sites stand on unchanged
ground). A Site is placed in three moves:

- **where**: centred on a point the World offered, of a kind that fits it: the recipe's
  ground and margin within the point's Free radius at its slope, clear of Kept_Clear (the
  ``ground`` Socket's, e.g. an outdoor dungeon's rooms, plus any ``keep_clear`` shapes the
  caller adds) and of earlier Sites; the kind drawn by weight and the recipe's likes (near
  water, high or low ground, by a zoneline, a clearing) read off the point
  (``_place_on_points``);
- **what**: the recipe's Structures, arranged round the centre (ring, row, cluster, lone,
  perimeter; facing in, out or any; a ``side = "open"`` line on the Site's flank);
- **keep clear**: its Site_Clear: an approach from open ground beyond the Site to its middle,
  an apron in front of each Enterable Structure's opening, and the margin round its ground.
  No Structure may stand in it; one that would is dropped and recorded.

Anything that can't fit (a Site with no ground, a Structure with no room, a POI whose
Structure dropped) is dropped and recorded with a reason; placement never fails (Req 4.3).
Every kept Site names at least one POI, each on ground reached from Spawn (Req 6.1).

The result is plain data (:class:`SitePlacement`); the build (task 7) turns it into models,
ZON objects and the sidecar, and hands :meth:`SitePlacement.clear_shapes` to the trees as
``place_trees(..., keep_clear=...)`` so trees keep off Site ground.

Frames: world XY, Z up; Z is read from the TER under the point. A Structure's ``yaw`` is the
way its front (an opening, if it has one) faces, in radians counter-clockwise from +X. A run
(fence, ruin wall) lies across its yaw: its ``radius`` is the run's half-length.
"""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from scipy.ndimage import distance_transform_edt, label

from analyzer.footprints import CLEAR_WIDTH as _GATE_CLEAR_WIDTH
from generators.sites.rules import (
    CENTRE,
    DEFAULT_DENSITY,
    ENTRANCE,
    Line,
    SiteRecipe,
    SiteRules,
    load_sites,
)
from generators.vegetation.placement import (
    ClearShape,
    Ground,
    ground_of,
    shapes_touch_quads,
)

#: The salt of the Sites' own stream: ``_salted_seed(seed, "sites", "placement")``.
SITES_SALT: Tuple[str, ...] = ("sites", "placement")
#: The width a player needs: an approach's width, an apron's, and the least gap between two
#: Structures (so a player walks between them). The gate's own clear width (archive
#: decision 9: 8 u; the player is 3 u wide), so placement leaves what the gate demands.
CLEAR_WIDTH = _GATE_CLEAR_WIDTH
#: How deep the clear apron in front of an Enterable Structure's opening reaches.
APRON_DEPTH = 8.0
#: Half the thickness of a run (fence, ruin wall) for spacing and the Site_Clear.
RUN_HALF_THICK = 1.0
#: Structures laid as runs: ``radius`` is the run's half-length, the run lies across its yaw.
RUN_STRUCTURES = frozenset({"fence", "ruin_wall"})
#: Steepest ground the walker stands on (``AgentModel.walkable_slope_deg``): reached ground.
WALK_SLOPE_DEG = 40.0
#: The approach must find walkable reached ground this far beyond the Site's margin.
APPROACH_REACH = 40.0
APPROACH_DIRECTIONS = 16
#: Likes fade to nothing at these distances.
NEAR_WATER_REACH = 400.0
ZONELINE_REACH = 600.0
#: The clearing like: share of eligible ground within this many quads of the centre (the
#: World measures it per point, ``sites.points``).
CLEARING_QUADS = 2
#: Tries a cluster or lone Structure gets to find room.
CLUSTER_TRIES = 40
#: How far in front of a solid Structure its POI stands.
POI_OFFSET = 2.0

#: Drop reasons (the sidecar's words).
NO_APPROACH = "no approach from open ground"
NO_ROOM = "no room on its arrangement"
OUTSIDE = "outside its Site's ground"
IN_CLEAR = "in its Site_Clear"
CROWDED = "too close to another Structure"
APRON_OFF = "its opening's apron leaves the Site's ground"
APRON_BLOCKED = "its opening's apron is blocked"
STRUCTURE_GONE = "its Structure dropped"
NO_FREE_GROUND = "no free ground beside its Structure"
NO_POI = "no POI left"
NO_STRUCTURES = "no Structure left"
NO_POINT = "no point fits its recipe"

_WET = ("water", "river", "lava")
_EPS = 1e-6


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlacedStructure:
    """One Structure: its model (kind and the Inhabitant's variant), where it stands, its yaw
    (the way its front faces), its radius (a run's half-length) and whether it's a run."""
    kind: str
    variant: str
    x: float
    y: float
    z: float
    yaw: float
    radius: float
    run: bool = False
    enterable: bool = False

    def footprint(self) -> ClearShape:
        """The Structure's ground shape as a capsule ``(x0, y0, x1, y1, r)``."""
        return _footprint(self.kind in RUN_STRUCTURES, self.x, self.y, self.yaw, self.radius)


@dataclass(frozen=True)
class POIPoint:
    """A Site's named point (advisory, sidecar only, Req 6.2)."""
    name: str
    purpose: str
    x: float
    y: float
    z: float
    at: str


@dataclass(frozen=True)
class ClearArea:
    """One piece of a Site's Site_Clear (or its ground): ``what`` is ``ground`` (the Site's
    ground and margin), ``approach`` or ``apron``; the shape is a capsule."""
    what: str
    x0: float
    y0: float
    x1: float
    y1: float
    r: float

    @property
    def shape(self) -> ClearShape:
        return (self.x0, self.y0, self.x1, self.y1, self.r)


@dataclass(frozen=True)
class Drop:
    """Something that didn't fit, and why. ``what`` is ``site``, ``structure`` or ``poi``;
    ``site`` is the kept Site's index (None when the Site itself dropped)."""
    what: str
    kind: str
    reason: str
    inhabitant: str = ""
    site: Optional[int] = None


@dataclass(frozen=True)
class Site:
    kind: str
    inhabitant: str
    x: float
    y: float
    z: float
    radius: float
    margin: float
    approach_yaw: float
    structures: Tuple[PlacedStructure, ...]
    pois: Tuple[POIPoint, ...]
    clear: Tuple[ClearArea, ...]
    #: The point Socket's id the Site stands on (step 13). None only on a Site made by hand,
    #: whose JSON form then leaves the key out.
    socket: Optional[str] = None


def _site_dict(s: Site) -> dict:
    d = asdict(s)
    if d["socket"] is None:
        del d["socket"]
    return d


@dataclass
class SitePlacement:
    """The Sites of one zone, what dropped, and the count's inputs."""
    sites: List[Site]
    drops: List[Drop]
    target: int
    walkable_area: float
    control: str
    band: Tuple[float, float]
    counts: Dict[str, int] = field(default_factory=dict)

    def clear_shapes(self) -> Tuple[ClearShape, ...]:
        """Every Site's ground and Site_Clear, for ``place_trees(..., keep_clear=...)``."""
        return tuple(c.shape for s in self.sites for c in s.clear)

    def to_dict(self) -> dict:
        return {"control": self.control, "target": self.target,
                "walkable_area": self.walkable_area, "band": list(self.band),
                "sites": [_site_dict(s) for s in self.sites], "drops": [asdict(d) for d in self.drops]}


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def _footprint(run: bool, x: float, y: float, yaw: float, radius: float) -> ClearShape:
    if not run:
        return (x, y, x, y, radius)
    tx, ty = -math.sin(yaw), math.cos(yaw)
    return (x - tx * radius, y - ty * radius, x + tx * radius, y + ty * radius, RUN_HALF_THICK)


def _point_segment(px: float, py: float, s: ClearShape) -> float:
    x0, y0, x1, y1, _ = s
    vx, vy = x1 - x0, y1 - y0
    ll = vx * vx + vy * vy
    t = 0.0 if ll == 0 else min(max(((px - x0) * vx + (py - y0) * vy) / ll, 0.0), 1.0)
    return math.hypot(px - (x0 + t * vx), py - (y0 + t * vy))


def _cross(a: ClearShape, b: ClearShape) -> bool:
    def orient(px, py, qx, qy, rx, ry):
        return (qx - px) * (ry - py) - (qy - py) * (rx - px)
    ax0, ay0, ax1, ay1, _ = a
    bx0, by0, bx1, by1, _ = b
    d1, d2 = orient(bx0, by0, bx1, by1, ax0, ay0), orient(bx0, by0, bx1, by1, ax1, ay1)
    d3, d4 = orient(ax0, ay0, ax1, ay1, bx0, by0), orient(ax0, ay0, ax1, ay1, bx1, by1)
    return d1 * d2 < 0 and d3 * d4 < 0


def gap(a: ClearShape, b: ClearShape) -> float:
    """The free distance between two capsules (negative when they overlap)."""
    if _cross(a, b):
        core = 0.0
    else:
        core = min(_point_segment(a[0], a[1], b), _point_segment(a[2], a[3], b),
                   _point_segment(b[0], b[1], a), _point_segment(b[2], b[3], a))
    return core - a[4] - b[4]


def reach(s: ClearShape, cx: float, cy: float) -> float:
    """How far from ``(cx, cy)`` the capsule reaches."""
    return max(math.hypot(s[0] - cx, s[1] - cy), math.hypot(s[2] - cx, s[3] - cy)) + s[4]


def _quad_slope_deg(h: np.ndarray, res: float) -> np.ndarray:
    """Per quad, the steeper of its two TER triangles' slopes (degrees)."""
    ha, hb, hc, hd = h[:-1, :-1], h[1:, :-1], h[1:, 1:], h[:-1, 1:]
    s1 = np.hypot(hb - ha, hc - hb)
    s2 = np.hypot(hc - hd, hd - ha)
    return np.degrees(np.arctan(np.maximum(s1, s2) / res))


def _corners_all(mask: np.ndarray) -> np.ndarray:
    return mask[:-1, :-1] & mask[1:, :-1] & mask[1:, 1:] & mask[:-1, 1:]


def _corners_any(mask: np.ndarray) -> np.ndarray:
    return mask[:-1, :-1] | mask[1:, :-1] | mask[1:, 1:] | mask[:-1, 1:]


@dataclass
class _Terrain:
    """What placement reads of the landscape, per TER quad."""
    ground: Ground               # TER heights; ``eligible`` = the trees' Eligible_Ground
    reached: np.ndarray          # walkable quads joined to Spawn's
    base: np.ndarray             # Site-eligible before the recipe's slope
    slope: np.ndarray            # degrees
    water_d: Optional[np.ndarray]
    zoneline_d: Optional[np.ndarray]
    height_rank: np.ndarray      # 0 (lowest reached quad) .. 1 (highest)
    spawn_xy: Tuple[float, float]

    def quad_at(self, x: float, y: float) -> Optional[Tuple[int, int]]:
        i, j, _, _ = self.ground.quad_of(x, y)
        nqx, nqy = self.reached.shape
        return (i, j) if 0 <= i < nqx and 0 <= j < nqy else None


def _terrain(terrain, spawn_xy: Tuple[float, float],
             keep_clear: Sequence[ClearShape]) -> _Terrain:
    ground = ground_of(terrain, spawn_xy)
    h, res = ground.heights, ground.res
    node = np.asarray(terrain.node_type)
    slope = _quad_slope_deg(h, res)

    wet_nodes = np.isin(node, _WET)
    walk = (slope <= WALK_SLOPE_DEG) & ~_corners_any(wet_nodes) & ~_corners_any(terrain.rim_seal.astype(bool))
    labels, _ = label(walk)
    reached = np.zeros_like(walk)
    si, sj, _, _ = ground.quad_of(*spawn_xy)
    si = min(max(si, 0), walk.shape[0] - 1)
    sj = min(max(sj, 0), walk.shape[1] - 1)
    if labels[si, sj]:
        reached = labels == labels[si, sj]

    base = ground.eligible & reached & _corners_all(np.asarray(terrain.playable_interior, dtype=bool))
    if keep_clear:
        base &= ~shapes_touch_quads(base.shape, ground.origin, res, keep_clear)

    def dist_to(mask_nodes: np.ndarray) -> Optional[np.ndarray]:
        q = _corners_any(mask_nodes)
        return distance_transform_edt(~q) * res if q.any() else None

    rank = np.zeros(walk.shape)
    if reached.any():
        hq = (h[:-1, :-1] + h[1:, :-1] + h[1:, 1:] + h[:-1, 1:]) / 4.0
        vals = np.sort(hq[reached])
        rank = np.searchsorted(vals, hq, side="right") / float(len(vals))
    return _Terrain(ground=ground, reached=reached, base=base, slope=slope,
                    water_d=dist_to(wet_nodes), zoneline_d=dist_to(node == "zoneline_gap"),
                    height_rank=np.clip(rank, 0.0, 1.0), spawn_xy=spawn_xy)


# ---------------------------------------------------------------------------
# Where
# ---------------------------------------------------------------------------

def approach_way(cx: float, cy: float, outer: float, yaw: float) -> ClearShape:
    """The way in beyond a Site's ground: from its margin out ``APPROACH_REACH`` along ``yaw``,
    a player's clear width across."""
    fx, fy = math.cos(yaw), math.sin(yaw)
    return (cx + fx * outer, cy + fy * outer, cx + fx * (outer + APPROACH_REACH),
            cy + fy * (outer + APPROACH_REACH), CLEAR_WIDTH / 2)


def _approach(t: _Terrain, cx: float, cy: float, outer: float, rng: random.Random,
              avoid: Sequence[ClearShape] = ()) -> Optional[float]:
    """The way in: of the directions whose ground beyond the Site is reached and walkable all
    the way out to ``APPROACH_REACH``, the one facing Spawn most (with a little chance).
    ``avoid``: shapes the way in may not meet (earlier Sites' grounds, Req 3.7)."""
    to_spawn = math.atan2(t.spawn_xy[1] - cy, t.spawn_xy[0] - cx)
    best, best_score = None, -math.inf
    steps = max(2, int(math.ceil(APPROACH_REACH / (t.ground.res / 2))))
    for k in range(APPROACH_DIRECTIONS):
        a = 2 * math.pi * k / APPROACH_DIRECTIONS
        if avoid:
            way = approach_way(cx, cy, outer, a)
            if any(gap(way, s) < 0 for s in avoid):
                continue
        ok = True
        for s in range(steps + 1):
            d = outer + APPROACH_REACH * s / steps
            q = t.quad_at(cx + d * math.cos(a), cy + d * math.sin(a))
            if q is None or not t.reached[q]:
                ok = False
                break
        if not ok:
            continue
        score = math.cos(a - to_spawn) + 0.5 * rng.random()
        if score > best_score:
            best, best_score = a, score
    return best


# ---------------------------------------------------------------------------
# What: arranging a recipe's Structures
# ---------------------------------------------------------------------------

_PRIORITY = {CENTRE: 0, "ring": 2, "perimeter": 2, "row": 3, "lone": 4, "cluster": 4}


def _line_order(lines: Sequence[Line]) -> List[Line]:
    """Centre first, then a line on the open side, the ring or perimeter, rows, then the rest
    (which find room among them)."""
    def key(ix):
        i, line = ix
        return (0 if line.at == CENTRE else 1 if line.side == "open" else _PRIORITY[line.at], i)
    return [line for _, line in sorted(enumerate(lines), key=key)]


class _Arranger:
    def __init__(self, rules: SiteRules, recipe: SiteRecipe, cx: float, cy: float, approach: float,
                 rng: random.Random):
        self.rules, self.recipe, self.rng = rules, recipe, rng
        self.cx, self.cy, self.a = cx, cy, approach
        self.R = recipe.ground.radius
        self.outer = recipe.ground.radius + recipe.ground.margin
        self.kept: List[Tuple[PlacedStructure, ClearShape, int]] = []   # (structure, shape, line id)
        self.clear: List[ClearArea] = []
        self.reserved: List[ClearShape] = []    # ground a line keeps for itself (a corral's yard)
        self.drops: List[Tuple[str, str]] = []  # (Structure kind, reason)
        self.open_side = approach + (math.pi / 2 if rng.random() < 0.5 else -math.pi / 2)
        self.inner = 0.0

    # -- checks -----------------------------------------------------------
    def _misfit(self, shape: ClearShape, line_id: int, apron: Optional[ClearShape],
                check_reserved: bool) -> Optional[str]:
        if reach(shape, self.cx, self.cy) > self.R + _EPS:
            return OUTSIDE
        if any(gap(shape, c.shape) < -_EPS for c in self.clear if c.what != "ground"):
            return IN_CLEAR
        for _, other, lid in self.kept:
            same_run = lid == line_id and shape[4] == RUN_HALF_THICK
            # Runs of one line may meet end to end (a pen's corners); nothing else may come
            # nearer than a player's way between.
            if gap(shape, other) < (-2 * RUN_HALF_THICK if same_run else CLEAR_WIDTH) - _EPS:
                return CROWDED
        if check_reserved and any(gap(shape, r) < -_EPS for r in self.reserved):
            return CROWDED
        if apron is not None:
            if reach(apron, self.cx, self.cy) > self.outer + _EPS:
                return APRON_OFF
            if any(gap(apron, other) < -_EPS for _, other, _ in self.kept):
                return APRON_BLOCKED
        return None

    def _try(self, line: Line, line_id: int, x: float, y: float, yaw: float,
             check_reserved: bool = True) -> Optional[str]:
        st = self.rules.structures[line.kind]
        run = line.kind in RUN_STRUCTURES
        shape = _footprint(run, x, y, yaw, st.radius)
        apron = None
        if st.enterable and not run:
            # A capsule covering the APRON_DEPTH in front of the opening, CLEAR_WIDTH wide.
            fx, fy = math.cos(yaw), math.sin(yaw)
            w = CLEAR_WIDTH / 2
            d0, d1 = st.radius + w, st.radius + max(APRON_DEPTH - w, w)
            apron = (x + fx * d0, y + fy * d0, x + fx * d1, y + fy * d1, w)
        why = self._misfit(shape, line_id, apron, check_reserved)
        if why is None:
            s = PlacedStructure(kind=line.kind, variant=line.variant, x=x, y=y, z=0.0, yaw=_wrap(yaw),
                                radius=st.radius, run=run, enterable=st.enterable)
            self.kept.append((s, shape, line_id))
            if apron is not None:
                self.clear.append(ClearArea("apron", *apron))
        return why

    def _yaw(self, line: Line, x: float, y: float, enterable: bool) -> float:
        to_centre = math.atan2(self.cy - y, self.cx - x)
        if line.face == "in":
            return to_centre
        if line.face == "out":
            return to_centre + math.pi
        if enterable:   # an opening faces the yard, or the way in from the middle
            return self.a if math.hypot(x - self.cx, y - self.cy) < 1e-6 else to_centre
        return self.rng.uniform(-math.pi, math.pi)

    # -- arrangements -----------------------------------------------------
    def place_line(self, line: Line, line_id: int) -> None:
        rng = self.rng
        if line.chance < 1.0 and rng.random() >= line.chance:
            return
        n = rng.randint(*line.count)
        if n <= 0:
            return
        st = self.rules.structures[line.kind]
        run = line.kind in RUN_STRUCTURES
        if line.at == CENTRE:
            if n == 1:
                self._record(line, self._try(line, line_id, self.cx, self.cy,
                                             self._yaw(line, self.cx, self.cy, st.enterable)))
            else:
                self._cluster(line, line_id, n, near=True)
        elif line.at in ("ring", "perimeter"):
            self._ring(line, line_id, n, st.radius, run)
        elif line.at == "row":
            self._row(line, line_id, n, st.radius, run)
        elif line.at == "lone":
            centre_free = not any(math.hypot(s.x - self.cx, s.y - self.cy) < 1e-6 for s, _, _ in self.kept)
            if centre_free and line.side != "open":
                if n == 1:
                    self._record(line, self._try(line, line_id, self.cx, self.cy,
                                                 self._yaw(line, self.cx, self.cy, st.enterable)))
                else:   # a pair (or more) side by side across the way in; else one alone
                    px, py = -math.sin(self.a), math.cos(self.a)
                    step = 2 * st.radius + CLEAR_WIDTH
                    before, before_clear = len(self.kept), len(self.clear)
                    why = None
                    for k in range(n):
                        off = (k - (n - 1) / 2.0) * step
                        x, y = self.cx + px * off, self.cy + py * off
                        why = why or self._try(line, line_id, x, y, self._yaw(line, x, y, st.enterable))
                    if why is not None:
                        del self.kept[before:]
                        del self.clear[before_clear:]
                        self._record(line, self._try(line, line_id, self.cx, self.cy,
                                                     self._yaw(line, self.cx, self.cy, st.enterable)))
                        for _ in range(n - 1):
                            self._record(line, why)
            else:
                self._cluster(line, line_id, n)
        else:
            self._cluster(line, line_id, n)

    def _record(self, line: Line, why: Optional[str]) -> None:
        if why is not None:
            self.drops.append((line.kind, why))

    def _ring(self, line: Line, line_id: int, n: int, r: float, run: bool) -> None:
        # The ring's radius keeps each Structure inside the Site's ground.
        if run:
            inner = self.R - RUN_HALF_THICK
            if inner <= r:
                for _ in range(n):
                    self._record(line, OUTSIDE)
                return
            ring = math.sqrt(inner * inner - r * r)
            half = r + RUN_HALF_THICK      # what each run needs either side, along the ring
        else:
            ring = self.R - r
            half = r
        if ring <= 0:
            for _ in range(n):
                self._record(line, OUTSIDE)
            return
        # The ring stands a player's way out from whatever holds the middle (a camp's fire):
        # a ground too small for both drops the line here, named, rather than one by one.
        mid = [reach(shape, self.cx, self.cy) for s, shape, _ in self.kept
               if math.hypot(s.x - self.cx, s.y - self.cy) < ring / 2]
        nearest = ring - (RUN_HALF_THICK if run else r)
        if mid and nearest < max(mid) + CLEAR_WIDTH - _EPS:
            for _ in range(n):
                self._record(line, CROWDED)
            return
        # Leave the approach's sector empty (and the open side's, when a line holds it).
        gap_half = math.asin(min(1.0, (CLEAR_WIDTH / 2 + half) / ring))
        span = 2 * math.pi - 2 * gap_half
        need = 2 * math.asin(min(1.0, (half + CLEAR_WIDTH / 2) / ring))
        fit = max(0, int(span / need + 1e-9)) if need > 0 else n
        for _ in range(max(0, n - fit)):
            self._record(line, NO_ROOM)
        n = min(n, fit)
        if n <= 0:
            return
        step = span / n
        start = self.a + gap_half
        for k in range(n):
            ang = start + (k + 0.5) * step + self.rng.uniform(-0.15, 0.15) * max(0.0, step - need)
            x, y = self.cx + ring * math.cos(ang), self.cy + ring * math.sin(ang)
            if run:     # a wall lies along the ring: it faces the centre (or away)
                yaw = ang + math.pi if line.face != "out" else ang
            else:
                yaw = self._yaw(line, x, y, self.rules.structures[line.kind].enterable)
            self._record(line, self._try(line, line_id, x, y, yaw))

    def _row(self, line: Line, line_id: int, n: int, r: float, run: bool) -> None:
        s = self.open_side if line.side == "open" else self.a + math.pi
        sx, sy = math.cos(s), math.sin(s)
        if run and n >= 3:
            # A pen: n runs on an (n+1)-gon, the missing side facing the Site's middle.
            sides = n + 1
            apothem = r / math.tan(math.pi / sides)
            circum = r / math.sin(math.pi / sides)
            d = self.R - circum - RUN_HALF_THICK
            if d < 0:
                for _ in range(n):
                    self._record(line, OUTSIDE)
                return
            px, py = self.cx + sx * d, self.cy + sy * d
            self.reserved.append((px, py, px, py, apothem - RUN_HALF_THICK))
            for k in range(1, sides):
                th = s + math.pi + 2 * math.pi * k / sides
                x, y = px + apothem * math.cos(th), py + apothem * math.sin(th)
                self._record(line, self._try(line, line_id, x, y, th + math.pi, check_reserved=False))
            return
        # A straight row across ``s``, as far out as the Site's ground allows.
        tx, ty = -sy, sx
        step = 2 * r if run else 2 * r + CLEAR_WIDTH
        half_len = (n * step - (0 if run else CLEAR_WIDTH)) / 2.0
        edge = (self.R - RUN_HALF_THICK) if run else (self.R - r)
        lateral = half_len if run else max(0.0, half_len - r)
        d = math.sqrt(edge * edge - lateral * lateral) if edge > lateral else edge * 0.5
        for k in range(n):
            off = (k - (n - 1) / 2.0) * step
            x, y = self.cx + sx * d + tx * off, self.cy + sy * d + ty * off
            yaw = s + math.pi if line.face != "out" else s
            if not run and line.face == "any":
                yaw = self._yaw(line, x, y, self.rules.structures[line.kind].enterable)
            self._record(line, self._try(line, line_id, x, y, yaw))

    def _cluster(self, line: Line, line_id: int, n: int, near: bool = False) -> None:
        st = self.rules.structures[line.kind]
        run = line.kind in RUN_STRUCTURES
        extent = st.radius + (RUN_HALF_THICK if run else 0.0)
        room = max(0.0, self.R - extent)
        if near:
            room = min(room, 2 * st.radius + CLEAR_WIDTH)
        for _ in range(n):
            why = OUTSIDE
            for _ in range(CLUSTER_TRIES):
                rr = room * math.sqrt(self.rng.random())
                th = self.rng.uniform(0, 2 * math.pi)
                x, y = self.cx + rr * math.cos(th), self.cy + rr * math.sin(th)
                why = self._try(line, line_id, x, y, self._yaw(line, x, y, st.enterable))
                if why is None:
                    break
            self._record(line, why)

    # -- the whole recipe -------------------------------------------------
    def arrange(self) -> None:
        """The middle first (centre lines, or a lone recipe's first line), then the way in,
        then everything else round them."""
        lines = list(self.recipe.structures)
        order = _line_order(lines)
        ids = {id(line): k for k, line in enumerate(lines)}
        middle = [ln for ln in order if ln.at == CENTRE]
        if not middle:
            middle = [ln for ln in order if ln.at == "lone" and ln.side != "open"][:1]
        for line in middle:
            self.place_line(line, ids[id(line)])
        self._make_approach()
        for line in order:
            if not any(line is m for m in middle):
                self.place_line(line, ids[id(line)])

    def _make_approach(self) -> None:
        """The way in: from beyond the margin along the approach direction to just short of
        whatever stands at the middle (the first point the capsule clears everything kept)."""
        fx, fy = math.cos(self.a), math.sin(self.a)
        w = CLEAR_WIDTH / 2

        def capsule(t: float) -> ClearShape:
            return (self.cx + fx * t, self.cy + fy * t, self.cx + fx * self.outer, self.cy + fy * self.outer, w)

        t = 0.0
        while t < self.R and any(gap(capsule(t), shape) < 0 for _, shape, _ in self.kept):
            t += 0.5
        self.inner = t
        self.clear.append(ClearArea("approach", *capsule(t)))


def _wrap(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


# ---------------------------------------------------------------------------
# POIs
# ---------------------------------------------------------------------------

def _free_point(x: float, y: float, shapes: Sequence[ClearShape]) -> bool:
    return all(_point_segment(x, y, s) > s[4] + 0.5 for s in shapes)


def _poi_points(arr: _Arranger, recipe: SiteRecipe) -> Tuple[List[Tuple[str, str, float, float, str]],
                                                            List[Tuple[str, str]]]:
    """Each recipe POI's point, on the Site's own free ground, or a drop."""
    solid = [shape for s, shape, _ in arr.kept if not s.enterable or s.run]
    cx, cy, a = arr.cx, arr.cy, arr.a

    def at_middle() -> Optional[Tuple[float, float]]:
        if _free_point(cx, cy, solid):
            return cx, cy
        d = arr.inner + 0.5
        x, y = cx + math.cos(a) * d, cy + math.sin(a) * d
        return (x, y) if _free_point(x, y, solid) else None

    out, drops = [], []
    for poi in recipe.pois:
        pt: Optional[Tuple[float, float]] = None
        reason = NO_FREE_GROUND
        if poi.at == CENTRE:
            pt = at_middle()
        elif poi.at == ENTRANCE:
            pt = (cx + math.cos(a) * arr.R, cy + math.sin(a) * arr.R)
        else:
            mine = [(s, shape) for s, shape, _ in arr.kept if s.kind == poi.at]
            if not mine:
                reason = STRUCTURE_GONE
            else:
                s, shape = mine[0]
                if s.enterable and s.run:            # a ruin's court: inside its ring
                    pt = at_middle()
                elif s.enterable:                    # its interior, floored by the ground
                    pt = (s.x, s.y)
                else:                                # just in front of it, else round it
                    for k in range(8):
                        ang = s.yaw + (math.pi / 4) * ((k + 1) // 2) * (1 if k % 2 else -1)
                        d = s.radius + (RUN_HALF_THICK if s.run else 0.0) + POI_OFFSET
                        x, y = s.x + math.cos(ang) * d, s.y + math.sin(ang) * d
                        if _free_point(x, y, solid) and math.hypot(x - cx, y - cy) <= arr.outer:
                            pt = (x, y)
                            break
        if pt is None:
            drops.append((poi.name, reason))
        else:
            out.append((poi.name, poi.purpose, pt[0], pt[1], poi.at))
    return out, drops


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------

def sites_seed(seed: int) -> int:
    """The Sites' own stream: the zone seed salted as the trees salt theirs."""
    from generators.wilderness.build import _salted_seed
    return _salted_seed(int(seed) & 0x7FFFFFFF, *SITES_SALT)


def site_target(rng: random.Random, band: Tuple[float, float], area: float,
                least: int = 0) -> int:
    """How many Sites to try: a density drawn in ``band`` (Sites per 1e6 u^2) times ``area``,
    rounded so the expected value is kept: the floor, plus one with the fraction's chance;
    then at least ``least`` (an outdoor dungeon at Normal and Dense tries one, site-sockets
    Req 5.2). The floor is applied after both draws, so the stream is the same either way."""
    want = rng.uniform(*band) * area / 1e6
    whole = int(math.floor(want))
    return max(whole + (1 if rng.random() < want - whole else 0), int(least))


#: The Sites controls under which an outdoor dungeon tries at least one Site (Req 5.2).
DUNGEON_FLOOR_CONTROLS = ("normal", "dense")


def _dungeon_floor(control: str, keep_clear: Sequence[ClearShape]) -> int:
    """1 on an outdoor dungeon at Normal or Dense, else 0 (Sparse keeps step 10's draw).
    An outdoor dungeon is ground with Kept_Clear shapes (an earlier Attachment's: the
    dungeon's Tunnel, Apron, rooms and corridors); a wilderness's ground has none. Not the
    points' ``hill`` flag: on some seeds the World offers no point over the hill."""
    if control not in DUNGEON_FLOOR_CONTROLS:
        return 0
    return int(bool(keep_clear))


def place_sites(terrain, ground, seed: int, biome: str = "plains",
                control: str = DEFAULT_DENSITY, inhabitant: str = "",
                rules: Optional[SiteRules] = None,
                spawn_xy: Optional[Tuple[float, float]] = None,
                keep_clear: Sequence[ClearShape] = (),
                points: Sequence[Any] = ()) -> SitePlacement:
    """The Sites of one zone (Requirements 4 and 6; step 13 Requirement 3). Pure.

    ``points``: the World's point Site Sockets (kind ``site``, in rank order). Each Site
    stands on one of them, centred on its point (``_place_on_points``, whose docstring holds
    the order of the stream's draws) and names it in ``Site.socket``; with no points, every
    Site drops (``NO_POINT``).

    ``terrain`` is the World's ``Terrain`` with every earlier Attachment's Terrain edits
    applied, and ``ground`` its ``ground`` Socket (world-sockets task 5): the Spawn is the
    Socket's ``spawn`` and its ``keep_clear`` shapes are Kept_Clear.

    ``seed`` is the Attach stage's seed (``stages.rooms_seed``; the zone seed while no
    ``rooms_seed`` is set): the Sites salt their own stream from it (``SITES_SALT``).
    ``control`` is the Sites control (none, sparse, normal, dense); ``inhabitant`` pins one
    Inhabitant ("" draws from the biome's mix). ``spawn_xy`` overrides the Spawn;
    ``keep_clear`` adds Kept_Clear shapes. Nothing here changes the terrain."""
    rules = rules or load_sites()
    if hasattr(terrain, "synth"):
        raise TypeError("place_sites takes a World's terrain and ground Socket; the "
                        "(landscape, TER) form is retired (site-sockets task 8)")
    if spawn_xy is None:
        sx, sy = ground.ground["spawn"][:2]
        spawn_xy = (float(sx), float(sy))
    shapes = tuple(tuple(s) for s in ground.ground.get("keep_clear", ())) + tuple(keep_clear)
    t = _terrain(terrain, spawn_xy, shapes)
    area = float(t.reached.sum()) * t.ground.res ** 2
    band = rules.density(biome, control)
    rng = random.Random(sites_seed(seed))
    out = SitePlacement(sites=[], drops=[], target=0, walkable_area=area, control=control, band=band)
    if band[1] <= 0 or area <= 0:
        return out
    out.target = site_target(rng, band, area, least=_dungeon_floor(control, shapes))
    _place_on_points(out, t, rules, biome, inhabitant, rng, points, shapes)
    return out


def _arrange_site(out: SitePlacement, t: _Terrain, rules: SiteRules, recipe: SiteRecipe,
                  kind: str, who: str, cx: float, cy: float, a: float, rng: random.Random,
                  socket: Optional[str] = None) -> Optional[Site]:
    """Step 10's Site round ``(cx, cy)`` with its way in ``a``: its Structures arranged, its
    POIs, its drops recorded in ``out``; the Site, kept in ``out``, or None when it dropped."""
    outer = recipe.ground.radius + recipe.ground.margin
    arr = _Arranger(rules, recipe, cx, cy, a, rng)
    arr.arrange()
    pois, poi_drops = _poi_points(arr, recipe)
    index = len(out.sites)
    if not arr.kept or not pois:
        out.drops.append(Drop("site", kind, NO_STRUCTURES if not arr.kept else NO_POI, who))
        return None
    for k, why in arr.drops:
        out.drops.append(Drop("structure", k, why, who, index))
    for name, why in poi_drops:
        out.drops.append(Drop("poi", name, why, who, index))
    z = t.ground.surface_z
    structures = tuple(PlacedStructure(**{**asdict(s), "z": z(s.x, s.y)}) for s, _, _ in arr.kept)
    clear = (ClearArea("ground", cx, cy, cx, cy, outer),) + tuple(arr.clear)
    site = Site(kind=kind, inhabitant=who, x=cx, y=cy, z=z(cx, cy),
                radius=recipe.ground.radius, margin=recipe.ground.margin, approach_yaw=_wrap(a),
                structures=structures,
                pois=tuple(POIPoint(n, p, x, y, z(x, y), at) for n, p, x, y, at in pois),
                clear=clear, socket=socket)
    out.sites.append(site)
    out.counts[kind] = out.counts.get(kind, 0) + 1
    return site


# ---------------------------------------------------------------------------
# On point Sockets (step 13)
# ---------------------------------------------------------------------------

def _point_likes(recipe: SiteRecipe, g: Mapping[str, Any]) -> float:
    """:func:`_likes_score` read off a point Socket's ``ground`` (its height rank, clearing,
    water and zoneline distances, as the World measured them)."""
    score = 0.0
    for like, w in recipe.likes.items():
        if like == "near_water":
            d = g.get("water_d")
            f = 0.0 if d is None else max(0.0, 1.0 - float(d) / NEAR_WATER_REACH)
        elif like == "by_zoneline":
            d = g.get("zoneline_d")
            f = 0.0 if d is None else max(0.0, 1.0 - float(d) / ZONELINE_REACH)
        elif like == "high_ground":
            f = float(g["height_rank"])
        elif like == "low_ground":
            f = 1.0 - float(g["height_rank"])
        else:  # clearing
            f = float(g["clearing"])
        score += w * f
    return score


def _smallest_outer(rules: SiteRules, free: Mapping[str, float]) -> Optional[float]:
    """The smallest ``radius + margin`` of the recipes that fit a point's Free radii."""
    from generators.sites.points import slope_key
    fits = [r.ground.radius + r.ground.margin for r in rules.kinds.values()
            if float(free.get(slope_key(r.ground.slope_deg), 0.0)) >= r.ground.radius + r.ground.margin]
    return min(fits) if fits else None


def usable_points(points: Sequence[Any], rules: SiteRules,
                  keep_clear: Sequence[ClearShape]) -> List[Any]:
    """The point Sockets a Site may take (Req 3.3): those whose smallest-outer disc (the
    smallest recipe that fits them) meets no Kept_Clear shape, in their order."""
    out = []
    for p in points:
        outer = _smallest_outer(rules, p.ground["free"])
        if outer is None:
            continue
        disc = (p.x, p.y, p.x, p.y, outer)
        if any(gap(disc, s) < 0 for s in keep_clear):
            continue
        out.append(p)
    return out


def _group_order(usable: Sequence[Any], rng: random.Random) -> List[Any]:
    """The usable points Group by Group: each next Group drawn with a chance in proportion to
    its usable size (Req 3.4), its points in rank order."""
    groups: Dict[int, List[Any]] = {}
    for p in sorted(usable, key=lambda p: int(p.ground["rank"])):
        groups.setdefault(int(p.ground["group"]), []).append(p)
    order: List[Any] = []
    while groups:
        names = sorted(groups)
        g = rng.choices(names, weights=[len(groups[n]) for n in names])[0]
        order.extend(groups.pop(g))
    return order


def _place_on_points(out: SitePlacement, t: _Terrain, rules: SiteRules, biome: str,
                     inhabitant: str, rng: random.Random, points: Sequence[Any],
                     keep_clear: Sequence[ClearShape]) -> None:
    """Sites on point Sockets (step 13 design "The Sites stage on points"); ``out.target`` is
    drawn. The ``SITES_SALT`` stream draws, after the target, in this order (every Site
    build's bytes depend on it):

    1. the Group order: one draw per Group with a usable point (:func:`_group_order`);
    2. then per point taken, in that order: its Inhabitant; if a kind fits, the kind, then
       the way in (:func:`_approach`), then the arrangement (``_Arranger``'s draws).

    A kind fits a point when its ``radius + margin`` is within the point's Free radius at the
    recipe's slope, its disc meets no Kept_Clear shape and no earlier Site's way in, and keeps
    ``CLEAR_WIDTH`` from every earlier Site's ground and margin; of those with a weight, one
    is drawn by ``weight * (1 + likes)``. A point no kind fits, or with no way in, is passed
    over; every point is taken at most once. A Site still to place when no point is left is
    dropped (``NO_POINT``)."""
    from generators.sites.points import slope_key

    for p in points:
        if p.kind != "site":
            raise ValueError(f"Socket {p.id!r} ({p.kind}) is not a point Site Socket")
    queue = iter(_group_order(usable_points(points, rules, keep_clear), rng))
    grounds: List[ClearShape] = []      # earlier Sites' ground and margin
    ways: List[ClearShape] = []         # earlier Sites' ways in, beyond their margin
    for _ in range(out.target):
        site = None
        for p in queue:
            who = rules.draw_inhabitant(biome, rng, inhabitant)
            weights = rules.kind_weights(biome, who)
            free = p.ground["free"]
            fits: Dict[str, float] = {}
            for kind in sorted(weights):
                if weights[kind] <= 0:
                    continue
                recipe = rules.kinds[kind]
                outer = recipe.ground.radius + recipe.ground.margin
                if float(free.get(slope_key(recipe.ground.slope_deg), 0.0)) < outer:
                    continue
                disc = (p.x, p.y, p.x, p.y, outer)
                if any(gap(disc, s) < 0 for s in keep_clear) or any(gap(disc, w) < 0 for w in ways):
                    continue
                if any(gap(disc, s) < CLEAR_WIDTH for s in grounds):
                    continue
                fits[kind] = weights[kind] * (1.0 + _point_likes(recipe, p.ground))
            if not fits:
                continue
            names = sorted(fits)
            kind = rng.choices(names, weights=[fits[n] for n in names])[0]
            recipe = rules.recipe_for(kind, who)
            outer = recipe.ground.radius + recipe.ground.margin
            cx, cy = float(p.x), float(p.y)
            # The way in keeps off earlier Sites' grounds and the Kept_Clear (an outdoor
            # dungeon's rooms reach under the hill's flat ground, site-sockets P7).
            a = _approach(t, cx, cy, outer, rng, avoid=tuple(grounds) + tuple(keep_clear))
            if a is None:
                continue
            site = _arrange_site(out, t, rules, recipe, kind, who, cx, cy, a, rng, socket=p.id)
            # The point is used either way; a Site whose arrangement failed is dropped, named.
            if site is not None:
                grounds.append((cx, cy, cx, cy, outer))
                ways.append(approach_way(cx, cy, outer, a))
            break
        else:
            out.drops.append(Drop("site", "", NO_POINT))


__all__ = ["APRON_DEPTH", "CLEAR_WIDTH", "ClearArea", "Drop", "NO_POINT", "POIPoint",
           "PlacedStructure", "RUN_STRUCTURES", "SITES_SALT", "Site", "SitePlacement",
           "approach_way", "gap", "place_sites", "reach", "site_target", "sites_seed",
           "usable_points"]
