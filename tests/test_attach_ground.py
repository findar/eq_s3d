"""Sites attached to the ``ground`` Socket (world-sockets tasks 5 and 12; design "The Attach
stage", "Order and Terrain edits", "Testing in isolation", P6; Req 3.2, 3.3, 7.2, 7.4).

Most tests read a recorded World (``tests/fixtures/worlds/``), attach an outdoor dungeon's
rooms to its hill first where it has one, apply that Attachment and attach the ground Socket,
with landscape synthesis, every TER build and the zone gate patched to raise
(``test_attach_hillside.forbid_world_and_build``). They check the Sites' own rules: Kept_Clear,
spacing, Structures inside their Site, Site_Clear free, POIs on reached ground, misfits
dropped with a reason, the terrain left alone.

One test builds TERs (two seeds, dry and wet): the Build applies the same edits and gets the
same Sites as the Attach stage (P6).
"""

from __future__ import annotations

import math
import pickle
from dataclasses import replace

import numpy as np
import pytest
from scipy.ndimage import label

from analyzer.traverse import AgentModel
from generators import outdoor_dungeon as od
from generators import stages
from generators.sites import placement as sp
from generators.sites.placement import gap, place_sites, reach
from generators.sites.rules import load_sites
from generators.vegetation.placement import SPAWN_CLEARING, ter_heights
from generators.world import World, world_of
import generators.wilderness.build as wb
from tests.test_attach_hillside import attach, forbid_world_and_build, record_worlds

RULES = load_sites()
EPS = 1e-6
#: Every recording with a ground Socket (the landscape zone types).
GROUNDS = [r["name"] for r in record_worlds.RECORDINGS
           if r["zone_type"] in record_worlds.LANDSCAPE]
#: Recorded hills whose open ground takes no Site at the seeds below (the hill fills it).
BARE = {"outdoor_n", "outdoor_w"}
REASONS = {sp.NO_GROUND, sp.NO_APPROACH, sp.NO_ROOM, sp.OUTSIDE, sp.IN_CLEAR, sp.CROWDED,
           sp.APRON_OFF, sp.APRON_BLOCKED, sp.STRUCTURE_GONE, sp.NO_FREE_GROUND, sp.NO_POI,
           sp.NO_STRUCTURES}


@pytest.fixture
def ground(monkeypatch):
    """``ground(name)``: a recorded World with every earlier Attachment applied (an outdoor
    dungeon's rooms on ``hill0``, classic, at the recording's seed), the World as read, and
    those Attachments. From then on, making terrain, building a TER and the gate raise."""
    def make(name):
        world = record_worlds.load_world(name)
        forbid_world_and_build(monkeypatch)
        atts = [attach(world)] if any(s.kind == "hillside" for s in world.sockets) else []
        return stages.apply_edits(world, atts), world, atts
    return make


def _sites(dug, seed, control="dense", rules=RULES, **kw):
    return stages.attach_sites(dug, dug.socket("ground"), seed, biome=dug.recipe["biome"],
                               control=control, rules=rules, **kw)


def _reached(terrain, spawn_xy):
    """The quads the walker reaches from the Spawn's, re-derived from the World's grid: both
    of a quad's triangles no steeper than the agent stands on, no wet or Rim-seal corner,
    joined to the Spawn's quad."""
    h, res = terrain.heights, float(terrain.res)
    a, b, c, d = h[:-1, :-1], h[1:, :-1], h[1:, 1:], h[:-1, 1:]
    steep = np.maximum(np.hypot(b - a, c - b), np.hypot(c - d, d - a)) / res
    walk = np.degrees(np.arctan(steep)) <= AgentModel().walkable_slope_deg
    node = np.asarray(terrain.node_type)
    for bad in (np.isin(node, ("water", "river", "lava")), np.asarray(terrain.rim_seal, bool)):
        walk &= ~(bad[:-1, :-1] | bad[1:, :-1] | bad[1:, 1:] | bad[:-1, 1:])
    labels, _ = label(walk)
    ox, oy = terrain.origin
    i = int(math.floor((spawn_xy[0] - ox) / res - 0.5))
    j = int(math.floor((spawn_xy[1] - oy) / res - 0.5))
    assert labels[i, j], "the Spawn stands on walkable ground"
    return labels == labels[i, j]


