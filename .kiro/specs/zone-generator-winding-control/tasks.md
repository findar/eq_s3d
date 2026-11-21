# Tasks — zone-generator-winding-control (roadmap step 26)

This file is an **index**. Each task has a card in `cards/` holding the goal, the "Done when"
checks and pitfalls. Decisions are in `archive.md`. The project rules are under "Card-format
specs" in `.kiro/steering/project.md`.

**How to run a task:**
- Pick one whose `Depends` are ticked (`python scripts/task_status.py`).
- Read its card and the design section it names, and verify both against the code (written at
  `3f925f8`).
- Work in a worktree (`agent/winding-<n>`) and edit only `Owns`.
- Put the trailer `Task: zone-generator-winding-control/<n>` on every commit.
- Fill the card's Result and tick the task here.
- **Never tick a `Type: human` task.**

Bytes (Req 4): at `winding = 1`, every zone stays byte-identical. Prove it with:

`EQ_PATH='F:\everquest_rof2' python -m pytest tests/test_layout_engine.py tests/test_site_builds.py tests/test_decor_builds.py tests/test_partial_rebuild.py -q -n 4`

## Tasks

- [x] 1. Winding on the plan, the spec and every reader
  - Card: [cards/01-plumbing.md](cards/01-plumbing.md)
  - Type: agent · Size: M · Depends: —
  - Owns: ai/schema.py, generators/zone_spec.py, generators/layout.py, generators/pipeline.py, generators/builder.py, generators/transitions.py, generators/wall_styles.py, generators/routing.py, callers of `winding_legs`/`tunnel_rules()` (named in the commit), tests/test_winding_control.py
  - Reqs: 1, 2, 3, 4

- [x] 2. Measure the range
  - Card: [cards/02-range.md](cards/02-range.md)
  - Type: agent · Size: S · Depends: 1
  - Owns: ai/schema.py (`WINDING_MAX`), generators/layout.py (run factor, only if measured), tests/test_winding_control.py, archive.md
  - Reqs: 2

- [x] 3. Controls, server and planner words
  - Card: [cards/03-controls.md](cards/03-controls.md)
  - Type: agent · Size: M · Depends: 2
  - Owns: server/app.py, web/index.html, web/src/main.ts, web/src/api.ts, ai/rule_planner.py, ai/llm_planner.py, tests/test_winding_words.py
  - Reqs: 5

- [x] 4. Gate and bands
  - Card: [cards/04-gate.md](cards/04-gate.md)
  - Type: agent · Size: S · Depends: 2
  - Owns: fixes only where a failure is new (stop and report first)
  - Reqs: 6

- [x] 5. Acceptance section
  - Card: [cards/05-acceptance.md](cards/05-acceptance.md)
  - Type: agent · Size: S · Depends: 3, 4
  - Owns: docs/ACCEPTANCE.md

- [ ] 6. HUMAN: first look
  - Card: [cards/06-first-look.md](cards/06-first-look.md)
  - Type: human · Depends: 5

- [ ] 7. Close step 26
  - Card: [cards/07-close.md](cards/07-close.md)
  - Type: agent · Size: S · Depends: 6 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-winding-control/, .kiro/specs/zone-generator/
