# Design — zone-generator-site-sockets (roadmap step 13)

Written 2026-11-14 at master `2448243`. Verify against the code before working a task; the
names below are from that commit.

## Overview

```
WORLD    world_for(...) -> terrain, water, regions, Spawn, Sockets
         │   hill0  (hillside: outdoor dungeon)
         │   ground (area: Spawn, Kept_Clear)
         │   site0..siteN  (NEW: point Sockets in Groups, from the terrain, the biome's
         │                  clustering rules and the World seed; no Site control reads here)
         │
ATTACH   hillside: rooms, Entrance, Apron edit; Kept_Clear = the dungeon's own rooms,
         │         corridors, Tunnel and Apron (NEW: no longer the hill's whole disc)
         │ ground: the Sites stage, from rooms_seed:
         │         target count (Sites control) -> Groups in a size-biased order ->
         │         each point: skip if it meets Kept_Clear; draw Inhabitant; draw a kind that
         │         fits the point; arrange as step 10 -> Site (names its point)
         │
BUILD / DECOR / PACK as step 12; trees keep off the Sites as now
```

The `ground` Socket stays the one Attachment for Sites: the count, the Spawn and the
Kept_Clear shapes are zone-wide. Each Site records which point Socket it took.

## Today (as read at `2448243`)

- `world.world_for` gives a wilderness one `ground` Socket and an outdoor dungeon `hill0` then
  `ground` (step 12 task 3). `World` is version 1.
- `stages.attach_sites` -> `sites.placement.place_sites(terrain, ground, seed, ...)`. One
  stream (`sites_seed(rooms_seed)`, salt `SITES_SALT`) draws the target (`site_target`: a
  density in the biome's band times the reached area, rounded to keep its mean), then per
  Site an Inhabitant, a kind, and a centre: `_choose_centre` samples up to 48 candidate spots
  on the recipe's eligible ground, rejects any nearer another Site than
  `max(recipe.spacing, other.spacing, outer + other's outer)`, and keeps the best by likes
  plus a Gumbel draw. A kind with no ground is redrawn from the others (step 10 task 15).
- Recipe `spacing` is 200 u (camp, hut), 300 u (farmstead, shrine, ruin) or 400 u
  (watchtower) (`rules/sites/sites.toml`). Stock plains' closest pairs are 108–191 u
  (finding 1): the spacing alone keeps Sites from ever grouping as stock's do.
- An outdoor dungeon's Sites keep off `stages.entrance_keep_clear`: the Host_Hill's disc
  (`radius + flank / 2` = 400 u for `DEFAULT_HOST_HILL`), the Tunnel and the Apron.
  `outdoor_dungeon.keep_clear_shapes` is the same function on a spec (a test pins them equal;
  step 12 follow-up).
- `tests/test_site_bands.py` asserts Clark–Evans R (pooled and median zone) inside the
  all-zone band `STOCK_R` 0.64–1.64 and spacing p10 inside the all-zone 130–490 u.

## Research findings

### 1. How stock places its Sites (measured)

Measured 2026-11-14 with the step 10 survey's own code (`scripts/site_survey.py`: `cluster`,
`site_measures`, `ground_of` on the cached walked ground) by `scripts/site_clustering.py`
(task 1; `python scripts/site_clustering.py --eq-path F:\everquest_rof2` prints every number
below). R_CE is Clark–Evans as `tests/test_site_bands.clark_evans` computes it (mean
nearest-Site distance over `0.5 / sqrt(Sites / ground)`). R_mc divides the same mean by the
mean nearest distance of as many points dropped uniformly on the zone's own dry walked cells
(400 draws, generator seed 13), so the ground's shape and edges are in the expectation; p is
the share of those draws as clustered or more. "In 300" is the share of Sites with another
Site within 300 u. The biome groups are the script's reading of the zones (`BIOME`), not the
survey's.