# ---------------------------------------------------------------------------
# P6 on the corpus: the ground Socket after the hill
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", GROUNDS)
def test_ground_attachment_keeps_its_rules_on_the_corpus(name, ground):
    """The ground Socket sees the Apron's heights and the hill, Tunnel and Apron as
    Kept_Clear (the shapes the Entrance's Attachment makes from the Entrance alone); its
    Sites keep off them and each other, keep their Structures in and their Site_Clear free,
    and every POI stands on reached ground. Placing them changes no terrain."""
    dug, world, atts = ground(name)
    gsock = dug.socket("ground")
    if atts:
        (att,) = atts
        again = stages.entrance_attachment(world, world.socket("hill0"), att.entrance)
        assert again.edits == att.edits and again.keep_clear == att.keep_clear
        assert [tuple(s) for s in gsock.ground["keep_clear"]] == list(att.keep_clear)
        assert not np.array_equal(dug.terrain.heights, world.terrain.heights)
        assert tuple(gsock.ground["spawn"][:2]) == tuple(world.spawn[:2])
    else:
        assert dug is world and gsock.ground["keep_clear"] == []
    shapes = [tuple(s) for s in gsock.ground["keep_clear"]]
    before = dug.to_json()
    spawn = np.array(gsock.ground["spawn"][:2])
    reached = _reached(dug.terrain, spawn)
    surface = od._grid_surface(dug.terrain.heights, dug.terrain.origin, dug.terrain.res)
    ox, oy = dug.terrain.origin
    res = float(dug.terrain.res)

    got = _sites(dug, 1001)
    assert got.socket == "ground" and got.kind == "ground" and not got.edits
    assert dug.to_json() == before                      # the terrain is left alone (P5)
    p = got.sites
    if name not in BARE:
        assert p.sites, f"{name} gets a Site at dense"
    for s in p.sites:
        outer = s.radius + s.margin
        assert np.linalg.norm(np.array([s.x, s.y]) - spawn) >= SPAWN_CLEARING + outer - EPS
        for c in s.clear:
            for keep in shapes:
                assert gap(c.shape, keep) >= 0.0, (s.kind, c.what, keep)
        assert s.structures
        for t in s.structures:
            assert reach(t.footprint(), s.x, s.y) <= s.radius + EPS, (s.kind, t.kind)
        assert sum(c.what == "approach" for c in s.clear) == 1
        for c in s.clear:
            if c.what == "ground":
                continue
            for other in p.sites:
                for t in other.structures:
                    assert gap(c.shape, t.footprint()) >= -EPS, (s.kind, c.what, t.kind)
        assert s.pois, s.kind
        for poi in s.pois:
            i = int(math.floor((poi.x - ox) / res - 0.5))
            j = int(math.floor((poi.y - oy) / res - 0.5))
            assert reached[i, j], (s.kind, poi.name)
            assert abs(poi.z - float(surface(poi.x, poi.y))) < 1e-3
            for t in s.structures:
                if not t.enterable or t.run:
                    assert gap((poi.x, poi.y, poi.x, poi.y, 0.0), t.footprint()) > 0, \
                        (poi.name, t.kind)
    for k, a in enumerate(p.sites):
        for b in p.sites[k + 1:]:
            need = max(RULES.kinds[a.kind].ground.spacing, RULES.kinds[b.kind].ground.spacing)
            assert math.hypot(a.x - b.x, a.y - b.y) >= need - EPS
    for d in p.drops:
        assert d.reason in REASONS and d.what in ("site", "structure", "poi")
        assert (d.site is None) == (d.what == "site")


@pytest.mark.parametrize("seed,edges", [(1001, None), (7, {"E": "river", "S": "zoneline"})],
                         ids=["1001", "7-wet"])
def test_p6_the_build_applies_the_attach_stages_edits(seed, edges):
    """P6 against a build: the edit and shapes the Attach stage made when it planned are
    the Build's; the Apron's heights are exactly the built TER's grid; the Kept_Clear is
    ``keep_clear_shapes``; the Sites are the ones placed on the built TER, and the build's.
    A seed that gets a Site at dense, and one with water, whose grid before the water bed
    sinks differs from the TER's."""
    spec = od.outdoor_dungeon_spec(f"g{seed}", seed, edges=edges)
    spec.sites = "dense"
    ter = od.build_outdoor_dungeon_ter(spec, "ter_t.ter", 2)
    world = World.from_json(world_of(spec).to_json())
    entrance = od.Entrance.from_dict(spec.wilderness[od.DUNGEON_KEY]["entrance"])
    att = stages.entrance_attachment(world, world.socket("hill0"), entrance)

    planned = attach(world, seed=seed)
    assert planned.entrance == entrance
    assert planned.edits == att.edits and planned.keep_clear == att.keep_clear

    dug = stages.apply_edits(world, [att])
    built = ter_heights(ter, world.terrain.heights.shape)
    assert np.array_equal(dug.terrain.heights, built)
    assert not np.array_equal(world.terrain.heights, built)
    shapes = od.keep_clear_shapes(spec)
    assert [tuple(s) for s in dug.socket("ground").ground["keep_clear"]] == list(shapes)
    assert tuple(dug.socket("ground").ground["spawn"][:2]) == tuple(spec.safe_point[:2])

    biome = spec.wilderness["biome"]
    got = _sites(dug, stages.rooms_seed(seed))
    legacy = place_sites(wb.landscape_for(spec), ter, seed, biome=biome, control="dense",
                         rules=RULES, spawn_xy=tuple(spec.safe_point[:2]), keep_clear=shapes)
    assert pickle.dumps(got.sites) == pickle.dumps(legacy)
    assert pickle.dumps(wb.sites_for(spec, ter).placement) == pickle.dumps(got.sites)
    if edges is None:
        assert got.sites.sites, "this seed gets a Site at dense"


