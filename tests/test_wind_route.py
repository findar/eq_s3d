"""Winding routes task 1 (Requirements 1 and 2; design "Data", "The route line", "Clearance"):
``routing.wind_route`` draws a rough corridor's centreline opening to opening, and
``transitions.measure_winds`` stores it in ``CorridorSpec.path`` only where its strip clears
everything else.
"""

import functools
import json
import math

import pytest
from hypothesis import given, settings, strategies as st

from tests.pbt_helpers import scaled

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.layout import ENTRY_MAX
from generators.routing import (HELD_TURN_MAX, TunnelRules, angled, corridor_route, door_ends, entry_line,
                                plan_route, plan_u_route, route_seed, strip_corners, wind_route)
from generators.transitions import (PLAYER_HALF_WIDTH, WIND_Z_SPARE, _corridor_boxes, path_pieces,
                                    poly_gap)
from generators.zone_spec import CorridorSpec, ZoneSpec

ROUGH = TunnelRules((20.0, 72.0), 60.0, 0.2, 20.0)

rules_st = st.builds(
    lambda lo, extra, turn, wander, end: TunnelRules((lo, lo + extra), turn, wander, end),
    st.floats(4.0, 50.0), st.floats(0.0, 80.0), st.floats(5.0, 120.0), st.floats(0.0, 1.0),
    st.floats(0.0, 40.0)) | st.just(ROUGH)


@st.composite
def routes(draw):
    """A straight, Z, L or U route between two openings, as the layout plans them."""
    hw = draw(st.floats(2.0, 15.0))
    a = (draw(st.floats(-300.0, 300.0)), draw(st.floats(-300.0, 300.0)))
    b = (draw(st.floats(-300.0, 300.0)), draw(st.floats(-300.0, 300.0)))
    kind = draw(st.sampled_from(("plan", "u")))
    if kind == "u":
        route = plan_u_route(a, b, draw(st.sampled_from("NSEW")), 2 * hw)
    else:
        route = plan_route(a, b, draw(st.booleans()), draw(st.booleans()), hw, 0)
    return route, hw


def _dist(p, q):
    return math.hypot(q[0] - p[0], q[1] - p[1])


def _turns(line):
    out = []
    for i in range(1, len(line) - 1):
        (ax, ay), (bx, by), (cx, cy) = line[i - 1], line[i], line[i + 1]
        d0, d1 = (bx - ax, by - ay), (cx - bx, cy - by)
        out.append(abs(math.degrees(math.atan2(d0[0] * d1[1] - d0[1] * d1[0], d0[0] * d1[0] + d0[1] * d1[1]))))
    return out


def _exit(route, end):
    """The unit heading out of the first opening (end 0) or into the last (end 1)."""
    (x0, y0), (x1, y1) = route.waypoints[:2] if end == 0 else route.waypoints[-2:]
    d = math.hypot(x1 - x0, y1 - y0)
    return (x1 - x0) / d, (y1 - y0) / d


@settings(max_examples=scaled(300), deadline=None)
@given(routes(), rules_st, st.integers(0, 2 ** 32), st.booleans())
def test_route_line_shape(case, rules, seed, wander):
    """Ends exactly at the openings, straight ``max(hw, end)`` out of each along its exit axis,
    no turn past ``max_turn``."""
    route, hw = case
    line = wind_route(route, hw, rules, seed, wander)
    if line is None:
        return
    a, b = route.waypoints[0], route.waypoints[-1]
    assert line[0] == pytest.approx(a) and line[-1] == pytest.approx(b)
    run = max(hw, rules.end)
    da, db = _exit(route, 0), _exit(route, 1)
    assert line[1] == pytest.approx((a[0] + da[0] * run, a[1] + da[1] * run), abs=1e-6)
    assert line[-2] == pytest.approx((b[0] - db[0] * run, b[1] - db[1] * run), abs=1e-6)
    assert max(_turns(line)) <= rules.max_turn + 1e-6
    assert all(_dist(p, q) > 1e-6 for p, q in zip(line, line[1:]))


@settings(max_examples=scaled(100), deadline=None)
@given(routes(), rules_st, st.integers(0, 2 ** 32))
def test_route_line_is_pure(case, rules, seed):
    route, hw = case
    assert wind_route(route, hw, rules, seed) == wind_route(route, hw, rules, seed)


def test_bends_cut_and_runs_wander():
    """A Z route's square bends become 45 degree turns at ``max_turn`` 60, and its long runs
    wander, within ``wander`` x span."""
    route = plan_route((0.0, 0.0), (300.0, 80.0), True, True, 8.0, 0)
    plain = wind_route(route, 8.0, ROUGH, "s", wander=False)
    assert plain is not None
    assert _turns(plain) == pytest.approx([0.0, 45.0, 45.0, 0.0], abs=1e-6)
    wound = wind_route(route, 8.0, ROUGH, "s")
    assert len(wound) > len(plain) and max(_turns(wound)) <= 60.0 + 1e-6
    # Every point stays within wander x the route's longest run of the plain line's bones.
    assert min(p[1] for p in wound) >= -0.2 * 300 and max(p[1] for p in wound) <= 80 + 0.2 * 300


