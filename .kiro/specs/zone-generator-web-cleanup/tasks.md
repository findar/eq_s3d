# Tasks — zone-generator-web-cleanup (roadmap step 14)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Decisions later tasks rely on are in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card, then the design section it names. Verify both against the
   code; the design was written at `0b604ea`.
3. Work in a worktree (`agent/web-cleanup-<n>`) unless the card says MAIN
   checkout. Edit only the files under `Owns`.
4. Every commit carries the trailer `Task: zone-generator-web-cleanup/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**
6. Run the full Python suite once before ticking, even for a frontend-only task,
   and don't commit while it runs (a server-staleness test notices).

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it). `Depends` lists task numbers. `Owns` lists the files and folders
the task may edit; two ready tasks with disjoint `Owns` can run in parallel.

**The design's open questions were decided on 2026-11-14** (`archive.md` "Decisions").

Bytes: nothing a build makes changes in this step (Req 4.1).

Tasks 1–3 own the same files and run one after another, in one worktree.

## Tasks

- [x] 1. Grouped, aligned Controls and header
  - Card: [cards/01-layout.md](cards/01-layout.md)
  - Type: agent · Size: M · Depends: —
  - Owns: web/index.html, web/src/style.css, web/src/main.ts
  - Reqs: 3

- [ ] 2. Describe or Controls, one Generate
  - Card: [cards/02-mode.md](cards/02-mode.md)
  - Type: agent · Size: M · Depends: 1
  - Owns: web/index.html, web/src/style.css, web/src/main.ts
  - Reqs: 1

- [ ] 3. Show only what applies
  - Card: [cards/03-applies.md](cards/03-applies.md)
  - Type: agent · Size: M · Depends: 2
  - Owns: web/index.html, web/src/style.css, web/src/main.ts, web/src/scene.ts
  - Reqs: 2

- [ ] 4. Acceptance section
  - Card: [cards/04-acceptance.md](cards/04-acceptance.md)
  - Type: agent · Size: S · Depends: 3
  - Owns: docs/ACCEPTANCE.md

- [ ] 5. HUMAN: look and acceptance
  - Card: [cards/05-human.md](cards/05-human.md)
  - Type: human · Depends: 4

- [ ] 6. Close step 14
  - Card: [cards/06-close.md](cards/06-close.md)
  - Type: agent · Size: S · Depends: 5 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-web-cleanup/
