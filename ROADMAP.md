# Roadmap & Open Items

The authoritative list of what's done, what's next, and known gaps. The README
carries the narrative "what it does / how it works"; this file is the tracker.
Keep it in sync when work lands (check items off, move them, note the commit).

Last updated: M0 (hygiene + PBT harness) landed and passed its human pass.
The ordered plan now lives in the umbrella spec's Delivery plan
(`.kiro/specs/zone-generator/design.md`), milestones M1–M6.

---

## ▶ Pick up here (next session)

**M0 — hygiene + PBT harness is DONE** (merge `b0d412f`, 98 branch commits
since `99d346a`; human pass complete). It added a Hypothesis property suite,
deleted the broken cave pipeline and the `cave` theme, removed the legacy Flask
viewer, bound the server to loopback with explicit CORS, and fixed the
elevation grade-cap bug the properties found. The human pass also turned up an
unsound traversability gate (fixed), and added room-id labels and a stale-code
banner to the viewer. Suite: 249 passed at the branch tip.

**Planning moved to Kiro specs.** The umbrella spec `.kiro/specs/zone-generator/`
(requirements + design) describes the target system, and its Delivery plan
orders the work as milestones M0–M6. Each milestone gets its own spec,
`.kiro/specs/zone-generator-mN-<name>/`, which owns its `tasks.md`. The `tasks/`
board is now history; new work doesn't go there. "Next" below is kept for its
detail, but the Delivery plan is the ordering.

**M1 wave 1 — large-zone connectivity is DONE** (merge `c63f056` into master).
The walk surface is faster (union-find, equivalence-proven), all corridors route
through one function, the validator now checks corridor floor-continuity and
corridor-corridor conflicts, and flat + elevation connectivity is proven through
30 rooms with both human 3D passes signed off. One-time M1 seed break recorded
(Decision 13): 765 of 1200 flat builds moved; pre-M1 pinned seeds are not
expected to reproduce. Budget flag carried to wave 3: the suite is ~+140 s over
the +120 s ceiling and the only effective lever (wilderness budgets) lands in
wave 3. A parked backlog note (intersecting corridors on the elevated path, seed
105770060) is in the M1 spec tasks.md — not blocking, possibly a feature.

**M1 wave 2 — zone-type rename is DONE** (merge `43e00f6` into master, 12 branch commits since `5705ce4`). `theme` -> `zone_type` and `outdoor` -> `wilderness` across plan/planner/`generators/zone_types.py`/spec/layout/builder/pipeline/sidecar/server/CLI/web. Legacy load boundaries retained (saved `theme`/`outdoor` still load and map forward); Property 12 (M1-P3) pins the round-trip; all 35 fork-point TER hashes matched, so the rename moved no geometry (Decision 13 invariant holds). Suite 259 passed; frontend builds.

**M1 wave 3 — backend registry is DONE; wilderness terrain DESCOPED** (merge `fbadf63` into master). The `GeometryBackend` registry (task 12) landed: `generators/backends.py` with `BoxBackend`/`TerrainBackend`, `ZoneBuilder` routed through `backend_for(zone_type)` with a box fallback, no cave backend. The wave-3 wilderness TERRAIN work (room-graph drape: pads + graded corridor paths, tasks 13.x) was **REJECTED and abandoned** — wilderness must be an open scenic landscape, not a room-graph in a grass skin. **Wilderness ships in M1 present-but-DISABLED** (`ENABLED_ZONE_TYPES = {dungeon, city}`). The real open-world wilderness generator is its own milestone (see below). Suite 261 passed; the suite now runs in parallel (pytest-xdist, ~2.5 min).

**M1 wave 4 — all-zone-type gate + availability is DONE** (merge `8aecc96` into master). One Enabled set (`ENABLED_ZONE_TYPES = {dungeon, city}`; wilderness DISABLED/deferred) with an availability listing; sidecar on every build; rebuilt `generate_validated` with scratch attempt dirs + the reachability+continuity+format-stub gate + atomic move-on-pass / cleanup-on-fail-and-exception; server gating (disabled-type 400 before any write, prompt-planned disabled type substituted to dungeon with a warning + `planned_zone_type` in the sidecar) and per-build versioned `/api/zones/{zone_id}/{version}/{filename}` paths with traversal guards; Properties 2 and 7. Two root bugs the property tests caught were fixed at root (empty `.attempts/` root left behind; prompt path not canonicalizing the planned zone type). Suite 271 passed. The city 3D pass (16.2) is pending human sign-off.

**Pick up here: M1 wave 5 — modes, `from_controls` and geometry-slice controls** (`.kiro/specs/zone-generator-m1-controls-traversability/tasks.md`, tasks 17.x–18.x, then wave 6): explicit prompt-vs-controls `mode`, `ZonePlan.from_controls`, the geometry-slice CLI/web controls and two Generate actions; then wave 6 (build naming + `rof2check` format gate + file-system confinement). Dungeon + city only; wilderness stays DISABLED. Fork the wave-5 worktree (`agent/m1-modes`) from this updated master.

**Milestone ordering (open-world wilderness is sequenced, not lost):** **M1** (dungeon + city; wilderness disabled) → **`zone-generator-followup`** runway (pluggable `LayoutEngine` seam F1, 3D `Envelope` + typed edges F2, gate-learns-connectors F4) → **`zone-generator-wilderness`** (the open-world landmark-first generator: biome-as-texture, 2D design-matrix IR, graph-replacement, hydrology/erosion, intent-driven `playable`/`scenic` reachability). The wilderness spec (requirements + design + tasks) is COMPLETE at `.kiro/specs/zone-generator-wilderness/` and must not start until M1 and the followup runway land.

