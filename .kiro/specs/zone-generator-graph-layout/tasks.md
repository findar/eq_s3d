# Tasks — zone-generator-graph-layout (roadmap step 6)

This file is an **index**. Each task has a card in `cards/` holding the goal,
the "Done when" checks (each with the exact command that proves it) and
pitfalls. Decisions later tasks rely on are in `archive.md`.

**How to run a task** (the project-wide rules are in `.kiro/steering/project.md`):
1. Pick a task whose `Depends` are all ticked. `python scripts/task_status.py`
   lists the ready ones and which can run side by side.
2. Read its card, then the design section it names. Verify both against the
   code; the design was written at `67e5b69`.
3. Work in a worktree (`agent/graph-<n>`) unless the card says MAIN
   checkout. Edit only the files under `Owns`.
4. Every commit carries the trailer
   `Task: zone-generator-graph-layout/<n>`.
5. When every "Done when" box passes, write the card's one-line Result and tick
   the box here. **Never tick a `Type: human` task.**

Index fields: `Type` is `agent` or `human`. `Size` is S (≤ 2 files) / M (≤ 5) /
L (split it). `Depends` lists task numbers. `Owns` lists the files and folders
the task may edit; two ready tasks with disjoint `Owns` can run in parallel.

**Not ready to run:** the design's open questions are not answered yet. Record
the answers in `archive.md` "Decisions" before starting any task; tasks 6–8
depend on questions 1–3.

## Tasks

- [ ] 1. Measure the stock dungeon topology
  - Card: [cards/01-topology-survey.md](cards/01-topology-survey.md)
  - Type: agent · Size: M · Depends: —
  - Owns: scripts/dungeon_topology_survey.py, .kiro/specs/zone-generator-graph-layout/design.md
  - Reqs: 1

- [ ] 2. LayoutEngine seam, byte-identical
  - Card: [cards/02-engine-seam.md](cards/02-engine-seam.md)
  - Type: agent · Size: M · Depends: —
  - Owns: generators/layout_engine.py, generators/layout.py, tests/test_layout_engine.py
  - Reqs: 2

- [ ] 3. Topology graph and rewrite driver
  - Card: [cards/03-grammar-driver.md](cards/03-grammar-driver.md)
  - Type: agent · Size: M · Depends: —
  - Owns: generators/topology/__init__.py, generators/topology/graph.py, generators/topology/rewrite.py, tests/test_topology_grammar.py
  - Reqs: 3

- [ ] 4. Rules and profiles from the survey
  - Card: [cards/04-rules-profiles.md](cards/04-rules-profiles.md)
  - Type: agent · Size: M · Depends: 1, 3
  - Owns: generators/topology/rules.py, tests/test_topology_profiles.py
  - Reqs: 4

- [ ] 5. Embedding and the grown engine
  - Card: [cards/05-embedding.md](cards/05-embedding.md)
  - Type: agent · Size: M · Depends: 2, 4
  - Owns: generators/topology/embed.py, generators/layout_engine.py, tests/test_topology_embed.py
  - Reqs: 5

- [ ] 6. Plan field, planner words, sidecar
  - Card: [cards/06-plan-and-sidecar.md](cards/06-plan-and-sidecar.md)
  - Type: agent · Size: M · Depends: 5
  - Owns: ai/schema.py, ai/rule_planner.py, ai/expand.py, generators/zone_spec.py, generators/builder.py, tests/test_grown_layout_plan.py
  - Reqs: 6.2, 6.3

- [ ] 7. CLI, server and outdoor dungeon
  - Card: [cards/07-cli-server.md](cards/07-cli-server.md)
  - Type: agent · Size: S · Depends: 6
  - Owns: main.py, server/app.py, generators/outdoor_dungeon.py, tests/test_grown_layout_controls.py
  - Reqs: 6.1, 5.3

- [ ] 8. Web: layout control
  - Card: [cards/08-web.md](cards/08-web.md)
  - Type: agent · Size: S · Depends: 7
  - Owns: web/index.html, web/src/main.ts
  - Reqs: 6.1

- [ ] 9. Gate sweep on built zones
  - Card: [cards/09-gate-sweep.md](cards/09-gate-sweep.md)
  - Type: agent · Size: M · Depends: 7
  - Owns: tests/test_grown_layout_build.py, generators/topology/embed.py, generators/topology/rules.py
  - Reqs: 7

- [ ] 10. HUMAN: first look, classic against grown
  - Card: [cards/10-human-first-look.md](cards/10-human-first-look.md)
  - Type: human · Depends: 8, 9

- [ ] 11. Tune from the first look
  - Card: [cards/11-tuning.md](cards/11-tuning.md)
  - Type: agent · Size: S · Depends: 10
  - Owns: generators/topology/, tests/test_topology_embed.py, tests/test_topology_profiles.py

- [ ] 12. Acceptance section, thorough run, timing
  - Card: [cards/12-release-prep.md](cards/12-release-prep.md)
  - Type: agent · Size: S · Depends: 11
  - Owns: docs/ACCEPTANCE.md, tests/test_grown_layout_build.py
  - Reqs: 7.4, exit criteria 1–2

- [ ] 13. HUMAN: grown layout acceptance pass
  - Card: [cards/13-human-acceptance.md](cards/13-human-acceptance.md)
  - Type: human · Depends: 12

- [ ] 14. Close step 6
  - Card: [cards/14-close.md](cards/14-close.md)
  - Type: agent · Size: S · Depends: 13 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-graph-layout/, .kiro/specs/zone-generator/
