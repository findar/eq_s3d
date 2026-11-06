# Archive — zone-generator-dungeon-verticality

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

Signed off 2026-11-06; master `406292e`. Suite 1430 (fast and thorough both
green). Graph dungeons and outdoor dungeons have Levels; every room-graph build
is at stock scale.

| Task | What landed |
|------|-------------|
| 1 | Stock vertical survey (`scripts/dungeon_vertical_survey.py`), design finding 7: stacked share 0.02–0.36, 2–4 levels, span 1.1–3.7 gaps |
| 2 | The walk gate learns stairs and bridges before anything builds them: `classify_corridor`, `check_connector`, each failure named |
| 3 | Planned stairs (`steps = AUTO_STAIRS`, `stair_layout`): risers up to 2 u, treads 3 u, switchbacks with flush landings, U-routes |
| 4 | Levels from the rules' relations, `may_overlap_in_plan` opened, the Slab (14 u) |
| 5 | The shared layout steps judge rooms and corridors in 3D on stacked builds; Classic byte-identical |
| 6 | Vertical rules in the shipped sets; Verticality flat / moderate / dramatic sets stacking and vertical-rule weights |
| 7 | Outdoor dungeons go down into the hill, the Tunnel entering the top Level |
| 8 | Sidecar `levels`, `connectors`, `stacked_share`; a map band per stacked Level |
| 9 | Gate sweep on built zones: stacked builds no worse than flat first try, reproducible |
| 10 | First look signed off (no findings) |
| 11 | Bridges: a railed deck over a lower room through a shaft in its ceiling, `bridge_hall` rule |
| 12 | Third-room stair clips gone, bridges labelled in the sidecar, warren keeps its loops; the gate fails a corridor walled through a room |
| 13 | `docs/ACCEPTANCE.md` "Step 7", the build-time test (14 rooms: flat 0.3 s, dramatic 2.4 s) |
| 14 | Human acceptance pass signed off |
| 16 | Race body heights from `racedata.txt` and stock room sizes, design finding 8 |
| 17 | Stock scale for both engines: rooms 2.5–10 H tall and 8–20 H across, corridors 3 H wide and 2.5 H tall; `dragon` joins the races |
| 18 | The gate counts only up-wound faces as floor, so ceilings stop passing as walkable |
| 19 | Outdoor corridors and stairs stay inside the bowl |

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

- **Race bands in code (task 17, 2026-11-04):** `semantics.RACE_HEIGHT` (H) replaces `RACE_SCALE`; every room-graph room (both engines, city, outdoor dungeon) is clamped into [2.5 H, 10 H] tall and [8 H, 20 H] a side; Size_Class picks a geometric point (tiny 0 ... huge 1), the Size control shifts it (-0.125 / 0 / +0.125 / +0.25); corridors 3 H x 2.5 H; rises in H (moderate 1-3.5, dramatic 2.5-7.5); `race_scale` = H / 6 for rule conditions. The measured zone floor area no longer sizes rooms. Outdoor dungeons align the entrance wall to the terrain grid; ogres now plan under the hill, giants and dragons still drop rooms (task 7).

- **Outdoor dungeons descend (task 7, 2026-11-04):** under a hill, Levels only go down from the entrance, so the Tunnel always enters the top Level (an all-up graph is turned upside down; towers become cellars). The general dungeon decision (up and down) stands for dungeons. The floor limit is 150 u under the Entrance plus one race Level height per extra Level (moderate 1, dramatic 2); `flat` and the classic layout stay one Level. Step 5's cases a-g build on two Levels at moderate and dramatic.

- **Bridges (task 11, 2026-11-05):** a Bridge is a same-Level corridor flagged `CorridorSpec.bridge` = the lower room it crosses (omitted from JSON when unset). The deck runs at the upper Level OVER the lower room's ceiling (the stacked Slab always leaves room; the lower room's height is never changed); the ceiling is cut in a slot under the deck plus a half-width either side, walled as a shaft from the lower ceiling to the corridor's ceiling; rails 0.24 x corridor height (0.6 H), at least 3.5 u (over the step-up); deck 2 u thick, at least as long as it is wide, on one straight leg (`geometry.bridge_layout`, shared by builder, layout and gate). Job B bridges every same-Level corridor that can take one (straightening its doors onto one line if needed), one per lower room, shaft clear of every other room and corridor; no rng draws. The `bridge` edge tag (classic_eq `bridge_hall`, left out with stacking off) makes the placement put the far gallery on the near one's wall facing the hall. The gate counts a flagged room as bridged when the deck is a player height over its floor.

- **Stacked Job B keeps edges (task 12, 2026-11-05):** a route a third room blocks after its one split is dropped (a loop edge) or swapped (a tree edge); stair doors may stand along the wall (`U_DOOR_STOPS`); a dropped edge is restored once it clears every room and corridor; corridors are re-judged after a relax (`SETTLE_PASSES`). Stacked graph builds only; classic and flat are unchanged. The gate now fails any walled crossing, even when the flood finds a way round. Built warren loops 0.194 per room, fidelity 0.93-0.96.

## Follow-ups

- **Stock stacking is low rooms over low rooms** (task 1): where stock floors stack they are only ~28 u apart (14 u of headroom), because corridors and low rooms stack, not halls. Our rooms are about four times taller, so a Level is ~135 u. A low stacking room type (a crawlway, a cellar, a gallery) would bring built dungeons closer to stock.

- **Cities now share dungeon geometry** (task 17): with the zone-type floor area no longer sizing rooms, a plain city and a plain classic dungeon on the same seed build the same rooms (materials and lights differ). Cities need their own sizing or layout (streets, plazas) to read as cities.
- **Dragon stairs are long** (task 17): risers stay 2 u, so a dragon's ~250 u level height is a very long switchback. A race-scaled riser or ramp-and-stair mix for big races is worth a look at the first look.
- **Dramatic is only somewhat more than Moderate** (task 13): 2.70 Levels against 2.33 at 12 rooms on `classic_eq`, and 19 of 60 seeds stack the same at both. It's a weight on the vertical rules, so a stronger Dramatic would need more of them or a higher weight.
- **Outdoor dungeons rarely reach three Levels** (task 13): at Dramatic, of 30 seeds each, 0 at 5 rooms, 1 at 8, 4 at 12. The hill's depth limits them. The requirement (more than one Level) holds.
- **Height bands overlap at the top** (task 17): a human's tallest hall (60 u) is taller than a dragon's lowest room (52.5 u); footprints still separate (120 < 168 u).

- **Giant and dragon outdoor dungeons drop rooms** (task 7): they always plan now, but giants keep every room in only 4-6 of 20 seeds and dragons 10-14 of 20 (5 rooms). A host sized to the race (a taller hill or a pit) would let them fit whole.

Carried in from earlier steps and relevant here:

- **Big-race outdoor dungeons never plan** (step 5): resolved for ogres by stock scale (task 17); giants and dragons now plan with rooms dropped (task 7).
- **The walk surface takes ceilings as floor** (step 6 task 1): matters more
  once floors stack; task 1's survey keeps only floor-wound faces, and task 5
  makes the gate's room-face test pick a room's own floor. Done by task 18.
