"""Winding tunnels task 2 (Requirement 2; design "The centreline"): a rough corridor's plain
legs wind inside the clearance measured from the finished spec.
"""

import math

import pytest
from hypothesis import given, settings, strategies as st

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.geometry import MeshBuilder
from generators.routing import TunnelRules, corridor_route, wind_leg, winding_legs
from generators.topology.ruleset import RuleSetError
from generators.transitions import PLAYER_HALF_WIDTH, _corridor_boxes, leg_clearance
from generators.wall_styles import WALLS_DIR, load_style, load_styles, tunnel_rules
from generators.zone_spec import CorridorSpec, ZoneSpec

ROUGH = TunnelRules((20.0, 72.0), 60.0, 0.2, 20.0)

rules_st = st.builds(
    lambda lo, extra, turn, wander, end: TunnelRules((lo, lo + extra), turn, wander, end),
    st.floats(4.0, 50.0), st.floats(0.0, 80.0), st.floats(5.0, 120.0), st.floats(0.0, 1.0),
    st.floats(0.0, 40.0)) | st.just(ROUGH)


@st.composite
def legs(draw):
    along_x = draw(st.booleans())
    a0 = draw(st.floats(-500.0, 500.0))
    span = draw(st.floats(0.0, 500.0))
    a1 = a0 + span * draw(st.sampled_from((1.0, -1.0)))
    cross = draw(st.floats(-500.0, 500.0))
    drift = draw(st.floats(-2.0, 2.0))      # a near-straight route's ends differ across
    start = (a0, cross) if along_x else (cross, a0)
    end = (a1, cross + drift) if along_x else (cross + drift, a1)
    return start, end, along_x, draw(st.floats(2.0, 15.0))


def _local(line, start, along_x):
    """(along from start, across from start's line) of each point."""
    ax = 0 if along_x else 1
    return [(abs(p[ax] - start[ax]), p[1 - ax] - start[1 - ax]) for p in line]


def _heading(p, q):
    return math.atan2(q[1] - p[1], q[0] - p[0])


def _edges(local, hw):
    """The strip's two mitred edges, in local coordinates."""
    out = {1: [], -1: []}
    for i, p in enumerate(local):
        dirs = [_heading(local[j], local[j + 1]) for j in (i - 1, i) if 0 <= j < len(local) - 1]
        normals = [(-math.sin(a), math.cos(a)) for a in dirs]
        mx, my = sum(n[0] for n in normals), sum(n[1] for n in normals)
        size = math.hypot(mx, my)
        mx, my = mx / size, my / size
        reach = hw / (mx * normals[0][0] + my * normals[0][1])
        for side in (1, -1):
            out[side].append((p[0] + side * reach * mx, p[1] + side * reach * my))
    return out


@settings(max_examples=300, deadline=None)
@given(leg=legs(), clearance=st.floats(0.0, 120.0), rules=rules_st, seed=st.integers(0, 2 ** 32))
def test_wind_leg_properties(leg, clearance, rules, seed):
    start, end, along_x, hw = leg
    line = wind_leg(start, end, along_x, hw, clearance, rules, seed)
    # Deterministic, from its own seed.
    assert line == wind_leg(start, end, along_x, hw, clearance, rules, seed)
    ax = 0 if along_x else 1
    # The ends are exact: the start, and the far end's place on the start's line.
    assert line[0] == start
    assert line[-1][ax] == end[ax] and line[-1][1 - ax] == start[1 - ax]
    local = _local(line, start, along_x)
    span = abs(end[ax] - start[ax])
    us = [u for u, _ in local]
    assert all(b >= a - 1e-9 for a, b in zip(us, us[1:]))
    if len(line) == 2:
        return
    # Every turn within max_turn.
    heads = [_heading(local[i], local[i + 1]) for i in range(len(local) - 1)]
    for a, b in zip(heads, heads[1:]):
        assert abs(b - a) <= math.radians(rules.max_turn) + 1e-9
    # Straight for max(hw, end) at each end.
    run_in = max(hw, rules.end)
    for u, v in local:
        if u < run_in - 1e-6 or u > span - run_in + 1e-6:
            assert v == 0.0
    assert any(abs(u - run_in) < 1e-6 and v == 0.0 for u, v in local)
    assert any(abs(u - (span - run_in)) < 1e-6 and v == 0.0 for u, v in local)
    # The wander and the whole strip stay inside the clearance.
    assert max(abs(v) for _, v in local) <= min(clearance, rules.wander * span) + 1e-9
    for edge in _edges(local, hw).values():
        assert max(abs(v) for _, v in edge) <= hw + clearance + 1e-6


