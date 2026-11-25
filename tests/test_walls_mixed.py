"""Room layouts task 16 (Requirement 12; design F13): a room's finish is its wall style."""

import hashlib
from collections import Counter

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.builder import ZoneBuilder
from generators.topology.ruleset import RuleSetError, load_theme_map
from generators.wall_styles import WALLS_DIR, load_style, load_styles, style_for_finish
from tests.conftest import gated_attempts, gated_key

#: A plan naming a style, in master's bytes before finish chose a room's style, footer aside.
NAMED = {"rough": "0b7875b29b5e075954c0d094da882995f1841b1e02299bf56806a3fa1bc9747f", "hewn": "d0f29b92139b4ca9a15dfc13e54a9f735a05cd14d033da38471d916c3ed60d9e", "built": "b47699190e817cf8e1f727aa409a3ce7eded97a3ea8081778f10b64513c29af5"}


def _plan(**fields):
    fields = {"room_count": 16, "verticality": "flat", **fields}
    return ZonePlan(name="wm", zone_type=fields.pop("zone_type", "dungeon"), layout="graph", **fields).validate()


def _styles(spec):
    return Counter(spec.layout["rooms"][r.id]["style"] for r in spec.rooms)


@pytest.mark.parametrize("style", sorted(NAMED))
def test_a_named_style_keeps_its_bytes(tmp_path, style):
    """F13: naming a style still gives every room that style, as before."""
    spec = plan_to_spec(_plan(walls=style, dungeon_theme="temple", features="none"), seed=5)
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


def test_a_zone_mixes_styles_and_a_corridor_without_a_seam_is_the_rougher_rooms():
    spec = plan_to_spec(_plan(rule_set="classic_eq", room_count=24), seed=4)
    assert len(_styles(spec)) >= 2
    assert spec.layout["walls"] == "rules"
    styles = load_styles()
    records = spec.layout["rooms"]
    for cor in spec.corridors:
        if cor.steps or cor.bridge:
            assert cor.rough == 0
            continue
        if cor.transition is not None and cor.transition.floor_material:
            continue                # its from_room's up to the line (test_transition_rules)
        ends = sorted(records[r]["style"] for r in (cor.from_room, cor.to_room))
        if ends[0] != ends[1] and "rough" in ends:
            assert cor.rough >= styles["rough"].corridor_break * 0.75


@pytest.mark.slow
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


MIXED_SEEDS = range(4)
_CASE_ID = {i: "-".join(str(v) for v in f.values()) for i, f in enumerate(CASES)}


def _mixed_key(fields: dict, seed: int) -> tuple:
    """``conftest.gated_attempts``'s key for a case on sweep seed ``seed``: ``_plan``'s
    fields, four attempts, 300 s."""
    plan = {"room_count": 16, "verticality": "flat", "zone_type": "dungeon", "layout": "graph",
            **fields}
    return gated_key(plan, seed, 4, 300.0)


@pytest.mark.gate
@pytest.mark.slow
@pytest.mark.parametrize("case, seed", [(i, s) for i in range(len(CASES)) for s in MIXED_SEEDS],
                         ids=[f"{_CASE_ID[i]}-{s}" for i in range(len(CASES)) for s in MIXED_SEEDS])
def test_mixed_zone_passes_within_the_retries(shared_results, case, seed):
    """One seed of a case (a test each, so the sweep spreads over the workers): it passes
    every step 8 check within four attempts. The first-try count below reads these."""
    tries = shared_results.get(_mixed_key(CASES[case], seed), gated_attempts)
    assert tries is not None, "out of retries"


@pytest.mark.gate
@pytest.mark.slow
@pytest.mark.parametrize("fields", CASES, ids=lambda f: "-".join(str(v) for v in f.values()))
def test_mixed_zones_pass_the_gate(shared_results, fields):
    """Every step 8 check, on zones of more than one style, first try 3 times in 4."""
    keys = [_mixed_key(fields, s) for s in MIXED_SEEDS]
    tries = shared_results.get_many(keys[::-1], gated_attempts)[::-1]
    assert None not in tries, tries
    assert sum(t == 1 for t in tries) >= 3, tries
