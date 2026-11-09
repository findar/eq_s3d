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
    python scripts/topology_rules.py check rules/sites                # the Site files, together
    python scripts/topology_rules.py draw-sites --out output/rules/   # each Site recipe's plan
    python scripts/topology_rules.py check rules/decor                # the decor files, with unmet Tags
    python scripts/topology_rules.py check rules/decor --strict       # ... failing on unmet Tags
    python scripts/topology_rules.py draw-decor --out output/rules/   # each decor recipe's plan

``<set>`` is a base set name in ``rules/topology/`` or a path to a ``.toml``
file. ``--theme T`` merges the layers ``themes.toml`` gives theme T (those
that fit the set).

``check`` exits 1 with the full report when any file fails; ``dry-run``
exits 1 when any graph raised ``TopologyError``. A decor recipe line whose
Tags have no ``use = "yes"`` model is reported as ``unmet``; it fails the
check only with ``--strict`` (until the tag review, every line is unmet).
"""

from __future__ import annotations

import argparse
import math
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
from generators.sites.rules import (  # noqa: E402
    BIOMES_FILE, CENTRE, INHABITANTS_FILE, SITES_DIR, SITES_FILE, SiteRecipe, SiteRules, load_sites,
)
from generators.decor import catalogue as decor_catalogue  # noqa: E402
from generators.decor.rules import (  # noqa: E402
    BARE, ROOMS_FILE as DECOR_ROOMS_FILE, SETS_FILE as DECOR_SETS_FILE, DecorRules, asks, draw_count, load_decor,
    unmet,
)
from generators.semantics import ROOM_TYPES  # noqa: E402
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
    if path.is_dir():
        if (path / DECOR_ROOMS_FILE).is_file():
            return "decor"
        return "sites" if (path / SITES_FILE).is_file() else "folder"
    if (path.name in (DECOR_ROOMS_FILE, DECOR_SETS_FILE, decor_catalogue.TAGS_FILE, decor_catalogue.CATALOGUE_FILE)
            and (path.parent / DECOR_ROOMS_FILE).is_file()):
        return "decor"
    if path.name in (SITES_FILE, INHABITANTS_FILE, BIOMES_FILE) and (path.parent / SITES_FILE).is_file():
        return "sites"
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
    files.append(SITES_DIR)
    files.append(decor_catalogue.DECOR_DIR)
    return files


def _expand(paths: Sequence[Path]) -> List[Path]:
    """A folder of rule files is its files; the Site files' folder is one set, checked together."""
    out: List[Path] = []
    for p in paths:
        kind = _kind_of(p)
        if kind == "folder":
            out += sorted(p.glob("*.toml"))
        elif kind in ("sites", "decor"):
            folder = p if p.is_dir() else p.parent
            if folder not in out:
                out.append(folder)
        else:
            out.append(p)
    return out


def _decor_catalogue(folder: Path):
    """The catalogue a decor folder's recipes are checked against: the folder's own
    ``catalogue.json`` and ``tags.toml`` where it has them, else the shipped ones."""
    def pick(name: str) -> Path:
        own = folder / name
        return own if own.is_file() else decor_catalogue.DECOR_DIR / name
    return decor_catalogue.load(pick(decor_catalogue.CATALOGUE_FILE), pick(decor_catalogue.TAGS_FILE))


def check_decor(folder: Path, strict: bool = False) -> Tuple[int, List[str]]:
    """(failures, report lines) for a decor folder: its files checked, which recipe each
    room type takes, and every recipe line with no usable model (a failure only when ``strict``)."""
    out: List[str] = []
    tags = folder / decor_catalogue.TAGS_FILE
    rules = load_decor(folder, tags if tags.is_file() else None)
    falls = sorted(t for t in ROOM_TYPES if t not in rules.types)
    out.append(f"ok    {folder.name}/: decor, {len(rules.types)} type, {len(rules.kinds)} kind and "
               f"{len(rules.sites)} Site recipes, {len(rules.groups)} groups, Dressing for "
               f"{len(rules.dressing)} POI purposes; {len(ROOM_TYPES) - len(falls)} of {len(ROOM_TYPES)} room "
               f"types have their own recipe" + (f", {', '.join(falls)} fall back to their kind's or the default"
                                                  if falls else ""))
    cat = _decor_catalogue(folder)
    missing = unmet(rules, cat)
    asked = sum(1 for _ in asks(rules))
    usable = len(cat.usable())
    if missing:
        label = "FAIL " if strict else "unmet"
        out.append(f"{label} {folder.name}/: {len(missing)} of {asked} recipe lines and Group members ask for "
                   f"Tags no use = \"yes\" model has ({usable} of {len(cat.models)} models usable; "
                   f"the tag review, task 4, sets use)")
        out.extend(f"      {e}" for e in missing)
    else:
        out.append(f"ok    {folder.name}/: every Tag asked for has a usable model ({usable} usable)")
    return (1 if missing and strict else 0), out


