# 1 — The route line and its clearance

Index entry: `tasks.md` task 1. Requirements 1, 2. Design "Data", "The route line", "Clearance".

## Goal
`routing.wind_route` draws a rough corridor's centreline opening to opening, and
`transitions.measure_winds` stores it in `CorridorSpec.path` when its strip clears everything else
(A2), else keeps step 23's per-leg `wind`.

## Done when
- [x] `wind_route` starts and ends at the openings, runs straight `max(hw, end)` out of each, no
      turn exceeds `max_turn`, and it is pure for a seed. → verify:
      `python -m pytest tests/test_wind_route.py -q`
- [x] Over 10 cave graph builds (8–30 rooms, each verticality) every stored `path`'s strip keeps
      `PLAYER_HALF_WIDTH` from every room box and other corridor box in its Z band. Same command.
      The share of rough corridors that got a `path` goes in the commit body.
- [x] A spec without `path` loads as before; `_corridor_dict` writes `path` only when set.
- [ ] `python -m pytest tests/ -q -m "not slow"` is green. Nothing reads `path` until task 2, so
      the mesh is unchanged; the byte check passes.

## Pitfalls
- Tasks 2 and 3 read `path`: keep its shape exactly as the design says.
- Don't change routes, footprints or conflicts (A1).

## Result
