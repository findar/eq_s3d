# 5 — Painters: timber, plaster, ice and sky

Index entry: `tasks.md` task 5. Design: "Painters". Requirement 4.

## Goal
The remaining dungeon and city families on task 4's building blocks:
`planks`, `plaster`, `ice`, `sky`. (Ground, water, lava and foliage families
come with the wilderness step.)

## Done when
- [x] Each family paints a seamless, pure, distinct 256×256 image with its
      structure (plank grain and seams, plaster cracks and stains, ice
      fractures, cloud).
- [x] Rendered samples looked at by the worker; the commit body says what was
      seen.
      → verify: `python -m pytest tests/test_painters_natural.py -q`.
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
- `ice` (ice_keep and the ice tint) and `sky` (city ceilings) sit outside the
  classic brightness band by nature; the recipe lists their Look_Stats
  exceptions.

## Result
✔ 1aa8889 · 801 passed
