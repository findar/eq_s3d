"""
generators/sites/models.py
--------------------------
Procedural low-poly Structure models for Sites (wilderness POIs spec task 3, Req 3).

:func:`structure_model` builds one ``EQGM`` model for a Structure kind, a model variant and an
Inhabitant's material set, in the Classic recipe task 1 measured on the stock client (design
finding 1: tents 20-110 triangles, huts 48-92, houses 80-219, towers 42-254, fire rings 44-80,
every stock model under 400).

The kinds are ``rules/sites/sites.toml``'s Structures (:data:`VARIANTS` lists each one's model
variants, the first the default):

========== ============================================================================
hut         timber: a gabled plank house under thatch, a door in the front gable;
            wattle: a round wall under a conical roof, a gap in the wall for the door
barn        timber: a gambrel-roofed barn with doors, a loft door and a cupola (closed)
tent        canvas: a ridge tent with a sagging ridge, poles and a door flap;
            hide: a conical hide tent, its poles crossing out of the smoke hole
lean_to     timber: a sloped thatch roof on two posts and a front beam;
            hide: a hide roof with hide side panels
tower       stone: a round corbelled tower with merlons; timber: a tapered square shaft,
            braced, under a lookout and a pyramid roof; lashed: a rough log shaft, a hide
            lookout ringed with stakes, a hide cone roof
fire_ring   stone: a ring of stones round three crossed logs
fence       rail: three posts and two rails; stake: a row of pointed stakes on a rail
standing_
stone       stone: an irregular tapering monolith
altar_stone stone: a capstone on two uprights
monument    obelisk: a tapering obelisk on a stepped plinth; burial_mound: a long barrow
ruin_wall   stone: a broken wall run, stepped down, with a fallen block
========== ============================================================================

Conventions
    Z is up; the origin is ground level at the footprint's middle. Every model's front faces
    +x, so a placed Structure's ``yaw`` (task 6: the way its front faces, radians
    counter-clockwise from +x) turns it straight: a hut's door, a lean-to's open side, a tent's
    flap, a ruin wall's court side. Fence and ruin wall are runs laid across the yaw (along
    local y), :data:`RUN_HALF_LENGTH` either side of the origin (their ``radius`` in
    ``sites.toml``) and within 1 u of the run's line. Every part that meets the ground goes down
    to ``-sink`` (the buried skirt), so a Structure on ground up to 10 degrees shows no gap.

Solid and passable
    Walls, posts, stone and roofs over the walls are closed solids (every edge shared by a face
    each way). Thatch eaves, the overhang of a conical roof and cloth flaps are passable
    (``FLAG_PASSABLE``) and double-sided, and so is trim high above head height that sits in
    another solid (a cupola, merlons, a tent's ridge pole and pole tips, a tower's braces): no collidable solid
    is buried in another, so the first triangle above any point inside one faces up.
    Enterable models (hut, lean_to, ruin_wall) have no
    floor: the ground is the floor. A hut's or lean-to's opening is well over
    :data:`CLEAR_WIDTH` wide and :data:`HEAD_HEIGHT` high (the gate's numbers,
    ``analyzer.footprints``); a ruin's way in is the gap its placement leaves between runs.
    Solids are wound outward: the gate reads "inside a solid" from the first triangle above.

Materials and UVs
    Each part names a slot (wall, roof, tent, wood, stone) and the material set maps it to a
    material (``generators.textures.sites``). UVs are world position x ``uv_scale()``,
    projected per face: ``u`` along a wall (across a roof or tent), ``v`` down it, so texture
    row 0 is the top; flat faces take plan x, y.

Pure in (kind, variant, material set, seed): the seed sets a gentle, smooth warp (no box reads
true) and small shape differences. No mesh file is read (umbrella Req 32.7); coordinates are
rounded to float32 so the model round-trips through ``core.ter`` exactly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from analyzer.footprints import CLEAR_WIDTH, HEAD_HEIGHT
from core.ter import FLAG_PASSABLE, MAGIC_MODEL, SHADER_OPAQUE, Material, Polygon, TerFile, Vertex
from generators.textures.sites import set_material, site_texture_name, uv_scale

#: The doors as built (u): a hut's door is a stock hut's, well over the gate's clear width and
#: head height (8 u each, ``analyzer.footprints``), so the warp (under 0.5 u) never matters.
DOOR_WIDTH = 15.0
DOOR_HEIGHT = 14.0
assert DOOR_WIDTH >= CLEAR_WIDTH + 1 and DOOR_HEIGHT >= HEAD_HEIGHT + 1

#: Each Structure kind's model variants; the first is the default (variant "").
VARIANTS: Dict[str, Tuple[str, ...]] = {
    "hut": ("timber", "wattle"),
    "barn": ("timber",),
    "tent": ("canvas", "hide"),
    "lean_to": ("timber", "hide"),
    "tower": ("stone", "timber", "lashed"),
    "fire_ring": ("stone",),
    "fence": ("rail", "stake"),
    "standing_stone": ("stone",),
    "altar_stone": ("stone",),
    "monument": ("obelisk", "burial_mound"),
    "ruin_wall": ("stone",),
}
#: Half the length of a run (fence, ruin wall): its ``radius`` in ``rules/sites/sites.toml``,
#: as task 6's placement lays runs (a capsule this long either side, 1 u thick each side).
RUN_HALF_LENGTH = 10.0
#: Kinds a player walks into, floored by the ground (archive decision 2).
ENTERABLE = frozenset({"hut", "lean_to", "ruin_wall"})

#: The warp's largest offset (u) and its wavelength band (u).
WARP = 0.35
WARP_WAVELENGTH = (18.0, 30.0)

Vec = np.ndarray


class SiteModelError(ValueError):
    """An unknown Structure kind or variant; the message names it."""


@dataclass(frozen=True)
class Opening:
    """A way in, in model space: its middle at ground level, its clear size, and the yaw it
    faces (radians, 0 = +x)."""
    x: float
    y: float
    width: float
    height: float
    facing: float = 0.0


@dataclass(frozen=True)
class StructureModel:
    """One built model and what placement, the gate and the sidecar need to know of it."""
    kind: str
    variant: str
    material_set: str
    ter: TerFile
    radius: float        # the largest plan distance of any vertex from the origin (u)
    height: float        # the top (u)
    sink: float          # how far the skirt goes below the origin (u)
    enterable: bool
    openings: Tuple[Opening, ...]

    @property
    def name(self) -> str:
        return self.ter.name


def resolve_variant(kind: str, variant: str = "") -> str:
    """The variant a (kind, variant) builds: "" is the kind's default."""
    if kind not in VARIANTS:
        raise SiteModelError(f"unknown Structure kind {kind!r}; known: {', '.join(VARIANTS)}")
    if not variant:
        return VARIANTS[kind][0]
    if variant not in VARIANTS[kind]:
        raise SiteModelError(f"unknown {kind} variant {variant!r}; known: {', '.join(VARIANTS[kind])}")
    return variant


