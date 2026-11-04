"""
tests/test_stair_geometry.py
----------------------------
Planned staircases (verticality step 7 task 3, Requirement 3, property V2).

A corridor with ``steps = AUTO_STAIRS`` gets a stair the builder plans:
risers of at most ``RISER_CAP`` and treads of ``TREAD_DEPTH``, straight when
the carry leg holds the run, else a Switchback folded into a stairwell beside
the leg. The built mesh is probed directly along the stair's walk path
(``StairLayout.path``): every riser, every tread, both ends flush with the
room floors, the landing flush with both flights, headroom over every tread,
walls wherever a floor ends, and the wall UV convention.

Task 2's gate checks (``classify_corridor``, ``check_connector``,
``corridor_continuity``) judge every planned stair on the built mesh: the
gate reads ``steps == AUTO_STAIRS`` through ``stair_layout``, walks its
``path`` against its ``profile`` and includes its stairwell. A gap cut into
a built switchback's landing must fail it, and the crossing check's floor
height (``_route_floor_z_at``) must read the stair's real floors.
"""

import dataclasses
import math

import numpy as np
import pytest
from hypothesis import assume, example, given, settings, strategies as st

import analyzer.traverse as T
from analyzer.traverse import AgentModel, build_walk_surface
from generators.geometry import (AUTO_STAIRS, MIN_LANE, RISER_CAP, TREAD_DEPTH,
                                 _overlap_area, _room_rects, build_mesh,
                                 stair_layout, stair_plan)
from generators.zone_spec import CorridorSpec, RoomSpec, ZoneSpec

AGENT = AgentModel()
EPS = 1e-4


# ---------------------------------------------------------------------------
# Builders and probes
# ---------------------------------------------------------------------------

def stair_spec(rise, run, width=40.0, height=50.0, *, along_x=True,
               reverse=False, jog=0.0):
    """Rooms ``a`` (floor 0) and ``b`` (floor ``rise``) joined by a planned
    stair, ``run`` u of corridor between their facing walls (task 2's
    builder, with ``steps = AUTO_STAIRS``). ``jog`` makes it a Z-route whose
    middle jog carries the stair; ``reverse`` runs the corridor from b."""
    def xy(u, v):
        return (u, v) if along_x else (v, u)

    side_a, side_b = ("E", "W") if along_x else ("N", "S")
    spec = ZoneSpec(name="stair", zone_type="dungeon")
    a = RoomSpec("a", *xy(0.0, 0.0), floor_z=0.0, width=200, depth=200,
                 height=80)
    a.role = "entrance"
    a.open_walls = [side_a]
    b = RoomSpec("b", *xy(200.0 + run, jog), floor_z=rise, width=200,
                 depth=200, height=80)
    b.open_walls = [side_b]
    spec.rooms = [a, b]
    pa, pb = xy(100.0, 0.0), xy(100.0 + run, jog)
    if not reverse:
        cor = CorridorSpec("stair", *pa, *pb, from_z=0.0, to_z=rise,
                           width=width, height=height, steps=AUTO_STAIRS,
                           from_room="a", to_room="b")
    else:
        cor = CorridorSpec("stair", *pb, *pa, from_z=rise, to_z=0.0,
                           width=width, height=height, steps=AUTO_STAIRS,
                           from_room="b", to_room="a")
    spec.corridors = [cor]
    spec.safe_point = (*xy(0.0, 0.0), 5.0)
    return spec


