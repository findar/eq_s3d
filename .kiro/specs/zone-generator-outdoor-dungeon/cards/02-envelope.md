# 2 — Envelope and layout inside it

Index entry: `tasks.md` task 2. Requirements 2.

## Goal
`Envelope` (a continuous 3D predicate) and `LayoutGenerator.generate(envelope=...)`: every room and corridor inside it; `envelope=None` byte-identical to today.

## Done when
- [ ] D1: layouts without an Envelope are byte-identical (the step 3 UV-free goldens and layout tests pass untouched).
- [ ] D2: with a synthetic Envelope (a sloped surface over a disc footprint), every room box and corridor swept box lies inside it, over many seeds (Hypothesis).
- [ ] Rooms that don't fit are dropped to a minimum of 3 with a `rooms_reduced` warning.
      → verify: `python -m pytest tests/test_envelope.py tests/test_material_names.py -q`.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- Corridors are checked as swept boxes, not centre lines.
- lessons-learned: same-axis room pairs route as Z-corridors; keep the routing, only reject or re-route what leaves the Envelope.

## Result
