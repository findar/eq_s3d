// main.ts — wires the UI, API, scene, and controls together

import * as THREE from "three";
import {
  generateZone, fetchControls, fetchSidecar, fetchVersion, fetchZoneTypes, rebuildZone,
  fetchZoneVersions,
  type DecorLayerListing, type GenerateParams, type GenerateResult, type RebuildParams,
  type ZoneSidecar, type ZoneVersionEntry,
} from "./api";
import { ZoneScene } from "./scene";
import { FirstPersonControls } from "./controls";
import { showArtifacts, loadMapSvg } from "./artifacts";
import { setExportBuild } from "./exportrow";
import { drawSockets } from "./sockets";
import { RoomView } from "./roomview";

// How a grown zone's rooms lean: "From rules", or a number or an overlay on top.
const SCALE_CONTROLS = ["finish", "structure", "clutter", "overlay"];

// The two generation modes, chosen explicitly by the Describe | Controls
// switch (or which field's Enter fired) — the server no longer infers it from
// the body shape.
type Mode = "prompt" | "controls";

// ---- DOM ----
const $ = (id: string) => document.getElementById(id)!;
const canvas = $("viewport") as HTMLCanvasElement;
const statusEl = $("status");
const generateBtn = $("generate") as HTMLButtonElement;
const promptInput = $("prompt") as HTMLInputElement;
const hintOverlay = $("hint-overlay");
const seedInput = $("seed") as HTMLInputElement;
const reproduceBtn = $("reproduce") as HTMLButtonElement;
const rerollDecorBtn = $("reroll-decor") as HTMLButtonElement;
const rerollRoomsBtn = $("reroll-rooms") as HTMLButtonElement;
const versionNav = $("version-nav");
const versionLabel = $("version-label");
const versionPrev = $("version-prev") as HTMLButtonElement;
const versionNext = $("version-next") as HTMLButtonElement;

// Latest generated map URL, shown by the Map modal.
let currentMapUrl: string | null = null;
// The latest build's sidecar, whose Sockets the map dialog marks.
let currentSidecar: ZoneSidecar | null = null;
// Seed of the last successful generation, for the "reproduce" affordance.
let lastSeed: number | null = null;
// The result of the version on screen: the rerolls and Use in zone rebuild
// from it (/api/rebuild {zone: id, version}).
let lastResult: GenerateResult | null = null;
// The open zone's versions (GET /api/zones/<zone>/versions), in order.
let versions: ZoneVersionEntry[] = [];
// Every answer this page has had, by "<zone>/v<n>": opening that version again
// shows it as built. A version made elsewhere is filled from its listing.
const results = new Map<string, GenerateResult>();
// The latest showBuild; a load still in flight from an earlier one is dropped.
let showSeq = 0;

// ---- Scene + controls ----
const zoneScene = new ZoneScene(canvas);
const controls = new FirstPersonControls(zoneScene.camera, canvas);

// The Room view (roomview.ts): one room re-decorated, over the viewport.
const roomView = new RoomView({
  decorSelect: $("decor") as HTMLSelectElement,
  layerSelect: $("decor-layers") as HTMLSelectElement,
  beforeOpen: () => closeMap(),
  // Use in zone: the room's decor seed kept in the next version, which opens
  // with the room view still on that room.
  useInZone: async (room, decorSeed) => {
    console.log(`[input] use in zone: ${room} decor_seed=${decorSeed}`);
    const err = await runRebuild({ room_decor: { room, decor_seed: decorSeed } }, room);
    if (err) throw new Error(err);
  },
});

controls.onLockChange = (locked) => {
  hintOverlay.classList.toggle("hidden", locked);
};

// ---- Overlay toggles ----
($("t-wire") as HTMLInputElement).addEventListener("change", (e) =>
  zoneScene.setWireframe((e.target as HTMLInputElement).checked)
);
($("t-lights") as HTMLInputElement).addEventListener("change", (e) =>
  zoneScene.setLightsVisible((e.target as HTMLInputElement).checked)
);
($("t-regions") as HTMLInputElement).addEventListener("change", (e) =>
  zoneScene.setRegionsVisible((e.target as HTMLInputElement).checked)
);
($("t-gates") as HTMLInputElement).addEventListener("change", (e) =>
  zoneScene.setGatesVisible((e.target as HTMLInputElement).checked)
);
($("t-labels") as HTMLInputElement).addEventListener("change", (e) =>
  zoneScene.setLabelsVisible((e.target as HTMLInputElement).checked)
);
const treesToggle = $("t-trees") as HTMLInputElement;

// Show or hide an overlay toggle's whole row (its <label>).
function showToggle(id: string, on: boolean): void {
  ($(id).closest("label") as HTMLElement).hidden = !on;
}
treesToggle.addEventListener("change", () =>
  zoneScene.setVegetationVisible(treesToggle.checked)
);

// ---- Build identity ----
// The backend runs without auto-reload, so code changed after it started is
// NOT what generates zones. Show which commit each side runs, and warn loudly
// when the server's source moved on (restart) or the frontend build doesn't
// match the server (rebuild/reload).
const buildLine = $("build-line");
const buildWarning = $("build-warning");

async function refreshVersion(): Promise<void> {
  const web = __WEB_COMMIT__;
  const warnings: string[] = [];
  let serverLabel = "?";
  try {
    const v = await fetchVersion();
    serverLabel = v.short + (v.dirty ? "*" : "");
    if (v.stale) {
      warnings.push(
        "<b>Server code changed since it started</b> — restart the server " +
        `(loaded ${v.short}${v.dirty ? "*" : ""}, ` +
        `started ${new Date(v.started_at).toLocaleTimeString()}).`,
      );
    }
    if (web !== "unknown" && v.short !== "unknown" && web !== v.short) {
      warnings.push(
        `<b>Frontend build doesn't match server</b> (web ${web}, server ${v.short}) ` +
        "— rebuild/reload the frontend or restart the server.",
      );
    }
    buildLine.title =
      `server ${v.commit} on ${v.branch}` + (v.dirty ? " (uncommitted changes)" : "") +
      `, started ${v.started_at}\nweb ${web}, built ${__WEB_BUILT_AT__}`;
  } catch (err) {
    // A server without /api/version predates this frontend — i.e. it's stale.
    console.warn("[version]", err);
    warnings.push(
      "<b>Couldn't read the server's version</b> — it may be running older " +
      "code than this frontend; restart the server.",
    );
  }
  buildLine.textContent = `server ${serverLabel} · web ${web}`;
  buildLine.classList.toggle("mismatch", warnings.length > 0);
  buildWarning.innerHTML = warnings.join("<br>");
  buildWarning.classList.toggle("hidden", warnings.length === 0);
}

