# Tasks — zone-generator-winding-tunnels (roadmap step 23)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Decisions later tasks rely on are in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card, then the design section it names. Verify both against the
   code; the design was written at `b2db7b4`.
3. Work in a worktree (`agent/tunnels-<n>`) unless the card says MAIN checkout.
   Edit only the files under `Owns`.
4. Every commit carries the trailer `Task: zone-generator-winding-tunnels/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**
6. Iterate on your task's own tests and `python -m pytest tests/ -q -m "not slow"`.
   When tasks run side by side, the lead runs the full suite after merging.

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it). `Depends` lists task numbers. `Owns` lists the files and folders the
task may edit; two ready tasks with disjoint `Owns` can run in parallel.

**The choice was made by the lead on 2026-11-20** and is confirmed with the user at task 7
(`archive.md` "Decisions").

Bytes (A4): a zone with no rough corridor stays byte-identical, proven by
`python -m pytest tests/test_layout_engine.py tests/test_site_builds.py tests/test_decor_builds.py tests/test_partial_rebuild.py -q`.
A golden whose zone has rough corridors may be recaptured, named in its own commit.

## Tasks

- [x] 1. Stock tunnel survey
  - Card: [cards/01-survey.md](cards/01-survey.md)
  - Type: agent · Size: S · Depends: —
  - Owns: scripts/tunnel_survey.py, tests/test_tunnel_survey.py, .kiro/specs/zone-generator-winding-tunnels/archive.md (the survey numbers)
  - Reqs: 1

- [x] 2. The winding centreline and its clearance
  - Card: [cards/02-centreline.md](cards/02-centreline.md)
  - Type: agent · Size: M · Depends: 1
  - Owns: generators/routing.py (a new `wind_leg`), generators/transitions.py, generators/zone_spec.py (`CorridorSpec.wind`), generators/wall_styles.py, rules/walls/rough.toml, tests/test_winding.py
  - Reqs: 2

- [ ] 3. The winding mesh
  - Card: [cards/03-mesh.md](cards/03-mesh.md)
  - Type: agent · Size: M · Depends: 2, 9
  - Owns: generators/geometry.py (the leg builders), tests/test_winding_mesh.py, goldens of zones with rough corridors (named)
  - Reqs: 3, 6

- [x] 4. Decor, map and room view read the tunnel
  - Card: [cards/04-readers.md](cards/04-readers.md)
  - Type: agent · Size: M · Depends: 2, 9
  - Owns: generators/room_context.py, generators/mapgeom.py, generators/mapview.py, tests/test_winding_readers.py
  - Reqs: 4

- [ ] 5. Gate and bands
  - Card: [cards/05-gate.md](cards/05-gate.md)
  - Type: agent · Size: M · Depends: 3, 4
  - Owns: scripts/sweep_themed_navigability.py, scripts/quality_sweep.py, any root-cause fix named in the commit
  - Reqs: 5

- [ ] 6. Acceptance section
  - Card: [cards/06-acceptance.md](cards/06-acceptance.md)
  - Type: agent · Size: S · Depends: 5
  - Owns: docs/ACCEPTANCE.md

- [ ] 7. HUMAN: first look
  - Card: [cards/07-first-look.md](cards/07-first-look.md)
  - Type: human · Depends: 6

- [ ] 8. Close step 23
  - Card: [cards/08-close.md](cards/08-close.md)
  - Type: agent · Size: S · Depends: 7 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-winding-tunnels/, .kiro/specs/zone-generator/

- [x] 9. Cave tunnels as long as stock
  - Card: [cards/09-length.md](cards/09-length.md)
  - Type: agent · Size: M · Depends: 2
  - Owns: scripts/tunnel_survey.py, generators/topology/embed.py (the run only), generators/layout_engine.py (`LayoutContext`), generators/layout.py (the profile's run only), tests/test_winding.py, tests/test_cave_profile.py, .kiro/specs/zone-generator-winding-tunnels/cards/02-centreline.md
  - Reqs: 2 (added by the lead at the task 2 merge, archive decision 5)
