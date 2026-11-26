"""Hall length task 2 (Requirements 1-3; design "The field"): the plan's ``hall_length`` is
clamped and round-trips, reaches the spec, and scales each layout's door-to-door halls while
the grown graph and its Levels stay as they are. At 1 nothing changes.
"""

import functools
import math
import statistics

import pytest

from ai.expand import plan_to_spec
from ai.schema import HALL_MAX, HALL_MIN, ZonePlan
from generators.routing import corridor_route
from generators.zone_spec import ZoneSpec

KINDS = {
    "fortress": {"zone_type": "dungeon", "dungeon_theme": "fortress", "layout": "graph"},
    "cave": {"zone_type": "dungeon", "dungeon_theme": "cave", "layout": "graph"},
    "city": {"zone_type": "city"},
}
SEEDS = (2001, 2004, 2007)


@functools.lru_cache(maxsize=None)
def _build(kind, seed, hall_length=None):
    controls = dict(KINDS[kind], room_count=12, verticality="moderate")
    if hall_length is not None:
        controls["hall_length"] = hall_length
    plan = ZonePlan.from_controls(controls, [])
    plan.name = "halls"
    return plan_to_spec(plan, seed=seed, warnings=[])


def _halls(spec):
    """Door-to-door length of each corridor joining two rooms (its path, else its route),
    throats (no longer than a corridor width) left out: they don't scale."""
    by = {r.id: r for r in spec.rooms}
    out = []
    for c in spec.corridors:
        if c.from_room in by and c.to_room in by and c.from_room != c.to_room:
            line = c.path or list(corridor_route(c, by).waypoints)
            length = sum(math.dist(a, b) for a, b in zip(line, line[1:]))
            if length > c.width:
                out.append(length)
    return out


def _graph(spec):
    """The grown graph's rooms as the layout record keeps them (what each room is)."""
    keys = ("kind", "size", "shape", "district", "wing", "node")
    return {rid: tuple(r.get(k) for k in keys) for rid, r in spec.layout["rooms"].items()}


def test_plan_clamps_falls_back_and_round_trips():
    assert ZonePlan().validate().hall_length == 1.0
    assert ZonePlan(hall_length=0.1).validate().hall_length == HALL_MIN
    assert ZonePlan(hall_length=99).validate().hall_length == HALL_MAX
    for bad in ("long", None, True, float("nan")):
        assert ZonePlan(hall_length=bad).validate().hall_length == 1.0
    assert "hall_length" not in ZonePlan().validate().to_dict()
    assert ZonePlan.from_dict(ZonePlan(hall_length=2.5).validate().to_dict()).hall_length == 2.5


def test_spec_writes_hall_length_only_off_one():
    spec = ZoneSpec.from_dict(ZoneSpec(name="h").to_dict())
    assert spec.hall_length == 1.0 and "hall_length" not in spec.to_dict()
    spec.hall_length = 2.0
    again = ZoneSpec.from_dict(spec.to_dict())
    assert again.hall_length == 2.0 and again.to_dict()["hall_length"] == 2.0
    assert _build("fortress", SEEDS[0], 2.0).hall_length == 2.0


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_one_is_the_zone_without_it(kind):
    assert _build(kind, SEEDS[0], 1.0).to_dict() == _build(kind, SEEDS[0]).to_dict()


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_halls_scale_and_the_graph_stays(kind):
    """At HALL_MAX the halls run about three times as long (the 40-seed sweep in the task's
    commit: 2.9-3.3; a 12-room city over three seeds reads lower), on the same grown graph,
    Levels and rooms."""
    base = [_build(kind, s) for s in SEEDS]
    long = [_build(kind, s, HALL_MAX) for s in SEEDS]
    ratio = (statistics.median(x for b in long for x in _halls(b))
             / statistics.median(x for b in base for x in _halls(b)))
    assert 2.0 <= ratio <= 3.6, ratio
    for b, lg in zip(base, long):
        assert len(lg.rooms) == len(b.rooms)
        if b.layout is not None:            # a Graph layout
            assert lg.layout["applied"] == b.layout["applied"]
            assert _graph(lg) == _graph(b)
            assert lg.layout.get("levels") == b.layout.get("levels")
