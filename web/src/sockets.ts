// sockets.ts — marks the sidecar's Sockets on the inlined map SVG.
//
// The map SVG (generators/mapview.py) draws world (x, y) at
//   u = a + s·x,  v = b − s·y          (north up, 40 px padding)
// and writes a, b and s on its root as data-frame-a / -b / -s (site-sockets
// task 9). A map made before that carries no frame, so it is recovered from
// points the SVG and the sidecar both carry: each room's depth number sits at
// its centre (u, v + 4), followed by its id. Two rooms or more fit all three;
// with one room, or none (a wilderness), the sidecar's outline bounds give the
// frame. No frame, no markers: the map is left as it is.

import type { ZoneSidecar, ZoneSocket } from "./api";

const SVG_NS = "http://www.w3.org/2000/svg";
const PADDING = 40;        // mapview.render_map_svg's default padding

interface Frame { a: number; b: number; s: number; }

type Anchor = { x: number; y: number; u: number; v: number };

/** The rooms' depth-number labels paired with their sidecar centres. */
function roomAnchors(svg: SVGSVGElement, sidecar: ZoneSidecar): Anchor[] {
  const centres = new Map<string, [number, number, number]>();
  for (const r of sidecar.rooms ?? []) centres.set(r.id, r.center);
  const out: Anchor[] = [];
  for (const t of Array.from(svg.querySelectorAll("text"))) {
    if (t.getAttribute("font-size") !== "12" || t.getAttribute("text-anchor") !== "middle") continue;
    const idEl = t.nextElementSibling;
    if (!idEl || idEl.tagName.toLowerCase() !== "text" || idEl.getAttribute("font-size") !== "9") continue;
    const c = centres.get((idEl.textContent ?? "").trim());
    const u = Number(t.getAttribute("x"));
    const v = Number(t.getAttribute("y")) - 4;
    if (c && Number.isFinite(u) && Number.isFinite(v)) out.push({ x: c[0], y: c[1], u, v });
  }
  return out;
}

/** Scale from the outline bounds alone: the frame's longer side spans the
 *  viewBox's longer side less the padding. */
function boundsScale(svg: SVGSVGElement, bounds: number[]): number | null {
  const vb = svg.viewBox?.baseVal;
  if (!vb) return null;
  const span = Math.max(bounds[3] - bounds[0], bounds[4] - bounds[1], 1);
  const inner = Math.max(vb.width, vb.height) - 2 * PADDING;
  return inner > 0 ? inner / span : null;
}

/** The frame mapview.py wrote on the SVG's root, or null on an older map. */
function writtenFrame(svg: SVGSVGElement): Frame | null {
  const [a, b, s] = ["a", "b", "s"].map((k) => {
    const v = svg.getAttribute(`data-frame-${k}`);
    return v === null || v.trim() === "" ? NaN : Number(v);
  });
  return Number.isFinite(a) && Number.isFinite(b) && Number.isFinite(s) && s > 0 ? { a, b, s } : null;
}

function mapFrame(svg: SVGSVGElement, sidecar: ZoneSidecar): Frame | null {
  const written = writtenFrame(svg);
  if (written) return written;
  // A map made before the frame was written: fit it from the room labels.
  const anchors = roomAnchors(svg, sidecar);
  const bounds = sidecar.outline?.bounds;
  if (anchors.length >= 2) {
    // Least squares on u = a + s·x and v = b − s·y, sharing s.
    const n = anchors.length;
    const mx = anchors.reduce((t, p) => t + p.x, 0) / n;
    const my = anchors.reduce((t, p) => t + p.y, 0) / n;
    const mu = anchors.reduce((t, p) => t + p.u, 0) / n;
    const mv = anchors.reduce((t, p) => t + p.v, 0) / n;
    let num = 0, den = 0;
    for (const p of anchors) {
      num += (p.x - mx) * (p.u - mu) - (p.y - my) * (p.v - mv);
      den += (p.x - mx) ** 2 + (p.y - my) ** 2;
    }
    if (den > 1e-6 && num > 0) {
      const s = num / den;
      return { a: mu - s * mx, b: mv + s * my, s };
    }
  }
  if (bounds && bounds.length >= 6) {
    const s = boundsScale(svg, bounds);
    if (!s) return null;
    if (anchors.length >= 1) {
      const p = anchors[0];
      return { a: p.u - s * p.x, b: p.v + s * p.y, s };
    }
    // No rooms: the outline is the whole frame (min x at the left padding,
    // max y at the top one).
    return { a: PADDING - s * bounds[0], b: PADDING + s * bounds[4], s };
  }
  return null;
}

/** "hillside hill0 (N): dungeon, 7 rooms" — the marker's tooltip. A point
 *  Socket: "site site3, Group 1: farmstead" or "site site7: unused". */
