# Design — zone-generator-room-layouts (roadmap step 9)

Written at master `1c69568`. Verify against the code before working a task. Step 8's human
pass is open, so if it turns up changes to Outlines or styles, those land first.

## Overview

```
rules/rooms/*.toml ── room type or kind -> Features, arrangements, POIs
                                     │
finished room (Box, Outline, doors, slots, height; nothing below changes)
                                     │
Spine ── paths joining the doors, each door's Throat: floor that stays clear
                                     │
arrangement ── ring, rows, corners, along_wall, far_end, centre, scatter
               proposes spots; each must clear Spine, walls and slots, or it's dropped
                                     │
geometry ── each Feature is a closed solid standing on the floor; a Dais is a raised floor
                                     │
walk gate ── learns Features FIRST (task 2)        sidecar ── Features, POIs, drops
```

Features come after everything else, so nothing that exists today moves, and `none` is
exactly the build before this step (Req 8.1).

## Research findings

### 1. What stands in stock rooms (task 1, `scripts/room_feature_survey.py`)

Step 8's kept zones and step 6's chamber split. A **free-standing solid** is a connected group
of wall faces at least 10 u inside the chamber's edge, at least 4 u tall, compact (at most 40 u
across, no longer than 2.5 to 1) and facing every way. Other groups are **partitions**. **Raised**
is floor at least 2 u over the chamber's median, on at least 8% of it. **Objects** are the zone's
placed instances (`objects.wld`), not part of its mesh.

| Zone | Style | Rooms | Rooms with a solid | Side p50 | Rooms with a partition | Raised rooms | Raised share | Rise | Objects |
|---|---|---|---|---|---|---|---|---|---|
| blackburrow | rough | 36 | 0.11 | 10.5 | 0.75 | 0.47 | 0.29 | 4.8 | 283 |
| paw | rough | 32 | 0.03 | 18.0 | 0.75 | 0.47 | 0.28 | 3.9 | 344 |
| crystal | rough | 21 | 0.00 | – | 0.48 | 0.29 | 0.33 | 5.3 | 447 |
| runnyeye | rough | 17 | 0.24 | 2.0 | 0.94 | 0.00 | – | – | 648 |
| soldungb | rough | 18 | 0.28 | 4.0 | 0.89 | 0.44 | 0.30 | 4.0 | 337 |
| soldunga | rough | 15 | 0.13 | 11.0 | 1.00 | 0.33 | 0.22 | 4.0 | 461 |
| permafrost | rough | 29 | 0.17 | 31.3 | 0.48 | 0.28 | 0.23 | 5.1 | 502 |
| kaesora | hewn | 20 | 0.05 | 18.5 | 0.85 | 0.65 | 0.30 | 3.9 | 396 |
| guktop | hewn | 13 | 0.23 | 8.0 | 0.85 | 0.15 | 0.28 | 6.3 | 395 |
| najena | hewn | 22 | 0.14 | 22.2 | 0.59 | 0.18 | 0.24 | 4.8 | 414 |
| gukbottom | hewn | 10 | 0.20 | 4.0 | 0.70 | 0.20 | 0.16 | 3.0 | 482 |
| sebilis | hewn | 44 | 0.18 | 6.0 | 0.61 | 0.39 | 0.22 | 5.1 | 501 |
| qcat | built | 5 | 0.20 | 8.9 | 0.60 | 0.00 | – | – | 93 |
| befallen | built | 24 | 0.25 | 22.0 | 0.62 | 0.12 | 0.11 | 3.5 | 346 |
| kurn | built | 40 | 0.40 | 14.0 | 0.88 | 0.17 | 0.21 | 8.1 | 267 |

**Bands:** rooms with a solid: rough 0.00–0.28, hewn 0.05–0.23, built 0.20–0.40. Raised rooms:
rough 0.00–0.47, hewn 0.15–0.65, built 0.00–0.17. Raised share 0.11–0.33, rise 3–8 u.

What this says, and where it corrects the spec's first reading:

- **The first reading over-counted three or four times.** It said most rooms hold about 2 solids.
  Plots show that count was mostly partitions, stair sides and walls between rooms the split
  had joined. Free-standing solids in the mesh are uncommon: 0–40% of rooms, usually one.
- **What fills a stock room is placed objects:** 93–648 per zone, against 5–44 rooms, so many per
  room. The commonest are torches, bones, rocks, benches, barrels and braziers (TORCH1, BONEPILE,
  PAWROCK8, STONEBENCH, GUKBRAZIER1), and some pillars (CBPILLAR101). Those are step 11's side
  of the line (umbrella Req 32.4), and they're why stock rooms feel fuller than these numbers.