**Suggested next step: M1 — Controls + all-theme traversability + format gate**
(pillars P-A, P-B and P-C Tier 1). Stand up `.kiro/specs/zone-generator-m1-*`
first, and carry these into its scope:
- **Large-zone connectivity.** The build-level navigability properties only
  draw 2–12 rooms; the disconnected corridors reported in the M0 pass were all
  on 30-room dungeons. Raise the range, and add a corridor-floor continuity
  property (every corridor floor runs unbroken from opening to opening). The
  gate checks that every room is reachable, not that every corridor lands.
- **Flat first, then elevation** (user decision). Prove flat dungeons connected,
  then harden elevation ramps on top. Add a flat / no-elevation toggle to the
  controls.
- **Angled corridors** are wanted, but they change the umbrella's axis-aligned
  routing requirement. Do them as an umbrella amendment once flat connectivity
  is green, not inside the fix.

**Restart the server after pulling.** It runs without auto-reload and keeps
serving the code it started with. The side panel shows `server <hash> · web
<hash>` and a banner when the server is stale or the frontend build doesn't
match.

**Validate major changes** with the acceptance checklist in
[`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md). Proc-gen approach investigations and
their verdicts are in [`docs/RESEARCH.md`](docs/RESEARCH.md).

---

## Done

| Area | Summary |
|------|---------|
| Analyzer (Phase 0) | Extract style metrics from a RoF2 install; profiles in `styles/` |
| Core I/O (Phase 1) | PFS read/write (EQ big-endian CRC), TER/ZON serialisers, EQG assembler |
| WLD reader | Classic–PoP `.s3d`/WLD geometry reader (0x36 meshes) |
| Inspector (Phase 1b) | Rich terminal metrics + zone comparison |
| Geometry (Phase 2) | Box rooms/corridors; inward walls; planar UVs |
| Elevation (Phase 2.5) | Multi-level layout; ramp & staircase corridors |
| Web app | FastAPI + Vite/Three.js; generate + first-person walk + overlays + seed input (reproduce a zone) |
| ~~Organic caves~~ | Removed in M0 (rendered as disconnected blobs). Caves return as a dungeon archetype (M3) and the natural geometry style (M5) |
| ~~Walkable floors + features~~ | Cave-only; removed in M0 with the cave pipeline (lessons kept in steering for M5) |
| Outdoor terrain | Heightfield + erosion; walkable rolling hills |
| Textures | Procedural seamless (no API) + AI provider drop-in |
| Prompt planning (Phase 3) | Rule planner (no API) + LLM drop-in; expand → ZoneSpec |
| Classic–PoP profiles | Analyzer reads s3d/WLD; profiles from Guk/Sebilis/Faydark… |
| Theme-accurate scale | Room size from measured per-theme floor_area |
| TinyKeep layout | Scatter → separate → Delaunay → MST + loops → graph elevation |
| Pacing | Graph-derived roles (entrance/hub/climax/deadend) + depth; biased geometry & lighting |
| Gating | Optional lock-and-key suggestions, solvability-guaranteed |
| Top-down map | SVG floor-plan sidecar + web modal |
| Corridor connection fix | Z/L/straight routing meets both wall openings flush; elevation grade-capped and carried by subdivided (walkable) ramps |
| ~~Cave connectivity fix~~ | Removed in M0 with the cave pipeline |
| Acceptance checklist | `docs/ACCEPTANCE.md` — manual UAT for validating major changes |
| Content layer — Step 1 | Dungeon semantic themes: archetype × race × tint; per-room type, shape/region/light/palette realization; props/encounter/boss as suggestions; surfaced in viewer panel + top-down map |
| M0 — Hygiene + PBT harness | Hypothesis property suite (P1–P16 + CORS; `slow` marker; derandomised default and 5× `thorough` profiles); cave pipeline, `cave` theme and legacy Flask viewer deleted; loopback bind + explicit CORS; elevation grade-cap root-cause fix; agents and steering re-pointed at spec `tasks.md`. Merge `b0d412f` |
| Traversability gate soundness | `analyzer/traverse` connects floor faces only on true triangle contact at matching floor height; bounding-box overlap + centroid Z had bridged real gaps |
| Viewer room-id labels | `room_N` floats over each room in 3D and is printed in each map box, so a reported room can be named |
| Build identity | `/api/version`; side panel shows server and web build commits with a stale-code banner; generate responses carry `build_commit` |
| M1 wave 1 — large-zone connectivity | Faster walk surface (union-find; 6-room validate 118 s to <1 s, equivalence proven vs a frozen fork-point reference); all corridors routed through one function (`generators/routing.py`, byte-identical over 32 TER captures); corridor floor-continuity + corridor-corridor conflict checks in the validator; flat AND elevation connectivity proven through 30 rooms; both 3D passes signed off. Merge `c63f056` |
| M1 wave 2 — zone-type rename | `theme`->`zone_type`, `outdoor`->`wilderness` across plan/planner/spec/layout/builder/pipeline/sidecar/server/CLI/web; legacy load boundaries retained; Property 12 pins the round-trip; 35/35 fork-point TER hashes unchanged (no geometry moved); suite 259. Merge `43e00f6` |
| M1 wave 3 — backend registry | `GeometryBackend` protocol + Box/Terrain backends + `BACKENDS` registry; `ZoneBuilder` routed through `backend_for` with box fallback; no cave backend. Wilderness terrain-drape work REJECTED/abandoned; wilderness ships DISABLED. Open-world wilderness moved to its own milestone. Suite 261. Merge `fbadf63` |
| M1 wave 4 — gate + availability | One Enabled set (dungeon+city; wilderness disabled) + listing; sidecar on every build; `generate_validated` scratch-attempt gate (reachability+continuity+format) with atomic move/cleanup; server gating + per-build versioned `/api/zones` paths; Properties 2 & 7; two property-caught root bugs fixed. Suite 271. Merge `8aecc96` |

---

## Next — ordered priorities

> **Superseded by the umbrella Delivery plan** (`.kiro/specs/zone-generator/design.md`).
> There, districts (content Step 2) are M3, iterative refinement is M4 and the
> SQL export is M6, with M1 (controls + traversability + format gate) and M2
> (true-layout artifacts) first. The items below are kept for their detail.

Rationale for this order: the north-star is "indistinguishable from hand-crafted"
with the layout as a starting point for a manual pass. Making rooms *theme-coherent*
moves that needle most; iterative refinement is usability polish worth doing once
there's richer output to iterate on; the SQL export is the "now make it playable"
capstone that consumes the content layer's suggestion data. Manual validation
passes (`docs/ACCEPTANCE.md`) are good enough to vet designs until then, so the
export sits last.

### 1. Content / semantic layer — theme-conforming rooms + suggestions

Give each room a semantic **type + theme**, assigned coherently across the graph
so the zone reads as a place with a progression. Scope is **no new art**. Design,
theme vocabulary, and the archetype × race × tint + districts model are in
`docs/RESEARCH.md` ("Content / semantic layer — dungeon theme vocabulary &
districts"). Split into two steps:

- [x] **Step 1 — single-district themes (DONE).** A room gets a semantic type
  from a zone **archetype** (fortress / war_city / warren / temple / tomb /
  wizard_lair / corrupted_sanctum / mine_delve / sunken_ruin / lava_forge /
  ice_keep), scaled by an inhabiting **race** (global size multiplier) with an
  optional elemental **tint** (lava/ice/water). Realized into geometry — shape /
  proportion bias, `AWT_`/`ALV_` region volumes, lighting mood, elevation
  character, per-theme palette (material variants). Props / encounter intent /
  boss are carried as **suggestions** (RoomSpec fields → sidecar + map + viewer,
  for the eventual SQL export). The rule planner detects archetype/race/tint
  keywords; the LLM planner can propose them (schema extended). Code:
  `generators/semantics.py`, wired into `generators/layout.py::generate`.
  *Known gap: race scale values are relative placeholders pending real EQ model
  dimensions (see Known issues).*
- [ ] **Step 2 — districts (NEXT).** Partition the room graph into 1–3
  contiguous **districts**, each its own sub-theme, joined at hubs / gated
  thresholds — so a zone can be several places at once (live vs. dead side,
  fortress + warren). Auto-split large zones (≥8 → 2, ≥14 → 3) with an off
  switch; **per-district climaxes** (multiple boss rooms allowed); a district
  **relationship** tag (sequential / factional / abandoned-vs-active). Renders
  district boundaries on the map/viewer. `RoomSpec.district` exists as a
  placeholder; a `ZoneSpec.districts` list does not exist yet (it arrives with
  the district work in M3).

- **Explicitly NOT doing:** placing prop MODs. A room *is* a theme-conforming
  empty space with written suggestions, not furnished geometry.

### 2. Iterative refinement

Worth building once there's content-rich output to refine.

- [ ] **Iterative chat loop** — refine an existing zone with follow-up prompts
      ("make the entrance wider", "add a water pool to the north") instead of
      regenerating from scratch. Needs: a session/zone-state concept server-side,
      a diff-style prompt interpretation, and a way to carry the seed/spec forward.
- [ ] **Partial regeneration** — re-run only changed rooms/textures, not the whole
      zone, so iteration is fast.

### 3. EQEmu SQL export (capstone — makes a zone playable)

- [ ] Zone records, spawn points, and door/key rows. A `GateSpec` maps to a
      `doors` row (`lock_x/y/z` → position, `corridor_id` → the opening, key →
      `keyitem`); the content layer's spawn/encounter suggestions become spawn
      and loot rows. Deferred to last: empty shells aren't worth standing up on a
      server, and manual validation covers design checks until then. This is also
      where to add a real **in-engine validation loop** (load one generated zone
      on an EQEmu server) so quality isn't judged only by our own reader/viewer.

---

## Design work captured, not yet built

(Opportunistic — slot in around the ordered priorities above. Normal maps in
particular are a cheap, high-impact quick win.)

- [x] **Traversability validator** — ✅ **Done (dungeon/box backend).** An
      automated check that a player can walk to every room, run on the generated
      TER mesh (not the room graph), with an EQ-scale agent (walkable slope cap
      40°, max step-up 3u). Walks the actual triangles from the safe point and
      reports per-room reachability + *why* (cliff ramp / oversized stair step /
      misaligned corridor). CLI: `python -m analyzer.traverse output/<zone>.eqg`;
      suite: `tests/test_traversability.py` (sweeps known-good flat seeds plus
      the formerly-broken elevation seeds, which now walk 9/9 after
      `corridor-connection` landed). It's the objective gate those fixes pass.
      Code in
      `analyzer/traverse.py`. *Known limit: outdoor not swept — its heightfield
      mesh is generated in a different coordinate frame than the room graph
      (terrain starts at origin going +X/+Y rather than centred on the rooms), so
      room-footprint mapping isn't meaningful for it yet. Logged in Known
      issues.* *M0 correction: the adjacency test was unsound (bounding-box
      overlap + centroid Z bridged real gaps), so earlier "walks 9/9" results
      were optimistic. It now requires true triangle contact at matching floor
      height, and the suite re-ran green.* Tracked as
      `tasks/traversability-validator.md`.
- [x] **Validator gates the pipeline** — ✅ **Done (dungeon/box backend).** The
      validator now runs in the hot path, not just on demand: a shared
      `generators.pipeline.generate_validated(...)` helper builds → validates →
      **retries on a fresh seed** (bounded by an attempt cap *and* a wall-clock
      timeout) and returns the first passing zone, or raises `GenerationFailed`.
      Both `/api/generate` and `main.py generate` call it, so a validator-failing
      dungeon never reaches a client — on exhaustion the server returns a clean
      503 instead of a broken GLB. Every rejected attempt is appended to
      `output/validation_failures.jsonl` (seed + theme + per-room reasons) as the
      triage feed for `corridor-connection`. Gating is dungeon-only for now;
      city and outdoor pass through **ungated** (gating them is M1; outdoor's
      coordinate-frame mismatch would false-fail every zone — see Known issues).
      A pinned seed that fails errors out (never a
      silent seed swap); `main.py generate --no-validate` bypasses the gate for
      debugging broken seeds. Tracked as `tasks/validate-in-pipeline.md`.
- [ ] **Multi-level / stacked-floor dungeons** — today's box layout is 2.5D:
      rooms scatter + separate on XY only (so one can never sit directly above
      another) and elevation is just a per-room `floor_z` nudge on a planar
      graph, with every corridor a horizontal run + ramp/stairs. Add true
      stacked floors — rooms above/below each other joined by vertical
      connectors (stairwells/shafts) — behind a "levels" control, so a zone can
      be a tower or a deep vertical dungeon. Follows `corridor-connection`
      (vertical connectors reuse its stair helper) and is gated by the
      traversability validator. Becomes the follow-on spec `multi-level-dungeon`
      after M3 (umbrella design, "Scope of open task files"); scoping lives in
      `tasks/multi-level-dungeon.md` until then.
- [x] **Cave rebuild — "cavify the dungeon layout"** — superseded. M0 deleted the
      broken cave pipeline and the `cave` theme outright. Caves return as a
      dungeon archetype built by the box backend (umbrella M3) and as the
      optional natural geometry style that reshapes a validated box layout (M5).
      `tasks/cave-backend-refactor.md` is absorbed by M0 and
      `tasks/cave-cavify-dungeon.md` by M5.
- [ ] **Doorway-fit for gates** — catalogue the RoF2 door models used for doorways
      and their world-space footprints by theme (swinging wood/stone, portcullis,
      double doors, archway frames), then snap gated corridor openings to a chosen
      door type and record the model name on `GateSpec`. Prerequisite for a
      meaningful door export. (See README "Doors are records, not geometry".)
- [ ] **Water & mixed-environment zones**
  - [ ] Outdoor + water: a water plane at fixed Z, terrain sloped beneath it for a
        shoreline/lakebed, and an `AWT_` region so the client treats it as swimmable.
        Terrain backend needs a "water level" + shoreline shaping.
  - [ ] Cave-mouth-in-hillside: compose a cave with heightfield terrain in one
        TER. The SDF cave backend this relied on was removed in M0; revisit once
        the M5 natural geometry style exists.
- [ ] **Outdoor rooms as real places** — outdoor "rooms" currently only set terrain
      bounds; make them clearings, lookouts, etc.
- [ ] **Procedural normal maps** — textures are diffuse-only; real zones use the
      `e_TextureNormal0` material slot. No-API, high visual impact. Scheduled
      in umbrella M3.
- [ ] **Doorway-fit** also gates a real door export (listed above); it depends on
      the catalogue of RoF2 door models.

---

## Known issues / smaller fixes

- [x] **Cave theme broken in 3D despite passing tests** — resolved by removal:
      M0 deleted the cave pipeline and the `cave` theme, and cave prompts now
      build a `dungeon`. The lesson stands: automated structural checks can pass
      while the viewer shows something wrong, so validate major geometry changes
      in 3D per `docs/ACCEPTANCE.md`.
- [x] **Corridors between same-axis room pairs mis-connect, esp. with elevation**
      — ✅ **Fixed.** When two rooms faced each other on parallel walls (both
      E↔W or both N↔S — the common case), the single-corner L-bend forced one
      leg parallel to a wall and met the opening at the wrong XY/floor height,
      leaving a gap (seeds 1955208177, 1516796975, 678358326). `add_corridor`
      now routes a 3-segment **Z-corridor** for same-axis pairs (perpendicular
      stub → cross-jog → perpendicular stub), keeps the L-bend for genuine
      cross-axis pairs and a straight leg for collinear openings, all through one
      `_emit_route` helper. Elevation is now bounded by corridor run (grade cap
      0.5 ≈ 26.6°, with loop-edge relaxation) and carried by **subdivided ramps**
      so the per-triangle traversability agent (step-up ~3u) can climb them — a
      single-quad ramp read as a cliff regardless of slope. `analyzer.traverse`
      passes 9/9 on the reported seeds and across a 160-zone + 100-themed sweep
      (measured with the gate later found unsound; the suite re-ran green after
      the M0 fix). Delivered by `tasks/corridor-connection.md`.
- [ ] **Outdoor mesh vs room graph are in different coordinate frames** —
      surfaced while building the traversability validator. The heightfield
      terrain mesh places vertices at `x = i*res` (origin → +X/+Y), while the
      room graph is centred near the origin (negative coords common), so the
      terrain isn't actually under its rooms. Consequence: the validator can't
      map room footprints onto that mesh, so outdoor navigability stays manual
      for now. Fix direction (umbrella M1): offset/centre the terrain mesh onto
      the room-graph frame so
      world positions agree. (`generators/field/terrain.py::_heightfield_to_ter`.)
- [ ] **Race scale values are relative placeholders** — the content layer's
      per-race size multipliers (`giant` 2.2×, `froglok` 0.9×, …, in
      `generators/semantics.py::RACE_SCALE`) are tuned-by-feel, not measured.
      Real per-race limits (doorway clearance, headroom) should come from EQ
      model bounding boxes, which we don't have yet; the RoF2 install at
      `F:\everquest_rof2` could be mined for model bounds the way the
      era-fidelity triangle-edge table was. Until then they're a tunable knob.
- [ ] Style profiles for `city` and `cave` are thin (3–4 zones) — expand once more
      zone names are identified.
- [ ] Light-density stat reads 0 in profiles (most dungeon references use embedded
      MOD placement without ZON lights). Accurate, not a bug — but worth a note so
      it isn't "fixed" by mistake.
- [ ] Inspector ASCII bbox diagram doesn't render Z height — add a side-elevation view.
- [ ] Outdoor terrain is just the ground surface — no cliff walls, boulders, or
      vegetation yet.
- [ ] Web bundle is a single ~570 kB chunk (Vite warns > 500 kB). Cosmetic; could
      code-split Three.js if it ever matters.
- [ ] **Build-level properties don't cover large zones** — the navigability,
      ramp and determinism properties draw 2–12 rooms, but users generate up to
      30. The disconnected-corridor reports in the M0 pass were all on 30-room
      zones (they cleared after a server restart). Raise the range and add a
      corridor-floor continuity property in M1.
- [ ] **Server doesn't auto-reload** — `python -m server.app` runs with
      `reload=False`, so it serves the code it started with. Restart after
      pulling or editing. The viewer shows the server and web commits and a
      stale-code banner (`/api/version`).
- [ ] **Elevation-on overwrites the semantic sink/raise** — with elevation on,
      `_assign_elevation` re-derives every `floor_z` and discards the content
      layer's `sink` bias (M0 fixed only the elevation-off path). Content-layer
      follow-up.
- [ ] **Procedural texture seeds use salted `hash()`** —
      `generators/textures/procedural._seed_from` isn't stable across processes
      (PYTHONHASHSEED), so textures aren't reproducible run to run. The
      determinism properties compare TER/ZON only for this reason.
- [ ] **Shared Python env drifts from the pins** — the global interpreter had
      `fastapi 0.143.1` / `starlette 1.8.0` instead of the pinned `0.115.6` /
      `0.41.3`, and lacked `hypothesis` / `httpx`. The CORS override depends on
      starlette internals, so run `pip install -r requirements.txt`.

---

## Deliberately NOT doing (and why)

Recording these so they aren't re-proposed:

- **Cave mesh decimation** — quadric decimation collapses the flat walkable floor
  into a few steep triangles. Poly count is controlled via `voxel` size instead.
  (Kept as guidance for the M5 natural style; the cave mesh was removed in M0.)
- **Multi-key gating models (fragments / master key)** — the requested case was
  *independent* locks, which the N-separate-gates model already covers.
- **Baking doors into the `.ter`** — a door welded into the mesh is a door-shaped
  wall that can't open. Doors are runtime records (EQEmu `doors` table), produced
  by the SQL export, dropped into the open corridor gap.
- **Full Dormans mission-graph grammar** — EQ gates by depth/danger, not Zelda-style
  lock chains. We adopted only the solvability-invariant idea for gating.
- **Grid + rule-tile rooms (Labyrinth "Blueprints")** — grid-snapped rooms whose
  shape is chosen from the neighbour pattern read as modern roguelike (Isaac /
  Gungeon), the opposite of hand-crafted EQ sprawl. We already use the stronger
  non-grid choices (TinyKeep over Drunkard's-Walk+A\*). See `docs/RESEARCH.md`.

---

## Phase status

| Phase | Description | Status |
|-------|-------------|--------|
| **0** | Zone analyzer — extract style profiles from RoF2 install | ✅ Done |
| **1** | Core I/O — PFS reader/writer, TER/ZON binary serialisers | ✅ Done |
| **1b** | Zone inspector — rich terminal metrics + profile comparison | ✅ Done |
| **2** | Procedural geometry — rooms, corridors, lighting, regions | ✅ Done |
| **2.5** | Elevation — multi-level layout, ramp & staircase corridors | ✅ Done |
| **web** | Browser app — dropdown generate + first-person walk + overlays | ✅ Done |
| **organic** | Cave geometry — SDF + marching cubes | ✗ Removed in M0 (caves return as an M3 archetype + M5 natural style) |
| **organic+** | Walkable floors + natural features (stalactites/pillars) | ✗ Removed in M0 with the cave pipeline |
| **terrain** | Outdoor heightfield terrain — eroded, walkable rolling hills | ✅ Done |
| **textures** | Procedural seamless textures (no API) + AI provider drop-in | ✅ Done |
| **3** | Prompt-driven generation — rule planner (no API) + LLM drop-in | ✅ Done |
| **layout** | TinyKeep room-graph — scatter/separate/Delaunay/MST + loops | ✅ Done |
| **pacing** | Room roles & depth — entrance/hub/dead-end/climax, biased geometry & lighting | ✅ Done |
| **gating** | Lock-and-key suggestions (optional, keyed dungeons), solvability-guaranteed | ✅ Done |
| **content** | Theme-conforming rooms + suggestions (no prop placement) | ◑ Step 1 done; Step 2 (districts) → umbrella M3 |
| **refine** | Iterative chat loop + partial regeneration | ⏳ umbrella M4 |
| **export** | EQEmu SQL export + in-engine validation (capstone) | ⏳ umbrella M6 |
| **M0** | Hygiene + PBT harness — the first umbrella milestone; later work is M1–M6 | ✅ Done |

---

## Completed-work detail

Narrative record of what each area delivered and the decisions baked into it.

### Phase 0 — Zone analyzer

Reads any `.eqg`/`.s3d` zone from a RoF2 install and extracts measurable style
metrics: bounding dimensions, polygon density, material/shader counts, light
density, region-type distribution, and whole-zone floor area. Profiles are built
from authentic **Classic–PoP** zones (the default target era), read via the WLD
reader, and stored in `styles/`.

| Theme | Reference zones | Ceiling (mean) | Edge median | Materials |
|-------|-----------------|----------------|-------------|-----------|
| `dungeon` | Befallen, Sol A/B, Najena, Sebilis, Chardok, Velketor, Paw, Guk | 303 u | **12.4 u** | 102 |
| `outdoor` | Greater Faydark, Karanas, Oasis, Feerrott, Burning Woods, E. Wastes | 1103 u | 75 u (wide) | 52 |
| `city` | Qeynos, Freeport, Felwithe, Rivervale, Cabilis, Neriak | 403 u | **11.2 u** | 117 |
| `cave` | Crushbone, Blackburrow, Runnyeye, Cazic-Thule, Kedge, Guk, Warrens | 474 u | **14.1 u** | 116 |

Interior themes cluster at ~11–14 u median triangle edge — the authentic
Classic–PoP resolution the generator targets (cave default `voxel=12` ≈ 12 u).

**Theme-accurate scale.** Profiles also record whole-zone footprint: outdoor
zones average **~94M u²** of floor vs **~2M u²** indoor — roughly **40× larger**.
`LayoutGenerator` derives room size from each theme's measured `floor_area`
divided across room count, so outdoor zones are correctly vast and dungeons
correctly tight. Ceiling heights track the measured per-theme means.

### Phase 1 — Core I/O

- **`core/pfs.py`** — full PFS read/write. EQ big-endian CRC32 (`poly
  0x04C11DB7`, null-terminated, case-sensitive; ref `EQEmu/zone-utilities
  src/common/pfs_crc.cpp`). Multi-chunk deflate (RoF2 name blocks 35KB+).
  Validated: 1340/1340 filenames resolve in `broodlands.eqg`.
- **`core/ter.py`** — TER/MOD terrain serialiser (`EQGT`); materials, v2/v3
  vertices, polygon flags.
- **`core/zon.py`** — ZON placement serialiser (`EQGZ`); models, object
  instances (EQ heading unit conversion), region volumes, point lights.
- **`core/eqg.py`** — high-level assembler: TER + ZON + DDS → `.eqg`, plus GLB
  export for browser preview.
- **`core/wld.py`** — Classic–PoP `.s3d`/WLD geometry reader (0x36 meshes).

### Phase 1b — Zone inspector

`analyzer/inspect.py` — rich terminal metrics vs. the style profile (geometry
table, per-metric ✓/⚠ vs profile range, materials, lights/regions, texture list,
ASCII bbox diagram) and a side-by-side `--compare` of two zones. Metric fixes:
UV scale uses median of 99th-pct-clipped values; ZON search tries any `.zon`;
`has_zon` flag added (many RoF2 dungeons use embedded MOD placement).

### Phase 2 / 2.5 — Procedural geometry + elevation

Box backend: hollow rooms + corridors with inward-facing walls, planar UVs,
material resolution. Elevation is a generator feature (EQG collision is
per-triangle via the `0x01` flag — confirmed in `azone/map.cpp::CompileEQG` —
no BSP needed). Corridors ramp between differing floor heights. Routing picks a
**straight** leg for collinear openings, a 3-segment **Z-corridor** when the two
rooms face each other on parallel walls (the common case), or an **L-bend** for
a genuine cross-axis pair — meeting both openings flush at each room's floor.
Elevation grade is capped to a walkable slope and the ramp mesh is subdivided so
it's climbable by the traversability agent.

### Organic caves + features (removed in M0)

*Historical. M0 deleted this backend because it rendered as disconnected
blobs in 3D despite passing tests. Its hard-won facts are kept in
`.kiro/steering/lessons-learned.md` as guidance for the M5 natural style.*

The `cave` theme used a density-field backend: solid rock → carve chambers
(irregular multi-lobe blobs) and tunnels (winding capsule chains) → FBM wall
noise → marching cubes → single watertight mesh. Floors stay walkable
(flat-bottomed domes, floor-tapered one-sided noise, re-intersected with the
floor plane after blending). Features (stalactites/stalagmites/pillars) grow
into the field before meshing so they fuse with the rock. Noise is fully
vectorised numpy (~27s → ~1s); features use localized SDFs (97s → 8s big caves).

### Outdoor terrain

`outdoor` theme: FBM hills → thermal erosion → walkable-gradient cap (≈100%
under 40°) → triangulated ground mesh with gradient normals.

### Textures

Provider abstraction: `ProceduralProvider` (default, no API — layered tileable
value noise, seamless, ~20ms) and `AIProvider` (optional, OpenAI/Stability, falls
back to procedural on any failure). Factory auto-selects, caches, honours
`EQ_S3D_TEXTURE_PROVIDER`. Diffuse-only for now (normal maps are a known gap).

### Web app

FastAPI backend (`server/app.py`, fresh random seed per call unless a seed is
pinned, serves GLB + `.zone.json` sidecar + front-end). Vite/TS/Three.js
first-person viewer (`web/`): WASD at EQ scale, pointer-lock look, a seed input
(blank = random, a number pins the zone) with a "⟳ reproduce" button,
toggleable overlays (wire/lights/regions/gates), top-down SVG map modal, live
metrics panel. Single-command dev launcher (`web/dev.mjs`). Seeds reproduce
deterministically across all themes — geometry is seeded from the user seed
(carried on `ZoneSpec.seed`), not a hash of the timestamped zone name. Since
M0 the server binds `127.0.0.1` with an explicit CORS origin list, the legacy
Flask viewer and `main.py preview` are gone, rooms show `room_N` labels in 3D
and on the map, and the side panel shows the server and web build commits
with a warning when either is stale.

### Prompt-driven generation

`RulePlanner` (default, keyword/heuristic, no API) and `LLMPlanner` (optional,
OpenAI/Anthropic, JSON output grounded in style profiles, falls back to rule).
`expand.plan_to_spec` drives the same `LayoutGenerator` the dropdowns use.

### Layout + pacing + gating

TinyKeep spatial layout (scatter → separate → Delaunay → MST + ~12% loop edges →
graph elevation → wall-to-wall corridors). Pacing analyses the graph for roles
(entrance/hub/climax/deadend) and depth, biasing geometry and lighting so the
progression is visible. Gating optionally places lock-and-key *suggestions* on
deep tree edges with keys reachable earlier (solvability guaranteed). Pacing and
gating ride in the sidecar — advisory metadata, never baked into geometry.

### M0 — Hygiene + PBT harness

Spec: `.kiro/specs/zone-generator-m0-hygiene/`. A Hypothesis property suite
(`tests/test_properties_*.py`, shared `strategies.py` / `pbt_helpers.py`; the
default profile is derandomised so runs repeat, and `--hypothesis-profile=thorough`
runs 5× the examples randomised) pins the invariants the generator relies on:
PFS and TER/ZON round-trips, layout connectivity and gating solvability, the
elevation grade cap, flush openings, ramp subdivision, seed determinism, the
validation gate's behaviour and the no-API defaults. Two root-cause fixes came
out of it: the elevation relax pass now also runs on themed dungeons with
elevation off, and the relax fixpoint converges tightly enough that loop edges
stay under the grade cap. One format limit was accepted: PFS keys files by a
32-bit CRC, so two names with the same CRC can't share an archive; real zones
use a fixed set of names, so the round-trip property excludes colliding sets.
The human pass found the traversability gate's adjacency test was unsound. It
was fixed, and room-id labels and a stale-code banner were added to the viewer.

---

## Design notes & rationale

### Geometric fidelity by era

Generated geometry should sit at the resolution the original artists worked at —
not smoother (reads too modern) nor coarser. Key metric: **median triangle edge
length** (world units), measured from real zones. Format boundary is **Gates of
Discord (2003)**: Classic → PoP ship as `.s3d`/WLD; GoD onward as `.eqg`.

| Era | Format | Median edge (u) | Median polys |
|-----|--------|-----------------|--------------|
| Classic (1999) | s3d | **13.1** | 22.6k |
| Kunark (2000) | s3d | **14.1** | 39.3k |
| Velious (2000) | s3d | 49.3 (big open zones) | 41.6k |
| Luclin (2001) | s3d | 8.0 (finer architecture) | 57.8k |
| PoP (2002) | s3d | **12.2** | 105k |
| GoD/OoW (2003–4) | eqg | 13.2 | 166k |
| DoN/DoDH (2005) | eqg | 5.8 | 148k |
| TBS/SoF (2007) | eqg | 15.8 | 50k |
| SoD/UF (2008–9) | eqg | 18.4 | 61k |
| HoT/VoA (2010–11) | eqg | 20.4 | 213k |
| RoF (2012) | eqg | 5.8 | 71k |

The iconic Classic/Kunark/PoP look clusters at ~12–14u median edge — the default
target (`voxel=12` ≈ 12u, confirmed). Fidelity didn't evolve monotonically; it
oscillated with art teams, tools, and zone type.

### Room-graph composition (TinyKeep + pacing + gating)

The room-graph is the zone's abstract floor-plan (rooms = nodes, corridors =
edges) that every backend realises into 3D. The naive random walk was replaced
with the TinyKeep spatial layout above, fixing overlap/tangle/linearity. Pacing
assigns roles + depth; gating adds optional lock-and-key suggestions. All three
geometry backends consume the layout unchanged.

### Doors are records, not geometry — openings must fit a door model

A functional EQ door is a separate record (EQEmu `doors` table) referencing an
animated door model, with position/heading/open-type/`keyitem`; the server drives
open-close and gatekeeping. Expected to be consistent across EQG and classic
s3d/WLD (both feed the EQEmu door system); the per-format door-model lookup needs
verifying against our readers before writing the export.

- **Never bake a door into the `.ter`** — it becomes a door-shaped wall that
  can't open. Corridors stay open gaps; a `GateSpec` becomes a real door only in
  the SQL export (`lock_x/y/z` → position, `corridor_id` → opening, key →
  `keyitem`).
- **The opening is the constraint** — a gated corridor's width/height must fit a
  standard EQ door. Follow-up: catalogue RoF2 doorway models + footprints by
  theme, then snap gated openings to a chosen door type and record its model name
  on the `GateSpec`.

### Cave = cavified dungeon layout (superseded in M0)

*Superseded: M0 deleted the cave pipeline. The idea below lives on in the
umbrella spec as the `cave` dungeon archetype (M3) and the natural geometry
style (M5), which reshapes a validated box layout under the same gate.*

The current cave backend re-derives its own spatial structure (chambers from
rooms, tunnels from corridors, with fragile endpoint-matching), and it keeps
rendering as disconnected blobs in 3D even though the connectivity tests pass —
the tests and the rendered result disagree, which means the backend is building
geometry our analysis doesn't faithfully capture. Rather than keep patching it,
the plan is to **rebuild the cave as a transform of the dungeon layout**:

1. Generate the layout with the **box/dungeon backend**, which already produces a
   correct, connected, navigable set of rooms + corridors that meet their
   openings. This is the single source of truth for connectivity.
2. **"Cavify"** that known-good geometry as a post-process: round box rooms into
   organic chambers, convert corridors into winding tunnels, roughen with noise —
   while preserving the connectivity that already works.

Connectivity is thus established once, in the backend that gets it right; the
cave becomes a styling pass over validated geometry instead of an independent
re-derivation. This should eliminate the disconnected-chamber class of bug by
construction. Open design question: whether to cavify at the mesh level (deform
the box mesh) or re-voxelise the box layout into an SDF and re-mesh — the latter
is closer to what we have and composes with the terrain-as-SDF idea below.

The `cave` theme no longer exists; cave prompts build a `dungeon`.

### Water and mixed-environment zones

- **Outdoor + water** — water plane at fixed Z, terrain sloped beneath it for a
  shoreline/lakebed, an `AWT_` region so the client treats it as swimmable.
  Terrain backend needs a water level + shoreline shaping.
- **Cave-mouth-in-hillside** — compose SDF cave + heightfield terrain into one
  TER. Strongest argument for unifying both onto a single density-field
  representation (terrain as an SDF too). The SDF cave backend was removed in
  M0; revisit with M5.

### Content / semantic layer — making rooms *interesting* (candidate for after Phase 4)

So far the generator solves **spatial structure**: where rooms are, how they
connect, that they're navigable and enclosed. It does almost nothing about
**content** — what makes a room a memorable *place* rather than an empty shell.
These are different problems and should stay separated.

**Two separate problems hiding under "interesting rooms":**

1. **Semantic content** — what a room *is* and *means*: a flooded crypt with an
   submerged altar, collapsed mine shaft, guard barracks, throne dais. Props,
   set dressing, encounter/spawn intent, loot, and a *theme* that ties rooms
   into a small narrative (barracks → prison → ritual chamber). Almost entirely
   missing today.
2. **Geometric uniqueness** — the room's shape being distinctive. We have a
   little (pacing biases size, caves vary) but it's shallow.

"Rooms as nodes that share themes" is problem #1, and it lives at the
**ZoneSpec / graph level, not the mesh level** — which decides where ML fits.

**Where a model helps — Version A (recommended):** a model (most likely the
existing `LLMPlanner`, extended) produces a *richer structured ZoneSpec* — per-
room semantic type + theme + intent ("flooded ritual chamber, floor -40, raised
altar platform, water region in the lower third, 4 braziers, boss on the dais").
Our deterministic pipeline already converts structured descriptions into
EQ-accurate, navigable, enclosed geometry. The model supplies *creativity and
semantics*; the pipeline keeps the hard-constraint guarantees. No training data
needed — it's a design/language task on a general model.

**Where a model does NOT help — Version B (avoid):** a model generates the
actual 3D *mesh* of a room and we "restyle" it to look EQ. 3D mesh style-transfer
isn't a drop-in solved thing; you'd get wrong-resolution, hole-ridden meshes you
must remesh/repair/retexture anyway, and there's no corpus to train a room-mesh
generator on. Repairing back to our guarantees throws away most of what the model
gave you.

**Key insight:** "convert generated rooms to the EQ look" assumes the look lives
in the geometry and must be transferred. But from our measurements the EQ look
lives mostly in **resolution, proportion, palette, and texture** — which the
style profiles and backends already enforce. So we don't need to restyle a mesh;
we need to feed richer *semantic intent* into a pipeline that already produces
the look. The model never needs to know what EQ looks like.

**Proposed layer (between layout and geometry):**
- Assign each room a **semantic type + theme**, coherent with neighbours, so the
  progression reads as a small story (graph-labelling on the pacing graph we have).
- Each room type carries **content rules** → expand into ZoneSpec elements
  (region volumes, lights, elevation/shape bias) and eventually MOD placements +
  EQEmu spawn/loot/door data via the same deterministic realization.
- The (LLM) planner proposes theme assignment + per-room intent from the prompt;
  deterministic rules realize it as valid, era-accurate geometry/placement.
- Lines up with the planned EQEmu SQL export — content and server-side data are
  the same layer.

**No-new-art first slice:** props/set-dressing need actual MOD models to place,
which we don't generate (generating EQ-authentic props is its own hard problem;
likely reference existing EQ object models, cf. the door-model note). So start
with the parts needing zero new art: semantic room themes, region volumes
(water/lava), lighting mood, per-theme elevation/shape bias, and spawn/encounter
intent carried as data for the SQL export.

### Should we train a bespoke model instead? (decision: no, for the core)

Recorded so the question has a durable answer. Training a from-scratch 3D-mesh
generator for zones is the wrong tool here:
- **Data regime** — only a few hundred real EQ zones exist, one narrow art
  style, no pretrained base to fine-tune. Far too little for 3D generation.
- **Hard constraints** — navigable floors, watertight enclosure, reachable
  rooms, solvable gating are discrete global pass/fail properties. Generative
  mesh models produce plausible-but-leaky output (holes, non-manifold edges,
  unreachable pockets — the exact bugs we fix deterministically). You'd bolt the
  repair passes back on anyway.
- **Controllability** — prompt-driven iteration ("make the entrance wider") is
  trivial with explicit parametric knobs, hard to steer in a mesh generator.
- **Format** — output still has to become valid `.ter`/`.zon`/PFS with
  per-triangle collision; the model doesn't help with the part we've solved.

Where ML *does* fit, in priority: (1) richer LLM planning / the semantic layer
above; (2) a lightweight learned "EQ-ness" critic that scores a generated zone
against real-zone feature distributions (discriminative, modest data) — only if
"does this *feel* like EQ?" becomes the bottleneck; (3) learned textures /
normal maps (the AI texture provider is already a drop-in slot). Keep the
procedural spine; push ML into planning/semantics and optionally textures.
