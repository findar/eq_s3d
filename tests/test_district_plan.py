"""Districts in the plan and the prompt (districts spec task 4, Req 4.1, 4.2, A2)."""

from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from ai.expand import layout_proposals, plan_to_spec
from ai.llm_planner import system_prompt
from ai.rule_planner import RulePlanner, _ARCHETYPE_WORDS, _ZONE_TYPE_WORDS, match_districts
from ai.schema import (
    VALID_DISTRICT_RELATIONSHIPS, VALID_DUNGEON_THEMES, ZONE_PLAN_JSON_SCHEMA, ZonePlan,
)
from generators import districts as gd
from generators import semantics
from .pbt_helpers import scaled


def _purposes(plan):
    return [p["purpose"] for p in plan.district_plan]


# --- The plan's fields ---------------------------------------------------------

def test_vocabularies_match_the_generators():
    assert VALID_DISTRICT_RELATIONSHIPS == list(gd.RELATIONSHIPS)
    assert set(VALID_DUNGEON_THEMES) == set(semantics.ARCHETYPES)


def test_round_trip():
    plan = ZonePlan(districts=True, district_plan=["temple", {"purpose": "tomb"}],
                    district_relationship="abandoned_vs_active").validate()
    d = plan.to_dict()
    assert d["districts"] is True
    assert d["district_plan"] == [{"purpose": "temple"}, {"purpose": "tomb"}]
    assert d["district_relationship"] == "abandoned_vs_active"
    for load in (ZonePlan.from_dict, ZonePlan.from_saved):
        back = load(d)
        assert (back.districts, back.district_plan, back.district_relationship) == \
            (plan.districts, plan.district_plan, plan.district_relationship)


def test_a_saved_plan_without_them_loads_off():
    d = ZonePlan(room_count=12, dungeon_theme="temple").validate().to_dict()
    assert not {"districts", "district_plan", "district_relationship"} & set(d)
    back = ZonePlan.from_saved(d)
    assert (back.districts, back.district_plan, back.district_relationship) == (False, [], "")


def test_unknown_values_are_kept_out_with_a_note():
    notes = []
    plan = ZonePlan.from_dict({"districts": "true",
                               "district_plan": ["Temple", {"purpose": "bogus"}, 7, "tomb"],
                               "district_relationship": "allied"}, notes)
    assert plan.districts is True
    assert _purposes(plan) == ["temple", "", ""]
    assert plan.district_relationship == ""
    assert notes == ["district_purpose_unknown: 'bogus' ignored (District 1)",
                     "district_purpose_unknown: 7 ignored (District 2)",
                     "district_plan_truncated: 4 proposed, the first 3 kept",
                     "district_relationship_unknown: 'allied' ignored, using sequential"]
    with pytest.raises(ValueError):
        ZonePlan(district_plan="temple").validate()


def test_pinned_purpose():
    assert ZonePlan(district_plan=["tomb", "tomb"]).validate().pinned_purpose() == "tomb"
    assert ZonePlan(district_plan=["tomb"]).validate().pinned_purpose() == ""
    assert ZonePlan(district_plan=["tomb", ""]).validate().pinned_purpose() == ""
    assert ZonePlan(district_plan=["tomb", "temple"]).validate().pinned_purpose() == ""


# --- plan_to_spec ------------------------------------------------------------

def _dungeon(**kw):
    base = dict(name="d", zone_type="dungeon", room_count=12, layout="classic", districts=True)
    base.update(kw)
    return ZonePlan(**base).validate()


def test_a_districted_dungeon_takes_its_proposals():
    notes = []
    spec = plan_to_spec(_dungeon(district_plan=["temple", "tomb"],
                                 district_relationship="abandoned_vs_active"),
                        seed=11, warnings=notes)
    assert [d.purpose for d in spec.districts] == ["temple", "tomb"]
    assert {d.relationship for d in spec.districts} == {"abandoned_vs_active"}
    assert not any(n.startswith("districts_ignored") for n in notes)


def test_the_switch_off_changes_nothing():
    plain = plan_to_spec(ZonePlan(name="d", zone_type="dungeon", room_count=12,
                                  layout="classic").validate(), seed=11)
    off = plan_to_spec(_dungeon(districts=False, district_plan=["tomb"]), seed=11)
    assert off.to_dict() == plain.to_dict()
    assert not off.districts


@pytest.mark.parametrize("zone_type", ["city", "wilderness"])
def test_other_zone_types_ignore_it_with_a_note(zone_type):
    notes = []
    plan = ZonePlan(name="z", zone_type=zone_type, room_count=12, districts=True).validate()
    spec = plan_to_spec(plan, seed=5, warnings=notes)
    assert plan.districts is True            # kept on the plan
    assert not spec.districts
    assert any(n.startswith("districts_ignored:") for n in notes)


