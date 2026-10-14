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

  $("m-seed").textContent = String(result.seed);
  $("m-verts").textContent = result.vertices.toLocaleString();
  $("m-polys").textContent = result.polygons.toLocaleString();
  $("m-mats").textContent = String(result.materials);
  $("m-lights").textContent = String(sidecar.lights.length);
  $("m-regions").textContent = String(sidecar.regions.length);
  $("m-wx").textContent = wx;
  $("m-wy").textContent = wy;
  $("m-wz").textContent = wz;
}

// ---- Generate ----
async function doGenerate() {
  const theme = ($("theme") as HTMLSelectElement).value;
  const rooms = parseInt(($("rooms") as HTMLSelectElement).value, 10);
  const elevation = ($("elevation") as HTMLInputElement).checked;

  genBtn.disabled = true;
  statusEl.textContent = "generating…";

  try {
    const result = await generateZone({ theme, rooms, elevation });
    statusEl.textContent = "loading…";

    const box = await zoneScene.loadZone(result.glb_url);
    const sidecar = await fetchSidecar(result.zone_url);
    zoneScene.applyOverlays(sidecar);
    updatePanel(result, sidecar);

    // Place camera at the first light (roughly room 0) looking into the zone,
    // or fall back to the box edge.
    const size = box.getSize(new THREE.Vector3());
    const start = new THREE.Vector3(0, -size.y * 0.4, size.z * 0.25 + 20);
    if (sidecar.lights.length > 0) {
      const offset: THREE.Vector3 = (zoneScene as any).zoneGroup?.userData?.offset;
      const l = sidecar.lights[0];
      start.set(l.pos[0], l.pos[1], l.pos[2] - 20);
      if (offset) start.add(offset);
    }
    controls.setStart(start, 0);

    statusEl.textContent = `seed ${result.seed} · ${result.polygons.toLocaleString()} polys`;
  } catch (err) {
    console.error(err);
    statusEl.textContent = "error — see console";
  } finally {
    genBtn.disabled = false;
  }
}

genBtn.addEventListener("click", doGenerate);

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
