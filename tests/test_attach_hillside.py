"""The outdoor dungeon attached to its ``hillside`` Socket (world-sockets task 4; design
"The Attach stage", P5 and P10; Req 2.4, 3.1, 3.5).

Each World is made first, then read back from its JSON text, so the Attach stage runs off
what a saved Socket holds. While it attaches, landscape synthesis and every TER build are
patched to raise: the rooms stage needs neither.
"""

from __future__ import annotations

from dataclasses import asdict

import numpy as np
import pytest

from ai.expand import layout_engine
from generators import outdoor_dungeon as od
from generators import stages
from generators.layout import LayoutGenerator
from generators.world import World, world_for

# (seed, edges, layout, verticality, race): both engines, each Verticality, a few races.
CASES = [
    (0, None, None, None, ""),
    (3, {"N": "zoneline"}, None, None, "ogre"),
    (7, {"E": "river", "S": "zoneline"}, None, None, ""),
    (11, None, "graph", "flat", ""),
    (2, None, "graph", "moderate", "ogre"),
    (5, {"W": "zoneline"}, "graph", "dramatic", "kobold"),
]


def _no_terrain(*_a, **_k):
    raise AssertionError("the Attach stage made terrain")


@pytest.fixture
def saved(monkeypatch):
    """``saved(seed, edges)``: the outdoor dungeon's World, read back from its JSON text;
    from then on, landscape synthesis and TER builds raise."""
    import generators.wilderness.build as wb

    def make(seed, edges) -> World:
        w = World.from_json(world_for("outdoor_dungeon", seed, edges=edges).to_json())
        for name in ("synthesize_landscape", "_landscape", "landscape_for",
                     "build_wilderness_ter"):
            monkeypatch.setattr(wb, name, _no_terrain)
        for name in ("landscape_for", "build_wilderness_ter", "build_outdoor_dungeon_ter",
                     "build_outdoor_ter", "TerFile"):
            monkeypatch.setattr(od, name, _no_terrain)
        return w
    return make


def _attach(world, layout, verticality, race, seed):
    fields = {"name": "d", "room_count": od.DEFAULT_ROOMS, "verticality": verticality}
    if race:
        fields["dungeon_race"] = race
    engine = layout_engine(layout, "", verticality, outdoor=True) if layout else None
    return stages.attach_rooms(world, world.socket("hill0"), fields, seed, engine)


@pytest.mark.parametrize("seed,edges,layout,verticality,race", CASES,
                         ids=[f"{c[0]}-{c[2] or 'classic'}-{c[3] or 'none'}" for c in CASES])
def test_hillside_attachment_holds_without_terrain(seed, edges, layout, verticality, race, saved):
    """P5 and P10: from the saved World alone, the rooms lie in the Envelope, the Tunnel is
    covered and within grade, and the Apron (a Terrain edit) digs no undiggable cell and
    only lowers the ground; applying it moves the Spawn only down."""
    world = saved(seed, edges)
    hill = world.socket("hill0")
    try:
        att = _attach(world, layout, verticality, race, seed)
    except od.PLAN_ERRORS as e:
        assert "'hill0'" in str(e)
        pytest.skip(f"seed {seed} doesn't plan: {e}")
    env, e = att.envelope, att.entrance
    assert att.socket == "hill0" and att.layout.rooms
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
    dug = stages.apply_edits(world, [att])
    moved = dug.terrain.heights != world.terrain.heights
    assert {(int(i), int(j)) for i, j in np.argwhere(moved)} <= {(i, j) for i, j, _ in edit.cells}
    assert dug.spawn[:2] == world.spawn[:2] and dug.spawn[2] <= world.spawn[2]
    assert dug.socket("ground").z == dug.spawn[2]
    assert world.terrain.heights is not dug.terrain.heights   # the World itself is kept


def test_planning_builds_no_ter(monkeypatch):
    """Req 2.4: ``outdoor_dungeon_spec`` plans on the World, building no TER, and the spec
    carries the Attachment: its rooms, Entrance, floor limit and the Spawn after the Apron."""
    import generators.wilderness.build as wb
    seed = 4
    world = world_for("outdoor_dungeon", seed)
    att = _attach(world, None, None, "", seed)
    for name in ("build_wilderness_ter", "build_outdoor_dungeon_ter", "build_outdoor_ter",
                 "TerFile"):
        monkeypatch.setattr(od, name, _no_terrain)
    monkeypatch.setattr(wb, "build_wilderness_ter", _no_terrain)
    spec = od.outdoor_dungeon_spec("d", seed)
    data = spec.wilderness[od.DUNGEON_KEY]
    assert [asdict(r) for r in spec.rooms] == [asdict(r) for r in att.layout.rooms]
    assert data["entrance"] == att.entrance.to_dict()
    assert data["floor_limit"] == att.envelope.floor_limit
    assert tuple(spec.safe_point) == stages.apply_edits(world, [att]).spawn


def test_a_socket_that_cant_take_the_dungeon_names_itself(saved):
    """Req 3.5: a hill too small for the minimum rooms is a planning failure the pipeline
    retries (one of ``PLAN_ERRORS``), and it names the Socket."""
    world = saved(0, None)
    hill = world.socket("hill0")
    x, y = hill.x, hill.y
    tiny = [[x, y], [x + 4.0, y], [x, y + 4.0]]
    small = World.from_dict({**world.to_dict(), "sockets": [
        {**s.to_dict(), "ground": {**s.ground, "footprint": tiny}} if s.id == "hill0"
        else s.to_dict() for s in world.sockets]})
    with pytest.raises(od.PLAN_ERRORS, match="'hill0'"):
        _attach(small, None, None, "", 0)
