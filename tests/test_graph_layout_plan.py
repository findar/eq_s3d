"""
tests/test_graph_layout_plan.py
-------------------------------
Graph-layout task 9 (Req 7.2-7.5): the plan's ``layout`` / ``rule_set``
fields, ``expand`` choosing the engine and the rule set, each theme's room
kind -> room type map, and the sidecar's ``layout`` block.

Classic output staying byte-identical is pinned by the task 2 goldens in
``tests/test_layout_engine.py``.
"""

import json

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan, available_rule_sets
from generators import semantics
from generators.builder import ZoneBuilder
from generators.topology.graph import ROOM_KINDS
from generators.zone_spec import ZoneSpec


def _graph_spec(theme="", rooms=10, seed=3, **kw):
    plan = ZonePlan(name="gp", room_count=rooms, layout="graph",
                    dungeon_theme=theme, **kw)
    return plan_to_spec(plan.validate(), seed=seed)


# --- the plan fields --------------------------------------------------------

def test_plan_defaults_and_legacy():
    plan = ZonePlan.from_dict({"zone_type": "dungeon", "room_count": 6})
    assert (plan.layout, plan.rule_set) == ("classic", "")
    again = ZonePlan.from_dict(ZonePlan(layout="graph", rule_set="warren").to_dict())
    assert (again.layout, again.rule_set) == ("graph", "warren")


def test_rule_sets_are_discovered():
    assert {"classic_eq", "warren"} <= set(available_rule_sets())
    assert "themes" not in available_rule_sets()


@pytest.mark.parametrize("field,value,allowed", [
    ("layout", "maze", "classic, graph"),
    ("rule_set", "nope", "classic_eq"),
])
def test_unknown_value_names_the_allowed(field, value, allowed):
    with pytest.raises(ValueError) as e:
        ZonePlan.from_dict({field: value})
    assert value in str(e.value) and allowed in str(e.value)


def test_other_zone_types_ignore_the_toggle():
    spec = plan_to_spec(ZonePlan(name="c", zone_type="city", room_count=5,
                                 layout="graph").validate(), seed=2)
    assert spec.layout is None and all(not r.kind for r in spec.rooms)


# --- expand: engine and rule set ---------------------------------------------

def test_classic_spec_has_no_layout():
    spec = plan_to_spec(ZonePlan(name="c", room_count=6).validate(), seed=1)
    assert spec.layout is None
    d = spec.to_dict()
    assert "layout" not in d and all("kind" not in r for r in d["rooms"])


@pytest.mark.parametrize("theme,base,layers", [
    ("warren", "warren", []),
    ("temple", "classic_eq", ["temple"]),
    ("fortress", "classic_eq", []),
    ("", "classic_eq", []),
])
def test_theme_picks_the_set(theme, base, layers):
    spec = _graph_spec(theme)
    lay = spec.layout
    assert lay["engine"] == "graph"
    assert (lay["rule_set"], lay["layers"]) == (base, layers)
    assert lay["applied"] and "edge_fidelity" in lay and "relations_broken" in lay
    assert set(lay["rooms"]) == {r.id for r in spec.rooms}
    for r in spec.rooms:
        assert r.kind == lay["rooms"][r.id]["kind"]
        assert r.district == lay["rooms"][r.id]["district"]
    # The spec round-trips with its layout and kinds.
    back = ZoneSpec.from_dict(json.loads(json.dumps(spec.to_dict())))
    assert back.layout == lay and [r.kind for r in back.rooms] == [r.kind for r in spec.rooms]


def test_named_set_beats_the_theme():
    lay = _graph_spec("temple", rule_set="warren").layout
    # temple's layer fits only classic_eq, so it drops out on warren.
    assert (lay["rule_set"], lay["layers"]) == ("warren", [])


# --- kind -> type -------------------------------------------------------------

def test_every_theme_maps_every_shipped_kind():
    for theme in semantics.ARCHETYPES:
        kmap = semantics.kind_types(theme)
        assert semantics.unmapped_kinds(theme, ROOM_KINDS) == [], theme
        for kind in ROOM_KINDS:
            assert all(t in semantics.ROOM_TYPES for t in kmap[kind]), (theme, kind)


