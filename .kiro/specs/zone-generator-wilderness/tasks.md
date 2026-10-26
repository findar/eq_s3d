# Implementation Plan: zone-generator-wilderness — the open-world wilderness engine

## Overview

This plan implements `requirements.md` and `design.md` in this folder. "Req X.Y"
means this spec's acceptance criterion. "Property N" means this spec's design
Correctness Property N (tagged in each test's docstring as
`Feature: zone-generator-wilderness, Property N: ...`). The implementation
language is **Python** throughout — the design is written in concrete Python
(dataclasses, `Protocol`s, numpy), matching the existing `generators/` / `ai/`
code; no language choice is open.

The generator builds a genuinely open, scenic EQ outdoor landscape around a
central landmark (an oasis in the desert, a river fork in the plains). The
governing idea is a 2D IR, the **Design_Matrix**: intent resolves to a matrix of
typed cells; graph-replacement refines it; a noise/erosion pass synthesizes a
heightfield *subordinate* to the matrix; the result upsamples to terrain, gets
biome texturing + a water plane + rivers, and flows through the existing
`ZoneSpec` to EQG + sidecar. **Playability, not full connectivity, is the
invariant** (Requirement 3 amends followup). It is a **geometry-producing** spec:
a green structural + property suite is **necessary but NOT sufficient** — every
geometry-producing milestone takes a Human_3D_Pass per `docs/ACCEPTANCE.md`
(Requirement 14.4).

### HARD PREREQUISITE — do not start this spec until M1 and the followup runway land

This is a **POST-M1, POST-`zone-generator-followup` milestone.** It must not
begin until BOTH land on `master`:

```
M1 (dungeon + city shipping; wilderness present-but-DISABLED)
  -> zone-generator-followup runway (F1 LayoutEngine seam, F2 3D Envelope +
     typed edges, F3 harness, F4 gate-learns-connectors)
    -> THIS spec (the wilderness engine)
```

Wilderness sits **behind followup's F1 seam**, specializes F2's `Envelope`, and
**narrows** F4's gate. The exact followup pieces that are hard predecessors, and
the wilderness wave each gates:

| followup task | what it lands | wilderness wave that needs it | why |
|---------------|---------------|-------------------------------|-----|
| **F1** (followup task 1: `LayoutEngine` seam + registry routing) | the pluggable layout-engine protocol selected by `zone_type` | **Wave 1** (Design_Matrix engine) | wilderness is a `LayoutEngine` (or sibling layout stage) behind this seam, not a reinvented one (design "Architecture") |
| **F2.1** (followup task 2.1: typed edges `(i,j,kind,vhint)`) | the typed-edge vocabulary | **Wave 2** (Graph_Replacement) | the `borders`/`approaches`/`flows_into` relations specialize F2's typed edges, not a parallel edge set (design "Graph-replacement") |
| **F2.2** (followup task 2.2: `Envelope` 3D-volume interface) | the `Envelope` type | **Wave 1** (Design_Matrix as a specialization of `Envelope`) | the Design_Matrix is the cell-grid authoring face of a thin `Envelope` (Req 2.1; design "how it specializes followup's `Envelope`") |
| **F4** (followup task 3: gate learns vertical connectors) | the connector-aware traverse gate | **Wave 5** (reachability amendment on the mesh) | wilderness narrows the F4 gate's scope with a defaulted required-reachable/excluded-regions parameter; the `cliff -> ramp` approach rides F4's bridge/ramp walkability (design "Interaction with followup's F4 connector-aware gate") |

followup F3 (the side-by-side harness) is **not** a wilderness predecessor — it
settles the typed-vs-abstract embedding question for the dungeon path and does
not gate any wilderness wave. If F1/F2/F4 have not landed when a worker picks up
a wave below, that wave is **blocked**: stop and surface it, do not reinvent the
seam.

### Delivery waves

The plan follows the design's pipeline as six waves, in order. Each wave is one
branch in its own worktree, forked from `master`, merged back before the next
wave starts. The partition is by module so parallel workers (if any) don't
collide; the cross-branch code hotspots are called out per wave.

| Wave | Tasks | Branch | Module partition / hotspot owner |
|------|-------|--------|----------------------------------|
| 1 Matrix IR | 1–3 | `agent/wild-matrix` | `generators/wilderness/` (new package); owns the F1/F2 seam wiring in `generators/backends.py` |
| 2 Graph_Replacement | 4–5 | `agent/wild-rewrite` | `generators/wilderness/rewrite.py` (new); reuses followup's rewrite layer |
| 3 Noise + upsample | 6–7 | `agent/wild-noise` | `generators/wilderness/synth.py` (new); reads `generators/field/` but does not edit it |
| 4 Biome + water + rivers + texturing | 8–9 | `agent/wild-biome` | `generators/wilderness/biome.py`, `drainage.py` (new); `biomes/` data table; reuses `generators/textures/factory.py` |
| 5 POI + reachability on the mesh | 10–11 | `agent/wild-reach` | `generators/wilderness/poi.py` (new); narrows `analyzer/traverse.py` (hotspot — single owner) |
| 6 Integration + end-to-end + 3D passes | 12–13 | `agent/wild-integrate` | `generators/zone_spec.py`, `generators/backends.py`, `core/eqg.py` sidecar (hotspots — single owner), `generators/pipeline.py` |
| Exit | 14 | MAIN checkout after wave 6 merges | none |

