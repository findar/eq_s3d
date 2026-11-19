// quality.ts — the open version's quality (zone-generator-quality Req 5,
// umbrella 25.5–25.8, 25.10, 25.11).
//
// One entry point, showQuality(sidecar.quality), called by main.ts showBuild
// once a version's sidecar and GLB are in, so generate, rebuild, an applied
// edit, the version steppers and Undo/Redo all show the sidecar's entry the
// same way. A request that fails or brings no new build never reaches
// showBuild, so the banner, indicator and list stay as they were.
//
// - Degraded: the banner over the 3D view (no close control, role="status")
//   with the out-of-band count, the reason and a link that opens and focuses
//   the Quality list; the indicator says degraded; the list shows the
//   out-of-band metrics first as `metric — value (band lo–hi)`, then the rest.
// - Passed: no banner; the indicator says passed; the list shows the values.
// - No valid entry (a version built before step 19): "quality unknown", no list.

import type { QualityBlock } from "./api";

const $ = (id: string) => document.getElementById(id)!;

// The reasons the server can give, as words (umbrella 25.2).
const REASON_WORDS: Record<string, string> = {
  quality_degraded: "no draw met the targets, so the closest one was kept",
  quality_outside_bands_pinned: "the pinned seed was built as asked",
  edit_outside_bands: "the edit was applied as asked",
};

export const QUALITY_REASONS = new Set(Object.keys(REASON_WORDS));

export function reasonWords(reason: string | null | undefined): string {
  if (!reason) return "no reason given";
  return REASON_WORDS[reason] ?? reason.replace(/_/g, " ");
}

// A metric value: whole numbers as they are, others to at most 3 decimals.
function num(v: unknown): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return String(v);
  return Number.isInteger(v) ? String(v) : String(Number(v.toFixed(3)));
}

// A band with an open end (null) shows "…" on that side.
function band(lo: number | null, hi: number | null): string {
  return `band ${lo == null ? "…" : num(lo)}–${hi == null ? "…" : num(hi)}`;
}

// The sidecar's entry, if it has the Quality_Block's shape.
function valid(q: unknown): q is QualityBlock {
  if (!q || typeof q !== "object") return false;
  const b = q as Record<string, unknown>;
  return typeof b.degraded === "boolean"
    && !!b.metrics && typeof b.metrics === "object" && !Array.isArray(b.metrics)
    && Array.isArray(b.out_of_band)
    && b.out_of_band.every((e) => !!e && typeof (e as { metric?: unknown }).metric === "string");
}

// Show the open version's quality: its sidecar's `quality` entry (or none).
export function showQuality(entry: unknown): void {
  const banner = $("quality-banner");
  const indicator = $("m-quality");
  const section = $("s-quality");
  const list = $("quality-list");

  if (!valid(entry)) {
    banner.hidden = true;
    document.body.classList.remove("quality-degraded");
    indicator.textContent = "quality unknown";
    indicator.className = "quality-unknown";
    indicator.title = "This version was built before quality was measured";
    section.hidden = true;
    list.replaceChildren();
    return;
  }

  const out = entry.out_of_band;
  const n = out.length;
  if (entry.degraded) {
    $("quality-banner-text").textContent =
      `Walkable, but outside quality targets: ${n} metric${n === 1 ? "" : "s"} ` +
      `out of band (${reasonWords(entry.reason)}).`;
    banner.title = entry.reason ?? "";
    banner.hidden = false;
    document.body.classList.add("quality-degraded");
    indicator.textContent = `degraded · ${n} out of band`;
    indicator.className = "quality-degraded";
    indicator.title = entry.reason ?? "";
  } else {
    banner.hidden = true;
    document.body.classList.remove("quality-degraded");
    indicator.textContent = "passed";
    indicator.className = "quality-passed";
    indicator.title = "Every measured metric is inside its band";
  }

  // Out-of-band entries first, then the rest of the metrics with their values.
  const items: HTMLLIElement[] = [];
  const outNames = new Set<string>();
  for (const e of out) {
    outNames.add(e.metric);
    const li = document.createElement("li");
    li.className = "out";
    li.textContent = `${e.metric} — ${num(e.value)} (${band(e.lo, e.hi)})`;
    items.push(li);
  }
  for (const [name, value] of Object.entries(entry.metrics)) {
    if (outNames.has(name)) continue;
    const li = document.createElement("li");
    li.textContent = `${name} — ${num(value)}`;
    items.push(li);
  }
  list.replaceChildren(...items);
  section.hidden = false;
}

// The banner's link: open the Quality list and move focus to it.
export function initQuality(): void {
  $("quality-link").addEventListener("click", (ev) => {
    ev.preventDefault();
    const details = $("quality-details") as HTMLDetailsElement;
    details.open = true;
    const list = $("quality-list");
    list.scrollIntoView({ block: "nearest" });
    list.focus();
  });
}
