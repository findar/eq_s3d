# Design — zone-generator-wilderness-pois (roadmap step 10)

Written at master `28b6781`. Verify against the code before working a task.

## Overview

```
rules/sites/*.toml ── biome x Inhabitant -> Weights over Site kinds; recipes; materials
                                     │
landscape (matrix, heightfield, water, bowl; nothing below changes it)
                                     │
site placement ── own salted stream; eligible ground: playable plains, slope <= recipe,
                  outside Kept_Clear, spaced; likes score candidate spots
                                     │
arrangement ── ring, row, cluster, lone, perimeter: proposes Structure spots;
               each must keep its Site_Clear, or it's dropped
                                     │
trees ── Kept_Clear grows by every Site's ground (trees are placed after Sites)
                                     │
models ── one site_<kind>.mod per Structure kind and variant; one ZON object each
                                     │
walk gate ── learns Footprints FIRST (task 2)     sidecar ── Sites, POIs, drops
```

Sites come after the landscape and before trees, from their own stream, so terrain never
moves and `none` is exactly the step 9 build (Req 4.4, 9.2).

## Research findings

### 1. Stock wilderness places (probe at design time; task 1 makes it a survey)

The placed objects (`objects.wld` instance fragments, 0x15) of 14 Classic outdoor zones,
read with `scripts/room_feature_survey.placed_objects`. Commonest objects per zone, trees
first:

| Zone | Objects | Trees and plants (by name) | What makes the places |
|---|---|---|---|
| qeytoqrg | 383 | 363 | QOUTPOST, HOUSE1, SHAK, CAMPFIRE ×3, MILESTONE1, a flag |
| northkarana | 1933 | 1866 | BARN1 ×4, RHOUSE1 ×3, HAYBALE ×11, CAMPFIRE2 ×2, rocks |
| eastkarana | 1446 | 1350 | HOUSE1 ×6, CORRALL ×3, BUNK1, lamp posts |
| southkarana | 3790 | 3695 | CENLEANTO ×7, CENTFIRE ×5, CENFLAG, BURIAL ×13, CARMORY2 |
| ecommons | 1809 | 1531 | COMHOUSE ×15, WOODSUPPORT ×12, dunes |
| nro | 345 | 178 | DTOW1–3 ×42, DESTENT ×6 |
| sro | 810 | 678 | DTOW ×52, CAMPFIRE ×16, ORCTENT1 ×8, BTENT1 ×7, GOBTENT ×7 |
| butcher | 1884 | 1596 | BTOW ×59, KALHSE1 ×14, CAMPFIRE ×25, TIKI ×12, DWMONU ×12 |
| everfrost | 675 | 348 | IGLOO ×11, HALMOUND ×17, PERBRICK ×25, many rocks |
| gfaydark | 2829 | 2323 | LEANTO3 ×13, furniture of the tree city |
| feerrott | 2088 | 1961 | LIZTENT ×21, CAZMON2 ×15 |
| innothule | 1937 | 1920 | TRLEANTO ×6, CAMPFIRE ×4, MTOWER |
| oasis | 247 | 119 | DTOW ×57, BTENT1 ×6, CAMPFIRE ×7, MCIRCLE ×4, MONU4 ×4 |
| qeynos2 | 480 | 160 | a town: lamps, chairs, crates, tables |

What it says:

- **Places are placed objects**, like trees. Buildings, tents, towers, fires and monuments are
  instances; the terrain under them is ordinary ground. So a Site is models on the ground, and
  the TER need not change.
- **Who lives there decides the look.** Centaur lean-tos and flags, orc and goblin tents, igloos
  and halfling mounds, lizardman tents, Freeport's houses: each is its own model set. That is
  the Inhabitant.
- **Camps are the commonest Site**: a fire with tents or lean-tos round it, in nearly every
  zone. Farms (house, barn, corral, haybales) are the Karanas' signature. Towers (DTOW, BTOW)
  stand alone or in twos. Monuments and burial mounds mark shrines.
- **Many Structures are furnished**: chairs, bunks, tables, crates sit with them. That half
  is step 11.
- What the probe can't see: places in the terrain mesh (walls, ruins, a hut built into the
  zone), and which object belongs to which Site. Task 1 clusters the objects and plots them.

### 2. What the code already offers

- `POIAnchor` (name, x, y, is_spawn, intent): grows a `kind` and stays XY only, Z from the
  surface.
- Step 2's path: `generators/vegetation/` builds models from the Zone_Spec; `builder.py`
  packs them and writes one ZON object each; `bowl_report` runs `trees_block`, which removes
  each trunk disc grown by the player's half-width and checks the ground stays joined to Spawn.
  A Footprint is the same idea for a shape that isn't a disc.
- Kept_Clear (`vegetation/placement.py`): Spawn clearing, zoneline approaches, shores.
- Step 9's checked-TOML loaders and POI type (`generators/room_layouts.py`), and its
  rule tooling (`scripts/topology_rules.py`).

## Sites

A Site is placed in three moves: **where** (a centre on eligible ground, scored by the
recipe's likes), **what** (the recipe's Structures, arranged round the centre), and **keep
clear** (its Site_Clear: an approach from the zone's open ground, a clear apron in front of
each opening, and a margin). Kinds in v1, from finding 1:

| Kind | Structures | Arrangement | Ground |
|---|---|---|---|
| camp | fire ring, 2–5 tents or lean-tos | ring round the fire, openings inward | flat, often near water |
| hut | one Enterable hut, maybe a fence run | lone | flat |
| farmstead | house, barn, corral fence | cluster, corral on the open side | flat, wide, low ground |
| watchtower | 1–2 solid towers | lone or pair | high ground, a view of a zoneline |
| shrine | standing stones or a monument round an altar stone | ring | high ground or a clearing |
| ruin | broken wall runs round a court | perimeter, gaps for the way in | any |

