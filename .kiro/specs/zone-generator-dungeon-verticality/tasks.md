# Tasks — zone-generator-dungeon-verticality (roadmap step 7)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Decisions later tasks rely on are in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card, then the design section it names. Verify both against the
   code; the design was written at `8edf1df`.
3. Work in a worktree (`agent/vert-<n>`) unless the card says MAIN
   checkout. Edit only the files under `Owns`.
4. Every commit carries the trailer
   `Task: zone-generator-dungeon-verticality/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**
6. Run the full Python suite before ticking, even for a frontend-only task
   (step 6's task 11 broke two hygiene tests that way), and don't commit
   while it runs (a server-staleness test notices).

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it). `Depends` lists task numbers. `Owns` lists the files and folders
the task may edit; two ready tasks with disjoint `Owns` can run in parallel.

The design's open questions were answered on 2026-11-04 (`archive.md`
"Decisions"): bridges stay in the step as task 11, after the first look.

## Tasks

- [x] 1. Measure the stock vertical anatomy
  - Card: [cards/01-vertical-survey.md](cards/01-vertical-survey.md)
  - Type: agent · Size: M · Depends: —
  - Owns: scripts/dungeon_vertical_survey.py, .kiro/specs/zone-generator-dungeon-verticality/design.md
  - Reqs: 1

- [x] 2. The gate learns stairs and bridges
  - Card: [cards/02-gate-connectors.md](cards/02-gate-connectors.md)
  - Type: agent · Size: M · Depends: —
  - Owns: analyzer/traverse.py, tests/test_traverse_connectors.py
  - Reqs: 2

- [x] 3. Stair geometry and switchbacks
  - Card: [cards/03-stair-geometry.md](cards/03-stair-geometry.md)
  - Type: agent · Size: M · Depends: 2
  - Owns: generators/geometry.py, tests/test_stair_geometry.py, analyzer/traverse.py (planned stairs)
  - Reqs: 3.1–3.3

- [ ] 4. Levels and stacking in the graph engine
  - Card: [cards/04-levels.md](cards/04-levels.md)
  - Type: agent · Size: M · Depends: 1
  - Owns: generators/topology/rewrite.py, generators/topology/ruleset.py, generators/topology/embed.py, generators/layout_engine.py, tests/test_topology_levels.py
  - Reqs: 4.1, 4.2

- [ ] 5. The shared layout steps in 3D
  - Card: [cards/05-job-b-3d.md](cards/05-job-b-3d.md)
  - Type: agent · Size: M · Depends: 3, 4
  - Owns: generators/layout.py, generators/routing.py, generators/zone_spec.py, analyzer/traverse.py (room faces only), tests/test_layout_levels.py
  - Reqs: 4.3–4.5

- [ ] 6. The rules go up and down
  - Card: [cards/06-vertical-rules.md](cards/06-vertical-rules.md)
  - Type: agent · Size: M · Depends: 1, 5
  - Owns: rules/topology/, ai/expand.py, tests/test_ruleset_classic_eq.py, tests/test_ruleset_warren.py, tests/test_topology_levels.py
  - Reqs: 5, 6

- [ ] 7. Outdoor dungeons go down
  - Card: [cards/07-outdoor-levels.md](cards/07-outdoor-levels.md)
  - Type: agent · Size: M · Depends: 6, 17
  - Owns: generators/outdoor_dungeon.py, generators/envelope.py, tests/test_outdoor_levels.py
  - Reqs: 7

- [ ] 8. Controls, sidecar and maps
  - Card: [cards/08-controls-sidecar-maps.md](cards/08-controls-sidecar-maps.md)
  - Type: agent · Size: S · Depends: 5
  - Owns: web/src/main.ts, generators/builder.py, tests/test_level_sidecar_maps.py
  - Reqs: 8

- [ ] 9. Gate sweep on built multi-level zones
  - Card: [cards/09-gate-sweep.md](cards/09-gate-sweep.md)
  - Type: agent · Size: M · Depends: 6, 7, 8, 17
  - Owns: tests/test_vertical_build.py, generators/topology/embed.py, rules/topology/
  - Reqs: 9

- [ ] 10. HUMAN: first look at multi-level dungeons
  - Card: [cards/10-human-first-look.md](cards/10-human-first-look.md)
  - Type: human · Depends: 9

- [ ] 11. Bridges
  - Card: [cards/11-bridges.md](cards/11-bridges.md)
  - Type: agent · Size: M · Depends: 10
  - Owns: generators/geometry.py, generators/layout.py, generators/topology/embed.py, analyzer/traverse.py, rules/topology/, tests/test_bridges.py
  - Reqs: 2.1, 3.4

- [ ] 12. Tune from the first look
  - Card: [cards/12-tuning.md](cards/12-tuning.md)
  - Type: agent · Size: S · Depends: 10, 11
  - Owns: rules/topology/, generators/topology/, generators/geometry.py (stairs), tests/test_vertical_build.py

- [ ] 13. Acceptance section, thorough run, timing
  - Card: [cards/13-release-prep.md](cards/13-release-prep.md)
  - Type: agent · Size: S · Depends: 12
  - Owns: docs/ACCEPTANCE.md, tests/test_vertical_build.py
  - Reqs: 9.4, exit criteria 1–2

- [ ] 14. HUMAN: verticality acceptance pass
  - Card: [cards/14-human-acceptance.md](cards/14-human-acceptance.md)
  - Type: human · Depends: 13

- [ ] 15. Close step 7
  - Card: [cards/15-close.md](cards/15-close.md)
  - Type: agent · Size: S · Depends: 14 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-dungeon-verticality/, .kiro/specs/zone-generator/

- [ ] 16. Measure race body heights and stock room sizes
  - Card: [cards/16-race-survey.md](cards/16-race-survey.md)
  - Type: agent · Size: M · Depends: —
  - Owns: scripts/race_size_survey.py, .kiro/specs/zone-generator-dungeon-verticality/design.md (finding 8 only)
  - Reqs: 10.1

- [ ] 17. Rooms sized for their race
  - Card: [cards/17-race-rooms.md](cards/17-race-rooms.md)
  - Type: agent · Size: M · Depends: 5, 16
  - Owns: generators/semantics.py, generators/topology/embed.py, generators/layout.py, ai/schema.py, web/index.html, tests/test_race_sizing.py, tests/test_layout_engine.py (raced goldens, deliberately)
  - Reqs: 10
