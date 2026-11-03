# Tasks — zone-generator-outdoor-dungeon (roadmap step 5)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Decisions later tasks rely on are in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card, then the design section it names. Verify both against the
   code; the design was written at `a311b50`.
3. Work in a worktree (`agent/outdoor-<n>`) unless the card says MAIN
   checkout. Edit only the files under `Owns`.
4. Every commit carries the trailer
   `Task: zone-generator-outdoor-dungeon/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it). `Depends` lists task numbers. `Owns` lists the files and folders
the task may edit; two ready tasks with disjoint `Owns` can run in parallel.

The design's five open questions were answered on 2026-11-01
(`archive.md` "Decisions").

## Tasks

- [x] 1. Measure the classic outdoor-dungeon anatomy
  - Card: [cards/01-anatomy-survey.md](cards/01-anatomy-survey.md)
  - Type: agent · Size: S · Depends: —
  - Owns: scripts/outdoor_dungeon_survey.py, .kiro/specs/zone-generator-outdoor-dungeon/design.md
  - Reqs: 1

- [x] 2. Envelope and layout inside it
  - Card: [cards/02-envelope.md](cards/02-envelope.md)
  - Type: agent · Size: M · Depends: —
  - Owns: generators/envelope.py, generators/layout.py, tests/test_envelope.py
  - Reqs: 2

- [x] 3. Host terrain with a Host_Hill
  - Card: [cards/03-host-terrain.md](cards/03-host-terrain.md)
  - Type: agent · Size: M · Depends: 1
  - Owns: generators/wilderness/matrix.py, generators/wilderness/build.py, generators/wilderness/synth.py, tests/test_host_terrain.py
  - Reqs: 3

- [x] 4. Envelope from the built terrain
  - Card: [cards/04-envelope-from-terrain.md](cards/04-envelope-from-terrain.md)
  - Type: agent · Size: S · Depends: 2, 3
  - Owns: generators/outdoor_dungeon.py, tests/test_outdoor_envelope.py, generators/layout.py (`_fit_floors`)
  - Reqs: 2.1, 3.1

- [x] 5. Entrance: Apron, Tunnel and Mouth
  - Card: [cards/05-entrance-spike.md](cards/05-entrance-spike.md)
  - Type: agent · Size: M · Depends: 4
  - Owns: generators/outdoor_dungeon.py, generators/geometry.py, tests/test_entrance.py
  - Reqs: 4

- [x] 6. Outdoor-dungeon backend and gate
  - Card: [cards/06-backend-and-gate.md](cards/06-backend-and-gate.md)
  - Type: agent · Size: M · Depends: 5
  - Owns: generators/backends.py, generators/pipeline.py, generators/builder.py, generators/outdoor_dungeon.py, tests/test_outdoor_dungeon_build.py
  - Reqs: 5, 7.1, 8.2

- [x] 7. Zone type, prompt words, controls, sidecar
  - Card: [cards/07-zone-type.md](cards/07-zone-type.md)
  - Type: agent · Size: M · Depends: 6
  - Owns: generators/zone_types.py, ai/rule_planner.py, ai/expand.py, main.py, server/app.py, tests/test_outdoor_dungeon_controls.py, generators/backends.py, generators/outdoor_dungeon.py, generators/builder.py, generators/pipeline.py, web/index.html (zone-type option), tests/test_hygiene.py, tests/strategies.py, tests/test_server.py, tests/test_properties_build.py, tests/test_properties_pipeline.py, tests/test_properties_layout.py (zone-type lists)
  - Reqs: 6

- [x] 8. Maps and preview
  - Card: [cards/08-maps-and-preview.md](cards/08-maps-and-preview.md)
  - Type: agent · Size: S · Depends: 6
  - Owns: generators/mapgeom.py, generators/eqmap.py, tests/test_outdoor_dungeon_maps.py, generators/envelope.py, generators/layout.py, generators/outdoor_dungeon.py, tests/test_entrance.py, tests/test_outdoor_dungeon_controls.py (entrance-room fix)
  - Reqs: 7.2, 7.3

- [x] 9. Web: zone type and controls
  - Card: [cards/09-web.md](cards/09-web.md)
  - Type: agent · Size: S · Depends: 7
  - Owns: web/index.html, web/src/main.ts
  - Reqs: 6.1

- [x] 10. HUMAN: first look at an outdoor dungeon
  - Card: [cards/10-human-first-look.md](cards/10-human-first-look.md)
  - Type: human · Depends: 6, 7, 9

- [x] 11. Tune from the first look
  - Card: [cards/11-tuning.md](cards/11-tuning.md)
  - Type: agent · Size: S · Depends: 10
  - Owns: generators/outdoor_dungeon.py, generators/wilderness/matrix.py, tests/test_outdoor_envelope.py (regression test)

- [x] 12. Acceptance section, thorough run, timing
  - Card: [cards/12-release-prep.md](cards/12-release-prep.md)
  - Type: agent · Size: S · Depends: 8, 11
  - Owns: docs/ACCEPTANCE.md, tests/test_outdoor_dungeon_build.py
  - Reqs: 8.3, exit criteria 1–2

- [x] 13. HUMAN: outdoor dungeon acceptance pass
  - Card: [cards/13-human-acceptance.md](cards/13-human-acceptance.md)
  - Type: human · Depends: 12

- [x] 14. Close step 5
  - Card: [cards/14-close.md](cards/14-close.md)
  - Type: agent · Size: S · Depends: 13 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-outdoor-dungeon/, .kiro/specs/zone-generator/