`requirements.txt` changes in no wave (numpy + Hypothesis are already pinned),
so no wave needs `-Venv`. No wave changes `web/package.json`, so the shared
`web/node_modules` junction is fine; wave 6 does touch `web/` (water/biome
preview), so it runs `cd web; npx vite build` at its checkpoint.

### Working rules for every task

- Create each wave's worktree from the MAIN checkout with
  `./scripts/new-worktree.ps1 -Branch agent/wild-<wave>`. Stay in it. Don't push
  the branch. Tear down only with `./scripts/remove-worktree.ps1`.
- Commit one logical change at a time. Write the message to
  `.git/COMMIT_EDITMSG_TMP`, run `git commit -F .git/COMMIT_EDITMSG_TMP`, then
  delete the file. Messages must not contain the words blocked by the
  commit-message hook (the frontend build tool name and "dev server").
- **Tracker writes go to this `tasks.md` only** (checkboxes, measurements,
  hashes, Deliverables). Don't edit `ROADMAP.md`, `README.md` or
  `tasks/README.md`; those are integration state, written once per landed branch
  in the single-writer integration step (each wave's checkpoint note + task 14).
- Run `python -m pytest tests/ -q` before each commit. After any `web/` change
  run `cd web; npx vite build` (one-shot, never a watch process).
- **A failing property is a real bug: fix it at the root** and pin the
  counterexample as a Regression_Example (`@example(...).via("discovered
  failure")`). Never weaken an assertion, never `xfail`, never `assume` a builder
  exception away. When a walkability/reachability property fails, that is almost
  always a real geometry/graph bug, not a test to loosen (lessons-learned).
- Every property test has a docstring starting
  `Feature: zone-generator-wilderness, Property N: <title>`, naming the
  requirement ids it validates. **Matrix properties (1–10, 16, 17) run with NO
  geometry built** — plain data over a seed/prompt space, default profile
  ≥ 100 examples. Heightfield properties (11–14) run on the synthesized field.
  The mesh property (15) runs the real traversability agent on the built mesh
  under `@pytest.mark.slow` + `build_settings(n)` (n 10–25).
- Human-gated subtasks (marked **HUMAN-GATED**) are signed off by the user in
  the live 3D viewer or browser. The agent writes the checklist, marks it
  PENDING-HUMAN and leaves the checkbox unchecked. **The agent never ticks one.**
- **Structural tests passing is necessary but NOT sufficient — eyeball it in
  3D.** No geometry-producing wave closes until its Human_3D_Pass is signed off
  (Requirement 14.4; lessons-learned).

## Tasks

### Wave 1 — Design_Matrix IR + intent resolution + matrix properties (Requirements 1, 2, 3.4)

> Intent: land the governing 2D IR and prove its matrix-level invariants BEFORE
> any geometry exists — the central guard against "a room graph in a grass skin."
> Behind followup F1 (engine seam) + F2.2 (`Envelope` type). New package
> `generators/wilderness/`; the only shared-file edit is the registry wiring in
> `generators/backends.py` (owned here).

- [ ] 1. Set up wave 1, confirm the followup runway, and resolve the first open decision
  - [ ] 1.1 Create the worktree and capture prerequisites + baselines
    - Run `./scripts/new-worktree.ps1 -Branch agent/wild-matrix`. Record the fork-point commit hash here.
    - **Confirm the runway is present on the fork point** before any wilderness work: verify followup F1 (`LayoutEngine` protocol + registry routing in `generators/backends.py`) and F2.2 (`Envelope` interface) exist, and that M1 ships wilderness present-but-disabled. If either is absent, STOP and surface it — this spec is blocked. Record exactly which followup symbols/types you found and where.
    - Run `python -m pytest tests/ -q` once; record the pass count and wall time as the wave-1 baseline.
    - _Requirements: 2.1_
  - [ ] 1.2 Resolve open decision: `LayoutEngine` vs sibling layout stage, and the `Envelope` shared type
    - Read followup's landed `LayoutEngine` contract and `Envelope` type. Decide and RECORD here whether wilderness is a literal `LayoutEngine` (with a thin `rooms=[], edges=[]` adapter) or a **sibling layout stage** selected by the same `zone_type` registry (design "Open decisions" favours the sibling stage). Confirm the shared `Envelope` type wilderness will specialize (continuous predicate vs cell grid — design commits wilderness to the cell-grid authoring face; confirm F2.2's actual shape).
    - This is a decision-recording subtask: no code beyond a stub module header. The decision governs tasks 1.3 and 12.
    - _Requirements: 2.1_