- **Raised floor is real and common:** up to two-thirds of rooms in a zone, about a quarter of the
  room, about 4–5 u up. This is the mesh's main piece of room structure, more than pillars are.
- **Inner walls are common too:** 48–100% of rooms have a partition, though this count still holds
  stair sides and door frames. The spec has no partition Feature; worth a look at task 8.

What this means for the design:

- **Bar for solids:** with no objects until step 11, Features stand in for what objects give stock
  rooms. So `normal` may run above stock's mesh-only count: named rooms always, ordinary rooms
  mostly bare. W-style bars take stock's band as a floor, and at most 0.6 of rooms as a ceiling.
- **Dais is the first Feature,** not pillars. Rise about 4–5 u, a quarter of the room.
- **Rocks and boulders** are placed objects in stock. A mesh Boulder is a stand-in until step 11.

### 2. What the code already offers

- `RoomSpec.prop_hints` (`semantics.ROOM_TYPES`) names 24 room types' props: some structural
  ("raised throne dais", "pillar ring", "rune pillars", "island platform"), most loose
  ("crates", "banners"), which stay step 11's.
- The Outline has its Core and Throats; a plain `built` room has none, so the Spine is computed
  from doors for both.
- Mesh building is per room in `MeshBuilder.add_room`, and walk surface floods share vertices or
  seam contact, so a Dais on shared vertices costs little (step 8's lesson on speed).
- The floor stays whole under a solid, so the walk surface thinks you can walk through a pillar.
  That's why the gate needs its own clearance check (Req 2); the existing flood can't see it.
- `mapgeom.extract_outline` draws where the floor ends, so a solid standing on an unbroken floor
  won't reach the EQ map files by itself (Req 8.3, task 7).

## Features

`generators/room_features.py`, data on `RoomSpec.features` (default empty, left out of JSON).

| Feature | Shape | Top | Style's form |
|---|---|---|---|
| `pillar` | prism, side about 1–2 H | meets the ceiling | `built` square, `hewn` cut 8-sided, `rough` irregular and wider at the foot |
| `plinth` | prism, about 1–3 H across, 1 H tall | capped | square or cut; `rough` becomes a `boulder` |
| `boulder` | irregular prism | capped, lower | `rough` and `hewn` |
| `dais` | raised floor, about a quarter of the room | walkable | steps on the Spine's side; `rough` a shelf with a low lip |

**Why a solid stands on the floor, and doesn't cut it** (Open question 2): cutting holes would
reach into Outline, walls and relief. A closed solid on an unbroken floor touches nothing, works
in plain `built` rooms with no Outline, and can be removed by a control. Its foot goes below the
floor's highest lift and its head above the ceiling's lowest drop, so moving surfaces meet it
with no gap. Its caps keep the gate's closure check happy.

**Dais:** a top face at `floor + rise`, sides down to the floor, and, on the side facing the
Spine, either a riser at most the step-up or steps (2 u risers). Rise about 4–5 u from finding 1;
the top is standable, and its side faces are walls. Headroom over it stays at least the
`add_relief` minimum, or it's dropped.

## The Spine and clearance

For each room: a grid at 2 u over the floor. Doors' Throats are always clear. Between each pair
of doors, and from each door to the Core, the shortest path is found, then widened to the clear
width (about 2 H, a corridor's clear width in a rock style). Cells in the widened paths are the
Spine. Spots are tested against it, against walls (margin about 1 H, so no snagging behind a
pillar) and Bridge slots. After each placement, the door graph is re-checked with the Feature's
footprint grown by the player's radius: if a pair disconnects, the Feature is dropped. This is
the same check the gate does independently from the mesh (Req 2), so the generator can't simply
trust itself.

Python per-cell loops are confined to one room's small grid; the lesson on per-voxel loops says
to watch it, and task 12 times it.

## Room layouts as data

`rules/rooms/layouts.toml` (one file; split if it grows), loaded by `generators/room_layouts.py`
with step 6's checker.

```toml
[types.throne]
features = [
  { kind = "dais", at = "far_end", share = 0.25 },
  { kind = "plinth", at = "on_dais", poi = "boss" },
  { kind = "pillar", at = "rows", spacing_h = 8, away_from = "spine" },
]
pois = [ { purpose = "boss", at = "on_dais" } ]

[types.inner_sanctum]
features = [
  { kind = "pillar", at = "ring", count = [6, 8], radius = 0.35 },
  { kind = "plinth", at = "centre", poi = "altar" },
]

[kinds.lair]
features = [ { kind = "boulder", at = "scatter", count = [1, 3] } ]

[default]
features = [ { kind = "pillar", at = "corners", chance = 0.4 } ]
```

A style can replace a Feature kind (`rough`: `pillar` draws as a rock column). The **Features**
control scales `count` and `chance` (none 0, sparse 0.5, normal 1, dense 1.5).

## POIs

Sidecar `layout.rooms.<id>.pois`: `{name, purpose, x, y, z, feature}`. Purposes: `boss`,
`treasure`, `altar`, `guard`, `ambush`, `view`. Pacing picks: the climax gets `boss` even if its
recipe forgot; `treasure` for dead ends at depth, as an existing gating note suggests. Advisory
only, per the project's rule that layouts are suggestions. A POI stands on walkable floor (a Dais
top counts), tested by the gate.

## Controls and sidecar

**Features** select: None, Sparse, Normal (default), Dense, shown with Walls under Graph.
`ZonePlan.features`, `--features`, `features` in the server's controls, hygiene allowlists. Old
plans load as Normal. Sidecar: `layout.features`, per room `room_layout`, `features`, `dropped`,
`pois`. The map SVG draws Features and POIs from the spec. EQ map files get extra lines for
free-standing Features, added in the map post-pass from `RoomSpec.features` (Open question 6).

## Correctness properties

| # | Property | Req |
|---|---|---|
| F1 | A Feature in a Throat, one blocking two doors, one walling off floor, an unreachable POI, an unwalkable Dais: each fails, named | 2 |
| F2 | Every Feature is closed on any floor and ceiling; the room's closure check still passes | 3.1 |
| F3 | Dais edges are within the step-up or have steps; headroom holds | 3.3, 3.4 |
| F4 | Placement: inside the floor, clear of Spine, walls and slots; door pairs stay joined at the clear width; a misfit drops, never fails | 4 |
| F5 | Placement draws nothing from the layout's rng; rooms, corridors, Levels and walls are identical across densities | 4.4, 8.1 |
| F6 | Layout files: every bad value named; every room type has a recipe | 5 |
| F7 | POIs stand on walkable floor; the climax has a boss POI | 6 |
| F8 | Outdoor and stacked builds hold step 5 and 7's guarantees | 7 |
| F9 | Built zones in the survey's bands, per style | 9.1 |
| F10 | Classic, city and wilderness goldens unchanged; `none` matches step 8's walls; first-try rate holds; same inputs same `.eqg`; time within step 8 + 5 s | 9.2–9.4 |

## Risks

- **Features stand in for objects.** Stock's rooms read as full because of placed objects, which
  we can't place until step 11. Rooms may read barer than stock whatever this step does.
- **Scatter reads as random, not designed.** The biggest risk, and the point of naming
  arrangements: a throne room should look deliberate. Task 8 is an early look for it.
- **Snagging.** Free-standing solids are what catches a player, and the gate has no body radius
  beyond the clearance check. M6 is the real test.
- **Small rooms.** A 48 u human room has little to spare after Throats. Most drops land here; a
  high drop rate is fine (Req 4.3) but the survey's density bar should be set per size.
- **The survey's limits** (finding 1): bars rest on a mesh-only count that both over- and
  under-counts, so they stay broad, and the human pass counts for more.
- **Step 8 isn't signed off.** Findings from that pass may move Outlines or relief, so Feature
  placement must read the room's final shape, not assume today's.

## Open questions (answered 2026-11-06: the recommended answers; see `archive.md`)

1. **A Features control?** *Recommended: yes, None/Sparse/Normal/Dense, default Normal, as Trees
   has density.*
2. **Solids on the floor, or holes cut in it?** *Recommended: solids. Simpler, works on plain
   rooms, and touches no earlier step. The cost is the gate needs its own check, and EQ map
   lines need adding (question 6).*
3. **Real pits?** Stock has sunken floor, but the project's rule is no pits. *Recommended: no. A
   floor only rises, so a sunken court is built as a Dais ring around a lower middle.*
4. **Which rooms?** *Recommended: Graph builds in every style, plain `built` rooms included, and
   outdoor dungeons. Classic stays empty, as it did for walls.*
5. **The line with step 11.** *Recommended: step 9 is solid structure in the zone's mesh, plus POIs
   as advisory points. Anything loose or small that could be a `.mod` (crates, statues, banners,
   bones) is step 11.*
6. **Pillars on the EQ map?** Map files draw where floor ends, so solids don't appear. *Recommended:
   add lines for free-standing Features in the map post-pass; stock maps show large ones.*
7. **Order with step 8's pass.** *Recommended: tasks 1–7 can land now. Run step 8's pass before or
   with task 8's first look, since the look is at the same rooms. Close step 8 before step 9.*

## Decisions

1. Features are added after the layout and walls, so nothing earlier moves.
2. The way through stays clear by construction, and the gate checks it independently.
3. Recipes are checked TOML data, chosen by room type, then kind, then a default.
4. POIs are advisory: sidecar only.
