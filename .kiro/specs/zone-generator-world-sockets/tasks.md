# Tasks — zone-generator-world-sockets (roadmap step 12)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Decisions later tasks rely on are in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card, then the design section it names. Verify both against the
   code; the design was written at `ad392b8`.
3. Work in a worktree (`agent/sockets-<n>`) unless the card says MAIN
   checkout. Edit only the files under `Owns`.
4. Every commit carries the trailer `Task: zone-generator-world-sockets/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**
6. Iterate on your task's own tests and `python -m pytest tests/ -q -m "not slow"`;
   run the full Python suite once before ticking, even for a frontend-only task,
   and don't commit while it runs (a server-staleness test notices).

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it). `Depends` lists task numbers. `Owns` lists the files and folders
the task may edit; two ready tasks with disjoint `Owns` can run in parallel.

**The design's open questions were answered on 2026-11-12** (`archive.md`
"Decisions"). Seven took the recommendation; question 5 (reroll only the failing
stage) was answered yes, which added task 19 and Req 9. Task 14 runs (question 7 yes).

Bytes: with no stage seed set, every build stays step 11's (Req 6.1). Tasks 3-8
and 10 each prove it with `python -m pytest tests/test_layout_engine.py -q` plus
their own goldens. Only task 14 recaptures goldens, and only the Decor-on ones.

## Tasks

- [x] 1. Stage timings and the suite baseline
  - Card: [cards/01-baseline.md](cards/01-baseline.md)
  - Type: agent · Size: S · Depends: —
  - Owns: scripts/stage_timings.py, .kiro/specs/zone-generator-world-sockets/design.md (findings 1 and 2 only)
  - Reqs: 7.5

- [x] 2. Socket and World types
  - Card: [cards/02-types.md](cards/02-types.md)
  - Type: agent · Size: S · Depends: —
  - Owns: generators/world.py, tests/test_world.py
  - Reqs: 1.1, 1.4, 1.5, 5.3

- [x] 3. The World stage
  - Card: [cards/03-world-stage.md](cards/03-world-stage.md)
  - Type: agent · Size: M · Depends: 2
  - Owns: generators/world.py, generators/wilderness/build.py (expose what the World reads; no behaviour change), generators/outdoor_dungeon.py (the hillside Socket's ground; no behaviour change), tests/test_world.py
  - Reqs: 1.2, 1.3, 2.1–2.3

- [x] 4. The outdoor dungeon attaches to its hillside Socket
  - Card: [cards/04-hillside.md](cards/04-hillside.md)
  - Type: agent · Size: M · Depends: 3
  - Owns: generators/outdoor_dungeon.py, generators/stages.py, ai/expand.py (the outdoor-dungeon branch only), tests/test_attach_hillside.py
  - Reqs: 2.4, 3.1, 3.5, 6.1

- [x] 5. Sites attach to the ground Socket
  - Card: [cards/05-ground.md](cards/05-ground.md)
  - Type: agent · Size: M · Depends: 4
  - Owns: generators/sites/placement.py, generators/vegetation/placement.py (`ground_for` from a World), generators/wilderness/build.py (`sites_for`), generators/stages.py, tests/test_attach_ground.py
  - Reqs: 3.2, 3.3, 6.1

- [x] 6. The stages in the build; hand-offs saved
  - Card: [cards/06-handoffs.md](cards/06-handoffs.md)
  - Type: agent · Size: M · Depends: 5
  - Owns: generators/builder.py, generators/pipeline.py (the post-pass writes the hand-offs), generators/stages.py, tests/test_handoffs.py
  - Reqs: 3.3, 5.1, 5.2, 6.3

- [ ] 7. The rooms seed
  - Card: [cards/07-rooms-seed.md](cards/07-rooms-seed.md)
  - Type: agent · Size: M · Depends: 6
  - Owns: ai/schema.py, ai/expand.py, generators/zone_spec.py, generators/builder.py (the sidecar's `seeds` block only), tests/test_stage_seeds.py
  - Reqs: 4.1, 4.2, 4.4, 4.5

- [ ] 8. The rooms seed on the CLI and the server
  - Card: [cards/08-cli-server.md](cards/08-cli-server.md)
  - Type: agent · Size: M · Depends: 7
  - Owns: main.py, server/app.py, tests/test_stage_seeds_controls.py, tests/test_hygiene.py (its control-name guard and allow-lists)
  - Reqs: 4.1

- [ ] 9. Reroll rooms on the page; Sockets on the map
  - Card: [cards/09-page.md](cards/09-page.md)
  - Type: agent · Size: S · Depends: 8
  - Owns: web/src/, web/index.html
  - Reqs: 4.3

- [ ] 10. Stage commands
  - Card: [cards/10-stage-commands.md](cards/10-stage-commands.md)
  - Type: agent · Size: S · Depends: 6
  - Owns: scripts/stage.py, tests/test_stage_script.py
  - Reqs: 5.4

- [x] 11. The World corpus
  - Card: [cards/11-world-corpus.md](cards/11-world-corpus.md)
  - Type: agent · Size: M · Depends: 3
  - Owns: scripts/record_worlds.py, tests/fixtures/worlds/, tests/test_world_corpus.py
  - Reqs: 7.1, 7.3

- [x] 12. Attach tests on the World corpus
  - Card: [cards/12-attach-tests.md](cards/12-attach-tests.md)
  - Type: agent · Size: M · Depends: 5, 11
  - Owns: tests/test_attach_hillside.py, tests/test_attach_ground.py, tests/test_world_corpus.py (the attach contract), tests/test_outdoor_dungeon_build.py (planning-only cases move out), tests/test_site_placement.py (placement-only cases move out)
  - Reqs: 7.2–7.4

- [ ] 13. The suite pass
  - Card: [cards/13-suite-pass.md](cards/13-suite-pass.md)
  - Type: agent · Size: M · Depends: 1, 12
  - Owns: tests/conftest.py (shared sweep builds), tests/test_vertical_build.py, tests/test_graph_layout_build.py, tests/test_walls_build.py, tests/test_features_sweep.py
  - Reqs: 7.5

- [ ] 14. Corridor RoomContexts
  - Card: [cards/14-corridor-contexts.md](cards/14-corridor-contexts.md)
  - Type: agent · Size: M · Depends: 6
  - Owns: generators/room_context.py, scripts/record_rooms.py + tests/fixtures/rooms/, tests/test_room_context.py, tests/test_decor_builds.py, tests/test_decor_bands.py (recaptured bands only); widened by the lead: generators/builder.py (the sidecar `corridors` list and `summary()` counting corridors separately, nothing else), generators/eqmap.py `_sidecar_props`, tests/test_decor_bands.py `_read_back` row order, rules/decor/rooms.toml (rooms' wall lights retuned for corridor lights), tests/test_site_decor_builds.py + tests/test_decor_controls.py (rows in ZON order, corridors included), tests/test_decor_placement.py (room-spacing and light-set tests skip corridors; corridor spacing asserted)
  - Reqs: 8

- [ ] 15. HUMAN: first look
  - Card: [cards/15-first-look.md](cards/15-first-look.md)
  - Type: human · Depends: 9, 10, 14, 19

- [ ] 16. Acceptance section, thorough run
  - Card: [cards/16-acceptance.md](cards/16-acceptance.md)
  - Type: agent · Size: S · Depends: 13, 15
  - Owns: docs/ACCEPTANCE.md

- [ ] 17. HUMAN: World Sockets acceptance pass
  - Card: [cards/17-human-acceptance.md](cards/17-human-acceptance.md)
  - Type: human · Depends: 16

- [ ] 18. Close step 12
  - Card: [cards/18-close.md](cards/18-close.md)
  - Type: agent · Size: S · Depends: 17 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-world-sockets/, .kiro/specs/zone-generator/

- [ ] 19. A gate failure rerolls only the failing stage
  - Card: [cards/19-stage-reroll.md](cards/19-stage-reroll.md)
  - Type: agent · Size: M · Depends: 7
  - Owns: generators/pipeline.py (the retry loop and its helpers), tests/test_stage_reroll.py
  - Reqs: 9
