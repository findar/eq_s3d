# Tasks — zone-generator-layout-repair (roadmap step 33)

This file is an **index**. Each task has a card in `cards/` holding the goal, the "Done when"
checks and pitfalls. Decisions are in `archive.md`. The project rules are under "Card-format
specs" in `.kiro/steering/project.md`.

**How to run a task:** pick one whose `Depends` are ticked (`python scripts/task_status.py`);
read its card and verify it against the code (written at `0eeec16`); work in a worktree
(`agent/repair-<n>`) and edit only `Owns`; put the trailer
`Task: zone-generator-layout-repair/<n>` on every commit; fill the card's Result and tick the
task here. **Never tick a `Type: human` task.** Cards 2-4 are refined from task 1's measure
before they start.

## Tasks

- [x] 1. Measure where a generate's time goes
  - Card: [cards/01-measure.md](cards/01-measure.md)
  - Type: agent · Size: M · Depends: —
  - Owns: scripts/generate_profile.py (new), generators/pipeline.py (timers and reasons only, no behaviour change), generators/layout.py (the same)
  - Reqs: 1

- [ ] 2. Check the plan before the mesh
  - Card: [cards/02-plan-check.md](cards/02-plan-check.md)
  - Type: agent · Size: M · Depends: 1
  - Owns: generators/plancheck.py (new), generators/pipeline.py, tests/test_plancheck.py (new)
  - Reqs: 2

- [ ] 3. Repair locally
  - Card: [cards/03-repair.md](cards/03-repair.md)
  - Type: agent · Size: L→split after task 1 · Depends: 2
  - Owns: generators/layout.py, generators/embed.py, generators/plancheck.py, tests/test_plancheck.py
  - Reqs: 3, 5

- [ ] 4. Score intended contacts
  - Card: [cards/04-contact.md](cards/04-contact.md)
  - Type: agent · Size: M · Depends: 3
  - Owns: generators/embed.py, generators/layout.py, tests/test_intrusion.py
  - Reqs: 4, 5

- [ ] 5. Gate, bands and timing
  - Card: [cards/05-gate.md](cards/05-gate.md)
  - Type: agent · Size: S · Depends: 4
  - Owns: fixes only where a failure is new (stop and report first)
  - Reqs: 5

- [ ] 6. HUMAN: look
  - Card: [cards/06-look.md](cards/06-look.md)
  - Type: human · Depends: 5

- [ ] 7. Close step 33
  - Card: [cards/07-close.md](cards/07-close.md)
  - Type: agent · Size: S · Depends: 6 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-layout-repair/, .kiro/specs/zone-generator/
