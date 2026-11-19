"""
tests/test_quality_gate.py
--------------------------
The quality gate in the pipeline (zone-generator-quality Req 3, task 3; umbrella 24.5-24.8,
25.4): an unpinned generate Draws and measures before it builds, redraws a failing spec up to
``QUALITY_DRAWS`` times and builds only the chosen one; 32 failures build the lowest score as
``quality_degraded``; a pinned seed builds once as ``quality_outside_bands_pinned``; a
hard-gate failure after the Draws retries with no more Draws; the timeout cuts the Draws
short. The sidecar's ``quality`` is the returned Quality_Block. Rebuilds and edits measure,
never redraw (A4).

The meter is driven by hand: ``compute_metrics`` is replaced by one that reads a value the
test's factory stamps on each spec, and the bands are injected (``quality_bands``), so each
Draw's verdict and score are chosen by the test. The builds are real (a small dungeon), so
each test builds only once or twice.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import generators.builder as builder_mod
import generators.pipeline as pl
import generators.quality as quality_mod
import generators.rebuild as rebuild_mod
from generators.layout import LayoutGenerator
from generators.outdoor_dungeon import PLAN_ERRORS
from generators.quality import quality_summary
from generators.zone_spec import RoomSpec

#: One metric, passing only at 0; a spec's score is its stamped value.
BANDS = {"cyclomatic": (0.0, 0.0)}
PINNED = 1955208177


def _good(value, tag=None):
    spec = LayoutGenerator(zone_type="dungeon", seed=1).generate("qg", room_count=5)
    spec.q_value, spec.q_tag = float(value), tag
    return spec


def _broken(value, tag=None):
    """Fails the hard gate: an isolated room no corridor reaches."""
    spec = _good(value, tag)
    spec.rooms.append(RoomSpec(id="isolated", center_x=100_000.0, center_y=100_000.0,
                               floor_z=0.0, width=200, depth=200, height=100))
    return spec


class Factory:
    """Hands out ``make(i)`` for the i-th call (0-based), recording the seeds asked."""

    def __init__(self, make):
        self.make, self.seeds = make, []

    def __call__(self, seed):
        self.seeds.append(seed)
        return self.make(len(self.seeds) - 1)


@pytest.fixture
def meter(monkeypatch):
    """The meter reads the stamped value; every build is recorded by its spec's tag."""
    monkeypatch.setattr(quality_mod, "compute_metrics",
                        lambda spec: {"cyclomatic": getattr(spec, "q_value", 0.0)})
    built = []
    real = builder_mod.ZoneBuilder.build

    def build(self, *a, **k):
        built.append(getattr(self.spec, "q_tag", None))
        return real(self, *a, **k)

    monkeypatch.setattr(builder_mod.ZoneBuilder, "build", build)
    return built


def _run(factory, tmp_path, **kw):
    kw.setdefault("zone_type", "dungeon")
    kw.setdefault("zone_id", "qg")
    kw.setdefault("output_dir", str(tmp_path))
    kw.setdefault("write_glb", False)
    kw.setdefault("failure_log", tmp_path / "fail.jsonl")
    kw.setdefault("quality_bands", BANDS)
    return pl.generate_validated(factory, **kw)


def _sidecar_quality(vb):
    return json.loads(Path(vb.result.sidecar_path).read_text(encoding="utf-8"))["quality"]


def _block_ok(vb):
    """Umbrella 25.2/25.3 and 25.4: the sidecar holds the returned block, and a block is
    either degraded with a reason and out-of-band entries, or a clean pass."""
    block = quality_summary(vb.quality)
    assert _sidecar_quality(vb) == json.loads(json.dumps(block))
    if block["degraded"]:
        assert block["reason"] and block["out_of_band"] and block["score"] > 0
    else:
        assert block["reason"] is None and block["out_of_band"] == [] and block["score"] == 0
    return block


