# Design — zone-generator-room-decor (roadmap step 11)

Written at master `e50ecfc`. Verify against the code before working a task.

## Overview

```
rules/decor/*.toml ── Prop_Kinds; Decor_Recipes by type, kind, race, theme; Material_Sets
                                     │
room geometry (steps 6-9: outline, walls, Features, Spine; nothing below changes it)
                                     │
dressing ── each POI's Dressing first (throne at boss, candles at altar)
                                     │
decor placement ── own salted stream; floor Props off the Spine, Throats and Features;
                   wall Props on wall faces clear of doors; ceiling Props where it's high
                                     │
groups ── table + chairs, bunk rows, crate piles: placed whole or dropped whole
                                     │
models ── one prop_<kind>_<variant>_<set>.mod per kind in use; one ZON object per Prop;
          one ZON light per light-bearing Prop
                                     │
walk gate ── learns placed models in room builds FIRST (task 2)   sidecar ── Props, drops
```

Props come after all room geometry, from their own stream, so geometry never moves and Decor
`none` is exactly the step 10 build (Req 5.4, 11.2).

## Research findings

### 1. What fills stock rooms (design-time probe; task 1's survey refines it)

The placed objects (`objects.wld` instance fragments, 0x15) of step 9's 15 dungeons and 15
cities, read with `scripts/room_feature_survey.placed_objects`, named by pattern (digits
stripped). The commonest per zone:

| Zone | Objects | Rooms | Commonest |
|---|---|---|---|
| blackburrow | 283 | 36 | TORCH ×78, BONES ×40, BLOODYPUNGEE ×28, BARREL ×13, PAWTABLE ×5 |
| paw | 344 | 32 | TORCH ×99, PAWROCK ×89, PAWBRICK ×48, PAWBARREL ×25, PAWPAL ×24, PAWHOOK ×23, PAWTABLE ×14 |
| crystal | 447 | 21 | CCROCK ×172, VELIUMCRYSTALS ×164, CCTORCH ×13, MISTWEBS ×10, CCBRAZ ×9 |
| runnyeye | 648 | 17 | TORCHPOINT ×225, SLIMEPILE ×44, BARREL ×42, CHAIR ×26, PAWTABLE ×15, URN ×14 |
| soldungb | 337 | 18 | TORCHPOINT ×59, STEAM ×47, FURPILE ×36, WEB ×27, KEG ×13, BRAZIER ×11, CANDELABRA ×8 |
| soldunga | 461 | 15 | TORCHPOINT ×129, TORCH ×87, BENCH ×21, CRATEA ×19, KEG ×15, DARKTABLE ×13, GOBDIVAN ×10 |
| permafrost | 502 | 29 | PERROCK ×255, PERTORCH ×119, PERBRICK ×21, PERSTAL ×17, PAWHOOK ×15 |
| kaesora | 396 | 20 | KSROCK ×202, KSTIKI ×39, KSLIGHT ×23, KSBOKPILE ×20, KSBOOK ×14, KSPEW ×14, KSSTATUE ×11 |
| guktop | 395 | 13 | OGGLANTERN ×107, MUSHROOM ×73, GUKBRAZIER ×26, GUKCHAIR ×25, GUKPLNK ×25, GUKTABLE ×15 |
| najena | 414 | 22 | BONEPILE ×77, PAWHOOK ×72, BONES ×48, STONEBENCH ×26, HPCHAIN ×21, PALLET ×11 |
| gukbottom | 482 | 10 | OGGLANTERN ×209, MUSHROOM ×64, GUKBRAZIER ×31, LADDER ×16, GROBCAGE ×13 |
| sebilis | 501 | 44 | CBTORCH ×121, CBTIKI ×69, SBROCK ×68, SBSHAKLE ×32, CBPILLAR ×24, SBTABLE ×18, SBBOOK ×13 |
| qcat | 93 | 5 | TORCHPOINT ×48, BONES ×14, BOOKCASE ×6, CHAIR ×4, RECTTABLE ×4, CANDLE ×4 |
| befallen | 346 | 24 | BHROCK ×112, BONEPILE ×84, STONEBENCH ×30, URN ×29, PAWHOOK ×20, BOOKCASE ×4 |
| kurn | 267 | 40 | KNTORCH ×53, CBTORCH ×45, CBCRATE ×40, CBBARREL ×26, VEBRAZ ×19, DNBUNK ×16 |
| qeynos2 | 480 | – | TREE ×160, TORCHPOINT ×46, HLAMP ×36, CHAIR ×33, LIGHTPOLE ×23, CRATEA ×19 |
| qeynos | 476 | – | LIGHTPOLE ×51, HLAMP ×46, CHAIR ×39, BED ×31, RUG ×26, BARSTOOL ×17 |
| freportw | 758 | – | HLAMP ×146, LIGHTPOLE ×86, CHAIR ×51, BARREL ×38, BOOKCASE ×20, DRAWER ×19, BED ×19 |
| freportn | 556 | – | HLAMP ×120, BED ×51, CHAIR ×46, BENCH ×25, DRAWER ×21, DRESSER ×14 |
| neriaka / neriakb | 525 / 387 | – | HLAMP ×97, TORCH ×66, CHAIR ×36, BARSTOOL ×29, BED ×20, DARKTABLE ×24 |
| halas | 445 | – | HALMOUND ×61, HLAMP ×40, FURRUG ×24, BARREL ×21, HBOX ×20, TABAC ×17 |
| rivervale | 531 | – | HLAMP ×123, LIGHTPOLE ×49, CHAIR ×48, BENCH ×29, BARSTOOL ×24, PALLET ×21 |
| kaladima | 266 | – | KALLAMP ×62, LAMP ×43, KALBRAZ ×14, KEG ×14, BOOKCASE ×10, MISTCOUCH ×7 |
| akanon | 452 | – | AKALIGHT ×170, RUG ×55, AKASTACK ×44, AKAWORKBENCH ×37, AKAWALLGIZ ×28 |
| erudnext, felwithea | 165, 213 | – | ERLANT ×154, BARSTOOL ×14, BED ×17, FELCHAIR ×10 |
| oggok | 370 | – | OGGLANTERN ×213, OGGRUG ×27, OGGCHAIR ×17, URN ×15 |
| cabeast | 430 | – | CBROCK ×112, CBRUG ×54, CBTORCH ×52, CBBARREL ×28, CBCRATE ×25, IKCHAIR ×21 |
| paineel | 531 | – | PALAMP ×198, PAFLAG ×108, PACHAIR ×37, PATABLE ×22, PABOOK ×12 |

