# Tasks — zone-generator-hall-length (roadmap step 30)

This file is an **index**. Each task has a card in `cards/` holding the goal, the "Done when"
checks and pitfalls. Decisions are in `archive.md`. The project rules are under "Card-format
specs" in `.kiro/steering/project.md`.

**How to run a task:**
- Pick one whose `Depends` are ticked (`python scripts/task_status.py`).
- Read its card and the design section it names, and verify both against the code (written at
  `83ec73a`).
- Work in a worktree (`agent/halls-<n>`) and edit only `Owns`.
- Put the trailer `Task: zone-generator-hall-length/<n>` on every commit.
- Fill the card's Result and tick the task here.
- **Never tick a `Type: human` task.**

## Tasks

- [x] 1. Measure stock hall lengths and the range
  - Card: [cards/01-measure.md](cards/01-measure.md)
  - Type: agent · Size: S · Depends: —
  - Owns: scripts/stock_room_shapes.py, scripts/grid_score.py, .kiro/specs/zone-generator-hall-length/archive.md (decisions only)
  - Reqs: 1, 2

- [x] 2. Hall length on the plan, the spec and every layout
  - Card: [cards/02-field.md](cards/02-field.md)
  - Type: agent · Size: M · Depends: 1
  - Owns: ai/schema.py, generators/zone_spec.py, generators/layout.py, generators/layout_engine.py, generators/topology/embed.py, generators/outdoor_dungeon.py, generators/pipeline.py, tests/test_hall_length.py (new), goldens it moves (named in the commit)
  - Reqs: 1, 2, 3

- [x] 3. Controls, server and planner words
  - Card: [cards/03-controls.md](cards/03-controls.md)
  - Type: agent · Size: M · Depends: 2
  - Owns: server/app.py, web/index.html, web/src/main.ts, web/src/api.ts, ai/rule_planner.py, ai/llm_planner.py, tests/test_hall_length_words.py (new)
  - Reqs: 4

- [ ] 4. Gate and bands (first run failed: decision 5; re-run after 8)
  - Card: [cards/04-gate.md](cards/04-gate.md)
  - Type: agent · Size: S · Depends: 2, 8
  - Owns: fixes only where a failure is new (stop and report first)
  - Reqs: 5

- [ ] 5. Acceptance section
  - Card: [cards/05-acceptance.md](cards/05-acceptance.md)
  - Type: agent · Size: S · Depends: 3, 4
  - Owns: docs/ACCEPTANCE.md

- [ ] 6. HUMAN: look
  - Card: [cards/06-look.md](cards/06-look.md)
  - Type: human · Depends: 5

- [ ] 7. Close step 30
  - Card: [cards/07-close.md](cards/07-close.md)
  - Type: agent · Size: S · Depends: 6 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-hall-length/, .kiro/specs/zone-generator/

## Gate fixes (decision 5)

- [x] 8. Long and short hall failures
  - Card: [cards/08-fixes.md](cards/08-fixes.md)
  - Type: agent · Size: L · Depends: 2
  - Owns: generators/ (root-cause fixes; name each file in its commit), tests that pin the fixed seeds, goldens it moves (named); not analyzer/ (the gate's bars stay); stop and report before touching ai/, server/, web/
  - Reqs: 2, 5
