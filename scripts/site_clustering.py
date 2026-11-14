r"""How stock places its Sites against each other (step 13, task 1; design finding 1).

Reads the surveyed Classic outdoor zones with ``site_survey``'s own code (``placed``,
``cluster``, ``site_measures``, ``ground_of`` with its cache, towns left out) and prints:

- **per zone**: Sites, dry walked ground (1e6 u^2), Clark-Evans R_CE (as
  ``tests/test_site_bands.clark_evans``: mean nearest-Site distance over
  ``0.5 / sqrt(Sites / ground)``), R_mc (the same mean over the mean nearest distance of as
  many points dropped uniformly on the zone's own dry walked cells, ``DRAWS`` draws, so the
  ground's shape and edges are in the expectation) with p (the share of draws as clustered
  or more), Sites per Group (single linkage of Site centres at ``GAP``), the share of Sites
  with another within ``GAP`` ("in gap"), and nearest-Site p10 / p50;
- **per biome group** (zones with at least 3 Sites): R_CE min-max (median), R_mc median,
  "in gap" median; plus all zones, whose R_CE p10-p90 is step 10's ``STOCK_R``;
- **the plains' Groups** at 200, 300 and 400 u: count, size shares, mean size, within-Group
  nearest-neighbour p10/p50/p90 and Group-centre nearest-neighbour p10/p50, pooled;
- the ``[biomes.plains.groups]`` block those numbers give (``rules/sites/biomes.toml``).

The biome groups (``BIOME``) are a reading of the zones by eye, not data in the survey.
R_mc's draws use a fixed generator seed (``MC_SEED``), so the numbers repeat.

Usage::

    python scripts/site_clustering.py --eq-path F:\everquest_rof2
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import site_survey as ss  # noqa: E402
from analyzer.traverse import AgentModel  # noqa: E402

#: Each surveyed zone's biome group: this script's reading of the zones, not the survey's.
BIOME = {
    "qeytoqrg": "plains", "qey2hh1": "plains", "northkarana": "plains",
    "eastkarana": "plains", "southkarana": "plains",
    "innothule": "swamp", "feerrott": "swamp",
    "everfrost": "snow",
    "lakerathe": "hills", "rathemtn": "hills", "ecommons": "hills", "steamfont": "hills",
    "cauldron": "hills",
    "nro": "desert", "sro": "desert", "oasis": "desert",
    "tox": "forest", "lfaydark": "forest", "kithicor": "forest", "nektulos": "forest",
    "beholder": "hills",
}
GROUPS = ("plains", "swamp", "snow", "hills", "desert", "forest")
GAP = 300.0             # u: Sites this close are one Group
GAPS = (200.0, 300.0, 400.0)
MIN_SITES_R = 3         # a zone's R needs this many Sites (tests/test_site_bands.MIN_SITES_R)
DRAWS = 400
MC_SEED = 13
MAX_SIZE = 4            # no control asks for more than 5 Sites: larger Groups fold into 4


def clark_evans(n: int, ground: float, nn: np.ndarray) -> float:
    """As ``tests/test_site_bands.clark_evans``."""
    return float(nn.mean() / (0.5 / np.sqrt(n / ground)))


def nearest(c: np.ndarray) -> np.ndarray:
    return cKDTree(c).query(c, k=2)[0][:, 1]


def r_mc(c: np.ndarray, cells: np.ndarray, rng: np.random.Generator) -> tuple:
    """R against uniform points on the zone's dry walked cells, and the share of draws whose
    mean nearest distance is at most the Sites' (as clustered or more)."""
    obs = nearest(c).mean()
    means = np.empty(DRAWS)
    for k in range(DRAWS):
        pick = cells[rng.integers(0, len(cells), len(c))]
        pts = (pick + rng.random((len(c), 2))) * ss.PLAN_CELL
        means[k] = nearest(pts).mean()
    return float(obs / means.mean()), float((means <= obs).mean())