(Rooms: step 9's chamber split. Grobb has no `.s3d` in this install.)

By Category, sorted by name pattern (task 1 checks the leftovers by hand):

| | Objects | Debris | Light | Furniture | Container | Hanging | Plant | Other |
|---|---|---|---|---|---|---|---|---|
| 15 dungeons | 5916 | 36% | 29% | 10% | 9% | 5% | 4% | 6% |
| 15 cities | 6585 | 5% | 37% | 23% | 14% | 9% | 9% | 4% |

What it says:

- **Rooms are full.** Dungeons hold 7–48 objects a room (zone-wide, corridors included),
  median about 19. A room with nothing in it is the exception in stock and the rule here.
- **Lights are the backbone.** Nearly a third of everything is a torch, lantern, lamp or
  brazier, every zone has them, and most hang on walls (TORCHPOINT, TORCH). A room without
  them reads unlit whatever the ZON says.
- **Debris is the dungeon's texture**: rocks, bones, webs, mushrooms, crystals, slime. It's a
  third of a dungeon's objects and a twentieth of a city's: that's Clutter.
- **Furniture marks who lives there.** Inhabited dungeons (Paw, Guk, Sol A, Kurn, Runnyeye)
  have tables, chairs, benches, bunks and pallets; cities have beds, dressers, drawers and
  bookcases. Dead places (Crystal, Befallen, Kaesora) have almost none.
- **Each race has its own set**: PAW-, GUK-, KS-, SB-, CB-, AKA-, OGG-, PA- prefixes. Shape is
  shared (a table is a table); material and detail differ. That's the Material_Set.
- **Some objects are structure**: CBPILLAR, KSSTATUE, ladders, cages. Step 9's Features already
  cover pillars and plinths; ladders and cages are out (Req intro).

What the probe can't see, and task 1 measures: which room each object stands in, floor vs
wall vs ceiling, how close to a wall, Groups, lights' spacing, and the stock models' sizes and
triangle counts (from `<zone>_obj.s3d`).

### 2. What the code already offers

- Step 10's model path: `generators/sites/models.py` builds closed, outward-wound models;
  `builder.py` packs them and writes one ZON object each; the GLB gets a `sites` mesh.
- `analyzer/footprints.py`: `placed_from_zon`, `collidable_triangles`, `world_triangles`,
  `coverage` on a ground raster, the 8 u clear width and head height. Built for a heightfield;
  room-graph builds need a floor raster per Level (`flat_raster` exists).
- `analyzer/traverse.py`: the per-triangle agent the room gate runs today.
- Step 9's room plan grid (`generators/room_layouts.py`): the floor, the Spine, Features and
  POIs per room, and checked-TOML loaders; `rules/rooms/scales.toml` has Clutter and Finish.
- One `LightSpec` per room (`generators/layout.py`), written as a ZON light by `builder.py`.
- `rules/sites/` and its loader: the pattern for `rules/decor/`.

## Props

Kinds in v1, from finding 1 (task 1 sets sizes and counts):

| Category | Kinds | Mount | Collision |
|---|---|---|---|
| light | wall torch, brazier, standing lamp, hanging lantern, candle cluster | wall, floor, ceiling | brazier and lamp solid; others passable |
| furniture | table, chair, bench, stool, bed/bunk, pallet, bookcase, shelf, throne | floor (shelf, bookcase against a wall) | solid; pallet passable |
| container | barrel, crate, chest, keg, urn, sack | floor | solid; sack passable |
| debris | bone pile, bones, rock, web, mushroom cluster, rubble | floor, wall (web), ceiling (web) | passable, rock solid above step height |
| hanging | banner, chain, hook, rug | wall, ceiling, floor (rug) | passable |

A Prop's origin is its Mount point: floor Props at the floor, wall Props at the wall face
(front facing out along +X at yaw 0, as step 10's Structures), ceiling Props at the ceiling.
Props are small (tens of triangles); one model per kind, variant and Material_Set in use.

## Placement

Per room, after step 9's plan: **Dressing** first (each POI's asks, round the POI, never on
its spot), then the recipe's **Groups**, then single Props, then debris by Clutter. Floor
spots come from the room's plan grid with the Spine, Throats and Features masked, grown by
the clear width; "along wall" spots sit a Prop's half-depth off a wall face. Wall spots walk
the room's wall faces at the recipe's height, skipping door openings and their frame, spaced
by the recipe (lights' spacing from task 1). Ceiling spots need the ceiling at least head
height above the Prop's bottom. What doesn't fit drops, recorded.

Corridors get lights only in v1 (wall torches by spacing), as stock's corridors do.

## The gate

Task 2 teaches the room gate placed models, as step 10's task 2 taught the wilderness gate.
**Recommended route:** the traversal agent takes the placed models' collidable triangles
(`world_triangles`) as obstacles beside the mesh's own, so one check covers dungeons, cities
and outdoor-dungeon interiors on every Level, and the Spine and Throats are checked by the
same "reached floor stays joined" rule. With no placed models it is today's check.

## Decor recipes as data

```
rules/decor/
  props.toml      Prop_Kinds: Category, Mount, size, collision, variants, light colour
  rooms.toml      Decor_Recipes by default, kind, room type; Dressing by POI purpose
  sets.toml       Material_Sets, and which race and theme takes which
```

Weights multiply by Layer (default x zone type x race x theme x room kind or type x control), as step 9's
Scales do. Clutter moves debris, Structure moves furniture lines, Finish picks worked or rough
variants. The loader checks every field; `scripts/topology_rules.py` gains `check rules/decor`
and `draw-decor` (a room's plan with its Props).

## Controls and sidecar

`decor` (none, sparse, normal, dense) scales every recipe's count; `decor_seed` (an integer,
unset for one drawn from the zone seed) salts the stream, so a reroll changes only Props. The
sidecar gains, per room, `props` (kind, variant, set, x, y, z, yaw, Mount), `dressing` by POI,
and `decor_drops`. The EQ map draws floor Props' Footprints; the web map draws them and lists
a room's Props in the side panel.

## Correctness properties

| # | Property | Req |
|---|---|---|
| P1 | A cutting Footprint, a narrowed Throat, an unreached POI: each fails, named | 2.1 |
| P2 | With no placed models the room gate's answer is unchanged | 2.2 |
| P3 | Every model closed where solid, round-trips exactly, origin at its Mount | 3 |
| P4 | Floor Props off Spine, Throats and Features; wall Props on walls, off doors; ceiling Props under headroom; Groups whole; misfits drop | 5.1–5.3 |
| P5 | Geometry identical across Decor; `none` matches step 10 bytes | 5.4, 11.2 |
| P6 | Decor files: every bad value named; every kind and set referenced exists | 6 |
| P7 | Dressing at every POI that asks; POIs on reached floor | 7 |
| P8 | One ZON light per light-bearing Prop | 8 |
| P9 | A decor seed changes only Props | 9.2 |
| P10 | Sites keep every step 10 guarantee with Props | 10 |
| P11 | Built rooms in the survey's bands | 11.1 |
| P12 | Same inputs same `.eqg`; time within step 10 + 5 s | 11.3, 11.4 |

## Risks

- **Small models read as boxes.** A chair at 20 triangles is easy to make look like a crate.
  Silhouette is what sells it; task 9's look is early for that reason.
- **Clutter in the way.** Rooms are small and the Spine is wide; stock packs Props tight
  against walls. Too strict a clearance gives bare rooms, too loose blocks doors. The gate is
  the bar, and tuning follows the look.
- **The gate's cost.** Hundreds of Props add obstacle triangles to every Level's traversal.
  Props are tens of triangles each, so a 30-room zone adds a few thousand; measured in task 7.
- **Lights.** Whether RoF2 lights an `.eqg` zone from ZON point lights at all is unverified
  until the in-client check (M6); the flame's own texture carries the look meanwhile.
- **Wall faces on rough walls.** Step 8's rough and hewn walls are noisy; a torch must sit on
  the surface, not float or sink. Wall spots should sample the wall mesh, not the outline.

## Open questions

1. **Generated Props, or the client's own models?** *Recommended: generated, as trees and
   Structures are (umbrella Req 32.7). Stock models live in each zone's own `_obj.s3d` and an
   `.eqg` zone can't name them; generating keeps every build self-contained.*
2. **Which kinds in v1?** *Recommended: the table under "Props": about 25 kinds over five
   Categories, the ones finding 1 shows in most zones. Ladders, cages, statues and
   race-specific oddities (gears, steam vents) wait.*
3. **Which Props block?** *Recommended: furniture, containers, braziers, lamps and big rocks are
   solid; rugs, pallets, small debris, webs and hangings are passable. Stock is looser (many
   small objects are passable); being solid only where a player would walk round is the
   honest middle, and the gate judges it.*
4. **Wall and ceiling Mounts in v1?** *Recommended: yes. Torches alone are an eighth of stock's
   objects and lights nearly a third, mostly on walls; a room of floor Props only would read
   wrong.*
5. **Lights: does a torch add a ZON light?** *Recommended: yes, one point light per
   light-bearing Prop at its flame, coloured by kind; the room's own centre light stays, so a
   room never gets darker than step 10's. Verified in-client at M6.*
6. **Cities in v1?** *Recommended: yes. Cities build on dungeon geometry and are stock's most
   furnished zones, so a city Layer leans every recipe toward furniture and lights (finding 1's
   city column). Cities have no room types of their own today (tavern, home, shop); adding them
   is a follow-up, not this step.*
7. **Site Props in v1?** *Recommended: yes, as one late task (task 11) through the same path:
   haybales, a cart, crates, bedrolls, offerings at a Site's POIs. Step 10's decision 5 left
   them here.*
8. **A Decor control and a decor seed?** *Recommended: both. Decor (None, Sparse, Normal, Dense)
   as Trees and Sites have; the decor seed is step 9's "reroll a room's contents" follow-up,
   nearly free on its own stream. The page gets a "Reroll decor" button on a built zone.*
9. **Step 9's mesh Boulders.** *Recommended: leave them. Rock Props add debris on top; turning
   Boulders into Props would change the geometry at Decor `none`. The "boulders read as short
   pillars" follow-up stays its own.*
10. **Animated flames?** *Recommended: no. A static flame texture, as stock's torches mostly
    are; animation waits.*

## Decisions

None yet; the answers go here and in `archive.md` "Decisions".
