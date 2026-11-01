"""
generators/vegetation/models.py
-------------------------------
Procedural low-poly tree models (trees spec task 3, Requirement 2).

:func:`tree_model` builds one ``EQGM`` model per Species, in the Classic
Karana recipe measured on the stock client (design "Research findings" 2):
about 15 solid trunk triangles and 16 walk-through canopy triangles.

- **Trunk:** a 6-sided prism tapering to 0.6 of its base radius, from
  ``-TRUNK_SINK`` (buried, so a tree on a slope shows no gap) up into the
  canopy, with a 4-triangle top cap: 16 triangles, collidable, opaque bark.
- **Broadleaf canopy:** 4 vertical cards crossed at 45° through the crown,
  each double-sided: 16 triangles.
- **Conifer canopy:** 3 stacked tiers of 2 crossed double-sided cards,
  narrowing upward: 24 triangles.

Canopy triangles carry ``FLAG_PASSABLE`` and use the chroma shader with the
leaf texture's alpha silhouette. Z is up and the origin is ground level. The
model is a pure function of the Species and the seed; no mesh file is read
(umbrella Req 32.7). Coordinates are rounded to float32 so the model
round-trips through ``core.ter`` exactly.
"""

from __future__ import annotations

import math
from typing import List, Tuple

import numpy as np

from core.ter import (
    FLAG_PASSABLE,
    MAGIC_MODEL,
    SHADER_CHROMA,
    SHADER_OPAQUE,
    Material,
    Polygon,
    TerFile,
    Vertex,
)
from generators.vegetation.kit import Species
from generators.vegetation.textures import bark_texture_name, leaf_texture_name

#: How far the trunk reaches below the model origin (world units at scale 1).
TRUNK_SINK = 12.0
#: Trunk top as a share of the tree height.
TRUNK_TOP = 0.45
#: Trunk sides.
TRUNK_SIDES = 6
#: Largest lean from vertical, degrees.
MAX_LEAN_DEG = 3.0

MAT_BARK = 0
MAT_LEAF = 1

Vec3 = Tuple[float, float, float]


def model_name(species: Species) -> str:
    """The archive filename of the Species' model."""
    return f"veg_{species.name}.mod"


def _f32(v: float) -> float:
    return float(np.float32(v))


class _Mesh:
    """Accumulates float32-exact vertices and triangles."""

    def __init__(self, shear: Tuple[float, float]):
        self.vertices: List[Vertex] = []
        self.polygons: List[Polygon] = []
        self._sx, self._sy = shear

    def vert(self, p: Vec3, n: Vec3, uv: Tuple[float, float]) -> int:
        x, y, z = p
        # The lean is a shear proportional to height; normals stay as given
        # (a 3° shear moves them by under 0.06 rad).
        x, y = x + self._sx * z, y + self._sy * z
        ln = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
        self.vertices.append(Vertex(
            x=_f32(x), y=_f32(y), z=_f32(z),
            nx=_f32(n[0] / ln), ny=_f32(n[1] / ln), nz=_f32(n[2] / ln),
            u=_f32(uv[0]), v=_f32(uv[1])))
        return len(self.vertices) - 1

    def tri(self, a: int, b: int, c: int, material: int, flags: int = 0) -> None:
        self.polygons.append(Polygon(a, b, c, material=material, flags=flags))


def _trunk(m: _Mesh, radius: float, top: float) -> None:
    """Tapered 6-sided prism from -TRUNK_SINK to ``top``, plus a top cap."""
    bottom = -TRUNK_SINK
    r_top = 0.6 * radius
    ring_b, ring_t = [], []
    for i in range(TRUNK_SIDES + 1):  # the seam column is duplicated for UVs
        a = 2 * math.pi * i / TRUNK_SIDES
        c, s = math.cos(a), math.sin(a)
        u = i / TRUNK_SIDES
        ring_b.append(m.vert((radius * c, radius * s, bottom), (c, s, 0.0), (u, (top - bottom) / 32)))
        ring_t.append(m.vert((r_top * c, r_top * s, top), (c, s, 0.0), (u, 0.0)))
    for i in range(TRUNK_SIDES):
        b0, b1, t0, t1 = ring_b[i], ring_b[i + 1], ring_t[i], ring_t[i + 1]
        # CCW seen from outside (counter-clockwise around +Z, going up).
        m.tri(b0, b1, t1, MAT_BARK)
        m.tri(b0, t1, t0, MAT_BARK)
    cap = []
    for i in range(TRUNK_SIDES):
        a = 2 * math.pi * i / TRUNK_SIDES
        c, s = math.cos(a), math.sin(a)
        cap.append(m.vert((r_top * c, r_top * s, top), (0.0, 0.0, 1.0), (0.5 + 0.5 * c, 0.5 + 0.5 * s)))
    for i in range(1, TRUNK_SIDES - 1):
        m.tri(cap[0], cap[i], cap[i + 1], MAT_BARK)