@settings(max_examples=100, deadline=None)
@given(leg=legs(), rules=rules_st, seed=st.integers(0, 2 ** 32))
def test_zero_clearance_is_the_straight_leg(leg, rules, seed):
    start, end, along_x, hw = leg
    line = wind_leg(start, end, along_x, hw, 0.0, rules, seed)
    far = (end[0], start[1]) if along_x else (start[0], end[1])
    assert line == [start, far]


def test_a_long_leg_with_room_winds():
    line = wind_leg((0.0, 0.0), (300.0, 0.0), True, 9.0, 40.0, ROUGH, "c:0")
    assert len(line) > 4 and max(abs(y) for _, y in line) > 1.0


def _segment_rect_distance(p, q, rect):
    x0, y0, x1, y1 = rect

    def point_rect(x, y):
        return math.hypot(max(x0 - x, 0.0, x - x1), max(y0 - y, 0.0, y - y1))

    def point_segment(x, y):
        dx, dy = q[0] - p[0], q[1] - p[1]
        t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((x - p[0]) * dx + (y - p[1]) * dy) / (dx * dx + dy * dy)))
        return math.hypot(p[0] + t * dx - x, p[1] + t * dy - y)

    for s in range(65):             # does it cross the rectangle?
        t = s / 64
        x, y = p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
        if x0 <= x <= x1 and y0 <= y <= y1:
            return 0.0
    return min([point_rect(*p), point_rect(*q)] + [point_segment(cx, cy) for cx in (x0, x1) for cy in (y0, y1)])


def _strip_clear_of(line, start, along_x, hw, z_lo, z_hi, boxes):
    """Each part of the strip's edges that leaves the straight strip, against each box beside
    the leg in Z: the least distance in plan (inf when nothing is near)."""
    ax = 0 if along_x else 1
    local = _local(line, start, along_x)
    sign = 1.0 if line[-1][ax] >= start[ax] else -1.0

    def world(u, v):
        a, c = start[ax] + sign * u, start[1 - ax] + v
        return (a, c) if along_x else (c, a)

    least = math.inf
    for edge in _edges(local, hw).values():
        for (u0, v0), (u1, v1) in zip(edge, edge[1:]):
            if max(abs(v0), abs(v1)) <= hw + 1e-9:
                continue
            for x0, y0, x1, y1, bz0, bz1 in boxes:
                if bz1 <= z_lo or bz0 >= z_hi:
                    continue
                least = min(least, _segment_rect_distance(world(u0, v0), world(u1, v1), (x0, y0, x1, y1)))
    return least


@st.composite
def boxes_beside(draw):
    n = draw(st.integers(0, 6))
    out = []
    for _ in range(n):
        x0, y0 = draw(st.floats(-50.0, 350.0)), draw(st.floats(-200.0, 200.0))
        w, d = draw(st.floats(1.0, 120.0)), draw(st.floats(1.0, 120.0))
        z0 = draw(st.floats(-60.0, 60.0))
        out.append((x0, y0, x0 + w, y0 + d, z0, z0 + draw(st.floats(5.0, 60.0))))
    return out


