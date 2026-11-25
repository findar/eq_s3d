"""How short can a cave Graph corridor be before a reader fails? (cave clumps step 29, task 2)

Builds cave Graph zones (Dungeon, Graph layout, Cave theme, as ``grid_score.py --kinds cave``
draws them: ``ZonePlan.from_controls`` then ``plan_to_spec``) through the gate
(``generate_validated`` on a pinned seed: one build, traversability + corridor continuity +
the Format_Checker, then the map files), with a share of edges forced short. Seeds 2000-2009,
10-16 rooms (10 + i % 7), flat and moderate verticality.

The forcing is monkeypatched from here; no generator code changes:

- ``embed._jitter_table``: of the edges that take a jitter (never a stair, a Bridge or an
  edge across Levels), a third, chosen by a hash of the seed and the two room ids, get a
  spacing that rests their facing walls ``LEN`` u apart (spacing ``LEN`` / run) and no
  bearing (the far room straight off the wall, so the doors line up).
- ``embed.spring_relax``: the forced pairs don't repel (their spring alone holds them).
- ``embed.layout_clashes``: a forced pair closer than the separation gap is no clash.
- ``LayoutGenerator._separate_rooms``: first squares each forced pair up (the room
  straight off its parent's wall in a tree of forced pairs, centred across it, ``LEN`` u
  away, so its doors line up; ``--no-snap``
  leaves them where the springs put them, mostly corner to corner), then keeps a forced pair
  ``LEN`` u apart, not a corridor width plus 1 (every other pair as before).

``LEN`` is the wall-to-wall gap asked for; the probe prints what the built corridors
measure door to door (their ``path``, else their route, as ``grid_score.py`` reads it).
``w`` is one corridor width (the build's ``corridor_width``); ``off`` forces nothing (the
baseline). Per length it prints: builds passing the gate, the forced edges built as
corridors (of those forced), their door-to-door and wall-to-wall gap p0/p50/p100, the share
of them built straight (doors lined up: door to door within ``STRAIGHT_TOL`` of the gap
plus both doors' insets; the rest jog sideways in the gap), forced pairs on different
floors, forced corridors whose Transition gave way (``asked`` != ``form``), new warnings
(map files, outline), failing builds whose failure (a point the gate names) is within ``NEAR`` u of a straight
forced corridor's door (``stF``) or only a jogged one's (``jgF``), or that the gate blames on
Decor (``dcF``), and
the first failing check (or the crash, with the generator file
and function it came from) with its seed.

Usage (from the repo root, ``EQ_PATH`` set to the RoF2 install)::

    python scripts/throat_probe.py [--lengths off 0 4 8 16 24 w] [--seeds 10]
                                   [--verts flat moderate] [--jobs 4] [--json out.json]
                                   [--no-snap]
    python scripts/throat_probe.py --summary out.json     # the table again, no builds
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import sys
import tempfile
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

FIRST_SEED = 2000
SHARE = 1.0 / 3.0
DOOR_INSET = 2.0    # each door stands this far inside its wall (layout's _wall_point)
NEAR = 30.0         # a failure this near a forced corridor's door is that corridor's
STRAIGHT_TOL = 1.0  # a corridor is straight when door to door is within this of gap + 2 insets


def _straight(c) -> bool:
    """Do the forced corridor's doors line up (no jog between them)?"""
    return c["d2d"] <= c["gap"] + 2 * DOOR_INSET + STRAIGHT_TOL
LENGTHS = ["off", "0", "4", "8", "16", "24", "w"]

# The forcing, per build (one build at a time per process).
_F = {"length": None, "seed": None, "nodes": {}, "rooms": {}, "order": None, "snap": True}


def _forced(seed, a: str, b: str) -> bool:
    lo, hi = sorted((a, b))
    h = hashlib.blake2b(f"throat:{seed}|{lo}|{hi}".encode(), digest_size=4).digest()
    return int.from_bytes(h, "little") / 2 ** 32 < SHARE


def _gap_of(length: str, width: float) -> float:
    return width if length == "w" else float(length)


