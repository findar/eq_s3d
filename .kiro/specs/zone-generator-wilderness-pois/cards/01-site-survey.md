# 1 — Measure the stock Sites

Index entry: `tasks.md` task 1. Requirements 1.

## Goal
`scripts/site_survey.py`, from the design's finding 1: cluster each Classic outdoor zone's non-tree placed objects into Sites and report, per zone, Sites per 1e6 u² of walkable ground, Structures per Site, Site radius, spacing, distance to Spawn, zonelines and water, and slope under each Site. Measure the common Structure models from `<zone>_obj.s3d`: triangles, footprint, height, collidable share, walk-in or not. Plot each zone's Sites to check the clustering by eye. Measures importable, for task 11.

## Done when
- [x] The script prints both tables.
      → verify: `python scripts/site_survey.py --eq-path F:\everquest_rof2`
- [x] Finding 1 has the final tables, what the plots changed, and bands for Sites per area, Structures per Site and spacing.
- [x] It says what it can't see (Sites in the terrain mesh, objects it can't name).

## Pitfalls
Reuse `room_feature_survey.placed_objects` and `outdoor_dungeon_survey.load_mesh`. Tree names are matched by pattern; check the leftovers by hand. No tests: a script that writes a finding, apart from what task 11 imports.

## Result
✔ 73929ec · 1951 passed (1 timing test failed under load)
