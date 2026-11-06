# Tasks — zone-generator-room-walls (roadmap step 8)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Decisions later tasks rely on are in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card, then the design section it names. Verify both against the
   code; the design was written at `d09449c`.
3. Work in a worktree (`agent/walls-<n>`) unless the card says MAIN
   checkout. Edit only the files under `Owns`.
4. Every commit carries the trailer `Task: zone-generator-room-walls/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**
6. Run the full Python suite before ticking, even for a frontend-only task,
   and don't commit while it runs (a server-staleness test notices).

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it). `Depends` lists task numbers. `Owns` lists the files and folders
the task may edit; two ready tasks with disjoint `Owns` can run in parallel.

## Tasks

- [x] 1. Measure the stock walls
  - Card: [cards/01-wall-survey.md](cards/01-wall-survey.md)
  - Type: agent · Size: S · Depends: —
  - Owns: scripts/wall_survey.py, .kiro/specs/zone-generator-room-walls/design.md (finding 1 only)
  - Reqs: 1

- [x] 2. The gate learns Outlines
  - Card: [cards/02-gate-outlines.md](cards/02-gate-outlines.md)
  - Type: agent · Size: M · Depends: —
  - Owns: analyzer/traverse.py, generators/zone_spec.py (`RoomSpec.outline`), generators/outline.py (the data type only), tests/test_gate_outlines.py
  - Reqs: 3

- [x] 3. Outlines and their meshes
  - Card: [cards/03-outline-mesh.md](cards/03-outline-mesh.md)
  - Type: agent · Size: M · Depends: 2
  - Owns: generators/outline.py, generators/geometry.py, analyzer/traverse.py (a Throat's chain), tests/test_outline.py
  - Reqs: 2, 4

- [x] 4. Style files and their tooling
  - Card: [cards/04-style-files.md](cards/04-style-files.md)
  - Type: agent · Size: M · Depends: 1, 3
  - Owns: rules/walls/, generators/wall_styles.py, scripts/topology_rules.py, generators/topology/draw.py, docs/TOPOLOGY_RULES.md, tests/test_wall_styles.py
  - Reqs: 5

- [x] 5. Rooms get Outlines in graph builds
  - Card: [cards/05-styles-in-layout.md](cards/05-styles-in-layout.md)
  - Type: agent · Size: M · Depends: 3, 4
  - Owns: generators/topology/graph.py, generators/topology/ruleset.py, generators/layout_engine.py, generators/builder.py, generators/semantics.py, rules/topology/, tests/test_outline_build.py
  - Reqs: 6, 2.5, 12.3

- [x] 6. Floors and ceilings move
  - Card: [cards/06-relief.md](cards/06-relief.md)
  - Type: agent · Size: M · Depends: 5
  - Owns: generators/outline.py, generators/geometry.py, tests/test_relief.py
  - Reqs: 7

- [x] 7. Walls control, sidecar and maps
  - Card: [cards/07-controls-maps.md](cards/07-controls-maps.md)
  - Type: agent · Size: M · Depends: 5
  - Owns: ai/schema.py, ai/expand.py, main.py, server/app.py, web/index.html, web/src/main.ts, generators/builder.py, generators/mapview.py, tests/test_hygiene.py, tests/test_walls_controls.py
  - Reqs: 11

- [ ] 8. HUMAN: first look at the three styles
  - Card: [cards/08-first-look.md](cards/08-first-look.md)
  - Type: human · Depends: 6, 7

- [ ] 9. Corridors match their rooms
  - Card: [cards/09-corridors.md](cards/09-corridors.md)
  - Type: agent · Size: M · Depends: 8
  - Owns: generators/geometry.py, tests/test_rough_corridors.py
  - Reqs: 8

- [ ] 10. Textures follow the style
  - Card: [cards/10-textures.md](cards/10-textures.md)
  - Type: agent · Size: M · Depends: 8
  - Owns: generators/textures/, generators/semantics.py, tests/test_wall_textures.py
  - Reqs: 9

- [ ] 11. Outdoor dungeons
  - Card: [cards/11-outdoor.md](cards/11-outdoor.md)
  - Type: agent · Size: S · Depends: 8
  - Owns: generators/outdoor_dungeon.py, rules/topology/themes.toml, tests/test_outdoor_walls.py
  - Reqs: 10

- [ ] 12. Gate sweep and stock bands
  - Card: [cards/12-sweep-bands.md](cards/12-sweep-bands.md)
  - Type: agent · Size: M · Depends: 9, 10, 11
  - Owns: tests/test_walls_build.py, rules/walls/
  - Reqs: 12

- [ ] 13. Tune from the looks
  - Card: [cards/13-tuning.md](cards/13-tuning.md)
  - Type: agent · Size: S · Depends: 12
  - Owns: rules/walls/, generators/outline.py, generators/geometry.py, tests/

- [ ] 14. Acceptance section, thorough run, timing
  - Card: [cards/14-release-prep.md](cards/14-release-prep.md)
  - Type: agent · Size: S · Depends: 13
  - Owns: docs/ACCEPTANCE.md, tests/test_walls_build.py
  - Reqs: 12.6, exit criteria 1–2

- [ ] 15. HUMAN: room walls acceptance pass
  - Card: [cards/15-human-acceptance.md](cards/15-human-acceptance.md)
  - Type: human · Depends: 14

- [ ] 16. Close step 8
  - Card: [cards/16-close.md](cards/16-close.md)
  - Type: agent · Size: S · Depends: 15 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-room-walls/, .kiro/specs/zone-generator/