class Mesh:
    """The built mesh as triangles, split by geometric facing."""

    def __init__(self, spec):
        self.ter = build_mesh(spec).to_ter(spec.name)
        V = np.array([[v.x, v.y, v.z] for v in self.ter.vertices])
        F = np.array([[p.v1, p.v2, p.v3] for p in self.ter.polygons])
        self.tris = V[F]
        n = np.cross(self.tris[:, 1] - self.tris[:, 0],
                     self.tris[:, 2] - self.tris[:, 0])
        ln = np.linalg.norm(n, axis=1)
        ok = ln > 1e-9
        self.normals = np.zeros_like(n)
        self.normals[ok] = n[ok] / ln[ok, None]
        self.ok = ok
        self.floors = self.tris[ok & (self.normals[:, 2] > 0.5)]
        self.ceils = self.tris[ok & (self.normals[:, 2] < -0.5)]
        self.walls = self.tris[ok & (np.abs(self.normals[:, 2]) < 1e-6)]
        self.wall_n = self.normals[ok & (np.abs(self.normals[:, 2]) < 1e-6)]

    def heights(self, P, tris):
        """For points P (N, 2): (inside (N, M), z (N, M)) against ``tris``."""
        return T._bary_z(np.asarray(P, dtype=np.float64), tris)


def walk(path, ds):
    """Points every ``ds`` along a polyline, with their arc lengths."""
    pts, arcs, s = [], [], 0.0
    for p, q in zip(path, path[1:]):
        p, q = np.asarray(p, float), np.asarray(q, float)
        L = float(np.hypot(*(q - p)))
        k = max(1, int(math.ceil(L / ds)))
        for i in range(k):
            pts.append(p + (q - p) * i / k)
            arcs.append(s + L * i / k)
        s += L
    pts.append(np.asarray(path[-1], float))
    arcs.append(s)
    return np.array(pts), np.array(arcs)


def profile_z(lay, s):
    xs, zs = zip(*lay.profile)
    return np.interp(s, xs, zs)


def floor_profile(mesh, lay, ds=0.05):
    """The floor under the stair's walk path: (arc lengths, floor z), the
    floor nearest the planned pitch line at each point (NaN for none)."""
    P, S = walk(lay.path, ds)
    ins, z = mesh.heights(P, mesh.floors)
    zp = profile_z(lay, S)[:, None]
    d = np.where(ins, np.abs(z - zp), np.inf)
    k = d.argmin(axis=1)
    fz = z[np.arange(len(P)), k]
    fz[~np.isfinite(d.min(axis=1))] = np.nan
    return P, S, fz


def risers_of(S, fz, tol=1e-3):
    """(position, signed rise) of each jump in the floor profile."""
    out = []
    for i in range(1, len(S)):
        dz = fz[i] - fz[i - 1]
        if abs(dz) > tol:
            out.append(((S[i] + S[i - 1]) / 2, dz))
    return out


# ---------------------------------------------------------------------------
# The plan
# ---------------------------------------------------------------------------

@settings(max_examples=200, deadline=None)
@given(rise=st.floats(0.05, 200.0), leg=st.floats(0.0, 600.0))
def test_plan_risers_under_cap_and_straight_iff_leg_holds_run(rise, leg):
    p = stair_plan(rise, leg)
    n = math.ceil(rise / RISER_CAP - 1e-9)
    assert p.run == pytest.approx(n * TREAD_DEPTH)
    assert p.riser <= RISER_CAP + 1e-9
    assert p.riser * p.risers == pytest.approx(rise)
    assert p.switchback == (leg + 1e-6 < p.run)
    if p.switchback:
        assert p.flights == 2 and p.risers % 2 == 0
        assert p.flight_risers == math.ceil(n / 2)
    else:
        assert p.risers == n and p.flight_run == pytest.approx(p.run)


def test_plan_examples():
    C, D = RISER_CAP, TREAD_DEPTH
    p = stair_plan(4 * C, 4 * D)                # exactly fits: straight
    assert (p.risers, p.riser, p.switchback) == (4, C, False)
    p = stair_plan(-10 * C, 10 * D - 1)         # 10 risers, a bit short
    assert p.switchback and p.flight_risers == 5 and p.riser == pytest.approx(C)
    p = stair_plan(3 * C, D)                    # 3 risers -> 2 flights of 2
    assert p.switchback and p.risers == 4
    assert p.riser == pytest.approx(3 * C / 4)


