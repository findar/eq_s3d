# 2 — Same seed, same build

Index entry: `tasks.md` task 2. Requirements 3, 4.

## Goal
Building zone B after zone A in the same process gives the same bytes as building B alone.

## Done when
- [x] Reproduced: the step 31 task 14 case (a race-less classic Districts zone differs in two decor entries and its `.zone.json` after another zone was built first), plus a search over a few zone pairs for others.
- [x] The leaked state named (file, name) and fixed so every build starts clean; no cache dropped that buys real time without saying what it costs.
- [x] A test that builds A then B in one process and compares B with B built in a fresh process (bytes without the `.eqg` time footer).
- [x] Zones built alone byte-identical to master (each in its own process); any change named.
- [x] Quick tier; full suite alone at close.

## Pitfalls
- Lessons-learned: two `.eqg` writes are never byte-identical (compare `bytes[:-4]`).
- If the fix needs a file outside Owns, stop and report.

## Result
✔ 6781622 · quick 3209 passed; full 4414 passed, 11 skipped, 2 failed (eqmap deadline flake, passes alone; decor_controls '>prop' legend, fails on master cab41dd too)