// ---- Warnings ----
// Non-fatal advisories ride in the response as raw tokens
// (zone_type_substituted:<planned>-><built>, backend_fallback: <detail>).
// Render them as human-readable sentences in the #warnings status region, and
// clear it when a request produced none.
const warningsEl = $("warnings");

function warningToWords(w: string): string {
  const sub = w.match(/^zone_type_substituted:(.+?)->(.+)$/);
  if (sub) {
    return `Requested zone type "${sub[1]}" isn't available yet — built a ` +
      `"${sub[2]}" zone instead.`;
  }
  if (w.startsWith("backend_fallback")) {
    // e.g. "backend_fallback: terrain unavailable, built with box"
    const detail = w.slice("backend_fallback".length).replace(/^[:\s]+/, "");
    return detail
      ? `Geometry backend fell back — ${detail}.`
      : "Geometry backend fell back to the box builder.";
  }
  return w;   // unknown token: show it verbatim rather than hide it
}

function renderWarnings(warnings: string[] | undefined): void {
  warningsEl.innerHTML = "";
  if (!warnings || warnings.length === 0) return;
  for (const w of warnings) {
    const div = document.createElement("div");
    div.className = "warning";
    div.textContent = warningToWords(w);
    warningsEl.appendChild(div);
  }
}

// ---- Metrics panel ----
function updatePanel(result: GenerateResult, sidecar: ZoneSidecar) {
  const b = sidecar.bounds;
  const wx = (b.max[0] - b.min[0]).toFixed(0);
  const wy = (b.max[1] - b.min[1]).toFixed(0);
  const wz = (b.max[2] - b.min[2]).toFixed(0);

  // Plan readout. The resolved mode comes back from the server; show
  // "description (<planner>)" for prompt mode, "controls" otherwise.
  const modeLabel = result.mode === "prompt"
    ? `description (${result.planner})`
    : "controls";
  $("m-mode").textContent = modeLabel;
  $("m-zone-type").textContent = result.zone_type;
  $("m-rooms").textContent = String(result.rooms);
  // A wilderness lays out no rooms: its plan's count is a default nobody set.
  $("r-rooms").hidden = !usesControl(result.zone_type, "rooms");

  renderWarnings(result.warnings);

  const extra = $("m-plan-extra");
  extra.innerHTML = "";
  if (result.plan) {
    const p = result.plan;
    // Size and verticality only where the zone type reads them.
    const rows: [string, string][] = [
      ...(usesControl(p.zone_type, "size") ? [["Size", p.size] as [string, string]] : []),
      ...(usesControl(p.zone_type, "verticality")
        ? [["Verticality", p.verticality] as [string, string]] : []),
      ...(p.walls ? [["Walls", p.walls] as [string, string]] : []),
      ...(p.features && p.layout === "graph" ? [["Features", p.features] as [string, string]] : []),
      ...SCALE_CONTROLS.flatMap((id) => p[id] != null && p[id] !== ""
        ? [[id[0].toUpperCase() + id.slice(1), String(p[id])] as [string, string]] : []),
    ];
    if (usesControl(p.zone_type, "edges") && p.sites) {
      rows.push(["Sites", p.sites]);
      if (p.sites !== "none") rows.push(["Inhabitants", p.inhabitant || "biome's mix"]);
    }
    if (usesControl(p.zone_type, "decor") && p.decor) rows.push(["Decor", p.decor]);
    if (p.regions.length) rows.push(["Regions", p.regions.join(", ")]);
    if (p.mood) rows.push(["Mood", p.mood]);
    for (const [k, v] of rows) {
      const div = document.createElement("div");
      div.className = "row";
      div.innerHTML = `<span>${k}</span><span>${v}</span>`;
      extra.appendChild(div);
    }
  }

  $("m-seed").textContent = String(result.seed);
  // The seeds block; a sidecar from before it has none (the plan's, else "—").
  const seeds = sidecar.seeds;
  const roomsSeed = seeds?.rooms_seed ?? result.plan?.rooms_seed ?? null;
  const decorSeed = seeds?.decor_seed ?? result.plan?.decor_seed ?? null;
  $("m-rooms-seed").textContent = roomsSeed != null ? String(roomsSeed) : "—";
  $("m-decor-seed").textContent = decorSeed != null ? String(decorSeed) : "—";
  // The decor row and its reroll only when the build has Decor (placed Props).
  $("r-rooms-seed").hidden = roomsSeed == null;
  $("r-decor-seed").hidden = !sidecar.decor;
  $("s-seeds").hidden = roomsSeed == null && !sidecar.decor;
  $("m-build").textContent = result.build_commit ?? "unknown";
  $("m-verts").textContent = result.vertices.toLocaleString();
  $("m-polys").textContent = result.polygons.toLocaleString();
  $("m-mats").textContent = String(result.materials);
  $("m-lights").textContent = String(sidecar.lights.length);
  $("m-regions").textContent = String(sidecar.regions.length);
  $("m-gates").textContent = String((sidecar.gates ?? []).length);
  $("r-gates").hidden = (sidecar.gates ?? []).length === 0;
  $("m-wx").textContent = wx;
  $("m-wy").textContent = wy;
  $("m-wz").textContent = wz;

  updatePropsPanel(result, sidecar);

  // Pacing: role counts + max depth
  const pacing = $("m-pacing");
  pacing.innerHTML = "";
  $("s-pacing").hidden = !(sidecar.rooms && sidecar.rooms.length);
  if (sidecar.rooms && sidecar.rooms.length) {
    const counts: Record<string, number> = {};
    let maxDepth = 0;
    for (const r of sidecar.rooms) {
      counts[r.role] = (counts[r.role] || 0) + 1;
      if (r.graph_depth > maxDepth) maxDepth = r.graph_depth;
    }
    const order = ["entrance", "hub", "standard", "deadend", "climax"];
    for (const role of order) {
      if (!counts[role]) continue;
      const div = document.createElement("div");
      div.className = "row";
      div.innerHTML = `<span>${role}</span><span>${counts[role]}</span>`;
      pacing.appendChild(div);
    }
    const dd = document.createElement("div");
    dd.className = "row";
    dd.innerHTML = `<span>max depth</span><span>${maxDepth}</span>`;
    pacing.appendChild(dd);
  }

  // Content / semantic layer: content line, room-type counts, boss + a sample
  // of suggestions. Only shown when the zone was themed. Current sidecars carry
  // this under `content`; old sidecars used `theme`, so fall back to it.
  const content = $("m-content");
  content.innerHTML = "";
  const cnt = sidecar.content ?? sidecar.theme;
  const themed = !!(cnt && cnt.dungeon_theme);
  $("s-content").hidden = !(themed && sidecar.rooms && sidecar.rooms.length);
  if (themed && sidecar.rooms && sidecar.rooms.length) {
    const tbits: string[] = [cnt!.dungeon_theme!];
    if (cnt!.dungeon_race && cnt!.dungeon_race !== "default")
      tbits.push(cnt!.dungeon_race!);
    if (cnt!.elemental_tint) tbits.push(cnt!.elemental_tint!);
    const head = document.createElement("div");
    head.className = "row";
    head.innerHTML = `<span>Theme</span><span>${tbits.join(" · ")}</span>`;
    content.appendChild(head);

    const typeCounts: Record<string, number> = {};
    const bosses: ZoneSidecar["rooms"] = [];
    for (const r of sidecar.rooms) {
      const t = r.semantic_type || "—";
      typeCounts[t] = (typeCounts[t] || 0) + 1;
      if (r.boss) bosses.push(r);
    }
    for (const [t, n] of Object.entries(typeCounts).sort((a, b) => b[1] - a[1])) {
      const div = document.createElement("div");
      div.className = "row";
      div.innerHTML = `<span>${t}</span><span>${n}</span>`;
      content.appendChild(div);
    }
    for (const b of bosses) {
      const div = document.createElement("div");
      div.className = "row";
      div.innerHTML = `<span style="color:#ce93d8">boss</span>` +
        `<span style="color:#ce93d8">${b.semantic_type || b.role}</span>`;
      content.appendChild(div);
    }
    // One representative suggestion (climax/boss room if present, else first).
    const sample = bosses[0] ?? sidecar.rooms[0];
    if (sample && (sample.prop_hints?.length || sample.encounter_intent)) {
      const note = document.createElement("div");
      note.style.cssText = "font-size:10px;color:#8aa;margin-top:4px;line-height:1.4";
      const props = (sample.prop_hints ?? []).join(", ");
      note.innerHTML =
        `<b>${sample.semantic_type}</b><br>` +
        (props ? `props: ${props}<br>` : "") +
        (sample.encounter_intent ? `intent: ${sample.encounter_intent}` : "");
      content.appendChild(note);
    }
  }
}