def test_unpinned_redraws_until_a_pass_and_builds_only_that(meter, tmp_path):
    f = Factory(lambda i: _good([3, 2, 0][i], tag=i))
    vb = _run(f, tmp_path)
    assert len(f.seeds) == 3 and len(set(f.seeds)) == 3     # fresh seed per Draw
    assert meter == [2]                                       # only the passing Draw built
    assert vb.seed == f.seeds[2] and vb.attempts == 1
    assert _block_ok(vb)["degraded"] is False


def test_32_failures_build_the_lowest_score_earliest_on_tie(meter, tmp_path):
    scores = [5.0 + i for i in range(pl.QUALITY_DRAWS)]
    scores[7] = scores[20] = 1.5                              # the lowest, tied
    f = Factory(lambda i: _good(scores[i], tag=i))
    vb = _run(f, tmp_path)
    assert len(f.seeds) == pl.QUALITY_DRAWS
    assert meter == [7]
    assert vb.seed == f.seeds[7]
    block = _block_ok(vb)
    assert block["degraded"] and block["reason"] == pl.REASON_DEGRADED
    assert block["out_of_band"] == [{"metric": "cyclomatic", "value": 1.5, "lo": 0.0, "hi": 0.0}]


def test_pinned_failure_builds_once_marked_pinned(meter, tmp_path):
    f = Factory(lambda i: _good(4, tag=i))
    vb = _run(f, tmp_path, seed=PINNED)
    assert f.seeds == [PINNED] and meter == [0]
    block = _block_ok(vb)
    assert block["reason"] == pl.REASON_PINNED


def test_hard_gate_failure_after_the_draws_retries_without_draws(meter, tmp_path):
    # 32 failing Draws; the best (call 3) fails the hard gate; later calls never Draw again.
    def make(i):
        if i < pl.QUALITY_DRAWS:
            return (_broken if i == 3 else _good)(1.0 if i == 3 else 9.0, tag=i)
        return _good(6.0, tag=i)
    f = Factory(make)
    vb = _run(f, tmp_path, max_attempts=4)
    assert vb.attempts == 2
    assert len(f.seeds) == pl.QUALITY_DRAWS + 1
    assert meter == [3, pl.QUALITY_DRAWS]
    block = _block_ok(vb)
    assert block["reason"] == pl.REASON_DEGRADED and block["metrics"]["cyclomatic"] == 6.0


def test_hard_gate_failure_after_a_passing_draw_draws_again(meter, tmp_path):
    # The budget is per generate: a passing Draw that fails the hard gate leaves the rest.
    f = Factory(lambda i: [_broken(0, 0), _good(2, 1), _good(0, 2)][i])
    vb = _run(f, tmp_path, max_attempts=4)
    assert meter == [0, 2] and vb.attempts == 2
    assert _block_ok(vb)["degraded"] is False


