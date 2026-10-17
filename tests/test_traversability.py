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

Outdoor/cave are intentionally NOT swept here: their meshes (heightfield
terrain / organic cave) live in a different coordinate frame than the room
graph, so room-footprint mapping isn't meaningful yet. See the task notes.
"""

import math

import pytest

import analyzer.traverse as T
from analyzer.traverse import AgentModel, classify_corridor, validate
from generators.zone_spec import CorridorSpec
from generators.layout import LayoutGenerator
from generators.builder import ZoneBuilder


# ---------------------------------------------------------------------------
# Known seeds (dungeon, box backend)
# ---------------------------------------------------------------------------

# Flat dungeon seeds whose corridors carry no elevation AND connect cleanly on
# the mesh — the no-false-alarm bar. If one of these starts failing, either the
# validator regressed or the box backend broke a previously-good flat zone.
KNOWN_GOOD_DUNGEON = [1, 6, 26, 49]

# Elevation-/same-axis-heavy seeds that are genuinely broken today (cliff ramps,
# oversized stair steps, or misaligned openings). These SHOULD fail until
# tasks/corridor-connection.md lands; kept as xfail so the suite stays green but
# the day they're fixed, xfail → xpass flags it loudly (strict=False so an
# incidental pass doesn't error the run).
KNOWN_BAD_DUNGEON = [1955208177, 1516796975, 481893615]


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

class TestKnownBadDungeons:
    @pytest.mark.parametrize("seed", KNOWN_BAD_DUNGEON)
    @pytest.mark.xfail(
        reason="Elevation/same-axis corridor bugs (tasks/corridor-connection.md). "
               "Flips to xpass once those land — then drop the xfail.",
        strict=False,
    )
    def test_fully_reachable(self, seed, tmp_path):
        rep = _build_and_validate("dungeon", seed, rooms=8, tmp_path=tmp_path)
        assert rep.passed, rep.summary()

    def test_validator_flags_the_breakage(self, tmp_path):
        # The positive assertion: on a known-bad seed the validator MUST report a
        # failure AND name a concrete cause (so it's trustworthy, not just red).
        rep = _build_and_validate("dungeon", 1955208177, rooms=8, tmp_path=tmp_path)
        assert not rep.passed
        assert rep.reachable_rooms < rep.total_rooms
        unreachable = [r for r in rep.rooms if not r.reachable]
        assert unreachable, "expected at least one unreachable room"
        # Every unreachable room gets a non-empty diagnosis.
        assert all(r.reason for r in unreachable)
        # At least one failure is a walkability cause (cliff ramp / oversized
        # step) — the exact class the structural tests miss.
        joined = " ".join(r.reason for r in unreachable)
        assert ("step-up" in joined or "cliff ramp" in joined
                or "walkable cap" in joined), joined
