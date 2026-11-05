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

- **Numbers from the survey (task 1, 2026-11-04):** Slab 14 u (stock median; band 11-39); Level_Height = the tallest overlapped lower room + the Slab (~135 u for dungeon rooms, ~94 u for outdoor-dungeon rooms); Riser_Cap 2.0 u (stock risers 1.0 u median, 2.0 u p90); tread 3.0 u (grade 0.67, 34 deg, the stock median). Req 6 bands over nine zones: Stacked_Share 0.02-0.36, 2-4 levels, span 1.1-3.7 floor-to-floor gaps. Unrest is excluded (its yard swamps the floor).

- **Rooms sized for their builders (user, 2026-11-04):** "Our room height should end up confirming to whatever the related race size is to some degree. An ogre would never have small rooms ... baseline overall minimum height per type and then also decide on maximums ... Dragons need lots of space but it would be unlikely for a human to create a dungeon with the same sized rooms." Added as Requirement 10 and tasks 16 (measure race body heights and stock rooms) and 17 (race bands replace the race multiplier, both engines, `dragon` added). Outdoor dungeons (task 7) and the gate sweep (task 9) wait for it.

- **Stacked layouts (task 5, 2026-11-04):** floors at Level x level height with variation kept within +-14 u (`LEVEL_VARIATION` 28 u = two Slabs); a stair between stacked rooms is usually a U-route (both doors on walls facing the same way, the middle leg one corridor past both rooms carrying the stair; `CorridorSpec.side`, omitted from JSON when unset); stairwells are a clearance check against every room, not a placed room; a stacked edge is split at most once and never dropped for running out of splits. Stacked builds keep 0.85 of their edges (0.93 unstacked) because the gate reads ceilings as floor (task 18).

- **The gate stands on floors only (task 18, 2026-11-04):** `build_walk_surface` takes a face as standable only when wound up (`floors_up=False` for WLD-wound meshes, floors down); a ceiling is never floor. A corridor over or under a crossed room with the Slab between is not a crossing on any spec (`is_stacked_build` is gone). Tubes on a stacked build keep the Slab between them (top of the lower to the upper floor). Stacked Edge_Fidelity on task 5's sweep: 0.85 -> 0.92 (0.93 unstacked).

- **Stock scale (user, 2026-11-04):** "Stock scale". Task 16 found our rooms are 3-4 times stock size (human dungeon rooms 121 u tall and ~340 u across; stock human rooms 15-60 u tall and 48-120 u across). Every dungeon moves to the race bands, rooms and corridors both, Classic included: room height 2.5-10 H, footprint side 8-20 H, H from the client's `racedata.txt` (human 6, ogre 9, giant 22, dragon 21). Task 17.

- **Verticality drives stacking (task 6, 2026-11-04):** `flat` = stacking off and no vertical rules; `moderate` = stacking on, weights as written; `dramatic` = vertical weights x2 (`GraphEngine` vertical-rule hook). `passage` (classic_eq) and `tunnel` (warren) stay real Level drops. Outdoor dungeons keep the vertical rules at weight 1 as ramp hints, stacking off, until task 7. Built means at moderate: Stacked_Share 0.08-0.10, 2.1-2.4 Levels, span 1.2-1.5 gaps (inside the survey bands); stacked fidelity 0.92-0.96.

## Follow-ups

- **Stock stacking is low rooms over low rooms** (task 1): where stock floors stack they are only ~28 u apart (14 u of headroom), because corridors and low rooms stack, not halls. Our rooms are about four times taller, so a Level is ~135 u. A low stacking room type (a crawlway, a cellar, a gallery) would bring built dungeons closer to stock.

- **Stacked warren loops** (task 6): 0.184 cycles per room against step 6's 0.19 floor (xfail): stacked warrens lose ~11% of their edges between Levels against 6% within one. For task 12's tuning.

Carried in from earlier steps and relevant here:

- **Big-race outdoor dungeons never plan** (step 5): rooms taller than the
  hill; task 7 measures whether a deeper floor limit fixes it.
- **The walk surface takes ceilings as floor** (step 6 task 1): matters more
  once floors stack; task 1's survey keeps only floor-wound faces, and task 5
  makes the gate's room-face test pick a room's own floor. Done by task 18.
