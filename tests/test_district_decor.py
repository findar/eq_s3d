"""
tests/test_district_decor.py
----------------------------
Decor per District (district-looks task 2, Req 2, A1).

- In a dungeon whose ``cave`` District follows a ``fortress`` District, each room's Props come
  from its own District's layers: the cave rooms' from ``layers/cave.toml`` and the shared base
  (``rooms.toml``), never a bench or a banner; the fortress rooms' never from the cave layer.
  A corridor takes the layers of the room it leaves (``from_room``); a Threshold the outer
  District's (the lower District id), whichever end it was drawn from.
- The sidecar's ``decor`` block names each District's layers under ``districts``; a one-District
  build's block has no such key (its bytes are the byte check's).
- ``BareCap`` stays one zone-wide cap, each room's bare chance read from its own District's rules.
- The room view (``room_view.decorate_room`` with the sidecar's ``decor.districts``, task 9) and
  ``scripts/stage.py decor`` on the build's rooms file give every room and corridor the Props the
  build placed; without the record (an old sidecar) they dress every room with the zone's layers.

The builds need the install (``EQ_PATH``) and skip without it; they live in ``tmp_path`` only.
"""

from __future__ import annotations

import json
import math
from types import SimpleNamespace

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators import builder
from generators.builder import BareCap, ZoneBuilder, decor_layers_of
from generators.decor.rules import BARE
from generators.decor.stock import eq_path_from_env

EQ = eq_path_from_env()
needs_install = pytest.mark.skipif(EQ is None, reason="EQ_PATH is not set (no EQ install to read)")

#: A pinned seed whose fortress-then-cave dungeon builds first time with both Districts.
SEED = 3
BUILT = ("bench", "banner")
#: A Prop's spot, which the build settles onto its walls and the stage command doesn't.
WHERE = ("x", "y", "z", "yaw")


def _plan(**kw):
    base = dict(name="dd", zone_type="dungeon", room_count=12, districts=True,
                district_plan=[{"purpose": "fortress"}, {"purpose": "cave"}])
    base.update(kw)
    return ZonePlan(**base).validate()


def _file(prop) -> str:
    """The rules file a Prop's line was written in: ``rooms.toml``, ``cave.toml``, ..."""
    return prop["line"].split(" ", 1)[0]


@pytest.fixture(scope="module")
def districted_build(tmp_path_factory):
    """The build's folder (its ``.eqg``, sidecar and hand-offs, as the pipeline leaves it)."""
    spec = plan_to_spec(_plan(), seed=SEED)
    assert [d.purpose for d in spec.districts] == ["fortress", "cave"]
    spec.decor = "normal"
    out = tmp_path_factory.mktemp("dd")
    result = ZoneBuilder(spec).build(output_dir=out, write_glb=False)
    for fname, text in result.handoffs().items():
        (out / fname).write_text(text, encoding="utf-8")
    return spec, json.loads(result.sidecar_path.read_text(encoding="utf-8")), out


@pytest.fixture(scope="module")
def districted(districted_build):
    spec, side, _out = districted_build
    return spec, side


@needs_install
def test_each_district_s_rooms_take_its_own_layers(districted):
    spec, side = districted
    theme = {r.id: r.room_theme for r in spec.rooms}
    cave_files, fortress_files = set(), set()
    for r in side["rooms"]:
        files = {_file(p) for p in r["props"]}
        if theme[r["id"]] == "cave":
            cave_files |= files
            assert files <= {"rooms.toml", "cave.toml"}, (r["id"], files)
            assert not [p["kind"] for p in r["props"] if p["kind"] in BUILT], r["id"]
        else:
            assert theme[r["id"]] == "fortress"
            fortress_files |= files
            assert "cave.toml" not in files, (r["id"], files)
    assert "cave.toml" in cave_files                # the cave layer did dress the cave
    assert fortress_files                           # and the fortress was dressed at all


@needs_install
def test_corridors_take_their_from_room_s_layers(districted):
    spec, side = districted
    theme = {r.id: r.room_theme for r in spec.rooms}
    district = {r.id: r.district for r in spec.rooms}
    threshold = {c.id for c in spec.corridors if c.threshold}
    seen = set()
    for c in side["corridors"]:
        files = {_file(p) for p in c["props"]}
        look = c["from_room"]
        if c["id"] in threshold and district[c["to_room"]] < district[look]:
            look = c["to_room"]                     # a Threshold looks like the outer District
        seen.add(theme[look])
        if theme[look] == "cave":
            assert files <= {"rooms.toml", "cave.toml"}, (c["id"], files)
        else:
            assert "cave.toml" not in files, (c["id"], files)
    assert seen == {"fortress", "cave"}


@needs_install
def test_the_record_names_each_district_s_layers(districted):
    _spec, side = districted
    decor = side["decor"]
    assert "layers" not in decor                    # the zone's (District 0's) take none
    assert decor["districts"] == [{"id": 0, "theme": "fortress", "layers": []},
                                  {"id": 1, "theme": "cave", "layers": ["cave"]}]


