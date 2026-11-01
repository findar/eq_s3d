# Tasks — zone-generator-wilderness-trees (roadmap step 2)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Decisions later tasks rely on are in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card, then the design section it names. Verify both against the
   code; the design was written at `f28ff85`.
3. Work in a worktree (`agent/trees-<n>`) unless the card says MAIN checkout.
   Edit only the files under `Owns`.
4. Every commit carries the trailer
   `Task: zone-generator-wilderness-trees/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it). `Depends` lists task numbers. `Owns` lists the files and folders
the task may edit; two ready tasks with disjoint `Owns` can run in parallel.

The design's four open questions were answered on 2026-10-31
(`archive.md` "Decisions").

## Tasks

- [x] 1. ZON object rotation in radians, yaw in the first field
  - Card: [cards/01-zon-rotation.md](cards/01-zon-rotation.md)
  - Type: agent · Size: S · Depends: —
  - Owns: core/zon.py, tests/test_zon.py
  - Reqs: 8.2

- [ ] 2. Vegetation kit data and loader
  - Card: [cards/02-vegetation-kit.md](cards/02-vegetation-kit.md)
  - Type: agent · Size: S · Depends: —
  - Owns: styles/vegetation.json, generators/vegetation/__init__.py, generators/vegetation/kit.py, tests/test_vegetation_kit.py
  - Reqs: 1

- [ ] 3. Procedural tree models and leaf/bark textures
  - Card: [cards/03-tree-models.md](cards/03-tree-models.md)
  - Type: agent · Size: M · Depends: 2
  - Owns: generators/vegetation/models.py, generators/vegetation/textures.py, tests/test_vegetation_models.py
  - Reqs: 2

- [ ] 4. Tree placement: eligible ground, groves, clearance
  - Card: [cards/04-placement.md](cards/04-placement.md)
  - Type: agent · Size: M · Depends: 2
  - Owns: generators/vegetation/placement.py, tests/test_vegetation_placement.py
  - Reqs: 4, 5

- [ ] 5. Build integration: archive, ZON objects, sidecar, gate
  - Card: [cards/05-build-integration.md](cards/05-build-integration.md)
  - Type: agent · Size: M · Depends: 1, 3, 4
  - Owns: generators/wilderness/build.py, generators/builder.py, tests/test_wilderness_trees.py
  - Reqs: 6, 7, 8.1–8.2, 9.3, 10, 11

- [ ] 6. GLB `vegetation` node
  - Card: [cards/06-glb-node.md](cards/06-glb-node.md)
  - Type: agent · Size: S · Depends: 5
  - Owns: core/eqg.py, generators/builder.py, tests/test_wilderness_trees.py
  - Reqs: 9.1

- [ ] 7. Format gate checks objects, models and textures
  - Card: [cards/07-format-gate.md](cards/07-format-gate.md)
  - Type: agent · Size: S · Depends: 5
  - Owns: analyzer/rof2check.py, tests/test_rof2check.py
  - Reqs: 8.3

- [ ] 8. Density control: prompt, CLI, server
  - Card: [cards/08-density-control.md](cards/08-density-control.md)
  - Type: agent · Size: M · Depends: 5
  - Owns: generators/wilderness/biome_resolve.py, ai/expand.py, main.py, server/app.py, tests/test_wilderness_trees_controls.py
  - Reqs: 3.1–3.3

- [ ] 9. Web: Trees selector and vegetation toggle
  - Card: [cards/09-web.md](cards/09-web.md)
  - Type: agent · Size: M · Depends: 6, 8
  - Owns: web/index.html, web/src/main.ts, web/src/api.ts, web/src/scene.ts, web/src/style.css
  - Reqs: 3.4, 9.2

- [ ] 10. HUMAN: first look at trees in 3D
  - Card: [cards/10-human-first-look.md](cards/10-human-first-look.md)
  - Type: human · Depends: 6

- [ ] 11. Tune from the first look
  - Card: [cards/11-tuning.md](cards/11-tuning.md)
  - Type: agent · Size: S · Depends: 10
  - Owns: styles/vegetation.json, generators/vegetation/

- [ ] 12. Acceptance section, thorough run, timing
  - Card: [cards/12-release-prep.md](cards/12-release-prep.md)
  - Type: agent · Size: S · Depends: 7, 8, 9, 11
  - Owns: docs/ACCEPTANCE.md, tests/test_wilderness_trees.py
  - Reqs: 11.2, exit criteria 1–2

- [ ] 13. HUMAN: trees acceptance pass
  - Card: [cards/13-human-acceptance.md](cards/13-human-acceptance.md)
  - Type: human · Depends: 12

- [ ] 14. Close step 2
  - Card: [cards/14-close.md](cards/14-close.md)
  - Type: agent · Size: S · Depends: 13 · Where: MAIN checkout
  - Owns: ROADMAP.md, tasks/README.md, .kiro/specs/zone-generator/, .kiro/specs/zone-generator-wilderness-trees/

## Out of scope for step 2
Biomes beyond plains; bushes, grass, rocks and props (steps 10–11); trees in
dungeons or cities; real textures (steps 3–4); LOD, animation or seasons; trees
on the EQ `.txt` map; the in-client look (M6). See `requirements.md`.
