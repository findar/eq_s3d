# Tasks — zone-generator-export (roadmap step 17)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Decisions later tasks rely on are in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card, then the design section it names. Verify both against the
   code; the design was written at `b005e80`.
3. Work in a worktree (`agent/export-<n>`) unless the card says MAIN
   checkout. Edit only the files under `Owns`.
4. Every commit carries the trailer `Task: zone-generator-export/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**
6. Iterate on your task's own tests and `python -m pytest tests/ -q -m "not slow"`;
   run the full Python suite once before ticking, and don't commit while it runs
   (a server-staleness test notices).

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it); recaptured golden hashes don't count. `Depends` lists task numbers.
`Owns` lists the files and folders the task may edit; two ready tasks with
disjoint `Owns` can run in parallel.

**The shape was chosen by the lead on 2026-11-16** and is confirmed with the user at task 8
(`archive.md` "Decisions").

Bytes: every Generate stays byte-identical (Req 5) except builds with Gates in task 5. Every
task proves it with
`python -m pytest tests/test_layout_engine.py tests/test_site_builds.py tests/test_decor_builds.py tests/test_site_decor_builds.py -q`.

## Tasks

- [x] 1. Known short names
  - Card: [cards/01-zonelist.md](cards/01-zonelist.md)
  - Type: agent · Size: S · Depends: —
  - Owns: analyzer/zonelist.py, analyzer/data/rof2_zones.json, tests/test_zonelist.py
  - Reqs: 1.1

- [x] 2. Ground the takeover and the doors
  - Card: [cards/02-grounding.md](cards/02-grounding.md)
  - Type: agent · Size: S · Depends: —
  - Owns: docs/RESEARCH.md, .kiro/specs/zone-generator-export/archive.md, tests/test_export_grounding.py
  - Reqs: 3.3

- [ ] 3. The exported archive and files
  - Card: [cards/03-export.md](cards/03-export.md)
  - Type: agent · Size: M · Depends: 1
  - Owns: generators/export.py, analyzer/rof2check.py, tests/test_export.py
  - Reqs: 2

- [ ] 4. The SQL script
  - Card: [cards/04-sql.md](cards/04-sql.md)
  - Type: agent · Size: M · Depends: 1, 2
  - Owns: generators/sqlexport.py, tests/test_sqlexport.py
  - Reqs: 3

- [ ] 5. Door models in builds with Gates
  - Card: [cards/05-door-models.md](cards/05-door-models.md)
  - Type: agent · Size: M · Depends: 2
  - Owns: generators/doors.py, generators/builder.py, tests/test_door_models.py, recaptured golden hashes of builds with Gates
  - Reqs: 3.3, 5

- [ ] 6. Route, bundle and CLI
  - Card: [cards/06-route.md](cards/06-route.md)
  - Type: agent · Size: M · Depends: 3, 4
  - Owns: server/app.py, main.py, generators/export.py (the SQL call and the bundle), tests/test_export_route.py
  - Reqs: 1.2, 4.1, 4.3, 4.4

- [ ] 7. The Export row in the page
  - Card: [cards/07-page.md](cards/07-page.md)
  - Type: agent · Size: M · Depends: 6
  - Owns: web/src/, web/index.html, tests/test_hygiene.py (the web control id allowlist only)
  - Reqs: 4.2

- [ ] 8. HUMAN: first look
  - Card: [cards/08-first-look.md](cards/08-first-look.md)
  - Type: human · Depends: 5, 7

- [ ] 9. Acceptance section, thorough run
  - Card: [cards/09-acceptance.md](cards/09-acceptance.md)
  - Type: agent · Size: S · Depends: 8
  - Owns: docs/ACCEPTANCE.md

- [ ] 10. HUMAN: acceptance pass and in-client load
  - Card: [cards/10-human-acceptance.md](cards/10-human-acceptance.md)
  - Type: human · Depends: 9

- [ ] 11. Close step 17
  - Card: [cards/11-close.md](cards/11-close.md)
  - Type: agent · Size: S · Depends: 10 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-export/, .kiro/specs/zone-generator/