# ---------------------------------------------------------------------------
# Placement on the corpus (from test_site_placement.py)
# ---------------------------------------------------------------------------

def test_sites_draw_their_own_stream(ground):
    """Same inputs, same Sites; the stream is the seed salted, not the seed itself."""
    dug, _, _ = ground("wilderness_plains")
    a = _sites(dug, 3, control="normal")
    assert pickle.dumps(a.sites) == pickle.dumps(_sites(dug, 3, control="normal").sites)
    assert sp.sites_seed(3) != 3 and sp.SITES_SALT == ("sites", "placement")


@pytest.mark.parametrize("name", ["wilderness_plains", "wilderness_river", "outdoor_e"])
def test_terrain_identical_across_site_densities(name, ground):
    """P5 (sites spec): the World, with its Terrain, reads the same whatever the Sites
    control; none places nothing and dense places some."""
    dug, _, _ = ground(name)
    before = dug.to_json()
    counts = []
    for control in ("none", "sparse", "normal", "dense"):
        got = _sites(dug, 1001, control=control)
        counts.append(len(got.sites.sites))
        assert not got.edits and dug.to_json() == before
    assert counts[0] == 0 and counts[-1] > 0


def test_misfits_drop_with_reasons_and_never_fail(ground):
    """A recipe that can't fit: too many tents for its ring, and a kind no ground holds."""
    dug, _, _ = ground("wilderness_plains")
    camp = RULES.kinds["camp"]
    crowded = replace(camp, structures=(camp.structures[0], replace(camp.structures[1], count=(12, 12))))
    shrine = RULES.kinds["shrine"]
    nowhere = replace(shrine, ground=replace(shrine.ground, radius=400.0))
    # The test picks the kinds (camps and shrines only) and the density itself, so it doesn't
    # hang on the shipped weights or density.
    plains = RULES.biomes["plains"]
    only = replace(plains, density=(2.0, 2.0),
                   weights={k: (1.0 if k in ("camp", "shrine") else 0.0) for k in RULES.kinds})
    rules = replace(RULES, kinds={**RULES.kinds, "camp": crowded, "shrine": nowhere},
                    biomes={**RULES.biomes, "plains": only})
    seen = set()
    for seed in range(6):
        p = _sites(dug, seed, rules=rules, inhabitant="human").sites
        seen |= {(d.kind, d.reason) for d in p.drops}
        assert all(len([t for t in s.structures if t.kind == "tent"]) < 12 for s in p.sites)
    assert ("tent", sp.NO_ROOM) in seen
    # A shrine with no ground is redrawn as a camp (task 15); with nothing else to try, it drops.
    assert not any(d.reason == sp.NO_GROUND for d in p.drops)
    alone = replace(rules, biomes={**rules.biomes, "plains": replace(
        only, weights={k: float(k == "shrine") for k in RULES.kinds})})
    p = _sites(dug, 0, rules=alone, inhabitant="human").sites
    assert ("shrine", sp.NO_GROUND) in {(d.kind, d.reason) for d in p.drops}


@pytest.mark.parametrize("name,seed", [("wilderness_plains", 1000), ("wilderness_plains", 1001),
                                       ("wilderness_river", 1002), ("wilderness_river", 1003)])
def test_camp_ring_clears_its_fire_and_faces_in(name, seed, ground):
    """Each kept tent stands a clear width from the fire and its neighbours, opening inward."""
    dug, _, _ = ground(name)
    biome = dug.recipe["biome"]
    rules = replace(RULES, biomes={**RULES.biomes, biome: replace(
        RULES.biomes[biome], weights={k: float(k == "camp") for k in RULES.kinds})})
    p = _sites(dug, seed, rules=rules).sites
    assert p.sites
    for s in p.sites:
        fire = [t for t in s.structures if t.kind == "fire_ring"]
        tents = [t for t in s.structures if t.kind in ("tent", "lean_to")]
        assert len(fire) == 1 and 2 <= len(tents) <= 4
        for i, t in enumerate(tents):
            assert gap(t.footprint(), fire[0].footprint()) >= sp.CLEAR_WIDTH - EPS
            to_fire = math.atan2(fire[0].y - t.y, fire[0].x - t.x)
            assert abs(sp._wrap(t.yaw - to_fire)) < 1e-6
            for u in tents[i + 1:]:
                assert gap(t.footprint(), u.footprint()) >= sp.CLEAR_WIDTH - EPS


def test_target_outdoor_dungeon_gets_a_site_at_normal(ground):
    """An outdoor dungeon's open ground (~0.82e6 u^2) gets Sites at Normal on some seeds."""
    dug, _, _ = ground("outdoor_e")
    p = _sites(dug, 1001, control="normal").sites
    assert p.walkable_area < 1e6 and p.target >= 1 and p.sites
