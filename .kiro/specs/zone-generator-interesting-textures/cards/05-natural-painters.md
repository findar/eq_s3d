# 5 — Painters: natural and other families

Index entry: `tasks.md` task 5. Design: "Painters". Requirement 4.

## Goal
The remaining families on task 4's building blocks: `planks`, `plaster`,
`dirt`, `grass`, `mud`, `sand`, `lava`, `water`, `ice`, `sky` (and `foliage`
if Open question 4 says so).

## Done when
- [ ] Each family paints a seamless, pure, distinct 256×256 image with its
      structure (grain, ripples, blades, cracks…).
- [ ] Rendered samples looked at by the worker; the commit body says what was
      seen.
      → verify: `python -m pytest tests/test_painters_natural.py -q`.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- Water and lava are surfaces players see from above at a distance; they need
  less fine detail than stone, and the recipe lists their Look_Stats exceptions.

## Result
