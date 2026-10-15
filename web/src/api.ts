// api.ts — client for the eq_s3d FastAPI backend

export interface GenerateParams {
  prompt?: string;
  theme?: string;
  rooms?: number;
  elevation?: boolean;
  seed?: number;
}

export interface ZonePlan {
  theme: string;
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
  theme: string;
  rooms: number;
  seed: number;
  vertices: number;
  polygons: number;
  materials: number;
  glb_url: string;
  zone_url: string;
  map_url: string;             // top-down SVG layout map
  source: string;              // "prompt" | "controls"
  planner?: string | null;     // "rule" | "llm"
  plan?: ZonePlan | null;
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

export async function fetchSidecar(url: string): Promise<ZoneSidecar> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`sidecar fetch failed (${res.status})`);
  return res.json();
}
