"""
tests/test_topology_embed.py
----------------------------
Graph-layout task 8 (Requirement 6): size classes, the ``spring`` placement
and the graph engine, through Job B (``LayoutGenerator.generate``).

G7  rooms take their class size; no two footprints overlap in plan; the
    classic corridor clearance holds; the ``entrance`` node is the entrance
    room; the final graph is connected.
G8  Edge_Fidelity over the sweep, per set (classic_eq, warren, temple): mean
    at or above the bar. The BUILT graph (the corridors after Job B) keeps the
    survey's shape: cycles per room, dead-end share and deep-end distance in
    each base set's band on the sweep mean (task 18).
G9  ``above`` / ``below`` / ``level`` hold after elevation unless counted in
    ``relations_broken``.
G10 grown rooms fit an Envelope as classic ones do.
G11 umbrella Req 21: one entrance, one climax, solvable gates.
G12 (task 19) rooms carry their kind; the rules' ``deep`` room is the climax
    and the boss, every seed.
Task 20: ogre and giant graph dungeons keep Edge_Fidelity and the classic
    cycles per room (rooms placed at their race-scaled size).
"""

from __future__ import annotations

import json
import statistics
from functools import lru_cache

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from generators.envelope import EnvelopeFitError
from generators.layout import (LEVEL_TOL, MIN_ENVELOPE_ROOMS, RELATION_RISE,
                               LayoutGenerator)
from generators.layout_engine import ENGINES, GraphEngine
from generators.topology import embed
from generators.topology.ruleset import PLACEMENTS
from tests.pbt_helpers import room_graph, scaled, solvable_walk
from tests.strategies import seeds
from tests.test_corridor_clearance import clearance_violations
from tests.test_envelope import _boxes, _disc, _inside_exactly
from tests.test_properties_layout import _connected
from tests.test_ruleset_classic_eq import SHAPE_BANDS as CLASSIC_BANDS
from tests.test_ruleset_warren import BANDS as WARREN_BANDS, SHAPES as WARREN_SHAPES

THEMES = st.sampled_from(["", "temple"])     # classic_eq, classic_eq + temple
TOUCH = 1e-6

# G8: Edge_Fidelity measured over this sweep (seeds x room counts, 48 layouts
# per set). Task 8 measured 0.9018 for classic_eq and temple together; task 18
# (rings of four, one wall side per neighbour) measured the means below (min
# 0.81, 0.75, 0.82). The bar is the measured mean less a margin, floored at
# the design's 0.85. Below it the placement is the bug, not the bar.
SWEEP_SEEDS = range(8)
SWEEP_NS = (6, 10, 15, 20, 25, 30)
# set label -> (rule set for GraphEngine, dungeon theme)
SWEEP_SETS = {"classic_eq": (None, ""), "warren": ("warren", ""), "temple": (None, "temple")}
FIDELITY_MEASURED = {"classic_eq": 0.9834, "warren": 0.9602, "temple": 0.9816}
FIDELITY_BAR = {k: max(0.85, v - 0.03) for k, v in FIDELITY_MEASURED.items()}
# The built-shape check skips the 6-room layouts: a graph that small can't
# show the shape (its entrance and deep end are already a third of it), as
# the rule-set tests say. Bands: design.md finding 5, as tasks 5 and 6 test
# the grammar graphs against them. Task 18 measured, on rooms >= 10:
# classic_eq cycles 0.134, dead ends 0.287, deep end 0.338; warren 0.217,
# 0.152, 0.247 (task 8's placement: classic_eq built cycles 0.038 and warren
# 0.045, both under their bands).
SHAPE_MIN_ROOMS = 10
BUILT_BANDS = {"classic_eq": CLASSIC_BANDS, "warren": {m: WARREN_BANDS[m] for m in WARREN_SHAPES}}


def _graph_layout(seed, n, theme="", rule_set=None, **kw):
    gen = LayoutGenerator("dungeon", seed=seed, engine=GraphEngine(rule_set))
    spec = gen.generate(f"g{seed}", room_count=n, dungeon_theme=theme,
                        add_lights=False, **kw)
    return gen, spec