def model_name(kind: str, variant: str, material_set: str) -> str:
    """The archive filename: ``site_<kind>_<variant>_<material set>.mod``."""
    return f"site_{kind}_{resolve_variant(kind, variant)}_{material_set}.mod"


# ---------------------------------------------------------------------------
# Mesh building
# ---------------------------------------------------------------------------

def _f32(v: float) -> float:
    return float(np.float32(v))


def _v(*p: float) -> Vec:
    return np.array(p, dtype=float)


def _ring(cx: float, cy: float, z: float, rx: float, n: int, phase: float = 0.0,
          ry: Optional[float] = None, radii: Optional[Sequence[float]] = None) -> Vec:
    """``n`` points round (cx, cy) at height z, counter-clockwise seen from above."""
    ry = rx if ry is None else ry
    a = phase + 2 * math.pi * np.arange(n) / n
    k = np.ones(n) if radii is None else np.asarray(radii, float)
    return np.stack([cx + rx * k * np.cos(a), cy + ry * k * np.sin(a), np.full(n, z)], axis=1)


def _rect(cx: float, cy: float, z: float, hx: float, hy: float, yaw: float = 0.0) -> Vec:
    """A rectangle's corners (half-sizes hx, hy), turned by yaw."""
    c, s = math.cos(yaw), math.sin(yaw)
    pts = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
    return np.array([[cx + c * x - s * y, cy + s * x + c * y, z] for x, y in pts])


