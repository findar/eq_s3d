"""A room's real walls in plan (roadmap step 8, design "Outlines").

A room keeps its Box (``RoomSpec.bounds``) as its allotment: placement, stacking,
corridors and the Envelope all use it. An ``Outline`` is what the room actually
is inside that Box: a connected set of convex Cells on shared vertices, so a
floor, a ceiling and a wall weld exactly. A wall is any Cell edge with a chosen
Cell on one side only.

Doors reach the room through Throats, straight strips of floor as wide as the
corridor, and every Throat ends in the Core, the part round the Box's centre that
is always floor (the spawn and labels stand there).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

import numpy as np

Rect = Tuple[float, float, float, float]    # x0, y0, x1, y1


@dataclass
class Outline:
    verts: List[Tuple[float, float]]        # plan vertices, shared between Cells
    cells: List[List[int]]                  # convex Cells, counter-clockwise from above
    core: Rect                              # always floor; holds the Box's centre
    throats: List[Rect] = field(default_factory=list)   # one per door, Tunnel or slot

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Outline":
        return cls(verts=[tuple(v) for v in d["verts"]],
                   cells=[list(c) for c in d["cells"]],
                   core=tuple(d["core"]),
                   throats=[tuple(t) for t in d.get("throats", [])])

    def contains(self, pts: np.ndarray, tol: float = 1e-6) -> np.ndarray:
        """Which of the plan points ``pts`` (N, 2) lie on the room's floor."""
        pts = np.asarray(pts, dtype=np.float64)
        verts = np.asarray(self.verts, dtype=np.float64)
        inside = np.zeros(len(pts), bool)
        for cell in self.cells:
            poly = verts[cell]
            a, b = poly, np.roll(poly, -1, axis=0)
            edge = b - a
            lengths = np.maximum(np.linalg.norm(edge, axis=1), 1e-12)
            # Signed distance from each edge: inward is positive when counter-clockwise.
            side = ((edge[:, 0] * (pts[:, 1, None] - a[:, 1])
                     - edge[:, 1] * (pts[:, 0, None] - a[:, 0])) / lengths)
            inside |= (side >= -tol).all(axis=1)
        return inside
