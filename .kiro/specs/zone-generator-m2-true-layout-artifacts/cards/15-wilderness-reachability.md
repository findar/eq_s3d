# 15 — Wilderness: every playable cell reachable from spawn

Index entry: `tasks.md` task 15. Found by task 11's thorough run
(2026-10-31). It's a step 1 (wilderness) bug, not an M2 regression:
`generators/wilderness/matrix.py` hasn't changed since the wilderness
milestone. It's fixed here because step 1b's exit needs a green thorough run.

## Goal
`tests/test_wilderness_matrix.py::test_property5_playable_regions_reachable_from_spawn`
fails under `--hypothesis-profile=thorough` for plains with all four edges
`mountain`, seed 2275961: the playable cell (1, 14) can't be reached from the
spawn at (8, 8). Find why `build_matrix` leaves a playable cell cut off, and
fix it at the root so Property 5 holds for every input.

## Done when
- [ ] The failing case is pinned as an `@example` on the property, and passes.
      → verify: `python -m pytest tests/test_wilderness_matrix.py -q`.
- [ ] Property 5 passes three thorough runs.
      → verify: `python -m pytest tests/test_wilderness_matrix.py -q --hypothesis-profile=thorough` (three times).
- [ ] The commit body names the root cause and says how many seeds' matrices
      the fix changes (it may move some wilderness layouts).
- [ ] `python -m pytest tests/ -q` is green with no loosened test.

## Pitfalls
- Don't loosen Property 5 or filter the case out; an unreachable playable cell
  is a real navigability bug.
- `_assert_construction_invariants` is meant to enforce reachability; find out
  why it didn't catch this case.
- If the fix needs `rewrite.py`, `synth.py` or `bowl.py`, stop and say so.
- The agent can't check this in 3D; say so in Result.

## Result
