"""
tests/test_decor_controls.py
----------------------------
Decor controls, the decor seed, and Props on the maps (room-decor spec task 10;
Reqs 10.1-10.4).

- The Decor control (none, sparse, normal, dense; unchosen builds normal) and the
  decor seed through the plan, the CLI, the server (``/api/controls`` lists the
  values) and prompt words.
- P10: a decor seed changes only Props: the ZON's ``decor_*`` objects and
  ``decor_light_*`` lights and the Prop models and their textures. Every other
  archive entry, and everything else in the ZON, is byte-identical.
- Floor Props' Footprints on the EQ map, Props on the web map, read back from the
  built ``.eqg`` and sidecar.

Builds with Props need the install (``EQ_PATH``); those tests skip without it.
Built ``.eqg`` files hold the client's art: they live in ``tmp_path`` only.
"""

from __future__ import annotations

import dataclasses
import json
import tempfile

import pytest
from fastapi.testclient import TestClient

import main
import server.app as app_mod
from ai.expand import plan_to_spec
from ai.rule_planner import RulePlanner
from ai.schema import DEFAULT_DECOR, VALID_DECOR, ZonePlan
from core.pfs import PfsArchive
from core.ter import TerFile
from core.zon import ZonFile
from generators.builder import ZoneBuilder
from generators.decor.stock import eq_path_from_env
from generators.eqmap import (PROP_COLOUR, MapLine, PropFootprint, PropMarks, build_map_file,
                              parse_map_layer, prop_marks)
from generators.mapview import render_map_svg

EQ = eq_path_from_env()
needs_install = pytest.mark.skipif(EQ is None, reason="EQ_PATH is not set (no EQ install to read)")


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

def test_the_lists_are_decors_own():
    from generators.decor.rules import CONTROLS, DEFAULT_CONTROL
    assert VALID_DECOR == list(CONTROLS) and DEFAULT_DECOR == DEFAULT_CONTROL


def test_the_plan_carries_them_to_the_spec_only_when_chosen():
    plan = ZonePlan.from_controls({"zone_type": "dungeon", "decor": "Dense", "decor_seed": 42})
    assert (plan.decor, plan.decor_seed) == ("dense", 42)
    spec = plan_to_spec(plan, seed=4)
    assert (spec.decor, spec.decor_seed) == ("dense", 42)
    # Unchosen: the spec is the one it always was (the pipeline builds normal).
    bare = plan_to_spec(ZonePlan.from_controls({"zone_type": "dungeon"}), seed=4)
    assert (bare.decor, bare.decor_seed) == (None, None)
    assert "decor" not in bare.to_dict() and "decor_seed" not in bare.to_dict()
    # The same zone either way: only the two fields differ.
    a, b = spec.to_dict(), bare.to_dict()
    a.pop("decor"), a.pop("decor_seed")
    assert a == b


@pytest.mark.parametrize("fields, message", [
    ({"decor": "lots"}, "decor 'lots' is not one of: none, sparse, normal, dense"),
    ({"decor_seed": -1}, "decor_seed -1 is not a whole number"),
    ({"decor_seed": 2 ** 31}, "is not a whole number"),
    ({"decor_seed": True}, "is not a whole number"),
    ({"decor_seed": 1.5}, "is not a whole number"),
])
def test_the_plan_refuses_bad_values(fields, message):
    with pytest.raises(ValueError, match=message):
        ZonePlan(zone_type="dungeon", **fields).validate()


@pytest.mark.parametrize("prompt, decor", [
    ("a cluttered goblin warren", "dense"),
    ("a richly furnished keep", "dense"),
    ("a bare tomb", "sparse"),
    ("a sparsely furnished crypt", "sparse"),
    ("an unfurnished fortress", "none"),
    ("a goblin warren", ""),                           # no word: the default
    ("a barely lit temple", ""),                       # "bare" only as a word
    ("a cluttered forest with orc camps", "dense"),    # Site Props (task 20)
])
def test_prompt_words_pick_decor(prompt, decor):
    assert RulePlanner().plan(prompt).decor == decor


# ---------------------------------------------------------------------------
# The CLI
# ---------------------------------------------------------------------------

def test_cli_options_reach_the_spec(monkeypatch, tmp_path):
    monkeypatch.setattr(tempfile, "tempdir", tempfile.tempdir)
    main.main(["generate", "d10", "--zone-type", "dungeon", "--seed", "4", "--rooms", "3",
               "--decor", "sparse", "--decor-seed", "5", "--output", str(tmp_path)])
    (path,) = tmp_path.glob("d10_*/v1/d10.json")
    spec = json.loads(path.read_text(encoding="utf-8"))
    assert (spec["decor"], spec["decor_seed"]) == ("sparse", 5)


