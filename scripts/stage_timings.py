r"""Time each stage of a zone build, cold and warm (step 12, task 1).

For each zone type (dungeon, city, wilderness, outdoor dungeon) and pinned seed, one
zone is planned, built and gated as the pipeline does (``generate_validated``: the
default Decor control, no GLB, the traversal report and the Format_Checker), and the
time spent in each stage is recorded. Rows are named by the stage each piece of
today's code becomes in step 12, so the same script reads the new stages later:

- **World**: the landscape synth (``wilderness.build._landscape``: matrix, rewrite,
  synth, bowl), wherever it runs first (inside the plan today).
- **Plan**: ``plan_to_spec``, less the World inside it (room layout, the outdoor
  dungeon's host TER and Envelope).
- **Geometry**: ``ZoneBuilder._build_geometry`` (the TER; an outdoor dungeon builds
  its host TER again here).
- **Sites**, **Trees**: ``sites_for``, ``vegetation_for`` (wilderness types only).
- **RoomContexts**: ``room_context.contexts`` and ``site_contexts``.
- **Decor**: ``builder.decor_for`` less its RoomContexts (placement, model import;
  cold, also loading the catalogue).
- **Pack**: ``EqgZone.write`` (the PFS archive).
- **Rest of build**: ``ZoneBuilder.build`` less the above (textures, ZON, sidecar).
- **Gate**: ``pipeline._traversal_report`` plus ``check_eqg``.

Each zone type runs in a fresh Python process. **Cold** is the first seed there,
with imports, the decor catalogue and the stock model importer all loading for the
first time (the module import itself is its own row). **Warm** builds every seed
again in that process after clearing the per-seed caches (landscape, Sites, trees),
so only process-wide state (imports, catalogue, imported models) carries over; it
shows the median and the max over the seeds.

Decor needs the install (``EQ_PATH`` or ``--eq-path``); without it the Decor control
falls back to none with a warning, and the Decor rows read 0.

Usage::

    python scripts/stage_timings.py --seeds 1-5
    python scripts/stage_timings.py --seeds 7 --types dungeon,outdoor_dungeon --decor none
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ZONE_TYPES = ("dungeon", "city", "wilderness", "outdoor_dungeon")

#: Table rows, in pipeline order.
ROWS = ("import", "world", "plan", "geometry", "sites", "trees", "room_contexts",
        "decor", "pack", "rest", "gate", "total")
LABELS = {
    "import": "Imports (cold only)",
    "world": "World (landscape synth)",
    "plan": "Plan (plan_to_spec less World)",
    "geometry": "Build: geometry (TER)",
    "sites": "Build: Sites",
    "trees": "Build: trees",
    "room_contexts": "Build: RoomContexts",
    "decor": "Build: decor (less contexts)",
    "pack": "Build: pack (.eqg)",
    "rest": "Build: rest (textures, ZON, sidecar)",
    "gate": "Gate (traversal + format)",
    "total": "Total (plan + build + gate)",
}


def parse_seeds(text: str) -> list:
    """``"1-5"`` -> [1..5]; ``"3,7,9-10"`` -> [3, 7, 9, 10]."""
    out = []
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    if not out:
        raise argparse.ArgumentTypeError("no seeds")
    return out


# ---------------------------------------------------------------------------
# Worker: one zone type in its own process
# ---------------------------------------------------------------------------

class _Clock:
    """Accumulates wall time per stage while armed. Nested stages are subtracted
    from their parent by the caller (decor less contexts, plan less world)."""

    def __init__(self):
        self.t = {}
        self.armed = False

    def wrap(self, key, fn):
        def timed(*a, **kw):
            if not self.armed:
                return fn(*a, **kw)
            t0 = time.perf_counter()
            try:
                return fn(*a, **kw)
            finally:
                self.t[key] = self.t.get(key, 0.0) + time.perf_counter() - t0
        timed.__wrapped__ = fn
        return timed


def _worker(zone_type: str, seeds: list, decor: str) -> dict:
    t0 = time.perf_counter()
    sys.path.insert(0, str(ROOT))
    import generators.builder as builder
    import generators.room_context as room_context
    import generators.wilderness.build as wbuild
    from ai.expand import plan_to_spec
    from ai.schema import ZonePlan
    from analyzer.rof2check import check_eqg
    from core.eqg import EqgZone
    from generators.outdoor_dungeon import PLAN_ERRORS
    from generators.pipeline import _traversal_report, _with_decor
    imports = time.perf_counter() - t0

    clock = _Clock()
    land_cached = wbuild._landscape                   # the lru_cache, for cache_clear
    wbuild._landscape = clock.wrap("world", land_cached)
    wbuild.sites_for = clock.wrap("sites", wbuild.sites_for)
    wbuild.vegetation_for = clock.wrap("trees", wbuild.vegetation_for)
    room_context.contexts = clock.wrap("room_contexts", room_context.contexts)
    room_context.site_contexts = clock.wrap("room_contexts", room_context.site_contexts)
    builder.decor_for = clock.wrap("decor", builder.decor_for)
    builder.ZoneBuilder._build_geometry = clock.wrap(
        "geometry", builder.ZoneBuilder._build_geometry)
    EqgZone.write = clock.wrap("pack", EqgZone.write)

    def clear_seed_caches():
        land_cached.cache_clear()
        wbuild._sites.cache_clear()
        wbuild._vegetation.cache_clear()

    def one(seed: int) -> dict:
        clock.t = {}
        clock.armed = True
        t = time.perf_counter()
        plan = ZonePlan(name=f"t{seed}", zone_type=zone_type)
        try:
            spec = plan_to_spec(plan.validate(), seed=seed)
        except PLAN_ERRORS as e:
            clock.armed = False
            return {"seed": seed, "error": f"plan: {type(e).__name__}"}
        plan_t = time.perf_counter() - t
        if decor:
            spec.decor = decor
        spec = _with_decor(spec)
        with tempfile.TemporaryDirectory() as tmp:
            t = time.perf_counter()
            r = builder.ZoneBuilder(spec).build(output_dir=Path(tmp), write_glb=False)
            build_t = time.perf_counter() - t
            clock.armed = False                       # the gate re-reads cached stages
            t = time.perf_counter()
            report = _traversal_report(r.eqg_path, spec, None)
            fmt = check_eqg(r.eqg_path, spec, sidecar_path=r.sidecar_path)
            gate_t = time.perf_counter() - t
        s = dict(clock.t)
        row = {k: s.get(k, 0.0) for k in ("world", "geometry", "sites", "trees",
                                         "room_contexts", "pack")}
        # World runs inside the plan today; contexts run inside decor.
        row["plan"] = plan_t - row["world"]
        row["decor"] = s.get("decor", 0.0) - row["room_contexts"]
        row["rest"] = build_t - sum(s.get(k, 0.0) for k in
                                    ("geometry", "sites", "trees", "decor", "pack"))
        row["gate"] = gate_t
        row["total"] = plan_t + build_t + gate_t
        row["seed"] = seed
        row["passed"] = bool(report.passed and report.corridors_passed and fmt.passed)
        return row

    cold = one(seeds[0])
    cold["import"] = imports
    warm = []
    for seed in seeds:
        clear_seed_caches()
        warm.append(one(seed))
    return {"zone_type": zone_type, "cold": cold, "warm": warm}


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def _run_type(zone_type: str, seeds: list, decor: str, env: dict) -> dict:
    cmd = [sys.executable, str(Path(__file__).resolve()), "--worker", zone_type,
           "--seeds", ",".join(map(str, seeds))]
    if decor:
        cmd += ["--decor", decor]
    p = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(ROOT))
    if p.returncode != 0:
        raise SystemExit(f"{zone_type} worker failed:\n{p.stderr[-3000:]}")
    return json.loads(p.stdout.strip().splitlines()[-1])


def _fmt(v) -> str:
    return "-" if v is None else f"{v:6.2f}"


def render(results: list, seeds: list) -> str:
    head = ["Stage (s)".ljust(38)]
    sub = ["".ljust(38)]
    for r in results:
        name = r["zone_type"]
        head.append(name.center(22))
        sub.append(f"{'cold':>6} {'p50':>7} {'max':>7}")
    lines = [" | ".join(head), " | ".join(sub), "-" * (41 + 25 * len(results))]
    for key in ROWS:
        cells = [LABELS[key].ljust(38)]
        for r in results:
            ok = [w for w in r["warm"] if "error" not in w]
            cold = r["cold"].get(key) if "error" not in r["cold"] else None
            vals = [w[key] for w in ok if key in w]
            p50 = statistics.median(vals) if vals else None
            mx = max(vals) if vals else None
            cells.append(f"{_fmt(cold)} {_fmt(p50):>7} {_fmt(mx):>7}")
        lines.append(" | ".join(cells))
    lines.append("")
    for r in results:
        notes = []
        for w in r["warm"]:
            if "error" in w:
                notes.append(f"seed {w['seed']}: {w['error']}")
            elif not w["passed"]:
                notes.append(f"seed {w['seed']}: gate failed")
        if "error" in r["cold"]:
            notes.append(f"cold seed {r['cold']['seed']}: {r['cold']['error']}")
        if notes:
            lines.append(f"{r['zone_type']}: " + "; ".join(notes))
    lines.append(f"seeds {seeds}; warm = median / max over the seeds, per-seed caches "
                 f"cleared; cold = seed {seeds[0]} in a fresh process.")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=parse_seeds, default=parse_seeds("1-5"),
                    help="pinned seeds, e.g. 1-5 or 3,7,9 (default 1-5)")
    ap.add_argument("--types", default=",".join(ZONE_TYPES),
                    help="comma-separated zone types (default: all four)")
    ap.add_argument("--decor", default="",
                    help="Decor control (default: the pipeline's default)")
    ap.add_argument("--eq-path", default=None,
                    help="EverQuest install for Decor (default: $EQ_PATH)")
    ap.add_argument("--json", action="store_true", help="print the raw numbers as JSON")
    ap.add_argument("--worker", default=None, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)

    if a.worker:
        print(json.dumps(_worker(a.worker, a.seeds, a.decor)))
        return 0

    types = [t.strip() for t in a.types.split(",") if t.strip()]
    bad = [t for t in types if t not in ZONE_TYPES]
    if bad:
        ap.error(f"unknown zone type(s) {bad}; expected {', '.join(ZONE_TYPES)}")
    env = dict(os.environ)
    if a.eq_path:
        env["EQ_PATH"] = a.eq_path
    if not env.get("EQ_PATH"):
        print("note: no EQ_PATH; Decor falls back to none", file=sys.stderr)
    results = [_run_type(t, a.seeds, a.decor, env) for t in types]
    print(json.dumps(results, indent=1) if a.json else render(results, a.seeds))
    return 0


if __name__ == "__main__":
    sys.exit(main())
