# Archive — zone-generator-outdoor-area

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

1. **Step 35 is the area layer** (the lead, 2026-11-28, on the user's "Yes, plan it" after "to be clear, we should be working top down. area map > dungeon > rooms > decor" and "i mean one zones area, so like a wilderness or outdoor dungeon. we should be generating the external area before anything we attach to it").
   The area is generated first; what attaches is fitted after. Ground textures
   ([P-5-3](../../../docs/pillars/P-5-look-and-feel/OPEN.md#p-5-3)) are left for a look step.
2. **Area defaults from the stock measure** (task 1, `scripts/stock_outdoor_area.py`; proposed, for tasks 4-6).
   Walked extent of 62 open Classic-PoP outdoor zones (water, island and covered zones left out, named
   in the output): width p10/p25/p50/p75/p90 4054/4803/7120/10451/13899 u, depth p50 5524, aspect p50 1.21,
   p90 1.96. Today's 2400 u is under every one, so a plan with no Size does not keep it.
   - *Size (wilderness)*: width small 4000-4800, medium 4800-7100, large 7100-10500, huge 10500-13900 u
     (p10-p25-p50-p75-p90); unset draws 4000-13900; depth = width / aspect, aspect drawn 1.0-2.0.
     At 150 u/cell, huge is up to 93 cells a side against today's 16: task 6 must time it.
   - *Size (outdoor dungeon's zone)*: weak signal, 5 zones (beholder, crushbone, mistmoore, unrest,
     citymist): width 793-3804, p50 1234 u, aspect 1.03-1.60. Medium keeps 1200; small 800, large 1700,
     huge 2500.
   - *Host margin*: rock interiors with a host of their own (69 of 132 in-zone; 57 sit in the zone's
     edge massif): footprint-to-host-edge p50 48 u (p10 11), host side / interior side p50 1.8, host
     height p50 283 u over the way in. Default: the host is the dungeon's footprint plus 48 u each side
     (never under 16), at least 1.8 times its side.
   - *Mouth width*: rock "mouth" ways in (200), p10/p50/p90 16/48/159 u. Default 48 u, drawn 32-96.
   - *Second kind*: cliff opening, the most frequent of the listed kinds (rock ways in: mouth 200, cliff
     opening 101, sinkhole 59, ravine 21; widest way per interior 85/46/23/9), weight about 1 in 3. Ruin
     stairs (74 of 443 built ways in, doors 369) belongs to built interiors. Well: no signal (a shaft
     can't be walked, so the survey can't see one).
3. **The lava patch is themed** (task 2, `matrix.wants_lava`). A wilderness or outdoor dungeon's interior lava
   patch is drawn only when the plan's element is `lava` (the rule planner's lava, magma, volcanic, molten,
   fire, volcano) or its dungeon theme is `lava_forge`; off otherwise. The spec's wilderness payload and the
   World's recipe carry `"lava": true` only when on, so themed zones keep their bytes.
4. **The host is sized from the plan** (task 4). Interior side = 2.5 × √rooms medium room sides of the race
   (graph layouts spread to ~31.5 H × √rooms on an unconstrained hill); host = side + 48 u each side, at least
   1.8 × side, never under the default hill; the zone grows to hold it in even 150 u cells. Task 6's size bands
   take the larger of the band and this. Giant 30 rooms reaches 7500 u, above stock's largest outdoor dungeon (3804 u).
5. **Three Levels is the dungeon layer's, not the area's** (the lead, task 4 review). With no hill at all the
   outdoor engine builds 2 Levels on 30 of 30 seeds at 5 rooms: `GraphEngine._descending` takes the first
   one-way graph and sets every room above the entrance to Level 0. Moved to P-7-19.
6. **The Mouth flares in width and height** (task 5, the lead). Tunnel at the race's corridor width (at most the
   40 u cell), flaring at most 45 degrees to the drawn width; the ceiling rises over the flare to height/width drawn
   0.25-1.97, p50 0.61 (stock rock mouths 32-96 u wide, n=74, `stock_outdoor_area.py`; cliff openings 1.65 p50, for
   task 12). Too tall to cover: halfway down, then the Tunnel's height; too wide: 0.8 narrower, then one cell.
7. **The scarp is the area's, the cliff opening the dungeon's** (task 12, the lead's option 2). The host Landform
   may carry a scarp (`Landform.scarp`), drawn on its own stream at `SCARP_SHARE` = 46/131 (decision 2's widest way
   per interior, mouth against cliff opening). The scarp is a frozen ~110 u face on the approach side, over a frozen
   level foot, with its top 10 u under the crown behind it. The dungeon cuts a cliff opening into it, else a Mouth:
   - the floor is at the foot, and the Apron digs at most 1 u;
   - height/width is drawn 0.48-4.43 (p50 1.65), capped by the face;
   - no Apron may rise to its floor or fall more than `MAX_GRADE` a cell.
   Synth tiles a 150 u matrix cell as 160 u, so the Socket reads the foot off the field (`scarp_foot`).
8. **The area's extent from the plan's Size** (task 6, the lead). An unset Size stays `""` on a wilderness or
   outdoor dungeon, and is medium on a dungeon or city.
   - *Wilderness* (`matrix.draw_zone_extent`): the width is drawn in the Size's band, and unset picks the band
     15/25/25/15. The aspect is drawn from stock's quantiles (`WILDERNESS_ASPECT_QUANTILES`, p10/p50/p90
     1.02/1.21/1.96, max 2.6).
   - *Outdoor dungeon* (`draw_outdoor_zone_extent`): the Size's side (unset picks one of four evenly) at
     stock's 5-zone aspect. Neither side is under `host_zone_size`, and both are even cells. A host past huge
     stays square.
   - Both draws count cells at the side a cell builds at (`built_cell_size`, 160 u: synth tiles a 150 u cell
     as 4 x 40 u), so the band holds the built terrain's width (`built_extent`). The zone size handed on is
     still in matrix units, so a World given an explicit size keeps its bytes.
   - The gate shares one walk surface between `check_bowl` and the Footprint checks.

## Follow-ups
- Giant and dragon cliff openings are squat (200-300 u wide, 65-86 u tall, height/width ~0.3 vs stock p10 0.48):
  the scarp's ~110 u face caps them. A scarp scaled to the race's Mouth would fix it (task 12).
- Steps 5 and 10's surveys (`outdoor_dungeon_survey.py`, `site_survey.py`) take a zone's main ground as the largest
  network by area, which in some zones is a flat sheet under the map (steamfont z -232, fieldofbone z -279);
  task 1's script picks by face count. Step 10's site densities may be off (task 1, not checked).
- Wells: no signal (a vertical shaft can't be walked, so the survey can't see one).
