"""Room layouts task 20 (Requirements 14.1, 14.4, 14.5; design F15): builds choose Transitions."""

import random
from collections import Counter
from pathlib import Path

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from analyzer.traverse import AgentModel, build_walk_surface, check_transition
from generators.geometry import build_mesh
from generators.mapview import render_map_svg
from generators.topology.ruleset import RuleSetError
from generators.transitions import TRANSITIONS_FILE, draw_transition, load_transitions
from generators.wall_styles import load_styles
from generators.zone_spec import CorridorSpec, RoomSpec, ZoneSpec

AGENT = AgentModel()


def _plan(walls="", rooms=16, theme="", verticality="flat", race=""):
    return ZonePlan(name="tr", zone_type="dungeon", room_count=rooms, layout="graph", walls=walls, features="none",
                    dungeon_theme=theme, dungeon_race=race, verticality=verticality).validate()


def _load(tmp_path, text):
    p = tmp_path / "transitions.toml"
    p.write_text(text, encoding="utf-8")
    return load_transitions(p)


GOOD = TRANSITIONS_FILE.read_text(encoding="utf-8")


@pytest.mark.parametrize("old, new, field", [
    ("seam = 4", "lintel = 4", "forms.lintel"),
    ("seam = 4", "seam = -1", "forms.seam"),
    ("[types.vault]", "[types.shed]", "shed"),
    ("[pairs.built_rough]", "[pairs.built_mud]", "built_mud"),
])
def test_a_bad_file_is_named(tmp_path, old, new, field):
    assert old in GOOD
    with pytest.raises(RuleSetError) as exc:
        _load(tmp_path, GOOD.replace(old, new))
    assert any(field in e.field for e in exc.value.errors), str(exc.value)


def test_every_two_styles_need_a_pair(tmp_path):
    with pytest.raises(RuleSetError) as exc:
        _load(tmp_path, GOOD.replace("[pairs.hewn_rough]\nforms = { seam = 3, none = 3, breach = 1 }\n", ""))
    assert "pair for every two" in str(exc.value)


def test_a_pair_reads_either_way_round():
    rules = load_transitions()
    assert rules.pair("rough", "built") == rules.pair("built", "rough")
    assert rules.pair("hewn", "hewn") == rules.pairs["same"]


def test_room_types_multiply_once_per_end():
    rules = load_transitions()
    base = rules.weights("built", "rough", [("", ""), ("", "")])
    one = rules.weights("built", "rough", [("vault", ""), ("", "")])
    two = rules.weights("built", "rough", [("vault", ""), ("vault", "")])
    assert one["frame"] == base["frame"] * 4 and two["frame"] == base["frame"] * 16
    assert one["seam"] == base["seam"]


def _corridor(width=18.0, height=30.0, steps=0):
    a = RoomSpec("a", 0.0, 0.0, width=100.0, depth=60.0, height=40.0, open_walls=["E"])
    b = RoomSpec("b", 200.0, 0.0, width=100.0, depth=60.0, height=40.0, open_walls=["W"])
    cor = CorridorSpec("c", 50.0, 0.0, 150.0, 0.0, width=width, height=height, from_room="a", to_room="b", steps=steps)
    return cor, {"a": a, "b": b}


class _Only:
    """Rules that always ask for one form."""
    def __init__(self, form):
        self.form = form

    def weights(self, *_):
        return {f: float(f == self.form) for f in ("none", "seam", "frame", "breach")}


@pytest.mark.parametrize("form", ["frame", "breach"])
def test_what_cannot_fit_becomes_a_seam_and_says_so(form):
    styles = load_styles()
    cor, rooms = _corridor(width=13.0)
    rec = draw_transition(cor, rooms, styles["built"], styles["rough"], [], _Only(form), 1, 6.0)
    assert rec["form"] == "seam" and rec["asked"] == form
    assert cor.transition.form == "seam"


def test_between_one_style_what_cannot_fit_is_nothing():
    styles = load_styles()
    cor, rooms = _corridor(width=12.0)
    rec = draw_transition(cor, rooms, styles["built"], styles["built"], [], _Only("frame"), 1, 6.0)
    assert rec == {"corridor": "c", "form": "none", "asked": "frame"} and cor.transition is None


