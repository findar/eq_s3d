"""Wilderness POIs task 8 (Requirements 8.1, 8.3): the Sites and Inhabitants
controls through the plan, CLI, server and prompt words; the EQ map's Footprint
lines and Site labels, and the Sites on the web map."""

import json
import tempfile

import pytest
from fastapi.testclient import TestClient

import main
import server.app as app_mod
from ai.expand import plan_to_spec
from ai.rule_planner import RulePlanner
from ai.schema import VALID_SITES, ZonePlan, available_inhabitants
from generators.eqmap import SITE_COLOUR, parse_map_layer


@pytest.fixture
def client(tmp_path, monkeypatch):
    out = tmp_path / "web_out"
    out.mkdir()
    monkeypatch.setattr(app_mod, "OUTPUT_DIR", out)
    monkeypatch.setattr(app_mod, "FAILURE_LOG", tmp_path / "failures.jsonl")
    return TestClient(app_mod.app)


def test_server_controls_reach_the_build_and_both_maps_show_the_sites(client):
    r = client.post("/api/generate", json={
        "mode": "controls", "seed": 1955208177,
        "controls": {"zone_type": "wilderness", "sites": "dense", "inhabitant": "orc"}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["plan"]["sites"], body["plan"]["inhabitant"]) == ("dense", "orc")
    build = app_mod.OUTPUT_DIR / body["id"] / "v1"
    block = json.loads((build / f"{body['id']}.zone.json").read_text(encoding="utf-8"))["sites"]
    assert (block["control"], block["control_source"], block["inhabitant"]) == ("dense", "controls", "orc")
    sites = block["sites"]
    assert sites and all(s["inhabitant"] == "orc" for s in sites)

    svg = (build / f"{body['id']}.map.svg").read_text(encoding="utf-8")
    assert svg.count('class="site"') == len(sites)
    assert svg.count('class="site-footprint"') > 0

    layers = [parse_map_layer(p.read_text(encoding="utf-8")).layer for p in sorted(build.glob("maps/*.txt"))]
    labels = [p for layer in layers for p in layer.labels if (p.r, p.g, p.b) == SITE_COLOUR]
    lines = [l for layer in layers for l in layer.lines if (l.r, l.g, l.b) == SITE_COLOUR]
    assert sorted(p.text for p in labels) == sorted(f"Orc_{s['kind']}" for s in sites)
    assert len(lines) >= 3 * svg.count('class="site-footprint"')


@pytest.mark.parametrize("controls, named", [
    ({"zone_type": "wilderness", "sites": "lots"}, VALID_SITES),
    ({"zone_type": "wilderness", "sites": 2}, VALID_SITES),
    ({"zone_type": "wilderness", "inhabitant": "elf"}, available_inhabitants()),
    ({"zone_type": "dungeon", "sites": "dense"}, ["sites", "wilderness", "outdoor_dungeon"]),
    ({"zone_type": "city", "inhabitant": "orc"}, ["inhabitant", "wilderness", "outdoor_dungeon"]),
])
def test_a_bad_value_is_a_400_naming_the_choices(client, controls, named):
    r = client.post("/api/generate", json={"mode": "controls", "controls": controls})
    assert r.status_code == 400, r.text
    assert all(n in r.json()["detail"] for n in named), r.json()


def test_the_plan_carries_them_to_the_spec_and_rejects_bad_values():
    plan = ZonePlan.from_controls({"zone_type": "outdoor_dungeon", "sites": "Sparse", "inhabitant": "centaur"})
    spec = plan_to_spec(plan, seed=3, sites_source="controls")
    assert (spec.sites, spec.inhabitant, spec.sites_source) == ("sparse", "centaur", "controls")
    old = ZonePlan.from_saved({"name": "x", "zone_type": "wilderness"})
    assert (old.sites, old.inhabitant) == ("normal", "")
    assert plan_to_spec(old, seed=3).sites_source == "default"
    with pytest.raises(ValueError, match="sites 'lots' is not one of: none, sparse, normal, dense"):
        ZonePlan(zone_type="wilderness", sites="lots").validate()
    with pytest.raises(ValueError, match="inhabitant 'elf' is not one of: centaur, gnoll, human, orc"):
        ZonePlan(zone_type="wilderness", inhabitant="elf").validate()


@pytest.mark.parametrize("prompt, sites, inhabitant", [
    ("an orc camp on the plains", "normal", "orc"),
    ("farmsteads across the rolling hills", "normal", "human"),
    ("empty wilderness plains, no camps", "none", ""),
    ("lots of camps on the grassland", "dense", ""),
    ("settled plains with gnolls", "dense", "gnoll"),
    ("sparsely settled steppe", "sparse", ""),
    ("torch-lit plains", "normal", ""),                 # "orc" only as a word
    ("an orc fortress dungeon", "normal", ""),          # not a landscape zone
])
def test_prompt_words_pick_them(prompt, sites, inhabitant):
    plan = RulePlanner().plan(prompt)
    assert (plan.sites, plan.inhabitant) == (sites, inhabitant)
    if plan.zone_type == "wilderness":
        moved = (sites, inhabitant) != ("normal", "")
        assert plan_to_spec(plan, seed=1).sites_source == ("prompt" if moved else "default")


def test_cli_options_reach_the_build(monkeypatch, tmp_path):
    monkeypatch.setattr(tempfile, "tempdir", tempfile.tempdir)
    main.main(["generate", "s8", "--zone-type", "wilderness", "--seed", "31337",
               "--sites", "sparse", "--inhabitant", "gnoll", "--output", str(tmp_path)])
    (path,) = tmp_path.glob("s8_*/v1/s8.zone.json")
    block = json.loads(path.read_text(encoding="utf-8"))["sites"]
    assert (block["control"], block["control_source"], block["inhabitant"]) == ("sparse", "cli", "gnoll")


@pytest.mark.parametrize("argv", [["--zone-type", "wilderness", "--sites", "lots"],
                                  ["--zone-type", "wilderness", "--inhabitant", "elf"],
                                  ["--zone-type", "dungeon", "--sites", "dense"],
                                  ["--zone-type", "city", "--inhabitant", "orc"]])
def test_cli_bad_use_is_a_usage_error(argv, tmp_path):
    with pytest.raises(SystemExit):
        main.main(["generate", "s8", *argv, "--output", str(tmp_path)])
