# TASK: content-layer-dungeon

Status: in-progress        <!-- not-started | in-progress | blocked | done -->
Epic: Content / semantic layer, Step 1 — single-theme rooms (ROADMAP "Next" #1).
      Step 2 (districts) split out to tasks/content-layer-districts.md.
Last touched: 2026-10-18 — Step 2 (districts) split out to its own task; this
      file now closes on the remaining Step 1 human 3D validation.

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
- [x] Automated tests written for the new behaviour and the suite is green
- [ ] **ACCEPTANCE.md A/E confirmed in the 3D viewer** for several archetypes +
      seeds (NOT yet done — the automated pass ≠ a human 3D pass; see cave lesson)
- [~] Rooms stay navigable with semantic shape bias applied — now has an
      AUTOMATED gate (`analyzer.traverse`). Measured across archetypes; see the
      finding below. **BLOCKED**: themed zones currently fail traversability, but
      the cause is the `corridor-connection` bug (sink-induced elevation routed
      through same-axis corridors that mis-connect), NOT the content layer. The
      content layer's elevation is gentle/walkable (ramps 6-7°, steps <1.2u).
- [ ] Rooms stay enclosed (no see-through) with shape bias — still a manual 3D
      check (the traversability validator covers navigability, not enclosure).

## Subtasks

- [x] Research theme vocabulary & districts (commit bb97abe)
- [x] Implement semantics module + wiring — Step 1, single district (commit 1f155b6)
- [~] **Step 1 validation pass** — split into two halves now that the
      traversability validator exists:
  - [x] *Navigability (automated):* ran `analyzer.traverse` across all archetypes
        × seeds. Finding: content layer is sound (gentle walkable elevation) but
        themed zones fail traversability because `sink` routes elevation through
        same-axis corridors that mis-connect — i.e. the `corridor-connection`
        bug, not a content-layer bug. **Navigability sign-off is BLOCKED on
        `tasks/corridor-connection.md`.** Re-run this sweep after it lands; it
        should go green with no content-layer changes.
  - [ ] *Aesthetic + enclosure (manual, NOT blocked):* human 3D pass that themed
        rooms read as coherent places — regions/lights/palette land right, rooms
        stay enclosed (no see-through). Doesn't depend on corridors connecting.
- [ ] Address any issues the aesthetic pass surfaces (the navigability failures
      are already owned by `corridor-connection`).
- [ ] Sync ROADMAP + README when this task's Step 1 validation closes.

**Step 2 — districts has moved to its own task:
`tasks/content-layer-districts.md`.** It was split out so this file can close on
Step 1 (single-theme rooms, now built — only the human 3D aesthetic/enclosure
validation remains) while districts (making a zone several themed places at once)
is tracked as its own coherent change. The full Step 2 design still lives in
`docs/RESEARCH.md` ("Multi-area zones — districts").

## Deliverables

- Code: `generators/semantics.py`, `generators/layout.py`, `generators/zone_spec.py`,
  `ai/schema.py`, `ai/rule_planner.py`, `ai/expand.py`, `generators/mapview.py`
- Tests: `tests/test_generators.py::TestSemantics`, `tests/test_planner.py`
- Docs: `docs/RESEARCH.md` (theme vocabulary + districts design); ROADMAP in sync
- Commits: bb97abe, 1f155b6 (Step 2 commits as they land)

## Notes / decisions / blockers

- Step 2 (districts) is now its own task: `tasks/content-layer-districts.md`.
  Its design + user decisions are captured in `docs/RESEARCH.md` ("Multi-area
  zones — districts") and ROADMAP — don't re-derive them.
- Semantic labelling only runs for box themes (dungeon/city); cave/outdoor are
  untouched (cave is shelved — see ROADMAP).
- IMPORTANT: this task file was reconstructed by inspecting the repo — the code
  had advanced past the stale session summary. Step 1 is BUILT; the remaining
  work in THIS file is the **human 3D validation** (aesthetic + enclosure).
  Step 2 (districts) is now `tasks/content-layer-districts.md`. VERIFY the code
  state before assuming, as it may have moved again.
- **Navigability finding (via `analyzer.traverse`, measured this session):**
  Swept all 7 archetypes × 2 seeds with elevation OFF to isolate the content
  layer. The `sink` (per-room elevation character) introduces gentle floor
  offsets (10-30u) EVEN with the elevation flag off, because it's applied in
  `label_rooms` before `_assign_elevation`. Those offsets are individually
  walkable (validator reports the corridors as "nominally walkable" — ramps
  6-7°, stairs 0.6-1.2u/step), but ~half the themed zones still fail because the
  corridors carrying that elevation hit the **same-axis mis-connection** bug
  ("mesh opening doesn't meet the room / disconnected corridor"). Conclusion:
  the content layer is sound; its navigability sign-off is gated on
  `tasks/corridor-connection.md`. Recommended sequencing: do corridor-connection
  next (it also unblocks `multi-level-dungeon`), then re-run the sweep here — it
  should pass with zero content-layer changes.
- Open design question surfaced by the above: should `sink` be suppressed /
  scaled when the user asked for a FLAT zone (elevation off)? Today a "flat"
  themed zone still gets sink offsets. Defer the call until corridor-connection
  lands and we can see whether the gentle sink elevation reads well in 3D.
