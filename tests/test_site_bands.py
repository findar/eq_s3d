"""Wilderness POIs task 11 (Req 9.1, 9.2's gate, 9.4; design P9, P10).

P9: built wilderness zones at Normal measure inside the stock bands of design finding 1, by the
survey's own code. Each zone is built, its ``.eqg`` read back, and the ZON's placed objects
clustered by ``site_survey.cluster`` and measured by ``site_survey.site_measures`` on the
shipped TER's walked ground, measured the way ``site_survey.ground_of`` measures a stock zone.

Which band. Sites per 1e6 u^2 uses the plains band: step 10 builds plains, and Normal aims at
0.3-0.5 inside plains' 0.1-0.5 (finding 1). Structures per Site and spacing use the all-zone
bands: the plains band is the p10-p90 of only five zones, so it is about their min and max
(Structures p90 2-10 is one centaur camp), where the all-zone band is over 21. A built zone
holds 1-3 Sites, so one zone's value is coarse; the sweep's median zone must sit in the band.
Spacing p10 is the exception: a zone with 2-3 Sites has its p10 equal to its p50 (both Sites'
nearest neighbour is the other), so the p10 is taken over every Site in the sweep pooled, where
stock's zones hold 6-43 Sites each.

Spacing p50 is printed but not asserted against finding 1's 195-910: it is set mostly by how
many Sites a zone holds. With 2-3 Sites in 4.8e6 u^2 any placement gives about 1000 u, and
stock's sparse zones read the same (qeytoqrg 896, nektulos 1046, cauldron 1282), so the
all-zone band, dominated by zones of 6-43 Sites, would test the count, not the placement. What
it asks, whether Sites cluster as stock's do, is asserted with the Clark-Evans ratio R: the
mean nearest-Site distance over 0.5 / sqrt(Sites per u^2), the mean a random placement at that
density would give (R < 1 clustered, about 1 random, > 1 dispersed). It doesn't depend on the
count. Stock's band is ``STOCK_R``; ``test_stock_r_band`` recomputes it.

The gate's first-try rate (build, then the pipeline's ``bowl_report`` on the TER read back)
holds at Normal and Dense, and a build stays within step 9's time (Sites none) plus 5 s.

The sweep is marked slow; ``test_a_build_reads_back_as_its_sites`` is the fast check.
"""

import os
import sys
import tempfile
import time
from pathlib import Path
from statistics import median

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from analyzer.traverse import AgentModel, build_walk_surface  # noqa: E402
from core.pfs import PfsArchive  # noqa: E402
from core.zon import ZonFile  # noqa: E402
from generators.builder import ZoneBuilder  # noqa: E402
from generators.pipeline import load_ter_from_eqg  # noqa: E402
from generators.sites.rules import STRUCTURE_KINDS  # noqa: E402
import generators.wilderness.build as wb  # noqa: E402
from site_survey import (NOT_STRUCTURE, PLAN_CELL, Ground, _samples, cluster,  # noqa: E402
                         site_measures)

# Finding 1's bands (p10-p90 of the per-zone values).
PER_AREA = (0.3, 0.5)          # Normal's aim, inside the plains band 0.1-0.5
STRUCTS_P50 = (1.0, 3.0)       # all 21 zones (plains the same)
STRUCTS_P90 = (1.8, 5.6)       # all 21 zones
SPACING_P10 = (130.0, 490.0)   # all 21 zones
#: Clark-Evans R, p10-p90 over the 20 kept stock zones with at least 3 Sites (median 1.02,
#: min 0.50 southkarana, max 1.73 nektulos; plains 0.50-0.95). Reproduce with
#: ``python -m pytest tests/test_site_bands.py -k stock_r -s`` (needs EQ_PATH).
STOCK_R = (0.64, 1.64)
MIN_SITES_R = 3                # a zone's R needs this many Sites

EQ = Path(os.environ.get("EQ_PATH", r"F:\everquest_rof2"))

SEEDS = range(1000, 1040)

