# 2 — Ground the resize ops

Index entry: `tasks.md` task 2. Amendment A3, Requirement 2.7. Design "Resize".

## Goal
Decide whether one room can be resized from the saved spec alone, with its outline, features and
touching corridors redrawn and every other room's and corridor's triangles kept (umbrella
19.2). Read the code; try it in a scratch script on 3 saved Graph and classic dungeon specs.

## Done when
- [ ] `archive.md` decision 6 says yes or no in two or three lines, naming the functions to call
      (or what blocks it). → verify: `git show HEAD -- .kiro/specs/zone-generator-edits/archive.md`
- [ ] `cards/07-resize.md` is rewritten: if yes, a Goal, "Done when" (with commands) and the
      Owns line for `tasks.md` task 7; if no, a Goal of keeping the resize ops "not yet
      supported" with a test that says so. → verify: the same command, on the card.
- [ ] The commit body gives the measurements (which seeds, which rooms, triangles kept or not).

## Pitfalls
Elevation is relaxed over the whole room graph (lessons-learned "Bound elevation by the
corridor run"): a taller or wider room can move other rooms' floors. Same-axis corridors are
Z-routes (lessons-learned). No production code in this task.

## Result
