"""Room layouts task 16 (Requirement 12; design F13): a room's finish is its wall style."""

import hashlib
import random
from collections import Counter

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.builder import ZoneBuilder
from generators.pipeline import generate_validated
from generators.topology.ruleset import RuleSetError, load_theme_map
from generators.wall_styles import WALLS_DIR, load_style, load_styles, style_for_finish

#: A plan naming a style, in master's bytes before finish chose a room's style, footer aside.
NAMED = {"rough": "ffa7d4bb59f6618193227ad3a22a1f576e5c553b023df28602b6803fc2eac6ba", "hewn": "5a023de421938889478190ef48285e4ca9eed1158f441b2cb6a4e27c77438517", "built": "58a6c9150c3e756fba7d21dcc60278e4d8c6e0b4501c71e9f7632f10badc59a3"}


def _plan(**fields):
    fields = {"room_count": 16, "verticality": "flat", **fields}
    return ZonePlan(name="wm", zone_type=fields.pop("zone_type", "dungeon"), layout="graph", **fields).validate()


def _styles(spec):
    return Counter(spec.layout["rooms"][r.id]["style"] for r in spec.rooms)


@pytest.mark.parametrize("style", sorted(NAMED))
def test_a_named_style_keeps_its_bytes(tmp_path, style):
    """F13: naming a style still gives every room that style, as before."""
    spec = plan_to_spec(_plan(walls=style, dungeon_theme="temple"), seed=5)
    assert set(_styles(spec)) == {style}
    eqg = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False).eqg_path.read_bytes()
    assert hashlib.sha256(eqg[:-4]).hexdigest() == NAMED[style]


def test_finish_chooses_the_style_across_0_to_10():
    styles = load_styles()
    names = [style_for_finish(v, styles).name for v in range(11)]
    assert names == ["rough"] * 4 + ["hewn"] * 3 + ["built"] * 4


def test_a_styles_middle_is_as_written_and_its_ends_move():
    rough = load_styles()["rough"]
    assert rough.at_finish(0).wobble_h > rough.wobble_h > rough.at_finish(3).wobble_h
    mid = load_styles()["hewn"].at_finish(5)
    assert mid.ceiling_spread == load_styles()["hewn"].ceiling_spread
    assert mid.corridor_break == pytest.approx(load_styles()["hewn"].corridor_break)


def test_styles_must_cover_0_to_10_once(tmp_path):
    for p in WALLS_DIR.glob("*.toml"):
        (tmp_path / p.name).write_bytes(p.read_bytes().replace(b"finish = [4, 6]", b"finish = [4, 5]"))
    from generators.wall_styles import load_styles as load
    with pytest.raises(RuleSetError):
        load(tmp_path)


def test_a_style_must_name_its_band_and_a_good_tune(tmp_path):
    src = (WALLS_DIR / "rough.toml").read_text(encoding="utf-8")
    p = tmp_path / "rough.toml"
    p.write_text(src.replace("wobble_h = [1.25, 0.75]", "wobble_h = [5, 0.75]"), encoding="utf-8")
    with pytest.raises(RuleSetError) as exc:
        load_style(p)
    assert any(e.where == "tune" and e.field == "wobble_h" for e in exc.value.errors)


def test_themes_name_no_style(tmp_path):
    """One source of a room's finish."""
    p = tmp_path / "themes.toml"
    p.write_text('default = { base = "classic_eq", walls = "built" }\n', encoding="utf-8")
    with pytest.raises(RuleSetError):
        load_theme_map(p)


def test_a_zone_mixes_styles_and_a_corridor_is_the_rougher_rooms():
    spec = plan_to_spec(_plan(rule_set="classic_eq", room_count=24), seed=4)
    assert len(_styles(spec)) >= 2
    assert spec.layout["walls"] == "rules"
    styles = load_styles()
    records = spec.layout["rooms"]
    for cor in spec.corridors:
        if cor.steps or cor.bridge:
            assert cor.rough == 0
            continue
        ends = sorted(records[r]["style"] for r in (cor.from_room, cor.to_room))
        if ends[0] != ends[1] and "rough" in ends:
            assert cor.rough >= styles["rough"].corridor_break * 0.75


def test_a_warren_is_mostly_rough_and_a_fortress_mostly_built():
    warren, fort = Counter(), Counter()
    for seed in range(6):
        warren += _styles(plan_to_spec(_plan(dungeon_theme="warren"), seed=seed))
        fort += _styles(plan_to_spec(_plan(dungeon_theme="fortress"), seed=seed))
    assert warren.most_common(1)[0][0] == "rough"
    assert fort.most_common(1)[0][0] == "built"


def test_an_outdoor_dungeon_with_no_theme_is_mostly_cave():
    rooms = Counter()
    for seed in range(4):
        rooms += _styles(plan_to_spec(_plan(zone_type="outdoor_dungeon", room_count=8), seed=seed))
    assert rooms.most_common(1)[0][0] == "rough"


CASES = [dict(rule_set="classic_eq", verticality="moderate"), dict(rule_set="classic_eq", verticality="dramatic"),
         dict(dungeon_theme="temple", verticality="moderate"), dict(dungeon_theme="mine_delve", verticality="moderate"),
         dict(dungeon_theme="fortress", dungeon_race="ogre", verticality="moderate"),
         dict(rule_set="warren", verticality="dramatic"), dict(dungeon_race="giant", room_count=8),
         dict(zone_type="outdoor_dungeon", room_count=8, verticality="dramatic")]


@pytest.mark.slow
@pytest.mark.parametrize("fields", CASES, ids=lambda f: "-".join(str(v) for v in f.values()))
def test_mixed_zones_pass_the_gate(tmp_path, fields):
    """Every step 8 check, on zones of more than one style, first try 3 times in 4."""
    plan = _plan(**fields)
    zone_type = fields.get("zone_type", "dungeon")
    tries = []
    for seed in range(4):
        vb = generate_validated(lambda s: plan_to_spec(plan, seed=s), zone_type=zone_type, zone_id="wm",
                                rng=random.Random(seed), output_dir=tmp_path / str(seed), write_glb=False,
                                failure_log=None, max_attempts=4, timeout_s=300.0)
        assert vb.validated
        tries.append(vb.attempts)
    assert sum(t == 1 for t in tries) >= 3, tries
