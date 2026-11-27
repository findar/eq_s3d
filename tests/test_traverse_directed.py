"""
tests/test_traverse_directed.py
-------------------------------
The gate reads a drop as a one-way link (district races step 31, task 2): an open
floor edge with floor more than the step-up and at most ``max_drop`` below, nothing
in the way, links upper -> lower, and a room passes only if the player can reach it
from the entrance AND get back.

Hand-built faces (floors wound up, cliff and railing faces vertical):

* A one-way loop: the entrance ``a`` drops 20 u into the pit ``b``, a ramp climbs from
  ``b`` to the ledge ``c`` 20 u over ``a``, and ``c`` drops back into ``a``. Every room
  passes, and only through the drops (``max_drop=0`` fails ``b`` and ``c``).
* The same with a railing along ``c``'s edge: no way back, ``b`` and ``c`` fail as
  stranded.
* Two rooms a drop apart: within ``max_drop`` the lower one is stranded; deeper, the
  edge is a wall and the report is the one ``max_drop=0`` gives.

And the box backend's ramp and stair, each way: one component, no drop, the same report
with the pass on or off.
"""

import numpy as np
import pytest

import analyzer.traverse as T
from analyzer.traverse import AgentModel, build_walk_surface, find_drops, shell_report
from core.ter import Polygon, TerFile, Vertex
from generators.geometry import build_mesh
from generators.zone_spec import RoomSpec, ZoneSpec
from tests.test_traverse_connectors import stair_spec

AGENT = AgentModel()
OFF = AgentModel(max_drop=0.0)


class _Mesh:
    """Faces by hand, floors in 20 u tiles wound up."""

    def __init__(self):
        self.v, self.p = [], []

    def quad(self, *pts):
        base = len(self.v)
        self.v += [Vertex(x=x, y=y, z=z) for x, y, z in pts]
        self.p += [Polygon(base, base + 1, base + 2, 0, 0),
                   Polygon(base, base + 2, base + 3, 0, 0)]

    def floor(self, x0, y0, x1, y1, z, step=20.0):
        for u in np.arange(x0, x1, step):
            for v in np.arange(y0, y1, step):
                u1, v1 = min(u + step, x1), min(v + step, y1)
                self.quad((u, v, z), (u1, v, z), (u1, v1, z), (u, v1, z))

    def ramp(self, x0, x1, y0, y1, z0, z1, seg=8.0):
        """A ramp along +Y from (y0, z0) to (y1, z1), one quad per ``seg`` u."""
        ys = np.arange(y0, y1 + 1e-9, seg)
        for ya, yb in zip(ys[:-1], ys[1:]):
            za = z0 + (z1 - z0) * (ya - y0) / (y1 - y0)
            zb = z0 + (z1 - z0) * (yb - y0) / (y1 - y0)
            self.quad((x0, ya, za), (x1, ya, za), (x1, yb, zb), (x0, yb, zb))

    def wall_x(self, x, y0, y1, z0, z1):
        """A vertical face in the plane x = const."""
        self.quad((x, y0, z0), (x, y1, z0), (x, y1, z1), (x, y0, z1))

    def wall_y(self, y, x0, x1, z0, z1):
        self.quad((x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1))

    def ter(self):
        t = TerFile(name="drops")
        t.vertices, t.polygons = self.v, self.p
        return t


def _room(rid, x0, y0, x1, y1, z, role="normal"):
    r = RoomSpec(rid, (x0 + x1) / 2, (y0 + y1) / 2, floor_z=z, width=x1 - x0,
                 depth=y1 - y0, height=60.0)
    r.role = role
    return r


def loop_zone(railing=False):
    """``a`` (entrance, z 20) | ``b`` (pit, z 0) side by side; a ramp north out of ``b``
    up to a landing at z 40 beside the ledge ``c`` (z 40), which overhangs ``a``'s north
    edge. ``railing`` puts a rail along ``c``'s edge over ``a``."""
    m = _Mesh()
    m.floor(0, 0, 100, 100, 20.0)            # a
    m.floor(100, 0, 200, 100, 0.0)           # b
    m.wall_x(100, 0, 100, 0.0, 20.0)         # cliff a -> b
    m.ramp(100, 200, 100, 260, 0.0, 40.0)    # b up to the landing (14 deg, 2 u a quad)
    m.floor(100, 260, 200, 300, 40.0)        # landing
    m.floor(0, 100, 100, 300, 40.0)          # c
    m.wall_y(100, 0, 100, 20.0, 40.0)        # cliff c -> a
    if railing:
        m.wall_y(100, 0, 100, 40.0, 46.0)
    spec = ZoneSpec(name="loop", zone_type="dungeon")
    spec.rooms = [_room("a", 0, 0, 100, 100, 20.0, "entrance"),
                  _room("b", 100, 0, 200, 100, 0.0),
                  _room("c", 0, 100, 100, 300, 40.0)]
    spec.safe_point = (50.0, 50.0, 25.0)
    return spec, m.ter()


def ledge_zone(height):
    """``a`` (entrance) ``height`` u over ``b``, beside it, a cliff face between."""
    m = _Mesh()
    m.floor(0, 0, 100, 100, height)
    m.floor(100, 0, 200, 100, 0.0)
    m.wall_x(100, 0, 100, 0.0, height)
    spec = ZoneSpec(name="ledge", zone_type="dungeon")
    spec.rooms = [_room("a", 0, 0, 100, 100, height, "entrance"),
                  _room("b", 100, 0, 200, 100, 0.0)]
    spec.safe_point = (50.0, 50.0, height + 5.0)
    return spec, m.ter()


def _off(zone):
    spec, ter = zone
    return shell_report(ter, spec, OFF)


def _verdict(shell):
    return [(r.room_id, r.reachable, r.reason) for r in shell.rooms]


