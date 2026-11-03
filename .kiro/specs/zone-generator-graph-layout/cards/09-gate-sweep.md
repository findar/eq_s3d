# 9 — Gate sweep on built zones

Index entry: `tasks.md` task 9. Requirements 7. Design G9.

## Goal
Build grown dungeons and outdoor dungeons across profiles, themes and seeds, run the walkability gate on each, and fix the root cause of anything that fails.

## Done when
- [ ] A slow test builds grown zones over a fixed seed list per profile (dungeon: plain and two themes; outdoor dungeon: plain) and asserts each passes the gate on the first attempt or within the retry budget, with the first-attempt pass rate printed.
- [ ] The first-attempt pass rate is no worse than classic's on the same seeds (both in the commit body).
- [ ] Same inputs give the same `.eqg` contents (G9).
      → verify: `python -m pytest tests/test_grown_layout_build.py -q`

## Pitfalls
- project.md: a walkability failure is usually a real geometry or graph bug. Fix it in the embedding or rules, not by loosening the gate.
- lessons-learned "Automated structural tests can pass while the 3D viewer shows it's broken": this sweep is necessary, not sufficient; task 10 looks.

## Result
