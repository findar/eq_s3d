"""
tests/test_llm_edits.py
-----------------------
The optional LLM edit interpreter (zone-generator-edits Req 1.5, task 6). A fake client stands in
for the provider: good JSON gives validated, clamped ops named "llm"; bad JSON, a schema failure,
an exception and a timeout each give the rule interpreter's ops and name. Without a key the rule
interpreter is picked and no provider SDK is imported. No network.
"""

from __future__ import annotations

import builtins
import sys
import threading
import time

import pytest

from ai.edits import RULE, RuleEditInterpreter
from ai.expand import plan_to_spec
from ai.llm_edits import LLM, LLMEditInterpreter, get_edit_interpreter, system_prompt
from ai.schema import ZonePlan


def _doc():
    plan = ZonePlan.from_controls({"zone_type": "dungeon", "room_count": 12, "layout": "graph",
                                   "dungeon_theme": "tomb", "locks": 1})
    return plan_to_spec(plan, seed=2).to_dict()


#: Tomb rooms at seed 2 (as in test_edit_interpreter): room_5 is the climax vault.
TOMB = _doc()
TEXT = "make the boss room bigger and lock the way into the crypt"


def _client(reply):
    calls = []

    def client(system, user, timeout):
        calls.append((system, user, timeout))
        if isinstance(reply, BaseException):
            raise reply
        return reply

    client.calls = calls
    return client


def _rule(text=TEXT):
    return RuleEditInterpreter().interpret(text, TOMB)


def test_good_json_gives_validated_clamped_ops():
    reply = ('{"ops": [{"op": "widen_room", "target": "boss room", "by": 5},'
             ' {"op": "add_lock", "target": "room_1"}, {"op": "reroll_decor"}]}')
    client = _client(reply)
    ops, notes, name = LLMEditInterpreter(client=client).interpret(TEXT, TOMB)
    assert name == LLM
    assert ops == [{"op": "widen_room", "target": "room_5", "by": 1.0},
                   {"op": "add_lock", "target": "room_1"}, {"op": "reroll_decor"}]
    assert notes == []
    system, user, timeout = client.calls[0]
    assert user == TEXT and timeout == 15.0
    assert "widen_room" in system and "room_5" in system and "climax" in system


def test_fenced_json_is_accepted():
    reply = '```json\n{"ops": [{"op": "set_topology", "shape": "Looped"}]}\n```'
    ops, notes, name = LLMEditInterpreter(client=_client(reply)).interpret("more loops", TOMB)
    assert (ops, notes, name) == ([{"op": "set_topology", "shape": "looped"}], [], LLM)


def test_unknown_target_is_a_note_and_the_rest_apply():
    reply = ('{"ops": [{"op": "add_lock", "target": "kitchen"},'
             ' {"op": "taller_room", "target": "room_5"}]}')
    ops, notes, name = LLMEditInterpreter(client=_client(reply)).interpret("x", TOMB)
    assert name == LLM
    assert ops == [{"op": "taller_room", "target": "room_5", "by": 0.25}]
    assert len(notes) == 1 and "kitchen" in notes[0]


def test_empty_ops_are_accepted():
    assert LLMEditInterpreter(client=_client('{"ops": []}')).interpret("hm", TOMB) == ([], [], LLM)


@pytest.mark.parametrize("reply", [
    "not json at all",
    "[1, 2]",
    '{"edits": []}',
    '{"ops": {"op": "reroll_decor"}}',
    '{"ops": [{"op": "fly_away"}]}',
    '{"ops": [{"op": "widen_room", "target": "room_5", "by": "lots"}]}',
    '{"ops": [{"op": "reroll_decor"}, {"op": "add_region", "target": "room_5"}]}',
    None,
])
def test_bad_json_or_schema_failure_falls_back_to_rule(reply):
    interp = LLMEditInterpreter(client=_client(reply))
    assert interp.interpret(TEXT, TOMB) == _rule()
    assert interp.last_error is not None


def test_exception_falls_back_without_leaking_its_text(capsys):
    interp = LLMEditInterpreter(client=_client(RuntimeError("sk-secret in body")))
    ops, notes, name = interp.interpret(TEXT, TOMB)
    assert (ops, notes, name) == _rule() and name == RULE
    assert interp.last_error == "RuntimeError"
    assert "sk-secret" not in capsys.readouterr().out


def test_timeout_falls_back_to_rule():
    release = threading.Event()

    def slow(system, user, timeout):
        release.wait(10)
        return '{"ops": [{"op": "reroll_decor"}]}'

    interp = LLMEditInterpreter(client=slow, timeout=0.2)
    start = time.monotonic()
    try:
        result = interp.interpret(TEXT, TOMB)
    finally:
        release.set()
    assert time.monotonic() - start < 5
    assert result == _rule()
    assert interp.last_error == "_Timeout"


def test_empty_text_never_calls_the_client():
    client = _client('{"ops": [{"op": "reroll_decor"}]}')
    assert LLMEditInterpreter(client=client).interpret(" \x00 ", TOMB) == ([], [], RULE)
    assert client.calls == []


def test_control_characters_are_cleaned_before_sending():
    client = _client('{"ops": []}')
    LLMEditInterpreter(client=client).interpret("more\x07 loops" + "x" * 3000, TOMB)
    user = client.calls[0][1]
    assert "\x07" not in user and len(user) == 2000


def test_system_prompt_survives_a_bad_spec():
    assert "(none)" in system_prompt({})
    assert "(none)" in system_prompt({"rooms": [None, {"id": 3}]})


def test_no_key_picks_rule_and_imports_no_provider_sdk(no_api_keys, monkeypatch):
    imported = []
    real_import = builtins.__import__

    def spy(name, *args, **kwargs):
        if name.split(".")[0] in ("openai", "anthropic"):
            imported.append(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", spy)
    interp = get_edit_interpreter()
    assert isinstance(interp, RuleEditInterpreter)
    assert not LLMEditInterpreter().available()
    assert interp.interpret(TEXT, TOMB)[2] == RULE
    assert LLMEditInterpreter().interpret(TEXT, TOMB) == _rule()
    assert imported == []


def test_a_key_picks_llm_and_planner_rule_forces_rule(no_api_keys, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    assert isinstance(get_edit_interpreter(), LLMEditInterpreter)
    monkeypatch.setenv("EQ_S3D_PLANNER", "rule")
    assert isinstance(get_edit_interpreter(), RuleEditInterpreter)


@pytest.mark.parametrize("key", ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"])
def test_missing_sdk_falls_back_to_rule(no_api_keys, no_network, monkeypatch, key):
    monkeypatch.setenv(key, "test-key")
    monkeypatch.setitem(sys.modules, "openai", None)
    monkeypatch.setitem(sys.modules, "anthropic", None)
    interp = get_edit_interpreter()
    assert isinstance(interp, LLMEditInterpreter)
    assert interp.interpret(TEXT, TOMB) == _rule()
    assert interp.last_error in ("ImportError", "ModuleNotFoundError")
