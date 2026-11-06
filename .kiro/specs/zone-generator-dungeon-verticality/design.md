# Design — zone-generator-dungeon-verticality (roadmap step 7)

Written at master `8edf1df`. Verify against the code before working a task.

## Overview

Step 6's graph engine grows a room graph whose edges can carry a vertical
relation (`above`, `below`, `level`, `any`). Step 7 turns those relations
into real levels:

```
rules (TOML)  ── vertical rules: a descent, a stair hall, a gallery ─┐
                                                                    ▼
Topology_Graph  (kinds, sizes, relations)  ──►  Levels: integrate the relations
                                                 from the entrance (above +1,
                                                 below −1, level 0, any free)
                                                    │
placement (spring)  ── rooms on different Levels may overlap in plan
                       (may_overlap_in_plan), every other pair stays apart
                                                    │
Job B, now judged in 3D ── separation, crossing splits and conflict drops
                           respect the Slab; floors at Level × Level_Height
                           (+ today's ramp variation); an edge across Levels
                           becomes a Staircase (straight or switchback)
                                                    │
geometry (box backend) ── treads and risers (exists today, unused), switchback
                           landings, the stairwell; bridges if Open question 1
                                                    │
walk gate ── learns stairs and bridges FIRST (task 2), before any of the above
             produces them
```