class _Mesh:
    """Triangles (in world units, before the warp) with a slot and flags each."""

    def __init__(self) -> None:
        self.faces: List[Tuple[Vec, Vec, Vec, str, int]] = []

    def _tri(self, a: Vec, b: Vec, c: Vec, ref: Vec, slot: str, flags: int = 0) -> None:
        """A triangle wound counter-clockwise seen from the side away from ``ref``."""
        if np.dot(np.cross(b - a, c - a), (a + b + c) / 3 - ref) < 0:
            b, c = c, b
        self.faces.append((a, b, c, slot, flags))

    def _band(self, r0: Vec, r1: Vec, slots: Sequence[str], flags: int = 0,
              ref: Optional[Vec] = None) -> None:
        """Faces between two rings, wound away from ``ref`` (default: midway between the rings;
        a flat band, an eave's underside, passes a point inside the solid)."""
        if ref is None:
            ref = (r0.mean(axis=0) + r1.mean(axis=0)) / 2
        n = max(len(r0), len(r1))
        for i in range(n):
            j = (i + 1) % n
            slot = slots[i % len(slots)]
            if len(r1) == 1:
                self._tri(r0[i], r0[j], r1[0], ref, slot, flags)
            elif len(r0) == 1:
                self._tri(r0[0], r1[i], r1[j], ref, slot, flags)
            else:
                self._tri(r0[i], r0[j], r1[j], ref, slot, flags)
                self._tri(r0[i], r1[j], r1[i], ref, slot, flags)

    def _cap(self, ring: Vec, away_from: Vec, slot: str, flags: int = 0) -> None:
        for i in range(1, len(ring) - 1):
            self._tri(ring[0], ring[i], ring[i + 1], away_from, slot, flags)

    def loft(self, rings: Sequence[Vec], slot: str, band_slots: Optional[Sequence[str]] = None,
             cap_slots: Optional[Tuple[str, str]] = None, flags: int = 0) -> None:
        """A closed solid through ``rings`` (each N points, or one point for an apex), capped at
        both ends. ``band_slots`` gives each band its slot."""
        rings = [np.atleast_2d(np.asarray(r, float)) for r in rings]
        for k in range(len(rings) - 1):
            # A flat band (an eave's underside) faces away from the solid beyond it: the ring
            # after it, or before it at the end.
            flat = np.ptp(np.concatenate([rings[k], rings[k + 1]])[:, 2]) < 1e-9
            beyond = rings[k + 2] if k + 2 < len(rings) else rings[k - 1]
            self._band(rings[k], rings[k + 1], [band_slots[k] if band_slots else slot], flags,
                       ref=beyond.mean(axis=0) if flat else None)
        c0, c1 = cap_slots or (slot, slot)
        if len(rings[0]) > 2:
            self._cap(rings[0], rings[1].mean(axis=0), c0, flags)
        if len(rings[-1]) > 2:
            self._cap(rings[-1], rings[-2].mean(axis=0), c1, flags)

    def prism(self, outline: Sequence[Tuple[float, float]], origin: Tuple[float, float], theta: float,
              thickness: float, slot: str, edge_slots: Optional[Sequence[str]] = None,
              cap_slot: Optional[str] = None) -> None:
        """A convex outline in a vertical plane, (s, z) with s along ``theta``, extruded
        ``thickness`` across the plane: a wall piece. Edge k joins outline points k and k+1."""
        s_ax = _v(math.cos(theta), math.sin(theta), 0.0)
        n_ax = _v(-math.sin(theta), math.cos(theta), 0.0)
        o = _v(origin[0], origin[1], 0.0)
        flat = np.array([o + s * s_ax + _v(0, 0, z) for s, z in outline])
        a, b = flat - n_ax * thickness / 2, flat + n_ax * thickness / 2
        self._band(a, b, list(edge_slots) if edge_slots else [slot])
        self._cap(a, b.mean(axis=0), cap_slot or slot)
        self._cap(b, a.mean(axis=0), cap_slot or slot)

    def beam(self, p0: Sequence[float], p1: Sequence[float], r: float, slot: str, sides: int = 4,
             r1: Optional[float] = None, roll: float = 0.0, tip: float = 0.0, flags: int = 0) -> None:
        """A closed prism from p0 to p1, corner radius r (tapering to r1), optionally ending in
        a point ``tip`` beyond p1."""
        p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
        d = (p1 - p0) / np.linalg.norm(p1 - p0)
        up = _v(0, 0, 1) if abs(d[2]) < 0.95 else _v(1, 0, 0)
        e1 = np.cross(d, up)
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(e1, d)
        a = roll + math.pi / sides + 2 * math.pi * np.arange(sides) / sides
        ring = np.cos(a)[:, None] * e1 + np.sin(a)[:, None] * e2
        rings = [p0 + r * ring, p1 + (r if r1 is None else r1) * ring]
        if tip:
            rings.append(p1 + tip * d)
        self.loft(rings, slot, flags=flags)

    def sheet(self, points: Sequence[Sequence[float]], slot: str) -> None:
        """A passable convex polygon, double-sided (cloth, an eave)."""
        pts = [np.asarray(p, float) for p in points]
        n = np.cross(pts[1] - pts[0], pts[2] - pts[0])
        c = sum(pts) / len(pts)
        for sign in (1.0, -1.0):
            self._cap(np.array(pts), c - sign * n, slot, FLAG_PASSABLE)


def _warp(rng: np.random.Generator, amp: float) -> Callable[[Vec], Vec]:
    """A smooth offset field: three sine waves 18-30 u long, at most ``amp`` (half in z)."""
    ks, phases = [], rng.uniform(0, 2 * math.pi, 3)
    for _ in range(3):
        d = rng.normal(size=3)
        ks.append(d / np.linalg.norm(d) * 2 * math.pi / rng.uniform(*WARP_WAVELENGTH))

    def f(p: Vec) -> Vec:
        return p + amp * np.array([math.sin(p @ ks[0] + phases[0]), math.sin(p @ ks[1] + phases[1]),
                                   0.5 * math.sin(p @ ks[2] + phases[2])])
    return f