def test_a_low_corridor_takes_no_lintel():
    styles = load_styles()
    cor, rooms = _corridor(height=12.0)
    rec = draw_transition(cor, rooms, styles["built"], styles["rough"], [], _Only("frame"), 1, 6.0)
    assert rec["form"] == "seam"


def test_a_seam_at_a_stair_is_nothing_and_a_frame_stands_at_a_door():
    styles = load_styles()
    cor, rooms = _corridor(steps=-1)
    assert draw_transition(cor, rooms, styles["built"], styles["rough"], [], _Only("seam"), 1, 6.0)["form"] == "none"
    rec = draw_transition(cor, rooms, styles["built"], styles["rough"], [], _Only("frame"), 1, 6.0)
    assert rec["form"] == "frame" and rec["x"] < 57.0


def _mixed(seed, **kw):
    return plan_to_spec(_plan(**kw), seed=seed)


def test_every_frame_has_a_door_spot_on_the_sidecar_and_the_map():
    seen = 0
    for seed in range(8):
        spec = _mixed(seed)
        written = {w["corridor"]: w for w in spec.layout["transitions"]}
        frames = [c for c in spec.corridors if c.transition is not None and c.transition.form == "frame"]
        for cor in frames:
            spot = written[cor.id]["door_spot"]
            seen += 1
            assert (spot["x"], spot["y"]) == (cor.transition.x, cor.transition.y)
            assert spot["facing"] in "EN" and spot["width"] > 0 and spot["height"] > 0
            assert len(spot["finishes"]) == 2
        assert render_map_svg(spec).count('class="door-spot"') == len(frames)
    assert seen


def test_a_zone_of_mixed_styles_takes_every_form():
    forms = Counter(w["form"] for seed in range(10) for w in _mixed(seed).layout["transitions"])
    assert {"none", "seam", "frame", "breach"} <= set(forms)
    assert forms["seam"] >= forms["breach"]


def _break(records, room_id):
    """A room's corridor break, tuned to its finish."""
    record = records[room_id]
    return load_styles()[record["style"]].at_finish(record["scales"]["finish"]).corridor_break


def test_a_seam_looks_like_each_end():
    for seed in range(10):
        spec = _mixed(seed)
        records = spec.layout["rooms"]
        for cor in spec.corridors:
            t = cor.transition
            if t is None or not t.floor_material:
                continue
            assert cor.rough == _break(records, cor.from_room)
            assert t.rough == _break(records, cor.to_room)
            return
    pytest.fail("no corridor changed at a line")


def test_a_corridor_without_one_is_the_rougher_rooms():
    for seed in range(4):
        spec = _mixed(seed)
        records = spec.layout["rooms"]
        for cor in spec.corridors:
            if cor.transition is None and cor.steps == 0 and not cor.bridge:
                ends = (cor.from_room, cor.to_room)
                rougher = min(ends, key=lambda i: records[i]["scales"]["finish"])
                same = records[ends[0]]["style"] == records[ends[1]]["style"]
                assert cor.rough in ({_break(records, i) for i in ends} if same else {_break(records, rougher)})


def test_nothing_but_a_transitions_pieces_changes(monkeypatch):
    """The rooms and the corridors' routes are the same with no Transition at all."""
    def route(spec):
        return [(c["id"], c["from_x"], c["from_y"], c["to_x"], c["to_y"], c["from_z"], c["to_z"], c["width"],
                 c["height"]) for c in spec["corridors"]]
    with_them = _mixed(3).to_dict()
    monkeypatch.setattr("generators.transitions.load_transitions", lambda: _Only("none"))
    without = _mixed(3).to_dict()
    assert with_them["rooms"] == without["rooms"]
    assert route(with_them) == route(without)


@pytest.mark.parametrize("kw", [dict(), dict(theme="temple"), dict(race="giant"), dict(verticality="vertical"),
                                dict(walls="built"), dict(walls="rough")])
def test_every_transition_built_passes_the_gate(kw):
    """First try, the walk through each one."""
    for seed in random.Random(str(kw)).sample(range(1000), 4):
        spec = _mixed(seed, **kw)
        surf = build_walk_surface(build_mesh(spec).to_ter("tr"), AGENT)
        for cor in spec.corridors:
            if cor.transition is not None:
                v = check_transition(surf, cor, spec, AGENT)
                assert v.ok, f"seed {seed} {cor.id}: {v.reason}"
