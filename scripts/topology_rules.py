r"""Check, dry-run and draw topology rule sets (roadmap step 6, Req 3.2-3.5).

Thin over the library: loading and checking are ``generators/topology/
ruleset.py``'s, growing is ``rewrite.py``'s, drawing is ``draw.py``'s. The
authoring guide is ``docs/TOPOLOGY_RULES.md``.

Usage::

    python scripts/topology_rules.py check                       # every shipped file
    python scripts/topology_rules.py check my_set.toml layers/my_layer.toml
    python scripts/topology_rules.py dry-run classic_eq --graphs 50 --rooms 5-20
    python scripts/topology_rules.py dry-run classic_eq --theme temple --race-scale 1.6
    python scripts/topology_rules.py draw classic_eq --out output/rules/
    python scripts/topology_rules.py draw-walls --out output/rules/   # sample rooms per wall style
    python scripts/topology_rules.py draw-rooms --out output/rules/   # each room layout, per style

``<set>`` is a base set name in ``rules/topology/`` or a path to a ``.toml``
file. ``--theme T`` merges the layers ``themes.toml`` gives theme T (those
that fit the set).

``check`` exits 1 with the full report when any file fails; ``dry-run``
exits 1 when any graph raised ``TopologyError``.
"""

from __future__ import annotations

import argparse
import random
import sys
import tomllib
from collections import Counter
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from generators.outline import SHAPES as OUTLINE_SHAPES  # noqa: E402
from generators.topology import draw  # noqa: E402
from generators.topology.graph import SIZE_CLASSES  # noqa: E402
from generators.topology.rewrite import BuildContext, TopologyError, grow  # noqa: E402
from generators.topology.ruleset import (  # noqa: E402
    RuleSet, RuleSetError, ThemeLayer, load_for_theme, load_layer, load_rule_set,
    load_theme_map, merge,
)

from generators.room_layouts import LAYOUTS_FILE, load_layouts, place  # noqa: E402
from generators.room_scales import SCALES_FILE, load_scales  # noqa: E402
from generators.transitions import TRANSITIONS_FILE, load_transitions  # noqa: E402
from generators.zone_spec import RoomSpec  # noqa: E402
from generators.wall_styles import RECT, WALLS_DIR, load_style, load_styles  # noqa: E402

RULES = ROOT / "rules" / "topology"
THEMES = "themes.toml"


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------

def _kind_of(path: Path) -> str:
    """'themes', 'layer' or 'set', from the file name and its top-level tables."""
    if path.name == THEMES:
        return "themes"
    if path.name == SCALES_FILE.name:
        return "scales"
    if path.name == TRANSITIONS_FILE.name:
        return "transitions"
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return "layer" if path.parent.name == "layers" else "set"   # the loader reports it
    if "style" in data:
        return "style"
    if "types" in data:
        return "rooms"
    return "layer" if "layer" in data else "set"


def _set_path(name: str) -> Path:
    p = Path(name)
    if p.suffix == ".toml" or p.exists():
        return p
    return RULES / f"{name}.toml"


def fitting_layers(base: RuleSet, rules_dir: Path = RULES) -> List[ThemeLayer]:
    """Every layer in ``rules_dir/layers`` whose ``fits`` names the base set."""
    out = []
    for p in sorted((rules_dir / "layers").glob("*.toml")):
        layer = load_layer(p)
        if base.name in layer.fits:
            out.append(layer)
    return out


def load_set(name: str, theme: Optional[str]) -> Tuple[RuleSet, RuleSet, List[ThemeLayer]]:
    """(the set to use, the base alone, the theme's layers merged in)."""
    base = load_rule_set(_set_path(name))
    if theme is None:
        return base, base, []
    entry = load_theme_map(RULES / THEMES).entry_for(theme)
    layers = [load_layer(RULES / "layers" / f"{n}.toml") for n in entry.layers]
    layers = [l for l in layers if base.name in l.fits]
    return merge(base, layers), base, layers


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------

def _shipped() -> List[Path]:
    files = sorted(RULES.glob("*.toml"))
    files += sorted((RULES / "layers").glob("*.toml"))
    files += sorted(WALLS_DIR.glob("*.toml"))
    files.append(LAYOUTS_FILE)
    files.append(SCALES_FILE)
    files.append(TRANSITIONS_FILE)
    return files


