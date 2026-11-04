# 9 — Gate sweep on built multi-level zones

Index entry: `tasks.md` task 9. Requirements 9. Design V10.

## Goal
Build multi-level graph dungeons and outdoor dungeons across both rule sets, themes, races and the three Verticality settings; run the walk gate on each; fix the root cause of anything that fails.

## Done when
- [ ] A slow test sweeps built zones (dungeon: both sets × plain and two themes × moderate and dramatic; outdoor dungeon: moderate) and asserts each passes the gate first try or within the retry budget, printing the first-try rate.
- [ ] The first-try rate is no worse than step 6's graph rate on the same seeds (both in the commit body); same inputs give the same `.eqg`.
      → verify: `python -m pytest tests/test_vertical_build.py -q`

## Pitfalls
- project.md: a walkability failure is usually a real geometry or graph bug; fix it in the rules or placement, not the gate. If the cause is in `generators/layout.py` or `generators/geometry.py`, stop and report (not in Owns).
- Step 6 task 12 found step 5 bugs this way; expect the same.

## Result
