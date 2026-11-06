# Design — zone-generator-room-walls (roadmap step 8)

Written at master `d09449c`. Verify against the code before working a task.

## Overview

One idea carries this step: **a room keeps its Box, and draws its real walls
inside it.**

```
rules/walls/<style>.toml ── Cell size, Fill band, Relief, shapes per kind
rules/topology/themes.toml ── theme → style     rule `shape` ── per-room override
                                     │
layout (unchanged: boxes, levels, corridors, stacking, Envelope) ───┐
                                     │                              │ doors, slots
                                     ▼                              ▼
Cell_Complex over the Box ──► grow a connected set of Cells from the Core, through
(Voronoi or grid)             each door's Throat, to the style's Fill ──► Outline
                                     │
Relief ── floor rises, ceiling falls, per vertex; flat in Throats and at slots
                                     │
geometry ── floor and ceiling fans over the Cells; one vertical wall quad per edge
            of the Outline, on shared vertices
                                     │
walk gate and maps ── read the mesh as they already do; the gate learns Throats
                      and closure FIRST (task 2)
```

Everything before the Outline is unchanged, so step 6 and 7's guarantees about
placement, stacking, corridors and the Envelope hold by construction: an Outline
can only make a room smaller.

## Research findings

### 1. Stock walls (first numbers, 25 zones, at spec time)

A scratch survey over the WLD meshes, using step 6's floor walk and chamber split.
Task 1 redoes it as a script, adds straight runs and corners, and confirms the
style labels against plots. The labels below are a first reading of each zone,
not yet checked. Walls are non-passable faces with `|nz| < 0.7` beside the walked
floor.

| Zone | First label | Axis_Share | Plumb (≤ 3°) | Median edge | Fill | Floor Relief (u) | Ceiling spread | Flat floor | Flat ceiling |
|---|---|---|---|---|---|---|---|---|---|
| blackburrow | rough | 0.37 | 0.99 | 13.5 | 0.67 | 5.4 | 0.32 | 0.64 | 0.70 |
| paw | rough | 0.43 | 0.97 | 14.1 | 0.69 | 2.0 | 0.49 | 0.63 | 0.37 |
| crystal | rough | 0.45 | 0.99 | 10.0 | 0.70 | 0.2 | 0.06 | 0.78 | 0.80 |
| velketor | rough | 0.50 | 0.97 | 9.0 | 0.68 | 2.0 | 0.62 | 0.81 | 0.73 |
| runnyeye | rough | 0.51 | 1.00 | 12.0 | 0.69 | 0.0 | 0.12 | 0.93 | 0.54 |
| soldungb | rough | 0.51 | 0.99 | 12.0 | 0.69 | 1.2 | 0.51 | 0.65 | 0.34 |
| soldunga | rough | 0.57 | 0.99 | 10.0 | 0.74 | 1.4 | 0.65 | 0.83 | 0.71 |
| permafrost | rough | 0.57 | 0.96 | 13.3 | 0.69 | 0.0 | 0.25 | 0.84 | 0.88 |
| kaesora | hewn | 0.52 | 1.00 | 7.3 | 0.70 | 4.9 | 0.54 | 0.75 | 0.54 |
| chardok | hewn | 0.54 | 0.98 | 12.0 | 0.69 | 2.1 | 0.43 | 0.63 | 0.36 |
| guktop | hewn | 0.61 | 1.00 | 12.0 | 0.70 | 2.0 | 0.51 | 0.67 | 0.50 |
| najena | hewn | 0.63 | 0.98 | 10.0 | 0.70 | 0.0 | 0.21 | 0.90 | 0.74 |
| gukbottom | hewn | 0.64 | 1.00 | 14.0 | 0.71 | 1.7 | 0.30 | 0.51 | 0.48 |
| sebilis | hewn | 0.69 | 0.95 | 10.0 | 0.74 | 1.5 | 0.36 | 0.73 | 0.51 |
| cazicthule | hewn | 0.69 | 0.86 | 14.0 | 0.72 | 0.0 | 0.02 | 0.78 | 0.77 |
| mistmoore | built | 0.67 | 0.96 | 6.0 | 0.70 | 4.5 | 0.64 | 0.66 | 0.59 |
| qcat | built | 0.71 | 0.97 | 14.0 | 0.71 | 0.0 | 0.08 | 0.99 | 0.96 |
| unrest | built | 0.72 | 0.99 | 6.1 | 0.64 | 2.9 | 0.17 | 0.92 | 0.81 |
| hole | built | 0.72 | 0.99 | 5.7 | 0.72 | 1.5 | 0.58 | 0.72 | 0.49 |
| befallen | built | 0.77 | 0.99 | 5.0 | 0.75 | 0.0 | 0.00 | 0.84 | 0.87 |
| dulak | built | 0.79 | 0.87 | 8.1 | 0.72 | 11.6 | 0.05 | 0.91 | 0.12 |
| kurn | built | 0.96 | 1.00 | 10.0 | 0.74 | 0.5 | 0.27 | 0.99 | 0.97 |

