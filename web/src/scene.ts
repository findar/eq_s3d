// scene.ts — Three.js scene, GLB loading, and overlay rendering

import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type { ZoneSidecar } from "./api";

const REGION_COLORS: Record<string, number> = {
  water: 0x3a7ad0,
  lava: 0xd04020,
  zoneline: 0xe0c040,
  pvp: 0xc040c0,
  ice: 0x80d0e0,
  generic: 0x808080,
};

// The tint of the rooms an accepted edit touched.
const HIGHLIGHT = 0x4dd0e1;

/** A mesh's material(s) as a list (three allows one or an array). */
function materialsOf(mesh: THREE.Mesh): THREE.Material[] {
  const m = mesh.material;
  if (!m) return [];
  return Array.isArray(m) ? m : [m];
}

/** Remove every child of `group`, disposing its geometries, materials and textures. */
function clearDisposed(group: THREE.Object3D): void {
  for (const child of [...group.children]) {
    group.remove(child);
    child.traverse((o) => {
      const mesh = o as THREE.Mesh;
      mesh.geometry?.dispose();
      for (const mat of materialsOf(mesh)) {
        for (const v of Object.values(mat)) {
          if (v instanceof THREE.Texture) v.dispose();
        }
        mat.dispose();
      }
    });
  }
}

export class ZoneScene {
  readonly scene = new THREE.Scene();
  readonly camera: THREE.PerspectiveCamera;
  readonly renderer: THREE.WebGLRenderer;

  private zoneGroup = new THREE.Group();
  private lightGroup = new THREE.Group();
  private regionGroup = new THREE.Group();
  private gateGroup = new THREE.Group();
  private labelGroup = new THREE.Group();
  // The rooms an accepted edit touched (highlightRooms).
  private highlightGroup = new THREE.Group();
  private wireframe: THREE.LineSegments | null = null;
  // The GLB's `vegetation` node (wilderness trees), or null when it has none.
  private vegetation: THREE.Object3D | null = null;
  private loader = new GLTFLoader();

  constructor(canvas: HTMLCanvasElement) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setPixelRatio(window.devicePixelRatio);

    this.scene.background = new THREE.Color(0x0a0a12);
    this.scene.fog = new THREE.Fog(0x0a0a12, 400, 4000);

    this.camera = new THREE.PerspectiveCamera(75, 1, 0.5, 20000);

    // Lighting so geometry reads well
    this.scene.add(new THREE.AmbientLight(0x4a5566, 1.4));
    const sun = new THREE.DirectionalLight(0xfff0e0, 1.6);
    sun.position.set(300, 500, 400);
    this.scene.add(sun);
    const fill = new THREE.DirectionalLight(0x8090b0, 0.6);
    fill.position.set(-300, -200, 200);
    this.scene.add(fill);

    this.scene.add(this.zoneGroup);
    this.scene.add(this.lightGroup);
    this.scene.add(this.regionGroup);
    this.scene.add(this.gateGroup);
    this.scene.add(this.labelGroup);
    this.scene.add(this.highlightGroup);