def test_only_auto_corridors_get_a_layout():
    spec = stair_spec(10.0, 60.0)
    rooms = {r.id: r for r in spec.rooms}
    cor = spec.corridors[0]
    assert stair_layout(cor, rooms) is not None
    for steps in (0, 4):
        assert stair_layout(dataclasses.replace(cor, steps=steps), rooms) is None
    flat = dataclasses.replace(cor, to_z=cor.from_z)
    assert stair_layout(flat, rooms) is None


# ---------------------------------------------------------------------------
# Property: every planned stair is built as planned (V2)
# ---------------------------------------------------------------------------

def check_stair(spec):
    """Probe the built stair; return its layout. Asserts V2 and the walls."""
    rooms = {r.id: r for r in spec.rooms}
    cor = spec.corridors[0]
    lay = stair_layout(cor, rooms)
    assert lay is not None and not lay.cramped
    plan = lay.plan
    mesh = Mesh(spec)

    # Winding agrees with each face's declared normal (the gate tells floor
    # from ceiling by winding; UVs come from the declared normal).
    for p in mesh.ter.polygons:
        v = mesh.ter.vertices[p.v1]
        A, B, C = (np.array([mesh.ter.vertices[i].x, mesh.ter.vertices[i].y,
                             mesh.ter.vertices[i].z]) for i in (p.v1, p.v2, p.v3))
        g = np.cross(B - A, C - A)
        if np.linalg.norm(g) > 1e-9:
            assert g @ np.array([v.nx, v.ny, v.nz]) > 0

    # The floor along the walk: no hole, level treads joined by risers.
    P, S, fz = floor_profile(mesh, lay)
    assert not np.isnan(fz).any(), "hole under the walk path"
    assert abs(fz[0] - lay.from_z) < EPS and abs(fz[-1] - lay.to_z) < EPS
    rs = risers_of(S, fz)
    assert len(rs) == plan.risers
    for _, dz in rs:
        assert abs(dz) <= RISER_CAP + EPS
        assert abs(abs(dz) - plan.riser) < EPS
        assert dz * (lay.to_z - lay.from_z) > 0      # always the same way
    # Treads: TREAD_DEPTH between the risers of each flight.
    pos = [s for s, _ in rs]
    k = plan.flight_risers
    for f in range(plan.flights):
        fl = pos[f * k:(f + 1) * k]
        for a, b in zip(fl, fl[1:]):
            assert b - a == pytest.approx(TREAD_DEPTH, abs=0.06)
    # The floor never leaves the pitch line by more than a riser.
    assert np.all(np.abs(fz - profile_z(lay, S)) <= plan.riser + EPS)

    # Both ends flush: the floor just inside each room is the room's floor,
    # level with the corridor's end.
    for end, room_id, z in ((lay.path[0], cor.from_room, cor.from_z),
                            (lay.path[-1], cor.to_room, cor.to_z)):
        r = rooms[room_id]
        assert abs(r.floor_z - z) < EPS
        (x0, y0, _), (x1, y1, _) = r.bounds
        q = np.clip(np.asarray(end, float), [x0 + 2, y0 + 2], [x1 - 2, y1 - 2])
        ins, zz = mesh.heights(q[None], mesh.floors)
        assert np.any(ins[0] & (np.abs(zz[0] - r.floor_z) < EPS))
    if plan.switchback:
        zm = (lay.from_z + lay.to_z) / 2
        mid = (np.asarray(lay.path[2]) + np.asarray(lay.path[3])) / 2
        ins, zz = mesh.heights(mid[None], mesh.floors)
        assert np.any(ins[0] & (np.abs(zz[0] - zm) < EPS)), "landing not flush"

    # Headroom over every tread and landing: at least height less a riser.
    ins, cz = mesh.heights(P, mesh.ceils)
    above = np.where(ins & (cz > fz[:, None] + 1e-6), cz - fz[:, None], np.inf)
    head = above.min(axis=1)
    assert np.all(head >= cor.height - plan.riser - EPS), head.min()

    # Walls wherever the stair's floor ends: from points on the floor, a step
    # out in each direction either lands on floor within the step-up or
    # crosses a wall face at knee height.
    check_walls(mesh, spec, lay)

    # And the global flood (room reachability) walks from one room to the other.
    surf = build_walk_surface(mesh.ter, AGENT)
    seed = T.seed_face_for(surf, spec.safe_point)
    reached = T.flood_reachable(surf, seed)
    for r in spec.rooms:
        assert {int(f) for f in T._faces_in_room(surf, r)} & reached, r.id
    return lay