def cmd_check(files: Sequence[str], strict: bool = False) -> int:
    paths = _expand([Path(f) for f in files] if files else _shipped())
    failures = 0
    lines: List[str] = []
    bases = {}
    layers = {}
    for p in paths:
        kind = _kind_of(p)
        try:
            if kind == "decor":
                failed, report = check_decor(p if p.is_dir() else p.parent, strict)
                failures += failed
                lines.extend(report)
            elif kind == "sites":
                sr = load_sites(p)
                lines.append(f"ok    {p.name}/: sites, {len(sr.kinds)} kinds, {len(sr.structures)} structures, "
                             f"{len(sr.inhabitants)} inhabitants, {len(sr.biomes)} biomes")
            elif kind == "themes":
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


def _site_spots(recipe: SiteRecipe, rules: SiteRules, rng: random.Random):
    """A schematic plan of a recipe, for review only (placement is generators/sites/placement.py):
    each line's Structures at its arrangement's ideal spots round the centre, at a drawn count.
    Yields (structure, x, y, yaw toward the centre or not)."""
    r = recipe.ground.radius
    out = []
    by_at = {}
    for line in recipe.structures:
        if line.chance < 1.0 and rng.random() >= line.chance:
            continue
        n = rng.randint(*line.count)
        by_at.setdefault(line.at, []).extend([line] * n)
    centre_taken = bool(by_at.get(CENTRE))
    for at, lines in by_at.items():
        n = len(lines)
        for k, line in enumerate(lines):
            if at == CENTRE:
                x, y = (0.0, 0.0) if n == 1 else (0.25 * r * math.cos(2 * math.pi * k / n),
                                                  0.25 * r * math.sin(2 * math.pi * k / n))
            elif at in ("ring", "perimeter"):
                a = 2 * math.pi * (k + 0.5) / n
                d = 0.62 * r if at == "ring" else 0.85 * r
                x, y = d * math.cos(a), d * math.sin(a)
            elif at == "lone":
                x, y = ((0.0, 0.0) if n == 1 and not centre_taken else
                        ((k - (n - 1) / 2) * 0.45 * r, 0.3 * r if centre_taken else 0.0))
            elif at == "row":
                y0 = -0.75 * r if line.side == "open" else 0.0
                x, y = (k - (n - 1) / 2) * 2.1 * rules.structures[line.kind].radius, y0
            else:   # cluster
                a = rng.uniform(0, 2 * math.pi)
                d = rng.uniform(0.25, 0.6) * r
                x, y = d * math.cos(a), d * math.sin(a) * (0.5 if line.side == "open" else 1.0)
            out.append((line, x, y))
    return out


