"""
generators/wilderness/water.py
------------------------------
The visual water plane (wilderness spec task 6, Req 11.4 / 13.1).

Every fine-grid quad whose cell is ``water`` (boundary river edge) or ``river``
(interior channel) gets a flat surface at the matrix ``Water_Level``. The
surface is purely VISUAL: its polygons carry ``FLAG_PASSABLE`` (EQG collision
is per-triangle, ``0x01`` = non-collidable), so the client walks through it and
``analyzer.traverse.build_walk_surface`` never stands on it. A river edge is
sealed by its Invisible_Wall, not by the water.

The synth freezes the water bed AT ``Water_Level``, so a surface there would
z-fight with the bed. :func:`sink_water_bed` lowers every vertex that touches
only water quads by :data:`WATER_DEPTH`; shore vertices stay put, so the bank
still meets the surface flush.

Real swimmable or shallow-water volumes are OUT OF SCOPE: the ``AWT`` region
emitted here marks the visual body for the client and the sidecar, but nothing
tunes swim depth, current or shallows, and the water sits beyond the
Invisible_Wall where no player reaches it anyway.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from core.ter import FLAG_PASSABLE, Polygon, TerFile, Vertex
from generators.zone_spec import RegionSpec

#: Fine-cell Node_Types that lie under the water surface.
WATER_TYPES = frozenset({"water", "river"})

#: How far the fully-submerged bed is sunk below ``Water_Level`` (EQ units).
WATER_DEPTH: float = 12.0

#: TER/spec material name of the surface (the bed keeps ``wild_water``). The
#: ``liquid_`` prefix is what ``analyzer.rof2check``'s ``collision_policy``
#: allows to carry passable polygons.
WATER_SURFACE_MATERIAL = "liquid_water"


def water_quad_mask(node_type: np.ndarray) -> np.ndarray:
    """``(nx-1, ny-1)`` bool: the terrain quads that lie under water.

    A quad between vertex ``(i, j)`` and ``(i+1, j+1)`` takes its cell from the
    lower corner — the same rule ``build_wilderness_ter`` uses for materials.
    """
    is_water = np.isin(node_type, list(WATER_TYPES))
    return is_water[:-1, :-1]


def sink_water_bed(heights: np.ndarray, quads: np.ndarray,
                   water_level: float, depth: float = WATER_DEPTH) -> np.ndarray:
    """A copy of ``heights`` with every vertex that touches ONLY water quads
    lowered to ``water_level - depth``. Shore vertices are unchanged."""
    nx, ny = heights.shape
    touch = np.zeros((nx, ny), dtype=np.int32)   # quads touching each vertex
    wet = np.zeros((nx, ny), dtype=np.int32)     # ... of which are water
    q = quads.astype(np.int32)
    for di in (0, 1):
        for dj in (0, 1):
            touch[di:nx - 1 + di, dj:ny - 1 + dj] += 1
            wet[di:nx - 1 + di, dj:ny - 1 + dj] += q
    submerged = (touch > 0) & (wet == touch)
    out = np.array(heights, dtype=np.float64, copy=True)
    out[submerged] = np.minimum(out[submerged], water_level - depth)
    return out


def add_water_surface(ter: TerFile, quads: np.ndarray, origin: Tuple[float, float],
                      resolution: float, water_level: float, material: int) -> int:
    """Append the flat, passable water surface over ``quads`` to ``ter``.

    Vertices sit on the terrain's cell-centre frame at ``water_level``, shared
    between neighbouring water quads; winding matches the terrain (CCW from
    +Z). Returns the number of polygons added.
    """
    ox, oy = origin
    res = float(resolution)
    index: Dict[Tuple[int, int], int] = {}

    def vid(i: int, j: int) -> int:
        k = index.get((i, j))
        if k is None:
            x = ox + (i + 0.5) * res
            y = oy + (j + 0.5) * res
            k = len(ter.vertices)
            ter.vertices.append(Vertex(x=x, y=y, z=water_level, nx=0.0, ny=0.0, nz=1.0,
                                       u=x / 128.0, v=y / 128.0))
            index[(i, j)] = k
        return k

    added = 0
    for i, j in zip(*np.nonzero(quads)):
        i, j = int(i), int(j)
        a, b, c, d = vid(i, j), vid(i + 1, j), vid(i + 1, j + 1), vid(i, j + 1)
        ter.polygons.append(Polygon(a, b, c, material=material, flags=FLAG_PASSABLE))
        ter.polygons.append(Polygon(a, c, d, material=material, flags=FLAG_PASSABLE))
        added += 2
    return added


def _components(mask: np.ndarray) -> List[List[Tuple[int, int]]]:
    """4-connected components of ``mask``'s True cells, as coord lists."""
    cells = {(int(i), int(j)) for i, j in zip(*np.nonzero(mask))}
    comps: List[List[Tuple[int, int]]] = []
    seen: set = set()
    for start in sorted(cells):
        if start in seen:
            continue
        seen.add(start)
        comp, stack = [start], [start]
        while stack:
            ci, cj = stack.pop()
            for nb in ((ci + 1, cj), (ci - 1, cj), (ci, cj + 1), (ci, cj - 1)):
                if nb in cells and nb not in seen:
                    seen.add(nb)
                    comp.append(nb)
                    stack.append(nb)
        comps.append(comp)
    return comps


def water_regions(node_type: np.ndarray, origin: Tuple[float, float],
                  resolution: float, water_level: float,
                  depth: float = WATER_DEPTH) -> List[RegionSpec]:
    """One ``RegionSpec(kind="water")`` (-> ``AWT``) per connected water body,
    spanning its footprint from the sunk bed up to ``water_level``."""
    ox, oy = origin
    res = float(resolution)
    out: List[RegionSpec] = []
    for n, comp in enumerate(_components(np.isin(node_type, list(WATER_TYPES)))):
        ii = [i for i, _ in comp]
        jj = [j for _, j in comp]
        x0, x1 = ox + min(ii) * res, ox + (max(ii) + 1) * res
        y0, y1 = oy + min(jj) * res, oy + (max(jj) + 1) * res
        out.append(RegionSpec(
            id=f"water_{n}", kind="water",
            center_x=0.5 * (x0 + x1), center_y=0.5 * (y0 + y1),
            center_z=water_level - 0.5 * depth,
            extent_x=0.5 * (x1 - x0), extent_y=0.5 * (y1 - y0),
            extent_z=0.5 * depth,
        ))
    return out