def check_walls(mesh, spec, lay, step=0.75, grid=1.5):
    """No drop off the stair's floor without a wall: sample the corridor and
    stairwell floor, step ``step`` out along ±X/±Y; where no floor is within
    the step-up there, a wall triangle must cross the step at knee height."""
    cor = spec.corridors[0]
    hw = cor.width / 2
    xs = [p[0] for p in lay.path] + ([lay.stairwell[0], lay.stairwell[2]]
                                     if lay.stairwell else [])
    ys = [p[1] for p in lay.path] + ([lay.stairwell[1], lay.stairwell[3]]
                                     if lay.stairwell else [])
    gx = np.arange(min(xs) - hw + 0.3, max(xs) + hw, grid)
    gy = np.arange(min(ys) - hw + 0.3, max(ys) + hw, grid)
    G = np.array([(x, y) for x in gx for y in gy])

    def in_room(P):
        m = np.zeros(len(P), bool)
        for r in spec.rooms:
            (x0, y0, _), (x1, y1, _) = r.bounds
            m |= ((P[:, 0] > x0 - 1) & (P[:, 0] < x1 + 1) &
                  (P[:, 1] > y0 - 1) & (P[:, 1] < y1 + 1))
        return m

    G = G[~in_room(G)]
    ins, z = mesh.heights(G, mesh.floors)
    has = ins.any(axis=1)
    G, ins, z = G[has], ins[has], z[has]
    # Each point's floors (a point may be over two stacked floors).
    for d in ((step, 0), (-step, 0), (0, step), (0, -step)):
        Q = G + np.array(d)
        qin, qz = mesh.heights(Q, mesh.floors)
        for i in range(len(G)):
            if in_room(Q[i:i + 1])[0]:
                continue
            for z0 in z[i][ins[i]]:
                near = qin[i] & (np.abs(qz[i] - z0) <= AGENT.max_step_up)
                if near.any():
                    continue
                assert crosses_wall(mesh, G[i], Q[i], z0 + 1.0), \
                    f"drop without a wall at {G[i]} z={z0:.2f} toward {d}"


def crosses_wall(mesh, p, q, z):
    """Does the segment p→q (XY) at height z cross a wall triangle?"""
    W = mesh.walls
    p3, q3 = np.array([p[0], p[1], z]), np.array([q[0], q[1], z])
    n = mesh.wall_n
    a = W[:, 0]
    dp = np.einsum("ij,ij->i", p3 - a, n)
    dq = np.einsum("ij,ij->i", q3 - a, n)
    hit = (dp * dq <= 0) & (np.abs(dp - dq) > 1e-12)
    for k in np.nonzero(hit)[0]:
        t = dp[k] / (dp[k] - dq[k])
        x = p3 + (q3 - p3) * t
        A, B, C = W[k]
        v0, v1, v2 = B - A, C - A, x - A
        d00, d01, d11 = v0 @ v0, v0 @ v1, v1 @ v1
        d20, d21 = v2 @ v0, v2 @ v1
        den = d00 * d11 - d01 * d01
        if abs(den) < 1e-12:
            continue
        b1 = (d11 * d20 - d01 * d21) / den
        b2 = (d00 * d21 - d01 * d20) / den
        if b1 >= -1e-6 and b2 >= -1e-6 and b1 + b2 <= 1 + 1e-6:
            return True
    return False