| Zone | Group | Sites | Ground 1e6 u² | R_CE | R_mc | p | Sites per 300 u Group | In 300 | NN p10 / p50 |
|---|---|---|---|---|---|---|---|---|---|
| qeytoqrg | plains | 6 | 15.4 | 0.95 | 0.71 | 0.12 | 1.20 | 33 % | 173 / 896 |
| qey2hh1 | plains | 43 | 114.3 | 0.58 | 0.51 | 0.00 | 1.79 | 65 % | 108 / 192 |
| northkarana | plains | 17 | 50.9 | 0.83 | 0.68 | 0.02 | 1.21 | 35 % | 181 / 671 |
| eastkarana | plains | 17 | 36.3 | 0.76 | 0.56 | 0.01 | 1.70 | 59 % | 160 / 196 |
| southkarana | plains | 8 | 90.3 | 0.50 | 0.41 | 0.00 | 1.60 | 62 % | 191 / 222 |
| innothule | swamp | 10 | 10.1 | 0.64 | 0.52 | 0.01 | 1.67 | 60 % | 140 / 188 |
| feerrott | swamp | 34 | 17.8 | 0.99 | 0.89 | 0.14 | 1.55 | 56 % | 148 / 264 |
| everfrost | snow | 29 | 39.4 | 0.94 | 0.86 | 0.10 | 1.32 | 45 % | 197 / 305 |
| lakerathe | hills | 36 | 17.4 | 0.94 | 0.84 | 0.07 | 1.80 | 64 % | 132 / 201 |
| rathemtn | hills | 30 | 65.1 | 0.82 | 0.75 | 0.01 | 1.25 | 27 % | 128 / 697 |
| ecommons | hills | 18 | 17.5 | 1.21 | 1.01 | 0.52 | 1.12 | 22 % | 288 / 626 |
| steamfont | hills | 11 | 14.6 | 1.35 | 1.16 | 0.81 | 1.38 | 36 % | 182 / 414 |
| cauldron | hills | 4 | 9.7 | 1.70 | 1.24 | 0.80 | 1.00 | 0 % | 1232 / 1282 |
| nro | desert | 17 | 16.1 | 1.12 | 0.92 | 0.29 | 1.06 | 12 % | 256 / 434 |
| sro | desert | 20 | 11.4 | 1.63 | 1.40 | 1.00 | 1.00 | 0 % | 448 / 615 |
| oasis | desert | 16 | 11.0 | 1.31 | 1.03 | 0.60 | 1.14 | 25 % | 233 / 488 |
| tox | forest | 12 | 11.5 | 1.62 | 1.20 | 0.86 | 1.00 | 0 % | 417 / 602 |
| lfaydark | forest | 15 | 17.3 | 1.42 | 1.23 | 0.94 | 1.00 | 0 % | 481 / 791 |
| kithicor | forest | 17 | 16.5 | 1.04 | 0.93 | 0.30 | 1.13 | 24 % | 226 / 531 |
| nektulos | forest | 7 | 11.2 | 1.73 | 1.34 | 0.91 | 1.00 | 0 % | 607 / 1046 |

(beholder has no Site; the three towns stay out, as in step 10.) By group, zones with 3+ Sites:

| Group | Zones | R_CE min–max (median) | R_mc median | In 300, median | NN p10, min–max |
|---|---|---|---|---|---|
| plains | 5 | 0.50–0.95 (0.76) | 0.56 | 59 % | 108–191 |
| swamp | 2 | 0.64–0.99 (0.82) | 0.71 | 58 % | 140–148 |
| snow | 1 | 0.94 | 0.86 | 45 % | 197 |
| hills | 5 | 0.82–1.70 (1.21) | 1.01 | 27 % | 128–1232 |
| desert | 3 | 1.12–1.63 (1.31) | 1.03 | 12 % | 233–448 |
| forest | 4 | 1.04–1.73 (1.52) | 1.21 | 0 % | 226–607 |
| all 20 | 20 | p10–p90 0.64–1.64 (1.02) | 0.90 | 30 % | 108–1232 |

The all-zone R_CE p10–p90 reproduces step 10's `STOCK_R` (0.64–1.64) and the plains range
its 0.50–0.95, so the numbers here are step 10's numbers, extended.

What it says:

- **Plains cluster, and not because of their ground's shape.** R_mc is 0.41–0.71 and four of
  five plains zones are more clustered than 98 % of random draws on their own ground. Swamps
  and snow cluster too; forests and deserts space their Sites out (R_mc 0.92–1.40, no Site
  within 300 u in five of seven). So the clustering target is per biome, and stock supports
  three kinds of answer: clustered (plains, swamp, snow), random-ish (hills), dispersed
  (desert, forest). Only plains has Site rules today; the others are recorded for their
  biomes.
