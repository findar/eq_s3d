// main.ts — wires the UI, API, scene, and controls together

import * as THREE from "three";
import { generateZone, fetchSidecar, type GenerateResult, type ZoneSidecar } from "./api";
import { ZoneScene } from "./scene";
import { FirstPersonControls } from "./controls";

// ---- DOM ----
const $ = (id: string) => document.getElementById(id)!;
const canvas = $("viewport") as HTMLCanvasElement;
const statusEl = $("status");
const genBtn = $("generate") as HTMLButtonElement;
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

// ---- Metrics panel ----
function updatePanel(result: GenerateResult, sidecar: ZoneSidecar) {
  const b = sidecar.bounds;
  const wx = (b.max[0] - b.min[0]).toFixed(0);
  const wy = (b.max[1] - b.min[1]).toFixed(0);
  const wz = (b.max[2] - b.min[2]).toFixed(0);

  // Plan readout
  const sourceLabel = result.source === "prompt"
    ? `prompt (${result.planner})`
    : "controls";
  $("m-source").textContent = sourceLabel;
  $("m-theme").textContent = result.theme;
  $("m-rooms").textContent = String(result.rooms);

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

  // Content / semantic layer: theme line, room-type counts, boss + a sample of
  // suggestions. Only shown when the zone was themed.
  const content = $("m-content");
  content.innerHTML = "";
  const theme = sidecar.theme;
  const themed = !!(theme && theme.dungeon_theme);
  if (themed && sidecar.rooms && sidecar.rooms.length) {
    const tbits: string[] = [theme!.dungeon_theme!];
    if (theme!.dungeon_race && theme!.dungeon_race !== "default")
      tbits.push(theme!.dungeon_race!);
    if (theme!.elemental_tint) tbits.push(theme!.elemental_tint!);
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
async function doGenerate() {
  const prompt = ($("prompt") as HTMLInputElement).value.trim();
  const theme = ($("theme") as HTMLSelectElement).value;
  // Rooms is a free number input; clamp to the server's accepted 1–30 range
  // and fall back to 5 if blank/unparseable so an out-of-range value never
  // trips the backend's validation (422).
  const roomsRaw = parseInt(($("rooms") as HTMLInputElement).value, 10);
  const rooms = Number.isFinite(roomsRaw)
    ? Math.min(30, Math.max(1, roomsRaw))
    : 5;
  const elevation = ($("elevation") as HTMLInputElement).checked;

  // Seed: blank or non-numeric → omit (server picks a fresh random seed, the
  // default "identical inputs still vary" behaviour). A number pins the seed so
  // the same inputs reproduce the exact zone. Negative/decimal input is
  // floored to a non-negative integer; anything unparseable falls back to
  // random rather than erroring.
  const seedRaw = seedInput.value.trim();
  let seed: number | undefined;
  if (seedRaw !== "") {
    const n = Number(seedRaw);
    if (Number.isFinite(n)) seed = Math.abs(Math.trunc(n));
  }

  genBtn.disabled = true;
  statusEl.textContent = "generating…";

  try {
    // If a prompt is given, it drives generation (theme/rooms); otherwise the
    // controls do. Either way the seed, when set, pins the randomness — the
    // backend applies `seed` in both paths.
    const params = prompt
      ? { prompt, ...(seed !== undefined ? { seed } : {}) }
      : { theme, rooms, elevation, ...(seed !== undefined ? { seed } : {}) };

    // Log the user's input so it's visible in the browser console.
    const seedNote = seed !== undefined ? ` seed=${seed}` : " seed=random";
    if (prompt) {
      console.log(`[input] prompt: "${prompt}"${seedNote}`);
    } else {
      console.log(`[input] controls: theme=${theme} rooms=${rooms} elevation=${elevation}${seedNote}`);
    }

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
      `[generate] seed=${result.seed} theme=${result.theme} rooms=${result.rooms} ` +
      `source=${result.source}` +
      (result.planner ? ` planner=${result.planner}` : ""),
    );

    statusEl.textContent = `seed ${result.seed} · ${result.polygons.toLocaleString()} polys`;
  } catch (err) {
    console.error(err);
    statusEl.textContent = "error — see console";
  } finally {
    genBtn.disabled = false;
  }
}

genBtn.addEventListener("click", doGenerate);

// Reset View button — return the camera to its starting position/orientation
$("reset-view").addEventListener("click", () => {
  controls.reset();
  console.log("[input] reset view");
});

// Enter in the prompt box triggers generation
($("prompt") as HTMLInputElement).addEventListener("keydown", (e) => {
  if ((e as KeyboardEvent).key === "Enter") doGenerate();
});

// Enter in the seed box triggers generation too.
seedInput.addEventListener("keydown", (e) => {
  if ((e as KeyboardEvent).key === "Enter") doGenerate();
});

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

// Generate one on load so the viewport isn't empty
doGenerate();
