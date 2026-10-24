# Implementation Plan: M1 — Controls + all-zone-type traversability + format gate

## Overview

This plan implements `requirements.md` and `design.md` in this folder. "Req X.Y"
means this spec's criterion. "Property N" means this spec's design Correctness
Property N (the design's umbrella/M1 tag follows in brackets, e.g. Property 10
is M1-P1). "Pn" means the umbrella (`zone-generator`) property. "Decision N"
means this spec's design Decision N. Umbrella design decision 19 applies: new
code uses `zone_type` / `wilderness`; until wave 2 lands, the code still says
`theme` / `outdoor`.

The plan follows the design's six delivery waves, in order. Each wave is one
branch in its own worktree, merged to `master` before the next wave starts.
Within a wave, steps are ordered so each one can be committed on its own and the
suite stays green after each commit (exceptions are named in the task).

| Wave | Tasks | Branch | Hotspot owner |
|------|-------|--------|---------------|
| 1 Connectivity | 1–9 | `agent/m1-connectivity` | none (`analyzer/traverse.py`, `generators/{routing,geometry,layout}.py`, `scripts/`, `tests/`) |
| 2 Rename | 10–11 | `agent/m1-rename` | `server/app.py`, `main.py`, `generators/pipeline.py` |
| 3 Wilderness | 12–14 | `agent/m1-wilderness` | `generators/builder.py` (not a listed hotspot; one owner anyway) |
| 4 Gate + availability | 15–16 | `agent/m1-gate` | `generators/pipeline.py`, `server/app.py` |
| 5 Controls + modes | 17–18 | `agent/m1-modes` | `server/app.py`, `main.py`, `ai/schema.py` |
| 6 Naming + format + confinement | 19–21 | `agent/m1-format` | `generators/pipeline.py`, `server/app.py`, `main.py` |
| Exit | 22 | MAIN checkout after wave 6 merges | none |

`requirements.txt` changes in no wave (`python-dotenv` is already pinned;
`sys.addaudithook` is stdlib), so no wave needs `-Venv`. No wave changes
`web/package.json`, so the shared `web/node_modules` junction is fine.

Working rules for every task:

- Create each wave's worktree from the MAIN checkout with
  `./scripts/new-worktree.ps1 -Branch agent/m1-<wave>`. Stay in it. Don't push
  the branch. Tear down only with `./scripts/remove-worktree.ps1`.
- Commit one logical change at a time. Write the message to
  `.git/COMMIT_EDITMSG_TMP`, run `git commit -F .git/COMMIT_EDITMSG_TMP`, then
  delete the file. Messages must not contain the words blocked by the
  commit-message hook (the frontend tool name and "dev server").