#: Our Structure kinds as the survey names stock models (``site_survey.STRUCTURES``).
SURVEY_KIND = {"fire_ring": "fire", "tent": "tent", "lean_to": "lean-to", "hut": "hut",
               "barn": "house", "tower": "tower", "fence": "fence", "ruin_wall": "ruin",
               "standing_stone": "stone", "altar_stone": "stone", "monument": "stone"}


def _kind(model: str) -> str:
    """A ZON model's survey kind: trees are scenery, ``site_<kind>_...`` a Structure."""
    m = model.lower()
    if m.startswith("veg_"):
        return "tree"
    for k in sorted(STRUCTURE_KINDS, key=len, reverse=True):
        if m.startswith(f"site_{k}_"):
            return SURVEY_KIND[k]
    return "unknown"


def _ground(ter, zon: ZonFile) -> Ground:
    """``site_survey.ground_of`` for a built TER: the largest walked network on the 16 u plan
    raster; cells inside an AWT region are wet (left out, as stock's ``WT`` regions are)."""
    surf = build_walk_surface(ter, AgentModel())
    tri = surf.verts[surf.faces]
    cr = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area = 0.5 * np.linalg.norm(cr, axis=1)
    nz = cr[:, 2] / np.maximum(2 * area, 1e-9)            # our floors wind up
    slope = np.degrees(np.arccos(np.clip(nz, -1, 1)))
    std = np.nonzero(surf.standable)[0]
    by: dict = {}
    for fi in std:
        by[int(surf.component[fi])] = by.get(int(surf.component[fi]), 0.0) + area[fi]
    main = max(by, key=by.get)
    walked = std[surf.component[std] == main]
    up = np.nonzero((nz > 0.05) & (area > 0))[0]
    pts = _samples(tri[walked], PLAN_CELL / 2)
    cells, first = np.unique(np.floor(pts[:, :2] / PLAN_CELL).astype(np.int64), axis=0,
                             return_index=True)
    p = pts[first] + [0.0, 0.0, 3.0]
    wet = np.zeros(len(cells), bool)
    for r in zon.regions:
        if r.name.upper().startswith("AWT"):
            wet |= ((np.abs(p[:, 0] - r.center_x) <= r.extend_x)
                    & (np.abs(p[:, 1] - r.center_y) <= r.extend_y)
                    & (np.abs(p[:, 2] - r.center_z) <= r.extend_z))
    cen = surf.centroids
    none = np.zeros(len(walked), np.int64)
    return Ground(cen[walked], area[walked], slope[walked], none, cen[up], area[up], slope[up],
                  cells, np.zeros(len(cells), np.int64), wet)


def _spec(seed: int, sites: str):
    spec = wb.wilderness_spec(f"b{seed}", seed)
    spec.sites = sites
    return spec


def _zones(shared, sites: str, seeds) -> list:
    """The zones of ``seeds`` at ``sites``, each built once per session whichever worker
    asks first (``conftest.SharedResults``): the band and first-try tests share the Normal
    builds. Claimed from the far end, so two tests that start together meet in the middle."""
    keys = [("site_bands", s, sites) for s in seeds][::-1]
    return shared.get_many(keys, _make_zone)[::-1]


def _make_zone(key: tuple) -> dict:
    """Build, read the archive back, gate it as the pipeline does, and measure its Sites."""
    _tag, seed, sites = key
    spec = _spec(seed, sites)
    with tempfile.TemporaryDirectory() as tmp:
        r = ZoneBuilder(spec).build(output_dir=Path(tmp), write_glb=False)
        ter, _ = load_ter_from_eqg(r.eqg_path)
        zon = ZonFile.from_bytes(PfsArchive.from_file(r.eqg_path).get(f"{spec.name}.zon"))
    gate = wb.bowl_report(spec, ter).passed
    if sites == "none":
        return {"gate": gate}
    objs = [(o.x, o.y, o.z, zon.models[o.model_id], _kind(zon.models[o.model_id]))
            for o in zon.objects]
    sites_ = cluster(objs)
    m = site_measures(sites_, _ground(ter, zon), np.zeros((0, 2)), np.zeros((0, 2)))
    placed = wb.sites_for(spec, ter).placement.sites
    return {"gate": gate, "m": m, "placed": len(placed),
            "placed_structs": sorted(len(s.structures) for s in placed),
            "kinds": {o[4] for o in objs if o[3].lower().startswith("site_")}}


