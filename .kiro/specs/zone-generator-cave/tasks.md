# Tasks — zone-generator-cave (roadmap step 21)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Decisions later tasks rely on are in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card, then the design section it names. Verify both against the
   code; the design was written at `a377d54`.
3. Work in a worktree (`agent/cave-<n>`) unless the card says MAIN checkout.
   Edit only the files under `Owns`.
4. Every commit carries the trailer `Task: zone-generator-cave/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**
6. Iterate on your task's own tests and `python -m pytest tests/ -q -m "not slow"`;
   run the full Python suite once before ticking, and don't commit while it runs
   (a server-staleness test notices).

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it). `Depends` lists task numbers. `Owns` lists the files and folders the
task may edit; two ready tasks with disjoint `Owns` can run in parallel.

**The choice was made by the lead on 2026-11-19** and is confirmed with the user at task 8
(`archive.md` "Decisions").

Bytes: every zone built today stays byte-identical (Req 6). Every task that touches generation
proves it with
`python -m pytest tests/test_layout_engine.py tests/test_site_builds.py tests/test_decor_builds.py tests/test_partial_rebuild.py -q`
(no golden is recaptured in this step).

## Tasks

- [x] 1. The cave Purpose
  - Card: [cards/01-purpose.md](cards/01-purpose.md)
  - Type: agent · Size: M · Depends: —
  - Owns: generators/semantics.py, ai/schema.py, tests/test_cave_purpose.py, any test that pins the Purpose list, rules/rooms/layouts.toml (placeholder recipes only)
  - Reqs: 1

- [ ] 2. Rule files: finish, recipes, topology, textures
  - Card: [cards/02-rules.md](cards/02-rules.md)
  - Type: agent · Size: M · Depends: 1
  - Owns: rules/rooms/, rules/topology/themes.toml, styles/texture_recipes.json, tests/test_cave_rules.py
  - Reqs: 2.1–2.3, 2.5

- [x] 3. The decor layer
  - Card: [cards/03-decor.md](cards/03-decor.md)
  - Type: agent · Size: S · Depends: 1
  - Owns: rules/decor/themes.toml, rules/decor/layers/cave.toml, tests/test_decor_rules.py, rules/decor/sets.toml, rules/decor/tags.toml, tests/test_decor_layers.py (the theme-map line)
  - Reqs: 2.4, 2.5

- [ ] 4. Room scale from the cave profile
  - Card: [cards/04-profile.md](cards/04-profile.md)
  - Type: agent · Size: S · Depends: 1
  - Owns: ai/expand.py, generators/layout.py (constructor and its one call), tests/test_cave_profile.py
  - Reqs: 3

- [ ] 5. Planner words, page and Districts
  - Card: [cards/05-planner.md](cards/05-planner.md)
  - Type: agent · Size: M · Depends: 1
  - Owns: ai/rule_planner.py, generators/districts.py, web/index.html, tests/test_planner.py, tests/test_properties_layout.py (property 19 wording), tests/test_district_purposes.py
  - Reqs: 4

- [ ] 6. Gate and bands
  - Card: [cards/06-gate.md](cards/06-gate.md)
  - Type: agent · Size: M · Depends: 2, 3, 4
  - Owns: scripts/sweep_themed_navigability.py, scripts/quality_sweep.py, generators/quality.py (only a cave row, if measured), any root-cause fix named in the commit
  - Reqs: 5

- [ ] 7. Acceptance section
  - Card: [cards/07-acceptance.md](cards/07-acceptance.md)
  - Type: agent · Size: S · Depends: 5, 6, 10
  - Owns: docs/ACCEPTANCE.md

- [ ] 8. HUMAN: first look
  - Card: [cards/08-first-look.md](cards/08-first-look.md)
  - Type: human · Depends: 7

- [ ] 9. Close step 21
  - Card: [cards/09-close.md](cards/09-close.md)
  - Type: agent · Size: S · Depends: 8 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-cave/, .kiro/specs/zone-generator/

- [ ] 10. Record cave rooms for the room-context corpus
  - Card: [cards/10-recording.md](cards/10-recording.md)
  - Type: agent · Size: S · Depends: 2, 3, 4
  - Owns: scripts/record_rooms.py, tests/fixtures/rooms/
  - Reqs: 2.5