@settings(max_examples=200, deadline=None)
@given(boxes=boxes_beside(), span=st.floats(60.0, 300.0), hw=st.floats(3.0, 12.0), seed=st.integers(0, 999))
def test_a_strip_keeps_off_what_its_clearance_counted(boxes, span, hw, seed):
    start, end, height = (0.0, 0.0), (span, 0.0), 15.0
    room = leg_clearance((start, end), True, hw, 0.0, 0.0, height, max(hw, ROUGH.end), boxes)
    limit = min(room, ROUGH.wander * span)
    line = wind_leg(start, end, True, hw, limit, ROUGH, seed)
    if len(line) == 2:
        return
    assert _strip_clear_of(line, start, True, hw, -2.0, height + 2.0, boxes) >= PLAYER_HALF_WIDTH - 1e-6


# --- The [tunnel] rules ------------------------------------------------------------------

def test_rough_has_the_plain_tunnels_numbers():
    styles = load_styles()
    assert styles["rough"].tunnel == ROUGH
    assert tunnel_rules() == ROUGH
    assert all(s.tunnel is None for name, s in styles.items() if name != "rough")


def test_a_bad_tunnel_names_its_field(tmp_path):
    text = (WALLS_DIR / "rough.toml").read_text(encoding="utf-8")
    bad = text.replace("max_turn = 60", "max_turn = 400").replace("segment = [20, 72]", "segment = [72, 20]")
    path = tmp_path / "rough.toml"
    path.write_text(bad, encoding="utf-8")
    with pytest.raises(RuleSetError) as err:
        load_style(path)
    fields = {e.field for e in err.value.errors}
    assert {"max_turn", "segment"} <= fields


# --- The corridor's wind in JSON ---------------------------------------------------------

def test_wind_is_written_only_when_a_leg_winds():
    spec = ZoneSpec(name="w", zone_type="dungeon", safe_point=(0.0, 0.0, 1.0))
    spec.corridors = [CorridorSpec("a", 0, 0, 10, 0, wind=[0.0, 0.0]),
                      CorridorSpec("b", 0, 0, 10, 0, wind=[0.0, 3.5, 0.0]),
                      CorridorSpec("c", 0, 0, 10, 0)]
    rows = spec.to_dict()["corridors"]
    assert "wind" not in rows[0] and "wind" not in rows[2]
    assert rows[1]["wind"] == [0.0, 3.5, 0.0]
    again = ZoneSpec.from_dict(spec.to_dict())
    assert [c.wind for c in again.corridors] == [[], [0.0, 3.5, 0.0], []]


# --- Ten cave dungeons -------------------------------------------------------------------

def _cave(seed):
    plan = ZonePlan.from_controls({"zone_type": "dungeon", "dungeon_theme": "cave", "layout": "graph",
                                   "room_count": 12}, [])
    plan.name = "wind"
    return plan_to_spec(plan, seed=seed, warnings=[])


@pytest.mark.parametrize("seed", range(10))
def test_cave_strips_keep_off_rooms_and_corridors(seed):
    spec = _cave(seed)
    rooms = {r.id: r for r in spec.rooms}
    room_boxes = [(*r.bounds[0][:2], *r.bounds[1][:2], r.bounds[0][2], r.bounds[1][2]) for r in spec.rooms]
    boxes = {c.id: _corridor_boxes(c, rooms) for c in spec.corridors}
    for cor in spec.corridors:
        lines = winding_legs(cor, rooms)
        if cor.rough <= 0:
            assert cor.wind == [] and not any(lines)
        route = corridor_route(cor, rooms)
        zs, _ = MeshBuilder._waypoint_zs(list(route.waypoints), None if route.carry < 0 else route.carry,
                                         cor.from_z, cor.to_z)
        for k, line in enumerate(lines):
            if line is None:
                continue
            others = room_boxes + [b for cid, bs in boxes.items() if cid != cor.id for _, b in bs]
            others += [b for i, b in boxes[cor.id] if i != k]
            lo, hi = min(zs[k], zs[k + 1]) - 2.0, max(zs[k], zs[k + 1]) + cor.height + 2.0
            assert _strip_clear_of(line, line[0], route.axes[k], cor.width / 2, lo, hi, others) \
                >= PLAYER_HALF_WIDTH - 1e-6
