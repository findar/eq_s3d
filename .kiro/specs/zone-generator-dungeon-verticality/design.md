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
7. **Stock vertical anatomy: task 1.** The survey (extending step 6's
   `scripts/dungeon_topology_survey.py` walk) reports vertical span, level
   count, Stacked_Share, level-to-level height and stair dimensions for the
   stock dungeons, and fills this finding. Its numbers set the Level_Height,
   the Riser_Cap, the tread depth, the rules' vertical weights and the
   bands of Req 6.

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

## Open questions (for the user; defaults recommended)

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
