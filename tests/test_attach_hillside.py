"""The outdoor dungeon attached to its ``hillside`` Socket (world-sockets tasks 4 and 12;
design "The Attach stage", "Testing in isolation", P5; Req 3.1, 3.5, 7.2, 7.4).

Every recorded hill of the World corpus (``tests/fixtures/worlds/``: each approach side, dry
and wet) is attached at each Verticality, with both engines and a few races. The World is read
from its file; landscape synthesis, every TER build and the zone gate are patched to raise
(:func:`forbid_world_and_build`), so the Attach stage is tested on what a saved Socket holds
alone. That an Attachment from a saved Socket equals one from the live World, and that
``outdoor_dungeon_spec`` carries it (Req 2.4), is the ``slow`` contract in
``test_world_corpus.py``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from ai.expand import layout_engine
from generators import outdoor_dungeon as od
from generators import stages
from generators.layout import LayoutGenerator
from generators.world import World

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("record_worlds", ROOT / "scripts" / "record_worlds.py")
record_worlds = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(record_worlds)

#: The recordings with a hill: one per approach side, and the wet one.
HILLS = [r["name"] for r in record_worlds.RECORDINGS if "side" in r]

#: (layout, verticality, race): the classic engine, and the graph engine at each Verticality
#: (the stacking ones with a race, whose floor depth is the race's).
CONFIGS = [(None, None, ""), ("graph", "flat", ""), ("graph", "moderate", "ogre"),
           ("graph", "dramatic", "kobold")]


def _forbidden(*_a, **_k):
    raise AssertionError("the Attach stage made terrain, built a TER or ran the gate")


def forbid_world_and_build(monkeypatch) -> None:
    """From here on, landscape synthesis (and so the World stage), every TER build and the
    zone gate (traversal, the outdoor-dungeon report, the walk flood, the format check)
    raise."""
    import analyzer.rof2check as rc
    import analyzer.traverse as tr
    import core.ter as ct
    import generators.wilderness.build as wb

    for name in ("synthesize_landscape", "_landscape", "landscape_for",
                 "build_wilderness_ter", "_reached_faces", "_gate_zon"):
        monkeypatch.setattr(wb, name, _forbidden)
    for name in ("landscape_for", "build_wilderness_ter", "build_outdoor_dungeon_ter",
                 "build_outdoor_ter", "outdoor_dungeon_report"):
        monkeypatch.setattr(od, name, _forbidden)
    monkeypatch.setattr(ct.TerFile, "__init__", _forbidden)
    monkeypatch.setattr(tr, "validate", _forbidden)
    monkeypatch.setattr(rc, "check_eqg", _forbidden)


@pytest.fixture
def saved(monkeypatch):
    """``saved(name)``: a recorded World read from its file; from then on, making terrain,
    building a TER and the gate raise."""
    def make(name) -> World:
        w = record_worlds.load_world(name)
        forbid_world_and_build(monkeypatch)
        return w
    return make


def attach(world, layout=None, verticality=None, race="", seed=None):
    fields = {"name": "d", "room_count": od.DEFAULT_ROOMS, "verticality": verticality}
    if race:
        fields["dungeon_race"] = race
    engine = layout_engine(layout, "", verticality, outdoor=True) if layout else None
    seed = world.recipe["seed"] if seed is None else seed
    return stages.attach_rooms(world, world.socket("hill0"), fields, seed, engine)


@pytest.mark.parametrize("layout,verticality,race", CONFIGS,
                         ids=[c[1] or "classic" for c in CONFIGS])
@pytest.mark.parametrize("name", HILLS)
def test_hillside_attachment_holds_on_the_corpus(name, layout, verticality, race, saved):
    """P5: from the saved World alone, the rooms lie in the Envelope, the Tunnel is covered
    and within grade, and the Apron (a Terrain edit) digs no undiggable cell and only lowers
    the ground; applying it moves the Spawn only down, and keeps the World itself."""
    world = saved(name)
    hill = world.socket("hill0")
    att = attach(world, layout, verticality, race)
    env, e = att.envelope, att.entrance
    assert att.socket == "hill0" and att.kind == "hillside" and att.layout.rooms
    assert att.rooms_requested == od.DEFAULT_ROOMS
    assert LayoutGenerator.fits(att.layout, env)
    # The floor limit is the dungeon's own: step 5's depth, deeper per extra Level.
    depth = od.floor_depth(verticality, race) if verticality in ("moderate", "dramatic") \
        else od.FLOOR_DEPTH
    assert env.floor_limit == hill.z - depth
    grid = od.socket_grid(hill, world.terrain)
    run = (grid.coord(e.axis, e.portal) - e.wall) * e.outward
    assert run >= od.MIN_TUNNEL
    assert abs(e.floor - e.room_floor) <= od.MAX_GRADE * run + 1e-9
    assert od._tunnel_covered(grid, e, hill.ground["rock_cover"])
    (edit,) = att.edits
    assert edit.socket == "hill0" and edit.cells
    keep = {tuple(p) for p in hill.ground["undiggable"]}
    for i, j, z in edit.cells:
        assert (i, j) not in keep
        assert z <= world.terrain.heights[i, j]
    # The Tunnel, Apron, rooms and corridors as Kept_Clear, for the ground Socket (no hill
    # disc, site-sockets decision 3): the Tunnel runs wall to portal, the Apron out from the
    # portal, then one capsule per room and one per leg of each corridor's built route.
    from generators.routing import corridor_route
    from generators.sites.placement import gap as sp_gap
    tunnel, apron = att.keep_clear[:2]
    assert (apron[0], apron[1]) == (tunnel[2], tunnel[3])        # both meet at the portal
    assert apron[4] > tunnel[4]                                  # the trench is wider
    rooms = {r.id: r for r in att.layout.rooms}
    routes = [corridor_route(c, rooms).waypoints for c in att.layout.corridors]
    legs = [leg for wps in routes for leg in zip(wps, wps[1:])]
    assert att.keep_clear[2:] == stages.dungeon_keep_clear(att.layout)
    assert len(att.keep_clear) == 2 + len(rooms) + len(legs)
    for shape, r in zip(att.keep_clear[2:], att.layout.rooms):   # each room inside its capsule
        for sx in (-1, 1):
            for sy in (-1, 1):
                px, py = r.center_x + sx * r.width / 2, r.center_y + sy * r.depth / 2
                assert sp_gap((px, py, px, py, 0.0), shape) < 0
    for shape, ((x0, y0), (x1, y1)) in zip(att.keep_clear[2 + len(rooms):], legs):
        assert shape[:4] == (x0, y0, x1, y1)
    dug = stages.apply_edits(world, [att])
    moved = dug.terrain.heights != world.terrain.heights
    assert {(int(i), int(j)) for i, j in np.argwhere(moved)} <= {(i, j) for i, j, _ in edit.cells}
    assert dug.spawn[:2] == world.spawn[:2] and dug.spawn[2] <= world.spawn[2]
    assert dug.socket("ground").z == dug.spawn[2]
    assert [tuple(s) for s in dug.socket("ground").ground["keep_clear"]] == list(att.keep_clear)
    assert world.terrain.heights is not dug.terrain.heights   # the World itself is kept
    assert world.socket("ground").ground["keep_clear"] == []


def test_a_socket_that_cant_take_the_dungeon_names_itself(saved):
    """Req 3.5: a hill too small for the minimum rooms is a planning failure the pipeline
    retries (one of ``PLAN_ERRORS``), and it names the Socket."""
    world = saved("outdoor_n")
    hill = world.socket("hill0")
    x, y = hill.x, hill.y
    tiny = [[x, y], [x + 4.0, y], [x, y + 4.0]]
    small = World.from_dict({**world.to_dict(), "sockets": [
        {**s.to_dict(), "ground": {**s.ground, "footprint": tiny}} if s.id == "hill0"
        else s.to_dict() for s in world.sockets]})
    with pytest.raises(od.PLAN_ERRORS, match="'hill0'"):
        attach(small)