The Classic engine is untouched: one level, byte-identical (step 6's goldens).

## Research findings

Measured at `8edf1df`.

1. **Stairs are built but never asked for.** `CorridorSpec.steps > 0` makes
   `generators/geometry.py` build treads and risers, with the ceiling
   following the treads and the last riser landing flush on the upper floor.
   Every corridor today is made with `steps=0` (`generators/layout.py`), so
   every height change is a ramp.
2. **The walk agent climbs stairs with risers of 3 u or less.**
   `analyzer.traverse.AgentModel`: slope cap 40°, step-up 3 u, player height
   6 u. `classify_corridor` already passes a staircase whose step is at most
   the step-up and names a taller one ("too tall to climb"). Faces join when
   their footprints touch and their centroids are within the step-up in Z,
   so tread-to-tread across a riser works (lessons-learned "A ramp must be
   SUBDIVIDED": ramps are cut into 2.5 u rises for the same reason).
3. **Ramps cost run.** `_assign_elevation` bounds every rise by the corridor
   run × 0.5 (`max_grade`, 26.6°); a stacked pair (one Level_Height apart,
   about a room's height) would need a ramp twice that long. A stair at
   ~35–40° climbs the same height in half the run, and a switchback in a
   quarter of the footprint.
4. **Stacked floors already map.** `generators/mapgeom.depth_bands` splits
   the floor into height bands so the two floors of every stacked pair
   (overlapping in plan, more than `STACK_GAP` = 12 u apart) fall in
   different bands, and the EQ map gets one file per band (step 1b).
5. **Placement keeps rooms apart in plan through one function.**
   `generators/topology/embed.py` `may_overlap_in_plan(a, b)` returns False;
   step 6 wrote it so step 7 changes one function. Job B's
   `_separate_rooms`, `_resolve_crossings` and the gate's `_faces_in_room`
   are XY tests today.
6. **Outdoor dungeons have little height.** Step 5's Envelope runs from a
   floor limit 150 u under the approach foot to the surface less a 24 u
   Rock_Cover, under a hill of about 110 u relief; rooms are 80 u tall. Two
   Levels need roughly two rooms plus a Slab (~180 u): the floor limit must
   go deeper for multi-level outdoor dungeons, which also answers step 5's
   follow-up that the Verticality control is ignored there.
7. **Stock vertical anatomy (task 1).**
   `scripts/dungeon_vertical_survey.py --eq-path F:\everquest_rof2` reuses
   step 6's walk (floor-wound WLD faces on the 4 u layered raster, the
   largest piece the agent walks). A level is a floor-height cluster holding
   at least 10 % of the floor area (the count at 5 % is in brackets).
   Stacked means another walked floor more than 12 u (`STACK_GAP`) above in
   the same column. Gap is the distance to that floor (p10/50/90). Headroom
   and slab split the gap at the first ceiling face over the lower floor
   (p50). A connector is floor with a grade of at least 0.35 that rises at
   least 12 u. A stair is a connector whose flat faces form 3 or more
   distinct treads. Going is the run per riser, landings included. Water is
   the share of the walked floor under a passable WLD face (water or lava
   plane). Dropped is the floor-wound area outside the walked piece, with
   the share of it that lies under a passable face.

   | zone | floor k u² | span p10–p90 | levels | Stacked | gap | headroom / slab | steepest (grade) | stairs: n, riser, going | water; dropped (wet) |
   |---|---|---|---|---|---|---|---|---|---|
   | befallen | 291 | 57 | 3 [3] | 11 % | 17/28/40 | 16 / 13 | 0.91 | 3, 1.0, 2.3 | 0 %; 3 k |
   | najena | 274 | 28 | 1 [1] | 4 % | 13/28/29 | 14 / 14 | 0.76 | 1, 1.0, 8.2 | 3 %; 3 k |
   | permafrost | 497 | 46 | 2 [2] | 8 % | 14/42/56 | 14 / 28 | 1.00 | 0 | 0 %; 177 k (0 %) |
   | sebilis | 508 | 88 | 2 [2] | 2 % | 14/18/27 | 16 / 2 | 1.18 | 14, 1.0, 2.0 | 1 %; 531 k (20 %) |
   | chardok | 878 | 351 | 2 [5] | 13 % | 20/157/358 | 30 / 83 | 0.99 | 9, 2.0, 3.2 | 1 %; 118 k (37 %) |
   | blackburrow | 522 | 171 | 4 [4] | 34 % | 24/59/148 | 42 / 19 | 0.99 | 1 (rock ledges, 5.0) | 19 %; 70 k (3 %) |
   | runnyeye | 402 | 132 | 4 [4] | 46 % | 23/46/86 | 12 / 26 | 0.71 | 2, 1.0, 1.8 | 10 %; 66 k (93 %) |
   | guktop | 272 | 84 | 2 [2] | 1 % | 14/28/28 | 14 / 14 | 0.88 | 2, 1.0, 3.1 | 10 %; 460 k (38 %) |
   | gukbottom | 452 | 96 | 2 [2] | 6 % | 15/28/56 | 14 / 14 | 1.03 | 8, 1.0, 1.9 | 2 %; 273 k (45 %) |
   | *unrest* | 557 | 18 | 1 [2] | 17 % | 14/22/36 | 14 / 6 | 0.94 | 9, 1.0, 1.6 | 1 %; 117 k (13 %) |

   Every zone's side view (height against its longer plan axis, coloured by
   level) was read by eye. **Unrest is excluded:** its outdoor yard is most
   of the floor at one height, so its level count and span describe the
   yard. The house really is four storeys (cellar at −14, then 0, 16 and
   44 u), but each storey holds under a tenth of the floor, and the roof top
   walks as floor. The other nine read right. Blackburrow and Runnyeye are
   stacked warrens of four levels each. Befallen has three tiers about 28 u
   apart. Permafrost has two, 42 u apart. Sebilis, Chardok and the Guks
   mostly descend and stack little. Najena's lower tiers (−14, −28, −45 u)
   each hold under 5 %, so it counts as one level.

   **Water.** Floor under shallow water is walked and counts: Blackburrow's
   stream (19 % of its floor) and some of Runnyeye's and Guktop's halls
   (10 % each). Floor under deep water is reached only by swimming, so it
   drops out. That removes Runnyeye's pool (93 % of its dropped floor is
   wet), part of Chardok's moat, and Guk's flooded halls: Guktop drops
   1.7 times the floor it keeps, Gukbottom 0.6 times, and about 40 % of that
   lies under water. Sebilis drops more than it keeps, but only 20 % of that
   is wet. "Dropped" is an upper bound: it also holds unreached ledges and
   wall tops, and the wet test (a passable face up to 80 u above) can't tell
   water from other passable faces. So the numbers for Sebilis and the two
   Guks describe their dry parts, and with the swim-only halls their
   stacking could be higher. They stay in the bands. Leaving all three out
   would give Stacked_Share 0.06–0.40 and a level count of 1.5–4.0.

   **Bands for Req 6** (p10–p90 over the nine kept zones):
   - Stacked_Share **0.02–0.36**;
   - level count **1.8–4.0**, i.e. 2–4 levels, with Najena's 1 as the low
     tail;
   - span p10–p90 **42–207 u**, or **1.1–3.7** stock level-to-level gaps
     (span divided by the zone's gap p50).
   Stock floors stack much tighter than our rooms (below), so a built
   dungeon's span should be checked in Level_Heights against the 1.1–3.7
   band. The span in units only holds at stock scale.

   **Starting values.**
   - **Slab = 14 u.** This is the median of the zones' slab p50s (band
     11–39 u). Najena, Guktop and Gukbottom are exactly 14. Sebilis's is
     2 u: there is almost nothing between its stacked floors.
   - **Level_Height = the tallest lower room overlapped + Slab.** For our
     dungeon rooms (0.4 × the measured 303 u ceiling = 121 u) that is about
     135 u. For outdoor dungeon rooms (80 u) it is 94 u. The stock levels
     are much tighter: floor to floor over a stacked spot is 28 u at the
     median (zone p50s 18–157 u, band 26–79 u), and level centres sit
     28–70 u apart. The stock headroom where floors stack is only 14 u at
     the median, so in stock dungeons it is corridors and low rooms that
     stack, not tall halls. Our rooms are about 4 times that tall, so our
     Level_Height cannot follow the stock 28 u. A lower stacking room (a
     stair hall or corridor-height room under another) is how to get
     closer, and is left as a follow-up.
   - **Riser_Cap = 2.0 u.** Stock stair risers are 1.0 u at p10 and p50
     and 2.0 u at p90, over 40 stairs. Every Chardok stair uses 2.0 u; the
     rest use 1.0 u. In Sebilis and Gukbottom, for example, 14 u-wide
     treads are 1 u deep, so the stairs climb at 45°. 2.0 u is the stock
     maximum and sits under the design's 2.5 u start and the agent's 3 u
     step-up. It also halves the tread count against stock's 1 u. The one
     coarser "stair" (Blackburrow, 4–6 u) is flat rock ledges on a slope,
     not a built stair.
   - **Tread depth = 3.0 u.** Stock going is 2.3 u at p50 (zone p50s
     1.6–3.2 u, with landings), and stock stairs climb at a grade of 0.63–0.70
     at the zone p50s (32–35°), up to 1.18. A 3 u tread under 2 u risers is
     a grade of 0.67 (34°), the stock median. The design's 4 u start would
     give 0.5, the grade of our ramps.
   - **Steep ramps.** Connectors that aren't stairs reach grades of
     0.84–1.0 (40–45°) in Permafrost, Blackburrow and Chardok, but only over
     short rises (13–27 u). The p50 rise of a stock connector is 15–28 u.
     Our ramps stay at `max_grade` 0.5. Stairs take the steep climbs.

   **Not verified:** the walk is the agent's, not the client's (the agent
   steps up to 3 u; the client may climb more). A floor-wound ceiling that
   joins the walked piece would count as stacked floor; the side views show
   none outside Unrest's roof. Tread grouping can pick up flat floor beside a
   stair, which is why riser maxima reach 4–12 u; the p50s are robust. None
   of this has been checked in the client.
