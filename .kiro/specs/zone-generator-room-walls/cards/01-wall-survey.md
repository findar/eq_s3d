# 1 — Measure the stock walls

Index entry: `tasks.md` task 1. Requirements 1.

## Goal
`scripts/wall_survey.py`, from the design's finding 1 numbers: per zone Axis_Share, plumb share, median edge, straight wall runs (length p10/p50/p90), corners per room, Fill, floor and ceiling Relief and flat shares. Measures importable, because task 10 runs them on built zones. Plots to sort the zones into `rough`, `hewn` and `built`. Finding 1 gets the final table, labels, bands and each style's Cell size.

## Done when
- [ ] The script prints the table.
      → verify: `python scripts/wall_survey.py --eq-path F:\everquest_rof2`
- [ ] Each zone has a style or is named and left out, on the evidence of its plots; finding 1 is updated and says where it changed the first reading.
- [ ] Proposed bands per style (Axis_Share, plumb, Fill, Relief, median edge) and Cell sizes in H.

## Pitfalls
Reuse step 6's floor walk and chamber split and step 7's `load_faces`. WLD floors wind down (`floors_up=False`). No tests: a script that writes a finding, apart from what task 10 imports.

## Result
