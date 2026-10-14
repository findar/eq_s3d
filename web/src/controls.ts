// controls.ts — first-person WASD + pointer-lock mouse look

import * as THREE from "three";

export class FirstPersonControls {
  private camera: THREE.PerspectiveCamera;
  private domElement: HTMLElement;
  private keys: Record<string, boolean> = {};
  private yaw = 0;
  private pitch = 0;
  private locked = false;
  private resetPos = new THREE.Vector3(0, 0, 50);

  // Movement speeds in EQ units/sec (character ≈ 6 units tall)
  walkSpeed = 120;
  sprintSpeed = 400;

  onLockChange?: (locked: boolean) => void;

  constructor(camera: THREE.PerspectiveCamera, domElement: HTMLElement) {
    this.camera = camera;
    this.domElement = domElement;

    document.addEventListener("keydown", (e) => { this.keys[e.code] = true; });
    document.addEventListener("keyup", (e) => { this.keys[e.code] = false; });

    domElement.addEventListener("click", () => {
      if (!this.locked) domElement.requestPointerLock();
    });

    document.addEventListener("pointerlockchange", () => {
      this.locked = document.pointerLockElement === domElement;
      this.onLockChange?.(this.locked);
    });

    document.addEventListener("mousemove", (e) => {
      if (!this.locked) return;
      this.yaw -= e.movementX * 0.0022;
      this.pitch -= e.movementY * 0.0022;
      const lim = Math.PI / 2 - 0.05;
      this.pitch = Math.max(-lim, Math.min(lim, this.pitch));
    });
  }

  setStart(pos: THREE.Vector3, lookYaw = 0): void {
    this.camera.position.copy(pos);
    this.resetPos.copy(pos);
    this.yaw = lookYaw;
    this.pitch = 0;
  }

  update(dt: number): void {
    const euler = new THREE.Euler(this.pitch, this.yaw, 0, "YXZ");
    this.camera.quaternion.setFromEuler(euler);

    const speed =
      this.keys["ShiftLeft"] || this.keys["ShiftRight"]
        ? this.sprintSpeed
        : this.walkSpeed;

    const move = new THREE.Vector3();
    if (this.keys["KeyW"] || this.keys["ArrowUp"]) move.z -= 1;
    if (this.keys["KeyS"] || this.keys["ArrowDown"]) move.z += 1;
    if (this.keys["KeyA"] || this.keys["ArrowLeft"]) move.x -= 1;
    if (this.keys["KeyD"] || this.keys["ArrowRight"]) move.x += 1;
    if (this.keys["KeyE"] || this.keys["Space"]) move.y += 1;
    if (this.keys["KeyQ"]) move.y -= 1;

    if (move.lengthSq() > 0) {
      move.normalize().multiplyScalar(speed * dt);
      move.applyQuaternion(this.camera.quaternion);
      this.camera.position.add(move);
    }

    if (this.keys["KeyR"]) {
      this.camera.position.copy(this.resetPos);
      this.yaw = 0;
      this.pitch = 0;
    }
  }
}
