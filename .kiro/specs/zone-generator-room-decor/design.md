# Design — zone-generator-room-decor (roadmap step 11)

Written at master `e50ecfc`; revised the same day for the user's direction to use the
client's own models (finding 0, decision 1). Verify against the code before working a task.

## Overview

```
EQ install ── every <zone>_obj.s3d ── catalogue: one entry per distinct model, measured,
                                      with how stock placed it; tags (auto + reviewed)
                                     │
rules/decor/*.toml ── Decor_Recipes ask for tags (kind, set, Mount), not models
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
import ── each catalogue model in use converted once (WLD mesh + textures -> .mod + DDS),
          packed in the .eqg; one ZON object per Prop; one ZON light per light-bearing Prop
                                     │
walk gate ── learns placed models in room builds FIRST (task 2)   sidecar ── Props, drops
```

Props come after all room geometry, from their own stream, so geometry never moves and Decor
`none` is exactly the step 10 build (Req 6.4, 12.2).

## Research findings

### 0. How a stock zone loads its objects (design-time probe)

A Classic zone is three files the client loads by the zone's short name:

- **`<zone>.s3d`** holds `<zone>.wld` (the terrain mesh), `lights.wld` and **`objects.wld`**:
  the placements. Each placement is an instance fragment (0x15) naming an actor by string
  (`TORCH_ACTORDEF`) with a position, rotation and scale. This is where finding 1's counts
  come from (`scripts/room_feature_survey.placed_objects`).
- **`<zone>_obj.s3d`** (and `_obj2.s3d` where a zone has one) holds the models: an actor
  definition (0x14) per name, pointing at its mesh (0x36) and textures (BMP or DDS in the
  same archive).
- The client joins the two **by name, within the zone's own files.** In 12 zones checked
  (6 dungeons, 4 cities, 2 outdoor), every placed name resolved to an actor in that zone's
  `_obj.s3d`; none needed another archive. `global_obj.s3d`, the only object archive in
  `Resources/GlobalLoad.txt`, holds 7 files (teleporter art), not furniture.

So **a model can't be borrowed by name from another zone**: each zone ships its own copy
(BARREL is a separate model in every zone that has barrels, and copies may differ). An
`.eqg` zone works the same way, its ZON objects naming `.mod` files in the same `.eqg`. Using
a stock model therefore means **copying its mesh and textures into our `.eqg`** as a `.mod`,
which is how stock zones do it too. `core/wld.py` already reads a mesh's vertices, triangles,
flags, UVs and per-triangle texture names.

**Size of the catalogue.** The install has 293 `_obj*.s3d` archives holding **4,408 distinct
actor names**, the Classic–PoP look's models. The 855 `.eqg` files with `.mod` entries hold
38,583 names, mostly later-era zones and equipment (1,043 in `*equip*`, `*_chr*` and `global*`
archives); they're out of v1 (open question 2).

