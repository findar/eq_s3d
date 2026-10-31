// artifacts.ts — the Artifacts panel: the latest build's files as download
// links, plus the browser-rendered PNG of the map SVG.
//
// The list is rebuilt on every accepted build. Each entry is probed with HEAD;
// one that fails is marked unavailable on its own and the rest stay usable.
// The PNG is drawn from the SVG at 2× its viewBox only when first asked for, so
// it costs nothing (and no server request) unless someone wants it.

import type { ArtifactRef } from "./api";

export type { ArtifactRef };

// Kind of the browser-made PNG entry (not a server artifact).
const PNG_KIND = "map_png";

const listEl = () => document.getElementById("artifact-list")!;
const modalBody = () => document.getElementById("map-body");
const modalPng = () =>
  document.getElementById("map-download-png") as HTMLAnchorElement | null;

// Per-build state. `build` increments on every showArtifacts so probes and
// renders still in flight from an earlier build can't touch the new list.
let build = 0;
let svgCache: { url: string; text: Promise<string> } | null = null;
let svgUrl: string | null = null;      // the current build's map SVG
let pngName = "map.png";
let png: { url: string } | null = null;
let pngPending: Promise<string> | null = null;

/** The visible label of an entry: names the file type (Req 10.5). */
function label(ref: ArtifactRef): string {
  switch (ref.kind) {
    case "map_svg": return "Map (SVG)";
    case PNG_KIND: return "Map (PNG)";
    case "eqmap": return `EQ map layer ${ref.layer ?? 0} (.txt)`;
    case "eqg": return "Zone archive (.eqg)";
    case "glb": return "Preview model (.glb)";
    case "sidecar": return "Zone sidecar (.json)";
    default: return `${ref.kind} (${ref.filename})`;
  }
}

/** The name a download is saved under: the build file's own name. */
function baseName(filename: string): string {
  return filename.slice(filename.lastIndexOf("/") + 1);
}

function entryFor(kind: string, filename: string): HTMLLIElement | null {
  for (const li of listEl().querySelectorAll<HTMLLIElement>("li")) {
    if (li.dataset.kind === kind && li.dataset.filename === filename) return li;
  }
  return null;
}

/** Disable a link in place: no href (so it's inert and leaves the tab order),
 *  struck through, with the reason as its tooltip. */
function disableLink(a: HTMLAnchorElement, why: string): void {
  a.removeAttribute("href");
  a.removeAttribute("download");
  a.setAttribute("aria-disabled", "true");
  a.classList.add("unavailable");
  a.title = `Unavailable: ${why}`;
}

/** Mark one entry unavailable, leaving every other entry alone (Req 10.4). */
export function markUnavailable(kind: string, filename: string, why: string): void {
  const li = entryFor(kind, filename);
  const a = li?.querySelector("a");
  if (li && a) {
    li.classList.add("unavailable");
    disableLink(a, why);
  }
  // No SVG means no PNG either, in the list and in the map dialog.
  if (kind === "map_svg") {
    markUnavailable(PNG_KIND, pngName, `the map SVG is unavailable (${why})`);
    const mp = modalPng();
    if (mp) disableLink(mp, `the map SVG is unavailable (${why})`);
  }
}

/** Fetch the map SVG text, once per build. */
export async function loadMapSvg(url: string): Promise<string> {
  if (!svgCache || svgCache.url !== url) {
    const text = fetch(url).then(async (res) => {
      if (!res.ok) throw new Error(`map fetch failed (${res.status})`);
      return res.text();
    });
    svgCache = { url, text };
    text.catch(() => { if (svgCache?.text === text) svgCache = null; });
  }
  return svgCache.text;
}

/** Render SVG text to a PNG at `scale` × its viewBox, entirely in the browser.
 *  The map SVG has no external references, so the canvas isn't tainted. */
export async function svgToPng(svgText: string, scale = 2): Promise<Blob> {
  const root = new DOMParser()
    .parseFromString(svgText, "image/svg+xml").documentElement;
  const vb = (root.getAttribute("viewBox") ?? "").trim().split(/[\s,]+/).map(Number);
  const w = vb.length === 4 ? vb[2] : parseFloat(root.getAttribute("width") ?? "");
  const h = vb.length === 4 ? vb[3] : parseFloat(root.getAttribute("height") ?? "");
  if (!(w > 0 && h > 0)) throw new Error("map SVG has no usable viewBox");

  const src = URL.createObjectURL(new Blob([svgText], { type: "image/svg+xml" }));
  try {
    const img = new Image();
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error("map SVG failed to decode"));
      img.src = src;
    });
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(w * scale);
    canvas.height = Math.round(h * scale);
    canvas.getContext("2d")!.drawImage(img, 0, 0, canvas.width, canvas.height);
    return await new Promise<Blob>((resolve, reject) =>
      canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("PNG encode failed"))),
        "image/png"));
  } finally {
    URL.revokeObjectURL(src);
  }
}

