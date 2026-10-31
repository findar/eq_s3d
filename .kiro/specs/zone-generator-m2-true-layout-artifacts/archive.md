# Archive — zone-generator-m2-true-layout-artifacts

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

Nothing yet. Rows are added at the close step (task 13).

## Decisions

The design's "Decisions" section (1–13) stands. The user answered its open
questions on 2026-10-30:

- **Open room walls (design Open question 2):** fixed inside step 1b, as task 2
  (walls beside and above every doorway), before the outline is checked on box
  builds. It changes box TER bytes for every seed with a corridor, not the
  layout.
- **In-client `.txt` check (Open question 1):** 1b closes with the grounding
  test plus the overlay script (task 10). The in-client half of the exit
  criterion moves to M6's in-engine smoke load.
- **Wilderness map content (Open question 4):** accepted as the terrain border
  plus slope breaks over 40°. Contour or path lines are a possible later
  requirement, not 1b.
- **Boss label text (Open question 5):** every climax label reads `Boss` until
  M3 adds a name field.
- **Umbrella wording (Open question 3):** the refinements and superseded
  details are recorded in the umbrella spec at the close step (task 13).
