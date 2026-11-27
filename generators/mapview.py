"""
generators/mapview.py
----------------------
Render a top-down 2D map of a ZoneSpec as a standalone SVG string.

This is a schematic floor-plan — rooms, corridors, and lock/key gates viewed
from directly above (the XY plane, Z ignored) — not a render of the 3D mesh.
It's cheap (no 3D, no extra dependencies) and gives an at-a-glance read of the
generated layout: where the entrance is, how rooms branch, where the climax
and any locked doors sit.

North is +Y. The SVG Y axis points down, so we flip Y when projecting so the
map reads with north up.

Given an `OutlineSet` (the real walls and ledges traced from the mesh by
`generators.mapgeom.extract_outline`), the map draws it first, under every
schematic annotation, and lightens the schematic so the true walls read
through. Without one, the output is byte-for-byte the plain schematic
(frozen in `tests/reference_mapview.py`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple

from .routing import built_line, corridor_route, tunnel_for, winding_legs
from .zone_spec import ZoneSpec

if TYPE_CHECKING:
    from .eqmap import PropMarks, SiteMarks
    from .mapgeom import OutlineSet


def corridor_path(c, rooms_by_id, rules=None) -> List[Tuple[float, float]]:
    """A corridor's centreline in plan: its route's waypoints, a winding leg (step 23,
    ``routing.winding_legs``) along its tunnel between its bend squares. Without a winding
    leg it is the route's waypoints, as it always was. A route line (step 25,
    ``CorridorSpec.path``, or an angled corridor's line: ``routing.built_line``) is the
    whole centreline, opening to opening, and wins over any winding leg. ``rules`` is the zone's tunnel (``routing.tunnel_for``); None is the stock
    one, right only for a zone whose Winding is 1."""
    line = built_line(c, rooms_by_id, rules)
    if line:
        return line
    route = corridor_route(c, rooms_by_id)
    wps = list(route.waypoints)
    lines = winding_legs(c, rooms_by_id, rules) if any(c.wind) else [None] * (len(wps) - 1)
    if not any(line is not None for line in lines):
        return wps
    out = [wps[0]]
    for k, line in enumerate(lines):
        for p in (line or []) + [wps[k + 1]]:
            if p != out[-1]:
                out.append(p)
    return out


_FEATURE_FILL = {"dais": "#8a7a4a", "pillar": "#c8ccd0", "plinth": "#b07a4c", "boulder": "#8a8f94"}


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

# Outline stroke by depth-band offset from the Main_Band. The Main_Band is a
# light grey (the EQ map's black would vanish on this background); the others
# are the in-game map's band colours (design "EQ map layers", BAND_COLOURS).
_BAND_STROKE = {
    0: "#d7dee2",
    +1: "#966400", +2: "#7f4000", +3: "#643200",
    -1: "#0000f0", -2: "#00007f", -3: "#007f00",
}


def _outline_group(outline: "OutlineSet", px, py) -> str:
    """One `<path>` per outline polyline: walls solid, ledges dashed."""
    offsets = {b.index: b.offset for b in outline.bands}
    parts = ['<g id="outline" fill="none" stroke-linecap="round" '
             'stroke-linejoin="round">']
    for pl in outline.polylines:
        d = " ".join(f'{"M" if i == 0 else "L"} {px(p[0]):.1f} {py(p[1]):.1f}'
                     for i, p in enumerate(pl.points))
        stroke = _BAND_STROKE.get(offsets.get(pl.band, 0), _BAND_STROKE[0])
        if pl.kind == "ledge":
            style = 'stroke-width="1.5" stroke-dasharray="6 4"'
        else:
            style = 'stroke-width="2"'
        parts.append(f'<path d="{d}" stroke="{stroke}" {style}/>')
    parts.append("</g>")
    return "".join(parts)


_SITE_STROKE = "#d08850"


def _sites_group(sites: "SiteMarks", px, py) -> str:
    """Each Structure's Footprint as an outline, each Site as a marker and label."""
    parts = ['<g id="sites">']
    for fp in sites.footprints:
        pts = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in fp.points)
        parts.append(f'<polygon class="site-footprint" points="{pts}" fill="{_SITE_STROKE}" '
                     f'fill-opacity="0.25" stroke="{_SITE_STROKE}" stroke-width="1.2"/>')
    for lab in sites.labels:
        cx, cy = px(lab.x), py(lab.y)
        parts.append(f'<circle class="site" cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="{_SITE_STROKE}" '
                     f'stroke="#0f0f16"><title>{_esc(lab.text)}</title></circle>')
        parts.append(f'<text class="site-label" x="{cx:.1f}" y="{cy - 8:.1f}" fill="#f0c090" '
                     f'font-size="10" font-family="sans-serif" text-anchor="middle">{_esc(lab.text)}</text>')
    parts.append("</g>")
    return "".join(parts)


_PROP_FILL = "#b48ad8"


