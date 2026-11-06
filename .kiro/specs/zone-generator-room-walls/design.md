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

### 1. Stock walls (task 1, `scripts/wall_survey.py`)

Per zone, using step 6's floor walk and chamber split. Walls are solid faces with
`|nz| < 0.7` beside the walked floor. Labels come from each zone's plan plot.
"Today" is a plain 20-room graph build, measured by the same code.

| Zone | Style | Axis_Share | Plumb (≤ 3°) | Median edge | Run p50 | Corners | Fill | Floor Relief (u) | Flat floor | Ceiling spread | Flat ceiling |
|---|---|---|---|---|---|---|---|---|---|---|---|
| blackburrow | rough | 0.37 | 0.99 | 13.5 | 30.5 | 15 | 0.67 | 5.4 | 0.64 | 0.32 | 0.70 |
| paw | rough | 0.43 | 0.97 | 14.1 | 22.6 | 15 | 0.69 | 2.0 | 0.63 | 0.49 | 0.37 |
| crystal | rough | 0.45 | 0.99 | 10.0 | 25.1 | 11.5 | 0.70 | 0.2 | 0.78 | 0.06 | 0.80 |
| runnyeye | rough | 0.51 | 1.00 | 12.0 | 24.2 | 31 | 0.69 | 0.0 | 0.93 | 0.12 | 0.54 |
| soldungb | rough | 0.51 | 0.99 | 12.0 | 21.0 | 21 | 0.69 | 1.2 | 0.65 | 0.51 | 0.34 |
| soldunga | rough | 0.57 | 0.99 | 10.0 | 17.0 | 31 | 0.74 | 1.4 | 0.83 | 0.65 | 0.71 |
| permafrost | rough | 0.57 | 0.96 | 13.3 | 28.0 | 12 | 0.69 | 0.0 | 0.84 | 0.25 | 0.88 |
| kaesora | hewn | 0.52 | 1.00 | 7.3 | 32.0 | 20 | 0.70 | 4.9 | 0.75 | 0.54 | 0.54 |
| guktop | hewn | 0.61 | 1.00 | 12.0 | 28.0 | 30 | 0.70 | 2.0 | 0.67 | 0.51 | 0.50 |
| najena | hewn | 0.63 | 0.98 | 10.0 | 31.3 | 10 | 0.70 | 0.0 | 0.90 | 0.21 | 0.74 |
| gukbottom | hewn | 0.64 | 1.00 | 14.0 | 27.8 | 18 | 0.71 | 1.7 | 0.51 | 0.30 | 0.48 |
| sebilis | hewn | 0.69 | 0.95 | 10.0 | 37.5 | 13 | 0.74 | 1.5 | 0.73 | 0.36 | 0.51 |
| qcat | built | 0.71 | 0.97 | 14.0 | 28.0 | 14 | 0.71 | 0.0 | 0.99 | 0.08 | 0.96 |
| befallen | built | 0.77 | 0.99 | 5.0 | 34.0 | 19.5 | 0.75 | 0.0 | 0.84 | 0.00 | 0.87 |
| kurn | built | 0.96 | 1.00 | 10.0 | 39.0 | 23.5 | 0.74 | 0.5 | 0.99 | 0.27 | 0.97 |
| *today* | | *1.00* | *1.00* | *23* | *36–39* | *9.5–12* | *0.78–0.81* | *0.0* | *1.00* | *0.00* | *1.00* |

**Bands** (these are W11's bars, in the survey's own measures):

| Style | Axis_Share | Plumb | Median edge | Run p50 | Fill | Floor Relief | Flat floor | Ceiling spread | Flat ceiling |
|---|---|---|---|---|---|---|---|---|---|
| rough | 0.37–0.57 | 0.96–1.00 | 10–14 | 17–31 | 0.67–0.74 | 0–5.4 | 0.63–0.93 | 0.06–0.65 | 0.34–0.88 |
| hewn | 0.52–0.69 | 0.95–1.00 | 7–14 | 28–38 | 0.70–0.74 | 0–4.9 | 0.51–0.90 | 0.21–0.54 | 0.48–0.74 |
| built | 0.71–0.96 | 0.97–1.00 | 5–14 | 28–39 | 0.71–0.75 | 0–0.5 | 0.84–0.99 | 0.00–0.27 | 0.87–0.97 |

