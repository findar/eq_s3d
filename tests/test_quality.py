"""The quality meter (zone-generator-quality task 1; umbrella Requirement 24.1-24.4).

Specs only: nothing here builds a zone.
"""

from __future__ import annotations

import copy
import json
import math

import pytest
from hypothesis import given, strategies as st

from generators import quality
from generators.outline import Outline
from generators.quality import (METRICS, OutOfBand, QualityReport, UNBOUNDED, bands_for,
                                bands_for_spec, evaluate, measure, quality_summary, spec_key)
from generators.zone_spec import CorridorSpec, GateSpec, RoomSpec, ZoneSpec


# ---------------------------------------------------------------------------
# Spec helpers
# ---------------------------------------------------------------------------

def _room(rid, *, role="standard", depth=0, z=0.0, w=100.0, d=100.0, stype="", district=0,
          outline=None):
    return RoomSpec(rid, 0.0, 0.0, floor_z=z, width=w, depth=d, role=role, graph_depth=depth,
                    semantic_type=stype, district=district, outline=outline)


def _cor(cid, a, b):
    return CorridorSpec(cid, 0.0, 0.0, 0.0, 0.0, from_room=a, to_room=b)


def _spec(rooms, pairs, **kw):
    spec = ZoneSpec("q", **kw)
    spec.rooms = rooms
    spec.corridors = [_cor(f"c{i}", a, b) for i, (a, b) in enumerate(pairs)]
    return spec


def _square(side):
    return Outline(verts=[(0.0, 0.0), (side, 0.0), (side, side), (0.0, side)],
                   cells=[[0, 1, 2, 3]], core=(0.0, 0.0, 1.0, 1.0))


# ---------------------------------------------------------------------------
# Hand-worked specs
# ---------------------------------------------------------------------------

def test_line():
    rooms = [_room("a", role="entrance", depth=0, stype="hall"),
             _room("b", depth=1, stype="hall"),
             _room("c", depth=2, stype="crypt"),
             _room("d", role="climax", depth=3, stype="crypt")]
    m = measure(_spec(rooms, [("a", "b"), ("b", "c"), ("c", "d")])).metrics
    assert m == {"cyclomatic": 0.0, "max_degree": 2.0, "dead_end_ratio": 0.5,
                 "critical_path_ratio": 1.0, "branching_factor": 2.0, "elevation_range": 0.0,
                 "elevation_levels": 1.0, "role_diversity": 3.0, "room_type_diversity": 0.5,
                 "size_cv": 0.0, "district_balance": 1.0}


def test_loop_counts_parallel_corridors_once_and_ignores_stubs():
    rooms = [_room("a", role="entrance"), _room("b", depth=1), _room("c", depth=2),
             _room("d", role="climax", depth=1)]
    pairs = [("a", "b"), ("b", "c"), ("c", "d"), ("d", "a"),
             ("b", "a"),            # parallel, the other way round
             ("a", ""), ("c", "x"), ("d", "d")]   # a stub, an unknown room, a self-loop
    m = measure(_spec(rooms, pairs)).metrics
    assert m["cyclomatic"] == 1.0
    assert m["max_degree"] == 2.0
    assert m["dead_end_ratio"] == 0.0
    assert m["branching_factor"] == 2.0
    assert m["critical_path_ratio"] == round(1 / 3, 6)


def test_star():
    rooms = [_room("hub", role="entrance")] + [_room(f"l{i}", role="deadend", depth=1)
                                                for i in range(4)]
    m = measure(_spec(rooms, [("hub", f"l{i}") for i in range(4)])).metrics
    assert m["cyclomatic"] == 0.0
    assert m["max_degree"] == 4.0
    assert m["dead_end_ratio"] == 0.8
    assert m["branching_factor"] == 4.0
    # No climax role: the deepest room (the first leaf) is the climax.
    assert m["critical_path_ratio"] == 0.25
    assert m["role_diversity"] == 2.0


def test_two_levels_and_districts():
    rooms = [_room("a", z=0.0, district=0), _room("b", z=3.0, district=0),
             _room("c", z=48.0, district=0), _room("d", z=50.0, district=1)]
    m = measure(_spec(rooms, [("a", "b"), ("b", "c"), ("c", "d")])).metrics
    assert m["elevation_range"] == 50.0
    assert m["elevation_levels"] == 2.0          # bins 0, 0, 6, 6
    assert m["district_balance"] == round(1 / 3, 6)


def test_outline_area_feeds_size_cv():
    rooms = [_room("a", outline=_square(50.0)), _room("b"), _room("c"), _room("d")]
    m = measure(_spec(rooms, [("a", "b"), ("b", "c"), ("c", "d")])).metrics
    areas = [2500.0, 10000.0, 10000.0, 10000.0]
    mean = sum(areas) / 4
    sd = math.sqrt(sum((a - mean) ** 2 for a in areas) / 4)
    assert m["size_cv"] == round(sd / mean, 6)
    assert quality.floor_area(rooms[0]) == 2500.0