- **Plains Sites come in hamlets.** Single linkage of the plains' 91 Sites at the Group gap:

  | Gap | Groups | Sizes (share of Groups) | Mean size | Within-Group NN p10/p50/p90 | Group-centre NN p10/p50 |
  |---|---|---|---|---|---|
  | 200 u | 68 | 1: 75 %, 2: 16 %, 3: 9 % | 1.34 | 108 / 160 / 192 | 235 / 896 |
  | 300 u | 58 | 1: 69 %, 2: 19 %, 3: 9 %, 6: 2 %, 8: 2 % | 1.57 | 112 / 164 / 227 | 672 / 1075 |
  | 400 u | 58 | the same as 300 u | 1.57 | 112 / 164 / 227 | 672 / 1075 |

  Nothing joins between 300 and 400 u, so 300 u is the natural gap. By Site rather than by
  Group, 44 % of plains Sites stand alone and 56 % in a Group of two or more (Groups of 1, 2,
  3, 6 and 8 hold 40, 22, 15, 6 and 8 of the 91).

  **The plains block** (`rules/sites/biomes.toml`, task 2), as the script prints it from the
  300 u row and the plains zones:

  ```toml
  [biomes.plains.groups]
  gap = 300                       # nothing joins between 300 and 400 u
  sizes = { 1 = 0.69, 2 = 0.19, 3 = 0.09, 4 = 0.03 }   # 300 u shares; the 6 and 8 fold into 4
  within = [112, 227]             # within-Group NN p10-p90 (111.6, 226.8)
  spacing = 600                   # Group-centre NN p10 672, rounded down
  target_r = [0.50, 0.95]         # plains R_CE min-max (0.497, 0.946)
  target_in_gap = [0.33, 0.65]    # plains "in 300" min-max (0.333, 0.651)
  target_nn_p10 = [108, 191]      # plains zone NN p10 min-max (108.4, 191.3)
  ```

  Corrected from the draft: `target_nn_p10`'s high is 191 (southkarana's p10 is 191.3), not
  the 190 the draft wrote below and in Req 4.1. The draft's R_mc and p columns came from other
  random draws; the table above holds the script's (seed 13), and every conclusion stands.

### 2. Where today's Sites stand (measured for this draft)

Placement only (`world_for` + `stages.attach_sites`, no TER, no build), wilderness seeds
1000–1039, same R_CE on the placement's reached area:

| Control | Sites per zone, mean (min–max) | R_CE median, zones with 3+ | R_CE pooled, zones with 2+ | R_mc median (3+) | NN p10 / p50 | In 300 |
|---|---|---|---|---|---|---|
| Normal | 1.95 (1–3) | 1.12 (6 zones) | 1.54 (32 zones) | 0.81 | 447 / 1050 | 0 % |
| Dense | 3.90 (3–5) | 1.36 (40) | 1.32 (40) | 1.01 | 383 / 658 | 4 % |

Step 10 task 11 measured R pooled 1.45 on the built, read-back zones (archive); this draft's
1.54 is on the placement alone, before trees and the survey's re-clustering. Either way no
Site has a neighbour within 300 u at Normal, against 33–65 % on stock plains.

**What a clustering target can see at Normal.** A zone holds 1–3 Sites (the plains density
times 4.8e6 u²), so one zone's R is noise, and R pooled over zones with two Sites is mostly
the question "are the two in one Group". An estimate, not a measurement (task 6 measures it, task 11 holds it):
two Sites in one Group are about 164 u apart (finding 1), R about 0.2; two in different
Groups measure about today's 1.3–1.5. Drawing the first Group by its size gives a Site a
Group-mate 56 % of the time (finding 1), which puts R pooled near 0.7–0.8, inside 0.50–0.95.
Drawing Groups uniformly would pair only 31 % (the share of Groups of two or more), near 1.1:
outside. Hence the size-biased order (Req 3.4) and the "in 300" share as a second target that
edges don't distort.

### 3. Why outdoor dungeons get few Sites (measured for this draft)

Outdoor-dungeon seeds 0–39 (seed 8 fails to plan, 39 plan), the planned spec's World with its
Apron applied, placement's own masks:

