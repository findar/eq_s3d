"""Room walls task 7 (Requirement 11): the Walls control through the plan, CLI, server and
page; the sidecar; the map and EQ map files following shaped rooms.
"""

import json
import random
import tempfile
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

import main
import server.app as app_mod
from ai.expand import plan_to_spec
from ai.schema import ZonePlan, available_wall_styles
from generators.eqmap import map_to_world, parse_map_layer
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


def test_the_styles_are_the_rule_files():
    assert available_wall_styles() == ["built", "hewn", "rough"]


@pytest.mark.parametrize("walls", ["built", "hewn", "rough"])
def test_each_setting_reaches_the_build_through_the_server(client, walls):
    r = client.post("/api/generate", json={
        "mode": "controls", "seed": 4,
        "controls": {"zone_type": "dungeon", "room_count": 6, "layout": "graph", "walls": walls}})
    assert r.status_code == 200, r.text
    assert r.json()["plan"]["walls"] == walls
    block = _sidecar(r.json())["layout"]
    assert block["walls"] == walls
    for rec in block["rooms"].values():
        assert rec["shape"] and 0 < rec["fill"] <= 1
        assert (rec["outline"] is None) == (rec["shape"] == "rect")


def test_from_theme_is_each_rooms_draw(client):
    r = client.post("/api/generate", json={
        "mode": "controls", "seed": 4,
        "controls": {"zone_type": "dungeon", "room_count": 6, "layout": "graph", "walls": "",
                     "dungeon_theme": "warren"}})
    assert r.status_code == 200, r.text
    assert _sidecar(r.json())["layout"]["walls"] == "rules"


@pytest.mark.parametrize("controls, named", [
    ({"zone_type": "dungeon", "walls": "marble"}, ["built", "hewn", "rough"]),
    ({"zone_type": "dungeon", "walls": 3}, ["built", "hewn", "rough"]),
    ({"zone_type": "city", "walls": "rough"}, ["dungeon", "outdoor_dungeon"]),
])
def test_a_bad_value_is_a_400_naming_the_choices(client, controls, named):
    r = client.post("/api/generate", json={"mode": "controls", "controls": controls})
    assert r.status_code == 400, r.text
    assert all(n in r.json()["detail"] for n in named), r.json()


def test_a_plan_rejects_a_bad_style_and_old_plans_still_load():
    with pytest.raises(ValueError, match="built, hewn, rough"):
        ZonePlan(name="x", zone_type="dungeon", walls="marble").validate()
    assert ZonePlan.from_dict({"name": "x", "zone_type": "dungeon"}).walls == ""


def test_cli_flag_reaches_the_build(monkeypatch, tmp_path):
    monkeypatch.setattr(tempfile, "tempdir", tempfile.tempdir)
    main.main(["generate", "w7", "--zone-type", "dungeon", "--rooms", "5", "--seed", "4",
               "--layout", "graph", "--walls", "hewn", "--output", str(tmp_path)])
    (path,) = tmp_path.glob("w7_*/v1/w7.zone.json")
    assert json.loads(path.read_text(encoding="utf-8"))["layout"]["walls"] == "hewn"


@pytest.mark.parametrize("argv", [["--walls", "marble"], ["--zone-type", "city", "--walls", "rough"]])
def test_cli_bad_use_is_a_usage_error(argv, monkeypatch, tmp_path):
    with pytest.raises(SystemExit):
        main.main(["generate", "w7", *argv, "--output", str(tmp_path)])


def test_the_page_carries_the_control():
    root = Path(__file__).resolve().parent.parent / "web"
    html = (root / "index.html").read_text(encoding="utf-8")
    assert 'id="walls"' in html and all(f'value="{s}"' in html for s in available_wall_styles())
    assert 'walls' in (root / "src" / "main.ts").read_text(encoding="utf-8")


def _rough(rooms=8):
    return ZonePlan(name="w7", zone_type="dungeon", room_count=rooms, layout="graph", walls="rough",
                    verticality="flat").validate()


def test_the_map_draws_outlines_not_boxes():
    spec = plan_to_spec(_rough(), seed=4)
    svg = render_map_svg(spec)
    assert svg.count("<polygon") >= len(spec.rooms)
    plain = plan_to_spec(ZonePlan(name="w7", zone_type="dungeon", room_count=8, layout="classic").validate(), seed=4)
    assert "<polygon" not in render_map_svg(plain)


@pytest.mark.slow
def test_eq_map_lines_follow_shaped_walls(tmp_path):
    """Req 11.3: the EQ map reads walls from the mesh, so its lines bend with them."""
    plan = _rough()
    vb = generate_validated(lambda s: plan_to_spec(plan, seed=s), zone_type="dungeon", zone_id="w7",
                            rng=random.Random(4), output_dir=tmp_path, failure_log=None,
                            max_attempts=3, timeout_s=300.0)
    files = sorted(vb.build_dir.glob("maps/*.txt"))
    assert files
    parsed = parse_map_layer(files[0].read_text(encoding="utf-8"))
    lines = parsed.layer.lines
    assert lines
    dirs = np.array([[ln.x2 - ln.x1, ln.y2 - ln.y1] for ln in lines])
    length = np.hypot(dirs[:, 0], dirs[:, 1])
    slanted = (np.abs(dirs[:, 0]) > 0.5) & (np.abs(dirs[:, 1]) > 0.5)
    assert length[slanted].sum() > 0.2 * length.sum(), "walls off the grid show on the map"
    # Each shaped room has map lines off its Box's sides: its real walls, not its Box.
    mids = np.array([map_to_world((ln.x1 + ln.x2) / 2, (ln.y1 + ln.y2) / 2, ln.z1)[:2] for ln in lines])
    for room in vb.spec.rooms:
        (x0, y0, _), (x1, y1, _) = room.bounds
        off_box = ((mids[:, 0] > x0 + 1) & (mids[:, 0] < x1 - 1)
                   & (mids[:, 1] > y0 + 1) & (mids[:, 1] < y1 - 1))
        assert off_box.any(), room.id
