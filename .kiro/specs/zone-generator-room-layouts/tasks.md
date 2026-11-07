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

- [x] 4. Placement and the Spine
  - Card: [cards/04-placement.md](cards/04-placement.md)
  - Type: agent · Size: M · Depends: 2
  - Owns: generators/room_layouts.py, tests/test_room_placement.py
  - Reqs: 4

- [x] 5. Room layouts as data
  - Card: [cards/05-layout-files.md](cards/05-layout-files.md)
  - Type: agent · Size: M · Depends: 1, 3, 4
  - Owns: rules/rooms/, generators/room_layouts.py, generators/semantics.py (`prop_hints`), scripts/topology_rules.py, generators/topology/draw.py, docs/TOPOLOGY_RULES.md, tests/test_room_layouts.py
  - Reqs: 5

- [x] 6. Rooms get Features in graph builds
  - Card: [cards/06-in-builds.md](cards/06-in-builds.md)
  - Type: agent · Size: M · Depends: 5
  - Owns: ai/expand.py, generators/room_layouts.py, generators/outdoor_dungeon.py, generators/builder.py, tests/test_features_build.py, tests/ (goldens that change, deliberately)
  - Reqs: 4.4, 6, 7

- [x] 7. Features control, sidecar and maps
  - Card: [cards/07-controls-maps.md](cards/07-controls-maps.md)
  - Type: agent · Size: M · Depends: 6
  - Owns: ai/schema.py, ai/expand.py, main.py, server/app.py, web/index.html, web/src/main.ts, generators/mapview.py, generators/eqmap.py, generators/pipeline.py, tests/test_hygiene.py, tests/test_features_controls.py
  - Reqs: 8, 6.4

- [x] 8. HUMAN: first look at room layouts
  - Card: [cards/08-first-look.md](cards/08-first-look.md)
  - Type: human · Depends: 6, 7

- [x] 9. Pieces that suit each style
  - Card: [cards/09-style-pieces.md](cards/09-style-pieces.md)
  - Type: agent · Size: M · Depends: 8
  - Owns: generators/room_features.py, rules/rooms/, generators/room_layouts.py, tests/test_feature_mesh.py
  - Reqs: 3.2

- [x] 10. Themes and rooms read as themselves
  - Card: [cards/10-themes.md](cards/10-themes.md)
  - Type: agent · Size: S · Depends: 8
  - Owns: rules/rooms/, tests/test_room_layouts.py
  - Reqs: 5

- [x] 11. Gate sweep and stock bands
  - Card: [cards/11-sweep-bands.md](cards/11-sweep-bands.md)
  - Type: agent · Size: M · Depends: 9, 10
  - Owns: tests/test_features_sweep.py, rules/rooms/
  - Reqs: 9

- [x] 12. Measure how stock rooms change
  - Card: [cards/12-scale-survey.md](cards/12-scale-survey.md)
  - Type: agent · Size: S · Depends: 11
  - Owns: scripts/room_scale_survey.py, .kiro/specs/zone-generator-room-layouts/design.md, .kiro/specs/zone-generator-room-layouts/archive.md
  - Reqs: 11.5, 14

- [x] 13. Scales as data
  - Card: [cards/13-scales-data.md](cards/13-scales-data.md)
  - Type: agent · Size: M · Depends: 12
  - Owns: generators/room_scales.py, rules/rooms/scales.toml, scripts/topology_rules.py, docs/TOPOLOGY_RULES.md, tests/test_room_scales.py
  - Reqs: 10

- [x] 14. Rooms draw their Scales
  - Card: [cards/14-scale-draw.md](cards/14-scale-draw.md)
  - Type: agent · Size: S · Depends: 13
  - Owns: generators/room_scales.py, ai/expand.py, tests/test_room_scales.py, tests/test_topology_levels.py
  - Reqs: 11.1, 11.2, 11.4