def _props_group(props: "PropMarks", px, py) -> str:
    """Each floor Prop's Footprint as a small filled outline (its kind as the
    tooltip), every other Prop (wall, raised, ceiling) as a dot."""
    parts = ['<g id="props">']
    for fp in props.footprints:
        pts = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in fp.points)
        parts.append(f'<polygon class="prop-footprint" points="{pts}" fill="{_PROP_FILL}" '
                     f'fill-opacity="0.55" stroke="{_PROP_FILL}" stroke-width="0.8">'
                     f'<title>{_esc(fp.kind)}</title></polygon>')
    for x, y, _z, mount in props.points:
        if mount == "floor":
            continue
        parts.append(f'<circle class="prop" cx="{px(x):.1f}" cy="{py(y):.1f}" r="1.8" '
                     f'fill="{_PROP_FILL}"><title>{_esc(mount)}</title></circle>')
    parts.append("</g>")
    return "".join(parts)


# District hull colours by District id (districts spec Req 6.2): light fills so the
# rooms read through. A fourth District, should one ever exist, wraps round.
_DISTRICT_FILL = ("#4fc3f7", "#ffb74d", "#aed581", "#f48fb1")
_THRESHOLD_STROKE = "#e0c068"


def _district_fill(did: int) -> str:
    return _DISTRICT_FILL[did % len(_DISTRICT_FILL)]


def district_label(did: int, purpose: str) -> str:
    """How the map and the page name a District: 1-based, with its Purpose ("District 1 — tomb")."""
    return f"District {did + 1}" + (f" — {purpose}" if purpose else "")


def _convex_hull(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Andrew's monotone chain; counter-clockwise, no repeated end point."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: List[Tuple[float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: List[Tuple[float, float]] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _room_corners(r) -> List[Tuple[float, float]]:
    """A room's footprint points: its Outline's vertices when shaped, else its Box corners."""
    if r.outline is not None and r.outline.verts:
        return [(float(v[0]), float(v[1])) for v in r.outline.verts]
    hw, hd = r.width / 2, r.depth / 2
    return [(r.center_x - hw, r.center_y - hd), (r.center_x + hw, r.center_y - hd),
            (r.center_x + hw, r.center_y + hd), (r.center_x - hw, r.center_y + hd)]


def _districts_group(spec: ZoneSpec, px, py, labelled: bool = False) -> str:
    """One convex hull per District over its rooms' footprints, a light fill per District id
    (districts spec Req 6.2). Only drawn for a zone of two or more Districts. ``labelled`` (the
    layered map) also names each District ("District 2 — tomb") over its hull's top edge."""
    rooms_by_id = {r.id: r for r in spec.rooms}
    parts = ['<g id="districts">']
    labels: List[str] = []
    for d in spec.districts:
        pts: List[Tuple[float, float]] = []
        for rid in d.room_ids:
            r = rooms_by_id.get(rid)
            if r is not None:
                pts += _room_corners(r)
        hull = _convex_hull(pts)
        if len(hull) < 3:
            continue
        colour = _district_fill(d.id)
        poly = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in hull)
        parts.append(f'<polygon class="district" data-district="{d.id}" points="{poly}" '
                     f'fill="{colour}" fill-opacity="0.12" stroke="{colour}" stroke-opacity="0.6" '
                     f'stroke-width="1.5" stroke-dasharray="8 4" stroke-linejoin="round">'
                     f'<title>{_esc(district_label(d.id, d.purpose))}</title></polygon>')
        if labelled:
            lx = sum(px(x) for x, _ in hull) / len(hull)
            ly = max(12.0, min(py(y) for _, y in hull) - 6)
            labels.append(f'<text class="district-label" data-district="{d.id}" x="{lx:.1f}" y="{ly:.1f}" '
                          f'fill="{colour}" font-size="13" font-weight="bold" font-family="sans-serif" '
                          f'text-anchor="middle" stroke="#0f0f16" stroke-width="3" paint-order="stroke">'
                          f'{_esc(district_label(d.id, d.purpose))}</text>')
    parts += labels
    parts.append("</g>")
    return "".join(parts)


def frame_attrs(a: float, b: float, s: float) -> str:
    """The map's world-to-pixel frame as attributes on the root ``<svg>``: world (x, y)
    is drawn at ``u = a + s·x``, ``v = b − s·y``. Nothing drawn reads them; the page
    places Sockets by them (`web/src/sockets.ts`)."""
    return f' data-frame-a="{float(a)!r}" data-frame-b="{float(b)!r}" data-frame-s="{float(s)!r}"'


