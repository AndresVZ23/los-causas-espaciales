// Jugador en primera persona sobre la maqueta: teclado y mouse en escritorio, arrastre con el dedo en pantallas táctiles.
// Camina con gravedad, sube un bloque sin saltar y puede volar para ver la zona desde arriba.

import type { PerspectiveCamera } from "three";
import { WATER, cellIndex, type ZoneGrid } from "./zone-data";

const WALK = 7, RUN = 13, FLY = 20, FLY_FAST = 38;
const GRAVITY = 26, JUMP = 8.5, STEP = 1.05, RADIUS = 0.3;
const EYE = 1.7, EYE_IN_WATER = 1.05, CEILING = 150;
const MOVE_KEYS: Record<string, [number, number]> = {
  KeyW: [1, 0], ArrowUp: [1, 0], KeyS: [-1, 0], ArrowDown: [-1, 0], KeyD: [0, 1], ArrowRight: [0, 1], KeyA: [0, -1], ArrowLeft: [0, -1],
};

export type PlayerState = { x: number; z: number; feet: number; yaw: number; flying: boolean; inWater: boolean };
export type Player = {
  update: (seconds: number) => void; state: () => PlayerState;
  place: (x: number, z: number, options?: { height?: number; flying?: boolean }) => void; lookAt: (x: number, y: number, z: number) => void;
  setFlying: (on: boolean) => void; jump: () => void; setLift: (direction: -1 | 0 | 1) => void; capture: () => void; dispose: () => void;
};

export type PlayerEvents = {
  onLock: (locked: boolean) => void; onFly: (flying: boolean) => void;
  /** Con el mouse capturado: clic izquierdo quita un bloque y clic derecho pone la pieza elegida. */
  onAct: (action: "break" | "place") => void;
  /** Rueda del mouse: pieza siguiente (+1) o anterior (−1). */
  onWheel: (direction: 1 | -1) => void;
};

