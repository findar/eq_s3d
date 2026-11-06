"""
generators/topology/draw.py
---------------------------
SVG drawings of Topology_Graphs and of rules (roadmap step 6, Req 3.5;
design "The dry run, the diagrams and the guide").

Plain SVG strings, no drawing library. Three things:

- :func:`graph_svg` draws a graph: a start graph, or a grown one (a built
  zone's graph, for its sidecar trace).
- :func:`rule_svg` draws one rule as before -> after: the match on the left,
  the replacement on the right, and a stub "outside" node per match node
  standing for its edges to the rest of the graph. On the right, dashed lines
  run from each stub to the nodes its edges reattach to, numbered in order
  when they split.
- :func:`rule_set_html` writes one page for a set: its start graph, the
  recipe, a card per rule, and the rules of every layer that fits it.

How a drawing reads (the page's legend says the same):

- **Nodes:** fill and outline by kind (an ``Area`` is a dashed outline with no
  fill; the entrance has a double ring), radius by Size_Class. A district
  other than 0 gets a ``d<n>`` badge.
- **Edges:** ``above`` / ``below`` get an arrowhead at the higher end (the
  arrow points up the slope); ``level`` gets a double tick at the middle; a
  ``threshold`` tag gets a red bar across the middle.
- In a rule, a bold id is the same graph node on both sides (kept); other
  replacement ids are new nodes.

The layout is deterministic: breadth-first layers from a root, then a fixed
number of spring (Fruchterman-Reingold) steps, then turned so its long axis
runs left to right with the root on the left. No randomness, so a page
redrawn from the same files is byte-identical.
"""

from __future__ import annotations

import html
import math
from collections import deque
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from generators.topology.graph import AREA, ENTRANCE, ROOM_KINDS, SIZE_CLASSES, Edge, Node, TopologyGraph

Point = Tuple[float, float]

# ---------------------------------------------------------------------------
# Look
# ---------------------------------------------------------------------------

#: kind -> (fill, outline). Light fills, so the id inside reads dark in both themes.
KIND_STYLE: Dict[str, Tuple[str, str]] = {
    "entrance": ("#9ed99e", "#2e7d32"),
    "chamber": ("#a9cbeb", "#1f5f99"),
    "passage": ("#dcdcdc", "#6b6b6b"),
    "hub": ("#f4cd7f", "#a66f00"),
    "lair": ("#eeaaaa", "#a83232"),
    "hall": ("#cfb2e6", "#6a3d9a"),
    "deep": ("#93d9d1", "#00695c"),
}
#: Extra kinds a set declares take these, in sorted order.
EXTRA_STYLES: Tuple[Tuple[str, str], ...] = (
    ("#f7b98b", "#b3541e"), ("#c5e1a5", "#558b2f"), ("#f8bbd0", "#ad1457"),
    ("#b2ebf2", "#00838f"), ("#e6ee9c", "#827717"), ("#d7ccc8", "#5d4037"),
)
SIZE_RADIUS: Dict[str, float] = {"tiny": 10, "small": 13, "medium": 16, "large": 20, "huge": 25}
AREA_RADIUS = 15
STUB_RADIUS = 8
UP_COLOUR = "#d35400"
THRESHOLD_COLOUR = "#c0392b"

#: Shared CSS: the page puts it in <head>; a standalone SVG carries it.
STYLE = """
.tg { --ink: #1d1d1f; --muted: #6e6e73; --line: #55555a; --faint: #8a8a91; --bg: #ffffff;
      --card: #f6f6f8; --rule: #d9d9de; }
@media (prefers-color-scheme: dark) {
  .tg { --ink: #ececf0; --muted: #a8a8b0; --line: #b4b4bc; --faint: #75757d; --bg: #1b1b1e;
        --card: #242428; --rule: #3a3a40; }
}
.tg text { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; fill: var(--ink); }
.tg .nid { font-size: 10px; fill: #111; text-anchor: middle; dominant-baseline: central; }
.tg .nid.area { fill: var(--ink); }
.tg .nid.kept { font-weight: 700; }
.tg .cap { font-size: 9.5px; fill: var(--muted); text-anchor: middle; }
.tg .lbl { font-size: 10px; fill: var(--muted); text-anchor: middle; dominant-baseline: central; }
.tg .ttl { font-size: 12px; font-weight: 600; fill: var(--ink); }
.tg .edge { stroke: var(--line); stroke-width: 1.8; fill: none; }
.tg .hops { stroke: var(--faint); stroke-width: 1.4; stroke-dasharray: 2 3; fill: none; }
.tg .out { stroke: var(--faint); stroke-width: 1.3; stroke-dasharray: 5 4; fill: none; }
.tg .stub { stroke: var(--faint); stroke-width: 1.2; stroke-dasharray: 2 2; fill: var(--bg); }
.tg .areanode { stroke: var(--line); stroke-width: 1.6; stroke-dasharray: 4 3; fill: none; }
.tg .arrowpanel { stroke: var(--muted); stroke-width: 2; fill: none; }
"""