// Props: the sidecar's decor block (control, decor seed, counts) and the
// placed Props by Category and by kind, read from the build: the rooms' and
// (wilderness, outdoor dungeon) the Sites'. A build without the install on
// the server has none, with a warning; the section shows only with Props.
function addRow(parent: HTMLElement, k: string, v: string, title = ""): void {
  const div = document.createElement("div");
  div.className = "row";
  const a = document.createElement("span");
  a.textContent = k;
  const b = document.createElement("span");
  b.textContent = v;
  if (title) div.title = title;
  div.append(a, b);
  parent.appendChild(div);
}

function updatePropsPanel(result: GenerateResult, sidecar: ZoneSidecar): void {
  const decorEl = $("m-decor");
  const list = $("m-props");
  list.innerHTML = "";
  rerollDecorBtn.disabled = !usesControl(result.zone_type, "decor");
  const d = sidecar.decor;
  $("s-props").hidden = !d;
  if (!d) return;
  decorEl.textContent = `${d.control} · seed ${d.seed}`;
  if (d.layers?.length) addRow(list, "Decor rules", d.layers.join(", "), "Decor layers merged on, in order");
  addRow(list, "Props", String(d.props));
  addRow(list, "Lights", String(d.lights));
  addRow(list, "Models", String(d.models));
  addRow(list, d.sites ? "Bare rooms + Sites" : "Bare rooms", `${d.bare} / ${d.rooms + (d.sites ?? 0)}`);
  addRow(list, "Dropped", String(d.drops), "Recipe lines that found no model or no spot");
  if (d.check.length) addRow(list, "Check", String(d.check.length), d.check.join("\n"));
  const byCat: Record<string, number> = {};
  const byKind: Record<string, number> = {};
  for (const r of [...(sidecar.rooms ?? []), ...(sidecar.sites?.sites ?? [])]) {
    for (const p of r.props ?? []) {
      byCat[p.category] = (byCat[p.category] || 0) + 1;
      byKind[p.kind] = (byKind[p.kind] || 0) + 1;
    }
  }
  const cats = Object.entries(byCat).sort((a, b) => b[1] - a[1]);
  if (cats.length) {
    const note = document.createElement("div");
    note.style.cssText = "font-size:10px;color:#8aa;margin-top:4px;line-height:1.4";
    const kinds = Object.entries(byKind).sort((a, b) => b[1] - a[1]).slice(0, 8);
    note.textContent =
      cats.map(([c, n]) => `${c} ${n}`).join(" · ") + " — " +
      kinds.map(([k, n]) => `${k} ${n}`).join(", ");
    list.appendChild(note);
  }
}

// ---- Generate ----
// The seed box feeds both modes. Blank or non-numeric → omit (the server picks
// a fresh random seed, the default "identical inputs still vary" behaviour). A
// number pins the seed so the same inputs reproduce the exact zone;
// negative/decimal input is floored to a non-negative integer.
function readSeed(): number | undefined {
  const seedRaw = seedInput.value.trim();
  if (seedRaw === "") return undefined;
  const n = Number(seedRaw);
  return Number.isFinite(n) ? Math.abs(Math.trunc(n)) : undefined;
}

// The zone types each Controls-panel control applies to; for the others it is
// hidden and not sent (the server ignores it there). "edges" is the Landscape
// group (map edges, trees, Sites); the rest are the room-graph controls.
// Mirrors the server's expand path: rooms and locks reach an outdoor dungeon's
// layout, size only a dungeon's or city's; verticality a dungeon's (classic or
// graph layout), a city's and an outdoor dungeon's (step 7: it scales the
// Levels the hill holds); layout a dungeon's or outdoor dungeon's (server
// LAYOUT_ZONE_TYPES); the dungeon theme and race every room-graph type's
// (server CONTENT_ZONE_TYPES: a city goes through the same semantic layer as a
// dungeon). Keys are the control's element id. `applies` adds the rules that
// hang on another control.
const CONTROL_ZONE_TYPES: Record<string, readonly string[]> = {
  rooms: ["dungeon", "city", "outdoor_dungeon"],
  locks: ["dungeon", "city", "outdoor_dungeon"],
  size: ["dungeon", "city"],
  verticality: ["dungeon", "city", "outdoor_dungeon"],
  edges: ["wilderness", "outdoor_dungeon"],
  layout: ["dungeon", "outdoor_dungeon"],
  "dungeon-theme": ["dungeon", "city", "outdoor_dungeon"],
  "dungeon-race": ["dungeon", "city", "outdoor_dungeon"],
  // Replaced by /api/controls' decor.zone_types on load (refreshControls).
  decor: ["dungeon", "city", "wilderness", "outdoor_dungeon"],
  // Every zone type (server: rooms_seed on any plan).
  "rooms-seed": ["dungeon", "city", "wilderness", "outdoor_dungeon"],
};