**The built catalogue** (task 1, `scripts/prop_catalogue.py build`): the 293 archives hold
12,320 actors under those 4,408 names, and every one parses (**0 failures**). Deduped by name
and mesh they are **4,651 models**: 227 names have more than one mesh, giving **243 variants**
(`NAME@zone`) beyond the first; 711 models share one mesh but ship different texture bytes in
different zones. **378 are animated** (229 skeletal, 149 vertex-animated: flags, pennants,
reeds) and 258 carry an animated texture (fire, smoke, shine; the mesh itself static). 10
sky domes, backdrops and ships (over 1e6 u² of surface) have no footprint or walk-in measured.
The 247 zones with an `objects.wld` place 313,012 objects; 311,557 resolve to a model in the
zone's own archives (`_obj`, `_obj2`, then `_2_obj`, which serves the zone too), and 4,192
models are placed somewhere. The 1,455 that don't: 1,445 in `hole`, whose `hole.s3d` places
Paineel-style names (`PALAMP102R`...) that its only object archive, `hole_2_obj.s3d`, lacks
(there's no `hole_obj.s3d`), and 10 `YKCVDRP400` in `mmcb`. Eight archives' zones have no
`<zone>.s3d` (grobb, lavastorm, nurga, potimea, uqua, chardokb, global, backup_stonebrunt).

### 1. What fills stock rooms (task 2's survey, `scripts/decor_survey.py`)

The placed objects (`objects.wld` instance fragments, 0x15: position, yaw, scale) of step 9's
15 dungeons and 15 cities. The commonest per zone, named by pattern (digits stripped):

| Zone | Objects | Commonest |
|---|---|---|
| blackburrow | 283 | TORCH ×78, BONES ×40, BLOODYPUNGEE ×28, BARREL ×13, PAWTABLE ×5 |
| paw | 344 | TORCH ×99, PAWROCK ×89, PAWBRICK ×48, PAWBARREL ×25, PAWPAL ×24, PAWHOOK ×23, PAWTABLE ×14 |
| crystal | 447 | CCROCK ×172, VELIUMCRYSTALS ×164, CCTORCH ×13, MISTWEBS ×10, CCBRAZ ×9 |
| runnyeye | 648 | TORCHPOINT ×225, SLIMEPILE ×44, BARREL ×42, CHAIR ×26, PAWTABLE ×15, URN ×14 |
| soldungb | 337 | TORCHPOINT ×59, STEAM ×47, FURPILE ×36, WEB ×27, KEG ×13, BRAZIER ×11, CANDELABRA ×8 |
| soldunga | 461 | TORCHPOINT ×129, TORCH ×87, BENCH ×21, CRATEA ×19, KEG ×15, DARKTABLE ×13, GOBDIVAN ×10 |
| permafrost | 502 | PERROCK ×255, PERTORCH ×119, PERBRICK ×21, PERSTAL ×17, PAWHOOK ×15 |
| kaesora | 396 | KSROCK ×202, KSTIKI ×39, KSLIGHT ×23, KSBOKPILE ×20, KSBOOK ×14, KSPEW ×14, KSSTATUE ×11 |
| guktop | 395 | OGGLANTERN ×107, MUSHROOM ×73, GUKBRAZIER ×26, GUKCHAIR ×25, GUKPLNK ×25, GUKTABLE ×15 |
| najena | 414 | BONEPILE ×77, PAWHOOK ×72, BONES ×48, STONEBENCH ×26, HPCHAIN ×21, PALLET ×11 |
| gukbottom | 482 | OGGLANTERN ×209, MUSHROOM ×64, GUKBRAZIER ×31, LADDER ×16, GROBCAGE ×13 |
| sebilis | 501 | CBTORCH ×121, CBTIKI ×69, SBROCK ×68, SBSHAKLE ×32, CBPILLAR ×24, SBTABLE ×18, SBBOOK ×13 |
| qcat | 93 | TORCHPOINT ×48, BONES ×14, BOOKCASE ×6, CHAIR ×4, RECTTABLE ×4, CANDLE ×4 |
| befallen | 346 | BHROCK ×112, BONEPILE ×84, STONEBENCH ×30, URN ×29, PAWHOOK ×20, BOOKCASE ×4 |
| kurn | 267 | KNTORCH ×53, CBTORCH ×45, CBCRATE ×40, CBBARREL ×26, VEBRAZ ×19, DNBUNK ×16 |
| qeynos2 | 480 | TREE ×160, TORCHPOINT ×46, HLAMP ×36, CHAIR ×33, LIGHTPOLE ×23, CRATEA ×19 |
| qeynos | 476 | LIGHTPOLE ×51, HLAMP ×46, CHAIR ×39, BED ×31, RUG ×26, BARSTOOL ×17 |
| freportw | 758 | HLAMP ×146, LIGHTPOLE ×86, CHAIR ×51, BARREL ×38, BOOKCASE ×20, DRAWER ×19, BED ×19 |
| freportn | 556 | HLAMP ×120, BED ×51, CHAIR ×46, BENCH ×25, DRAWER ×21, DRESSER ×14 |
| neriaka / neriakb | 525 / 387 | HLAMP ×97, TORCH ×66, CHAIR ×36, BARSTOOL ×29, BED ×20, DARKTABLE ×24 |
| halas | 445 | HALMOUND ×61, HLAMP ×40, FURRUG ×24, BARREL ×21, HBOX ×20, TABAC ×17 |
| rivervale | 531 | HLAMP ×123, LIGHTPOLE ×49, CHAIR ×48, BENCH ×29, BARSTOOL ×24, PALLET ×21 |
| kaladima | 266 | KALLAMP ×62, LAMP ×43, KALBRAZ ×14, KEG ×14, BOOKCASE ×10, MISTCOUCH ×7 |
| akanon | 452 | AKALIGHT ×170, RUG ×55, AKASTACK ×44, AKAWORKBENCH ×37, AKAWALLGIZ ×28 |
| erudnext, felwithea | 165, 213 | ERLANT ×154, BARSTOOL ×14, BED ×17, FELCHAIR ×10 |
| oggok | 370 | OGGLANTERN ×213, OGGRUG ×27, OGGCHAIR ×17, URN ×15 |
| cabeast | 430 | CBROCK ×112, CBRUG ×54, CBTORCH ×52, CBBARREL ×28, CBCRATE ×25, IKCHAIR ×21 |
| paineel | 531 | PALAMP ×198, PAFLAG ×108, PACHAIR ×37, PATABLE ×22, PABOOK ×12 |

(Grobb has no `.s3d` in this install.)

**How the survey reads them.** Each object joins the walked floor node nearest it (within
14 u, at the height of the floor under it), and so a room or a corridor of step 9's chamber
split. Rooms are chambers at least 50 u a side; the split's passage and smaller chambers are
corridor. In a city a room is a chamber with a ceiling over half its floor (a building); the
rest is open ground, counted as corridor. Step 6's `Floor` keeps only the largest walked
piece, which lost Kaesora's temple, Guk's halls past the water and most of South Qeynos;
the survey builds one per piece of at least 150 nodes, so room counts are higher than step
9's (Kaesora 36, not 20), and under 1% of objects (8% in Ak'Anon) stand off the walked floor.
Floor, walls and ceiling come from the zone mesh: the floor under an object is the highest
solid upward face at or just over its origin, the wall distance is to the nearest sampled
wall face (3 u grid), and the ceiling is the lowest solid downward face 4–250 u over the
floor (Crushbone's sky shell is 620 u up).

**Mount**, first match: **floor** when the model's bottom or origin is within 1.5 u of the
floor; **raised** when its bottom sits on another object's top (a stacked crate, a candle on a
table); **wall** when its origin is within 3.5 u of a wall; **ceiling** when its top is within
3 u of the ceiling or through it (hooks, chains); else **raised** (a ledge the ray missed).
Checked by name: TORCHPOINT 97% wall, HLAMP 99% wall, PAWHOOK 82% ceiling, CHAIR 98% floor.

