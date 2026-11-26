// api.ts — client for the eq_s3d FastAPI backend

// The Controls sub-object the server's controls path drives generation from
// (server/app.py GenerateRequest.controls). Matches ZonePlan.from_controls:
// zone_type/room_count/size/verticality/locks (the web app sends these names).
export interface GenerateControls {
  zone_type?: string;
  room_count?: number;
  size?: string;
  verticality?: string;
  // Dungeon / city / outdoor dungeon only: how far rough corridors stray, 0
  // (straight) to 2; 1 is the stock tunnel (winding-control step 26).
  winding?: number;
  // Dungeon / city / outdoor dungeon only: how long the halls between rooms run,
  // 0.5 to 3, a multiple of today's; 1 is the default (hall-length step 30).
  hall_length?: number;
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
  // The zone types /api/controls lists (rooms and Sites): the Decor control
  // (a value from /api/controls) and the decor seed that rerolls the Props alone.
  decor?: string;
  decor_seed?: number;
  // Decor layers (rules/decor/layers/) on top of the theme's; absent for none.
  decor_layers?: string[];
  // Every zone type: the rooms seed that rerolls the rooms and Sites alone.
  rooms_seed?: number;
  // Dungeon only: split the rooms into 2-3 Districts (left out: off).
  districts?: boolean;
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
  // Rerolls the rooms and Sites on the same World, in either mode ("Reroll rooms").
  rooms_seed?: number;
}

export interface ZonePlan {
  zone_type: string;
  room_count: number;
  size: string;
  elevation: boolean;
  verticality: string;
  // Absent at the default, 1 (ZonePlan.to_dict leaves it out).
  winding?: number;
  hall_length?: number;
  regions: string[];
  mood: string;
  prompt: string;
  // Sites (wilderness / outdoor dungeon): how many, and who builds them.
  sites?: string;
  inhabitant?: string;
  // Decor ("" = the default) and the decor seed (null = the zone's).
  decor?: string;
  decor_seed?: number | null;
  // The rooms seed (null = the zone's).
  rooms_seed?: number | null;
  // Districts on (dungeon only; absent on a plan from before step 20).
  districts?: boolean;
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
  // The build's Quality_Block, equal to its sidecar's `quality` entry; the page
  // shows the sidecar's (quality.ts), so every way a version opens is the same.
  quality?: QualityBlock | null;
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
  // The room's own decor seed, when it keeps one (else the zone's decor seed).
  decor_seed?: number;
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
  // Sites dressed (wilderness, outdoor dungeon); absent when none were.
  sites?: number;
  bare: number;
  drops: number;
  check: string[];
  // The decor layers merged on, in merge order (theme's, race's, the
  // request's); absent when none were.
  layers?: string[];
}

// One control's list (/api/controls): its values in order, the default and
// the zone types it applies to.
export interface ControlListing {
  values: string[];
  default: string;
  zone_types: string[];
}

// One decor layer /api/controls lists: its name and description.
export interface DecorLayerListing {
  name: string;
  description: string;
}