def _room_of(shell, rid):
    return next(r for r in shell.rooms if r.room_id == rid)


def _drop_heights(surf, drops):
    return sorted({round(float(surf.centroids[u, 2] - surf.centroids[low, 2]), 3)
                   for u, lows in drops.items() for low in lows})


def test_drop_in_and_a_way_back_passes():
    spec, ter = loop_zone()
    shell = shell_report(ter, spec, AGENT)
    assert shell.reachable_rooms == 3, _verdict(shell)
    assert _drop_heights(shell.surface, shell.drops) == [20.0]
    # Each drop runs a -> b or c -> a, never back up.
    z = shell.surface.centroids[:, 2]
    pairs = {(round(z[u]), round(z[low])) for u, lows in shell.drops.items() for low in lows}
    assert pairs == {(20, 0), (40, 20)}
    # The pass is what lets them in: with it off, b and c are another component.
    off = shell_report(ter, spec, OFF)
    assert off.drops == {}
    assert [r.reachable for r in off.rooms] == [True, False, False]


def test_no_way_back_fails_naming_the_stranded_rooms():
    spec, ter = loop_zone(railing=True)
    shell = shell_report(ter, spec, AGENT)
    assert _room_of(shell, "a").reachable
    for rid in ("b", "c"):
        r = _room_of(shell, rid)
        assert not r.reachable
        assert r.reason.startswith(T.STRANDED), r.reason
    # The railing blocks c's drop; a's drop into b is still there.
    pairs = {(round(shell.surface.centroids[u, 2]), round(shell.surface.centroids[low, 2]))
             for u, lows in shell.drops.items() for low in lows}
    assert pairs == {(20, 0)}


@pytest.mark.parametrize("height", [10.0, 40.0, T.AgentModel().max_drop])
def test_a_drop_with_no_way_back_is_stranded(height):
    spec, ter = ledge_zone(height)
    shell = shell_report(ter, spec, AGENT)
    assert _drop_heights(shell.surface, shell.drops) == [height]
    b = _room_of(shell, "b")
    assert not b.reachable and b.reason.startswith(T.STRANDED), b.reason
    assert shell.reachable == _off(ledge_zone(height)).reachable


@pytest.mark.parametrize("height", [T.AgentModel().max_drop + 1.0, 200.0])
def test_a_drop_deeper_than_max_drop_is_a_wall(height):
    spec, ter = ledge_zone(height)
    shell = shell_report(ter, spec, AGENT)
    assert shell.drops == {}
    off = _off(ledge_zone(height))
    assert _verdict(shell) == _verdict(off)
    assert not _room_of(shell, "b").reachable
    assert not _room_of(shell, "b").reason.startswith(T.STRANDED)


def test_a_step_is_not_a_drop():
    spec, ter = ledge_zone(AGENT.max_step_up)
    shell = shell_report(ter, spec, AGENT)
    assert shell.drops == {} and shell.reachable_rooms == 2


def test_max_drop_sets_the_limit():
    spec, ter = ledge_zone(40.0)
    assert find_drops(build_walk_surface(ter, AGENT), AgentModel(max_drop=30.0)) == {}
    assert find_drops(build_walk_surface(ter, AGENT), AgentModel(max_drop=50.0))


@pytest.mark.parametrize("steps", [0, 8], ids=["ramp", "stair"])
@pytest.mark.parametrize("reverse", [False, True], ids=["up", "down"])
def test_ramps_and_stairs_stay_two_way(steps, reverse):
    spec = stair_spec(20.0, steps, 100.0, reverse=reverse)
    for entrance in ("a", "b"):
        for r in spec.rooms:
            r.role = "entrance" if r.id == entrance else "normal"
        room = next(r for r in spec.rooms if r.id == entrance)
        spec.safe_point = (room.center_x, room.center_y, room.floor_z + 5.0)
        ter = build_mesh(spec).to_ter(spec.name)
        shell = shell_report(ter, spec, AGENT, True)
        assert shell.reachable_rooms == 2, _verdict(shell)
        assert all(c.connected for c in shell.corridors)
        off = shell_report(build_mesh(spec).to_ter(spec.name), spec, OFF, True)
        assert _verdict(shell) == _verdict(off)
        assert shell.reachable == off.reachable


# --- A Transition's clearance is the race it was cut for (task 16) ------------

def _raced_frame(zone_race, races):
    """test_gate_transitions' 14 u frame between rooms a (District 0) and b (District 1)."""
    from generators.zone_spec import DistrictSpec
    from tests.test_gate_transitions import JAMBS, _spec, _verdict as frame_verdict
    spec = _spec()
    spec.dungeon_race = zone_race
    if races is not None:
        spec.districts = [DistrictSpec(i, room_ids=[rid], race=race)
                          for i, (rid, race) in enumerate(zip("ab", races))]
        for d in spec.districts:
            next(r for r in spec.rooms if r.id == d.room_ids[0]).district = d.id
    return frame_verdict(*JAMBS, spec=spec)


def test_a_goblin_breach_into_a_giant_zone_is_measured_at_goblin_size():
    """The prompt's goblins in a giant zone: the 14 u hole is judged against 2 goblin H (12 u)."""
    v = _raced_frame("giant", ("", "goblin"))
    assert v.ok, v.reason


@pytest.mark.parametrize("zone_race, races", [("giant", None), ("giant", ("", "")),
                                              ("", ("giant", "giant")), ("goblin", ("giant", "giant"))])
def test_the_bar_is_still_the_larger_race_where_both_ends_are(zone_race, races):
    """No District race reads the zone's, as before; giant at both ends still needs 44 u."""
    v = _raced_frame(zone_race, races)
    assert not v.ok and "under 44.0 u" in v.reason, v.reason