- [ ] 2. The Design_Matrix data model and landmark-first construction
  - [ ] 2.1 Create `generators/wilderness/matrix.py` — the IR data model
    - Define `NodeType` (`river|cliff|flatland|oasis|landmark_pad|water|backdrop`), `IntentTag` (`playable|scenic`), `MatrixCell` (node_type, intent, frozen, frozen_z, biome) and `DesignMatrix` (cells `np.ndarray` object grid, cell_size, origin, water_level, biome, landmark, intent_overrides) per the design's data model. The matrix is the cell-grid authoring face of a thin `Envelope`: add the `Envelope.contains(x,y,z)` derivation stub (filled after synthesis in wave 3) so the type relationship to F2.2 is explicit.
    - _Requirements: 2.1, 2.2, 2.3_
    - **Deliverables:** `generators/wilderness/matrix.py` with the dataclasses above; a `DesignMatrix` is constructible and serializable to plain data with no heightfield built (Req 2.5).
  - [ ] 2.2 Implement landmark-first construction (`build_matrix(intent, seed)`)
    - Place the landmark node first at/near matrix center (oasis + water ring, or a river seed), mark its `landmark_pad` cells frozen; derive biome backdrop outward; place scenic framing (`cliff` edge, `backdrop` band); assign a default Intent_Tag to every region (landmark + surrounding ground `playable`, distant backdrop/far cliff/deep water `scenic`). Enforce as post-conditions: desert+oasis rings every `oasis` cell so none touches the boundary (Req 2.6); `water` cells form one connected region (Req 2.7).
    - Expose the finished `DesignMatrix` on the engine output for inspection before any noise pass (Req 2.5).
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.4_
    - **Deliverables:** `build_matrix` produces a desert+oasis and a plains+river-fork matrix from a resolved intent + seed; both satisfy the Req 2.6/2.7 post-conditions (proven by the properties in task 3).
  - [ ] 2.3 Wire the wilderness engine behind the F1 seam
    - Per the task-1.2 decision, add `WildernessLayoutEngine` (or sibling stage) that owns `build_matrix` and exposes the `DesignMatrix`, selected by `zone_type == "wilderness"` through `generators/backends.py`. With no matrix (a plain terrain spec) the existing `TerrainBackend` path is unchanged — additive, no regression to dungeon/city/plain-terrain.
    - _Requirements: 2.1, 11.2_
    - **Deliverables:** `backend_for("wilderness")` resolves the engine; a dungeon/city build is byte-unchanged (spot-check one TER hash against master); `generators/backends.py` is the only shared file touched.

- [ ] 3. Prove the matrix-level invariants (pre-geometry properties)
  - [ ] 3.1 Create `generators/wilderness/__init__.py` + `tests/test_wilderness_matrix.py` scaffolding and intent resolution
    - Extend the existing planner seam (`ai/rule_planner.py` landmark lexicon) so a prompt resolves to a `LandmarkIntent(biome, landmark, requested_*, substituted)`: desert words + "oasis" -> `desert`+`oasis`; plains words + "river"/"fork" -> `plains`+`river_fork` (Req 1.1/1.2); LLM drop-in proposes the same intent through the existing `get_planner()`/`make_plan()` seam with rule-planner fallback (Req 1.3); an out-of-set biome/landmark resolves to the nearest supported intent and records the substitution for the sidecar (Req 1.4); the resolved biome+landmark are stored on the `ZoneSpec` (Req 1.5, additive defaulted fields).
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
    - **Deliverables:** intent resolution works zero-key via the rule planner; `LandmarkIntent` carries the substitution record; `ZoneSpec` gains defaulted `biome`/`landmark` fields.
  - [ ]* 3.2 Write property test for Property 4: Landmark is placed first and is central
    - **Property 4: Landmark is placed first and is central** — for any resolved intent + seed the matrix contains the landmark node and derives supporting geography around it (no supporting feature displaces it from central placement).
    - **Validates: Requirements 2.4**
  - [ ]* 3.3 Write property test for Property 3: Every cell has exactly one Node_Type and one Intent_Tag
    - **Property 3: Every cell has exactly one Node_Type and one Intent_Tag** — every cell carries exactly one `Node_Type` from the v1 set and exactly one `Intent_Tag`, and every region has a proposed default Intent_Tag.
    - **Validates: Requirements 2.2, 2.3, 3.4**
  - [ ]* 3.4 Write property test for Property 1: Oasis is ringed by desert, never on the boundary
    - **Property 1: Oasis is ringed by desert, never on the boundary** — for any desert+oasis intent + seed, every `oasis` cell is surrounded by desert `flatland`/`backdrop` cells and no `oasis` cell lies on the matrix boundary.
    - **Validates: Requirements 2.6**
  - [ ]* 3.5 Write property test for Property 2: Water forms a single connected region
    - **Property 2: Water forms a single connected region** — for any constructed matrix the `water` cells form exactly one connected region (4-connectivity).
    - **Validates: Requirements 2.7**
  - [ ]* 3.6 Write property test for Property 17: Fallback substitution is recorded
    - **Property 17: Fallback substitution is recorded** — for any prompt naming an out-of-set biome/landmark, the resolved intent is the nearest supported one AND the substitution is recorded (asserted on the `LandmarkIntent`; the sidecar emission is checked in wave 6).
    - **Validates: Requirements 1.4**

- [ ] 4. Checkpoint — wave 1 closed
  - Run `python -m pytest tests/ -q` (green). Confirm the matrix properties (1–4, 17) pass with NO geometry built, and the dungeon/city TER hash spot-check is unchanged. Write the wave-1 integration note (Done-table row, "Pick up here" line, commit hash/count) in Deliverables WITHOUT editing `ROADMAP.md`/`README.md`/`tasks/README.md`. Ask the user if questions arise.
  - _Requirements: 2.5_

### Wave 2 — Graph_Replacement rules (terminate; preserve reachability by construction) (Requirement 4, Property 5–10)

> Intent: refine the matrix with rewrite rules that cannot loop or strand
> playable regions, reusing followup's dimension-free graph-rewrite layer over a
> terrain vocabulary. Matrix-level still — no geometry. Needs wave 1 + followup
> F2.1 (typed edges). Hotspot: `generators/wilderness/rewrite.py` (new).

