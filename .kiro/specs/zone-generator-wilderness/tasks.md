# Tasks — zone-generator-wilderness (roadmap step 1: the open Karana)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Finished waves 1–4 are summarised in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card. Verify the card against the code; the repo can be ahead of it.
3. Work in a worktree (`agent/wild-<n>`) unless the card says MAIN checkout.
   Edit only the files under `Owns`.
4. Every commit carries the trailer `Task: zone-generator-wilderness/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it). `Depends` lists task numbers. `Owns` lists the files and folders
the task may edit; two ready tasks with disjoint `Owns` can run in parallel.

## Tasks

- [x] 1. Housekeeping: land waves 1–4 on the trackers
  - Card: [cards/01-housekeeping.md](cards/01-housekeeping.md)
  - Type: agent · Size: S · Depends: — · Where: MAIN checkout
  - Owns: ROADMAP.md, README.md, tasks/README.md, .kiro/specs/

- [x] 2. Build a wilderness zone end to end (behind a dev flag)
  - Card: [cards/02-build-end-to-end.md](cards/02-build-end-to-end.md)
  - Type: agent · Size: M · Depends: 1
  - Owns: generators/wilderness/build.py, generators/backends.py, generators/zone_spec.py, generators/zone_types.py, generators/pipeline.py, main.py, ai/expand.py, tests/test_wilderness_build.py, tests/test_planner.py, tests/test_hygiene.py
  - Reqs: 14.1, 14.2, 14.3

- [x] 3. Edge declarations in the server and the web Controls panel
  - Card: [cards/03-web-edges.md](cards/03-web-edges.md)
  - Type: agent · Size: M · Depends: 2
  - Owns: server/app.py, web/index.html, web/src/, tests/test_server.py, tests/test_hygiene.py, tests/conftest.py
  - Reqs: 3.1, 3.2

- [x] 4. HUMAN: first look at a Karana (terrain + bowl)
  - Card: [cards/04-human-first-look.md](cards/04-human-first-look.md)
  - Type: human · Depends: 2, 3
  - Reqs: 13.4

- [x] 5. Tune from the first look (time-boxed)
  - Card: [cards/05-tuning.md](cards/05-tuning.md)
  - Type: agent · Size: M · Depends: 4
  - Owns: generators/wilderness/matrix.py, generators/wilderness/synth.py, generators/wilderness/bowl.py, generators/field/terrain.py
  - Reqs: 5.1, 6.1, 12.1, 13.3

- [x] 6. Visual water plane
  - Card: [cards/06-water-plane.md](cards/06-water-plane.md)
  - Type: agent · Size: M · Depends: 2
  - Owns: generators/wilderness/build.py, generators/wilderness/water.py, generators/zone_spec.py, analyzer/traverse.py, tests/test_wilderness_water.py
  - Reqs: 11.4, 13.1

- [x] 7. Plains biome kit and ground textures
  - Card: [cards/07-biome-kit.md](cards/07-biome-kit.md)
  - Type: agent · Size: M · Depends: 2
  - Owns: generators/wilderness/build.py, generators/wilderness/biome.py, styles/, generators/textures/, tests/test_wilderness_biome_kit.py
  - Reqs: 11.1, 11.2, 11.3

- [x] 8. Wilderness advisory data in the `.zone.json` sidecar
  - Card: [cards/08-sidecar.md](cards/08-sidecar.md)
  - Type: agent · Size: S · Depends: 2
  - Owns: core/eqg.py, generators/builder.py, ai/expand.py, tests/test_wilderness_sidecar.py
  - Reqs: 1.4, 3.7, 10.2, 14.4

- [ ] 9. Release prep: reproducibility, budget, acceptance checklist
  - Card: [cards/09-release-prep.md](cards/09-release-prep.md)
  - Type: agent · Size: M · Depends: 5, 6, 7, 8
  - Owns: tests/test_wilderness_build.py, docs/ACCEPTANCE.md
  - Reqs: 5.3, 13.2, 13.3

- [ ] 10. HUMAN: final Karana acceptance pass
  - Card: [cards/10-human-final-pass.md](cards/10-human-final-pass.md)
  - Type: human · Depends: 9
  - Reqs: 13.4

- [ ] 11. Enable wilderness and close step 1
  - Card: [cards/11-enable-and-close.md](cards/11-enable-and-close.md)
  - Type: agent · Size: S · Depends: 10 · Where: MAIN checkout
  - Owns: generators/zone_types.py, tests/test_wilderness_build.py, docs/ACCEPTANCE.md, ROADMAP.md, tasks/README.md
  - Reqs: 13.4

## Out of scope for step 1
Named POIs (roadmap step 10), rivers crossing the interior, swimmable water
volumes, droplet erosion, the desert/forest/coast/tundra biomes, the
`LayoutEngine` seam (step 6), the 3D `Envelope` (steps 5/7), and region-record
export (SQL capstone). See `requirements.md` "Out of scope".