8. **Race body heights and stock rooms (task 16).**
   `scripts/race_size_survey.py --eq-path F:\everquest_rof2`.

   **Body height H.** H is the race's default height from the client's
   `racedata.txt` (last two fields of each race row, male/female, in world
   units: the size of an NPC spawned at the race's default, the same units
   as an NPC's `size`). The character models were posed and measured as a
   check: each model's WLD skeleton (0x10) with its bones' rest tracks
   (0x13 → 0x12 frame 0, quaternion + shift/256 + scale = the shift
   denominator/256, composed down the bone tree) moves the skinned mesh's
   vertex pieces; "native" is the Z extent of the body and head-0 meshes.
   Every humanoid model is 6–7 u tall natively whatever its race (the frost
   giant is 6.8, the ogre 6.5), so the meshes are authored at one scale and
   the client sizes each race on top: the model can't give H on its own. It
   gives proportions: the dragon's length is 2.7× its height (tail
   included), so a dragon at H 21 is ~56 u long. Humanoid plan extents are
   arm spans (the rest pose is a T-pose).

   | race | H (u) | model (race id, archive) | native Z (u) | others |
   |---|---|---|---|---|
   | default (human) | 6 | HUM (1, globalhum_chr) | 7.1 | HUF 6.9 |
   | goblin | 6 | GOB (40, runnyeye_chr) | 7.1 | |
   | froglok | 5 | FRG (26, gukbottom_chr) | 4.9 | FRO (330) 5.0, H 5 |
   | kobold | 5 | KOB (48, kob_chr) | 5.7 | |
   | lizardman | 6 | LIZ (51, liz_chr) | 6.5 | |
   | gnoll | 6 | GNN (39, blackburrow_chr) | 7.3 | |
   | sarnak | 9 | SRW (131, chardok_chr) | 6.9 | |
   | troll | 8 | TRM (9, globaltrm_chr) | 7.2 | TRF 7.1 |
   | ogre | 9 | OGM (10, globalogm_chr) | 6.5 | OGF 7.0 |
   | giant | 22 | FSG frost giant (188, kael_chr) | 6.8 | STG storm giant (189) 6.7, H 20; GIA (18) 6.9, H 21 |
   | dragon | 21 | DRA (49, dra_chr) | 36.2 (97 long) | DR2 Velious dragon (184) 15.3 native, 62 long, H 25 |
   | orc (reference) | 6 | ORC (54, crushbone_chr) | 5.9 | |

   Every race was found. The code ↔ race-id pairs are EQ's race list, not
   read from a file. The walk agent's player height is 6 u, the human H.

   **Rooms.** Step 6's walk and chamber split, with the width threshold
   scaled to the race (40 u × H/6: 33 u for frogloks and kobolds, 60 u for
   sarnak and ogres, ~140 u for giants and dragons; at 40 u Veeshan's Peak's
   tunnels read as chambers). Height = the p50, over a chamber's floor, of
   the headroom to the first ceiling-wound face (vault = p90); chambers less
   than half under a ceiling are open and left out; a flat lid at the zone's
   top counts as sky. Per zone p10/p50/p90 over the covered chambers (N),
   in H:

   | zone | race (H) | N | height u | height / H | vault / H | side u | side / H |
   |---|---|---|---|---|---|---|---|
   | befallen | default (6) | 24 | 14/14/18 | 2.3/2.3/3.1 | 2.3/2.3/4.5 | 53/75/125 | 8.9/12.4/20.9 |
   | blackburrow | gnoll (6) | 37 | 25/49/96 | 4.1/8.2/15.9 | 5.3/10.0/17.2 | 57/74/124 | 9.4/12.3/20.6 |
   | runnyeye | goblin (6) | 18 | 12/12/21 | 2.0/2.0/3.5 | 2.0/2.6/4.8 | 50/64/78 | 8.4/10.6/13.0 |
   | droga | goblin (6) | 124 | 16/17/48 | 2.7/2.8/8.0 | 2.7/4.0/8.0 | 55/87/155 | 9.2/14.5/25.9 |
   | soldunga | kobold (5) | 27 | 12/12/38 | 2.4/2.4/7.6 | 2.4/4.0/8.4 | 42/54/93 | 8.4/10.8/18.7 |
   | guktop | froglok (5) | 30 | 13/19/31 | 2.7/3.9/6.3 | 2.8/5.2/7.8 | 42/51/93 | 8.3/10.2/18.6 |
   | gukbottom | froglok (5) | 29 | 14/15/35 | 2.8/3.1/6.9 | 2.8/4.4/9.3 | 45/51/69 | 8.9/10.2/13.8 |
   | cazicthule | lizardman (6) | 23 | 13/28/77 | 2.2/4.7/12.8 | 2.2/4.7/14.1 | 50/61/120 | 8.3/10.2/20.0 |
   | chardok | sarnak (9) | 31 | 25/45/95 | 2.8/5.0/10.5 | 4.4/6.7/14.9 | 73/87/111 | 8.1/9.7/12.4 |
   | oggok | ogre (9) | 23 | 30/40/55 | 3.4/4.4/6.1 | 3.7/4.8/6.6 | 67/80/119 | 7.5/8.9/13.2 |
   | kael | giant (22) | 8 | 124/140/302 | 5.7/6.4/13.7 | 6.9/7.5/15.5 | 151/168/228 | 6.9/7.6/10.4 |
   | soldungb | dragon (21) | 1 | 98 | 4.7 | 5.7 | 164 | 7.8 |
   | veeshan | dragon (21) | 18 | 80/157/383 | 3.8/7.5/18.2 | 3.8/7.6/21.3 | 142/196/344 | 6.8/9.3/16.4 |
   | sleeper | dragon (21) | 12 | 92/96/192 | 4.4/4.6/9.1 | 4.4/4.6/9.1 | 132/205/443 | 6.3/9.8/21.1 |
   | skyshrine | dragon (21) | 15 | 80/95/139 | 3.8/4.5/6.6 | 3.9/5.0/6.7 | 131/217/413 | 6.3/10.3/19.7 |

   Plans and side views were read by eye. **Crushbone is left out:** it is
   outdoor and its sky lid (620 u) sits under a higher face, so its valley
   reads as 100 H rooms. At the dragon threshold Nagafen's lair (soldungb)
   keeps one chamber, the lair itself (98 u, 4.7 H); the rest of the zone
   is kobold and goblin tunnels under it. Kael keeps 8 chambers: halls of
   5.7–6.4 H and two forecourts under the cavern roof at ~14 H. Oggok and
   Cazic-Thule lose their lidded yards (5 open chambers each). Veeshan's
   Peak's 18 H is its great cavern.

   Across the 15 zones kept (p10–p90 across zones; median in brackets):
   height zone-p10 2.3–4.6 H (2.8), zone-p50 2.4–7.0 H (4.5), zone-p90
   4.0–15.1 H (7.6); side zone-p10 6.5–9.1 H (8.3), zone-p50 8.3–12.4 H
   (10.2), zone-p90 11.2–21.0 H (18.6). Once divided by H the big races'
   rooms land in the same range as the small ones': Kael's and the dragon
   zones' heights (4.5–7.5 H at p50) sit beside Blackburrow's and
   Chardok's, so one set of multiples for every race holds.

   **Proposed bands (the same for every race; only H changes):**
   - room height **[2.5 H, 10 H]**: `tiny` at 2.5 H (stock's low rooms,
     the zones' p10 median 2.8 H; Befallen, Runnyeye and the Guks sit at
     2–3 H), `huge` at 10 H (above the zone-p90 median 7.6 H, under
     Veeshan's and Blackburrow's 15–18 H caverns);
   - footprint side **[8 H, 20 H]**: `tiny` at 8 H (the zone-p10 median
     8.3 H), `huge` at 20 H (the zone-p90s reach 21 H). The low end is
     partly the chamber definition: a chamber is floor wider than 6.7 H.

   In units: human (H 6) rooms 15–60 u tall, 48–120 u across; ogre (9)
   23–90 u, 72–180 u; giant (22) 55–220 u, 176–440 u; dragon (21) 53–210 u,
   168–420 u (a 56 u dragon fits the smallest).

   **Against our numbers.** Our human dungeon rooms are 121 u tall at
   `medium` (97–182 u from `tiny` to `huge`): 16–30 H, 1.6–3× the proposed
   maximum and ~4× stock's typical human room (Befallen 14 u, 2.3 H). The
   medium side is ~340 u at 10 rooms (57 H; 290–440 u for 14–6 rooms), ~3×
   the 20 H maximum. Outdoor-dungeon rooms (80 u) are 13 H. The walk
   agent's 6 u player is the human H. At the bands a human dungeon room is
   about the height a giant's or dragon's is today relative to its body;
   today's human rooms are roughly giant-sized (121 u = 5.5 giant H).

   **Not verified / uncertain.** How the client scales a model to its
   race's height is not in the client files: H assumes an NPC at default
   size stands its racedata height tall (true for the human, 6 u, against
   the 6–7 u meshes). The dragon model's native 36 u comes from the
   shift-denominator-as-scale reading (its pelvis bone has scale 6.2);
   read the other way it would be 6 u, so dragon proportions rest on that
   reading (it is the one that poses the Luclin human correctly). Named
   NPCs often spawn above their race's default (Nagafen, Vox and the VP
   dragons are server data, not here). Room heights under-read where a
   ceiling-wound beam or ledge sits over the floor and over-read where a
   lid escaped the test. Kael has only 8 chambers and Nagafen's lair one.
   None of this has been checked in the client.

