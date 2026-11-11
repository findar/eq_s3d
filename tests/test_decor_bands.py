"""Room-decor task 14: the gate sweep and the stock bands (Reqs 12.1, 12.2's first-try
rate, 12.4; design P12).

P12: over many seeds at Normal, built dungeons and cities measure inside design finding 1's
bands, by the survey's own code. Each zone is built, its ``.eqg`` read back (the TER, and the
ZON's ``decor_`` objects with their sidecar rows for the catalogue key), and measured by
``decor_survey.measure_zone`` exactly as the survey measures a stock zone: its chamber split
makes the rooms, ``category`` names the Category from the model's name, ``surroundings``
reads the Mount from the mesh. Nothing here re-implements a measure.

Which band. Finding 1 says "Task 14's bands are the dungeon and city p25-p75, by zone type,
with the min-max as the hard edge". One built zone holds five rooms, so one zone's value is
coarse; the sweep's median zone must sit in the p25-p75 band, and every zone's Props per room
inside the min-max (the finding gives min-max for that measure only). The Structure share is
printed, not asserted: decor places no Structure (finding 1: step 9's Features are the
pillars and plinths; ladders and cages are out of the Req intro), so it reads 0 against
stock's 0.01-0.04.

The gate's first-try rate (the pipeline's PASS: traversal, corridors, outlines and the
Format_Checker) holds at Normal against Decor ``none`` on the same seeds, and a build stays
within step 10's time (Decor ``none``) plus 5 s.

Built ``.eqg`` files hold the client's art: they live in a temporary folder only. The tests
need the install (``EQ_PATH``) and skip without it.
"""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import time
from functools import lru_cache
from pathlib import Path
from statistics import median

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from ai.expand import plan_to_spec  # noqa: E402
from ai.schema import ZonePlan  # noqa: E402
from analyzer.rof2check import check_eqg  # noqa: E402
from analyzer.traverse import AgentModel  # noqa: E402
from core.pfs import PfsArchive  # noqa: E402
from core.zon import ZonFile  # noqa: E402
from generators.builder import ZoneBuilder  # noqa: E402
from generators.decor.stock import eq_path_from_env  # noqa: E402
from generators.pipeline import _traversal_report, load_ter_from_eqg  # noqa: E402
import decor_survey as ds  # noqa: E402

EQ = eq_path_from_env()
needs_install = pytest.mark.skipif(EQ is None, reason="EQ_PATH is not set (no EQ install to read)")

SEEDS = range(40)

#: Finding 1's bands by zone type: p25-p75 over the 15 stock zones of each.
BANDS = {
    "dungeon": {
        "per_room_mean": (2.9, 6.8),
        "category": {"light": (.21, .45), "container": (.03, .11), "furniture": (.09, .15),
                     "hanging": (0.0, .04), "debris": (.20, .56), "plant": (0.0, 0.0),
                     "other": (0.0, .03)},
        "mount": {"floor": (.51, .66), "wall": (.26, .38), "ceiling": (0.0, .09),
                  "raised": (.04, .07)},
    },
    "city": {
        "per_room_mean": (4.0, 12.5),
        "category": {"light": (.24, .45), "container": (.10, .15), "furniture": (.23, .34),
                     "hanging": (0.0, .02), "debris": (0.0, .07), "plant": (0.0, .08),
                     "other": (0.0, .02)},
        "mount": {"floor": (.65, .77), "wall": (.18, .31), "ceiling": (0.0, .02),
                  "raised": (.03, .05)},
    },
}
#: The hard edge: min-max over the stock zones (Props per room, mean).
HARD_PER_ROOM = {"dungeon": (0.9, 11.5), "city": (1.9, 17.4)}

#: Timed builds: the pinned seeds of tests/test_decor_builds.py.
TIMED = {"dungeon": 4, "city": 5}


def _spec(zone_type: str, seed: int, decor: str):
    spec = plan_to_spec(ZonePlan(name=f"b{seed}", zone_type=zone_type).validate(), seed=seed)
    spec.decor = decor
    return spec


@lru_cache(maxsize=None)
def _catalogue() -> dict:
    return json.loads((ROOT / "rules" / "decor" / "catalogue.json").read_text(encoding="utf-8"))["models"]


def _read_back(eqg: Path, side: dict):
    """(TER, [Placed], [size]) of a built zone: the ZON's ``decor_`` objects, each with its
    sidecar row's catalogue key (rooms first, then Sites, as the ZON lists them)."""
    arc = PfsArchive.from_file(eqg)
    zon = ZonFile.from_bytes(arc.get(next(f for f in arc.list_files() if f.lower().endswith(".zon"))))
    rows = ([p for r in side["rooms"] for p in r.get("props", [])]
            + [p for s in side.get("sites", {}).get("sites", []) for p in s.get("props", [])])
    objs = [o for o in zon.objects if o.name.startswith("decor_")]
    assert len(objs) == len(rows)
    cat = _catalogue()
    placed = [ds.Placed(o.x, o.y, o.z, math.degrees(o.yaw), o.scale, cat[p["key"]]["name"])
              for o, p in zip(objs, rows)]
    sizes = [ds.size_of(cat[p["key"]]) for p in rows]
    ter, _ = load_ter_from_eqg(eqg)
    return ter, placed, sizes