@pytest.mark.parametrize("argv", [["--zone-type", "dungeon", "--decor", "lots"],
                                  ["--zone-type", "dungeon", "--decor-seed", "-3"]])
def test_cli_bad_use_is_a_usage_error(argv, tmp_path):
    with pytest.raises(SystemExit):
        main.main(["generate", "d10", *argv, "--output", str(tmp_path)])


# ---------------------------------------------------------------------------
# The server
# ---------------------------------------------------------------------------

def test_the_page_reads_the_list_from_the_server(client):
    r = client.get("/api/controls")
    assert r.status_code == 200
    assert r.json()["decor"] == {"values": VALID_DECOR, "default": DEFAULT_DECOR,
                                 "zone_types": ["dungeon", "city", "wilderness", "outdoor_dungeon"]}


@pytest.mark.parametrize("body, named", [
    ({"controls": {"zone_type": "dungeon", "decor": "lots"}}, VALID_DECOR),
    ({"controls": {"zone_type": "dungeon", "decor": 2}}, VALID_DECOR),
    ({"controls": {"zone_type": "dungeon", "decor_seed": "x"}}, ["decor_seed"]),
    ({"controls": {"zone_type": "dungeon", "decor_seed": -1}}, ["decor_seed"]),
    ({"controls": {"zone_type": "dungeon"}, "decor_seed": 2 ** 31}, ["decor_seed"]),
    ({"controls": {"zone_type": "dungeon"}, "decor_seed": 1.5}, ["decor_seed"]),
])
def test_a_bad_value_is_a_400_naming_the_choices(client, body, named):
    r = client.post("/api/generate", json={"mode": "controls", **body})
    assert r.status_code == 400, r.text
    assert all(n in r.json()["detail"] for n in named), r.json()


@pytest.mark.slow
@needs_install
def test_reroll_decor_changes_only_the_props_and_both_maps_show_them(client):
    """What the page's "Reroll decor" sends: the same request, its seed pinned,
    a fresh top-level decor seed. Same zone, other Props, on both maps."""
    body = {"mode": "controls", "seed": 4, "controls": {"zone_type": "dungeon", "decor": "dense"}}
    first = client.post("/api/generate", json=body)
    again = client.post("/api/generate", json={**body, "decor_seed": 99})
    assert first.status_code == 200 and again.status_code == 200, (first.text, again.text)
    a, b = first.json(), again.json()
    assert (a["plan"]["decor_seed"], b["plan"]["decor_seed"]) == (None, 99)
    assert {**a["plan"], "decor_seed": 99, "name": ""} == {**b["plan"], "name": ""}

    def built(body):
        build = app_mod.OUTPUT_DIR / body["id"] / "v1"
        side = json.loads((build / f"{body['id']}.zone.json").read_text(encoding="utf-8"))
        return build, side

    (_, sa), (build, sb) = built(a), built(b)
    assert (sa["decor"]["control"], sa["decor"]["seed"]) == ("dense", 4)
    assert (sb["decor"]["control"], sb["decor"]["seed"]) == ("dense", 99)
    rows = lambda s: [(p["key"], p["x"], p["y"]) for r in s["rooms"] for p in r.get("props", [])]
    assert rows(sa) != rows(sb)
    assert [r["center"] for r in sa["rooms"]] == [r["center"] for r in sb["rooms"]]

    props = [p for r in sb["rooms"] for p in r.get("props", [])]
    floor = sum(1 for p in props if p["mount"] == "floor")
    svg = (build / f"{b['id']}.map.svg").read_text(encoding="utf-8")
    assert svg.count('class="prop-footprint"') == floor > 0
    assert svg.count('class="prop"') == len(props) - floor
    assert ">prop</text>" in svg
    layers = [parse_map_layer(p.read_text(encoding="utf-8")).layer for p in sorted(build.glob("maps/*.txt"))]
    lines = [l for layer in layers for l in layer.lines if (l.r, l.g, l.b) == PROP_COLOUR]
    assert len(lines) >= 3 * floor


# ---------------------------------------------------------------------------
# The maps (no install needed)
# ---------------------------------------------------------------------------

def _square(name="decor_0000", kind="table", z=0.0, x=0.0, y=0.0):
    return PropFootprint(name, kind, z, ((x, y), (x + 4, y), (x + 4, y + 4), (x, y + 4)))


