"""
tests/test_wilderness_biome.py
------------------------------
Biome resolution for the wilderness generator (Requirement 1).

Covers task 2.1: a plains/Karana prompt resolves to the `plains` biome through
the existing planner seam, zero-key; out-of-set biomes fall back to `plains`
and record the substitution on the intent object. The matrix-level property
suite (Property 17) lands in wave 1's task 3; these are the targeted unit
checks for the resolver itself.
"""

import pytest

from ai import planner as planner_mod
from ai.rule_planner import RulePlanner
from generators.wilderness.biome_resolve import (
    DEFAULT_BIOME,
    V1_BIOMES,
    BiomeSubstitution,
    WildernessIntent,
    resolve_biome,
    resolve_wilderness_intent,
)


class TestRulePlannerRoutesPlains:
    """A plains/Karana prompt routes to the wilderness zone type (Req 1.1)."""

    def setup_method(self):
        self.rp = RulePlanner()

    @pytest.mark.parametrize("prompt", [
        "an open plains zone",
        "the north karana steppe",
        "a rolling grassland under open sky",
        "the karanas, wide open prairie",
        "a windswept savanna",
    ])
    def test_plains_wording_is_wilderness(self, prompt):
        assert self.rp.plan(prompt).zone_type == "wilderness"


class TestResolveBiome:
    """resolve_biome over a validated plan (Req 1.1, 1.4)."""

    def _plan(self, prompt):
        return RulePlanner().plan(prompt)

    def test_plains_prompt_resolves_plains(self):
        intent = resolve_biome(self._plan("an open plains karana"))
        assert intent.biome == "plains"
        assert intent.substituted is False
        assert intent.substitution is None

    def test_karana_prompt_resolves_plains(self):
        intent = resolve_biome(self._plan("the west karana, open fields"))
        assert intent.biome == "plains"
        assert intent.requested_biome == "plains"

    def test_no_biome_named_defaults_plains_no_substitution(self):
        # A wilderness prompt with no biome word still resolves to plains, but
        # nothing was swapped away, so there is no substitution record.
        intent = resolve_biome(self._plan("a wide open wilderness zone"))
        assert intent.biome == DEFAULT_BIOME
        assert intent.substituted is False

    @pytest.mark.parametrize("prompt,requested", [
        ("a scorching desert of endless dunes", "desert"),
        ("a dense forest of towering woods", "forest"),
        ("a windy coast with a long shoreline", "coast"),
        ("a frozen tundra permafrost", "tundra"),
    ])
    def test_out_of_set_biome_falls_back_and_records(self, prompt, requested):
        # Req 1.4: an out-of-set biome resolves to plains AND records the
        # requested-vs-resolved substitution on the intent object.
        intent = resolve_biome(self._plan(prompt))
        assert intent.biome == DEFAULT_BIOME
        assert intent.requested_biome == requested
        assert intent.substituted is True
        assert intent.substitution == BiomeSubstitution(
            requested=requested, resolved=DEFAULT_BIOME
        )

    def test_resolved_biome_always_in_v1_set(self):
        for prompt in ["karana", "desert", "forest", "nothing here"]:
            assert resolve_biome(self._plan(prompt)).biome in V1_BIOMES

    def test_sidecar_record_shape(self):
        plain = resolve_biome(self._plan("open plains"))
        assert plain.sidecar_record() == {"biome": "plains"}

        swapped = resolve_biome(self._plan("a desert of dunes"))
        rec = swapped.sidecar_record()
        assert rec["biome"] == "plains"
        assert rec["substitution"] == {"requested": "desert", "resolved": "plains"}


class TestResolveThroughPlannerSeam:
    """resolve_wilderness_intent goes through make_plan (Req 1.2, 1.3)."""

    def teardown_method(self):
        planner_mod.set_planner(None)

    def test_zero_key_rule_planner_resolves_plains(self, monkeypatch):
        # Req 1.2: zero-key, no external service. Force the rule planner and
        # confirm a plains prompt resolves without any API key configured.
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("EQ_S3D_PLANNER", "rule")
        planner_mod.set_planner(None)
        intent = resolve_wilderness_intent("an open karana plains", name="z")
        assert isinstance(intent, WildernessIntent)
        assert intent.biome == "plains"

    def test_llm_proposed_plan_flows_through_seam(self, monkeypatch):
        # Req 1.3: an LLM-proposed plan reaches biome resolution through the
        # same make_plan drop-in. We inject a fake "llm" planner that proposes
        # a wilderness plan whose prompt names a desert; resolution then falls
        # back to plains and records the substitution — exercising the seam,
        # not the provider.
        class FakeLLM:
            name = "llm"

            def available(self):
                return True

            def plan(self, prompt, name="zone", style_hint=""):
                from ai.schema import ZonePlan
                return ZonePlan(name=name, zone_type="wilderness",
                                prompt=prompt).validate()

        planner_mod.set_planner(FakeLLM())
        intent = resolve_wilderness_intent("a desert of endless dunes", name="z")
        assert intent.biome == "plains"
        assert intent.substituted is True
        assert intent.requested_biome == "desert"
