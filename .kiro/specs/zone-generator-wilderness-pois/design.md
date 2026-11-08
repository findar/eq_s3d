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

### 1. Stock wilderness places (task 1's survey: `scripts/site_survey.py`)

The placed objects (`objects.wld` instance fragments, 0x15) of 14 Classic outdoor zones,
read with `scripts/room_feature_survey.placed_objects`. The design-time probe, commonest
objects per zone, trees first (DTOW and BTOW turned out to be rock, see below):

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

**The survey.** `python scripts/site_survey.py --eq-path F:\everquest_rof2` reads 24 Classic
outdoor zones (West Karana is `qey2hh1`). It names each object by pattern (`kind_of`): tree,
rock, a Structure kind (fire, lean-to, tent, tower, hut, house, ruin, fence, stone, dock), or
prop. A **Site** is a single-linkage cluster of Structures and props no more than 100 u apart
(`cluster`), holding at least one Structure. Ground is the walkable network's dry plan area on
a 16 u raster; lake and sea beds are walkable but left out. Zonelines and water are the zone's
`DRNTP` and `WT` BSP regions. `--plots DIR` draws each zone. Task 11 imports `kind_of`,
`cluster`, `site_measures` and `measure_model`.

Per zone (p50/p90 unless marked; ground in 1e6 u^2; distances in u; slope in degrees):

| Zone | Ground | Sites | Per 1e6 | Structs | Radius p50 | Spacing p50/p10 | Zoneline | Water | Slope |
|---|---|---|---|---|---|---|---|---|---|
| qeytoqrg | 15.4 | 6 | 0.4 | 1/2 | 6 | 896/173 | 1462 | 1417 | 7.8/20.2 |
| qey2hh1 | 114.3 | 43 | 0.4 | 2/4 | 0 | 192/108 | 4800 | 1338 | 3.5/7.2 |
| northkarana | 50.9 | 17 | 0.3 | 1/2 | 0 | 671/181 | 2115 | 1824 | 0.0/4.5 |
| eastkarana | 36.3 | 17 | 0.5 | 1/4 | 41 | 196/160 | 3911 | 984 | 1.0/14.4 |
| southkarana | 90.3 | 8 | 0.1 | 3/10 | 93 | 222/191 | 4359 | 2058 | 0.9/4.7 |
| lakerathe | 17.4 | 36 | 2.1 | 1/4 | 21 | 201/132 | - | - | 12.6/34.1 |
| rathemtn | 65.1 | 30 | 0.5 | 1/5 | 22 | 697/128 | - | - | 3.5/10.9 |
| ecommons | 17.5 | 18 | 1.0 | 2/4 | 50 | 626/288 | 1131 | - | 0.0/10.0 |
| nro | 16.1 | 17 | 1.1 | 1/3 | 0 | 434/256 | 1104 | 1291 | 2.3/27.3 |
| sro | 11.4 | 20 | 1.8 | 3/5 | 37 | 615/448 | 1410 | - | 0.4/6.8 |
| oasis | 11.0 | 16 | 1.5 | 3/6 | 42 | 488/233 | 1112 | 343 | 1.1/49.9 |
| tox | 11.5 | 12 | 1.0 | 1/3 | 44 | 602/417 | 3433 | 504 | 7.1/15.7 |
| steamfont | 14.6 | 11 | 0.8 | 2/6 | 34 | 414/182 | - | - | 0.8/6.0 |
| lfaydark | 17.3 | 15 | 0.9 | 3/5 | 43 | 791/481 | 1954 | - | 0.7/2.9 |
| kithicor | 16.5 | 17 | 1.0 | 1/2 | 26 | 531/226 | - | - | 5.6/11.0 |
| nektulos | 11.2 | 7 | 0.6 | 1/2 | 0 | 1046/607 | - | 560 | 8.5/22.9 |
| innothule | 10.1 | 10 | 1.0 | 1/3 | 4 | 188/140 | - | 345 | 8.1/22.8 |
| feerrott | 17.8 | 34 | 1.9 | 2/5 | 36 | 264/148 | - | - | 4.4/11.6 |
| everfrost | 39.4 | 29 | 0.7 | 1/3 | 0 | 305/197 | - | - | 0.1/17.0 |
| cauldron | 9.7 | 4 | 0.4 | 2/2 | 24 | 1282/1232 | - | - | 5.6/11.8 |
| beholder | 1.5 | 0 | 0.0 | - | - | - | - | - | - |
| *butcher* | 21.3 | 34 | 1.6 | 2/5 | 38 | 718/251 | 4685 | 2419 | 1.3/12.0 |
| *gfaydark* | 23.3 | 21 | 0.9 | 3/8 | 68 | 226/104 | 899 | - | 11.1/34.4 |
| *erudsxing* | 0.5 | 9 | 17.4 | 1/3 | 0 | 196/150 | - | 5 | 10.2/15.2 |