def test_no_rooms_is_all_zero_and_passes():
    report = measure(ZoneSpec("w", zone_type="wilderness"))
    assert report.metrics == {k: 0.0 for k in METRICS}
    assert report.passed and report.score == 0 and report.out_of_band == []


def test_band_table_is_unbounded_for_now():
    assert quality.BAND_TABLE == {}
    for zt in ("dungeon", "city", "outdoor_dungeon", "wilderness"):
        for layout in ("classic", "graph"):
            for v in ("flat", "moderate", "dramatic", None):
                assert bands_for(zt, layout, 12, v) == {m: UNBOUNDED for m in METRICS}


# ---------------------------------------------------------------------------
# spec_key
# ---------------------------------------------------------------------------

def test_spec_key_reads_layout_from_the_spec_and_takes_verticality():
    rooms = [_room(c) for c in "abcde"]
    classic = _spec(rooms, [])
    assert spec_key(classic) == ("dungeon", "classic", 5, "moderate")
    graph = _spec(rooms, [], zone_type="outdoor_dungeon")
    graph.layout = {"engine": "graph", "rule_set": "x"}
    assert spec_key(graph, "dramatic") == ("outdoor_dungeon", "graph", 5, "dramatic")


# ---------------------------------------------------------------------------
# 24.4: the unbounded cases
# ---------------------------------------------------------------------------

_TIGHT = {m: (100.0, 200.0) for m in METRICS}


@pytest.fixture
def tight_table(monkeypatch):
    table = {("dungeon", "classic", "moderate"): [(1, 30, dict(_TIGHT))]}
    monkeypatch.setattr(quality, "BAND_TABLE", table)
    return table


def test_rows_apply_by_room_count(tight_table, monkeypatch):
    monkeypatch.setattr(quality, "BAND_TABLE", {("dungeon", "classic", "flat"): [
        (4, 6, {"cyclomatic": (0.0, 0.0)}), (7, 30, {"cyclomatic": (1.0, None)})]})
    assert bands_for("dungeon", "classic", 5, "flat")["cyclomatic"] == (0.0, 0.0)
    assert bands_for("dungeon", "classic", 9, "flat")["cyclomatic"] == (1.0, None)
    assert bands_for("dungeon", "classic", 9, "flat")["max_degree"] == UNBOUNDED
    assert bands_for("dungeon", "classic", 31, "flat")["cyclomatic"] == UNBOUNDED
    assert bands_for("dungeon", "graph", 9, "flat")["cyclomatic"] == UNBOUNDED


@pytest.mark.parametrize("n", [0, 1, 2, 3])
def test_fewer_than_four_rooms_is_all_unbounded(tight_table, n):
    assert bands_for("dungeon", "classic", n, "moderate") == {m: UNBOUNDED for m in METRICS}
    rooms = [_room(f"r{i}", district=i) for i in range(n)]
    assert measure(_spec(rooms, [], dungeon_theme="temple")).passed


def test_four_rooms_are_bounded(tight_table):
    assert bands_for("dungeon", "classic", 4, "moderate") == _TIGHT


def test_one_district_leaves_district_balance_unbounded(tight_table):
    rooms = [_room(f"r{i}") for i in range(5)]
    bands = bands_for_spec(_spec(rooms, [], dungeon_theme="temple"))
    assert bands["district_balance"] == UNBOUNDED
    assert bands["cyclomatic"] == _TIGHT["cyclomatic"]
    rooms[0].district = 1
    assert bands_for_spec(_spec(rooms, [], dungeon_theme="temple"))["district_balance"] \
        == _TIGHT["district_balance"]


def test_no_purpose_leaves_room_type_diversity_unbounded(tight_table):
    rooms = [_room(f"r{i}") for i in range(5)]
    assert bands_for_spec(_spec(rooms, []))["room_type_diversity"] == UNBOUNDED
    assert bands_for_spec(_spec(rooms, [], dungeon_theme="tomb"))["room_type_diversity"] \
        == _TIGHT["room_type_diversity"]
    report = measure(_spec(rooms, []))
    assert "room_type_diversity" not in [o.metric for o in report.out_of_band]
    assert "district_balance" not in [o.metric for o in report.out_of_band]


# ---------------------------------------------------------------------------
# quality_summary
# ---------------------------------------------------------------------------

def test_quality_summary_shape():
    r = QualityReport(metrics={"cyclomatic": 0.0}, out_of_band=[OutOfBand("cyclomatic", 0.0, 1.0, None)],
                      passed=False, score=1.0, degraded=True, reason="quality_degraded")
    s = quality_summary(r)
    assert s == {"degraded": True, "reason": "quality_degraded", "score": 1.0,
                 "metrics": {"cyclomatic": 0.0},
                 "out_of_band": [{"metric": "cyclomatic", "value": 0.0, "lo": 1.0, "hi": None}]}
    assert json.loads(json.dumps(s)) == s
    ok = quality_summary(measure(ZoneSpec("w")))
    assert ok["degraded"] is False and ok["reason"] is None and ok["score"] == 0
    assert ok["out_of_band"] == [] and set(ok["metrics"]) == set(METRICS)