# Map layers (district races task 18): what the viewer's map dialog shows and hides. Each is
# one ``<g class="map-layer" data-layer=KEY>`` on the traced map (an outline given); the walls,
# corridors and room fills are the base, always drawn. (key, checkbox label, on by default).
MAP_LAYERS: Tuple[Tuple[str, str, bool], ...] = (
    ("districts", "Districts", True),
    ("races", "Races", True),
    ("links", "Links and drops", True),
    ("mixed", "Mixed rooms", False),
    ("gates", "Gates and pacing", False),
    ("types", "Room types", False),
    ("ids", "Room IDs", True),
    ("props", "Props and features", False),
    ("sites", "Sites", True),
)
# The EQ export view: what the in-client ``maps/*.txt`` carries, drawn from the same
# ``eqmap.build_map_file`` the pipeline writes, hidden until the dialog's preset shows it alone.
EQ_LAYER = ("eq", "EQ export view")
_EQ_PAPER = "#e8e1cc"

# A race's colour on the Races layer (its rooms' rings and tags, its corridors' lines).
_RACE_COLOUR = {
    "default": "#cfd8dc", "giant": "#7986cb", "goblin": "#d4e157", "kobold": "#ff8a65",
    "froglok": "#4db6ac", "lizardman": "#81c784", "gnoll": "#bcaaa4", "sarnak": "#ba68c8",
    "troll": "#66bb6a", "ogre": "#e57373", "dragon": "#ef5350",
}
_MIXED_STROKE = "#f06292"
_LINK_STROKE = {"threshold": _THRESHOLD_STROKE, "breach": "#4dd0e1", "return": "#81c784"}


def race_colour(race: str) -> str:
    return _RACE_COLOUR.get((race or "default").lower(), "#e0e0e0")


def link_kinds(spec: ZoneSpec) -> dict:
    """Each corridor joining two Districts: corridor id -> ``threshold``, ``breach`` or
    ``return``. A return is a flush breach every other link of its District pair drops into
    (``layout._add_return``'s case: the intruder's way back out)."""
    rooms = {r.id: r for r in spec.rooms}
    cross = {}
    for c in spec.corridors:
        a, b = rooms.get(c.from_room), rooms.get(c.to_room)
        if a is not None and b is not None and a.district != b.district:
            cross[c.id] = (c, tuple(sorted((a.district, b.district))))
    out = {}
    for cid, (c, pair) in cross.items():
        if c.threshold:
            out[cid] = "threshold"
            continue
        others = [o for o, p in cross.values() if p == pair and o.id != cid]
        out[cid] = "return" if (not c.drop and others and all(o.drop for o in others)) else "breach"
    return out


def mixed_rooms(spec: ZoneSpec) -> dict:
    """Host rooms an intruder's breaches enter (district races Req 9): room id -> the
    intruder's race, the lower intruder id's for a room two intruders breach (as
    ``builder._spill_hosts`` gives the decor its spill). Empty for a zone without intrusion."""
    from .semantics import room_race
    from .transitions import breach_hosts
    rooms = {r.id: r for r in spec.rooms}
    cors = {c.id: c for c in spec.corridors}
    best = {}
    for cid, host in breach_hosts(spec, rooms).items():
        c = cors[cid]
        them = rooms[c.to_room if c.from_room == host else c.from_room]
        if host not in best or them.district < best[host][0]:
            best[host] = (them.district, room_race(spec, them) or "default")
    return {rid: race for rid, (_d, race) in best.items()}


def _room_ring(r, px, py, scale, attrs: str) -> List[str]:
    """``r``'s footprint again, unfilled, with ``attrs`` (a Races or Mixed rooms mark)."""
    if r.outline is not None:
        return ['<polygon points="'
                + " ".join(f"{px(r.outline.verts[i][0]):.1f},{py(r.outline.verts[i][1]):.1f}" for i in loop)
                + f'" fill="none" {attrs}/>' for loop in r.outline.wall_loops()]
    rw, rh = r.width * scale, r.depth * scale
    return [f'<rect x="{px(r.center_x) - rw / 2:.1f}" y="{py(r.center_y) - rh / 2:.1f}" '
            f'width="{rw:.1f}" height="{rh:.1f}" rx="4" fill="none" {attrs}/>']


def _layer_group(key: str, label: str, on: bool, body: str, hidden: bool = False) -> str:
    return (f'<g id="layer-{key}" class="map-layer" data-layer="{key}" data-label="{_esc(label)}" '
            f'data-default="{int(on)}"' + (' display="none"' if hidden else "") + f'>{body}</g>')


