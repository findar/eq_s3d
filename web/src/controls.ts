// controls.ts — first-person WASD + pointer-lock mouse look.
//
// IMPORTANT: EverQuest zones are Z-up (Z is the vertical axis), while Three.js
// defaults to Y-up. We orient the camera for a Z-up world: yaw rotates around
// Z, pitch tilts up/down, and "forward" is in the XY plane. This keeps the
// horizon level and movement intuitive instead of tilted.

import * as THREE from "three";

export class FirstPersonControls {
  private camera: THREE.PerspectiveCamera;
  private domElement: HTMLElement;
  private keys: Record<string, boolean> = {};
  private yaw = 0;      // rotation around world Z (looking left/right)
  private pitch = 0;    // tilt up/down
  private locked = false;

  private startPos = new THREE.Vector3(0, 0, 50);
  private startYaw = 0;

  // Movement speeds in EQ units/sec (character ≈ 6 units tall)
  walkSpeed = 120;
  sprintSpeed = 400;

  onLockChange?: (locked: boolean) => void;

  constructor(camera: THREE.PerspectiveCamera, domElement: HTMLElement) {
    this.camera = camera;
    this.domElement = domElement;

    // Make the camera treat Z as up so the horizon stays level in our Z-up world.
    this.camera.up.set(0, 0, 1);

    // Ignore movement keys while the user is typing into a form field, so
    // WASD/Space/R edit the text instead of flying the camera. We still record
    // keyups so a key held before focusing an input doesn't get stuck down.
    document.addEventListener("keydown", (e) => {
      if (this._typingTarget(e.target)) return;
      this.keys[e.code] = true;
    });
    document.addEventListener("keyup", (e) => { this.keys[e.code] = false; });

    // Releasing pointer lock or blurring the window should clear held keys so
    // the camera doesn't keep drifting.
    const clearKeys = () => { this.keys = {}; };
    window.addEventListener("blur", clearKeys);

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
      const lim = Math.PI / 2 - 0.02;
      this.pitch = Math.max(-lim, Math.min(lim, this.pitch));
    });
  }

  /** True when focus is in a text input / select / textarea / editable node. */
  private _typingTarget(target: EventTarget | null): boolean {
    const el = target as HTMLElement | null;
    if (!el) return false;
    const tag = el.tagName;
    return (
      tag === "INPUT" ||
      tag === "SELECT" ||
      tag === "TEXTAREA" ||
      el.isContentEditable === true
    );
  }

  /** Set the camera start position and the yaw it should face. */
  setStart(pos: THREE.Vector3, lookYaw = 0): void {
    this.startPos.copy(pos);
    this.startYaw = lookYaw;
    this.reset();
  }

  /** Snap the camera back to the starting position and orientation. */
  reset(): void {
    this.camera.position.copy(this.startPos);
    this.yaw = this.startYaw;
    this.pitch = 0;
    this._applyOrientation();
  }

  /** Compute the forward and right vectors for the current yaw/pitch (Z-up). */
  private _forward(): THREE.Vector3 {
    const cp = Math.cos(this.pitch);
    return new THREE.Vector3(
      Math.cos(this.yaw) * cp,
      Math.sin(this.yaw) * cp,
      Math.sin(this.pitch)
    );
  }

  private _right(): THREE.Vector3 {
    // Right is forward rotated -90° in the XY plane (independent of pitch).
    return new THREE.Vector3(Math.sin(this.yaw), -Math.cos(this.yaw), 0);
  }

  private _applyOrientation(): void {
    const target = this.camera.position.clone().add(this._forward());
    this.camera.lookAt(target);
  }

  update(dt: number): void {
    this._applyOrientation();

    const speed =
      this.keys["ShiftLeft"] || this.keys["ShiftRight"]
        ? this.sprintSpeed
        : this.walkSpeed;

    const forward = this._forward();
    const right = this._right();
    const move = new THREE.Vector3();

    if (this.keys["KeyW"] || this.keys["ArrowUp"]) move.add(forward);
    if (this.keys["KeyS"] || this.keys["ArrowDown"]) move.sub(forward);
    if (this.keys["KeyD"] || this.keys["ArrowRight"]) move.add(right);
    if (this.keys["KeyA"] || this.keys["ArrowLeft"]) move.sub(right);
    // Vertical fly (world Z)
    if (this.keys["KeyE"] || this.keys["Space"]) move.z += 1;
    if (this.keys["KeyQ"]) move.z -= 1;

    if (move.lengthSq() > 0) {
      move.normalize().multiplyScalar(speed * dt);
      this.camera.position.add(move);
    }

    if (this.keys["KeyR"]) {
      this.reset();
    }
  }
}