def test_a_build_reads_back_as_its_sites(shared_results):
    """The fast check: one Normal build's shipped Structures read back through the survey's
    code as the Sites placement made (every one a Structure, none merged or split)."""
    z = _zones(shared_results, "normal", [1000])[0]
    assert z["kinds"] and not z["kinds"] & NOT_STRUCTURE, z["kinds"]
    m = z["m"]
    assert m["sites"] == z["placed"] >= 1
    assert sorted(m["structs"].tolist()) == z["placed_structs"]
    assert 2.0e6 < m["ground"] < 20e6, m["ground"]


def clark_evans(m: dict) -> float:
    """Clark-Evans R of one zone's ``site_measures``: mean nearest-Site distance over the
    random expectation 0.5 / sqrt(Sites per u^2)."""
    return float(m["spacing"].mean() / (0.5 / np.sqrt(m["sites"] / m["ground"])))


@pytest.mark.slow
@pytest.mark.skipif(not EQ.exists(), reason="EQ install not present (set EQ_PATH)")
def test_stock_r_band():
    """``STOCK_R`` from the stock zones, by the survey's own code (``site_survey.main``'s
    per-zone steps; towns left out, ground cached under output/site_survey/cache)."""
    import site_survey as ss
    agent, rs = AgentModel(), {}
    for zone in ss.ZONES:
        if zone in ss.TOWNS:
            continue
        ground = ss.ground_of(EQ, zone, agent, ROOT / "output" / "site_survey" / "cache")
        _nodes, kinds = ss.regions(EQ, zone)
        ground.cell_wet = np.array([kinds.get(int(r), "") for r in ground.cell_region]) == "water"
        m = site_measures(cluster(ss.placed(EQ, zone)), ground, np.zeros((0, 2)), np.zeros((0, 2)))
        if m["sites"] >= MIN_SITES_R:
            rs[zone] = clark_evans(m)
    v = list(rs.values())
    print(f"\nstock R: {len(v)} zones, p10 {np.percentile(v, 10):.2f}, median {median(v):.2f}, "
          f"p90 {np.percentile(v, 90):.2f}; " + ", ".join(f"{z} {r:.2f}" for z, r in rs.items()))
    assert len(v) == 20
    assert np.percentile(v, [10, 90]) == pytest.approx(STOCK_R, abs=0.005)


def _band(name, value, band):
    lo, hi = band
    return None if lo <= value <= hi else f"{name} {value:.2f} outside {lo}-{hi}"