function usesControl(zoneType: string, control: string): boolean {
  return CONTROL_ZONE_TYPES[control].includes(zoneType);
}

// How many decor layers /api/controls listed (refreshControls): with none the
// Decor rules control has nothing to offer past "From theme", so it hides.
let decorLayerCount = 0;

// What the visibility rules read: the zone type and the controls that gate
// others (Layout, Decor, Sites).
interface ControlState { zoneType: string; layout: string; decor: string; sites: string }

function readControlState(): ControlState {
  const v = (id: string) => ($(id) as HTMLSelectElement).value;
  return { zoneType: v("zone-type"), layout: v("layout"), decor: v("decor"), sites: v("sites") };
}

// Map edges: one selector per side.
const EDGE_SIDES = ["N", "E", "S", "W"];

function readEdges(): Record<string, string> {
  const edges: Record<string, string> = {};
  for (const s of EDGE_SIDES) {
    edges[s] = ($(`edge-${s.toLowerCase()}`) as HTMLSelectElement).value;
  }
  return edges;
}

// The Landscape group's controls: shown (and sent) on a landscape zone type.
const LANDSCAPE_CONTROLS = ["edge-n", "edge-e", "edge-s", "edge-w", "trees", "sites"];

// Whether a control applies: the server would read it for the zone type and
// the gating choices on screen. A control that doesn't apply is hidden and not
// sent (Req 2.1, 2.3).
function applies(id: string, s: ControlState): boolean {
  if (id === "zone-type") return true;
  // The rule set and how the grown rooms lean: the graph engine only.
  if (id === "rule-set" || SCALE_CONTROLS.includes(id)) {
    return applies("layout", s) && s.layout === "graph";
  }
  if (LANDSCAPE_CONTROLS.includes(id)) return usesControl(s.zoneType, "edges");
  // Who builds the Sites: only when there are Sites.
  if (id === "inhabitant") return usesControl(s.zoneType, "edges") && s.sites !== "none";
  // The decor seed rerolls Props: none to reroll under Decor None.
  if (id === "decor-seed") return usesControl(s.zoneType, "decor") && s.decor !== "none";
  // Decor rules: the same, and only when /api/controls lists some layers.
  if (id === "decor-layers") {
    return decorLayerCount > 0 && usesControl(s.zoneType, "decor") && s.decor !== "none";
  }
  return usesControl(s.zoneType, id);
}

function syncControlVisibility(): void {
  const state = readControlState();
  // `hidden` does the hiding: the stylesheet's `[hidden]` rule beats the grid
  // display of a `label.field` and the flex of a `fieldset.group`.
  for (const field of document.querySelectorAll<HTMLElement>("#controls-panel label.field")) {
    const control = field.querySelector("select, input");
    if (control) field.hidden = !applies(control.id, state);
  }
  // A group with nothing showing hides.
  for (const group of document.querySelectorAll<HTMLElement>("#controls-panel fieldset.group")) {
    const fields = [...group.querySelectorAll<HTMLElement>("label.field")];
    group.hidden = fields.every((f) => f.hidden);
  }
}

// The bar wraps by whole groups when narrow; keep --header-h at its real
// height so the viewport, side panel and banner start below it, and let the
// scene re-fit its canvas.
const headerEl = $("controls");
new ResizeObserver(() => {
  const h = Math.ceil(headerEl.getBoundingClientRect().height);
  if (document.documentElement.style.getPropertyValue("--header-h") !== `${h}px`) {
    document.documentElement.style.setProperty("--header-h", `${h}px`);
    window.dispatchEvent(new Event("resize"));
  }
}).observe(headerEl);

