# 1 — Measure the stock dungeon topology

Index entry: `tasks.md` task 1. Requirements 1. Design "Research findings" 5.

## Goal
`scripts/dungeon_topology_survey.py`: walk each stock dungeon in design finding 5, split its floor into chambers and passages by floor width, and report its room graph's shape. The table goes into finding 5, the warren-like zones apart.

## Done when
- [ ] The script prints, per zone: chamber count, chamber sizes (p10 / p50 / p90 side), degree histogram, cycle rank, dead-end share, deep-end distance.
      → verify: `python scripts/dungeon_topology_survey.py --eq-path F:\everquest_rof2`
- [ ] Each zone's chamber graph checked by eye against its EQ map file (`F:\everquest_rof2\maps\<zone>.txt`, drawn with `scripts/eqmap_preview.py`); zones that come out wrong are named in the finding and left out of the bands.
- [ ] Design finding 5 has the table and two sets of bands (classic, warren-like) for tasks 5 and 6: dead-end share, cycle rank per room, deep-end distance, chamber size mix as Size_Class shares; and the direction `warren` differs in.

## Pitfalls
- Reuse `analyzer.traverse.build_walk_surface` and the step 5 survey's approach (`scripts/outdoor_dungeon_survey.py`): walk the largest walkable network, not every face.
- Floor width is the distance to the walk surface's boundary on a raster; chambers are the wide components, passages the narrow ones joining them. Pick the threshold from the corridor widths `scripts/measure_corridors.py` measures, and print it.
- No tests: it's a script that writes a finding.

## Result