def _finish(m: _Mesh, name: str, material_set: str, warp: Callable[[Vec], Vec]) -> TerFile:
    """Warp, wind, UV and pack the mesh: flat-shaded, three vertices a face."""
    s = uv_scale()
    mats: Dict[str, int] = {}
    vertices: List[Vertex] = []
    polygons: List[Polygon] = []
    cache: Dict[Tuple[float, float, float], Vec] = {}

    def moved(p: Vec) -> Vec:
        key = tuple(round(float(x), 6) for x in p)
        if key not in cache:
            cache[key] = np.array([_f32(x) for x in warp(p)])
        return cache[key]

    for a, b, c, slot, flags in m.faces:
        pts = [moved(a), moved(b), moved(c)]
        n = np.cross(pts[1] - pts[0], pts[2] - pts[0])
        n /= np.linalg.norm(n)
        if abs(n[2]) > 0.85:
            uv = [(p[0] * s, -p[1] * s) for p in pts]
        else:
            t = _v(-n[1], n[0], 0.0)
            t /= np.linalg.norm(t)
            up = _v(0, 0, 1) - n * n[2]
            up /= np.linalg.norm(up)
            uv = [(float(p @ t) * s, -float(p @ up) * s) for p in pts]
        material = set_material(material_set, slot)
        mi = mats.setdefault(material, len(mats))
        idx = []
        for p, (u, v) in zip(pts, uv):
            vertices.append(Vertex(x=float(p[0]), y=float(p[1]), z=float(p[2]),
                                   nx=_f32(n[0]), ny=_f32(n[1]), nz=_f32(n[2]), u=_f32(u), v=_f32(v)))
            idx.append(len(vertices) - 1)
        polygons.append(Polygon(*idx, material=mi, flags=flags))
    materials = []
    for material, i in mats.items():
        mat = Material(index=i, name=f"site_{material}", shader=SHADER_OPAQUE)
        mat.add_diffuse(site_texture_name(material))
        materials.append(mat)
    return TerFile(name=name, magic=MAGIC_MODEL, version=2, materials=materials,
                   vertices=vertices, polygons=polygons)


# ---------------------------------------------------------------------------
# The models. Each builder fills the mesh and returns (openings, sink).
# ---------------------------------------------------------------------------

Built = Tuple[Tuple[Opening, ...], float]


def _gable_roof(m: _Mesh, half_l: float, half_w: float, eave: float, ridge: float,
                thick: float, overhang: float) -> None:
    """Two solid thatch slopes over the walls, each with a passable eave beyond them."""
    rise = ridge - eave
    for side in (1.0, -1.0):
        n = _v(0.0, side * rise, half_w)
        n /= np.linalg.norm(n)

        def under(y: float) -> float:
            return ridge - rise * abs(y) / half_w

        def slab(y0: float, y1: float, flags: int) -> None:
            lo = np.array([[-half_l, y0, under(y0)], [half_l, y0, under(y0)],
                           [half_l, y1, under(y1)], [-half_l, y1, under(y1)]])
            m.loft([lo, lo + n * thick], "roof", flags=flags)
        slab(0.0, side * half_w, 0)
        slab(side * half_w, side * (half_w + overhang), FLAG_PASSABLE)


def _hut_timber(m: _Mesh, rng: np.random.Generator) -> Built:
    sink, t = 4.0, 1.0
    half_l, half_w = 14.0 + rng.uniform(-1, 1), 11.0 + rng.uniform(-0.5, 0.5)
    eave, ridge = DOOR_HEIGHT + 1.0, 27.0 + rng.uniform(-1.5, 1.5)
    dw, dh = DOOR_WIDTH / 2, DOOR_HEIGHT
    w = half_w + t / 2
    gable = [(-w, eave), (0.0, ridge)]
    # Front gable: two jambs and the gable over the door.
    for sgn in (1.0, -1.0):
        m.prism([(sgn * -w, -sink), (sgn * -dw, -sink), (sgn * -dw, dh), (sgn * -w, dh)],
                (half_l, 0.0), math.pi / 2, t, "wall")
    m.prism([(-w, dh), (w, dh), (w, eave), *gable[::-1]], (half_l, 0.0), math.pi / 2, t, "wall")
    m.prism([(-w, -sink), (w, -sink), (w, eave), *gable[::-1]], (-half_l, 0.0), math.pi / 2, t, "wall")
    for sgn in (1.0, -1.0):
        m.prism([(-half_l, -sink), (half_l, -sink), (half_l, eave), (-half_l, eave)],
                (0.0, sgn * half_w), 0.0, t, "wall")
    _gable_roof(m, half_l + t, half_w, eave, ridge, 1.4, 2.8)
    # The ridge beam, standing out past both gables.
    m.beam((-half_l - 2.5, 0, ridge + 1.5), (half_l + 2.5, 0, ridge + 1.5), 0.6, "wood")
    return (Opening(half_l, 0.0, DOOR_WIDTH, DOOR_HEIGHT),), sink


