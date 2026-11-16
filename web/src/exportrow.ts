// exportrow.ts — the Export row in the side panel's Files section (export spec
// Req 4.2, umbrella 8.5): exports the version on screen as a takeover of an
// existing zone, then lists the bundle and each file of that Export.
//
// The picker is a filter box over a list of the known zones (GET
// /api/shortnames): installed ones first, as the server orders them, and the
// default (arena) picked at first. The filter matches the short or the long
// name, case-insensitively. When nothing matches, Export sends the typed name
// as it is, so the server's 400 can name it and the close names.
//
// The row lives inside #panel-body, so it shows only while a build is open
// (step 14's rule). Its fields are <input>/<select>, which controls.ts already
// keeps the movement keys out of; the Files section stops them on its button.

import {
  exportZone, fetchShortnames, ExportNameError,
  type ExportFile, type ExportResult, type KnownZone,
} from "./api";

const $ = (id: string) => document.getElementById(id)!;
const filterEl = $("export-filter") as HTMLInputElement;
const pickEl = $("export-shortname") as HTMLSelectElement;
const spawnsEl = $("export-clear-spawns") as HTMLInputElement;
const noteZone = $("export-note-zone");
const runBtn = $("export-run") as HTMLButtonElement;
const msgEl = $("export-msg");
const listEl = $("export-list");

let zones: KnownZone[] = [];
let defaultShort = "arena";
let chosen = defaultShort;              // kept across filters and builds
let build: { zone: string; version: number } | null = null;
// Bumped on every new build and every Export, so an answer that comes back
// after either can't fill the row for the wrong version.
let seq = 0;
let busy = false;

function optionText(z: KnownZone): string {
  const name = z.long_name && z.long_name !== z.shortname ? `${z.shortname} — ${z.long_name}` : z.shortname;
  return z.in_install ? name : `${name} (not installed)`;
}

/** Refill the list from the filter, keeping the chosen zone when it still matches. */
function renderPicker(): void {
  const q = filterEl.value.trim().toLowerCase();
  const shown = q === "" ? zones : zones.filter((z) =>
    z.shortname.toLowerCase().includes(q) || z.long_name.toLowerCase().includes(q));
  pickEl.innerHTML = "";
  for (const z of shown) {
    const o = document.createElement("option");
    o.value = z.shortname;
    o.textContent = optionText(z);
    if (!z.in_install) o.className = "absent";
    pickEl.appendChild(o);
  }
  if (shown.some((z) => z.shortname === chosen)) pickEl.value = chosen;
  else if (shown.length) pickEl.selectedIndex = 0;
  syncNote();
}

/** The short name Export sends: the picked one, or the typed text when nothing matches. */
function currentShort(): string {
  if (pickEl.selectedIndex >= 0 && pickEl.value) return pickEl.value;
  return filterEl.value.trim();
}

function syncNote(): void {
  noteZone.textContent = currentShort() || defaultShort;
  syncButton();
}

function syncButton(): void {
  runBtn.disabled = busy || build === null;
  runBtn.textContent = busy ? "Exporting…" : `Export to ${currentShort() || defaultShort}`;
  runBtn.setAttribute("aria-busy", String(busy));
}

/** Labels for an Export's files, naming the file type. */
function label(f: ExportFile): string {
  switch (f.kind) {
    case "bundle": return "Bundle (.zip)";
    case "eqg": return "Zone archive (.eqg)";
    case "eqmap": return `EQ map layer ${f.layer ?? 0} (.txt)`;
    case "sql": return "Server rows (.sql)";
    case "sidecar": return "Zone sidecar (.json)";
    case "install": return "Install notes (.txt)";
    default: return `${f.kind} (${f.filename})`;
  }
}

function clearResult(): void {
  msgEl.textContent = "";
  msgEl.className = "";
  listEl.innerHTML = "";
}

function showResult(res: ExportResult): void {
  clearResult();
  const lines = [`${res.zone} ${res.version} → ${res.shortname}` +
    (res.clear_spawns ? " · spawn cleanup" : "")];
  if (res.format && !res.format.passed) {
    const failed = res.format.checks.filter((c) => !c.passed).map((c) => c.name);
    lines.push(`Format check failed (${failed.join(", ") || "see the sidecar"}): no SQL or bundle.`);
    msgEl.className = "warn";
  } else if (!res.sql_written) {
    lines.push("No SQL was written, so there is no bundle.");
    msgEl.className = "warn";
  }
  for (const w of res.warnings) lines.push(w);
  msgEl.textContent = lines.join("\n");

  // The bundle first, then each file in the server's order.
  const files = [...res.files.filter((f) => f.kind === "bundle"),
    ...res.files.filter((f) => f.kind !== "bundle")];
  for (const f of files) {
    const li = document.createElement("li");
    li.dataset.kind = f.kind;
    if (f.kind === "bundle") li.className = "bundle";
    const a = document.createElement("a");
    a.href = f.url;
    a.download = f.filename.slice(f.filename.lastIndexOf("/") + 1);
    a.textContent = label(f);
    a.title = f.filename;
    li.appendChild(a);
    listEl.appendChild(li);
  }
}

function showError(err: unknown): void {
  clearResult();
  msgEl.className = "error";
  if (err instanceof ExportNameError) {
    // The server's message names the close ones already; add them only if it doesn't.
    const missing = err.close.some((c) => !err.message.includes(c));
    msgEl.textContent = missing && err.close.length
      ? `${err.message}\nClose names: ${err.close.join(", ")}`
      : err.message;
  } else {
    msgEl.textContent = String((err as Error)?.message ?? err);
  }
}

async function runExport(): Promise<void> {
  if (busy || !build) return;
  const mine = ++seq;
  const short = currentShort();
  const params = { zone: build.zone, version: build.version, shortname: short,
    clear_spawns: spawnsEl.checked };
  console.log(`[input] export: ${params.zone} v${params.version} -> ${short || "(default)"}` +
    `${params.clear_spawns ? " clear_spawns" : ""}`);
  busy = true;
  syncButton();
  clearResult();
  msgEl.textContent = "Exporting…";
  try {
    const res = await exportZone(params);
    if (mine === seq) showResult(res);
  } catch (err) {
    if (mine === seq) showError(err);
  } finally {
    busy = false;
    syncButton();
  }
}

/** The version on screen changed: its Export has to be asked for again. */
export function setExportBuild(zone: string, version: number): void {
  if (build && build.zone === zone && build.version === version) return;
  build = { zone, version };
  seq += 1;
  clearResult();
  syncButton();
}

filterEl.addEventListener("input", renderPicker);
filterEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter") runExport();
  else if (e.key === "ArrowDown" && pickEl.options.length) {
    e.preventDefault();
    pickEl.focus();
  }
});
pickEl.addEventListener("change", () => {
  if (pickEl.value) chosen = pickEl.value;
  syncNote();
});
pickEl.addEventListener("keydown", (e) => { if (e.key === "Enter") runExport(); });
pickEl.addEventListener("dblclick", () => runExport());
runBtn.addEventListener("click", () => runExport());

fetchShortnames()
  .then((listing) => {
    zones = listing.zones;
    defaultShort = listing.default || defaultShort;
    chosen = defaultShort;
    renderPicker();
  })
  .catch((err) => {
    // No listing: typing a short name still exports (the server checks it).
    console.warn("[export]", err);
    filterEl.placeholder = "short name (list unavailable)";
    renderPicker();
  });
syncButton();
