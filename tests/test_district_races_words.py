"""District races and intrusion from Controls and words (district races step 31, task 9, Req 10)."""

from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from ai.expand import layout_proposals, plan_to_spec
from ai.llm_planner import system_prompt
from ai.rule_planner import RulePlanner, _ARCHETYPE_WORDS, _ZONE_TYPE_WORDS
from ai.schema import (
    VALID_DISTRICT_RELATIONSHIPS, VALID_DUNGEON_RACES, ZONE_PLAN_JSON_SCHEMA, ZonePlan,
)
from .pbt_helpers import scaled

GIANT_GOBLIN = [{"purpose": "fortress", "race": "giant"}, {"purpose": "warren", "race": "goblin"}]


# --- The rule planner ---------------------------------------------------------

@pytest.mark.parametrize("prompt", [
    "a giant fortress the goblins tunnelled into",
    "a giant fortress the goblins tunneled into",
    "a giant fortress the goblins burrowed into",
    "a giant fortress the goblins dug into",
    "a giant fortress the goblins dug their way into",
    "a giant fortress the goblins have tunnelled through",
    "a giant fortress tunnelled into by goblins",
    "a giant fortress that was burrowed into by the goblins",
    "goblins digging into a giant fortress",
    "goblins tunnelling into a giant fortress",
])
def test_a_fortress_the_goblins_tunnelled_into(prompt):
    plan = RulePlanner().plan(prompt)
    assert (plan.zone_type, plan.dungeon_theme, plan.dungeon_race) == ("dungeon", "fortress", "giant")
    assert plan.districts is True
    assert plan.district_plan == GIANT_GOBLIN
    assert plan.district_relationship == "intrusion"
    assert plan.room_count == 8


def test_one_race_named_is_the_intruders():
    """The goblins dug into a fortress of the zone's default race."""
    plan = RulePlanner().plan("a fortress the goblins dug into")
    assert plan.dungeon_race == ""
    assert plan.district_plan == [{"purpose": "fortress"}, {"purpose": "warren", "race": "goblin"}]
    host = RulePlanner().plan("a giant keep the rats burrowed into")
    assert host.dungeon_race == "giant"
    assert host.district_plan == [{"purpose": "fortress", "race": "giant"}, {"purpose": "warren"}]


@pytest.mark.parametrize("prompt, plan, race, relationship", [
    ("a goblin keep overrun by giants",
     [{"purpose": "fortress", "race": "goblin"}, {"purpose": "", "race": "giant"}],
     "goblin", "abandoned_vs_active"),
    ("two warring clans, goblins and kobolds",
     [{"purpose": "", "race": "goblin"}, {"purpose": "", "race": "kobold"}],
     "goblin", "factional"),
])
def test_two_races_named_give_each_district_its_own(prompt, plan, race, relationship):
    p = RulePlanner().plan(prompt)
    assert (p.district_plan, p.dungeon_race, p.district_relationship) == (plan, race, relationship)


@pytest.mark.parametrize("prompt, race", [
    ("a keep overrun by kobolds", "kobold"),
    ("a temple fallen to the dead", ""),
    ("two factions of goblins", "goblin"),
])
def test_one_race_on_another_phrase_plans_as_before(prompt, race):
    plan = RulePlanner().plan(prompt)
    assert plan.dungeon_race == race
    assert not any("race" in p for p in plan.district_plan)


@pytest.mark.parametrize("prompt", ["dwarves digging in the mines", "a long tunnel dug deep",
                                    "a burrow of rats", "a goblin warren"])
def test_no_intrusion_without_into(prompt):
    plan = RulePlanner().plan(prompt)
    assert plan.district_relationship != "intrusion"
    assert not any("race" in p for p in plan.district_plan)


_PHRASES = ["the goblins tunnelled into", "tunnelled into by kobolds", "the rats burrowed into",
            "goblins digging into", "the giants dug their way into"]
_WORDS = sorted({w for ws in _ZONE_TYPE_WORDS.values() for w in ws}
                | {w for ws in _ARCHETYPE_WORDS.values() for w in ws}
                | {"a", "the", "dark", "with", "of", "huge", "small", "rooms"})


@settings(deadline=None, max_examples=scaled(100))
@given(words=st.lists(st.sampled_from(_WORDS), max_size=6), phrase=st.sampled_from(_PHRASES))
def test_an_intrusion_phrase_never_moves_the_zone_type_or_the_theme(words, phrase):
    base = " ".join(words)
    plain, phrased = RulePlanner().plan(base), RulePlanner().plan(f"{base} {phrase}")
    assert phrased.zone_type == plain.zone_type
    assert phrased.dungeon_theme == plain.dungeon_theme
    assert phrased.districts and phrased.district_relationship == "intrusion"


