"""Verticality step 7, task 17 (Requirement 10; design "Race-sized rooms",
property V11): rooms and corridors sized for their race, at stock scale.

Every race has a body height H (``semantics.RACE_HEIGHT``, from the client's
racedata.txt; the default race is a human, H 6 u). Every room-graph room's
height lies in [2.5 H, 10 H] and each footprint side in [8 H, 20 H], whatever
its Size_Class, room type, pacing role or the plan's Size control, in both
layout engines and under a hill; corridors are 3 H wide and 2.5 H tall, over
the walk agent's player height.
"""

import random

import pytest

from ai.expand import plan_to_spec
from ai.schema import VALID_DUNGEON_RACES, ZonePlan
from analyzer.traverse import AgentModel
from generators import semantics
from generators.topology import embed

RACES = [""] + list(VALID_DUNGEON_RACES)
CLASSES = list(semantics.CLASS_POSITION)
EPS = 1e-6


def _plan(race, layout, theme="temple", size="medium", rooms=12, zone_type="dungeon",
          verticality="moderate"):
    return ZonePlan(name="race", zone_type=zone_type, room_count=rooms, size=size,
                    dungeon_race=race, dungeon_theme=theme, layout=layout,
                    verticality=verticality).validate()


def _in_bands(spec, race):
    (s0, s1), (h0, h1) = semantics.room_bands(race)
    for r in spec.rooms:
        assert s0 - EPS <= r.width <= s1 + EPS, (race, r.id, r.width, (s0, s1))
        assert s0 - EPS <= r.depth <= s1 + EPS, (race, r.id, r.depth, (s0, s1))
        assert h0 - EPS <= r.height <= h1 + EPS, (race, r.id, r.height, (h0, h1))


def _corridors_in_band(spec, race):
    h = semantics.body_height(race)
    w0, w1 = semantics.CORRIDOR_WIDTH_BAND
    c0, c1 = semantics.CORRIDOR_HEIGHT_BAND
    player = AgentModel().player_height
    assert spec.corridors
    for c in spec.corridors:
        assert w0 * h - EPS <= c.width <= w1 * h + EPS, (race, c.id, c.width)
        assert c0 * h - EPS <= c.height <= c1 * h + EPS, (race, c.id, c.height)
        assert c.height >= player, (race, c.id, c.height)


def test_every_dungeon_race_has_a_body_height():
    assert set(VALID_DUNGEON_RACES) | {"default"} == set(semantics.RACE_HEIGHT)
    assert "dragon" in VALID_DUNGEON_RACES
    assert semantics.body_height("") == semantics.body_height("default") == 6.0
    assert semantics.body_height("dragon") == 21.0 and semantics.body_height("giant") == 22.0


def test_bands_in_units():
    # Design finding 8: human rooms 15-60 u tall and 48-120 u across.
    assert semantics.room_bands("") == ((48.0, 120.0), (15.0, 60.0))
    assert semantics.corridor_size("") == (18.0, 15.0)


@pytest.mark.parametrize("race", RACES)
def test_size_classes_pick_inside_the_band(race):
    """tiny at the band minimum, huge at its maximum, each class larger than
    the last; the Size control's shift never leaves the band."""
    (s0, s1), (h0, h1) = semantics.room_bands(race)
    rng = random.Random(0)
    for shift in semantics.SIZE_SHIFT.values():
        last = None
        for size in CLASSES:
            for _ in range(20):
                w, d, h = embed.room_size(size, race, rng, shift)
                assert s0 - EPS <= w <= s1 + EPS and s0 - EPS <= d <= s1 + EPS
                assert h0 - EPS <= h <= h1 + EPS
            t = semantics.band_position(size, shift)
            side = semantics.room_side(race, t)
            assert last is None or side >= last
            last = side
    assert semantics.room_side(race, semantics.band_position("tiny")) == pytest.approx(s0)
    assert semantics.room_side(race, semantics.band_position("huge")) == pytest.approx(s1)
    assert semantics.room_height(race, semantics.band_position("tiny")) == pytest.approx(h0)
    assert semantics.room_height(race, semantics.band_position("huge")) == pytest.approx(h1)


@pytest.mark.parametrize("layout", ["classic", "graph"])
@pytest.mark.parametrize("race", RACES)
def test_v11_rooms_and_corridors_in_the_race_bands(race, layout):
    """V11: every room inside its race's bands, every corridor inside the
    corridor band and over the player's height, for both engines, every Size,
    plain and themed (role and room-type biases are clamped back in)."""
    seen = set()
    for k, (size, theme) in enumerate([("small", ""), ("medium", "temple"),
                                       ("large", "fortress"), ("huge", "warren")]):
        spec = plan_to_spec(_plan(race, layout, theme, size), seed=100 + k)
        _in_bands(spec, race)
        _corridors_in_band(spec, race)
        if spec.layout:
            seen |= {r["size"] for r in spec.layout["rooms"].values()}
    if layout == "graph":
        # The grown rooms span the classes (the rule sets' mixes).
        assert {"small", "medium", "large", "huge"} <= seen, seen


@pytest.mark.parametrize("race", ["", "ogre"])
def test_v11_city_and_outdoor_dungeon(race):
    """City follows the bands (at the default race when it has none); an
    outdoor dungeon's rooms are a dungeon's, through every shrink."""
    _in_bands(plan_to_spec(_plan(race, "classic", "", zone_type="city", rooms=7), seed=5), race)
    for layout in ("classic", "graph"):
        spec = plan_to_spec(_plan(race, layout, "fortress", rooms=5,
                                  zone_type="outdoor_dungeon"), seed=3)
        _in_bands(spec, race)
        _corridors_in_band(spec, race)


def _extremes(race):
    rooms = []
    for layout in ("classic", "graph"):
        for k, (size, theme) in enumerate([("small", "temple"), ("huge", "fortress")]):
            rooms += plan_to_spec(_plan(race, layout, theme, size), seed=200 + k).rooms
    return rooms


def test_big_races_never_build_small_rooms():
    """An ogre's smallest room is above a human's band minimum (side and
    height); a human's largest footprint is below a dragon's band minimum.
    (Heights overlap at the top: a human's 10 H hall, 60 u, is over a
    dragon's 2.5 H minimum, 52.5 u.)"""
    (hs0, _hs1), (hh0, _hh1) = semantics.room_bands("")
    (ds0, _ds1), _ = semantics.room_bands("dragon")
    ogre = _extremes("ogre")
    assert min(min(r.width, r.depth) for r in ogre) > hs0
    assert min(r.height for r in ogre) > hh0
    human = _extremes("")
    assert max(max(r.width, r.depth) for r in human) < ds0


@pytest.mark.slow
def test_dragon_graph_dungeon_passes_the_gate(tmp_path):
    from generators.pipeline import generate_validated
    plan = _plan("dragon", "graph", "", rooms=10)
    vb = generate_validated(lambda s: plan_to_spec(plan, seed=s), zone_type="dungeon",
                            zone_id="dragon", output_dir=tmp_path, write_glb=False,
                            rng=random.Random(2), failure_log=None, timeout_s=600.0)
    assert vb.validated
    assert vb.attempts == 1
