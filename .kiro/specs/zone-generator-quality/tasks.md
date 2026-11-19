# Tasks — zone-generator-quality (roadmap step 19)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Decisions later tasks rely on are in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card, then the design section it names. Verify both against the
   code; the design was written at `19c041d`.
3. Work in a worktree (`agent/quality-<n>`) unless the card says MAIN
   checkout. Edit only the files under `Owns`.
4. Every commit carries the trailer `Task: zone-generator-quality/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**
6. Iterate on your task's own tests and `python -m pytest tests/ -q -m "not slow"`;
   run the full Python suite once before ticking, and don't commit while it runs
   (a server-staleness test notices).

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it); recaptured golden hashes don't count. `Depends` lists task numbers.
`Owns` lists the files and folders the task may edit; two ready tasks with
disjoint `Owns` can run in parallel.

**The choice was made by the lead on 2026-11-18** and is confirmed with the user at task 7
(`archive.md` "Decisions").

Bytes: geometry stays byte-identical (Req 6). Every task proves it with
`python -m pytest tests/test_layout_engine.py tests/test_site_builds.py tests/test_decor_builds.py tests/test_partial_rebuild.py -q`
(a golden that hashes the sidecar may be recaptured once, by task 3, for the `quality` entry
alone; say so in the commit body).

## Tasks

- [x] 1. The quality meter
  - Card: [cards/01-meter.md](cards/01-meter.md)
  - Type: agent · Size: S · Depends: —
  - Owns: generators/quality.py, tests/test_quality.py
  - Reqs: 1

- [x] 2. Calibrate the bands
  - Card: [cards/02-bands.md](cards/02-bands.md)
  - Type: agent · Size: S · Depends: 1
  - Owns: scripts/quality_sweep.py, generators/quality.py (the band table only), .kiro/specs/zone-generator-quality/archive.md
  - Reqs: 2

- [x] 3. The gate in the pipeline
  - Card: [cards/03-pipeline.md](cards/03-pipeline.md)
  - Type: agent · Size: M · Depends: 1
  - Owns: generators/pipeline.py, generators/rebuild.py, tests/test_quality_gate.py, golden hash files a sidecar change moves
  - Reqs: 3, 6

- [x] 4. Responses, edits, listing and CLI
  - Card: [cards/04-route.md](cards/04-route.md)
  - Type: agent · Size: M · Depends: 2, 3
  - Owns: server/app.py, main.py, tests/test_quality_route.py
  - Reqs: 4

- [x] 5. The page
  - Card: [cards/05-page.md](cards/05-page.md)
  - Type: agent · Size: M · Depends: 4
  - Owns: web/src/, web/index.html, tests/test_hygiene.py (the web control id allowlist only)
  - Reqs: 5

- [x] 6. Acceptance section
  - Card: [cards/06-acceptance.md](cards/06-acceptance.md)
  - Type: agent · Size: S · Depends: 5
  - Owns: docs/ACCEPTANCE.md

- [x] 7. HUMAN: first look
  - Card: [cards/07-first-look.md](cards/07-first-look.md)
  - Type: human · Depends: 5, 6

- [x] 8. Close step 19
  - Card: [cards/08-close.md](cards/08-close.md)
  - Type: agent · Size: S · Depends: 7 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-quality/, .kiro/specs/zone-generator/
