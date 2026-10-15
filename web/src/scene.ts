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

export class ZoneScene {
  readonly scene = new THREE.Scene();
  readonly camera: THREE.PerspectiveCamera;
  readonly renderer: THREE.WebGLRenderer;

  private zoneGroup = new THREE.Group();
  private lightGroup = new THREE.Group();
  private regionGroup = new THREE.Group();
  private gateGroup = new THREE.Group();
  private wireframe: THREE.LineSegments | null = null;
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

    this.resize();
    window.addEventListener("resize", () => this.resize());
  }

  resize(): void {
    const w = window.innerWidth - 240;
    const h = window.innerHeight - 52;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h, false);
  }

  /** Load a GLB zone. Returns the bounding box for camera placement. */
  async loadZone(glbUrl: string): Promise<THREE.Box3> {
    // Clear previous
    this.zoneGroup.clear();
    if (this.wireframe) { this.wireframe = null; }

    const gltf = await this.loader.loadAsync(glbUrl);
    const model = gltf.scene;

    const box = new THREE.Box3().setFromObject(model);
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
    this.lightGroup.clear();
    this.regionGroup.clear();
    this.gateGroup.clear();

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
  }

  setWireframe(on: boolean): void {
    this.zoneGroup.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (mesh.isMesh) {
        const mat = mesh.material as THREE.MeshStandardMaterial;
        if (mat) mat.wireframe = on;
      }
    });
  }

  setLightsVisible(on: boolean): void { this.lightGroup.visible = on; }
  setRegionsVisible(on: boolean): void { this.regionGroup.visible = on; }
  setGatesVisible(on: boolean): void { this.gateGroup.visible = on; }

  render(): void {
    this.renderer.render(this.scene, this.camera);
  }
}
