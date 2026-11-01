"""
tests/test_wilderness_trees_controls.py
---------------------------------------
Tree density control (trees spec Req 3.1-3.3): ``trees`` reaches
``spec.wilderness`` from the prompt, ``--trees`` and ``controls.trees`` like
``edges`` does, its source is recorded, and a bad or misplaced value is refused
before any write.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import main
import server.app as app_mod
from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.wilderness.biome_resolve import named_tree_density


def _wild_plan(prompt: str = "") -> ZonePlan:
    return ZonePlan(name="trees", zone_type="wilderness", prompt=prompt)


@pytest.mark.parametrize("prompt, level", [
    ("a treeless karana", "none"),
    ("barren plains", "none"),
    ("open grassland", "none"),
    ("sparse plains", "sparse"),
    ("scattered trees on the plains", "sparse"),
    ("a karana with forest", "dense"),
    ("wooded hills", "dense"),
    ("plains with woods", "dense"),
    ("dense grassland", "dense"),
    ("sparse woods", "sparse"),
    ("rolling karana", None),
    ("an opening in the plains", None),
])
def test_prompt_words_map_to_levels(prompt, level):
    assert named_tree_density(prompt) == level
    trees = plan_to_spec(_wild_plan(prompt), seed=1).wilderness
    if level is None:
        assert "trees" not in trees and "trees_source" not in trees
    else:
        assert (trees["trees"], trees["trees_source"]) == (level, "prompt")


@pytest.mark.parametrize("source", ["controls", "cli"])
def test_explicit_level_beats_the_prompt(source):
    spec = plan_to_spec(_wild_plan("a dense forest"), seed=1, trees="none",
                        trees_source=source)
    assert (spec.wilderness["trees"], spec.wilderness["trees_source"]) == ("none", source)


def test_plan_to_spec_rejects_a_bad_level():
    with pytest.raises(ValueError, match="trees"):
        plan_to_spec(_wild_plan(), seed=1, trees="jungle")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_trees_reaches_the_spec(tmp_path, monkeypatch):
    seen = {}

    def fake_generate(factory, **kw):
        seen["spec"] = factory(3)
        raise SystemExit(0)

    monkeypatch.setattr(main, "generate_validated", fake_generate)
    with pytest.raises(SystemExit):
        main.main(["generate", "woods", "--zone-type", "wilderness",
                   "--trees", "sparse", "--output", str(tmp_path / "out")])
    wild = seen["spec"].wilderness
    assert (wild["trees"], wild["trees_source"]) == ("sparse", "cli")


@pytest.mark.parametrize("argv", [
    ["--zone-type", "dungeon", "--trees", "dense"],
    ["--trees", "dense"],
    ["--zone-type", "wilderness", "--trees", "jungle"],
])
def test_cli_bad_trees_exits_2_before_any_write(tmp_path, capsys, argv):
    out = tmp_path / "out"
    with pytest.raises(SystemExit) as exc:
        main.main(["generate", "woods", *argv, "--output", str(out)])
    assert exc.value.code == 2
    assert "--trees" in capsys.readouterr().err
    assert not out.exists()


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    out = tmp_path / "web_out"
    out.mkdir()
    monkeypatch.setattr(app_mod, "OUTPUT_DIR", out)
    monkeypatch.setattr(app_mod, "FAILURE_LOG", tmp_path / "failures.jsonl")
    return TestClient(app_mod.app)


@pytest.mark.parametrize("controls, needle", [
    ({"zone_type": "dungeon", "trees": "dense"}, "wilderness"),
    ({"zone_type": "wilderness", "trees": "jungle"}, "one of"),
    ({"zone_type": "wilderness", "trees": 3}, "one of"),
])
def test_server_bad_trees_is_a_400_before_any_write(client, controls, needle):
    resp = client.post("/api/generate", json={"mode": "controls", "controls": controls})
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"]
    assert "trees" in detail and needle in detail, detail
    assert list(app_mod.OUTPUT_DIR.iterdir()) == []


def _find_vegetation(doc):
    if isinstance(doc, dict):
        if "vegetation" in doc:
            return doc["vegetation"]
        for v in doc.values():
            found = _find_vegetation(v)
            if found is not None:
                return found
    return None


def test_server_controls_trees_reach_the_sidecar(client):
    resp = client.post("/api/generate", json={
        "mode": "controls", "seed": 2024,
        "controls": {"zone_type": "wilderness", "edges": {"N": "zoneline"},
                     "trees": "sparse"},
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    sidecar = app_mod.OUTPUT_DIR / body["id"] / "v1" / f"{body['id']}.zone.json"
    veg = _find_vegetation(json.loads(sidecar.read_text()))
    assert veg is not None, "sidecar has no vegetation block"
    assert (veg["level"], veg["level_source"]) == ("sparse", "controls")
