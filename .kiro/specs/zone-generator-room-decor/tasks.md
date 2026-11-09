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
6. Iterate on your task's own tests and `python -m pytest tests/ -q -m "not slow"`;
   run the full Python suite once before ticking, even for a frontend-only task,
   and don't commit while it runs (a server-staleness test notices).

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it). `Depends` lists task numbers. `Owns` lists the files and folders
the task may edit; two ready tasks with disjoint `Owns` can run in parallel.

The design's open questions are answered (2026-11-08); the answers are in `archive.md`
"Decisions".

## Tasks

- [x] 1. Catalogue every stock model
  - Card: [cards/01-catalogue.md](cards/01-catalogue.md)
  - Type: agent · Size: M · Depends: —
  - Owns: scripts/prop_catalogue.py, rules/decor/catalogue.json, .kiro/specs/zone-generator-room-decor/design.md (finding 0 only)
  - Reqs: 1.1, 1.2, 1.5

- [x] 2. Measure what fills stock rooms
  - Card: [cards/02-decor-survey.md](cards/02-decor-survey.md)
  - Type: agent · Size: S · Depends: 1
  - Owns: scripts/decor_survey.py, scripts/prop_catalogue.py (the observed fields only), rules/decor/catalogue.json, .kiro/specs/zone-generator-room-decor/design.md (finding 1 only)
  - Reqs: 1.3, 1.4

- [ ] 3. Auto-tags and the review sheet
  - Card: [cards/03-tags-sheet.md](cards/03-tags-sheet.md)
  - Type: agent · Size: M · Depends: 2
  - Owns: scripts/prop_catalogue.py (`tag` and `sheet`), rules/decor/catalogue.json, rules/decor/tags.toml, generators/decor/__init__.py, generators/decor/catalogue.py, tests/test_prop_catalogue.py
  - Reqs: 3

- [ ] 4. HUMAN: review the tags
  - Card: [cards/04-tag-review.md](cards/04-tag-review.md)
  - Type: human · Depends: 3

- [x] 5. The room gate learns placed models
  - Card: [cards/05-gate-props.md](cards/05-gate-props.md)
  - Type: agent · Size: M · Depends: —
  - Owns: analyzer/traverse.py, analyzer/footprints.py, generators/pipeline.py (the room gate's call only), tests/test_gate_props.py
  - Reqs: 2

- [x] 6. Import a catalogued model
  - Card: [cards/06-import.md](cards/06-import.md)
  - Type: agent · Size: M · Depends: 1
  - Owns: generators/decor/stock.py, tests/test_prop_import.py
  - Reqs: 4

- [ ] 7. Decor recipes as data
  - Card: [cards/07-decor-files.md](cards/07-decor-files.md)
  - Type: agent · Size: M · Depends: 3
  - Owns: rules/decor/rooms.toml, rules/decor/sets.toml, generators/decor/rules.py, scripts/topology_rules.py (a `decor` check and draw), tests/test_decor_rules.py
  - Reqs: 5, 7

- [ ] 8. Decor placement in rooms
  - Card: [cards/08-placement.md](cards/08-placement.md)
  - Type: agent · Size: M · Depends: 7, 18
  - Owns: generators/decor/placement.py, tests/test_decor_placement.py, scripts/decor_room.py
  - Reqs: 5, 6, 8, 13.4, 13.5

- [ ] 9. Decor in builds
  - Card: [cards/09-in-builds.md](cards/09-in-builds.md)
  - Type: agent · Size: M · Depends: 4, 5, 6, 8
  - Owns: generators/builder.py, generators/pipeline.py, generators/zone_spec.py, generators/outdoor_dungeon.py, tests/test_decor_builds.py, tests/test_texture_manifest.py (the `decor` texture mode)
  - Reqs: 6.4, 9, 10.3, 10.5, 10.6, 12.2, 12.3

- [ ] 10. Decor controls, decor seed, sidecar and maps
  - Card: [cards/10-controls-maps.md](cards/10-controls-maps.md)
  - Type: agent · Size: M · Depends: 9
  - Owns: ai/schema.py, ai/expand.py, ai/rule_planner.py, main.py, server/app.py, web/src/, web/index.html, generators/eqmap.py, generators/mapview.py, tests/test_decor_controls.py, tests/test_hygiene.py (its control-name guard and allow-lists), generators/pipeline.py (`_write_map_artifacts` passes the built Props)
  - Reqs: 10.1–10.4

- [ ] 11. Site Props
  - Card: [cards/11-site-props.md](cards/11-site-props.md)
  - Type: agent · Size: M · Depends: 9, 18
  - Owns: rules/decor/rooms.toml (Site recipes only), generators/decor/placement.py (Site POIs), generators/sites/placement.py (hand Site POIs to decor), tests/test_site_props.py, tests/test_site_builds.py (its Decor `none` cases), scripts/record_rooms.py + tests/fixtures/rooms/ (add a farmstead recording)
  - Reqs: 11

- [ ] 12. HUMAN: first look at decorated rooms
  - Card: [cards/12-first-look.md](cards/12-first-look.md)
  - Type: human · Depends: 10, 11

- [ ] 13. Tune from the first look
  - Card: [cards/13-tune.md](cards/13-tune.md)
  - Type: agent · Size: M · Depends: 12
  - Owns: rules/decor/rooms.toml, rules/decor/sets.toml, rules/decor/tags.toml (only corrections the user gave), generators/decor/, tests/test_layout_engine.py (goldens with Decor on)

- [ ] 14. Gate sweep and stock bands
  - Card: [cards/14-sweep-bands.md](cards/14-sweep-bands.md)
  - Type: agent · Size: S · Depends: 2, 13
  - Owns: tests/test_decor_bands.py
  - Reqs: 12.1, 12.4

- [ ] 15. Acceptance section, thorough run
  - Card: [cards/15-acceptance.md](cards/15-acceptance.md)
  - Type: agent · Size: S · Depends: 14
  - Owns: docs/ACCEPTANCE.md

- [ ] 16. HUMAN: decorating rooms acceptance pass
  - Card: [cards/16-human-acceptance.md](cards/16-human-acceptance.md)
  - Type: human · Depends: 15

- [ ] 17. Close step 11
  - Card: [cards/17-close.md](cards/17-close.md)
  - Type: agent · Size: S · Depends: 16 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-room-decor/, .kiro/specs/zone-generator/

- [x] 18. RoomContext and the room corpus
  - Card: [cards/18-room-context.md](cards/18-room-context.md)
  - Type: agent · Size: M · Depends: —
  - Owns: generators/room_context.py, generators/room_layouts.py (export what a context needs, no behaviour change), generators/sites/placement.py (a Site's context, no behaviour change), scripts/record_rooms.py, tests/fixtures/rooms/, tests/test_room_context.py
  - Reqs: 13.1–13.3
