"""The World corpus (world-sockets Req 7.1, 7.3; design "Testing in isolation").

The fast tests read the recorded Worlds (``tests/fixtures/worlds/``) and make nothing. The
``slow`` contract test re-makes the recordings from their seeds and compares the text: when
the World stage changes on purpose, re-record with ``python scripts/record_worlds.py``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from generators.world import World, load

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("record_worlds", ROOT / "scripts" / "record_worlds.py")
record_worlds = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(record_worlds)

FILES = sorted(record_worlds.FIXTURES.glob("*.json"))
CORPUS_MB = 3.0
CORPUS = {p.stem: load(p) for p in FILES}


def test_every_recording_is_on_disk_and_nothing_else():
    assert sorted(CORPUS) == sorted(r["name"] for r in record_worlds.RECORDINGS)


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_a_recording_loads_as_recorded(path):
    """It reads back to the same text, and holds its recording's inputs and approach side."""
    world = CORPUS[path.stem]
    assert world.to_json() == path.read_text(encoding="utf-8")
    recipe = record_worlds.recipe_named(path.stem)
    assert (world.recipe["zone_type"], world.recipe["seed"]) == (recipe["zone_type"], recipe["seed"])
    for side, edge in recipe.get("edges", {}).items():
        assert world.recipe["edges"][side] == edge
    sides = [s.side for s in world.sockets if s.kind == "hillside"]
    assert sides == ([recipe["side"]] if "side" in recipe else [])


def test_the_corpus_covers_every_biome_side_water_case_and_socket_kind():
    assert record_worlds.missing(list(CORPUS.values())) == {}


def test_the_corpus_is_small():
    size = sum(p.stat().st_size for p in FILES) / 1024 / 1024
    assert size < CORPUS_MB, f"corpus is {size:.2f} MB"


@pytest.mark.slow
@pytest.mark.parametrize("name", [r["name"] for r in record_worlds.RECORDINGS])
def test_the_corpus_still_matches_the_world_stage(name):
    """The contract: re-made from its seed, a recording is what's saved. If the World stage
    changed on purpose, re-record: ``python scripts/record_worlds.py``. (A World is cheap to
    make, so every recording is checked, not a sample.)"""
    now: World = record_worlds.record(record_worlds.recipe_named(name))
    assert now.to_json() == record_worlds.path_for(name).read_text(encoding="utf-8"), \
        f"{name} differs from the World stage: re-record with scripts/record_worlds.py"
