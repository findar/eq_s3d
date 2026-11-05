"""
tests/test_traverse_ceilings.py
-------------------------------
The walk gate stands on floors only (verticality task 18): a ceiling's
underside is wound down by the box builder and is never standable, so a
storey's ceiling can't pass as floor under the storey above.

* A corridor over another, one Slab (14 u) between the lower tube's ceiling
  and the upper floor: the lower ceiling is not on the walk surface, and
  ``corridor_conflicts`` reports nothing (it read the ceiling as a floor 14 u
  under the upper one, inside the height + 1 clearance).
* A room under a corridor and a room under a room, likewise: the lower ceiling
  is not walkable, the corridor over it is not "crosses room", and each room's
  faces are its own floor.

Built by the box backend (``generators.geometry.build_mesh``).
"""

import numpy as np

import analyzer.traverse as T
from analyzer.traverse import AgentModel, build_walk_surface
from core.ter import Polygon, TerFile, Vertex
from generators.geometry import build_mesh
from generators.topology.embed import SLAB
from generators.zone_spec import CorridorSpec, RoomSpec, ZoneSpec

AGENT = AgentModel()
H = 30.0                   # corridor height
UP = H + SLAB              # the upper corridor's floor


def _room(rid, x, y, z, walls, h=80.0):
    r = RoomSpec(rid, x, y, floor_z=z, width=200, depth=200, height=h)
    r.open_walls = list(walls)
    return r


def _surface(spec):
    return build_walk_surface(build_mesh(spec).to_ter(spec.name), AGENT)


def _at(surf, x, y, z, tol=0.5):
    """(standable, built): faces over the XY point (x, y) at height z."""
    built = np.zeros(len(surf.faces), bool)
    for f, tri in enumerate(surf.verts[surf.faces]):
        if abs(surf.centroids[f, 2] - z) <= tol and T._point_in_tri_xy(x, y, tri):
            built[f] = True
    return built & surf.standable, built


class _Mesh:
    """Hand-built faces: floors wound up, ceilings wound down, in 20 u tiles
    (the gate's conflict test compares floors cell by cell)."""

    def __init__(self):
        self.v, self.p = [], []

    def _quad(self, *pts):
        base = len(self.v)
        self.v += [Vertex(x=x, y=y, z=z) for x, y, z in pts]
        self.p += [Polygon(base, base + 1, base + 2, 0, 0),
                   Polygon(base, base + 2, base + 3, 0, 0)]

    def tube(self, x0, y0, x1, y1, z, h, step=20.0):
        """A corridor's floor at z and ceiling at z + h over the rect."""
        for u in np.arange(x0, x1, step):
            for v in np.arange(y0, y1, step):
                u1, v1 = min(u + step, x1), min(v + step, y1)
                self._quad((u, v, z), (u1, v, z), (u1, v1, z), (u, v1, z))
                self._quad((u, v1, z + h), (u1, v1, z + h), (u1, v, z + h),
                           (u, v, z + h))

    def ter(self):
        t = TerFile(name="tubes")
        t.vertices, t.polygons = self.v, self.p
        return t


def crossing_spec(up=UP):
    """Corridor ``low`` along X at z=0 and ``high`` along Y at ``up``, crossing
    over (0, 0); each joins its own two rooms (none shared). Only the two tubes
    are built."""
    spec = ZoneSpec(name="cross", zone_type="dungeon")
    w, e = _room("w", -300, 0, 0.0, "E"), _room("e", 300, 0, 0.0, "W")
    s, n = _room("s", 0, -300, up, "N"), _room("n", 0, 300, up, "S")
    spec.rooms = [w, e, s, n]
    spec.corridors = [
        CorridorSpec("low", -200, 0, 200, 0, from_z=0.0, to_z=0.0, width=20,
                     height=H, from_room="w", to_room="e"),
        CorridorSpec("high", 0, -200, 0, 200, from_z=up, to_z=up, width=20,
                     height=H, from_room="s", to_room="n"),
    ]
    m = _Mesh()
    m.tube(-200, -10, 200, 10, 0.0, H)
    m.tube(-10, -200, 10, 200, up, H)
    return spec, build_walk_surface(m.ter(), AGENT)


def test_corridor_over_a_corridor_one_slab_apart():
    spec, surf = crossing_spec()
    # The lower tube's ceiling (z = H) is built, wound down, not standable.
    std, built = _at(surf, 0.0, 0.0, H)
    assert built.any() and not std.any()
    assert (surf.normals[built, 2] < 0).all()
    assert _at(surf, 0.0, 0.0, 0.0)[0].any()
    assert _at(surf, 0.0, 0.0, UP)[0].any()
    assert T.corridor_conflicts(surf, spec, AGENT) == []


def test_corridor_closer_than_its_height_still_conflicts():
    # The clearance still holds between floors: 20 u apart is under H + 1.
    spec, surf = crossing_spec(up=20.0)
    assert T.corridor_conflicts(surf, spec, AGENT) == [("high", "low")]


def stacked_rooms_spec():
    """A cellar (floor 0) with a corridor over it from ``a`` to ``b`` one Slab
    over its ceiling, and a loft one Slab over a store room beside it."""
    up = 80.0 + SLAB
    spec = ZoneSpec(name="stack", zone_type="dungeon")
    a, b = _room("a", -300, 0, up, "E"), _room("b", 300, 0, up, "W")
    cellar = _room("cellar", 0, 0, 0.0, "")
    store = _room("store", 0, 400, 0.0, "")
    loft = _room("loft", 0, 400, up, "")
    a.role = "entrance"
    spec.rooms = [a, cellar, b, store, loft]
    spec.corridors = [CorridorSpec("over", -200, 0, 200, 0, from_z=up, to_z=up,
                                   width=20, height=H, from_room="a", to_room="b")]
    spec.safe_point = (-300.0, 0.0, up + 5)
    return spec, up


def test_room_under_a_corridor_and_under_a_room():
    spec, up = stacked_rooms_spec()
    surf = _surface(spec)
    for x, y in ((0.0, 0.0), (0.0, 400.0)):
        std, built = _at(surf, x, y, 80.0)        # the lower ceiling
        assert built.any() and not std.any()
    # The corridor over the cellar is another storey, not a crossing.
    [cont] = T.corridor_continuity(surf, spec, AGENT)
    assert cont.connected, cont.reason
    assert T.corridor_conflicts(surf, spec, AGENT) == []
    # Each stacked room finds only its own floor.
    rooms = spec.rooms
    by = {r.id: r for r in rooms}
    for rid, z in (("cellar", 0.0), ("store", 0.0), ("loft", up)):
        faces = T._faces_in_room(surf, by[rid], rooms)
        assert len(faces)
        assert np.allclose(surf.centroids[faces][:, 2], z, atol=0.5), rid
