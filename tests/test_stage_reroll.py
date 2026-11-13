"""A gate failure rerolls only the failing stage (world-sockets task 19, Req 9).

The gate's verdict is scripted (``pipeline._traversal_report`` and the Props-free re-run)
so each fault is forced on a real build; the stage named from it, the seeds each attempt
used and the files the accepted build writes are the pipeline's own.
"""

from __future__ import annotations

import json
import random
from dataclasses import replace

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from analyzer.rof2check import FormatReport
from analyzer.traverse import AgentModel, OutlineResult, RoomResult, TraversalReport
from generators import pipeline
from generators.pipeline import GenerationFailed, generate_validated

PLAN = ZonePlan(name="rr", zone_type="dungeon", room_count=5).validate()


def _factory(seed, rooms_seed=None):
    plan = PLAN if rooms_seed is None else replace(PLAN, rooms_seed=rooms_seed)
    return plan_to_spec(plan, seed=seed)


def _report(spec, *, room=None, outline=None) -> TraversalReport:
    """A failing verdict: ``room`` unreachable, or an ``outline`` (a Prop's) failure."""
    rooms = [RoomResult(r.id, r.role, r.id != room, 1, 1, "cut off" if r.id == room else "")
             for r in spec.rooms]
    if room is not None and room not in {r.id for r in spec.rooms}:
        rooms.append(RoomResult(room, room, False, 1, 0, "cut off"))
    out = [OutlineResult(outline, False, "footprint_cut: crate: cut off")] if outline else []
    return TraversalReport(zone_name=spec.name, agent=AgentModel(), total_rooms=len(rooms),
                           reachable_rooms=sum(r.reachable for r in rooms), rooms=rooms,
                           outlines=out)


FAULTS = {
    # Fails with its Props, passes without them.
    "decor": (lambda s: _report(s, outline=s.rooms[1].id), lambda s: _report(s)),
    # Fails without Props too, on a room of the Attachment.
    "rooms": (lambda s: _report(s, room=s.rooms[1].id), None),
    # Fails on something no Attachment holds.
    "zone": (lambda s: _report(s, room="bowl"), None),
}


@pytest.fixture
def gate(monkeypatch):
    """Script the gate: each call to ``gate(*faults)`` queues one forced fault per attempt;
    once they are spent the real gate judges."""
    queue, bare = [], {}
    real = pipeline._traversal_report

    def traversal(eqg, spec, agent):
        if not queue:
            return real(eqg, spec, agent)
        fail, without = FAULTS[queue.pop(0)]
        report = fail(spec)
        bare[id(report)] = without(spec) if without else report
        return report

    monkeypatch.setattr(pipeline, "_traversal_report", traversal)
    monkeypatch.setattr(pipeline, "_report_without_props",
                        lambda eqg, spec, agent, report: bare[id(report)])
    return lambda *faults: queue.extend(faults)


def _run(tmp_path, factory=_factory, seed=None, name="run", **kw):
    log = tmp_path / f"{name}.jsonl"
    vb = generate_validated(factory, zone_type="dungeon", zone_id=name, seed=seed,
                            output_dir=tmp_path / name, write_glb=False,
                            rng=random.Random(5), failure_log=log, **kw)
    return vb, _lines(log)