def install(length: str) -> None:
    """Monkeypatch the placement and separation to force ``length`` (see the module doc)."""
    from generators import layout as layout_mod
    from generators.topology import embed

    _F["length"] = length
    if length == "off":
        return
    orig_table, orig_relax = embed._jitter_table, embed.spring_relax
    orig_overlap, orig_clashes = embed._overlap_matrix, embed.layout_clashes
    orig_sep = layout_mod.LayoutGenerator._separate_rooms

    def jitter_table(graph, order, half, storeys, seed, corridor_width, *a, **k):
        table = orig_table(graph, order, half, storeys, seed, corridor_width, *a, **k)
        _F["nodes"], _F["rooms"] = {}, {}
        if table is None:
            return table
        gap = _gap_of(length, corridor_width)
        run = embed.RUN_FACTOR * corridor_width
        # (the run ``spring`` uses: its run_factor reaches here only through the caller)
        run = _F.get("run", run)
        idx = {r: i for i, r in enumerate(order)}
        for e, (f, t) in list(table.edges.items()):
            a_, b_ = sorted(e)
            if not _forced(_F["seed"], a_, b_):
                continue
            table.edges[e] = (gap / run, 0.0)
            _F["nodes"][e] = gap
            _F["rooms"][frozenset((f"room_{idx[a_]}", f"room_{idx[b_]}"))] = gap
        return table

    def spring(graph, order, half, corridor_width, gap, storeys=None, run_factor=None,
               **k):
        _F["run"] = (embed.RUN_FACTOR if run_factor is None else run_factor) * corridor_width
        return orig_spring(graph, order, half, corridor_width, gap, storeys=storeys,
                           run_factor=run_factor, **k)

    def spring_relax(order, *a, **k):
        _F["order"] = list(order)
        try:
            return orig_relax(order, *a, **k)
        finally:
            _F["order"] = None

    def overlap_matrix(rooms, slab=embed.SLAB):
        out = orig_overlap(rooms, slab)
        order = _F["order"]
        if order is not None and len(rooms) == len(order) and _F["nodes"]:
            idx = {r: i for i, r in enumerate(order)}
            for e in _F["nodes"]:
                a_, b_ = tuple(e)
                if a_ in idx and b_ in idx:
                    out[idx[a_], idx[b_]] = out[idx[b_], idx[a_]] = True
        return out

    def layout_clashes(graph, order, pos, half, gap, storeys=None):
        bad = orig_clashes(graph, order, pos, half, gap, storeys)
        keys = embed._plan_keys(graph, order, storeys)
        for e in _F["nodes"]:
            a_, b_ = tuple(e)
            if (a_ in pos and b_ in pos and not embed.may_overlap_in_plan(keys[a_], keys[b_])
                    and embed._box_gap(pos[a_], half[a_], pos[b_], half[b_]) < gap - 1e-6):
                bad -= 1
        return bad

    def separate(self, rooms, iterations=None, storeys=None):
        forced = _F["rooms"]
        if not forced or not self.corridor_clearance:
            return orig_sep(self, rooms, iterations=iterations, storeys=storeys)
        stacked = None
        if storeys is not None:
            stacked = {(a, b) for a in range(len(rooms)) for b in range(a + 1, len(rooms))
                       if embed.may_overlap_in_plan(storeys[a], storeys[b])}
        base = self.corridor_width + 1.0
        if _F["snap"]:
            _snap(rooms, forced)
        for _ in range(iterations or 200):
            moved = False
            for a in range(len(rooms)):
                for b in range(a + 1, len(rooms)):
                    if stacked and (a, b) in stacked:
                        continue
                    ra, rb = rooms[a], rooms[b]
                    gap = forced.get(frozenset((ra.id, rb.id)), base)
                    ox = (ra.width + rb.width) / 2 + gap - abs(rb.center_x - ra.center_x)
                    oy = (ra.depth + rb.depth) / 2 + gap - abs(rb.center_y - ra.center_y)
                    if ox > 1e-9 and oy > 1e-9:
                        dx, dy = rb.center_x - ra.center_x, rb.center_y - ra.center_y
                        if ox < oy:
                            push = ox / 2 * (1 if dx >= 0 else -1)
                            ra.center_x -= push
                            rb.center_x += push
                        else:
                            push = oy / 2 * (1 if dy >= 0 else -1)
                            ra.center_y -= push
                            rb.center_y += push
                        moved = True
            if not moved:
                break

    orig_spring = embed.spring
    embed._jitter_table = jitter_table
    embed.spring = spring
    embed.PLACEMENT_FUNCS["spring"] = spring
    embed.spring_relax = spring_relax
    embed._overlap_matrix = overlap_matrix
    embed.layout_clashes = layout_clashes
    layout_mod.LayoutGenerator._separate_rooms = separate