Left out: kedge (one chamber, mostly water), droga (the split makes 124 chambers),
crushbone (mostly outdoors). Floor Relief is the chamber's p10–p90 floor height;
ceiling spread is its p10–p90 headroom over the median.

What this says:

- **Walls are plumb in every style** (0.86–1.00), caves included. That's the
  decision this design rests on: vertical walls over an Outline. It's why the
  removed SDF cave pipeline was the wrong tool, not merely a broken one.
- **Axis_Share separates the styles,** with overlap: rough 0.37–0.57, hewn about
  0.52–0.69, built 0.67–0.96.
- **Stock rooms fill about 0.70 of their bounding box in every style** (0.64–0.75).
  A rectangle fills 1.0, so even "built" stock rooms aren't plain boxes.
- **Relief doesn't separate styles cleanly.** Caves lean to moving ceilings and
  non-flat floors, but qcat and kurn are flat and crystal nearly so, while hole and
  mistmoore have ceiling spreads as high as caves. So Relief varies within a style,
  and the bands will be wide. Ceilings move far more than floors (spread 0.3–0.6 of
  the height, floors 0–5 u).
- **Median edges are 10–14 u in caves and 5–14 u in built zones,** matching the
  existing "voxel=12" lesson for caves.

### 2. What assumes a room is a rectangle

- **Stays on the Box, safely.** Placement and separation, stacking, corridor routes
  (`generators/routing.py`), the Envelope and Rock_Cover
  (`generators/outdoor_dungeon.py`), the gate's corridor checks
  (`analyzer/traverse.py` `corridor_continuity`, which is only stricter with the Box
  than the walls) and regions (`RegionSpec` boxes are metadata, and a box reaching
  past a wall into rock is harmless).
- **Must land on floor, so the Core keeps them true.** Spawn and labels use the
  room's centre; `traverse._faces_in_room` tests the Box for a walkable face.
- **Must change.** `MeshBuilder.add_room` (the only place room faces are made),
  `_door_openings` (its result becomes Throats), `_bridge_slots` (a slot becomes
  something an Outline must keep) and `mapview.py` (draws rectangles).
- **Reads the mesh already, nothing to change.** `mapgeom.extract_outline`, the
  EQ map files and the walk surface.

### 3. No new dependency

`shapely` isn't installed and boolean polygon work would be the obvious reason to
add it. A set of convex Cells needs none: the floor is a fan over each Cell, and a
wall is any Cell edge with a chosen Cell on one side only. `scipy.spatial.Voronoi`
gives the Cells, and `scipy` is already pinned (trimesh needs it).

## Outlines

**Representation** (`generators/outline.py`, data on `RoomSpec`):
`Outline(cells, verts, walls)`: convex Cells as vertex index lists, shared vertices
so a floor and wall weld exactly, and wall edges in order round the room.
`RoomSpec.outline` is `None` by default and omitted from JSON when unset, so
nothing else changes byte for byte.

**Cell_Complex:**

- `rough`: Voronoi of jittered seeds over the Box, spacing about 3 H. Irregular,
  with many bends.
- `hewn`: Voronoi, spacing about 6 H, after two or three rounds of Lloyd relaxation
  so facets come out longer, straighter and more even. Reads as cut, not formed.
- `built`: a grid aligned to the Box, module about 2 H. Choosing cells gives
  L-shapes, crosses, cut corners and alcoves, with every wall square to the grid.

Each is clipped to the Box. Spacing is in H, so an ogre's cave has bigger bends for
its bigger body. The exact numbers come from task 1.

**Throats first.** A Throat is a rectangle from the door's wall to the Core, as
wide as the corridor. Mirrored seeds on both sides of a Throat's long edges make
Voronoi edges fall exactly along them, so a Throat is a run of whole Cells and door
corners are real vertices. `built` gets the same from grid lines at the door edges.

**Growth.** Starting from Core and Throats (always connected, because each Throat
ends in the Core), add neighbouring Cells in seeded random order, weighted by the
kind's shape, until the Fill target for this room is met. Fill target: drawn from
the style's band (about 0.65–0.75 from finding 1; `built` runs higher, because a
`rect` shape is one of its choices and fills 1.0). **Fill floor 0.5:** under it, the
room has shrunk too far to read as its size class. Holes in the set are filled (a
Cell ringed by chosen Cells is chosen), since a column is step 9's job.

