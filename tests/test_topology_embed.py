"""
tests/test_topology_embed.py
----------------------------
Graph-layout task 8 (Requirement 6): size classes, the ``spring`` placement
and the graph engine, through Job B (``LayoutGenerator.generate``).

G7  rooms take their class size; no two footprints overlap in plan; the
    classic corridor clearance holds; the ``entrance`` node is the entrance
    room; the final graph is connected.
G8  Edge_Fidelity over the sweep: mean at or above the bar.
G9  ``above`` / ``below`` / ``level`` hold after elevation unless counted in
    ``relations_broken``.
G10 grown rooms fit an Envelope as classic ones do.
G11 umbrella Req 21: one entrance, one climax, solvable gates.
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

THEMES = st.sampled_from(["", "temple"])     # classic_eq, classic_eq + temple
TOUCH = 1e-6

# G8: Edge_Fidelity measured over this sweep (both sets) at task 8: mean
# 0.9018 (min 0.72; 96 layouts). The bar is the measured mean less a margin, floored at
# the design's 0.85. Below it the placement is the bug, not the bar.
SWEEP_SEEDS = range(8)
SWEEP_NS = (6, 10, 15, 20, 25, 30)
SWEEP_THEMES = ("", "temple")
FIDELITY_MEASURED = 0.9018
FIDELITY_BAR = max(0.85, FIDELITY_MEASURED - 0.03)


def _graph_layout(seed, n, theme="", **kw):
    gen = LayoutGenerator("dungeon", seed=seed, engine=GraphEngine())
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

@lru_cache(maxsize=1)
def _sweep():
    out = []
    for theme in SWEEP_THEMES:
        for n in SWEEP_NS:
            for s in SWEEP_SEEDS:
                gen, spec = _graph_layout(1000 * n + s, n, theme)
                out.append((spec, gen.layout_record))
    return out


def test_edge_fidelity_over_the_sweep():
    fids = [rec["edge_fidelity"] for _spec, rec in _sweep()]
    mean = statistics.mean(fids)
    assert mean >= FIDELITY_BAR, f"mean Edge_Fidelity {mean:.4f} < bar {FIDELITY_BAR:.4f}"


def test_relations_hold_unless_counted():
    held = total = 0
    for spec, rec in _sweep():
        broken = _broken(spec, rec)
        assert rec["relations_broken"] == broken
        n_rel = sum(1 for e in rec["edges"] if e[2] != "any")
        total += n_rel
        held += n_rel - broken
    assert total > 0
    # Most relations survive the loop relax (task 8 measured 85 of 100 held).
    assert held / total >= 0.7, (held, total)


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
