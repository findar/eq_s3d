# 1 — Cave draw time

Index entry: `tasks.md` task 1. Requirement 1, design "Draw time".

## Goal
A 30-room cave Graph layout draws in ≤ 14 s with identical placements.

## Done when
- [ ] A timing script (in the commit body, not committed) draws cave Graph layouts at 30 rooms
      over seeds 2000–2009 and 731402518, before and after: median and max seconds in the
      commit body; median ≤ 14 s.
- [ ] The same script compares every room centre before and after: all equal (float `==`).
- [ ] The Req 6 byte check from step 27 (`tests/test_layout_engine.py tests/test_site_builds.py
      tests/test_partial_rebuild.py`) green, plus `tests/test_topology_embed.py`.
- [ ] Quick tier green; full suite alone green at close.

## Pitfalls
- Equality, not closeness: re-ordering a float sum can move a centre by 1 ulp and change a
  build. Keep summation order, or prove equality by the comparison above.
- lessons-learned "Performance": never a per-item Python loop where arrays fit.
- If a speed-up needs a placement change, stop and report.

## Result
