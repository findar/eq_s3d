# Tasks — zone-generator-m2-true-layout-artifacts (roadmap step 1b)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Decisions later tasks rely on are in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card, then the design section it names. Verify both against the
   code; the design was written at `5dabd21`, before M1 finished and before
   wilderness was enabled.
3. Work in a worktree (`agent/m2-<n>`) unless the card says MAIN checkout.
   Edit only the files under `Owns`.
4. Every commit carries the trailer
   `Task: zone-generator-m2-true-layout-artifacts/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it). `Depends` lists task numbers. `Owns` lists the files and folders
the task may edit; two ready tasks with disjoint `Owns` can run in parallel.

**M1 dependencies D1–D7 are all on master** (checked at `a211efb`):
`generators/routing.py` (`corridor_route`, `route_footprint`), the union-find
`WalkSurface.component`, the `zone_type` vocabulary, wilderness enabled,
scratch attempts in `generate_validated`, the M1 response shape, and
`core/paths.OutputRoot` with `/api/zones/{zone_id}/{version}/{filename}`. The
design's "interim if M1 is late" column no longer applies.

## Tasks

- [x] 1. EQ map core: convention, grounding, format, parse
  - Card: [cards/01-eqmap-core.md](cards/01-eqmap-core.md)
  - Type: agent · Size: S · Depends: —
  - Owns: generators/eqmap.py, tests/test_eqmap.py
  - Reqs: 4, 5.2, 6

- [x] 2. Walls beside and above every doorway
  - Card: [cards/02-doorway-walls.md](cards/02-doorway-walls.md)
  - Type: agent · Size: S · Depends: —
  - Owns: generators/geometry.py, tests/test_generators.py

- [x] 3. Outline extractor and depth bands on synthetic worlds
  - Card: [cards/03-outline-synthetic.md](cards/03-outline-synthetic.md)
  - Type: agent · Size: M · Depends: —
  - Owns: generators/mapgeom.py, analyzer/traverse.py, tests/strategies.py, tests/pbt_helpers.py, tests/test_properties_mapgeom.py
  - Reqs: 1, 2

- [x] 4. Outline on box builds
  - Card: [cards/04-outline-box-builds.md](cards/04-outline-box-builds.md)
  - Type: agent · Size: M · Depends: 2, 3
  - Owns: generators/mapgeom.py, tests/pbt_helpers.py, tests/test_properties_mapgeom.py
  - Reqs: 1.1–1.4, 1.7

- [x] 5. Outline layer in the map SVG
  - Card: [cards/05-svg-outline-layer.md](cards/05-svg-outline-layer.md)
  - Type: agent · Size: M · Depends: 3
  - Owns: generators/mapview.py, tests/reference_mapview.py, tests/test_properties_mapview.py
  - Reqs: 7

- [x] 6. EQ map layers from the outline
  - Card: [cards/06-eqmap-layers.md](cards/06-eqmap-layers.md)
  - Type: agent · Size: S · Depends: 1, 4
  - Owns: generators/eqmap.py, tests/test_eqmap.py
  - Reqs: 5.1, 5.3–5.7

- [x] 7. Pipeline post-pass: map artifacts for accepted builds only
  - Card: [cards/07-pipeline-post-pass.md](cards/07-pipeline-post-pass.md)
  - Type: agent · Size: M · Depends: 5, 6
  - Owns: generators/pipeline.py, generators/builder.py, analyzer/traverse.py, tests/test_pipeline.py, tests/test_properties_pipeline.py
  - Reqs: 3, 8

- [x] 8. Serve build files under `maps/`, HEAD, and artifact URLs
  - Card: [cards/08-serve-build-files.md](cards/08-serve-build-files.md)
  - Type: agent · Size: S · Depends: 7
  - Owns: server/app.py, tests/test_server.py
  - Reqs: 9

- [ ] 9. Artifacts panel in the web app
  - Card: [cards/09-artifacts-panel.md](cards/09-artifacts-panel.md)
  - Type: agent · Size: M · Depends: 8
  - Owns: web/index.html, web/src/artifacts.ts, web/src/main.ts, web/src/api.ts, web/src/style.css
  - Reqs: 10

- [ ] 10. `.txt` overlay preview script
  - Card: [cards/10-overlay-preview.md](cards/10-overlay-preview.md)
  - Type: agent · Size: S · Depends: 7
  - Owns: scripts/eqmap_preview.py

- [ ] 11. Wilderness coverage, acceptance section, thorough run
  - Card: [cards/11-wilderness-and-release-prep.md](cards/11-wilderness-and-release-prep.md)
  - Type: agent · Size: M · Depends: 7, 8, 9, 10, 14
  - Owns: tests/test_properties_mapgeom.py, tests/test_eqmap.py, docs/ACCEPTANCE.md
  - Reqs: 1.7, exit criteria 1–3

- [ ] 12. HUMAN: true-layout map acceptance pass
  - Card: [cards/12-human-acceptance.md](cards/12-human-acceptance.md)
  - Type: human · Depends: 11

- [ ] 13. Close step 1b
  - Card: [cards/13-close.md](cards/13-close.md)
  - Type: agent · Size: S · Depends: 12 · Where: MAIN checkout
  - Owns: ROADMAP.md, tasks/README.md, .kiro/specs/zone-generator/, .kiro/specs/zone-generator-m2-true-layout-artifacts/

- [x] 14. Corridors stay out of rooms; corridor bends have walls
  - Card: [cards/14-corridors-clear-of-rooms.md](cards/14-corridors-clear-of-rooms.md)
  - Type: agent · Size: M · Depends: 2, 3
  - Owns: generators/layout.py, generators/routing.py, generators/geometry.py, tests/test_corridor_clearance.py
  - Added 2026-10-31 from tasks 4 and 5's findings; numbered last so other numbers stay stable.

## Out of scope for step 1b
The Export (`export/<short>/`), Target_Shortname picker, `<short>.sql` and the
bundle `.zip` (M6); the in-client `.txt` check (moved to M6, see `archive.md`);
district hulls (M3); contour or path lines on wilderness maps; boss names on
labels (M3). See `requirements.md` "Explicitly out of M2".
