"""Site placement (roadmap step 10 task 6, Requirements 4 and 6).

On synthesized landscapes and their built TERs (no full build), Sites placed on each one's
World (its terrain is the TER's grid) and the World's point Site Sockets, the checks that need
a TER or many terrains:

- P4: Sites only on eligible ground (playable plains, slope within the recipe, outside
  Kept_Clear), grounds a clear width apart; Structures inside their Site; Site_Clear free of Structures and
  trees (Req 4.1-4.3);
- P7: every Site names a POI, and every POI stands on ground the walk gate reaches from
  Spawn (Req 6.1);
- P5: trees identical with Sites ``none`` and with no Sites argument at all (Req 4.4);
- task 15: camps keep their tents over 30 terrains; the target's expected value;
- step 13 P4: on point Sockets, every Site on a point it fits, grounds and ways in clear of
  each other, no point under Kept_Clear used (Req 3.1-3.3, 3.7, 3.8).

The checks re-derive what they test (TER triangle planes, node types, distances, the walk
gate's own flood) rather than reusing the placement's helpers. The placement-only cases on
one terrain (misfits, terrain identical across densities, the Sites' own stream, the camp
ring, an outdoor dungeon's target) run on the World corpus in ``test_attach_ground.py``.
"""

import math
import pickle
from functools import lru_cache

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from scipy.spatial import cKDTree

from analyzer.traverse import AgentModel
from generators.sites import placement as sp
from generators.sites.placement import gap, place_sites, reach
from generators.sites.rules import load_sites
from generators.vegetation.kit import load_vegetation_kit
from generators.vegetation.placement import SPAWN_CLEARING, place_trees
from generators.wilderness.build import (
    _reached_faces,
    build_wilderness_ter,
    synthesize_landscape,
    wilderness_spec,
)
from generators.world import world_for, world_of
from tests.pbt_helpers import scaled

RULES = load_sites()
KIT = load_vegetation_kit("plains_grassland")
EDGES = [None, {"N": "zoneline", "E": "river"}, {"E": "zoneline", "W": "zoneline"},
         {"N": "mountain", "S": "zoneline", "W": "river"}]
REASONS = {sp.NO_APPROACH, sp.NO_ROOM, sp.OUTSIDE, sp.IN_CLEAR, sp.CROWDED,
           sp.APRON_OFF, sp.APRON_BLOCKED, sp.STRUCTURE_GONE, sp.NO_FREE_GROUND, sp.NO_POI,
           sp.NO_STRUCTURES, sp.NO_POINT}
EPS = 1e-6

ZONES = st.tuples(st.integers(0, 2**31 - 1), st.sampled_from(range(len(EDGES))),
                  st.sampled_from(["sparse", "normal", "dense"]))
SETTINGS = settings(max_examples=scaled(10), deadline=None,
                    suppress_health_check=[HealthCheck.too_slow])


@lru_cache(maxsize=16)
def _zone(seed, edge_ix):
    edges = EDGES[edge_ix]
    spec = wilderness_spec("t", seed, edges)
    ter = build_wilderness_ter(spec, "ter_t.ter", 2)
    return spec, ter, synthesize_landscape(seed, edges)


@lru_cache(maxsize=16)
def _world(seed, edge_ix):
    spec, _, _ = _zone(seed, edge_ix)
    return world_of(spec)


def _place(seed, edge_ix, control):
    """The zone's Sites on its World's ground and point Site Sockets."""
    return _place_on(_world(seed, edge_ix), seed, control)


def _place_on(world, seed, control):
    return place_sites(world.terrain, world.socket("ground"), seed, control=control, rules=RULES,
                       points=[s for s in world.sockets if s.kind == "site"])


def _triangle_under(ter, land, x, y):
    """The TER grid triangle containing (x, y): its index, Z there and its cos(slope)."""
    s = land.synth
    res, (ox, oy), (_, ny) = float(s.resolution), s.origin, s.heights.shape
    i = int(math.floor((x - ox) / res - 0.5))
    j = int(math.floor((y - oy) / res - 0.5))
    q = i * (ny - 1) + j
    for f in (2 * q, 2 * q + 1):
        poly = ter.polygons[f]
        P = np.array([[ter.vertices[k].x, ter.vertices[k].y, ter.vertices[k].z]
                      for k in (poly.v1, poly.v2, poly.v3)])
        a, b, c = P
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        l1 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / den
        l2 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / den
        l3 = 1 - l1 - l2
        if min(l1, l2, l3) >= -1e-9:
            n = np.cross(b - a, c - a)
            return f, float(l1 * a[2] + l2 * b[2] + l3 * c[2]), abs(n[2]) / np.linalg.norm(n)
    raise AssertionError(f"no TER triangle under ({x}, {y})")