@needs_install
def test_a_one_district_build_records_no_districts(tmp_path):
    spec = plan_to_spec(ZonePlan(name="one", zone_type="dungeon", room_count=8,
                                 dungeon_theme="cave").validate(), seed=SEED)
    assert not spec.districts
    spec.decor = "normal"
    side = json.loads(ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)
                      .sidecar_path.read_text(encoding="utf-8"))
    assert "districts" not in side["decor"] and side["decor"]["layers"] == ["cave"]


def test_the_bare_cap_reads_each_room_s_own_rules():
    """One zone-wide cap: ceil of the rooms' summed bare chances, each from its own rules."""
    spec = plan_to_spec(_plan(), seed=SEED)
    rules = {t: builder._decor_data(decor_layers_of(spec, t))[0] for t in ("fortress", "cave")}
    rooms = [SimpleNamespace(source="room", zone_type="dungeon", race="", theme=r.room_theme,
                             kind=r.kind, room_type=r.semantic_type) for r in spec.rooms]
    want = math.ceil(sum(rules[c.theme].weights_for(c.zone_type, c.race, c.theme, c.kind,
                                                    c.room_type, "normal")[BARE]
                         for c in rooms) - 1e-9)
    assert BareCap(rooms, rules["fortress"], "normal", lambda c: rules[c.theme]).left == want
    one = math.ceil(sum(rules["fortress"].weights_for(c.zone_type, c.race, c.theme, c.kind,
                                                      c.room_type, "normal")[BARE]
                        for c in rooms) - 1e-9)
    assert BareCap(rooms, rules["fortress"], "normal").left == one


def _built_props(side) -> dict:
    """Each room's and corridor's Props as the build placed them, by id."""
    want = {r["id"]: r.get("props", []) for r in side["rooms"]}
    want.update({c["id"]: c.get("props", []) for c in side.get("corridors", [])})
    return want


@needs_install
def test_the_room_view_gives_each_district_the_build_s_props(districted_build):
    """Room view per District (task 9): every room and corridor re-decorated from the build
    folder, with the record, gives the build's Props and names its own District's layers."""
    from generators.decor.room_view import decorate_room, load_build
    spec, side, out = districted_build
    b = load_build(out, "dd")
    assert b.districts == side["decor"]["districts"]
    layers = {d["theme"]: d["layers"] for d in b.districts}
    theme = {c.id: c.theme for c in b.contexts}
    want = _built_props(side)
    assert {theme[k] for k, v in want.items() if v} == {"fortress", "cave"}
    for cid, props in want.items():
        _glb, rep = decorate_room(b.contexts, cid, seed=b.seed, control=b.control, layers=b.layers,
                                  eq_path=EQ, mesh=b.mesh, room_seeds=b.room_seeds,
                                  districts=b.districts)
        assert rep["props"] == props, cid
        assert rep["layers"] == layers[theme[cid]], cid


@needs_install
def test_without_the_record_the_room_view_takes_the_zone_s_layers(districted_build):
    """An old sidecar (no ``decor.districts``): every room as before, on the zone's layers, so a
    cave room is dressed as a fortress one (the build's Props differ there)."""
    from generators.decor.room_view import decorate_room, load_build
    _spec, side, out = districted_build
    b = load_build(out, "dd")
    cave = [c.id for c in b.contexts if c.source == "room" and c.theme == "cave"]
    want = _built_props(side)
    got = {}
    for cid in cave:
        _glb, rep = decorate_room(b.contexts, cid, seed=b.seed, control=b.control, layers=b.layers,
                                  eq_path=EQ, mesh=b.mesh, room_seeds=b.room_seeds)
        assert rep["layers"] == list(b.layers), cid
        assert "cave.toml" not in {_file(p) for p in rep["props"]}, cid
        got[cid] = rep["props"]
    assert got != {cid: want[cid] for cid in cave}


@needs_install
def test_stage_decor_on_the_hand_off_equals_the_build(districted_build, tmp_path):
    """``scripts/stage.py decor`` on the build's rooms file (its sidecar beside it) places each
    room and corridor as the build did: the same Props from the same rule lines. The stage
    never settles them onto the built walls (it has no mesh), so where they stand is
    placement's, not the build's settled spot."""
    import importlib.util
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    mod_spec = importlib.util.spec_from_file_location("stage_t9", root / "scripts" / "stage.py")
    stage = importlib.util.module_from_spec(mod_spec)
    mod_spec.loader.exec_module(stage)
    _spec, side, out = districted_build
    assert stage.main(["decor", str(out / "dd.rooms.json"), "--out", str(tmp_path), "--boxes"]) == 0
    doc = json.loads((tmp_path / "dd.decor.json").read_text(encoding="utf-8"))
    def chosen(props):
        return [{k: v for k, v in p.items() if k not in WHERE} for p in props]
    got = {r["id"]: chosen(r["props"]) for r in doc["rooms"]}
    want = {k: chosen(v) for k, v in _built_props(side).items()}
    assert got == want
    assert {_file(p) for v in _built_props(side).values() for p in v} >= {"cave.toml"}