def test_the_maps_draw_floor_footprints_and_are_unchanged_without_props():
    spec = plan_to_spec(ZonePlan.from_controls({"zone_type": "dungeon", "room_count": 3}), seed=4)
    room = spec.rooms[0]
    marks = PropMarks((_square(z=room.floor_z, x=room.center_x, y=room.center_y),),
                      ((room.center_x, room.center_y, room.floor_z, "floor"),
                       (room.center_x + 3, room.center_y, room.floor_z + 5, "wall")))
    plain = render_map_svg(spec)
    assert render_map_svg(spec, props=PropMarks()) == plain
    svg = render_map_svg(spec, props=marks)
    assert svg.count('class="prop-footprint"') == 1 and svg.count('class="prop"') == 1
    assert "<title>table</title>" in svg and ">prop</text>" in svg

    from generators.mapgeom import DepthBand, OutlineSet
    outline = OutlineSet(polylines=(), bands=(DepthBand(0, -1e9, 1e9, 0.0, "main", 0),),
                         bounds=(0, 0, 0, 1, 1, 1), seed_face=0, reachable_only=True)
    mf = build_map_file(outline, spec, "d", props=marks)
    lines = [l for layer in mf.layers for l in layer.lines]
    assert lines == [l for l in lines if (l.r, l.g, l.b) == PROP_COLOUR] and len(lines) == 4
    assert all(isinstance(l, MapLine) for l in lines)
    assert build_map_file(outline, spec, "d").layers[0].lines == []


# ---------------------------------------------------------------------------
# P10: a decor seed changes only Props
# ---------------------------------------------------------------------------

def _build(tmp_path, decor_seed):
    spec = plan_to_spec(ZonePlan(name="p10", zone_type="dungeon").validate(), seed=4)
    spec.decor, spec.decor_seed = "dense", decor_seed
    return ZoneBuilder(spec).build(output_dir=tmp_path / f"s{decor_seed}", write_glb=False)


def _prop_files(arc: PfsArchive, zon: ZonFile) -> set:
    """The Prop models the ZON's ``decor_*`` objects place, and every file
    their materials name (lower case)."""
    files = {zon.models[o.model_id] for o in zon.objects if o.name.startswith("decor_")}
    out = {f.lower() for f in files}
    for f in files:
        for mat in TerFile.from_bytes(arc.get(f), name=f).materials:
            out |= {p.value_s.lower() for p in mat.properties if getattr(p, "value_s", None)}
    return out


def _not_props(zon: ZonFile) -> dict:
    """Everything in the ZON that isn't a Prop, with model ids as names."""
    objs = [{**dataclasses.asdict(o), "model_id": zon.models[o.model_id]}
            for o in zon.objects if not o.name.startswith("decor_")]
    used = {zon.models[o.model_id] for o in zon.objects if not o.name.startswith("decor_")}
    return {"objects": objs, "regions": [dataclasses.asdict(r) for r in zon.regions],
            "lights": [dataclasses.asdict(l) for l in zon.lights if not l.name.startswith("decor_light_")],
            "models": [m for m in zon.models if m in used or m.lower().endswith(".ter")]}


@pytest.mark.slow
@needs_install
def test_p10_a_decor_seed_changes_only_props(tmp_path):
    builds = [_build(tmp_path, s) for s in (1, 2)]
    arcs = [PfsArchive.from_file(b.eqg_path) for b in builds]
    zons = []
    for arc in arcs:
        (name,) = [f for f in arc.list_files() if f.lower().endswith(".zon")]
        zons.append((name, ZonFile.from_bytes(arc.get(name))))
    props = [_prop_files(arc, zon) for arc, (_, zon) in zip(arcs, zons)]
    rest = [{f: arc.get(f) for f in arc.list_files()
             if f.lower() not in prop and not f.lower().endswith(".zon")}
            for arc, prop in zip(arcs, props)]
    assert rest[0].keys() == rest[1].keys() and len(rest[0]) > 2
    assert all(rest[0][f] == rest[1][f] for f in rest[0]), \
        [f for f in rest[0] if rest[0][f] != rest[1][f]]
    assert _not_props(zons[0][1]) == _not_props(zons[1][1])

    # The Props did change, and the maps read every one of them back.
    placed = [[(o.model_id, round(o.x, 2), round(o.y, 2)) for o in zon.objects
               if o.name.startswith("decor_")] for _, zon in zons]
    assert placed[0] and placed[0] != placed[1]
    side = json.loads(builds[1].sidecar_path.read_text(encoding="utf-8"))
    marks = prop_marks(builds[1].eqg_path, side)
    rows = [p for r in side["rooms"] for p in r.get("props", [])]
    assert len(marks.points) == len(rows) == side["decor"]["props"]
    assert len(marks.footprints) == sum(1 for p in rows if p["mount"] == "floor")
