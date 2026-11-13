# 1 — Stage timings and the suite baseline

Index entry: `tasks.md` task 1. Requirement 7.5. Design findings 1 and 2.

## Goal
Measure what this step is meant to speed up, on an idle machine, so task 13 has a yardstick. `scripts/stage_timings.py` times each stage of a build for pinned seeds per zone type (dungeon, city, wilderness, outdoor dungeon), cold and warm: World (landscape), plan (`plan_to_spec`), and inside the build geometry, Sites, trees, RoomContexts, decor and pack; then the gate. It times today's functions and names each row by the stage it becomes, so the same script reads the new stages later. Replace the design's contended numbers (findings 1 and 2) with idle ones, and confirm or revise finding 2's targets.

## Done when
- [x] The script prints a per-stage table, cold and warm, for the four zone types.
      → verify: `python scripts/stage_timings.py --seeds 1-5`
- [x] Finding 2 holds the full and fast suites' wall times and the 30 slowest tests with their files, from an idle machine, and the two targets.
      → verify: `EQ_PATH='F:\everquest_rof2' python -m pytest tests/ -q --durations=30 -p no:cacheprovider` and the same with `-m "not slow"`
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
Other agents running skew every number (the design's were taken beside other work); say in the commit body what else was running. Decor needs `EQ_PATH`; cold numbers include loading the catalogue and importing models. Don't commit while the suite runs (a server-staleness test notices).

## Result
✔ 4ae52bd · 2403 passed