def cmd_check(files: Sequence[str]) -> int:
    paths = [Path(f) for f in files] if files else _shipped()
    failures = 0
    lines: List[str] = []
    bases = {}
    layers = {}
    for p in paths:
        kind = _kind_of(p)
        try:
            if kind == "themes":
                tm = load_theme_map(p)
                lines.append(f"ok    {p.name}: theme map, {len(tm.entries)} themes")
            elif kind == "scales":
                sc = load_scales(p)
                lines.append(f"ok    {p.name}: scales, {len(sc.races)} races, {len(sc.themes)} themes, "
                             f"{len(sc.overlays)} overlays")
            elif kind == "transitions":
                tr = load_transitions(p)
                lines.append(f"ok    {p.name}: transitions, {len(tr.pairs)} pairs, {len(tr.types)} types, "
                             f"{len(tr.kinds)} kinds")
            elif kind == "rooms":
                rl = load_layouts(p)
                lines.append(f"ok    {p.name}: room layouts, {len(rl.types)} types, {len(rl.kinds)} kinds")
            elif kind == "style":
                st = load_style(p)
                lines.append(f"ok    {p.name}: wall style, {st.complex}, {len(st.shapes)} kinds")
            elif kind == "layer":
                l = load_layer(p)
                layers[l.name] = (p, l)
                lines.append(f"ok    {p.name}: layer, {len(l.rules)} rules, fits "
                             f"{', '.join(l.fits)}")
            else:
                s = load_rule_set(p)
                bases[s.name] = (p, s)
                lines.append(f"ok    {p.name}: base set, {len(s.rules)} rules, "
                             f"{len(s.recipe)} stages")
        except RuleSetError as exc:
            failures += 1
            lines.append(f"FAIL  {p.name}: {len(exc.errors)} problem(s)")
            lines.extend(f"      {e}" for e in exc.errors)

    # Each layer merged onto every checked (or shipped) base set it says it fits.
    for lname, (lp, layer) in layers.items():
        for bname in layer.fits:
            if bname in bases:
                base = bases[bname][1]
            elif (RULES / f"{bname}.toml").is_file():
                try:
                    base = load_rule_set(RULES / f"{bname}.toml")
                except RuleSetError:
                    continue            # reported when that file is checked
            else:
                lines.append(f"note  {lp.name}: fits {bname!r}, but there is no {bname}.toml")
                continue
            try:
                m = merge(base, [layer])
                lines.append(f"ok    {bname} + {lname}: merged, {len(m.rules)} rules, "
                             f"{len(m.recipe)} stages")
            except RuleSetError as exc:
                failures += 1
                lines.append(f"FAIL  {bname} + {lname}: {len(exc.errors)} problem(s)")
                lines.extend(f"      {e}" for e in exc.errors)

    # Each theme's merged set, when the theme map is among the files checked.
    for p in paths:
        if _kind_of(p) != "themes":
            continue
        try:
            tm = load_theme_map(p)
        except RuleSetError:
            continue
        for theme, entry in tm.entries.items():
            label = f"theme {theme} ({' + '.join([entry.base] + list(entry.layers))})"
            try:
                load_for_theme(p.parent, theme)
                lines.append(f"ok    {label}")
            except RuleSetError as exc:
                failures += 1
                lines.append(f"FAIL  {label}: {len(exc.errors)} problem(s)")
                lines.extend(f"      {e}" for e in exc.errors)

    print("\n".join(lines))
    print(f"\n{failures} failing" if failures else "\nall checks passed")
    return 1 if failures else 0


# ---------------------------------------------------------------------------
# dry-run
# ---------------------------------------------------------------------------

def _rooms(text: str) -> List[int]:
    try:
        if "-" in text:
            a, b = (int(x) for x in text.split("-", 1))
        else:
            a = b = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"rooms must be N or A-B, got {text!r}")
    if not 1 <= a <= b <= 30:
        raise argparse.ArgumentTypeError(f"rooms must lie in 1-30 with A <= B, got {text!r}")
    return list(range(a, b + 1))


def _pct(values: Sequence[float]) -> str:
    if not values:
        return "  -     -     -     -"
    p10, p50, p90 = np.percentile(values, [10, 50, 90])
    return f"{p10:5.2f} {p50:5.2f} {p90:5.2f} {float(np.mean(values)):5.2f}"