def kind_style(kind: str, extra_kinds: Sequence[str] = ()) -> Tuple[str, str]:
    """(fill, outline) for a kind; extra kinds cycle through EXTRA_STYLES."""
    if kind in KIND_STYLE:
        return KIND_STYLE[kind]
    extras = sorted(set(extra_kinds) | {kind})
    return EXTRA_STYLES[extras.index(kind) % len(EXTRA_STYLES)]


def node_radius(node: Node) -> float:
    if not node.is_room:
        return AREA_RADIUS
    return SIZE_RADIUS.get(node.size or "medium", SIZE_RADIUS["medium"])


def _esc(s: object) -> str:
    return html.escape(str(s), quote=True)


def _f(x: float) -> str:
    return f"{x:.1f}"


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def layout(ids: Sequence[str], edges: Iterable[Tuple[str, str]], root: Optional[str] = None,
           iterations: int = 300) -> Dict[str, Point]:
    """Deterministic positions in abstract units (edge length about 1).

    Breadth-first layers from ``root`` (or the first id) seed the positions;
    spring steps relax them; the result is turned so its long axis is
    horizontal with the root on the left.
    """
    ids = list(ids)
    if not ids:
        return {}
    if len(ids) == 1:
        return {ids[0]: (0.0, 0.0)}
    idx = {n: i for i, n in enumerate(ids)}
    adj: Dict[str, List[str]] = {n: [] for n in ids}
    pairs: List[Tuple[int, int]] = []
    for a, b in edges:
        if a in idx and b in idx and a != b:
            adj[a].append(b)
            adj[b].append(a)
            pairs.append((idx[a], idx[b]))
    root = root if root in idx else ids[0]

    # Breadth-first layers; components after the first continue the layering.
    layer: Dict[str, int] = {}
    base = 0
    for start in [root] + ids:
        if start in layer:
            continue
        layer[start] = base
        q = deque([start])
        while q:
            u = q.popleft()
            for v in sorted(adj[u]):
                if v not in layer:
                    layer[v] = layer[u] + 1
                    q.append(v)
        base = max(layer.values()) + 1
    by_layer: Dict[int, List[str]] = {}
    for n in ids:
        by_layer.setdefault(layer[n], []).append(n)
    pos = np.zeros((len(ids), 2))
    for l, members in by_layer.items():
        for j, n in enumerate(members):
            pos[idx[n]] = (float(l), j - (len(members) - 1) / 2 + 0.013 * (idx[n] % 7))

    # Fruchterman-Reingold with a cooling step and a weak pull to the centre.
    k = 1.0
    e = np.array(pairs, dtype=int).reshape(-1, 2)
    for it in range(iterations):
        delta = pos[:, None, :] - pos[None, :, :]
        dist = np.sqrt((delta ** 2).sum(-1)) + 1e-9
        np.fill_diagonal(dist, np.inf)
        disp = (delta / dist[..., None] * (k * k / dist)[..., None]).sum(1)
        if len(e):
            d = pos[e[:, 0]] - pos[e[:, 1]]
            dl = np.sqrt((d ** 2).sum(-1)) + 1e-9
            f = d / dl[:, None] * (dl * dl / k)[:, None]
            np.add.at(disp, e[:, 0], -f)
            np.add.at(disp, e[:, 1], f)
        disp -= 0.05 * (pos - pos.mean(0))
        t = 0.12 * (1 - it / iterations) + 0.005
        ln = np.sqrt((disp ** 2).sum(-1)) + 1e-9
        pos += disp / ln[:, None] * np.minimum(ln, t)[:, None]

    # Long axis horizontal, root on the left, root's half on top (for stability).
    pos -= pos.mean(0)
    if len(ids) > 2:
        cov = pos.T @ pos
        w, v = np.linalg.eigh(cov)
        axis = v[:, int(np.argmax(w))]
        rot = np.array([[axis[0], axis[1]], [-axis[1], axis[0]]])
        pos = pos @ rot.T
    elif len(ids) == 2:
        d = pos[1] - pos[0]
        ang = -math.atan2(d[1], d[0])
        c, s = math.cos(ang), math.sin(ang)
        pos = pos @ np.array([[c, -s], [s, c]]).T
    r = idx[root]
    if pos[r, 0] > 0:
        pos[:, 0] *= -1
    if pos[r, 1] > 1e-6:
        pos[:, 1] *= -1
    return {n: (float(pos[i, 0]), float(pos[i, 1])) for n, i in idx.items()}


