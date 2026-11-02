"""Outdoor-dungeon task 6: the backend and the gate (D4, D6, D7, retry)."""

import random

import pytest

from generators import outdoor_dungeon as od
from generators.backends import TerrainBackend
from generators.builder import ZoneBuilder
from generators.pipeline import GenerationFailed, generate_validated
from generators.wilderness.build import build_wilderness_ter, wilderness_spec


def _build(tmp_path, seed, name="odtest"):
    spec = od.outdoor_dungeon_spec(name, seed)
    result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)
    return spec, result


@pytest.mark.parametrize("seed", [0, 5, 11])
def test_every_room_reached_from_outdoor_spawn(tmp_path, seed):
    """D4: the bowl passes, every room is reached from the outdoor Spawn
    (through the Entrance: the dungeon is otherwise sealed), and every
    corridor is continuous."""
    spec, result = _build(tmp_path, seed)
    report = od.outdoor_dungeon_report(result.eqg_path, spec)
    assert report.rooms[0].room_id == "bowl"
    assert report.total_rooms == len(spec.rooms) + 1
    assert report.passed, report.summary()
    assert report.checked_corridors and report.corridors_passed


def test_same_inputs_same_eqg(tmp_path):
    """D6: the same seed gives the same .eqg (the PFS footer's write time
    aside)."""
    _, a = _build(tmp_path / "a", 3)
    _, b = _build(tmp_path / "b", 3)
    assert a.eqg_path.read_bytes()[:-4] == b.eqg_path.read_bytes()[:-4]


def test_plain_wilderness_unchanged():
    """D7: a wilderness spec with no dungeon still builds the plain
    wilderness TER through the terrain backend."""
    spec = wilderness_spec("plain", 4, None)
    assert not od.is_outdoor_dungeon(spec)
    built = TerrainBackend().build(spec, "ter_plain", 2)
    assert built.to_bytes() == build_wilderness_ter(spec, "ter_plain", 2).to_bytes()


def test_planning_failure_is_retried_on_a_fresh_seed(tmp_path):
    """A seed whose dungeon can't be planned is a rejected attempt: the
    pipeline tries a fresh seed; a pinned one fails with a ``plan`` check."""
    seeds = []

    def factory(seed):
        seeds.append(seed)
        if len(seeds) == 1:
            raise od.EntranceError("no wall")
        return od.outdoor_dungeon_spec("odretry", seed)

    vb = generate_validated(factory, zone_type="wilderness", zone_id="odretry",
                            output_dir=tmp_path, write_glb=False,
                            rng=random.Random(1), failure_log=None)
    assert vb.attempts == 2 and vb.validated
    assert len(set(seeds)) == 2

    def never(seed):
        raise od.EntranceError("no wall")

    with pytest.raises(GenerationFailed) as err:
        generate_validated(never, zone_type="wilderness", zone_id="odpinned", seed=9,
                           output_dir=tmp_path, write_glb=False, failure_log=None)
    assert err.value.failures[0].checks == ["plan"]
    assert not (tmp_path / ".attempts").exists()