**Category** comes from the name (`decor_survey.category`, first matching pattern: light,
container, furniture, hanging, structure, debris, plant). It's rough until task 3's tags:
2.5% of the 12,501 objects match nothing (STEAM ×107, AKASTACK ×44 and Ak'Anon's machinery
make most of it), and a hand check of the commonest 45 names per Category found few
misfilings but some judgement calls: mushrooms, webs, books, meat and tools are **debris**;
tiki torches are lights; ladders, carts, cages, cells and tents are **structure**.

Per zone type (p25–p50–p75 over the zones, min–max in brackets):

| | 15 dungeons | 15 cities |
|---|---|---|
| Objects in rooms (share) | 0.30–0.37–0.42 (0.09–0.76) | 0.16–0.24–0.35 (0.06–0.81) |
| **Props per room**, mean | 2.9–4.2–6.8 (0.9–11.5) | 4.0–9.4–12.5 (1.9–17.4) |
| Props per room, p50 over rooms | 1–2–5.5 (0–8) | 2–6–10 (0–19) |
| Empty rooms | 0.13–0.26–0.38 (0.04–0.78) | 0–0.20–0.40 (0–0.50) |
| **Per 1000 u²** of room floor | 0.45–0.54–0.96 (0.21–2.38) | 0.39–1.47–2.17 (0.18–4.31) |
| Per 1000 u² of corridor | 0.53–0.72–1.04 (0.31–1.64) | 0.26–0.40–1.04 (0.02–1.37) |

