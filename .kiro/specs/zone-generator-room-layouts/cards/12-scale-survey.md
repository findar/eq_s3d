# 12 — Measure how stock rooms change

Index entry: `tasks.md` task 12. Requirements 11.5, 14.

## Goal
Find out how finish changes from room to room in stock, and what stands where it changes. This sets the default coherence and Req 11.5's band.

## Done when
- [x] Per chamber in step 8's kept zones: a finish estimate from `scripts/wall_survey.py`'s measures, and the main wall material.
- [x] Between neighbouring chambers: how far finish drifts, how often it breaks, whether breaks come in wings. How often the material changes at a passage, and whether the passage narrows there. `python scripts/room_scale_survey.py` prints it.
- [x] The table, the band and what it can't see (doors are server records, not in the files) go in design.md as finding 3, and the default coherence in `archive.md` Decisions.

## Pitfalls
Same-zone rooms can be in different style by accident of the split; look at plots before trusting a number (the first feature survey over-counted three times over).

## Result
✔ 8a85479 · script only, no tests
