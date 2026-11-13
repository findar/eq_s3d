"""Room layouts task 11 (Requirement 9; design F9, F10): built zones measure like stock by the room
survey's own code, and pass the gate as often as before.

Rooms with a solid: stock's band is a floor, and 0.6 of rooms a ceiling, because Features stand in
for placed objects until step 11 (design finding 1). Raised floor: stock's band, with its low end
taken loosely, since themed zones trade some of it for solids. The sample's few seeds get a small
tolerance.
"""

import os
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
from generators.builder import ZoneBuilder  # noqa: E402
from generators.geometry import build_mesh  # noqa: E402
from generators.pipeline import generate_validated  # noqa: E402
from room_feature_survey import measure_rooms  # noqa: E402
from tests.conftest import gated_attempts, gated_key  # noqa: E402

SOLID_FLOOR = {"rough": 0.00, "hewn": 0.05, "built": 0.20}
SOLID_CEILING = 0.60
RAISED = {"rough": (0.00, 0.47), "hewn": (0.15, 0.65), "built": (0.00, 0.17)}
TOLERANCE = 0.06


def _plan(walls="", theme="", features="normal", rooms=16, verticality="flat", rule_set="", race="",
          zone_type="dungeon"):
    return ZonePlan(name="w11", zone_type=zone_type, room_count=rooms, layout="graph", walls=walls, features=features,
                    dungeon_theme=theme, rule_set=rule_set, dungeon_race=race, verticality=verticality).validate()


def _measure(walls, theme=""):
    agent = AgentModel()
    rows, solid = [], []
    for seed in (2, 4, 7, 10):
        spec = plan_to_spec(_plan(walls, theme), seed=seed)
        rows.append(measure_rooms(build_mesh(spec).to_ter("w11"), agent, floors_up=True))
        solid.append(sum(any(f.kind != "dais" for f in r.features) for r in spec.rooms) / len(spec.rooms))
    return {"survey": median(r["with_free"] for r in rows), "solid": median(solid),
            "raised": median(r["raised"] for r in rows), "rise": median(r["rise"] for r in rows)}


@pytest.mark.slow
@pytest.mark.parametrize("walls", ["rough", "hewn", "built"])
def test_f9_plain_zones_measure_like_their_stock_zones(walls):
    m = _measure(walls)
    print(f"\n{walls}: {m}")
    assert m["survey"] >= SOLID_FLOOR[walls] - TOLERANCE
    assert m["solid"] <= SOLID_CEILING
    lo, hi = RAISED[walls]
    assert lo - TOLERANCE <= m["raised"] <= hi + TOLERANCE
    assert 2.0 <= m["rise"] <= 8.0


@pytest.mark.slow
@pytest.mark.parametrize("walls, theme", [("rough", "warren"), ("hewn", "mine_delve"), ("built", "fortress"),
                                          ("built", "temple"), ("hewn", "temple"), ("built", "tomb")])
def test_f9_themed_zones_stand_out_and_stay_under_the_ceiling(walls, theme):
    m = _measure(walls, theme)
    print(f"\n{walls} {theme}: {m}")
    assert SOLID_FLOOR[walls] <= m["solid"] <= SOLID_CEILING + TOLERANCE
    assert m["raised"] > 0


CASES = [("rough", "classic_eq", "", "", "normal", 12, "moderate", "dungeon"),
         ("rough", "", "warren", "", "dense", 12, "dramatic", "dungeon"),
         ("rough", "classic_eq", "", "ogre", "normal", 8, "dramatic", "dungeon"),
         ("hewn", "", "temple", "", "normal", 12, "dramatic", "dungeon"),
         ("hewn", "", "mine_delve", "", "dense", 16, "moderate", "dungeon"),
         ("hewn", "classic_eq", "", "dragon", "normal", 8, "moderate", "dungeon"),
         ("built", "", "fortress", "", "dense", 16, "moderate", "dungeon"),
         ("built", "", "tomb", "", "sparse", 12, "flat", "dungeon"),
         ("built", "warren", "", "giant", "normal", 8, "moderate", "dungeon"),
         ("", "", "", "", "normal", 8, "dramatic", "outdoor_dungeon"),
         ("built", "", "temple", "", "dense", 5, "moderate", "outdoor_dungeon")]


SEEDS = range(4)


def _key(walls, rule_set, theme, race, features, rooms, vert, zone_type, seed):
    fields = dict(zone_type=zone_type, room_count=rooms, layout="graph", walls=walls, features=features,
                  dungeon_theme=theme, rule_set=rule_set, dungeon_race=race, verticality=vert)
    return gated_key(fields, seed, 4, 300.0)


@pytest.mark.slow
@pytest.mark.parametrize("walls, rule_set, theme, race, features, rooms, vert, zone_type, seed",
                         [case + (s,) for case in CASES for s in SEEDS])
def test_f10_passes_within_the_retries(shared_results, walls, rule_set, theme, race, features, rooms, vert,
                                       zone_type, seed):
    """One seed of a case: it passes within four attempts. The case's first-try count
    below reads these builds, so a case's seeds spread over the workers."""
    tries = shared_results.get(_key(walls, rule_set, theme, race, features, rooms, vert, zone_type, seed),
                               gated_attempts)
    assert tries is not None, "out of retries"


@pytest.mark.slow
@pytest.mark.parametrize("walls, rule_set, theme, race, features, rooms, vert, zone_type", CASES)
def test_f10_first_try(shared_results, walls, rule_set, theme, race, features, rooms, vert, zone_type):
    case = (walls, rule_set, theme, race, features, rooms, vert, zone_type)
    keys = [_key(*case, s) for s in SEEDS]
    tries = shared_results.get_many(keys[::-1], gated_attempts)[::-1]
    print(f"\n{walls} {theme or rule_set} {race} {features} {vert} {zone_type}: attempts {tries}")
    assert None not in tries, tries
    assert sum(t == 1 for t in tries) >= 3, tries


@pytest.mark.slow
def test_f10_same_inputs_same_eqg(tmp_path):
    plan = _plan("rough", "warren")
    eqgs = [ZoneBuilder(plan_to_spec(plan, seed=5)).build(output_dir=tmp_path / str(k), write_glb=False)
            .eqg_path.read_bytes() for k in range(2)]
    assert eqgs[0][:-4] == eqgs[1][:-4]


def _timed(tmp_path, features):
    plan = _plan("rough", "warren", features, rooms=14, verticality="moderate")
    t0 = time.process_time()
    vb = generate_validated(lambda s: plan_to_spec(plan, seed=s), zone_type="dungeon", zone_id="w11", seed=8,
                            output_dir=tmp_path, failure_log=None)
    assert vb.validated
    return time.process_time() - t0


@pytest.mark.slow
def test_f10_features_cost_at_most_5_s(tmp_path):
    """Req 9.4: over the same build with none, the best of two runs each in CPU time. The bar
    doubles under the parallel suite, as in test_walls_build."""
    runs = {"none": [], "normal": []}
    for k in range(2):
        for f in runs:
            runs[f].append(_timed(tmp_path / f"{f}{k}", f))
    none, normal = min(runs["none"]), min(runs["normal"])
    print(f"\n14 rooms, warren: none {none:.2f} s, normal {normal:.2f} s")
    assert normal <= none + (10.0 if os.environ.get("PYTEST_XDIST_WORKER") else 5.0), runs