| Ground (1e6 u², median, min–max) | |
|---|---|
| Reached | 0.816 (0.808–0.816) |
| Site-eligible (trees' Eligible_Ground, playable, reached) | 0.739 |
| ... and no steeper than 8° | 0.205 (0.139–0.378) |
| ... outside the hill's 400 u disc | 0.221 |
| ... outside the hill, Tunnel and Apron (today's Kept_Clear) | 0.208 |
| ... and no steeper than 8° | 0.019 (0.002–0.061) |
| ... and no steeper than 10° / 15° | 0.050 / 0.125 |

Today's Sites at Normal: on 8 of 39 seeds (target mean 0.33); at Dense on 10 (target mean
0.67). So two things hold them back: the count (the plains density times 0.82e6 u² averages
a third of a Site) and the ground (the hill disc takes 70 % of the eligible ground, and the
ring left is lower flank, steeper than any recipe allows).

Seeds on which a disc of the smallest Sites fits anywhere (outer radius 40 u: a ruin; 48: a
hut; 54: a camp), by what Sites keep off and the slope allowed (placement's own
`disc_on_eligible`, tried at nine spots in every eligible quad):

| Kept_Clear | 8°, r 40 | 8°, r 48 | 10°, r 40 | 10°, r 48 |
|---|---|---|---|---|
| Hill disc 400 u, Tunnel, Apron (today) | 13/39 | 7/39 | 22/39 | 17/39 |
| Hill disc 250 u (the Landform's radius), Tunnel, Apron | 28/39 | 15/39 | 34/39 | 30/39 |
| The dungeon's rooms and corridors + 16 u, Tunnel, Apron | 39/39 | 39/39 (r 54: 39/39) | 39/39 | 39/39 |
| Tunnel and Apron only | 39/39 | 39/39 | 39/39 | 39/39 |

The flat ground is on the hill (its crown and the shelf at its foot), not round it. Keeping
Sites off the dungeon itself rather than the whole hill gives every seed room for a camp.

### 4. What else the code offers

- `vegetation.placement.ground_of`, `Ground.disc_on_eligible`, `shapes_touch_quads` and
  `placement._terrain` already compute everything a point needs (eligible quads, slope,
  reached, water and zoneline distances, height rank).
- `world.Socket.ground` carries any plain JSON, exact; `World.sockets` keeps attach order.
- The page's map already draws a diamond per Socket from the sidecar (`web/src/sockets.ts`).

## Point Sockets

### What a point holds

```python
Socket(id="site3", kind="site", x, y, z,          # z: the World's ground at the point
       accepts=("site",),
       ground={"group": 1,                         # Group index, in the World's order
               "rank": 3,                          # order among all points
               "free": {"5": 61.0, "6": 61.0, "8": 74.5, "10": 74.5},  # Free radius per slope
               "height_rank": 0.42, "clearing": 0.9,                   # for the recipes' likes
               "water_d": 512.0, "zoneline_d": None})
```

`free` is keyed by the slopes the Site recipes use (5, 6, 8, 10 degrees today, read from
`rules/sites/sites.toml`). It is the radius of the largest disc round the point on eligible
ground at that slope, measured with placement's own test (`disc_on_eligible`), so a recipe
whose `radius + margin` is within it fits on the World's ground before any Attachment. A
`site` Socket has no facing: the Sites stage picks the approach as step 10 does.

`KINDS` gains `site`; `world.VERSION` becomes 2 (Req 1.2).

### How the World chooses them

In `generators/sites/points.py` (new; pure; `world_for` calls it inside the call so loading a
World still imports nothing from the generators), on its own stream:
`_salted_seed(seed, "sites", "points")` from the World's seed.

1. **Ground.** Placement's `_terrain` on the World's terrain with no Kept_Clear beyond the
   trees' own: Site-eligible quads (trees' Eligible_Ground, reached from Spawn, playable,
   dry) and their slope, height rank, clearing, water and zoneline distances. Per recipe
   slope, the eligible mask at that slope.
2. **How many.** `n_offer = max(2 * dense_top, 6)`, where `dense_top` is the Dense control's
   largest target on this ground: `ceil(band_high * DENSITIES["dense"] * area / 1e6)` (plains:
   `ceil(1.0 * 4.8) = 5` for a wilderness, so 10; `ceil(0.82)` = 1 for an outdoor dungeon, so 6).
   The World reads the biome's band, never the Sites control.
3. **Groups.** Draw a Group size from the biome's size shares (plains, from finding 1 at
   300 u: 1: 0.69, 2: 0.19, 3: 0.09, 4: 0.03, the 6 and 8 folded into 4 since no control asks
   for more than 5 Sites). Place its first point: a uniformly drawn spot in an eligible quad
   where at least one recipe fits (its `radius + margin` within the Free radius at its own
   slope; the loosest is the ruin, 40 u at 10°), at least `group_spacing` from every earlier
   Group's points (plains 600 u: stock's
   Group-centre NN p10 is 672 u, rounded down so a 1200 u outdoor dungeon holds two Groups).
   Then each further point of the Group: a spot at a distance drawn from the biome's
   within-Group NN band (plains 112–227 u) from a point of the Group, whose own smallest-outer
   disc keeps `CLEAR_WIDTH` from the others'. A point that can't be placed in 48 tries ends
   its Group.
