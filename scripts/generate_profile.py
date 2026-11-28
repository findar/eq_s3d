r"""Where a generate's time goes (zone-generator-layout-repair task 1).

Each zone runs through ``generate_validated`` as a user's generate does (an unpinned
seed drawn from the job's rng: the quality Draws, the gate, its retries), with timers
wrapped round the pipeline's and the layout's functions from here (no output change;
the one edit in the code is ``DistrictSplitError.reason``). Per generate it records:

- **Draws**: each ``plan_to_spec`` call, timed, with its verdict: built, refused by the
  bands (the out-of-band metrics) or a plan error; and inside each, the layout redraws
  (``_generate_once`` calls that raised ``DistrictSplitError``, with its reason), the
  ``_resolve_conflicts`` passes (time, loop edges dropped) and ``_resolve_crossings``.
- **Build**: ``ZoneBuilder.build``, with geometry (``_build_geometry``) and decor
  (``builder.decor_for``, its RoomContexts inside it).
- **Gate**: ``_traversal_report`` plus ``check_eqg``, and ``_blame`` on a reject (the
  gate run again without Props); each reject's failing rooms, outlines, corridors and
  conflicts, read off the report.
- **Finish**: the accepted build's map files, handoffs, inputs and finalize.
- **Retries**: attempts, and what each rejected attempt cost.

Job sets (``--set``, several allowed):

- ``intrusion24`` / ``sequential24``: the 24-room timing set of district races task 10:
  ``fortress/giant+warren/goblin`` and ``cave/giant+warren/goblin``, classic and graph,
  flat/moderate/dramatic, 5 seeds per cell from rng seed 32 (60 zones each).
- ``sweep31``: every 4th job of the ``--intrusion`` sweep seed 31 (16 and 24 rooms, 10
  seeds per cell; 60 of its 240 zones).
- ``prompt``: "a towering giant fortress the goblins tunnelled into, with 16 rooms" through
  the rule planner and the server's factory, generate rng seeds 2020-2029.
- ``raceless``: 20 zones without a District race: dungeon classic, dungeon graph, cave
  (graph) and city, 5 each, rooms and verticality drawn from rng seed 33.

Rows go to ``--out`` (JSON lines, one per zone, every event kept), and the summary
(median / p90 / max per phase, per set) prints at the end; ``--summary FILE...`` reprints
it from saved rows. Gate failures are classified plan-visible or mesh-only by
:data:`CLASSES` (the 2D check that would see each named).

Usage::

    python scripts/generate_profile.py --set intrusion24 sequential24 --jobs 6 --out output/prof.jsonl
    python scripts/generate_profile.py --summary output/prof.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import statistics
import sys
import tempfile
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PAIRS = ("fortress/giant+warren/goblin", "cave/giant+warren/goblin")
VERTS = ("flat", "moderate", "dramatic")
PROMPT = "a towering giant fortress the goblins tunnelled into, with 16 rooms"

#: Gate failure classes: (regex on the failure text, class, the 2D plan check that sees it,
#: or why only the mesh can). First match wins. "plan" = a check on the laid-out spec could
#: catch it before the mesh; "mesh" = needs the built TER / Props.
CLASSES = [
    (r"conflicts with corridor|^conflict ", "plan",
     "corridor/corridor overlap in XY (the gate's own corridor_conflicts on spec routes)"),
    (r"crosses room", "plan", "corridor route through a third room's box"),
    (r"leaves [\d.]+ u of headroom", "plan", "breach/frame headroom from floor and ceiling heights"),
    (r"leaves [\d.]+ u clear", "plan", "breach/frame clear width against body width"),
    (r"a step of [\d.]+ u through", "plan", "floor heights either side of a breach"),
    (r"drop walks both ways|drop: no fall", "plan", "drop height from the two floors"),
    (r"no floor in (from|to)_room", "mesh", "corridor end lands on no floor (room shape/decor cut)"),
    (r"no floor through the", "mesh", "breach floor missing in the built TER"),
    (r"open seam", "mesh", "wall seam in the built TER"),
    (r"footprint_cut|cuts \d+ u\^?2", "mesh", "a Prop cuts the floor outline (decor)"),
    (r"floor walled off|walled off", "mesh", "floor region cut off in the outline"),
    (r"door .* is blocked|cut off from each other", "mesh", "door blocked (decor/walls)"),
    (r"throat|dais", "mesh", "room-shape throat/dais walk"),
    (r"\bgap\b|without floor|step exceeds", "mesh", "corridor floor continuity on the mesh"),
    (r"nearest walkable surface|unreachable", "mesh", "room not reached on the mesh"),
    (r"^format ", "mesh", "Format_Checker on the archive"),
]


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def _intrusion_plan(cell):
    plan = []
    for part in cell.split("+"):
        purpose, _, race = part.partition("/")
        plan.append({"purpose": purpose, **({"race": race} if race else {})})
    return plan


def _district_controls(cell, layout, v, rooms, relationship):
    c = {"zone_type": "dungeon", "room_count": rooms, "verticality": v, "layout": layout,
         "districts": True, "district_plan": _intrusion_plan(cell)}
    if relationship != "sequential":
        c["district_relationship"] = relationship
    return c


def _sweep_jobs(set_name, rng_seed, rooms, seeds, relationship):
    """The job list ``sweep_themed_navigability --intrusion`` draws (same rng order)."""
    rng = random.Random(rng_seed)
    out = []
    for cell in PAIRS:
        for layout in ("classic", "graph"):
            for v in VERTS:
                for n in rooms:
                    for _ in range(seeds):
                        s = rng.randint(0, 2 ** 31 - 1)
                        out.append({"set": set_name, "kind": "controls", "verticality": v,
                                    "label": f"{cell} {layout} {v} {n}", "seed": s,
                                    "controls": _district_controls(cell, layout, v, n,
                                                                   relationship)})
    return out


def jobs_for(name):
    if name == "intrusion24":
        return _sweep_jobs(name, 32, [24], 5, "intrusion")
    if name == "sequential24":
        return _sweep_jobs(name, 32, [24], 5, "sequential")
    if name == "sweep31":
        return _sweep_jobs(name, 31, [16, 24], 10, "intrusion")[::4]
    if name == "prompt":
        return [{"set": name, "kind": "prompt", "prompt": PROMPT, "seed": s,
                 "label": f"prompt {s}", "verticality": None} for s in range(2020, 2030)]
    if name == "raceless":
        rng = random.Random(33)
        out = []
        for kind in ("classic", "graph", "cave", "city"):
            for _ in range(5):
                n, v = rng.randint(8, 24), rng.choice(VERTS)
                if kind == "city":
                    c = {"zone_type": "city", "room_count": n, "verticality": v}
                elif kind == "cave":
                    c = {"zone_type": "dungeon", "room_count": n, "verticality": v,
                         "layout": "graph", "dungeon_theme": "cave"}
                else:
                    c = {"zone_type": "dungeon", "room_count": n, "verticality": v,
                         "layout": kind}
                out.append({"set": name, "kind": "controls", "controls": c, "verticality": v,
                            "label": f"{kind} {v} {n}", "seed": rng.randint(0, 2 ** 31 - 1)})
        return out
    raise SystemExit(f"unknown set {name}")


# ---------------------------------------------------------------------------
# Hooks (installed once per worker process)
# ---------------------------------------------------------------------------

EV: list = []           # this zone's events, in order
_PLAN: list = []        # the open plan_to_spec call's layout counters (a stack)
_DEPTH = {"return": 0}


def _now():
    return time.perf_counter()


def _wrap(owner, attr, kind, after=None):
    fn = getattr(owner, attr)

    def timed(*a, **kw):
        t0 = _now()
        out, err = None, None
        try:
            out = fn(*a, **kw)
            return out
        except BaseException as e:
            err = e
            raise
        finally:
            ev = {"k": kind, "dt": _now() - t0}
            if after is not None:
                after(ev, a, kw, out, err)
            if ev.get("skip"):
                pass
            elif _PLAN and kind.startswith("lay_"):
                _PLAN[-1].append(ev)
            else:
                EV.append(ev)
    timed.__wrapped__ = fn
    setattr(owner, attr, timed)


def _install():
    import generators.builder as builder
    import generators.layout as layout
    import generators.pipeline as pipeline
    import generators.room_context as room_context

    L = layout.LayoutGenerator

    def once_after(ev, a, kw, out, err):
        if isinstance(err, layout.DistrictSplitError):
            ev["redraw"] = getattr(err, "reason", "") or "unnamed"
    _wrap(L, "_generate_once", "lay_once", once_after)

    def conflicts_before(fn):
        def run(self, rooms, edges, *a, **kw):
            if _DEPTH["return"]:
                return fn(self, rooms, edges, *a, **kw)
            n0, t0 = len(edges), _now()
            try:
                return fn(self, rooms, edges, *a, **kw)
            finally:
                ev = {"k": "lay_conflicts", "dt": _now() - t0, "dropped": n0 - len(edges)}
                (_PLAN[-1] if _PLAN else EV).append(ev)
        return run
    L._resolve_conflicts = conflicts_before(L._resolve_conflicts)

    ret = L._add_return

    def add_return(self, *a, **kw):
        _DEPTH["return"] += 1
        t0 = _now()
        try:
            return ret(self, *a, **kw)
        finally:
            _DEPTH["return"] -= 1
            (_PLAN[-1] if _PLAN else EV).append({"k": "lay_return", "dt": _now() - t0})
    L._add_return = add_return
    _wrap(L, "_resolve_crossings", "lay_crossings")

    def measure_after(ev, a, kw, out, err):
        if out is not None:
            ev["passed"] = bool(out.passed)
            ev["oob"] = [o.metric for o in out.out_of_band]
    _wrap(pipeline, "measure", "measure", measure_after)

    _wrap(builder.ZoneBuilder, "build", "build")
    _wrap(builder.ZoneBuilder, "_build_geometry", "geometry")
    _wrap(builder, "decor_for", "decor")
    _wrap(room_context, "contexts", "contexts")

    def trav_after(ev, a, kw, out, err):
        if out is None:
            return
        fails = [f"{r.room_id}: {r.reason or 'unreachable'}" for r in out.rooms
                 if not r.reachable]
        fails += [f"{o.room_id}: {o.reason}" for o in getattr(out, "outlines", ()) if not o.ok]
        fails += [f"corridor {c.corridor_id}: {c.reason}" for c in out.corridors
                  if not c.connected]
        fails += [f"conflict {a_}/{b_}" for a_, b_ in out.conflicts]
        ev["passed"] = bool(out.passed and out.corridors_passed)
        ev["fails"] = fails
    _wrap(pipeline, "_traversal_report", "gate_trav", trav_after)

    def fmt_after(ev, a, kw, out, err):
        if out is not None:
            ev["passed"] = bool(out.passed)
            ev["fails"] = [f"format {c}" for c in (out.failed_checks or
                                                   ([] if out.passed else ["format"]))]
    _wrap(pipeline, "check_eqg", "gate_fmt", fmt_after)

    def blame_after(ev, a, kw, out, err):
        ev["stage"] = out
    _wrap(pipeline, "_blame", "blame", blame_after)
    _wrap(pipeline, "_write_map_artifacts", "finish_map")
    for name in ("_write_handoffs", "_write_inputs", "_finalize_build"):
        _wrap(pipeline, name, "finish")

    def reject_after(ev, a, kw, out, err):
        ev["checks"] = list(kw.get("checks", ()))
        ev["stage"] = kw.get("stage", "")
        ev["reasons"] = list(out.reasons) if out is not None else []
    _wrap(pipeline, "log_validation_failure", "reject", reject_after)


def _init(eq_path):
    if eq_path:
        os.environ["EQ_PATH"] = eq_path
    _install()


# ---------------------------------------------------------------------------
# One zone
# ---------------------------------------------------------------------------

def run_job(job):
    import dataclasses

    from ai.expand import plan_to_spec
    from ai.rule_planner import RulePlanner
    from ai.schema import ZonePlan
    from generators.builder import with_district_notes
    from generators.outdoor_dungeon import PLAN_ERRORS
    from generators.pipeline import GenerationFailed, generate_validated

    EV.clear()
    if job["kind"] == "prompt":
        plan = RulePlanner().plan(job["prompt"], name="prof")
    else:
        plan = ZonePlan.from_controls(dict(job["controls"]), [])
    plan.name = f"prof_{job['seed']}"
    verticality = job["verticality"]
    zone_type = plan.zone_type

    def factory(s, rooms_seed=None):
        p = plan if rooms_seed is None else dataclasses.replace(plan, rooms_seed=rooms_seed)
        notes: list = []
        _PLAN.append([])
        t0 = _now()
        err = ""
        try:
            return with_district_notes(plan_to_spec(p, seed=s, warnings=notes), notes)
        except PLAN_ERRORS as e:
            err = f"{type(e).__name__}: {e}"[:160]
            raise
        finally:
            inner = _PLAN.pop()
            EV.append({"k": "plan", "dt": _now() - t0, "seed": s, "rooms_seed": rooms_seed,
                       "error": err, "inner": inner})

    row = {k: job[k] for k in ("set", "label", "seed")}
    t0 = _now()
    with tempfile.TemporaryDirectory(prefix="prof", ignore_cleanup_errors=True) as tmp:
        try:
            vb = generate_validated(factory, zone_type=zone_type, zone_id=plan.name,
                                    output_dir=Path(tmp), write_glb=False,
                                    rng=random.Random(job["seed"]), failure_log=None,
                                    verticality=verticality)
            row.update(passed=True, attempts=vb.attempts, built_seed=vb.seed,
                       degraded=bool(vb.quality and vb.quality.degraded))
        except GenerationFailed as e:
            row.update(passed=False, attempts=e.attempts, timed_out=e.timed_out,
                       built_seed=e.failures[-1].seed if e.failures else None)
    row["wall"] = _now() - t0
    row["events"] = list(EV)
    return row


# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------

def classify(text):
    for rx, cls, check in CLASSES:
        if re.search(rx, text):
            return cls, check
    return "unclassified", ""


def phases(row):
    """The row's events as phase totals, its Draw refusals and its rejected attempts."""
    ev = row["events"]
    p = defaultdict(float)
    draws = []                 # one per plan call: (dt, verdict)
    redraws = defaultdict(int)
    attempts = []              # per build: {build, gate, blame, passed, fails}
    for i, e in enumerate(ev):
        k = e["k"]
        if k == "plan":
            p["plan"] += e["dt"]
            for x in e["inner"]:
                if x["k"] == "lay_once" and "redraw" in x:
                    p["layout_redraw"] += x["dt"]
                    redraws[x["redraw"]] += 1
                elif x["k"] == "lay_conflicts":
                    p["conflicts"] += x["dt"]
                    p["conflict_drops"] += x["dropped"]
                elif x["k"] == "lay_crossings":
                    p["crossings"] += x["dt"]
            # The verdict: the next measure (a Draw's) or the build.
            verdict = "plan_error" if e["error"] else "built"
            if not e["error"]:
                nxt = ev[i + 1] if i + 1 < len(ev) else None
                after = ev[i + 2] if i + 2 < len(ev) else None
                if nxt and nxt["k"] == "measure" and not nxt.get("passed", True) and not (
                        after and after["k"] == "build"):
                    verdict = "bands:" + ",".join(nxt.get("oob", []))
            draws.append((e["dt"], verdict, e["error"]))
        elif k == "measure":
            p["measure"] += e["dt"]
        elif k == "build":
            p["build"] += e["dt"]
            attempts.append({"build": e["dt"], "gate": 0.0, "blame": 0.0, "passed": None,
                             "fails": []})
        elif k == "geometry":
            p["geometry"] += e["dt"]
        elif k == "decor":
            p["decor"] += e["dt"]
        elif k == "contexts":
            p["contexts"] += e["dt"]
        elif k in ("gate_trav", "gate_fmt"):
            p["gate"] += e["dt"]
            if attempts:
                a = attempts[-1]
                a["gate"] += e["dt"]
                a["fails"] += e.get("fails", [])
                a["passed"] = (a["passed"] is not False) and e.get("passed", True)
        elif k == "blame":
            p["gate"] += e["dt"]
            p["blame"] += e["dt"]
            if attempts:
                attempts[-1]["blame"] += e["dt"]
                attempts[-1]["stage"] = e.get("stage")
        elif k.startswith("finish"):
            p["finish"] += e["dt"]
            if k == "finish_map":
                p["finish_map"] += e["dt"]
    p["wall"] = row["wall"]
    p["draws"] = len(draws)
    p["attempts"] = row["attempts"]
    p["other"] = row["wall"] - sum(p[x] for x in ("plan", "measure", "build", "gate", "finish"))
    return p, draws, dict(redraws), attempts