## Levels

The graph engine assigns Levels after growing and before placement:
breadth-first from the entrance, each edge's relation gives the neighbour's
Level (`above` +1, `below` −1, `level` 0). An `any` edge gives no constraint;
its room takes its first-reached neighbour's Level. A relation cycle that
disagrees (e.g. a loop that goes down twice and up once back to its start)
is resolved by the rewrite driver, which rejects a rule application that
makes the relations inconsistent (a new invariant, alongside connected,
degree ≤ 4 and loops 4–5).

Floor height = Level × Level_Height + the step 6 ramp variation within a
Level (bounded so two Levels never meet). Level_Height = the tallest room on
the lower Level that the upper one overlaps + the Slab; simplest first: one
Level_Height per build from the size classes and race scale.

## Stacking (`may_overlap_in_plan`)

`may_overlap_in_plan(a, b)` becomes: rooms on different Levels whose
vertical gap (upper floor − lower ceiling) is at least the Slab. Placement's
springs then don't push such a pair apart, and a stair edge between them
pulls them together in plan (a stair room over/beside its lower room).
Everything Job B does in plan becomes a 3D test through the same predicate:

- `_separate_rooms`: skip pairs that may overlap.
- `_resolve_crossings`: a corridor crossing a room's footprint at a height
  clear of the room (over its ceiling + Slab, or under its floor − Slab) is
  not a crossing.
