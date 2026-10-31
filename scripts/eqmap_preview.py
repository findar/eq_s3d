"""Draw a build's EQ map files back over its outline SVG.

    python scripts/eqmap_preview.py output/<zone_id>/v<version>

Reads ``<name>.map.svg``, ``<name>.json`` (the spec), ``<name>.zone.json``
(the sidecar's outline bounds) and ``maps/<name>*.txt`` from the build dir.
Each map line is parsed with ``parse_map_layer``, taken back to world with
``map_to_world`` and drawn in magenta on top of the SVG, in the SVG's own
frame. Writes ``<name>.overlay.svg`` next to it and nothing else. If the map
convention is right, the magenta lines sit exactly on the outline's walls,
north-up.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generators.eqmap import map_to_world, parse_map_layer  # noqa: E402
from generators.zone_spec import ZoneSpec  # noqa: E402

# render_map_svg's defaults, which the pipeline's map post-pass uses.
SIZE = 720
PADDING = 40
STROKE = "#ff00ff"


def svg_frame(spec: ZoneSpec, outline_bounds) -> tuple:
    """Rebuild render_map_svg's world->pixel transform: the frame covers the
    rooms, corridor endpoints and the outline bounds, scaled to fit SIZE with
    Y flipped so north is up. Returns ``(px, py, w, h)``."""
    xs, ys = [], []
    for r in spec.rooms:
        xs += [r.center_x - r.width / 2, r.center_x + r.width / 2]
        ys += [r.center_y - r.depth / 2, r.center_y + r.depth / 2]
    for c in spec.corridors:
        xs += [c.from_x, c.to_x]
        ys += [c.from_y, c.to_y]
    if outline_bounds:
        bx0, by0, _, bx1, by1, _ = outline_bounds
        xs += [bx0, bx1]
        ys += [by0, by1]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1.0)
    span_y = max(max_y - min_y, 1.0)
    scale = (SIZE - 2 * PADDING) / max(span_x, span_y)
    w = span_x * scale + 2 * PADDING
    h = span_y * scale + 2 * PADDING
    return (lambda x: PADDING + (x - min_x) * scale,
            lambda y: PADDING + (max_y - y) * scale, w, h)


def build_overlay(build_dir: Path) -> Path:
    svgs = sorted(build_dir.glob("*.map.svg"))
    if len(svgs) != 1:
        raise SystemExit(f"expected one *.map.svg in {build_dir}, found {len(svgs)}")
    svg_path = svgs[0]
    name = svg_path.name[: -len(".map.svg")]
    svg = svg_path.read_text(encoding="utf-8")

    spec = ZoneSpec.load(build_dir / f"{name}.json")
    sidecar = json.loads((build_dir / f"{name}.zone.json").read_text(encoding="utf-8"))
    outline = sidecar.get("outline") or {}
    px, py, w, h = svg_frame(spec, outline.get("bounds"))

    # The rebuilt frame must be the one the SVG was drawn in.
    m = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg)
    if not m or (int(m.group(1)), int(m.group(2))) != (round(w), round(h)):
        raise SystemExit(f"frame mismatch: SVG viewBox {m and m.groups()}, "
                         f"rebuilt {w:.0f}x{h:.0f}")

    maps = sorted((build_dir / "maps").glob(f"{name}*.txt"))
    if not maps:
        raise SystemExit(f"no maps/{name}*.txt in {build_dir}")
    parts = [f'<g id="eqmap-overlay" fill="none" stroke="{STROKE}" '
             f'stroke-opacity="0.75" stroke-width="1" stroke-linecap="round">']
    n_lines = n_labels = 0
    for path in maps:
        res = parse_map_layer(path.read_text(encoding="ascii"))
        if res.skipped:
            print(f"{path.name}: skipped malformed lines {res.skipped}")
        for ln in res.layer.lines:
            x1, y1, _ = map_to_world(ln.x1, ln.y1, ln.z1)
            x2, y2, _ = map_to_world(ln.x2, ln.y2, ln.z2)
            parts.append(f'<line x1="{px(x1):.2f}" y1="{py(y1):.2f}" '
                         f'x2="{px(x2):.2f}" y2="{py(y2):.2f}"/>')
        for lb in res.layer.labels:
            x, y, _ = map_to_world(lb.x, lb.y, lb.z)
            parts.append(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="3" '
                         f'fill="{STROKE}" stroke="none"/>'
                         f'<text x="{px(x) + 5:.1f}" y="{py(y) - 5:.1f}" '
                         f'fill="{STROKE}" stroke="none" font-size="11" '
                         f'font-family="sans-serif">{escape(lb.text)}</text>')
        n_lines += len(res.layer.lines)
        n_labels += len(res.layer.labels)
    parts.append("</g>")

    end = svg.rindex("</svg>")
    out = build_dir / f"{name}.overlay.svg"
    out.write_text(svg[:end] + "".join(parts) + svg[end:], encoding="utf-8")
    print(f"{out}: {n_lines} lines, {n_labels} labels from {len(maps)} file(s)")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("build_dir", type=Path)
    build_overlay(ap.parse_args().build_dir)


if __name__ == "__main__":
    main()