- [ ] 5. Graph_Replacement over the Design_Matrix
  - [ ] 5.1 Set up wave 2 and bind to followup's rewrite layer
    - Run `./scripts/new-worktree.ps1 -Branch agent/wild-rewrite`. Record the fork-point hash. Confirm followup's dimension-free mission-grammar/graph-rewrite layer and F2.1 typed edges are present; record the symbols reused. If absent, STOP — wave 2 is blocked.
    - _Requirements: 4.1_
  - [ ] 5.2 Implement the region graph + typed-edge adapter
    - Build the region graph from the matrix: a node is a connected set of same-type cells; edges specialize followup's typed edges adapted to terrain — `borders`, `approaches`, `flows_into`. This reuses F2.1's edge model, not a parallel one.
    - _Requirements: 4.1_
  - [ ] 5.3 Implement termination-bounded rewrite with apply-then-check-then-commit
    - Run the followup rewrite machinery parameterized with wilderness rules to a fixed-point under a hard iteration cap (`max_iters = C * region_count`); exceeding the cap raises a construction error, never a silent loop (Req 4.2). Before committing each rule, compute the playable-reachability relation (connected `playable` regions reachable from Spawn via non-barrier cells); apply to a candidate, recheck, and **reject the application keeping the prior matrix if any playable region became stranded** (Req 4.3/4.6). Honor `intent_overrides` in the reachability relation (Req 3.5).
    - _Requirements: 4.1, 4.2, 4.3, 4.6, 3.5_
  - [ ] 5.4 Implement the two v1 rules
    - `cliff -> ramp/pass approach` (Req 4.4): when a `cliff` region would strand a `playable` region, spawn a graded `flatland` ramp/pass corridor carrying an `approaches` edge so the region stays reachable — committed only together with its approach. `river -> fork` (Req 4.5): in a plains+river-fork zone, grow the single `river` node into two branches meeting at a junction (`flows_into` edges), realized downstream as two splines.
    - _Requirements: 4.4, 4.5_
    - **Deliverables:** both rules run inside the bounded rewrite; a desert+oasis and a plains+river-fork matrix refine to a fixed-point with the invariant held at every committed step.
  - [ ]* 5.5 Write property test for Property 8: Graph_Replacement terminates
    - **Property 8: Graph_Replacement terminates** — for any starting matrix + seed the rewrite reaches a fixed-point within the bounded iteration cap (never looping).
    - **Validates: Requirements 4.2**
  - [ ]* 5.6 Write property test for Property 9: Graph_Replacement preserves playable reachability at every step
    - **Property 9: Graph_Replacement preserves playable reachability at every step** — mutual reachability among `playable` regions holds after every committed rewrite step; a rule application that would strand a `playable` region is rejected and the prior matrix preserved.
    - **Validates: Requirements 4.3, 4.6**
  - [ ]* 5.7 Write property test for Property 10: Cliffs never strand playable regions
    - **Property 10: Cliffs never strand playable regions** — for any matrix with a `cliff` that would strand a `playable` region, the rewrite spawns a ramp/pass approach so that region stays reachable.
    - **Validates: Requirements 4.4**
  - [ ]* 5.8 Write property test for Property 5: Playable regions are mutually reachable from Spawn on the matrix
    - **Property 5: Playable regions are mutually reachable from Spawn on the matrix** — every `playable` region (and a `playable` landmark) is reachable from Spawn through non-barrier cells; an unreachable `playable` region is reported as a failure naming it.
    - **Validates: Requirements 3.1, 3.6, 3.7**
  - [ ]* 5.9 Write property test for Property 6: Scenic regions may be unreachable without breaking the invariant
    - **Property 6: Scenic regions may be unreachable without breaking the invariant** — the reachability check passes even when scenic regions are unreachable from Spawn.
    - **Validates: Requirements 3.2, 12.3**
  - [ ]* 5.10 Write property test for Property 7: Intent override is honored
    - **Property 7: Intent override is honored** — for any user override of a region's Intent_Tag, the reachability invariant is enforced using the overridden tag.
    - **Validates: Requirements 3.5**

- [ ] 6. Checkpoint — wave 2 closed
  - Run `python -m pytest tests/ -q` (green). Confirm the rewrite properties (5–10) pass with NO geometry built. Write the wave-2 integration note (Done-table row, "Pick up here", commit hash/count) in Deliverables WITHOUT editing the three tracker files. Ask the user if questions arise.
  - _Requirements: 4.3_

### Wave 3 — Noise/erosion subordinate to the matrix + sharp-edge upsample (Requirements 5, 6, Property 11–14)

> Intent: synthesize the heightfield FROM the finished matrix — frozen cells
> masked, edges blended, sharp cliff/shore edges preserved, hills everywhere
> else. First geometry wave: it ends with a HUMAN-GATED 3D pass. Needs wave 2.
> Hotspot: `generators/wilderness/synth.py` (new); reads `generators/field/`
> (FBM noise + thermal erosion) without editing it.

