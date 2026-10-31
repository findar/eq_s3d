"""
tests/reference_mapview.py
--------------------------
FROZEN, TEST-ONLY copy of ``generators.mapview.render_map_svg`` as it stood at
commit 7156d9f (master, before M2 task 5 added the ``outline`` layer).

Property 14 (M2-P9) checks that ``render_map_svg(spec, size, padding)`` with no
outline stays byte-identical to this rendering. NEVER edit this file: it is the
oracle, not a copy to keep in sync. Its only change from the original is the
import of ``ZoneSpec`` (absolute, since this module lives under ``tests/``).
"""

from __future__ import annotations

from typing import List, Tuple

from generators.zone_spec import ZoneSpec


def _esc(s: str) -> str:
    """Minimal XML-escape for text drawn into the SVG."""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


# Role → fill colour for room boxes.
_ROLE_FILL = {
    "entrance": "#2e7d32",   # green — the safe start
    "hub": "#1565c0",        # blue — crossroads
    "climax": "#8e24aa",     # purple — boss chamber
    "deadend": "#8d6e63",    # brown — reward nook
    "standard": "#455a64",   # slate — ordinary room
}
_ROLE_STROKE = {
    "entrance": "#66bb6a",
    "hub": "#42a5f5",
    "climax": "#ce93d8",
    "deadend": "#bcaaa4",
    "standard": "#78909c",
}


def render_map_svg(spec: ZoneSpec, size: int = 720, padding: int = 40) -> str:
    """
    Build an SVG top-down map of the zone. `size` is the max pixel dimension;
    the map preserves the zone's aspect ratio and is centred in a square-ish
    canvas. Returns the SVG document as a string.
    """
    # ---- Gather world-space extents from rooms + corridors ----
    xs: List[float] = []
    ys: List[float] = []
    for r in spec.rooms:
        xs += [r.center_x - r.width / 2, r.center_x + r.width / 2]
        ys += [r.center_y - r.depth / 2, r.center_y + r.depth / 2]
    for c in spec.corridors:
        xs += [c.from_x, c.to_x]
        ys += [c.from_y, c.to_y]

    if not xs or not ys:
        return _empty_svg(size)

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1.0)
    span_y = max(max_y - min_y, 1.0)

    inner = size - 2 * padding
    scale = inner / max(span_x, span_y)
    w = span_x * scale + 2 * padding
    h = span_y * scale + 2 * padding

    def px(x: float) -> float:
        return padding + (x - min_x) * scale

    def py(y: float) -> float:
        # Flip Y so north (+Y) is up in the image.
        return padding + (max_y - y) * scale

    parts: List[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" '
        f'viewBox="0 0 {w:.0f} {h:.0f}">'
    )
    parts.append(f'<rect x="0" y="0" width="{w:.0f}" height="{h:.0f}" fill="#0f0f16"/>')

    # ---- Corridors (drawn first, under the rooms) ----
    for c in spec.corridors:
        x1, y1 = px(c.from_x), py(c.from_y)
        x2, y2 = px(c.to_x), py(c.to_y)
        cw = max(2.0, c.width * scale)
        parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="#5c6b73" stroke-width="{cw:.1f}" stroke-linecap="round"/>'
        )

    # ---- Rooms ----
    label_rooms = {"entrance", "hub", "climax", "deadend"}
    for r in spec.rooms:
        rw = r.width * scale
        rh = r.depth * scale
        x = px(r.center_x) - rw / 2
        y = py(r.center_y) - rh / 2
        fill = _ROLE_FILL.get(r.role, _ROLE_FILL["standard"])
        stroke = _ROLE_STROKE.get(r.role, _ROLE_STROKE["standard"])
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{rw:.1f}" height="{rh:.1f}" '
            f'rx="4" fill="{fill}" fill-opacity="0.82" stroke="{stroke}" '
            f'stroke-width="1.5"/>'
        )
        # Depth number in the room centre
        cx, cy = px(r.center_x), py(r.center_y)
        parts.append(
            f'<text x="{cx:.1f}" y="{cy + 4:.1f}" fill="#e8eef2" font-size="12" '
            f'font-family="monospace" text-anchor="middle">{r.graph_depth}</text>'
        )
        # Room id in the box's top-left corner so the map matches the 3D view —
        # a human can point at a room in either and know exactly which room_N it
        # is. Small monospace, slightly dimmed to sit under the depth number.
        parts.append(
            f'<text x="{x + 3:.1f}" y="{y + 11:.1f}" fill="#9fb2bd" font-size="9" '
            f'font-family="monospace" text-anchor="start">{_esc(r.id)}</text>'
        )
        # Semantic type label below the room (content layer). Falls back to the
        # pacing role label for un-themed zones so existing behaviour is kept.
        sem = getattr(r, "semantic_type", "")
        if sem:
            parts.append(
                f'<text x="{cx:.1f}" y="{y + rh + 11:.1f}" fill="#b0bec5" '
                f'font-size="9" font-family="sans-serif" text-anchor="middle">'
                f'{_esc(sem)}</text>'
            )
        if r.role in label_rooms:
            parts.append(
                f'<text x="{cx:.1f}" y="{y - 4:.1f}" fill="{stroke}" font-size="11" '
                f'font-family="sans-serif" text-anchor="middle">{r.role}</text>'
            )
        # Boss marker (content layer): a small star glyph in the top-right.
        if getattr(r, "boss", False):
            parts.append(
                f'<text x="{x + rw - 3:.1f}" y="{y + 11:.1f}" fill="#ffd24a" '
                f'font-size="13" font-family="sans-serif" text-anchor="end">&#9733;</text>'
            )

    # ---- Gates (lock + key + connector) ----
    for g in spec.gates:
        lx, ly = px(g.lock_x), py(g.lock_y)
        kx, ky = px(g.key_x), py(g.key_y)
        # Dashed connector from key to lock
        parts.append(
            f'<line x1="{kx:.1f}" y1="{ky:.1f}" x2="{lx:.1f}" y2="{ly:.1f}" '
            f'stroke="#ffd24a" stroke-width="1.2" stroke-dasharray="6 4" '
            f'stroke-opacity="0.7"/>'
        )
        # Lock — red square
        parts.append(
            f'<rect x="{lx - 6:.1f}" y="{ly - 6:.1f}" width="12" height="12" '
            f'rx="2" fill="#e53935" stroke="#ff8a80" stroke-width="1"/>'
        )
        # Key — gold diamond
        parts.append(
            f'<path d="M {kx:.1f} {ky - 7:.1f} L {kx + 7:.1f} {ky:.1f} '
            f'L {kx:.1f} {ky + 7:.1f} L {kx - 7:.1f} {ky:.1f} Z" '
            f'fill="#ffd24a" stroke="#fff3c4" stroke-width="1"/>'
        )

    # ---- Legend ----
    parts.append(_legend(w, h, bool(spec.gates)))

    # ---- Scale bar (world units) ----
    parts.append(_scale_bar(scale, padding, h))

    parts.append("</svg>")
    return "".join(parts)


