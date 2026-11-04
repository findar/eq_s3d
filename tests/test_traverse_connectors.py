"""
tests/test_traverse_connectors.py
---------------------------------
The walk gate knows Staircases and Bridges before any layout makes them
(verticality step 7, Requirement 2, design property V1).

* Staircases are built by the box backend's own ``steps > 0`` path
  (``generators.geometry.build_mesh``), over rise, steps, run, width and
  height, on straight and Z routes, up and down. For each one the spec-level
  oracle (``classify_corridor``), the mesh-level connector walk
  (``check_connector``) and the gate's corridor continuity
  (``corridor_continuity``) must all give the verdict the numbers predict,
  naming the same failure classes.
* Bridges are built by hand as faces: a deck at the upper level crossing a
  tall lower room's air, flush with two upper rooms.
* Each failure class is pinned as an explicit regression case.
"""

import math

import numpy as np
import pytest
from hypothesis import assume, example, given, settings, strategies as st

import analyzer.traverse as T
from analyzer.traverse import AgentModel, build_walk_surface
from core.ter import Polygon, TerFile, Vertex
from generators.geometry import build_mesh
from generators.zone_spec import CorridorSpec, RoomSpec, ZoneSpec

AGENT = AgentModel()


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def stair_spec(rise, steps, run, width=40.0, height=50.0, *, along_x=True,
               reverse=False, jog=0.0, b_floor_off=0.0, b_shift=0.0):
    """Two rooms joined by one staircase corridor.

    Room ``a`` (floor 0) and room ``b`` (floor ``rise + b_floor_off``) face
    each other across ``run`` u of corridor along X (or Y). ``jog`` offsets
    ``b`` sideways so the route becomes a Z-corridor whose middle jog carries
    the stair. ``reverse`` makes ``b`` the corridor's from-room, so the walk
    and the build run the other way. ``b_shift`` moves ``b`` away from the
    doorway, leaving a hole at that landing.
    """
    def xy(u, v):
        return (u, v) if along_x else (v, u)

    side_a, side_b = ("E", "W") if along_x else ("N", "S")
    spec = ZoneSpec(name="stair", zone_type="dungeon")
    a = RoomSpec("a", *xy(0.0, 0.0), floor_z=0.0, width=200, depth=200, height=80)
    a.role = "entrance"
    a.open_walls = [side_a]
    b = RoomSpec("b", *xy(200.0 + run + b_shift, jog),
                 floor_z=rise + b_floor_off, width=200, depth=200, height=80)
    b.open_walls = [side_b]
    spec.rooms = [a, b]
    pa = xy(100.0, 0.0)
    pb = xy(100.0 + run, jog)
    if not reverse:
        cor = CorridorSpec("stair", *pa, *pb, from_z=0.0, to_z=rise,
                           width=width, height=height, steps=steps,
                           from_room="a", to_room="b")
    else:
        cor = CorridorSpec("stair", *pb, *pa, from_z=rise, to_z=0.0,
                           width=width, height=height, steps=steps,
                           from_room="b", to_room="a")
    spec.corridors = [cor]
    spec.safe_point = (*xy(0.0, 0.0), 5.0)
    return spec


def surface_of(spec):
    return build_walk_surface(build_mesh(spec).to_ter(spec.name), AGENT)


def verdicts(spec):
    """(spec oracle, mesh connector walk, gate continuity) for the corridor."""
    rooms = {r.id: r for r in spec.rooms}
    cor = spec.corridors[0]
    surf = surface_of(spec)
    oracle = T.classify_corridor(cor, AGENT, rooms)
    mesh = T.check_connector(surf, cor, rooms, AGENT)
    cont = T.corridor_continuity(surf, spec, AGENT)[0]
    return oracle, mesh, cont


def classes(reason, names=T.STAIR_FAILURES):
    """The failure classes a reason names (each reason part is 'class: …')."""
    if not reason:
        return set()
    return {part.split(":", 1)[0] for part in reason.split("; ")} & set(names)


