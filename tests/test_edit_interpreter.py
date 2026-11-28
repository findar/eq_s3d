"""
tests/test_edit_interpreter.py
------------------------------
Edit ops and the rule interpreter (zone-generator-edits Req 1.1-1.4, task 1): every op has a
schema, validation clamps into range and rejects unknown ops and missing parameters, targets
resolve by id, role and room type / kind (several rooms is ambiguous), a phrase table reads on a
saved Graph dungeon spec, and any 0-2000 character string gives valid ops without raising.

The spec is a real Graph dungeon's ``ZoneSpec.to_dict()`` (the shape a version's
``spec.json`` holds), planned with a pinned seed: tomb theme, so rooms carry semantic types.
"""

from __future__ import annotations

import pytest
from hypothesis import example, given, strategies as st

from ai.edits import (
    HELP, MAX_TEXT, OPS, RULE, RuleEditInterpreter, interpret, resolve_target, validate,
)
from ai.expand import plan_to_spec
from ai.schema import VALID_DECOR, ZonePlan


def _doc(**controls):
    plan = ZonePlan.from_controls({"zone_type": "dungeon", "room_count": 12, "layout": "graph",
                                   **controls})
    return plan_to_spec(plan, seed=2).to_dict()


#: Tomb rooms at seed 2: room_0 entrance/entry_hall, room_1 hub/ossuary, room_2 deadend,
#: room_3 passage, room_4 hub, room_5 climax/vault/deep, room_11 deadend; checked below.
TOMB = _doc(dungeon_theme="tomb", locks=1)
PLAIN = _doc()   # no theme: no semantic types, kinds only


def test_fixture_is_the_shape_the_tests_read():
    rooms = {r["id"]: r for r in TOMB["rooms"]}
    assert (rooms["room_0"]["role"], rooms["room_0"]["semantic_type"]) == ("entrance", "entry_hall")
    assert (rooms["room_1"]["role"], rooms["room_1"]["semantic_type"]) == ("hub", "ossuary")
    assert (rooms["room_5"]["role"], rooms["room_5"]["semantic_type"], rooms["room_5"]["kind"]) \
        == ("climax", "vault", "deep")
    assert [r["id"] for r in TOMB["rooms"] if r["role"] == "hub"] == ["room_1", "room_4"]
    assert [r["id"] for r in TOMB["rooms"] if r["semantic_type"] == "ossuary"] == ["room_1"]
    assert all(r["semantic_type"] == "" for r in PLAIN["rooms"])


# ---------------------------------------------------------------------------
# Schema and validation (Req 1.1)
# ---------------------------------------------------------------------------

UMBRELLA_18_2 = {"widen_room", "narrow_room", "taller_room", "lower_room", "add_room",
                 "remove_room", "add_region", "remove_region", "set_purpose", "set_verticality",
                 "add_lock", "remove_lock", "reroll_room", "set_topology", "regenerate"}


def test_every_op_has_a_schema():
    assert set(OPS) == UMBRELLA_18_2 | {"reroll_decor", "set_decor_level"}
    for name, params in OPS.items():
        for key, p in params.items():
            assert p.kind in ("room", "float", "int", "choice"), (name, key)
            if p.kind in ("float", "int"):
                assert p.lo <= p.hi
                assert p.default is None or p.lo <= p.default <= p.hi
            if p.kind == "choice":
                assert p.choices
        assert name in HELP


@pytest.mark.parametrize("op, want", [
    ({"op": "widen_room", "target": "room_5", "by": 9}, {"by": 1.0}),
    ({"op": "widen_room", "target": "room_5", "by": -3}, {"by": 0.1}),
    ({"op": "narrow_room", "target": "room_5", "by": 0.9}, {"by": 0.5}),
    ({"op": "lower_room", "target": "room_5", "by": 0.0}, {"by": 0.05}),
    ({"op": "add_room", "count": 40}, {"count": 3}),
    ({"op": "add_room", "count": 0.2}, {"count": 1}),
    ({"op": "set_verticality", "delta": -7}, {"delta": -1}),
    ({"op": "regenerate", "seed": -1}, {"seed": 0}),
    ({"op": "regenerate", "seed": 10 ** 12}, {"seed": 2_147_483_647}),
])
def test_validation_clamps_into_range(op, want):
    good, bad = validate([op], TOMB)
    assert bad == []
    assert {k: good[0][k] for k in want} == want