- [ ] 7. Noise_Pass + upsample
  - [ ] 7.1 Set up wave 3 and capture synthesis baselines
    - Run `./scripts/new-worktree.ps1 -Branch agent/wild-noise`. Record the fork-point hash. Capture the existing `generators/field/terrain.py` FBM + thermal-erosion + `_enforce_walkable` behavior on one plain-terrain spec (timing + a height-array checksum) so the subordinated path can be compared against it.
    - _Requirements: 5.1_
  - [ ] 7.2 Implement freeze/mask + edge-blend (Noise_Pass subordinate to the matrix)
    - Reuse the FBM + thermal-erosion + `_enforce_walkable` core but mask the write out of every `Frozen_Cell` (terrain set by `frozen_z`, not noise — Req 5.2); blend noise toward the frozen value across a short distance-field falloff band at shared edges (Req 5.3); run erosion AFTER masking so it smooths only non-frozen terrain. Hold `landmark_pad` cells flat to a stated tolerance after the pass (Req 5.4); clamp `river` channel cells at/below adjacent bank height (Req 5.5). All masking/blending is vectorised numpy — no per-cell Python loop (lessons-learned performance rule).
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
    - **Deliverables:** a finalized matrix synthesizes a heightfield where frozen cells equal their constraint height and non-frozen terrain is weathered FBM; vectorised, well within budget.
  - [ ] 7.3 Implement type-aware upsample preserving sharp transitions
    - Upsample the coarse matrix to terrain resolution: bilinear/bicubic across `flatland`<->`flatland` (Req 6.1); treat `cliff`<->non-`cliff` and `water`<->non-`water` boundaries as discontinuities — interpolate each side independently, preserve the height step (Req 6.2/6.3); trace cliff/shore boundaries as a polyline through the coarse grid and jitter/smooth along the edge direction before applying the step, so edges follow a natural contour with no axis-aligned stair-steps (Req 6.4). Resolve the open decision on matrix resolution here: tune `cell_size` (~150–250 u/cell starting point) against the upsample and the 3D pass; record the chosen value and why.
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
    - **Deliverables:** upsampled terrain is smooth on flatland and sharp at cliffs/shorelines, free of grid stair-steps; the chosen matrix resolution is recorded.
  - [ ] 7.4 Derive the `Envelope.contains` predicate from the synthesized surface
    - Fill the task-2.1 stub: a point is inside the thin `Envelope` if within XY bounds and below the synthesized surface + headroom. This closes the Req 2.1 "specialization of followup's `Envelope`" relationship against real geometry.
    - _Requirements: 2.1_
  - [ ]* 7.5 Write property test for Property 11: Noise is masked out of frozen cells
    - **Property 11: Noise is masked out of frozen cells** — for any finalized matrix + seed, every `Frozen_Cell`'s terrain equals its constraint height after the Noise_Pass.
    - **Validates: Requirements 5.2**
  - [ ]* 7.6 Write property test for Property 12: Landmark pad stays flat after noise
    - **Property 12: Landmark pad stays flat after noise** — every `landmark_pad` cell is flat to within the stated tolerance after the Noise_Pass.
    - **Validates: Requirements 5.4**
  - [ ]* 7.7 Write property test for Property 13: River stays at or below its banks
    - **Property 13: River stays at or below its banks** — every river-channel cell is at or below its adjacent bank height after the Noise_Pass.
    - **Validates: Requirements 5.5**
  - [ ]* 7.8 Write property test for Property 14: Upsample smooths flatland and preserves sharp cliff/shore edges
    - **Property 14: Upsample smooths flatland and preserves sharp cliff/shore edges** — height interpolates smoothly across `flatland`<->`flatland` boundaries, AND the discontinuity across `cliff`<->non-`cliff` and the `water`<->non-`water` shoreline is preserved as a sharp transition.
    - **Validates: Requirements 6.1, 6.2, 6.3**

