# 2 — Walls beside and above every doorway

Index entry: `tasks.md` task 2. Design Open question 2 (answered: fix in 1b,
see `archive.md`). No requirement number; it's a walkability defect.

## Goal
A room side that has a corridor is dropped whole (`room.open_walls` in
`generators/geometry.py`), so 55–57% of the floor edge on the test seeds is a
drop into the void, and a player can walk off the floor beside a doorway. Build
that side as wall pieces either side of each opening plus a lintel above it, so
the only gap is the corridor's own width and height. The outline (task 4) then
draws real walls instead of ledges.

## Done when
- [ ] Every opening on an open wall is exactly the corridor's width, centred on
      the corridor's end leg (the Doorway_Span from `routing.corridor_route`),
      with wall above it up to the room's ceiling. A side with two corridors
      gets two openings.
      → verify: a new test in `tests/test_generators.py` that measures the wall gap on a built room against `corridor_route`.
- [ ] Rooms, corridors and elevation are unchanged: the layouts of seeds
      1955208177, 1516796975 and 678358326 are the same; only box TER bytes move.
      → verify: `python -m pytest tests/test_traversability.py tests/test_properties_build.py -q`.
- [ ] Walkability and corridor-continuity tests still pass with no loosening.
      → verify: `python -m pytest tests/ -q` is green.
- [ ] The commit body says box TER bytes change for every seed with a corridor
      (a geometry break, not a layout break).

## Pitfalls
- Read lessons-learned "Same-axis room pairs need a Z-route" and "A ramp must
  be SUBDIVIDED": openings land where `_wall_point` puts them, and ramp ends
  must stay flush with the opening.
- The opening must cover the corridor's full width, or the corridor floor runs
  into a wall piece. Use the routed end leg, not the room centre line.
- The agent can't check this in 3D; say so in Result. Task 12 eyeballs it.

## Result
