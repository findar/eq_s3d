# 1 — Measure the stock dungeon topology

Index entry: `tasks.md` task 1. Requirements 1. Design "Research findings" 3.

## Goal
`scripts/dungeon_topology_survey.py`: walk each listed classic dungeon's WLD floor, split it into chambers and passages by floor width, and report each zone's room graph shape. The table goes into design finding 3.

## Done when
- [ ] The script prints, per zone in design finding 3: chamber count, degree histogram, cycle rank, dead-end share, deep-end distance (longest shortest path from the entry chamber over the chamber count).
      → verify: `python scripts/dungeon_topology_survey.py --eq-path F:\everquest_rof2`
- [ ] Each zone's chamber graph checked by eye against its EQ map file (`F:\everquest_rof2\maps\<zone>.txt`, drawn with `scripts/eqmap_preview.py`); zones that come out wrong are named in the finding and left out of the bands.
- [ ] Design finding 3 has the table and the bands task 4 uses (dead-end share, cycle rank per room, deep-end distance: p10 to p90 over the zones kept).

## Pitfalls
- Reuse `analyzer.traverse.build_walk_surface` and the step 5 survey's approach (`scripts/outdoor_dungeon_survey.py`): walk the largest walkable network, not every face.
- Floor width is the distance to the walk surface's boundary edge on a raster; chambers are the wide components, passages the narrow ones joining them. Pick the width threshold from the corridor widths `scripts/measure_corridors.py` measures, and print it.
- No tests: it's a script that writes a finding.

## Result
