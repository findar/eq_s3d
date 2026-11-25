# Tasks — test-speed (roadmap step 28)

This file is an **index**. Each task has a card in `cards/` holding the goal, the "Done when"
checks and pitfalls. Decisions are in `archive.md`. The project rules are under "Card-format
specs" in `.kiro/steering/project.md`.

**How to run a task:**
- Pick one whose `Depends` are ticked (`python scripts/task_status.py`).
- Read its card and `design.md`, and verify both against the code.
- Work in a worktree (`agent/speed-<n>`) and edit only `Owns`.
- Put the trailer `Task: test-speed/<n>` on every commit.
- Fill the card's Result and tick the task here.
- **Never tick a `Type: human` task.**

**Timing:** run one heavy suite at a time on the machine. Check for a running `pytest tests/`
or sweep first. Wall times in commit bodies are measured alone.

## Tasks

- [x] 1. Tiers: markers, the quick profile, the quick command
  - Card: [cards/01-tiers.md](cards/01-tiers.md)
  - Type: agent · Size: M · Depends: —
  - Owns: pytest.ini, tests/conftest.py, tests/pbt_helpers.py, marker and `settings` lines in tests/test_*.py
  - Reqs: 1, 2

- [x] 2. A cheaper full suite
  - Card: [cards/02-full.md](cards/02-full.md)
  - Type: agent · Size: M · Depends: 1
  - Owns: tests/ (the files the timings name; stop and report before touching generator code)
  - Reqs: 3

- [ ] 3. Affected-only runs: measure testmon
  - Card: [cards/03-testmon.md](cards/03-testmon.md)
  - Type: agent · Size: S · Depends: 1
  - Owns: nothing committed until the user agrees; scratch measurements only
  - Reqs: 5

- [ ] 4. The rules name the tiers
  - Card: [cards/04-rules.md](cards/04-rules.md)
  - Type: agent · Size: S · Depends: 1, 2
  - Owns: .kiro/steering/project.md, .kiro/steering/lessons-learned.md
  - Reqs: 4

- [ ] 5. Close step 28
  - Card: [cards/05-close.md](cards/05-close.md)
  - Type: agent · Size: S · Depends: 2, 3, 4, 6 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/test-speed/

- [ ] 6. A faster gate
  - Card: [cards/06-gate.md](cards/06-gate.md)
  - Type: agent · Size: M · Depends: 2
  - Owns: analyzer/traverse.py, tests/test_traverse*.py (new equivalence test if warranted); stop and report before widening
  - Reqs: 3
