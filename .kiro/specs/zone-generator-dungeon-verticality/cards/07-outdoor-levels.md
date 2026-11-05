# 7 — Outdoor dungeons go down

Index entry: `tasks.md` task 7. Requirements 7. Design "Outdoor dungeons".

## Goal
Outdoor dungeons honour Verticality and go down into the hill: the Envelope's floor limit follows the control, rooms take more than one Level where it fits, the Tunnel enters at the top Level.

## Done when
- [x] V8 on the step 5 acceptance seeds at `moderate` and `dramatic`: every room under the hill with the Rock_Cover, one Entrance at the top Level, every room reached from the Outdoor_Spawn; at least two Levels where the hill holds them (rooms dropped with `rooms_reduced` otherwise).
- [x] `flat` outdoor dungeons build as today (step 5's tests unchanged).
      → verify: `python -m pytest tests/test_outdoor_levels.py tests/test_outdoor_envelope.py tests/test_entrance.py tests/test_graph_layout_controls.py -q`
- [x] Measure the big-race outdoor dungeon (ogre, giant) at `dramatic`: does the deeper floor limit let it plan? Write the result in the commit body (fixing it is a follow-up unless it falls out).

## Pitfalls
- The Tunnel is planned against the entrance room; with Levels, that room must be on the top Level (the Envelope's `entry` already picks the entrance room).

## Result
✔ 69f9daa · 1377 passed