def _lines(log):
    return [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []


def _file(vb, kind):
    return (vb.build_dir / f"{vb.spec.name.lower()}.{kind}.json").read_text(encoding="utf-8")


def _pinned(tmp_path, seed):
    vb, _ = _run(tmp_path, seed=seed, name="pinned")
    return vb


@pytest.mark.slow
def test_a_decor_fault_redraws_only_decor_seed(tmp_path, gate):
    gate("decor")
    vb, lines = _run(tmp_path)
    (line,) = lines
    s = line["seed"]
    assert line["stage"] == "decor"
    assert line["seeds"] == {"seed": s, "rooms_seed": s, "decor_seed": s}
    assert vb.attempts == 2 and vb.seed == s
    assert vb.spec.rooms_seed is None and vb.spec.decor_seed not in (None, s)
    base = _pinned(tmp_path, s)
    assert _file(vb, "world") == _file(base, "world")
    assert _file(vb, "attach") == _file(base, "attach")
    assert json.loads(_file(vb, "rooms"))["rooms"] == json.loads(_file(base, "rooms"))["rooms"]


@pytest.mark.slow
def test_a_rooms_fault_keeps_the_world_and_redraws_rooms_seed(tmp_path, gate):
    gate("rooms")
    vb, lines = _run(tmp_path)
    (line,) = lines
    s = line["seed"]
    assert line["stage"] == "rooms"
    assert vb.attempts == 2 and vb.seed == s
    assert vb.spec.rooms_seed not in (None, s) and vb.spec.decor_seed is None
    base = _pinned(tmp_path, s)
    assert _file(vb, "world") == _file(base, "world")
    assert _file(vb, "attach") != _file(base, "attach")


@pytest.mark.slow
def test_an_unattributed_fault_draws_a_fresh_seed(tmp_path, gate):
    gate("zone")
    vb, (line,) = _run(tmp_path)
    assert line["stage"] == "zone" and vb.seed != line["seed"]


@pytest.mark.slow
def test_a_third_stage_failure_draws_a_fresh_seed(tmp_path, gate):
    gate("decor", "rooms", "decor")
    vb, lines = _run(tmp_path)
    assert [x["stage"] for x in lines] == ["decor", "rooms", "decor"]
    first, second, third = (x["seeds"] for x in lines)
    s = first["seed"]
    assert second["seed"] == third["seed"] == s
    assert second["decor_seed"] != s and second["rooms_seed"] == s          # Decor rerolled
    assert third["rooms_seed"] != s and third["decor_seed"] == s            # then the rooms
    assert vb.attempts == 4 and vb.seed != s


@pytest.mark.slow
def test_a_factory_without_rooms_seed_and_a_pinned_stage_draw_a_fresh_seed(tmp_path, gate):
    gate("rooms")
    vb, (line,) = _run(tmp_path, factory=lambda s: plan_to_spec(PLAN, seed=s), name="plain")
    assert line["stage"] == "rooms" and vb.seed != line["seed"]

    def pinned_decor(s):
        spec = _factory(s)
        spec.decor_seed = 77
        return spec
    gate("decor")
    vb, (line,) = _run(tmp_path, factory=pinned_decor, name="pd")
    assert line["seeds"]["decor_seed"] == 77 and vb.seed != line["seed"]
    assert vb.spec.decor_seed == 77


@pytest.mark.slow
def test_a_pinned_seed_fails_as_before_and_names_the_stage(tmp_path, gate):
    gate("decor")
    with pytest.raises(GenerationFailed) as e:
        _run(tmp_path, seed=8)
    assert e.value.pinned and e.value.attempts == 1
    assert e.value.failures[0].stage == "decor"
    assert e.value.failures[0].seeds == {"seed": 8, "rooms_seed": 8, "decor_seed": 8}


def test_blame_reads_the_report(monkeypatch):
    """The rule itself: a format failure, or a fault outside every Attachment, names no stage."""
    spec = _factory(3)

    class Built:
        eqg_path = None
        attachments = [type("A", (), {"layout": spec})()]

    ok, bad = FormatReport(passed=True, checks=[]), FormatReport(passed=False, checks=[])
    rooms = _report(spec, room=spec.rooms[0].id)
    monkeypatch.setattr(pipeline, "_report_without_props", lambda e, s, a, r: r)
    assert pipeline._blame(Built, spec, rooms, ok, None) == "rooms"
    assert pipeline._blame(Built, spec, rooms, bad, None) == "zone"
    assert pipeline._blame(Built, spec, _report(spec, room="bowl"), ok, None) == "zone"
    monkeypatch.setattr(pipeline, "_report_without_props", lambda e, s, a, r: _report(s))
    assert pipeline._blame(Built, spec, _report(spec, outline="r1"), ok, None) == "decor"