4. **Until** `n_offer` points or no Group can start. On a hillside World, points over the
   Host_Hill's disc are allowed: the hillside Attachment's Kept_Clear removes the ones over the
   dungeon (question 3), so the World offers them last in its order (after every point off the
   hill) and lets them break `group_spacing` with each other, as spares.
5. Each point's `free`, `height_rank`, `clearing`, `water_d`, `zoneline_d` are read off step 1.

Time: step 1 is what the Sites stage computes today (Sites cost 0.81 s a wilderness in all,
world-sockets finding 1; the placement-only sweep of finding 2 ran 40 seeds in 3 s), and the
free-radius tests are a few thousand `disc_on_eligible` calls. Req 2.6 holds points to 0.1 s
a World; task 4 measures it, and if `disc_on_eligible` per point is too slow, a distance
transform of each slope's mask gives the radius to within half a quad.

### The clustering rules, as data

`rules/sites/biomes.toml` gains a block per biome, checked by the loader (`rules.py`):

```toml
[biomes.plains.groups]          # finding 1: 91 stock plains Sites, single linkage at 300 u
gap = 300                       # u: Sites this close are one Group
sizes = { 1 = 0.69, 2 = 0.19, 3 = 0.09, 4 = 0.03 }   # share of Groups
within = [112, 227]             # u: NN distance inside a Group, p10-p90
spacing = 600                   # u: least distance between two Groups' points
target_r = [0.50, 0.95]         # Clark-Evans R the built zones must measure inside
target_in_gap = [0.33, 0.65]    # share of Sites with another within `gap`
target_nn_p10 = [108, 190]      # u: pooled nearest-Site spacing p10
```

The targets ride with the biome so the band test reads them; a later biome (forest: R
1.04–1.73, no Groups) is a new block, not new code. Recipe `spacing` is retired (question 5).

## The Sites stage on points

