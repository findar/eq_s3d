# Tasks — zone-generator-district-races (roadmap step 31)

This file is an **index**. Each task has a card in `cards/` holding the goal, the "Done when"
checks and pitfalls. Decisions are in `archive.md`. The project rules are under "Card-format
specs" in `.kiro/steering/project.md`.

**How to run a task:**
- Pick one whose `Depends` are ticked (`python scripts/task_status.py`).
- Read its card and the design section it names, and verify both against the code (written at
  `070126c`).
- Work in a worktree (`agent/races-<n>`) and edit only `Owns`.
- Put the trailer `Task: zone-generator-district-races/<n>` on every commit.
- Fill the card's Result and tick the task here.
- **Never tick a `Type: human` task.**

## Tasks

- [x] 1. Measure stock: race hall lengths, drops, layered links
  - Card: [cards/01-measure.md](cards/01-measure.md)
  - Type: agent · Size: S · Depends: —
  - Owns: scripts/stock_room_shapes.py, scripts/stock_drops.py (new), .kiro/specs/zone-generator-district-races/archive.md (decisions only)
  - Reqs: 1

- [x] 2. One-way navigation in the gate
  - Card: [cards/02-oneway-gate.md](cards/02-oneway-gate.md)
  - Type: agent · Size: M · Depends: 1
  - Owns: analyzer/traverse.py, tests/test_traverse_directed.py (new)
  - Reqs: 2

- [x] 3. Advisory gates and pacing on the directed graph
  - Card: [cards/03-oneway-gating.md](cards/03-oneway-gating.md)
  - Type: agent · Size: S · Depends: 2
  - Owns: generators/layout.py (gating and pacing only), generators/edits.py, tests/test_gating_directed.py (new)
  - Reqs: 3

- [x] 4. A race per District
  - Card: [cards/04-race.md](cards/04-race.md)
  - Type: agent · Size: M · Depends: 1
  - Owns: generators/zone_spec.py, generators/districts.py, generators/layout.py (room and corridor sizing), tests/test_district_races.py (new), goldens it moves (named)
  - Reqs: 4

- [x] 5. Hall length per District
  - Card: [cards/05-district-halls.md](cards/05-district-halls.md)
  - Type: agent · Size: M · Depends: 1, 4
  - Owns: generators/layout.py (placement run), generators/topology/embed.py, generators/semantics.py (defaults table), tests/test_district_races.py
  - Reqs: 5

- [x] 6. Intrusion: an intruder District breaks in at several places
  - Card: [cards/06-intrusion.md](cards/06-intrusion.md)
  - Type: agent · Size: M · Depends: 3, 4
  - Owns: generators/districts.py, generators/layout.py (Districts and links), generators/transitions.py, tests/test_intrusion.py (new)
  - Reqs: 6

- [x] 7. Flush or a drop, and one-way loops
  - Card: [cards/07-drops.md](cards/07-drops.md)
  - Type: agent · Size: M · Depends: 2, 3, 6
  - Owns: generators/zone_spec.py (CorridorSpec.drop), generators/layout.py, generators/geometry.py, generators/room_context.py, tests/test_drops.py (new)
  - Reqs: 7, 8

- [x] 8. Mixed boundary rooms
  - Card: [cards/08-boundary-decor.md](cards/08-boundary-decor.md)
  - Type: agent · Size: S · Depends: 6, 14
  - Owns: generators/decor/, tests/test_decor_placement.py
  - Reqs: 9

- [x] 9. Controls and words
  - Card: [cards/09-controls.md](cards/09-controls.md)
  - Type: agent · Size: M · Depends: 4, 5, 6, 7
  - Owns: ai/schema.py, ai/rule_planner.py, ai/llm_planner.py, server/app.py, web/index.html, web/src/main.ts, web/src/api.ts, tests/test_district_races_words.py (new)
  - Reqs: 10

- [x] 10. Gate and bands
  - Card: [cards/10-gate.md](cards/10-gate.md)
  - Type: agent · Size: S · Depends: 7, 8, 9, 14, 15
  - Owns: scripts/sweep_themed_navigability.py (an --intrusion option); fixes only where a failure is new (stop and report first)
  - Reqs: 11

- [x] 11. Acceptance section
  - Card: [cards/11-acceptance.md](cards/11-acceptance.md)
  - Type: agent · Size: S · Depends: 10
  - Owns: docs/ACCEPTANCE.md

- [ ] 12. HUMAN: look
  - Card: [cards/12-look.md](cards/12-look.md)
  - Type: human · Depends: 11, 16

- [ ] 13. Close step 31
  - Card: [cards/13-close.md](cards/13-close.md)
  - Type: agent · Size: S · Depends: 12 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-district-races/, .kiro/specs/zone-generator/

## Added at task 4

- [x] 14. Size everything in a room by the room's race
  - Card: [cards/14-room-race.md](cards/14-room-race.md)
  - Type: agent · Size: M · Depends: 4, 5
  - Owns: generators/semantics.py (a per-room race helper, `_apply_shape`), generators/wall_styles.py, generators/room_layouts.py, generators/room_context.py, generators/transitions.py, tests/test_district_races.py
  - Reqs: 4

## Added at task 10

- [x] 15. Decor placement time in giant Districts
  - Card: [cards/15-decor-time.md](cards/15-decor-time.md)
  - Type: agent · Size: S · Depends: 8
  - Owns: generators/decor/placement.py, tests/test_decor_placement.py, generators/room_context.py
  - Reqs: 11

## Added at task 11

- [ ] 16. The giant fortress prompt builds its goblin breaches
  - Card: [cards/16-prompt-breaches.md](cards/16-prompt-breaches.md)
  - Type: agent · Size: M · Depends: 11
  - Owns: analyzer/traverse.py (the Transition clearance check), generators/semantics.py (`flood_level`), ai/rule_planner.py, ai/expand.py, tests/test_district_races_words.py, tests/test_traverse_directed.py, docs/ACCEPTANCE.md (the step 31 prompt case)
  - Reqs: 4, 10, 11