- Tracker writes go to this `tasks.md` only (checkboxes, measurements, hashes,
  Deliverables). Don't edit `ROADMAP.md`, `README.md` or `tasks/README.md`;
  those changes go in the integration notes (each wave's close and task 22.6).
- Run `python -m pytest tests/ -q` before each commit. After any `web/` change
  run `cd web; npx vite build`.
- A failing property is a real bug: fix it at the root and pin the
  counterexample as a Regression_Example (`@example(...).via("discovered
  failure")`). Never weaken an assertion, never `xfail`, never `assume` a
  builder exception away. Record every seed a fix moved for the 3D pass.
- Every property test has a docstring starting
  `Feature: zone-generator-m1-controls-traversability, Property N: <title>`,
  naming the umbrella Pn or M1-Pn and the requirement ids. Build-level property
  tests use `@pytest.mark.slow` and `build_settings(n)` (n 10–25); others run
  ≥ 100 examples under the default profile.
- Human-gated subtasks (marked **HUMAN-GATED**) are signed off by the user in
  the live 3D viewer or browser. The agent writes the checklist, marks it
  PENDING-HUMAN and leaves the checkbox unchecked. The agent never ticks one.

## Tasks

### Wave 1 — Large-zone connectivity (Requirement 5)

- [x] 1. Set up wave 1 and capture the fork-point baselines
  - [x] 1.1 Create the worktree and record timing baselines
    - Run `./scripts/new-worktree.ps1 -Branch agent/m1-connectivity`. Record the fork-point commit hash here.
    - On the fork-point code, time `analyzer.traverse.validate` for a 12-room dungeon, a 30-room dungeon and a 6-room outdoor zone (seed 7). Record the three times (design finding 4: ≈ 2.1 s, 3.4 s, 118 s).
    - Run `python -m pytest tests/ -q` 3 times, deleting `.hypothesis/` before each run. Record the median: it is the M0-exit baseline for the "+120 s" budget lever.
    - _Requirements: 5.1_
  - [x] 1.2 Capture the routing-refactor hashes and the Decision 13 "before" layouts
    - With a throwaway script outside the repo (not committed), on the fork-point code, build TER bytes for dungeon and city × seeds 7 / 1955208177 / 1516796975 / 481893615 × rooms 12 and 30 × elevation on and off (32 builds). Record each `sha256(ter_bytes)` here.
    - Reproduce the M0 human-pass inputs: `RulePlanner().plan("create a dungeon with 30 rooms")` with seed 1949459644 and `RulePlanner().plan("a dungeon with 30 rooms and long halls")` with seed 1510177507, through `plan_to_spec` + `ZoneBuilder`. Record for each: room count, corridor count, the number of corridors that cross a third room and of corridor pairs that cross (finding 2 method), and the `.map.svg` path. These are the "before" half of Decision 13.
    - _Requirements: 5.5_

- [x] 2. Speed up the walk surface without changing reachability
  - [x] 2.1 Add the fork-point reference validator
    - Create `tests/reference_traverse.py`: a verbatim copy of the fork-point `build_walk_surface`, `flood_reachable` and the helpers they call from `analyzer/traverse.py`, with a header comment naming the fork-point commit and saying it is test-only and never edited.
    - Done when it imports standalone and reproduces the fork-point `validate` room results on one dungeon build.
    - _Requirements: 5.2_
  - [x] 2.2 Implement the union-find speed-up in `analyzer/traverse.py`
    - `build_walk_surface`: keep a union-find over standable faces; the shared-vertex pass unions as it adds edges; the seam pass skips a candidate pair when `find(fi) == find(fj)` before calling `_tri_tri_xy_contact`, and unions on every accepted edge.
    - Restrict seam candidates to faces whose weld component touches another component's XY bounding box; vectorise `_cells_for` with numpy; skip the per-cell pair loop for cells holding one component.
    - Add `WalkSurface.component: np.ndarray` (root per standable face).
    - Re-time the three 1.1 cases and record them against the targets (≤ 1.0 s for a 30-room dungeon, ≤ 15 s for a 12-room wilderness/outdoor zone). If a target is missed, record the measured numbers here before any budget is widened.
    - _Requirements: 5.1, 5.2_
  - [x] 2.3 Write property test for Property 13: The faster walk surface has the same reachability (M1-P4)
    - `tests/test_properties_core.py::test_walk_surface_equivalence`, `slow`, budget 10, over box zone types, n 2–30 and all verticalities (wilderness 2–6 is added in 13.7).
    - Assert that the optimised and reference walk surfaces have the same standable faces in the same connected components, that `flood_reachable` agrees from every start face, and that every `TraversalReport` room result is equal. (Continuity equality is added in 4.2.)
    - **Validates: Requirements 4.1, 5.2**

- [x] 3. Route every corridor through one function
  - [x] 3.1 Add `generators/routing.py` and switch both callers to it (byte-identical)
    - Implement `Route`, `plan_route(from_xy, to_xy, exit_from_x, exit_to_x, hw, steps)`, `corridor_route(cor, rooms)` and `route_footprint(route, hw)` per the design. Make `MeshBuilder.add_corridor` (`generators/geometry.py`) and `LayoutGenerator._route_legs` (`generators/layout.py`) call it; `_emit_route` keeps its body.
    - Re-run the 1.2 throwaway script on the refactor and confirm all 32 TER hashes are identical. Record the before/after hashes and the result in Deliverables. Don't commit the script or a hash test (wave-1 fixes are meant to move geometry).
    - Done when the suite is green and all 32 hashes match.
    - _Requirements: 5.5_

- [x] 4. Corridor floor continuity and corridor conflicts
  - [x] 4.1 Implement `corridor_continuity` and the conflict check in `analyzer/traverse.py`
    - Add `CorridorResult` and `corridor_continuity(surf, spec, agent)` per the design's five steps: region = route footprint (grown by `agent.adjacency_eps`) ∪ both room footprints, minus every other room's footprint; flood restricted to the region's standable faces; `reason` in `""`, `"no floor in from_room"`, `"no floor in to_room"`, `"gap"`, `"crosses room <id>"`.
    - Add the corridor–corridor conflict check (Decision 12): two corridors that share no room conflict when their route footprints intersect in XY **and** their walkable floors over the intersection are closer in Z than the clearance. Use the clearance and reporting shape of design Decision 16; a pair separated by at least the clearance is not a conflict, so a future bridge kind is exempt by construction.
    - `validate(..., check_corridors=False)` fills `TraversalReport.corridors` (and the conflict list) when asked; add `TraversalReport.corridors_passed` (all connected and no conflicts; `True` when not checked). `TraversalReport.passed` keeps its meaning.
    - _Requirements: 5.2_
  - [x] 4.2 Extend the Property 13 test to continuity results
    - In `test_walk_surface_equivalence`, also assert that `corridor_continuity` gives equal results (including conflicts) on the optimised and reference surfaces.
    - Design Decision 15: `corridor_continuity` computes seam contacts locally for its region's faces and never uses the pruned adjacency, so the results must match; a mismatch is a bug in the continuity flood, not the property.
    - **Validates: Requirements 4.1, 5.2**
  - [x] 4.3 Add constructed example tests for continuity
    - In `tests/test_traversability.py`, hand-built specs: a corridor whose route runs through a third room reports `crosses room <id>`; a corridor with a missing floor segment reports `gap`; two unrelated corridors crossing at the same height conflict; the same pair separated in Z by more than the clearance does not.
    - _Requirements: 5.2_

- [x] 5. Measure before fixing
  - [x] 5.1 Add and run `scripts/sweep_connectivity.py`
    - New committed script: dungeon and city × rooms 12 / 20 / 30 × flat and elevation × 200 seeds, built through `plan_to_spec` + `ZoneBuilder` + `validate(check_corridors=True)`. Report counts and seeds per failure class: `gap`, `crosses room`, `no floor`, inverted stub (`fx` past `tx`, computed from the spec), corridor–corridor conflict, plus P1 failures.
    - Record the per-class table and representative seeds here before any fix. No fix lands in this task.
    - _Requirements: 5.2, 5.3, 5.4_

- [x] 6. Flat first: widen the properties and fix flat failures at the root
  - [x] 6.1 Add the wave-1 strategies and constants
    - `tests/strategies.py`: `room_counts_wide = st.one_of(st.integers(2, 12), st.integers(13, 30))`, `flat_only = st.just("flat")`, `verticality_all`.
    - Add `M0_HUMAN_PASS = (("create a dungeon with 30 rooms", 1949459644), ("a dungeon with 30 rooms and long halls", 1510177507))` to `tests/pbt_helpers.py`, plus a helper that turns an entry into a spec through `RulePlanner` + `plan_to_spec`, with an optional verticality override.
    - _Requirements: 5.1, 5.3_
  - [x] 6.2 Write property test for Property 1: Raw builds are navigable (umbrella P1), flat
    - Rename `test_properties_build.py::test_raw_dungeon_navigable` to `test_raw_navigable`. Draw box zone types, `room_counts_wide` and `flat_only`, building through `plan_to_spec`; budget 15. Pin both `M0_HUMAN_PASS` inputs re-planned flat with `@example(...).via("M0 human pass")`.
    - Done when green with no weakened assertion.
    - **Validates: Requirements 4.1, 5.1, 5.3**
  - [x] 6.3 Write property test for Property 10: Corridor floor continuity (M1-P1), flat
    - New `test_properties_build.py::test_corridor_continuity`, same domain and examples as 6.2, budget 15. Assert every `CorridorResult.connected` and no conflicts, printing failing corridor ids and reasons.
    - **Validates: Requirements 5.2, 5.3**
  - [x] 6.4 Write property test for Property 3: Flush openings through 30 rooms (umbrella P7), flat
    - Widen `test_properties_layout.py::test_flush_openings` to `room_counts_wide` with elevation off (elevation draws return in 8.2). Budget stays 50.
    - **Validates: Requirements 5.1, 5.5**
  - [x] 6.5 Fix flat failure classes at the root
    - Take each failure class 5.1 and 6.2–6.4 found, in turn, and fix it in `generators/layout.py` / `generators/geometry.py` / `generators/routing.py`, choosing from the design's suspect table only after measuring (e.g. inverted stub → choose the wall by footprint separation in `_wall_point`, mirrored in `plan_route`; third-room crossing → split the edge A–B into A–C–B in `_connect_rooms`; corridor conflicts → the same).
    - One commit per class, each with its Regression_Example(s). Re-run `scripts/sweep_connectivity.py` (flat) after each and record the per-class counts and the seeds whose geometry moved.
    - Keep Req 5.1–5.6 and the Room_Graph properties (umbrella P3, P4, P6) green; an edge split changes the graph, so those run unchanged on it.
    - Done when the flat sweep shows zero failures in every class and 6.2–6.4 are green. Leave unchecked with "not triggered" if nothing failed.
    - _Requirements: 5.3, 5.5_

- [x] 7. Checkpoint: flat connectivity proven
  - [x] 7.1 Run the suite and check the budget
    - `python -m pytest tests/ -q` green. Run it 3 times (deleting `.hypothesis/`), record the median against the 1.1 baseline. If it grew by more than 120 s, apply the design's levers in order (shared P1/M1-P1 build cache; wilderness budgets; 2:1 small:large bias) and re-measure.
    - _Requirements: 5.1, 5.3_
  - [x] 7.2 **HUMAN-GATED:** flat 30-room 3D pass
    - Write this checklist here and mark it PENDING-HUMAN. The user, in the live viewer with Elevation unchecked: flat 30-room dungeons (and one city) walk end to end; every corridor meets both its rooms; no corridor runs through a room or another corridor; checked on `M0_HUMAN_PASS` seeds 1949459644 and 1510177507 re-planned flat and on every seed a 6.5 fix moved.
    - No elevation draw (task 8) lands until the user signs this off.
    - _Requirements: 5.3_

- [x] 8. Then elevation: widen to all verticalities and fix at the root
  - [x] 8.1 Extend the Property 1 and Property 10 tests to all verticalities
    - Switch `test_raw_navigable` and `test_corridor_continuity` from `flat_only` to `verticality_all`. Add the `M0_HUMAN_PASS` inputs as originally planned (no override) as `@example`s, keeping the flat ones.
    - **Validates: Requirements 4.1, 5.1, 5.2, 5.4**
  - [x] 8.2 Write property test for Property 4: Ramp subdivision through 30 rooms (umbrella P8), and restore elevation in Property 3
    - Widen `test_ramp_subdivision` to box zone types, `room_counts_wide`, moderate/dramatic, budget 20. Restore the elevation flag draw in `test_flush_openings` (`room_counts_wide`, budget 50).
    - **Validates: Requirements 5.1, 5.5**
  - [x] 8.3 Fix elevation failure classes at the root
    - Same procedure as 6.5 with the sweep's elevation half (e.g. a carry leg lying inside a room → carry on the jog, if the inverted-stub fix didn't remove it). One commit per class with Regression_Examples; record moved seeds. Flat properties stay green.
    - Done when the full sweep (flat and elevation) shows zero failures and 8.1–8.2 are green. Leave unchecked with "not triggered" if nothing failed.
    - _Requirements: 5.4, 5.5_

