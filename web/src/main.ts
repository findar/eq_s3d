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
}

// ---- Generate ----
async function doGenerate() {
  const prompt = ($("prompt") as HTMLInputElement).value.trim();
  const theme = ($("theme") as HTMLSelectElement).value;
  const rooms = parseInt(($("rooms") as HTMLSelectElement).value, 10);
  const elevation = ($("elevation") as HTMLInputElement).checked;

  genBtn.disabled = true;
  statusEl.textContent = "generating…";

  try {
    // If a prompt is given, it drives generation; otherwise the controls do.
    const params = prompt
      ? { prompt }
      : { theme, rooms, elevation };

    // Log the user's input so it's visible in the browser console.
    if (prompt) {
      console.log(`[input] prompt: "${prompt}"`);
    } else {
      console.log(`[input] controls: theme=${theme} rooms=${rooms} elevation=${elevation}`);
    }

    const result = await generateZone(params);
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