def _rect(r):
    return (r.center_x - r.width / 2, r.center_y - r.depth / 2,
            r.center_x + r.width / 2, r.center_y + r.depth / 2)


def _overlap_in_plan(a, b) -> bool:
    ra, rb = _rect(a), _rect(b)
    return (min(ra[2], rb[2]) - max(ra[0], rb[0]) > TOUCH
            and min(ra[3], rb[3]) - max(ra[1], rb[1]) > TOUCH)


def _broken(spec, record) -> int:
    rooms = {r.id: r for r in spec.rooms}
    out = 0
    for a, b, rel in record["edges"]:
        dz = rooms[b].floor_z - rooms[a].floor_z
        if rel == "above":
            out += dz < RELATION_RISE - LEVEL_TOL
        elif rel == "below":
            out += dz > -RELATION_RISE + LEVEL_TOL
        elif rel == "level":
            out += abs(dz) > LEVEL_TOL
    return out


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------

def test_registry_matches_the_checker_and_no_stacking():
    assert set(embed.PLACEMENT_FUNCS) == set(PLACEMENTS)
    assert ENGINES["graph"] is GraphEngine
    assert GraphEngine.name == "graph" and GraphEngine.sizes_rooms is True
    from generators.topology.graph import Node
    assert embed.may_overlap_in_plan(Node("a", "chamber", "medium"),
                                     Node("b", "chamber", "medium")) is False


def test_one_build_context():
    import generators.layout_engine as le
    from generators.topology.rewrite import BuildContext
    assert le.BuildContext is BuildContext


def test_same_seed_same_layout():
    a = _graph_layout(5, 14, "temple")[1]
    b = _graph_layout(5, 14, "temple")[1]
    assert json.dumps(a.to_dict(), sort_keys=True) == json.dumps(b.to_dict(), sort_keys=True)


def test_record_names_set_layers_and_rooms():
    gen, spec = _graph_layout(3, 12, "temple")
    rec = gen.layout_record
    assert rec["engine"] == "graph" and rec["rule_set"] == "classic_eq"
    assert rec["layers"] == ["temple"] and rec["applied"]
    assert set(rec["rooms"]) == {r.id for r in spec.rooms}
    for r in spec.rooms:
        assert r.district == rec["rooms"][r.id]["district"]
    assert 0.0 <= rec["edge_fidelity"] <= 1.0
    # Classic records nothing.
    classic = LayoutGenerator("dungeon", seed=3)
    classic.generate("c", room_count=12)
    assert classic.layout_record is None


# ---------------------------------------------------------------------------
# G7
# ---------------------------------------------------------------------------

@settings(max_examples=scaled(25), deadline=None)
@given(s=seeds, n=st.integers(1, 30), theme=THEMES)
def test_engine_sizes_rooms_by_class(s, n, theme):
    """Straight from the engine: every room's footprint is its class side
    within the spread, its height the class height (race scaling and the
    theme's room types come later, in semantics)."""
    gen = LayoutGenerator("dungeon", seed=s)
    gen._apply_room_scale(n)
    ctx = gen._layout_context(n, theme, "")
    res = GraphEngine().generate(ctx, n, None)
    classes = [res.record["rooms"][r.id]["size"] for r in res.rooms]
    base = embed.area_matched_base(embed.base_side(ctx.room_min, ctx.room_max), classes)
    assert len(res.rooms) == n
    for r in res.rooms:
        foot, tall = embed.SIZE_SCALE[res.record["rooms"][r.id]["size"]]
        side = base * foot
        for v in (r.width, r.depth):
            assert side * (1 - embed.SPREAD) - 1e-6 <= v <= side * (1 + embed.SPREAD) + 1e-6
        assert r.height == pytest.approx(ctx.ceiling * tall)


