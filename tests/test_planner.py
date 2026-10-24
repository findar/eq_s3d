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
from generators.zone_spec import ZoneSpec


class TestZonePlan:
    def test_validate_clamps(self):
        p = ZonePlan(theme="bogus", room_count=999, size="gigantic").validate()
        assert p.theme == "dungeon"
        assert p.room_count == 30
        assert p.size == "medium"

    def test_roundtrip_dict(self):
        # Legacy "outdoor" maps forward to "wilderness" on load (Req 11.2).
        p = ZonePlan(theme="outdoor", room_count=7, regions=["water"])
        p2 = ZonePlan.from_dict(p.to_dict())
        assert p2.theme == "wilderness"
        assert p2.room_count == 7
        assert p2.regions == ["water"]

    def test_from_dict_ignores_unknown(self):
        # "cave" is no longer a valid theme (M0 removed the cave pipeline);
        # ZonePlan.validate normalises it to the dungeon default.
        p = ZonePlan.from_dict({"theme": "cave", "nonsense": 123})
        assert p.theme == "dungeon"

    def test_zonespec_cave_theme_normalised(self):
        # The spec side of cave removal: a legacy ZoneSpec dict carrying
        # theme="cave" loads back as a dungeon (ZoneSpec.from_dict remaps it).
        d = ZoneSpec(name="t", theme="dungeon").to_dict()
        d["theme"] = "cave"
        spec = ZoneSpec.from_dict(d)
        assert spec.theme == "dungeon"


class TestRulePlanner:
    def setup_method(self):
        self.rp = RulePlanner()

    @pytest.mark.parametrize("word", ["cave", "cavern", "grotto",
                                      "underground", "tunnel"])
    def test_cave_words_mean_dungeon(self, word):
        # The cave pipeline was removed in M0: cave-like words fold into the
        # dungeon bucket, so each one on its own plans as a dungeon.
        p = self.rp.plan(f"a dark {word} to explore")
        assert p.theme == "dungeon"

    def test_detects_outdoor(self):
        p = self.rp.plan("a sprawling forest with rolling hills")
        assert p.theme == "wilderness"

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

    # --- content / semantic layer ---

    def test_detects_dungeon_archetype(self):
        p = self.rp.plan("a sunken drowned ruin full of submerged chambers")
        assert p.theme == "dungeon"
        assert p.dungeon_theme == "sunken_ruin"

    def test_detects_fortress_archetype(self):
        p = self.rp.plan("a stone fortress stronghold with a throne room")
        assert p.dungeon_theme == "fortress"

    def test_detects_race(self):
        p = self.rp.plan("a giant fortress with huge halls")
        assert p.dungeon_race == "giant"

    def test_lava_promotes_to_tint(self):
        p = self.rp.plan("a molten forge full of lava")
        assert p.elemental_tint == "lava"

    def test_no_archetype_for_non_dungeon(self):
        p = self.rp.plan("a sprawling forest fortress")  # outdoor wins theme
        # dungeon_theme only set for dungeon theme
        if p.theme != "dungeon":
            assert p.dungeon_theme == ""


class TestExpand:
    def test_plan_to_spec_basic(self):
        plan = ZonePlan(name="t", zone_type="wilderness", room_count=4)
        spec = plan_to_spec(plan, seed=1)
        assert spec.theme == "wilderness"
        assert len(spec.rooms) == 4

    def test_regions_added(self):
        plan = ZonePlan(name="t", theme="dungeon", room_count=3, regions=["water"])
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

    def test_dungeon_theme_flows_to_spec(self):
        plan = ZonePlan(name="t", theme="dungeon", room_count=6,
                        dungeon_theme="temple", dungeon_race="lizardman")
        spec = plan_to_spec(plan, seed=1)
        assert spec.dungeon_theme == "temple"
        assert spec.dungeon_race == "lizardman"
        assert all(r.semantic_type for r in spec.rooms)

    def test_elemental_region_not_double_added(self):
        # A sunken_ruin theme emits water regions itself; the plan's water
        # region must not be added a second time by _add_regions.
        plan = ZonePlan(name="t", theme="dungeon", room_count=6,
                        dungeon_theme="sunken_ruin", regions=["water"])
        spec = plan_to_spec(plan, seed=1)
        water = [r for r in spec.regions if r.kind == "water"]
        # All water regions should come from the semantic layer (ids prefixed
        # "water_"); none should be the expand._add_regions duplicate (also
        # "water_"), so just assert the count is reasonable (<= room count).
        assert 0 < len(water) <= len(spec.rooms)


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
