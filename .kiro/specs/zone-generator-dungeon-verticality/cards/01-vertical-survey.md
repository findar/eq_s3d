# 1 — Measure the stock vertical anatomy

Index entry: `tasks.md` task 1. Requirements 1. Design "Research findings" 7.

## Goal
`scripts/dungeon_vertical_survey.py`: walk each stock dungeon step 6's survey kept (plus blackburrow, runnyeye, guktop, gukbottom, unrest) and report its vertical anatomy. The table and the numbers later tasks need go into design finding 7.

## Done when
- [ ] Per zone: vertical span (p10–p90 of walked floor height), level count (height clusters holding at least a set share of floor area; print the share used), Stacked_Share (floor area with another walked floor above it), level-to-level height, and the steepest connector chains (rise, run, riser and tread where the treads are distinct faces).
      → verify: `python scripts/dungeon_vertical_survey.py --eq-path F:\everquest_rof2`
- [ ] Each zone's levels checked by eye on a side-view plot (height against one plan axis) rendered to PNG; zones that come out wrong are named and left out.
- [ ] Design finding 7 has the table, the bands for Req 6 (Stacked_Share, level count, span), and starting values for the Level_Height, Slab, Riser_Cap and tread depth.

## Pitfalls
- Reuse step 6's survey walk (`scripts/dungeon_topology_survey.py`): it keeps only floor-wound WLD faces, because `build_walk_surface` takes ceilings as floor (step 6 `archive.md` "Follow-ups").
- Water and lava aren't floor: Guk's flooded halls dropped out of step 6's survey for this reason; say how they affect each zone.
- No tests: a script that writes a finding.

## Result