def _hut_wattle(m: _Mesh, rng: np.random.Generator) -> Built:
    sink, t, r = 4.0, 1.1, 13.0 + rng.uniform(-0.5, 0.5)
    wall = DOOR_HEIGHT + 1.0
    gap = math.asin((DOOR_WIDTH / 2 + t) / r)
    n_seg = 7
    angles = np.linspace(gap, 2 * math.pi - gap, n_seg + 1)
    for a0, a1 in zip(angles[:-1], angles[1:]):
        p0, p1 = r * _v(math.cos(a0), math.sin(a0), 0), r * _v(math.cos(a1), math.sin(a1), 0)
        mid, d = (p0 + p1) / 2, p1 - p0
        half = np.linalg.norm(d) / 2 + t / 2
        top = wall + rng.uniform(-0.3, 0.3)
        m.prism([(-half, -sink), (half, -sink), (half, top), (-half, top)], (mid[0], mid[1]),
                math.atan2(d[1], d[0]), t, "wall")
    n = 10
    eave_r, apex = r + 0.8, wall + 13.0 + rng.uniform(-1, 1)
    base = _ring(0, 0, wall + 0.3, eave_r, n, phase=0.1)
    m.loft([base, _v(rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), apex)], "roof")
    # The overhang: a passable skirt of thatch round the cone's foot.
    slope = (apex - wall) / eave_r
    out = _ring(0, 0, wall + 0.3 - slope * 3.2, eave_r + 3.2, n, phase=0.1)
    for i in range(n):
        j = (i + 1) % n
        m.sheet([base[i], base[j], out[j], out[i]], "roof")
    return (Opening(r * math.cos(gap), 0.0, DOOR_WIDTH, wall),), sink


def _barn(m: _Mesh, rng: np.random.Generator) -> Built:
    sink = 6.0
    hl, hw, wall = 28.0 + rng.uniform(-1, 1), 20.0, 22.0
    knee, ridge = (14.0, 34.0), 42.0 + rng.uniform(-1, 1)
    outline = [(-hw, -sink), (hw, -sink), (hw, wall), knee, (0.0, ridge), (-knee[0], knee[1]), (-hw, wall)]
    m.prism(outline, (0.0, 0.0), math.pi / 2, 2 * hl, "wall",
            edge_slots=["wall", "wall", "roof", "roof", "roof", "roof", "wall"], cap_slot="wall")
    # Passable eaves along both long walls.
    rise = (knee[1] - wall) / (hw - knee[0])
    for sgn in (1.0, -1.0):
        lo = np.array([[-hl - 1, sgn * hw, wall], [hl + 1, sgn * hw, wall],
                       [hl + 1, sgn * (hw + 2.5), wall - 2.5 * rise], [-hl - 1, sgn * (hw + 2.5), wall - 2.5 * rise]])
        m.loft([lo, lo + _v(0, 0, 1.0)], "roof", flags=FLAG_PASSABLE)
    # Big doors and a loft door on the front gable, standing 0.3 u proud (no wider: the gate reads
    # the sliver between a proud panel and the wall as enclosed ground), a cupola on the ridge.
    m.loft([_rect(hl + 0.15, 0, -3.0, 0.15, 8.5), _rect(hl + 0.15, 0, 18.0, 0.15, 8.5)], "wood")
    m.loft([_rect(hl + 0.15, 0, 25.0, 0.15, 4.0), _rect(hl + 0.15, 0, 31.0, 0.15, 4.0)], "wood")
    cx = rng.uniform(-6, 6)
    m.loft([_rect(cx, 0, ridge - 2, 3.5, 3.5), _rect(cx, 0, ridge + 4, 3.5, 3.5),
            _v(cx, 0, ridge + 8.5)], "wood", band_slots=["wood", "roof"], flags=FLAG_PASSABLE)
    return (), sink


def _tent_canvas(m: _Mesh, rng: np.random.Generator) -> Built:
    sink, hl, hw, side, ridge = 3.0, 10.0, 8.0, 3.0, 17.0 + rng.uniform(-1, 1)
    sag = rng.uniform(0.6, 1.4)
    rings = []
    for x, dz, bulge in ((-hl, 0.0, 0.0), (0.0, -sag, 0.4), (hl, 0.0, 0.0)):
        w = hw + bulge
        rings.append(np.array([[x, -w, -sink], [x, w, -sink], [x, w, side], [x, 0.0, ridge + dz],
                               [x, -w, side]]))
    m.loft(rings, "tent")
    m.beam((-hl - 1.8, 0, ridge + 0.3), (hl + 1.8, 0, ridge + 0.3), 0.45, "wood", flags=FLAG_PASSABLE)
    for x in (-hl - 0.4, hl + 0.4):
        m.beam((x, 0, -sink), (x, 0, ridge + 1.8), 0.45, "wood")
    # The door flap, tied back on the front gable.
    m.sheet([(hl + 0.25, -0.6, 0.0), (hl + 0.25, 4.2, 0.0), (hl + 0.25, 0.6, ridge - 3.0)], "tent")
    return (), sink


def _tent_hide(m: _Mesh, rng: np.random.Generator) -> Built:
    sink, n, r, top = 3.0, 8, 9.0 + rng.uniform(-0.5, 0.5), 15.5 + rng.uniform(-1, 1)
    sag = 1.0 - 0.07 * (np.arange(n) % 2)       # the hide sags between the poles
    rings = [_ring(0, 0, -sink, r + 0.4, n), _ring(0, 0, 0.0, r, n),
             _ring(0, 0, 7.0, r * 0.68, n, radii=sag), _ring(0.3, 0, top, 1.3, n)]
    m.loft(rings, "tent")
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2 + rng.uniform(-0.15, 0.15)
        c, s = math.cos(a), math.sin(a)
        m.beam((1.6 * c, 1.6 * s, top - 2.0), (-2.6 * c, -2.6 * s, top + 5.5), 0.35, "wood", sides=3,
               flags=FLAG_PASSABLE)
    m.sheet([(r + 0.15, -2.5, 0.2), (r + 0.15, 2.5, 0.2), (r * 0.7 + 0.15, 0.8, 7.5),
             (r * 0.7 + 0.15, -0.8, 7.5)], "tent")
    return (), sink


