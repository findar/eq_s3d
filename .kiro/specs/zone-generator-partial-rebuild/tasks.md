# Tasks — zone-generator-partial-rebuild (roadmap step 16)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Decisions later tasks rely on are in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card, then the design section it names. Verify both against the
   code; the design was written at `56b14c5`.
3. Work in a worktree (`agent/rebuild-<n>`) unless the card says MAIN
   checkout. Edit only the files under `Owns`.
4. Every commit carries the trailer `Task: zone-generator-partial-rebuild/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**
6. Iterate on your task's own tests and `python -m pytest tests/ -q -m "not slow"`;
   run the full Python suite once before ticking, and don't commit while it runs
   (a server-staleness test notices).

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it); recaptured golden hashes don't count. `Depends` lists task numbers.
`Owns` lists the files and folders the task may edit; two ready tasks with
disjoint `Owns` can run in parallel.

**The shape was agreed with the user on 2026-11-15** (`archive.md` "Decisions").

Bytes: Generate and every build with no room decor seeds stay byte-identical in every task
(Req 6.1). Every task proves it with
`python -m pytest tests/test_layout_engine.py tests/test_site_builds.py tests/test_decor_builds.py tests/test_site_decor_builds.py -q`.

## Tasks

- [ ] 1. Room decor seeds
  - Card: [cards/01-room-seeds.md](cards/01-room-seeds.md)
  - Type: agent · Size: M · Depends: —
  - Owns: generators/zone_spec.py, ai/schema.py, ai/expand.py, generators/builder.py, generators/decor/room_view.py, tests/test_room_decor_seeds.py
  - Reqs: 3

- [x] 2. Versions of one zone
  - Card: [cards/02-versions.md](cards/02-versions.md)
  - Type: agent · Size: M · Depends: —
  - Owns: server/app.py, generators/pipeline.py, tests/test_versions.py
  - Reqs: 1, 2.1, 2.2 (full path)

- [ ] 3. Rebuild from the saved stages
  - Card: [cards/03-partial.md](cards/03-partial.md)
  - Type: agent · Size: M · Depends: 1, 2
  - Owns: generators/rebuild.py, generators/builder.py, generators/pipeline.py, server/app.py, tests/test_partial_rebuild.py
  - Reqs: 2.2, 2.3, 4.1

- [ ] 4. Keep the shell's gate result
  - Card: [cards/04-shell.md](cards/04-shell.md)
  - Type: agent · Size: M · Depends: 3
  - Owns: analyzer/traverse.py, generators/rebuild.py, generators/pipeline.py, generators/outdoor_dungeon.py, tests/test_partial_rebuild.py
  - Reqs: 4.2–4.5

- [ ] 5. Versions and Use in zone in the page
  - Card: [cards/05-page.md](cards/05-page.md)
  - Type: agent · Size: M · Depends: 1, 2
  - Owns: web/src/, web/index.html, tests/test_hygiene.py (the web control id allowlist only)
  - Reqs: 5

- [ ] 6. HUMAN: first look
  - Card: [cards/06-first-look.md](cards/06-first-look.md)
  - Type: human · Depends: 4, 5

- [ ] 7. Acceptance section, thorough run
  - Card: [cards/07-acceptance.md](cards/07-acceptance.md)
  - Type: agent · Size: S · Depends: 6
  - Owns: docs/ACCEPTANCE.md

- [ ] 8. HUMAN: acceptance pass
  - Card: [cards/08-human-acceptance.md](cards/08-human-acceptance.md)
  - Type: human · Depends: 7

- [ ] 9. Close step 16
  - Card: [cards/09-close.md](cards/09-close.md)
  - Type: agent · Size: S · Depends: 8 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-partial-rebuild/, .kiro/specs/zone-generator/