**Left out,** on their plots: chardok (built halls and cave tunnels, about half
each), cazicthule (temple, tunnel maze, pyramid), mistmoore (a castle in open
grounds), hole (a ruined city inside caves), velketor (large geometric facets, not
rock and not masonry), unrest (a house in an open yard), dulak (a harbour town,
mostly open), kedge (one chamber, mostly water), droga (the split makes 124
chambers), crushbone (mostly outdoors). The `built` band rests on three zones.

What this says, including where it changes the first reading at spec time:

- **Walls are plumb in every style** (0.95–1.00 in kept zones), caves included.
  This stands, and the design rests on it.
- **Fill was misread.** The spec's first version said stock rooms fill about 0.70 of
  their box, so a plain rectangle (1.0) was wrong. Today's all-rectangle builds
  measure 0.78–0.81 by the same code, because the split keeps door stubs in a
  chamber and the raster loses its edge. So stock's 0.70 is only about 0.9 of what a
  rectangle measures. **Outlines take off about 5–20% of the Box, not 30%.**
- **Built stock rooms are mostly plain rectangles.** Befallen is rectangles joined by
  short corridors, with some octagons (cut corners) for its large rooms. Plain
  rectangles stay the commonest `built` shape; cut corners come next; L-shapes and
  crosses are the rare ones.
- **Relief does separate the styles** once mixed zones are out. Built floors and
  ceilings are nearly flat (flat ceiling 0.87–0.97, at spec time this looked
  otherwise because of hole and mistmoore). Caves move, and the ceiling far more than
  the floor.
- **Hewn looks like polygons.** Kaesora and Najena's rooms are convex 6–10-sided
  shapes, often with 45° cuts, joined by square corridors: rooms look laid out, not
  formed. A few large relaxed Cells suit that.
- **Rough walls have longer runs than expected.** Run p50 is 17–31 u (about 3–5 H for
  a human), so Cell spacing needs to be about 5 H, not the 3 H first proposed.
- **Whole zones mix styles.** Four of the 25 zones plainly mix built and cave parts,
  and soldungb and guktop have built wings. One style per zone stays this step's
  decision, but a mix by district is the natural follow-up.
- **Corners doesn't separate styles** (door jambs dominate it: rectangles measure
  9.5–12). It's reported but isn't a bar.

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

- `rough` (`voronoi`): Voronoi of jittered seeds over the Box, spacing about 4 H. Every
  wall vertex then wanders inward by up to about 1.3 H (`wobble`), or a room keeps the
  Box's straight sides with bites out of them, which is how the first drawing looked.
  In a small room it wanders less, at most 8% of the Box's short side (the thorough run
  found a 48 u room losing too much floor).
- `hewn` (`facet`): the Box with each corner cut at an uneven angle, one convex room of
  a few long facets, as Kaesora and Najena's are. A Throat keeps a stub of a corner
  piece where a door lands on one. Voronoi didn't suit this: relaxed large cells drew
  the same bitten rectangles. `shape` sets the cuts' depths (`FACET_CUTS`).
- `built`: a grid aligned to the Box, module about 4 H, whose corner cells can be cut
  at 45° (a corner cell splits into a kept piece and a dropped triangle). Choosing
  cells gives cut corners, L-shapes, crosses and alcoves. Plain rectangles are the
  commonest choice and carry no Outline at all.

Each is clipped to the Box. Spacing is in H, so an ogre's cave has bigger bends for
its bigger body. Task 12 tunes these to the bands in finding 1.