@pytest.mark.slow
def test_p9_normal_zones_measure_inside_the_stock_bands(shared_results):
    built = _zones(shared_results, "normal", SEEDS)
    zs = [z["m"] for z in built]
    per = [m["per_area"] for m in zs]
    pooled = sum(m["sites"] for m in zs) / (sum(m["ground"] for m in zs) / 1e6)
    p50 = [float(np.percentile(m["structs"], 50)) for m in zs if m["sites"]]
    p90 = [float(np.percentile(m["structs"], 90)) for m in zs if m["sites"]]
    sp50 = [float(np.percentile(m["spacing"], 50)) for m in zs if len(m["spacing"])]
    spacing = np.concatenate([m["spacing"] for m in zs])
    allst = np.concatenate([m["structs"] for m in zs])
    split = [s for s, z in zip(SEEDS, built) if z["m"]["sites"] != z["placed"]]
    r_zone = [clark_evans(m) for m in zs if m["sites"] >= MIN_SITES_R]
    # Pooled over every zone with 2+ Sites: each Site's nearest distance over its own zone's
    # random expectation.
    r_pool = float(np.mean(np.concatenate(
        [m["spacing"] / (0.5 / np.sqrt(m["sites"] / m["ground"])) for m in zs if m["sites"] >= 2])))
    print(f"\nNormal, seeds {SEEDS.start}-{SEEDS.stop - 1}: Sites/1e6 median {median(per):.2f} "
          f"pooled {pooled:.2f} (p10 {np.percentile(per, 10):.2f}, p90 {np.percentile(per, 90):.2f}); "
          f"Structures zone p50 median {median(p50):.1f}, zone p90 median {median(p90):.1f} "
          f"({len(allst)} Sites: lone {np.mean(allst == 1):.0%}, 2-5 "
          f"{np.mean((allst >= 2) & (allst <= 5)):.0%}, 6+ {np.mean(allst >= 6):.0%}); "
          f"spacing zone p50 median {median(sp50):.0f} ({len(sp50)} zones with 2+ Sites), "
          f"pooled p50 {np.percentile(spacing, 50):.0f}, p10 {np.percentile(spacing, 10):.0f}, "
          f"closest {spacing.min():.0f}; Clark-Evans R median {median(r_zone):.2f} over "
          f"{len(r_zone)} zones with {MIN_SITES_R}+ Sites, pooled {r_pool:.2f}; "
          f"read back split on seeds {split}")
    bad = [b for b in (_band("Sites per 1e6 u^2, median zone", median(per), PER_AREA),
                       _band("Sites per 1e6 u^2, pooled", pooled, PER_AREA),
                       _band("Structures per Site, zone p50", median(p50), STRUCTS_P50),
                       _band("Structures per Site, zone p90", median(p90), STRUCTS_P90),
                       _band("spacing p10, pooled", float(np.percentile(spacing, 10)), SPACING_P10),
                       _band(f"Clark-Evans R, median of {len(r_zone)} zones", median(r_zone), STOCK_R),
                       _band("Clark-Evans R, pooled", r_pool, STOCK_R))
           if b]
    assert not bad, bad


@pytest.mark.slow
def test_gate_first_try_rate_holds(shared_results):
    """Req 9.2: at Normal and Dense the gate passes on the first try at least as often as
    step 9's (Sites none) on the same seeds."""
    passed = {s: [n for n, z in zip(SEEDS, _zones(shared_results, s, SEEDS)) if z["gate"]]
              for s in ("none", "normal", "dense")}
    print(f"\nfirst try, seeds {SEEDS.start}-{SEEDS.stop - 1}: "
          + ", ".join(f"{s} {len(p)}/{len(SEEDS)}" for s, p in passed.items()))
    for s in ("normal", "dense"):
        assert len(passed[s]) >= len(passed["none"]), (s, sorted(set(passed["none"]) - set(passed[s])))


def _timed(seed: int, sites: str, out: Path) -> float:
    """A cold wilderness build (EQG and GLB) and its gate, in CPU time."""
    for f in (wb._landscape, wb._sites, wb._vegetation):
        f.cache_clear()
    spec = _spec(seed, sites)
    t0 = time.process_time()
    r = ZoneBuilder(spec).build(output_dir=out, write_glb=True)
    ter, _ = load_ter_from_eqg(r.eqg_path)
    assert wb.bowl_report(spec, ter).passed
    return time.process_time() - t0


@pytest.mark.slow
def test_p10_sites_cost_at_most_5_s(tmp_path):
    """Req 9.4: Normal against none on the same seed, best of three each in CPU time. The bar
    doubles under the parallel suite, as in test_features_sweep."""
    runs = {"none": [], "normal": []}
    for k in range(3):
        for s in runs:
            runs[s].append(_timed(1955208177, s, tmp_path / f"{s}{k}"))
    none, normal = min(runs["none"]), min(runs["normal"])
    print(f"\nwilderness 1955208177: none {none:.2f} s, normal {normal:.2f} s")
    assert normal <= none + (10.0 if os.environ.get("PYTEST_XDIST_WORKER") else 5.0), runs