# ---------------------------------------------------------------------------
# Hypothesis: 24.2 (stable) and 24.3 (pass, list, score)
# ---------------------------------------------------------------------------

_ROLES = st.sampled_from(["entrance", "hub", "deadend", "climax", "standard", ""])
_TYPES = st.sampled_from(["", "barracks", "crypt", "shrine", "hall"])
_finite = st.floats(-500, 500, allow_nan=False, allow_infinity=False)
_size = st.floats(1, 400, allow_nan=False, allow_infinity=False)


@st.composite
def specs(draw):
    n = draw(st.integers(0, 10))
    rooms = []
    for i in range(n):
        outline = _square(draw(_size)) if draw(st.booleans()) and i % 3 == 0 else None
        rooms.append(RoomSpec(
            f"r{i}", draw(_finite), draw(_finite), floor_z=draw(_finite), width=draw(_size),
            depth=draw(_size), role=draw(_ROLES), graph_depth=draw(st.integers(0, 9)),
            semantic_type=draw(_TYPES), district=draw(st.integers(0, 2)), outline=outline,
            prop_hints=draw(st.lists(st.sampled_from(["altar", "brazier"]), max_size=2)),
            encounter_intent=draw(st.sampled_from(["", "ambush"])), boss=draw(st.booleans())))
    ids = [r.id for r in rooms] + ["", "nowhere"]
    pairs = draw(st.lists(st.tuples(st.sampled_from(ids), st.sampled_from(ids)), max_size=16))
    spec = _spec(rooms, pairs, dungeon_theme=draw(st.sampled_from(["", "temple"])))
    if rooms and draw(st.booleans()):
        spec.layout = {"engine": "graph"}
    return spec


_bound = st.one_of(st.none(), st.floats(-50, 50, allow_nan=False))


@st.composite
def band_sets(draw):
    out = {}
    for m in METRICS:
        lo, hi = draw(_bound), draw(_bound)
        if lo is not None and hi is not None and lo > hi:
            lo, hi = hi, lo
        out[m] = (lo, hi)
    return out


def _same(a: QualityReport, b: QualityReport):
    assert (a.metrics, a.passed, a.out_of_band, a.score) == (b.metrics, b.passed, b.out_of_band,
                                                             b.score)


@given(specs(), band_sets())
def test_repeat_and_json_round_trip_measure_the_same(spec, bands):
    first = measure(spec, bands)
    _same(first, measure(spec, bands))
    back = ZoneSpec.from_dict(json.loads(json.dumps(spec.to_dict())))
    _same(first, measure(back, bands))
    _same(measure(spec), measure(back))


@given(specs(), band_sets(), st.data())
def test_advisory_fields_and_gates_do_not_matter(spec, bands, data):
    first = measure(spec, bands)
    other = copy.deepcopy(spec)
    for r in other.rooms:
        r.prop_hints = data.draw(st.lists(st.sampled_from(["x", "y", "z"]), max_size=3))
        r.encounter_intent = data.draw(st.sampled_from(["", "patrol", "boss fight"]))
        r.boss = data.draw(st.booleans())
    other.gates = [GateSpec(f"g{i}", f"c{i}", 0, 0, 0, "r0", 0, 0, 0, tier=i)
                   for i in range(data.draw(st.integers(0, 3)))]
    _same(first, measure(other, bands))


def _inside(v, band):
    lo, hi = band
    return (lo is None or v >= lo) and (hi is None or v <= hi)


@given(specs(), band_sets())
def test_pass_list_and_score(spec, bands):
    r = measure(spec, bands)
    failing = [m for m in METRICS if not _inside(r.metrics[m], bands[m])]
    assert r.passed == (not failing)
    assert [o.metric for o in r.out_of_band] == failing
    for o in r.out_of_band:
        assert (o.value, o.lo, o.hi) == (r.metrics[o.metric], *bands[o.metric])
    assert (r.score == 0) == r.passed
    assert r.score >= 0
    assert not r.degraded and r.reason == ""


@given(st.sampled_from(METRICS), band_sets(), st.floats(0.01, 100), st.floats(0.01, 100),
       st.booleans())
def test_score_strictly_increases_moving_away(metric, bands, step1, step2, below):
    lo, hi = bands[metric]
    bound = lo if below else hi
    if bound is None:
        bands[metric] = (0.0, None) if below else (None, 0.0)
        bound = 0.0
    sign = -1 if below else 1
    near, far = bound + sign * step1, bound + sign * (step1 + step2)
    metrics = {m: 0.0 for m in METRICS}
    # Every other metric in its band, so only `metric` scores.
    clear = {m: UNBOUNDED for m in METRICS}
    clear[metric] = bands[metric]
    a = evaluate(dict(metrics, **{metric: near}), clear)
    b = evaluate(dict(metrics, **{metric: far}), clear)
    assert 0 < a.score < b.score
    # The normaliser: the band width, or |bound| when half-open, at least 1.
    blo, bhi = clear[metric]
    width = (bhi - blo) if (blo is not None and bhi is not None) else abs(bound)
    assert a.score == pytest.approx(abs(near - bound) / max(1.0, width))
