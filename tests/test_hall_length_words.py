"""Hall length task 3 (Requirement 4): the Hall length through the server's Controls, and the
rule planner's words for it."""

import json

import pytest
from fastapi.testclient import TestClient

import server.app as app_mod
from ai.rule_planner import RulePlanner, match_hall_length


@pytest.fixture
def client(tmp_path, monkeypatch):
    out = tmp_path / "web_out"
    out.mkdir()
    monkeypatch.setattr(app_mod, "OUTPUT_DIR", out)
    monkeypatch.setattr(app_mod, "FAILURE_LOG", tmp_path / "failures.jsonl")
    return TestClient(app_mod.app)


def _build(client, hall_length, **extra):
    r = client.post("/api/generate", json={
        "mode": "controls", "seed": 4, **extra,
        "controls": {"zone_type": "dungeon", "room_count": 5, "hall_length": hall_length}})
    assert r.status_code == 200, r.text
    body = r.json()
    spec = json.loads((app_mod.OUTPUT_DIR / body["id"] / "v1"
                          / f"{body['id']}.spec.json").read_text(encoding="utf-8"))
    return body, spec


@pytest.mark.parametrize("hall_length", [0.5, 2.5])
def test_the_controls_value_reaches_the_spec(client, hall_length):
    body, spec = _build(client, hall_length)
    assert body["plan"]["hall_length"] == hall_length
    assert spec["hall_length"] == hall_length


@pytest.mark.parametrize("bad", ["long", "nan", True, None])
def test_a_bad_value_falls_back_to_1(client, bad):
    body, spec = _build(client, bad)
    # 1 is the default, which the plan and spec leave out.
    assert "hall_length" not in body["plan"]
    assert "hall_length" not in spec


@pytest.mark.parametrize("prompt, hall_length", [
    ("a crypt of long halls", 2.0),
    ("long corridors under the keep", 2.0),
    ("a mine with long passages", 2.0),
    ("a sprawling ruin", 2.0),
    ("far-flung chambers", 2.0),
    ("a temple spread out on the cliff", 2.0),
    ("a compact keep", 0.6),
    ("a tight crypt", 0.6),
    ("cramped, close-set cells", 0.6),
    ("a vault of short halls", 0.6),
    ("short corridors", 0.6),
    ("a sprawling ruin of tight cells", 0.6),   # short wins a tie
    ("compact rooms joined by long corridors", 0.6),
    ("a long-forgotten crypt", 1.0),          # bare long / short never fire
    ("a long dungeon", 1.0),
    ("a short trip into the dark", 1.0),
    ("a dark cave", 1.0),
])
def test_words_set_the_hall_length(prompt, hall_length):
    assert match_hall_length(prompt) == hall_length
    assert RulePlanner().plan(prompt).hall_length == hall_length


def test_controls_win_over_words(client):
    # Controls mode reads the Controls, never the prompt's words.
    body, _ = _build(client, 2.5, prompt="a compact dungeon")
    assert body["mode"] == "controls"
    assert body["plan"]["hall_length"] == 2.5