def cmd_dry_run(name: str, theme: Optional[str], graphs: int, rooms: List[int],
                race_scale: Optional[float], zone_type: str, seed: int) -> int:
    rule_set, _, _ = load_set(name, theme)
    ctx = BuildContext(theme=theme, race_scale=race_scale, zone_type=zone_type)
    stage_names = [s.name for s in rule_set.recipe]
    ended = {s: Counter() for s in stage_names}
    spent = {s: [] for s in stage_names}
    fired = Counter()
    fired_in = Counter()
    errors = Counter()
    measures = {"dead-end share": [], "cycles per room": [], "deep-end distance": []}
    mixes = {c: [] for c in SIZE_CLASSES}
    for i in range(graphs):
        n = rooms[i % len(rooms)]
        rng = random.Random(seed * 100003 + i)
        try:
            res = grow(rule_set, n, rng, ctx)
        except TopologyError as exc:
            errors[str(exc)] += 1
            continue
        for st in res.stats["stages"]:
            ended[st["stage"]][st["ended"]] += 1
            spent[st["stage"]].append((st["spent"], st["budget"]))
        per = Counter(a.rule for a in res.applied)
        fired.update(per)
        fired_in.update(per.keys())
        g = res.graph
        measures["dead-end share"].append(g.dead_end_share())
        measures["cycles per room"].append(g.cycle_rank() / n)
        measures["deep-end distance"].append(g.deep_end_distance())
        for c, v in g.size_mix().items():
            mixes[c].append(v)
    ok = graphs - sum(errors.values())

    layers = f" + {', '.join(rule_set.layers)}" if rule_set.layers else ""
    print(f"dry run: {rule_set.name}{layers} ({rule_set.source})")
    print(f"  {graphs} graphs, rooms {rooms[0]}-{rooms[-1]}, seed {seed}; context: theme={theme}, "
          f"race_scale={race_scale}, zone_type={zone_type}")
    print(f"  grown {ok}, TopologyError {sum(errors.values())}")
    for msg, c in errors.most_common():
        print(f"    {c} x {msg}")

    print("\nstages (over the graphs grown)")
    print(f"  {'stage':<16} {'share':>5}  {'complete':>8}  {'ended early':>11}  "
          f"{'spent/budget':>12}")
    for s in rule_set.recipe:
        e = ended[s.name]
        runs = sum(e.values()) or 1
        share = "rest" if s.is_rest else f"{s.share:g}"
        done = e["budget"] + e["done"]
        sp = spent[s.name]
        tot_b = sum(b for _, b in sp)
        ratio = f"{sum(x for x, _ in sp)}/{tot_b}" if tot_b else "-"
        print(f"  {s.name:<16} {share:>5}  {100 * done / runs:7.0f}%  "
              f"{100 * e['no match'] / runs:10.0f}%  {ratio:>12}")
    print("  complete = spent its budget (or, for rest, finished the graph); "
          "ended early = ran out of legal matches, budget passed on")

    print("\nrules (applications, graphs it fired in)")
    used = []
    for s in rule_set.recipe:
        used += [r for r in s.apply if r not in used]
    width = max((len(r) for r in rule_set.rules), default=8)
    for r in used:
        print(f"  {r:<{width}} {fired[r]:6d}  {100 * fired_in[r] / max(ok, 1):5.0f}%")
    never = [r for r in used if fired[r] == 0]
    unused = [r for r in rule_set.rules if r not in used]
    print(f"  never fired: {', '.join(never) if never else 'none'}")
    if unused:
        print(f"  in no stage: {', '.join(unused)}")

    print("\nshape (p10 p50 p90 mean)")
    for k, v in measures.items():
        print(f"  {k:<18} {_pct(v)}")
    print("\nsize mix (share of rooms: p10 p50 p90 mean)")
    for c in SIZE_CLASSES:
        print(f"  {c:<18} {_pct(mixes[c])}")
    return 1 if errors else 0


# ---------------------------------------------------------------------------
# draw
# ---------------------------------------------------------------------------

def cmd_draw(name: str, theme: Optional[str], out: Path, example_rooms: int) -> int:
    rule_set, base, _ = load_set(name, theme)
    layers = fitting_layers(base)       # every fitting layer's rules are shown, theme or not
    example = caption = None
    if example_rooms:
        ctx = BuildContext(theme=theme, race_scale=1.0, zone_type="dungeon")
        try:
            res = grow(rule_set, example_rooms, 1, ctx)
            example = res.graph
            per = Counter(a.rule for a in res.applied)
            caption = (f"{example_rooms} rooms, seed 1, race scale 1: "
                       + ", ".join(f"{r} x{c}" for r, c in sorted(per.items()))
                       + f". Dead-end share {example.dead_end_share():.2f}, cycle rank "
                         f"{example.cycle_rank()}, deep-end distance "
                         f"{example.deep_end_distance():.2f}.")
        except TopologyError as exc:
            caption = f"growing failed: {exc}"
    page = draw.rule_set_html(rule_set, layers, theme=theme, base_recipe=base.recipe,
                              example=example, example_caption=caption or "")
    out.mkdir(parents=True, exist_ok=True)
    path = out / (f"{base.name}-{theme}.html" if theme else f"{base.name}.html")
    path.write_text(page, encoding="utf-8")
    print(f"wrote {path} ({len(rule_set.rules)} rules, {len(layers)} fitting layer(s))")
    return 0