def test_a_pinned_plan_gives_every_district_its_purpose():
    notes = []
    spec = plan_to_spec(_dungeon(room_count=16, district_plan=["mine_delve", "mine_delve"]),
                        seed=3, warnings=notes)
    assert len(spec.districts) >= 2
    assert {d.purpose for d in spec.districts} == {"mine_delve"}
    assert "district_purpose_pinned: every District is mine_delve" in notes


def test_too_few_rooms_is_noted():
    notes = []
    spec = plan_to_spec(_dungeon(room_count=5), seed=3, warnings=notes)
    assert not spec.districts
    assert any(n.startswith("districts_too_few_rooms:") for n in notes)


def test_open_proposals_before_a_named_one_are_filled():
    plan = _dungeon(district_plan=["", "tomb", ""], district_relationship="factional")
    out = [p["purpose"] for p in layout_proposals(plan, 7)]
    assert out[1] == "tomb" and len(out) == 2           # the trailing open one is the layout's
    assert out[0] in gd.CONTRASTS["tomb"]
    themed = _dungeon(dungeon_theme="fortress", district_plan=["", "tomb"])
    assert [p["purpose"] for p in layout_proposals(themed, 7)] == ["fortress", "tomb"]
    assert layout_proposals(_dungeon(district_plan=["", ""]), 7) == []


# --- The rule planner ---------------------------------------------------------

@pytest.mark.parametrize("prompt, theme, purposes, relationship, rooms", [
    ("a temple fallen to the dead", "temple", ["temple", "tomb"], "abandoned_vs_active", 8),
    ("two factions of goblins", "", ["", ""], "factional", 8),
    ("the upper and lower mines", "mine_delve", ["mine_delve", "mine_delve"], "sequential", 8),
    ("three warring clans in a fortress", "fortress", ["fortress", "", ""], "factional", 14),
    ("a keep overrun by kobolds", "fortress", ["fortress", "warren"], "abandoned_vs_active", 8),
    ("a crypt of the living and the dead", "tomb", ["", "tomb"], "factional", 8),
    ("a temple fallen to the dead with 5 rooms", "temple", ["temple", "tomb"],
     "abandoned_vs_active", 5),
])
def test_contrasting_area_phrases(prompt, theme, purposes, relationship, rooms):
    plan = RulePlanner().plan(prompt)
    assert plan.zone_type == "dungeon"
    assert plan.dungeon_theme == theme
    assert plan.districts is True
    assert _purposes(plan) == purposes
    assert plan.district_relationship == relationship
    assert plan.room_count == rooms


def test_the_upper_and_lower_mines_pin_their_purpose():
    assert RulePlanner().plan("the upper and lower mines").pinned_purpose() == "mine_delve"


@pytest.mark.parametrize("prompt", ["a dark damp cave", "a temple to the dead",
                                    "a big fortress with many halls", "a sprawling forest"])
def test_no_phrase_leaves_them_off(prompt):
    plan = RulePlanner().plan(prompt)
    assert (plan.districts, plan.district_plan, plan.district_relationship) == (False, [], "")
    assert match_districts(prompt.lower()) is None


_PHRASES = ["the living and the dead", "two factions", "three rival clans",
            "upper and lower", "upper, middle and lower", "fallen to the dead",
            "overrun by kobolds", "old and new", "lost to the shadows"]
_WORDS = sorted({w for ws in _ZONE_TYPE_WORDS.values() for w in ws}
                | {w for ws in _ARCHETYPE_WORDS.values() for w in ws}
                | {"a", "the", "dark", "with", "of", "huge", "small", "rooms"})


@settings(deadline=None, max_examples=scaled(100))
@given(words=st.lists(st.sampled_from(_WORDS), max_size=6), phrase=st.sampled_from(_PHRASES))
def test_a_phrase_never_moves_the_zone_type_or_the_theme(words, phrase):
    base = " ".join(words)
    plain, phrased = RulePlanner().plan(base), RulePlanner().plan(f"{base} {phrase}")
    assert phrased.zone_type == plain.zone_type
    assert phrased.dungeon_theme == plain.dungeon_theme
    assert phrased.districts and not plain.districts
    assert 2 <= len(phrased.district_plan) <= 3


# --- The LLM planner ----------------------------------------------------------

def test_the_llm_planner_carries_the_fields():
    props = ZONE_PLAN_JSON_SCHEMA["properties"]
    assert props["districts"]["type"] == "boolean"
    assert props["district_plan"]["maxItems"] == 3
    assert props["district_relationship"]["enum"] == VALID_DISTRICT_RELATIONSHIPS
    text = system_prompt()
    for word in ("districts", "district_plan", "district_relationship", "abandoned_vs_active",
                 "corrupted_sanctum"):
        assert word in text
    plan = ZonePlan.from_dict({"zone_type": "dungeon", "room_count": 10, "size": "large",
                               "districts": True,
                               "district_plan": [{"purpose": "temple"}, {"purpose": "tomb"}],
                               "district_relationship": "abandoned_vs_active"})
    assert plan.districts and _purposes(plan) == ["temple", "tomb"]