def link(c: np.ndarray, gap: float) -> np.ndarray:
    """Single-linkage Group label per point at ``gap``."""
    parent = list(range(len(c)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, j in cKDTree(c).query_pairs(gap):
        parent[find(i)] = find(j)
    roots = [find(i) for i in range(len(c))]
    ids = {r: k for k, r in enumerate(dict.fromkeys(roots))}
    return np.array([ids[r] for r in roots])


def zone_rows(eq: Path, cache: Path) -> dict:
    agent, rng, rows = AgentModel(), np.random.default_rng(MC_SEED), {}
    for zone in ss.ZONES:
        if zone in ss.TOWNS:
            continue
        ground = ss.ground_of(eq, zone, agent, cache)
        _nodes, kinds = ss.regions(eq, zone)
        ground.cell_wet = np.array([kinds.get(int(r), "") for r in ground.cell_region]) == "water"
        sites = ss.cluster(ss.placed(eq, zone))
        m = ss.site_measures(sites, ground, np.zeros((0, 2)), np.zeros((0, 2)))
        row = {"sites": m["sites"], "ground": m["ground"], "biome": BIOME[zone]}
        if m["sites"] >= 2:
            c = np.array([s.centre for s in sites])
            lab = link(c, GAP)
            row.update(c=c, nn=m["spacing"], r_ce=clark_evans(m["sites"], m["ground"], m["spacing"]),
                       per_group=len(c) / (lab.max() + 1), in_gap=float((m["spacing"] <= GAP).mean()))
            row["r_mc"], row["p"] = r_mc(c, ground.cells[~ground.cell_wet], rng)
        rows[zone] = row
    return rows


def groups_at(rows: dict, gap: float) -> dict:
    """The plains' Groups at ``gap``, pooled over the plains zones."""
    sizes, within, centre_nn, members = Counter(), [], [], Counter()
    for r in rows.values():
        if r["biome"] != "plains" or "c" not in r:
            continue
        c = r["c"]
        lab = link(c, gap)
        n = lab.max() + 1
        cent = np.array([c[lab == g].mean(axis=0) for g in range(n)])
        for g in range(n):
            pts = c[lab == g]
            sizes[len(pts)] += 1
            members[len(pts)] += len(pts)
            if len(pts) >= 2:
                within.extend(nearest(pts).tolist())
        if n >= 2:
            centre_nn.extend(nearest(cent).tolist())
    return {"sizes": sizes, "members": members, "within": np.array(within),
            "centre_nn": np.array(centre_nn)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--eq-path", required=True, type=Path)
    ap.add_argument("--cache", type=Path, default=ROOT / "output" / "site_survey" / "cache")
    args = ap.parse_args(argv)
    rows = zone_rows(args.eq_path, args.cache)

    print(f"{'zone':12} {'group':7} {'sites':>5} {'ground':>6} {'R_CE':>5} {'R_mc':>5} "
          f"{'p':>5} {'/Group':>6} {'in gap':>6} {'NN p10/p50':>11}")
    for zone, r in rows.items():
        if "c" not in r:
            print(f"{zone:12} {r['biome']:7} {r['sites']:5d} {r['ground'] / 1e6:6.1f}  (under 2 Sites)")
            continue
        print(f"{zone:12} {r['biome']:7} {r['sites']:5d} {r['ground'] / 1e6:6.1f} {r['r_ce']:5.2f} "
              f"{r['r_mc']:5.2f} {r['p']:5.2f} {r['per_group']:6.2f} {r['in_gap']:6.0%} "
              f"{np.percentile(r['nn'], 10):5.0f}/{np.percentile(r['nn'], 50):<5.0f}")

    big = {z: r for z, r in rows.items() if "c" in r and r["sites"] >= MIN_SITES_R}
    print(f"\nBy group, zones with {MIN_SITES_R}+ Sites:")
    print(f"{'group':7} {'zones':>5} {'R_CE min-max (median)':>22} {'R_mc med':>8} "
          f"{'in gap med':>10} {'NN p10 min-max':>14}")
    for g in (*GROUPS, "all"):
        rs = [r for r in big.values() if g == "all" or r["biome"] == g]
        if not rs:
            continue
        ce = [r["r_ce"] for r in rs]
        p10 = [np.percentile(r["nn"], 10) for r in rs]
        span = (f"p10-p90 {np.percentile(ce, 10):.2f}-{np.percentile(ce, 90):.2f}" if g == "all"
                else f"{min(ce):.2f}-{max(ce):.2f}")
        print(f"{g:7} {len(rs):5d} {span + f' ({np.median(ce):.2f})':>22} "
              f"{np.median([r['r_mc'] for r in rs]):8.2f} "
              f"{np.median([r['in_gap'] for r in rs]):10.0%} {min(p10):6.0f}-{max(p10):<6.0f}")
    plains = [r for r in big.values() if r["biome"] == "plains"]
    allz = [r["r_ce"] for r in big.values()]
    print(f"  reproduces: plains R_CE {min(r['r_ce'] for r in plains):.2f}-"
          f"{max(r['r_ce'] for r in plains):.2f} (spec 0.50-0.95); all-zone p10-p90 "
          f"{np.percentile(allz, 10):.2f}-{np.percentile(allz, 90):.2f} (STOCK_R 0.64-1.64)")

    print(f"\nPlains Groups (single linkage of {sum(r['sites'] for r in plains)} Sites):")
    print(f"{'gap':>5} {'Groups':>6} {'sizes (share of Groups)':40} {'mean':>5} "
          f"{'within p10/p50/p90':>18} {'centre p10/p50':>14}")
    at = {}
    for gap in GAPS:
        g = at[gap] = groups_at(rows, gap)
        n = sum(g["sizes"].values())
        shares = ", ".join(f"{k}: {v / n:.0%}" for k, v in sorted(g["sizes"].items()))
        mean = sum(k * v for k, v in g["sizes"].items()) / n
        w = np.percentile(g["within"], [10, 50, 90])
        cn = np.percentile(g["centre_nn"], [10, 50])
        print(f"{gap:5.0f} {n:6d} {shares:40} {mean:5.2f} "
              f"{w[0]:5.0f}/{w[1]:.0f}/{w[2]:<5.0f} {cn[0]:6.0f}/{cn[1]:<6.0f}")
    g = at[GAP]
    tot = sum(g["members"].values())
    print("  Sites by Group size at 300 u: " + ", ".join(
        f"{k}: {v}" for k, v in sorted(g["members"].items())) + f" of {tot} "
        f"({g['members'][1] / tot:.0%} alone)")

    # The block task 2 writes: sizes over 4 fold into 4; the rest from the 300 u row.
    n = sum(g["sizes"].values())
    folded = Counter({min(k, MAX_SIZE): 0 for k in g["sizes"]})
    for k, v in g["sizes"].items():
        folded[min(k, MAX_SIZE)] += v
    shares = {k: round(v / n, 2) for k, v in sorted(folded.items())}
    shares[1] = round(1 - sum(v for k, v in shares.items() if k != 1), 2)
    w = np.percentile(g["within"], [10, 90])
    cn10 = np.percentile(g["centre_nn"], 10)
    ce = [r["r_ce"] for r in plains]
    ig = [r["in_gap"] for r in plains]
    p10 = [np.percentile(r["nn"], 10) for r in plains]
    print("\n[biomes.plains.groups]")
    print(f"gap = {GAP:.0f}")
    print("sizes = { " + ", ".join(f"{k} = {v:.2f}" for k, v in shares.items()) + " }")
    print(f"within = [{w[0]:.0f}, {w[1]:.0f}]")
    print(f"spacing = 600            # Group-centre NN p10 {cn10:.0f}, rounded down")
    print(f"target_r = [{min(ce):.2f}, {max(ce):.2f}]")
    print(f"target_in_gap = [{min(ig):.2f}, {max(ig):.2f}]")
    print(f"target_nn_p10 = [{min(p10):.0f}, {max(p10):.0f}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