export interface ControlsListing {
  decor?: ControlListing;
  decor_layers?: DecorLayerListing[];
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

// One District of a multi-District dungeon (generators/zone_spec.py DistrictSpec);
// the sidecar lists them only when the zone has two or more.
export interface ZoneDistrict {
  id: number;                  // 0 holds the zone entrance; the page shows id + 1
  purpose: string;             // an archetype name (the page calls it a theme)
  entrance_room: string;
  climax_room: string;
  room_ids: string[];
  threshold_corridor: string | null;
  relationship: string;
  palette: string;
  light_mood: string;
}

// How the page and the map name a District: "District 1 — tomb" (mapview.district_label).
export function districtLabel(d: { id: number; purpose: string }): string {
  return `District ${d.id + 1}` + (d.purpose ? ` — ${d.purpose}` : "");
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
  // Districts (districts spec Req 4.4): only when the zone has two or more.
  districts?: ZoneDistrict[];
  // Sites (wilderness, outdoor dungeon): each Site's Props ride on its row, and
  // `socket` names the point `site` Socket it stands on (site-sockets; absent
  // on older sidecars).
  sites?: { sites?: { kind?: string; socket?: string | null; props?: ZoneProp[] }[] };
  // Every stage seed the build used, resolved (world-sockets Req 4.4).
  // room_decor_seeds: the rooms that keep their own decor seed (room id -> seed).
  seeds?: {
    seed: number | null; rooms_seed: number | null; decor_seed: number | null;
    room_decor_seeds?: Record<string, number>;
  };
  // Which version this is (partial-rebuild Req 1.2): v2 and later; v1 has none.
  version?: ZoneVersionBlock;
  // The World's Sockets and what attached to each (world-sockets task 6).
  sockets?: ZoneSocket[];
  // The traced outline (pipeline map post-pass): bounds are
  // [x0, y0, z0, x1, y1, z1] of the Floor_Region.
  outline?: { bounds: number[] } | null;
  // The layout engine's report; on a graph layout each room's outline rings
  // (world x, y), which the map dialog hit-tests a click against.
  layout?: { rooms?: Record<string, { outline?: number[][][] }> } | null;
  // The Quality_Block (zone-generator-quality Req 3, 4): absent on a version
  // built before step 19 (quality.ts shows "quality unknown").
  quality?: QualityBlock;
}

// The build's quality (umbrella 25.2-25.4): the same in the generate, rebuild
// and edit responses and in the sidecar. An open band end is null.
export interface QualityBlock {
  degraded: boolean;
  reason: string | null;
  score: number;
  metrics: Record<string, number>;
  out_of_band: { metric: string; value: number; lo: number | null; hi: number | null }[];
}

// ---- The room view (decor-rules Req 4, 5) ----

// POST /api/room_decor: one room of a build re-decorated. Left out, the seed,
// level and layers are what the build's Decor ran with (its sidecar);
// decor_layers [] is the theme's alone, [name] one layer on top.
export interface RoomDecorParams {
  zone: string;
  version: number | string;
  room: string;
  decor_seed?: number;
  control?: string;
  decor_layers?: string[];
}

// A Prop in the report: the sidecar's shape plus the recipe line it came from.
export interface RoomProp extends ZoneProp {
  line: string;                // "rooms.toml kinds.chamber props[0]"
  at?: string;
  poi?: number | null;
  group?: number | null;
  w?: number;
  d?: number;
  h?: number;
}

export interface RoomPoi {
  index: number;
  purpose: string;
  name: string;
  x: number;
  y: number;
  z: number;
  dressing: string[];          // model keys of its Props
  props: number[];             // their indices in `props`
  dropped: string[];           // reasons
}

export interface RoomDrop {
  step: string;
  line: string;
  what: string;
  reason: string;
  poi: number | null;
}

export interface RoomDecorReport {
  zone: string;
  version: string;
  glb_url: string;             // the room alone; Prop n is node `prop_<n>`
  room: {
    id: string; source: string; room_type: string; kind: string;
    theme: string; race: string; zone_type: string;
    box: number[];             // x0, y0, z0, x1, y1, z1
  };
  seed: number;                // the seed the Props came from
  zone_seed?: number;          // the build's zone decor seed (the bare draw's)
  room_seed?: number | null;   // the room's own seed (a reroll's, or the one it keeps)
  control: string;
  layers: string[];
  sets: string[];
  bare: boolean;
  props: RoomProp[];
  pois: RoomPoi[];
  drops: RoomDrop[];
  check: string[];
  install: boolean;
  bare_replayed: number;
  notes: string[];
  took_ms: number;
}

export async function fetchRoomDecor(params: RoomDecorParams): Promise<RoomDecorReport> {
  const res = await fetch("/api/room_decor", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    // FastAPI's detail: a string, or {message, errors} for a failing rule file.
    let msg = `room decor failed (${res.status})`;
    try {
      const body = await res.json();
      const d = body?.detail;
      if (typeof d === "string") msg += `: ${d}`;
      else if (d?.message) msg += `: ${d.message}` + (d.errors?.length ? `\n${d.errors.join("\n")}` : "");
      else if (d) msg += `: ${JSON.stringify(d)}`;
    } catch { /* not JSON: the status alone */ }
    throw new Error(msg);
  }
  return res.json();
}

// What attached to a Socket: a dungeon or city ({kind, rooms}), the ground's
// Sites ({kind: "sites", sites}) or, on a point `site` Socket, the Site standing
// on it ({kind: "site", site: <its kind>, group: <the point's Group>}).
export interface SocketAttachment {
  kind: string;
  rooms?: number;
  sites?: number;
  site?: string;
  group?: number;
}

// One Socket in the sidecar (generators/stages.py sockets_sidecar).
export interface ZoneSocket {
  id: string;
  kind: string;                // root | hillside | ground | site | door
  point: [number, number, number];
  side: string;                // N/E/S/W, "" when none
  attached: SocketAttachment | null;
  group?: number;              // a site point's Group, used or not
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

// ---- Versions of one zone (partial-rebuild Req 1, 2) ----

// A version's `version` block (the sidecar's on v2 and later, the rebuild
// answer's version_info): its number, the version it was rebuilt from, the
// inputs that differ from that one ("decor_seed", "rooms_seed", "room_decor")
// and how ("full": planned again; "partial": from the parent's saved stages).
export interface ZoneVersionBlock {
  n: number;
  parent: number | null;
  changed: string[];
  how: string | null;
}

// POST /api/rebuild: the next version of `zone` from `version`, changing what
// it names (at least one). room_decor keeps one room's decor seed in the zone.
export interface RebuildParams {
  zone: string;
  version: number | string;
  decor_seed?: number;
  rooms_seed?: number;
  room_decor?: { room: string; decor_seed: number };
}

export interface RebuildResult extends GenerateResult {
  version_info: ZoneVersionBlock;
}

// One finished version in GET /api/zones/<zone>/versions, in order.
export interface ZoneVersionEntry {
  n: number;
  parent: number | null;
  changed: string[];
  how: string | null;
  seeds: ZoneSidecar["seeds"] | null;
  created: string;
  took_ms: number | null;
  // The edit that made this version ({text, ops}; text null when ops were sent), else null.
  edit?: { text: string | null; ops: EditOp[] } | null;
  // Its sidecar's quality, in brief; null for a version built before step 19.
  quality?: { degraded: boolean; reason: string | null } | null;
  glb_url: string;
  zone_url: string;
  map_url: string;
  eqg_url: string;
}

export interface ZoneVersions {
  zone: string;
  versions: ZoneVersionEntry[];
}

// FastAPI's error detail as words: a string, or {message, errors}.
async function errorDetail(res: Response, what: string): Promise<string> {
  let msg = `${what} failed (${res.status})`;
  try {
    const d = (await res.json())?.detail;
    if (typeof d === "string") msg += `: ${d}`;
    else if (d?.message) msg += `: ${d.message}`;
    else if (d) msg += `: ${JSON.stringify(d)}`;
  } catch { /* not JSON: the status alone */ }
  return msg;
}

export async function rebuildZone(params: RebuildParams): Promise<RebuildResult> {
  const res = await fetch("/api/rebuild", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(await errorDetail(res, "rebuild"));
  return res.json();
}

export async function fetchZoneVersions(zone: string): Promise<ZoneVersions> {
  const res = await fetch(`/api/zones/${encodeURIComponent(zone)}/versions`, { cache: "no-store" });
  if (!res.ok) throw new Error(await errorDetail(res, "versions fetch"));
  return res.json();
}

// ---- Edits: feedback on a version (zone-generator-edits Req 3, 4; decision 10) ----

// One edit op (ai/edits.py): {op, target?, ...its parameters}.
export interface EditOp {
  op: string;
  target?: string;
  [param: string]: unknown;
}

// POST /api/edit: feedback `text` (or `ops`, exactly one) on `version` of `zone`.
export interface EditParams {
  zone: string;
  version: number | string;
  text?: string;
  ops?: EditOp[];
  seed?: number;
}

// An op that didn't apply, and why.
export interface EditRefusal {
  op: unknown;
  reason: string;
}

// What an edit did. applied: `version` was written and `build` opens it. Not applied:
// nothing changed, and `help`, `invalid`, `rejected` or `diagnostics` says why.
export interface EditResult {
  applied: boolean;
  zone: string;
  parent: number;
  version: number | null;
  interpreter: string | null;
  text: string | null;
  ops: EditOp[];
  notes: string[];
  affected: { rooms: string[]; corridors: string[] };
  how: string | null;
  help: string | null;
  invalid: EditRefusal[];
  rejected: EditRefusal[];
  diagnostics: { seed: number; attempt: number; checks: string[]; reasons: string[] }[];
  build: RebuildResult | null;
}

export async function editZone(params: EditParams): Promise<EditResult> {
  const res = await fetch("/api/edit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(await errorDetail(res, "edit"));
  return res.json();
}

// ---- Export: a build as a takeover of an existing zone (export spec Req 4) ----

// One known RoF2 zone (GET /api/shortnames), installed ones first.
export interface KnownZone {
  shortname: string;
  long_name: string;
  container: string;           // "s3d" | "eqg"
  in_install: boolean;         // its archive is in the server's EQ install
}

export interface ShortnameListing {
  default: string;             // "arena"
  zones: KnownZone[];
}

export async function fetchShortnames(): Promise<ShortnameListing> {
  const res = await fetch("/api/shortnames");
  if (!res.ok) throw new Error(await errorDetail(res, "short names fetch"));
  return res.json();
}

// POST /api/export: the version to export and the zone it replaces (blank or
// absent = the default); clear_spawns adds the spawn cleanup to the SQL.
export interface ExportParams {
  zone: string;
  version: number | string;
  shortname?: string;
  clear_spawns?: boolean;
}

// One file of an Export, in order: eqg, eqmap by layer, sql, sidecar, install,
// then the bundle (zipped on its first request; absent without the SQL).
export interface ExportFile {
  kind: string;                // "eqg" | "eqmap" | "sql" | "sidecar" | "install" | "bundle"
  filename: string;            // relative to export/<short>/ ("maps/<short>_1.txt")
  url: string;
  layer: number | null;        // eqmap only
}

export interface ExportResult {
  zone: string;
  version: string;             // "v3"
  shortname: string;
  clear_spawns: boolean;
  sql_written: boolean;        // false when the format check failed
  format: { passed: boolean; checks: { name: string; passed: boolean; messages: string[] }[] } | null;
  warnings: string[];
  files: ExportFile[];
}

// The 400 for an unknown short name: the message, the name and up to 5 close ones.
export class ExportNameError extends Error {
  constructor(message: string, readonly shortname: string, readonly close: string[]) {
    super(message);
  }
}

export async function exportZone(params: ExportParams): Promise<ExportResult> {
  const res = await fetch("/api/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (res.status === 400) {
    let d: any = null;
    try { d = (await res.clone().json())?.detail; } catch { /* not JSON */ }
    if (d && typeof d === "object" && typeof d.message === "string") {
      throw new ExportNameError(d.message, String(d.shortname ?? ""),
        Array.isArray(d.close) ? d.close.map(String) : []);
    }
  }
  if (!res.ok) throw new Error(await errorDetail(res, "export"));
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
