"""The rooms -> decor hand-off (roadmap step 11, Req 13; task 18).

The fast tests read the recorded corpus (``tests/fixtures/rooms/``) and build nothing but a
small city. The ``slow`` contract test re-records a sample of the corpus from its seeds and
compares: when room generation changes on purpose, re-record with
``python scripts/record_rooms.py``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from generators.room_context import RoomContext, contexts, dumps, load

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("record_rooms", ROOT / "scripts" / "record_rooms.py")
record_rooms = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(record_rooms)

FILES = sorted(record_rooms.FIXTURES.glob("*.json"))
CORPUS_MB = 5.0


def _corpus():
    return [(path, *load(path)) for path in FILES]


CORPUS = _corpus()
ROOMS = [c for _p, _r, rooms in CORPUS for c in rooms]


def test_every_recording_is_on_disk_and_nothing_else():
    assert sorted(p.stem for p in FILES) == sorted(r["name"] for r in record_rooms.RECORDINGS)


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_a_recording_reads_back_to_the_same_text(path, tmp_path):
    recipe, rooms = load(path)
    assert recipe == record_rooms.recipe_named(path.stem)
    out = tmp_path / path.name
    record_rooms.save(out, recipe, rooms)
    assert out.read_bytes() == path.read_bytes()


def test_each_context_round_trips_through_json():
    for c in ROOMS:
        text = c.to_json()
        back = RoomContext.from_json(text)
        assert back.to_json() == text
        np.testing.assert_array_equal(back.floor, c.floor)
        assert back.reached.dtype == bool and back.reached.shape == c.floor.shape


def test_a_context_from_another_version_is_refused():
    d = ROOMS[0].to_dict()
    d["version"] += 1
    with pytest.raises(ValueError, match="version"):
        RoomContext.from_dict(d)


def test_the_corpus_covers_every_room_type_wall_style_and_race():
    assert record_rooms.missing(ROOMS) == {}
    have = record_rooms.coverage(ROOMS)
    assert have["zone_type"] == {"dungeon", "city", "outdoor_dungeon", "wilderness"}
    assert have["site"], "no Sites recorded"


def test_the_corpus_is_small():
    size = sum(p.stat().st_size for p in FILES) / 1024 / 1024
    assert size < CORPUS_MB, f"corpus is {size:.2f} MB"


def test_contexts_are_consistent():
    """What every decor test leans on: the grid's parts agree, walls face into the room,
    doors and POIs sit in the room."""
    for c in ROOMS:
        where = f"{c.zone_type}/{c.id}"
        floor = ~np.isnan(c.floor)
        assert floor.any(), where
        assert not (c.reached & ~floor).any(), where
        assert c.reached.any(), where
        x0, y0, z0, x1, y1, z1 = c.box
        if c.source == "site":
            assert c.ceiling is None and not c.walls and not c.doors, where
            assert c.features and c.pois and c.clear, where
            continue
        assert not (c.spine & ~floor).any(), where
        lid = ~np.isnan(c.ceiling)
        assert (c.ceiling[lid] > c.floor[lid]).all(), where
        assert c.walls and c.doors, where
        for w in c.walls:
            assert abs(np.hypot(w.nx, w.ny) - 1) < 0.02 and w.top > w.bottom, where
            assert x0 - 0.02 <= w.x <= x1 + 0.02 and y0 - 0.02 <= w.y <= y1 + 0.02, where
        # Walls face the floor: a step off most walls, along the normal, is floor.
        into = 0
        for w in c.walls:
            i = int(round((w.x + 3 * w.nx - c.origin[0]) / c.cell))
            j = int(round((w.y + 3 * w.ny - c.origin[1]) / c.cell))
            into += 0 <= i < floor.shape[0] and 0 <= j < floor.shape[1] and floor[i, j]
        assert into >= 0.9 * len(c.walls), where
        for d in c.doors:
            assert d.side in "NSEW" and d.c1 > d.c0 and d.throats, where
            cx0, cy0, cx1, cy1 = d.clear
            assert x0 - 0.01 <= cx0 < cx1 <= x1 + 0.01 and y0 - 0.01 <= cy0 < cy1 <= y1 + 0.01, where
        for p in c.pois:
            assert x0 <= p["x"] <= x1 and y0 <= p["y"] <= y1, where


def test_rough_walls_follow_the_mesh_not_a_flat_box():
    """On a rough room the walls' feet lift with the floor: their bottoms aren't all the floor."""
    rough = [c for c in ROOMS if c.style == "rough"]
    assert rough
    assert any(len({w.bottom for w in c.walls}) > 1 for c in rough)


def test_reading_contexts_changes_nothing_about_the_build():
    from ai.expand import plan_to_spec
    from ai.schema import ZonePlan
    from generators.backends import backend_for

    spec = plan_to_spec(ZonePlan(name="rc_still", zone_type="city", room_count=4), seed=5)
    ter = backend_for(spec.zone_type).build(spec, "ter_rc_still", 2)
    before = (dumps(spec.to_dict()), ter.to_bytes())
    rooms = contexts(spec, ter)
    assert len(rooms) == len(spec.rooms)
    assert (dumps(spec.to_dict()), ter.to_bytes()) == before


# A sample, cheap to build, over every zone type and wall style.
SAMPLE = ["fortress_goblin_built", "warren_kobold_rough", "temple_human_hewn", "city_plain",
          "outdoor_tomb_goblin", "wilderness_sites"]


@pytest.mark.slow
@pytest.mark.parametrize("name", SAMPLE)
def test_the_corpus_still_matches_the_room_stage(name):
    """The contract: re-recorded from its seed, a recording is what's saved. If room
    generation changed on purpose, re-record: ``python scripts/record_rooms.py``."""
    _recipe, saved = load(record_rooms.path_for(name))
    now = record_rooms.record(record_rooms.recipe_named(name))
    assert [c.to_json() for c in now] == [c.to_json() for c in saved], \
        f"{name} differs from the room stage: re-record with scripts/record_rooms.py"