## Structures

Low-poly models in the Classic recipe (task 1 sets the counts). Walls are thin closed slabs,
roofs are passable above head height where they overhang, and every model is buried by a
skirt as trunks are. An Enterable model has no floor of its own: its floor is the terrain,
so the walk surface inside is the ground's, and the gate needs only the walls. A tower is
solid in v1. Each Inhabitant names a material set and, where it differs, a variant (a hide
tent vs a canvas one).

## The gate

The Footprint check replaces `trees_block`: rasterise the reached ground, remove every
collidable triangle below head height that a player's half-width would touch (taken from the
models in the archive, placed by their ZON objects), and the ground joined to Spawn must not
lose anything but the Footprints themselves. Enterable openings are measured from the model:
the gap in its walls at ground level must be at least the clear width, under a lintel at least
head height. A trunk is a Footprint, so tree-only zones give the same answer (Req 2.2).

## Site recipes as data

```
rules/sites/
  sites.toml        kinds: structures, arrangement, ground, likes, POIs
  inhabitants.toml  per Inhabitant: material set, variants, Weights over kinds
  biomes.toml       per biome: the Inhabitant mix, and Weights over kinds
```

Weights multiply by Layer (biome x Inhabitant x control), as step 9's Scales do, and a kind's
chance is its weight over the sum. The loader checks every field, and the rule tooling
draws a recipe's plan for review.

## Controls and sidecar

`sites` (none, sparse, normal, dense) scales the target count from finding 1's band;
`inhabitants` is "" (the biome's mix) or one Inhabitant. The sidecar gains `sites`: each
Site's kind, Inhabitant, centre, Structures (kind, position, yaw), POIs, and what dropped and
why. The EQ map draws Footprints as lines and each Site as a label; the web map draws a marker
and the Footprints.

## Correctness properties

| # | Property | Req |
|---|---|---|
| P1 | A cutting Footprint, a narrow or low opening, an unreached interior, an unreached POI: each fails, named | 2.1 |
| P2 | Footprint check equals `trees_block` on tree-only zones | 2.2 |
| P3 | Every model closed where solid, round-trips exactly, opening at least clear width and head | 3 |
| P4 | Sites only on eligible ground, spaced; Structures inside, Site_Clear free of Structures and trees; misfits drop | 4.1–4.3 |
| P5 | Terrain identical across Site densities; `none` matches step 9 bytes | 4.4, 9.2 |
| P6 | Site files: every bad value named; every kind has a recipe; weights are weight over sum | 5 |
| P7 | Every Site has a POI; every POI on reached ground | 6 |
| P8 | Outdoor dungeons keep Apron, Tunnel, Mouth and Host_Hill clear; step 5 holds | 7 |
| P9 | Built zones in the survey's bands | 9.1 |
| P10 | Dungeon and city goldens unchanged; same inputs same `.eqg`; time within step 9 + 5 s | 9.2–9.4 |

## Risks

- **Furnished Sites read bare.** Stock places are half furniture. Until step 11 a camp is tents
  and a fire; it may read thinner than stock whatever this step does.
- **Models are the look.** Trees passed on silhouettes; a hut is looked at close. Low-poly
  done badly reads as boxes. Task 9's look is early for that reason.
- **The gate's raster.** The Footprint check rasterises at a step; thin walls must not slip
  between samples, and a door gap must not close up at the raster's grain.
- **Plains only.** One biome means Inhabitant variety carries the variety. Deserts and snow
  (towers, igloos) wait for their biomes.
- **Placement reads as random.** A camp in the middle of nowhere looks dropped. Likes (water,
  high ground, a zoneline) are what make a place read as chosen.

## Open questions (waiting on the user)

1. **Terrain under a Site: leave it, or flatten a pad?** *Recommended: leave it. Pick ground
   already flat enough and bury a skirt, as stock does; the TER never changes, so every earlier
   guarantee holds and `none` is trivially the old bytes. Flattening is a follow-up if a look
   says Sites sit badly.*
2. **Enterable Structures in v1?** *Recommended: yes, for huts, lean-tos and ruins, with the
   ground as their floor. Towers stay solid: no upper floors or ladders.*
3. **Which kinds?** *Recommended: camp, hut, farmstead, watchtower, shrine, ruin, from finding 1.*
4. **Which Inhabitants?** *Recommended: human, orc, gnoll, centaur for plains: the Karanas'
   own. Others come with their biomes.*
5. **The line with step 11.** *Recommended: step 10 is a Site's Structures (buildings, tents,
   fire rings, fences, towers, stones). Furniture and loose props, haybales included, are step
   11, which can fill a Site's POIs.*
6. **A Sites control and an Inhabitants control?** *Recommended: yes, both, as Trees and
   Features have density.*
7. **Roads between Sites?** *Recommended: not in this step. Stock Karanas have roads; they change
   the terrain's texture and want their own step.*
8. **Light at a camp fire?** *Recommended: no light in v1; the fire is a model, and a Light_Spot
   POI marks it for later.*

## Decisions

1. Sites are placed objects on unchanged ground, through step 2's model and ZON path.
2. The way through stays clear by construction (Site_Clear) and the gate checks Footprints
   independently, from the models themselves.
3. Recipes, Inhabitants and biome weights are checked TOML data under `rules/sites/`.
4. POIs are advisory: sidecar only.