- `_resolve_conflicts`: already compares corridor heights.
- The gate's room-face test (`_faces_in_room`) must pick a room's own floor,
  not the floor stacked above or below it (z-bounded).

## Staircases

An edge across Levels becomes a corridor with `steps > 0`:

- risers = ceil(rise / Riser_Cap); Riser_Cap below the 3 u step-up (start
  2.5 u, the ramp subdivision's figure; task 1 refines it);
- tread depth from the survey (start 4 u), so the stair's run = risers ×
  tread;
- the routing rule stays: the whole rise lives on one leg (lessons-learned
  "Same-axis room pairs need a Z-route"). If that leg is shorter than the
  stair's run, the stair becomes a **Switchback**: two flights, half the
  rise each, with a flat landing, folded inside a stairwell box beside the
  leg. The stairwell is a small room (kind `stair`) placed by the engine, so
  its footprint is separated and checked like any room;
- headroom: the ceiling follows the treads (already true).

## Bridges (Open question 1)

A Bridge joins two rooms on the same upper Level across the plan footprint
of a taller lower room (a gallery over a hall): the corridor runs at the
upper Level through the lower room's air, and the lower room's ceiling is
opened under the deck so the void reads from both levels. This needs the
box backend to cut a ceiling opening and the gate to accept a corridor whose
floor is inside another room's volume. It is the riskiest piece of the step
(new geometry plus a new gate case), so if it is in, it lands as its own task
after stairs, with a human look of its own.

## Rule format

The format already carries everything: an edge's `rel` is `above`, `below`,
`level` or `any`. Rules with an `above`/`below` edge in their replacement
are *vertical rules*; the Verticality control scales their weights
(`flat`: 0, `moderate`: 1, `dramatic`: 2), so no new field is needed. New
shipped rules (task 6): `descent` (the way on goes down a Level), `stair_hall`
(a hub with a stair down to a room below it), `gallery` (a room above a hall,
joined by a stair; with bridges, a bridge across). The checker gains one
rule: a rule's replacement must not contain an `above` cycle that disagrees
with itself.

## Outdoor dungeons

`host_envelope`'s floor limit follows the Verticality control (`flat`: as
today; `moderate`/`dramatic`: deep enough for two or three Levels, capped by
the host); the Tunnel enters at the top Level; the Envelope fit treats each
Level's rooms against their own heights. This is step 5's follow-up option
(1) plus stacked levels (its option (3)). The big-race outdoor dungeon
(rooms taller than the hill) stays a follow-up unless the deeper floor limit
happens to fix it; task 8 measures it.