def _site_svg(recipe: SiteRecipe, rules: SiteRules, rng: random.Random, title: str, scale: float = 3.0) -> str:
    from generators.topology.draw import _esc, _f
    r = recipe.ground.radius + recipe.ground.margin
    size = 2 * (r + 6) * scale

    def px(x: float, y: float) -> Tuple[str, str]:
        return _f((x + r + 6) * scale), _f((r + 6 - y) * scale)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{_f(size)}" height="{_f(size)}" '
             f'viewBox="0 0 {_f(size)} {_f(size)}"><title>{_esc(title)}</title>',
             f'<rect width="100%" height="100%" fill="#f4f1e8"/>']
    c = px(0, 0)
    parts.append(f'<circle cx="{c[0]}" cy="{c[1]}" r="{_f(r * scale)}" fill="none" stroke="#9bb07a" '
                 f'stroke-dasharray="4 3"><title>Site_Clear margin</title></circle>')
    parts.append(f'<circle cx="{c[0]}" cy="{c[1]}" r="{_f(recipe.ground.radius * scale)}" fill="#e3dcc4" '
                 f'stroke="#b8ad8a"><title>ground, radius {recipe.ground.radius:g} u</title></circle>')
    placed = _site_spots(recipe, rules, rng)
    colours = {"fire_ring": "#d9682b", "altar_stone": "#8a6fb3"}
    seen = {}
    for line, x, y in placed:
        st = rules.structures[line.kind]
        at = px(x, y)
        fill = colours.get(line.kind, "#7a5a3a" if st.enterable else "#555")
        label = line.kind + (f" ({line.variant})" if line.variant else "") + (", enterable" if st.enterable else "")
        if line.kind in ("fence", "ruin_wall"):
            a = math.atan2(y, x) + math.pi / 2 if line.at != "row" else 0.0
            dx, dy = st.radius * math.cos(a), st.radius * math.sin(a)
            p, q = px(x - dx, y - dy), px(x + dx, y + dy)
            parts.append(f'<line x1="{p[0]}" y1="{p[1]}" x2="{q[0]}" y2="{q[1]}" stroke="{fill}" '
                         f'stroke-width="{_f(1.2 * scale)}"><title>{_esc(label)}</title></line>')
        else:
            parts.append(f'<circle cx="{at[0]}" cy="{at[1]}" r="{_f(st.radius * scale)}" fill="{fill}" '
                         f'fill-opacity="0.85"><title>{_esc(label)}</title></circle>')
            if line.face == "in" and (x or y):
                d = math.hypot(x, y)
                q = px(x - x / d * st.radius * 1.4, y - y / d * st.radius * 1.4)
                parts.append(f'<line x1="{at[0]}" y1="{at[1]}" x2="{q[0]}" y2="{q[1]}" stroke="#fff" '
                             f'stroke-width="2"><title>opening</title></line>')
        seen.setdefault(line.kind, (x, y))
    for poi in recipe.pois:
        if poi.at in seen:
            x, y = seen[poi.at]
        elif poi.at == "entrance":
            x, y = 0.0, -recipe.ground.radius
        else:
            x, y = 0.0, 0.0
        at = px(x, y + 2.5)
        colour = "#f2c230" if poi.purpose == "Light_Spot" else "#2b6fd6"
        parts.append(f'<circle cx="{at[0]}" cy="{at[1]}" r="5" fill="{colour}" stroke="#123"><title>'
                     f'{_esc(poi.name)}: {_esc(poi.purpose)} at {_esc(poi.at)}</title></circle>')
    parts.append("</svg>")
    return "".join(parts)


def cmd_draw_sites(out: Path) -> int:
    """sites.html: each kind's plan as each Inhabitant builds it, and the chances by biome."""
    from generators.topology.draw import _esc
    rules = load_sites()
    body = []
    for biome in sorted(rules.biomes):
        mix = rules.inhabitant_chances(biome)
        kinds = sorted(rules.kinds)
        head = "".join(f"<th>{_esc(k)}</th>" for k in kinds)
        rows = []
        for who in sorted(rules.inhabitants):
            ch = rules.kind_chances(biome, who)
            rows.append(f"<tr><th>{_esc(who)} ({mix.get(who, 0):.0%})</th>"
                        + "".join(f"<td>{ch[k]:.0%}</td>" for k in kinds) + "</tr>")
        body.append(f"<h2>biome {_esc(biome)}</h2><p>Density {rules.biomes[biome].density[0]:g}-"
                    f"{rules.biomes[biome].density[1]:g} Sites per 1e6 u&sup2; at Normal. A kind's chance "
                    f"for each Inhabitant (its share of the mix in brackets): biome x Inhabitant, weight over sum.</p>"
                    f"<table><tr><th></th>{head}</tr>{''.join(rows)}</table>")
    for kind, recipe in sorted(rules.kinds.items()):
        g = recipe.ground
        likes = ", ".join(f"{k} {v:g}" for k, v in recipe.likes.items()) or "nothing in particular"
        pois = "; ".join(f"{p.name} ({p.purpose} at {p.at})" for p in recipe.pois)
        body.append(f"<h2>{_esc(kind)}</h2><p>{_esc(recipe.arrangement)}; ground radius {g.radius:g} u, "
                    f"slope up to {g.slope_deg:g}&deg;, spacing {g.spacing:g} u, margin {g.margin:g} u; likes "
                    f"{_esc(likes)}. POIs: {_esc(pois)}.</p><div class=row>")
        for who in sorted(rules.inhabitants):
            built = rules.recipe_for(kind, who)
            for seed in (1, 2):
                svg = _site_svg(built, rules, random.Random(f"{kind}{who}{seed}"), f"{kind} {who} {seed}")
                body.append(f"<figure>{svg}<figcaption>{_esc(who)}, seed {seed}</figcaption></figure>")
        body.append("</div>")
    page = ("<!doctype html><meta charset=utf-8><title>Site recipes</title><style>"
            "body{font:14px sans-serif;margin:24px;color:#222;background:#fff}"
            ".row{display:flex;flex-wrap:wrap;gap:12px}figure{margin:0}"
            "figcaption{text-align:center;color:#555}table{border-collapse:collapse}"
            "td,th{border:1px solid #ccc;padding:3px 8px;text-align:right}</style><h1>Site recipes</h1>"
            "<p>A schematic plan of each recipe as each Inhabitant builds it, at a drawn count: not placement. "
            "Tan is the Site's ground, the dashed ring its Site_Clear margin; brown Structures are Enterable, "
            "grey solid, white ticks openings, lines fence and wall runs. Yellow is a Light_Spot POI, blue the "
            "others. Hover for names.</p>" + "".join(body))
    out.mkdir(parents=True, exist_ok=True)
    path = out / "sites.html"
    path.write_text(page, encoding="utf-8")
    print(f"wrote {path} ({len(rules.kinds)} kinds, {len(rules.inhabitants)} inhabitants)")
    return 0


