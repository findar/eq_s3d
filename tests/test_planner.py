"""
tests/test_planner.py
---------------------
Tests for the prompt planner (rule-based default + LLM abstraction) and the
plan → ZoneSpec expansion.
"""

import pytest

from ai.schema import ZonePlan, VALID_THEMES
from ai.rule_planner import RulePlanner
from ai.llm_planner import LLMPlanner
from ai.expand import plan_to_spec
from ai.planner import make_plan, plan_zone, get_planner
from ai import planner as planner_mod


class TestZonePlan:
    def test_validate_clamps(self):
        p = ZonePlan(theme="bogus", room_count=999, size="gigantic").validate()
        assert p.theme == "dungeon"
        assert p.room_count == 30
        assert p.size == "medium"

    def test_roundtrip_dict(self):
        p = ZonePlan(theme="cave", room_count=7, regions=["water"])
        p2 = ZonePlan.from_dict(p.to_dict())
        assert p2.theme == "cave"
        assert p2.room_count == 7
        assert p2.regions == ["water"]

    def test_from_dict_ignores_unknown(self):
        p = ZonePlan.from_dict({"theme": "cave", "nonsense": 123})
        assert p.theme == "cave"


class TestRulePlanner:
    def setup_method(self):
        self.rp = RulePlanner()

    def test_detects_cave(self):
        p = self.rp.plan("a dark underground cavern")
        assert p.theme == "cave"

    def test_detects_outdoor(self):
        p = self.rp.plan("a sprawling forest with rolling hills")
        assert p.theme == "outdoor"

    def test_detects_water_region(self):
        p = self.rp.plan("a flooded cave with a lake")
        assert "water" in p.regions

    def test_detects_lava_region(self):
        p = self.rp.plan("a volcanic dungeon full of molten lava")
        assert "lava" in p.regions

    def test_size_from_keyword(self):
        assert self.rp.plan("a huge cavern").size == "huge"
        assert self.rp.plan("a tiny crypt").size == "small"

    def test_explicit_room_count_digits(self):
        assert self.rp.plan("a dungeon with 7 rooms").room_count == 7

    def test_explicit_room_count_words(self):
        assert self.rp.plan("a cave with three chambers").room_count == 3

    def test_many_increases_rooms(self):
        few = self.rp.plan("a cave")
        many = self.rp.plan("a cave with many chambers")
        assert many.room_count > few.room_count

    def test_dramatic_verticality(self):
        p = self.rp.plan("a towering multi-level temple")
        assert p.verticality == "dramatic"

    def test_mood_extracted(self):
        p = self.rp.plan("a dark damp mossy cave")
        assert "dark" in p.mood


class TestExpand:
    def test_plan_to_spec_basic(self):
        plan = ZonePlan(name="t", theme="cave", room_count=4)
        spec = plan_to_spec(plan, seed=1)
        assert spec.theme == "cave"
        assert len(spec.rooms) == 4

    def test_regions_added(self):
        plan = ZonePlan(name="t", theme="cave", room_count=3, regions=["water"])
        spec = plan_to_spec(plan, seed=1)
        assert any(r.kind == "water" for r in spec.regions)

    def test_mood_folds_into_materials(self):
        plan = ZonePlan(name="t", theme="dungeon", room_count=2, mood="dark, mossy")
        spec = plan_to_spec(plan, seed=1)
        assert any("mossy" in m.description for m in spec.materials.values())

    def test_flat_verticality_no_elevation(self):
        plan = ZonePlan(name="t", theme="dungeon", room_count=5,
                        verticality="flat", elevation=True)
        spec = plan_to_spec(plan, seed=1)
        floor_zs = {r.floor_z for r in spec.rooms}
        assert floor_zs == {0.0}


class TestPlannerFactory:
    def teardown_method(self):
        planner_mod.set_planner(None)

    def test_default_is_rule_without_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("EQ_S3D_PLANNER", raising=False)
        planner_mod.set_planner(None)
        assert get_planner().name == "rule"

    def test_override_forces_rule(self, monkeypatch):
        monkeypatch.setenv("EQ_S3D_PLANNER", "rule")
        planner_mod.set_planner(None)
        assert get_planner().name == "rule"

    def test_make_plan_returns_valid(self):
        p = make_plan("a big flooded cave", name="z")
        assert p.theme in VALID_THEMES
        assert p.name == "z"

    def test_plan_zone_full_pipeline(self):
        plan, spec = plan_zone("a small frozen dungeon", name="z", seed=1)
        assert plan.theme == "dungeon"
        assert spec.theme == "dungeon"
        assert len(spec.rooms) == plan.room_count


class TestLLMPlanner:
    def test_unavailable_without_keys(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert LLMPlanner().available() is False

    def test_available_with_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        assert LLMPlanner().available() is True