def cmd_draw_walls(out: Path) -> int:
    box = (-60.0, -45.0, 60.0, 45.0)
    doors = [("E", -20.0, -2.0), ("N", 15.0, 33.0)]
    rows = []
    for name, style in load_styles().items():
        used = sorted({shape for table in style.shapes.values() for shape in table})
        samples = []
        for shape in [s for s in (RECT,) + OUTLINE_SHAPES if s in used]:
            for seed in (1, 2, 3):
                outline = style.draw(box, doors, [], shape, 6.0, random.Random(f"{name}{shape}{seed}"))
                fill = 1.0 if outline is None else outline.fill(box)
                samples.append((f"{shape}, seed {seed}, fill {fill:.2f}",
                                draw.outline_svg(outline, box, title=f"{name} {shape} {seed}")))
        rows.append((name, style.description, samples))
    out.mkdir(parents=True, exist_ok=True)
    path = out / "walls.html"
    path.write_text(draw.walls_html(rows), encoding="utf-8")
    print(f"wrote {path} ({len(rows)} styles)")
    return 0


def cmd_draw_rooms(out: Path) -> int:
    box = (-60.0, -45.0, 60.0, 45.0)
    doors = [("E", -20.0, -2.0), ("W", 5.0, 23.0)]
    layouts = load_layouts()
    recipes = [(f"type {n}", a) for n, a in sorted(layouts.types.items()) if a]
    recipes += [(f"kind {n}", a) for n, a in sorted(layouts.kinds.items()) if a]
    forms = {"built": "square", "hewn": "cut", "rough": "rough"}
    styles = load_styles()
    rows = []
    for name, asks in recipes:
        samples = []
        for sname, form in forms.items():
            rng = random.Random(f"{name}{sname}")
            room = RoomSpec("r", 0.0, 0.0, width=120.0, depth=90.0, height=40.0)
            room.outline = styles[sname].draw(box, doors, [], "blob" if sname != "built" else "rect", 6.0, rng,
                                              room_height=40.0)
            placed = place(room, doors, [], asks, 6.0, form, rng)
            samples.append((f"{sname}, {len(placed.features)} placed" + (", drops" if placed.dropped else ""),
                            draw.room_svg(box, room.outline, placed.features, placed.pois, title=f"{name} {sname}")))
        rows.append((name, samples))
    out.mkdir(parents=True, exist_ok=True)
    path = out / "rooms.html"
    path.write_text(draw.rooms_html(rows), encoding="utf-8")
    print(f"wrote {path} ({len(rows)} recipes)")
    return 0


# ---------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="See docs/TOPOLOGY_RULES.md.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="check rule files (default: every shipped file)")
    c.add_argument("files", nargs="*")
    d = sub.add_parser("dry-run", help="grow graphs and report stages, rules and shape")
    d.add_argument("set")
    d.add_argument("--theme")
    d.add_argument("--graphs", type=int, default=50)
    d.add_argument("--rooms", type=_rooms, default=_rooms("5-20"), help="N or A-B (1-30)")
    d.add_argument("--race-scale", type=float, default=1.0)
    d.add_argument("--zone-type", default="dungeon")
    d.add_argument("--seed", type=int, default=0)
    w = sub.add_parser("draw", help="write <set>.html: start graph, recipe, rule diagrams")
    w.add_argument("set")
    w.add_argument("--theme")
    w.add_argument("--out", type=Path, required=True)
    w.add_argument("--example-rooms", type=int, default=15,
                   help="rooms in the example grown graph (0 for none)")
    o = sub.add_parser("draw-rooms", help="write rooms.html: each room layout, in each wall style")
    o.add_argument("--out", type=Path, required=True)
    v = sub.add_parser("draw-walls", help="write walls.html: sample rooms for each wall style")
    v.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # the checker's "›"
    try:
        if a.cmd == "check":
            return cmd_check(a.files)
        if a.cmd == "dry-run":
            return cmd_dry_run(a.set, a.theme, a.graphs, a.rooms, a.race_scale, a.zone_type,
                               a.seed)
        if a.cmd == "draw-rooms":
            return cmd_draw_rooms(a.out)
        if a.cmd == "draw-walls":
            return cmd_draw_walls(a.out)
        return cmd_draw(a.set, a.theme, a.out, a.example_rooms)
    except RuleSetError as exc:
        print(f"the rule set failed its checks ({len(exc.errors)} problem(s)):")
        print("\n".join(f"  {e}" for e in exc.errors))
        return 1


if __name__ == "__main__":
    sys.exit(main())
