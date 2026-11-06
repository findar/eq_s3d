"""Room walls task 5 (Requirements 6, 2.4, 2.5, 12.3; design W2, W3): graph builds draw
their rooms' Outlines, and nothing else moves.
"""

import copy
import random

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.pipeline import generate_validated
from generators.topology.ruleset import load_theme_map
from generators.wall_styles import THEMES_FILE, apply_walls, load_styles, style_for_theme


def _plan(zone_type="dungeon", layout="graph", rooms=12, theme="", race="", rule_set="",
          verticality="moderate"):
    return ZonePlan(name="w5", zone_type=zone_type, room_count=rooms, layout=layout, rule_set=rule_set,
                    dungeon_theme=theme, dungeon_race=race, verticality=verticality).validate()


def _layout_only(spec):
    d = copy.deepcopy(spec.to_dict())
    for r in d["rooms"]:
        r.pop("outline", None)
    d.pop("layout", None)
    return d


def test_w2_layout_is_the_same_whatever_the_style():
    spec = plan_to_spec(_plan(rule_set="classic_eq"), seed=11)
    base = _layout_only(spec)
    for style in load_styles().values():
        apply_walls(spec, style, 11)
        assert _layout_only(spec) == base, style.name
        assert spec.layout["walls"] == style.name


@pytest.mark.parametrize("zone_type, layout", [("dungeon", "classic"), ("city", "classic")])
def test_w3_classic_and_cities_draw_no_outlines(zone_type, layout):
    spec = plan_to_spec(_plan(zone_type=zone_type, layout=layout), seed=4)
    assert all(r.outline is None for r in spec.rooms)


@pytest.mark.parametrize("theme, style", [("", "built"), ("fortress", "built"), ("temple", "built"),
                                          ("warren", "rough"), ("mine_delve", "hewn"),
                                          ("lava_forge", "hewn"), ("ice_keep", "hewn")])
def test_a_theme_chooses_its_style(theme, style):
    assert style_for_theme(theme).name == style
    assert plan_to_spec(_plan(theme=theme), seed=3).layout["walls"] == style


def test_themes_file_names_only_real_styles(tmp_path):
    (tmp_path / "topology").mkdir()
    (tmp_path / "walls").mkdir()
    (tmp_path / "walls" / "built.toml").write_text("", encoding="utf-8")
    p = tmp_path / "topology" / "themes.toml"
    p.write_text('default = { base = "classic_eq", walls = "marble" }\n', encoding="utf-8")
    with pytest.raises(ValueError, match="walls: found \"marble\", expected one of built"):
        load_theme_map(p)
    assert load_theme_map(THEMES_FILE).entry_for("warren").walls == "rough"


def test_kinds_take_the_shapes_their_style_allows():
    style = style_for_theme("warren")
    for seed in range(6):
        spec = plan_to_spec(_plan(theme="warren"), seed=seed)
        for room in spec.rooms:
            rec = spec.layout["rooms"][room.id]
            table = style.shapes.get(rec["kind"], style.shapes["default"])
            assert rec["shape"] in table, (rec, table)
            assert rec["fill"] == pytest.approx(room.outline.fill(_box(room)), abs=1e-3)


def _box(room):
    (x0, y0, _), (x1, y1, _) = room.bounds
    return (x0, y0, x1, y1)


def test_built_keeps_most_rooms_plain():
    plain = shaped = 0
    for seed in range(6):
        for room in plan_to_spec(_plan(rooms=16), seed=seed).rooms:
            plain += room.outline is None
            shaped += room.outline is not None
    assert plain > 0 and shaped > 0


def test_a_rule_can_fix_a_shape():
    """The temple's nave stays a long hall, whatever the style's table says."""
    found = 0
    for seed in range(8):
        spec = plan_to_spec(_plan(theme="temple"), seed=seed)
        if ["Nave", "nave"] not in spec.layout["applied"]:
            continue
        found += sum(r["kind"] == "hall" and r["shape"] == "long" for r in spec.layout["rooms"].values())
    assert found >= 1


def test_same_seed_same_outlines():
    a, b = (plan_to_spec(_plan(theme="warren"), seed=9) for _ in range(2))
    assert [r.outline for r in a.rooms] == [r.outline for r in b.rooms]


def test_outlines_change_with_the_seed_but_the_stream_is_per_room():
    style = style_for_theme("warren")
    spec = plan_to_spec(_plan(theme="warren"), seed=9)
    before = spec.rooms[0].outline
    spec.rooms[-1].outline = None
    apply_walls(spec, style, 9)
    assert spec.rooms[0].outline == before


@pytest.mark.slow
@pytest.mark.parametrize("theme, rule_set, race, seed", [
    ("", "classic_eq", "", 10),
    ("", "classic_eq", "", 11),      # stacked, two bridges
    ("warren", "", "", 4),
    ("warren", "", "", 15),          # stacked, four Levels
    ("mine_delve", "", "", 6),
    ("temple", "", "", 13),
    ("mine_delve", "", "ogre", 10),
    ("warren", "", "dragon", 10),
])
def test_built_zones_pass_the_gate_in_each_style(tmp_path, theme, rule_set, race, seed):
    plan = _plan(theme=theme, rule_set=rule_set, race=race, rooms=8 if race == "dragon" else 12)
    vb = generate_validated(lambda s: plan_to_spec(plan, seed=s), zone_type="dungeon", zone_id="w5",
                            rng=random.Random(seed), output_dir=tmp_path, write_glb=False,
                            failure_log=None, max_attempts=4, timeout_s=300.0)
    assert vb.validated
    assert vb.attempts == 1, (theme, seed, vb.attempts)
