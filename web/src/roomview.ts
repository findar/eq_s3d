// roomview.ts — the Room view (decor-rules Req 5): one room of the shown build,
// re-decorated by POST /api/room_decor and drawn alone.
//
// While open it covers the zone's viewport and side panel with its own Three.js
// scene (Z-up, an orbit camera framed on the room's box), the room GLB (floor,
// walls, Features, a red marker on each POI, each Prop its own node
// `prop_<n>`, n its index in the report's `props`), POI markers and, on
// request, labels. Beside it a list groups the Props by recipe line, lists each
// POI with its Dressing and the drops with their reasons; hovering an entry
// lights its Props and hovering a Prop lights its entries. The toolbar
// re-decorates: ⟳ reroll (a fresh decor seed), Decor (the level), Decor rules
// (a layer on top of the theme's) and re-read rules (same seed, rules read
// fresh). Use in zone keeps the room's decor seed in the zone: the next version
// is built with it (main.ts, /api/rebuild room_decor) and the view reopens on
// that room of the new version. Close drops the scene and returns to the zone
// untouched: its camera doesn't move while this is open (movement keys stop
// here) and main.ts skips its render loop.
//
// Opened from the side panel's room list (setBuild fills it) and from a click
// on a room in the map dialog (wireMap: the click goes through the SVG's world
// frame, data-frame-a/b/s, and is hit-tested against each room's outline).

import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import {
  fetchRoomDecor,
  type RoomDecorParams, type RoomDecorReport, type ZoneSidecar,
} from "./api";

/** The build a room view opens rooms of. */
export interface RoomBuild {
  zone: string;                // the build id
  version: number | string;
  sidecar: ZoneSidecar;
}

export interface RoomViewOptions {
  /** The Controls' Decor and Decor rules lists, whose options the toolbar copies. */
  decorSelect: HTMLSelectElement;
  layerSelect: HTMLSelectElement;
  /** Called before the view opens (close the map dialog, release the mouse). */
  beforeOpen?: () => void;
  /** Use in zone: build the next version with `room` keeping `decorSeed`, then
   *  show it (setBuild with the room to reopen). Rejects with the error's words. */
  useInZone?: (room: string, decorSeed: number) => Promise<void>;
}

/** Walls are cut away this far above the room's floor (head height and a wall light's reach). */
const CUT_HEIGHT = 14;

// The keys the zone's camera reads (controls.ts), plus M (the map): stopped
// while the room view is open so they never reach the zone.
const BLOCKED_KEYS = new Set([
  "KeyW", "KeyA", "KeyS", "KeyD", "KeyQ", "KeyE", "KeyR", "KeyM", "Space",
  "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "ShiftLeft", "ShiftRight",
]);

// The Decor rules option that sends no decor_layers: what the build ran with.
const AS_BUILT = "@build";

const HOT = new THREE.Color(0xffaa22);
const POI_COLOR = 0xff4040;

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K, cls = "", text = "",
): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text) e.textContent = text;
  return e;
}

function typingTarget(t: EventTarget | null): boolean {
  const e = t as HTMLElement | null;
  return !!e && (e.tagName === "INPUT" || e.tagName === "SELECT" ||
    e.tagName === "TEXTAREA" || e.isContentEditable);
}

/** A camera-facing text sprite `height` world units tall. */
function labelSprite(text: string, height: number, color = "#ffffff"): THREE.Sprite {
  const fontSize = 40, pad = 8;
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d")!;
  const font = `bold ${fontSize}px monospace`;
  ctx.font = font;
  canvas.width = Math.ceil(ctx.measureText(text).width) + pad * 2;
  canvas.height = fontSize + pad * 2;
  ctx.font = font;
  ctx.textBaseline = "middle";
  ctx.textAlign = "center";
  ctx.fillStyle = "rgba(10, 10, 18, 0.65)";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = color;
  ctx.fillText(text, canvas.width / 2, canvas.height / 2);
  const tex = new THREE.CanvasTexture(canvas);
  tex.minFilter = THREE.LinearFilter;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true }));
  sprite.scale.set(height * canvas.width / canvas.height, height, 1);
  sprite.renderOrder = 10;
  return sprite;
}

