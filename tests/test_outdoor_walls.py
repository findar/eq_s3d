"""Room walls task 11 (Requirement 10): outdoor dungeons draw their rooms' walls, and step 5
and 7's guarantees hold. The Tunnel is a door like any other.
"""

import random

import numpy as np
import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.outdoor_dungeon import MOUTH_FLOOR_MATERIAL, MOUTH_WALL_MATERIAL, tunnel_doors
from generators.pipeline import generate_validated


def _plan(rooms=5, walls="", theme="", race="", verticality="moderate", layout="graph"):
    return ZonePlan(name="w11", zone_type="outdoor_dungeon", room_count=rooms, layout=layout, walls=walls,
                    dungeon_theme=theme, dungeon_race=race, verticality=verticality).validate()


def test_no_theme_is_a_cave_and_a_theme_keeps_its_style():
    assert plan_to_spec(_plan(), seed=4).layout["walls"] == "rough"
    assert plan_to_spec(_plan(theme="temple"), seed=4).layout["walls"] == "built"
    assert plan_to_spec(_plan(theme="temple", walls="hewn"), seed=4).layout["walls"] == "hewn"


def test_classic_outdoor_dungeons_stay_rectangles():
    spec = plan_to_spec(_plan(layout="classic"), seed=4)
    assert all(r.outline is None for r in spec.rooms)


def test_the_tunnel_has_a_throat_into_its_room():
    spec = plan_to_spec(_plan(), seed=4)
    (room_id, sides), = tunnel_doors(spec).items()
    room = next(r for r in spec.rooms if r.id == room_id)
    (side, cuts), = sides.items()
    (c0, c1, _top), = cuts
    (x0, y0, _), (x1, y1, _) = room.bounds
    plane = {"S": y0 + 0.5, "N": y1 - 0.5, "W": x0 + 0.5, "E": x1 - 0.5}[side]
    along = np.linspace(c0 + 0.5, c1 - 0.5, 5)
    probe = (np.c_[along, np.full(5, plane)] if side in "NS" else np.c_[np.full(5, plane), along])
    assert room.outline.contains(probe).all()
    assert room.outline.extra_doors == [(side, c0, c1)]


def test_terrain_and_mouth_materials_survive_a_rock_look():
    spec = plan_to_spec(_plan(walls="rough"), seed=4)
    assert MOUTH_FLOOR_MATERIAL in spec.materials and MOUTH_WALL_MATERIAL in spec.materials
    assert any(n.startswith("wild_") or n.startswith("liquid_") for n in spec.materials)
    assert any("_rock_wall" in r.wall_material for r in spec.rooms)


@pytest.mark.slow
@pytest.mark.parametrize("walls, theme, race, rooms, verticality, seed", [
    ("", "", "", 5, "moderate", 4),
    ("", "", "", 8, "dramatic", 13),         # two Levels and a bridge
    ("hewn", "", "", 5, "moderate", 6),
    ("built", "temple", "", 5, "flat", 9),
    ("rough", "", "ogre", 5, "moderate", 3),
])
def test_built_outdoor_dungeons_pass_their_gate(tmp_path, walls, theme, race, rooms, verticality, seed):
    plan = _plan(rooms, walls, theme, race, verticality)
    vb = generate_validated(lambda s: plan_to_spec(plan, seed=s), zone_type="outdoor_dungeon", zone_id="w11",
                            rng=random.Random(seed), output_dir=tmp_path, write_glb=False, failure_log=None,
                            max_attempts=4, timeout_s=300.0)
    assert vb.validated, "every room reached from the Outdoor_Spawn, the bowl holds, one Entrance"
    assert vb.attempts <= 2, vb.attempts
