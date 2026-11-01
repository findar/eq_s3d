# Tasks — zone-generator-placeholder-textures (roadmap step 3)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Decisions later tasks rely on are in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card, then the design section it names. Verify both against the
   code; the design was written at `d77cee3`.
3. Work in a worktree (`agent/textures-<n>`) unless the card says MAIN
   checkout. Edit only the files under `Owns`.
4. Every commit carries the trailer
   `Task: zone-generator-placeholder-textures/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it). `Depends` lists task numbers. `Owns` lists the files and folders
the task may edit; two ready tasks with disjoint `Owns` can run in parallel.

The design's four open questions were answered on 2026-11-01
(`archive.md` "Decisions").

## Tasks

- [x] 1. Material names by set and surface; real shaders
  - Card: [cards/01-material-names.md](cards/01-material-names.md)
  - Type: agent · Size: M · Depends: —
  - Owns: generators/layout.py, generators/semantics.py, analyzer/rof2check.py, tests/test_material_names.py, tests/test_rof2check.py
  - Reqs: 1, 2, 7.1

- [x] 2. Bitmap font and placeholder painter
  - Card: [cards/02-placeholder-painter.md](cards/02-placeholder-painter.md)
  - Type: agent · Size: M · Depends: —
  - Owns: generators/textures/font.py, generators/textures/placeholder.py, tests/test_placeholder_textures.py
  - Reqs: 3

- [x] 3. Texture mode and texture manifest
  - Card: [cards/03-mode-and-manifest.md](cards/03-mode-and-manifest.md)
  - Type: agent · Size: M · Depends: 1, 2
  - Owns: generators/textures/base.py, generators/textures/factory.py, generators/builder.py, tests/test_texture_manifest.py
  - Reqs: 4, 5

- [x] 4. Textured GLB terrain
  - Card: [cards/04-textured-glb.md](cards/04-textured-glb.md)
  - Type: agent · Size: M · Depends: 3
  - Owns: core/eqg.py, generators/builder.py, tests/test_glb_textures.py
  - Reqs: 6.1–6.3

- [ ] 5. Web renders the textured preview
  - Card: [cards/05-web-textures.md](cards/05-web-textures.md)
  - Type: agent · Size: S · Depends: 4
  - Owns: web/src/scene.ts, web/src/main.ts
  - Reqs: 6.4–6.6

- [ ] 6. HUMAN: first look at placeholders in 3D
  - Card: [cards/06-human-first-look.md](cards/06-human-first-look.md)
  - Type: human · Depends: 5

- [ ] 7. Tune from the first look
  - Card: [cards/07-tuning.md](cards/07-tuning.md)
  - Type: agent · Size: S · Depends: 6
  - Owns: generators/textures/placeholder.py, generators/textures/font.py, tests/test_placeholder_textures.py

- [ ] 8. Acceptance section, thorough run, timing
  - Card: [cards/08-release-prep.md](cards/08-release-prep.md)
  - Type: agent · Size: S · Depends: 7
  - Owns: docs/ACCEPTANCE.md, tests/test_texture_manifest.py
  - Reqs: 8, exit criteria 1–2

- [ ] 9. HUMAN: placeholder textures acceptance pass
  - Card: [cards/09-human-acceptance.md](cards/09-human-acceptance.md)
  - Type: human · Depends: 8

- [ ] 10. Close step 3
  - Card: [cards/10-close.md](cards/10-close.md)
  - Type: agent · Size: S · Depends: 9 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-placeholder-textures/, .kiro/specs/zone-generator/
