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

The design's open questions were settled on 2026-11-03 (`archive.md`
"Decisions").

## Tasks

- [x] 1. Measure the stock dungeon topology
  - Card: [cards/01-topology-survey.md](cards/01-topology-survey.md)
  - Type: agent · Size: M · Depends: —
  - Owns: scripts/dungeon_topology_survey.py, .kiro/specs/zone-generator-graph-layout/design.md
  - Reqs: 1

- [x] 2. LayoutEngine seam, byte-identical
  - Card: [cards/02-engine-seam.md](cards/02-engine-seam.md)
  - Type: agent · Size: M · Depends: —
  - Owns: generators/layout_engine.py, generators/layout.py, tests/test_layout_engine.py
  - Reqs: 2

- [x] 3. Rule-set format, loader and checks
  - Card: [cards/03-ruleset-format.md](cards/03-ruleset-format.md)
  - Type: agent · Size: M · Depends: —
  - Owns: generators/topology/__init__.py, generators/topology/graph.py, generators/topology/ruleset.py, tests/test_topology_ruleset.py
  - Reqs: 3.1–3.3

- [x] 4. Rewrite driver, recipes and layers
  - Card: [cards/04-rewrite-driver.md](cards/04-rewrite-driver.md)
  - Type: agent · Size: M · Depends: 3
  - Owns: generators/topology/rewrite.py, tests/test_topology_rewrite.py
  - Reqs: 4

- [x] 5. Base set classic_eq and the temple layer
  - Card: [cards/05-classic-eq.md](cards/05-classic-eq.md)
  - Type: agent · Size: M · Depends: 1, 4
  - Owns: rules/topology/classic_eq.toml, rules/topology/layers/temple.toml, rules/topology/themes.toml, tests/test_ruleset_classic_eq.py
  - Reqs: 5.1, 5.3

- [ ] 6. Base set warren
  - Card: [cards/06-warren.md](cards/06-warren.md)
  - Type: agent · Size: S · Depends: 1, 4, 5
  - Owns: rules/topology/warren.toml, tests/test_ruleset_warren.py, rules/topology/themes.toml
  - Reqs: 5.1, 5.2

- [ ] 7. Check, dry-run and draw; the authoring guide
  - Card: [cards/07-tooling-and-guide.md](cards/07-tooling-and-guide.md)
  - Type: agent · Size: M · Depends: 5
  - Owns: scripts/topology_rules.py, generators/topology/draw.py, docs/TOPOLOGY_RULES.md, rules/topology/README.md
  - Reqs: 3.4–3.6

- [x] 8. Placement, size classes and the graph engine
  - Card: [cards/08-placement.md](cards/08-placement.md)
  - Type: agent · Size: M · Depends: 2, 5
  - Owns: generators/topology/embed.py, generators/layout_engine.py, generators/layout.py, generators/topology/rewrite.py (BuildContext only), tests/test_topology_embed.py
  - Reqs: 6

- [ ] 9. Plan fields, theme kind map, sidecar
  - Card: [cards/09-plan-and-sidecar.md](cards/09-plan-and-sidecar.md)
  - Type: agent · Size: M · Depends: 8
  - Owns: ai/schema.py, ai/expand.py, generators/semantics.py, generators/zone_spec.py, generators/builder.py, tests/test_graph_layout_plan.py
  - Reqs: 7.2–7.5

- [ ] 10. CLI, server and outdoor dungeon
  - Card: [cards/10-cli-server.md](cards/10-cli-server.md)
  - Type: agent · Size: S · Depends: 9
  - Owns: main.py, server/app.py, generators/outdoor_dungeon.py, tests/test_graph_layout_controls.py
  - Reqs: 7.1, 6.6

- [ ] 11. Web: Layout toggle and rule set
  - Card: [cards/11-web.md](cards/11-web.md)
  - Type: agent · Size: S · Depends: 10
  - Owns: web/index.html, web/src/main.ts
  - Reqs: 7.1

- [ ] 12. Gate sweep on built zones
  - Card: [cards/12-gate-sweep.md](cards/12-gate-sweep.md)
  - Type: agent · Size: M · Depends: 10
  - Owns: tests/test_graph_layout_build.py, generators/topology/embed.py, rules/topology/
  - Reqs: 8

- [ ] 13. HUMAN: first look, classic against graph
  - Card: [cards/13-human-first-look.md](cards/13-human-first-look.md)
  - Type: human · Depends: 7, 11, 12

- [ ] 14. Tune from the first look
  - Card: [cards/14-tuning.md](cards/14-tuning.md)
  - Type: agent · Size: S · Depends: 13
  - Owns: rules/topology/, generators/topology/, tests/test_topology_embed.py, tests/test_ruleset_classic_eq.py, tests/test_ruleset_warren.py

- [ ] 15. Acceptance section, thorough run, timing
  - Card: [cards/15-release-prep.md](cards/15-release-prep.md)
  - Type: agent · Size: S · Depends: 14
  - Owns: docs/ACCEPTANCE.md, tests/test_graph_layout_build.py
  - Reqs: 8.4, exit criteria 1–2

- [ ] 16. HUMAN: graph layout acceptance pass
  - Card: [cards/16-human-acceptance.md](cards/16-human-acceptance.md)
  - Type: human · Depends: 15

- [ ] 17. Close step 6
  - Card: [cards/17-close.md](cards/17-close.md)
  - Type: agent · Size: S · Depends: 16 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-graph-layout/, .kiro/specs/zone-generator/
