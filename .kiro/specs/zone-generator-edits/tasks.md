# Tasks — zone-generator-edits (roadmap step 18)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Decisions later tasks rely on are in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card, then the design section it names. Verify both against the
   code; the design was written at `bac2371`.
3. Work in a worktree (`agent/edits-<n>`) unless the card says MAIN
   checkout. Edit only the files under `Owns`.
4. Every commit carries the trailer `Task: zone-generator-edits/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**
6. Iterate on your task's own tests and `python -m pytest tests/ -q -m "not slow"`;
   run the full Python suite once before ticking, and don't commit while it runs
   (a server-staleness test notices).

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it); recaptured golden hashes don't count. `Depends` lists task numbers.
`Owns` lists the files and folders the task may edit; two ready tasks with
disjoint `Owns` can run in parallel.

**The shape was chosen by the lead on 2026-11-18** and is confirmed with the user at task 9
(`archive.md` "Decisions").

Bytes: Generate and every rebuild stay byte-identical (Req 5). Every task proves it with
`python -m pytest tests/test_layout_engine.py tests/test_site_builds.py tests/test_decor_builds.py tests/test_partial_rebuild.py -q`.

## Tasks

- [x] 1. Edit ops and the rule interpreter
  - Card: [cards/01-interpreter.md](cards/01-interpreter.md)
  - Type: agent · Size: M · Depends: —
  - Owns: ai/edits.py, tests/test_edit_interpreter.py
  - Reqs: 1.1–1.4

- [x] 2. Ground the resize ops
  - Card: [cards/02-resize-grounding.md](cards/02-resize-grounding.md)
  - Type: agent · Size: S · Depends: —
  - Owns: .kiro/specs/zone-generator-edits/archive.md, .kiro/specs/zone-generator-edits/cards/07-resize.md
  - Reqs: A3, 2.7

- [x] 3. Apply the spec-only ops
  - Card: [cards/03-apply.md](cards/03-apply.md)
  - Type: agent · Size: M · Depends: 1
  - Owns: generators/edits.py, generators/layout.py (lifting the gating rule into a function only), tests/test_edits.py
  - Reqs: 2.1–2.6

- [ ] 4. The edit route and CLI
  - Card: [cards/04-route.md](cards/04-route.md)
  - Type: agent · Size: M · Depends: 3
  - Owns: server/app.py, main.py, generators/rebuild.py, tests/test_edit_route.py, tests/test_hygiene.py (the CLI option allowlist only)
  - Reqs: 3

- [ ] 5. The Feedback section in the page
  - Card: [cards/05-page.md](cards/05-page.md)
  - Type: agent · Size: M · Depends: 4
  - Owns: web/src/, web/index.html, tests/test_hygiene.py (the web control id allowlist only)
  - Reqs: 4

- [ ] 6. The optional LLM interpreter
  - Card: [cards/06-llm.md](cards/06-llm.md)
  - Type: agent · Size: S · Depends: 1
  - Owns: ai/llm_edits.py, tests/test_llm_edits.py
  - Reqs: 1.5

- [ ] 7. Resize ops (if task 2 says yes)
  - Card: [cards/07-resize.md](cards/07-resize.md)
  - Type: agent · Size: M · Depends: 2, 3
  - Owns: generators/resize.py, generators/edits.py (the resize rows only), tests/test_resize.py
  - Reqs: 2.7

- [ ] 8. Acceptance section
  - Card: [cards/08-acceptance.md](cards/08-acceptance.md)
  - Type: agent · Size: S · Depends: 5
  - Owns: docs/ACCEPTANCE.md

- [ ] 9. HUMAN: first look
  - Card: [cards/09-first-look.md](cards/09-first-look.md)
  - Type: human · Depends: 5, 8

- [ ] 10. Close step 18
  - Card: [cards/10-close.md](cards/10-close.md)
  - Type: agent · Size: S · Depends: 6, 7, 9 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-edits/, .kiro/specs/zone-generator/