@settings(max_examples=scaled(25), deadline=None)
@given(s=seeds, n=st.integers(1, 30), theme=THEMES)
def test_grown_layouts_hold_after_job_b(s, n, theme):
    gen, spec = _graph_layout(s, n, theme)
    rec = gen.layout_record
    assert len(spec.rooms) == n
    if not theme:
        # No role size bias and no semantic types: the class sizes survive.
        sizes = {r.id: (r.width, r.depth) for r in
                 GraphEngine().generate(_ctx(s, n, theme), n, None).rooms}
        for r in spec.rooms:
            assert (r.width, r.depth) == pytest.approx(sizes[r.id])
    for i, a in enumerate(spec.rooms):
        for b in spec.rooms[i + 1:]:
            assert not _overlap_in_plan(a, b), (a.id, b.id)
    assert clearance_violations(spec) == []
    entrance = next(rid for rid, v in rec["rooms"].items() if v["kind"] == "entrance")
    assert [r.id for r in spec.rooms if r.role == "entrance"] == [entrance]
    adj = room_graph(spec)
    ids = [r.id for r in spec.rooms]
    assert _connected(adj, ids) if n > 1 else True


def _ctx(s, n, theme):
    """The context the generator hands the engine on its first draw."""
    gen = LayoutGenerator("dungeon", seed=s)
    gen._apply_room_scale(n)
    return gen._layout_context(n, theme, "")


# ---------------------------------------------------------------------------
# G8 and G9 over the sweep
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def _sweep(label):
    rule_set, theme = SWEEP_SETS[label]
    out = []
    for n in SWEEP_NS:
        for s in SWEEP_SEEDS:
            gen, spec = _graph_layout(1000 * n + s, n, theme, rule_set)
            out.append((spec, gen.layout_record))
    return out


def _built_shape(spec, record):
    """Cycles per room, dead-end share and deep-end distance of the graph the
    corridors build (Job B's, not the grammar's)."""
    n = len(spec.rooms)
    adj = {r.id: set() for r in spec.rooms}
    for c in spec.corridors:
        adj[c.from_room].add(c.to_room)
        adj[c.to_room].add(c.from_room)
    pairs = sum(len(v) for v in adj.values()) // 2
    entrance = next(rid for rid, v in record["rooms"].items() if v["kind"] == "entrance")
    dist = {entrance: 0}
    queue = [entrance]
    for u in queue:
        for v in sorted(adj[u]):
            if v not in dist:
                dist[v] = dist[u] + 1
                queue.append(v)
    return {"cycles_per_room": (pairs - n + 1) / n,
            "dead_end": sum(1 for v in adj.values() if len(v) == 1) / n,
            "deep_end": max(dist.values()) / n}


@pytest.mark.parametrize("label", sorted(SWEEP_SETS))
def test_edge_fidelity_over_the_sweep(label):
    fids = [rec["edge_fidelity"] for _spec, rec in _sweep(label)]
    mean = statistics.mean(fids)
    bar = FIDELITY_BAR[label]
    assert mean >= bar, f"{label}: mean Edge_Fidelity {mean:.4f} < bar {bar:.4f}"


@pytest.mark.parametrize("label", sorted(BUILT_BANDS))
def test_built_graph_keeps_the_survey_shape(label):
    """Loops survive placement (task 18): the corridors Job B builds still
    have the set's survey shape on the sweep mean."""
    rows = [_built_shape(spec, rec) for spec, rec in _sweep(label)
            if len(spec.rooms) >= SHAPE_MIN_ROOMS]
    bad = []
    for m, (lo, hi) in BUILT_BANDS[label].items():
        mean = statistics.fmean(r[m] for r in rows)
        if not lo <= mean <= hi:
            bad.append(f"{m}: built mean {mean:.3f}, band {lo:.2f}-{hi:.2f}")
    assert not bad, f"{label}: " + "; ".join(bad)


