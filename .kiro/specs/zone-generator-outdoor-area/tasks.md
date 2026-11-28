# Tasks — zone-generator-outdoor-area (roadmap step 35)

This file is an **index**. Each task has a card in `cards/`. Rules: "Card-format specs" in
`.kiro/steering/project.md`. Work in a worktree (`agent/area-<n>`), edit only `Owns`, trailer
`Task: zone-generator-outdoor-area/<n>`. **Never tick a `Type: human` task.** Starts after steps 32 and 34
land (both touch the layout or the defaults this builds on).

## Tasks

- [x] 1. Measure stock outdoor zones: extent, host features, ways in
  - Card: [cards/01-measure.md](cards/01-measure.md)
  - Type: agent · Size: M · Depends: —
  - Owns: scripts/stock_outdoor_area.py (new)
  - Reqs: 1

- [x] 2. Area features by theme (the lava patch)
  - Card: [cards/02-features.md](cards/02-features.md)
  - Type: agent · Size: S · Depends: 3
  - Owns: generators/wilderness/matrix.py (the lava patch only), ai/expand.py, generators/world.py, generators/wilderness/build.py and generators/outdoor_dungeon.py (passing the lava flag through only), tests/test_wilderness*.py
  - Reqs: 3

- [x] 3. The area is read once
  - Card: [cards/03-read-once.md](cards/03-read-once.md)
  - Type: agent · Size: S · Depends: —
  - Owns: generators/outdoor_dungeon.py, generators/wilderness/build.py
  - Reqs: 4

- [x] 4. A host sized to what it holds
  - Card: [cards/04-host-size.md](cards/04-host-size.md)
  - Type: agent · Size: M · Depends: 1, 3
  - Owns: generators/outdoor_dungeon.py, generators/wilderness/matrix.py (host Landform sizing), tests/test_outdoor_dungeon*.py
  - Reqs: 5, 7

- [x] 5. A wide, flaring Mouth
  - Card: [cards/05-entrances.md](cards/05-entrances.md)
  - Type: agent · Size: M · Depends: 1, 4
  - Owns: generators/outdoor_dungeon.py, generators/stages.py (the Apron edit), tests/test_outdoor_dungeon*.py, tests/test_attach_*.py, the outdoor goldens and recordings it moves
  - Reqs: 6, 7

- [x] 12. A second way in: the cliff opening
  - Card: [cards/12-cliff-opening.md](cards/12-cliff-opening.md)
  - Type: agent · Size: M · Depends: 5
  - Owns: generators/outdoor_dungeon.py, generators/stages.py (the Apron edit), generators/mapview.py (the entrance mark), tests/test_outdoor_dungeon*.py, the outdoor goldens and recordings it moves
  - Reqs: 6, 7

- [x] 6. Area size from the plan
  - Card: [cards/06-area-size.md](cards/06-area-size.md)
  - Type: agent · Size: M · Depends: 1, 2, 5
  - Owns: generators/wilderness/matrix.py, ai/schema.py (wilderness size), ai/rule_planner.py (size words), server/app.py (pass-through), web/src/controls.ts or main.ts (the Size control for outdoor), tests/
  - Reqs: 2, 7

- [ ] 11. Sites pack and cluster like stock
  - Card: [cards/11-sites.md](cards/11-sites.md)
  - Type: agent · Size: M · Depends: 2, 6
  - Owns: generators/sites/, tests/test_site_bands.py, tests/test_site_points.py, the Site and wilderness goldens and recordings it moves

- [ ] 7. Gate, bands and time
  - Card: [cards/07-gate.md](cards/07-gate.md)
  - Type: agent · Size: S · Depends: 6, 11, 12
  - Owns: fixes only where a failure is new (stop and report first)
  - Reqs: 7

- [ ] 8. Acceptance section
  - Card: [cards/08-acceptance.md](cards/08-acceptance.md)
  - Type: agent · Size: S · Depends: 7
  - Owns: docs/ACCEPTANCE.md (or its split, if the docs refactor landed)

- [ ] 9. HUMAN: look
  - Card: [cards/09-look.md](cards/09-look.md)
  - Type: human · Depends: 8

- [ ] 10. Close step 35
  - Card: [cards/10-close.md](cards/10-close.md)
  - Type: agent · Size: S · Depends: 9 · Where: MAIN checkout
  - Owns: ROADMAP.md, OPEN.md, docs/pillars/ (P-2, P-7, P-8, P-9 plans and open items), .kiro/specs/zone-generator-outdoor-area/
