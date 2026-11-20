# Tasks — zone-generator-district-looks (roadmap step 22)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Decisions later tasks rely on are in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card, then the design section it names. Verify both against the
   code; the design was written at `b11764b`.
3. Work in a worktree (`agent/looks-<n>`) unless the card says MAIN checkout.
   Edit only the files under `Owns`.
4. Every commit carries the trailer `Task: zone-generator-district-looks/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**
6. Iterate on your task's own tests and `python -m pytest tests/ -q -m "not slow"`.
   When tasks run side by side, the lead runs the full suite after merging (two
   full suites at once run out of memory).

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it). `Depends` lists task numbers. `Owns` lists the files and folders the
task may edit; two ready tasks with disjoint `Owns` can run in parallel.

**The choice was made by the lead on 2026-11-20** and is confirmed with the user at task 7
(`archive.md` "Decisions").

Bytes (A4): a zone with no Districts and a Purpose other than `cave` stays byte-identical, proven by
`python -m pytest tests/test_layout_engine.py tests/test_site_builds.py tests/test_decor_builds.py tests/test_partial_rebuild.py -q`.
A golden covering a districted or `cave` zone may be recaptured, named in its own commit.

## Tasks

- [ ] 1. Walls per District
  - Card: [cards/01-walls.md](cards/01-walls.md)
  - Type: agent · Size: S · Depends: —
  - Owns: generators/room_scales.py, tests/test_district_looks.py
  - Reqs: 1

- [ ] 2. Decor per District
  - Card: [cards/02-decor.md](cards/02-decor.md)
  - Type: agent · Size: M · Depends: —
  - Owns: generators/builder.py (the decor part), generators/room_context.py, generators/rebuild.py, tests/test_district_decor.py, tests/test_partial_rebuild.py
  - Reqs: 2

- [ ] 3. Cave dressing
  - Card: [cards/03-cave-dressing.md](cards/03-cave-dressing.md)
  - Type: agent · Size: S · Depends: —
  - Owns: generators/semantics.py, rules/decor/layers/cave.toml, tests/test_cave_purpose.py, tests/fixtures/rooms/cave_graph.json
  - Reqs: 3

- [ ] 4. Cave ceilings
  - Card: [cards/04-ceilings.md](cards/04-ceilings.md)
  - Type: agent · Size: S · Depends: —
  - Owns: generators/layout.py (the profile shift only), ai/expand.py, tests/test_cave_profile.py
  - Reqs: 4

- [ ] 5. Gate and bands
  - Card: [cards/05-gate.md](cards/05-gate.md)
  - Type: agent · Size: M · Depends: 1, 2, 3, 4
  - Owns: scripts/sweep_themed_navigability.py, scripts/quality_sweep.py, any root-cause fix named in the commit
  - Reqs: 5

- [ ] 6. Acceptance section
  - Card: [cards/06-acceptance.md](cards/06-acceptance.md)
  - Type: agent · Size: S · Depends: 5
  - Owns: docs/ACCEPTANCE.md

- [ ] 7. HUMAN: first look
  - Card: [cards/07-first-look.md](cards/07-first-look.md)
  - Type: human · Depends: 6

- [ ] 8. Close step 22
  - Card: [cards/08-close.md](cards/08-close.md)
  - Type: agent · Size: S · Depends: 7 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-district-looks/, .kiro/specs/zone-generator/