`place_sites(terrain, ground, seed, ..., points)` (the World's `site` Sockets in rank order):

1. **Target**: `site_target` as now, from `rooms_seed`'s stream. On an outdoor dungeon at
   Normal or Dense, at least 1 (question 4).
2. **Usable points**: drop each point whose smallest-outer disc meets a `keep_clear` shape on
   the `ground` Socket (Req 3.3). The rest keep their Groups.
3. **Group order**: draw the next Group with a chance in proportion to its usable size (Req
   3.4, finding 2), take its points in rank order, then draw the next, until the target is met
   or no point is left.
4. **At each point**: draw the Inhabitant as now. Fitting kinds: `free[recipe.slope] >=
   radius + margin`, and the disc keeps `CLEAR_WIDTH` from every earlier Site's ground and
   margin. Draw the kind by `weight * (1 + likes)`, where `likes` is today's `_likes_score`
   read off the point's attributes, so a farmstead still leans to low ground and a shrine to
   high. No kind fits: pass the point over (recorded only if the Site finally drops, reason
   "no point fits its recipe").
5. **Then step 10 unchanged**, centred on the point: `_approach` (which now also refuses a
   direction that crosses an earlier Site's ground and margin, Req 3.7), `_Arranger`,
   `_poi_points`, drops.
6. The `Site` gains `socket: str`, the point's id.

The legacy `place_sites(land, ter, ...)` form goes: step 12 left only tests calling it, and a
point list needs a World. `_choose_centre` and recipe `spacing` go with it.

## The outdoor dungeon

- **Kept_Clear** (question 3): `stages.entrance_keep_clear` returns the dungeon's rooms (each a
  capsule along its long side, radius half its short side times √2, plus a margin) and its
  corridors (capsules of half-width plus a margin), the Tunnel and the Apron; no hill disc. The
  margin is `SITE_CLEAR` (8 u) plus 8 u, the 16 u finding 3 measured with. A Site may then stand
  on the hill's crown or shelf, never over a room. Rooms sit under the Rock_Cover (24 u) and
  Structures stand on the terrain, so the vertical gap is the Rock_Cover even at the edge.
  `outdoor_dungeon.keep_clear_shapes` (the duplicate, step 12 follow-up) is deleted and its
  pinning test with it.
- **Count** (question 4): the floor of one Site at Normal and Dense.
- **Points**: the World offers points over the hill as spares (above); after the rooms' Kept_Clear,
  the usable ones are what's left. Req 5.3 asks for a Site on 35 of the 39 planning seeds;
  finding 3 says ground for a camp exists on all 39, so a shortfall would be the World's
  sample missing it, which task 7 measures and, if short, fixes by offering more spares.
- **Trees** keep step 5's ground and keep off the Sites, as now.

## Seeds

| Draw | Seed | So that |
|---|---|---|
| Points (where Sites may stand, their Groups) | World `seed`, salt `("sites", "points")` | a rooms reroll keeps the World file, points included (Req 6.2) |
| Target, Group order, Inhabitant, kind, approach, arrangement | `rooms_seed`, `SITES_SALT` as now | "Reroll rooms" moves Sites among the World's Groups and redraws what they are |
| Trees | World `seed`, as now | trees move only near Sites |

With no `rooms_seed` set it is `seed`, as step 12. The bytes still move once (the stream's
draws change), which is the deliberate recapture of Req 7.2.

## Hand-offs

- **World v2** (`world.VERSION = 2`): `site` Sockets after `ground` in `sockets`. A v1 file is
  refused, named (Req 1.2). Every World corpus file is re-recorded (the version changes for
  dungeons and cities too; their Sockets don't).
- **Attachments v2** (`stages.ATTACH_VERSION = 2`): each Site in the `ground` Attachment's
  `sites` carries `socket`. A v1 file is refused, named.
- **Sidecar** `sockets`: one entry per point Socket (`kind: "site"`, its point, and in
  `attached` `{"kind": "site", "site": "<kind>", "group": g}` or `null`); the `ground` entry
  keeps `{"kind": "sites", "sites": n}`. The `sites` block's Sites gain `socket`. Existing
  keys keep their meaning (step 12 Req 6.3).
- **`scripts/stage.py`**: `world` marks point Sockets in its GLB (a small post per point,
  attached or not); `attach` reads v2.
- **`.rooms.json`** is unchanged in form; the Site RoomContexts move with the Sites.

## Holding the clustering target

- **Fast check** (Req 4.4): over a fixed list of wilderness seeds, Worlds and the Sites stage
  only (`world_for` + `attach_sites`; 40 seeds took 3 s for finding 2), R pooled, the "in 300"
  share and NN p10 inside the biome's targets. Not `slow`.
- **Band check** (`tests/test_site_bands.py`, `slow`): the built, read-back zones of seeds
  1000–1039 at Normal measured by the survey's code against the biome's `target_*` (plains),
  replacing `STOCK_R` (all-zone) and `SPACING_P10` (all-zone 130–490) in the asserts: clustered
  plains Sites put spacing p10 near stock plains' 108–190, below the all-zone floor of 130.
  The all-zone bands stay printed. Sites per 1e6 u² and Structures per Site keep step 10's
  bands. `test_stock_r_band` grows a per-group check that reproduces finding 1's plains band.
- **Per biome**: the test reads the targets from `biomes.toml` for each biome that has Site
  rules, so a new biome brings its own band.

## The gate and first try

- **Sites closer together.** A Group's points are 112–227 u apart; each Site's ground and
  margin keep `CLEAR_WIDTH` (8 u, the gate's clear width) from the others', and approaches
  keep off other Sites' grounds (Req 3.7), so the ground between two Sites stays a way through.
  The gate's Footprint check is unchanged; it judges.
- **Outdoor dungeons gain Sites** on about 30 more of 39 seeds, on the hill. The gate's
  reached-ground and POI checks now see Structures near the Mouth's approach; the Apron and
  Tunnel stay Kept_Clear, so the way in is as today.
- **Measured, not assumed**: Req 8.1's sweep (wilderness 40 seeds, outdoor 39 seeds, Normal
  and Dense) against step 12's numbers, before and after, in task 11's commit body. Step 10
  recorded 40/40 at Normal for the wilderness (its archive, its task 11).
- **Step 12's stage reroll** (decision 5) blames Decor or rooms; a Site's Footprint failure
  names neither, so it draws a fresh `seed`, as today. Naming the Sites stage is question 8.
- **Pinned acceptance cases** for steps 10 and 12 that build Sites will look different; task
  13 re-checks them and says which changed.

## Bytes

| Build | Changes? |
|---|---|
| Dungeon, city | No (no terrain, no points) |
| Wilderness or outdoor dungeon, Sites `none` | No: step 9's bytes (`test_site_builds.py` STEP9) |
| Wilderness or outdoor dungeon, Sites on | Yes (wilderness at task 6; outdoor dungeons at tasks 6 and 7): Sites, Site models, trees near them; `test_layout_engine.py` wilderness and outdoor-dungeon `.eqg` hashes (their spec hashes stay), STEP10 Site goldens, Site-decor goldens, the room corpus's Site recordings |
| Any Zone_Spec JSON | No |
| World files, Attachments files | Yes: versions 2, points added |

## Testing

- `tests/test_site_points.py` (new): points from hand-built and corpus Worlds: on eligible
  ground with their stated Free radius true (P2), Groups inside `gap` and `within`, Groups
  apart by `spacing`, the same text for the same World, no Site control read (patched to raise).
- `tests/test_attach_ground.py`: the Sites stage on corpus Worlds: each Site on a point,
  no point under Kept_Clear used, kinds fit, approaches clear (P3–P5); the outdoor dungeon's
  Kept_Clear is its rooms, corridors, Tunnel and Apron (P7).
- `tests/test_world_corpus.py`: the corpus covers points, Groups of 2+, and a hillside World
  with points over the hill.
- `tests/test_site_bands.py`: the clustering target, fast and slow (above), and the gate's
  first try.

## Correctness properties

| # | Property | Req |
|---|---|---|
| P1 | A `site` Socket and a v2 World round-trip exactly; v1 Worlds and Attachments are refused, named | 1, 6.3 |
| P2 | Every point stands on Site-eligible ground and its `free` radii are true at their slopes | 2.2 |
| P3 | Points form Groups within `gap`, at `within` spacing, Groups `spacing` apart; same World, same text; no Site control read | 2.1, 2.3, 2.5 |
| P4 | Every Site stands on a point, its kind fits that point, its ground keeps `CLEAR_WIDTH` from every other Site's, its approach crosses none | 3.1–3.3, 3.7 |
| P5 | Sites `none` attaches nothing; step 9 bytes | 3.8, 7.1 |
| P6 | A new `rooms_seed` keeps the World text and moves Sites only among its points | 6.1, 6.2 |
| P7 | No Site, Structure or Site_Clear over an outdoor dungeon's room, corridor, Tunnel or Apron | 5.1, 5.4 |
| P8 | Outdoor dungeons at Normal get a Site on 35+ of the planning seeds 0–39 | 5.2, 5.3 |
| P9 | Built plains zones inside the plains clustering target; step 10's count bands hold | 4 |
| P10 | Gate first try no worse; Sites within 5 s | 8 |

## Risks

- **Two Sites is a small sample.** At Normal a zone holds 1–3 Sites, so R pooled moves with
  a handful of pairs. The "in 300" share is the steadier measure; Dense's median zone is the
  third. If R pooled lands just outside the band while the other two are in, that's a call for
  the user, not a reason to over-tune the Group sizes.
- **Kind mix drifts.** Kinds now draw from those that fit a given point, weighted by likes:
  big recipes (farmstead, outer 100 u) lose ground they found before. Step 10's mix (48 % of
  Sites one Structure, stock 51 %) is checked by the Structures-per-Site band; task 5 prints
  the kind counts before and after.
- **The World now reads Site rules.** Points need the recipes' slopes and smallest outer, and
  the biome's Group rules. They are World inputs in the same sense as the biome kit; the Sites
  control and Inhabitant still never reach the World (Req 2.1). A change to a recipe's ground
  moves every landscape World once.
- **Hidden reads.** `place_sites` must read points only from the `site` Sockets. A test that
  patches `points.site_points` to raise during the Sites stage catches a recompute.
- **Outdoor dungeon Sites on the hill.** A Site on the crown may sit in view of the Mouth and
  read as guarding it (good) or crowd the approach (bad). The first look judges.
- **Cross-branch hotspots**: `generators/stages.py`, `generators/world.py` and
  `generators/wilderness/build.py` are touched by several tasks; `Depends` sequences them.
  `pipeline.py`, `main.py` and `server/app.py` are not touched.

## Open questions

These go to the user. Each has options and a recommendation; the requirements and tasks are
written for the recommendations.

1. **Who makes the clustering: the World's points, or a "near another Site" like in today's
   Sites stage?**
   - (a) The World offers point Sockets in Groups; the Sites stage builds on them.
   - (b) Keep the area Socket; add a like that scores spots near an earlier Site, and drop the
     recipe spacing. Smaller (one file), but the World offers no points, a Site's spot is still
     chosen in the Sites stage, and the outdoor-dungeon case is untouched.
   *Recommended: (a).* It is what step 12 named this step for (decision 2), it puts "where a
   Site may stand" in the World as the user's aim asks, and Groups are a direct copy of stock's
   hamlets (finding 1) rather than a weight tuned until R comes out right.

2. **Does "Reroll rooms" move the Sites?**
   - (a) No: points and their order come from the World seed; a reroll keeps where Sites stand
     and redraws only what they are.
   - (b) Yes, among the World's points: the World offers spares, and the Group order is drawn
     from `rooms_seed`.
   *Recommended: (b).* Step 12's first look checked that a rooms reroll gives "new Sites on the
   same ground"; (b) keeps that while the ground stays the World's. Spares also let the
   outdoor dungeon drop points under its rooms.

3. **What does an outdoor dungeon keep Sites off?**
   - (a) As today: the hill's 400 u disc, Tunnel and Apron (at 8°, a ruin fits on 13 of 39
     seeds, a hut on 7).
   - (b) The Landform's radius, 250 u, Tunnel and Apron (a ruin on 28, a hut on 15).
   - (c) The dungeon's own rooms and corridors plus 16 u, Tunnel and Apron (a camp on 39 of
     39).
   *Recommended: (c).* The hill disc stood in for "where the dungeon is" before the rooms were
   known at Site time; since step 12 they are. It changes step 10's Req 7 wording ("keep the
   Host_Hill clear" becomes "keep the dungeon under it clear"), recorded in `archive.md`.