def test_defaults_are_filled_and_names_normalised():
    good, bad = validate([{"op": "widen_room", "target": "boss room"},
                          {"op": "set_purpose", "target": "room_3", "type": "Throne Room"},
                          {"op": "set_decor_level", "level": " Dense "}], TOMB)
    assert bad == []
    assert good == [{"op": "widen_room", "target": "room_5", "by": 0.25},
                    {"op": "set_purpose", "target": "room_3", "type": "throne"},
                    {"op": "set_decor_level", "level": "dense"}]


@pytest.mark.parametrize("op, reason", [
    ({"op": "explode_room", "target": "room_1"}, "unknown op 'explode_room'"),
    ({"target": "room_1"}, "unknown op None"),
    ("widen_room", "an edit op is an object"),
    ({"op": "widen_room"}, "widen_room: missing parameter target"),
    ({"op": "set_purpose", "target": "room_1"}, "set_purpose: missing parameter type"),
    ({"op": "add_region", "target": "room_1"}, "add_region: missing parameter kind"),
    ({"op": "set_topology"}, "set_topology: missing parameter shape"),
    ({"op": "set_decor_level"}, "set_decor_level: missing parameter level"),
    ({"op": "set_verticality"}, "set_verticality: needs one of level, delta"),
    ({"op": "set_verticality", "delta": 0}, "set_verticality: delta must be -1 or 1"),
    ({"op": "widen_room", "target": "room_1", "by": "lots"}, "widen_room: by must be a number"),
    ({"op": "widen_room", "target": "room_1", "by": True}, "widen_room: by must be a number"),
    ({"op": "widen_room", "target": "room_1", "by": float("nan")}, "must be a finite number"),
    ({"op": "set_purpose", "target": "room_1", "type": "bouncy_castle"}, "is not one of"),
    ({"op": "add_region", "target": "room_1", "kind": "pvp"}, "is not one of: water, lava, ice"),
    ({"op": "reroll_decor", "target": "room_1"}, "reroll_decor: unknown parameter target"),
    ({"op": "add_lock", "target": 5}, "add_lock: target must name a room"),
])
def test_validation_rejects_with_a_reason(op, reason):
    good, bad = validate([op, {"op": "reroll_decor"}], TOMB)
    assert good == [{"op": "reroll_decor"}]
    assert len(bad) == 1 and bad[0]["why"] == "schema" and bad[0]["op"] == op
    assert reason in bad[0]["reason"]


def test_validate_takes_a_list():
    assert validate({"op": "regenerate"}, TOMB) == ([], [{"op": {"op": "regenerate"},
                                                         "reason": "edit ops are a list",
                                                         "why": "schema"}])


def test_valid_ops_validate_to_themselves():
    good, _ = validate([{"op": "widen_room", "target": "the crypt", "by": 5},
                        {"op": "add_lock", "target": "entrance"}], TOMB)
    assert validate(good, TOMB) == (good, [])


# ---------------------------------------------------------------------------
# Targets (Req 1.2)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ref, ids", [
    ("room_7", ["room_7"]),                       # id
    ("room 7", ["room_7"]),
    ("Room #7", ["room_7"]),
    ("the boss room", ["room_5"]),                # role words
    ("climax", ["room_5"]),
    ("the final chamber", ["room_5"]),
    ("entrance", ["room_0"]),
    ("hub", ["room_1", "room_4"]),
    ("the dead end", ["room_2", "room_11"]),
    ("the ossuary", ["room_1"]),                  # room type, and its words
    ("crypt", ["room_1"]),
    ("the vault", ["room_5"]),
    ("entry hall", ["room_0"]),                   # the type, not the role word "entry"
    # room_2 joins since random placement task 11 (sizes vary, so the type draw moved).
    ("collapsed gallery", ["room_2", "room_7", "room_8", "room_9", "room_10", "room_11"]),
    ("deep", ["room_5"]),                         # rule-set kind
    ("the hall", ["room_6"]),
    ("room_99", []),
    ("the kitchen", []),
    ("", []),
])
def test_targets_resolve(ref, ids):
    assert resolve_target(ref, TOMB) == ids


