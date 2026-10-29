// main.ts — wires the UI, API, scene, and controls together

import * as THREE from "three";
import {
  generateZone, fetchSidecar, fetchVersion, fetchZoneTypes,
  type GenerateParams, type GenerateResult, type ZoneSidecar,
} from "./api";
import { ZoneScene } from "./scene";
import { FirstPersonControls } from "./controls";

// The two generation modes, chosen explicitly by which button (or which
// field's Enter) fired — the server no longer infers it from the body shape.
type Mode = "prompt" | "controls";

// ---- DOM ----
const $ = (id: string) => document.getElementById(id)!;
const canvas = $("viewport") as HTMLCanvasElement;
const statusEl = $("status");
const genDescBtn = $("generate-description") as HTMLButtonElement;
const genCtrlBtn = $("generate-controls") as HTMLButtonElement;
const hintOverlay = $("hint-overlay");
const seedInput = $("seed") as HTMLInputElement;
const reproduceBtn = $("reproduce") as HTMLButtonElement;

// Latest generated map URL, shown by the Map modal.
let currentMapUrl: string | null = null;
// Seed of the last successful generation, for the "reproduce" affordance.
let lastSeed: number | null = null;

// ---- Scene + controls ----
const zoneScene = new ZoneScene(canvas);
const controls = new FirstPersonControls(zoneScene.camera, canvas);

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

  renderWarnings(result.warnings);

  const extra = $("m-plan-extra");
  extra.innerHTML = "";
  if (result.plan) {
    const p = result.plan;
    const rows: [string, string][] = [
      ["Size", p.size],
      ["Verticality", p.verticality],
    ];
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
  $("m-build").textContent = result.build_commit ?? "unknown";
  $("m-verts").textContent = result.vertices.toLocaleString();
  $("m-polys").textContent = result.polygons.toLocaleString();
  $("m-mats").textContent = String(result.materials);
  $("m-lights").textContent = String(sidecar.lights.length);
  $("m-regions").textContent = String(sidecar.regions.length);
  $("m-gates").textContent = String((sidecar.gates ?? []).length);
  $("m-wx").textContent = wx;
  $("m-wy").textContent = wy;
  $("m-wz").textContent = wz;

  // Pacing: role counts + max depth
  const pacing = $("m-pacing");
  pacing.innerHTML = "";
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
  } else {
    content.innerHTML = `<span style="color:#555;font-size:11px">no theme (plain dungeon)</span>`;
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

// Wilderness map edges: one selector per side, shown only for wilderness.
const EDGE_SIDES = ["N", "E", "S", "W"];

function readEdges(): Record<string, string> {
  const edges: Record<string, string> = {};
  for (const s of EDGE_SIDES) {
    edges[s] = ($(`edge-${s.toLowerCase()}`) as HTMLSelectElement).value;
  }
  return edges;
}

function syncEdgesVisibility(): void {
  const wild = ($("zone-type") as HTMLSelectElement).value === "wilderness";
  $("edges").hidden = !wild;
}

async function doGenerate(mode: Mode) {
  const seed = readSeed();
  const prompt = ($("prompt") as HTMLInputElement).value.trim();

  // In prompt mode a description is required; fall back to controls if empty so
  // the on-load / accidental-empty case still produces a zone.
  if (mode === "prompt" && prompt === "") {
    mode = "controls";
  }

  // Build the request body per the server's explicit-mode contract: prompt mode
  // sends {mode, prompt}, controls mode sends {mode, controls:{…}}; seed rides
  // on either when set.
  let params: GenerateParams;
  const seedNote = seed !== undefined ? ` seed=${seed}` : " seed=random";
  if (mode === "prompt") {
    params = { mode, prompt, ...(seed !== undefined ? { seed } : {}) };
    console.log(`[input] description: "${prompt}"${seedNote}`);
  } else {
    const zoneType = ($("zone-type") as HTMLSelectElement).value;
    // Rooms/locks are free number inputs; clamp to the server's accepted ranges
    // and fall back to a sane default if blank/unparseable so an out-of-range
    // value never trips the backend's validation.
    const roomsRaw = parseInt(($("rooms") as HTMLInputElement).value, 10);
    const rooms = Number.isFinite(roomsRaw)
      ? Math.min(30, Math.max(1, roomsRaw))
      : 5;
    const locksRaw = parseInt(($("locks") as HTMLInputElement).value, 10);
    const locks = Number.isFinite(locksRaw)
      ? Math.min(5, Math.max(0, locksRaw))
      : 0;
    const size = ($("size") as HTMLSelectElement).value;
    const verticality = ($("verticality") as HTMLSelectElement).value;
    const edges = zoneType === "wilderness" ? readEdges() : undefined;
    params = {
      mode,
      controls: {
        zone_type: zoneType, room_count: rooms, size, verticality, locks,
        ...(edges ? { edges } : {}),
      },
      ...(seed !== undefined ? { seed } : {}),
    };
    console.log(
      `[input] controls: zone_type=${zoneType} rooms=${rooms} size=${size} ` +
      `verticality=${verticality} locks=${locks}` +
      (edges ? ` edges=${JSON.stringify(edges)}` : "") + seedNote,
    );
  }

  genDescBtn.disabled = true;
  genCtrlBtn.disabled = true;
  statusEl.textContent = "generating…";

  // Cheap re-check so a stale-server warning shows exactly when it matters.
  await refreshVersion();

  try {
    const result = await generateZone(params);
    currentMapUrl = result.map_url;
    lastSeed = result.seed;
    reproduceBtn.disabled = false;
    statusEl.textContent = "loading…";

    const box = await zoneScene.loadZone(result.glb_url);
    const sidecar = await fetchSidecar(result.zone_url);
    zoneScene.applyOverlays(sidecar);
    updatePanel(result, sidecar);

    // Place the camera near the zone's lowest/entry corner at a sensible
    // eye height, looking toward the centre. World is Z-up and the mesh is
    // centred on the origin, so the centre is roughly (0,0,0).
    const size = box.getSize(new THREE.Vector3());
    const groundZ = -size.z / 2;        // bottom of the centred mesh
    const eye = Math.min(60, size.z * 0.3);
    // Stand back along -Y, near the floor, looking toward +Y (yaw = +90°).
    const start = new THREE.Vector3(0, -size.y * 0.45, groundZ + eye);
    const startYaw = Math.PI / 2;       // face +Y (into the zone)
    controls.setStart(start, startYaw);

    console.info(
      `[generate] seed=${result.seed} zone_type=${result.zone_type} rooms=${result.rooms} ` +
      `mode=${result.mode}` +
      (result.planner ? ` planner=${result.planner}` : "") +
      ` build=${result.build_commit ?? "unknown"}`,
    );

    statusEl.textContent = `seed ${result.seed} · ${result.polygons.toLocaleString()} polys`;
  } catch (err) {
    console.error(err);
    statusEl.textContent = "error — see console";
  } finally {
    genDescBtn.disabled = false;
    genCtrlBtn.disabled = false;
  }
}

// Populate the zone-type dropdown from the server's single source of truth.
// Each entry is {name, enabled, reason}: a DISABLED type is rendered as a
// disabled <option> whose text and title carry the reason (so it's visible but
// unselectable — not hidden), and the first ENABLED type is preselected (or the
// current selection if it survives and is still enabled). The static <option>s
// in index.html are the offline fallback if the fetch fails.
function titleCase(z: string): string {
  return z.charAt(0).toUpperCase() + z.slice(1);
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
        opt.textContent = titleCase(zt.name);
      } else {
        opt.disabled = true;
        const reason = zt.reason ?? "not available yet";
        opt.textContent = `${titleCase(zt.name)} — ${reason}`;
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
  syncEdgesVisibility();
}

($("zone-type") as HTMLSelectElement).addEventListener("change", syncEdgesVisibility);

// The two Generate actions choose the mode explicitly.
genDescBtn.addEventListener("click", () => doGenerate("prompt"));
genCtrlBtn.addEventListener("click", () => doGenerate("controls"));

// Reset View button — return the camera to its starting position/orientation
$("reset-view").addEventListener("click", () => {
  controls.reset();
  console.log("[input] reset view");
});

// Enter routing is per field: Enter in the description → prompt mode; Enter in
// any Controls-panel field (or the shared seed box) → controls mode.
($("prompt") as HTMLInputElement).addEventListener("keydown", (e) => {
  if ((e as KeyboardEvent).key === "Enter") doGenerate("prompt");
});

for (const id of ["zone-type", "rooms", "size", "verticality", "locks", "seed",
                  "edge-n", "edge-e", "edge-s", "edge-w"]) {
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
    const res = await fetch(currentMapUrl);
    if (!res.ok) throw new Error(`map fetch failed (${res.status})`);
    mapBody.innerHTML = await res.text();   // inline SVG so it scales crisply
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
  controls.update(dt);
  zoneScene.render();
}
animate();

// Populate zone types, then generate one on load (controls mode) so the
// viewport isn't empty.
refreshZoneTypes().finally(() => doGenerate("controls"));
