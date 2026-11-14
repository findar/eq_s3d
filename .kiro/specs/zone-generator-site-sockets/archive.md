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
9. **Kind first, then the point** (lead, 2026-11-14, from task 11's measurements). Drawing the
   kind by weight x likes at each point drifted the mix off stock (wilderness farmsteads 13 % ->
   5 %, outdoor dungeons 51 % ruins). The kind is drawn by weight alone, then stood on the next
   fitting point in the Group order, likes choosing within the Group. Req 3.2 revised; task 16.
10. **Kind-first is judged against the weights, not stock** (lead, 2026-11-14, task 16's first
    run). Kind-first reproduces the weights (built mix within noise of them), but the weights
    themselves sit ~32 points from stock plains (farmsteads 13 % vs ~27 %, ruins 11 % vs ~1 %):
    a step 10 gap, now a follow-up. Outdoor dungeons are fit-limited (ruins expected ~36 %;
    farmsteads fit 1 of 39 seeds): gate is "largest share below task 6's 51 %". Dense clustering
    asserts the pooled measures; per-zone R (about 4 Sites a zone) is printed, not asserted.
11. **Stock clustering is held at Normal, the stock density** (lead, 2026-11-14, task 11). The
    plains bands come from stock zones at 0.3-0.5 Sites per 1e6 u², which Normal reproduces
    (0.41). Dense is denser than any stock zone, so no stock clustering figure exists for it:
    with kind-first, Dense pooled R is 1.03 (big recipes open new Groups). Dense asserts that
    Sites still group (within 300 u 33-65 %, NN p10 108-191, pooled R below the pre-points
    1.30); its R is printed. Supersedes decision 10's Dense clause.

From the tasks:

- Task 1: plains `target_nn_p10` is **[108, 191]**, not the draft's 190 (southkarana's p10 is
  191.3); `biomes.toml` holds it and task 11 reads it from there. Req 4.1 still says 190.
- Task 3: a point's `ground` also carries **`hill`** (true for a spare over the hillside
  footprint); spares share the one `n_offer` budget with the points off the hill.

## Follow-ups

Found while working this step:

- **Site weights vs stock plains** (task 16): the biome/Inhabitant weights' expected mix is ~32
  points from stock (task 11's sorting of stock Sites by their Structures): farmsteads 13 % vs
  ~27 %, ruins 11 % vs ~1 %. Retune `biomes.toml` weights against a proper stock kind survey.
- **Outdoor-dungeon points favour small recipes** (task 16): most usable points are hill points
  where only ruins and watchtowers fit (farmsteads fit on 1 of 39 seeds, huts 16). Offering
  flatter points would let bigger recipes stand.

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
