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
  // Wilderness only: side (N/E/S/W) -> mountain | river | zoneline.
  edges?: Record<string, string>;
  // Wilderness only: tree density, none | sparse | normal | dense.
  trees?: string;
  // Wilderness / outdoor dungeon only: Sites none | sparse | normal | dense,
  // and who builds them (human | orc | gnoll | centaur, "" for the biome's mix).
  sites?: string;
  inhabitant?: string;
  // Dungeon / outdoor dungeon only: the layout engine, classic | graph.
  layout?: string;
  // Graph layout only: a base rule set, or "" for the theme's set.
  rule_set?: string;
  // Dungeon / city / outdoor dungeon only: ai/schema.py VALID_DUNGEON_THEMES /
  // VALID_DUNGEON_RACES, or "" for none.
  dungeon_theme?: string;
  dungeon_race?: string;
  // Dungeon / city / outdoor dungeon only: the Decor control (a value from
  // /api/controls) and the decor seed that rerolls the Props alone.
  decor?: string;
  decor_seed?: number;
}

// The /api/generate request body. The server resolves `mode` explicitly:
// "prompt" uses `prompt`, "controls" uses `controls`. `seed` pins randomness
// in either mode (omit for a fresh random seed).
export interface GenerateParams {
  mode?: "prompt" | "controls";
  prompt?: string;
  controls?: GenerateControls;
  seed?: number;
  // Rerolls the Props alone, in either mode ("Reroll decor").
  decor_seed?: number;
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
  // Sites (wilderness / outdoor dungeon): how many, and who builds them.
  sites?: string;
  inhabitant?: string;
  // Decor ("" = the default) and the decor seed (null = the zone's).
  decor?: string;
  decor_seed?: number | null;
}

// One file of an accepted build (server/app.py ArtifactRef), in panel order:
// map_svg, eqmap by layer, eqg, glb, sidecar.
export interface ArtifactRef {
  kind: string;                // "map_svg" | "eqmap" | "eqg" | "glb" | "sidecar"
  filename: string;            // relative to the build dir ("maps/<name>_1.txt")
  url: string;                 // the build-file route that serves it
  layer?: number | null;       // eqmap only: 0 = main band, 1..3
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
  eqg_url?: string;            // the zone archive ("" when none was written)
  artifacts?: ArtifactRef[];   // every file the build wrote, with its URL
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
  // Props (room-decor; only when the build placed any): each Prop, its
  // Dressing by POI, and what dropped and why.
  props?: ZoneProp[];
  dressing?: { poi: number; purpose: string; name: string; props: string[]; dropped: string[] }[];
  decor_drops?: { step: string; line: string; what: string; reason: string; poi: number | null }[];
  bare?: boolean;
}

// One placed Prop (generators/decor/placement.py Prop.to_dict).
export interface ZoneProp {
  key: string;
  kind: string;
  category: string;
  mount: string;               // floor | wall | ceiling | raised
  set: string;
  x: number;
  y: number;
  z: number;
  yaw: number;
  scale: number;
  step: string;
}

// The sidecar's top-level decor block (generators/builder.py DecorBuild.summary).
export interface ZoneDecor {
  control: string;
  seed: number;
  props: number;
  lights: number;
  models: number;
  rooms: number;
  bare: number;
  drops: number;
  check: string[];
}

// One control's list (/api/controls): its values in order, the default and
// the zone types it applies to.
export interface ControlListing {
  values: string[];
  default: string;
  zone_types: string[];
}

export interface ControlsListing {
  decor?: ControlListing;
}

export async function fetchControls(): Promise<ControlsListing> {
  const res = await fetch("/api/controls");
  if (!res.ok) throw new Error(`controls fetch failed (${res.status})`);
  return res.json();
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
  // Props (room-decor): present only when the build placed Props.
  decor?: ZoneDecor;
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
