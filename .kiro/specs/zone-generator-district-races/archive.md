# Archive — zone-generator-district-races

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

1. **Step 31 is district races, intrusion and one-way drops** (the lead, 2026-11-26, from the
   user's ideas at the step 30 look). One spec, ordered so the one-way gate (task 2) lands
   before anything makes a drop. The bar for drops is the user's: strong connectivity (a drop
   may be the only way in, never the only way back), weighted toward flush.
2. **`MAX_DROP` 80 u, flush weight 0.9, giant hall length 3.0, intrusion links 3** (task 1): drop p90 84 u (cave 79), 11 % of passage ends drop;
   only giants (kael, 1 zone: 38.5 H vs built band 10.7-30.2, 3.8x ours, clamped) show a hall signal, no other race or Purpose
   (orc, dark elf: LDoN kit / city kind; dragon: u only); 13 mixed zones join built and cave by 3 links (median).
3. **A drop's height is drawn from stock, capped by `MAX_DROP`; the giant default is provisional** (the lead,
   2026-11-26, at task 1). `MAX_DROP` 80 u is the gate's limit, inflated by water and steep slopes; task 7 draws each drop's
   height from stock's (p50 24 u) under it, not uniformly. Giant 3.0 rests on one zone (kael, 7 halls): it applies to giant
   Districts only (requirement 5), and the step 31 look decides whether it stays.
   Task 7's draw: log-normal through p50 24 u / p90 84 u, redrawn into 6-80 u, then clamped to what the pair can take.
4. **Classic takes a per-District hall length, by scaling the District's offsets from its centre** (task 5), as task 4
   does for race: the zone-wide spread would lengthen the goblins' halls too. Graph uses a run per edge in the springs.
5. **The Graph giant hall misses its band on seeds 2000-2019 (x2.43, band 2.55-3.45); the lead accepted it** (task 5
   review). The same layout with and without the default gives x2.96. The shortfall is retry selection: longer halls clash
   more and the survivors run shorter. Seeds 2020-2059 give x2.68, inside the band. The default is provisional anyway (decision 3).

6. **A raced District's rooms also pick that race's decor sets, not only its sizes** (task 14, `RoomContext.race`
   per room; the lead kept it: a giant hall dressed as a giant's). One line to revert if the look says otherwise.

7. **The intruder is the Threshold's child side; a pair short of 3 links gets new breaches** (task 6, the lead's call at
   review): the intruder is the District farther from the zone entrance (the higher id). The graph's own cross edges are
   kept first, then new ones are added on the final rooms, just before the crossing passes: the nearest host/intruder pairs,
   spread off rooms already on a link, on one Level, within grade and `BREACH_SPAN` (2x) the longest hall of the two
   Districts, retried up to `BREACH_ROUNDS` (8) when those passes drop one. Seeds 2000-2019: 126 of 154 pairs (82 %)
   have 2+ links, 93 have 3; gate 80/80.
8. **Throats in a raced District take the pair's race corridor width** for their slack and separation gap (task 6, the
   follow-up). THROAT_GAP stays 8 u. Un-raced zones are byte-identical; giant cave Districts gate 40/40 (master 39/40).
9. **A breached host room draws 1 in 3 of its non-light recipe lines from the intruder, at the intruder's race** (task 8,
   the lead's call): the offset comes from a stream salted `spill/<seed>/<room>`. Spilled lines take the intruder's Sets and
   weights at the host's Scales, so goblin props stand at goblin size. Walls, light lines, POI Dressing and the bare draw stay
   the host's. Seeds 2000-2019: 159 of 208 host rooms spilled (49 drew bare), 29 % of their Props.
10. **A drop lowers only the lower room's opening** (task 7): the corridor's lower end runs `CorridorSpec.drop` u above
   that room's floor, the room keeps its wall below the sill (box and outline rooms), and the upper end stays flush.
   Decor keeps a body's width clear each side of the landing, under the sill too. No stairs, U-routes or bridges drop.
11. **Pacing stays two-way** (task 7): pacing roles read the room graph as undirected; a drop only changes the gate's
   directed reach, as advisory data should.
