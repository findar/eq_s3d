"""Winding control task 3 (Requirement 5): the Winding through the server's Controls, and the
rule planner's words for it."""

import json

import pytest
from fastapi.testclient import TestClient

import server.app as app_mod
from ai.rule_planner import RulePlanner, match_winding


@pytest.fixture
def client(tmp_path, monkeypatch):
    out = tmp_path / "web_out"
    out.mkdir()
    monkeypatch.setattr(app_mod, "OUTPUT_DIR", out)
    monkeypatch.setattr(app_mod, "FAILURE_LOG", tmp_path / "failures.jsonl")
    return TestClient(app_mod.app)


def _build(client, winding, **extra):
    r = client.post("/api/generate", json={
        "mode": "controls", "seed": 4, **extra,
        "controls": {"zone_type": "dungeon", "room_count": 5, "dungeon_theme": "cave",
                     "winding": winding}})
    assert r.status_code == 200, r.text
    body = r.json()
    spec = json.loads((app_mod.OUTPUT_DIR / body["id"] / "v1"
                          / f"{body['id']}.spec.json").read_text(encoding="utf-8"))
    return body, spec


@pytest.mark.parametrize("winding", [0, 2])
def test_the_controls_value_reaches_the_spec(client, winding):
    body, spec = _build(client, winding)
    assert body["plan"]["winding"] == winding
    assert spec["winding"] == winding


@pytest.mark.parametrize("bad", ["twisty", "nan", True, None])
def test_a_bad_value_falls_back_to_1(client, bad):
    body, spec = _build(client, bad)
    # 1 is the default, which the plan leaves out.
    assert "winding" not in body["plan"]
    assert "winding" not in spec


@pytest.mark.parametrize("prompt, winding", [
    ("a straight dungeon of orderly halls", 0.25),
    ("a regular crypt", 0.25),
    ("a twisting cave", 1.75),
    ("labyrinthine serpentine tunnels", 1.75),
    ("a meandering, twisty grotto", 1.75),
    ("a dark cave", 1.0),
    ("an irregular cave", 1.0),             # whole words only
    ("a straightforward crypt", 1.0),
    ("a keep with a winding stair", 1.0),   # the stair winds, not the tunnels
])
def test_words_set_the_winding(prompt, winding):
    assert match_winding(prompt) == winding
    assert RulePlanner().plan(prompt).winding == winding


def test_controls_win_over_words(client):
    # Controls mode reads the Controls, never the prompt's words (as verticality does).
    body, _ = _build(client, 2, prompt="a straight dungeon")
    assert body["mode"] == "controls"
    assert body["plan"]["winding"] == 2
