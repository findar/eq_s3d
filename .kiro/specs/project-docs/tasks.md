# Tasks — project-docs

This file is an **index**. Each task has a card in `cards/`. The project rules are under
"Card-format specs" in `.kiro/steering/project.md`.

**How to run a task:** pick one whose `Depends` are ticked; work in a worktree (`agent/docs-<n>`)
and edit only `Owns`; trailer `Task: project-docs/<n>`; fill the card's Result and tick it here.
**Never tick a `Type: human` task.** No heavy test runs are needed (docs only).

## Tasks

- [ ] 1. Proposal: architecture, pillar map, open items
  - Card: [cards/01-proposal.md](cards/01-proposal.md)
  - Type: agent · Size: M · Depends: —
  - Owns: docs/ARCHITECTURE.md (new), docs/pillars/ (new), OPEN.md (new)

- [ ] 2. HUMAN: review the structure
  - Card: [cards/02-review.md](cards/02-review.md)
  - Type: human · Depends: 1

- [ ] 3. Move the closed steps under their pillars
  - Card: [cards/03-move.md](cards/03-move.md)
  - Type: agent · Size: M · Depends: 2
  - Owns: docs/pillars/, .kiro/specs/ (closed specs only), tasks/

- [ ] 4. One-page roadmap, split acceptance, trimmed steering
  - Card: [cards/04-roadmap.md](cards/04-roadmap.md)
  - Type: agent · Size: M · Depends: 3
  - Owns: ROADMAP.md, README.md, docs/ACCEPTANCE.md, docs/acceptance/, .kiro/steering/, CLAUDE.md

- [ ] 5. Tooling: task_status and the heavy-run lock
  - Card: [cards/05-tooling.md](cards/05-tooling.md)
  - Type: agent · Size: S · Depends: 3
  - Owns: scripts/task_status.py, scripts/heavy.py (new), tests/test_task_status.py

- [ ] 6. Reconcile with master and move the active specs
  - Card: [cards/06-reconcile.md](cards/06-reconcile.md)
  - Type: agent · Size: S · Depends: 4, 5 · Where: MAIN checkout
  - Owns: everything this spec touched
