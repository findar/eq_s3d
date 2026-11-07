"""Room layouts task 7 (Requirements 8, 6.4): the Features control through the plan, CLI, server
and page; the sidecar; the map and EQ map files showing what stands in rooms.
"""

import json
import random
import tempfile

import pytest
from fastapi.testclient import TestClient

import main
import server.app as app_mod
from ai.expand import plan_to_spec
from ai.schema import VALID_FEATURES, ZonePlan
from generators.eqmap import build_map_file, parse_map_layer
from generators.mapgeom import DepthBand, OutlineSet, with_solids
from generators.mapview import render_map_svg
from generators.pipeline import generate_validated


@pytest.fixture
def client(tmp_path, monkeypatch):
    out = tmp_path / "web_out"
    out.mkdir()
    monkeypatch.setattr(app_mod, "OUTPUT_DIR", out)
    monkeypatch.setattr(app_mod, "FAILURE_LOG", tmp_path / "failures.jsonl")
    return TestClient(app_mod.app)


def _sidecar(body):
    return json.loads((app_mod.OUTPUT_DIR / body["id"] / "v1"
                       / f"{body['id']}.zone.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("features", VALID_FEATURES)
def test_each_setting_reaches_the_build_through_the_server(client, features):
    r = client.post("/api/generate", json={
        "mode": "controls", "seed": 4,
        "controls": {"zone_type": "dungeon", "room_count": 8, "layout": "graph", "features": features,
                     "dungeon_theme": "temple"}})
    assert r.status_code == 200, r.text
    block = _sidecar(r.json())["layout"]
    assert block["features"] == features
    has = any(rec.get("features") for rec in block["rooms"].values())
    assert has == (features != "none")


@pytest.mark.parametrize("controls, named", [
    ({"zone_type": "dungeon", "features": "lots"}, VALID_FEATURES),
    ({"zone_type": "dungeon", "features": 3}, VALID_FEATURES),
    ({"zone_type": "city", "features": "dense"}, ["dungeon", "outdoor_dungeon"]),
])
def test_a_bad_value_is_a_400_naming_the_choices(client, controls, named):
    r = client.post("/api/generate", json={"mode": "controls", "controls": controls})
    assert r.status_code == 400, r.text
    assert all(n in r.json()["detail"] for n in named), r.json()


def test_none_builds_step_8s_rooms():
    a = ZonePlan(name="x", zone_type="dungeon", room_count=10, layout="graph", walls="rough", features="none").validate()
    spec = plan_to_spec(a, seed=4)
    assert not any(r.features or r.pois for r in spec.rooms)


def test_a_plan_rejects_a_bad_density_and_old_plans_load_as_normal():
    with pytest.raises(ValueError, match="none, sparse, normal, dense"):
        ZonePlan(name="x", zone_type="dungeon", features="lots").validate()
    assert ZonePlan.from_dict({"name": "x", "zone_type": "dungeon"}).features == "normal"


def test_cli_flag_reaches_the_build(monkeypatch, tmp_path):
    monkeypatch.setattr(tempfile, "tempdir", tempfile.tempdir)
    main.main(["generate", "w7", "--zone-type", "dungeon", "--rooms", "5", "--seed", "4", "--layout", "graph",
               "--features", "dense", "--output", str(tmp_path)])
    (path,) = tmp_path.glob("w7_*/v1/w7.zone.json")
    assert json.loads(path.read_text(encoding="utf-8"))["layout"]["features"] == "dense"


@pytest.mark.parametrize("argv", [["--features", "lots"], ["--zone-type", "city", "--features", "dense"]])
def test_cli_bad_use_is_a_usage_error(argv, tmp_path):
    with pytest.raises(SystemExit):
        main.main(["generate", "w7", *argv, "--output", str(tmp_path)])


def _temple(rooms=14, seed=4):
    plan = ZonePlan(name="w7", zone_type="dungeon", room_count=rooms, layout="graph", dungeon_theme="temple",
                    verticality="flat").validate()
    return plan, plan_to_spec(plan, seed=seed)


def test_the_map_draws_features_and_pois():
    _plan, spec = _temple()
    svg = render_map_svg(spec)
    assert svg.count('class="feature"') == sum(len(r.features) for r in spec.rooms) > 0
    assert svg.count('class="poi"') == sum(len(r.pois) for r in spec.rooms) > 0


def test_eq_map_draws_free_standing_solids_and_not_a_dais():
    _plan, spec = _temple()
    outline = OutlineSet(polylines=(), bands=(DepthBand(index=0, z_lo=-1e9, z_hi=1e9, median_z=0.0, role="main", offset=0),),
                         bounds=(0, 0, 0, 0, 0, 0), seed_face=0, reachable_only=True)
    mf = build_map_file(with_solids(outline, spec), spec, "w7")
    expected = sum(len(f.plan) for r in spec.rooms for f in r.features if f.kind != "dais")
    assert expected and len(mf.layers[0].lines) == expected


@pytest.mark.slow
def test_a_built_map_file_parses_with_them(tmp_path):
    plan, _spec = _temple()
    vb = generate_validated(lambda s: plan_to_spec(plan, seed=s), zone_type="dungeon", zone_id="w7",
                            rng=random.Random(4), output_dir=tmp_path, failure_log=None, max_attempts=3, timeout_s=300.0)
    files = sorted(vb.build_dir.glob("maps/*.txt"))
    assert files
    parsed = parse_map_layer(files[0].read_text(encoding="utf-8"))
    assert not parsed.skipped and parsed.layer.lines
