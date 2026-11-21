# Tasks — zone-generator-flooded-rooms (roadmap step 24)

This file is an **index**. Each task has a card in `cards/`. Decisions are in `archive.md`.
The rules are under "Card-format specs" in `.kiro/steering/project.md`.

Bytes: a zone with no flooded room stays byte-identical, proven by
`python -m pytest tests/test_layout_engine.py tests/test_site_builds.py tests/test_decor_builds.py tests/test_partial_rebuild.py -q`.
A golden whose zone has a flooded room may be recaptured, named in its own commit.

## Tasks

- [ ] 1. Water fills a flooded room
  - Card: [cards/01-water.md](cards/01-water.md)
  - Type: agent · Size: M · Depends: — · Where: MAIN checkout
  - Owns: generators/semantics.py (the flood), generators/geometry.py (`_add_flood`), generators/layout.py (`settle_floods` call), analyzer/traverse.py (`WalkSurface.solid`), tests/test_flooded_rooms.py, goldens of zones with flooded rooms (named)
  - Reqs: 1–6

- [ ] 2. HUMAN: look at a flooded room
  - Card: [cards/02-look.md](cards/02-look.md)
  - Type: human · Depends: 1

- [ ] 3. Close step 24
  - Card: [cards/03-close.md](cards/03-close.md)
  - Type: agent · Size: S · Depends: 2 · Where: MAIN checkout
  - Owns: ROADMAP.md, .kiro/specs/zone-generator-flooded-rooms/
