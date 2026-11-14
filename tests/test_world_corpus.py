"""The World corpus (world-sockets Req 7.1, 7.3; design "Testing in isolation").

The fast tests read the recorded Worlds (``tests/fixtures/worlds/``) and make nothing. The
``slow`` contract test re-makes the recordings from their seeds and compares the text: when
the World stage changes on purpose, re-record with ``python scripts/record_worlds.py``. The
``slow`` attach contract (P4) checks that an Attachment from a recording equals one from the
live World.
"""

from __future__ import annotations

import dataclasses
import importlib.util
from pathlib import Path

import numpy as np
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
    """... and point Sockets (site-sockets task 4): a Group of two or more points in each
    landscape zone type, and an outdoor dungeon's points over its hill."""
    assert record_worlds.missing(list(CORPUS.values())) == {}


@pytest.mark.parametrize("path", [p for p in FILES if p.stem.startswith("outdoor_")],
                         ids=lambda p: p.stem)
def test_an_outdoor_world_holds_one_landscape(path):
    """Task 20: an outdoor dungeon's World is made on its placed Landform (the recipe's is the
    hill's), and its Spawn stands on the terrain's ground."""
    world = CORPUS[path.stem]
    t = world.terrain
    assert world.recipe["landform"] == world.socket("hill0").ground["landform"]
    assert world.recipe["landform"]["approach"] == world.socket("hill0").side
    i, j = (round((v - o) / t.res - 0.5) for v, o in zip(world.spawn[:2], t.origin))
    assert world.spawn[2] == t.heights[i, j]


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


def _plain(v):
    """``v`` as plain data to compare exactly: floats by ``repr``, arrays by dtype, shape and
    values, dataclasses and objects by class and fields. Functions (the Envelope's
    ``surface``) are left out; the test samples them. Pickled bytes won't do: a loaded and a
    live World share strings differently, so equal Attachments pickle apart."""
    if isinstance(v, float):
        return ("f", repr(v))
    if isinstance(v, (str, int, bool, type(None))):
        return v
    if isinstance(v, np.generic):
        return _plain(v.item())
    if isinstance(v, np.ndarray):
        return ("a", str(v.dtype), v.shape, _plain(v.tolist()))
    if isinstance(v, dict):
        return ("d", sorted((repr(k), _plain(x)) for k, x in v.items()))
    if isinstance(v, (list, tuple)):
        return (type(v).__name__, [_plain(x) for x in v])
    if callable(v):
        return "callable"
    if dataclasses.is_dataclass(v):
        return (type(v).__name__, [(f.name, _plain(getattr(v, f.name)))
                                   for f in dataclasses.fields(v)])
    return (type(v).__name__, _plain(vars(v)))


def _same_attachment(a, b) -> bool:
    if _plain(a) != _plain(b):
        return False
    if a.envelope is None:
        return b.envelope is None
    pts = np.array([*a.envelope.footprint, a.envelope.entry[:2]], dtype=float)
    return _plain(a.envelope.surface(pts[:, 0], pts[:, 1])) == \
        _plain(b.envelope.surface(pts[:, 0], pts[:, 1]))


@pytest.mark.slow
@pytest.mark.parametrize("name", [r["name"] for r in record_worlds.RECORDINGS
                                  if r["zone_type"] in record_worlds.LANDSCAPE])
def test_p4_an_attachment_from_a_saved_socket_equals_the_live_one(name, monkeypatch):
    """P4 (Req 1.5, 7.3): attaching to a recording's Sockets gives exactly what
    attaching to the live World gives (:func:`_plain`, floats by ``repr``): every hill's
    rooms with both engines at each Verticality, then the ground Socket's Sites after the
    hill's edits. For an outdoor
    dungeon the spec ``outdoor_dungeon_spec`` plans (building no TER, Req 2.4) carries that
    Attachment: its rooms, Entrance, floor limit, the Spawn after the Apron, and the
    Kept_Clear the build's ``keep_clear_shapes`` gives (wet ground included)."""
    from dataclasses import asdict

    import generators.wilderness.build as wb
    from generators import outdoor_dungeon as od
    from generators import stages
    from tests.test_attach_hillside import CONFIGS, attach

    recipe = record_worlds.recipe_named(name)
    live, saved = record_worlds.record(recipe), CORPUS[name]
    atts = []
    if "side" in recipe:
        for layout, verticality, race in CONFIGS:
            a = attach(saved, layout, verticality, race)
            assert _same_attachment(a, attach(live, layout, verticality, race)), \
                (layout, verticality, race)
        atts = [attach(saved)]

    def sites(world):
        dug = stages.apply_edits(world, [stages.entrance_attachment(
            world, world.socket("hill0"), a.entrance) for a in atts])
        return stages.attach_sites(dug, dug.socket("ground"), 1001,
                                   biome=world.recipe["biome"], control="dense")
    got = sites(saved)
    assert got.sites.sites or atts, f"{name} gets a Site at dense"
    assert _same_attachment(got, sites(live))

    if atts:
        (att,) = atts

        def no_ter(*_a, **_k):
            raise AssertionError("planning built a TER")
        for n in ("build_wilderness_ter", "build_outdoor_dungeon_ter", "build_outdoor_ter",
                  "TerFile"):
            monkeypatch.setattr(od, n, no_ter)
        monkeypatch.setattr(wb, "build_wilderness_ter", no_ter)
        spec = od.outdoor_dungeon_spec("d", recipe["seed"], edges=recipe.get("edges"))
        data = spec.wilderness[od.DUNGEON_KEY]
        assert [asdict(r) for r in spec.rooms] == [asdict(r) for r in att.layout.rooms]
        assert data["entrance"] == att.entrance.to_dict()
        assert data["floor_limit"] == att.envelope.floor_limit
        assert tuple(spec.safe_point) == stages.apply_edits(saved, [att]).spawn
        assert tuple(od.keep_clear_shapes(spec)) == att.keep_clear