@pytest.mark.parametrize("theme", ["fortress", "temple"])
def test_kinds_become_the_themes_types(theme):
    kmap = semantics.kind_types(theme)
    arch = semantics.ARCHETYPES[theme]
    for seed in range(4):
        spec = _graph_spec(theme, rooms=12, seed=seed)
        for r in spec.rooms:
            assert r.semantic_type in kmap[r.kind], (seed, r.id, r.kind, r.semantic_type)
        deep = [r for r in spec.rooms if r.kind == "deep"]
        assert len(deep) == 1 and deep[0].semantic_type == arch.climax_type
        assert [r.id for r in spec.rooms if r.boss] == [deep[0].id]
        assert [r.id for r in spec.rooms if r.role == "climax"] == [deep[0].id]
    assert semantics.kind_types("fortress")["deep"] == ("throne",)


def test_unmapped_kind_falls_back_with_a_note():
    from generators.zone_spec import RoomSpec
    import random
    rooms = [RoomSpec(id="room_0", center_x=0, center_y=0, role="entrance", kind="entrance"),
             RoomSpec(id="room_1", center_x=500, center_y=0, role="climax",
                      graph_depth=1, kind="chapel")]
    spec = ZoneSpec(name="u")
    semantics.label_rooms(spec, rooms, random.Random(0), archetype="fortress")
    assert rooms[1].semantic_type == "throne"     # the arc's climax type
    assert semantics.unmapped_kinds("fortress", ["chapel", "deep"]) == ["chapel"]

    from ai.expand import layout_block
    spec.dungeon_theme = "fortress"
    block = layout_block({"engine": "graph", "rooms": {"room_1": {"kind": "chapel"}}}, spec)
    assert any("chapel" in n for n in block["notes"])


def test_type_keeps_the_size_class_area():
    """A grown room keeps its footprint area through the type's shape bias
    (rules own size); only the race scale changes it. Classic rooms still
    take the type's footprint multiplier."""
    from generators.zone_spec import RoomSpec
    throne = semantics.ROOM_TYPES["throne"]           # footprint 1.6, aspect 1.5
    grown = RoomSpec(id="g", center_x=0, center_y=0, width=300, depth=200, kind="deep")
    semantics._apply_shape(grown, throne, "")
    assert grown.width * grown.depth == pytest.approx(300 * 200)
    assert grown.width / grown.depth == pytest.approx(1.5 * 1.5)
    ogre = RoomSpec(id="o", center_x=0, center_y=0, width=300, depth=200, kind="deep")
    semantics._apply_shape(ogre, throne, "ogre")
    assert ogre.width * ogre.depth == pytest.approx(300 * 200 * 1.4 ** 2)
    classic = RoomSpec(id="c", center_x=0, center_y=0, width=300, depth=200)
    semantics._apply_shape(classic, throne, "")
    assert classic.width * classic.depth == pytest.approx(300 * 200 * 1.6 ** 2 * 1.5)


# --- the sidecar ---------------------------------------------------------------

def _sidecar(spec, tmp_path):
    result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)
    return json.loads(result.sidecar_path.read_text())


def _check_shape(shape):
    assert set(shape) == {"dead_end_share", "cycle_rank", "deep_end"}
    assert 0.0 <= shape["dead_end_share"] <= 1.0
    assert shape["cycle_rank"] >= 0 and 0.0 < shape["deep_end"] <= 1.0


def test_classic_sidecar_layout_block(tmp_path):
    spec = plan_to_spec(ZonePlan(name="sc", room_count=6).validate(), seed=4)
    lay = _sidecar(spec, tmp_path)["layout"]
    assert set(lay) == {"engine", "shape"} and lay["engine"] == "classic"
    _check_shape(lay["shape"])


def test_graph_sidecar_layout_block(tmp_path):
    spec = _graph_spec("temple", rooms=10, seed=5)
    lay = _sidecar(spec, tmp_path)["layout"]
    assert lay["engine"] == "graph"
    assert (lay["rule_set"], lay["layers"]) == ("classic_eq", ["temple"])
    assert lay["applied"] == spec.layout["applied"]
    assert all(len(a) == 2 for a in lay["applied"])
    assert set(lay["rooms"]) == {r.id for r in spec.rooms}
    for rec in lay["rooms"].values():
        assert {"kind", "size", "district"} <= set(rec)
    assert 0.0 <= lay["edge_fidelity"] <= 1.0
    assert lay["relations_broken"] is not None
    _check_shape(lay["shape"])
    # The shape is the built graph's: one edge per corridor pair.
    pairs = {frozenset((c.from_room, c.to_room)) for c in spec.corridors}
    assert lay["shape"]["cycle_rank"] == len(pairs) - len(spec.rooms) + 1


def test_wilderness_sidecar_has_no_layout_block(tmp_path):
    spec = plan_to_spec(ZonePlan(name="w", zone_type="wilderness").validate(), seed=4)
    assert "layout" not in _sidecar(spec, tmp_path)
