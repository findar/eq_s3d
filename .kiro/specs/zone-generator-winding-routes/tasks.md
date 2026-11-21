# Tasks — zone-generator-winding-routes (roadmap step 25)

This file is an **index**. Each task has a card in `cards/` holding the goal, the "Done when"
checks and pitfalls. Decisions are in `archive.md`. The project rules are under "Card-format
specs" in `.kiro/steering/project.md`.

**How to run a task:** pick one whose `Depends` are ticked (`python scripts/task_status.py`), read
its card and the design section it names, verify both against the code (written at `169e985`),
work in a worktree (`agent/routes-<n>`), edit only `Owns`, put the trailer
`Task: zone-generator-winding-routes/<n>` on every commit, then fill the card's Result and tick
here. **Never tick a `Type: human` task.**

Bytes (A4): a zone with no rough corridor stays byte-identical, proven by
`python -m pytest tests/test_layout_engine.py tests/test_site_builds.py tests/test_decor_builds.py tests/test_partial_rebuild.py -q`.
A golden whose zone has rough corridors may be recaptured, named in its own commit.

## Tasks

- [x] 1. The route line and its clearance
  - Card: [cards/01-route.md](cards/01-route.md)
  - Type: agent · Size: M · Depends: —
  - Owns: generators/routing.py (`wind_route`), generators/transitions.py (`measure_winds`), generators/zone_spec.py (`CorridorSpec.path`), tests/test_wind_route.py
  - Reqs: 1, 2

- [ ] 2. The mesh along the path
  - Card: [cards/02-mesh.md](cards/02-mesh.md)
  - Type: agent · Size: M · Depends: 1
  - Owns: generators/geometry.py (`_emit_route` and the strip), analyzer/traverse.py (`corridor_continuity`), tests/test_wind_route_mesh.py, goldens of zones with rough corridors (named)
  - Reqs: 3

- [x] 3. Decor, map and room view read the path
  - Card: [cards/03-readers.md](cards/03-readers.md)
  - Type: agent · Size: M · Depends: 1
  - Owns: generators/room_context.py, generators/mapgeom.py, generators/mapview.py, tests/test_wind_route_readers.py
  - Reqs: 4

- [ ] 4. Cave run length
  - Card: [cards/04-length.md](cards/04-length.md)
  - Type: agent · Size: S · Depends: 2, 3
  - Owns: generators/layout.py (`PROFILE_RUN_FACTOR`), tests/test_cave_profile.py, tests/test_winding.py, .kiro/specs/zone-generator-winding-routes/archive.md (the measurement)
  - Reqs: 5

- [ ] 5. Gate and bands
  - Card: [cards/05-gate.md](cards/05-gate.md)
  - Type: agent · Size: M · Depends: 4
  - Owns: scripts/sweep_themed_navigability.py, scripts/quality_sweep.py, any root-cause fix named in the commit
  - Reqs: 6

- [ ] 6. Acceptance section
  - Card: [cards/06-acceptance.md](cards/06-acceptance.md)
  - Type: agent · Size: S · Depends: 5
  - Owns: docs/ACCEPTANCE.md

- [ ] 7. HUMAN: first look
  - Card: [cards/07-first-look.md](cards/07-first-look.md)
  - Type: human · Depends: 6

- [ ] 8. Close step 25
  - Card: [cards/08-close.md](cards/08-close.md)
  - Type: agent · Size: S · Depends: 7 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-winding-routes/, .kiro/specs/zone-generator/
