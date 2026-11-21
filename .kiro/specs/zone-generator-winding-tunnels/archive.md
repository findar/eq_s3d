# Archive — zone-generator-winding-tunnels

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

| Tasks | What landed | Commits |
|---|---|---|
| 1 | Survey of 113 tunnels in 7 stock rough caves (`scripts/tunnel_survey.py`): segment, turn, wander, width, end straight | `f4baf04`, `71fdaa2` |
| 2 | `routing.wind_leg` / `winding_legs`: a plain rough leg's centreline winds into clearance measured from the finished spec; `[tunnel]` in `rough.toml` | `c7f248c`, `f134027` |
| 9 | Cave corridors as long as stock: the cave profile's spring run at 9 corridor widths; lead fix: a stock-length leg takes one bend | `ceecc02`, `0a134ee`, `4c7d185` |
| 3 | The winding mesh: mitred floor strip, rough walls and ceiling along the centreline, welded to bends and openings; `corridor_continuity` reads the segments | `24af605`, `c65c11b` |
| 4 | Decor RoomContexts, the map line, outline and EQ map follow the tunnel; angled wall lines merge | `560ff84`, `3df464b`, `353b2a0` |
| 5 | Gate 691/696 (5 pre-existing, follow-ups), bands held; fixes: no floor-relief fan steeper than 35°, a sliver Throat read 2 u wide; goldens re-recorded for floor lift only | `1588fdd`, `fb279b8`, `8f46c1f`, `f816092`, `76a7a27` |
| 6 | ACCEPTANCE "Step 23 — Winding tunnels" (cases a–f); thorough 3949 passed, 1 pre-existing | `4308d00`, `d0a23e2` |
| 7 | First look: "looks good" (user, 2026-11-20); the flooded-room water noted as a follow-up | — |

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

6. **The cave run stays at 9 widths** (lead, at the task 6 merge). Door to door, a plain cave corridor
   now routes 194/217/233 u (p25/p50/p75; was 47/59/66), inside the stock tunnels' centreline
   p25-p75 (76-341 u, all 113) but above the plain tunnels' p75 (163 u). Matching the plain median
   (factor 5-6, ~130-150 u) leaves only 15-16% of legs bending, because a Z route splits a corridor
   into legs that each wind alone. Winding the whole route is the follow-up that would let it drop.

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
- **Wind the whole route, not each leg** (task 6, decision 6): a Z corridor's ramp sits on its short jog and never winds, and stock-length corridors split into legs too short to bend; one winding path door to door would let the cave run drop toward the plain tunnels' length.
- **Warrens never wind** (task 6: 0 of 99 rough legs over 4 builds): they keep the default run. Give them the cave's spacing or route-winding?
- **Cave rooms stand about twice as far apart** (task 6, case a: neighbour distance 225 u, was 101). Judge in 3D.
- **No decor in a winding tunnel in any build** (task 6): cave corridors carry no Props or lights; only `tests/test_winding_readers.py` covers decor on the strip.
- **A flooded room's water is a square in the middle** (user, at the step 23 first look): `semantics._add_room_region` floods a `flooded_gallery` or `sump` with a box 0.76 of the footprint, centred, so a cave room's irregular floor shows one square pool. The water should fill the room's floor outline up to a water line.