| **Category** | Light | Container | Furniture | Hanging | Structure | Debris | Plant | Other |
|---|---|---|---|---|---|---|---|---|
| Dungeons p50 (p25–p75) | .34 (.21–.45) | .08 (.03–.11) | .14 (.09–.15) | .01 (0–.04) | .02 (.01–.04) | .30 (.20–.56) | 0 | 0 (0–.03) |
| Dungeons pooled | .31 | .08 | .11 | .04 | .04 | .39 | .01 | .02 |
| Cities p50 (p25–p75) | .39 (.24–.45) | .12 (.10–.15) | .28 (.23–.34) | 0 (0–.02) | .01 (.01–.03) | .02 (0–.07) | .03 (0–.08) | .01 (0–.02) |
| Cities pooled | .38 | .12 | .29 | .03 | .02 | .06 | .08 | .03 |

| **Mount** | Floor | Wall | Ceiling | Raised |
|---|---|---|---|---|
| Dungeons p50 (p25–p75) | .56 (.51–.66) | .31 (.26–.38) | .01 (0–.09) | .05 (.04–.07) |
| Cities p50 (p25–p75) | .72 (.65–.77) | .23 (.18–.31) | 0 (0–.02) | .04 (.03–.05) |

By room style (the 15 dungeons; min–max over the zones):

| Style | Zones | Props per room, mean | Per 1000 u² | Light | Debris | Furniture | Floor | Wall | Ceiling |
|---|---|---|---|---|---|---|---|---|---|
| rough | 7 | 2.8–11.5 | 0.44–2.38 | .05–.48 | .04–.90 | .01–.20 | .47–.71 | .21–.48 | 0–.13 |
| hewn | 5 | 2.8–8.0 | 0.40–1.36 | .10–.53 | .18–.66 | .08–.15 | .51–.70 | .10–.47 | 0–.23 |
| built | 3 | 0.9–11.0 | 0.21–1.25 | .01–.59 | .06–.68 | .14–.15 | .41–.84 | .03–.53 | 0–.10 |

Style barely separates; the zone's people do (Befallen's dead keep a built zone at 1% light
and 68% debris, Kurn's living keep another at 51% light). **Task 14's bands are the dungeon
and city p25–p75 above**, by zone type, with the min–max as the hard edge.

The rest, from the per-zone printout:

