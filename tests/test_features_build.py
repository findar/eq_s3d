"""Room layouts task 6 (Requirements 4.4, 6, 7; design F5, F7, F8): graph builds stand their
recipes in their rooms, and nothing else about them moves.
"""

import copy
import random

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.pipeline import generate_validated
from generators.room_layouts import apply_features
from generators.wall_styles import load_styles


def _plan(zone_type="dungeon", layout="graph", rooms=12, theme="", race="", rule_set="", walls="",
          verticality="moderate"):
    return ZonePlan(name="w6", zone_type=zone_type, room_count=rooms, layout=layout, rule_set=rule_set,
                    walls=walls, dungeon_theme=theme, dungeon_race=race, verticality=verticality).validate()


def _without_features(spec):
    d = copy.deepcopy(spec.to_dict())
    for r in d["rooms"]:
        for key in ("features", "pois", "prop_hints"):
            r.pop(key, None)
    d.pop("layout", None)
    return d


@pytest.mark.parametrize("zone_type, layout", [("dungeon", "classic"), ("city", "classic")])
def test_classic_and_cities_stay_empty(zone_type, layout):
    spec = plan_to_spec(_plan(zone_type=zone_type, layout=layout), seed=4)
    assert not any(r.features or r.pois for r in spec.rooms)


def test_f5_nothing_else_moves():
    spec = plan_to_spec(_plan(rule_set="classic_eq", walls="rough"), seed=11)
    base = _without_features(spec)
    for density in ("none", "sparse", "normal", "dense"):
        for room in spec.rooms:
            room.features, room.pois = [], []
        apply_features(spec, "voronoi", 11, density)
        assert _without_features(spec) == base, density


def test_none_adds_nothing_and_says_so():
    spec = plan_to_spec(_plan(walls="hewn"), seed=4)
    for room in spec.rooms:
        room.features, room.pois = [], []
    apply_features(spec, "facet", 4, "none")
    assert not any(r.features or r.pois for r in spec.rooms)
    assert spec.layout["features"] == "none"


def test_more_density_stands_more():
    def total(density):
        spec = plan_to_spec(_plan(rooms=20, theme="temple"), seed=7)
        for room in spec.rooms:
            room.features, room.pois = [], []
        apply_features(spec, "grid", 7, density)
        return sum(len(r.features) for r in spec.rooms)
    assert total("none") == 0 < total("sparse") <= total("normal") <= total("dense")


def test_f7_the_climax_has_a_boss_and_the_record_says_what_stands():
    for seed in range(5):
        spec = plan_to_spec(_plan(theme="temple"), seed=seed)
        for room in spec.rooms:
            rec = spec.layout["rooms"][room.id]
            assert rec["features"] == [f.kind for f in room.features]
            assert len(rec["pois"]) == len(room.pois)
            assert rec["room_layout"]
            if room.role == "climax":
                assert any(p.purpose == "boss" for p in room.pois), room.id


def test_structural_hints_leave_only_when_built():
    spec = plan_to_spec(_plan(theme="fortress", rooms=20), seed=4)
    thrones = [r for r in spec.rooms if r.semantic_type == "throne"]
    assert thrones
    for room in thrones:
        built = {f.kind for f in room.features}
        assert ("dais" in built) == (not any("dais" in h for h in room.prop_hints))
    classic = plan_to_spec(_plan(layout="classic", theme="fortress", rooms=20), seed=4)
    assert any("dais" in h for r in classic.rooms for h in r.prop_hints)


def test_named_rooms_stand_out_and_most_plain_rooms_stay_simple():
    spec = plan_to_spec(_plan(rooms=20), seed=9)
    with_any = sum(bool(r.features) for r in spec.rooms) / len(spec.rooms)
    assert with_any <= 0.8


@pytest.mark.slow
@pytest.mark.parametrize("zone_type, walls, theme, race, rooms, verticality, seed", [
    ("dungeon", "built", "", "", 12, "moderate", 10),
    ("dungeon", "hewn", "temple", "", 12, "dramatic", 13),
    ("dungeon", "rough", "warren", "", 12, "moderate", 4),
    ("dungeon", "rough", "", "", 12, "moderate", 11),       # stacked, two bridges
    ("dungeon", "built", "fortress", "ogre", 12, "moderate", 3),
    ("dungeon", "hewn", "tomb", "dragon", 8, "moderate", 5),
    ("outdoor_dungeon", "", "", "", 8, "dramatic", 13),     # two Levels, a bridge
    ("outdoor_dungeon", "built", "temple", "", 5, "flat", 9),
])
def test_f8_built_zones_pass_the_gate_with_features(tmp_path, zone_type, walls, theme, race, rooms, verticality, seed):
    plan = _plan(zone_type=zone_type, walls=walls, theme=theme, race=race, rooms=rooms, verticality=verticality)
    vb = generate_validated(lambda s: plan_to_spec(plan, seed=s), zone_type=zone_type, zone_id="w6",
                            rng=random.Random(seed), output_dir=tmp_path, write_glb=False, failure_log=None,
                            max_attempts=4, timeout_s=300.0)
    assert vb.validated
    assert vb.attempts == 1, vb.attempts


def test_styles_give_their_form():
    assert set(load_styles()) == {"built", "hewn", "rough"}
    rough = plan_to_spec(_plan(walls="rough", rooms=20), seed=2)
    built = plan_to_spec(_plan(walls="built", rooms=20), seed=2)
    pillars = [f for r in rough.rooms for f in r.features if f.kind == "pillar"]
    square = [f for r in built.rooms for f in r.features if f.kind == "pillar"]
    assert all(len(f.plan) >= 6 for f in pillars)
    assert all(len(f.plan) == 4 for f in square)