async function doGenerate(mode: Mode) {
  const seed = readSeed();
  const prompt = promptInput.value.trim();

  // Prompt mode needs a description: with none, nothing is sent (Generate is
  // disabled then; this catches Enter in an empty box). No silent fallback to
  // the Controls, which are off screen in Describe mode.
  if (mode === "prompt" && prompt === "") return;

  // Build the request body per the server's explicit-mode contract: prompt mode
  // sends {mode, prompt}, controls mode sends {mode, controls:{…}}; seed rides
  // on either when set.
  let params: GenerateParams;
  const seedNote = seed !== undefined ? ` seed=${seed}` : " seed=random";
  if (mode === "prompt") {
    params = { mode, prompt, ...(seed !== undefined ? { seed } : {}) };
    console.log(`[input] description: "${prompt}"${seedNote}`);
  } else {
    const state = readControlState();
    const zoneType = state.zoneType;
    const on = (id: string) => applies(id, state);
    const sel = (id: string) => ($(id) as HTMLSelectElement).value;
    // Only controls that apply are sent (Req 2.3); the server ignores the rest
    // and builds the same zone, sidecar and all, without them (two exceptions
    // below). Rooms/locks are free number
    // inputs; clamp to the server's accepted ranges and fall back to a sane
    // default if blank/unparseable so an out-of-range value never trips the
    // backend's validation.
    const roomsRaw = parseInt(($("rooms") as HTMLInputElement).value, 10);
    const rooms = !on("rooms") ? undefined
      : Number.isFinite(roomsRaw) ? Math.min(30, Math.max(1, roomsRaw)) : 5;
    const locksRaw = parseInt(($("locks") as HTMLInputElement).value, 10);
    const locks = !on("locks") ? undefined
      : Number.isFinite(locksRaw) ? Math.min(5, Math.max(0, locksRaw)) : 0;
    const size = on("size") ? sel("size") : undefined;
    const verticality = on("verticality") ? sel("verticality") : undefined;
    const edges = on("edge-n") ? readEdges() : undefined;
    const trees = on("trees") ? sel("trees") : undefined;
    // Sites and who builds them: landscape only; "" is the biome's mix. With
    // Sites None the Inhabitants box hides but is still sent: the build is the
    // same either way, but the sidecar's sites block records it.
    const sites = on("sites") ? sel("sites") : undefined;
    const inhabitant = on("sites") ? sel("inhabitant") : undefined;
    // Left out, the server's defaults: graph on a dungeon / outdoor dungeon,
    // the theme's set; the rule set rides only with the graph engine.
    const layout = on("layout") ? sel("layout") : undefined;
    const ruleSet = on("rule-set") ? sel("rule-set") : undefined;
    // Scale controls: "" is the rules alone.
    const scales: Record<string, string> = Object.fromEntries(
      SCALE_CONTROLS.filter(on).map((id) => [id, sel(id)]));
    // Theme and race: "" (None) is sent as-is.
    const dungeonTheme = on("dungeon-theme") ? sel("dungeon-theme") : undefined;
    const dungeonRace = on("dungeon-race") ? sel("dungeon-race") : undefined;
    // Decor and its seed. An empty list (no /api/controls) or a blank seed is
    // left out: the server's defaults. Under Decor None the seed box hides but
    // is still sent: no Props either way, but the sidecar's seeds block
    // records it.
    const decor = on("decor") ? sel("decor") || undefined : undefined;
    const decorSeed = on("decor") ? readDecorSeed() : undefined;
    // Decor rules: "From theme" ("") sends nothing.
    const decorLayer = on("decor-layers") ? sel("decor-layers") : "";
    // The rooms seed: blank is left out (the zone's).
    const roomsSeed = on("rooms-seed") ? readStageSeed("rooms-seed") : undefined;
    params = {
      mode,
      controls: {
        zone_type: zoneType,
        ...(rooms !== undefined ? { room_count: rooms } : {}),
        ...(size !== undefined ? { size } : {}),
        ...(verticality !== undefined ? { verticality } : {}),
        ...(locks !== undefined ? { locks } : {}),
        ...(edges ? { edges } : {}),
        ...(trees ? { trees } : {}),
        ...(sites ? { sites } : {}),
        ...(inhabitant !== undefined ? { inhabitant } : {}),
        ...(layout ? { layout } : {}),
        ...(ruleSet !== undefined ? { rule_set: ruleSet } : {}),
        ...scales,
        ...(dungeonTheme !== undefined ? { dungeon_theme: dungeonTheme } : {}),
        ...(dungeonRace !== undefined ? { dungeon_race: dungeonRace } : {}),
        ...(decor !== undefined ? { decor } : {}),
        ...(decorSeed !== undefined ? { decor_seed: decorSeed } : {}),
        ...(decorLayer ? { decor_layers: [decorLayer] } : {}),
        ...(roomsSeed !== undefined ? { rooms_seed: roomsSeed } : {}),
      },
      ...(seed !== undefined ? { seed } : {}),
    };
    console.log(
      `[input] controls: zone_type=${zoneType}` +
      (rooms !== undefined ? ` rooms=${rooms}` : "") +
      (size !== undefined ? ` size=${size}` : "") +
      (verticality !== undefined ? ` verticality=${verticality}` : "") +
      (locks !== undefined ? ` locks=${locks}` : "") +
      (edges ? ` edges=${JSON.stringify(edges)}` : "") +
      (trees ? ` trees=${trees}` : "") +
      (sites ? ` sites=${sites}` : "") +
      (inhabitant !== undefined ? ` inhabitant=${inhabitant || "(biome)"}` : "") +
      (layout ? ` layout=${layout}` : "") +
      (ruleSet !== undefined ? ` rule_set=${ruleSet || "(theme)"}` : "") +
      Object.entries(scales).map(([id, v]) => ` ${id}=${v || "(rules)"}`).join("") +
      (dungeonTheme !== undefined ? ` theme=${dungeonTheme || "(none)"}` : "") +
      (dungeonRace !== undefined ? ` race=${dungeonRace || "(none)"}` : "") +
      (decor !== undefined ? ` decor=${decor}` : "") +
      (decorSeed !== undefined ? ` decor_seed=${decorSeed}` : "") +
      (decorLayer ? ` decor_layers=${decorLayer}` : "") +
      (roomsSeed !== undefined ? ` rooms_seed=${roomsSeed}` : "") + seedNote,
    );
  }
  await runGenerate(params);
}

// While a request runs (Generate, a rebuild, opening a version): Generate,
// the rerolls and the version arrows are disabled; the zone on screen stays
// until the new one has loaded.
function beginBusy(text: string): void {
  generating = true;
  syncGenerateButton();
  rerollDecorBtn.disabled = true;
  rerollRoomsBtn.disabled = true;
  statusEl.textContent = text;
  statusEl.title = "";
  syncVersionNav();
}

function endBusy(): void {
  generating = false;
  syncGenerateButton();
  rerollDecorBtn.disabled = !(lastResult && usesControl(lastResult.zone_type, "decor"));
  rerollRoomsBtn.disabled = !lastResult;
  syncVersionNav();
}

// Say a request failed in the status line (its words in the tooltip and the
// console) and answer the words.
function failed(what: string, err: unknown): string {
  console.error(err);
  const msg = String((err as Error)?.message ?? err);
  statusEl.textContent = `${what} — see console`;
  statusEl.title = msg;
  return msg;
}

const versionKey = (zone: string, n: number) => `${zone}/v${n}`;

// Send one generate request and show what it built.
async function runGenerate(params: GenerateParams): Promise<void> {
  if (generating) return;
  beginBusy("generating…");
  roomView.close();

  // Cheap re-check so a stale-server warning shows exactly when it matters.
  await refreshVersion();

  try {
    const result = await generateZone(params);
    results.set(versionKey(result.id, result.version), result);
    statusEl.textContent = "loading…";
    if (!(await showBuild(result, false))) return;
    await refreshVersions(result.id);
    console.info(
      `[generate] seed=${result.seed} zone_type=${result.zone_type} rooms=${result.rooms} ` +
      `mode=${result.mode}` +
      (result.planner ? ` planner=${result.planner}` : "") +
      ` build=${result.build_commit ?? "unknown"}`,
    );
  } catch (err) {
    failed("error", err);
  } finally {
    endBusy();
  }
}

// The next version of the open one (/api/rebuild), opened once it's in with the
// camera where it is. `reopenRoom`: the room view stays open and shows that
// room of the new version (Use in zone). Answers the error's words, or null.
async function runRebuild(
  change: Omit<RebuildParams, "zone" | "version">, reopenRoom?: string,
): Promise<string | null> {
  if (generating || !lastResult) return "another request is running";
  const from = lastResult;
  const params: RebuildParams = { zone: from.id, version: from.version, ...change };
  beginBusy(`rebuilding from v${from.version}…`);
  if (!reopenRoom) roomView.close();
  await refreshVersion();
  try {
    const result = await rebuildZone(params);
    results.set(versionKey(result.id, result.version), result);
    statusEl.textContent = `loading v${result.version}…`;
    await refreshVersions(result.id);
    await showBuild(result, true, reopenRoom);
    const info = result.version_info;
    console.info(
      `[rebuild] ${result.id} v${from.version} -> v${result.version}` +
      (info ? ` (${info.changed.join(", ")}, ${info.how ?? "?"})` : ""),
    );
    return null;
  } catch (err) {
    return failed("rebuild failed", err);
  } finally {
    endBusy();
  }
}