12. **A picked drop passes on** (task 7): each cross link draws at `DROP_SHARE` 0.1; a pick that can't take a drop
   (too little headroom, a stair, a clash, or it would break strong connectivity) moves to the zone's next cross link
   that can. Without it only 3.3 % of links dropped; with it 6.8 %.
13. **On equal floors the drop may reverse the corridor** (task 7): the drop lands in whichever room has more headroom
   under its ceiling; an all-drop intruder gets a flush return from its room farthest from the landings
   (`drop_returns`, inside `BREACH_SPAN`).
14. **A drop corridor's low legs keep 4 u (`DROP_SEAM_GAP`) off the lower room** (task 7): the gate's seam rule joins
   floors within 2 u in XY with no wall test, so a Z-corridor's bend beside the lower room read as a way back up
   (seed 2035 classic 24 `corr_20`). Layout skips such a fit rather than teaching the seam rule about walls.
15. **The corridor check walks a drop one way** (task 7): it floods from the upper room only and passes when the
   flood reaches the corridor's lower end and `find_drops` links that end onto the lower room's floor; a flood that
   reaches the lower floor fails as "drop walks both ways". Flush corridors keep the two-way check.
16. **An open intruder is dug into its host** (task 9): `ai.expand.layout_proposals` fills open `intrusion`
   proposals from CONTRASTS, and an intruder (District 1 on) picks among its host's dug contrasts (warren, cave,
   mine_delve) when any is free: a fortress gets a warren or a cave. Only the plan path; the layout's own draw is unchanged.
17. **Words set per-District races only when a phrase can place them** (task 9): an intrusion phrase's captured race
   holds the intruder and the zone race becomes the host's (blank if none named); other phrases need two races named.
18. **No hall touching a raced District runs past 164 H** (task 10, the lead's call): stock's longest door-to-door
   hall (cazicthule 163.6 H; gukbottom 162.8, txevu 159.3, so the max, not p99 101.9), at the larger race's H between
   two Districts. `layout.HALL_CAP_H`, after the hall and race scaling for every layout; breaches keep to it too. A
   throat between two Districts of different H is an ordinary corridor (squaring it up dragged rooms 4000 u).

## Follow-ups
- The gate's seam rule joins floors within 2 u in XY and 3 u in Z with no wall test (decision 14 works round it
  for drops); any geometry hugging a room's outside wall can read as joined through it.
- A classic zone draws no wall styles, so its breaches are plain extra links (sized by the smaller race) with no
  `breach` form and no rough break; only grown (graph) zones show them.
- Flood depth and the gate's doorway check still read the zone's race (water at giant H would be over the player's head).
- Same seed, different build: a race-less classic Districts zone differs in two decor entries and its `.zone.json` when
  another zone was built earlier in the same process (master too, found at task 14). Not this step's.
- A districted generate whose first Draw and build take over 20 s gets one attempt (task 10): the
  dungeon `DEFAULT_TIMEOUT_S` is 20 s and the CLI and Server pass none, so one gate reject ends it
  (`GenerationFailed`, timed out). Districted builds take 30-100 s, giant Graph ones minutes
  (task 15). Revisit after task 15.
- Two `--pair` seeds fail on master and on `070126c` alike (task 10): cave_first:sunken_ruin graph
  moderate 24 s313486578 (room_10 floor walled off) and cave_second:ice_keep graph moderate 17
  s1985365888 (room_11 footprint_cut, decor_0079). Step 22 had 552/552; they came in between.
- Cave classic dramatic 21 s1866540615 (`--only cave warren ... --seed 23`) fails alone in a fresh
  process on 070126c, a4ea982 and master alike (room_11 footprint_cut, decor_0074, 68 u^2). Task 2's
  696/696 at a4ea982 was the in-process leak above (that sweep built it after other zones in its
  worker), not a fix. A step 30 failure, not step 31's.
- A third District is breached too (`breach_hosts` takes every non-Threshold cross link), so some host rooms spill
  from it (dark elf, undead Sets) and not from the goblins (task 8). On master these zones already run over stock's
  p25-p75 decor band (per room about 11-15, light share about 0.6 against 2.9-6.8 and 0.21-0.45).