def assert_agree(spec, expected):
    """Oracle, mesh walk and gate all reach ``expected`` (a set of classes)."""
    (ok, why), mesh, cont = verdicts(spec)
    assert classes(why if not ok else "") == expected, why
    assert classes(mesh.reason) == expected, mesh.reason
    assert mesh.ok == (not expected)
    assert cont.connected == (not expected), cont.reason
    if expected:
        assert classes(cont.reason) == expected, cont.reason
    return mesh


def expected_classes(rise, steps, run, height, agent=AGENT):
    """What the numbers say for a straight stair (a one-leg flight = run)."""
    r = abs(rise) / steps
    out = set()
    if r > agent.max_step_up:
        out.add("riser too tall")
    if steps >= 2 and run / steps < agent.min_tread:
        out.add("tread too short")
    # Built from the low-coordinate end: the ceiling descends over a tread
    # when the stair goes down along the axis (rise < 0 here).
    if height - (r if rise < 0 else 0.0) < agent.player_height:
        out.add("no headroom")
    return out


# ---------------------------------------------------------------------------
# Property: generated staircases (V1)
# ---------------------------------------------------------------------------

@settings(max_examples=60, deadline=None)
@given(
    rise=st.floats(1.0, 40.0).flatmap(
        lambda m: st.sampled_from([m, -m])),
    steps=st.integers(1, 24),
    run=st.floats(4.0, 120.0),
    width=st.floats(6.0, 60.0),
    height=st.floats(4.0, 60.0),
    along_x=st.booleans(),
    reverse=st.booleans(),
)
# One pinned example per class (and the good stair of today's geometry).
@example(rise=12.0, steps=6, run=100.0, width=40.0, height=50.0,
         along_x=True, reverse=False)                  # walkable
@example(rise=20.0, steps=4, run=100.0, width=40.0, height=50.0,
         along_x=True, reverse=False)                  # riser too tall
@example(rise=10.0, steps=8, run=10.0, width=40.0, height=50.0,
         along_x=False, reverse=False)                 # tread too short
@example(rise=10.0, steps=5, run=100.0, width=40.0, height=5.0,
         along_x=True, reverse=True)                   # no headroom
@example(rise=-10.0, steps=5, run=100.0, width=40.0, height=7.5,
         along_x=True, reverse=False)                  # no headroom (descending)
def test_generated_stairs_gate_agrees_with_numbers(rise, steps, run, width,
                                                   height, along_x, reverse):
    r = abs(rise) / steps
    tread = run / steps
    head = height - (r if rise < 0 else 0.0)
    # Stay off the thresholds by more than measurement noise.
    assume(abs(r - AGENT.max_step_up) > 0.02)
    assume(steps < 2 or abs(tread - AGENT.min_tread) > 0.02)
    assume(abs(head - AGENT.player_height) > 0.02)
    assume(r >= 0.25 and (steps < 2 or tread >= 0.25))
    spec = stair_spec(rise, steps, run, width, height,
                      along_x=along_x, reverse=reverse)
    mesh = assert_agree(spec, expected_classes(rise, steps, run, height))
    # The walk sees the stair the builder made: `steps` risers of r.
    assert len(mesh.risers) == steps
    assert all(abs(abs(h) - r) < 1e-6 for h in mesh.risers)


@settings(max_examples=25, deadline=None)
@given(
    rise=st.floats(4.0, 30.0),
    steps=st.integers(3, 12),
    jog=st.floats(90.0, 200.0),
    run=st.floats(150.0, 260.0),
    reverse=st.booleans(),
)
def test_generated_z_route_stairs_walk(rise, steps, jog, run, reverse):
    """A stair on a Z-corridor's middle jog (flight pulled back at both
    bends) walks when its risers are climbable, and the treads measured on
    the mesh are the jog's built length / steps."""
    width = 40.0
    assume(rise / steps < AGENT.max_step_up - 0.02)
    flight = jog - width          # the jog, less half a width at each bend
    assume(flight / steps > AGENT.min_tread + 0.02)
    spec = stair_spec(rise, steps, run, width, 50.0, jog=jog, reverse=reverse)
    mesh = assert_agree(spec, set())
    assert len(mesh.risers) == steps
    assert all(abs(t - flight / steps) < 1e-3 for t in mesh.treads)