// A version of the open zone, from the listing: the answer this page had for
// it, else the open one's with that version's URLs (its Files have the same
// names under v<n>/; one the version lacks shows unavailable).
function resultFor(entry: ZoneVersionEntry): GenerateResult | null {
  if (!lastResult) return null;
  const known = results.get(versionKey(lastResult.id, entry.n));
  if (known) return known;
  const base = lastResult;
  const from = `/v${base.version}/`, to = `/v${entry.n}/`;
  return {
    ...base,
    version: entry.n,
    seed: entry.seeds?.seed ?? base.seed,
    glb_url: entry.glb_url,
    zone_url: entry.zone_url,
    map_url: entry.map_url,
    eqg_url: entry.eqg_url,
    artifacts: (base.artifacts ?? []).map((a) => ({ ...a, url: a.url.replace(from, to) })),
    warnings: [],
    build_commit: undefined,
  };
}

// Open another version of the zone on screen, keeping the camera.
async function openVersion(n: number): Promise<void> {
  if (generating || !lastResult || n === lastResult.version) return;
  const entry = versions.find((v) => v.n === n);
  const result = entry ? resultFor(entry) : null;
  if (!result) return;
  console.log(`[input] open version: ${result.id} v${n}`);
  beginBusy(`opening v${n}…`);
  roomView.close();
  try {
    const known = results.has(versionKey(result.id, n));
    await showBuild(result, true, undefined, !known);
  } catch (err) {
    failed(`v${n} unavailable`, err);
  } finally {
    endBusy();
  }
}

// Show a build: its sidecar and GLB load first (the zone on screen stays until
// then), then the map, Files, overlays and panel switch to it. `keepCamera`:
// another version of the same zone, so the camera stays (Reset View goes to
// the new start). `fromSidecar`: a result filled from the listing, whose
// counts come from the sidecar. False when a later showBuild overtook it.
async function showBuild(
  result: GenerateResult, keepCamera: boolean, reopenRoom?: string, fromSidecar = false,
): Promise<boolean> {
  const seq = ++showSeq;
  const sidecar = await fetchSidecar(result.zone_url);
  if (seq !== showSeq) return false;
  if (fromSidecar && sidecar.metrics) result = { ...result, ...sidecar.metrics };
  const box = await zoneScene.loadZone(result.glb_url, () => seq === showSeq);
  if (!box) return false;

  currentMapUrl = result.map_url;
  currentSidecar = sidecar;
  // Rebuild the Files list (and drop the previous build's map + PNG).
  showArtifacts(result.artifacts ?? [], result.id);
  // The Export row exports this version; an earlier version's Export clears.
  setExportBuild(result.id, result.version);
  mapDownload.download = `${result.id}.map.svg`;
  lastSeed = result.seed;
  lastResult = result;
  reproduceBtn.disabled = false;

  // The Trees toggle only means something when the GLB has a vegetation
  // node; keep the user's last choice across builds (and the wireframe's).
  showToggle("t-trees", zoneScene.hasVegetation());
  zoneScene.setVegetationVisible(treesToggle.checked);
  zoneScene.setWireframe(($("t-wire") as HTMLInputElement).checked);
  zoneScene.applyOverlays(sidecar);
  // An overlay toggle shows only when the build has what it toggles;
  // Wireframe and Room IDs always.
  showToggle("t-lights", zoneScene.hasLights());
  showToggle("t-regions", zoneScene.hasRegions());
  showToggle("t-gates", zoneScene.hasGates());
  updatePanel(result, sidecar);
  syncVersionNav();
  roomView.setBuild({ zone: result.id, version: result.version, sidecar }, reopenRoom);
  $("panel-empty").hidden = true;
  $("panel-body").hidden = false;
  // A map dialog left open re-renders with this build's SVG and Sockets.
  if (!mapModal.classList.contains("hidden")) openMap();

  // Place the camera near the zone's lowest/entry corner at a sensible
  // eye height, looking toward the centre. World is Z-up and the mesh is
  // centred on the origin, so the centre is roughly (0,0,0).
  const size = box.getSize(new THREE.Vector3());
  const groundZ = -size.z / 2;        // bottom of the centred mesh
  const eye = Math.min(60, size.z * 0.3);
  // Stand back along -Y, near the floor, looking toward +Y (yaw = +90°).
  const start = new THREE.Vector3(0, -size.y * 0.45, groundZ + eye);
  const startYaw = Math.PI / 2;       // face +Y (into the zone)
  controls.setStart(start, startYaw, !keepCamera);

  statusEl.textContent = `v${result.version} · seed ${result.seed} · ` +
    `${result.polygons.toLocaleString()} polys`;
  return true;
}

// ---- Versions ----
// The header's v<n> with ◂ ▸ through the zone's versions, shown only when it
// has more than one; the side panel's Version row says where the open one
// came from.
const CHANGED_WORDS: Record<string, string> = {
  decor_seed: "decor seed",
  rooms_seed: "rooms seed",
  room_decor: "room decor",
};

async function refreshVersions(zone: string): Promise<void> {
  try {
    versions = (await fetchZoneVersions(zone)).versions;
  } catch (err) {
    console.warn("[versions]", err);   // a server without versions: the one alone
    versions = [];
  }
  syncVersionNav();
}

function syncVersionNav(): void {
  const n = lastResult?.version ?? 0;
  const i = versions.findIndex((v) => v.n === n);
  versionNav.hidden = versions.length <= 1;
  versionNav.classList.toggle("busy", generating);
  versionLabel.textContent = `v${n}`;
  versionPrev.disabled = generating || i <= 0;
  versionNext.disabled = generating || i < 0 || i >= versions.length - 1;

  // The Version row: v3 of 3 · from v2 · decor seed (the sidecar's block,
  // else the listing's).
  const block = currentSidecar?.version ?? versions[i];
  const last = versions.length ? versions[versions.length - 1].n : n;
  const row = $("r-version");
  row.hidden = versions.length <= 1 && !block?.parent;
  const bits = [`v${n} of ${Math.max(last, n)}`];
  if (block?.parent) bits.push(`from v${block.parent}`);
  if (block?.changed?.length) {
    bits.push(block.changed.map((c) => CHANGED_WORDS[c] ?? c.replace(/_/g, " ")).join(", "));
  }
  $("m-version").textContent = bits.join(" · ");
  row.title = block?.how === "partial" ? "Rebuilt from its parent's saved stages"
    : block?.how === "full" ? "Built again in full from its parent's request" : "";
}

// ◂ ▸: the version before or after the open one in the listing.
function stepVersion(d: number): void {
  const i = versions.findIndex((v) => v.n === lastResult?.version);
  const next = versions[i + d];
  if (i >= 0 && next) openVersion(next.n);
}
versionPrev.addEventListener("click", () => stepVersion(-1));
versionNext.addEventListener("click", () => stepVersion(1));