def _lean_to(m: _Mesh, rng: np.random.Generator, hide: bool) -> Built:
    sink, front, back, hw = 3.0, 7.0, -7.0, 9.0 + rng.uniform(-0.4, 0.4)
    top = DOOR_HEIGHT + 1.3 + rng.uniform(0, 1)       # the roof's underside at the front edge
    run = (top + sink) / (front + 0.5 - back)
    x_end = back                                       # where the roof's underside is at -sink

    def under(x: float) -> float:
        return top - (front + 0.5 - x) * run
    lo = np.array([[front + 0.5, -hw - 0.5, top], [front + 0.5, hw + 0.5, top],
                   [x_end, hw + 0.5, under(x_end)], [x_end, -hw - 0.5, under(x_end)]])
    n = _v(run, 0.0, 1.0)
    n /= np.linalg.norm(n)
    m.loft([lo, lo + n * 1.0], "wall" if hide else "roof")
    post = hw - 0.8
    for sgn in (1.0, -1.0):
        m.beam((front - 0.3, sgn * post, -sink), (front - 0.3, sgn * post, top + 0.2), 0.6, "wood", roll=math.pi / 4)
    if hide:
        for sgn in (1.0, -1.0):
            x1 = front - 1.2
            m.prism([(back + 0.2, -sink), (x1, -sink), (x1, under(x1) - 0.3)], (0.0, sgn * (hw - 0.1)),
                    0.0, 0.5, "wall")
    else:
        m.beam((front - 0.3, -hw - 0.8, top - 0.6), (front - 0.3, hw + 0.8, top - 0.6), 0.45, "wood")
    clear = 2 * (post - 0.6)
    return (Opening(front - 0.3, 0.0, clear, top - (0.0 if hide else 1.05)),), sink


def _tower_stone(m: _Mesh, rng: np.random.Generator) -> Built:
    sink, n, shaft = 3.5, 10, 50.0 + rng.uniform(-2, 2)
    rings = [_ring(0, 0, -sink, 10.3, n), _ring(0, 0, 0.0, 10.0, n),
             _ring(0, 0, shaft, 8.3, n), _ring(0, 0, shaft + 1.2, 9.6, n), _ring(0, 0, shaft + 8.0, 9.6, n)]
    m.loft(rings, "stone")
    phase = rng.uniform(0, 2 * math.pi)
    for k in range(5):
        a = phase + 2 * math.pi * k / 5
        c = _v(8.6 * math.cos(a), 8.6 * math.sin(a), 0)
        m.beam(c + _v(0, 0, shaft + 7.6), c + _v(0, 0, shaft + 11.5), 1.6, "stone", roll=a + math.pi / 4,
               flags=FLAG_PASSABLE)
    return (), sink


def _tower_timber(m: _Mesh, rng: np.random.Generator) -> Built:
    sink, shaft = 3.5, 44.0 + rng.uniform(-2, 2)
    look = shaft + 9.0
    rings = [_rect(0, 0, -sink, 8.4, 8.4), _rect(0, 0, 0.0, 8.2, 8.2), _rect(0, 0, shaft, 6.2, 6.2),
             _rect(0, 0, shaft + 1.0, 10.0, 10.0), _rect(0, 0, look, 10.0, 10.0),
             _rect(0, 0, look, 12.0, 12.0), _v(0, 0, look + 13.0 + rng.uniform(-1, 1))]
    m.loft(rings, "wall", band_slots=["wood", "wood", "wood", "wall", "roof", "roof"])
    # A diagonal brace on each face, turning round the tower.
    for k in range(4):
        yaw = k * math.pi / 2
        c, s = math.cos(yaw), math.sin(yaw)

        def at(u: float, z: float) -> Vec:
            half = 8.2 - 2.0 * z / shaft + 0.45
            return _v(c * half - s * u * half * 0.85, s * half + c * u * half * 0.85, z)
        # Passable: it lies on the face, inside the shaft's Footprint, and a solid brace would
        # leave pockets between it and the face that the gate reads as enclosed ground.
        m.beam(at(-1, 2.0), at(1, shaft - 4.0), 0.5, "wood", flags=FLAG_PASSABLE)
    return (), sink


