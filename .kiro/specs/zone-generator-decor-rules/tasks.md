# Tasks — zone-generator-decor-rules (roadmap step 15)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Decisions later tasks rely on are in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card, then the design section it names. Verify both against the
   code; the design was written at `8ebca55`.
3. Work in a worktree (`agent/decor-rules-<n>`) unless the card says MAIN
   checkout. Edit only the files under `Owns`.
4. Every commit carries the trailer `Task: zone-generator-decor-rules/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**
6. Iterate on your task's own tests and `python -m pytest tests/ -q -m "not slow"`;
   run the full Python suite once before ticking, and don't commit while it runs
   (a server-staleness test notices).

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it); recaptured golden hashes don't count. `Depends` lists task numbers.
`Owns` lists the files and folders the task may edit; two ready tasks with
disjoint `Owns` can run in parallel.

**The design's open questions were decided on 2026-11-14** (`archive.md` "Decisions").

Bytes: no build that names no decor layer changes, in any task (Req 6.1). Every task proves it
with `python -m pytest tests/test_layout_engine.py tests/test_site_builds.py tests/test_decor_builds.py tests/test_site_decor_builds.py -q`.

**Web tasks (5, 6) wait for step 14** (`zone-generator-web-cleanup` task 3) to be merged: they
build on its header, Controls and side panel.

## Tasks

- [x] 1. Decor layers in the loader
  - Card: [cards/01-loader.md](cards/01-loader.md)
  - Type: agent · Size: M · Depends: —
  - Owns: generators/decor/rules.py, rules/decor/themes.toml, rules/decor/layers/, tests/test_decor_rules.py, tests/test_decor_layers.py
  - Reqs: 1, 2.1

- [x] 2. Layers through the build
  - Card: [cards/02-build.md](cards/02-build.md)
  - Type: agent · Size: M · Depends: 1
  - Owns: ai/schema.py, generators/builder.py, server/app.py, main.py, tests/test_decor_layers_build.py, tests/test_hygiene.py (the CLI option list only)
  - Reqs: 2.2–2.5

- [x] 3. The tomb layer, the guide and the tools
  - Card: [cards/03-example.md](cards/03-example.md)
  - Type: agent · Size: M · Depends: 2
  - Owns: rules/decor/rooms.toml, rules/decor/layers/, rules/decor/themes.toml, docs/DECOR_RULES.md, scripts/topology_rules.py, tests/test_decor_layers.py, tests/test_decor_builds.py (the TOMB golden only), tests/test_decor_rules.py (the tomb figures only), scripts/stage.py (decor_stage's layers only)
  - Reqs: 3

- [x] 4. Re-decorate one room: module and route
  - Card: [cards/04-room-route.md](cards/04-room-route.md)
  - Type: agent · Size: M · Depends: 2
  - Owns: generators/decor/room_view.py, scripts/decor_room.py, server/app.py, tests/test_room_view.py, generators/builder.py
  - Reqs: 4

- [x] 5. The Decor rules control
  - Card: [cards/05-control.md](cards/05-control.md)
  - Type: agent · Size: S · Depends: 2
  - Owns: web/index.html, web/src/main.ts, web/src/api.ts, tests/test_hygiene.py (the web control id allowlist only)
  - Reqs: 2.2, 2.3

- [ ] 6. The room view in the page
  - Card: [cards/06-room-view.md](cards/06-room-view.md)
  - Type: agent · Size: M · Depends: 4, 5
  - Owns: web/src/roomview.ts, web/src/main.ts, web/index.html, web/src/style.css, web/src/api.ts
  - Reqs: 5

- [ ] 7. HUMAN: first look
  - Card: [cards/07-first-look.md](cards/07-first-look.md)
  - Type: human · Depends: 3, 6

- [ ] 8. Acceptance section, thorough run
  - Card: [cards/08-acceptance.md](cards/08-acceptance.md)
  - Type: agent · Size: S · Depends: 7
  - Owns: docs/ACCEPTANCE.md

- [ ] 9. HUMAN: acceptance pass
  - Card: [cards/09-human-acceptance.md](cards/09-human-acceptance.md)
  - Type: human · Depends: 8

- [ ] 10. Close step 15
  - Card: [cards/10-close.md](cards/10-close.md)
  - Type: agent · Size: S · Depends: 9 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-decor-rules/, .kiro/specs/zone-generator/