- [ ] 8. Checkpoint — wave 3 closed (first geometry pass)
  - [ ] 8.1 Run the suite and check the budget
    - `python -m pytest tests/ -q` green; the heightfield properties (11–14) pass. Record the Default_Run median against the wave-1 baseline; if build-level properties push it up, note the cost (budgets, not weakened assertions).
    - _Requirements: 14.3_
  - [ ] 8.2 **HUMAN-GATED:** terrain shape 3D pass
    - The user, in the live viewer: a synthesized wilderness terrain (desert+oasis and plains+river-fork, a few seeds) reads as an open landscape with weathered hills; the landmark pad is flat; cliffs and shorelines are SHARP, not blocky/stair-stepped (eyeballs Property 14); noise has not pushed through the river or tilted the pad (eyeballs Properties 11–13). The agent writes the checklist, marks it PENDING-HUMAN, leaves the box unchecked.
    - _Requirements: 14.4_
  - [ ] 8.3 Write the wave-3 integration note (don't apply it)
    - Done-table row, "Pick up here", commit hash/count, matrix-resolution decision, and the seeds to eyeball. No edit to the three tracker files.
    - _Requirements: 14.4_

### Wave 4 — Biome kits + visual water + rivers-as-splines + texturing (Requirements 7, 8, 9, 10)

> Intent: give desert and plains distinct identity over one terrain core — ground
> splat by slope/height/moisture, a flat visual water plane, rivers as splines
> behind one interface, all zero-key with the AI-texture seam preserved. Needs
> wave 3. Ends with a HUMAN-GATED look pass. Hotspots: new
> `generators/wilderness/{biome,drainage}.py`, a `biomes/` data table; reuses
> `generators/textures/factory.py` (no texture-side code change).

- [ ] 9. Biome kits, water plane, river splines, texturing
  - [ ] 9.1 Set up wave 4
    - Run `./scripts/new-worktree.ps1 -Branch agent/wild-biome`. Record the fork-point hash. No `requirements.txt`/`web/package.json` change expected.
    - _Requirements: 7.2_
  - [ ] 9.2 Implement the BiomeKit data table and selection
    - Add `BiomeKit` (name, ground_textures, water_present, sky_fog_tint, vegetation_kit) as a data table (JSON under `styles/` or a new `biomes/`), applied over one shared terrain+hydrology core — not a generator per biome (Req 7.1/7.2). `desert` and `plains` select their texture set, tint, vegetation kit from the table (Req 7.3/7.4). Vegetation/feature scatter is carried as placement data keyed to biome+moisture (resolve the open decision: v1 carries placement data; whether it emits placed MODs or defers is recorded here).
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  - [ ] 9.3 Implement the visual-only water plane
    - A zone with `water`/`oasis` cells gets a flat visual water plane at `Water_Level` (Req 8.1) with the biome water material (Req 8.2), carried as a `RegionSpec(kind="water")` + plane geometry on the `ZoneSpec` so it renders in the preview. Blend the shoreline texture across the land-water boundary where terrain meets `Water_Level` (Req 8.3). A kit with `water_present` triggers the plane (Req 7.5). Mark real walkable-shallows/swimmable-deep volumes out of scope for v1 in a code comment (Req 8.4).
    - _Requirements: 7.5, 8.1, 8.2, 8.3, 8.4_
  - [ ] 9.4 Implement `DrainageModel` + `SplineDrainage`
    - Define the `DrainageModel` Protocol (`carve(matrix, heights) -> heights`) and a v1 `SplineDrainage`: define the river as a drainage spline governing the valley (Req 9.1); carve the channel along the spline and locally erode banks so the valley reads water-made (Req 9.2); realize a river fork as two spline branches meeting at a junction (Req 9.3). Keep carving behind the `DrainageModel` seam so full hydraulic erosion drops in later without changing callers (Req 9.4). Resolve the open decision: record the spline type (Catmull-Rom vs Bezier) and fork-junction blending chosen.
    - _Requirements: 9.1, 9.2, 9.3, 9.4_
  - [ ] 9.5 Implement procedural texturing through the AI seam
    - Texture procedurally, zero-key (Req 10.1), blending ground textures by slope, height, and moisture (Req 10.2); route generation through the existing `generators/textures/factory.py` AI drop-in seam so an AI provider can be supplied without changing the generator (Req 10.3, no texture-side code change); raise the moisture input near `Water_Level` so water-adjacent surfaces read as damp shoreline (Req 10.4). Tune erosion/bank-erosion params here against the look (open decision — record the values).
    - _Requirements: 10.1, 10.2, 10.3, 10.4_
    - **Deliverables:** a desert+oasis build reads sandy with a central water plane; a plains+river-fork build reads grassy with a forking river valley; both zero-key.
  - [ ]* 9.6 Write the biome/water/texturing example tests (not PBT)
    - Example/config tests: biome kit selection picks the right texture set/tint/vegetation for desert vs plains; the water plane is placed at `Water_Level` with the biome water material on an oasis zone; texturing routes through the AI-texture seam (force a provider via the existing `set_provider` seam, assert the call path) — these are wiring/config, not input-varying, so example/mock-based not PBT.
    - _Requirements: 7.3, 7.4, 7.5, 8.1, 8.2, 10.3_

- [ ] 10. Checkpoint — wave 4 closed (biome look pass)
  - [ ] 10.1 Run the suite and build the frontend
    - `python -m pytest tests/ -q` green; the example tests pass. `cd web; npx vite build` (one-shot) since the water/biome preview touches `web/`. Record results.
    - _Requirements: 14.3_
  - [ ] 10.2 **HUMAN-GATED:** biome + water 3D/browser pass
    - The user, in the live viewer/browser: the desert biome reads as desert and plains as plains (ground texture, fog/sky tint) over the same terrain engine; the water plane reads as WATER with a clean shoreline blend (not a flat sheet with a hard grid edge); the river valley reads water-made with eroded banks and a believable fork. The agent writes the checklist, marks it PENDING-HUMAN, leaves the box unchecked.
    - _Requirements: 14.4_
  - [ ] 10.3 Write the wave-4 integration note (don't apply it)
    - Done-table row, "Pick up here", commit hash/count, the spline/erosion-param decisions, seeds to eyeball. No edit to the three tracker files.
    - _Requirements: 14.4_

### Wave 5 — POI anchors + reachability amendment wired into the traverse gate (Requirements 11, 12, 3.1–3.3, Property 15)

> Intent: wilderness navigability is open-ground walkability among named POI
> anchors in playable regions — not rooms. Narrows the F4 gate to prove
> reachability among playable anchors only, scenic ground excluded. Needs wave 4
> + followup F4. Hotspot: `analyzer/traverse.py` (SINGLE OWNER — the gate
> parameter is a shared seam); new `generators/wilderness/poi.py`.

- [ ] 11. POI anchors + narrowed reachability gate
  - [ ] 11.1 Set up wave 5 and confirm F4
    - Run `./scripts/new-worktree.ps1 -Branch agent/wild-reach`. Record the fork-point hash. Confirm followup F4 (the connector-aware traverse gate, bridge/ramp walkability by rise/run/headroom) is present and record its entry-point signature — wave 5 adds a defaulted parameter to it. If F4 is absent, STOP — wave 5 is blocked.
    - _Requirements: 12.1_
  - [ ] 11.2 Implement POI anchors + Spawn
    - Add `POIAnchor` (name, x, y, is_spawn, intent) and derive anchors from the matrix: the landmark plus a small number of camps/spawn clearings, NOT rooms (Req 11.1); do not use the TinyKeep room-and-corridor layout (Req 11.2); designate one anchor as Spawn (Req 11.3). Carry anchors on the `ZoneSpec` (additive defaulted `poi_anchors` field).
    - _Requirements: 11.1, 11.2, 11.3_
  - [ ] 11.3 Narrow the F4 gate with a defaulted playable-mask parameter
    - Add a defaulted parameter to the `analyzer/traverse.py` entry point: a set of required-reachable seed points (playable POI anchors) + excluded regions (scenic ground). With the parameter absent the gate behaves EXACTLY as the dungeon full-connectivity gate — no regression to F4/dungeon behavior (spot-check one dungeon validate result unchanged). With it present, the gate proves reachability among the playable anchors only, excluding scenic regions (Req 3.1/3.2/12.3). Realize deliberate scenic unreachability through cliffs/deep water (geometry the agent already rejects) and Invisible_Wall barriers (Req 3.3 — barriers carried as sidecar records in wave 6). Apply `_enforce_walkable` to playable cells only so scenic cliffs stay steep (Req 12.4). Report a stranded playable anchor as a walkability failure naming it (Req 12.2).
    - _Requirements: 3.1, 3.2, 3.3, 12.1, 12.2, 12.3, 12.4_
    - **Deliverables:** the gate runs over a built wilderness mesh proving every playable anchor reachable from Spawn with scenic excluded; a dungeon build's gate result is unchanged.
  - [ ]* 11.4 Write property test for Property 15: Open-ground walkability — playable POIs reachable, slopes within cap
    - **Property 15: Open-ground walkability** — for any built wilderness mesh, every Playable_Region POI_Anchor is reachable from Spawn by the traversability agent with Scenic_Regions excluded, walkable playable slopes stay within the agent's slope cap, and an unreachable playable anchor is reported as a walkability failure naming it. `@pytest.mark.slow` + `build_settings(n)` (n 10–25) — this runs the real agent on the built mesh.
    - **Validates: Requirements 12.1, 12.2, 12.3, 12.4**

- [ ] 12. Checkpoint — wave 5 closed (walkability pass)
  - [ ] 12.1 Run the suite and check the budget
    - `python -m pytest tests/ -q` green; Property 15 passes on the built mesh; the dungeon gate regression spot-check holds. Record the Default_Run median.
    - _Requirements: 14.3_
  - [ ] 12.2 **HUMAN-GATED:** reachability 3D pass
    - The user, in the live viewer: spawn into a desert+oasis and a plains+river-fork zone and walk — every playable POI (landmark + camps) is reachable on foot, slopes are climbable; scenic backdrops/far cliffs/deep water are visibly OUT OF REACH but visible (the playable-vs-scenic split reads right, not a walled-off box). The agent writes the checklist, marks it PENDING-HUMAN, leaves the box unchecked.
    - _Requirements: 14.4_
  - [ ] 12.3 Write the wave-5 integration note (don't apply it)
    - Done-table row, "Pick up here", commit hash/count, the gate-parameter shape, seeds to eyeball. No edit to the three tracker files.
    - _Requirements: 14.4_

### Wave 6 — ZoneSpec/EQG/sidecar integration + end-to-end builds + final 3D passes (Requirements 13, 14, Property 16)

> Intent: flow everything through the existing `ZoneSpec` to EQG (Z-up) + sidecar,
> wire the full pipeline, prove the two v1 pairs build end to end within budget,
> and close with the human 3D acceptance passes. Needs wave 5. Hotspots:
> `generators/zone_spec.py`, `generators/backends.py`, `core/eqg.py` sidecar,
> `generators/pipeline.py` (SINGLE OWNER each).

- [ ] 13. Integration, end-to-end builds, and close
  - [ ] 13.1 Set up wave 6
    - Run `./scripts/new-worktree.ps1 -Branch agent/wild-integrate`. Record the fork-point hash.
    - _Requirements: 13.1_
  - [ ] 13.2 Flow the full pipeline through ZoneSpec to EQG (Z-up)
    - Flow the Design_Matrix, heightfield, water plane, POI anchors, and biome kit through the `ZoneSpec` IR (Req 13.1); write the zone as EQG in the format the project produces (Req 13.2); emit geometry with Z as the up axis (Req 13.3). Wire intent resolution -> matrix -> rewrite -> synth -> biome/water/river/texture -> POI -> gate -> ZoneSpec -> EQG so there is no orphaned stage — a prompt produces a built zone through `generators/pipeline.py`.
    - _Requirements: 13.1, 13.2, 13.3_
  - [ ] 13.3 Write the sidecar advisory data
    - Carry Intent_Tags per region, POI_Anchor names, and biome kit identity in the `.zone.json` sidecar, not the binary (Req 13.4); record Invisible_Wall barriers as sidecar region metadata (`{min_xy, max_xy, kind:"invisible_wall"}`) suitable for later export as region records (Req 13.5). The matrix substitution record (task 3) is emitted here too (Req 1.4).
    - _Requirements: 13.4, 13.5, 1.4_
  - [ ] 13.4 Wire seed/reproducibility and the performance budget
    - A generate without a pinned seed draws a fresh seed (repeated generation differs — Req 14.1); a pinned seed reproduces the same landscape (Req 14.2); a full generate of each v1 pair completes within five minutes (Req 14.3).
    - _Requirements: 14.1, 14.2, 14.3_
  - [ ]* 13.5 Write property test for Property 16: Seeded reproducibility
    - **Property 16: Seeded reproducibility** — generating with the same pinned seed reproduces the same landscape; generating without a pinned seed draws a fresh seed (repeated generation differs). `@pytest.mark.slow` + `build_settings(n)`.
    - **Validates: Requirements 14.1, 14.2**
  - [ ]* 13.6 Write the integration/smoke example tests (not PBT)
    - Example/integration: the sidecar carries intent tags, POI names, biome identity, and invisible-wall regions; the EQG output loads and is Z-up; one timed test asserts a full generate of each v1 pair completes well within five minutes.
    - _Requirements: 13.4, 13.5, 14.3_
  - [ ] 13.7 Walk `docs/ACCEPTANCE.md` — add the wilderness rows
    - Add the new wilderness UAT rows the suite cannot verify (design "Testing Strategy"): desert+oasis reads as an open desert with a central oasis (not a room-graph in a grass skin); plains+river-fork reads as an open plain with a forking river valley; cliffs/shorelines sharp; landmark pad flat and water reads as water with a clean shoreline; scenic backdrops visibly out of reach while every playable POI is walkable. The agent writes the rows; they are human-signed in task 13.8.
    - _Requirements: 14.4_
  - [ ] 13.8 **HUMAN-GATED:** final end-to-end desert+oasis and plains+river-fork 3D pass
    - The user, in the live viewer: build each v1 pair end to end from a prompt and confirm every `docs/ACCEPTANCE.md` wilderness row — the whole zone reads as a hand-crafted open EQ outdoor landscape built around its landmark, walkable where playable, scenic where not, within the time budget. The agent writes the checklist, marks it PENDING-HUMAN, leaves the box unchecked. The spec does not close until this is signed off.
    - _Requirements: 14.4_

- [ ] 14. Checkpoint — wave 6 closed, spec complete
  - Run `python -m pytest tests/ -q` (green) and `cd web; npx vite build`. Confirm all 17 properties pass (matrix 1–10/16/17 pre-geometry, heightfield 11–14, mesh 15), and both HUMAN-GATED final passes (13.8) are signed off. Write the wave-6 and spec-exit integration note (Done-table row, "Pick up here" retiring the spec, commit hash/count, the resolved open decisions: LayoutEngine-vs-sibling, matrix resolution, F2/F4 consumption, spline/erosion params) in Deliverables WITHOUT editing `ROADMAP.md`/`README.md`/`tasks/README.md`. Ask the user if questions arise.
  - _Requirements: 14.4_

## Not in this cut (fast-follow — scoped, not implemented here)

Per requirements.md "Out of scope." Named so v1 stays bounded; these build on the
same v1 core and are NOT tasks in this plan:

- **Fast-follow biomes:** `forest`, `coast`, `tundra` (new BiomeKit entries over
  the same terrain core).
- **Fast-follow landmarks:** `temple`/`ruin`, `lake`, `mountain_pass` (new
  landmark-first construction + rewrite rules).
- **Real water volumes:** walkable-shallows and swimmable-deep volumes — v1 is
  the visual-only flat water plane (Requirement 8).
- **Full hydraulic erosion:** drainage-network simulation replacing
  `SplineDrainage` behind the same `DrainageModel` seam (Requirement 9.4).
- **AI textures by default:** the seam is preserved (Requirement 10.3) but
  procedural stays the zero-key default.
- **Region-record export:** Invisible_Wall barriers are recorded in the sidecar
  (Requirement 13.5); exporting them as live EQEmu region records rides with the
  SQL-export capstone (umbrella M6).

## Notes

- Tasks marked with `*` are optional test sub-tasks and can be deferred for a
  faster first build; core implementation sub-tasks are never marked optional.
  Per the house rule the worker MUST implement unmarked sub-tasks and MUST NOT
  implement `*`-marked ones unless doing the testing pass.
- Each task references the specific requirement sub-clauses it satisfies for
  traceability; every design Correctness Property (1–17) has its own task.
- **Matrix correctness is proven before synthesis:** Properties 1–10 (and 16, 17)
  run on plain matrix data with NO geometry built (waves 1–2), so the open
  landscape is validated as layout before a triangle exists. Heightfield
  properties (11–14) gate wave 3's geometry; the mesh property (15) gates wave 5.
- **Structural + property tests passing is necessary but NOT sufficient.** Every
  geometry-producing wave (3, 4, 5, 6) ends with a HUMAN-GATED 3D pass the agent
  writes and the user signs — the agent never ticks a human gate.
- **Tracker single-writer discipline:** task work updates ONLY this `tasks.md`
  (checkboxes, measurements, hashes, Deliverables). `ROADMAP.md`, `README.md`,
  and `tasks/README.md` are integration state, applied once per landed branch in
  the serialized integration step from the MAIN checkout — each wave's checkpoint
  writes its integration note here for that step, never edits those files.
- **Blocked-until-runway:** any wave whose followup predecessor (F1/F2/F4) is not
  on `master` is blocked — the worker stops and surfaces it rather than
  reinventing the seam (see the HARD PREREQUISITE table).

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "3.1"] },
    { "id": 3, "tasks": ["3.2", "3.3", "3.4", "3.5", "3.6"] },
    { "id": 4, "tasks": ["5.1", "5.2"] },
    { "id": 5, "tasks": ["5.3", "5.4"] },
    { "id": 6, "tasks": ["5.5", "5.6", "5.7", "5.8", "5.9", "5.10"] },
    { "id": 7, "tasks": ["7.1", "7.2"] },
    { "id": 8, "tasks": ["7.3", "7.4"] },
    { "id": 9, "tasks": ["7.5", "7.6", "7.7", "7.8", "8.1"] },
    { "id": 10, "tasks": ["9.1", "9.2", "9.3", "9.4"] },
    { "id": 11, "tasks": ["9.5", "9.6", "10.1"] },
    { "id": 12, "tasks": ["11.1", "11.2", "11.3"] },
    { "id": 13, "tasks": ["11.4", "12.1"] },
    { "id": 14, "tasks": ["13.1", "13.2", "13.3", "13.4"] },
    { "id": 15, "tasks": ["13.5", "13.6", "13.7"] }
  ]
}
```