- [x] 15. Rules set Weights
  - Card: [cards/15-rule-scales.md](cards/15-rule-scales.md)
  - Type: agent · Size: M · Depends: 14
  - Owns: generators/topology/, rules/topology/, generators/room_scales.py, tests/test_room_scales.py
  - Reqs: 11.3, 11.5

- [x] 16. A room's finish is its wall style
  - Card: [cards/16-per-room-style.md](cards/16-per-room-style.md)
  - Type: agent · Size: M · Depends: 15
  - Owns: generators/wall_styles.py, rules/walls/, rules/topology/themes.toml, ai/expand.py, tests/test_walls_mixed.py, tests/test_room_scales.py, tests/test_topology_levels.py
  - Reqs: 12

- [x] 17. Recipes read the Scales
  - Card: [cards/17-recipes-read.md](cards/17-recipes-read.md)
  - Type: agent · Size: S · Depends: 16
  - Owns: generators/room_layouts.py, rules/rooms/, tests/test_room_layouts.py, tests/test_features_sweep.py, tests/test_topology_levels.py
  - Reqs: 13

- [x] 18. The gate learns Transitions
  - Card: [cards/18-gate-transitions.md](cards/18-gate-transitions.md)
  - Type: agent · Size: S · Depends: 16
  - Owns: generators/zone_spec.py, analyzer/, tests/test_gate_transitions.py
  - Reqs: 14.3

- [x] 19. Transition pieces
  - Card: [cards/19-transition-mesh.md](cards/19-transition-mesh.md)
  - Type: agent · Size: M · Depends: 18
  - Owns: generators/geometry.py, generators/zone_spec.py, generators/transitions.py, tests/test_transition_mesh.py
  - Reqs: 14.2, 14.6

- [x] 20. Transitions as data, in builds
  - Card: [cards/20-transition-rules.md](cards/20-transition-rules.md)
  - Type: agent · Size: M · Depends: 19
  - Owns: generators/transitions.py, rules/rooms/transitions.toml, generators/wall_styles.py, generators/mapview.py, scripts/topology_rules.py, tests/test_transition_rules.py, tests/test_topology_levels.py
  - Reqs: 14.1, 14.4, 14.5

- [x] 21. Scale controls
  - Card: [cards/21-scale-controls.md](cards/21-scale-controls.md)
  - Type: agent · Size: M · Depends: 17, 20
  - Owns: generators/room_scales.py, ai/schema.py, ai/expand.py, main.py, server/app.py, web/index.html, web/src/main.ts, tests/test_hygiene.py, tests/test_scale_controls.py
  - Reqs: 15

- [x] 22. HUMAN: second look, rooms that vary
  - Card: [cards/22-second-look.md](cards/22-second-look.md)
  - Type: human · Depends: 21

- [x] 23. Tune from the looks
  - Card: [cards/23-tuning.md](cards/23-tuning.md)
  - Type: agent · Size: S · Depends: 22
  - Owns: rules/rooms/, rules/walls/, generators/room_layouts.py, generators/room_features.py, generators/room_scales.py, generators/transitions.py, docs/TOPOLOGY_RULES.md, tests/

- [ ] 24. Acceptance section, thorough run
  - Card: [cards/24-release-prep.md](cards/24-release-prep.md)
  - Type: agent · Size: S · Depends: 23
  - Owns: docs/ACCEPTANCE.md, tests/test_features_sweep.py, generators/outline.py, tests/test_properties_layout.py
  - Reqs: exit criteria 1–2

- [ ] 25. HUMAN: room layouts acceptance pass
  - Card: [cards/25-human-acceptance.md](cards/25-human-acceptance.md)
  - Type: human · Depends: 24

- [ ] 26. Close step 9
  - Card: [cards/26-close.md](cards/26-close.md)
  - Type: agent · Size: S · Depends: 25 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-room-layouts/, .kiro/specs/zone-generator/