**Throats first.** A Throat is a rectangle from the door's wall to the Core, as
wide as the corridor. Mirrored seeds on both sides of a Throat's long edges make
Voronoi edges fall exactly along them, so a Throat is a run of whole Cells and door
corners are real vertices. `built` gets the same from grid lines at the door edges.

**Growth.** Starting from Core and Throats (always connected, because each Throat
ends in the Core), add neighbouring Cells in seeded random order, weighted by the
kind's shape, until the Fill target for this room is met. Fill here is true floor
over Box, not the survey's measure: about 0.70–0.85 for `rough` once walls wander,
0.80 up for `built`, and whatever its cuts leave for `hewn` (0.74–0.89 drawn).
Task 12 checks the result in the survey's measure. **Fill floor 0.65:** under it, the
room has shrunk too far to read as its size class. Holes in the set are filled (a
Cell ringed by chosen Cells is chosen), since a column is step 9's job.

**Shapes per kind** (`rules/walls/<style>.toml`, `shape` in rules):

| `shape` | Means |
|---|---|
| `auto` | the default: the style's table picks by room kind |
| `rect` | the plain Box, no Outline. The existing default keeps its meaning if a rule writes it |
| `cut` | the Box with its corners cut (`built`'s octagon) |
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

Polygon count (task 3, measured): a 120 x 90 x 40 u room is 570–1,070 triangles, about
10,000 for 12 such rooms against 3,054 today; stock zones are well above that. The
cap, 3,000 per human room at the largest size, has a test.

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
cell_size_h = 4.0
wobble_h = 1.3
fill = [0.70, 0.85]
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
| W1 | Outline inside its Box, connected, contains the centre, reaches every door, Tunnel and slot; Fill in band or doors need more; never under 0.65 before walls wander | 2 |
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
- **Rooms read a little smaller.** A true Fill of 0.85 shrinks a room's effective side
  by about 8%. Task 12 measures it against step 7's bands; if it matters, the Box grows
  by `1/sqrt(fill)` for shaped rooms, which moves every layout once. Open question 4.
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
6. **Should `built` rooms change at all?** The roadmap names "dungeon" as a style.
   *Recommended: yes, built rooms get L-shapes, crosses, alcoves and cut corners, keeping
   some plain rectangles. Every Graph build changes once, with goldens recaptured.*
   (Task 1 corrected this question's first reason, that stock built rooms aren't plain
   boxes: most are. The answer stands, with plain rectangles the commonest shape.)

## Results of the tuning (task 12)

Built zones on the survey's own code, median of six seeds at 20 rooms, flat:

| Style | Axis_Share | Plumb | Edge | Run p50 | Fill | Flat floor | Ceiling spread | Flat ceiling | True Fill |
|---|---|---|---|---|---|---|---|---|---|
| rough | 0.46 | 0.99 | 10.7 | 17.3 | 0.69 | 0.82 | 0.27 | 0.51 | 0.75 |
| hewn | 0.60 | 0.98 | 11.3 | 27.1 | 0.74 | 0.89 | 0.33 | 0.52 | 0.86 |
| built | 0.91 | 1.00 | 11.9 | 34.6 | 0.76 | 1.00 | 0.00 | 1.00 | 0.93 |

Inside finding 1's bands, except: hewn's run p50 sits just under its 28 u floor; built's
Fill is 0.01 over; and built floors and ceilings are entirely flat, over the stock top of
0.99 and 0.97. W11's test takes these with a 3% tolerance and leaves the flat tops open.

## Decisions

1. A room keeps its Box as its allotment, and its Outline stays inside it.
2. Walls are plumb, because stock walls are (finding 1): no SDF or voxels. This
   answers the umbrella's M5 open question ("re-voxelise or deform"): neither, and
   step 8 replaces the M5 natural style sketch.
3. An Outline is a connected set of convex Cells, with no boolean polygon library.
4. Styles are validated TOML data, as topology rules are.
5. The gate learns Outlines before any generator makes one.