def _fit(points: Mapping[str, Point], width: float, height: float, margin: float,
         max_scale: float = 95.0) -> Dict[str, Point]:
    """Scale and centre abstract positions into a pixel box (aspect kept)."""
    if not points:
        return {}
    xs = [p[0] for p in points.values()]
    ys = [p[1] for p in points.values()]
    dx = max(xs) - min(xs)
    dy = max(ys) - min(ys)
    s = min((width - 2 * margin) / dx if dx > 1e-9 else max_scale,
            (height - 2 * margin) / dy if dy > 1e-9 else max_scale, max_scale)
    cx = (max(xs) + min(xs)) / 2
    cy = (max(ys) + min(ys)) / 2
    return {n: (width / 2 + (x - cx) * s, height / 2 + (y - cy) * s) for n, (x, y) in points.items()}


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

def _trim(p: Point, q: Point, rp: float, rq: float) -> Optional[Tuple[Point, Point]]:
    """The p-q segment cut back to the two circles' rims."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    d = math.hypot(dx, dy)
    if d <= rp + rq + 1:
        return None
    ux, uy = dx / d, dy / d
    return (p[0] + ux * rp, p[1] + uy * rp), (q[0] - ux * rq, q[1] - uy * rq)


def _edge_svg(p: Point, q: Point, rp: float, rq: float, rel: str = "any",
              tags: Iterable[str] = (), cls: str = "edge") -> str:
    """An edge read from p: ``rel`` says where q sits relative to p."""
    seg = _trim(p, q, rp, rq)
    if seg is None:
        return ""
    (x1, y1), (x2, y2) = seg
    out = [f'<line class="{cls}" x1="{_f(x1)}" y1="{_f(y1)}" x2="{_f(x2)}" y2="{_f(y2)}"/>']
    d = math.hypot(x2 - x1, y2 - y1) or 1.0
    ux, uy = (x2 - x1) / d, (y2 - y1) / d
    nx, ny = -uy, ux
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    if rel in ("above", "below"):
        # Arrowhead at the higher end: q when q is above p, else p.
        if rel == "above":
            tx, ty, sx, sy = x2, y2, ux, uy
        else:
            tx, ty, sx, sy = x1, y1, -ux, -uy
        bx, by = tx - sx * 10, ty - sy * 10
        pts = [(tx, ty), (bx + nx * 5, by + ny * 5), (bx - nx * 5, by - ny * 5)]
        out.append('<polygon fill="%s" points="%s"><title>%s</title></polygon>' % (
            UP_COLOUR, " ".join(f"{_f(a)},{_f(b)}" for a, b in pts),
            "the arrow points to the higher room"))
    elif rel == "level":
        for off in (-2.5, 2.5):
            ax, ay = mx + ux * off, my + uy * off
            out.append(f'<line stroke="{UP_COLOUR}" stroke-width="1.6" x1="{_f(ax - nx * 5)}" '
                       f'y1="{_f(ay - ny * 5)}" x2="{_f(ax + nx * 5)}" y2="{_f(ay + ny * 5)}"/>')
    if "threshold" in set(tags):
        out.append(f'<line stroke="{THRESHOLD_COLOUR}" stroke-width="4" stroke-linecap="round" '
                   f'x1="{_f(mx - nx * 8)}" y1="{_f(my - ny * 8)}" x2="{_f(mx + nx * 8)}" '
                   f'y2="{_f(my + ny * 8)}"><title>threshold</title></line>')
    return "".join(out)


def _node_svg(node: Node, p: Point, extra_kinds: Sequence[str] = (), caption: Optional[str] = None,
              kept: bool = False) -> str:
    x, y = p
    r = node_radius(node)
    out = [f'<g><title>{_esc(node.id)}: {_esc(node.kind)}'
           f'{" · " + _esc(node.size) if node.size else ""}'
           f'{" · district " + str(node.district) if node.district else ""}</title>']
    if not node.is_room:
        out.append(f'<circle class="areanode" cx="{_f(x)}" cy="{_f(y)}" r="{_f(r)}"/>')
    else:
        fill, stroke = kind_style(node.kind, extra_kinds)
        if node.kind == ENTRANCE:
            out.append(f'<circle cx="{_f(x)}" cy="{_f(y)}" r="{_f(r + 3.5)}" fill="none" '
                       f'stroke="{stroke}" stroke-width="1.4"/>')
        out.append(f'<circle cx="{_f(x)}" cy="{_f(y)}" r="{_f(r)}" fill="{fill}" '
                   f'stroke="{stroke}" stroke-width="2"/>')
    cls = "nid" + (" area" if not node.is_room else "") + (" kept" if kept else "")
    label = node.id if len(node.id) <= 5 else node.id[:4] + "…"
    out.append(f'<text class="{cls}" x="{_f(x)}" y="{_f(y)}">{_esc(label)}</text>')
    if node.district:
        out.append(f'<text class="cap" x="{_f(x + r + 2)}" y="{_f(y - r + 2)}" '
                   f'style="text-anchor:start;fill:{THRESHOLD_COLOUR}">d{node.district}</text>')
    if caption:
        out.append(f'<text class="cap" x="{_f(x)}" y="{_f(y + r + 12)}">{_esc(caption)}</text>')
    out.append("</g>")
    return "".join(out)


def _svg_open(width: float, height: float, standalone: bool, label: str) -> str:
    head = (f'<svg class="tg" xmlns="http://www.w3.org/2000/svg" width="{_f(width)}" '
            f'height="{_f(height)}" viewBox="0 0 {_f(width)} {_f(height)}" role="img" '
            f'aria-label="{_esc(label)}">')
    if standalone:
        head += f"<style>{STYLE}</style>"
        head += f'<rect width="100%" height="100%" fill="var(--bg)"/>'
    return head


# ---------------------------------------------------------------------------
# A graph
# ---------------------------------------------------------------------------

def _root(graph: TopologyGraph) -> Optional[str]:
    ent = [n.id for n in graph.rooms() if n.kind == ENTRANCE]
    if ent:
        return ent[0]
    ids = graph.node_ids()
    return ids[0] if ids else None


def graph_svg(graph: TopologyGraph, *, title: Optional[str] = None,
              extra_kinds: Sequence[str] = (), captions: bool = True,
              standalone: bool = True, highlight: Iterable[str] = ()) -> str:
    """One graph as an SVG string.

    ``captions`` puts each node's kind (and size) under it; ``highlight``
    names nodes drawn with bold ids (e.g. the nodes a trace step touched).
    ``standalone`` embeds the stylesheet so the SVG opens on its own.
    """
    n = len(graph)
    side = max(260.0, 95.0 * math.sqrt(max(n, 1)) * 1.25)
    width, height = side * 1.5, side
    top = 22.0 if title else 0.0
    pos = _fit(layout(graph.node_ids(), [(e.a, e.b) for e in graph.edges()], _root(graph)),
               width, height, 38.0, max_scale=110.0)
    if pos:                                     # crop the height to the drawing
        y0 = min(y for _, y in pos.values()) - 38.0
        y1 = max(y for _, y in pos.values()) + 44.0
        pos = {k: (x, y - y0) for k, (x, y) in pos.items()}
        height = y1 - y0
    hl = set(highlight)
    parts = [_svg_open(width, height + top, standalone, title or "topology graph")]
    if title:
        parts.append(f'<text class="ttl" x="10" y="16">{_esc(title)}</text>')
    parts.append(f'<g transform="translate(0,{_f(top)})">')
    for e in graph.edges():
        parts.append(_edge_svg(pos[e.a], pos[e.b], node_radius(graph.node(e.a)),
                               node_radius(graph.node(e.b)), e.rel, e.tags))
    for node in graph.nodes():
        cap = None
        if captions:
            cap = node.kind if not node.is_room else f"{node.kind} · {node.size}"
        parts.append(_node_svg(node, pos[node.id], extra_kinds, cap, kept=node.id in hl))
    parts.append("</g></svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# A rule
# ---------------------------------------------------------------------------

def _stub(m: str) -> str:
    return f"\x00out:{m}"


def condition_text(rule) -> str:
    """The rule's ``when`` as text, e.g. ``race_scale >= 1.5``; '' if none."""
    parts = []
    for c in rule.when:
        if c.op == "in":
            parts.append(f"{c.key} in {', '.join(str(v) for v in c.value)}")
        else:
            v = c.value
            if isinstance(v, float) and v.is_integer() and c.key == "room_count":
                v = int(v)
            parts.append(f"{c.key} {c.op} {v}")
    return " and ".join(parts)


