# Tasks — zone-generator-interesting-textures (roadmap step 4)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Decisions later tasks rely on are in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card, then the design section it names. Verify both against the
   code; the design was written at `ca3a61a`.
3. Work in a worktree (`agent/looks-<n>`) unless the card says MAIN checkout.
   Edit only the files under `Owns`.
4. Every commit carries the trailer
   `Task: zone-generator-interesting-textures/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it). `Depends` lists task numbers. `Owns` lists the files and folders
the task may edit; two ready tasks with disjoint `Owns` can run in parallel.

The design's four open questions were answered on 2026-11-01
(`archive.md` "Decisions").

## Tasks

- [x] 1. WLD reader keeps UVs and polygon textures
  - Card: [cards/01-wld-uvs.md](cards/01-wld-uvs.md)
  - Type: agent · Size: S · Depends: —
  - Owns: core/wld.py, tests/test_wld.py
  - Reqs: 1

- [x] 2. Texture_Profile in the style profiles
  - Card: [cards/02-texture-profile.md](cards/02-texture-profile.md)
  - Type: agent · Size: M · Depends: 1
  - Owns: analyzer/style_builder.py, styles/dungeon.json, styles/city.json, styles/outdoor.json, styles/cave.json, tests/test_texture_profile.py
  - Reqs: 2

- [x] 3. Texture recipe data and resolver
  - Card: [cards/03-recipes.md](cards/03-recipes.md)
  - Type: agent · Size: S · Depends: —
  - Owns: styles/texture_recipes.json, generators/textures/recipes.py, tests/test_texture_recipes.py
  - Reqs: 3

- [x] 4. Painters: stone families
  - Card: [cards/04-stone-painters.md](cards/04-stone-painters.md)
  - Type: agent · Size: M · Depends: —
  - Owns: generators/textures/painters/__init__.py, generators/textures/painters/stone.py, tests/test_painters.py
  - Reqs: 4

- [x] 5. Painters: timber, plaster, ice and sky
  - Card: [cards/05-natural-painters.md](cards/05-natural-painters.md)
  - Type: agent · Size: M · Depends: 4
  - Owns: generators/textures/painters/natural.py, tests/test_painters_natural.py
  - Reqs: 4

- [x] 6. Conformance and the recipe texture mode
  - Card: [cards/06-conformance-and-mode.md](cards/06-conformance-and-mode.md)
  - Type: agent · Size: M · Depends: 2, 3, 4, 5
  - Owns: generators/textures/conformance.py, generators/textures/procedural.py, generators/textures/factory.py, generators/builder.py, tests/test_texture_conformance.py
  - Reqs: 4.4, 5, 7

- [x] 7. Texel density from the profile
  - Card: [cards/07-texel-density.md](cards/07-texel-density.md)
  - Type: agent · Size: M · Depends: 2, 6
  - Owns: generators/geometry.py, generators/builder.py, generators/zone_spec.py, tests/test_wall_uvs.py, tests/test_texel_density.py
  - zone_spec.py added 2026-11-01: texel density is recorded on each MaterialSpec (the IR), the user's delegated choice for long-term maintenance over a backend-interface change.
  - Reqs: 6

- [x] 8. HUMAN: first look at the new textures in 3D
  - Card: [cards/08-human-first-look.md](cards/08-human-first-look.md)
  - Type: human · Depends: 6, 7

- [x] 9. Tune from the first look
  - Card: [cards/09-tuning.md](cards/09-tuning.md)
  - Type: agent · Size: S · Depends: 8
  - Owns: styles/texture_recipes.json, generators/textures/painters/, generators/layout.py, tests/test_material_names.py, tests/test_corridor_materials.py
  - layout.py and the goldens added 2026-11-01 for task 8's finding (corridors match the room they leave), at the user's choice.

- [ ] 10. Acceptance section, thorough run, timing
  - Card: [cards/10-release-prep.md](cards/10-release-prep.md)
  - Type: agent · Size: S · Depends: 9
  - Owns: docs/ACCEPTANCE.md, tests/test_texture_conformance.py
  - Reqs: 8, exit criteria 1–2

- [ ] 11. HUMAN: interesting textures acceptance pass
  - Card: [cards/11-human-acceptance.md](cards/11-human-acceptance.md)
  - Type: human · Depends: 10

- [ ] 12. Close step 4
  - Card: [cards/12-close.md](cards/12-close.md)
  - Type: agent · Size: S · Depends: 11, 13 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-interesting-textures/, .kiro/specs/zone-generator/

- [ ] 13. Windows path-resolution race in OutputRoot
  - Card: [cards/13-path-prefix-race.md](cards/13-path-prefix-race.md)
  - Type: agent · Size: S · Depends: —
  - Owns: core/paths.py, tests/test_paths.py, .kiro/steering/lessons-learned.md
  - Reqs: exit criterion 2
  - Added 2026-11-01 from task 10's first thorough run (the user's choice):
    the root cause of the collection failures step 3 task 12 recorded.
