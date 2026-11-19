# 1 — The partition

Index entry: `tasks.md` task 1. Requirement 1. Design "Partition".

## Goal
`generators/districts.py`: `district_count`, `partition_districts`, `district_climaxes` and the
`Partition` result; `DistrictSpec` on `ZoneSpec.districts` and `CorridorSpec.threshold`, both
round-tripping and defaulting on load.

## Done when
- [x] For random connected graphs of 1–30 rooms and k = 1–3: every room in one District, each
      District connected and at least max(3, ⌊n/(k+1)⌋) rooms (or k dropped, with requested and
      resolved counts), exactly one kept edge between adjacent Districts, kept edges connected,
      same result for the same seed, one climax per District by 23.4. → verify:
      `python -m pytest tests/test_districts.py -q`
- [x] k = 1 returns the edges unchanged and draws nothing from the rng (compare `rng.getstate()`).
      Same command.
- [x] A spec with Districts survives `to_dict`/`from_dict`; a dict without `districts` or
      `threshold` loads with them empty/False. Same command.
- [x] The byte check in `tasks.md` passes; `python -m pytest tests/ -q` is green.

## Pitfalls
Use `layout.gate_tree`'s BFS ordering (sorted adjacency) so the tree is deterministic; don't
import `layout` into `districts` if it makes a cycle (copy the 10-line BFS instead). Hypothesis
tests: keep them fast (lessons-learned on parallel suites).

## Result
✔ c2c0a14 · 3568 passed
