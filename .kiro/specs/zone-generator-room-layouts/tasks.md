# Tasks — zone-generator-room-layouts (roadmap step 9)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Decisions later tasks rely on are in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card, then the design section it names. Verify both against the
   code; the design was written at `1c69568`.
3. Work in a worktree (`agent/rooms-<n>`) unless the card says MAIN
   checkout. Edit only the files under `Owns`.
4. Every commit carries the trailer `Task: zone-generator-room-layouts/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**
6. Run the full Python suite before ticking, even for a frontend-only task,
   and don't commit while it runs (a server-staleness test notices).

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it). `Depends` lists task numbers. `Owns` lists the files and folders
the task may edit; two ready tasks with disjoint `Owns` can run in parallel.

The design's open questions were answered on 2026-11-06 (`archive.md`). Step 8's human pass is open too (its
`tasks.md` task 15), set aside by the user on 2026-11-06.

## Tasks

- [x] 1. Measure what stands in stock rooms
  - Card: [cards/01-feature-survey.md](cards/01-feature-survey.md)
  - Type: agent · Size: S · Depends: —
  - Owns: scripts/room_feature_survey.py, .kiro/specs/zone-generator-room-layouts/design.md (finding 1 only)
  - Reqs: 1

- [x] 2. The gate learns Features
  - Card: [cards/02-gate-features.md](cards/02-gate-features.md)
  - Type: agent · Size: M · Depends: —
  - Owns: analyzer/traverse.py, generators/zone_spec.py (`RoomSpec.features`), generators/room_features.py (the data type only), tests/test_gate_features.py
  - Reqs: 2

- [x] 3. Feature meshes
  - Card: [cards/03-feature-mesh.md](cards/03-feature-mesh.md)
  - Type: agent · Size: M · Depends: 2
  - Owns: generators/room_features.py, generators/geometry.py, tests/test_feature_mesh.py
  - Reqs: 3

- [ ] 4. Placement and the Spine
  - Card: [cards/04-placement.md](cards/04-placement.md)
  - Type: agent · Size: M · Depends: 2
  - Owns: generators/room_layouts.py, tests/test_room_placement.py
  - Reqs: 4

- [ ] 5. Room layouts as data
  - Card: [cards/05-layout-files.md](cards/05-layout-files.md)
  - Type: agent · Size: M · Depends: 1, 3, 4
  - Owns: rules/rooms/, generators/room_layouts.py, generators/semantics.py (`prop_hints`), scripts/topology_rules.py, generators/topology/draw.py, docs/TOPOLOGY_RULES.md, tests/test_room_layouts.py
  - Reqs: 5

- [ ] 6. Rooms get Features in graph builds
  - Card: [cards/06-in-builds.md](cards/06-in-builds.md)
  - Type: agent · Size: M · Depends: 5
  - Owns: ai/expand.py, generators/room_layouts.py, generators/outdoor_dungeon.py, generators/builder.py, tests/test_features_build.py, tests/ (goldens that change, deliberately)
  - Reqs: 4.4, 6, 7

- [ ] 7. Features control, sidecar and maps
  - Card: [cards/07-controls-maps.md](cards/07-controls-maps.md)
  - Type: agent · Size: M · Depends: 6
  - Owns: ai/schema.py, ai/expand.py, main.py, server/app.py, web/index.html, web/src/main.ts, generators/mapview.py, generators/eqmap.py, generators/pipeline.py, tests/test_hygiene.py, tests/test_features_controls.py
  - Reqs: 8, 6.4

- [ ] 8. HUMAN: first look at room layouts
  - Card: [cards/08-first-look.md](cards/08-first-look.md)
  - Type: human · Depends: 6, 7

- [ ] 9. Pieces that suit each style
  - Card: [cards/09-style-pieces.md](cards/09-style-pieces.md)
  - Type: agent · Size: M · Depends: 8
  - Owns: generators/room_features.py, rules/rooms/, generators/room_layouts.py, tests/test_feature_mesh.py
  - Reqs: 3.2

- [ ] 10. Themes and rooms read as themselves
  - Card: [cards/10-themes.md](cards/10-themes.md)
  - Type: agent · Size: S · Depends: 8
  - Owns: rules/rooms/, tests/test_room_layouts.py
  - Reqs: 5

- [ ] 11. Gate sweep and stock bands
  - Card: [cards/11-sweep-bands.md](cards/11-sweep-bands.md)
  - Type: agent · Size: M · Depends: 9, 10
  - Owns: tests/test_features_sweep.py, rules/rooms/
  - Reqs: 9

- [ ] 12. Tune from the looks
  - Card: [cards/12-tuning.md](cards/12-tuning.md)
  - Type: agent · Size: S · Depends: 11
  - Owns: rules/rooms/, generators/room_layouts.py, generators/room_features.py, tests/

- [ ] 13. Acceptance section, thorough run
  - Card: [cards/13-release-prep.md](cards/13-release-prep.md)
  - Type: agent · Size: S · Depends: 12
  - Owns: docs/ACCEPTANCE.md, tests/test_features_sweep.py
  - Reqs: exit criteria 1–2

- [ ] 14. HUMAN: room layouts acceptance pass
  - Card: [cards/14-human-acceptance.md](cards/14-human-acceptance.md)
  - Type: human · Depends: 13

- [ ] 15. Close step 9
  - Card: [cards/15-close.md](cards/15-close.md)
  - Type: agent · Size: S · Depends: 14 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-room-layouts/, .kiro/specs/zone-generator/