def _snap(rooms, forced) -> None:
    """Square each forced pair up: over each tree of forced pairs, from its lowest room
    breadth first, a room straight off its parent's wall (centred across it) at the forced
    gap, on the axis they're most apart on. A forced pair closing a loop stays as placed."""
    by = {r.id: r for r in rooms}
    num = lambda i: int(i.split("_")[1])     # noqa: E731
    nbrs = {}
    for pair in forced:
        a, b = tuple(pair)
        if a in by and b in by:
            nbrs.setdefault(a, set()).add(b)
            nbrs.setdefault(b, set()).add(a)
    done = set()
    for root in sorted(nbrs, key=num):
        if root in done:
            continue
        done.add(root)
        queue = [root]
        while queue:
            a = queue.pop(0)
            for b in sorted(nbrs[a], key=num):
                if b in done:
                    continue
                done.add(b)
                queue.append(b)
                ra, rb, g = by[a], by[b], forced[frozenset((a, b))]
                gx = abs(rb.center_x - ra.center_x) - (ra.width + rb.width) / 2
                gy = abs(rb.center_y - ra.center_y) - (ra.depth + rb.depth) / 2
                if gx >= gy:
                    sx = 1.0 if rb.center_x >= ra.center_x else -1.0
                    rb.center_x = ra.center_x + sx * ((ra.width + rb.width) / 2 + g)
                    rb.center_y = ra.center_y
                else:
                    sy = 1.0 if rb.center_y >= ra.center_y else -1.0
                    rb.center_y = ra.center_y + sy * ((ra.depth + rb.depth) / 2 + g)
                    rb.center_x = ra.center_x


def _d2d(cor, by) -> float:
    from generators.routing import corridor_route
    line = cor.path or list(corridor_route(cor, by).waypoints)
    return sum(math.dist(a[:2], b[:2]) for a, b in zip(line, line[1:]))


def _box_gap(a, b) -> float:
    gx = abs(b.center_x - a.center_x) - (a.width + b.width) / 2
    gy = abs(b.center_y - a.center_y) - (a.depth + b.depth) / 2
    return max(gx, gy)


def _where(exc: BaseException) -> str:
    """The innermost generators/ (or core/, analyzer/, ai/) frame of a crash."""
    tb = traceback.extract_tb(exc.__traceback__)
    for fr in reversed(tb):
        p = Path(fr.filename)
        if any(part in ("generators", "core", "analyzer", "ai") for part in p.parts):
            rel = p.relative_to(ROOT) if ROOT in p.parents else p
            return f"{rel.as_posix()}:{fr.name}:{fr.lineno}"
    return tb[-1].name if tb else "?"


