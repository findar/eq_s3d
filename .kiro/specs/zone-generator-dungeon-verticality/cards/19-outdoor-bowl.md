# 19 — Outdoor corridors and stairs stay inside the bowl

Index entry: `tasks.md` task 19. Requirements 7.2. Added after task 9 (found by it).

## Goal
Task 9 found dragon outdoor dungeons at moderate leak through the map edge: on seed 1654615998 (temple, 5 rooms) `corr_1`, a 192 u stair from `room_1` (Level 0) down to `room_2` (Level -1), puts walkable faces at x -541 to -440, inside the W off-map band (x < -440), so the bowl gate reads the flood as escaping (`BOWL-LEAK`); 7 of 10 seeds needed retries (19 in all). The outdoor fit checks rock cover over every corridor leg but not that legs, bends and switchback stairwells stay inside `bowl_interior` (step 6 task 12 clipped the Envelope footprint for rooms only). Keep every corridor piece inside the bowl interior, at the source.

## Done when
- [ ] The Envelope fit (or the outdoor plan) rejects or re-routes a corridor whose legs, bends or stairwell leave the bowl interior; a regression test pins seed 1654615998 (dragon, temple, 5 rooms, moderate) and checks every corridor piece inside the interior and the gate passing first try.
- [ ] Dragon outdoor dungeons at moderate join task 9's sweep (`tests/test_vertical_build.py`); their first-try rate is in the commit body.
- [ ] Every other outdoor test and the step 5 cases unchanged.
      → verify: `python -m pytest tests/test_outdoor_levels.py tests/test_vertical_build.py tests/test_outdoor_envelope.py tests/test_entrance.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- Use the same stair footprint the builder uses (`generators.geometry.stair_layout`'s path and stairwell), not the leg box.
- Rooms dropped for not fitting are still recorded with `rooms_reduced`.

## Result