def _node_trees(land):
    s = land.synth
    node, res, (ox, oy) = np.asarray(s.node_type), float(s.resolution), s.origin
    cells = np.argwhere(np.ones_like(node, dtype=bool))
    centres = np.column_stack([ox + (cells[:, 0] + 0.5) * res, oy + (cells[:, 1] + 0.5) * res])
    kinds = node[cells[:, 0], cells[:, 1]]

    def tree(mask):
        pts = centres[mask]
        return cKDTree(pts) if len(pts) else None
    return res, tree(kinds != "plains"), tree(np.isin(kinds, ("water", "river", "lava"))), \
        tree(kinds == "zoneline_gap")


# ---------------------------------------------------------------------------
# P4
# ---------------------------------------------------------------------------

@SETTINGS
@given(zone=ZONES)
def test_property_p4_sites_on_eligible_ground_spaced_and_kept_clear(zone):
    seed, edge_ix, control = zone
    spec, ter, land = _zone(seed, edge_ix)
    p = _place(seed, edge_ix, control)
    res, not_plains, wet, zoneline = _node_trees(land)
    spawn = np.array(spec.safe_point[:2])

    for s in p.sites:
        recipe = RULES.kinds[s.kind]
        outer = s.radius + s.margin
        # Eligible ground: every point of the Site's ground and margin is on plains (all
        # four corners of its quad), no steeper than the recipe, outside Kept_Clear.
        assert not_plains.query([s.x, s.y])[0] >= res / 2 + outer - EPS
        assert np.linalg.norm(np.array([s.x, s.y]) - spawn) >= SPAWN_CLEARING + outer - EPS
        if wet is not None:
            assert wet.query([s.x, s.y])[0] >= res + outer - EPS
        if zoneline is not None:
            assert zoneline.query([s.x, s.y])[0] >= 2 * res + outer - EPS
        for a in np.linspace(0, 2 * math.pi, 12, endpoint=False):
            for rr in (0.0, outer / 2, outer - 1e-3):
                _, _, cos_slope = _triangle_under(ter, land, s.x + rr * math.cos(a), s.y + rr * math.sin(a))
                assert cos_slope >= math.cos(math.radians(recipe.ground.slope_deg)) - 1e-9

        # Structures inside the Site's ground; the Site_Clear (approach, aprons) free of
        # every Structure in the zone.
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

    # Spaced: every two Sites' grounds and margins a player's clear width apart.
    for k, a in enumerate(p.sites):
        for b in p.sites[k + 1:]:
            gap_ab = math.hypot(a.x - b.x, a.y - b.y) - (a.radius + a.margin) - (b.radius + b.margin)
            assert gap_ab >= sp.CLEAR_WIDTH - EPS

    # Misfits are recorded with a known reason; Structure drops name a kept Site.
    for d in p.drops:
        assert d.reason in REASONS and d.what in ("site", "structure", "poi")
        assert (d.site is None) == (d.what == "site")

    # Trees keep off every Site's ground and Site_Clear.
    trees = place_trees(land, ter, KIT, "dense", seed ^ 0x5EED, keep_clear=p.clear_shapes())
    for t in trees.instances:
        disc = (t.x, t.y, t.x, t.y, t.radius)
        for shape in p.clear_shapes():
            assert gap(disc, shape) >= -EPS


# ---------------------------------------------------------------------------
# P7
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed,edge_ix", [(1, 0), (5, 1), (13, 2), (34, 3)])
def test_property_p7_every_site_names_a_poi_on_reached_ground(seed, edge_ix):
    spec, ter, land = _zone(seed, edge_ix)
    p = _place(seed, edge_ix, "dense")
    assert p.sites
    _, reached = _reached_faces(spec, ter, AgentModel())
    for s in p.sites:
        assert s.pois, s.kind
        for poi in s.pois:
            face, z, _ = _triangle_under(ter, land, poi.x, poi.y)
            assert face in reached, (s.kind, poi.name)
            assert abs(poi.z - z) < 1e-3
            # Not inside a solid Structure's footprint.
            for t in s.structures:
                if not t.enterable or t.run:
                    x0, y0, x1, y1, r = t.footprint()
                    assert gap((poi.x, poi.y, poi.x, poi.y, 0.0), (x0, y0, x1, y1, r)) > 0, (poi.name, t.kind)


