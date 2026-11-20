"""Room scale from the cave style profile (step 21 task 4, zone-generator-cave Req 3)."""

from __future__ import annotations

import statistics

import pytest

import ai.expand as expand
import generators.rebuild as rebuild
from ai.schema import VALID_DUNGEON_THEMES, ZonePlan
from generators.layout import LayoutGenerator
from generators.zone_spec import ZoneSpec

SEEDS = range(1, 13)


def _spec(theme="cave", layout="classic", rooms=10, seed=7, **kw):
    plan = ZonePlan(name="cp", room_count=rooms, layout=layout, dungeon_theme=theme, **kw)
    return expand.plan_to_spec(plan.validate(), seed=seed)


def _mean_area(spec):
    return statistics.mean(r.width * r.depth for r in spec.rooms)


def test_cave_gets_the_cave_profile():
    assert _spec().style_profile == "cave"
    assert _spec(layout="graph").style_profile == "cave"


@pytest.mark.parametrize("theme", [""] + [t for t in VALID_DUNGEON_THEMES if t != "cave"])
def test_any_other_purpose_keeps_the_dungeon_profile(theme):
    assert _spec(theme, rooms=5).style_profile == "dungeon"


def test_cities_and_outdoor_dungeons_keep_theirs():
    assert _spec(zone_type="city", rooms=5).style_profile == "city"
    assert _spec(zone_type="outdoor_dungeon", rooms=5).style_profile == "outdoor"


def test_the_profile_shrinks_rooms_and_nothing_else_moves():
    """cave.json's floor area is ~15% under dungeon.json's: a negative band shift."""
    plain = LayoutGenerator("dungeon", seed=1)
    cave = LayoutGenerator("dungeon", seed=1, profile="cave")
    assert plain.profile_shift == 0.0 and plain.size_shift == 0.0
    assert -0.12 < cave.profile_shift < -0.06
    assert cave.size_shift == cave.profile_shift


@pytest.mark.parametrize("layout", ["classic", "graph"])
def test_cave_rooms_are_smaller_than_without_the_profile(layout, monkeypatch):
    """Same seeds, same Purpose: the profile alone shrinks the mean room area."""
    with_profile = [_mean_area(_spec(layout=layout, seed=s)) for s in SEEDS]
    monkeypatch.setattr(expand, "PURPOSE_PROFILE", {})
    without = [_mean_area(_spec(layout=layout, seed=s)) for s in SEEDS]
    assert statistics.mean(with_profile) < 0.95 * statistics.mean(without)


@pytest.mark.parametrize("layout, shrink", [("classic", 0.076), ("graph", 0.139)])
def test_the_profile_shrinks_footprints_not_heights(layout, shrink, monkeypatch):
    """District-looks task 4: the shift sizes footprints only. Ten seeds with
    and without the profile: rooms still smaller (no more than step 21's
    shrink), mean room height within 2 %, corridor heights unchanged."""
    def measure():
        specs = [_spec(layout=layout, seed=s) for s in range(1, 11)]
        return (statistics.mean(_mean_area(sp) for sp in specs),
                statistics.mean(statistics.mean(r.height for r in sp.rooms) for sp in specs),
                sorted({c.height for sp in specs for c in sp.corridors}))
    area, height, corridors = measure()
    monkeypatch.setattr(expand, "PURPOSE_PROFILE", {})
    area0, height0, corridors0 = measure()
    assert 1 - shrink - 0.01 <= area / area0 < 0.97
    assert abs(height / height0 - 1) <= 0.02
    assert corridors == corridors0


def test_only_the_cave_profile_sets_a_corridor_run():
    """Winding tunnels task 9: the cave's graph placement runs corridors longer; every other
    build keeps ``embed.RUN_FACTOR`` (run_factor None)."""
    import generators.topology.embed as embed
    plain = LayoutGenerator("dungeon", seed=1)
    cave = LayoutGenerator("dungeon", seed=1, profile="cave")
    assert plain.run_factor is None
    assert plain._layout_context(10, "", "").run_factor is None
    assert cave.run_factor > embed.RUN_FACTOR
    assert cave._layout_context(10, "", "").run_factor == cave.run_factor
    assert LayoutGenerator("city", seed=1).run_factor is None


def test_cave_rooms_stand_further_apart_with_the_profile(monkeypatch):
    """Same seeds: the cave's own run lengthens its corridors."""
    def mean_length():
        return statistics.mean(abs(c.to_x - c.from_x) + abs(c.to_y - c.from_y)
                               for s in range(1, 6) for c in _spec(layout="graph", seed=s).corridors)
    longer = mean_length()
    monkeypatch.setattr(expand, "PURPOSE_PROFILE", {})
    assert longer > 2 * mean_length()


def test_the_profile_leaves_the_classic_ceiling():
    plain = LayoutGenerator("dungeon", seed=1)
    cave = LayoutGenerator("dungeon", seed=1, profile="cave")
    for g in (plain, cave):
        g._apply_room_scale(10)
    assert cave.ceiling == plain.ceiling
    assert cave.room_max < plain.room_max


def _districted(theme, proposals):
    return ZonePlan(name="cp", room_count=12, dungeon_theme=theme, districts=True,
                    district_plan=[{"purpose": p} for p in proposals]).validate()


@pytest.mark.parametrize("theme, proposals, profile", [
    ("cave", [], "cave"),                       # District 0 takes the theme
    ("fortress", ["cave", "tomb"], "cave"),     # District 0's proposal wins
    ("cave", ["fortress", "cave"], None),       # District 0 is a fortress
    ("", ["cave", "cave"], "cave"),             # pinned
])
def test_district_zero_sets_the_profile(theme, proposals, profile):
    plan = _districted(theme, proposals)
    args = expand._district_args(plan, 7, [])
    assert expand.purpose_profile(plan, args) == profile
    spec = expand.plan_to_spec(plan, seed=7)
    assert spec.style_profile == (profile or "dungeon")
    if len(spec.districts) >= 2:
        assert (spec.districts[0].purpose == "cave") == (profile == "cave")


def test_too_few_rooms_for_districts_uses_the_zone_purpose():
    plan = ZonePlan(name="cp", room_count=5, dungeon_theme="fortress", districts=True,
                    district_plan=[{"purpose": "cave"}]).validate()
    assert expand.purpose_profile(plan, expand._district_args(plan, 7, [])) is None


def test_a_saved_spec_keeps_its_profile_on_load_and_rebuild(tmp_path):
    doc = _spec().to_dict()
    assert ZoneSpec.from_dict(doc).style_profile == "cave"
    built = rebuild.build_spec(tmp_path, doc, zone_id="cp", stages=False,
                               generate=lambda factory, **kw: factory(kw["seed"]))
    assert built.style_profile == "cave"
