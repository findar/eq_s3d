# Archive — zone-generator-dungeon-verticality

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

Nothing yet. Rows are added at the close step (task 15).

## Decisions

The design's "Decisions" section (1–5) stands. The user took the
recommended answer to all five open questions on 2026-11-04 ("Do
recommended on all and continue"):

- **Connectors (Open question 1):** staircases (straight and switchback) in
  this step; bridges as a later task in the step (task 11) after the first
  look at the stairs; one-way drops out.
- **Stair collision (Open question 2):** real treads and risers are both the
  look and the collision (risers ≤ 2.5 u, which the walk agent and the client
  climb).
- **What drives stacking (Open question 3):** the rules' vertical relations,
  scaled by the existing Verticality control (`flat` / `moderate` /
  `dramatic`); no Levels control.
- **Outdoor dungeons (Open question 4):** multi-level, the floor limit
  following Verticality, at most the Levels the hill holds.
- **Direction (Open question 5):** up and down from the entrance (towers and
  cellars both).

- **What the gate calls walkable (task 2, 2026-11-04):** a stair fails on a riser over the 3 u step-up, a tread under `AgentModel.min_tread` (2 u, the seam tolerance), headroom under the 6 u player height, or a gap at a landing; a corridor through a room's air at least 6 u clear of its floor and ceiling is a bridge, failing on a gap at an end or in the deck, or a deck too steep. `classify_corridor` (from the spec) and `check_connector` (walking the built mesh) name the same classes; `corridor_continuity` runs the mesh check on every stair and bridge. Room reachability still uses the face flood, so a stair with a too-short tread fails its corridor verdict, not its rooms.

## Follow-ups

None yet. Carried in from earlier steps and relevant here:

- **Big-race outdoor dungeons never plan** (step 5): rooms taller than the
  hill; task 7 measures whether a deeper floor limit fixes it.
- **The walk surface takes ceilings as floor** (step 6 task 1): matters more
  once floors stack; task 1's survey keeps only floor-wound faces, and task 5
  makes the gate's room-face test pick a room's own floor.