def rule_notes(rule) -> List[str]:
    """Plain-language captions: growth, budget, finishing, ignored sizes, reattach."""
    notes = []
    growth = len(rule.replace) - len(rule.match)
    rooms = rule.rooms_added
    when = condition_text(rule)
    if when:
        notes.append(f"Offered only when {when}.")
    nodes_word = "node" if abs(growth) == 1 else "nodes"
    rooms_word = "room" if abs(rooms) == 1 else "rooms"
    if growth > 0:
        notes.append(f"Adds {growth} {nodes_word} ({rooms:+d} {rooms_word}): spends {growth} of the "
                     "stage's budget.")
    elif growth == 0:
        notes.append(f"Adds no node ({rooms:+d} {rooms_word}): spends none of the stage's budget.")
    else:
        notes.append(f"Removes {-growth} {nodes_word} ({rooms:+d} {rooms_word}).")
    if rule.finishes_area:
        notes.append("Finishes an Area: it can end a placeholder in the last stage.")
    if rule.match and all(m.is_room for m in rule.match) and growth > 0:
        notes.append("Grows from finished rooms, so it still applies when every Area is boxed in.")
    match_kinds = {m.id: m.kind for m in rule.match}
    ignored = [r.id for r in rule.replace if r.is_room and match_kinds.get(r.id) == r.kind]
    if ignored:
        notes.append("Kept with the same kind, so the size written here is ignored "
                     f"(the node keeps its own): {', '.join(ignored)}.")
    for m, targets in rule.reattach:
        if len(targets) == 1:
            notes.append(f"{m}'s outside edges all move to {targets[0]}.")
        else:
            notes.append(f"{m}'s outside edges, sorted by neighbour id, split in order over "
                         f"{', '.join(targets)} (earlier targets take the larger part).")
    return notes