def test_types_before_kinds_and_kinds_on_an_untyped_spec():
    # room_3's type and kind are both "passage"; on the plain spec only the kind is there.
    assert resolve_target("passage", TOMB) == ["room_3"]
    assert resolve_target("passage", PLAIN) == ["room_3"]
    assert resolve_target("the deep room", PLAIN) == ["room_5"]
    assert resolve_target("crypt", PLAIN) == []


def test_ambiguous_target_is_rejected_listing_the_rooms():
    good, bad = validate([{"op": "widen_room", "target": "hub"}, {"op": "reroll_decor"}], TOMB)
    assert good == [{"op": "reroll_decor"}]
    assert bad[0]["why"] == "target"
    assert bad[0]["reason"] == "widen_room: 'hub' is ambiguous, it matches 2 rooms: room_1, room_4"


def test_no_room_is_a_note_naming_op_and_target_and_the_rest_apply():
    ops, notes, name = interpret("lock the kitchen and make the boss room bigger", TOMB)
    assert name == RULE
    assert ops == [{"op": "widen_room", "target": "room_5", "by": 0.25}]
    assert notes == ["add_lock: no room matches 'kitchen'"]
    good, bad = validate([{"op": "add_lock", "target": "the kitchen"}], TOMB)
    assert good == [] and bad[0]["reason"] == "add_lock: no room matches 'the kitchen'"
    ops, notes, _ = interpret("lock the way into the crypt", PLAIN)
    assert ops == [] and notes == ["add_lock: no room matches 'crypt'"]


# ---------------------------------------------------------------------------
# The phrase table (Req 1.2-1.4)
# ---------------------------------------------------------------------------

PHRASES = [
    ("make the boss room bigger", [{"op": "widen_room", "target": "room_5", "by": 0.25}]),
    ("lock the way into the crypt", [{"op": "add_lock", "target": "room_1"}]),
    ("redecorate the entrance", [{"op": "reroll_room", "target": "room_0"}]),
    ("less decor", [{"op": "set_decor_level", "level": "sparse"}]),
    ("start over", [{"op": "regenerate"}]),
    ("make the boss room bigger and lock the way into the crypt",
     [{"op": "widen_room", "target": "room_5", "by": 0.25}, {"op": "add_lock", "target": "room_1"}]),
    ("redecorate the entrance and the boss room",
     [{"op": "reroll_room", "target": "room_0"}, {"op": "reroll_room", "target": "room_5"}]),
    ("make the vault 50% wider, then redecorate it",
     [{"op": "widen_room", "target": "room_5", "by": 0.5}, {"op": "reroll_room", "target": "room_5"}]),
    ("Make the climax MUCH bigger!", [{"op": "widen_room", "target": "room_5", "by": 1.0}]),
    ("make the boss room a bit smaller", [{"op": "narrow_room", "target": "room_5", "by": 0.05}]),
    ("raise the ceiling in room 6", [{"op": "taller_room", "target": "room_6", "by": 0.25}]),
    ("lower the ceiling in room 2", [{"op": "lower_room", "target": "room_2", "by": 0.2}]),
    ("give the vault more room", [{"op": "widen_room", "target": "room_5", "by": 0.25}]),
    ("make room 3 a forge", [{"op": "set_purpose", "target": "room_3", "type": "forge"}]),
    ("turn the entrance into a guard post",
     [{"op": "set_purpose", "target": "room_0", "type": "guard_post"}]),
    ("make the ossuary a throne room", [{"op": "set_purpose", "target": "room_1", "type": "throne"}]),
    ("unlock the crypt", [{"op": "remove_lock", "target": "room_1"}]),
    ("remove the locks", [{"op": "remove_lock"}]),
    ("redecorate", [{"op": "reroll_decor"}]),
    ("new decor please", [{"op": "reroll_decor"}]),
    ("no decor", [{"op": "set_decor_level", "level": "none"}]),
    ("more decor", [{"op": "set_decor_level", "level": "dense"}]),
    ("sparse", [{"op": "set_decor_level", "level": "sparse"}]),
    ("reroll the boss room", [{"op": "reroll_room", "target": "room_5"}]),
    ("flood the vault", [{"op": "add_region", "target": "room_5", "kind": "water"}]),
    ("add lava to room 9", [{"op": "add_region", "target": "room_9", "kind": "lava"}]),
    ("drain the vault", [{"op": "remove_region", "target": "room_5", "kind": "water"}]),
    ("add two rooms off the entrance", [{"op": "add_room", "target": "room_0", "count": 2}]),
    ("add a room", [{"op": "add_room", "count": 1}]),
    ("remove room 7", [{"op": "remove_room", "target": "room_7"}]),
    ("flatter", [{"op": "set_verticality", "delta": -1}]),
    ("more vertical", [{"op": "set_verticality", "delta": 1}]),
    ("more loops", [{"op": "set_topology", "shape": "looped"}]),
    ("make it linear", [{"op": "set_topology", "shape": "linear"}]),
    ("regenerate the whole thing; less decor",
     [{"op": "regenerate"}, {"op": "set_decor_level", "level": "sparse"}]),
]