export function createPlayer(camera: PerspectiveCamera, surface: HTMLElement, grid: ZoneGrid, events: PlayerEvents): Player {
  let x = grid.size / 2, z = grid.size / 2, feet = 0, eye = EYE, velocity = 0, yaw = 0, pitch = 0;
  let flying = false, grounded = false, lift: -1 | 0 | 1 = 0;
  const keys = new Set<string>();
  const stick = { id: -1, startX: 0, startY: 0, x: 0, y: 0 };
  const look = { id: -1, x: 0, y: 0 };
  const groundAt = (px: number, pz: number) => grid.solid[cellIndex(grid, px, pz)];
  const edge = (value: number) => Math.min(grid.size - 0.4, Math.max(0.4, value));
  const turn = (dx: number, dy: number, rate: number) => {
    yaw -= dx * rate;
    pitch = Math.max(-1.5, Math.min(1.5, pitch - dy * rate));
  };
  const setFlying = (on: boolean) => {
    if (flying === on) return;
    flying = on; velocity = 0; grounded = false;
    events.onFly(on);
  };
  const jump = () => { if (!flying && grounded) { velocity = JUMP; grounded = false; } };
  const typing = () => { const tag = document.activeElement?.tagName; return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT"; };

  const onKeyDown = (event: KeyboardEvent) => {
    if (typing() || event.ctrlKey || event.metaKey || event.altKey) return;
    const onButton = document.activeElement?.tagName === "BUTTON" || document.activeElement?.tagName === "A";
    if (event.code === "Space") {
      if (onButton) return;          // Espacio sobre un botón lo acciona; no debe saltar a la vez
      event.preventDefault();
      if (flying) keys.add("Space"); else jump();
      return;
    }
    if (event.code in MOVE_KEYS || event.code === "KeyE" || event.code === "KeyQ" || event.code.startsWith("Shift")) {
      if (event.code.startsWith("Arrow")) event.preventDefault();
      keys.add(event.code);
    } else if (event.code === "KeyF" && !event.repeat) setFlying(!flying);
  };
  const onKeyUp = (event: KeyboardEvent) => { keys.delete(event.code); };
  const onBlur = () => { keys.clear(); stick.id = -1; stick.x = stick.y = 0; look.id = -1; };
  const capture = () => {
    try { void (surface.requestPointerLock() as unknown as Promise<void> | undefined)?.catch?.(() => undefined); } catch { /* sin captura, se mira arrastrando */ }
  };
  const onLockChange = () => events.onLock(document.pointerLockElement === surface);
  const onMouseMove = (event: MouseEvent) => { if (document.pointerLockElement === surface) turn(event.movementX, event.movementY, 0.0022); };
  const onPointerDown = (event: PointerEvent) => {
    if (event.pointerType === "mouse") { if (event.button === 0) { look.id = event.pointerId; look.x = event.clientX; look.y = event.clientY; } return; }
    const box = surface.getBoundingClientRect();
    surface.setPointerCapture(event.pointerId);
    if (stick.id < 0 && event.clientX < box.left + box.width * 0.45) { stick.id = event.pointerId; stick.startX = event.clientX; stick.startY = event.clientY; stick.x = stick.y = 0; }
    else if (look.id < 0) { look.id = event.pointerId; look.x = event.clientX; look.y = event.clientY; }
  };
  const onPointerMove = (event: PointerEvent) => {
    if (event.pointerId === stick.id) {
      stick.x = Math.max(-1, Math.min(1, (event.clientX - stick.startX) / 55));
      stick.y = Math.max(-1, Math.min(1, (event.clientY - stick.startY) / 55));
    } else if (event.pointerId === look.id && document.pointerLockElement !== surface) {
      turn(event.clientX - look.x, event.clientY - look.y, event.pointerType === "mouse" ? 0.004 : 0.006);
      look.x = event.clientX; look.y = event.clientY;
    }
  };
  const onPointerUp = (event: PointerEvent) => {
    if (event.pointerId === stick.id) { stick.id = -1; stick.x = stick.y = 0; }
    if (event.pointerId === look.id) look.id = -1;
  };
  // Poner y quitar solo con el mouse capturado: el clic que captura el mouse no debe romper un bloque.
  const onMouseDown = (event: MouseEvent) => {
    if (document.pointerLockElement !== surface) return;
    if (event.button === 0) events.onAct("break");
    else if (event.button === 2) events.onAct("place");
  };
  const onContextMenu = (event: Event) => event.preventDefault();
  const onWheel = (event: WheelEvent) => { if (event.deltaY !== 0) events.onWheel(event.deltaY > 0 ? 1 : -1); };

  window.addEventListener("keydown", onKeyDown);
  window.addEventListener("keyup", onKeyUp);
  window.addEventListener("blur", onBlur);
  document.addEventListener("pointerlockchange", onLockChange);
  document.addEventListener("mousemove", onMouseMove);
  surface.addEventListener("pointerdown", onPointerDown);
  surface.addEventListener("pointermove", onPointerMove);
  surface.addEventListener("pointerup", onPointerUp);
  surface.addEventListener("pointercancel", onPointerUp);
  surface.addEventListener("mousedown", onMouseDown);
  surface.addEventListener("contextmenu", onContextMenu);
  surface.addEventListener("wheel", onWheel, { passive: true });

  const sync = () => {
    camera.position.set(x, feet + eye, z);
    camera.rotation.set(pitch, yaw, 0, "YXZ");
  };

  return {
    update: (seconds) => {
      let forward = -stick.y, strafe = stick.x;
      for (const code of keys) { const move = MOVE_KEYS[code]; if (move) { forward += move[0]; strafe += move[1]; } }
      const length = Math.hypot(forward, strafe);
      if (length > 1) { forward /= length; strafe /= length; }
      const fast = keys.has("ShiftLeft") || keys.has("ShiftRight");
      const inWater = grid.cover[cellIndex(grid, x, z)] === WATER;
      const speed = flying ? (fast ? FLY_FAST : FLY) : (fast ? RUN : WALK) * (inWater ? 0.55 : 1);
      const sin = Math.sin(yaw), cos = Math.cos(yaw);
      const dx = (-sin * forward + cos * strafe) * speed * seconds;
      const dz = (-cos * forward - sin * strafe) * speed * seconds;
      if (flying) {
        x = edge(x + dx); z = edge(z + dz);
        const rise = lift + (keys.has("Space") || keys.has("KeyE") ? 1 : 0) - (keys.has("KeyQ") ? 1 : 0);
        feet = Math.min(CEILING, Math.max(groundAt(x, z), feet + rise * speed * 0.7 * seconds));
      } else {
        // Cada eje por separado: al chocar con un escalón alto el jugador resbala a lo largo en vez de quedarse pegado.
        const nextX = edge(x + dx);
        if (groundAt(nextX + Math.sign(dx) * RADIUS, z) - feet <= STEP) x = nextX;
        const nextZ = edge(z + dz);
        if (groundAt(x, nextZ + Math.sign(dz) * RADIUS) - feet <= STEP) z = nextZ;
        const ground = groundAt(x, z);
        if (grounded && ground > feet) feet = ground;
        velocity = Math.max(-45, velocity - GRAVITY * seconds);
        feet += velocity * seconds;
        if (feet <= ground) { feet = ground; velocity = 0; grounded = true; } else if (feet - ground > 0.02) grounded = false;
      }
      // La altura de los ojos se suaviza: subir un bloque no da un salto de cámara.
      const target = !flying && inWater && grounded ? EYE_IN_WATER : EYE;
      eye += (target - eye) * Math.min(1, seconds * 10);
      sync();
    },
    state: () => ({ x, z, feet, yaw, flying, inWater: grid.cover[cellIndex(grid, x, z)] === WATER }),
    place: (px, pz, options) => {
      x = edge(px); z = edge(pz);
      if (options?.flying !== undefined) setFlying(options.flying);
      feet = Math.max(groundAt(x, z), options?.height ?? 0);
      velocity = 0; grounded = false;
      sync();
    },
    lookAt: (tx, ty, tz) => {
      yaw = Math.atan2(-(tx - x), -(tz - z));
      pitch = Math.max(-1.5, Math.min(1.5, Math.atan2(ty - (feet + eye), Math.hypot(tx - x, tz - z))));
      sync();
    },
    setFlying, jump, capture,
    setLift: (direction) => { lift = direction; },
    dispose: () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      window.removeEventListener("blur", onBlur);
      document.removeEventListener("pointerlockchange", onLockChange);
      document.removeEventListener("mousemove", onMouseMove);
      surface.removeEventListener("pointerdown", onPointerDown);
      surface.removeEventListener("pointermove", onPointerMove);
      surface.removeEventListener("pointerup", onPointerUp);
      surface.removeEventListener("pointercancel", onPointerUp);
      surface.removeEventListener("mousedown", onMouseDown);
      surface.removeEventListener("contextmenu", onContextMenu);
      surface.removeEventListener("wheel", onWheel);
      if (document.pointerLockElement === surface) document.exitPointerLock();
    },
  };
}