export function socketTitle(s: ZoneSocket): string {
  const head = `${s.kind} ${s.id}` + (s.side ? ` (${s.side})` : "");
  const a = s.attached;
  if (s.kind === "site") {
    // The sidecar names a point's Group only when a Site stands on it.
    if (!a) return `${head}: unused`;
    const group = a.group !== undefined && a.group !== null ? `, Group ${a.group}` : "";
    return `${head}${group}: ${a.site ?? a.kind}`;
  }
  if (!a) return `${head}: nothing attached`;
  if (a.kind === "sites") return `${head}: sites, ${a.sites ?? 0}`;
  return `${head}: ${a.kind}, ${a.rooms ?? 0} rooms`;
}

const SOCKET_FILL: Record<string, string> = {
  hillside: "#ff7043",
  ground: "#66bb6a",
  root: "#90a4ae",
  door: "#ba68c8",
  site: "#d08850",          // mapview.py's Site colour
};

// One step along the Socket's side, for the hillside's facing tick.
const SIDE_DIR: Record<string, [number, number]> = {
  N: [0, -1], E: [1, 0], S: [0, 1], W: [-1, 0],
};

/** A diamond of half-width `r` centred on (u, v). */
function diamond(u: number, v: number, r: number, fill: string, stroke: string, width: number): SVGPathElement {
  const d = document.createElementNS(SVG_NS, "path");
  d.setAttribute("d", `M ${u.toFixed(1)} ${(v - r).toFixed(1)} L ${(u + r).toFixed(1)} ${v.toFixed(1)} ` +
    `L ${u.toFixed(1)} ${(v + r).toFixed(1)} L ${(u - r).toFixed(1)} ${v.toFixed(1)} Z`);
  d.setAttribute("fill", fill);
  d.setAttribute("stroke", stroke);
  d.setAttribute("stroke-width", String(width));
  return d;
}

/** Draw the Sockets onto `svg` (the map dialog's inlined copy). Returns how
 *  many were drawn: 0 when the sidecar has none or the frame can't be found. */
export function drawSockets(svg: SVGSVGElement, sidecar: ZoneSidecar): number {
  const sockets = sidecar.sockets ?? [];
  if (!sockets.length) return 0;
  const frame = mapFrame(svg, sidecar);
  if (!frame) {
    console.warn("[map] Sockets not drawn: no rooms or outline to place them by");
    return 0;
  }
  const g = document.createElementNS(SVG_NS, "g");
  g.setAttribute("class", "sockets");
  for (const s of sockets) {
    const u = frame.a + frame.s * s.point[0];
    const v = frame.b - frame.s * s.point[1];
    if (!Number.isFinite(u) || !Number.isFinite(v)) continue;
    const fill = SOCKET_FILL[s.kind] ?? "#eceff1";
    const mark = document.createElementNS(SVG_NS, "g");
    mark.setAttribute("class", `socket socket-${s.kind}`);
    if (s.kind === "site") {
      // A point Socket: a small diamond, filled when a Site stands on it,
      // hollow when unused; no label (there are many), the tooltip says which.
      mark.appendChild(diamond(u, v, 5, s.attached ? fill : "none", s.attached ? "#0f0f16" : fill, 1.5));
      if (!s.attached) mark.setAttribute("class", "socket socket-site socket-unused");
      const title = document.createElementNS(SVG_NS, "title");
      title.textContent = socketTitle(s);
      mark.appendChild(title);
      g.appendChild(mark);
      continue;
    }
    const dir = SIDE_DIR[s.side];
    if (dir) {
      // The way out of the hill: a short tick toward the Socket's side.
      const tick = document.createElementNS(SVG_NS, "line");
      tick.setAttribute("x1", u.toFixed(1));
      tick.setAttribute("y1", v.toFixed(1));
      tick.setAttribute("x2", (u + dir[0] * 16).toFixed(1));
      tick.setAttribute("y2", (v + dir[1] * 16).toFixed(1));
      tick.setAttribute("stroke", fill);
      tick.setAttribute("stroke-width", "3");
      mark.appendChild(tick);
    }
    // A diamond, so it doesn't read as a POI or Prop dot.
    mark.appendChild(diamond(u, v, 8, fill, "#0f0f16", 1.5));
    // Its id beside it ("hill0", "ground", "root"); the tooltip says the rest.
    const label = document.createElementNS(SVG_NS, "text");
    label.setAttribute("x", (u + 11).toFixed(1));
    label.setAttribute("y", (v - 6).toFixed(1));
    label.setAttribute("fill", fill);
    label.setAttribute("font-size", "10");
    label.setAttribute("font-family", "monospace");
    label.textContent = s.id;
    mark.appendChild(label);
    const title = document.createElementNS(SVG_NS, "title");
    title.textContent = socketTitle(s);
    mark.appendChild(title);
    g.appendChild(mark);
  }
  svg.appendChild(g);
  return g.childElementCount;
}
