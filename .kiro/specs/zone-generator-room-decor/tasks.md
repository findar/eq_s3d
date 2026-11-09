# Tasks — zone-generator-room-decor (roadmap step 11)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Decisions later tasks rely on are in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card, then the design section it names. Verify both against the
   code; the design was written at `e50ecfc`.
3. Work in a worktree (`agent/decor-<n>`) unless the card says MAIN
   checkout. Edit only the files under `Owns`.
4. Every commit carries the trailer `Task: zone-generator-room-decor/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**
6. Run the full Python suite before ticking, even for a frontend-only task,
   and don't commit while it runs (a server-staleness test notices).

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it). `Depends` lists task numbers. `Owns` lists the files and folders
the task may edit; two ready tasks with disjoint `Owns` can run in parallel.

**No task starts until the design's open questions are answered**; the answers go in
`archive.md` "Decisions".

## Tasks

- [ ] 1. Measure what fills stock rooms
  - Card: [cards/01-decor-survey.md](cards/01-decor-survey.md)
  - Type: agent · Size: S · Depends: —
  - Owns: scripts/decor_survey.py, .kiro/specs/zone-generator-room-decor/design.md (finding 1 only)
  - Reqs: 1

- [ ] 2. The room gate learns placed models
  - Card: [cards/02-gate-props.md](cards/02-gate-props.md)
  - Type: agent · Size: M · Depends: —
  - Owns: analyzer/traverse.py, analyzer/footprints.py, generators/pipeline.py (the room gate's call only), tests/test_gate_props.py
  - Reqs: 2

- [ ] 3. Prop models
  - Card: [cards/03-prop-models.md](cards/03-prop-models.md)
  - Type: agent · Size: M · Depends: 1, 5
  - Owns: generators/decor/models.py, tests/test_prop_models.py, rules/decor/props.toml (finding 1's sizes in place of the placeholders)
  - Reqs: 3

- [ ] 4. Prop textures
  - Card: [cards/04-prop-textures.md](cards/04-prop-textures.md)
  - Type: agent · Size: S · Depends: —
  - Owns: generators/textures/decor.py, tests/test_prop_textures.py
  - Reqs: 4

- [ ] 5. Decor recipes as data
  - Card: [cards/05-decor-files.md](cards/05-decor-files.md)
  - Type: agent · Size: M · Depends: —
  - Owns: rules/decor/, generators/decor/rules.py, generators/decor/__init__.py, scripts/topology_rules.py (a `decor` check and draw), tests/test_decor_rules.py
  - Reqs: 6

- [ ] 6. Decor placement in rooms
  - Card: [cards/06-placement.md](cards/06-placement.md)
  - Type: agent · Size: M · Depends: 5
  - Owns: generators/decor/placement.py, tests/test_decor_placement.py, generators/room_layouts.py (expose the plan grid and wall faces, no behaviour change)
  - Reqs: 5, 7

- [ ] 7. Decor in builds
  - Card: [cards/07-in-builds.md](cards/07-in-builds.md)
  - Type: agent · Size: M · Depends: 2, 3, 4, 6
  - Owns: generators/builder.py, generators/pipeline.py, generators/zone_spec.py, generators/outdoor_dungeon.py, tests/test_decor_builds.py, tests/test_texture_manifest.py (the `decor` texture mode)
  - Reqs: 5.4, 8, 9.3, 9.5, 11.2, 11.3

- [ ] 8. Decor controls, decor seed, sidecar and maps
  - Card: [cards/08-controls-maps.md](cards/08-controls-maps.md)
  - Type: agent · Size: M · Depends: 7
  - Owns: ai/schema.py, ai/expand.py, ai/rule_planner.py, main.py, server/app.py, web/src/, web/index.html, generators/eqmap.py, generators/mapview.py, tests/test_decor_controls.py, tests/test_hygiene.py (its control-name guard and allow-lists), generators/pipeline.py (`_write_map_artifacts` passes the built Props)
  - Reqs: 9.1–9.4

- [ ] 9. Site Props
  - Card: [cards/09-site-props.md](cards/09-site-props.md)
  - Type: agent · Size: M · Depends: 7
  - Owns: rules/decor/ (Site recipes only), generators/decor/placement.py (Site POIs), generators/sites/placement.py (hand Site POIs to decor), tests/test_site_props.py, tests/test_site_builds.py (its Decor `none` cases)
  - Reqs: 10

- [ ] 10. HUMAN: first look at decorated rooms
  - Card: [cards/10-first-look.md](cards/10-first-look.md)
  - Type: human · Depends: 8, 9

- [ ] 11. Tune from the first look
  - Card: [cards/11-tune.md](cards/11-tune.md)
  - Type: agent · Size: M · Depends: 10
  - Owns: rules/decor/, generators/decor/, tests/test_layout_engine.py (goldens with Decor on)

- [ ] 12. Gate sweep and stock bands
  - Card: [cards/12-sweep-bands.md](cards/12-sweep-bands.md)
  - Type: agent · Size: S · Depends: 1, 11
  - Owns: tests/test_decor_bands.py
  - Reqs: 11.1, 11.4

- [ ] 13. Acceptance section, thorough run
  - Card: [cards/13-acceptance.md](cards/13-acceptance.md)
  - Type: agent · Size: S · Depends: 12
  - Owns: docs/ACCEPTANCE.md

- [ ] 14. HUMAN: decorating rooms acceptance pass
  - Card: [cards/14-human-acceptance.md](cards/14-human-acceptance.md)
  - Type: human · Depends: 13

- [ ] 15. Close step 11
  - Card: [cards/15-close.md](cards/15-close.md)
  - Type: agent · Size: S · Depends: 14 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-room-decor/, .kiro/specs/zone-generator/
