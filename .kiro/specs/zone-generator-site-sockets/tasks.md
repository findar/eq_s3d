# Tasks — zone-generator-site-sockets (roadmap step 13)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Decisions later tasks rely on are in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card, then the design section it names. Verify both against the
   code; the design was written at `2448243`.
3. Work in a worktree (`agent/site-sockets-<n>`) unless the card says MAIN
   checkout. Edit only the files under `Owns`.
4. Every commit carries the trailer `Task: zone-generator-site-sockets/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**
6. Iterate on your task's own tests and `python -m pytest tests/ -q -m "not slow"`;
   run the full Python suite once before ticking, even for a frontend-only task,
   and don't commit while it runs (a server-staleness test notices).

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it); recaptured golden hashes and re-recorded fixtures don't count.
`Depends` lists task numbers. `Owns` lists the files and folders the task may
edit; two ready tasks with disjoint `Owns` can run in parallel.

**The design's open questions were decided on 2026-11-14** (`archive.md` "Decisions"),
each on its recommendation, so the cards stand as written.

Bytes: dungeon, city and Sites `none` builds never move, nor any Zone_Spec hash
(Req 7.1). Wilderness builds with Sites move once, at task 6; outdoor dungeons
with Sites at tasks 6 and 7. Every other task keeps bytes and proves it with
`python -m pytest tests/test_layout_engine.py tests/test_site_builds.py -q`.

## Tasks

- [x] 1. Stock clustering, measured
  - Card: [cards/01-stock-clustering.md](cards/01-stock-clustering.md)
  - Type: agent · Size: S · Depends: —
  - Owns: scripts/site_clustering.py, .kiro/specs/zone-generator-site-sockets/design.md (finding 1 only)
  - Reqs: 4.1, 2.7

- [x] 2. The clustering rules
  - Card: [cards/02-cluster-rules.md](cards/02-cluster-rules.md)
  - Type: agent · Size: S · Depends: 1
  - Owns: rules/sites/biomes.toml, generators/sites/rules.py, tests/test_site_rules.py
  - Reqs: 2.7

- [x] 3. Choosing points
  - Card: [cards/03-points.md](cards/03-points.md)
  - Type: agent · Size: S · Depends: 2
  - Owns: generators/sites/points.py, tests/test_site_points.py
  - Reqs: 2.2–2.5

- [x] 4. The World offers point Sockets
  - Card: [cards/04-world-points.md](cards/04-world-points.md)
  - Type: agent · Size: M · Depends: 3
  - Owns: generators/world.py, tests/test_world.py, scripts/record_worlds.py, tests/fixtures/worlds/, tests/test_world_corpus.py
  - Reqs: 1, 2.1, 2.5, 2.6

- [ ] 5. Sites stand on points
  - Card: [cards/05-placement.md](cards/05-placement.md)
  - Type: agent · Size: S · Depends: 3
  - Owns: generators/sites/placement.py, tests/test_site_placement.py
  - Reqs: 3.1–3.4, 3.6, 3.7

- [ ] 6. The Sites stage on point Sockets
  - Card: [cards/06-sites-stage.md](cards/06-sites-stage.md)
  - Type: agent · Size: M · Depends: 4, 5
  - Owns: generators/stages.py, generators/wilderness/build.py (`_sites` only), tests/test_attach_ground.py, tests/test_handoffs.py; recaptures: tests/test_layout_engine.py (wilderness and outdoor-dungeon `.eqg` hashes only), tests/test_site_builds.py (STEP10 hashes only), tests/test_site_decor_builds.py (hashes only), tests/fixtures/rooms/ (recordings with Sites, by `scripts/record_rooms.py`)
  - Reqs: 3, 6.1–6.4, 7

- [ ] 7. The outdoor dungeon keeps its dungeon clear
  - Card: [cards/07-outdoor-dungeon.md](cards/07-outdoor-dungeon.md)
  - Type: agent · Size: M · Depends: 6
  - Owns: generators/stages.py (`entrance_keep_clear` only), generators/outdoor_dungeon.py (`keep_clear_shapes` deleted), generators/sites/placement.py (`site_target`'s floor only), tests/test_attach_ground.py, tests/test_world_corpus.py + tests/test_site_builds.py (their `keep_clear_shapes` uses); recaptures: tests/test_layout_engine.py (outdoor-dungeon `.eqg` hash only), tests/test_site_builds.py (outdoor-dungeon hashes only), tests/fixtures/rooms/ (`outdoor_*` recordings with Sites)
  - Reqs: 5, 7.2

- [ ] 8. Retire the area path and recipe spacing
  - Card: [cards/08-retire-spacing.md](cards/08-retire-spacing.md)
  - Type: agent · Size: M · Depends: 7
  - Owns: generators/sites/placement.py, generators/sites/rules.py, rules/sites/sites.toml, tests/test_site_placement.py, tests/test_site_rules.py
  - Reqs: 3.5

- [ ] 9. Point Sockets on the map
  - Card: [cards/09-map.md](cards/09-map.md)
  - Type: agent · Size: M · Depends: 6
  - Owns: generators/mapview.py (the frame attributes only), web/src/sockets.ts, web/src/api.ts, tests/test_properties_mapview.py (the frame only)
  - Reqs: 9

- [ ] 10. The stage command on version 2
  - Card: [cards/10-stage-command.md](cards/10-stage-command.md)
  - Type: agent · Size: S · Depends: 6
  - Owns: scripts/stage.py, tests/test_stage_script.py
  - Reqs: 6.5

- [ ] 11. The clustering target and the gate, held
  - Card: [cards/11-bands-and-gate.md](cards/11-bands-and-gate.md)
  - Type: agent · Size: S · Depends: 7, 8
  - Owns: tests/test_site_bands.py, tests/test_site_builds.py (the outdoor-dungeon sweep only)
  - Reqs: 4, 5.3, 8

- [ ] 12. HUMAN: first look
  - Card: [cards/12-first-look.md](cards/12-first-look.md)
  - Type: human · Depends: 9, 10, 11

- [ ] 13. Acceptance section, thorough run
  - Card: [cards/13-acceptance.md](cards/13-acceptance.md)
  - Type: agent · Size: S · Depends: 12
  - Owns: docs/ACCEPTANCE.md

- [ ] 14. HUMAN: point Site Sockets acceptance pass
  - Card: [cards/14-human-acceptance.md](cards/14-human-acceptance.md)
  - Type: human · Depends: 13

- [ ] 15. Close step 13
  - Card: [cards/15-close.md](cards/15-close.md)
  - Type: agent · Size: S · Depends: 14 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-site-sockets/, .kiro/specs/zone-generator/