def _legend(w: float, h: float, has_gates: bool) -> str:
    items = [
        ("#2e7d32", "entrance"),
        ("#1565c0", "hub"),
        ("#8e24aa", "climax"),
        ("#8d6e63", "dead end"),
    ]
    if has_gates:
        items += [("#e53935", "lock"), ("#ffd24a", "key")]

    lx = w - 118
    ly = 14
    parts = [f'<g font-family="sans-serif" font-size="10" fill="#cdd6db">']
    parts.append(
        f'<rect x="{lx - 8:.0f}" y="{ly - 8:.0f}" width="118" '
        f'height="{len(items) * 16 + 8:.0f}" rx="4" fill="#0a0a12" '
        f'fill-opacity="0.75" stroke="#2a2a38"/>'
    )
    for i, (color, label) in enumerate(items):
        yy = ly + i * 16
        parts.append(
            f'<rect x="{lx:.0f}" y="{yy:.0f}" width="10" height="10" rx="2" fill="{color}"/>'
        )
        parts.append(f'<text x="{lx + 16:.0f}" y="{yy + 9:.0f}">{label}</text>')
    parts.append("</g>")
    return "".join(parts)


def _scale_bar(scale: float, padding: int, h: float) -> str:
    # Choose a round world length that renders ~80–160px.
    target_px = 120.0
    world = target_px / scale
    # Round to a 1/2/5 ×10^n value.
    import math
    mag = 10 ** math.floor(math.log10(max(world, 1.0)))
    for mult in (1, 2, 5, 10):
        if mult * mag >= world:
            world = mult * mag
            break
    bar_px = world * scale
    x0 = padding
    y0 = h - padding * 0.5
    return (
        f'<g stroke="#9aa7ad" stroke-width="2" fill="#cdd6db" '
        f'font-family="monospace" font-size="10">'
        f'<line x1="{x0:.0f}" y1="{y0:.0f}" x2="{x0 + bar_px:.0f}" y2="{y0:.0f}"/>'
        f'<text x="{x0:.0f}" y="{y0 - 5:.0f}" stroke="none">{world:.0f} u</text>'
        f'</g>'
    )


def _empty_svg(size: int) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {size} {size}"><rect width="{size}" height="{size}" '
        f'fill="#0f0f16"/><text x="{size // 2}" y="{size // 2}" fill="#667" '
        f'font-family="sans-serif" font-size="14" text-anchor="middle">'
        f'no layout</text></svg>'
    )