@pytest.mark.parametrize("text, ops", PHRASES, ids=[t for t, _ in PHRASES])
def test_phrase_table(text, ops):
    # The table's decor steps start from normal (an unset level is the default, none:
    # test_decor_steps_from_the_spec_level).
    got, notes, name = RuleEditInterpreter().interpret(text, dict(TOMB, decor="normal"))
    assert (got, notes, name) == (ops, [], RULE)


def test_phrase_table_is_large_enough():
    assert len(PHRASES) >= 25


def test_ambiguous_phrase_gives_a_note_and_no_op():
    ops, notes, _ = interpret("make the hub bigger", TOMB)
    assert ops == []
    assert notes == ["widen_room: 'hub' is ambiguous, it matches 2 rooms: room_1, room_4"]


def test_decor_steps_from_the_spec_level():
    assert interpret("less decor", dict(TOMB, decor="sparse"))[0] == \
        [{"op": "set_decor_level", "level": "none"}]
    assert interpret("more decor", dict(TOMB, decor="dense"))[0] == \
        [{"op": "set_decor_level", "level": "dense"}]
    # A spec with no level is at the default, none (step 34).
    unset = {k: v for k, v in TOMB.items() if k != "decor"}
    assert interpret("more decor", unset)[0] == [{"op": "set_decor_level", "level": "sparse"}]
    assert interpret("less decor", unset)[0] == [{"op": "set_decor_level", "level": "none"}]


@pytest.mark.parametrize("text", ["", "   ", "\n\t", "hello", "paint it blue", "42", "\x00\x07"])
def test_unknown_text_gives_no_ops(text):
    ops, notes, name = interpret(text, TOMB)
    assert ops == [] and name == RULE
    assert all(n.startswith("not understood") for n in notes)


def test_text_is_cleaned_then_cut():
    # Control characters go (newline and tab stay), then the text is cut at MAX_TEXT, so the
    # clause past the cut is never read.
    assert interpret("make the boss\x00 room big\x1bger", TOMB)[0] == \
        [{"op": "widen_room", "target": "room_5", "by": 0.25}]
    tail = "x" * (MAX_TEXT - len("start over") - 1) + "\nstart over"
    assert interpret(tail, TOMB)[0] == [{"op": "regenerate"}]
    assert interpret("y" + tail, TOMB)[0] == []


# ---------------------------------------------------------------------------
# Any string (Req 1.3, 1.4)
# ---------------------------------------------------------------------------

_WORDS = st.sampled_from(["make", "the", "boss", "room", "bigger", "and", "lock", "crypt", "hub",
                          "redecorate", "less", "decor", "start over", "it", ",", "room 3",
                          "a", "forge", "into", "flood", "50%", "then", "dead end", "remove"])
_TEXT = st.one_of(st.text(max_size=MAX_TEXT),
                  st.text(alphabet=st.characters(min_codepoint=0, max_codepoint=0x7F), max_size=200),
                  st.lists(_WORDS, max_size=40).map(" ".join))


@given(text=_TEXT, spec=st.sampled_from([TOMB, PLAIN, {}, {"rooms": []}]))
@example(text="", spec=TOMB)
@example(text=" \t\n ", spec=TOMB)
@example(text="\x00" * MAX_TEXT, spec=TOMB)
@example(text="\ud800 make the boss room bigger \U0001F600", spec=TOMB)
@example(text="room " + "9" * 1999, spec=TOMB)
def test_any_text_gives_valid_ops_and_never_raises(text, spec):
    ops, notes, name = interpret(text, spec)
    assert name == RULE
    assert isinstance(notes, list) and all(isinstance(n, str) for n in notes)
    assert validate(ops, spec) == (ops, [])
    assert interpret(text, spec) == (ops, notes, name)