def rule_svg(rule, *, extra_kinds: Sequence[str] = (), standalone: bool = True) -> str:
    """The rule's before -> after diagram as an SVG string (no captions text block)."""
    repl_ids = [r.id for r in rule.replace]
    match_ids = [m.id for m in rule.match]
    reattach = rule.reattach_map()
    stubs = [_stub(m) for m in match_ids]
    lay_ids = repl_ids + stubs
    lay_edges = [(e.a, e.b) for e in rule.edges]
    for m in match_ids:
        for t in reattach.get(m, ()):
            lay_edges.append((_stub(m), t))
    abstract = layout(lay_ids, lay_edges, repl_ids[0] if repl_ids else None)
    # Match nodes sit where they are kept; a match node not kept sits among its targets.
    m_abs: Dict[str, Point] = {}
    for m in match_ids:
        if m in abstract and m in repl_ids:
            m_abs[m] = abstract[m]
        else:
            ts = [abstract[t] for t in reattach.get(m, ()) if t in abstract] or [(0.0, 0.0)]
            m_abs[m] = (sum(p[0] for p in ts) / len(ts), sum(p[1] for p in ts) / len(ts))
    seen: List[Point] = []
    for m in match_ids:
        p = m_abs[m]
        while any(math.hypot(p[0] - q[0], p[1] - q[1]) < 0.5 for q in seen):
            p = (p[0], p[1] + 0.7)
        m_abs[m] = p
        seen.append(p)
    every = dict(abstract)
    every.update({f"\x01{k}": v for k, v in m_abs.items()})

    pw, ph, gap, top = 420.0, 230.0, 46.0, 22.0
    fitted = _fit(every, pw, ph, 40.0, max_scale=110.0)
    right = {k: fitted[k] for k in abstract}
    left = {m: fitted[f"\x01{m}"] for m in match_ids}
    for s in stubs:
        left[s] = fitted[s]
    width, height = pw * 2 + gap, ph + top
    match_nodes = {m.id: m for m in rule.match}
    repl_nodes = {r.id: r for r in rule.replace}
    kept = set(match_ids) & set(repl_ids)

    parts = [_svg_open(width, height, standalone, f"rule {rule.name}: before and after")]
    parts.append(f'<text class="ttl" x="8" y="15">match</text>')
    parts.append(f'<text class="ttl" x="{_f(pw + gap + 8)}" y="15">replace</text>')
    ax = pw + gap / 2
    ay = top + ph / 2
    parts.append(f'<path class="arrowpanel" d="M{_f(ax - 14)},{_f(ay)} L{_f(ax + 12)},{_f(ay)} '
                 f'M{_f(ax + 5)},{_f(ay - 7)} L{_f(ax + 13)},{_f(ay)} L{_f(ax + 5)},{_f(ay + 7)}"/>')

    # Left: the match.
    parts.append(f'<g transform="translate(0,{_f(top)})">')
    for m in match_ids:
        s = _stub(m)
        seg = _trim(left[s], left[m], STUB_RADIUS, node_radius(match_nodes[m]))
        if seg:
            (x1, y1), (x2, y2) = seg
            parts.append(f'<line class="out" x1="{_f(x1)}" y1="{_f(y1)}" x2="{_f(x2)}" y2="{_f(y2)}"/>')
    for e in rule.match_edges:
        parts.append(_edge_svg(left[e.a], left[e.b], node_radius(match_nodes[e.a]),
                               node_radius(match_nodes[e.b]), e.rel, e.tags))
    for h in rule.match_hops:
        p, q = left[h.a], left[h.b]
        seg = _trim(p, q, node_radius(match_nodes[h.a]), node_radius(match_nodes[h.b]))
        if seg:
            (x1, y1), (x2, y2) = seg
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            d = math.hypot(x2 - x1, y2 - y1) or 1
            nx, ny = (y2 - y1) / d, -(x2 - x1) / d       # the normal pointing up the page
            if ny > 0:
                nx, ny = -nx, -ny
            cx, cy = mx + nx * 34, my + ny * 34
            parts.append(f'<path class="hops" d="M{_f(x1)},{_f(y1)} Q{_f(cx)},{_f(cy)} '
                         f'{_f(x2)},{_f(y2)}"/>')
            parts.append(f'<text class="lbl" x="{_f(cx)}" y="{_f(my + ny * 24)}">'
                         f'{h.lo}–{h.hi} hops apart</text>')
    for m in match_ids:
        parts.append(_stub_svg(left[_stub(m)], m))
        parts.append(_node_svg(match_nodes[m], left[m], extra_kinds, match_nodes[m].kind,
                               kept=m in kept))
    parts.append("</g>")

    # Right: the replacement, shifted into the right panel.
    parts.append(f'<g transform="translate({_f(pw + gap)},{_f(top)})">')
    for m in match_ids:
        targets = reattach.get(m, ())
        for i, t in enumerate(targets):
            seg = _trim(right[_stub(m)], right[t], STUB_RADIUS, node_radius(repl_nodes[t]))
            if not seg:
                continue
            (x1, y1), (x2, y2) = seg
            parts.append(f'<line class="out" x1="{_f(x1)}" y1="{_f(y1)}" x2="{_f(x2)}" y2="{_f(y2)}"/>')
            if len(targets) > 1:
                lx, ly = x1 + (x2 - x1) * 0.45, y1 + (y2 - y1) * 0.45
                parts.append(f'<circle cx="{_f(lx)}" cy="{_f(ly)}" r="6.5" fill="var(--bg)" '
                             f'stroke="var(--faint)"/>')
                parts.append(f'<text class="lbl" x="{_f(lx)}" y="{_f(ly)}" '
                             f'style="font-size:9px">{i + 1}</text>')
    for e in rule.edges:
        parts.append(_edge_svg(right[e.a], right[e.b], node_radius(repl_nodes[e.a]),
                               node_radius(repl_nodes[e.b]), e.rel, e.tags))
    match_kind = {m.id: m.kind for m in rule.match}
    for m in match_ids:
        parts.append(_stub_svg(right[_stub(m)], m))
    for r in rule.replace:
        if not r.is_room:
            cap = r.kind
        elif match_kind.get(r.id) == r.kind:
            cap = f"{r.kind} · kept"
        else:
            cap = f"{r.kind} · {r.size}"
        parts.append(_node_svg(r, right[r.id], extra_kinds, cap, kept=r.id in kept))
    parts.append("</g></svg>")
    return "".join(parts)