def one(job) -> dict:
    length, seed, rooms, vert = job
    os.chdir(ROOT)
    import random

    from ai.expand import plan_to_spec
    from ai.schema import ZonePlan
    from generators.pipeline import GenerationFailed, generate_validated

    if _F["length"] != length:
        if _F["length"] is not None:
            raise RuntimeError("one length per process")
        install(length)
    _F["seed"] = seed
    plan = ZonePlan.from_controls({"zone_type": "dungeon", "dungeon_theme": "cave",
                                   "layout": "graph", "room_count": rooms,
                                   "verticality": vert}, [])
    plan.name = f"throat_{seed}"
    plan = plan.validate()
    made = []

    def factory(s):
        _F["nodes"], _F["rooms"] = {}, {}
        spec = plan_to_spec(plan, seed=s, warnings=[])
        made.append((spec, dict(_F["rooms"])))
        return spec

    row = {"length": length, "seed": seed, "rooms": rooms, "vert": vert, "passed": False,
           "fail": None, "warnings": []}
    with tempfile.TemporaryDirectory(prefix="throat", ignore_cleanup_errors=True) as tmp:
        try:
            vb = generate_validated(factory, zone_type=plan.zone_type, zone_id=plan.name,
                                    seed=seed, output_dir=Path(tmp), write_glb=False,
                                    rng=random.Random(seed), failure_log=None,
                                    verticality=plan.verticality)
            row["passed"] = bool(vb.validated)
            row["warnings"] = sorted({w.split(":")[0] for w in vb.warnings})
            if not vb.validated:
                row["fail"] = "not validated"
        except GenerationFailed as e:
            f = e.failures[0]
            row["fail"] = (f"gate [{', '.join(f.checks)}] stage={f.stage or '-'}: "
                           + "; ".join(f.reasons[:2]))[:300]
            row["fail_rooms"] = sorted({x.split(":")[0].split(" ")[0] for x in f.reasons})
            row["fail_at"] = _points(f.reasons)
            row["fail_stage"] = f.stage
        except Exception as e:  # noqa: BLE001 - a reader that crashed is the finding
            row["fail"] = f"crash {type(e).__name__} at {_where(e)}: {str(e)[:160]}"
    if made:
        spec, forced = made[-1]
        by = {r.id: r for r in spec.rooms}
        seen = set()
        d2d, gaps, dz, gave, ent, cors = [], [], 0, 0, [], []
        from grid_score import entry_angles
        trans = {w.get("corridor"): w for w in (spec.layout or {}).get("transitions", [])}
        for cor in spec.corridors:
            pair = frozenset((cor.from_room, cor.to_room))
            if pair not in forced or cor.from_room not in by or cor.to_room not in by:
                continue
            seen.add(pair)
            d2d.append(_d2d(cor, by))
            gaps.append(_box_gap(by[cor.from_room], by[cor.to_room]))
            dz += abs(by[cor.from_room].floor_z - by[cor.to_room].floor_z) > 1e-6
            w = trans.get(cor.id)
            gave += bool(w and "asked" in w and w["asked"] != w["form"])
            one_spec = type("S", (), {"rooms": spec.rooms, "corridors": [cor]})
            ent.append(max(entry_angles(one_spec), default=float("nan")))
            cors.append({"rooms": [cor.from_room, cor.to_room], "gap": round(gaps[-1], 1),
                         "d2d": round(d2d[-1], 1), "entry": round(ent[-1], 1),
                         "dz": round(abs(by[cor.from_room].floor_z - by[cor.to_room].floor_z), 2),
                         "doors": [[round(cor.from_x, 1), round(cor.from_y, 1)],
                                   [round(cor.to_x, 1), round(cor.to_y, 1)]]})
        width = spec.corridors[0].width if spec.corridors else float("nan")
        row.update(forced=len(forced), built=len(seen), d2d=d2d, gaps=gaps, dz=dz, gave=gave,
                   entry=ent, cors=cors,
                   width=width, corridors=len(spec.corridors))
    return row


def _stats(v):
    if not v:
        return "   -/   -/   -"
    return f"{min(v):4.0f}/{statistics.median(v):4.0f}/{max(v):4.0f}"


def _points(reasons):
    """The plan points the gate's reasons name: a point's (x, y), a rect's centre."""
    out = []
    for why in reasons:
        for grp in re.findall(r"\(([^()]*)\)", why):
            try:
                v = [float(x) for x in grp.split(",")]
            except ValueError:
                continue
            if len(v) == 4:
                out.append([(v[0] + v[2]) / 2, (v[1] + v[3]) / 2])
            elif len(v) >= 2:
                out.append(v[:2])
    return out


def _at(row) -> str:
    """Where a failing build failed: the forced corridor with a door nearest a point the
    gate names (within ``NEAR`` u): "straight" or "jogged" (a straight one wins);
    "decor" when the gate blames Decor; "" elsewhere."""
    if row["passed"]:
        return ""
    if row.get("fail_stage") == "decor":
        return "decor"
    hit = set()
    for p in row.get("fail_at", []):
        near = [(min(math.dist(p, d) for d in c["doors"]), c) for c in row.get("cors", [])]
        near = [x for x in near if x[0] <= NEAR]
        if near:
            hit.add("straight" if _straight(min(near, key=lambda x: x[0])[1]) else "jogged")
    return "straight" if "straight" in hit else "jogged" if hit else ""