**Shapes per kind** (`rules/walls/<style>.toml`, `shape` in rules):

| `shape` | Means |
|---|---|
| `auto` | the default: the style's table picks by room kind |
| `rect` | the plain Box, no Outline. The existing default keeps its meaning if a rule writes it |
| `blob` | growth outward evenly: a rounded chamber |
| `long` | growth along the Box's long axis: a gallery or nave |
| `ell` | growth favouring two adjoining arms |
| `cross` | growth favouring four arms |

A style table might read: `hall = ["long"]`, `lair = ["blob", "ell"]`,
`hub = ["cross", "blob"]`, `deep = ["blob"]`. Kinds now show in 3D, which answers
step 6's "room kinds don't show" follow-up.

**A small room with many doors** may have little to choose: Core and Throats can
already exceed the Fill target. That's allowed (Req 2.3), and the room simply has
less variation.

**Rng.** The Outline draws from its own stream, seeded from the build's seed and the
room's id, so it can't shift a layout draw, and changing one style parameter doesn't
move another room's shape.

## Meshes

For a room with an Outline, `add_room` branches to `add_outline_room`:

- **Floor and ceiling:** a fan over each Cell (or for a Cell over the era edge, a
  fan with a centre vertex added). Winding as `add_quad` for the same normals.
- **Walls:** one quad per wall edge, from floor to ceiling heights at each vertex.
  A long edge splits so no triangle exceeds the era edge band by much. Doors are
  gaps in the wall run, and a lintel from the corridor's top up to the ceiling.
- **Texture coordinates:** a wall's U is its distance round the wall run, so
  texture runs on round a bend (`add_quad` projects each face alone, which would
  jump at every bend). Floors and ceilings stay planar, as today.

Polygon cap: at 12 u edges a shaped human room is roughly 600 triangles, so about
7,000 for 12 rooms against 3,054 for today's build, and stock zones are well above
that. The cap is set by task 3 at a measured margin, not a guess.

## Relief

Heights live on Outline vertices, from `generators/field`'s value noise (vectorised, per the
"never a per-voxel Python loop" lesson):

- **Floor:** `floor_z + max(0, noise) × relief`, zero in Throats, tapered to zero
  over one Cell next to them. It only rises: the lessons-learned entry on pits
  binds here. Slope is capped at build time by limiting the rise per Cell edge, so
  the gate passes first try rather than by retry.
- **Ceiling:** `top − max(0, noise) × spread × height`, never above the Box's top, so
  the Slab stands. At least `max(2.5 H, player height + margin)` over the floor, and
  at or above the lintel in a Throat. Flat within a Bridge slot's margin.

Style Relief bands come from task 1; finding 1 says they're wide, and that the
ceiling should move much more than the floor.

## Corridors

Flat and ramp legs in `rough` and `hewn` zones: the walls become a broken line with
vertices pulled inward by up to 15% of the width (never at the ends or a bend), and
the ceiling comes down by a matching amount. The floor and the route are as built, so
`corridor_continuity` and every route check are untouched. Minimum clear width:
2 H (a corridor is 3 H). Stairs and bridges stay as built (Open question 5).

## Styles and data

`rules/walls/{built,hewn,rough}.toml`, loaded by `generators/wall_styles.py` with
step 6's checker style: unknown keys rejected, each failure naming file, field and
expected. They'll eventually be prompt-written (the user's reason for strict
validation in step 6).

```toml
# rules/walls/rough.toml
complex = "voronoi"
cell_size_h = 3.0
relax = 0
fill = [0.62, 0.76]
floor_relief_h = [0.0, 0.8]
ceiling_spread = [0.2, 0.6]
corridor_break = 0.15

[shapes]
hall = ["long"]
lair = ["blob", "ell"]
hub  = ["cross", "blob"]
deep = ["blob"]
default = ["blob"]

[look]        # asks the texture layer for a family (Req 9)
wall = "rock"
floor = "rock"
ceiling = "rock"
```

`themes.toml` gains `walls` (default `built`). First reading, for task 5 to confirm:
`warren` rough; `mine_delve`, `lava_forge`, `ice_keep` hewn; the rest built; outdoor
dungeons with no theme rough. Only the Controls panel or a theme picks a style in
this step; description words join the existing "words choosing" fast follow.

## Controls and sidecar

