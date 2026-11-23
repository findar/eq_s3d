# Tasks — zone-generator-random-placement (roadmap step 27)

This file is an **index**. Each task has a card in `cards/` holding the goal, the "Done when"
checks and pitfalls. Decisions are in `archive.md`. The project rules are under "Card-format
specs" in `.kiro/steering/project.md`.

**How to run a task:**
- Pick one whose `Depends` are ticked (`python scripts/task_status.py`).
- Read its card and the design section it names, and verify both against the code (written at
  `b77d5a9`).
- Work in a worktree (`agent/placement-<n>`) and edit only `Owns`.
- Put the trailer `Task: zone-generator-random-placement/<n>` on every commit.
- Fill the card's Result and tick the task here.
- **Never tick a `Type: human` task.**

Bytes (Req 6): classic-layout zones, cities, wilderness and built/hewn Graph dungeons stay
byte-identical (decision 2). Task 2 (warrens) was dropped by decision 2. Prove it with:

`EQ_PATH='F:\everquest_rof2' python -m pytest tests/test_layout_engine.py tests/test_site_builds.py tests/test_partial_rebuild.py -q -n 4`

## Tasks

- [x] 1. Measure, and the build seed for the cave jitter (built and hewn tried, kept on the lattice: decision 2)
  - Card: [cards/01-dungeons.md](cards/01-dungeons.md)
  - Type: agent · Size: M · Depends: —
  - Owns: generators/topology/embed.py, generators/layout.py, generators/layout_engine.py, scripts/grid_score.py, tests/test_topology_embed.py, goldens it moves (named in the commit)
  - Reqs: 1, 2, 5, 6

- [x] 3. Outdoor dungeons
  - Card: [cards/03-outdoor.md](cards/03-outdoor.md)
  - Type: agent · Size: M · Depends: 1
  - Owns: generators/topology/embed.py, generators/layout.py, generators/outdoor_dungeon.py, tests/test_outdoor_levels.py, goldens it moves; widened by the lead: generators/layout_engine.py, tests/test_topology_embed.py, generators/room_context.py, generators/decor/placement.py, tests/test_room_context.py, tests/test_graph_layout_build.py (a re-pinned seed)
  - Reqs: 1, 2

- [x] 4. Gate and bands
  - Card: [cards/04-gate.md](cards/04-gate.md)
  - Type: agent · Size: S · Depends: 3
  - Owns: fixes only where a failure is new (stop and report first); widened by the lead: scripts/sweep_themed_navigability.py; fixes: generators/wilderness/build.py, generators/decor/placement.py, tests/test_gate_footprints.py, tests/test_decor_placement.py
  - Reqs: 4

- [x] 8. Outdoor draw time
  - Card: [cards/08-draw-time.md](cards/08-draw-time.md)
  - Type: agent · Size: M · Depends: 4
  - Owns: generators/layout_engine.py, generators/topology/embed.py, generators/layout.py, generators/outdoor_dungeon.py, tests/test_topology_embed.py, tests/test_outdoor_levels.py, goldens it moves (named in the commit)
  - Reqs: 1, 2

- [x] 5. Acceptance section
  - Card: [cards/05-acceptance.md](cards/05-acceptance.md)
  - Type: agent · Size: S · Depends: 4, 8
  - Owns: docs/ACCEPTANCE.md

- [ ] 6. HUMAN: first look
  - Card: [cards/06-first-look.md](cards/06-first-look.md)
  - Type: human · Depends: 5, 13

- [ ] 7. Close step 27
  - Card: [cards/07-close.md](cards/07-close.md)
  - Type: agent · Size: S · Depends: 6 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-random-placement/, .kiro/specs/zone-generator/

## First-look fixes (decision 4)

- [ ] 9. Measure what the eye sees, and stock room sizes
  - Card: [cards/09-measure.md](cards/09-measure.md)
  - Type: agent · Size: M · Depends: 5
  - Owns: scripts/grid_score.py, scripts/ (a new measuring script), .kiro/specs/zone-generator-random-placement/archive.md (targets only)
  - Reqs: 7, 8

- [ ] 10. Caves at any bearing
  - Card: [cards/10-bearing.md](cards/10-bearing.md)
  - Type: agent · Size: L · Depends: 9
  - Owns: generators/topology/embed.py, generators/layout_engine.py, generators/layout.py, generators/routing.py, generators/geometry.py, generators/outline.py, tests/test_topology_embed.py, goldens it moves (named in the commit); stop and report before widening
  - Reqs: 7

- [ ] 11. Room sizes vary
  - Card: [cards/11-sizes.md](cards/11-sizes.md)
  - Type: agent · Size: M · Depends: 10
  - Owns: generators/topology/embed.py (`room_size`), generators/semantics.py (size bands, room types), generators/layout.py (classic sizes), tests it moves, goldens it moves (named in the commit)
  - Reqs: 8

- [ ] 12. Gate and bands again
  - Card: [cards/12-gate.md](cards/12-gate.md)
  - Type: agent · Size: S · Depends: 11
  - Owns: fixes only where a failure is new (stop and report first)
  - Reqs: 4

- [ ] 13. Acceptance addendum
  - Card: [cards/13-acceptance.md](cards/13-acceptance.md)
  - Type: agent · Size: S · Depends: 12
  - Owns: docs/ACCEPTANCE.md