# --- The plan -----------------------------------------------------------------

def test_the_plan_keeps_a_districts_race():
    notes = []
    plan = ZonePlan.from_dict({"districts": True, "district_relationship": "intrusion",
                               "district_plan": [{"purpose": "fortress", "race": "Giant"},
                                                 {"purpose": "warren", "race": "bogus"},
                                                 {"purpose": "", "race": ""}, ]}, notes)
    assert plan.district_plan == [{"purpose": "fortress", "race": "giant"},
                                  {"purpose": "warren"}, {"purpose": ""}]
    assert notes == ["district_race_unknown: 'bogus' ignored (District 1), using the zone's race"]
    d = plan.to_dict()
    assert d["district_plan"][0] == {"purpose": "fortress", "race": "giant"}
    assert ZonePlan.from_saved(d).district_plan == plan.district_plan


def test_layout_proposals_carry_the_race():
    plan = ZonePlan(districts=True, district_plan=GIANT_GOBLIN,
                    district_relationship="intrusion").validate()
    assert layout_proposals(plan, 7) == GIANT_GOBLIN
    # An open District naming a race keeps its place; the race-less tail still drops.
    open_tail = ZonePlan(districts=True, district_plan=[{"purpose": "tomb"}, {"purpose": "", "race": "ogre"},
                                                        {"purpose": ""}]).validate()
    out = layout_proposals(open_tail, 7)
    assert len(out) == 2 and out[1]["race"] == "ogre" and out[1]["purpose"]
    pinned = ZonePlan(district_plan=[{"purpose": "tomb", "race": "giant"}, "tomb"]).validate()
    assert layout_proposals(pinned, 7) == [{"purpose": "tomb", "race": "giant"},
                                           {"purpose": "tomb"}, {"purpose": "tomb"}]


@pytest.mark.parametrize("seed", range(12))
def test_an_open_intruder_is_dug_into_its_host(seed):
    """intrusion fills an open intruder from its host's contrasts, dug ones first."""
    plan = ZonePlan(districts=True, district_relationship="intrusion",
                    district_plan=[{"purpose": "fortress"}, {"purpose": "", "race": "goblin"}]).validate()
    assert layout_proposals(plan, seed)[1] in ({"purpose": "warren", "race": "goblin"},
                                               {"purpose": "cave", "race": "goblin"})
    # A host with no dug contrast takes any contrast.
    cave = ZonePlan(districts=True, district_relationship="intrusion",
                    district_plan=[{"purpose": "cave"}, {"purpose": "", "race": "kobold"}]).validate()
    assert layout_proposals(cave, seed)[1]["purpose"] in ("fortress", "temple", "wizard_lair")


# --- The plan reaches the ZoneSpec --------------------------------------------

def test_the_words_reach_the_zone_spec():
    plan = RulePlanner().plan("a giant fortress the goblins tunnelled into")
    notes = []
    spec = plan_to_spec(plan, seed=2003, warnings=notes)
    assert [(d.purpose, d.race, d.relationship) for d in spec.districts] == \
        [("fortress", "giant", "intrusion"), ("warren", "goblin", "intrusion")]
    assert not any(n.startswith("district_") for n in notes)


def test_the_controls_reach_the_zone_spec():
    """The server's controls path: ZonePlan.from_controls, then plan_to_spec."""
    controls = {"zone_type": "dungeon", "room_count": 10, "layout": "classic", "districts": True,
                "district_relationship": "intrusion", "district_plan": GIANT_GOBLIN}
    spec = plan_to_spec(ZonePlan.from_controls(controls), seed=2001)
    assert [(d.purpose, d.race, d.relationship) for d in spec.districts] == \
        [("fortress", "giant", "intrusion"), ("warren", "goblin", "intrusion")]


# --- The LLM planner ----------------------------------------------------------

def test_the_llm_schema_and_prompt_carry_the_fields():
    props = ZONE_PLAN_JSON_SCHEMA["properties"]
    race = props["district_plan"]["items"]["properties"]["race"]
    assert race["enum"] == VALID_DUNGEON_RACES + [""]
    assert props["district_relationship"]["enum"] == VALID_DISTRICT_RELATIONSHIPS
    assert "intrusion" in VALID_DISTRICT_RELATIONSHIPS
    assert "intrusion" in props["district_relationship"]["description"]
    assert props["winding"]["type"] == props["hall_length"]["type"] == "number"
    text = system_prompt()
    for word in ("intrusion", '"race"', "tunnelled", "giant", "goblin"):
        assert word in text
    plan = ZonePlan.from_dict({"zone_type": "dungeon", "room_count": 10, "districts": True,
                               "district_plan": GIANT_GOBLIN, "district_relationship": "intrusion"})
    assert plan.district_plan == GIANT_GOBLIN
