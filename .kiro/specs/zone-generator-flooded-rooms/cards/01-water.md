# 1 — Water fills a flooded room

Index entry: `tasks.md` task 1. Requirements 1–5.

## Goal
A flooded room shows flat water over its whole floor at one water line, and its `AWT` region
matches that water on the room's final floor.

## Done when
- [ ] Every flooded room in cave and sunken_ruin builds (both layouts) has water polygons covering
      its floor's area, all passable at the water line, and a region over its footprint up to that
      line. → verify: `python -m pytest tests/test_flooded_rooms.py -q`
- [ ] The byte check passes for zones with no flooded room; goldens with one are recaptured by name.
- [ ] The cave and warren gate sweep stays at its step 23 count (691/696).
      → verify: `python scripts/sweep_themed_navigability.py --only cave warren ...` (as step 23 task 5)
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- Floors move after the semantic pass (the relax after a split, `_fit_floors`): read the water
  line from the final floor (`settle_floods`).
- lessons-learned "Two `.eqg` writes are never byte-identical".

## Result