DECOR_COLOURS = {"light": "#f2a230", "container": "#8a5a2b", "furniture": "#6a8f3a", "hanging": "#8a6fb3",
                 "structure": "#555", "debris": "#9a9a9a", "plant": "#2f8f5a", "other": "#c44"}
_DECOR_BOX = (-60.0, -45.0, 60.0, 45.0)


def _decor_spots(at: str, n: int, rng: random.Random) -> List[Tuple[float, float]]:
    """A schematic spot for each of ``n`` Props at ``at`` in the 120 x 90 u sample room, for review
    only (placement is generators/decor/placement.py). The doors are on the west wall."""
    x0, y0, x1, y1 = _DECOR_BOX
    out = []
    for k in range(n):
        t = (k + 0.5) / n
        if at == "on_wall":
            out.append((x0 + 10 + t * (x1 - x0 - 20), y1 - 1.5))
        elif at == "along_wall":
            out.append((x0 + 16 + t * (x1 - x0 - 26), y0 + 6))
        elif at == "corners":
            out.append([(x0 + 8, y0 + 8), (x1 - 8, y1 - 8), (x1 - 8, y0 + 8), (x0 + 8, y1 - 8)][k % 4])
        elif at == "centre":
            out.append((rng.uniform(-8, 8), rng.uniform(-6, 6)))
        elif at in ("far_end", "on_dais"):
            out.append((x1 - 14, (t - 0.5) * 40))
        elif at == "rows":
            out.append((-30 + 60 * ((k // 2 + 0.5) / max(1, (n + 1) // 2)), -14 if k % 2 else 14))
        elif at == "by_door":
            out.append((x0 + 7, (-8, 28)[k % 2]))
        elif at == "ceiling":
            out.append((rng.uniform(-30, 30), rng.uniform(-20, 20)))
        else:   # scatter
            out.append((rng.uniform(x0 + 8, x1 - 8), rng.uniform(y0 + 8, y1 - 8)))
    return out


def _decor_svg(rules: DecorRules, recipes, weights, rng: random.Random, title: str, scale: float = 2.2) -> str:
    """A sample room with each line's Props at a drawn count, coloured by Category."""
    from generators.topology.draw import _esc, _f
    x0, y0, x1, y1 = _DECOR_BOX
    pad = 6.0

    def px(x: float, y: float) -> Tuple[float, float]:
        return (x - x0 + pad) * scale, (y1 - y + pad) * scale

    w, h = (x1 - x0 + 2 * pad) * scale, (y1 - y0 + 2 * pad) * scale
    a, b = px(x0, y1)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{_f(w)}" height="{_f(h)}" viewBox="0 0 {_f(w)} '
             f'{_f(h)}"><title>{_esc(title)}</title><rect width="100%" height="100%" fill="#fff"/>',
             f'<rect x="{_f(a)}" y="{_f(b)}" width="{_f((x1 - x0) * scale)}" height="{_f((y1 - y0) * scale)}" '
             f'fill="#eee" stroke="#a33" stroke-width="2"/>']
    for dy in (-8.0, 28.0):
        p, q = px(x0, dy + 5), px(x0, dy - 5)
        parts.append(f'<line x1="{_f(p[0])}" y1="{_f(p[1])}" x2="{_f(q[0])}" y2="{_f(q[1])}" stroke="#eee" '
                     f'stroke-width="4"><title>door</title></line>')
    for recipe in recipes:
        for line in recipe.lines:
            n = draw_count(line, rules.factor(line, weights), rng)
            for x, y in _decor_spots(line.at, n, rng):
                if line.group:
                    items = [(m.kinds, m.category, x + 7 * j, y + (3.5 if m.at == "stack" else 0.0))
                             for j, m in enumerate(rules.groups[line.group].members)]
                else:
                    items = [(line.kinds, line.category, x, y)]
                for kinds, cat, gx, gy in items:
                    cx, cy = px(gx, gy)
                    label = f"{recipe.name}: {' or '.join(kinds)} ({line.at}{', ' + line.group if line.group else ''})"
                    if line.mount == "wall":
                        parts.append(f'<rect x="{_f(cx - 4)}" y="{_f(cy - 3)}" width="8" height="6" '
                                     f'fill="{DECOR_COLOURS[cat]}"><title>{_esc(label)}</title></rect>')
                    else:
                        dash = ' stroke="#333" stroke-dasharray="2 2"' if line.mount == "ceiling" else ""
                        parts.append(f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="4.5" fill="{DECOR_COLOURS[cat]}"{dash}>'
                                     f'<title>{_esc(label)}</title></circle>')
    parts.append("</svg>")
    return "".join(parts)


def _decor_row(rules: DecorRules, label: str, **room) -> str:
    from generators.topology.draw import _esc
    e = rules.expected(**room)
    total = sum(e.values())
    weights = rules.weights_for(**room)
    cells = "".join(f"<td>{e[c] / total:.0%}</td>" if total else "<td>-</td>" for c in decor_catalogue.CATEGORIES)
    return f"<tr><th>{_esc(label)}</th><td>{total:.1f}</td><td>{weights[BARE]:.0%}</td>{cells}</tr>"


def cmd_draw_decor(out: Path) -> int:
    """decor.html: Props per room by zone type, race and theme; each recipe's sample plan; the
    Dressing, the Sets, and the lines no usable model meets yet."""
    from generators.topology.draw import _esc
    rules = load_decor()
    head = ("<tr><th></th><th>Props a room</th><th>bare</th>"
            + "".join(f"<th>{_esc(c)}</th>" for c in decor_catalogue.CATEGORIES) + "</tr>")
    body = ["<h2>Props per room</h2><p>The mean a room takes (Dressing aside) and its Category shares, with the "
            "default recipe and every room's lines, Scales at 5, Decor Normal. Design finding 1's dungeon rooms "
            "hold 2.9-4.2-6.8 a room (p25-p50-p75 over zones), cities 4.0-9.4-12.5.</p><table>" + head]
    for zt in ("dungeon", "city", "outdoor_dungeon"):
        body.append(_decor_row(rules, f"zone type {zt}", zone_type=zt))
    for race in sorted(rules.weights["races"]):
        body.append(_decor_row(rules, f"race {race}", zone_type="dungeon", race=race))
    for theme in sorted(rules.weights["themes"]):
        body.append(_decor_row(rules, f"theme {theme}", zone_type="dungeon", theme=theme))
    for control in ("sparse", "dense"):
        body.append(_decor_row(rules, f"Decor {control}", zone_type="dungeon", control=control))
    body.append("</table><h2>By recipe</h2><table>" + head)
    recipes = ([("default", "", "")] + [(f"kinds.{k}", "", k) for k in sorted(rules.kinds)]
               + [(f"types.{t}", t, "") for t in sorted(ROOM_TYPES)])
    for label, rtype, kind in recipes:
        body.append(_decor_row(rules, f"{label} (takes {rules.which_recipe(rtype, kind)})", zone_type="dungeon",
                               room_type=rtype, kind=kind))
    body.append("</table>")
    for label, rtype, kind in recipes:
        own = rules.recipe_for(rtype, kind)
        body.append(f"<h2>{_esc(label)}</h2><div class=row>")
        for zt in ("dungeon", "city"):
            weights = rules.weights_for(zone_type=zt, room_type=rtype, kind=kind)
            for seed in (1, 2):
                svg = _decor_svg(rules, own, weights, random.Random(f"{label}{zt}{seed}"), f"{label} {zt} {seed}")
                body.append(f"<figure>{svg}<figcaption>{_esc(zt)}, seed {seed}</figcaption></figure>")
        body.append("</div>")
    body.append("<h2>Dressing</h2><ul>")
    for purpose, lines in sorted(rules.dressing.items()):
        text = "; ".join(f"{' or '.join(ln.kinds) or ln.group} {ln.at} x{ln.count[0]}-{ln.count[1]}"
                         + (f" ({ln.chance:.0%})" if ln.chance < 1 else "") for ln in lines)
        body.append(f"<li><b>{_esc(purpose)}</b>: {_esc(text)}</li>")
    body.append("</ul><h2>Sets</h2><table><tr><th>race</th><th>its Sets, best first, as a dungeon room</th></tr>")
    for race in sorted(rules.sets.races):
        body.append(f"<tr><th>{_esc(race)}</th><td style='text-align:left'>"
                    f"{_esc(', '.join(rules.sets.sets_for('dungeon', race)))}</td></tr>")
    body.append("</table>")
    missing = unmet(rules, _decor_catalogue(decor_catalogue.DECOR_DIR))
    body.append(f"<h2>Unmet ({len(missing)})</h2><p>Lines with no use = \"yes\" model yet (the tag review sets "
                "use); at build time they drop.</p><ul>" + "".join(f"<li>{_esc(e)}</li>" for e in missing) + "</ul>")
    page = ("<!doctype html><meta charset=utf-8><title>Decor recipes</title><style>"
            "body{font:14px sans-serif;margin:24px;color:#222;background:#fff}"
            ".row{display:flex;flex-wrap:wrap;gap:12px}figure{margin:0}"
            "figcaption{text-align:center;color:#555}table{border-collapse:collapse}"
            "td,th{border:1px solid #ccc;padding:3px 8px;text-align:right}</style><h1>Decor recipes</h1>"
            "<p>A schematic plan of each recipe in a 120 x 90 u room with its doors on the west wall, at a drawn "
            "count: not placement. Colour is the Category: "
            + ", ".join(f"<span style='color:{c}'>{_esc(k)}</span>" for k, c in DECOR_COLOURS.items())
            + ". Squares are wall Props, dashed circles ceiling ones; a Group stands in a line. Hover for names.</p>"
            + "".join(body))
    out.mkdir(parents=True, exist_ok=True)
    path = out / "decor.html"
    path.write_text(page, encoding="utf-8")
    print(f"wrote {path} ({len(recipes)} recipes, {len(missing)} unmet lines)")
    return 0


# ---------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="See docs/TOPOLOGY_RULES.md.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="check rule files (default: every shipped file)")
    c.add_argument("files", nargs="*")
    c.add_argument("--strict", action="store_true", help="fail on decor Tags with no usable model")
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
    t = sub.add_parser("draw-sites", help="write sites.html: each Site recipe's plan, and chances by biome")
    t.add_argument("--out", type=Path, required=True)
    e = sub.add_parser("draw-decor", help="write decor.html: each decor recipe's plan, and Props per room")
    e.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # the checker's "›"
    try:
        if a.cmd == "check":
            return cmd_check(a.files, a.strict)
        if a.cmd == "dry-run":
            return cmd_dry_run(a.set, a.theme, a.graphs, a.rooms, a.race_scale, a.zone_type,
                               a.seed)
        if a.cmd == "draw-rooms":
            return cmd_draw_rooms(a.out)
        if a.cmd == "draw-walls":
            return cmd_draw_walls(a.out)
        if a.cmd == "draw-sites":
            return cmd_draw_sites(a.out)
        if a.cmd == "draw-decor":
            return cmd_draw_decor(a.out)
        return cmd_draw(a.set, a.theme, a.out, a.example_rooms)
    except RuleSetError as exc:
        print(f"the rule set failed its checks ({len(exc.errors)} problem(s)):")
        print("\n".join(f"  {e}" for e in exc.errors))
        return 1


if __name__ == "__main__":
    sys.exit(main())
