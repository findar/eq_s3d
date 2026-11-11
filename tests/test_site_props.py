"""Room-decor task 11: Site Props (Req 11, P11).

A Site's POIs and ground are dressed by decor's own placement from the Site's RoomContext:
haybales and a cart at a farmstead, crates at a camp, offerings at a shrine. Props keep off
the Site_Clear (the approach, each opening's apron, the margin round the Site's ground) and
every Structure, and decor's own check holds on every recorded Site (these run on the corpus,
no build). P11 (``slow``, needs the install): on 40 seeds at Normal and Dense, the Sites with
their Props pass the wilderness Footprint gate, trees and Structures included.
"""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

import pytest

from generators.decor.catalogue import load as load_catalogue
from generators.decor.placement import SITE_MARGIN, check, place
from generators.decor.rules import load_decor
from generators.decor.stock import eq_path_from_env
from generators.room_context import load
from generators.sites.rules import load_sites

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "rooms"

SITES = [c for path in sorted(FIXTURES.glob("*.json")) for c in load(path)[1] if c.source == "site"]
CONTROLS = ("normal", "dense")
#: Decor seeds each recorded Site is placed with (a Site may be drawn bare).
DECOR_SEEDS = range(4)


@pytest.fixture(scope="module")
def rules():
    return load_decor()


@pytest.fixture(scope="module")
def catalogue():
    return load_catalogue()


@pytest.fixture(scope="module")
def placed(rules, catalogue):
    """Every recorded Site placed at each control and decor seed: (context, control, Decorated)."""
    return [(c, control, place(c, rules, catalogue, control, s))
            for c in SITES for control in CONTROLS for s in DECOR_SEEDS]


def _corners(p):
    c, s = math.cos(p.yaw), math.sin(p.yaw)
    return [(p.x + c * a - s * b, p.y + s * a + c * b)
            for a in (-p.w / 2, p.w / 2) for b in (-p.d / 2, p.d / 2)]


def _capsule_dist(x, y, c) -> float:
    x0, y0, x1, y1 = c["x0"], c["y0"], c["x1"], c["y1"]
    dx, dy = x1 - x0, y1 - y0
    n = dx * dx + dy * dy
    t = 0.0 if n == 0 else min(max(((x - x0) * dx + (y - y0) * dy) / n, 0.0), 1.0)
    return math.hypot(x - x0 - t * dx, y - y0 - t * dy)


def site_clear_problems(ctx, props) -> list:
    """Where a Prop's plan reaches into the Site's Site_Clear (its approach, an apron, the
    margin round its ground) or onto a Structure's footprint."""
    from generators.decor.placement import _in_polygon
    import numpy as np

    out = []
    margin = SITE_MARGIN
    for p in props:
        pts = _corners(p) + [(p.x, p.y)]
        for c in ctx.clear:
            for x, y in pts:
                d = _capsule_dist(x, y, c)
                if c["what"] == "ground" and d > c["r"] - margin + 1e-6:
                    out.append(f"{p.key} at ({p.x:.0f}, {p.y:.0f}) in the margin")
                    break
                if c["what"] != "ground" and d < c["r"] - 1e-6:
                    out.append(f"{p.key} at ({p.x:.0f}, {p.y:.0f}) in the {c['what']}")
                    break
        xs, ys = np.array([x for x, _ in pts]), np.array([y for _, y in pts])
        for f in ctx.features:
            if _in_polygon(xs, ys, f["plan"]).any():
                out.append(f"{p.key} at ({p.x:.0f}, {p.y:.0f}) on the {f['kind']}")
    return out


def test_the_corpus_holds_every_site_kind():
    """The pitfall of task 18's corpus: no farmstead. ``wilderness_farmstead`` adds two."""
    assert {c.room_type for c in SITES} == set(load_sites().kinds)


def test_site_margin_covers_every_recipes_margin():
    """Props stand ``SITE_MARGIN`` inside a Site's ``ground`` piece: never in its margin."""
    assert SITE_MARGIN >= max(r.ground.margin for r in load_sites().kinds.values())


def test_every_site_kind_has_a_recipe(rules):
    for kind in load_sites().kinds:
        assert [r.name for r in rules.recipe_for(kind, source="site")] == [f"sites.{kind}"]


