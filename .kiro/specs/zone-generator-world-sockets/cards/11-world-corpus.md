# 11 — The World corpus

Index entry: `tasks.md` task 11. Requirements 7.1, 7.3. Design "Testing in isolation".

## Goal
`scripts/record_worlds.py` records Worlds from pinned seeds into `tests/fixtures/worlds/`: every biome, every approach side (N, S, E, W), water and none, and every Socket kind the World stage makes, a few MB at most. It has `--check` (re-make in memory, compare, write nothing) and `--list`, as `scripts/record_rooms.py` does. `tests/test_world_corpus.py` checks the corpus loads, covers what it should and stays small; a `slow` contract test re-makes a sample from its seeds and compares the text.

## Done when
- [ ] The corpus covers every biome, approach side, water and none, and Socket kind; it loads; it is small.
      → verify: `python -m pytest tests/test_world_corpus.py -q -m "not slow"`
- [ ] The contract test passes.
      → verify: `python -m pytest tests/test_world_corpus.py -q -m slow`
- [ ] Every recording re-makes the same.
      → verify: `python scripts/record_worlds.py --check`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
An approach side is drawn from the seed: find seeds that give each side, and say which in the recorder's comments. Keep exact floats (task 2); the corpus diffs as text.

## Result