// A stage seed box: blank or non-numeric -> undefined (the zone's seed).
function readStageSeed(id: string): number | undefined {
  const raw = ($(id) as HTMLInputElement).value.trim();
  if (raw === "") return undefined;
  const n = Number(raw);
  return Number.isFinite(n) ? Math.min(2147483647, Math.abs(Math.trunc(n))) : undefined;
}

function readDecorSeed(): number | undefined {
  return readStageSeed("decor-seed");
}

// Reroll rooms: the next version of the open one with a fresh rooms seed, so
// the World stays and the rooms and Sites change (world-sockets Req 4.3; a
// full rebuild).
rerollRoomsBtn.addEventListener("click", () => {
  if (!lastResult) return;
  const roomsSeed = Math.floor(Math.random() * 2147483648);
  console.log(`[input] reroll rooms: ${lastResult.id} v${lastResult.version} rooms_seed=${roomsSeed}`);
  runRebuild({ rooms_seed: roomsSeed });
});

// Reroll decor: the next version of the open one with a fresh decor seed, so
// only the Props change (room-decor Req 10.2; a partial rebuild).
rerollDecorBtn.addEventListener("click", () => {
  if (!lastResult) return;
  const decorSeed = Math.floor(Math.random() * 2147483648);
  console.log(`[input] reroll decor: ${lastResult.id} v${lastResult.version} decor_seed=${decorSeed}`);
  runRebuild({ decor_seed: decorSeed });
});

// Fill the Decor list from the server (/api/controls), keeping the user's
// choice when it survives, else the server's default; the zone types it
// applies to come from there too. The Decor rules list gets "From theme" and
// each listed layer (its description as the option's title).
async function refreshControls(): Promise<void> {
  try {
    const listing = await fetchControls();
    fillDecorLayers(listing.decor_layers ?? []);
    const decor = listing.decor;
    if (decor?.values?.length) {
      const sel = $("decor") as HTMLSelectElement;
      const prev = sel.value;
      sel.innerHTML = "";
      for (const v of decor.values) {
        const opt = document.createElement("option");
        opt.value = v;
        opt.textContent = v.charAt(0).toUpperCase() + v.slice(1);
        sel.appendChild(opt);
      }
      sel.value = decor.values.includes(prev) ? prev : decor.default;
      if (decor.zone_types?.length) CONTROL_ZONE_TYPES.decor = decor.zone_types;
    }
  } catch (err) {
    console.warn("[controls]", err);    // empty list: the server's default
  }
  syncControlVisibility();
}

function fillDecorLayers(layers: DecorLayerListing[]): void {
  const sel = $("decor-layers") as HTMLSelectElement;
  const prev = sel.value;
  sel.innerHTML = "";
  const theme = document.createElement("option");
  theme.value = "";
  theme.textContent = "From theme";
  theme.title = "The theme's decor rules alone";
  sel.appendChild(theme);
  for (const layer of layers) {
    const opt = document.createElement("option");
    opt.value = layer.name;
    opt.textContent = layer.name.replace(/_/g, " ");
    opt.title = layer.description;
    sel.appendChild(opt);
  }
  sel.value = layers.some((l) => l.name === prev) ? prev : "";
  decorLayerCount = layers.length;
}

// Populate the zone-type dropdown from the server's single source of truth.
// Each entry is {name, enabled, reason}: a DISABLED type is rendered as a
// disabled <option> whose text and title carry the reason (so it's visible but
// unselectable — not hidden), and the first ENABLED type is preselected (or the
// current selection if it survives and is still enabled). The static <option>s
// in index.html are the offline fallback if the fetch fails.
function zoneTypeLabel(z: string): string {
  const words = z.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

async function refreshZoneTypes(): Promise<void> {
  const sel = $("zone-type") as HTMLSelectElement;
  try {
    const listing = await fetchZoneTypes();
    const types = listing.zone_types;
    if (!types?.length) return;
    const prev = sel.value;

    sel.innerHTML = "";
    for (const zt of types) {
      const opt = document.createElement("option");
      opt.value = zt.name;
      if (zt.enabled) {
        opt.textContent = zoneTypeLabel(zt.name);
      } else {
        opt.disabled = true;
        const reason = zt.reason ?? "not available yet";
        opt.textContent = `${zoneTypeLabel(zt.name)} — ${reason}`;
        opt.title = reason;
      }
      sel.appendChild(opt);
    }

    // Keep a surviving, still-enabled selection; else the server default when
    // it's enabled; else the first enabled option.
    const enabled = types.filter((z) => z.enabled).map((z) => z.name);
    const prevOk = enabled.includes(prev);
    const defaultOk = listing.default && enabled.includes(listing.default);
    sel.value = prevOk ? prev : (defaultOk ? listing.default : (enabled[0] ?? ""));
  } catch (err) {
    console.warn("[zone_types]", err);   // keep the static options
  }
  syncControlVisibility();
}

// The controls that gate others: re-run the visibility rules on each change.
for (const id of ["zone-type", "layout", "decor", "sites"]) {
  $(id).addEventListener("change", syncControlVisibility);
}

// ---- Generate mode ----
// Describe shows the description box, Controls the Controls panel (folded
// away by the chevron when the user wants the view); the one Generate button
// sends the chosen mode. Both the mode and the panel's open state are
// remembered per browser; storage can throw (private windows, blocked site
// data), so every access is guarded and the page works without it.
const MODE_KEY = "eq_s3d.mode";
const OPEN_KEY = "eq_s3d.controlsOpen";

function loadPref(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
function savePref(key: string, value: string): void {
  try { localStorage.setItem(key, value); } catch { /* the page works without it */ }
}

// Controls is the default with nothing remembered (archive decision 2).
let mode: Mode = loadPref(MODE_KEY) === "prompt" ? "prompt" : "controls";
let controlsOpen = loadPref(OPEN_KEY) !== "false";
// True while a request is in flight: Generate stays disabled.
let generating = false;

const modeButtons: Record<Mode, HTMLButtonElement> = {
  prompt: $("mode-describe") as HTMLButtonElement,
  controls: $("mode-controls") as HTMLButtonElement,
};
const controlsToggle = $("controls-toggle") as HTMLButtonElement;
const controlsPanel = $("controls-panel");

// Generate is disabled while a request runs, and in Describe mode while the
// description is empty (archive decision 3).
function syncGenerateButton(): void {
  generateBtn.disabled = generating || (mode === "prompt" && promptInput.value.trim() === "");
  generateBtn.title = mode === "prompt"
    ? (promptInput.value.trim() === "" ? "Type a description first" : "Generate from the description")
    : "Generate from the Controls";
}

function applyMode(): void {
  for (const m of ["prompt", "controls"] as Mode[]) {
    const on = m === mode;
    modeButtons[m].setAttribute("aria-checked", String(on));
    modeButtons[m].tabIndex = on ? 0 : -1;
  }
  promptInput.hidden = mode !== "prompt";
  controlsToggle.hidden = mode !== "controls";
  controlsPanel.hidden = mode !== "controls" || !controlsOpen;
  controlsToggle.setAttribute("aria-expanded", String(controlsOpen));
  controlsToggle.textContent = controlsOpen ? "▾" : "▸";
  syncGenerateButton();
}

function setMode(m: Mode, focus = false): void {
  mode = m;
  savePref(MODE_KEY, m);
  applyMode();
  if (focus) modeButtons[m].focus();
}

modeButtons.prompt.addEventListener("click", () => setMode("prompt"));
modeButtons.controls.addEventListener("click", () => setMode("controls"));
// Radio-group keys: the arrows move the choice. They stop here so they never
// reach the camera (controls.ts only skips form fields).
$("mode-switch").addEventListener("keydown", (e) => {
  const ev = e as KeyboardEvent;
  if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(ev.key)) {
    ev.preventDefault();
    ev.stopPropagation();
    setMode(mode === "prompt" ? "controls" : "prompt", true);
  }
});
controlsToggle.addEventListener("click", () => {
  controlsOpen = !controlsOpen;
  savePref(OPEN_KEY, String(controlsOpen));
  applyMode();
});
promptInput.addEventListener("input", syncGenerateButton);
applyMode();

generateBtn.addEventListener("click", () => doGenerate(mode));

// Reset View button — return the camera to its starting position/orientation
$("reset-view").addEventListener("click", () => {
  controls.reset();
  console.log("[input] reset view");
});

// Enter routing is per field: Enter in the description → prompt mode; Enter in
// any Controls-panel field → controls mode; Enter in the shared seed box →
// the chosen mode.
promptInput.addEventListener("keydown", (e) => {
  if ((e as KeyboardEvent).key === "Enter") doGenerate("prompt");
});
seedInput.addEventListener("keydown", (e) => {
  if ((e as KeyboardEvent).key === "Enter") doGenerate(mode);
});

for (const id of ["zone-type", "rooms", "size", "verticality", "locks",
                  "edge-n", "edge-e", "edge-s", "edge-w", "trees", "sites", "inhabitant",
                  "layout", "rule-set", ...SCALE_CONTROLS, "dungeon-theme", "dungeon-race",
                  "decor", "decor-layers", "decor-seed", "rooms-seed"]) {
  $(id).addEventListener("keydown", (e) => {
    if ((e as KeyboardEvent).key === "Enter") doGenerate("controls");
  });
}

// Reproduce last: refill the seed box with the last result's seed and copy it
// to the clipboard, so the next Generate reruns the exact same zone.
reproduceBtn.addEventListener("click", () => {
  if (lastSeed === null) return;
  seedInput.value = String(lastSeed);
  console.log(`[input] reproduce: seed set to ${lastSeed}`);
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(String(lastSeed)).catch(() => {/* non-fatal */});
  }
  const prev = reproduceBtn.textContent;
  reproduceBtn.textContent = "✓ seed set";
  setTimeout(() => { reproduceBtn.textContent = prev; }, 1200);
});

