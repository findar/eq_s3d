# 1 — Measure what stands in stock rooms

Index entry: `tasks.md` task 1. Requirements 1.

## Goal
`scripts/room_feature_survey.py`, from the design's finding 1: per zone and style, Features per room, size, height, raised floor, and where Features stand. Separate free-standing Features from partitions, stair sides and raised floors' edges by looking at plots. Count placed objects from `<zone>_obj.s3d`'s placement data if it can be read. Measures importable, for task 11.

## Done when
- [x] The script prints the table.
      → verify: `python scripts/room_feature_survey.py --eq-path F:\everquest_rof2`
- [x] Finding 1 has the final table, what the plots changed, and bands per style and room size.
- [x] It says what it can't see, and how many placed objects each zone has if readable.

## Pitfalls
Reuse `wall_survey`'s kept zones and `measure`'s pieces. WLD floors wind down. No tests: a script that writes a finding, apart from what task 11 imports.

## Result
✔ de2a5d1 · script only, no tests
