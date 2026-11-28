# Tasks — zone-generator-races-followups (roadmap step 32)

This file is an **index**. Each task has a card in `cards/` holding the goal, the "Done when"
checks and pitfalls. Decisions are in `archive.md`. The project rules are under "Card-format
specs" in `.kiro/steering/project.md`.

**How to run a task:** pick one whose `Depends` are ticked (`python scripts/task_status.py`);
read its card and verify it against the code (written at `fbfe1a9`); work in a worktree
(`agent/followups-<n>`) and edit only `Owns`; put the trailer
`Task: zone-generator-races-followups/<n>` on every commit; fill the card's Result and tick the
task here. **Never tick a `Type: human` task.**

## Tasks

- [x] 1. Breaches fit again
  - Card: [cards/01-breach-rate.md](cards/01-breach-rate.md)
  - Type: agent · Size: M · Depends: —
  - Owns: generators/layout.py, generators/embed.py, tests/test_intrusion.py, tests/test_district_races.py
  - Reqs: 1, 4

- [x] 2. Same seed, same build
  - Card: [cards/02-build-leak.md](cards/02-build-leak.md)
  - Type: agent · Size: M · Depends: —
  - Owns: generators/decor/, generators/room_context.py, generators/semantics.py, tests/test_build_order.py (new)
  - Reqs: 3, 4

- [ ] 3. The map's returns are real
  - Card: [cards/03-map-returns.md](cards/03-map-returns.md)
  - Type: agent · Size: S · Depends: 1, 2
  - Owns: generators/zone_spec.py, generators/layout.py, generators/mapview.py, tests/test_mapview_layers.py
  - Reqs: 2

- [ ] 4. Acceptance section
  - Card: [cards/04-acceptance.md](cards/04-acceptance.md)
  - Type: agent · Size: S · Depends: 3
  - Owns: docs/ACCEPTANCE.md

- [ ] 5. HUMAN: look
  - Card: [cards/05-look.md](cards/05-look.md)
  - Type: human · Depends: 4

- [ ] 6. Close step 32
  - Card: [cards/06-close.md](cards/06-close.md)
  - Type: agent · Size: S · Depends: 5 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-races-followups/, .kiro/specs/zone-generator/