/** The PNG's object URL for this build, rendering it on first request. */
function ensurePng(): Promise<string> {
  if (png) return Promise.resolve(png.url);
  if (!pngPending) {
    const mine = build;
    const url = svgUrl!;
    pngPending = loadMapSvg(url)
      .then((text) => svgToPng(text, 2))
      .then((blob) => {
        const obj = URL.createObjectURL(blob);
        if (mine !== build) { URL.revokeObjectURL(obj); throw new Error("stale build"); }
        png = { url: obj };
        return obj;
      })
      .finally(() => { if (mine === build) pngPending = null; });
  }
  return pngPending;
}

/** Click handler for both PNG links: the first click renders the PNG, points
 *  every PNG link at it, then re-clicks so the browser saves it. */
function onPngClick(e: MouseEvent): void {
  const a = e.currentTarget as HTMLAnchorElement;
  if (a.getAttribute("aria-disabled") === "true") { e.preventDefault(); return; }
  if (png && a.href === png.url) return;          // ready: let the link work
  e.preventDefault();
  const mine = build;
  a.setAttribute("aria-busy", "true");
  ensurePng()
    .then((url) => {
      for (const link of pngLinks()) link.href = url;
      a.click();
    })
    .catch((err) => {
      if (mine !== build) return;
      console.error("[artifacts] PNG", err);
      markUnavailable(PNG_KIND, pngName, String(err?.message ?? err));
      const mp = modalPng();
      if (mp) disableLink(mp, String(err?.message ?? err));
    })
    .finally(() => a.removeAttribute("aria-busy"));
}

function pngLinks(): HTMLAnchorElement[] {
  const links = [...listEl().querySelectorAll<HTMLAnchorElement>(
    `li[data-kind="${PNG_KIND}"] a[href]`)];
  const mp = modalPng();
  if (mp?.hasAttribute("href")) links.push(mp);
  return links;
}

/** Reset the map dialog's PNG link for a new build. */
function resetModalPng(available: boolean): void {
  const mp = modalPng();
  if (!mp) return;
  mp.classList.remove("unavailable");
  mp.removeAttribute("aria-disabled");
  mp.removeAttribute("title");
  if (available) {
    mp.href = "#";
    mp.download = pngName;
  } else {
    disableLink(mp, "this build has no map SVG");
  }
}

function addEntry(ref: ArtifactRef, href: string, download: string): HTMLAnchorElement {
  const li = document.createElement("li");
  li.dataset.kind = ref.kind;
  li.dataset.filename = ref.filename;
  const a = document.createElement("a");
  a.href = href;
  a.download = download;
  a.textContent = label(ref);
  a.title = download;
  li.appendChild(a);
  listEl().appendChild(li);
  return a;
}

/** Rebuild the panel for a newly accepted build and probe every file. */
export function showArtifacts(refs: ArtifactRef[], name: string): void {
  build += 1;
  const mine = build;

  // Drop everything from the previous build: cached SVG, dialog body, PNG.
  svgCache = null;
  const body = modalBody();
  if (body) body.innerHTML = "";
  if (png) URL.revokeObjectURL(png.url);
  png = null;
  pngPending = null;

  const svgRef = refs.find((r) => r.kind === "map_svg") ?? null;
  svgUrl = svgRef?.url ?? null;
  pngName = `${name}.map.png`;
  resetModalPng(svgRef !== null);

  const list = listEl();
  list.innerHTML = "";
  if (refs.length === 0) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = "No files for this build.";
    list.appendChild(li);
    return;
  }

  for (const ref of refs) {
    addEntry(ref, ref.url, baseName(ref.filename));
    if (ref === svgRef) {
      const a = addEntry({ kind: PNG_KIND, filename: pngName, url: "" }, "#", pngName);
      a.addEventListener("click", onPngClick);
    }
  }

  // Probe each file; a failure marks only that entry (Req 10.4).
  for (const ref of refs) {
    fetch(ref.url, { method: "HEAD", cache: "no-store" })
      .then((res) => {
        if (mine === build && !res.ok) {
          markUnavailable(ref.kind, ref.filename, `HTTP ${res.status}`);
        }
      })
      .catch((err) => {
        if (mine === build) {
          markUnavailable(ref.kind, ref.filename, `network error (${err?.message ?? err})`);
        }
      });
  }
}

// The dialog's PNG link is static markup; bind it once.
modalPng()?.addEventListener("click", onPngClick);