// ---- Top-down map modal ----
const mapModal = $("map-modal");
const mapBody = $("map-body");
const mapDownload = $("map-download") as HTMLAnchorElement;

async function openMap() {
  if (!currentMapUrl) return;
  try {
    // Inline SVG so it scales crisply; fetched once per build (artifacts.ts).
    mapBody.innerHTML = await loadMapSvg(currentMapUrl);
    // The Sockets go on the dialog's copy only, so the downloads stay the
    // server's map; the sidecar comes in after the map URL, so a dialog
    // opened in between is redrawn with them (runGenerate).
    const svg = mapBody.querySelector("svg");
    if (svg && currentSidecar) drawSockets(svg, currentSidecar);
    if (svg) {
      // Its shape, so the CSS can fit it to the window both ways (larger as well as smaller).
      const vb = svg.viewBox.baseVal;
      if (vb && vb.width > 0 && vb.height > 0) svg.style.setProperty("--map-aspect", String(vb.width / vb.height));
      roomView.wireMap(svg);
    }
    mapDownload.href = currentMapUrl;
    mapModal.classList.remove("hidden");
  } catch (err) {
    console.error(err);
    statusEl.textContent = "map unavailable — see console";
  }
}

function closeMap() {
  mapModal.classList.add("hidden");
}

$("show-map").addEventListener("click", openMap);
$("map-close").addEventListener("click", closeMap);
// Click the dim backdrop (but not the dialog) to close.
mapModal.addEventListener("click", (e) => {
  if (e.target === mapModal) closeMap();
});
// Movement keys stay out of the camera while a Files link or the map dialog has
// focus: controls.ts only skips form fields, and links/buttons aren't those.
// Stop them here, before they bubble to its document listener; the default
// action (Enter follows the link, arrows scroll) is untouched.
const MOVE_KEYS = new Set([
  "KeyW", "KeyA", "KeyS", "KeyD", "KeyQ", "KeyE", "KeyR", "Space",
  "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "ShiftLeft", "ShiftRight",
]);
for (const id of ["artifacts", "map-dialog", "version-nav"]) {
  $(id).addEventListener("keydown", (e) => {
    if (MOVE_KEYS.has((e as KeyboardEvent).code)) e.stopPropagation();
  });
}

// M toggles the map, Esc closes it — but not while typing in a field.
document.addEventListener("keydown", (e) => {
  const ev = e as KeyboardEvent;
  const el = ev.target as HTMLElement | null;
  const typing = el && (el.tagName === "INPUT" || el.tagName === "SELECT" ||
    el.tagName === "TEXTAREA" || el.isContentEditable);
  if (typing) return;
  if (ev.key === "m" || ev.key === "M") {
    mapModal.classList.contains("hidden") ? openMap() : closeMap();
  } else if (ev.key === "Escape" && !mapModal.classList.contains("hidden")) {
    closeMap();
  }
});

// ---- Render loop ----
let last = performance.now();
function animate() {
  requestAnimationFrame(animate);
  const now = performance.now();
  const dt = Math.min((now - last) / 1000, 0.05);
  last = now;
  // While the Room view is open the zone neither moves nor draws.
  if (roomView.isOpen) return;
  controls.update(dt);
  zoneScene.render();
}
animate();

// Populate zone types, then generate one on load (controls mode) so the
// viewport isn't empty.
Promise.all([refreshZoneTypes(), refreshControls()]).finally(() => doGenerate("controls"));
