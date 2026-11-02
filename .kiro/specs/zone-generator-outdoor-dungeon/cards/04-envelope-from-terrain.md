# 4 — Envelope from the built terrain

Index entry: `tasks.md` task 4. Requirements 2.1, 3.1.

## Goal
Build the Envelope from the Host_Hill's TER heights and the Rock_Cover; size the room count to fit.

## Done when
- [x] `surface(x, y)` matches the TER heights at the hill (sampled), `top_at` is surface minus Rock_Cover, and the footprint is the hill region.
- [x] A default room count fits on every seed of a sample (no `rooms_reduced`).
      → verify: `python -m pytest tests/test_outdoor_envelope.py -q`.
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
- Sample the TER, not the matrix: the built heights are what the player walks.

## Result
✔ c1f30c9 · 939 passed