def _stub_svg(p: Point, m: str) -> str:
    x, y = p
    return (f'<g><title>the rest of the graph: {_esc(m)}\'s outside edges</title>'
            f'<circle class="stub" cx="{_f(x)}" cy="{_f(y)}" r="{STUB_RADIUS}"/>'
            f'<text class="lbl" x="{_f(x)}" y="{_f(y - 1)}">…</text>'
            f'<text class="cap" x="{_f(x)}" y="{_f(y + STUB_RADIUS + 11)}">outside {_esc(m)}</text></g>')


# ---------------------------------------------------------------------------
# The legend
# ---------------------------------------------------------------------------

def legend_svg(extra_kinds: Sequence[str] = (), standalone: bool = False) -> str:
    kinds = [AREA] + list(ROOM_KINDS) + [k for k in extra_kinds if k not in ROOM_KINDS]
    parts: List[str] = []
    for i, k in enumerate(kinds):
        x = 40 + 92 * i
        node = Node("", k, None if k == AREA else "medium")
        parts.append(_node_svg(node, (x, 26), extra_kinds, k))
    x = 40
    for c in SIZE_CLASSES:
        r = SIZE_RADIUS[c]
        parts.append(f'<circle cx="{_f(x)}" cy="88" r="{r}" fill="none" stroke="var(--line)"/>')
        parts.append(f'<text class="cap" x="{_f(x)}" y="{_f(88 + r + 12)}">{c}</text>')
        x += 2 * r + 30
    x += 10
    parts.append(_edge_svg((x, 88), (x + 70, 88), 0, 0, "above"))
    parts.append(f'<text class="cap" x="{_f(x + 35)}" y="108">above / below: arrow up</text>')
    x += 130
    parts.append(_edge_svg((x, 88), (x + 70, 88), 0, 0, "level"))
    parts.append(f'<text class="cap" x="{_f(x + 35)}" y="108">level</text>')
    x += 100
    parts.append(_edge_svg((x, 88), (x + 70, 88), 0, 0, "any", ("threshold",)))
    parts.append(f'<text class="cap" x="{_f(x + 35)}" y="108">threshold</text>')
    x += 100
    parts.append(_stub_svg((x + 8, 84), "x"))
    parts.append(f'<line class="out" x1="{_f(x + 18)}" y1="84" x2="{_f(x + 70)}" y2="84"/>')
    parts.append(f'<text class="cap" x="{_f(x + 44)}" y="132">x\'s outside edges</text>')
    width = max(20 + 92 * len(kinds), x + 110)
    return _svg_open(width, 150, standalone, "legend") + "".join(parts) + "</svg>"


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------