def test_site_props_keep_off_the_site_clear_and_the_structures(placed):
    """P11: Site_Clear stays free; nothing stands on a Structure; decor's own check holds."""
    bad = []
    for ctx, control, d in placed:
        assert all(p.mount in ("floor", "raised") for p in d.props), ctx.id
        bad += [f"{ctx.id} {ctx.room_type} {control}: {why}"
                for why in site_clear_problems(ctx, d.props) + check(ctx, d)]
    assert not bad, bad[:10]


def test_sites_get_their_own_props(placed):
    """Haybales and a cart at a farmstead, crates at a camp, offerings at a shrine."""
    kinds = {}
    for ctx, _control, d in placed:
        kinds.setdefault(ctx.room_type, Counter()).update(p.kind for p in d.props)
    assert kinds["farmstead"]["hay"] and kinds["farmstead"]["cart"], kinds["farmstead"]
    assert sum(kinds["camp"][k] for k in ("crate", "barrel", "sack", "box")), kinds["camp"]
    assert sum(kinds["shrine"][k] for k in ("urn", "vase", "food")), kinds["shrine"]
    for kind in load_sites().kinds:
        assert sum(kinds[kind].values()), f"no Site {kind} got a Prop"


def test_dense_places_more_than_normal(placed):
    n = Counter()
    for _ctx, control, d in placed:
        n[control] += len(d.props)
    assert n["dense"] > n["normal"] > 0, n


def test_decor_none_places_nothing_at_a_site(rules, catalogue):
    for c in SITES:
        d = place(c, rules, catalogue, "none")
        assert not d.props and not d.drops


# ---------------------------------------------------------------------------
# P11: the Footprint gate on 40 seeds (slow, needs the install)
# ---------------------------------------------------------------------------

EQ = eq_path_from_env()
P11_SEEDS = range(1, 41)
#: P11 runs in blocks of seeds so the parallel runner spreads it (about 20 s a block).
P11_BLOCKS = [P11_SEEDS[i:i + 10] for i in range(0, len(P11_SEEDS), 10)]



@pytest.mark.slow
@pytest.mark.skipif(EQ is None, reason="EQ_PATH is not set (no EQ install to read)")
@pytest.mark.parametrize("control", CONTROLS)
@pytest.mark.parametrize("block", range(len(P11_BLOCKS)))
def test_p11_sites_with_props_pass_the_footprint_gate(rules, catalogue, control, block):
    """P11: at Normal and Dense (Sites and Decor both), Sites with their Props pass the
    wilderness Footprint gate with the trees and Structures, every POI reached and every
    Site_Clear free, on 40 seeds (here one control, one block of them). The gate reads the ZON the builder writes (``_gate_zon``,
    its Props from ``builder.decor_for``). Which models may stand on open ground is the
    catalogue's measured ``open_ground`` (``prop_catalogue.py screen``), not judged here."""
    import generators.wilderness.build as wb
    from analyzer.footprints import check_footprints, placed_from_zon
    from analyzer.traverse import AgentModel
    from generators.room_context import site_contexts

    agent = AgentModel()
    failed, props, kinds = [], Counter(), Counter()
    for seed in P11_BLOCKS[block]:
        spec = wb.wilderness_spec(f"p{seed}", seed)
        spec.sites = spec.decor = control
        ter = wb.build_wilderness_ter(spec, f"ter_p{seed}.ter", 2)
        here = 0
        for ctx in site_contexts(spec, ter):
            d = place(ctx, rules, catalogue, control)
            kinds[ctx.room_type] += 1
            props[ctx.room_type] += len(d.props)
            here += len(d.props)
            assert all(catalogue.models[p.key].open_ground for p in d.props)
            failed += [f"{control} seed {seed} {ctx.id}: {why}"
                       for why in site_clear_problems(ctx, d.props) + check(ctx, d)]
        zon, models = wb._gate_zon(spec, ter)
        assert sum(1 for o in zon.objects if o.name.startswith("decor_")) == here
        ground = wb._ground_raster(spec, ter, agent)
        report = check_footprints(ground, placed_from_zon(zon, models),
                                  wb.sites_for(spec, ter).pois(), agent)
        failed += [f"{control} seed {seed}: {f}" for f in report.failures]
    print("Sites and Props by kind:", {k: (kinds[k], props[k]) for k in sorted(kinds)})
    assert sum(props.values()), "no Props placed"
    assert not failed, failed[:10]