@settings(max_examples=40, deadline=None)
@given(
    rise=st.floats(1.0, 60.0).flatmap(lambda m: st.sampled_from([m, -m])),
    run=st.floats(12.0, 240.0),
    width=st.floats(12.0, 50.0),
    along_x=st.booleans(),
    reverse=st.booleans(),
    jog=st.sampled_from([0.0, 0.0, 70.0, -90.0, 160.0]),
)
@example(rise=10.0, run=60.0, width=40.0, along_x=True, reverse=False, jog=0.0)
@example(rise=30.0, run=20.0, width=40.0, along_x=True, reverse=False, jog=0.0)
@example(rise=-30.0, run=20.0, width=24.0, along_x=False, reverse=True, jog=0.0)
@example(rise=40.0, run=100.0, width=30.0, along_x=True, reverse=False, jog=90.0)
@example(rise=60.0, run=100.0, width=20.0, along_x=False, reverse=True, jog=-90.0)
def test_planned_stairs_built_as_planned(rise, run, width, along_x, reverse,
                                         jog):
    spec = stair_spec(rise, run, width, along_x=along_x, reverse=reverse,
                      jog=jog)
    lay = stair_layout(spec.corridors[0], {r.id: r for r in spec.rooms})
    assume(lay is not None and not lay.cramped)
    # Keeping a stairwell clear of the rooms is the layout's job (task 5);
    # here only stairwells the builder could place clear are judged.
    if lay.stairwell:
        assume(not any(_overlap_area(lay.stairwell, r)
                       for r in _room_rects(spec.rooms)))
    check_stair(spec)


def test_both_shapes_and_both_routes_occur():
    """The pinned cases cover straight and switchback, straight and Z."""
    cases = [stair_spec(10.0, 60.0), stair_spec(30.0, 20.0),
             stair_spec(40.0, 100.0, 30.0, jog=90.0),
             stair_spec(60.0, 100.0, 20.0, along_x=False, jog=-90.0)]
    kinds = set()
    for spec in cases:
        lay = check_stair(spec)
        kinds.add(("switchback" if lay.plan.switchback else "straight",
                   len(T.corridor_route(spec.corridors[0],
                                        {r.id: r for r in spec.rooms})
                       .waypoints)))
    assert {k for k, _ in kinds} == {"straight", "switchback"}
    assert {n for _, n in kinds} == {2, 4}


def test_switchback_stairwell_beside_the_carry_leg():
    """The stairwell box sits wholly beside the carry leg (outside its
    corridor band) and clear of the route's other legs; the rise stays on
    the carry leg (the other legs are level)."""
    spec = stair_spec(60.0, 100.0, 20.0, jog=90.0)
    rooms = {r.id: r for r in spec.rooms}
    cor = spec.corridors[0]
    lay = stair_layout(cor, rooms)
    assert lay.plan.switchback and lay.carry == 1
    route = T.corridor_route(cor, rooms)
    hw = cor.width / 2
    x0, y0, x1, y1 = lay.stairwell
    c = lay.start[1] if lay.along_x else lay.start[0]
    lo, hi = (y0, y1) if lay.along_x else (x0, x1)
    assert lo >= c + hw - EPS or hi <= c - hw + EPS
    for k, ((ax, ay), (bx, by)) in enumerate(zip(route.waypoints,
                                                 route.waypoints[1:])):
        if k == lay.carry:
            continue
        leg = (min(ax, bx) - hw, min(ay, by) - hw,
               max(ax, bx) + hw, max(ay, by) + hw)
        assert _overlap_area(lay.stairwell, leg) == 0.0


