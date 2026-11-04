# 12 — Gate sweep on built zones

Index entry: `tasks.md` task 12. Requirements 8. Design G12.

## Goal
Build graph dungeons and outdoor dungeons across both sets, themes and seeds, run the walkability gate on each, and fix the root cause of anything that fails.

## Done when
- [x] A slow test builds graph zones over a fixed seed list (dungeon: each set, plain and two themes including temple; outdoor dungeon: `classic_eq`) and asserts each passes the gate on the first attempt or within the retry budget, printing the first-attempt pass rate.
- [x] The first-attempt pass rate is no worse than classic's on the same seeds (both in the commit body).
- [x] Same inputs give the same `.eqg` contents.
      → verify: `python -m pytest tests/test_graph_layout_build.py -q`

## Pitfalls
- project.md: a walkability failure is usually a real geometry or graph bug. Fix it in the rules or placement, not by loosening the gate.
- lessons-learned "Automated structural tests can pass while the 3D viewer shows it's broken": this sweep is necessary, not sufficient; task 13 looks.

## Result
✔ 22a8e1c · 1210 passed