def test_relations_hold_unless_counted():
    held = total = 0
    for spec, rec in (x for label in SWEEP_SETS for x in _sweep(label)):
        broken = _broken(spec, rec)
        assert rec["relations_broken"] == broken
        n_rel = sum(1 for e in rec["edges"] if e[2] != "any")
        total += n_rel
        held += n_rel - broken
    assert total > 0
    # Most relations survive the loop relax (task 8 measured 85 of 100 held).
    assert held / total >= 0.7, (held, total)


# Big races (task 20). Measured over this sweep (plan_to_spec, dungeon,
# graph, seeds 0-11 x 10/15/20 rooms): with the race scale applied after
# placement, giants kept 0.865 of their edges (worst 0.53) and built 0.063
# cycles per room; placed at their final size, 0.991 and 0.101 (ogre 0.993
# and 0.101, both with great halls; no race 0.991 and 0.103).
BIG_RACE_SEEDS = range(12)
BIG_RACE_NS = (10, 15, 20)
BIG_RACE_FIDELITY = 0.95


@lru_cache(maxsize=None)
def _race_sweep(race):
    from ai.expand import plan_to_spec
    from ai.schema import ZonePlan
    out = []
    for s in BIG_RACE_SEEDS:
        for n in BIG_RACE_NS:
            plan = ZonePlan(name="r", zone_type="dungeon", room_count=n,
                            dungeon_race=race, layout="graph").validate()
            out.append(plan_to_spec(plan, seed=s))
    return out


@pytest.mark.parametrize("race", ["ogre", "giant"])
def test_big_races_keep_their_loops(race):
    """Rooms are placed at their race-scaled size, so the loops survive Job B
    and the built graph has the classic cycles per room; big races get great
    halls."""
    specs = _race_sweep(race)
    fid = statistics.mean(sp.layout["edge_fidelity"] for sp in specs)
    cycles = statistics.mean(
        (len({frozenset((c.from_room, c.to_room)) for c in sp.corridors})
         - len(sp.rooms) + 1) / len(sp.rooms) for sp in specs)
    lo, hi = CLASSIC_BANDS["cycles_per_room"]
    assert fid >= BIG_RACE_FIDELITY, f"{race}: mean Edge_Fidelity {fid:.3f}"
    assert lo <= cycles <= hi, f"{race}: built cycles per room {cycles:.3f}, band {lo}-{hi}"
    assert any(a[1] == "great_hall" for sp in specs for a in sp.layout["applied"])


def test_race_scale_applies_once():
    """The race scale goes on grown rooms once (in the engine): a giant's
    rooms average 2.2^2 the floor area of no race's, not 2.2^4."""
    def mean_area(race):
        return statistics.mean(r.width * r.depth for sp in _race_sweep(race)
                               for r in sp.rooms if r.kind)
    ratio = mean_area("giant") / mean_area("")
    assert 2.2 ** 2 * 0.8 <= ratio <= 2.2 ** 2 * 1.25, ratio


def test_relations_not_counted_without_elevation():
    gen, _spec = _graph_layout(2, 15, elevation=False)
    assert gen.layout_record["relations_broken"] is None


# ---------------------------------------------------------------------------
# G10: the Envelope
# ---------------------------------------------------------------------------

@settings(max_examples=scaled(15), deadline=None)
@given(s=seeds, n=st.integers(3, 8), elevation=st.booleans())
def test_grown_rooms_fit_an_envelope(s, n, elevation):
    radius = 1600.0
    gen = LayoutGenerator("dungeon", seed=s, engine=GraphEngine())
    try:
        spec = gen.generate("env", room_count=n, elevation=elevation,
                            envelope=_disc(radius))
    except EnvelopeFitError:
        return
    assert len(spec.rooms) >= min(n, MIN_ENVELOPE_ROOMS)
    if len(spec.rooms) < n:
        assert any(w.startswith("rooms_reduced:") for w in gen.warnings)
    for part, box in _boxes(spec):
        assert _inside_exactly(radius, *box), (part, box)


