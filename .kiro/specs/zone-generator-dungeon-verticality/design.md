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
  `connectors` (corridor id → kind, rise, risers, switchback) and
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
