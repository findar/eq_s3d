// api.ts — client for the eq_s3d FastAPI backend

// The Controls sub-object the server's controls path drives generation from
// (server/app.py GenerateRequest.controls). Matches ZonePlan.from_controls:
// zone_type/room_count/size/verticality/locks (the web app sends these names).
export interface GenerateControls {
  zone_type?: string;
  room_count?: number;
  size?: string;
  verticality?: string;
  locks?: number;
}

// The /api/generate request body. The server resolves `mode` explicitly:
// "prompt" uses `prompt`, "controls" uses `controls`. `seed` pins randomness
// in either mode (omit for a fresh random seed).
export interface GenerateParams {
  mode?: "prompt" | "controls";
  prompt?: string;
  controls?: GenerateControls;
  seed?: number;
}

export interface ZonePlan {
  zone_type: string;
  room_count: number;
  size: string;
  elevation: boolean;
  verticality: string;
  regions: string[];
  mood: string;
  prompt: string;
}

export interface GenerateResult {
  id: string;
  version: number;             // per-build version (output/<id>/v<version>/)
  mode: string;                // resolved mode: "prompt" | "controls"
  zone_type: string;
  rooms: number;
  seed: number;
  vertices: number;
  polygons: number;
  materials: number;
  glb_url: string;
  zone_url: string;
  map_url: string;             // top-down SVG layout map
  source: string;              // back-compat mirror of `mode`
  planner?: string | null;     // "rule" | "llm"
  plan?: ZonePlan | null;
  gates?: number;
  validated?: boolean;
  attempts?: number;
  // Non-fatal advisories for the UI, e.g. "zone_type_substituted:<planned>->
  // dungeon" or "backend_fallback: <name> unavailable, built with box".
  warnings: string[];
  format_passed: boolean;      // cleared the format gate?
  build_commit?: string;       // short commit of the code the server loaded
}

// /api/version — the code the server process loaded vs. what's on disk now.
export interface VersionInfo {
  commit: string;              // full hash loaded at startup ("unknown" w/o git)
  short: string;               // 7-char form of `commit`
  branch: string;
  dirty: boolean;              // uncommitted tracked changes at startup
  started_at: string;          // ISO UTC
  source_fingerprint: string;  // hash of server-side .py (path, mtime, size)
  current_commit: string;      // HEAD now
  current_fingerprint: string; // fingerprint now
  stale: boolean;              // HEAD or source moved since startup -> restart
}

export interface ZoneLight {
  name: string;
  pos: [number, number, number];
  color: [number, number, number];
  radius: number;
}

export interface ZoneRegion {
  name: string;
  kind: string;
  center: [number, number, number];
  extent: [number, number, number];
}

export interface ZoneRoom {
  id: string;
  role: string;
  graph_depth: number;
  center: [number, number, number];
  // Content / semantic layer (advisory; may be empty on un-themed zones).
  semantic_type?: string;
  room_theme?: string;
  district?: number;
  prop_hints?: string[];
  encounter_intent?: string;
  boss?: boolean;
}

// Content / semantic layer (field names unchanged — dungeon_theme etc.).
export interface ZoneContent {
  dungeon_theme?: string;
  dungeon_race?: string;
  elemental_tint?: string;
}

export interface ZoneGate {
  id: string;
  tier: number;
  lock: [number, number, number];
  key: [number, number, number];
  key_room: string;
}

export interface ZoneSidecar {
  name: string;
  bounds: { min: [number, number, number]; max: [number, number, number] };
  metrics: { vertices: number; polygons: number; materials: number };
  lights: ZoneLight[];
  regions: ZoneRegion[];
  rooms: ZoneRoom[];
  gates: ZoneGate[];
  zone_type?: string;
  // Current sidecars carry the content block under `content`; old sidecars
  // used `theme` for the same data, so the reader falls back to it.
  content?: ZoneContent;
  theme?: ZoneContent;
}

export async function generateZone(params: GenerateParams): Promise<GenerateResult> {
  const res = await fetch("/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`generate failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function fetchVersion(): Promise<VersionInfo> {
  const res = await fetch("/api/version", { cache: "no-store" });
  if (!res.ok) throw new Error(`version fetch failed (${res.status})`);
  return res.json();
}

export async function fetchSidecar(url: string): Promise<ZoneSidecar> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`sidecar fetch failed (${res.status})`);
  return res.json();
}

// One availability entry per defined zone type (server zone_type_listing()):
// disabled types carry a human-readable `reason`, enabled types carry null.
export interface ZoneTypeAvailability {
  name: string;
  enabled: boolean;
  reason: string | null;
}

export interface ZoneTypeListing {
  zone_types: ZoneTypeAvailability[];
  default: string;
  reference_zones: Record<string, unknown>;
}

// The available zone types, from the single source of truth on the server.
export async function fetchZoneTypes(): Promise<ZoneTypeListing> {
  const res = await fetch("/api/zone_types");
  if (!res.ok) throw new Error(`zone_types fetch failed (${res.status})`);
  return res.json();
}
