# Archive — zone-generator-winding-tunnels

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

Decided 2026-11-20 by the lead after the user's "Pick the step yourself". Multi-zone worlds wait
on the user's design review. The user confirms at the first look (task 7).

1. **Step 23 is winding tunnels.** Angled corridors have been "wanted" since M1, and a cave's
   corridors are its last straight boxes. This is the first piece of M5's "winding tunnels",
   built on the Box backend. M5's other parts, rounded rooms and the re-voxelise vs deform
   decision, wait.
2. **The layout is untouched** (A1, A2). Winding happens at dressing time, only into clearance
   measured from the finished spec, so routes, conflicts, the Envelope and Levels are the same
   and only rough corridors' meshes change.
3. **Stock tunnels wind like this** (task 1, `scripts/tunnel_survey.py`, 113 tunnels in 7 rough caves,
   p10/p50/p90): segment between turns 16/40/72 u, turn 24/48/87 deg, wander 0.07/0.25/1.50 of span,
   width 12/20/31 u, end straight 20/37/84 u. Proposed `[tunnel]`: `segment = [16, 72]`,
   `max_turn = 85`, `wander = 0.25`, `end = 20`.
4. **`[tunnel]` takes the plain tunnels' numbers** (lead, at the task 1 merge): `segment = [20, 72]`,
   `max_turn = 60`, `wander = 0.2`, `end = 20`. Junction legs (70 of 113) bend round junctions and push
   the turn p90 to 87; plain tunnels turn 32/52/78 and wander 0.03/0.17/0.58, and a generated corridor
   is a plain tunnel. A gentler max turn also keeps the strip's mitres short.
5. **Cave corridors get stock length** (lead, at the task 2 merge; amends A1/A2): with the layout
   untouched no cave leg wound (0 of 146: median 21 u, a turn needs ~80 u). Edges rest at 2 corridor
   widths; stock tunnels are far longer. The cave profile gets its own spring run from the survey's
   tunnel span (task 9); every other zone's layout stays as it is.

## Follow-ups

Gate failures from task 5's cave and warren sweep (`sweep_themed_navigability --only cave warren
--layouts classic graph --verticality flat moderate dramatic --rooms 2-30 --seeds 2 --seed 23`).
Each also fails at b2db7b4, so step 23 didn't cause any of them. Five of 696 builds:

- Decor alley between Props: `Room.spaced` shuts a seam with the hull of both plans, so a 4.6 u
  alley between a shelf and a rock never counts as a pocket. warren classic flat 23 rooms, seed
  490919952, room_3 (footprint_cut 88 u^2).
- Decor Prop-to-wall gap: only Prop-to-Prop gaps keep `BLOCKING_GAP`; a boulder 3.85 u off a wall
  walls the strip off. warren classic flat 26 rooms, seed 1205085953, room_19 (footprint_cut 72 u^2).
- Door jambs missing from decor's room data: a jamb plate standing 2 u into the room is in no
  RoomContext field, and a rock 4.7 u off it shuts the strip. cave classic moderate 8 rooms, seed
  1728424002, room_2 (footprint_cut 80 u^2).
- Outline floor behind a wall slit: the outline reaches floor through a slit no body fits,
  and `check_features` reads it walled off; no Feature is near it. cave graph flat 29 rooms, seed
  1259910114, room_25 (floor walled off at (178.5, -621.5)).
- Decor clear width: decor's wide reading lets a rock narrow door E's way that the gate measures
  under 8 u; not diagnosed. warren graph moderate 25 rooms, seed 616736071, room_23 (throat_narrow).
