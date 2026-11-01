# 7 — Format gate checks objects, models and textures

Index entry: `tasks.md` task 7. Requirement 8.3.

## Goal
The Tier-1 RoF2 check covers what trees add: every ZON object's model resolves
to a packed `.mod` that re-reads, every material's textures are packed, and
every shader is known.

## Done when
- [ ] A wilderness build with trees passes; a build with a dropped `.mod`, a
      dropped texture, a bad model index or an unknown shader each fails naming
      the problem.
      → verify: `python -m pytest tests/test_rof2check.py -q`.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- The existing `models[0]` check stays as it is.

## Result