def _tower_lashed(m: _Mesh, rng: np.random.Generator) -> Built:
    sink, n, shaft = 3.5, 8, 38.0 + rng.uniform(-2, 2)
    look = shaft + 7.0
    radii = 1.0 + rng.uniform(-0.06, 0.06, n)
    rings = [_ring(0, 0, -sink, 9.2, n, radii=radii), _ring(0, 0, 0.0, 9.0, n, radii=radii),
             _ring(0, 0, shaft, 6.4, n), _ring(0, 0, shaft + 1.0, 11.0, n), _ring(0, 0, look, 11.0, n),
             _ring(0, 0, look, 12.8, n), _v(0, 0, look + 12.0 + rng.uniform(-1, 1))]
    m.loft(rings, "wood", band_slots=["wood", "wood", "wood", "wall", "roof", "roof"])
    for k in range(6):
        a = 2 * math.pi * k / 6 + rng.uniform(-0.2, 0.2)
        c, s = math.cos(a), math.sin(a)
        m.beam((10.6 * c, 10.6 * s, shaft + 2.0), (12.6 * c, 12.6 * s, look + 4.5), 0.45, "wood",
               sides=3, tip=1.2)
    return (), sink


def _fire_ring(m: _Mesh, rng: np.random.Generator) -> Built:
    sink, n, r = 1.0, 7, 3.6
    phase = rng.uniform(0, 2 * math.pi)
    for k in range(n):
        a = phase + 2 * math.pi * k / n + rng.uniform(-0.12, 0.12)
        cx, cy = r * math.cos(a), r * math.sin(a)
        h = rng.uniform(1.2, 1.9)
        m.loft([_ring(cx, cy, -sink, 0.95, 3, phase=a), _ring(cx, cy, h, 0.55, 3, phase=a + 0.5)], "stone")
    spin = rng.uniform(0, 2 * math.pi)
    for k in range(3):
        a = spin + 2 * math.pi * k / 3
        c, s = math.cos(a), math.sin(a)
        m.beam((1.9 * c, 1.9 * s, 0.1), (-0.2 * c, -0.2 * s, 2.2), 0.3, "wood", sides=3)
    return (), sink


def _fence_rail(m: _Mesh, rng: np.random.Generator) -> Built:
    sink, half = 2.5, RUN_HALF_LENGTH
    for y in (-half, 0.0, half):
        # Along the run only, and the end posts inward: the run stays in task 6's capsule.
        lean = rng.uniform(-0.4, 0.4) if y == 0 else -math.copysign(rng.uniform(0, 0.4), y)
        m.beam((0, y, -sink), (0, y + lean, 7.5 + rng.uniform(-0.3, 0.3)), 0.6, "wood", roll=math.pi / 4)
    for z in (3.0, 6.0):
        dz = rng.uniform(-0.25, 0.25)
        m.beam((0, -half - 0.3, z - dz), (0, half + 0.3, z + dz), 0.55, "wood")
    return (), sink


def _fence_stake(m: _Mesh, rng: np.random.Generator) -> Built:
    sink, half, n = 2.5, RUN_HALF_LENGTH, 8
    for y in np.linspace(-half + 0.3, half - 0.3, n):
        h = rng.uniform(8.5, 10.5)
        lean = rng.uniform(-0.3, 0.3) * (1 - abs(y) / half) - 0.1 * math.copysign(1, y) * (abs(y) > half - 1)
        m.beam((0, y, -sink), (0, y + lean, h), 0.75, "wood", tip=1.5, roll=rng.uniform(-0.2, 0.2))
    m.beam((0.0, -half, 5.0), (0.0, half, 5.4), 0.6, "wood")      # through the stakes
    return (), sink


def _standing_stone(m: _Mesh, rng: np.random.Generator) -> Built:
    sink, n, h = 2.0, 6, 13.0 + rng.uniform(-1, 1)
    radii = 1.0 + rng.uniform(-0.15, 0.15, n)
    lean = rng.uniform(-0.5, 0.5, 2)
    rings = [_ring(0, 0, -sink, 2.3, n, ry=1.7, radii=radii), _ring(0, 0, 0.0, 2.3, n, ry=1.7, radii=radii),
             _ring(lean[0] * 0.5, lean[1] * 0.5, h * 0.5, 2.0, n, ry=1.5, radii=radii[::-1], phase=0.2),
             _ring(lean[0], lean[1], h, 1.3, n, ry=0.9, phase=0.4)]
    m.loft(rings, "stone")
    return (), sink


def _altar_stone(m: _Mesh, rng: np.random.Generator) -> Built:
    sink, h = 1.5, 3.2
    for y in (-2.2, 2.2):
        m.loft([_rect(0, y, -sink, 1.2, 0.8, rng.uniform(-0.1, 0.1)),
                _rect(0, y, h, 1.0, 0.7, rng.uniform(-0.1, 0.1))], "stone")
    tilt = rng.uniform(-0.25, 0.25)
    yaw = rng.uniform(-0.08, 0.08)
    lo = _rect(0, 0, h - 0.1, 1.9, 3.4, yaw)
    lo[:, 2] += lo[:, 1] * tilt * 0.1
    m.loft([lo, lo + _v(0, 0, 1.1)], "stone")
    return (), sink


def _monument_obelisk(m: _Mesh, rng: np.random.Generator) -> Built:
    sink, h = 2.0, 22.0 + rng.uniform(-1.5, 1.5)
    yaw = rng.uniform(0, math.pi / 2)
    m.loft([_rect(0, 0, -sink, 4.0, 4.0, yaw), _rect(0, 0, 1.2, 4.0, 4.0, yaw)], "stone")
    m.loft([_rect(0, 0, 0.8, 3.0, 3.0, yaw), _rect(0, 0, 2.4, 3.0, 3.0, yaw)], "stone")
    m.loft([_rect(0, 0, 2.0, 1.6, 1.6, yaw), _rect(0, 0, h * 0.5, 1.45, 1.45, yaw),
            _rect(0, 0, h, 1.1, 1.1, yaw), _v(0, 0, h + 2.6)], "stone")
    return (), sink


