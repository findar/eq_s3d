# Tasks — zone-generator-districts (roadmap step 20)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Decisions later tasks rely on are in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card, then the design section it names. Verify both against the
   code; the design was written at `a26d07b`.
3. Work in a worktree (`agent/districts-<n>`) unless the card says MAIN
   checkout. Edit only the files under `Owns`.
4. Every commit carries the trailer `Task: zone-generator-districts/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**
6. Iterate on your task's own tests and `python -m pytest tests/ -q -m "not slow"`;
   run the full Python suite once before ticking, and don't commit while it runs
   (a server-staleness test notices).

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it). `Depends` lists task numbers. `Owns` lists the files and folders the
task may edit; two ready tasks with disjoint `Owns` can run in parallel.

**The choice was made by the lead on 2026-11-18** and is confirmed with the user at task 9
(`archive.md` "Decisions").

Bytes: with the Districts switch off, geometry stays byte-identical (Req 7). Every task that
touches generation proves it with
`python -m pytest tests/test_layout_engine.py tests/test_site_builds.py tests/test_decor_builds.py tests/test_partial_rebuild.py -q`
(no golden is recaptured in this step).

## Tasks

- [ ] 1. The partition
  - Card: [cards/01-partition.md](cards/01-partition.md)
  - Type: agent · Size: S · Depends: —
  - Owns: generators/districts.py, generators/zone_spec.py, tests/test_districts.py
  - Reqs: 1

- [ ] 2. Purposes, palettes and lights
  - Card: [cards/02-purposes.md](cards/02-purposes.md)
  - Type: agent · Size: M · Depends: 1
  - Owns: generators/districts.py, generators/semantics.py, tests/test_district_purposes.py
  - Reqs: 2

- [ ] 3. Districts in the layout
  - Card: [cards/03-layout.md](cards/03-layout.md)
  - Type: agent · Size: M · Depends: 2
  - Owns: generators/layout.py, tests/test_district_layout.py
  - Reqs: 3, 7

- [ ] 4. The plan and the prompt
  - Card: [cards/04-plan.md](cards/04-plan.md)
  - Type: agent · Size: M · Depends: 3
  - Owns: ai/schema.py, ai/expand.py, ai/rule_planner.py, ai/llm_planner.py, ai/prompts/, tests/test_district_plan.py
  - Reqs: 4.1, 4.2

- [ ] 5. CLI, Server and sidecar
  - Card: [cards/05-route.md](cards/05-route.md)
  - Type: agent · Size: M · Depends: 4
  - Owns: main.py, server/app.py, generators/builder.py, tests/test_district_route.py
  - Reqs: 4.3, 4.4

- [ ] 6. Bands for Districts
  - Card: [cards/06-bands.md](cards/06-bands.md)
  - Type: agent · Size: S · Depends: 4
  - Owns: generators/quality.py, scripts/quality_sweep.py, tests/test_quality.py, .kiro/specs/zone-generator-districts/archive.md
  - Reqs: 5

- [ ] 7. The page and the map
  - Card: [cards/07-page.md](cards/07-page.md)
  - Type: agent · Size: M · Depends: 5
  - Owns: web/src/, web/index.html, generators/mapview.py, tests/test_hygiene.py (the web control id allowlist only)
  - Reqs: 6

- [ ] 8. Acceptance section
  - Card: [cards/08-acceptance.md](cards/08-acceptance.md)
  - Type: agent · Size: S · Depends: 6, 7
  - Owns: docs/ACCEPTANCE.md

- [ ] 9. HUMAN: first look
  - Card: [cards/09-first-look.md](cards/09-first-look.md)
  - Type: human · Depends: 7, 8

- [ ] 10. Close step 20
  - Card: [cards/10-close.md](cards/10-close.md)
  - Type: agent · Size: S · Depends: 9 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-districts/, .kiro/specs/zone-generator/
