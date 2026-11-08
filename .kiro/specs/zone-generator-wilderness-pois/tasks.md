# Tasks — zone-generator-wilderness-pois (roadmap step 10)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Decisions later tasks rely on are in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card, then the design section it names. Verify both against the
   code; the design was written at `28b6781`.
3. Work in a worktree (`agent/sites-<n>`) unless the card says MAIN
   checkout. Edit only the files under `Owns`.
4. Every commit carries the trailer `Task: zone-generator-wilderness-pois/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**
6. Run the full Python suite before ticking, even for a frontend-only task,
   and don't commit while it runs (a server-staleness test notices).

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it). `Depends` lists task numbers. `Owns` lists the files and folders
the task may edit; two ready tasks with disjoint `Owns` can run in parallel.

The design's open questions are answered (2026-11-07); the answers are in `archive.md`
"Decisions".

## Tasks


- [x] 1. Measure the stock Sites
  - Card: [cards/01-site-survey.md](cards/01-site-survey.md)
  - Type: agent · Size: S · Depends: —
  - Owns: scripts/site_survey.py, .kiro/specs/zone-generator-wilderness-pois/design.md (finding 1 only)
  - Reqs: 1

- [x] 2. The gate learns Structures
  - Card: [cards/02-gate-footprints.md](cards/02-gate-footprints.md)
  - Type: agent · Size: M · Depends: —
  - Owns: generators/wilderness/build.py (`trees_block` and `bowl_report`), analyzer/footprints.py, tests/test_gate_footprints.py
  - Reqs: 2

- [x] 3. Structure models
  - Card: [cards/03-structure-models.md](cards/03-structure-models.md)
  - Type: agent · Size: M · Depends: 1
  - Owns: generators/sites/models.py, generators/sites/__init__.py, tests/test_site_models.py, rules/sites/ (replace the placeholders with finding 1's values; task 4's material set names), tests/test_site_rules.py (only the TOML fragments its mutation tests search for), tests/test_site_placement.py (the misfit test picks its own kind)
  - Reqs: 3.1–3.3, 3.5

- [x] 4. Structure textures
  - Card: [cards/04-structure-textures.md](cards/04-structure-textures.md)
  - Type: agent · Size: S · Depends: —
  - Owns: generators/textures/ (site materials only), tests/test_site_textures.py
  - Reqs: 3.4

- [x] 5. Site recipes as data
  - Card: [cards/05-site-files.md](cards/05-site-files.md)
  - Type: agent · Size: M · Depends: —
  - Owns: rules/sites/, generators/sites/rules.py, scripts/topology_rules.py (a `sites` check and draw), tests/test_site_rules.py
  - Reqs: 5

- [x] 6. Site placement
  - Card: [cards/06-placement.md](cards/06-placement.md)
  - Type: agent · Size: M · Depends: 5
  - Owns: generators/sites/placement.py, generators/vegetation/placement.py (Kept_Clear grows by Site ground), tests/test_site_placement.py
  - Reqs: 4, 6

- [x] 7. Sites in builds
  - Card: [cards/07-in-builds.md](cards/07-in-builds.md)
  - Type: agent · Size: M · Depends: 2, 3, 4, 6
  - Owns: generators/builder.py, generators/wilderness/build.py, generators/outdoor_dungeon.py, generators/zone_spec.py, tests/test_site_builds.py, generators/sites/placement.py (its clear width becomes the gate's), generators/pipeline.py (only if the gate's POIs need it), tests/test_wilderness_trees.py + tests/test_gate_footprints.py (tree-only cases set Sites none), tests/test_texture_manifest.py (the `sites` texture mode)
  - Reqs: 4.4, 7, 8.2, 8.4, 9.2, 9.3

- [x] 8. Sites controls, sidecar and maps
  - Card: [cards/08-controls-maps.md](cards/08-controls-maps.md)
  - Type: agent · Size: M · Depends: 7
  - Owns: ai/schema.py, ai/expand.py, ai/rule_planner.py, main.py, server/app.py, web/src/, generators/eqmap.py, generators/mapview.py, tests/test_site_controls.py, tests/test_hygiene.py (its control-name guard and allow-lists), web/index.html (the Sites and Inhabitant selects), generators/pipeline.py (`_write_map_artifacts` passes the built Sites to the maps)
  - Reqs: 8.1, 8.3

- [x] 9. HUMAN: first look at Sites
  - Card: [cards/09-first-look.md](cards/09-first-look.md)
  - Type: human · Depends: 8, 15

- [ ] 10. Tune from the first look
  - Card: [cards/10-tune.md](cards/10-tune.md)
  - Type: agent · Size: M · Depends: 9
  - Owns: rules/sites/, generators/sites/, tests/test_layout_engine.py (the wilderness golden)
  - Note: no first-look findings; task 11's sweep found Sites too full (stock is half lone Structures), so task 10 tunes that, run in task 11's worktree.

- [ ] 11. Gate sweep and stock bands
  - Card: [cards/11-sweep-bands.md](cards/11-sweep-bands.md)
  - Type: agent · Size: S · Depends: 1, 10
  - Owns: tests/test_site_bands.py
  - Reqs: 9.1, 9.4

- [ ] 12. Acceptance section, thorough run
  - Card: [cards/12-acceptance.md](cards/12-acceptance.md)
  - Type: agent · Size: S · Depends: 11
  - Owns: docs/ACCEPTANCE.md

- [ ] 13. HUMAN: wilderness POIs acceptance pass
  - Card: [cards/13-human-acceptance.md](cards/13-human-acceptance.md)
  - Type: human · Depends: 12

- [ ] 14. Close step 10
  - Card: [cards/14-close.md](cards/14-close.md)
  - Type: agent · Size: S · Depends: 13 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-wilderness-pois/, .kiro/specs/zone-generator/

- [x] 15. Camps keep their tents; outdoor dungeons get Sites
  - Card: [cards/15-camps-and-counts.md](cards/15-camps-and-counts.md)
  - Type: agent · Size: S · Depends: 7
  - Owns: rules/sites/, generators/sites/placement.py, tests/test_site_placement.py, tests/test_layout_engine.py (the wilderness golden), tests/test_site_builds.py (P8's seeds)
  - Reqs: 4, 7