## Controls and sidecar

- Verticality shows for graph dungeons and outdoor dungeons
  (`CONTROL_ZONE_TYPES` in `web/src/main.ts`; today dungeon and city only).
- The sidecar's `layout` block gains `levels` (room id → Level),
  `connectors` (corridor id → kind, rise, risers, switchback; a bridge also names the room it crosses, `over`) and
  `stacked_share`.

## Race-sized rooms (Req 10; user, 2026-11-04)

Today a race is one multiplier (`semantics.RACE_SCALE`: goblin 0.85 ... ogre
1.4, giant 2.2) applied to every room, so an ogre can still roll a `small`
room barely bigger than a human's, and nothing caps the top. The code already
notes the gap: "Real per-race limits should come from EQ model bounding
boxes ... which we do not yet have."

The model instead: each race has a **body height** H (measured, finding 8;
the default race is a human, H about the walk agent's 6 u), and a **room
band** for height and footprint, each `[min, max]` as multiples of H. Size
classes (`tiny` ... `huge`) then pick a point inside the band (tiny at the
minimum, huge at the maximum) instead of multiplying a race-free base. So an
ogre's `tiny` room is sized for an ogre, a dragon's `huge` hall is vast, and a
human's `huge` hall is still a human's. The band multiples are set once from
the stock zones (task 16 measures rooms against the races that live in them,
e.g. Kael's halls for giants, Nagafen's lair and Veeshan's Peak for dragons)
and are the same for every race; only H changes. Both engines use the bands;
the Level_Height follows from the banded heights.

## Correctness properties

| P | Statement | Reqs |
|---|-----------|------|
| V1 | The gate passes a Staircase iff risers ≤ step-up, treads ≥ the minimum, headroom ≥ player height; a Bridge iff continuous and flush; failing cases are named | 2 |
| V2 | Generated stairs: every riser ≤ Riser_Cap, flush at both ends, switchback landings flush | 3.1–3.3 |
| V3 | Levels are consistent with every `above`/`below`/`level` edge of the grown graph | 4.1 |
| V4 | Only rooms on different Levels with at least the Slab between them overlap in plan; no corridor passes through a room without the Slab's clearance | 4.2, 4.3 |
| V5 | Every edge across Levels is a Vertical_Connector; the built graph is connected | 4.4 |
| V6 | Classic builds byte-identical; `flat` graph builds one Level | 4.5, 5.2, 9.1 |
| V7 | Built Stacked_Share, level count and span in the survey bands at `moderate`; step 6 bands and fidelity bars hold | 6 |
| V8 | Multi-level outdoor dungeons: rooms under the hill with the cover, one Entrance at the top Level, every room reached | 7 |
| V9 | Stacked builds map each Level on its own depth band | 8.3 |
| V10 | First-try gate rate ≥ step 6's; same inputs, same `.eqg`; time ≤ step 6 + 10 s | 9 |
| V11 | Every room's height and footprint lie inside its race's bands, for every size class and both engines | 10 |

## Risks

- **3D routing is the hard part.** vazgriz's TinyKeep-in-3D found that the
  staircase ate the effort: rise and run, headroom, a landing at each end,
  and routing around stairs just made (the retired followup design,
  "Spatial camp"). Mitigations: stairs live on the one leg that already
  carries the rise; switchbacks fold into a stairwell room the engine places
  and separates like any room; gate first.
- **Job B's XY assumptions.** Separation, crossing splits and the gate's
  room-face test all reason in plan. Each moves to the one predicate, and
  the classic goldens prove classic didn't move.
- **Structural tests pass, the 3D view shows it broken** (lessons-learned).
  Stairs are new geometry: the first look (task 11) is before tuning, and the
  stair spike (task 3) gets a look at its own geometry through the walk
  check's diagnosis output.
- **Outdoor height.** Two Levels need about 180 u; a hill of 110 u relief
  over a floor limit 150 u down may not hold them for big rooms. The
  Envelope drops rooms with `rooms_reduced` before it fails.

## Open questions (answered 2026-11-04: the defaults; see `archive.md`)

1. **Which vertical connectors.** Default: staircases (straight and
   switchback) in this step, bridges as a later task in the step after a
   look at the stairs, one-way drops (holes the player falls through) out.
   Alternatives: stairs only (bridges to a later step); or stairs, bridges
   and drops.
2. **Stair collision.** Default: real treads and risers as both the look and
   the collision (risers ≤ 2.5 u, which the walk agent and the client climb),
   as hand-made zones do. Alternative: visual steps over a hidden ramp for
   collision (smoother to walk, two meshes per stair).
3. **What drives stacking.** Default: the rules (their vertical relations),
   scaled by the existing Verticality control (`flat` / `moderate` /
   `dramatic`). Alternative: a separate Levels control (1, 2, 3).
4. **Outdoor dungeons.** Default: multi-level, the floor limit following
   Verticality, at most the levels the hill holds (likely two). Alternative:
   leave outdoor dungeons at one level for now.
5. **How far up.** Default: levels go up and down from the entrance (towers
   and cellars both). Alternative: down only (dungeons descend), which keeps
   the entrance on top and suits outdoor dungeons.

## Decisions

1. The gate learns stairs (and bridges) before any layout makes them.
2. Levels come from the rules' relations; no new rule field.
3. `may_overlap_in_plan` is the one switch; every plan test in Job B and the
   gate goes through it.
4. The Classic engine stays one level, byte-identical.
5. Measure the stock dungeons first (task 1) and set the numbers from them.
