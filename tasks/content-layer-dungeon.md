# TASK: content-layer-dungeon

Status: done        <!-- not-started | in-progress | blocked | done -->
Epic: Content / semantic layer, Step 1 — single-theme rooms (ROADMAP "Next" #1).
      Step 2 (districts) split out to tasks/content-layer-districts.md.
Last touched: 2026-10-19 — navigability re-swept after corridor-connection
      landed: 55/55 themed zones fully reachable with ZERO content-layer
      changes. Remaining aesthetic/enclosure 3D confirmation delegated to the
      user's ongoing random-sampling workflow. Step 1 closed as done.

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
- [x] Rooms stay navigable with semantic shape bias applied — AUTOMATED gate
      (`analyzer.traverse`). **SIGNED OFF.** Re-swept after `corridor-connection`
      landed: **55/55 themed zones fully reachable** (11 archetypes × 5 seeds,
      8 rooms each — including the formerly-broken seeds 678358326 and
      1955208177) with **zero content-layer code changes**. This confirms the
      earlier diagnosis: the half-failing sweep was the `corridor-connection`
      bug, not a content-layer defect. See the sweep evidence in Notes. Helper:
      `scripts/sweep_themed_navigability.py`.
- [~] **ACCEPTANCE.md A/E confirmed in the 3D viewer** for several archetypes +
      seeds — **DELEGATED, not a one-time gate.** The automated navigability gate
      above is green; the remaining aesthetic judgement (do themed rooms read as
      coherent places — regions/lights/palette land right) is a human-eyeball
      item that the user has delegated to their ongoing random-sampling workflow:
      they reopen this task or file a new one if sampling surfaces an aesthetic
      issue. Closed as delegated. See Notes.
- [~] Rooms stay enclosed (no see-through) with shape bias — **DELEGATED** to the
      same random-sampling workflow (enclosure is a visual check the automated
      validator does not cover). Closed as delegated, reopened on demand.

## Subtasks

- [x] Research theme vocabulary & districts (commit bb97abe)
- [x] Implement semantics module + wiring — Step 1, single district (commit 1f155b6)
- [x] **Step 1 validation pass** — split into two halves now that the
      traversability validator exists:
  - [x] *Navigability (automated):* re-ran `analyzer.traverse` across all 11
        archetypes × 5 seeds after `corridor-connection` landed. **55/55 fully
        reachable with zero content-layer changes** — confirming the content
        layer was sound all along and the earlier failures were the
        `corridor-connection` bug. **SIGNED OFF.**
  - [~] *Aesthetic + enclosure (manual):* **DELEGATED** to the user's ongoing
        random-sampling workflow (reopen / file a new task if sampling surfaces
        an issue) rather than held as a one-time gate.
- [x] Address any issues the sweep surfaced — none; the navigability failures
      were owned by `corridor-connection`, now landed.
- [ ] Sync ROADMAP + README — integration state, handled in the single-writer
      integration step (see integration note), NOT in this task.

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
- Close-out helper: `scripts/sweep_themed_navigability.py` (themed navigability sweep)
- Commits: bb97abe, 1f155b6, 69dea3c (close-out: navigability re-sweep + Status
  done; this line's hash recorded in a follow-up commit)

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
- **Navigability re-sweep (close-out, this session) — GREEN.** With
  `corridor-connection` now landed (verified in code: Z-corridor routing +
  `_emit_route` in `generators/geometry.py`; `max_grade` grade cap +
  `_relax_elevation` in `generators/layout.py`), re-ran the Step 1 sweep via
  `scripts/sweep_themed_navigability.py` — build themed dungeon
  (`LayoutGenerator(theme='dungeon', seed=…).generate(name, room_count=8,
  dungeon_theme=<archetype>)` → `ZoneBuilder(spec).build(write_glb=False)` →
  `analyzer.traverse.validate(eqg, spec=spec)`):
  - **55/55 themed zones fully reachable** — all 11 archetypes (fortress,
    war_city, warren, temple, tomb, wizard_lair, corrupted_sanctum, mine_delve,
    sunken_ruin, lava_forge, ice_keep) × 5 seeds (1, 42, 99, 678358326,
    1955208177), 8 rooms each. Every zone reported N/N reachable.
  - Examples: `fortress` seed 1 → 8/8; `lava_forge` seed 678358326 → 8/8;
    `ice_keep` seed 1955208177 → 8/8 (the two large seeds were among the
    formerly-broken ones in the earlier sweep).
  - **Zero content-layer code changes** were needed to reach green — this is the
    objective confirmation that the earlier ~50% failure rate was the
    `corridor-connection` bug, not a content-layer defect, exactly as diagnosed.
  - Full suite: **197 passed** (`python -m pytest tests/ -q`).
  - NOT verified in the live 3D viewer this session: the aesthetic read of themed
    rooms (ACCEPTANCE.md A/E) and enclosure (no see-through). Those are delegated
    to the user's random-sampling workflow (see below) — eyeball when sampling.
- **Aesthetic/enclosure sign-off is DELEGATED, by the user's decision.** The
  remaining human-only items (ACCEPTANCE.md A/E "themed rooms read as coherent
  places"; "rooms stay enclosed with shape bias") are closed as *delegated to the
  user's ongoing random-sampling workflow*, not as a one-time 3D gate: the user
  samples generated zones in the normal course of work and will reopen this task
  (or file a new one) if sampling surfaces an aesthetic or enclosure issue. This
  is an explicit decision recorded here so the task can close without a blocking
  manual gate while still being revisitable.
- **FUTURE (not a blocker):** open design question — should `sink` (per-room
  elevation character) be suppressed / scaled when the user asked for a FLAT
  zone (elevation off)? Today a "flat" themed zone still gets gentle sink
  offsets. The navigability sweep shows these offsets are walkable, so this is a
  polish/aesthetic call, not a correctness bug. It is already mirrored as a
  future item in `tasks/content-layer-districts.md`; left logged here for history
  and NOT holding this task open.