def test_timeout_during_draws_builds_the_best_so_far(meter, tmp_path, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(pl, "time", SimpleNamespace(monotonic=lambda: clock[0]))

    def make(i):
        clock[0] += 1.0                                       # each Draw takes 1 s
        return _good([4, 3, 1, 2, 5, 6, 7, 8][i], tag=i)
    f = Factory(make)
    vb = _run(f, tmp_path, timeout_s=5.5)
    assert len(f.seeds) == 6                                  # 6 s > 5.5 s: stop
    assert meter == [2]
    assert _block_ok(vb)["reason"] == pl.REASON_DEGRADED


def test_plan_error_during_a_draw_is_a_failed_draw(meter, tmp_path):
    err = PLAN_ERRORS[0] if isinstance(PLAN_ERRORS, tuple) else PLAN_ERRORS

    def make(i):
        if i < 2:
            raise err("no room for it")
        return _good(0, tag=i)
    f = Factory(make)
    vb = _run(f, tmp_path)
    assert len(f.seeds) == 3 and meter == [2] and vb.attempts == 1
    assert not (tmp_path / "fail.jsonl").exists()             # not a rejected attempt


def test_quality_draw_unit():
    """``_quality_draw``: a rooms reroll's ``make`` draws the same way; all-PLAN_ERRORS
    raises the last error; the budget is shared and marks itself done."""
    err = PLAN_ERRORS[0] if isinstance(PLAN_ERRORS, tuple) else PLAN_ERRORS
    rng = __import__("random").Random(0)
    budget = pl._DrawBudget(left=3)
    asked = []

    def boom(s):
        asked.append(s)
        raise err("x")
    with pytest.raises(err):
        pl._quality_draw(boom, 11, rng, budget, 0.0, 1e9, BANDS, None)
    assert asked[0] == 11 and len(asked) == 3 and budget.done


def test_ungated_build_measures_and_records(meter, tmp_path):
    f = Factory(lambda i: _good(3, tag=i))
    vb = _run(f, tmp_path, validate_enabled=False)
    assert len(f.seeds) == 1 and meter == [0] and not vb.gated
    assert _block_ok(vb)["reason"] == pl.REASON_DEGRADED
    vb = _run(Factory(lambda i: _good(0, tag=i)), tmp_path / "b", validate_enabled=False)
    assert _block_ok(vb)["degraded"] is False


def test_quality_reason_measures_only(meter, tmp_path):
    # An edit (or rebuild) names its reason: no Draws even with no seed, and that reason.
    f = Factory(lambda i: _good(2, tag=i))
    vb = _run(f, tmp_path, quality_reason=pl.REASON_EDIT)
    assert len(f.seeds) == 1 and meter == [0]
    assert _block_ok(vb)["reason"] == pl.REASON_EDIT


def test_verticality_comes_from_the_request_plan(monkeypatch, tmp_path):
    seen = []
    real = pl.measure

    def spy(spec, bands=None, verticality=None):
        seen.append(verticality)
        return real(spec, bands=bands, verticality=verticality)
    monkeypatch.setattr(pl, "measure", spy)
    f = Factory(lambda i: _good(0))
    _run(f, tmp_path, seed=1, request={"plan": {"verticality": "dramatic"}})
    _run(f, tmp_path / "b", seed=1, request={"plan": {"verticality": "dramatic"}},
         verticality="flat")
    assert seen == ["dramatic", "flat"]


# ---------------------------------------------------------------------------
# Rebuilds and edits (A4): measure only, with the parent's reason or edit_outside_bands
# ---------------------------------------------------------------------------

def _parent(tmp_path, quality):
    d = tmp_path / "v1"
    d.mkdir(parents=True)
    spec = _good(0).to_dict()
    (d / "qg.spec.json").write_text(json.dumps({**spec, "seed": 5}), encoding="utf-8")
    side = {} if quality is None else {"quality": quality}
    (d / "qg.zone.json").write_text(json.dumps(side), encoding="utf-8")
    return d


@pytest.mark.parametrize("parent, want", [
    ({"degraded": True, "reason": "quality_degraded"}, "quality_degraded"),
    ({"degraded": True, "reason": "edit_outside_bands"}, "edit_outside_bands"),
    ({"degraded": False, "reason": None}, pl.REASON_PINNED),
    (None, pl.REASON_PINNED),
])
def test_decor_rebuild_keeps_the_parents_reason(tmp_path, monkeypatch, parent, want):
    monkeypatch.setattr(rebuild_mod, "saved_stages", lambda d, n: None)
    got = {}
    rebuild_mod.rebuild_decor(_parent(tmp_path, parent), {"decor_seed": 3}, zone_id="qg",
                              generate=lambda factory, **kw: got.update(kw))
    assert got["quality_reason"] == want and got["seed"] == 5


def test_edit_build_marks_edit_outside_bands(tmp_path):
    got = {}
    doc = {**_good(0).to_dict(), "seed": 5}
    rebuild_mod.build_spec(tmp_path, doc, zone_id="qg", stages=False,
                           generate=lambda factory, **kw: got.update(kw))
    assert got["quality_reason"] == pl.REASON_EDIT
