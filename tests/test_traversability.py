"""
tests/test_traversability.py
----------------------------
Regression suite for the mesh-based traversability validator
(``analyzer.traverse``). Guards the "every room is reachable on foot" MUST so
it's caught here, not by a human walking the zone in the viewer.

Scope: the **box backend (dungeon theme)** — that's where navigability is the
north-star and where every known corridor bug lives. The validator walks the
real generated TER mesh from the safe point and maps each room's floor
footprint onto the reachable set.

Three groups:
  * agent model / corridor classifier unit tests (fast, no build)
  * known-GOOD flat dungeon seeds → full reachability (the no-false-alarm bar)
  * known-BAD elevation/same-axis seeds → xfail until ``corridor-connection``
    lands (then they flip green and we drop the xfail)

Outdoor is intentionally NOT swept here: its mesh (heightfield terrain) lives
in a different coordinate frame than the room graph, so room-footprint mapping
isn't meaningful yet. See the task notes.
"""

import math

import pytest

import analyzer.traverse as T
from analyzer.traverse import AgentModel, build_walk_surface, classify_corridor, validate
from core.ter import Polygon, TerFile, Vertex
from generators.zone_spec import CorridorSpec, RoomSpec, ZoneSpec
from generators.layout import LayoutGenerator
from generators.builder import ZoneBuilder


# ---------------------------------------------------------------------------
# Known seeds (dungeon, box backend)
# ---------------------------------------------------------------------------

# Flat dungeon seeds whose corridors carry no elevation AND connect cleanly on
# the mesh — the no-false-alarm bar. If one of these starts failing, either the
# validator regressed or the box backend broke a previously-good flat zone.
KNOWN_GOOD_DUNGEON = [1, 6, 26, 49]

# Elevation-/same-axis-heavy seeds that USED to be broken (cliff ramps,
# oversized stair steps, or misaligned openings on same-axis room pairs). Since
# tasks/corridor-connection.md landed they connect cleanly and walk end to end,
# so they are now a regression guard: if one starts failing again, the
# same-axis Z-corridor routing or the elevation-grade cap regressed.
FORMERLY_BROKEN_DUNGEON = [1955208177, 1516796975, 481893615, 678358326]


def _build_and_validate(theme: str, seed: int, rooms: int, tmp_path):
    spec = LayoutGenerator(theme=theme, seed=seed).generate("trav", room_count=rooms)
    result = ZoneBuilder(spec).build(output_dir=str(tmp_path), write_glb=False)
    return validate(result.eqg_path, spec=spec)


# ---------------------------------------------------------------------------
# Unit: agent model + corridor classifier (the "why" oracle)
# ---------------------------------------------------------------------------

class TestAgentModel:
    def test_slope_cap_to_normal(self):
        a = AgentModel(walkable_slope_deg=40.0)
        # cos(40deg) ~= 0.766 — a face normal flatter than this is standable
        assert math.isclose(a.min_up_normal, math.cos(math.radians(40)), rel_tol=1e-6)

    def test_defaults_are_eq_scale(self):
        a = AgentModel()
        assert a.player_height == pytest.approx(6.0)
        assert 0 < a.max_step_up < a.player_height


class TestCorridorClassifier:
    def _corr(self, dz, run=100.0, steps=0):
        return CorridorSpec("c", 0, 0, run, 0, from_z=0.0, to_z=dz, steps=steps)

    def test_flat_is_walkable(self):
        ok, why = classify_corridor(self._corr(0.0), AgentModel())
        assert ok and why == "flat"

    def test_cliff_ramp_flagged(self):
        # 66u rise over 50u run ~= 53deg — the classic cliff ramp
        ok, why = classify_corridor(
            CorridorSpec("c", 0, 0, 50, 0, from_z=0, to_z=66, steps=0), AgentModel()
        )
        assert not ok
        assert "cliff ramp" in why and "53deg" in why

    def test_oversized_stair_flagged(self):
        # 75u over 5 steps = 15u/step — far above the step-up
        ok, why = classify_corridor(
            CorridorSpec("c", 0, 0, 100, 0, from_z=0, to_z=75, steps=5), AgentModel()
        )
        assert not ok
        assert "step" in why and "15.0u" in why

    def test_gentle_ramp_ok(self):
        ok, _ = classify_corridor(self._corr(30.0, run=200.0), AgentModel())
        assert ok

    def test_short_stairs_ok(self):
        ok, _ = classify_corridor(self._corr(12.0, run=100.0, steps=6), AgentModel())
        assert ok


# ---------------------------------------------------------------------------
# Integration: known-good flat dungeons must be fully reachable
# ---------------------------------------------------------------------------