Italic zones are towns (Kaladim's and Kelethin's halls, Kelethin's platforms, a ferry island)
and stay out of the bands. "-" means none: 11 zones have no `DRNTP` region (their zonelines
are server-side only), and many have no water region.

**Bands** (over the 21 kept zones, p10-p90 of the per-zone values):

| Measure | All 21 zones | Plains (North, East, South and West Karana, Qeynos Hills) |
|---|---|---|
| Sites per 1e6 u^2 | 0.3-1.8, median 0.8 | 0.1-0.5 |
| Structures per Site, zone p50 | 1-3 | 1-3 |
| Structures per Site, zone p90 | 1.8-5.6 | 2-10 |
| Spacing, zone p50 | 195-910 | 190-900 |
| Spacing, zone p10 | 130-490 (closest pair anywhere 108) | 108-190 |
| Site radius, zone p50 / p90 | 0-45 / 35-120 | 0-93 / - |
| Slope under a Site, p50 / p90 | 0.1-8.1 / 4.7-28 | 0-7.8 / 4.5-20 |
| To water, zone p50 | 345-1850 | 980-2060 |

Of 367 Sites, 51% are one Structure, 44% are 2-5 and 5% are 6 or more. Plains are the
sparsest ground: about one Site per 2.5e6 u^2, where lake and desert zones hold two or three
times that. Step 10 builds plains only, so task 5's Normal should aim at 0.3-0.5 and Dense at
the all-zone median, about 0.8. Sites sit on gentle ground (slope p50 under 8 degrees in every
zone) and are not drawn to zonelines or water: both are 1000 u or more away at the median.

**What the plots changed.**

- **DTOW and BTOW are rock spires, not towers.** The models are 230-450 u across and 300 u
  tall, and they line the Ro deserts' and Butcherblock's edges. They're scenery now. Real
  towers are rare: EKTOWER, ELFTOWER and MTOWER, 21 placed in all, none on the plains. So
  the watchtower kind is weakly supported by stock; task 5 should give it a small Weight.
- **HALMOUND is a snow mound** (4 u tall, all passable), not a halfling house: scenery.
  PERBRICK is rubble round Permafrost's door: a ruin.
- **The gap is 100 u.** At 60 u a farmstead split in three: a house, barn and corral stand
  60-150 u apart, origin to origin. At 150 u neighbouring camps joined.
- The centaur camp in South Karana is one Site of 10 Structures; most others are 1-5.

**Stock Structure models** (from `<zone>_obj.s3d`, at the commonest placed scale; size in u;
"solid" is the collidable share of area; "walk-in" is reached floor under a roof or inside
walls, at least 25 u^2):

| Kind | Models | Tris | Plan (w x d) | Height | Solid | Walk-in |
|---|---|---|---|---|---|---|
| fire ring | CAMPFIRE, CAMPFIRE2, CENTFIRE | 44-80 | 6x6 to 10x12 | 5-7 | 33-64% | no |
| tent | BTENT1, ORCTENT, ORCTENT1, GOBTENT, LIZTENT, GTENT1-3, DESTENT | 20-110 | 14x11 to 58x35 | 18-27 | 96-100% | yes, all |
| lean-to | LEANTO, LEANTO3/5/6, CENLEANTO, TRLEANTO | 32-60 | 15x14, 23x20 | 11-17 | 0-100% | yes, all |
| hut | HUT1/2/4/5/6, SHAK, IGLOO | 48-92 | 21x21 to 52x38 | 18-32 | 100% | yes, but SHAK |
| house | HOUSE1/2, RHOUSE1, COMHOUSE, KIHOUSE, KALHSE1, OGHOUSE, ERHOUSE | 80-219 | 40x27 to 120x118 | 23-52 | 100% | about half |
| barn | BARN1 | 72 | 92x69 | 65 | 100% | yes |
| tower | EKTOWER, ELFTOWER, MTOWER | 42-254 | 40x40 to 62x62 | 66-106 | 100% | no |
| fence | CORRALL (a ring), WOODSUPPORT, POST | 12-288 | 46x43 ring; posts 3x3 | 7; posts 19 | 0-100% | no (WOODSUPPORT's beam reads as a roof) |
| standing stone | MONU1/4/6, DWMONU, ORCTOTEM, TIKI, MILESTONE3 | 28-52 | 2x2 to 15x15, MONU6 6x37 | 9-45 | 0-100% | no |
| monument | MONU3, MONU7, CAZMON1/2, DOLMEN | 39-216 | 20x20 to 98x89 | 34-125 | 100% | MONU3, DOLMEN |
| burial mound | BURIAL, BURIAL1/2 | 60-72 | 13x9 to 28x21 | 10-16 | 100% | BURIAL, BURIAL1 |
| ruin | COMRUIN, KIHRUIN | 52-70 | 46x35, 130x127 | 26-37 | 100% | COMRUIN |

Every Structure is under 400 triangles; most are 30-220. Tents and huts are about 30 u
across and 20-30 u tall; a house about 50x35 and 35 u tall. Some sit deep: the dock, HUT2,
QOUTPOST and the elf towers go 29-50 u below their origin. Two things to know for task 3:

- **Stock flags are loose.** LEANTO, LEANTO3 and TRLEANTO are all passable (0% solid);
  LEANTO5 is 93% solid. TIKI and POST are passable too. Ours will be solid where it stands
  in the way (Req 3.2), so they'll block more than stock does.
- **Many stock houses are closed shells** (HOUSE1/2, COMHOUSE, KIHOUSE, KINN): no gap a player
  fits through. Their doors are server-side door records. Huts, tents, lean-tos, barns and
  RHOUSE are open.

**What the survey can't see.**

- **Spawn.** Stock safe points live in the server's database, not the client files. Zonelines
  stand in for arrival, and only where the zone has `DRNTP` regions (13 of 24).
- **Places in the terrain mesh.** Walls, ruins and halls built into the zone (Kelethin's
  platforms, Kaladim's gate, Halas's walls) aren't objects, so they're not Sites. Beholder's
  gorge has none at all.
- **Objects it can't name**: FAYBAR1/2 (Kelethin), CAULCOL1-3 and CAULROOF (Dagnor's
  Cauldron's columns). They join Sites as props. Animated objects (flags, with no static
  mesh) are props and aren't modelled.
- Doors: they're server records, so a closed house's way in doesn't show.

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
| camp | fire ring, 2–5 tents or lean-tos | ring round the fire, openings inward | flat (stock camps are not drawn to water, finding 1) |
| hut | one Enterable hut, maybe a fence run | lone | flat |
| farmstead | house, barn, corral fence | cluster, corral on the open side | flat, wide, low ground |
| watchtower | 1–2 solid towers | lone or pair | high ground; rare in stock (finding 1), so a small Weight |
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

## Open questions (answered 2026-11-07: every recommendation taken, see `archive.md` "Decisions")

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