def _eq_group(outline: "OutlineSet", spec: ZoneSpec, sites, props, px, py, w: float, h: float) -> str:
    """The EQ export view: every ``L`` line and ``P`` label ``eqmap.build_map_file`` writes for
    this outline, taken back to world (``map_to_world``) and drawn in its own colour on a light
    sheet (the Main_Band's lines are black), one ``<path>`` per file layer and colour. Hidden
    (``display="none"``) until the dialog shows it. Empty when the map file can't be built."""
    from .eqmap import build_map_file, map_to_world
    try:
        mf = build_map_file(outline, spec, "map", sites=sites, props=props)
    except Exception:
        return ""
    parts = [f'<rect class="eq-paper" x="0" y="0" width="{w:.0f}" height="{h:.0f}" fill="{_EQ_PAPER}"/>']
    for layer in mf.layers:
        by_colour: dict = {}
        for ln in layer.lines:
            x1, y1, _ = map_to_world(ln.x1, ln.y1, ln.z1)
            x2, y2, _ = map_to_world(ln.x2, ln.y2, ln.z2)
            by_colour.setdefault((ln.r, ln.g, ln.b), []).append(
                f"M {px(x1):.1f} {py(y1):.1f} L {px(x2):.1f} {py(y2):.1f}")
        for (r, g, b), segs in by_colour.items():
            parts.append(f'<path class="eq-line" data-eq-layer="{layer.index}" d="{" ".join(segs)}" '
                         f'fill="none" stroke="rgb({r},{g},{b})" stroke-width="1.5" stroke-linecap="round"/>')
        for lab in layer.labels:
            x, y, _ = map_to_world(lab.x, lab.y, lab.z)
            rgb = f"rgb({lab.r},{lab.g},{lab.b})"
            parts.append(f'<circle class="eq-mark" cx="{px(x):.1f}" cy="{py(y):.1f}" r="2" fill="{rgb}"/>')
            parts.append(f'<text class="eq-label" data-eq-layer="{layer.index}" x="{px(x) + 4:.1f}" '
                         f'y="{py(y) + 4:.1f}" fill="{rgb}" font-size="11" '
                         f'font-family="sans-serif" font-weight="bold">{_esc(lab.text)}</text>')
    key, label = EQ_LAYER
    return _layer_group(key, label, False, "".join(parts), hidden=True)