def _burial_mound(m: _Mesh, rng: np.random.Generator) -> Built:
    sink, n = 2.5, 8
    a, b, h = 12.0 + rng.uniform(-1, 1), 8.0 + rng.uniform(-0.5, 0.5), 9.5 + rng.uniform(-0.8, 0.8)
    radii = 1.0 + rng.uniform(-0.05, 0.05, n)
    rings = [_ring(0, 0, -sink, a + 0.3, n, ry=b + 0.3, radii=radii), _ring(0, 0, 0.0, a, n, ry=b, radii=radii),
             _ring(0, 0, h * 0.38, a * 0.82, n, ry=b * 0.82), _ring(0.5, 0, h * 0.75, a * 0.52, n, ry=b * 0.5),
             _v(0.8, 0, h)]
    m.loft(rings, "stone")
    return (), sink


def _ruin_wall(m: _Mesh, rng: np.random.Generator) -> Built:
    """A run along y, its half-length RUN_HALF_LENGTH: three stepped-down pieces and a block
    fallen at the low end, all inside the run's 1 u half-thickness (task 6's capsule)."""
    sink, t, half = 3.0, 0.7, RUN_HALF_LENGTH
    pieces = [(-half, -3.5, 11.0), (-3.7, 3.0, 7.5), (2.8, 7.2, 4.5)]
    flip = rng.random() < 0.5
    if flip:
        pieces = [(-y1, -y0, h) for y0, y1, h in pieces[::-1]]
    for y0, y1, h in pieces:
        lo = np.array([[-t, y0, -sink], [t, y0, -sink], [t, y1, -sink], [-t, y1, -sink]])
        hi = lo.copy()
        hi[:, 2] = h + rng.uniform(-1.0, 1.0, 4)
        m.loft([lo, hi], "stone")
    tall = max(pieces, key=lambda p: p[2])
    cy = (tall[0] + tall[1]) / 2 + rng.uniform(-1, 1)
    m.loft([_rect(0.1, cy, tall[2] - 1.5, 0.6, 2.0, rng.uniform(-0.08, 0.08)),
            _rect(0.15, cy, tall[2] + 1.5, 0.55, 1.8, rng.uniform(-0.08, 0.08))], "stone",
           flags=FLAG_PASSABLE)      # set in the wall's top, above head height
    fy = -8.7 if flip else 8.7
    m.loft([_rect(0.0, fy, -0.8, 0.6, 1.0, rng.uniform(-0.1, 0.1)),
            _rect(0.05, fy, 1.6, 0.55, 0.9, rng.uniform(-0.1, 0.1))], "stone")
    return (), sink


_BUILDERS: Dict[Tuple[str, str], Callable[[_Mesh, np.random.Generator], Built]] = {
    ("hut", "timber"): _hut_timber,
    ("hut", "wattle"): _hut_wattle,
    ("barn", "timber"): _barn,
    ("tent", "canvas"): _tent_canvas,
    ("tent", "hide"): _tent_hide,
    ("lean_to", "timber"): lambda m, rng: _lean_to(m, rng, hide=False),
    ("lean_to", "hide"): lambda m, rng: _lean_to(m, rng, hide=True),
    ("tower", "stone"): _tower_stone,
    ("tower", "timber"): _tower_timber,
    ("tower", "lashed"): _tower_lashed,
    ("fire_ring", "stone"): _fire_ring,
    ("fence", "rail"): _fence_rail,
    ("fence", "stake"): _fence_stake,
    ("standing_stone", "stone"): _standing_stone,
    ("altar_stone", "stone"): _altar_stone,
    ("monument", "obelisk"): _monument_obelisk,
    ("monument", "burial_mound"): _burial_mound,
    ("ruin_wall", "stone"): _ruin_wall,
}


def structure_model(kind: str, variant: str = "", material_set: str = "timber_thatch",
                    seed: int = 0) -> StructureModel:
    """The model of ``kind`` in ``variant`` ("" is the default), textured from
    ``material_set``. Pure in its arguments."""
    variant = resolve_variant(kind, variant)
    rng = np.random.default_rng(seed)
    m = _Mesh()
    openings, sink = _BUILDERS[(kind, variant)](m, rng)
    ter = _finish(m, model_name(kind, variant, material_set), material_set, _warp(rng, WARP))
    xyz = np.array([(v.x, v.y, v.z) for v in ter.vertices])
    return StructureModel(
        kind=kind, variant=variant, material_set=material_set, ter=ter,
        radius=float(np.hypot(xyz[:, 0], xyz[:, 1]).max()), height=float(xyz[:, 2].max()),
        sink=sink, enterable=kind in ENTERABLE, openings=tuple(openings))
