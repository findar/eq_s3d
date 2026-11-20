"""
tests/test_district_decor.py
----------------------------
Decor per District (district-looks task 2, Req 2, A1).

- In a dungeon whose ``cave`` District follows a ``fortress`` District, each room's Props come
  from its own District's layers: the cave rooms' from ``layers/cave.toml`` and the shared base
  (``rooms.toml``), never a bench or a banner; the fortress rooms' never from the cave layer.
  A corridor takes the layers of the room it leaves (``from_room``).
- The sidecar's ``decor`` block names each District's layers under ``districts``; a one-District
  build's block has no such key (its bytes are the byte check's).
- ``BareCap`` stays one zone-wide cap, each room's bare chance read from its own District's rules.

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


def _plan(**kw):
    base = dict(name="dd", zone_type="dungeon", room_count=12, districts=True,
                district_plan=[{"purpose": "fortress"}, {"purpose": "cave"}])
    base.update(kw)
    return ZonePlan(**base).validate()


def _file(prop) -> str:
    """The rules file a Prop's line was written in: ``rooms.toml``, ``cave.toml``, ..."""
    return prop["line"].split(" ", 1)[0]


@pytest.fixture(scope="module")
def districted(tmp_path_factory):
    spec = plan_to_spec(_plan(), seed=SEED)
    assert [d.purpose for d in spec.districts] == ["fortress", "cave"]
    spec.decor = "normal"
    result = ZoneBuilder(spec).build(output_dir=tmp_path_factory.mktemp("dd"), write_glb=False)
    return spec, json.loads(result.sidecar_path.read_text(encoding="utf-8"))


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
    seen = set()
    for c in side["corridors"]:
        files = {_file(p) for p in c["props"]}
        seen.add(theme[c["from_room"]])
        if theme[c["from_room"]] == "cave":
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