def render_map_svg(spec: ZoneSpec, size: int = 720, padding: int = 40,
                   outline: Optional["OutlineSet"] = None,
                   sites: Optional["SiteMarks"] = None,
                   props: Optional["PropMarks"] = None) -> str:
    """
    Build an SVG top-down map of the zone. `size` is the max pixel dimension;
    the map preserves the zone's aspect ratio and is centred in a square-ish
    canvas. Returns the SVG document as a string.

    `outline` (optional) is the traced wall/ledge outline of the built mesh.
    When given, it is drawn directly over the background, corridors follow
    their `corridor_route` waypoints, room fills are lightened, the legend
    gains `wall`/`ledge`, and the frame also covers `outline.bounds`.

    With an outline the map is also LAYERED (district races task 18): the
    walls, corridors and room fills are drawn at the top level, every other
    mark in one ``<g class="map-layer" data-layer=KEY data-label=...
    data-default=0|1>`` per ``MAP_LAYERS`` entry that has anything to draw,
    then the EQ export view (``EQ_LAYER``, hidden). The viewer's map dialog
    shows and hides them; each legend row is a ``<g class="legend-row"
    data-layer=KEY>`` it restacks. Without an outline the map is the plain
    schematic it always was (frozen in `tests/reference_mapview.py`).

    `sites` (optional, `generators.eqmap.SiteMarks`) draws each Structure's
    Footprint and a marker and label at each Site, over the outline; the
    legend gains `site`. Without it the output is unchanged.

    `props` (optional, `generators.eqmap.PropMarks`, room-decor Req 10.4)
    draws each floor Prop's Footprint and a dot at every other Prop, over the
    rooms; the legend gains `prop`. Without it the output is unchanged.
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
    if outline is not None:
        bx0, by0, _, bx1, by1, _ = outline.bounds
        xs += [bx0, bx1]
        ys += [by0, by1]
    if sites:
        for fp in sites.footprints:
            xs += [p[0] for p in fp.points]
            ys += [p[1] for p in fp.points]
        xs += [lab.x for lab in sites.labels]
        ys += [lab.y for lab in sites.labels]

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

    # Layered (an outline given): each mark goes to its layer's list, drawn after the base.
    # Plain: straight into ``parts``, in the order the frozen schematic draws it.
    layered = outline is not None
    lay = {key: [] for key, _label, _on in MAP_LAYERS}
    parts: List[str] = []

    def put(layer: str, s: str) -> None:
        (lay[layer] if layered else parts).append(s)

    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" '
        f'viewBox="0 0 {w:.0f} {h:.0f}"{frame_attrs(padding - min_x * scale, padding + max_y * scale, scale)}>'
    )
    parts.append(f'<rect x="0" y="0" width="{w:.0f}" height="{h:.0f}" fill="#0f0f16"/>')

    # ---- True outline (under every schematic annotation) ----
    if outline is not None:
        parts.append(_outline_group(outline, px, py))

    # ---- District hulls (after the outline, under the corridors and rooms) ----
    has_districts = len(spec.districts) >= 2
    if has_districts:
        if layered:
            lay["districts"].append(_districts_group(spec, px, py, labelled=True))
        else:
            parts.append(_districts_group(spec, px, py))

    rooms_by_id = {r.id: r for r in spec.rooms}
    # ---- Corridors (drawn first, under the rooms) ----
    if outline is None:
        for c in spec.corridors:
            x1, y1 = px(c.from_x), py(c.from_y)
            x2, y2 = px(c.to_x), py(c.to_y)
            cw = max(2.0, c.width * scale)
            if c.threshold:
                # A Threshold (the one corridor joining two Districts): heavier.
                parts.append(
                    f'<line class="threshold" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" '
                    f'y2="{y2:.1f}" stroke="{_THRESHOLD_STROKE}" stroke-width="{cw * 1.5 + 2:.1f}" '
                    f'stroke-linecap="round"/>'
                )
                continue
            parts.append(
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="#5c6b73" stroke-width="{cw:.1f}" stroke-linecap="round"/>'
            )
    else:
        # Over a real outline, a corridor is a thin centreline along the route
        # the geometry builder actually cut (straight / Z / L / U, each winding
        # leg along its tunnel), not a chord. A Threshold keeps its class but is
        # drawn as any corridor is: the Links layer marks it.
        for c in spec.corridors:
            line = corridor_path(c, rooms_by_id, tunnel_for(c, spec))
            pts = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in line)
            cw = max(1.0, c.width * scale * 0.25)
            cls = 'class="threshold" ' if c.threshold else ""
            parts.append(
                f'<polyline {cls}points="{pts}" fill="none" stroke="#5c6b73" '
                f'stroke-opacity="0.45" stroke-width="{cw:.1f}" '
                f'stroke-linecap="round" stroke-linejoin="round"/>'
            )
    room_opacity = "0.82" if outline is None else "0.3"

    # ---- Rooms ----
    label_rooms = {"entrance", "hub", "climax", "deadend"}
    for r in spec.rooms:
        rw = r.width * scale
        rh = r.depth * scale
        x = px(r.center_x) - rw / 2
        y = py(r.center_y) - rh / 2
        fill = _ROLE_FILL.get(r.role, _ROLE_FILL["standard"])
        stroke = _ROLE_STROKE.get(r.role, _ROLE_STROKE["standard"])
        if r.outline is not None:
            # A shaped room: its real walls, not its Box (step 8).
            for loop in r.outline.wall_loops():
                pts = " ".join(f"{px(r.outline.verts[i][0]):.1f},{py(r.outline.verts[i][1]):.1f}"
                               for i in loop)
                parts.append(
                    f'<polygon points="{pts}" fill="{fill}" fill-opacity="{room_opacity}" '
                    f'stroke="{stroke}" stroke-width="1.5"/>'
                )
        else:
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{rw:.1f}" height="{rh:.1f}" '
                f'rx="4" fill="{fill}" fill-opacity="{room_opacity}" stroke="{stroke}" '
                f'stroke-width="1.5"/>'
            )
        # What stands in it, and its points of interest (step 9).
        for f in sorted(r.features, key=lambda f: f.kind != "dais"):
            pts = " ".join(f"{px(p[0]):.1f},{py(p[1]):.1f}" for p in f.plan)
            colour = _FEATURE_FILL.get(f.kind, "#6d6d6d")
            put("props", f'<polygon class="feature" points="{pts}" fill="{colour}" fill-opacity="0.9"/>')
        for poi in r.pois:
            put("props", f'<circle class="poi" cx="{px(poi.x):.1f}" cy="{py(poi.y):.1f}" r="4" fill="#4aa3ff" '
                         f'stroke="#0f0f16"><title>{_esc(poi.purpose)}</title></circle>')
        # Depth number in the room centre
        cx, cy = px(r.center_x), py(r.center_y)
        put("gates",
            f'<text x="{cx:.1f}" y="{cy + 4:.1f}" fill="#e8eef2" font-size="12" '
            f'font-family="monospace" text-anchor="middle">{r.graph_depth}</text>'
        )
        # Room id in the box's top-left corner so the map matches the 3D view —
        # a human can point at a room in either and know exactly which room_N it
        # is. Small monospace, slightly dimmed to sit under the depth number.
        put("ids",
            f'<text x="{x + 3:.1f}" y="{y + 11:.1f}" fill="#9fb2bd" font-size="9" '
            f'font-family="monospace" text-anchor="start">{_esc(r.id)}</text>'
        )
        # Semantic type label below the room (content layer). Falls back to the
        # pacing role label for un-themed zones so existing behaviour is kept.
        sem = getattr(r, "semantic_type", "")
        if sem:
            put("types",
                f'<text x="{cx:.1f}" y="{y + rh + 11:.1f}" fill="#b0bec5" '
                f'font-size="9" font-family="sans-serif" text-anchor="middle">'
                f'{_esc(sem)}</text>'
            )
        if r.role in label_rooms:
            put("gates",
                f'<text x="{cx:.1f}" y="{y - 4:.1f}" fill="{stroke}" font-size="11" '
                f'font-family="sans-serif" text-anchor="middle">{r.role}</text>'
            )
        # Boss marker (content layer): a small star glyph in the top-right.
        if getattr(r, "boss", False):
            put("gates",
                f'<text x="{x + rw - 3:.1f}" y="{y + 11:.1f}" fill="#ffd24a" '
                f'font-size="13" font-family="sans-serif" text-anchor="end">&#9733;</text>'
            )

    # ---- Races, links between Districts, mixed rooms (the layered map only) ----
    races: List[str] = []
    kinds: dict = {}
    mixed: dict = {}
    if layered:
        if any(d.race for d in spec.districts or ()):
            from .semantics import corridor_race, room_race
            for r in spec.rooms:
                race = room_race(spec, r) or "default"
                races.append(race)
                colour = race_colour(race)
                lay["races"] += _room_ring(r, px, py, scale,
                                           f'class="race-ring" data-race="{_esc(race)}" stroke="{colour}" '
                                           f'stroke-width="2.5" stroke-opacity="0.9"')
                lay["races"].append(
                    f'<text class="race-tag" data-room="{_esc(r.id)}" '
                    f'x="{px(r.center_x) - r.width * scale / 2 + 3:.1f}" '
                    f'y="{py(r.center_y) + r.depth * scale / 2 - 4:.1f}" fill="{colour}" font-size="10" '
                    f'font-family="sans-serif" font-weight="bold" text-anchor="start">{_esc(race)}</text>')
            for c in spec.corridors:
                race = corridor_race(spec, c, rooms_by_id) or "default"
                races.append(race)
                pts = " ".join(f"{px(x):.1f},{py(y):.1f}"
                               for x, y in corridor_path(c, rooms_by_id, tunnel_for(c, spec)))
                lay["races"].append(
                    f'<polyline class="race-link" data-race="{_esc(race)}" points="{pts}" fill="none" '
                    f'stroke="{race_colour(race)}" stroke-opacity="0.85" '
                    f'stroke-width="{max(1.5, c.width * scale * 0.25):.1f}" stroke-linecap="round" '
                    f'stroke-linejoin="round"><title>{_esc(c.id)}: {_esc(race)}</title></polyline>')
        if has_districts:
            kinds = link_kinds(spec)
            for c in spec.corridors:
                kind = kinds.get(c.id)
                if kind is None:
                    continue
                pts = " ".join(f"{px(x):.1f},{py(y):.1f}"
                               for x, y in corridor_path(c, rooms_by_id, tunnel_for(c, spec)))
                cw = max(1.0, c.width * scale * 0.25)
                dash = ' stroke-dasharray="6 4"' if kind == "return" else ""
                lay["links"].append(
                    f'<polyline class="link link-{kind}" points="{pts}" fill="none" '
                    f'stroke="{_LINK_STROKE[kind]}" stroke-opacity="0.9" stroke-width="{cw * 2.5 + 1:.1f}" '
                    f'stroke-linecap="round" stroke-linejoin="round"{dash}>'
                    f'<title>{kind} ({_esc(c.id)})</title></polyline>')
            mixed = mixed_rooms(spec)
            for r in spec.rooms:
                race = mixed.get(r.id)
                if race is None:
                    continue
                lay["mixed"] += _room_ring(r, px, py, scale,
                                           f'class="mixed-ring" stroke="{_MIXED_STROKE}" '
                                           f'stroke-width="2" stroke-dasharray="5 4"')
                lay["mixed"].append(
                    f'<text class="mixed-tag" data-room="{_esc(r.id)}" '
                    f'x="{px(r.center_x) + r.width * scale / 2 - 3:.1f}" '
                    f'y="{py(r.center_y) + r.depth * scale / 2 - 4:.1f}" fill="{_MIXED_STROKE}" font-size="9" '
                    f'font-family="sans-serif" text-anchor="end">mixed: {_esc(race)}</text>')

    # ---- Drops (district races step 31): a down-pointing mark at each drop's lower end ----
    drops = [c for c in spec.corridors if getattr(c, "drop", 0)]
    if drops:
        from .geometry import drop_end
        for c in drops:
            end = drop_end(c, rooms_by_id)
            if end is None:
                continue
            dx, dy = (px(c.to_x), py(c.to_y)) if end == "to" else (px(c.from_x), py(c.from_y))
            put("links",
                f'<path class="drop" d="M {dx - 6:.1f} {dy - 5:.1f} L {dx + 6:.1f} {dy - 5:.1f} '
                f'L {dx:.1f} {dy + 6:.1f} Z" fill="{_DROP_FILL}" stroke="#0f0f16" stroke-width="1">'
                f'<title>drop {c.drop:.0f} u ({c.id})</title></path>'
            )
            if layered:
                lay["links"].append(
                    f'<text class="drop-height" x="{dx + 8:.1f}" y="{dy + 4:.1f}" fill="{_DROP_FILL}" '
                    f'font-size="10" font-family="sans-serif" font-weight="bold">{c.drop:.0f} u</text>')

    # ---- Gates (lock + key + connector) ----
    for g in spec.gates:
        lx, ly = px(g.lock_x), py(g.lock_y)
        kx, ky = px(g.key_x), py(g.key_y)
        # Dashed connector from key to lock
        put("gates",
            f'<line x1="{kx:.1f}" y1="{ky:.1f}" x2="{lx:.1f}" y2="{ly:.1f}" '
            f'stroke="#ffd24a" stroke-width="1.2" stroke-dasharray="6 4" '
            f'stroke-opacity="0.7"/>'
        )
        # Lock — red square
        put("gates",
            f'<rect x="{lx - 6:.1f}" y="{ly - 6:.1f}" width="12" height="12" '
            f'rx="2" fill="#e53935" stroke="#ff8a80" stroke-width="1"/>'
        )
        # Key — gold diamond
        put("gates",
            f'<path d="M {kx:.1f} {ky - 7:.1f} L {kx + 7:.1f} {ky:.1f} '
            f'L {kx:.1f} {ky + 7:.1f} L {kx - 7:.1f} {ky:.1f} Z" '
            f'fill="#ffd24a" stroke="#fff3c4" stroke-width="1"/>'
        )

    # ---- Legend ----
    # Where a door could hang: a bar across the corridor at each Frame (step 9).
    for cor in spec.corridors:
        t = cor.transition
        if t is None or t.form != "frame":
            continue
        hw = cor.width / 2
        x0, y0, x1, y1 = (t.x, t.y - hw, t.x, t.y + hw) if t.along_x else (t.x - hw, t.y, t.x + hw, t.y)
        put("gates", f'<line class="door-spot" x1="{px(x0):.1f}" y1="{py(y0):.1f}" x2="{px(x1):.1f}" '
                     f'y2="{py(y1):.1f}" stroke="{_DOOR_SPOT}" stroke-width="3"><title>door spot</title></line>')

    if props:
        put("props", _props_group(props, px, py))
    if sites:
        put("sites", _sites_group(sites, px, py))

    has_doors = any(c.transition is not None and c.transition.form == "frame" for c in spec.corridors)
    districts = ([(_district_fill(d.id), district_label(d.id, d.purpose)) for d in spec.districts]
                 if has_districts else [])
    if layered:
        # In MAP_LAYERS order, so the later ones read over the earlier.
        for key, label, on in MAP_LAYERS:
            if lay[key]:
                parts.append(_layer_group(key, label, on, "".join(lay[key])))
        parts.append(_layered_legend(
            w, has_gates=bool(spec.gates), has_doors=has_doors, has_sites=bool(sites),
            has_props=bool(lay["props"]), districts=districts, has_drops=bool(drops),
            races=sorted(set(races)), links=sorted(set(kinds.values())), has_mixed=bool(mixed)))
    else:
        parts.append(_legend(w, h, bool(spec.gates), outline is not None, has_doors, bool(sites),
                             bool(props), districts, has_drops=bool(drops)))

    # ---- Scale bar (world units) ----
    parts.append(_scale_bar(scale, padding, h))
    if layered:
        parts.append(_eq_group(outline, spec, sites, props, px, py, w, h))

    parts.append("</svg>")
    return "".join(parts)


_DOOR_SPOT = "#e0a458"
_DROP_FILL = "#ff7043"


def _legend(w: float, h: float, has_gates: bool, has_outline: bool = False, has_doors: bool = False,
            has_sites: bool = False, has_props: bool = False,
            districts: Optional[List[Tuple[str, str]]] = None, has_drops: bool = False) -> str:
    """The key, top right. *districts* ((colour, "District 1 — tomb") in id order, only for a
    zone of two or more Districts) adds a swatch per District and a ``threshold`` line, and
    widens the box to fit; without it the legend is unchanged."""
    items = [
        ("#2e7d32", "entrance"),
        ("#1565c0", "hub"),
        ("#8e24aa", "climax"),
        ("#8d6e63", "dead end"),
    ]
    if has_gates:
        items += [("#e53935", "lock"), ("#ffd24a", "key")]
    if has_doors:
        items.append((_DOOR_SPOT, "door spot"))
    if has_sites:
        items.append((_SITE_STROKE, "site"))
    if has_props:
        items.append((_PROP_FILL, "prop"))
    # Outline entries get a line swatch (solid wall, dashed ledge), not a box.
    # (stroke, width, extra attributes, label)
    lines = ([(_BAND_STROKE[0], 2, "", "wall"), (_BAND_STROKE[0], 2, ' stroke-dasharray="4 3"', "ledge")]
             if has_outline else [])
    if districts:
        items += list(districts)
        lines.append((_THRESHOLD_STROKE, 4, "", "threshold"))
    if has_drops:
        items.append((_DROP_FILL, "drop (one way)"))

    # 118 wide; District labels are longer (about 6 px a character at 10 px sans).
    bw = 118 if not districts else max(118, 30 + 6 * max(len(lab) for _, lab in items))
    lx = w - bw
    ly = 14
    parts = [f'<g font-family="sans-serif" font-size="10" fill="#cdd6db">']
    parts.append(
        f'<rect x="{lx - 8:.0f}" y="{ly - 8:.0f}" width="{bw}" '
        f'height="{(len(items) + len(lines)) * 16 + 8:.0f}" rx="4" fill="#0a0a12" '
        f'fill-opacity="0.75" stroke="#2a2a38"/>'
    )
    for i, (color, label) in enumerate(items):
        yy = ly + i * 16
        parts.append(
            f'<rect x="{lx:.0f}" y="{yy:.0f}" width="10" height="10" rx="2" fill="{color}"/>'
        )
        parts.append(f'<text x="{lx + 16:.0f}" y="{yy + 9:.0f}">{_esc(label)}</text>')
    for j, (stroke, sw, dash, label) in enumerate(lines):
        yy = ly + (len(items) + j) * 16
        parts.append(
            f'<line x1="{lx:.0f}" y1="{yy + 5:.0f}" x2="{lx + 10:.0f}" y2="{yy + 5:.0f}" '
            f'stroke="{stroke}" stroke-width="{sw}"{dash}/>'
        )
        parts.append(f'<text x="{lx + 16:.0f}" y="{yy + 9:.0f}">{label}</text>')
    parts.append("</g>")
    return "".join(parts)


def _layered_legend(w: float, *, has_gates: bool, has_doors: bool, has_sites: bool, has_props: bool,
                    districts: List[Tuple[str, str]], has_drops: bool, races: List[str],
                    links: List[str], has_mixed: bool) -> str:
    """The layered map's key, top right: one ``<g class="legend-row" data-layer=KEY>`` per row,
    placed by ``transform`` (row ``i`` at ``16 i``), so the map dialog can drop the rows of a
    hidden layer and restack the rest; ``base`` rows (room roles, walls) always show. The box
    (``legend-box``) fits every row; the dialog resizes it to the rows it keeps."""
    rows: List[Tuple[str, str, str]] = []           # (layer, swatch markup, label)

    def box(colour: str) -> str:
        return f'<rect x="0" y="0" width="10" height="10" rx="2" fill="{colour}"/>'

    def line(stroke: str, sw: float, dash: str = "") -> str:
        return f'<line x1="0" y1="5" x2="10" y2="5" stroke="{stroke}" stroke-width="{sw}"{dash}/>'

    for colour, label in (("#2e7d32", "entrance"), ("#1565c0", "hub"), ("#8e24aa", "climax"),
                          ("#8d6e63", "dead end")):
        rows.append(("base", box(colour), label))
    rows.append(("base", line(_BAND_STROKE[0], 2), "wall"))
    rows.append(("base", line(_BAND_STROKE[0], 2, ' stroke-dasharray="4 3"'), "ledge"))
    for colour, label in districts:
        rows.append(("districts", box(colour), label))
    for race in races:
        rows.append(("races", line(race_colour(race), 3), race))
    names = {"threshold": "threshold", "breach": "breach (District link)", "return": "return (way back)"}
    for kind in ("threshold", "breach", "return"):
        if kind in links:
            dash = ' stroke-dasharray="4 3"' if kind == "return" else ""
            rows.append(("links", line(_LINK_STROKE[kind], 4, dash), names[kind]))
    if has_drops:
        rows.append(("links", box(_DROP_FILL), "drop (one way, u)"))
    if has_mixed:
        rows.append(("mixed", line(_MIXED_STROKE, 2, ' stroke-dasharray="4 3"'), "mixed room"))
    if has_gates:
        rows += [("gates", box("#e53935"), "lock"), ("gates", box("#ffd24a"), "key")]
    if has_doors:
        rows.append(("gates", box(_DOOR_SPOT), "door spot"))
    if has_props:
        rows.append(("props", box(_PROP_FILL), "prop / feature"))
    if has_sites:
        rows.append(("sites", box(_SITE_STROKE), "site"))

    bw = max(118, 30 + 6 * max(len(label) for _, _, label in rows))
    lx, ly = w - bw, 14
    parts = ['<g id="legend" font-family="sans-serif" font-size="10" fill="#cdd6db">',
             f'<rect class="legend-box" x="{lx - 8:.0f}" y="{ly - 8:.0f}" width="{bw}" '
             f'height="{len(rows) * 16 + 8:.0f}" rx="4" fill="#0a0a12" fill-opacity="0.75" stroke="#2a2a38"/>']
    for i, (layer, swatch, label) in enumerate(rows):
        parts.append(f'<g class="legend-row" data-layer="{layer}" transform="translate({lx:.0f} {ly + i * 16:.0f})">'
                     f'{swatch}<text x="16" y="9">{_esc(label)}</text></g>')
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
