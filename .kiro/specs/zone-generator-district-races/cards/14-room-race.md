# 14 — Size everything in a room by the room's race

Index entry: `tasks.md` task 14. Requirement 4.

## Goal
Inside a District with its own race, the outline's wall wander, room features, decor cells,
transition forms and sunk/raised floors all size by that room's race, not the zone's (task 4
sized rooms and corridors only).

## Done when
- [ ] One helper gives a room's race (its District's, else the zone's); the sites task 4 found
      use it: `wall_styles.py` outline wander, `room_layouts.py` features, `room_context.py`
      decor cells, `transitions.py` forms, `semantics._apply_shape` sink/raise.
- [ ] A giant/goblin pair over seeds 2000–2019 passes the gate; in giant rooms feature and
      decor cell sizes scale by H(giant)/H(zone) (test where cheap).
- [ ] Byte identity for zones whose Districts carry no race and for all zones without them.
- [ ] Quick tier; `-m gate` and the full suite alone at close.

## Pitfalls
- Cave throats keep the zone's corridor width (step 29): say whether a raced cave District
  should scale them, and stop and report rather than decide.
- Decor placement's clear widths are the PLAYER's (6 u agent), not the race's: don't scale those.

## Result
✔ c8d8138 · 4305 passed
