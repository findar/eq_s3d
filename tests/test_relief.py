"""Room walls task 6 (Requirement 7; design W7): floors and ceilings move, and nothing
traps the player or breaks a stacked room's Slab.
"""

import random

import numpy as np
import pytest
from hypothesis import given, settings, strategies as st

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from analyzer.traverse import AgentModel, build_walk_surface, check_outline
from generators.geometry import build_mesh
from generators.outline import MAX_GRADE, add_relief, draw_outline
from generators.pipeline import generate_validated
from generators.wall_styles import MIN_HEAD, load_styles

AGENT = AgentModel()


def _room(seed, rise, fall, height=40.0, min_head=8.0, complex="voronoi"):
    box = (-60.0, -50.0, 60.0, 50.0)
    o = draw_outline(box, [("E", -9.0, 9.0), ("N", 20.0, 38.0)], [(-40.0, -30.0, -20.0, -10.0)],
                     complex=complex, cell_size=24.0, fill=0.75, shape="blob", rng=random.Random(seed),
                     wobble=8.0 if complex == "voronoi" else 0.0)
    add_relief(o, height, rise, fall, min_head, 30.0, random.Random(seed + 1))
    return o


@settings(max_examples=40, deadline=None)
@given(seed=st.integers(0, 10 ** 6), rise=st.floats(0.0, 8.0), fall=st.floats(0.0, 30.0),
       height=st.floats(15.0, 60.0), complex=st.sampled_from(["voronoi", "grid"]))
def test_w7_floors_only_rise_and_ceilings_only_fall_within_bounds(seed, rise, fall, height, complex):
    o = _room(seed, rise, fall, height, complex=complex)
    if rise <= 0 and fall <= 0:
        return
    lift, drop, pts = np.array(o.lift), np.array(o.drop), np.array(o.verts)
    assert (lift >= 0).all() and (lift <= rise + 1e-3).all(), "a floor only rises"
    assert (drop >= 0).all() and (drop <= fall + 1e-3).all(), "a ceiling only falls"
    if height - rise >= 8.0:
        assert (height - lift - drop >= 8.0 - 1e-2).all(), "headroom holds"

    def inside(r):
        return (pts[:, 0] >= r[0] - 1e-3) & (pts[:, 0] <= r[2] + 1e-3) & \
               (pts[:, 1] >= r[1] - 1e-3) & (pts[:, 1] <= r[3] + 1e-3)
    for t in o.throats:
        assert (lift[inside(t)] == 0).all() and (drop[inside(t)] == 0).all(), "Throats stay flat"
    assert (lift[inside(o.core)] == 0).all(), "the spawn stands on the floor's own height"
    for c in o.cells:
        for a, b in zip(c, c[1:] + c[:1]):
            run = float(np.hypot(*(pts[a] - pts[b])))
            assert abs(lift[a] - lift[b]) <= run * MAX_GRADE + 2e-3, "no edge is too steep"


def test_a_room_with_no_relief_stays_flat():
    o = _room(1, 0.0, 0.0)
    assert o.lift == [] and o.drop == []


def _plan(theme="warren", rooms=12, rule_set="", verticality="moderate"):
    walls = {"warren": "rough", "mine_delve": "hewn"}.get(theme, "built")
    return ZonePlan(name="w6", zone_type="dungeon", room_count=rooms, layout="graph", rule_set=rule_set, walls=walls,
                    dungeon_theme=theme, verticality=verticality).validate()


@pytest.mark.parametrize("theme", ["warren", "mine_delve"])
def test_rock_styles_move_and_built_does_not(theme):
    spec = plan_to_spec(_plan(theme), seed=4)
    assert any(max(r.outline.drop) > 1 for r in spec.rooms)
    plain = plan_to_spec(_plan(""), seed=4)
    assert all(not r.outline.lift and not r.outline.drop for r in plain.rooms if r.outline)


def test_built_mesh_has_the_relief_and_is_closed_and_walkable():
    spec = plan_to_spec(_plan("warren"), seed=4)
    ter = build_mesh(spec).to_ter("w6")
    surf = build_walk_surface(ter, AGENT)
    for room in spec.rooms:
        v = check_outline(surf, room, spec, AGENT)
        assert v.ok, (room.id, v.reason)


def test_headroom_holds_over_every_floor_vertex():
    for seed in range(5):
        for room in plan_to_spec(_plan("warren"), seed=seed).rooms:
            o = room.outline
            head = room.height - np.array(o.lift) - np.array(o.drop)
            assert head.min() >= min(MIN_HEAD, room.height - max(o.lift)) - 1e-2
            assert max(o.lift) <= room.height, "a floor never reaches its ceiling"


@pytest.mark.slow
@pytest.mark.parametrize("theme, rule_set, verticality, seed", [
    ("warren", "", "dramatic", 10),
    ("warren", "", "moderate", 15),
    ("mine_delve", "", "dramatic", 12),
    ("lava_forge", "", "moderate", 3),
    ("ice_keep", "classic_eq", "dramatic", 11),      # a hewn room under a bridge's slot
])
def test_relief_adds_no_retries(tmp_path, theme, rule_set, verticality, seed):
    plan = _plan(theme, rule_set=rule_set, verticality=verticality)
    vb = generate_validated(lambda s: plan_to_spec(plan, seed=s), zone_type="dungeon", zone_id="w6",
                            rng=random.Random(seed), output_dir=tmp_path, write_glb=False,
                            failure_log=None, max_attempts=3, timeout_s=300.0)
    assert vb.validated and vb.attempts == 1


def test_style_relief_bands_reach_the_build():
    styles = load_styles()
    assert styles["built"].ceiling_spread == (0.0, 0.0)
    assert styles["rough"].ceiling_spread[1] > styles["hewn"].ceiling_spread[0]
