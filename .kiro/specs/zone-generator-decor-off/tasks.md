# Tasks — zone-generator-decor-off (roadmap step 34)

Index only; cards in `cards/`. Rules: "Card-format specs" in `.kiro/steering/project.md`. Trailer
`Task: zone-generator-decor-off/<n>`.

## Tasks

- [x] 1. Decor off by default
  - Card: [cards/01-decor-off.md](cards/01-decor-off.md)
  - Type: agent · Size: M · Depends: —
  - Owns: ai/schema.py, generators/pipeline.py (`_with_decor`), server/app.py (the default only), main.py (the default only), web/src/main.ts or web/src/controls.ts (the default selection only), scripts/sweep_*.py (a decor option), tests/ (fixtures and tests that need decor ask for it)
  - Reqs: 1, 2, 3

- [x] 2. Close step 34
  - Card: [cards/02-close.md](cards/02-close.md)
  - Type: agent · Size: S · Depends: 1 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-decor-off/