# ---------------------------------------------------------------------------
# Pinned regression cases: each stair failure class
# ---------------------------------------------------------------------------

class TestStairFailureClasses:
    def test_todays_default_stair_walks(self):
        # rise 12 over 6 steps: 2 u risers, 16.7 u treads, full headroom.
        mesh = assert_agree(stair_spec(12.0, 6, 100.0), set())
        assert mesh.min_headroom == pytest.approx(50.0)

    def test_riser_too_tall(self):
        assert_agree(stair_spec(20.0, 4, 100.0), {"riser too tall"})

    def test_single_tall_riser_is_a_riser_not_a_landing(self):
        # One step of 5 u: its only riser stands at the doorway, but it is
        # the stair's own riser, so the class is "riser too tall".
        assert_agree(stair_spec(5.0, 1, 40.0), {"riser too tall"})

    def test_tread_too_short(self):
        assert_agree(stair_spec(10.0, 8, 10.0), {"tread too short"})

    def test_no_headroom(self):
        assert_agree(stair_spec(10.0, 5, 100.0, height=5.0), {"no headroom"})

    def test_no_headroom_descending_ceiling(self):
        # Height 7.5 clears the player on flat floor, but the ceiling over a
        # descending tread drops a riser (2 u) before the next one: 5.5 u.
        assert_agree(stair_spec(-10.0, 5, 100.0, height=7.5), {"no headroom"})

    @pytest.mark.parametrize("reverse", [False, True])
    def test_gap_at_landing_floor_step(self, reverse):
        # Room b's floor sits 5 u above where the stair lands.
        assert_agree(stair_spec(10.0, 5, 100.0, b_floor_off=5.0,
                                reverse=reverse), {"gap at landing"})

    def test_gap_at_landing_on_z_route(self):
        # The flight is the middle jog; the 4 u step is at b's doorway, past
        # a flat stub — still a landing.
        assert_agree(stair_spec(12.0, 6, 150.0, jog=120.0, b_floor_off=4.0),
                     {"gap at landing"})

    def test_gap_at_landing_hole(self):
        # Room b stands 6 u back from the doorway: no floor between.
        assert_agree(stair_spec(10.0, 5, 100.0, b_shift=6.0), {"gap at landing"})

    def test_small_landing_offset_within_step_up_walks(self):
        # b's floor 0.5 u above the landing: the last riser is 2.5 u, fine.
        assert_agree(stair_spec(10.0, 5, 100.0, b_floor_off=0.5), set())

    def test_several_classes_named_together(self):
        mesh = assert_agree(stair_spec(24.0, 6, 9.0, height=5.0),
                            {"riser too tall", "tread too short", "no headroom"})
        assert mesh.reason.index("riser too tall") < mesh.reason.index("tread")


class TestOracleAlone:
    """``classify_corridor`` keeps its historic answers for ramps, flats and
    the pre-existing stair cases (no rooms passed)."""

    def test_old_oversized_stair_message_kept(self):
        ok, why = T.classify_corridor(
            CorridorSpec("c", 0, 0, 100, 0, from_z=0, to_z=75, steps=5), AGENT)
        assert not ok and "15.0u" in why and "riser too tall" in why

    def test_ramp_and_flat_unchanged(self):
        assert T.classify_corridor(
            CorridorSpec("c", 0, 0, 100, 0), AGENT) == (True, "flat")
        ok, why = T.classify_corridor(
            CorridorSpec("c", 0, 0, 50, 0, from_z=0, to_z=66), AGENT)
        assert not ok and "cliff ramp" in why


