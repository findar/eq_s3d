"""Sites attached to the ``ground`` Socket (world-sockets task 5; design "The Attach stage",
"Order and Terrain edits", P6; Req 3.2, 3.3).

An outdoor dungeon's World is read back from its JSON text, its Entrance's Attachment is
applied, and the ground Socket attached: it must see the Apron's heights (the built TER's
grid, exact), keep the hill, Tunnel and Apron clear, and give the Sites the built TER gives.
"""

from __future__ import annotations

import pickle

import numpy as np
import pytest

from generators import outdoor_dungeon as od
from generators import stages
from generators.sites.placement import gap, place_sites
from generators.sites.rules import load_sites
from generators.vegetation.placement import ter_heights
from generators.world import World, world_of
import generators.wilderness.build as wb

# (seed, edges): two seeds that get a Site at dense (``test_site_builds.OD_SEEDS``), and one
# with water, whose grid before the water bed sinks differs from the TER's.
CASES = [(1001, None), (1002, None), (7, {"E": "river", "S": "zoneline"})]


@pytest.mark.parametrize("seed,edges", CASES, ids=[str(c[0]) for c in CASES])
def test_p6_ground_sees_the_apron_and_keeps_the_dungeon_clear(seed, edges):
    spec = od.outdoor_dungeon_spec(f"g{seed}", seed, edges=edges)
    spec.sites = "dense"
    ter = od.build_outdoor_dungeon_ter(spec, "ter_t.ter", 2)
    world = World.from_json(world_of(spec).to_json())
    entrance = od.Entrance.from_dict(spec.wilderness[od.DUNGEON_KEY]["entrance"])
    att = stages.entrance_attachment(world, world.socket("hill0"), entrance)

    # The Build's edit and shapes are the ones the Attach stage made when it planned.
    fields = {"name": "d", "room_count": od.DEFAULT_ROOMS, "verticality": None}
    planned = stages.attach_rooms(world, world.socket("hill0"), fields, seed)
    assert planned.entrance == entrance
    assert planned.edits == att.edits and planned.keep_clear == att.keep_clear

    dug = stages.apply_edits(world, [att])
    assert world.socket("ground").ground["keep_clear"] == []     # the World itself is kept
    # The Apron's heights: exactly the built TER's grid.
    built = ter_heights(ter, world.terrain.heights.shape)
    assert np.array_equal(dug.terrain.heights, built)
    assert not np.array_equal(world.terrain.heights, built)
    # The hill, Tunnel and Apron as Kept_Clear: today's shapes, exactly.
    ground = dug.socket("ground")
    shapes = od.keep_clear_shapes(spec)
    assert [tuple(s) for s in ground.ground["keep_clear"]] == list(shapes)
    assert tuple(ground.ground["spawn"][:2]) == tuple(spec.safe_point[:2])

    biome = spec.wilderness["biome"]
    got = stages.attach_sites(dug, ground, stages.rooms_seed(seed), biome=biome,
                              control="dense", rules=load_sites())
    assert got.socket == "ground" and not got.edits
    # The same Sites as placing them on the built TER.
    legacy = place_sites(wb.landscape_for(spec), ter, seed, biome=biome, control="dense",
                         rules=load_sites(), spawn_xy=tuple(spec.safe_point[:2]),
                         keep_clear=shapes)
    assert pickle.dumps(got.sites) == pickle.dumps(legacy)
    assert pickle.dumps(wb.sites_for(spec, ter).placement) == pickle.dumps(got.sites)
    for s in got.sites.sites:
        for c in s.clear:
            for keep in shapes:
                assert gap(c.shape, keep) >= 0.0, (s.kind, c.what, keep)
    if edges is None:
        assert got.sites.sites, "this seed gets a Site at dense"
