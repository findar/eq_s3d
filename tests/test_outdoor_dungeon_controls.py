"""Outdoor-dungeon task 7: the zone type, prompt words, controls and sidecar."""

import json
import tempfile

import pytest
from fastapi.testclient import TestClient

import main
import server.app as app_mod
from ai.expand import plan_to_spec
from ai.rule_planner import RulePlanner
from ai.schema import ZonePlan
from generators.backends import backend_for
from generators.zone_types import is_enabled, zone_type_listing


@pytest.mark.parametrize("prompt", [
    "an outdoor dungeon full of gnolls",
    "a cave in a hill where kobolds live",
    "an old barrow on the moors",
    "a warren in the hills",
    "a hillside cave",
])
def test_prompt_words_plan_an_outdoor_dungeon(prompt):
    assert RulePlanner().plan(prompt).zone_type == "outdoor_dungeon"


def test_prompt_without_the_words_is_unchanged():
    planner = RulePlanner()
    assert planner.plan("a dark cave full of spiders").zone_type == "dungeon"
    assert planner.plan("rolling hills and meadows").zone_type == "wilderness"


def test_zone_type_is_defined_enabled_and_built_on_terrain():
    assert is_enabled("outdoor_dungeon")
    listing = {z["name"]: z for z in zone_type_listing()}
    assert listing["outdoor_dungeon"]["enabled"] is True
    assert backend_for("outdoor_dungeon").name == "terrain"


def test_plan_fields_reach_the_spec():
    """Room count, theme, race and tint as for dungeons; edges and trees as
    for wilderness."""
    plan = ZonePlan(name="odplan", zone_type="outdoor_dungeon", room_count=4,
                    dungeon_theme="temple", dungeon_race="gnoll",
                    elemental_tint="").validate()
    spec = plan_to_spec(plan, seed=1, edges={"N": "zoneline"}, trees="sparse",
                        trees_source="controls")
    assert spec.zone_type == "outdoor_dungeon"
    assert spec.wilderness["dungeon"]["rooms_requested"] == 4
    assert spec.wilderness["edges"]["N"] == "zoneline"
    assert spec.wilderness["trees"] == "sparse"
    assert spec.dungeon_theme == "temple" and spec.dungeon_race == "gnoll"
    assert {r.semantic_type for r in spec.rooms} != {""}


def test_cli_accepts_the_zone_type_with_edges_and_trees(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(main, "cmd_generate", lambda args: seen.update(vars(args)))
    # main() points tempfile at the output dir for the whole process.
    monkeypatch.setattr(tempfile, "tempdir", tempfile.tempdir)
    main.main(["generate", "odcli", "--zone-type", "outdoor_dungeon",
               "--edges", "N=zoneline", "--trees", "dense", "--output", str(tmp_path)])
    assert seen["zone_type"] == "outdoor_dungeon"
    assert seen["edges"]["N"] == "zoneline" and seen["trees"] == "dense"
    with pytest.raises(SystemExit):
        main.main(["generate", "oddun", "--zone-type", "dungeon", "--edges", "N=zoneline",
                   "--output", str(tmp_path)])


@pytest.fixture
def client(tmp_path, monkeypatch):
    out = tmp_path / "web_out"
    out.mkdir()
    monkeypatch.setattr(app_mod, "OUTPUT_DIR", out)
    monkeypatch.setattr(app_mod, "FAILURE_LOG", tmp_path / "failures.jsonl")
    return TestClient(app_mod.app)


def test_server_builds_it_and_the_sidecar_has_the_block(client):
    resp = client.post("/api/generate", json={
        "mode": "controls", "seed": 5,
        "controls": {"zone_type": "outdoor_dungeon", "rooms": 4,
                     "edges": {"N": "zoneline"}, "trees": "sparse"},
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["zone_type"] == "outdoor_dungeon" and body["validated"]
    sidecar = json.loads((app_mod.OUTPUT_DIR / body["id"] / "v1"
                          / f"{body['id']}.zone.json").read_text(encoding="utf-8"))
    block = sidecar["outdoor_dungeon"]
    assert block["rock_cover"] > 0
    env = block["envelope"]
    assert env["min_xy"][0] < env["max_xy"][0] and "floor_limit" in env
    (entrance,) = block["entrances"]
    assert entrance["tunnel_id"] and len(entrance["apron_centre"]) == 3
    assert {"centre", "width", "height"} <= set(entrance["mouth"])
    assert len(block["outdoor_spawn"]) == 3