def test_nothing_to_wind():
    """Too short to leave a run-out at each end, or a square route with nothing to cut."""
    assert wind_route(plan_route((0.0, 0.0), (30.0, 0.0), True, True, 8.0, 0), 8.0, ROUGH, 1) is None
    assert wind_route(plan_route((0.0, 0.0), (100.0, 0.0), True, True, 8.0, 0), 8.0, ROUGH, 1,
                      wander=False) is None
    # A U-route's stubs are a corridor width, shorter than the run-out.
    assert wind_route(plan_u_route((0.0, 0.0), (0.0, -100.0), "E", 16.0), 8.0, ROUGH, 1) is None


def test_poly_gap():
    sq = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    assert poly_gap(sq, [(x + 13, y) for x, y in sq]) == pytest.approx(3.0)
    assert poly_gap(sq, [(x + 13, y + 14) for x, y in sq]) == pytest.approx(5.0)
    assert poly_gap(sq, [(x + 5, y + 5) for x, y in sq]) == 0.0
    diamond = [(15.0, 5.0), (20.0, 0.0), (25.0, 5.0), (20.0, 10.0)]
    assert poly_gap(sq, diamond) == pytest.approx(5.0)


# --- Builds ----------------------------------------------------------------------------

#: (seed, rooms, verticality): 10 cave dungeons on the graph layout, 8-30 rooms, each verticality.
CAVES = [(s, r, v) for s, (r, v) in enumerate(
    [(8, "flat"), (12, "moderate"), (16, "dramatic"), (20, "flat"), (25, "moderate"),
     (30, "dramatic"), (10, "flat"), (14, "moderate"), (22, "dramatic"), (28, "flat")])]


@functools.lru_cache(maxsize=None)
def _spec(seed, rooms, verticality):
    plan = ZonePlan.from_controls({"zone_type": "dungeon", "dungeon_theme": "cave", "layout": "graph",
                                   "room_count": rooms, "verticality": verticality}, [])
    plan.name = f"wr_cave{seed}"
    return plan_to_spec(plan, seed=seed, warnings=[])


def _entry_fallback(cor, rooms):
    """Whether ``cor``'s path is an angled corridor's entry line (random placement task 10:
    ``routing.entry_line`` or ``held_entry_line``, when no wound line fits), not one
    ``wind_route`` or ``hold_route`` draws."""
    if not angled(cor):
        return False
    route = corridor_route(cor, rooms)
    if any(wind_route(route, cor.width / 2, ROUGH, route_seed(cor), w) == cor.path for w in (True, False)):
        return False
    if cor.transition is None:
        return cor.path == entry_line(route, cor.width / 2, max(cor.width / 2, ROUGH.end))
    return True


def _band(z0, z1, height):
    return min(z0, z1) - WIND_Z_SPARE, max(z0, z1) + height + WIND_Z_SPARE