PAGE_CSS = """
:root { color-scheme: light dark; }
body.tg { margin: 0; padding: 24px 16px 48px; background: var(--bg); color: var(--ink);
          font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1100px; margin: 0 auto; }
h1 { font-size: 26px; margin: 0 0 4px; } h2 { font-size: 20px; margin: 32px 0 8px; }
h3 { font-size: 16px; margin: 0 0 2px; font-family: ui-monospace, Consolas, monospace; }
.desc { color: var(--muted); margin: 0 0 8px; }
.src { color: var(--muted); font-size: 13px; }
.card { background: var(--card); border: 1px solid var(--rule); border-radius: 10px;
        padding: 14px 16px; margin: 14px 0; overflow-x: auto; }
.card ul { margin: 6px 0 0; padding-left: 20px; color: var(--muted); font-size: 13.5px; }
table { border-collapse: collapse; font-size: 14px; }
th, td { text-align: left; padding: 6px 12px 6px 0; border-bottom: 1px solid var(--rule);
         vertical-align: top; }
th { color: var(--muted); font-weight: 600; }
code { font-family: ui-monospace, Consolas, monospace; font-size: 13px; }
.chip { display: inline-block; margin: 0 6px 4px 0; padding: 1px 8px; border-radius: 10px;
        border: 1px solid var(--rule); font-size: 13px; font-family: ui-monospace, Consolas, monospace; }
.note { color: var(--muted); font-size: 13.5px; }
svg { max-width: 100%; height: auto; display: block; }
"""


def recipe_table(recipe, base_stages: Sequence[str] = (), sources: Mapping[str, str] = ()) -> str:
    """The recipe as an HTML table: stage, share, rules with weight and % of the stage."""
    rows = ["<table><tr><th>Stage</th><th>Share</th><th>Rules (weight, chance among the "
            "stage's rules)</th></tr>"]
    for s in recipe:
        total = sum(s.apply.values()) or 1.0
        chips = "".join(f'<span class="chip">{_esc(r)} {w:g} · {100 * w / total:.0f}%</span>'
                        for r, w in s.apply.items())
        share = "rest" if s.is_rest else f"{s.share:g}"
        tag = ""
        if base_stages and s.name not in base_stages:
            tag = f' <span class="note">(inserted by {_esc(sources.get(s.name, "a layer"))})</span>'
        rows.append(f"<tr><td>{_esc(s.name)}{tag}</td><td>{share}</td><td>{chips}</td></tr>")
    rows.append("</table>")
    return "".join(rows)


def rule_card(rule, extra_kinds: Sequence[str] = ()) -> str:
    notes = "".join(f"<li>{_esc(n)}</li>" for n in rule_notes(rule))
    return (f'<section class="card" id="rule-{_esc(rule.name)}"><h3>{_esc(rule.name)}</h3>'
            f'<p class="desc">{_esc(rule.description)} '
            f'<span class="src">({_esc(rule.source)})</span></p>'
            f"{rule_svg(rule, extra_kinds=extra_kinds, standalone=False)}<ul>{notes}</ul></section>")


def rule_set_html(rule_set, layers: Sequence = (), *, theme: Optional[str] = None,
                  base_recipe: Sequence = (), example=None, example_caption: str = "") -> str:
    """One HTML page for a set.

    ``rule_set`` is the set drawn (merged with a theme's layers when
    ``theme`` is given); ``layers`` are the layers that fit its base, each
    shown with its rules and stage additions. ``base_recipe`` (the base
    set's own stages) marks stages a layer inserted. ``example`` is an
    optional grown graph drawn at the end.
    """
    extra = list(rule_set.kinds)
    for l in layers:
        extra += [k for k in l.kinds if k not in extra]
    layer_rules = {n for l in layers for n in l.rules}
    title = rule_set.name + (f" · theme {theme}" if theme else "")
    out = ["<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
           "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
           f"<title>{_esc(title)} rules</title><style>{STYLE}{PAGE_CSS}</style></head>"
           "<body class=\"tg\"><main>"]
    out.append(f"<h1>{_esc(title)}</h1><p class=\"desc\">{_esc(rule_set.description)}</p>")
    out.append(f'<p class="src">From <code>{_esc(rule_set.source)}</code> · placement '
               f'<code>{_esc(rule_set.placement)}</code>'
               + (f" · layers merged: {_esc(', '.join(rule_set.layers))}" if rule_set.layers else "")
               + "</p>")
    out.append('<section class="card">' + legend_svg(extra) +
               '<p class="note">Fill and outline by kind (Area: dashed, no fill; the entrance has '
               'a double ring), radius by size class. In a rule, a bold id is the same graph node '
               'on both sides (kept); the dotted "outside" stubs stand for each match node\'s '
               'edges to the rest of the graph, and on the right their dashed lines show where '
               'those edges go, numbered in order when they split.</p></section>')
    out.append("<h2>Start graph</h2><section class=\"card\">"
               + graph_svg(rule_set.start_graph(), extra_kinds=extra, standalone=False) + "</section>")
    sources: Dict[str, str] = {}
    for l in layers:
        for ins in l.inserts:
            sources[ins.stage.name] = l.name
    out.append("<h2>Recipe</h2><section class=\"card\">"
               + recipe_table(rule_set.recipe, [s.name for s in base_recipe], sources)
               + '<p class="note">Stages run in order. A stage\'s share of the room budget '
                 '(counted in rooms plus Areas) is spent by its rules, picked by weight among '
                 'those with a legal match; a stage that runs out of matches passes what is left '
                 'on. The "rest" stage runs until the graph has exactly the requested rooms and '
                 'no Area.</p></section>')
    out.append("<h2>Rules</h2>")
    used = {r for s in rule_set.recipe for r in s.apply}
    for name, rule in rule_set.rules.items():
        if name in layer_rules:
            continue
        card = rule_card(rule, extra)
        if name not in used:
            card = card.replace("</ul></section>", "<li>In no stage of this recipe: it never fires."
                                "</li></ul></section>")
        out.append(card)
    for l in layers:
        out.append(f"<h2>Layer: {_esc(l.name)}</h2><p class=\"desc\">{_esc(l.description)} "
                   f'<span class="src">({_esc(l.source)}; fits {_esc(", ".join(l.fits))})</span></p>')
        adds = []
        for ins in l.inserts:
            share = "rest" if ins.stage.is_rest else f"{ins.stage.share:g}"
            chips = "".join(f'<span class="chip">{_esc(r)} {w:g}</span>' for r, w in ins.stage.apply.items())
            adds.append(f"<tr><td>inserts stage <b>{_esc(ins.stage.name)}</b> after "
                        f"{_esc(ins.after)}</td><td>{share}</td><td>{chips}</td></tr>")
        for sname, w in l.stage_weights.items():
            chips = "".join(f'<span class="chip">{_esc(r)} +{x:g}</span>' for r, x in w.items())
            adds.append(f"<tr><td>adds weight to <b>{_esc(sname)}</b></td><td></td><td>{chips}</td></tr>")
        if adds:
            out.append('<section class="card"><table><tr><th>Change</th><th>Share</th><th>Rules'
                       '</th></tr>' + "".join(adds) + "</table></section>")
        for rule in l.rules.values():
            out.append(rule_card(rule, extra))
    if example is not None:
        out.append("<h2>A grown graph</h2><section class=\"card\">"
                   + graph_svg(example, extra_kinds=extra, standalone=False)
                   + f'<p class="note">{_esc(example_caption)}</p></section>')
    out.append("</main></body></html>")
    return "".join(out)