**Walls** select: From theme (default), Built, Hewn, Rough. Shown with the Layout
control's rule while Layout is Graph. `ZonePlan.walls`, `--walls` on the CLI,
`walls` in the server's controls, hygiene allowlists updated, old saved plans with no
`walls` load as From theme under Graph. Sidecar `layout` block: `walls` and, in each
`rooms` entry, `shape`, `fill` and `outline` (points).

## Correctness properties

| # | Property | Req |
|---|---|---|
| W1 | Outline inside its Box, connected, contains the centre, reaches every door, Tunnel and slot; Fill in band or doors need more; never under 0.5 | 2 |
| W2 | Same room, doors, style and seed: same Outline; layout unchanged whatever the style | 2.4, 12.5 |
| W3 | No Outline: byte-identical build | 2.5, 12.3 |
| W4 | The gate catches a door with no Throat, a wall across a Throat, an open seam; each named | 3 |
| W5 | Room surface closed: every edge has two faces, apart from doors and slots | 3, 4.1 |
| W6 | Doors flush with corridors at every style | 4.3 |
| W7 | Floor at `floor_z` in Throats, never below it; slopes and steps pass; ceiling under the Box top and over the headroom floor; Slab intact on stacked builds | 7 |
| W8 | Corridor clear width ≥ 2 H, ends meet Throats, floor unchanged | 8 |
| W9 | Texture U continuous round a wall run | 9.2 |
| W10 | Style files: every bad value named | 5.1 |
| W11 | Built zones in each style's survey bands, in the right order | 12.1, 12.2 |
| W12 | First-try gate rate ≥ step 7's; time ≤ step 7 + 10 s | 12.4, 12.6 |

## Risks

- **"Tests pass" isn't "looks right".** This is the highest-risk step for that: the
  removed caves passed connectivity tests and rendered as blobs. A plumb wall over
  an Outline can't be disconnected that way, but it may look like a jagged paper cut
  out. Task 8 is an early human look, before corridors and textures, for that reason.
- **Voronoi may read as crystal facets rather than rock.** Stock caves have plumb
  walls and irregular runs, but their rhythm may differ. Task 1's straight-run
  numbers set spacing; the first look (task 8) judges it. If it fails, a Cell_Complex is one
  function and one file to swap.
- **Rooms read smaller.** Fill 0.7 shrinks a room's effective side by 16%. Step 7's
  bands are from stock floor area, so stock's sides are floor-based and ours would
  now be under. Task 12 measures it; if needed the Box grows by `1/sqrt(fill)` for
  shaped rooms, which moves every layout once. Open question 4.
- **Getting stuck in sharp corners.** A concave corner under the player's radius can
  snag the client. The gate has no radius. Noted for M6; Cell spacing in H keeps
  corners at least a body apart in `rough`, but it isn't proven.
- **Stacked seams.** A ceiling that moves changes the look of a room's top only; the
  Slab is safe because it only comes down.

## Open questions (answered 2026-11-06: the recommended answers; see `archive.md`)

1. **Three style names and their look.** `built`, `hewn`, `rough`, as the roadmap's
   "dungeon, man-made cave, rough cave". *Recommended: yes.*
2. **One style per zone?** Stock Guk mixes temple and cave. *Recommended: one per zone,
   with rules able to fix a shape; a mix by district is a follow-up, once it has a
   look to show.*
3. **Classic engine.** *Recommended: stays rectangles, byte-identical, as step 7 left
   it. Graph is the default now, and shapes reach it through kinds.*
4. **Should shaped rooms grow to keep their floor area?** *Recommended: measure first
   (task 12), and decide in task 13 with the first look in hand. It moves every layout once.*
5. **Rough stairs and bridges?** *Recommended: not in this step. Stairs and bridges stay
   square; a stone stair in a cave is plausible, and Blackburrow uses ramps anyway. Look
   at it in the first look.*
6. **Should `built` rooms change at all?** The roadmap names "dungeon" as a style, and
   stock built rooms fill about 0.7, so plain boxes aren't right either. *Recommended:
   yes, built rooms get L-shapes, crosses, alcoves and cut corners, keeping some
   plain rectangles. Every Graph build changes once, with goldens recaptured.*

## Decisions

1. A room keeps its Box as its allotment, and its Outline stays inside it.
2. Walls are plumb, because stock walls are (finding 1): no SDF or voxels. This
   answers the umbrella's M5 open question ("re-voxelise or deform"): neither, and
   step 8 replaces the M5 natural style sketch.
3. An Outline is a connected set of convex Cells, with no boolean polygon library.
4. Styles are validated TOML data, as topology rules are.
5. The gate learns Outlines before any generator makes one.
