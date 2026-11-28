"""
tests/test_decor_layers_build.py
--------------------------------
Decor layers through the build (decor-rules spec task 2; Reqs 2.2-2.5).

- ``ZonePlan.decor_layers`` is checked against ``rules/decor/layers/``: an unknown
  name is refused naming the known ones, on the plan, the CLI (exit 2) and the
  server (a 400); ``/api/controls`` lists the folder's layers with their
  descriptions.
- The layers ride beside the Zone_Spec, never in it: the spec's dict is the same
  with or without them. The builder loads the theme map's layers plus the
  request's, cached per tuple of names.
- With the install (``EQ_PATH``; these skip without it): a build naming a test
  layer gets its Props and records ``decor.layers``; the same build naming none
  is byte-identical to one that never heard of layers, with no ``layers`` key.

The test layer lives in a temporary copy of ``rules/decor`` (``ai.schema.RULES_DECOR_DIR``
points at it), so the shipped folder is never touched.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
import server.app as app_mod
from ai import schema
from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators import builder
from generators.builder import ZoneBuilder, decor_layers_of, with_decor_layers
from generators.decor.stock import eq_path_from_env

EQ = eq_path_from_env()
needs_install = pytest.mark.skipif(EQ is None, reason="EQ_PATH is not set (no EQ install to read)")

LAYER = "deco_test"
DESCRIPTION = "Two more lights on every room's walls (a test layer)"
LAYER_TOML = f'''
[layer]
name        = "{LAYER}"
description = "{DESCRIPTION}"

[every]
mode  = "add"
props = [ {{ kind = ["torch", "lantern", "lamp"], at = "on_wall", count = 2 }} ]
'''


@pytest.fixture
def rules_dir(tmp_path, monkeypatch):
    """A copy of ``rules/decor`` holding the test layer, as the folder everything reads."""
    shipped = Path(schema.RULES_DECOR_DIR)
    d = tmp_path / "decor"
    (d / "layers").mkdir(parents=True)
    for name in ("rooms.toml", "sets.toml", "tags.toml"):
        shutil.copy(shipped / name, d / name)
    (d / "layers" / f"{LAYER}.toml").write_text(LAYER_TOML, encoding="utf-8")
    monkeypatch.setattr(schema, "RULES_DECOR_DIR", d)
    return d


@pytest.fixture
def client(tmp_path, monkeypatch):
    out = tmp_path / "web_out"
    out.mkdir()
    monkeypatch.setattr(app_mod, "OUTPUT_DIR", out)
    monkeypatch.setattr(app_mod, "FAILURE_LOG", tmp_path / "failures.jsonl")
    return TestClient(app_mod.app)


# ---------------------------------------------------------------------------
# The plan
# ---------------------------------------------------------------------------

def test_the_plan_takes_known_layers_once_and_leaves_none_out_of_its_dict(rules_dir):
    plan = ZonePlan.from_controls({"zone_type": "dungeon", "decor_layers": [LAYER, LAYER]})
    assert plan.decor_layers == (LAYER,)
    assert plan.to_dict()["decor_layers"] == [LAYER]
    assert ZonePlan.from_saved(plan.to_dict()).decor_layers == (LAYER,)
    assert "decor_layers" not in ZonePlan.from_controls({"zone_type": "dungeon"}).to_dict()


@pytest.mark.parametrize("value", ["nope", ["nope"], [LAYER, "nope"], 3, [3]])
def test_the_plan_refuses_an_unknown_layer_naming_the_known(rules_dir, value):
    with pytest.raises(ValueError, match="decor_layers") as e:
        ZonePlan(zone_type="dungeon", decor_layers=value).validate()
    if value != 3 and value != [3]:
        assert LAYER in str(e.value)


def test_the_layers_stay_out_of_the_spec(rules_dir):
    plan = ZonePlan.from_controls({"zone_type": "dungeon", "room_count": 3, "decor_layers": [LAYER]})
    spec = with_decor_layers(plan_to_spec(plan, seed=4), plan.decor_layers)
    bare = plan_to_spec(ZonePlan.from_controls({"zone_type": "dungeon", "room_count": 3}), seed=4)
    assert spec.to_dict() == bare.to_dict()
    assert decor_layers_of(spec) == (LAYER,) and decor_layers_of(bare) == ()


def test_the_theme_map_comes_first(rules_dir):
    (rules_dir / "layers" / "other.toml").write_text(
        '[layer]\nname = "other"\ndescription = "x"\n', encoding="utf-8")
    (rules_dir / "themes.toml").write_text('tomb = { layers = ["other"] }\n', encoding="utf-8")
    spec = with_decor_layers(plan_to_spec(ZonePlan(zone_type="dungeon", dungeon_theme="tomb",
                                                   room_count=3).validate(), seed=4),
                             [LAYER, "other"])
    assert decor_layers_of(spec) == ("other", LAYER)


def test_the_rules_are_cached_per_tuple_of_layers(rules_dir):
    from generators.decor.rules import load_decor
    base, cat = builder._decor_data(())
    assert builder._decor_data(())[0] is base and base == load_decor(rules_dir)
    layered, cat2 = builder._decor_data((LAYER,))
    assert layered is builder._decor_data((LAYER,))[0] and cat2 is cat
    assert layered.layers == (LAYER,) and base.layers == ()
    assert len(layered.every.lines) == len(base.every.lines) + 1


# ---------------------------------------------------------------------------
# The CLI and the server
# ---------------------------------------------------------------------------

def test_the_cli_refuses_an_unknown_layer(rules_dir, tmp_path, capsys):
    with pytest.raises(SystemExit) as e:
        main.main(["generate", "d15", "--zone-type", "dungeon", "--decor-layer", "nope",
                   "--output", str(tmp_path / "out")])
    assert e.value.code == 2
    assert "nope" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_the_cli_names_the_known_layers(rules_dir, tmp_path, capsys):
    with pytest.raises(SystemExit):
        main.main(["generate", "d15", "--decor-layer", "nope", "--output", str(tmp_path / "out")])
    assert LAYER in capsys.readouterr().err


@pytest.mark.parametrize("value", ["nope", ["nope"], [LAYER, "nope"], 7])
def test_the_server_refuses_an_unknown_layer_with_a_400(rules_dir, client, value):
    r = client.post("/api/generate", json={"mode": "controls",
                                           "controls": {"zone_type": "dungeon", "decor_layers": value}})
    assert r.status_code == 400, r.text
    assert "decor_layers" in r.json()["detail"]
    if value != 7:
        assert LAYER in r.json()["detail"]


def test_api_controls_lists_the_folders_layers(rules_dir, client):
    r = client.get("/api/controls")
    assert r.status_code == 200
    assert r.json()["decor_layers"] == [{"name": LAYER, "description": DESCRIPTION}]
    # A dropped-in file shows up on the next call.
    (rules_dir / "layers" / "late.toml").write_text(
        '[layer]\nname = "late"\ndescription = "dropped in"\n', encoding="utf-8")
    names = [x["name"] for x in client.get("/api/controls").json()["decor_layers"]]
    assert names == [LAYER, "late"]


# ---------------------------------------------------------------------------
# Builds (with the install)
# ---------------------------------------------------------------------------

def _eqg_hash(path) -> str:
    return hashlib.sha256(path.read_bytes()[:-4]).hexdigest()


def _props(side) -> list:
    return [p for r in side["rooms"] + side.get("corridors", []) for p in r.get("props", [])]


def _build(out, layers=None):
    spec = plan_to_spec(ZonePlan(name="dl", zone_type="dungeon").validate(), seed=4)
    spec.decor = "normal"
    if layers is not None:
        with_decor_layers(spec, layers)
    result = ZoneBuilder(spec).build(output_dir=out, write_glb=False)
    return result, json.loads(result.sidecar_path.read_text(encoding="utf-8"))


@pytest.mark.slow
@needs_install
def test_a_build_naming_a_layer_gets_its_props(rules_dir, tmp_path):
    plain, side_plain = _build(tmp_path / "plain")
    none, side_none = _build(tmp_path / "none", ())
    layered, side = _build(tmp_path / "layered", (LAYER,))
    # Naming none is the build that never heard of layers.
    assert _eqg_hash(none.eqg_path) == _eqg_hash(plain.eqg_path)
    assert side_none["decor"] == side_plain["decor"] and "layers" not in side_plain["decor"]
    # Naming the layer: its lines placed Props, and the sidecar says what was used.
    assert side["decor"]["layers"] == [LAYER]
    mine = [p for p in _props(side) if p["line"].startswith(f"{LAYER}.toml")]
    assert mine, sorted({p["line"] for p in _props(side)})
    assert _eqg_hash(layered.eqg_path) != _eqg_hash(plain.eqg_path)
    # The geometry is the same: only Decor read it.
    assert [r["center"] for r in side["rooms"]] == [r["center"] for r in side_plain["rooms"]]


@pytest.mark.slow
@needs_install
def test_the_server_builds_with_the_layer(rules_dir, client):
    body = {"mode": "controls", "seed": 4,
            "controls": {"zone_type": "dungeon", "room_count": 3, "decor": "normal",
                         "decor_layers": [LAYER]}}
    r = client.post("/api/generate", json=body)
    assert r.status_code == 200, r.text
    zone = r.json()["id"]
    side = json.loads((app_mod.OUTPUT_DIR / zone / "v1" / f"{zone}.zone.json").read_text(encoding="utf-8"))
    assert r.json()["plan"]["decor_layers"] == [LAYER]
    assert side["decor"]["layers"] == [LAYER]
    assert any(p["line"].startswith(f"{LAYER}.toml") for p in _props(side))


@pytest.mark.slow
@needs_install
def test_the_cli_builds_with_the_layer(rules_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", tempfile.tempdir)
    main.main(["generate", "d15", "--zone-type", "dungeon", "--seed", "4", "--rooms", "3",
               "--decor", "normal", "--decor-layer", LAYER, "--no-validate", "--output", str(tmp_path)])
    (path,) = tmp_path.glob("d15_*/v1/d15.zone.json")
    side = json.loads(path.read_text(encoding="utf-8"))
    assert side["decor"]["layers"] == [LAYER]
    assert any(p["line"].startswith(f"{LAYER}.toml") for p in _props(side))
    (spec_path,) = tmp_path.glob("d15_*/v1/d15.json")
    assert "decor_layers" not in json.loads(spec_path.read_text(encoding="utf-8"))