class TestGateDiagnosis:
    """Through the whole gate: the built ``.eqg`` and ``validate``."""

    @staticmethod
    def _validate(spec, tmp_path):
        from generators.builder import ZoneBuilder
        res = ZoneBuilder(spec).build(output_dir=str(tmp_path), write_glb=False)
        return T.validate(res.eqg_path, spec=spec, check_corridors=True)

    def test_good_stair_passes_the_gate(self, tmp_path):
        rep = self._validate(stair_spec(12.0, 6, 100.0), tmp_path)
        assert rep.passed and rep.corridors_passed, rep.summary()

    def test_tall_riser_named_for_room_and_corridor(self, tmp_path):
        rep = self._validate(stair_spec(20.0, 4, 100.0), tmp_path)
        assert not rep.passed and not rep.corridors_passed
        b = next(r for r in rep.rooms if r.room_id == "b")
        assert "riser too tall" in b.reason, b.reason
        assert "riser too tall" in rep.corridors[0].reason

    def test_short_tread_fails_corridors(self, tmp_path):
        # The flood still crosses 1.25 u treads (they touch), so every room
        # is "reachable"; the connector check is what fails the gate.
        rep = self._validate(stair_spec(10.0, 8, 10.0), tmp_path)
        assert rep.passed
        assert not rep.corridors_passed
        assert classes(rep.corridors[0].reason) == {"tread too short"}


# ---------------------------------------------------------------------------
# Bridges (hand-built faces)
# ---------------------------------------------------------------------------

DECK_Z = 60.0


class _Mesh:
    def __init__(self):
        self.v, self.p = [], []

    def quad(self, p0, p1, p2, p3):
        """A quad wound as given (CCW from the side it faces)."""
        base = len(self.v)
        for x, y, z in (p0, p1, p2, p3):
            self.v.append(Vertex(x=x, y=y, z=z))
        self.p.append(Polygon(base, base + 1, base + 2, 0, 0))
        self.p.append(Polygon(base, base + 2, base + 3, 0, 0))

    def floor(self, x0, y0, x1, y1, z0, z1=None):
        """Up-facing floor; ``z1`` tilts it along X (z0 at x0, z1 at x1)."""
        z1 = z0 if z1 is None else z1
        self.quad((x0, y0, z0), (x1, y0, z1), (x1, y1, z1), (x0, y1, z0))

    def ceiling(self, x0, y0, x1, y1, z):
        self.quad((x0, y1, z), (x1, y1, z), (x1, y0, z), (x0, y0, z))

    def ter(self):
        t = TerFile(name="bridge")
        t.vertices, t.polygons = self.v, self.p
        return t


def bridge_case(*, gap_from=0.0, gap_to=0.0, to_floor_off=0.0, mid_gap=0.0,
                hump=0.0, hall_height=150.0):
    """Rooms a and b at z=60 either side of a tall hall c (floor 0); a 20 u
    deck at z=60 runs from a's doorway (x=-300) to b's (x=300) through c's
    air. ``gap_from``/``gap_to`` stop the deck short of a door, ``to_floor_off``
    lifts b's floor, ``mid_gap`` cuts the deck over the hall, ``hump`` raises
    a 6 u long piece of deck over the hall by that much (a steep pitch)."""
    spec = ZoneSpec(name="bridge", zone_type="dungeon")
    a = RoomSpec("a", -400, 0, floor_z=DECK_Z, width=200, depth=200, height=80)
    a.role = "entrance"
    c = RoomSpec("c", 0, 0, floor_z=0.0, width=300, depth=300, height=hall_height)
    b = RoomSpec("b", 400, 0, floor_z=DECK_Z + to_floor_off, width=200,
                 depth=200, height=80)
    spec.rooms = [a, c, b]
    spec.corridors = [CorridorSpec("deck", -300, 0, 300, 0, from_z=DECK_Z,
                                   to_z=DECK_Z, width=20, height=30,
                                   from_room="a", to_room="b")]
    spec.safe_point = (-400.0, 0.0, DECK_Z + 5)

    m = _Mesh()
    for r in spec.rooms:
        (x0, y0, z0), (x1, y1, z1) = r.bounds
        m.floor(x0, y0, x1, y1, z0)
        m.ceiling(x0, y0, x1, y1, z1)
    # The deck, in 20 u pieces (as a builder would subdivide it).
    xs = np.arange(-300.0 + gap_from, 300.0 - gap_to + 1e-9, 20.0)
    xs = list(xs) + ([300.0 - gap_to] if xs[-1] < 300.0 - gap_to - 1e-9 else [])
    for x0, x1 in zip(xs, xs[1:]):
        if mid_gap and x0 >= 0.0 and x1 <= mid_gap + 1e-9:
            continue
        if hump and x0 == 0.0:
            # a steep pitch up and back down over 6 u, then flat on top
            m.floor(0.0, -10, 3.0, 10, DECK_Z, DECK_Z + hump)
            m.floor(3.0, -10, 6.0, 10, DECK_Z + hump, DECK_Z)
            m.floor(6.0, -10, x1, 10, DECK_Z)
            continue
        m.floor(x0, -10, x1, 10, DECK_Z)
    return spec, build_walk_surface(m.ter(), AGENT)