@pytest.mark.slow
@pytest.mark.parametrize("case", CAVES, ids=[f"{r}-{v}" for _, r, v in CAVES])
def test_stored_paths_clear_everything(case):
    """A2: every stored path's strip keeps the player's half-width from every room box and
    every other corridor's boxes and path beside it in Z; it reaches the two rooms it joins
    only along its run-outs. It starts and ends at the corridor's openings."""
    spec = _spec(*case)
    rooms = {r.id: r for r in spec.rooms}
    room_solids = [(r.id, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z0, z1)
                   for r in spec.rooms for (x0, y0, z0), (x1, y1, z1) in [r.bounds]]
    pieces = {}
    for cor in spec.corridors:
        if cor.path:
            assert cor.steps == 0 and not cor.bridge and (cor.rough > 0 or cor.transition is not None)
            # An angled end (random placement task 10) starts on the wall plane
            # (``door_ends``), and its run-out may turn the entry angle more.
            a, b = door_ends(corridor_route(cor, rooms))
            assert cor.path[0] == pytest.approx(a) and cor.path[-1] == pytest.approx(b)
            pieces[cor.id] = path_pieces(cor.path, cor.width / 2, cor.from_z, cor.to_z)
            assert pieces[cor.id] is not None, f"{cor.id}'s strip folds"
            turns = _turns(cor.path)
            if _entry_fallback(cor, rooms):
                # No wound line fit: the entry line by the route's own bends (square as a Z's,
                # or a held line's turn back to its held stretch).
                assert max(turns) <= HELD_TURN_MAX + 1e-6, (cor.id, turns)
                continue
            extra = [ENTRY_MAX if cor.entry and cor.entry[e] else 0.0 for e in (0, 1)]
            for i, t in enumerate(turns):
                spare = extra[0] if i == 0 else extra[1] if i == len(turns) - 1 else 0.0
                assert t <= ROUGH.max_turn + spare + 1e-6, (cor.id, i, t)
    for cor in spec.corridors:
        if not cor.path:
            continue
        others = [(rid, poly, z0, z1) for rid, poly, z0, z1 in room_solids]
        for o in spec.corridors:
            if o.id == cor.id:
                continue
            others += [("", [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z0, z1)
                       for _, (x0, y0, x1, y1, z0, z1) in _corridor_boxes(o, rooms)]
            others += [("", quad, min(za, zb), max(za, zb) + o.height) for quad, za, zb in pieces.get(o.id, ())]
        # An angled corridor's entry line (random placement task 10) is unchecked, as the
        # legs it stands for are: it keeps the half-width, or no less than its legs do.
        legs = ([[(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
                 for _, (x0, y0, x1, y1, _z0, _z1) in _corridor_boxes(cor, rooms)]
                if _entry_fallback(cor, rooms) else None)
        last = len(pieces[cor.id]) - 1
        for j, (quad, za, zb) in enumerate(pieces[cor.id]):
            lo, hi = _band(za, zb, cor.height)
            for rid, poly, z0, z1 in others:
                if z1 <= lo or z0 >= hi:
                    continue
                if (j == 0 and rid == cor.from_room) or (j == last and rid == cor.to_room):
                    continue
                need = PLAYER_HALF_WIDTH
                if legs is not None:
                    need = min(need, min(poly_gap(leg, poly) for leg in legs))
                assert poly_gap(quad, poly) >= need - 1e-6, (cor.id, j, rid)


@pytest.mark.slow
def test_paths_wind_most_cave_corridors():
    """Most rough cave corridors that hold no Transition line get a path (87 of 132 at the
    cave run of 4 widths, winding routes task 4; 75% held at 9)."""
    eligible = with_path = 0
    for case in CAVES:
        for cor in _spec(*case).corridors:
            if cor.rough > 0 and cor.transition is None:
                eligible += 1
                with_path += bool(cor.path)
    assert with_path >= 0.6 * eligible, (with_path, eligible)


def test_path_is_the_route_line():
    """The stored path is ``wind_route``'s line for the corridor's route and seed."""
    spec = _spec(*CAVES[0])
    rooms = {r.id: r for r in spec.rooms}
    stored = [c for c in spec.corridors if c.path]
    assert stored
    for cor in stored:
        route = corridor_route(cor, rooms)
        lines = [wind_route(route, cor.width / 2, ROUGH, route_seed(cor), w) for w in (True, False)]
        if angled(cor) and cor.transition is None:
            # Random placement task 10: failing a wound line, an angled corridor still
            # leaves its doors at the angle they were cut for, along its entry line.
            lines.append(entry_line(route, cor.width / 2, max(cor.width / 2, ROUGH.end)))
        assert any(line == cor.path for line in lines), cor.id


# --- Data --------------------------------------------------------------------------------

def test_path_round_trips_and_is_written_only_when_set():
    spec = ZoneSpec(name="t")
    spec.corridors = [CorridorSpec(id="a", from_x=0, from_y=0, to_x=10, to_y=0),
                      CorridorSpec(id="b", from_x=0, from_y=0, to_x=10, to_y=0,
                                   path=[(0.0, 0.0), (2.5, 1.25), (10.0, 0.0)])]
    d = spec.to_dict()
    assert "path" not in d["corridors"][0]
    assert d["corridors"][1]["path"] == [[0.0, 0.0], [2.5, 1.25], [10.0, 0.0]] or \
        d["corridors"][1]["path"] == [(0.0, 0.0), (2.5, 1.25), (10.0, 0.0)]
    back = ZoneSpec.from_dict(json.loads(json.dumps(d)))
    assert back.corridors[0].path == []
    assert back.corridors[1].path == [(0.0, 0.0), (2.5, 1.25), (10.0, 0.0)]
    assert json.dumps(back.to_dict(), sort_keys=True) == json.dumps(json.loads(json.dumps(d)), sort_keys=True)


def test_strip_corners_fold():
    """A turn too sharp for the width folds the strip, as ``_add_winding_leg`` refuses it."""
    assert strip_corners([(0.0, 0.0), (20.0, 0.0), (40.0, 0.0)], 5.0) is not None
    assert strip_corners([(0.0, 0.0), (20.0, 0.0), (22.0, 2.0), (22.0, 20.0)], 8.0) is None
