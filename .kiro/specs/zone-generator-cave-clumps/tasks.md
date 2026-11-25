# Tasks — zone-generator-cave-clumps (roadmap step 29)

This file is an **index**. Each task has a card in `cards/` holding the goal, the "Done when"
checks and pitfalls. Decisions are in `archive.md`. The project rules are under "Card-format
specs" in `.kiro/steering/project.md`.

**How to run a task:**
- Pick one whose `Depends` are ticked (`python scripts/task_status.py`).
- Read its card and the design section it names, and verify both against the code (written at
  `056296a`).
- Work in a worktree (`agent/clumps-<n>`) and edit only `Owns`.
- Put the trailer `Task: zone-generator-cave-clumps/<n>` on every commit.
- Fill the card's Result and tick the task here.
- **Never tick a `Type: human` task.**

## Tasks

- [x] 1. Cave draw time
  - Card: [cards/01-draw-time.md](cards/01-draw-time.md)
  - Type: agent · Size: M · Depends: —
  - Owns: generators/topology/embed.py, tests/test_topology_embed.py
  - Reqs: 1

- [x] 2. Probe the shortest corridor
  - Card: [cards/02-probe.md](cards/02-probe.md)
  - Type: agent · Size: S · Depends: —
  - Owns: scripts/throat_probe.py (new), scripts/grid_score.py, .kiro/specs/zone-generator-cave-clumps/archive.md (decisions only)
  - Reqs: 2

- [x] 3. Throats and clumps
  - Card: [cards/03-throats.md](cards/03-throats.md)
  - Type: agent · Size: M · Depends: 1, 2
  - Owns: generators/topology/embed.py, generators/layout_engine.py, tests/test_topology_embed.py, goldens it moves (named in the commit); widened by the lead (task 2's finding): generators/layout.py (`_separate_rooms` keeps same-floor rooms w + 1 apart); stop and report before widening further
  - Reqs: 2, 3, 4

- [ ] 4. Gate and bands
  - Card: [cards/04-gate.md](cards/04-gate.md)
  - Type: agent · Size: S · Depends: 3
  - Owns: fixes only where a failure is new (stop and report first)
  - Reqs: 5

- [ ] 5. Acceptance section
  - Card: [cards/05-acceptance.md](cards/05-acceptance.md)
  - Type: agent · Size: S · Depends: 4
  - Owns: docs/ACCEPTANCE.md

- [ ] 6. HUMAN: look
  - Card: [cards/06-look.md](cards/06-look.md)
  - Type: human · Depends: 5

- [ ] 7. Close step 29
  - Card: [cards/07-close.md](cards/07-close.md)
  - Type: agent · Size: S · Depends: 6 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-cave-clumps/, .kiro/specs/zone-generator/