class TestKnownGoodDungeons:
    @pytest.mark.parametrize("seed", KNOWN_GOOD_DUNGEON)
    def test_all_rooms_reachable(self, seed, tmp_path):
        rep = _build_and_validate("dungeon", seed, rooms=5, tmp_path=tmp_path)
        assert rep.passed, (
            f"seed {seed} should be fully traversable:\n{rep.summary()}"
        )
        # Every room individually confirmed reachable with real reached faces.
        for r in rep.rooms:
            assert r.reachable, f"{r.room_id} unreachable: {r.reason}"
            assert r.reached_faces > 0

    def test_entrance_is_always_reachable(self, tmp_path):
        # The safe point sits in the entrance room, so it must always reach it
        # (a floor the camera stands on — ACCEPTANCE A "lands on the floor").
        rep = _build_and_validate("dungeon", 1, rooms=5, tmp_path=tmp_path)
        entrance = [r for r in rep.rooms if r.role == "entrance"]
        assert entrance, "no entrance room in spec"
        assert entrance[0].reachable


# ---------------------------------------------------------------------------
# Integration: known-bad seeds — flagged (xfail until corridor-connection)
# ---------------------------------------------------------------------------

class TestFormerlyBrokenDungeons:
    """
    The seeds that drove tasks/corridor-connection.md. They must now walk end to
    end on the real mesh — the regression bar that the same-axis Z-corridor
    routing and the elevation-grade cap stay fixed.
    """

    @pytest.mark.parametrize("seed", FORMERLY_BROKEN_DUNGEON)
    def test_fully_reachable(self, seed, tmp_path):
        rep = _build_and_validate("dungeon", seed, rooms=9, tmp_path=tmp_path)
        assert rep.passed, rep.summary()


class TestValidatorFlagsBreakage:
    def _cliff_spec(self):
        # Hand-built, deterministically-broken zone: two rooms joined by a
        # single over-steep ramp (150u rise over a ~100u run ≈ 56°). The ramp
        # is unstandable (slope > the agent's 40° cap), so the far room is
        # unreachable and the corridor classifier names it a cliff ramp. This
        # replaces the old "known-bad seed" now that no seed is reliably broken.
        spec = ZoneSpec(name="trav", theme="dungeon")
        a = RoomSpec("a", center_x=0, center_y=0, floor_z=0.0,
                     width=200, depth=200, height=100)
        a.role = "entrance"
        a.open_walls = ["N"]
        b = RoomSpec("b", center_x=0, center_y=300, floor_z=150.0,
                     width=200, depth=200, height=100)
        b.open_walls = ["S"]
        spec.rooms = [a, b]
        spec.corridors.append(CorridorSpec(
            "corr_0", from_x=0, from_y=100, to_x=0, to_y=200,
            from_z=0.0, to_z=150.0, width=50, height=90,
            from_room="a", to_room="b"))
        spec.safe_point = (0.0, 0.0, 5.0)
        return spec

    def test_validator_flags_the_breakage(self, tmp_path):
        # The validator MUST report a failure AND name a concrete walkability
        # cause (so it's trustworthy, not just red).
        spec = self._cliff_spec()
        result = ZoneBuilder(spec).build(output_dir=str(tmp_path), write_glb=False)
        rep = validate(result.eqg_path, spec=spec)
        assert not rep.passed
        assert rep.reachable_rooms < rep.total_rooms
        unreachable = [r for r in rep.rooms if not r.reachable]
        assert unreachable, "expected at least one unreachable room"
        assert all(r.reason for r in unreachable)
        # The failure names a walkability cause — the class structural tests miss.
        joined = " ".join(r.reason for r in unreachable)
        assert ("step-up" in joined or "cliff ramp" in joined
                or "walkable cap" in joined), joined


# ---------------------------------------------------------------------------
# Unit: footprint-contact adjacency soundness (the false-PASS this fix removes)
# ---------------------------------------------------------------------------