def test_cramped_leg_falls_back_to_stretched_stair():
    """A leg too short for two lanes builds the hand-count stair over it."""
    spec = stair_spec(30.0, 8.0, 40.0)
    lay = stair_layout(spec.corridors[0], {r.id: r for r in spec.rooms})
    assert lay.cramped and lay.lane < MIN_LANE
    ref = dataclasses.replace(spec, corridors=[
        dataclasses.replace(spec.corridors[0], steps=lay.plan.risers)])
    a = build_mesh(spec).to_ter("s")
    b = build_mesh(ref).to_ter("s")
    assert [(v.x, v.y, v.z) for v in a.vertices] == \
        [(v.x, v.y, v.z) for v in b.vertices]


# ---------------------------------------------------------------------------
# UVs: step 3's wall convention (tests/test_wall_uvs.py) on treads and risers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("spec", [
    stair_spec(10.0, 60.0), stair_spec(-30.0, 20.0, 24.0, along_x=False),
    stair_spec(30.0, 20.0, reverse=True),
    stair_spec(40.0, 100.0, 30.0, jog=90.0)],
    ids=["straight", "switchback-y-down", "switchback-reverse", "z-route"])
def test_stair_uvs_follow_the_wall_convention(spec):
    ter = build_mesh(spec).to_ter(spec.name)
    scale = 0.01                         # the default materials' 100 u repeat
    for p in ter.polygons:
        vs = [ter.vertices[i] for i in (p.v1, p.v2, p.v3)]
        n = np.array([vs[0].nx, vs[0].ny, vs[0].nz])
        P = np.array([[v.x, v.y, v.z] for v in vs])
        UV = np.array([[v.u, v.v] for v in vs])
        if n[2] > 0.5:
            assert UV == pytest.approx(np.c_[P[:, 0], -P[:, 1]] * scale)
        elif n[2] < -0.5:
            assert UV == pytest.approx(P[:, :2] * scale)
        else:
            e1, e2 = P[1] - P[0], P[2] - P[0]
            G = np.array([[e1 @ e1, e1 @ e2], [e1 @ e2, e2 @ e2]])
            if abs(np.linalg.det(G)) < 1e-9:
                continue

            def grad(vals):
                k = np.linalg.solve(G, [vals[1] - vals[0], vals[2] - vals[0]])
                return k[0] * e1 + k[1] * e2

            right = np.cross(-n, [0.0, 0.0, 1.0])
            right /= np.linalg.norm(right)
            assert grad(UV[:, 1]) @ [0, 0, 1] == pytest.approx(-scale, abs=1e-6)
            assert grad(UV[:, 0]) @ right == pytest.approx(scale, abs=1e-6)


# ---------------------------------------------------------------------------
# Task 2's gate on the built mesh
# ---------------------------------------------------------------------------
#
# Every verdict is on the corridor as the layout asks for it (steps ==
# AUTO_STAIRS); the gate finds the stair through ``stair_layout``.

def gate_verdicts(spec, ter=None):
    rooms = {r.id: r for r in spec.rooms}
    cor = spec.corridors[0]
    ter = ter or build_mesh(spec).to_ter(spec.name)
    surf = build_walk_surface(ter, AGENT)
    oracle = T.classify_corridor(cor, AGENT, rooms)
    mesh = T.check_connector(surf, cor, rooms, AGENT)
    cont = T.corridor_continuity(surf, spec, AGENT)[0]
    return oracle, mesh, cont


def assert_gate_passes(spec):
    lay = stair_layout(spec.corridors[0], {x.id: x for x in spec.rooms})
    (ok, why), mesh, cont = gate_verdicts(spec)
    assert ok, why
    assert mesh.ok, mesh.reason
    assert mesh.kind == "stair"
    assert len(mesh.risers) == lay.plan.risers
    assert all(abs(abs(r) - lay.plan.riser) < 1e-3 for r in mesh.risers)
    assert cont.connected, cont.reason


