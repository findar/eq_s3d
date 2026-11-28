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

## Follow-ups
- Steps 5 and 10's surveys (`outdoor_dungeon_survey.py`, `site_survey.py`) take a zone's main ground as the largest
  network by area, which in some zones is a flat sheet under the map (steamfont z -232, fieldofbone z -279);
  task 1's script picks by face count. Step 10's site densities may be off (task 1, not checked).
- Wells: no signal (a vertical shaft can't be walked, so the survey can't see one).