# ---------------------------------------------------------------------------
# P5
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed,edge_ix", [(3, 0), (21, 1)])
def test_p5_trees_identical_with_sites_none(seed, edge_ix):
    _, ter, land = _zone(seed, edge_ix)
    none = _place(seed, edge_ix, "none")
    assert none.sites == [] and none.clear_shapes() == ()
    tree_seed = seed ^ 0x5EED
    before = place_trees(land, ter, KIT, "normal", tree_seed)
    after = place_trees(land, ter, KIT, "normal", tree_seed, keep_clear=none.clear_shapes())
    assert pickle.dumps(after) == pickle.dumps(before)
    # And Sites do move the trees off their ground (the argument is live).
    some = _place(seed, edge_ix, "dense")
    assert pickle.dumps(place_trees(land, ter, KIT, "normal", tree_seed,
                                    keep_clear=some.clear_shapes())) != pickle.dumps(before)


# ---------------------------------------------------------------------------
# Task 15: camps keep their tents; the target keeps its expected value
# ---------------------------------------------------------------------------

def _drop_table(seeds, controls=("normal", "dense")):
    """Per Site kind: Structures tried (kept + dropped), Structures dropped; and per camp, the
    tents (or a centaur's lean-tos) it kept."""
    tried, dropped, camps = {}, {}, []
    for seed in seeds:
        # The World stage's terrain: the TER's grid, so no TER is built (world-sockets task 12).
        world = world_for("wilderness", seed)
        for control in controls:
            p = _place_on(world, seed, control)
            for s in p.sites:
                tried[s.kind] = tried.get(s.kind, 0) + len(s.structures)
                if s.kind == "camp":
                    camps.append((seed, control, sum(t.kind in ("tent", "lean_to") for t in s.structures)))
            for d in p.drops:
                if d.what == "structure":
                    k = p.sites[d.site].kind
                    tried[k] = tried.get(k, 0) + 1
                    dropped[k] = dropped.get(k, 0) + 1
    return tried, dropped, camps


def _check_camps_and_drops(seeds):
    tried, dropped, camps = _drop_table(seeds)
    assert sum(tried.values()) > 100
    assert camps, "no camp in these seeds: widen them"
    lone = [c for c in camps if c[2] < 2]
    assert not lone, f"camps with fewer than 2 tents: {lone}"
    for kind, n in tried.items():
        assert dropped.get(kind, 0) <= n / 5, (kind, dropped.get(kind, 0), n)


def test_camp_keeps_its_tents_and_no_recipe_drops_a_fifth():
    """Over 30 seeds at Normal and Dense a camp's tents ring its fire, a clear width out and
    inside its ground: every camp keeps 2 or more, and no recipe drops more than a fifth of
    its Structures (Req 4.2, 4.3)."""
    _check_camps_and_drops(range(1000, 1030))


# ---------------------------------------------------------------------------
# Step 13 P4: Sites on point Sockets
# ---------------------------------------------------------------------------

def _point_sockets(world):
    """The World's point Site Sockets: its own ``site`` Sockets once the World offers them
    (site-sockets task 4), else ``site_points`` on it, shaped as those Sockets are."""
    own = [s for s in world.sockets if s.kind == "site"]
    if own:
        return own
    from types import SimpleNamespace
    from generators.sites.points import site_points
    hills = [s for s in world.sockets if s.kind == "hillside"]
    pts = site_points(world.terrain, world.spawn, world.recipe["seed"], world.recipe["biome"], RULES,
                      hill=hills[0].ground["footprint"] if hills else None)
    return [SimpleNamespace(id=p.id, kind="site", x=p.x, y=p.y, z=p.z, accepts=("site",),
                            ground=p.ground()) for p in pts]


@lru_cache(maxsize=None)
def _point_world(name):
    """A World with its earlier Attachments applied (an outdoor dungeon's rooms on its hill)
    and its point Sockets: a corpus recording by name, or a fresh wilderness by seed."""
    from generators import stages
    from tests.test_attach_hillside import attach, record_worlds
    world = record_worlds.load_world(name) if isinstance(name, str) else world_for("wilderness", name)
    atts = [attach(world)] if any(s.kind == "hillside" for s in world.sockets) else []
    return stages.apply_edits(world, atts), _point_sockets(world)


