# 2 — Hall length on the plan, the spec and every layout

Index entry: `tasks.md` task 2. Requirements 1–3, design "The field".

## Goal
`ZonePlan.hall_length` scales the door-to-door length of every ordinary corridor, and at 1 nothing changes.

## Done when
- [ ] `hall_length` on `ZonePlan` (clamped, default 1, dropped from the dict at 1) and on
      `ZoneSpec` (written only when not 1), carried through the pipeline to every layout.
- [ ] Over seeds 2000–2039 per kind, door-to-door p50 at `HALL_MIN` and `HALL_MAX` is within 15%
      of `hall_length` x its value at 1 (or, outdoors, as far as the hill allows: say how far).
      Throats unchanged. Table in the commit body.
- [ ] Graph, Levels and stairs unchanged at every setting; grade within the cap.
- [ ] At 1, every zone byte-identical (the step 27 byte check plus a fortress, a cave, a city
      and an outdoor dungeon compared by archive entry).
- [ ] `tests/test_hall_length.py`: the clamp, the round trip, byte identity at 1, and the
      scaling on a few seeds (only what's warranted).
- [ ] Quick tier while working; `-m gate` and the full suite alone green at close.

## Pitfalls
- lessons-learned "Bound elevation by the corridor run" and "A ramp must be SUBDIVIDED".
- A longer run means a bigger footprint: check the outdoor dungeon still fits its hill and
  draw time at `HALL_MAX`.
- If decor, outline, gate or geometry needs a fix, stop and report.

## Result
✔ 613d384 · 4250 passed (gate 702)