4. **How many Sites does an outdoor dungeon get?**
   - (a) Stock's density on its ground: a target of 0.33 at Normal, a Site on about a third of
     seeds even with room.
   - (b) At least one at Normal and Dense, when a point fits; Sparse draws as now.
   - (c) As (b), plus a point the World always offers by the hill's approach foot (a camp by
     the way in).
   *Recommended: (b).* Stock density is measured on 10–114e6 u² zones; a 1.2 km zone built
   round a dungeon is a set piece, and one Site there is what the step 10 follow-up asked for.
   (c) needs the Apron's place, which the World doesn't know (step 12 decision 1).

5. **The recipes' `spacing` field?**
   - (a) Retire it: the Groups set spacing (within 112–227 u, Groups 600 u apart), and every
     Site keeps `CLEAR_WIDTH` from the next one's ground.
   - (b) Keep it as a least distance to a Site of another Group, per kind.
   *Recommended: (a).* Its 200–400 u is what keeps today's Sites from grouping, and Groups
   already keep hamlets apart. The loader refuses the field afterwards, so a stale recipe
   says so.

6. **Which clustering target, and per biome?**
   - (a) Per biome, in `biomes.toml`: plains 0.50–0.95 R, 33–65 % within 300 u, NN p10 108–190 u;
     the other biome groups measured (finding 1) and recorded for when their rules come.
   - (b) Keep the all-zone band (R 0.64–1.64) as the assert.
   *Recommended: (a).* Today's 1.45 already passes (b); a target it already meets can't fix
   the defect. Stock splits cleanly (clustered plains and swamps, dispersed forests and
   deserts), so one band for all would be wrong for every biome.

7. **Show the unused points on the map?**
   - (a) Every point: attached ones filled, unused ones hollow, each tooltip naming its Group.
   - (b) Only the points a Site took.
   *Recommended: (a)*, and have `mapview.py` write its world-to-pixel frame on the SVG so the
   markers stop inferring it (step 12 follow-up). Unused points are what a reroll can choose;
   seeing them explains the reroll.

8. **Should a gate failure caused by a Site reroll only the Sites (their `rooms_seed`)?**
   - (a) Not in this step: a Site failure draws a fresh `seed`, as step 12 does.
   - (b) Yes: name the Sites stage from a failing Footprint or POI (`site<i>:`), redraw
     `rooms_seed`.
   *Recommended: (a).* Step 10 measured 40/40 first try at Normal; a Site failure is rare, and
   (b) touches `pipeline.py`'s retry helpers, a hotspot. Revisit if task 11's sweep shows Site
   failures.