def _q(xs, f):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    k = (len(xs) - 1) * f
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


ROWS = [("wall", "Whole generate (s)"), ("plan", "Plan: plan_to_spec, all calls"),
        ("layout_redraw", "  layout redraws (DistrictSplitError)"),
        ("conflicts", "  _resolve_conflicts"), ("crossings", "  _resolve_crossings"),
        ("measure", "Quality measure"), ("build", "Build: ZoneBuilder.build"),
        ("geometry", "  geometry (TER)"), ("decor", "  decor (with contexts)"),
        ("contexts", "    RoomContexts"), ("gate", "Gate: traversal + format + blame"),
        ("blame", "  blame (rejects only)"), ("finish", "Finish: map, inputs, move"),
        ("finish_map", "  map files (_write_map_artifacts)"),
        ("other", "Other"), ("draws", "plan_to_spec calls (count)"),
        ("attempts", "Attempts (builds+plan errors)"),
        ("conflict_drops", "Loop edges dropped by conflicts")]


def summarise(rows):
    out = []
    by_set = defaultdict(list)
    for r in rows:
        by_set[r["set"]].append(r)
    for name, rs in list(by_set.items()) + [("ALL", rows)]:
        ph = [phases(r) for r in rs]
        ok = sum(r["passed"] for r in rs)
        out.append(f"\n== {name}: {len(rs)} zones, {ok} passed ==")
        out.append(f"{'phase':<40}{'median':>9}{'p90':>9}{'max':>9}{'sum':>10}{'share':>8}")
        tot = sum(p["wall"] for p, *_ in ph)
        for key, label in ROWS:
            vals = [p[key] for p, *_ in ph]
            share = f"{sum(vals) / tot:7.1%}" if key not in (
                "draws", "attempts", "conflict_drops", "wall") else ""
            out.append(f"{label:<40}{_q(vals, .5):9.2f}{_q(vals, .9):9.2f}{max(vals):9.2f}"
                       f"{sum(vals):10.1f}{share:>8}")
        # Draw verdicts and refusals.
        verdicts = defaultdict(lambda: [0, 0.0])
        red = defaultdict(int)
        for p, draws, redraws, _ in ph:
            for dt, v, _err in draws:
                key = v if not v.startswith("bands:") else "bands"
                verdicts[key][0] += 1
                verdicts[key][1] += dt
            for k, n in redraws.items():
                red[k] += n
        out.append("plan_to_spec verdicts: " + ", ".join(
            f"{k} {n} ({t:.0f} s)" for k, (n, t) in sorted(verdicts.items())))
        oob = defaultdict(int)
        for p, draws, *_ in ph:
            for _dt, v, _e in draws:
                if v.startswith("bands:"):
                    for m in v[6:].split(","):
                        oob[m] += 1
        if oob:
            out.append("  band metrics out: " + ", ".join(
                f"{k} {n}" for k, n in sorted(oob.items(), key=lambda kv: -kv[1])))
        if red:
            out.append("layout redraws by reason: " + ", ".join(
                f"{k} {n}" for k, n in sorted(red.items(), key=lambda kv: -kv[1])))
        # Rejected builds, classified.
        cls_t = defaultdict(float)
        cls_n = defaultdict(int)
        lines = []
        for r, (p, draws, redraws, atts) in zip(rs, ph):
            for a in atts:
                if a["passed"] is not False:
                    continue
                cost = a["build"] + a["gate"] + a["blame"]
                kinds = [classify(f) for f in a["fails"]] or [("unclassified", "")]
                # A reject is plan-visible only when every failure in it is.
                cls = "plan" if all(c == "plan" for c, _ in kinds) else (
                    "mesh" if all(c in ("plan", "mesh") for c, _ in kinds) else "unclassified")
                cls_t[cls] += cost
                cls_n[cls] += 1
                lines.append(f"  [{cls}] {r['label']} s{r['seed']} {cost:.1f} s: "
                             + " | ".join(a["fails"])[:300])
        if lines:
            out.append(f"rejected builds: {sum(cls_n.values())}, "
                       + ", ".join(f"{c} {cls_n[c]} ({cls_t[c]:.0f} s, {cls_t[c] / tot:.1%})"
                                   for c in sorted(cls_n)))
            out.extend(lines)
        failed = [r for r in rs if not r["passed"]]
        for r in failed:
            out.append(f"  GENERATE FAILED {r['label']} s{r['seed']} attempts {r['attempts']} "
                       f"timed_out {r.get('timed_out')}")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--set", nargs="+", default=[], help="job sets (see the module doc)")
    ap.add_argument("--jobs", type=int, default=6, help="worker processes")
    ap.add_argument("--out", default="output/generate_profile.jsonl", help="JSON lines rows")
    ap.add_argument("--limit", type=int, default=0, help="first N jobs of each set (testing)")
    ap.add_argument("--summary", nargs="*", default=None, help="reprint from saved rows")
    args = ap.parse_args(argv)
    if args.summary is not None:
        rows = [json.loads(line) for f in args.summary
                for line in Path(f).read_text(encoding="utf-8").splitlines() if line.strip()]
        print(summarise(rows))
        return 0
    jobs = []
    for name in args.set:
        js = jobs_for(name)
        jobs += js[:args.limit] if args.limit else js
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    eq = os.environ.get("EQ_PATH", "")
    with out.open("a", encoding="utf-8") as fh, ProcessPoolExecutor(
            args.jobs, initializer=_init, initargs=(eq,)) as ex:
        for row in ex.map(run_job, jobs, chunksize=1):
            rows.append(row)
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            print(f"  {'OK  ' if row['passed'] else 'FAIL'} {row['set']:<12} {row['label']:<44} "
                  f"s{row['seed']:<11} {row['wall']:7.1f} s  attempts {row['attempts']}",
                  flush=True)
    print(summarise(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
