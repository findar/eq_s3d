# 1 — Measure the classic outdoor-dungeon anatomy

Index entry: `tasks.md` task 1. Requirements 1.

## Goal
A survey script walks each classic outdoor dungeon's floor from its safe point and reports span, covered share, depth of covered floor below the open floor, rock cover and entrance count; the numbers go into the design's research findings.

## Done when
- [ ] `python scripts/outdoor_dungeon_survey.py --eq-path F:\everquest_rof2` reports mistmoore, blackburrow, runnyeye, unrest, highkeep and kaesora (and befallen as an all-indoor control, which must come out mostly covered).
- [ ] The design's research findings carry the table, and the defaults in Open questions 2 and Req 3–4 (size, Rock_Cover, depth) cite it.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- Walk the WLD triangles with the traversal agent's rules (slope ≤ 40°, step ≤ 3 u) from the zone's safe point; the plain overhead test is contaminated (design finding 3).
- Safe points come from the EQEmu zone table defaults; if unknown, use the lowest-ground walkable face near the zone's centre and say so.

## Result