    this.resize();
    window.addEventListener("resize", () => this.resize());
  }

  resize(): void {
    // The canvas's laid-out size: the bar above it can wrap to more than one
    // row on a narrow window (main.ts keeps --header-h), so 52 is only a
    // fallback.
    const canvas = this.renderer.domElement;
    const w = canvas.clientWidth || window.innerWidth - 240;
    const h = canvas.clientHeight || window.innerHeight - 52;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h, false);
  }

  /** Load a GLB zone. Returns the bounding box for camera placement. The
   *  zone on screen stays until the new one has loaded (a rebuild or another
   *  version), then is disposed. `isCurrent`, asked once the GLB is in: false
   *  drops it (a later load overtook this one) and answers null. */
  async loadZone(glbUrl: string, isCurrent: () => boolean = () => true): Promise<THREE.Box3 | null> {
    const gltf = await this.loader.loadAsync(glbUrl);
    const model = gltf.scene;
    if (!isCurrent()) {
      const holder = new THREE.Group();
      holder.add(model);
      clearDisposed(holder);
      return null;
    }

    // Drop the previous zone only now, so a failed or slow load leaves it up.
    clearDisposed(this.zoneGroup);
    if (this.wireframe) { this.wireframe = null; }
    this.vegetation = model.getObjectByName("vegetation") ?? null;

    // Textured terrain (one primitive per material, embedded diffuse): the
    // loader already applies each texture with repeat wrapping. Sharpen it at
    // grazing angles so a wall's placeholder label stays readable along a
    // corridor. Untextured (base-colour) meshes are left as they load.
    const anisotropy = this.renderer.capabilities.getMaxAnisotropy();
    model.traverse((o: THREE.Object3D) => {
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh) return;
      for (const mat of materialsOf(mesh)) {
        const map = (mat as THREE.MeshStandardMaterial).map;
        if (map) {
          map.anisotropy = anisotropy;
          map.needsUpdate = true;
        }
      }
    });

    // Frame on the terrain node when the GLB has one, so trees never shift the
    // centring or the camera start; a single-mesh GLB frames on the whole model.
    const box = new THREE.Box3().setFromObject(model.getObjectByName("terrain") ?? model);
    const center = box.getCenter(new THREE.Vector3());
    // Centre the zone on the origin so overlays line up
    model.position.sub(center);
    this.zoneGroup.add(model);

    // Store the centering offset so overlays can match
    this.zoneGroup.userData.offset = center.clone().negate();

    return box;
  }

  /** Render light + region overlays from the sidecar, applying the centering offset. */
  applyOverlays(sidecar: ZoneSidecar): void {
    for (const g of [this.lightGroup, this.regionGroup, this.gateGroup, this.labelGroup]) {
      clearDisposed(g);
    }

    const offset: THREE.Vector3 =
      this.zoneGroup.userData.offset ?? new THREE.Vector3();

    // Lights — glowing spheres at each light position
    for (const lt of sidecar.lights) {
      const color = new THREE.Color(lt.color[0], lt.color[1], lt.color[2]);
      const sphere = new THREE.Mesh(
        new THREE.SphereGeometry(8, 12, 12),
        new THREE.MeshBasicMaterial({ color })
      );
      sphere.position.set(
        lt.pos[0] + offset.x,
        lt.pos[1] + offset.y,
        lt.pos[2] + offset.z
      );
      this.lightGroup.add(sphere);

      // Faint radius wire sphere
      const radius = new THREE.Mesh(
        new THREE.SphereGeometry(lt.radius, 10, 10),
        new THREE.MeshBasicMaterial({ color, wireframe: true, transparent: true, opacity: 0.08 })
      );
      radius.position.copy(sphere.position);
      this.lightGroup.add(radius);
    }

    // Regions — translucent coloured boxes
    for (const reg of sidecar.regions) {
      const color = REGION_COLORS[reg.kind] ?? REGION_COLORS.generic;
      const box = new THREE.Mesh(
        new THREE.BoxGeometry(reg.extent[0] * 2, reg.extent[1] * 2, reg.extent[2] * 2),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.25 })
      );
      box.position.set(
        reg.center[0] + offset.x,
        reg.center[1] + offset.y,
        reg.center[2] + offset.z
      );
      this.regionGroup.add(box);
    }

    // Gates — a red locked-door marker on the corridor, a gold key marker in
    // its room, and a dashed line connecting them.
    for (const g of sidecar.gates ?? []) {
      const lockPos = new THREE.Vector3(
        g.lock[0] + offset.x, g.lock[1] + offset.y, g.lock[2] + offset.z + 15);
      const keyPos = new THREE.Vector3(
        g.key[0] + offset.x, g.key[1] + offset.y, g.key[2] + offset.z + 15);

      const lock = new THREE.Mesh(
        new THREE.BoxGeometry(16, 16, 24),
        new THREE.MeshBasicMaterial({ color: 0xe53935 })
      );
      lock.position.copy(lockPos);
      this.gateGroup.add(lock);

      const key = new THREE.Mesh(
        new THREE.OctahedronGeometry(12),
        new THREE.MeshBasicMaterial({ color: 0xffd24a })
      );
      key.position.copy(keyPos);
      this.gateGroup.add(key);

      const line = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([keyPos, lockPos]),
        new THREE.LineDashedMaterial({ color: 0xffd24a, dashSize: 20, gapSize: 12,
          transparent: true, opacity: 0.6 })
      );
      line.computeLineDistances();
      this.gateGroup.add(line);
    }

    // Room id labels — a camera-facing sprite floating above each room centre,
    // showing the room's id (e.g. "room_7") so a human can cross-reference the
    // 3D view with the top-down map and the spec. Driven entirely from the
    // sidecar's rooms[]; no geometry or backend data is touched.
    for (const r of sidecar.rooms ?? []) {
      const sprite = this.makeLabelSprite(r.id);
      sprite.position.set(
        r.center[0] + offset.x,
        r.center[1] + offset.y,
        r.center[2] + offset.z + 30   // float above the floor (Z is up)
      );
      this.labelGroup.add(sprite);
    }
  }

  /**
   * Build a camera-facing text sprite for a room id. The text is rendered to a
   * small canvas (white glyphs with a dark outline + translucent backing so
   * it's legible against any floor colour) and used as a CanvasTexture on a
   * THREE.Sprite. Dependency-free — no extra npm packages.
   */
  private makeLabelSprite(text: string): THREE.Sprite {
    const pad = 12;
    const fontSize = 48;
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d")!;
    const font = `bold ${fontSize}px monospace`;

    // Measure first, then size the canvas to fit.
    ctx.font = font;
    const textW = Math.ceil(ctx.measureText(text).width);
    canvas.width = textW + pad * 2;
    canvas.height = fontSize + pad * 2;

    // Re-apply after resizing the canvas (resize resets the 2D context state).
    ctx.font = font;
    ctx.textBaseline = "middle";
    ctx.textAlign = "center";

    // Translucent dark backing for contrast.
    ctx.fillStyle = "rgba(10, 10, 18, 0.6)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const cx = canvas.width / 2;
    const cy = canvas.height / 2;
    // Dark outline + white fill so the id reads over any floor colour.
    ctx.lineWidth = 6;
    ctx.strokeStyle = "rgba(0, 0, 0, 0.9)";
    ctx.strokeText(text, cx, cy);
    ctx.fillStyle = "#ffffff";
    ctx.fillText(text, cx, cy);

    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;
    texture.needsUpdate = true;

    const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
    const sprite = new THREE.Sprite(material);

    // Scale to a sensible world size: ~90u wide, height kept to the canvas
    // aspect so the text isn't stretched.
    const worldW = 90;
    const worldH = worldW * (canvas.height / canvas.width);
    sprite.scale.set(worldW, worldH, 1);
    return sprite;
  }

  /**
   * Tint rooms of the loaded zone (an edit's Affected_Set, zone-generator-edits
   * Req 4.4). The GLB is one terrain mesh with no per-room nodes, so the tint is
   * an overlay drawn from the sidecar: a room with an outline (a graph layout's
   * wall rings) gets its floor filled and its rings traced; one without (a
   * classic layout or a city, whose sidecar keeps only the centre) a disc about
   * its centre, sized to half the way to the nearest other room. The traces draw
   * through walls so a tinted room can be found from anywhere. Returns the ids
   * drawn; an id the sidecar doesn't know is skipped.
   */
  highlightRooms(ids: string[], sidecar: ZoneSidecar): string[] {
    this.clearHighlight();
    const offset: THREE.Vector3 =
      this.zoneGroup.userData.offset ?? new THREE.Vector3();
    const rooms = sidecar.rooms ?? [];
    const outlines = sidecar.layout?.rooms ?? {};
    const drawn: string[] = [];
    const fill = new THREE.MeshBasicMaterial({
      color: HIGHLIGHT, transparent: true, opacity: 0.38, depthWrite: false,
      side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4,
    });
    const line = new THREE.LineBasicMaterial({
      color: HIGHLIGHT, transparent: true, opacity: 0.9, depthTest: false,
    });
    for (const id of ids) {
      const room = rooms.find((r) => r.id === id);
      if (!room) continue;
      const z = room.center[2] + offset.z;
      const rings = (outlines[id]?.outline ?? []).filter((ring) => ring.length >= 3)
        .map((ring) => ring.map(([x, y]) => new THREE.Vector2(x + offset.x, y + offset.y)));
      if (rings.length) {
        // The largest ring is the room's edge; the rest (pillars) are holes in its floor.
        const area = (r: THREE.Vector2[]) => Math.abs(THREE.ShapeUtils.area(r));
        const outer = rings.reduce((a, b) => (area(b) > area(a) ? b : a));
        const shape = new THREE.Shape(outer);
        for (const ring of rings) if (ring !== outer) shape.holes.push(new THREE.Path(ring));
        const mesh = new THREE.Mesh(new THREE.ShapeGeometry(shape), fill);
        mesh.position.z = z + 0.5;
        this.highlightGroup.add(mesh);
        for (const ring of rings) {
          const pts = ring.map((p) => new THREE.Vector3(p.x, p.y, z + 2));
          const loop = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(pts), line);
          loop.renderOrder = 10;
          this.highlightGroup.add(loop);
        }
      } else {
        let nearest = Infinity;
        for (const r of rooms) {
          if (r.id === id) continue;
          nearest = Math.min(nearest, Math.hypot(r.center[0] - room.center[0], r.center[1] - room.center[1]));
        }
        const radius = Math.max(30, Math.min(120, Number.isFinite(nearest) ? nearest * 0.45 : 80));
        const disc = new THREE.Mesh(new THREE.CircleGeometry(radius, 48), fill);
        disc.position.set(room.center[0] + offset.x, room.center[1] + offset.y, z + 0.5);
        this.highlightGroup.add(disc);
        const pts = Array.from({ length: 48 }, (_, i) => {
          const a = (i / 48) * Math.PI * 2;
          return new THREE.Vector3(disc.position.x + Math.cos(a) * radius,
            disc.position.y + Math.sin(a) * radius, z + 2);
        });
        const loop = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(pts), line);
        loop.renderOrder = 10;
        this.highlightGroup.add(loop);
      }
      drawn.push(id);
    }
    return drawn;
  }

  /** Drop the room tint (the next edit, undo, redo or any other version). */
  clearHighlight(): void {
    clearDisposed(this.highlightGroup);
  }

  /** Whether the loaded zone has a `vegetation` node to toggle. */
  hasVegetation(): boolean {
    return this.vegetation !== null;
  }

  /** Whether the last applyOverlays drew any light, region or gate marker. */
  hasLights(): boolean { return this.lightGroup.children.length > 0; }
  hasRegions(): boolean { return this.regionGroup.children.length > 0; }
  hasGates(): boolean { return this.gateGroup.children.length > 0; }

  setVegetationVisible(on: boolean): void {
    if (this.vegetation) this.vegetation.visible = on;
  }

  setWireframe(on: boolean): void {
    this.zoneGroup.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (mesh.isMesh) {
        for (const mat of materialsOf(mesh)) {
          (mat as THREE.MeshStandardMaterial).wireframe = on;
        }
      }
    });
  }

  setLightsVisible(on: boolean): void { this.lightGroup.visible = on; }
  setRegionsVisible(on: boolean): void { this.regionGroup.visible = on; }
  setGatesVisible(on: boolean): void { this.gateGroup.visible = on; }
  setLabelsVisible(on: boolean): void { this.labelGroup.visible = on; }

  render(): void {
    this.renderer.render(this.scene, this.camera);
  }
}
