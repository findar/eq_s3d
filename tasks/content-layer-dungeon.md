# TASK: content-layer-dungeon

Status: in-progress        <!-- not-started | in-progress | blocked | done -->
Epic: Content / semantic layer (ROADMAP "Next" #1)
Last touched: picking up after commit 9f69d1f (166 tests passing)

## Goal

Give dungeon rooms a semantic identity so a zone reads as a coherent *place* with
a progression — realised through the existing pipeline, no new art. Rooms get a
type + theme (archetype × race × elemental tint); the theme drives region
volumes, lighting, textures, and shape; prop/spawn/boss intent is emitted as
*suggestions* (data only, never placed MODs).

## Current state (Step 1 — DONE, commit 1f155b6)

`generators/semantics.py` implements the whole first cut and it's wired in:
- **ROOM_TYPES** catalogue, **ARCHETYPES** arc vocabulary (fortress, war_city,
  warren, temple, tomb, wizard_lair, corrupted_sanctum, mine_delve, sunken_ruin,
  lava_forge, ice_keep), **RACE_SCALE**, elemental **TINT** palettes.
- `label_rooms()` assigns each room a `semantic_type` from the archetype arc,
  anchored by the pacing role + graph depth; `realize_semantics()` applies
  materials, region volumes, and lights. Only runs for box themes (dungeon/city).
- Plumbed through `ZonePlan` (`dungeon_theme`/`dungeon_race`/`elemental_tint`),
  `plan_to_spec`, `LayoutGenerator.generate(...)`, `RoomSpec`
  (`semantic_type`/`room_theme`/`district`/`prop_hints`/boss), the `.zone.json`
  sidecar, and the top-down map labels.
- Rule planner detects archetype/race/tint words. `TestSemantics` +
  `TestPlanner` cover it. Design note in `docs/RESEARCH.md`.

## Acceptance criteria

- [x] Each dungeon room gets a `semantic_type` + `room_theme`, coherent with the
      pacing graph (entrance/climax map to arc endpoints)
- [x] Theme drives region volume / lighting / texture; no prop MODs placed
- [x] Suggestions (prop hints, boss) emitted as spec data, shown in viewer + map
- [x] Automated tests green (166 passing)
- [ ] **ACCEPTANCE.md A/E confirmed in the 3D viewer** for several archetypes +
      seeds (NOT yet done — the automated pass ≠ a human 3D pass; see cave lesson)
- [ ] Rooms stay navigable/enclosed with semantic shape bias applied (spot-check
      in 3D, not just the walkable-floor test)

## Subtasks

- [x] Research theme vocabulary & districts (commit bb97abe)
- [x] Implement semantics module + wiring — Step 1, single district (commit 1f155b6)
- [ ] **Human 3D validation pass (Step 1)** across archetypes (fortress / temple /
      sunken_ruin / lava_forge / ice_keep) and a few seeds — confirm it reads as a
      coherent place, regions/lights land right, rooms stay walkable & enclosed.
      Log findings here. (Structural tests pass, but per the cave lesson that is
      necessary-not-sufficient.)
- [ ] Address any issues the 3D pass surfaces.
- [ ] **Step 2 — districts** (the live next build; design already decided in
      `docs/RESEARCH.md` "Multi-area zones — districts"):
  - [ ] Graph partition on the pacing graph (multi-source BFS/cut); auto-split
        ≥8 rooms → 2, ≥14 → 3 (cap 3), with an off switch / `multi_district` control.
  - [ ] Per-district sub-theme + its own entrance→climax arc (climax is per-district).
  - [ ] District boundary = threshold corridor; reuse gating for an optional
        locked door; flip palette/light sharply across the boundary.
  - [ ] IR: `RoomSpec.district`/`district_theme` (exist), add `ZoneSpec.districts:
        List[DistrictSpec]`; `ZonePlan` optional district proposals; deterministic
        partitioner with sensible defaults when the planner is silent.
  - [ ] Render district boundaries in the top-down map + viewer.
  - [ ] Tests + a separate 3D validation pass.
- [ ] Sync ROADMAP + README when Step 2 lands.

## Deliverables

- Code: `generators/semantics.py`, `generators/layout.py`, `generators/zone_spec.py`,
  `ai/schema.py`, `ai/rule_planner.py`, `ai/expand.py`, `generators/mapview.py`
- Tests: `tests/test_generators.py::TestSemantics`, `tests/test_planner.py`
- Docs: `docs/RESEARCH.md` (theme vocabulary + districts design); ROADMAP in sync
- Commits: bb97abe, 1f155b6 (Step 2 commits as they land)

## Notes / decisions / blockers

- Step 2 design + user decisions are already captured in `docs/RESEARCH.md`
  ("Multi-area zones — districts") and ROADMAP — don't re-derive them.
- Semantic labelling only runs for box themes (dungeon/city); cave/outdoor are
  untouched (cave is shelved — see ROADMAP).
- IMPORTANT: this task file was reconstructed by inspecting the repo — the code
  had advanced past the stale session summary. Step 1 is BUILT; the remaining
  Step 1 work is the **human 3D validation**, then Step 2 (districts) is the next
  build. VERIFY the code state before assuming, as it may have moved again.
