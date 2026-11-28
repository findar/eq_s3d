# Design — project-docs

Written at master `eab72c0`.

```
docs/ARCHITECTURE.md
docs/pillars/<id>-<name>/PLAN.md, DESIGN.md, DECISIONS.md, OPEN.md, slices/<step-spec>/
docs/acceptance/README.md (index + shared checklist), stepNN-<name>.md
OPEN.md (root roll-up)          ROADMAP.md (one page)
.kiro/steering/ (trimmed)        .kiro/specs/ (active specs only until reconcile)
```

The umbrella spec's requirements and design become the pillars' requirements (IDs kept, e.g.
P-B.4 for Requirement 4) and the architecture doc; its 48 decisions split by pillar. Card-format
rules stay; a slice is today's step spec. Moves use `git mv` so `git log --follow` works.
