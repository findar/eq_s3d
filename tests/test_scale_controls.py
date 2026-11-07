"""Room layouts task 21 (Requirement 15): Finish, Structure, Clutter and Overlay."""

from pathlib import Path
from statistics import mean

import pytest
from fastapi.testclient import TestClient

import main
from ai.expand import plan_to_spec
from ai.schema import ZonePlan, available_overlays
from generators.builder import ZoneBuilder
from server.app import app

WEB = Path(__file__).resolve().parent.parent / "web"


def _spec(seed=3, **kw):
    fields = {"name": "sc", "zone_type": "dungeon", "room_count": 16, "layout": "graph", "verticality": "flat", **kw}
    return plan_to_spec(ZonePlan(**fields).validate(), seed=seed)


def _values(scale, **kw):
    return [r["scales"][scale] for seed in (1, 2, 3) for r in _spec(seed, **kw).layout["rooms"].values()]


@pytest.mark.parametrize("scale", ["finish", "structure", "clutter"])
def test_a_number_leans_each_scale_its_way(scale):
    low, high = mean(_values(scale, **{scale: 1})), mean(_values(scale, **{scale: 9}))
    assert low < 3 < 7 < high


def test_a_number_is_a_lean_not_a_pin():
    assert len(set(_values("finish", finish=5))) > 1


def test_from_rules_is_the_default_and_the_same_as_before():
    plan = ZonePlan(name="sc", zone_type="dungeon").validate()
    assert (plan.finish, plan.structure, plan.clutter, plan.overlay) == (None, None, None, "")
    assert _spec(finish=None).to_dict() == _spec().to_dict()


def test_empty_reads_as_from_rules():
    plan = ZonePlan(name="sc", zone_type="dungeon", finish="", overlay="").validate()
    assert plan.finish is None and plan.overlay == ""


@pytest.mark.parametrize("field, value", [("finish", 11), ("clutter", -1), ("structure", "lots"), ("finish", True),
                                          ("clutter", 2.5), ("overlay", "haunted")])
def test_a_bad_value_is_refused(field, value):
    with pytest.raises(ValueError, match=field):
        ZonePlan(name="sc", zone_type="dungeon", **{field: value}).validate()


def test_an_overlay_multiplies_in():
    assert mean(_values("clutter", overlay="fresh_dig")) > mean(_values("clutter", overlay="reclaimed"))


def test_the_control_overlay_wins_over_an_outdoor_dungeons_own(monkeypatch):
    seen = []

    class Stop(Exception):
        pass

    def spy(spec, seed, overlay="", rules=None, asked=None):
        seen.append(overlay)
        raise Stop
    monkeypatch.setattr("generators.room_scales.draw_room_scales", spy)
    for kw, want in (({}, "natural_cave"), ({"overlay": "ruined"}, "ruined")):
        with pytest.raises(Stop):
            plan_to_spec(ZonePlan(name="sc", zone_type="outdoor_dungeon", room_count=6, **kw).validate(), seed=1)
        assert seen[-1] == want


def test_old_plans_load():
    walled = _spec(walls="hewn")
    assert {r["style"] for r in walled.layout["rooms"].values()} == {"hewn"}
    assert not any(r.features for r in _spec(features="none").rooms)
    count = {d: sum(len(r.features) for s in (1, 2, 3) for r in _spec(s, features=d).rooms)
             for d in ("sparse", "dense")}
    assert count["sparse"] < count["dense"]


def test_a_pinned_seed_still_gives_the_same_bytes(tmp_path):
    def eqg(sub):
        spec = _spec(5, finish=8, clutter=2, overlay="ruined")
        return ZoneBuilder(spec).build(output_dir=tmp_path / sub, write_glb=False).eqg_path.read_bytes()[:-4]
    assert eqg("a") == eqg("b")


def test_the_cli_takes_them(monkeypatch, tmp_path):
    class Stop(Exception):
        pass

    def spy(controls, warnings=None):
        assert controls["finish"] == 3 and controls["overlay"] == "ruined" and "clutter" not in controls
        raise Stop
    monkeypatch.setattr(main.ZonePlan, "from_controls", spy)
    with pytest.raises(Stop):
        main.main(["generate", "sc", "--zone-type", "dungeon", "--finish", "3", "--overlay", "ruined",
                   "--output", str(tmp_path)])


@pytest.mark.parametrize("argv", [["--zone-type", "wilderness", "--clutter", "3"],
                                  ["--zone-type", "dungeon", "--finish", "11"]])
def test_the_cli_refuses_what_it_should(argv, tmp_path):
    with pytest.raises(SystemExit):
        main.main(["generate", "sc", *argv, "--output", str(tmp_path)])


@pytest.mark.parametrize("body, status", [
    ({"zone_type": "dungeon", "finish": 12}, 400),
    ({"zone_type": "dungeon", "overlay": "haunted"}, 400),
    ({"zone_type": "wilderness", "clutter": 3}, 400),
    ({"zone_type": "wilderness", "overlay": "ruined"}, 400),
])
def test_the_server_refuses_what_it_should(body, status):
    r = TestClient(app).post("/api/generate", json={"mode": "controls", "controls": {"room_count": 4, **body}})
    assert r.status_code == status, r.text


def test_the_panel_has_them_in_place_of_walls_and_features():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    for id_ in ("finish", "structure", "clutter", "overlay"):
        assert f'id="{id_}"' in html
    assert 'id="walls"' not in html and 'id="features"' not in html
    assert all(f'value="{o}"' in html for o in available_overlays())
