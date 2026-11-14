# Archive — zone-generator-site-sockets

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

Decided 2026-11-14. The user said "Pick one and go" (choosing step 13 and its answers was
delegated); the lead took each recommendation after review.

1. **Clustering comes from the World offering points in groups** (copying stock's hamlets),
   not a "near another Site" preference.
2. **Reroll rooms moves Sites** among the World's spare points (step 12's "new Sites on the
   same ground" holds).
3. **An outdoor dungeon keeps its own rooms, corridors, Tunnel and Apron clear** (+16 u), not
   the whole hill: step 10's P8 is reworded from "Host_Hill clear" to "the dungeon under it
   clear". A camp then fits on 39 of 39 seeds.
4. **An outdoor dungeon gets at least one Site at Normal and Dense**; no fixed point by the
   approach (the World doesn't know the Apron).
5. **The recipes' `spacing` field is retired.**
6. **Clustering targets are per biome in `biomes.toml`** (plains bands now; other biomes keep
   the all-zone band until measured).
7. **The map shows every point**, used ones filled, unused hollow; `mapview.py` writes its
   world-to-pixel mapping on the SVG.
8. **A Site-caused gate failure is not a stage reroll in this step** (`pipeline.py` untouched).

## Follow-ups

Carried in from step 10 (`zone-generator-wilderness-pois/archive.md` "Follow-ups") by step 12,
because point Site Sockets are where they get fixed; this step closes them:

- **Sites spread at random where stock plains cluster them**: R pooled 1.45 (step 10 task 11),
  plains 0.50–0.95. Design findings 1 and 2; tasks 3–6 and 11.
- **Outdoor dungeons get Sites on only some seeds**: 8 of 39 at Normal (design finding 3).
  Task 7.

Carried in from step 12 (`zone-generator-world-sockets/archive.md` "Follow-ups"), because this
step works on the same code:

- **`outdoor_dungeon.keep_clear_shapes` duplicates `stages.entrance_keep_clear`**: task 7
  deletes it when the Kept_Clear changes.
- **The page's Socket markers infer the map's world-to-pixel mapping** (`web/src/sockets.ts`):
  task 9 has `mapview.py` write the frame on the SVG.

Carried in from step 10 and touched, not fixed:

- **A farmstead often loses its barn** (dropped in its Site_Clear on 5 of 20 seeds at Normal):
  points carry a Free radius, so a farmstead goes only where 100 u of ground is free, but its
  arrangement is unchanged. Task 5's kind counts will show whether it gets rarer.
- **Shoreline below water level on some seeds** (`synth.py`): points stand on dry, playable
  ground only, as Sites do now.

Recorded for later biomes (design finding 1): swamps and snow cluster as plains do; hills are
near random; deserts and forests space their Sites out (R_CE 1.04–1.73, no Site within 300 u in
five of seven zones). Each biome's `groups` block comes with its Site rules.