def bridge_verdict(spec, surf):
    rooms = {r.id: r for r in spec.rooms}
    cor = spec.corridors[0]
    bridged = T.bridged_rooms(cor, {"c"}, rooms, AGENT)
    mesh = T.check_connector(surf, cor, rooms, AGENT, bridged=bridged)
    cont = T.corridor_continuity(surf, spec, AGENT)[0]
    return bridged, mesh, cont


class TestBridges:
    def test_flush_deck_through_a_halls_air_walks(self):
        bridged, mesh, cont = bridge_verdict(*bridge_case())
        assert bridged == {"c"}
        assert mesh.ok, mesh.reason
        assert cont.connected, cont.reason

    def test_deck_over_a_low_halls_roof_still_crosses(self):
        # A hall whose roof is under the deck by less than the Slab (14 u)
        # isn't bridged and isn't another storey: the deck runs through its
        # roof, so the "crosses room" verdict stands.
        spec, surf = bridge_case(hall_height=50.0)
        bridged, _, cont = bridge_verdict(spec, surf)
        assert bridged == set()
        assert not cont.connected and cont.reason == "crosses room c"

    def test_deck_a_slab_over_a_low_halls_roof_walks(self):
        # 20 u over the roof (>= the Slab): the hall is a storey under the
        # deck (the layout's Slab rule), on any spec. Its ceiling is wound
        # down, so it is no floor for the deck to fall onto.
        spec, surf = bridge_case(hall_height=40.0)
        bridged, _, cont = bridge_verdict(spec, surf)
        assert bridged == set()
        assert cont.connected, cont.reason

    @pytest.mark.parametrize("kw, end", [
        (dict(gap_to=5.0), "(b end)"),
        (dict(gap_from=5.0), "(a end)"),
        (dict(to_floor_off=5.0), "(b end)"),
    ])
    def test_gap_at_bridge_end(self, kw, end):
        bridged, mesh, cont = bridge_verdict(*bridge_case(**kw))
        assert not mesh.ok
        assert classes(mesh.reason, T.BRIDGE_FAILURES) == {"gap at bridge end"}
        assert end in mesh.reason
        assert not cont.connected
        assert classes(cont.reason, T.BRIDGE_FAILURES) == {"gap at bridge end"}

    def test_gap_in_bridge_deck(self):
        _, mesh, cont = bridge_verdict(*bridge_case(mid_gap=20.0))
        assert classes(mesh.reason, T.BRIDGE_FAILURES) == {"gap in bridge deck"}
        assert not cont.connected

    def test_deck_over_the_slope_cap(self):
        # 8 u up over 3 u (~69 deg) and back: not standable.
        _, mesh, cont = bridge_verdict(*bridge_case(hump=8.0))
        assert classes(mesh.reason, T.BRIDGE_FAILURES) == {"bridge deck too steep"}
        assert not cont.connected

    def test_a_gap_within_the_seam_tolerance_walks(self):
        # 1.5 u is inside adjacency_eps (2 u): the walk joins it, as the
        # flood does.
        _, mesh, cont = bridge_verdict(*bridge_case(gap_to=1.5))
        assert mesh.ok, mesh.reason
        assert cont.connected, cont.reason