- [x] 9. Checkpoint: wave 1 closed
  - [x] 9.1 Record the one-time seed break (Decision 13)
    - Rebuild the two `M0_HUMAN_PASS` inputs on the branch head and record the "after" numbers next to the 1.2 "before" numbers (rooms, corridors, third-room crossings, corridor crossings, `.map.svg` path), the fix commits that moved them, and the full list of moved seeds from 6.5 and 8.3. State that pinned seeds saved before M1 are not expected to reproduce.
    - _Requirements: 5.4_
  - [x] 9.2 Run the suite and re-check the budget
    - Suite green; Default_Run median recorded as in 7.1.
    - _Requirements: 5.1_
  - [x] 9.3 **HUMAN-GATED:** elevation 30-room 3D pass
    - Checklist, PENDING-HUMAN: elevated 30-room dungeons walk end to end; ramps land flush at both openings; no corridor runs through a room or another corridor; checked on the `M0_HUMAN_PASS` inputs as originally planned and on every seed an 8.3 fix moved.
    - _Requirements: 5.4_
  - [x] 9.4 Write the wave-1 integration note (don't apply it)
    - Done-table row, "Pick up here" line, commit hash and count, and the moved-seed list from 9.1. Wave 2 starts only after the merge to `master`.
    - _Requirements: 5.4_

### Wave 2 — Zone-type rename (Requirement 11)

- [ ] 10. Rename `theme` → `zone_type` and `outdoor` → `wilderness`
  - [ ] 10.1 Create the worktree and capture the "before" hashes
    - `./scripts/new-worktree.ps1 -Branch agent/m1-rename`. With the 1.2 throwaway script, record the 32 box TER hashes plus outdoor seeds 7 / 1955208177 / 2147483647 at 6 rooms on the fork point of this wave.
    - _Requirements: 11.1_
  - [ ] 10.2 Add `generators/zone_types.py`
    - `DEFINED_ZONE_TYPES`, `DEFAULT_ZONE_TYPE`, `LEGACY_ZONE_TYPE_VALUES`, `STYLE_PROFILE` (`wilderness` → `outdoor`), `canonical_zone_type`, `read_zone_type` per the design. No Enabled set yet (wave 4).
    - _Requirements: 11.1, 11.2_
  - [ ] 10.3 Rename the plan and planner surface
    - `ai/schema.py`: `VALID_ZONE_TYPES = list(DEFINED_ZONE_TYPES)`, `ZonePlan.zone_type`, schema key `zone_type`; `from_dict`/`validate()` read `read_zone_type` → `canonical_zone_type` → `dungeon` if undefined. `ai/rule_planner.py`: `_ZONE_TYPE_WORDS` keyed `wilderness` (word list unchanged), `_match_zone_type`, same scoring and tie rule. `ai/llm_planner.py`: prompt text and enum. `ai/expand.py`: `LayoutGenerator(zone_type=...)`, `style_profile = STYLE_PROFILE[plan.zone_type]`.
    - Content fields keep their names (Req 11.6). 10.3–10.8 may land as one commit if splitting would leave the suite red; say so in the message.
    - _Requirements: 11.1, 11.2, 11.6_
  - [ ] 10.4 Rename the spec, layout, builder and pipeline surface
    - `generators/zone_spec.py`: `ZoneSpec.zone_type`; `from_dict` prefers `zone_type`, accepts `theme`, maps `outdoor` → `wilderness` and undefined → `dungeon`. `generators/layout.py`: `LayoutGenerator(zone_type)`, `self.zone_type`, per-type tables keyed `wilderness`, `load_style_profile(STYLE_PROFILE[...])`. `generators/builder.py`: `_TERRAIN_THEMES` → `{"wilderness"}` (replaced by the registry in 12.2). `generators/pipeline.py`: `zone_type=`, `gated_zone_types`, `DEFAULT_GATED_ZONE_TYPES = frozenset({"dungeon"})` until wave 4, JSONL key `zone_type`.
    - _Requirements: 11.1, 11.2_
  - [ ] 10.5 Move the Sidecar content block
    - `core/eqg.py::_write_glb_sidecar`: write `"content": {dungeon_theme, dungeon_race, elemental_tint}` and `"zone_type"`; no `theme` key.
    - _Requirements: 11.1, 11.6_
  - [ ] 10.6 Rename the Server surface
    - `server/app.py`: drop the duplicate `VALID_THEMES`; `GenerateRequest` accepts `zone_type` and legacy `theme` (preferring `zone_type`, `outdoor` → `wilderness`); `GenerateResponse.zone_type`; `GET /api/zone_types` with `GET /api/themes` as an alias (one handler, same body). Body shape for this wave: see the decision note below.
    - Decision note (the design only gives the wave-4 body): until wave 4 adds the Enabled set, serve `{"zone_types": [<DEFINED names>], "default": "dungeon", "reference_zones": ...}`; wave 4 replaces the list with `zone_type_listing()` objects.
    - _Requirements: 11.1, 11.2, 11.4_
  - [ ] 10.7 Rename the CLI option
    - `main.py`: `--zone-type` and deprecated `--theme` share `dest="zone_type"`, both accept legacy `outdoor`; help text marks `--theme` deprecated; later option wins.
    - _Requirements: 11.3_
  - [ ] 10.8 Relabel the Web_App
    - `web/`: `#theme` → `#zone-type`, `m-theme` → `m-zone-type`, `result.zone_type`, `sidecar.content ?? sidecar.theme` for old sidecars, list fetched from `/api/zone_types`. Run `cd web; npx vite build`.
    - _Requirements: 11.1_
  - [ ] 10.9 Retarget the tests and add the rename guards
    - Rename test-side identifiers (`box_themes` → `box_zone_types`, etc.); keep M0 docstring tags. `tests/test_hygiene.py::test_theme_surface_is_three` → `test_zone_type_surface_is_three` (schema, web options, CLI choices, server listing all equal `DEFINED_ZONE_TYPES`). Add a guard: no `"theme"` key in `ZonePlan.to_dict()`, `ZoneSpec.to_dict()`, the Sidecar or any `GenerateResponse` field; content fields still present. Add CLI examples: `--theme outdoor` ≡ `--zone-type wilderness`; `/api/zone_types` body equals `/api/themes` body.
    - _Requirements: 11.1, 11.3, 11.4, 11.6_
  - [ ] 10.10 Write property test for Property 12: Legacy vocabulary load round-trip (M1-P3)
    - `tests/test_properties_layout.py::test_legacy_vocabulary_round_trip`, budget 100. `zone_plan_dicts` gains `zone_type` and `theme`. For plans from `from_dict` and specs from `plan_to_spec` (all three zone types): `to_dict()` has `zone_type`, no `theme` and no `outdoor`; renaming to `theme`/`outdoor` and reloading gives an equal value; with both keys present and different, `zone_type` wins.
    - **Validates: Requirements 11.1, 11.2, 11.5**
  - [ ] 10.11 Confirm the rename moved no geometry
    - Re-run the 10.1 script on the branch head; all 35 hashes must match. Record them in Deliverables. `test_outdoor_ter_matches_fork_point` still passes unchanged.
    - _Requirements: 11.1_

- [ ] 11. Checkpoint: wave 2 closed
  - Suite green; frontend builds; 10.11 hashes match. Write the wave-2 integration note (Done-table row, "Pick up here" line, commit hash and count). Ask the user if questions arise.

### Wave 3 — Backend registry and wilderness terrain (Requirements 6, 7)

- [ ] 12. Geometry backend registry
  - [ ] 12.1 Create the worktree and record wilderness timings
    - `./scripts/new-worktree.ps1 -Branch agent/m1-wilderness`. Record build and validate times for wilderness at 2 / 6 / 12 rooms (seed 7) on this fork point.
    - _Requirements: 6.1_
  - [ ] 12.2 Add `generators/backends.py` and route `ZoneBuilder` through it
    - `GeometryBackend` protocol, `BoxBackend`, `TerrainBackend` (returns `None` when its `numpy` import fails), `BACKENDS` keyed by `DEFINED_ZONE_TYPES`, `backend_for` (undefined → dungeon). `ZoneBuilder._build_geometry` uses `backend_for(spec.zone_type)`; on `None` it builds with `BoxBackend` and appends `"backend_fallback: <name> unavailable, built with box"` to new `BuildResult.warnings`; add `BuildResult.backend`. Delete `_TERRAIN_THEMES`. No cave backend.
    - _Requirements: 4.3, 7.1_
  - [ ] 12.3 Add the fallback and no-cave tests
    - `tests/test_pipeline.py`: monkeypatch `TerrainBackend.build` to return `None`; a wilderness build succeeds with `backend == "box"` and the `backend_fallback` warning. `tests/test_hygiene.py`: `BACKENDS` keys equal `DEFINED_ZONE_TYPES` and contain no `cave`.
    - _Requirements: 4.3, 7.1_

- [ ] 13. Wilderness terrain in the Room_Graph frame
  - [ ] 13.1 Generate terrain in the Room_Graph frame with the floor material
    - `generators/field/terrain.py::build_terrain(spec, name, rooms, corridors, material)`: bounds from rooms and route footprints minus `margin = max(600, 2·res)`, `x0, y0` snapped down to multiples of `res`, vertices at `(x0 + i·res, y0 + j·res)`; noise/erosion/`_enforce_walkable` evaluated at world coordinates. The terrain uses the spec's `floor` MaterialSpec, so its texture is packed (fixes the missing `ground.dds`, design finding 5). Update `ZoneBuilder` and `tests/test_terrain.py` callers.
    - Delete `tests/test_hygiene.py::test_outdoor_ter_matches_fork_point` in this commit, saying in the message that the frame change retires the M0 baseline by design.
    - _Requirements: 6.1_
  - [ ] 13.2 Cap the wilderness grade at 0.1
    - `generators/layout.py`: `self.max_grade = 0.1` for `wilderness`, 0.5 otherwise, used by `_assign_elevation`, `_relax_elevation` and `_elevation_run`. Box zone types unchanged.
    - _Requirements: 6.2_
  - [ ] 13.3 Add graded corridor paths, room pads and frozen re-walkability
    - Paths first (`corridor_route` from wave 1; linear `h_path` along arc length; weight 1 within `hw + res`, smoothstep falloff over `L = max(2·res, |Δh| / 0.5)`), then pads (room footprint grown by `res`, same falloff), then `_enforce_walkable` again with weight-1 cells frozen. `build_terrain` never writes the specs.
    - _Requirements: 6.1, 6.2_
  - [ ] 13.4 Add the terrain sampling helper
    - `tests/pbt_helpers.py::terrain_samples(ter, route)`: terrain heights along a route centreline, one grid step apart, plus the triangles intersecting the route footprint.
    - _Requirements: 6.2_
  - [ ] 13.5 Write property test for Property 6: Wilderness terrain sits under the Room_Graph (umbrella P18)
    - `test_properties_build.py::test_wilderness_frame_and_pads`, `slow`, budget 10, seed × n 2–12: TER XY bounds contain every room footprint and route footprint grown by one sample spacing; every vertex inside a room footprint is within `floor_z` ± 1 u; `spec.to_dict()` is equal before and after `ZoneBuilder.build`.
    - **Validates: Requirements 6.1, 6.2**
  - [ ] 13.6 Write property test for Property 11: Wilderness corridor paths are walkable and continuous (M1-P2)
    - `test_properties_build.py::test_wilderness_corridor_paths`, `slow`, budget 10: triangles intersecting a route footprint have slope ≤ 40° and edge-adjacent centroids within 3 u in Z; centreline samples differ by ≤ `max_grade · res + 0.01` and end within ± 1 u of both rooms' `floor_z`.
    - **Validates: Requirements 6.2**
  - [ ] 13.7 Extend Properties 1, 10 and 13 to wilderness
    - Add separate wilderness `@given`s to `test_raw_navigable` and `test_corridor_continuity` (n 2–12, budget 10) and wilderness n 2–6 to `test_walk_surface_equivalence`. `test_seed_determinism` (P9) draws `wilderness` in the new frame. Fix any failure at the root (in terrain or, for third-room/conflict classes, in the wave-1 layout fixes).
    - **Validates: Requirements 4.1, 5.2, 6.3**
  - [ ] 13.8 Record wilderness timings
    - Build and validate times for 2 / 6 / 12 rooms on the branch head, against 12.1 and the ≤ 15 s target.
    - _Requirements: 6.1_

- [ ] 14. Checkpoint: wave 3 closed
  - [ ] 14.1 Run the suite and write the wave-3 integration note
    - Suite green; Default_Run median recorded (levers as in 7.1). Integration note: Done-table row, "Pick up here" line, commit hash and count, and the retired outdoor baseline.
    - _Requirements: 6.3_
  - [ ] 14.2 **HUMAN-GATED:** wilderness 3D pass
    - Checklist, PENDING-HUMAN: wilderness zones at 2 / 6 / 12 rooms; rooms sit on flat pads; corridor paths read as graded trails; nothing floats or is buried; the ground texture is present; the zone walks end to end.
    - _Requirements: 6.1, 6.2_

### Wave 4 — Gate city and wilderness from one Enabled set (Requirements 3, 4)

- [ ] 15. All-zone-type gate and availability
  - [ ] 15.1 Create the worktree
    - `./scripts/new-worktree.ps1 -Branch agent/m1-gate`. Record the fork-point hash.
    - _Requirements: 4.2_
  - [ ] 15.2 Add the Enabled set and the listing to `generators/zone_types.py`
    - `ENABLED_ZONE_TYPES = frozenset({"dungeon", "city"})` for now (wilderness joins in 15.8), `ZONE_TYPE_REASONS`, `DISABLED_REASON`, `is_enabled` (reads the set at call time), `zone_type_listing()` in DEFINED order.
    - _Requirements: 3.1, 3.2_
  - [ ] 15.3 Write the Sidecar on every build
    - Add `EqgZone.write_sidecar(path, *, rooms, gates, content, extra)` in `core/eqg.py`; `ZoneBuilder.build` writes `<name>.zone.json` whether or not `write_glb` is set; add `BuildResult.sidecar_path` and `map_path`. Decision note: the design lists this under wave 6, but the wave-4 Pipeline merges the gate results into the Sidecar and Property 2 asserts on it, so it lands here. Wave 6 adds the Build_Name check on top.
    - _Requirements: 4.2_
  - [ ] 15.4 Rebuild `generate_validated` with scratch attempts and the continuity gate
    - `generators/pipeline.py` per the design: new signature (`version`, `timeout_s=None` ⇒ `DEFAULT_TIMEOUT_S[zone_type]`, `gated_zone_types=None` ⇒ `ENABLED_ZONE_TYPES`, `warnings`); each attempt builds into `output_dir/.attempts/<zone_id>/a<k>/`; pass ⇔ `report.passed ∧ report.corridors_passed ∧ fmt.passed` with a passing `fmt` stub until 20.3; on pass `os.replace` every file into `output_dir/<zone_id>/v<version>/`, merge `format`, `warnings`, `validated`, `attempts`, `seed` into the Sidecar, remove the scratch and its empty parent; on fail log the JSONL line (with `checks`) and `shutil.rmtree` the scratch; builder exceptions remove the scratch in `finally` and re-raise; ungated builds run once through the same path marked `validated=False`.
    - `ValidatedBuild` gains `zone_type`, `build_dir`, `format`, `warnings`; `AttemptFailure.checks`; `GenerationFailed(zone_id, zone_type, ...)` lists each rejected seed with its failed checks. Remove `DEFAULT_GATED_ZONE_TYPES`.
    - Plain `pathlib` writes for now; 19.5 routes them through `OutputRoot`.
    - _Requirements: 4.2, 3.4_
  - [ ] 15.5 Gate and list zone types in the Server, and serve per-build paths
    - `server/app.py`: `/api/zone_types` and `/api/themes` return `{"zone_types": zone_type_listing(), "default": "dungeon", "reference_zones": ...}`. A controls zone type whose `canonical_zone_type` is not enabled (including `cave`) → 400 listing the enabled set, before any write. A prompt-planned disabled zone type → built as `dungeon` with `zone_type_substituted:<planned>->dungeon` and `planned_zone_type` passed to the Pipeline for the Sidecar. Pass `warnings` through; add `warnings` to the response.
    - Replace the flat `/api/zones/{filename}` route with `/api/zones/{zone_id}/{version}/{filename}` (segment regex, no `..`, extension allow-list, resolved path inside `OUTPUT_DIR`); response URLs point at `<zone_id>/v1/<zone_id>.*`. Decision note: the design's wave table puts per-build directories in wave 6, but its wave-4 Pipeline already moves accepted files into `<zone_id>/v<version>/`, so the route moves with it here. `main.py` is untouched in this wave beyond what the new `generate_validated` signature forces.
    - _Requirements: 3.1, 3.3, 3.4_
  - [ ] 15.6 Write property test for Property 2: Returned builds passed both gates, and rejected attempts leave nothing (umbrella P2)
    - `tests/test_properties_pipeline.py::test_returned_build_passed_both_gates` and `::test_forced_failure_leaves_nothing`, `slow`, budget 15 each, over `ENABLED_ZONE_TYPES`. Returned: `validated`, `report.passed`, `report.corridors_passed`, `format.passed`; Sidecar `format` equals `vb.format.to_dict()`; the output dir holds only `vb.build_dir` and the failure log. Forced failure: pinned raises `GenerationFailed(pinned=True)` after one attempt, unpinned after `max_attempts`; no `.attempts/` entry or build directory remains.
    - **Validates: Requirements 4.2, 9.2**
  - [ ] 15.7 Write property test for Property 7: Availability follows the Enabled set (umbrella P19)
    - `test_properties_pipeline.py::test_availability_follows_enabled`, budget 50, `TestClient`, 2–4 room builds, monkeypatching `ENABLED_ZONE_TYPES` to subsets from `enabled_subsets` and the planner to a stub picking t from `zone_type_names`. Assert the listing, the 400 iff `canonical_zone_type(t) ∉ E`, the substitution warning and Sidecar entry, and every 200's `zone_type ∈ E`.
    - **Validates: Requirements 3.1, 3.3, 3.4**
  - [ ] 15.8 Enable wilderness only if its properties are green
    - In a commit of its own, add `wilderness` to `ENABLED_ZONE_TYPES` once wilderness P1, Property 10, Property 6 and Property 11 are green on this branch. If they aren't, leave it disabled with `DISABLED_REASON` and record why. Decision note: the design gates enabling on P20 too, but the Format_Checker is a passing stub until wave 6, so P20 for wilderness is confirmed in 20.4, which disables it again if it fails.
    - _Requirements: 3.2, 4.1, 6.3_
  - [ ] 15.9 Add the pipeline and server example tests
    - `tests/test_pipeline.py`: a builder exception removes the scratch directory and propagates; an ungated build carries a `format` block and `validated=False`; `backend_fallback` reaches `ValidatedBuild.warnings` and the Sidecar. `tests/test_server.py`: `/api/zones/...` traversal guards (bad segment or extension → 400, absent → 404).
    - _Requirements: 4.2, 4.3_

- [ ] 16. Checkpoint: wave 4 closed
  - [ ] 16.1 Run the suite and write the wave-4 integration note
    - Suite green; Default_Run median recorded. Integration note: Done-table row, "Pick up here" line, commit hash and count, and whether wilderness shipped enabled.
    - _Requirements: 3.2, 4.2_
  - [ ] 16.2 **HUMAN-GATED:** city 3D pass
    - Checklist, PENDING-HUMAN: city zones (flat and elevated, 12 and 30 rooms) walk end to end in the viewer; if wilderness is enabled, one wilderness zone from the Server loads and walks.
    - _Requirements: 4.1_

### Wave 5 — Modes, `from_controls` and geometry-slice controls (Requirements 1, 2)

- [ ] 17. Explicit modes and the controls path
  - [ ] 17.1 Create the worktree
    - `./scripts/new-worktree.ps1 -Branch agent/m1-modes`. Record the fork-point hash.
    - _Requirements: 1.2_
  - [ ] 17.2 Add `ZonePlan.from_controls`
    - `ai/schema.py`: `CONTROL_ALIASES = {"rooms": "room_count", "theme": "zone_type"}` (a plan key wins over its alias); legacy `elevation: false` without `verticality` means `flat`; ends in the same `cls(**clean).validate(warnings)` as `from_dict`. Content fields keep their names and rules; target keys are dropped as unknown.
    - _Requirements: 1.2, 2.3, 2.4_
  - [ ] 17.3 Write property test for Property 5: Plan normalisation, both entry paths (umbrella P12)
    - Extend `test_zoneplan_normalisation` (budget 100): `zone_plan_dicts` gains `rooms` and `elevation` aliases and `zone_type` values `cave`, `outdoor`, junk. Assert both `from_dict(d)` and `from_controls(d)` have every field in its domain, agree on every key `d` names directly, and are fixed points of `validate()`.
    - **Validates: Requirements 1.2, 2.4**
  - [ ] 17.4 Add the controls golden test before switching any caller
    - `tests/test_planner.py::test_controls_golden`: dungeon/city/wilderness × seeds {7, 1955208177, 1949459644} × rooms {1, 5, 12, 30} × elevation on/off; the legacy `LayoutGenerator(...).generate(...)` and `plan_to_spec(ZonePlan.from_controls(...), seed)` give equal `to_dict()`. If it fails, record the difference here as the documented seed break before 17.5 lands.
    - _Requirements: 1.2_
  - [ ] 17.5 Add `mode` and the controls path to the Server
    - `server/app.py`: `GenerateRequest` / `GenerateResponse` per the design (`mode`, `controls`, `StrictInt` seed/rooms, legacy flat fields, `version`, `mode`, `warnings`, `format_passed`); mode resolution; `_require_int` for `controls.room_count` / `controls.locks`; seed range 0–2,147,483,647; a `RequestValidationError` handler turning any `/api/generate` validation error into a 400 naming the field; prompt mode via `make_plan` with `plan.name = zone_id`; controls mode checks the raw zone type then `ZonePlan.from_controls`. Every 400 happens before any build or write. Record `mode` in the Sidecar.
    - _Requirements: 1.1, 1.2, 1.3, 2.4, 2.5_
  - [ ] 17.6 Add the Server example tests
    - `tests/test_server.py`: the mode routing table; 400 for unknown mode, empty prompt and each non-integer field and kind (float, string, bool, null, list), with `OUTPUT_DIR` empty afterwards; a request carrying `target_shortname: "arena"` returns 200 with files named `<id>.*`; `mode` in the response.
    - _Requirements: 1.1, 1.3, 2.5, 8.1_
  - [ ] 17.7 Add the geometry-slice CLI options
    - `main.py generate`: `--rooms` (1–30), `--size`, `--verticality` (flat/moderate/dramatic), `--locks` (0–5), `--seed` (0–2,147,483,647) as range-checked `type=` functions; `_zone_type_arg` maps `outdoor` and rejects undefined or disabled values listing the enabled set; the plan is `ZonePlan.from_controls({...})`, built through `plan_to_spec` + `generate_validated`. Out-of-domain options exit 2 before any write. No target, topology, district or content options.
    - _Requirements: 2.2, 2.3, 2.5, 3.3, 5.3_
  - [ ] 17.8 Add the CLI example tests
    - `tests/test_pipeline.py::TestCliArgs`: every new option; `--zone-type cave`, `--rooms 0`, `--rooms 31`, `--locks 6`, `--seed -1` → exit 2 and no output directory; `--verticality flat` builds a flat zone; the CLI's plan equals the Server's controls plan for the same values and seed.
    - _Requirements: 1.2, 2.2, 2.5, 3.3, 5.3_
  - [ ] 17.9 Rebuild the Web_App header and Controls panel
    - `web/index.html`, `web/src/{main,api}.ts`: `#generate-description` and `#generate-controls`, `#seed` in the header; Controls panel `#zone-type` (from `fetchZoneTypes()`, disabled options with `disabled`, reason in text and `title`, first enabled preselected), `#rooms`, `#size`, `#verticality` (replaces `#elevation`), `#locks`; `doGenerate(mode)`, Enter routing per field, on-load generation in controls mode; `#m-mode` replaces `#m-source`; `#warnings` (`role="status"`) shows `zone_type_substituted` and `backend_fallback` in words. `controls.ts::_typingTarget` keeps suppressing movement keys. Run `cd web; npx vite build`.
    - _Requirements: 1.4, 2.1, 2.3, 2.6, 3.3_
  - [ ] 17.10 Add the surface guards
    - `tests/test_hygiene.py`: no topology / district / purpose / builder / inhabitants / condition / element control ids in `web/index.html` or CLI options; no target field in `ZonePlan` / `ZoneSpec` dataclass fields, `GenerateRequest`, CLI options or `web/index.html` ids.
    - _Requirements: 2.3, 8.1_

- [ ] 18. Checkpoint: wave 5 closed
  - [ ] 18.1 Run the suite, build the frontend and write the wave-5 integration note
    - Suite green; `cd web; npx vite build` succeeds. Integration note: Done-table row, "Pick up here" line, commit hash and count, and the golden-test result.
    - _Requirements: 1.4, 2.1_
  - [ ] 18.2 **HUMAN-GATED:** modes and controls pass
    - Checklist, PENDING-HUMAN: both Generate actions do what they say; the panel shows which one produced the zone; a blank seed gives a fresh seed; typing in every field moves no camera; a disabled zone type (forced in a dev build) shows its reason; a flat 30-room zone from the controls walks end to end.
    - _Requirements: 1.4, 2.1, 2.6, 3.3_

### Wave 6 — Build naming, format gate and file-system confinement (Requirements 8, 9, 10)

- [ ] 19. Build_Name naming and confinement
  - [ ] 19.1 Create the worktree
    - `./scripts/new-worktree.ps1 -Branch agent/m1-format`. Record the fork-point hash.
    - _Requirements: 8.2_
  - [ ] 19.2 Add `core/env.py` and read keys through it
    - `DOTENV_PATH`, `env_value(name, default)` (`os.environ` first, then `dotenv_values`; never mutates `os.environ`). Switch `ai/llm_planner.py`, `ai/planner.py`, `generators/textures/ai.py` and `generators/textures/factory.py` to it. `no_api_keys` also patches `core.env.DOTENV_PATH` to a missing file. `LLMPlanner` error logs print the exception type and HTTP status only. Add a precedence test with a temp `.env`.
    - _Requirements: 10.2_
  - [ ] 19.3 Add `core/paths.py`
    - `OutsideOutputError`, `OutputRoot` (`contains`, `path`, `mkdir`, `write_bytes`, `write_text`, `replace`, `remove_tree` that unlinks junctions/symlinks and never recurses through them), `assert_output_allowed(output_dir, eq_path)`, and `new_zone_id(prefix="gen")` (`<prefix>_<ts>_<hex6>`, lowercase; the design names it without a home module).
    - _Requirements: 10.1, 10.2_
  - [ ] 19.4 Name every artifact by the Build_Name
    - `generators/builder.py`: `BUILD_NAME_RE`, `fullmatch` check (`ValueError` before any write); archive `<name>.eqg`, entries `ter_<name>.ter` / `<name>.zon`, ZON `models[0] = "TER_<NAME>.TER"`, `<name>.glb`, `<name>.zone.json` (`name` = Build_Name), `<name>.map.svg`. A legacy `shortname` key is dropped on load; nothing writes one. `main.py`: positional `type=_build_name_arg` (lower-case, `^[a-z0-9_]+$`, else exit 2), zone id `new_zone_id(prefix=<name>)`, spec saved as `<name>.json` in the build directory. The Server uses `new_zone_id()`.
    - _Requirements: 8.1, 8.2, 8.3_
  - [ ] 19.5 Route every write through `OutputRoot` and add the refusal
    - `ZoneBuilder.build`, `EqgZone.write` / `write_sidecar` (checked paths), the Pipeline's scratch / move / remove and failure log, the CLI spec save and the Server's `OUTPUT_DIR` creation. Set `tempfile.tempdir` to `<output>/.tmp` in the CLI `main()` and the Server's startup path (never at import). `assert_output_allowed(out, env_value("EQ_PATH"))` in the CLI after parsing (exit 2, both paths named) and in `server/app.py` before `OUTPUT_DIR.mkdir`.
    - _Requirements: 10.1, 10.2_

- [ ] 20. Tier-1 format check in the gate
  - [ ] 20.1 Add the non-raising PFS directory reader
    - `core/pfs.py`: `RawEntry` and `read_directory(data) -> (entries, archive_errors)`; `PfsArchive.from_bytes` unchanged.
    - _Requirements: 9.3_
  - [ ] 20.2 Add `analyzer/rof2check.py`
    - `FormatCheck`, `FormatReport` (`messages`, `to_dict`), `LIQUID_SURFACE_PREFIXES`, `MAX_COORD`, `SAFE_POINT_XY`, `SAFE_POINT_DZ`, and `check_eqg(eqg_path, spec, *, sidecar_path, agent)` with the design's ten checks (`pfs_reads`, `required_files`, `ter_roundtrip`, `zon_roundtrip`, `zon_model_ref`, `material_indices`, `diffuse_textures`, `collision_policy`, `safe_point`, `bounds_sane`, `name_consistent`). Each check is wrapped so an exception becomes a failed check with a named message; dependents of an unreadable input report "skipped"; independent checks still run. No `normals_resolve`.
    - _Requirements: 9.1, 9.3, 9.4_
  - [ ] 20.3 Put the Format_Checker in the Pipeline gate
    - Replace the 15.4 stub with `check_eqg(eqg, spec, sidecar_path=scratch / f"{name}.zone.json")`; the failed check names go into the JSONL line and `GenerationFailed`; ungated builds still run it and record it. `GenerateResponse.format_passed` reflects it.
    - _Requirements: 9.1, 9.2_
  - [ ] 20.4 Write property test for Property 8: Every enabled build passes the Format_Checker (umbrella P20)
    - `test_properties_build.py::test_enabled_builds_pass_format`, `slow`, budget 15, over `ENABLED_ZONE_TYPES`, seeds, n (box 2–30, wilderness 2–12) and `build_names`. Assert `check_eqg` passes, including `name_consistent`, and has no `normals_resolve` check. Pin one `huge` 30-room wilderness `@example` (design risk table). If wilderness fails here, fix it at the root, or disable it in `ENABLED_ZONE_TYPES` with `DISABLED_REASON` and record why.
    - **Validates: Requirements 9.1, 9.4**
  - [ ] 20.5 Write property test for Property 14: The Format_Checker is total and specific (M1-P5)
    - `tests/strategies.py::archive_corruptions` (the design's list). `test_properties_core.py::test_format_checker_total`, `slow`, budget 25, archives built once per example: no exception, one entry per check name, every failed check has a message starting with its name, untouched checks report the same result as on the clean archive.
    - **Validates: Requirements 9.3**
  - [ ] 20.6 Write property test for Property 9: Every artifact carries the Build_Name, one directory per build (umbrella P41, Build_Name form)
    - `test_properties_pipeline.py::test_build_name_and_directories`, `slow`, budget 15, over enabled zone types, seeds and `build_names` (incl. `gen_<ts>_<hex6>` shapes): the accepted build is in `<output>/<zone_id>/v1/`, every artifact, entry name, model reference and Sidecar `name` agree, and a second build with the same Build_Name lands in a different directory without changing the first.
    - **Validates: Requirements 8.2, 8.3, 9.1**
  - [ ] 20.7 Write property test for Property 15: Writes stay inside the Output_Directory (M1-P6)
    - `tests/pbt_helpers.py`: `write_audit()` (one module-level `sys.addaudithook`, recording only while a flag is set) and `fake_install(tmp)`. `test_properties_pipeline.py::test_writes_confined`, `slow`, budget 10, over zone type, seed, n 2–8, pinned or not, first k attempts forced to fail: every recorded path resolves inside the Output_Directory and the fake `EQ_PATH` install is unchanged (file list, sizes, SHA-256).
    - **Validates: Requirements 10.1, 4.2**
  - [ ] 20.8 Add the confinement, key and format example tests
    - CLI and Server refusal with `EQ_PATH` containing the output dir (CLI exit 2; importing `server.app` raises); sentinel key values (`sk-SENTINEL-…`, rule planner, procedural textures) through one prompt generate and one CLI generate appear in no output file, response, captured log or stdout/stderr; CLI positional `bad-name` → exit 2, `MyZone` builds `myzone.*`; hygiene: no `normals_resolve` in `rof2check`, no `shortname` key in the Sidecar.
    - _Requirements: 8.2, 9.4, 10.2_
  - [ ] 20.9 Record one Server build and one CLI build
    - Directory listings (file names) and `check_eqg` reports for one Server build and one CLI build on the branch head.
    - _Requirements: 8.2, 8.3, 9.1_

- [ ] 21. Checkpoint: wave 6 closed
  - Suite green; Default_Run median recorded; frontend builds. Write the wave-6 integration note (Done-table row, "Pick up here" line, commit hash and count, and whether wilderness is still enabled after 20.4). Ask the user if questions arise.

### M1 exit

- [ ] 22. Exit checks and hand-off
  - [ ] 22.1 Run the final suite and record the budget
    - On `master` after the wave-6 merge, `python -m pytest tests/ -q` green. Record the result, the median of 3 Default_Runs against the 1.1 baseline, the commit count since the M1 fork point and the head hash.
    - _Requirements: Exit criteria 1_
  - [ ] 22.2 Run the thorough profile once and record it
    - `python -m pytest tests/ -q --hypothesis-profile=thorough`. Record the result, duration and commit hash. A counterexample goes through the root-fix rule, then this run is repeated.
    - _Requirements: Exit criteria 1_
  - [ ] 22.3 Build the frontend
    - `cd web; npx vite build` succeeds on the same head.
    - _Requirements: Exit criteria 2_
  - [ ] 22.4 Add the M1 section to `docs/ACCEPTANCE.md`
    - New section "M1 — Controls, zone types, connectivity" with the design's human-pass table rows (flat and elevated 30-room dungeons on the M0 seeds and every moved seed, wilderness pads and trails, city walk, both Generate actions, consistent file names, one `<zone_id>/v1/` folder per build), plus the moved-seed list from 9.1.
    - _Requirements: Exit criteria 3, 4_
  - [ ] 22.5 **HUMAN-GATED:** the M1 `docs/ACCEPTANCE.md` pass
    - Checklist, PENDING-HUMAN, on a restarted Server running the merged code: walk the 22.4 section. Every offered zone type (dungeon, city, wilderness) walks end to end, including flat and elevated 30-room dungeons and seeds 1949459644 and 1510177507; wilderness rooms sit on their pads; downloaded files carry the build's name consistently. State that the agent verified none of this in the live viewer.
    - _Requirements: Exit criteria 3_
  - [ ] 22.6 Write the M1 integration note (don't apply it)
    - In the final report give the integrator: the Done-table row, the "Pick up here" line, the commit hash and count, the per-wave notes (9.4, 11, 14.1, 16.1, 18.1, 21), the moved-seed list and the Decision 13 seed break, and whether wilderness shipped enabled. Don't edit `ROADMAP.md`, `README.md` or `tasks/README.md`.
    - _Requirements: Exit criteria 4_

## Notes

- No task is optional. The property tests are the M1 gate, so none carry `*`.
- Tests are added only where the design calls for them (new features, regressions, the Decision 12 bridge exemption); nothing else.
- Wave order is fixed. Within wave 1: speed-up and routing refactor (no geometry change) → measure → fix flat → flat 3D pass (7.2) → elevation draws → fix → elevation 3D pass (9.3). Task 8 does not start until 7.2 is signed off.
- 1.2 and 10.1 use one-off scripts that are never committed; their hashes go in Deliverables. `scripts/sweep_connectivity.py` (5.1) is committed.
- 6.5 and 8.3 are conditional. Leave them unchecked with "not triggered" if nothing failed.
- Human-gated subtasks: 7.2, 9.3, 14.2, 16.2, 18.2 and 22.5. The agent writes the checklist and marks it PENDING-HUMAN; only the user signs off.
- Single-writer: only this file is updated during task work. `ROADMAP.md`, `README.md` and `tasks/README.md` changes go in the integration notes.

## Parked / backlog (not scheduled)

- **BUG (parked, low priority) — intersecting corridors slip past the continuity/conflict checks in the 3D viewer.** Observed on a controls build: dungeon, 30 rooms, size medium, verticality **moderate**, seed **105770060**, build **378341f** (7,084 verts / 3,542 polys / 3 materials / 30 lights). In the viewer, a corridor near room_11 / room_23 visibly crosses/overlaps another corridor tube (screenshot captured by the user) even though the structural corridor-conflict gate (wave 1, tasks 4.1 / 6.5) passed — a fresh instance of the "structural tests pass ≠ correct in 3D" rule, this time on the *elevated* path where corridors at different heights can overlap in XY without the same-height conflict check firing. NOT blocking M1: left as-is on purpose. The user noted intersecting corridors may be *desirable* (interesting multi-level junctions), so the resolution is deliberately deferred — decide later whether to (a) tighten the conflict check to cover cross-height XY overlaps, or (b) embrace intersections as a feature and only reject genuinely broken ones. Reproduce with the pinned seed above before deciding. No fix attempted; no test added.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["2.2"] },
    { "id": 3, "tasks": ["2.3", "3.1"] },
    { "id": 4, "tasks": ["4.1"] },
    { "id": 5, "tasks": ["4.2", "4.3"] },
    { "id": 6, "tasks": ["5.1", "6.1"] },
    { "id": 7, "tasks": ["6.2", "6.4"] },
    { "id": 8, "tasks": ["6.3"] },
    { "id": 9, "tasks": ["6.5"] },
    { "id": 10, "tasks": ["7.1"] },
    { "id": 11, "tasks": ["7.2"] },
    { "id": 12, "tasks": ["8.1"] },
    { "id": 13, "tasks": ["8.2"] },
    { "id": 14, "tasks": ["8.3"] },
    { "id": 15, "tasks": ["9.1", "9.2"] },
    { "id": 16, "tasks": ["9.3"] },
    { "id": 17, "tasks": ["9.4"] },
    { "id": 18, "tasks": ["10.1"] },
    { "id": 19, "tasks": ["10.2"] },
    { "id": 20, "tasks": ["10.3", "10.5", "10.7", "10.8"] },
    { "id": 21, "tasks": ["10.4", "10.6"] },
    { "id": 22, "tasks": ["10.9"] },
    { "id": 23, "tasks": ["10.10"] },
    { "id": 24, "tasks": ["10.11"] },
    { "id": 25, "tasks": ["12.1"] },
    { "id": 26, "tasks": ["12.2"] },
    { "id": 27, "tasks": ["13.1", "13.2"] },
    { "id": 28, "tasks": ["12.3", "13.3", "13.4"] },
    { "id": 29, "tasks": ["13.5"] },
    { "id": 30, "tasks": ["13.6"] },
    { "id": 31, "tasks": ["13.7"] },
    { "id": 32, "tasks": ["13.8", "14.1"] },
    { "id": 33, "tasks": ["14.2", "15.1"] },
    { "id": 34, "tasks": ["15.2", "15.3"] },
    { "id": 35, "tasks": ["15.4"] },
    { "id": 36, "tasks": ["15.5"] },
    { "id": 37, "tasks": ["15.6", "15.9"] },
    { "id": 38, "tasks": ["15.7"] },
    { "id": 39, "tasks": ["15.8"] },
    { "id": 40, "tasks": ["16.1"] },
    { "id": 41, "tasks": ["16.2", "17.1"] },
    { "id": 42, "tasks": ["17.2"] },
    { "id": 43, "tasks": ["17.3", "17.4"] },
    { "id": 44, "tasks": ["17.5", "17.7", "17.9"] },
    { "id": 45, "tasks": ["17.6", "17.8", "17.10"] },
    { "id": 46, "tasks": ["18.1"] },
    { "id": 47, "tasks": ["18.2", "19.1"] },
    { "id": 48, "tasks": ["19.2", "19.3", "20.1"] },
    { "id": 49, "tasks": ["19.4", "20.2"] },
    { "id": 50, "tasks": ["19.5"] },
    { "id": 51, "tasks": ["20.3"] },
    { "id": 52, "tasks": ["20.4", "20.5", "20.6"] },
    { "id": 53, "tasks": ["20.7"] },
    { "id": 54, "tasks": ["20.8", "20.9"] },
    { "id": 55, "tasks": ["22.1"] },
    { "id": 56, "tasks": ["22.2", "22.3", "22.4"] },
    { "id": 57, "tasks": ["22.5"] },
    { "id": 58, "tasks": ["22.6"] }
  ]
}
```