def _card(m: _Mesh, angle: float, width: float, z0: float, z1: float) -> None:
    """A vertical double-sided card through the axis, ``width`` wide from z0 to
    z1. UV v = 0 at the top edge (texture rows run top-down)."""
    dx, dy = math.cos(angle) * width / 2, math.sin(angle) * width / 2
    nx, ny = -math.sin(angle), math.cos(angle)  # horizontal card normal
    corners = [((-dx, -dy, z0), (0.0, 1.0)), ((dx, dy, z0), (1.0, 1.0)),
               ((dx, dy, z1), (1.0, 0.0)), ((-dx, -dy, z1), (0.0, 0.0))]
    for sign in (1.0, -1.0):
        n = (sign * nx, sign * ny, 0.0)
        idx = [m.vert(p, n, uv) for p, uv in corners]
        a, b, c, d = idx
        if sign > 0:   # CCW seen from +normal
            m.tri(a, d, c, MAT_LEAF, FLAG_PASSABLE)
            m.tri(a, c, b, MAT_LEAF, FLAG_PASSABLE)
        else:          # the back face: reversed winding
            m.tri(a, b, c, MAT_LEAF, FLAG_PASSABLE)
            m.tri(a, c, d, MAT_LEAF, FLAG_PASSABLE)


def _broadleaf_canopy(m: _Mesh, height: float, crown: float) -> None:
    crown_h = min(max(0.9 * crown, 0.6 * height), 0.95 * height)
    for k in range(4):
        _card(m, k * math.pi / 4, crown, height - crown_h, height)


def _conifer_canopy(m: _Mesh, height: float, crown: float, rng: np.random.Generator) -> None:
    base = 0.2 * height
    tier_h = (height - base) / 2.2
    step = (height - base - tier_h) / 2
    spin = rng.uniform(0, math.pi / 2)
    for k in range(3):
        z0 = base + k * step
        width = crown * (1.0 - 0.28 * k)
        for j in range(2):
            _card(m, spin + k * math.pi / 6 + j * math.pi / 2, width, z0, z0 + tier_h)


def tree_model(species: Species, seed: int) -> TerFile:
    """The ``EQGM`` model for ``species``. Pure in (species, seed)."""
    rng = np.random.default_rng(seed)
    height = float(rng.uniform(*species.height))
    crown = float(rng.uniform(*species.canopy))
    lean = math.radians(float(rng.uniform(0.0, MAX_LEAN_DEG)))
    lean_dir = float(rng.uniform(0.0, 2 * math.pi))
    t = math.tan(lean)
    m = _Mesh(shear=(t * math.cos(lean_dir), t * math.sin(lean_dir)))

    _trunk(m, species.trunk_radius, TRUNK_TOP * height)
    if species.form == "conifer":
        _conifer_canopy(m, height, crown, rng)
    else:
        _broadleaf_canopy(m, height, crown)

    bark = Material(index=MAT_BARK, name=f"veg_{species.name}_bark", shader=SHADER_OPAQUE)
    bark.add_diffuse(bark_texture_name(species))
    leaf = Material(index=MAT_LEAF, name=f"veg_{species.name}_leaf", shader=SHADER_CHROMA)
    leaf.add_diffuse(leaf_texture_name(species))
    return TerFile(name=model_name(species), magic=MAGIC_MODEL, version=2,
                   materials=[bark, leaf], vertices=m.vertices, polygons=m.polygons)