def summarise(rows, lengths) -> str:
    base = {(r["seed"], r["vert"]): r for r in rows if r["length"] == "off"}
    width = next((r["width"] for r in rows if r.get("width") == r.get("width")), float("nan"))
    lines = [f"corridor width w = {width:.1f} u",
             f"{'len':>4s} {'pass':>6s} {'new':>4s} {'built/forced':>12s} "
             f"{'d2d mn/md/mx':>14s} {'gap mn/md/mx':>14s} {'str':>5s} {'dz':>3s} {'gave':>4s} {'stF':>3s} {'jgF':>3s} {'dcF':>3s} "
             f"{'new warns':>14s}  first failure (seed vert)"]
    for length in lengths:
        rs = sorted((r for r in rows if r["length"] == length), key=lambda r: (r["seed"], r["vert"]))
        if not rs:
            continue
        ok = sum(r["passed"] for r in rs)
        # New: failing where the unforced build of that seed passed.
        new = [r for r in rs if not r["passed"] and base.get((r["seed"], r["vert"]), {}).get("passed")]
        d2d = [x for r in rs for x in r.get("d2d", [])]
        gaps = [x for r in rs for x in r.get("gaps", [])]
        cs = [c for r in rs for c in r.get("cors", [])]
        straight = sum(_straight(c) for c in cs) / max(1, len(cs))
        warns = {}
        for r in rs:
            b = set(base.get((r["seed"], r["vert"]), {}).get("warnings", []))
            for w in set(r["warnings"]) - b:
                warns[w] = warns.get(w, 0) + 1
        first = next((r for r in rs if not r["passed"]), None)
        ftxt = f"{first['fail']} ({first['seed']} {first['vert']})" if first else "-"
        lines.append(
            f"{length:>4s} {ok:3d}/{len(rs):<2d} {len(new):4d} "
            f"{sum(r.get('built', 0) for r in rs):5d}/{sum(r.get('forced', 0) for r in rs):<6d} "
            f"{_stats(d2d):>14s} {_stats(gaps):>14s} "
            f"{straight:5.2f} {sum(r.get('dz', 0) for r in rs):3d} "
            f"{sum(r.get('gave', 0) for r in rs):4d} {sum(_at(r) == 'straight' for r in rs):3d} "
            f"{sum(_at(r) == 'jogged' for r in rs):3d} {sum(_at(r) == 'decor' for r in rs):3d} "
            f"{(','.join(f'{k}x{v}' for k, v in sorted(warns.items())) or '-'):>14s}  {ftxt}")
        for r in rs:
            if not r["passed"] and r is not first:
                lines.append(f"{'':>4s}   also {r['seed']} {r['vert']}: {r['fail']}")
    return "\n".join(lines)


def _run_length(args):
    """All of one length's builds in this process (the patches are per process)."""
    length, jobs, snap = args
    _F["snap"] = snap
    return [one(j) for j in jobs]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lengths", nargs="+", default=LENGTHS)
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--verts", nargs="+", default=["flat", "moderate"])
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--json", type=Path, help="write the per-build rows here")
    ap.add_argument("--summary", type=Path, help="reprint the table of a --json run, no builds")
    ap.add_argument("--no-snap", action="store_true",
                    help="leave forced pairs where the springs put them (else squared up)")
    a = ap.parse_args(argv)
    if a.summary:
        print(summarise(json.loads(a.summary.read_text()), a.lengths))
        return 0
    if not os.environ.get("EQ_PATH"):
        print("EQ_PATH is not set (the gate's format check reads the RoF2 install)", file=sys.stderr)
    builds = [(FIRST_SEED + i, 10 + i % 7, v) for i in range(a.seeds) for v in a.verts]
    # One length per task so a process's patches never mix; split each length's builds into
    # chunks so the pool stays busy (a process takes one task at a time: max_tasks_per_child).
    chunk = max(1, len(builds) // 2)
    tasks = [(length, [(length, *b) for b in builds[k:k + chunk]], not a.no_snap)
             for length in a.lengths for k in range(0, len(builds), chunk)]
    rows = []
    with ProcessPoolExecutor(a.jobs, max_tasks_per_child=1) as ex:
        for part in ex.map(_run_length, tasks):
            rows.extend(part)
            r = part[0]
            print(f"  done {r['length']} x{len(part)}: "
                  f"{sum(x['passed'] for x in part)} passed", flush=True)
    print(summarise(rows, a.lengths))
    if a.json:
        a.json.write_text(json.dumps(rows, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
