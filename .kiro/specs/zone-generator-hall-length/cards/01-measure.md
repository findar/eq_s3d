# 1 — Measure stock hall lengths and the range

Index entry: `tasks.md` task 1. Requirements 1–2, design "Measuring".

## Goal
Know how long stock halls run per kind, how far that varies zone to zone, and which knob in
each of our layouts moves door-to-door length, so task 2 can set `HALL_MIN`/`HALL_MAX` and
scale the right thing.

## Done when
- [ ] `python scripts/stock_room_shapes.py --eq-path F:\everquest_rof2 --halls` prints passage
      length door to door per zone and per kind (p10/p50/p90, and the spread of zone medians).
- [ ] `python scripts/grid_score.py` gives ours at 1 per kind (built, cave, city, outdoor) on
      seeds 2000–2039, and one run each with the Graph run factor, the classic gap/spread and
      the outdoor spacing scaled x0.5 and x2 (monkeypatched from a scratch script, not
      committed): door-to-door p50 and how close it tracks the scale.
- [ ] Decision in `archive.md`: `HALL_MIN`, `HALL_MAX`, and per layout the knob task 2 scales
      (one or two lines; tables in the commit body).

## Pitfalls
- The raster can't see passages narrower than its cells; say what it misses.
- No generator code.

## Result
✔ f3016e8 · 2961 passed (quick)