- **Lights' spacing**: a wall light's nearest wall light is 33–38–45 u away in dungeons
  (p25–p50–p75 over zones; Najena 76, Befallen's few 196) and 21–26–32 u in cities. Of all
  lights, 52–74–89% are on walls in dungeons and 49–59–70% in cities.
- **Groups**: where a zone has tables and chairs, 0.46–1.0 of its tables have a chair within
  12 u, 1.1–2.7 chairs each; Paw's 14 tables have none (its gnolls sit on PAWPALs). Beds
  stand in rows (another bed within 16 u) for 50–100% of beds in the barracks dungeons (Paw,
  Sol A, Sol B, Kurn's bunks) and 0–56% in cities.
- **By doors** (where a room's floor meets another room or a corridor): 16–23–26% of dungeon
  doors and 39–56–71% of city doors have a light within 16 u. The inhabited dungeons light
  half or more (Sol A 71%, Runnyeye 62%), the dead ones almost none (Befallen 1%, Crystal
  3%). What stands by a door is the zone's mix, with lights over-represented.

What it says:

- **Rooms are emptier than the probe said.** Two thirds of a dungeon's objects stand outside
  the split's rooms: in corridors, alcoves and the passage round a room's edge. A dungeon room
  holds about 4 objects (mean; median 2), a quarter of rooms hold none, and corridors are as
  dense per u² as rooms. The probe's "7–48 a room" divided the whole zone by the room count.
- **Lights are the backbone**: a third of a dungeon's objects and two fifths of a city's,
  three quarters of them on walls, about 38 u apart (26 u in cities).
- **Debris is the dungeon's texture**: rocks, bones, webs, mushrooms, crystals. A third of a
  dungeon (90% of Crystal), a twentieth of a city: that's Clutter.
- **Furniture marks who lives there**: 14% in dungeons, 28% in cities; inhabited dungeons seat
  their tables and row their beds.
- **Ceiling Mounts are rare and a dungeon thing** (hooks and chains in Najena, Paw, Befallen;
  1% median). Raised objects (stacks, things on tables) are about 5% everywhere.
- **Each race has its own set**: PAW-, GUK-, KS-, SB-, CB-, AKA-, OGG-, PA- prefixes. Shape is
  shared (a table is a table); material and detail differ. That's the Material_Set.
- **Some objects are structure**: CBPILLAR, KSSTATUE, ladders, cages. Step 9's Features already
  cover pillars and plinths; ladders and cages are out (Req intro).

**The catalogue's observed fields** (`decor_survey.py --write`, through
`prop_catalogue.put_observed`): for each of the 4,192 placed models, over the 246 zones that
place them (111 dungeon, 106 outdoor, 29 city; dungeon when a ceiling covers half the zone's
floor), its height over the floor and distance to a wall (p10/p50/p90), share under a ceiling,
scale (min/p50/max), Mount shares, zone types, the three names standing nearest, and per zone
the count, type, medians and commonest Mount. Over all 246 zones' placements: floor 74%,
wall 6%, ceiling 4%, raised 8%, and 7% `unknown`, where no solid floor face lies under the
object at all (mostly outdoor: a third of the East Wastes').

What the survey can't see:

- **Rooms the split joined or cut.** Room counts and sizes are the split's, not a person's:
  a big hall can be one room or several, alcoves and room edges fall to corridor, and a city's
  rooms are only its roofed chambers. Props per room is a bar for our own rooms measured by
  the same code (task 14), not a count a person would make.
- **Objects off the walked floor** (under 1%, 8% in Ak'Anon).
- **Real Categories.** Names are rough (2.5% unmatched, a few calls arguable); task 3's tags
  replace them.
- **Objects on objects** only by stacking geometry (a bottom on another's top within 1.5 u);
  a rug under a table, or a candle on a shelf the stacking misses, reads by its own height.
- **Orientation**: yaw is read but not judged (whether a wall Prop faces out from its wall).
- **The ZON's own lights**: only placed models count; `lights.wld` point lights aren't read.

### 2. What the code already offers

- `core/wld.py`: reads a WLD's 0x36 meshes (vertices, triangles with flags, UVs, per-triangle
  texture index) and texture names; `scripts/site_survey.py` loads `<zone>_obj.s3d` meshes by
  actor name and `measure_model` measures one (triangles, plan, height, solid share, walk-in).
- `scripts/room_feature_survey.placed_objects`: every placement in `objects.wld`.
- Step 10's model path: `builder.py` packs `.mod` models and writes one ZON object each; the GLB
  gets a mesh per model set; `core/eqg.py` writes DDS.
- `analyzer/footprints.py`: `placed_from_zon`, `collidable_triangles`, `world_triangles`,
  `coverage` on a ground raster, the 8 u clear width and head height. Built for a heightfield;
  room-graph builds need a floor raster per Level (`flat_raster` exists).
- `analyzer/traverse.py`: the per-triangle agent the room gate runs today.
- Step 9's room plan grid (`generators/room_layouts.py`): the floor, the Spine, Features and
  POIs per room, and checked-TOML loaders; `rules/rooms/scales.toml` has Clutter and Finish.
- One `LightSpec` per room (`generators/layout.py`), written as a ZON light by `builder.py`.
- `rules/sites/` and its loader: the pattern for `rules/decor/`.

## The catalogue

One entry per **distinct model** (same name and same mesh bytes is one model; the same name
with a different mesh is a variant, keyed `NAME@zone`). Built by `scripts/prop_catalogue.py`
from the install, written to `rules/decor/catalogue.json` (metadata only: no mesh or texture
bytes are committed; the import reads them from the install at build time).

Each entry holds three kinds of field:

| Kind | Fields | Source |
|---|---|---|
| **Measured** | source archive, actor name, mesh hash, triangles, plan w x d, height, depth below origin, solid share, walk-in, texture names and sizes, animated or static | the model |
| **Observed** | zones it's placed in and how often, zone type of each (dungeon, city, outdoor), height over the floor, distance to the nearest wall, under a ceiling or not, scale used, what stands near it | the placements (finding 1's survey code) |
| **Tags** | Category, kind (`wall_torch`, `table`, `barrel`...), Mount (floor, wall, ceiling), Set (race or culture: gnoll, goblin, dark elf, human city...), era, collision, suits (room kinds and types, themes), `use` (yes, no, review), confidence | auto-tagger, then review |

**Tagging.** The auto-tagger proposes every tag from the name (prefixes such as PAW-, GUK-,
CB-, KS- name the Set; TORCH, TABLE, BARREL the kind), the geometry (a model at a wall,
taller than wide, with a flame texture is a wall light), and the observed placements (where
stock put it is the strongest evidence for Mount and suits). Each tag carries a confidence.
**Reviewed tags win**: a human's corrections live in `rules/decor/tags.toml`, keyed by catalogue
entry, so rebuilding the catalogue never loses a review. A model enters builds only with
`use = yes`, whether set by review or by a high-confidence auto-tag the review accepted.

**The review sheet** (`scripts/prop_catalogue.py sheet`) writes a local HTML contact sheet:
one card per model with a rendered thumbnail (top and side views, textured), its measures,
where stock placed it, and its tags, sorted by stock use and grouped by proposed kind,
lowest confidence first. It stays local: it shows the client's art. The review covers the
models recipes can draw on, not all 4,408 (open question 3).

## Importing a model

`generators/decor/stock.py` turns a catalogue entry into a `.mod` and its textures: the mesh's
vertices, triangles, UVs and polygon flags (0x10 passable becomes `FLAG_PASSABLE`) as they are;
its BMP or DDS textures converted to DDS; its material per texture. The geometry is not
changed: no remeshing, closing or rewinding. Each model in use is imported once per build,
cached by mesh hash. Animated models (skeletal actors, flags) are left out of v1.

What the import must check, since step 10's models were closed by construction and stock
ones aren't: the gate reads "inside a solid" from the first triangle above a cell, which
assumes closed, outward-wound solids (step 10 decision 9). Task 2 makes the gate's Footprint
rule work for open stock meshes (a solid triangle's projection under head height blocks,
whether or not the mesh is closed).

## Stages and the RoomContext

The user's longer aim (decision 15) is three stages, each handing the next a small saved
file: **world -> Sockets** (points something can attach to), **Socket -> rooms ->
RoomContexts**, and **RoomContext -> Props**. Sockets are their own roadmap step (12); this
step builds the second hand-off, so decor never reaches back into the zone.

```
room stage (steps 6-9 + the built mesh) ── room_context.contexts(spec, mesh) ──> RoomContext[]
                                                                                  │
tests/fixtures/rooms/*.json  <── scripts/record_rooms.py (pinned seeds) ─────────┤
                                                                                  │
decor: place(context, catalogue, recipes, stream) ──> Props + its own room check ─┘
```

A **RoomContext** (`generators/room_context.py`) is a dataclass with a JSON form and a
version. It holds the floor grid (cell size, heights, reached mask), ceiling heights per
cell, wall faces sampled from the built wall mesh (point, outward normal, bottom and top),
doors with their Throats and clear zones, the Spine, Features with footprints, POIs, the
room's type, kind, race, theme, zone type and Scales, and a seed. A Site's context is the
same shape: its ground under the Site_Clear, its Structures as Features, its POIs, no walls
or ceiling.

**Tests in layers.** Decor tests run on the recorded room corpus (a few hundred rooms over
every room type, wall style and race) and on hand-built contexts: no zone build, so they're
milliseconds and carry no `slow` mark. One `slow` contract test regenerates a sample of the
corpus and compares. Decor's own room check (reached floor stays joined, doors and POIs
reached) runs on the context; the whole-zone gate stays in task 9's few integration builds.
Agents iterate on `-m "not slow"` and their task's tests, and run the full suite once
before ticking.

**Looking at one room.** `scripts/decor_room.py <context.json>` decorates one context and
writes a GLB of that room alone, for a look loop of seconds instead of a zone build.

## Placement

Per room, after step 9's plan: **Dressing** first (each POI's asks, round the POI, never on
its spot), then the recipe's **Groups**, then single Props, then debris by Clutter. A recipe
asks for tags (kind, Set, Mount); the placer picks a catalogue model that has them and
`use = yes`, preferring the room's race and theme Set, then a neutral one. Floor spots come
from the room's plan grid with the Spine, Throats and Features masked, grown by the clear
width; "along wall" spots sit a model's half-depth off a wall face, turned so its back faces
the wall. Wall spots walk the room's wall faces at the height stock uses for that model
(observed), skipping door openings and their frame, spaced by the observed lights' spacing.
Ceiling spots need the ceiling at least head height above the model's bottom. What doesn't
fit drops, recorded.

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
  catalogue.json  generated: measured and observed fields, auto tags (task 1)
  tags.toml       reviewed tags, keyed by catalogue entry (human, task 3)
  rooms.toml      Decor_Recipes by default, kind, room type; Dressing by POI purpose
  sets.toml       which race, theme and zone type take which Sets
```

Weights multiply by Layer (default x zone type x race x theme x room kind or type x control),
as step 9's Scales do. Clutter moves debris, Structure moves furniture lines, Finish leans
toward worked or rough Sets. The loader checks every field, and that every tag a recipe asks
for has at least one `use = yes` model; `scripts/topology_rules.py` gains `check rules/decor`
and `draw-decor` (a room's plan with its Props).

## Controls and sidecar

`decor` (none, sparse, normal, dense) scales every recipe's count; `decor_seed` (an integer,
unset for one drawn from the zone seed) salts the stream, so a reroll changes only Props. The
sidecar gains, per room, `props` (catalogue entry, kind, x, y, z, yaw, Mount), `dressing` by
POI, and `decor_drops`. The EQ map draws floor Props' Footprints; the web map draws them and
lists a room's Props in the side panel.

## Correctness properties

| # | Property | Req |
|---|---|---|
| P1 | A cutting Footprint, a narrowed Throat, an unreached POI: each fails, named | 2.1 |
| P2 | With no placed models the room gate's answer is unchanged | 2.2 |
| P3 | The catalogue covers every actor in every `_obj.s3d`; rebuilding it keeps every reviewed tag | 1, 3 |
| P4 | An imported model's triangles, UVs, flags and texture pixels equal the stock model's; the `.mod` round-trips | 4 |
| P5 | Floor Props off Spine, Throats and Features; wall Props on walls, off doors; ceiling Props under headroom; Groups whole; misfits drop | 6.1–6.3 |
| P6 | Geometry identical across Decor; `none` matches step 10 bytes | 6.4, 12.2 |
| P7 | Decor files: every bad value named; every tag asked for has a usable model | 7 |
| P8 | Dressing at every POI that asks; POIs on reached floor | 8 |
| P9 | One ZON light per light-bearing Prop | 9 |
| P10 | A decor seed changes only Props | 10.2 |
| P11 | Sites keep every step 10 guarantee with Props | 11 |
| P12 | Built rooms in the survey's bands; same inputs same `.eqg`; time within step 10 + 5 s | 12 |
| P13 | Placement reads only a RoomContext; the corpus matches room generation; decor's room check agrees with the zone gate on the integration builds | 13 |

## Risks

- **Builds need the install.** A build with Decor on reads models from `F:\everquest_rof2`
  (`EQ_PATH`). Without it, Decor falls back to `none` with a warning, and tests that need it
  skip as the survey tests do.
- **The output carries the client's art.** A built `.eqg` then holds copies of Daybreak's
  models and textures. That's fine for the user's own server and client, which already have
  them; it means builds shouldn't be published as standalone assets.
- **Stock meshes are loose.** Open shells, odd winding, passable flags on things that look
  solid (step 10 finding 1: LEANTO, TIKI, POST are 0% solid). The gate must judge them as they
  are (task 2), and placement must respect what stock made passable or not.
- **Tagging is the bulk of the work.** 4,408 models, names that are often cryptic (FAYBAR1,
  KSBOKPILE, TABAC). Auto-tags will be wrong often; the review is where quality comes from,
  and it must be small enough for a person to finish.
- **Mixing zones' art.** A Paw table beside a Guk chair reads wrong. Sets keep a room to one
  culture's models; neutral models (plain barrels, crates, bones) fill in.
- **Clutter in the way.** Rooms are small and the Spine is wide; stock packs Props tight
  against walls. The gate is the bar, and tuning follows the look.
- **The gate's cost.** Hundreds of Props add obstacle triangles to every Level's traversal.
  Stock props are 20-200 triangles; measured in task 9.
- **Lights.** Whether RoF2 lights an `.eqg` zone from ZON point lights is unverified until the
  in-client check (M6); the flame's own texture carries the look meanwhile.
- **Wall faces on rough walls.** A torch must sit on the surface, not float or sink. Wall
  spots should sample the wall mesh, not the outline.

## Open questions

Question 1 was answered by the user's direction (decision 1); the rest were answered 2026-11-08,
every recommendation taken (`archive.md` decisions 3-14).

2. **Which archives in v1?** *Recommended: the 293 `_obj*.s3d` archives (4,408 models), the
   Classic–PoP look this project defaults to. `.eqg` `.mod` models (later eras) are a
   follow-up; the catalogue's format leaves room for them.*
3. **How much is reviewed by hand?** *Recommended: everything recipes can draw on, which is far
   fewer than 4,408: the models stock places in dungeons and cities. Finding 1's 12,501
   placements use 581 names; 341 are placed 5 times or more, and 232 appear in two or more
   zones (same name, possibly different meshes). The rest
   stay auto-tagged with `use = review` and out of builds until someone looks. Reviewing happens
   on the contact sheet, and you can stop part-way: what's reviewed is usable at once.*
4. **Who reviews?** *Recommended: you, on the contact sheet, correcting tags in
   `rules/decor/tags.toml` (or telling me what to change and I write it). It's a human task
   (task 3) with no agent ticking it.*
5. **Collision: stock's flags or ours?** *Recommended: stock's, as the model has them. The look
   and feel is the point, and the gate judges whatever results; a model that blocks where it
   shouldn't is tagged `use = no` rather than edited.*
6. **Wall and ceiling Mounts in v1?** *Recommended: yes. Torches alone are an eighth of stock's
   objects and lights nearly a third, mostly on walls.*
7. **Lights: does a torch add a ZON light?** *Recommended: yes, one point light per
   light-bearing Prop at its flame; the room's own centre light stays. Verified in-client at
   M6.*
8. **Cities in v1?** *Recommended: yes, with a city Layer leaning recipes toward furniture and
   lights (finding 1). City room types (tavern, home, shop) are a follow-up.*
9. **Site Props in v1?** *Recommended: yes, one late task: the Karanas' haybales and carts, camp
   crates, centaur flags (static only), through the same catalogue.*
10. **A Decor control and a decor seed?** *Recommended: both, with a "Reroll decor" button on a
    built zone (step 9's "reroll a room's contents" follow-up, for Props).*
11. **Step 9's mesh Boulders.** *Recommended: leave them; stock rock models add debris on top.*
12. **Animated models?** *Recommended: out of v1 (flags, moving flames, gears); static models
    only. The catalogue records which are animated, so they can come later.*
13. **Generated Props at all?** *Recommended: not in this step. Where the catalogue has nothing
    usable for a kind, the recipe line drops. Generating a missing kind is a follow-up.*

## Decisions

1. **Props are the client's own models, copied into the build** (user, 2026-11-08: "generating
   props will be hard to keep in line with existing eq look and feel. for a first pass we should
   use the pre-existing ones if possible which means we need to catalogue all of them as they
   exist and tag appropriately"). This amends umbrella Req 32.7 for Props: a build may copy
   catalogued models from the user's install, unchanged. Terrain, rooms, trees and Structures
   are still generated.
15. **Decor stands on its own** (user, 2026-11-08, "soounds good lets do that"): room generation
    hands decor a saved RoomContext per room and decor reads nothing else; decor tests run on a
    recorded room corpus. Sockets (world points rooms attach to) become roadmap step 12.