@lru_cache(maxsize=None)
def _zone(zone_type: str, seed: int, decor: str) -> dict:
    """Build, gate as the pipeline does, and (with Decor) measure by the survey's code."""
    spec = _spec(zone_type, seed, decor)
    with tempfile.TemporaryDirectory() as tmp:
        r = ZoneBuilder(spec).build(output_dir=Path(tmp), write_glb=False)
        report = _traversal_report(r.eqg_path, spec, None)
        fmt = check_eqg(r.eqg_path, spec, sidecar_path=r.sidecar_path)
        gate = (report.passed and report.corridors_passed and fmt.passed
                and all(o.ok for o in getattr(report, "outlines", ())))
        if decor == "none":
            return {"gate": gate}
        side = json.loads(r.sidecar_path.read_text(encoding="utf-8"))
        ter, placed, sizes = _read_back(r.eqg_path, side)
    m = ds.measure_zone(ter, AgentModel(), placed, sizes, floors_up=True, city=zone_type == "city")
    return {"gate": gate, "m": m, "props": len(placed)}


@needs_install
def test_a_build_reads_back_through_the_survey():
    """The fast check: a Normal dungeon's Props all reach the survey, on the walked floor,
    with a known size and a Mount read from the mesh."""
    z = _zone("dungeon", 0, "normal")
    m = z["m"]
    assert z["props"] > 0 and m["objects"] == z["props"]
    assert m["off_floor"] <= 0.1, m["off_floor"]
    assert m["rooms"] >= 1 and m["in_room"] > 0.5
    assert set(m["_sur"]["mount"]) <= set(ds.MOUNTS)


def _q(v) -> str:
    return (f"p25 {np.percentile(v, 25):.2f} med {median(v):.2f} p75 {np.percentile(v, 75):.2f} "
            f"(min {min(v):.2f}, max {max(v):.2f})")


@pytest.mark.slow
@needs_install
@pytest.mark.parametrize("zone_type", sorted(BANDS))
def test_p12_normal_rooms_measure_inside_the_stock_bands(zone_type):
    zs = [_zone(zone_type, s, "normal")["m"] for s in SEEDS]
    band = BANDS[zone_type]
    lines, bad = [], []

    def check(name, values, lo_hi):
        lo, hi = lo_hi
        med = median(values)
        lines.append(f"  {name:20} {_q(values)}  band {lo:.2f}-{hi:.2f}")
        if not lo <= round(med, 2) <= hi:
            bad.append(f"{name} median {med:.3f} outside {lo}-{hi}")

    per_room = [m["per_room_mean"] for m in zs]
    check("per room, mean", per_room, band["per_room_mean"])
    lo, hi = HARD_PER_ROOM[zone_type]
    out = [(s, round(v, 2)) for s, v in zip(SEEDS, per_room) if not lo <= v <= hi]
    if out:
        bad.append(f"per room, mean outside the hard edge {lo}-{hi} on seeds {out}")
    for k, lo_hi in band["category"].items():
        check(f"category {k}", [m["category"][k] for m in zs], lo_hi)
    for k, lo_hi in band["mount"].items():
        check(f"mount {k}", [m["mount"][k] for m in zs], lo_hi)
    structure = [m["category"]["structure"] for m in zs]
    print(f"\n{zone_type} Normal, seeds {SEEDS.start}-{SEEDS.stop - 1} "
          f"({sum(m['objects'] for m in zs)} Props, split rooms median "
          f"{median(m['rooms'] for m in zs)}, in rooms {_q([m['in_room'] for m in zs])}):\n"
          + "\n".join(lines) + f"\n  category structure   {_q(structure)}  (not asserted)")
    assert not bad, bad


@pytest.mark.slow
@needs_install
@pytest.mark.parametrize("zone_type", sorted(BANDS))
def test_gate_first_try_rate_holds(zone_type):
    """Req 12.2: at Normal the gate passes first try at least as often as Decor ``none``
    on the same seeds."""
    passed = {d: [s for s in SEEDS if _zone(zone_type, s, d)["gate"]] for d in ("none", "normal")}
    print(f"\n{zone_type} first try, seeds {SEEDS.start}-{SEEDS.stop - 1}: "
          + ", ".join(f"{d} {len(p)}/{len(SEEDS)}" for d, p in passed.items()))
    assert len(passed["normal"]) >= len(passed["none"]), sorted(set(passed["none"]) - set(passed["normal"]))


def _timed(zone_type: str, decor: str, out: Path) -> float:
    """A build (EQG and GLB) in CPU time."""
    spec = _spec(zone_type, TIMED[zone_type], decor)
    t0 = time.process_time()
    ZoneBuilder(spec).build(output_dir=out, write_glb=True)
    return time.process_time() - t0


@pytest.mark.slow
@needs_install
@pytest.mark.parametrize("zone_type", sorted(TIMED))
def test_p12_decor_costs_at_most_5_s(tmp_path, zone_type):
    """Req 12.4: Normal against ``none`` on the same seed, best of three each in CPU time.
    The bar doubles under the parallel suite, as in test_site_bands."""
    runs = {"none": [], "normal": []}
    for k in range(3):
        for d in runs:
            runs[d].append(_timed(zone_type, d, tmp_path / f"{d}{k}"))
    none, normal = min(runs["none"]), min(runs["normal"])
    print(f"\n{zone_type} {TIMED[zone_type]}: none {none:.2f} s, normal {normal:.2f} s "
          f"(first normal {runs['normal'][0]:.2f} s)")
    assert normal <= none + (10.0 if os.environ.get("PYTEST_XDIST_WORKER") else 5.0), runs