POINT_WORLDS = ["wilderness_plains", "wilderness_river", "outdoor_n", "outdoor_s", "outdoor_e",
                "outdoor_w", "outdoor_river", 1000, 1001, 1002, 1003]


def _smallest_outer(free):
    fits = [r.ground.radius + r.ground.margin for r in RULES.kinds.values()
            if free.get(f"{r.ground.slope_deg:g}", 0.0) >= r.ground.radius + r.ground.margin]
    return min(fits) if fits else None


def test_property_p4_sites_stand_on_points_that_fit_them():
    """Every Site centred on a point of its own, of a kind whose ground and margin fit the
    point's Free radius at the recipe's slope, clear of Kept_Clear; grounds keep CLEAR_WIDTH;
    no way in crosses another Site's ground; no point under Kept_Clear used; Sites ``none``
    places nothing (step 13 Req 3.1-3.3, 3.7, 3.8)."""
    sites_seen = skipped_seen = 0
    for name in POINT_WORLDS:
        dug, points = _point_world(name)
        ground = dug.socket("ground")
        keep = [tuple(s) for s in ground.ground.get("keep_clear", ())]
        by_id = {p.id: p for p in points}
        under = {p.id for p in points if _smallest_outer(p.ground["free"]) is None or any(
            gap((p.x, p.y, p.x, p.y, _smallest_outer(p.ground["free"])), s) < 0 for s in keep)}
        skipped_seen += len(under)
        for seed in (0, 1, 2):
            none = place_sites(dug.terrain, ground, seed, control="none", rules=RULES, points=points)
            assert none.sites == [] and none.drops == [] and none.target == 0
            for control in ("normal", "dense"):
                p = place_sites(dug.terrain, ground, seed, control=control, rules=RULES, points=points)
                where = (name, seed, control)
                used = [s.socket for s in p.sites]
                assert len(set(used)) == len(used), where
                assert len(p.sites) + sum(d.what == "site" for d in p.drops) == p.target, where
                for d in p.drops:
                    assert d.reason in REASONS | {sp.NO_POINT}, where
                for s in p.sites:
                    pt = by_id[s.socket]
                    assert s.socket not in under, (where, s.socket)
                    assert (s.x, s.y) == (pt.x, pt.y), where
                    g = RULES.kinds[s.kind].ground
                    outer = s.radius + s.margin
                    assert outer == g.radius + g.margin
                    assert pt.ground["free"][f"{g.slope_deg:g}"] >= outer, (where, s.kind)
                    for k in keep:
                        assert gap((s.x, s.y, s.x, s.y, outer), k) >= -EPS, (where, s.kind)
                    for t in s.structures:
                        assert reach(t.footprint(), s.x, s.y) <= s.radius + EPS, (where, s.kind)
                    # The way in, beyond the margin: 40 u out, a player's clear width across.
                    fx, fy = math.cos(s.approach_yaw), math.sin(s.approach_yaw)
                    way = (s.x + fx * outer, s.y + fy * outer, s.x + fx * (outer + sp.APPROACH_REACH),
                           s.y + fy * (outer + sp.APPROACH_REACH), sp.CLEAR_WIDTH / 2)
                    for o in p.sites:
                        if o is s:
                            continue
                        disc = (o.x, o.y, o.x, o.y, o.radius + o.margin)
                        assert gap((s.x, s.y, s.x, s.y, outer), disc) >= sp.CLEAR_WIDTH - EPS, where
                        assert gap(way, disc) >= -EPS, (where, s.kind, o.kind)
                sites_seen += len(p.sites)
    assert sites_seen > 50 and skipped_seen, (sites_seen, skipped_seen)


@pytest.mark.parametrize("band, area", [((0.3, 0.5), 0.816e6), ((0.6, 1.0), 0.816e6),
                                        ((0.3, 0.5), 4.7e6), ((0.1, 0.1), 2.5e6)])
def test_target_keeps_the_expected_value(band, area):
    """The mean target is density x area (floor plus a draw on the fraction), not rounded
    away: outdoor-dungeon-sized ground gets a Site on some seeds."""
    import random
    draws = [sp.site_target(random.Random(sp.sites_seed(seed)), band, area) for seed in range(20000)]
    want = (band[0] + band[1]) / 2 * area / 1e6
    assert abs(sum(draws) / len(draws) - want) < 0.02
    lo = math.floor(band[0] * area / 1e6)
    hi = math.floor(band[1] * area / 1e6) + 1
    assert set(draws) <= set(range(lo, hi + 1))
    assert any(draws), "never a Site"