class TestFootprintContactAdjacency:
    """
    Direct guard on ``build_walk_surface``'s footprint-proximity pass. The bug
    this fixes was a false PASS: two individually-standable (near-flat) floor
    faces were wired together whenever their XY BOUNDING BOXES came within
    ``adjacency_eps`` on each axis independently AND their CENTROID Z values were
    within ``max_step_up`` -- neither of which requires the faces to actually
    meet in 3D. The flood fill then teleported across a real gap.

    These build tiny synthetic TER meshes with NO shared vertices (so only the
    footprint pass can connect them) and assert the pass connects two faces only
    when their floors genuinely meet. Without the true-contact + Z-at-contact
    fix, cases 1 and 2 would be (wrongly) adjacent.
    """

    @staticmethod
    def _tri(p0, p1, p2, base_index):
        """One flat, upward (standable) triangle from three (x, y, z) points.
        CCW winding in XY gives a +Z normal so the face is standable. Returns
        (verts, polys) with vertex indices starting at ``base_index``."""
        vs = [Vertex(*p0), Vertex(*p1), Vertex(*p2)]
        i = base_index
        return vs, [Polygon(i + 0, i + 1, i + 2)]

    def _surface(self, tris):
        """Build a WalkSurface from a list of triangles, each ((x,y,z) x3), each
        a separate island (no vertices shared BETWEEN triangles, so ONLY the
        footprint-contact pass can ever connect them)."""
        ter = TerFile(name="synthetic")
        for (p0, p1, p2) in tris:
            base = len(ter.vertices)
            vs, ps = self._tri(p0, p1, p2, base)
            ter.vertices.extend(vs)
            ter.polygons.extend(ps)
        return build_walk_surface(ter, AgentModel())

    def test_bbox_overlaps_both_axes_but_triangles_dont_touch_is_not_adjacent(self):
        # The exact shape of the real false bridge (faces 2642<->132 on the
        # 30-room seed), reduced to two triangles. Their XY BOUNDING BOXES
        # overlap on BOTH axes -- so the OLD per-axis bbox test (and the OLD
        # centroid-Z gate, since both are flat at z=0) WOULD wrongly bridge them
        # -- yet the triangles themselves are ~27u apart in XY and never meet.
        # The true-contact test must reject them.
        #   A bbox: x[549.6,658.9] y[-998.7,-949.6]
        #   B bbox: x[656.9,761.0] y[-1050.7,-897.6]  -> overlaps A on both axes
        a = (549.6, -998.7, 0.0), (658.9, -998.7, 0.0), (658.9, -949.6, 0.0)
        b = (656.9, -1050.7, 0.0), (761.0, -1050.7, 0.0), (761.0, -897.6, 0.0)
        surf = self._surface([a, b])
        assert 1 not in surf.adjacency.get(0, []), (
            "triangles whose bboxes overlap on both axes but which are ~27u "
            "apart in XY must NOT be adjacent (the real false-bridge shape)"
        )

    def test_stacked_overlap_beyond_step_up_is_not_adjacent(self):
        # Two triangles with the SAME XY footprint stacked 20u apart in Z
        # (>> the 3u step-up): a floor and a surface passing overhead. Must not
        # connect.
        pts = (0.0, 0.0), (100.0, 0.0), (0.0, 100.0)
        a = tuple((x, y, 0.0) for (x, y) in pts)
        b = tuple((x, y, 20.0) for (x, y) in pts)
        surf = self._surface([a, b])
        assert 1 not in surf.adjacency.get(0, []), (
            "triangles stacked 20u apart in Z must not be adjacent"
        )

    def test_z_measured_at_contact_not_centroid(self):
        # The discriminating case for the Z-at-contact change. A flat floor at
        # z=0 (x[0,100]) and a standable ramp (10 deg) overlapping it near x=100.
        # The ramp's CENTROID z is 2.73u (< the 3u step-up) -- so the OLD gate,
        # which compared centroids, would WRONGLY bridge them -- but the floors'
        # heights AT THE CONTACT POINT (x=100) differ by 5.71u (> step-up), so
        # the new Z-at-contact test correctly refuses the connection. This is a
        # floor and a ramp crossing overhead: not walkable between.
        floor = (0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (0.0, 100.0, 0.0)
        ramp = (95.0, 0.0, 6.6), (160.0, 0.0, -5.0), (95.0, 100.0, 6.6)
        surf = self._surface([floor, ramp])
        # Both must be standable for this to exercise the adjacency pass at all.
        assert bool(surf.standable[0]) and bool(surf.standable[1])
        assert 1 not in surf.adjacency.get(0, []), (
            "floor and overhead ramp (centroids close, contact 5.7u apart) "
            "must not be adjacent -- Z must be measured at the contact, not "
            "at the centroids"
        )

    def test_genuine_edge_touch_same_height_is_adjacent(self):
        # Positive control: two coplanar triangles whose edges abut within eps
        # at the same Z -- a real flush walkable seam. Must stay connected; the
        # fix must not over-tighten and disconnect continuous floor.
        a = (0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (0.0, 100.0, 0.0)
        b = (100.5, 0.0, 0.0), (100.5, 100.0, 0.0), (200.0, 0.0, 0.0)
        surf = self._surface([a, b])
        assert 1 in surf.adjacency.get(0, []), (
            "coplanar triangles touching within eps must stay adjacent"
        )

    def test_overlap_small_step_within_cap_is_adjacent(self):
        # Overlapping footprints whose floor heights at the contact differ by
        # 2.5u (< the 3u step-up): a climbable seam. Must connect.
        a = (0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (0.0, 100.0, 0.0)
        b = (50.0, 0.0, 2.5), (100.0, 50.0, 2.5), (50.0, 100.0, 2.5)
        surf = self._surface([a, b])
        assert 1 in surf.adjacency.get(0, []), (
            "overlapping triangles within the step-up at the contact must be adjacent"
        )