def test_tight_envelope_drops_grown_rooms_with_a_warning():
    gen = LayoutGenerator("dungeon", seed=1, engine=GraphEngine())
    spec = gen.generate("tight", room_count=6, envelope=_disc(900))
    assert MIN_ENVELOPE_ROOMS <= len(spec.rooms) < 6
    assert any(w.startswith("rooms_reduced:") for w in gen.warnings), gen.warnings
    for part, box in _boxes(spec):
        assert _inside_exactly(900, *box), (part, box)


# ---------------------------------------------------------------------------
# G11: umbrella Req 21
# ---------------------------------------------------------------------------

@settings(max_examples=scaled(25), deadline=None)
@given(s=seeds, n=st.integers(3, 30), locks=st.integers(1, 5), theme=THEMES)
def test_entrance_climax_and_solvable_gates(s, n, locks, theme):
    _gen, spec = _graph_layout(s, n, theme, locks=locks)
    entrances = [r for r in spec.rooms if r.role == "entrance"]
    climaxes = [r for r in spec.rooms if r.role == "climax"]
    assert len(entrances) == 1 and len(climaxes) == 1
    assert climaxes[0].id != entrances[0].id
    assert 1 <= len(spec.gates) <= locks
    assert solvable_walk(spec) == {r.id for r in spec.rooms}


# ---------------------------------------------------------------------------
# G12: rooms carry their kind; the deep end is the climax (task 19)
# ---------------------------------------------------------------------------

# set label -> the dungeon theme that picks it (themes.toml), so the rooms
# are labelled and carry ``boss``.
CLIMAX_THEMES = {"classic_eq": "fortress", "warren": "warren", "temple": "temple"}


@pytest.mark.parametrize("label", sorted(CLIMAX_THEMES))
@pytest.mark.parametrize("n", [2, 3, 6, 12, 20])
def test_deep_room_is_the_climax_and_the_boss(label, n):
    theme = CLIMAX_THEMES[label]
    for s in range(8):
        gen = LayoutGenerator("dungeon", seed=s, engine="graph")
        spec = gen.generate(f"g{s}", room_count=n, dungeon_theme=theme,
                            add_lights=False, locks=1)
        grown = spec.rooms[:n]                  # crossings may add waypoints
        assert all(r.kind for r in grown), (s, [r.id for r in grown if not r.kind])
        assert {r.id: r.kind for r in grown} == {
            rid: v["kind"] for rid, v in gen.layout_record["rooms"].items()}
        deep = [r.id for r in grown if r.kind == "deep"]
        climax = [r.id for r in spec.rooms if r.role == "climax"]
        boss = [r.id for r in spec.rooms if r.boss]
        assert len(deep) == 1 and climax == deep == boss, (s, deep, climax, boss)
        assert [r.kind for r in spec.rooms if r.role == "entrance"] == ["entrance"]


def test_one_room_has_no_climax():
    gen = LayoutGenerator("dungeon", seed=1, engine="graph")
    spec = gen.generate("g1", room_count=1, dungeon_theme="fortress", add_lights=False)
    assert [r.role for r in spec.rooms] == ["entrance"]
    assert not any(r.boss for r in spec.rooms)


def test_engine_climax_loses_to_the_entrance():
    """An engine's climax is used as given, unless it is the entrance room
    (an Envelope's way in can pick it): then the deepest by hops."""
    from generators.zone_spec import RoomSpec
    rooms = lambda: [RoomSpec(id=f"room_{i}", center_x=100.0 * i, center_y=0.0)
                     for i in range(4)]
    edges = [(0, 1), (1, 2), (2, 3)]
    gen = LayoutGenerator("dungeon", seed=0)
    r = rooms()
    assert gen._apply_pacing(r, edges, entry=(0.0, 0.0), size_bias=False, climax=1) == 0
    assert [x.role for x in r] == ["entrance", "climax", "standard", "deadend"]
    assert [x.graph_depth for x in r] == [0, 1, 2, 3]
    r = rooms()
    gen._apply_pacing(r, edges, entry=(0.0, 0.0), size_bias=False, climax=0)
    assert [x.role for x in r] == ["entrance", "standard", "standard", "climax"]