__all__ = [
    "KIND_STYLE", "SIZE_RADIUS", "STYLE", "kind_style", "node_radius", "layout",
    "graph_svg", "rule_svg", "rule_notes", "condition_text", "legend_svg",
    "recipe_table", "rule_card", "rule_set_html",
]


# ---------------------------------------------------------------------------
# Wall styles (roadmap step 8)
# ---------------------------------------------------------------------------

def outline_svg(outline, box, *, title: str = "", scale: float = 1.6) -> str:
    """One room in plan: its Box in grey, its floor, its walls."""
    x0, y0, x1, y1 = box
    pad = 6.0

    def px(x: float, y: float) -> str:
        return f"{_f((x - x0 + pad) * scale)},{_f((y1 - y + pad) * scale)}"

    width, height = (x1 - x0 + 2 * pad) * scale, (y1 - y0 + 2 * pad) * scale
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{_f(width)}" height="{_f(height)}" '
             f'role="img" aria-label="{_esc(title)}">',
             f'<rect x="{_f(pad * scale)}" y="{_f(pad * scale)}" width="{_f((x1 - x0) * scale)}" '
             f'height="{_f((y1 - y0) * scale)}" fill="none" stroke="#bbb"/>']
    if outline is None:
        parts.append(f'<rect x="{_f(pad * scale)}" y="{_f(pad * scale)}" width="{_f((x1 - x0) * scale)}" '
                     f'height="{_f((y1 - y0) * scale)}" fill="#eee" stroke="#b33" stroke-width="1.5"/>')
    else:
        for cell in outline.cells:
            pts = " ".join(px(*outline.verts[i]) for i in cell)
            parts.append(f'<polygon points="{pts}" fill="#eee"/>')
        for loop in outline.wall_loops():
            pts = " ".join(px(*outline.verts[i]) for i in loop)
            parts.append(f'<polygon points="{pts}" fill="none" stroke="#b33" stroke-width="1.5"/>')
    parts.append("</svg>")
    return "".join(parts)


def walls_html(rows) -> str:
    """A page of sample rooms. ``rows``: (style name, description, [(caption, svg), ...])."""
    body = []
    for name, description, samples in rows:
        body.append(f"<h2>{_esc(name)}</h2><p>{_esc(description)}</p><div class=row>")
        for caption, svg in samples:
            body.append(f"<figure>{svg}<figcaption>{_esc(caption)}</figcaption></figure>")
        body.append("</div>")
    return ("<!doctype html><meta charset=utf-8><title>Wall styles</title><style>"
            "body{font:14px sans-serif;margin:24px;color:#222;background:#fff}"
            ".row{display:flex;flex-wrap:wrap;gap:12px}figure{margin:0}"
            "figcaption{text-align:center;color:#555}</style><h1>Wall styles</h1>"
            "<p>Sample rooms in plan, 120 x 90 u with two doors, at a human's body height. "
            "Grey is the room's Box, red its walls.</p>" + "".join(body))