@settings(max_examples=30, deadline=None)
@given(
    rise=st.floats(1.0, 60.0).flatmap(lambda m: st.sampled_from([m, -m])),
    run=st.floats(12.0, 240.0),
    width=st.floats(12.0, 50.0),
    along_x=st.booleans(),
    reverse=st.booleans(),
    jog=st.sampled_from([0.0, 0.0, 70.0, -90.0, 160.0]),
)
@example(rise=40.0, run=200.0, width=40.0, along_x=True, reverse=False, jog=0.0)
@example(rise=30.0, run=20.0, width=40.0, along_x=True, reverse=False, jog=0.0)
@example(rise=-30.0, run=20.0, width=40.0, along_x=False, reverse=True, jog=0.0)
@example(rise=60.0, run=100.0, width=20.0, along_x=True, reverse=False, jog=90.0)
def test_gate_passes_planned_stairs(rise, run, width, along_x, reverse, jog):
    """Straight (compact flight on any leg) and switchback, on straight and
    Z routes, up and down: all three gate checks pass the built stair."""
    spec = stair_spec(rise, run, width, along_x=along_x, reverse=reverse,
                      jog=jog)
    lay = stair_layout(spec.corridors[0], {r.id: r for r in spec.rooms})
    assume(lay is not None and not lay.cramped)
    if lay.stairwell:
        assume(not any(_overlap_area(lay.stairwell, r)
                       for r in _room_rects(spec.rooms)))
    assert_gate_passes(spec)


def test_gate_fails_a_switchback_with_no_landing():
    """The gate isn't vacuous: cut the landing out of a built switchback and
    the connector walk and continuity both report the gap."""
    spec = stair_spec(30.0, 20.0)
    lay = stair_layout(spec.corridors[0], {r.id: r for r in spec.rooms})
    assert lay.plan.switchback
    zm = (lay.from_z + lay.to_z) / 2
    (lx, ly), (mx, my) = lay.path[2], lay.path[3]
    ter = build_mesh(spec).to_ter(spec.name)
    keep = []
    for p in ter.polygons:
        vs = [ter.vertices[i] for i in (p.v1, p.v2, p.v3)]
        cx = sum(v.x for v in vs) / 3
        cy = sum(v.y for v in vs) / 3
        landing = (all(abs(v.z - zm) < 1e-6 for v in vs) and vs[0].nz > 0.5
                   and min(lx, mx) - 6 <= cx <= max(lx, mx) + 6
                   and min(ly, my) - 6 <= cy <= max(ly, my) + 6)
        if not landing:
            keep.append(p)
    assert len(keep) < len(ter.polygons)
    ter.polygons = keep
    (ok, _), mesh, cont = gate_verdicts(spec, ter)
    assert ok                                   # the spec itself is fine
    assert not mesh.ok and "gap" in mesh.reason, mesh.reason
    assert not cont.connected


@pytest.mark.parametrize("spec", [
    stair_spec(40.0, 200.0), stair_spec(30.0, 20.0),
    stair_spec(-60.0, 100.0, 20.0, along_x=False, jog=90.0)],
    ids=["compact-long-leg", "switchback", "switchback-z-down"])
def test_crossing_check_reads_the_stair_floor(spec):
    """``_route_floor_z_at`` (the corridor-crossing check's own-tube test)
    puts every floor face of the built stair within a riser of its height."""
    rooms = {r.id: r for r in spec.rooms}
    cor = spec.corridors[0]
    lay = stair_layout(cor, rooms)
    route = T.corridor_route(cor, rooms)
    mesh = Mesh(spec)
    rects = _room_rects(spec.rooms)
    checked = 0
    for tri in mesh.floors:
        c = tri.mean(axis=0)
        if any(x0 <= c[0] <= x1 and y0 <= c[1] <= y1
               for x0, y0, x1, y1 in rects):
            continue
        z = T._route_floor_z_at(route, cor, c[0], c[1], lay)
        assert abs(z - c[2]) <= lay.plan.riser + EPS, (c, z)
        checked += 1
    assert checked > 10