/** Dispose every geometry, material and texture under `root`. */
function disposeTree(root: THREE.Object3D): void {
  root.traverse((o) => {
    const m = o as THREE.Mesh;
    if (m.geometry) m.geometry.dispose();
    const mats = m.material ? (Array.isArray(m.material) ? m.material : [m.material]) : [];
    for (const mat of mats) {
      for (const v of Object.values(mat)) {
        if (v instanceof THREE.Texture) v.dispose();
      }
      mat.dispose();
    }
  });
}

// ---- The map dialog: which room a click is on ----

interface Frame { a: number; b: number; s: number }

function svgFrame(svg: SVGSVGElement): Frame | null {
  const [a, b, s] = ["a", "b", "s"].map((k) => {
    const v = svg.getAttribute(`data-frame-${k}`);
    return v === null || v.trim() === "" ? NaN : Number(v);
  });
  return Number.isFinite(a) && Number.isFinite(b) && Number.isFinite(s) && s > 0 ? { a, b, s } : null;
}

function inRing(x: number, y: number, ring: number[][]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/** The room under world (x, y): inside its outline (a graph layout's rings),
 *  else inside its outline's box, else the nearest centre within 30 u. */
export function roomAt(sidecar: ZoneSidecar, x: number, y: number): string | null {
  const outlines = sidecar.layout?.rooms ?? {};
  const rooms = sidecar.rooms ?? [];
  for (const r of rooms) {
    const rings = outlines[r.id]?.outline ?? [];
    if (rings.some((ring) => ring.length >= 3 && inRing(x, y, ring))) return r.id;
  }
  for (const r of rooms) {
    const pts = (outlines[r.id]?.outline ?? []).flat();
    if (!pts.length) continue;
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    if (x >= Math.min(...xs) && x <= Math.max(...xs) && y >= Math.min(...ys) && y <= Math.max(...ys)) return r.id;
  }
  let best: string | null = null, bestD = 30 * 30;
  for (const r of rooms) {
    const d = (r.center[0] - x) ** 2 + (r.center[1] - y) ** 2;
    if (d < bestD) { bestD = d; best = r.id; }
  }
  return best;
}

/** World (x, y) under a pointer event on the inlined map SVG, or null. */
function worldAt(svg: SVGSVGElement, ev: MouseEvent): [number, number] | null {
  const frame = svgFrame(svg);
  const ctm = svg.getScreenCTM();
  if (!frame || !ctm) return null;
  const p = new DOMPoint(ev.clientX, ev.clientY).matrixTransform(ctm.inverse());
  return [(p.x - frame.a) / frame.s, (frame.b - p.y) / frame.s];
}

// ---- The view ----

export class RoomView {
  private opts: RoomViewOptions;
  private build: RoomBuild | null = null;
  private roomId = "";
  private report: RoomDecorReport | null = null;
  private seq = 0;                       // the latest request; older answers are dropped
  private busy = false;

  // DOM
  private root = document.getElementById("room-view")!;
  private stage!: HTMLElement;
  private list!: HTMLElement;
  private loading!: HTMLElement;
  private title!: HTMLElement;
  private seedEl!: HTMLElement;
  private levelSel!: HTMLSelectElement;
  private layerSel!: HTMLSelectElement;
  private labelsBox!: HTMLInputElement;
  private cutBox!: HTMLInputElement;
  private useBtn!: HTMLButtonElement;
  /** Walls are cut away above this plane (floor + CUT_HEIGHT) while `cutBox` is ticked. */
  private cut = new THREE.Plane(new THREE.Vector3(0, 0, -1), 0);
  private buttons: HTMLButtonElement[] = [];

  // Three.js, alive only while open
  private renderer: THREE.WebGLRenderer | null = null;
  private scene: THREE.Scene | null = null;
  private camera: THREE.PerspectiveCamera | null = null;
  private orbit: OrbitControls | null = null;
  private content = new THREE.Group();   // the GLB, POI markers, labels
  private labels = new THREE.Group();
  private helpers = new THREE.Group();   // highlight boxes
  private props: THREE.Object3D[] = [];  // by index
  private raf = 0;
  private resizeObs: ResizeObserver | null = null;
  private raycaster = new THREE.Raycaster();
  private hoverProp = -1;
  private loader = new GLTFLoader();

  constructor(opts: RoomViewOptions) {
    this.opts = opts;
    this.buildDom();
    // Capture phase on window: before controls.ts's and main.ts's document
    // listeners. Only propagation stops; typing in a field still types.
    window.addEventListener("keydown", (e) => {
      if (!this.isOpen) return;
      if (e.key === "Escape" && !typingTarget(e.target)) {
        e.stopPropagation();
        this.close();
        return;
      }
      if (BLOCKED_KEYS.has(e.code)) e.stopPropagation();
    }, true);
  }

  get isOpen(): boolean { return !this.root.hidden; }

  // ---- DOM ----

  private buildDom(): void {
    const bar = el("div", "rv-toolbar");
    this.title = el("span", "rv-title", "Room");
    this.seedEl = el("span", "rv-seed");
    const reroll = this.button("⟳ reroll", "Re-decorate this room with a fresh decor seed",
      () => this.request({ decor_seed: Math.floor(Math.random() * 2147483648) }));
    this.levelSel = el("select");
    this.levelSel.title = "How many Props stand in the room";
    this.levelSel.addEventListener("change", () => this.request({}));
    this.layerSel = el("select");
    this.layerSel.title = "Extra decor rules on top of the theme's";
    this.layerSel.addEventListener("change", () => this.request({}));
    const reread = this.button("re-read rules", "Same seed, the rule files read again",
      () => this.request({}));
    this.useBtn = this.button("Use in zone", "", () => this.useInZone());
    this.useBtn.classList.add("rv-use");
    const labelWrap = el("label", "rv-check");
    this.labelsBox = el("input");
    this.labelsBox.type = "checkbox";
    this.labelsBox.addEventListener("change", () => { this.labels.visible = this.labelsBox.checked; });
    labelWrap.append(this.labelsBox, " Labels");
    const cutWrap = el("label", "rv-check");
    cutWrap.title = "Cut the walls away above head height, so the room can be seen into";
    this.cutBox = el("input");
    this.cutBox.type = "checkbox";
    this.cutBox.checked = true;
    this.cutBox.addEventListener("change", () => this.applyCut());
    cutWrap.append(this.cutBox, " Cutaway");
    const close = el("button", "secondary", "Close");
    close.title = "Back to the zone (Esc)";
    close.addEventListener("click", () => this.close());
    const lvl = el("label", "rv-field", "Decor ");
    lvl.appendChild(this.levelSel);
    const lay = el("label", "rv-field", "Decor rules ");
    lay.appendChild(this.layerSel);
    bar.append(this.title, this.seedEl, reroll, lvl, lay, reread, this.useBtn, labelWrap, cutWrap, el("span", "rv-spacer"), close);

    const body = el("div", "rv-body");
    this.stage = el("div", "rv-stage");
    this.loading = el("div", "rv-loading");
    this.loading.hidden = true;
    this.stage.appendChild(this.loading);
    this.list = el("aside", "rv-list");
    body.append(this.stage, this.list);
    this.root.replaceChildren(bar, body);

    this.stage.addEventListener("pointermove", (e) => this.onPointerMove(e));
    this.stage.addEventListener("pointerleave", () => this.hover3d(-1));
  }

  private button(text: string, title: string, onClick: () => void): HTMLButtonElement {
    const b = el("button", "secondary", text);
    b.title = title;
    b.addEventListener("click", onClick);
    this.buttons.push(b);
    return b;
  }

  /** Copy a Controls list's options into a toolbar list. */
  private copyOptions(from: HTMLSelectElement, to: HTMLSelectElement): void {
    to.replaceChildren(...Array.from(from.options).map((o) => {
      const c = el("option", "", o.textContent ?? o.value);
      c.value = o.value;
      c.title = o.title;
      return c;
    }));
  }

  // ---- The build and its room list ----

  /** The shown build (null: none; closes the view). Fills the side panel's
   *  room list (#m-room-list, in #s-rooms) when the build has Decor.
   *  `reopenRoom`: with the view open, it stays open and shows that room of
   *  the new build (Use in zone made it). */
  setBuild(build: RoomBuild | null, reopenRoom?: string): void {
    const reopen = !!(build && reopenRoom && this.isOpen);
    if (!reopen) this.close();
    this.build = build;
    if (reopen) this.open(reopenRoom!);
    const section = document.getElementById("s-rooms");
    const listEl = document.getElementById("m-room-list");
    if (!section || !listEl) return;
    listEl.replaceChildren();
    const rooms = build?.sidecar.rooms ?? [];
    section.hidden = !(build?.sidecar.decor && rooms.length);
    if (section.hidden) return;
    for (const r of rooms) {
      const b = el("button", "rv-room", r.id);
      const n = r.props?.length ?? 0;
      b.title = `Open ${r.id} in the room view` + (r.semantic_type ? ` (${r.semantic_type})` : "") +
        ` · ${n} Props`;
      const count = el("span", "rv-room-n", String(n));
      b.appendChild(count);
      b.addEventListener("click", () => this.open(r.id));
      listEl.appendChild(b);
    }
  }

  /** Let a click on a room in the map dialog's SVG open it. */
  wireMap(svg: SVGSVGElement): void {
    if (!this.build?.sidecar.decor || !svgFrame(svg)) return;
    const sidecar = this.build.sidecar;
    svg.addEventListener("pointermove", (e) => {
      const w = worldAt(svg, e);
      const id = w ? roomAt(sidecar, w[0], w[1]) : null;
      svg.style.cursor = id ? "pointer" : "";
      svg.setAttribute("aria-label", id ? `Open ${id} in the room view` : "Top-down layout");
    });
    svg.addEventListener("click", (e) => {
      const w = worldAt(svg, e);
      const id = w ? roomAt(sidecar, w[0], w[1]) : null;
      if (id) this.open(id);
    });
  }

  // ---- Open / close ----

  open(roomId: string): void {
    if (!this.build) return;
    this.opts.beforeOpen?.();
    if (document.pointerLockElement) document.exitPointerLock();
    const reopen = this.isOpen;
    this.roomId = roomId;
    this.report = null;
    this.title.textContent = roomId;
    this.seedEl.textContent = "";
    this.copyOptions(this.opts.decorSelect, this.levelSel);
    this.copyOptions(this.opts.layerSelect, this.layerSel);
    const asBuilt = el("option", "", "As built");
    asBuilt.value = AS_BUILT;
    asBuilt.title = "The decor rules the build used";
    this.layerSel.prepend(asBuilt);
    this.layerSel.value = AS_BUILT;
    this.list.replaceChildren();
    this.root.hidden = false;
    if (!reopen) this.start();
    this.request({}, true);
  }

  close(): void {
    if (!this.isOpen) return;
    this.seq++;                            // drop an answer still in flight
    this.root.hidden = true;
    cancelAnimationFrame(this.raf);
    this.resizeObs?.disconnect();
    this.resizeObs = null;
    this.clearContent();
    this.orbit?.dispose();
    this.orbit = null;
    if (this.scene) disposeTree(this.scene);
    this.scene = null;
    this.camera = null;
    if (this.renderer) {
      this.renderer.dispose();
      this.renderer.forceContextLoss();
      this.renderer.domElement.remove();
    }
    this.renderer = null;
    this.report = null;
    this.setBusy(false);
  }

  private start(): void {
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.localClippingEnabled = true;
    renderer.setPixelRatio(window.devicePixelRatio);
    this.stage.prepend(renderer.domElement);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a12);
    scene.add(new THREE.AmbientLight(0x4a5566, 1.6));
    const sun = new THREE.DirectionalLight(0xfff0e0, 1.6);
    sun.position.set(300, -400, 500);
    scene.add(sun);
    const fill = new THREE.DirectionalLight(0x8090b0, 0.6);
    fill.position.set(-300, 200, 200);
    scene.add(fill);
    this.content = new THREE.Group();
    this.labels = new THREE.Group();
    this.labels.visible = this.labelsBox.checked;
    this.helpers = new THREE.Group();
    scene.add(this.content, this.labels, this.helpers);
    const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 5000);
    camera.up.set(0, 0, 1);              // Z-up, before the orbit reads it
    camera.position.set(0, -100, 80);
    const orbit = new OrbitControls(camera, renderer.domElement);
    orbit.enableDamping = true;
    this.renderer = renderer;
    this.scene = scene;
    this.camera = camera;
    this.orbit = orbit;
    this.resizeObs = new ResizeObserver(() => this.resize());
    this.resizeObs.observe(this.stage);
    this.resize();
    const loop = () => {
      this.raf = requestAnimationFrame(loop);
      this.orbit?.update();
      if (this.renderer && this.scene && this.camera) this.renderer.render(this.scene, this.camera);
    };
    loop();
  }

  private resize(): void {
    if (!this.renderer || !this.camera) return;
    const w = Math.max(1, this.stage.clientWidth), h = Math.max(1, this.stage.clientHeight);
    this.renderer.setSize(w, h);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  /** Clip (or stop clipping) the room's own mesh at the cut plane. */
  private applyCut(): void {
    const planes = this.cutBox.checked ? [this.cut] : [];
    this.content.traverse((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh || !m.userData.roomShell) return;
      for (const mat of Array.isArray(m.material) ? m.material : [m.material]) {
        mat.clippingPlanes = planes;
        mat.needsUpdate = true;
      }
    });
  }

  /** Point the orbit camera at the room's box from the south, above. */
  private frame(box: number[]): void {
    if (!this.camera || !this.orbit || box.length < 6) return;
    const c = new THREE.Vector3((box[0] + box[3]) / 2, (box[1] + box[4]) / 2, box[2]);
    const r = Math.max(box[3] - box[0], box[4] - box[1], 20) / 2;
    const dist = r / Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2)) * 1.1;
    this.orbit.target.copy(c);
    this.camera.position.set(c.x, c.y - dist * 0.75, c.z + dist * 0.75);
    this.camera.far = dist * 20;
    this.camera.updateProjectionMatrix();
    this.orbit.update();
  }

  // ---- Requests ----

  private setBusy(on: boolean, text = ""): void {
    this.busy = on;
    this.loading.hidden = !on && !text;
    this.loading.textContent = text;
    this.loading.classList.toggle("error", !on && !!text);
    for (const b of this.buttons) b.disabled = on;
    this.levelSel.disabled = on;
    this.layerSel.disabled = on;
    this.syncUse();
  }

  /** The decor seed the open build has for a room: its own, else the zone's. */
  private builtSeed(roomId: string): number | null {
    const s = this.build?.sidecar;
    if (!s) return null;
    return s.rooms?.find((r) => r.id === roomId)?.decor_seed ??
      s.seeds?.room_decor_seeds?.[roomId] ?? s.seeds?.decor_seed ?? s.decor?.seed ?? null;
  }

  /** Use in zone is enabled once the room shows a decor seed the build doesn't
   *  have for it, with the build's Decor level and rules (only the seed is kept). */
  private syncUse(): void {
    const r = this.report;
    const built = this.builtSeed(this.roomId);
    let why = "";
    if (!this.opts.useInZone) why = "Not available";
    else if (!r) why = "Decorating…";
    else if (r.seed === built) why = `The zone already has seed ${r.seed} for this room: reroll first`;
    else if (this.layerSel.value !== AS_BUILT || r.control !== this.build?.sidecar.decor?.control) {
      why = "Only the decor seed goes into the zone: set Decor to the build's and Decor rules to As built";
    } else if (r.bare) why = "The zone's draw leaves this room bare: no Props to keep";
    this.useBtn.disabled = this.busy || !!why;
    this.useBtn.title = why || `Build the next version of the zone with seed ${r!.seed} in ${this.roomId}` +
      (built !== null ? ` (it has ${built})` : "");
  }

  /** Keep the shown seed in the zone (main.ts rebuilds and reopens the room). */
  private async useInZone(): Promise<void> {
    const r = this.report;
    if (!this.build || !r || this.busy || !this.opts.useInZone) return;
    const seq = ++this.seq;
    this.setBusy(true, `Keeping seed ${r.seed} in the zone… (a rebuild takes a few seconds)`);
    try {
      await this.opts.useInZone(this.roomId, r.seed);
      // The new version reopened the room (its request took over), unless it didn't.
      if (seq === this.seq) this.setBusy(false);
    } catch (err) {
      if (seq !== this.seq) return;
      console.error("[room view]", err);
      this.setBusy(false, String((err as Error).message ?? err));
    }
  }

  /** Re-decorate the room. `over` names what changes (a fresh seed); the
   *  level and layers come from the toolbar once a report is in. `first`:
   *  the build's own seed, level and layers, and frame the camera. */
  private async request(over: { decor_seed?: number }, first = false): Promise<void> {
    if (!this.build || (this.busy && !first)) return;
    const params: RoomDecorParams = {
      zone: this.build.zone, version: this.build.version, room: this.roomId,
    };
    if (!first && this.report) {
      params.decor_seed = over.decor_seed ?? this.report.seed;
      if (this.levelSel.value) params.control = this.levelSel.value;
      const layer = this.layerSel.value;
      if (layer !== AS_BUILT) params.decor_layers = layer ? [layer] : [];
    }
    const seq = ++this.seq;
    const slow = setTimeout(() => {
      if (seq === this.seq) {
        this.loading.textContent = "Decorating… (the first room after a server start reads the install, ~15 s)";
      }
    }, 1500);
    this.setBusy(true, "Decorating…");
    try {
      const report = await fetchRoomDecor(params);
      if (seq !== this.seq) return;
      const gltf = await this.loader.loadAsync(report.glb_url);
      if (seq !== this.seq || !this.scene) { disposeTree(gltf.scene); return; }
      this.show(report, gltf.scene, first);
      this.setBusy(false);
    } catch (err) {
      if (seq !== this.seq) return;
      console.error("[room view]", err);
      this.setBusy(false, String((err as Error).message ?? err));
    } finally {
      clearTimeout(slow);
    }
  }

  // ---- Showing a report ----

  private clearContent(): void {
    for (const g of [this.content, this.labels, this.helpers]) {
      for (const c of [...g.children]) { g.remove(c); disposeTree(c); }
    }
    this.props = [];
    this.hoverProp = -1;
  }

  private show(report: RoomDecorReport, model: THREE.Object3D, first: boolean): void {
    this.clearContent();
    this.report = report;
    // Each Prop its own materials, so lighting one leaves the others.
    model.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh && m.material) {
        m.material = Array.isArray(m.material) ? m.material.map((x) => x.clone()) : m.material.clone();
      }
    });
    this.content.add(model);
    this.props = report.props.map((_p, n) => model.getObjectByName(`prop_${n}`) ?? new THREE.Object3D());

    // POI markers: a floating diamond over each POI (the GLB's red post is under it).
    for (const poi of report.pois) {
      const mark = new THREE.Mesh(new THREE.OctahedronGeometry(1.6),
        new THREE.MeshBasicMaterial({ color: POI_COLOR }));
      mark.position.set(poi.x, poi.y, poi.z + 8);
      mark.userData.poi = poi.index;
      this.content.add(mark);
      const label = labelSprite(`POI ${poi.index} ${poi.purpose}${poi.name ? ` · ${poi.name}` : ""}`, 2.2, "#ff9090");
      label.position.set(poi.x, poi.y, poi.z + 11);
      this.labels.add(label);
    }
    report.props.forEach((p, n) => {
      const label = labelSprite(`${n} ${p.kind}`, 1.4);
      const top = p.h !== undefined && p.h > 0 ? p.h * (p.scale || 1) : 3;
      label.position.set(p.x, p.y, p.z + top + 1.2);
      this.labels.add(label);
    });

    // The room's own mesh (not a Prop) is cut away above head height: the walls
    // between the camera and the room would otherwise hide what's in it.
    this.cut.constant = (report.room.box[2] ?? 0) + CUT_HEIGHT;
    model.traverse((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh || !m.material) return;
      let inProp = false;
      for (let a: THREE.Object3D | null = o; a; a = a.parent) if (/^prop_\d+$/.test(a.name)) inProp = true;
      if (!inProp) m.userData.roomShell = true;
    });
    this.applyCut();
    if (first) this.frame(report.room.box);
    if (![...this.levelSel.options].some((o) => o.value === report.control)) {
      const o = el("option", "", report.control);
      o.value = report.control;
      this.levelSel.appendChild(o);
    }
    this.levelSel.value = report.control;
    const r = report.room;
    this.title.textContent = `${r.id}` + (r.room_type ? ` · ${r.room_type}` : r.kind ? ` · ${r.kind}` : "");
    const built = this.builtSeed(r.id);
    this.seedEl.textContent = `seed ${report.seed}` +
      (built !== null && built !== report.seed ? ` (zone has ${built})` : "");
    this.fillList(report);
    this.syncUse();
  }

  private fillList(report: RoomDecorReport): void {
    const list = this.list;
    list.replaceChildren();
    const r = report.room;
    const head = el("div", "rv-head");
    const rows: [string, string][] = [
      ["Room", `${r.id} (${r.source})`],
      ...(r.room_type ? [["Type", r.room_type] as [string, string]] : []),
      ...(r.kind ? [["Kind", r.kind] as [string, string]] : []),
      ...(r.theme || r.race ? [["Theme", [r.theme, r.race].filter(Boolean).join(" · ")] as [string, string]] : []),
      ["Decor", `${report.control} · seed ${report.seed}`],
      ["Rules", report.layers.length ? report.layers.join(", ") : "base"],
      ...(report.sets.length ? [["Sets", report.sets.join(", ")] as [string, string]] : []),
      ["Props", String(report.props.length) + (report.bare ? " (bare)" : "")],
      ["Took", `${report.took_ms} ms`],
    ];
    for (const [k, v] of rows) {
      const row = el("div", "row");
      row.append(el("span", "", k), el("span", "", v));
      head.appendChild(row);
    }
    list.appendChild(head);
    for (const n of [...report.notes, ...report.check.map((c) => `check: ${c}`)]) {
      list.appendChild(el("div", "rv-note", n));
    }

    // Props by recipe line, in the order the lines first placed.
    list.appendChild(el("h4", "", "Props by recipe line"));
    const byLine = new Map<string, number[]>();
    report.props.forEach((p, n) => {
      const key = p.line || p.step || "?";
      if (!byLine.has(key)) byLine.set(key, []);
      byLine.get(key)!.push(n);
    });
    if (!byLine.size) list.appendChild(el("div", "rv-empty", "No Props."));
    for (const [line, idx] of byLine) {
      const kinds = new Map<string, number>();
      for (const n of idx) kinds.set(report.props[n].kind, (kinds.get(report.props[n].kind) ?? 0) + 1);
      const first = report.props[idx[0]];
      const entry = this.entry(idx);
      entry.append(el("div", "rv-line", `${line}: ${idx.length}`),
        el("div", "rv-sub", [...kinds].map(([k, c]) => (c > 1 ? `${k} ×${c}` : k)).join(", ") +
          ` · ${first.step}` + (first.at ? ` @ ${first.at}` : "")));
      entry.title = idx.map((n) => `${n}: ${report.props[n].key} (${report.props[n].category}, ${report.props[n].mount})`).join("\n");
      list.appendChild(entry);
    }

    list.appendChild(el("h4", "", "POIs"));
    if (!report.pois.length) list.appendChild(el("div", "rv-empty", "No POIs."));
    for (const poi of report.pois) {
      const entry = this.entry(poi.props);
      entry.append(el("div", "rv-line", `POI ${poi.index}: ${poi.purpose}` + (poi.name ? ` · ${poi.name}` : "")),
        el("div", "rv-sub", poi.dressing.length ? `Dressing: ${poi.dressing.join(", ")}` : "No Dressing"));
      for (const d of poi.dropped) entry.appendChild(el("div", "rv-sub rv-drop", `dropped: ${d}`));
      list.appendChild(entry);
    }

    list.appendChild(el("h4", "", "Drops"));
    if (!report.drops.length) list.appendChild(el("div", "rv-empty", "Nothing dropped."));
    for (const d of report.drops) {
      const entry = el("div", "rv-entry");
      entry.append(el("div", "rv-line", `${d.line || d.step}: ${d.what}`),
        el("div", "rv-sub rv-drop", d.reason + (d.poi !== null && d.poi !== undefined ? ` (POI ${d.poi})` : "")));
      list.appendChild(entry);
    }
  }

  /** A list entry that lights Props `idx` while hovered. */
  private entry(idx: number[]): HTMLElement {
    const e = el("div", "rv-entry");
    e.dataset.props = idx.join(",");
    e.addEventListener("mouseenter", () => this.highlight(idx));
    e.addEventListener("mouseleave", () => this.highlight([]));
    return e;
  }

  // ---- Highlighting ----

  private highlight(idx: number[]): void {
    for (const c of [...this.helpers.children]) { this.helpers.remove(c); disposeTree(c); }
    const on = new Set(idx);
    this.props.forEach((obj, n) => {
      obj.traverse((o) => {
        const m = o as THREE.Mesh;
        if (!m.isMesh) return;
        for (const mat of Array.isArray(m.material) ? m.material : [m.material]) {
          const e = (mat as THREE.MeshStandardMaterial).emissive;
          if (e) e.copy(on.has(n) ? HOT : new THREE.Color(0, 0, 0));
        }
      });
      if (on.has(n)) {
        const box = new THREE.Box3().setFromObject(obj);
        if (!box.isEmpty()) this.helpers.add(new THREE.Box3Helper(box, HOT));
      }
    });
    // The entries holding any lit Prop light with it.
    for (const e of this.list.querySelectorAll<HTMLElement>(".rv-entry[data-props]")) {
      const mine = (e.dataset.props ?? "").split(",").filter(Boolean).map(Number);
      e.classList.toggle("hot", mine.some((n) => on.has(n)));
    }
  }

  private onPointerMove(ev: PointerEvent): void {
    if (!this.renderer || !this.camera || ev.buttons) return;
    const rect = this.renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(((ev.clientX - rect.left) / rect.width) * 2 - 1,
      -((ev.clientY - rect.top) / rect.height) * 2 + 1);
    this.raycaster.setFromCamera(ndc, this.camera);
    const hit = this.raycaster.intersectObjects(this.props, true)[0];
    let n = -1;
    for (let o: THREE.Object3D | null = hit?.object ?? null; o; o = o.parent) {
      const m = /^prop_(\d+)$/.exec(o.name);
      if (m) { n = Number(m[1]); break; }
    }
    this.hover3d(n);
  }

  private hover3d(n: number): void {
    if (n === this.hoverProp) return;
    this.hoverProp = n;
    this.highlight(n >= 0 ? [n] : []);
    if (n >= 0) {
      const p = this.report?.props[n];
      this.stage.title = p ? `${n}: ${p.key} (${p.kind}) — ${p.line}` : "";
      this.list.querySelector<HTMLElement>(".rv-entry.hot")?.scrollIntoView({ block: "nearest" });
    } else {
      this.stage.title = "";
    }
  }
}
