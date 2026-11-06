"""Room walls task 12 (Requirement 12; design W11, W12): built zones measure like stock ones,
by the wall survey's own code, and pass the gate as often as before.

The bands are design finding 1's. Each measure is the median over a few seeds, with a
small tolerance for that sample. Two sides are one-sided, on purpose: built floors and
ceilings are perfectly flat (flat share 1.0), a shade above Kurn's 0.99 and 0.97, and
a built plain room's Fill can only come down toward stock.
"""

import os
import random
import sys
import time
from pathlib import Path
from statistics import median

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from ai.expand import plan_to_spec  # noqa: E402
from ai.schema import ZonePlan  # noqa: E402
from analyzer.traverse import AgentModel  # noqa: E402
from generators.geometry import build_mesh  # noqa: E402
from generators.pipeline import generate_validated  # noqa: E402
from wall_survey import measure  # noqa: E402

BANDS = {
    "rough": {"axis": (.37, .57), "plumb": (.96, 1), "edge": (10, 14), "run": (17, 31), "fill": (.67, .74),
              "floor_relief": (0, 5.4), "floor_flat": (.63, .93), "ceil_spread": (.06, .65),
              "ceil_flat": (.34, .88)},
    "hewn": {"axis": (.52, .69), "plumb": (.95, 1), "edge": (7, 14), "run": (28, 38), "fill": (.70, .74),
             "floor_relief": (0, 4.9), "floor_flat": (.51, .90), "ceil_spread": (.21, .54),
             "ceil_flat": (.48, .74)},
    "built": {"axis": (.71, .96), "plumb": (.97, 1), "edge": (5, 14), "run": (28, 39), "fill": (.71, .76),
              "floor_relief": (0, .5), "floor_flat": (.84, 1), "ceil_spread": (0, .27),
              "ceil_flat": (.87, 1)},
}
TOLERANCE = 0.03    # a share of the band's top, for the sample


@pytest.fixture(scope="module")
def measured():
    agent = AgentModel()
    out = {}
    for style in BANDS:
        rows = []
        for seed in (2, 4, 7, 10):
            plan = ZonePlan(name="w12", zone_type="dungeon", room_count=20, layout="graph", walls=style,
                            verticality="flat").validate()
            r = measure(build_mesh(plan_to_spec(plan, seed=seed)).to_ter("w12"), agent, floors_up=True)
            r["run"] = r["run"][1]
            rows.append(r)
        out[style] = {k: median(row[k] for row in rows) for k in BANDS[style]}
    return out


@pytest.mark.slow
@pytest.mark.parametrize("style", sorted(BANDS))
def test_w11_built_zones_measure_like_their_stock_zones(measured, style):
    bad = {}
    for key, (lo, hi) in BANDS[style].items():
        slack = TOLERANCE * hi
        if not lo - slack <= measured[style][key] <= hi + slack:
            bad[key] = (round(measured[style][key], 2), (lo, hi))
    print(f"\n{style}: " + ", ".join(f"{k} {v:.2f}" for k, v in measured[style].items()))
    assert not bad, bad


@pytest.mark.slow
def test_w11_the_styles_differ_the_right_way(measured):
    assert measured["built"]["axis"] > measured["hewn"]["axis"] > measured["rough"]["axis"]
    assert measured["built"]["ceil_flat"] > measured["hewn"]["ceil_flat"]
    assert measured["built"]["ceil_flat"] > measured["rough"]["ceil_flat"]
    assert measured["built"]["ceil_spread"] < measured["hewn"]["ceil_spread"]
    assert measured["built"]["ceil_spread"] < measured["rough"]["ceil_spread"]
    assert measured["rough"]["run"] < measured["hewn"]["run"] <= measured["built"]["run"]


SWEEP = [(style, rule_set, theme, race, rooms, vert)
         for style, rule_set, theme, race, rooms, vert in (
             ("rough", "classic_eq", "", "", 12, "moderate"),
             ("rough", "warren", "", "", 12, "dramatic"),
             ("rough", "", "temple", "", 12, "moderate"),
             ("rough", "classic_eq", "", "ogre", 8, "dramatic"),
             ("rough", "warren", "", "dragon", 8, "moderate"),
             ("hewn", "classic_eq", "", "", 12, "dramatic"),
             ("hewn", "warren", "", "", 12, "flat"),
             ("hewn", "", "fortress", "", 16, "moderate"),
             ("hewn", "classic_eq", "", "giant", 8, "moderate"),
             ("built", "classic_eq", "", "", 12, "dramatic"),
             ("built", "warren", "", "", 16, "moderate"),
             ("built", "", "temple", "", 12, "flat"),
             ("built", "classic_eq", "", "dragon", 8, "dramatic"),
         )]


@pytest.mark.slow
@pytest.mark.parametrize("style, rule_set, theme, race, rooms, vert", SWEEP)
def test_w12_first_try_across_styles(tmp_path, style, rule_set, theme, race, rooms, vert):
    plan = ZonePlan(name="w12", zone_type="dungeon", room_count=rooms, layout="graph", walls=style,
                    rule_set=rule_set, dungeon_theme=theme, dungeon_race=race, verticality=vert).validate()
    first = 0
    seeds = range(4)
    for seed in seeds:
        vb = generate_validated(lambda s: plan_to_spec(plan, seed=s), zone_type="dungeon", zone_id="w12",
                                rng=random.Random(seed), output_dir=tmp_path / str(seed), write_glb=False,
                                failure_log=None, max_attempts=4, timeout_s=300.0)
        assert vb.validated
        first += vb.attempts == 1
    print(f"\n{style} {rule_set or theme} {race} {vert}: first try {first}/{len(seeds)}")
    assert first == len(seeds), "step 7's stacked builds passed first try on every case"


@pytest.mark.slow
def test_same_inputs_same_eqg(tmp_path):
    from generators.builder import ZoneBuilder
    plan = ZonePlan(name="w12", zone_type="dungeon", room_count=10, layout="graph", walls="rough").validate()
    eqgs = [ZoneBuilder(plan_to_spec(plan, seed=5)).build(output_dir=tmp_path / str(k), write_glb=False)
            .eqg_path.read_bytes() for k in range(2)]
    assert eqgs[0][:-4] == eqgs[1][:-4]


def _timed(tmp_path, layout, walls):
    plan = ZonePlan(name="w12", zone_type="dungeon", room_count=14, layout=layout, walls=walls,
                    verticality="moderate").validate()
    t0 = time.process_time()
    vb = generate_validated(lambda s: plan_to_spec(plan, seed=s), zone_type="dungeon", zone_id="w12", seed=8,
                            output_dir=tmp_path, failure_log=None)
    assert vb.validated
    return time.process_time() - t0


@pytest.mark.slow
def test_w12_a_shaped_build_stays_within_its_budget(tmp_path):
    """Req 12.6: at most 10 s over a plain build, the best of two runs each, in CPU time.
    Alone a rough build costs about 6 s. Under the parallel suite the same work cost 13 s
    of CPU time (shared caches), which says nothing about the build, so the bar doubles
    there."""
    runs = {"plain": [], "rough": []}
    for k in range(2):
        runs["plain"].append(_timed(tmp_path / f"p{k}", "classic", ""))
        runs["rough"].append(_timed(tmp_path / f"r{k}", "graph", "rough"))
    plain, rough = min(runs["plain"]), min(runs["rough"])
    print(f"\n14 rooms: plain {plain:.2f} s, rough {rough:.2f} s")
    budget = 20.0 if os.environ.get("PYTEST_XDIST_WORKER") else 10.0
    assert rough <= plain + budget, runs
