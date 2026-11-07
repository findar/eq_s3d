# Requirements Document

> **STATUS: roadmap step 9, ready.** Written 2026-11-06 at master `1c69568`. The user took
> the recommended answer to every open question the same day (`archive.md` "Decisions"). Task index: `tasks.md` (card format, 26 tasks). Requirements 10–15 came from the user on the same day, after the first look: what a room is like belongs to the rules, not only to a slider.
> Step 8's acceptance pass and close are still open: the user set them aside on
> 2026-11-06 and asked to go on, so this step builds on walls not yet signed off.

## Introduction

Roadmap step 9: **interesting room layouts, POIs within rooms.** A generated room today is
an empty floor. It has a shape (step 8), a kind (step 6) and a list of props in its sidecar
(`prop_hints`: "raised throne dais", "pillar ring"), but nothing stands in it.

Stock rooms aren't empty. Across 15 stock zones, up to two-thirds of a zone's rooms have raised
floor, about a quarter of the room and 4–5 u up. Free-standing solids in the mesh are less common,
in up to 40% of rooms, and hundreds of placed objects per zone fill the rest, which is step 11's
side of the line (design finding 1).

This step puts structure inside rooms, chosen by what each room is, without ever blocking
the way through: a throne room gets a dais at its far end, a sanctum a ring of pillars, a
barracks rows of columns, a cave boulders and rock columns. It also names each room's
points of interest in the sidecar, for the hand-finishing pass and for what comes later.

Step 8 left these hooks:

- **Room types carry props as words** (`generators/semantics.py`), shown in the side panel
  and acting on nothing.
- **Three wall styles,** which should change what a pillar looks like.
- **Outlines with a Core and Throats,** which mark floor that must stay clear.

This spec sits under the umbrella `zone-generator` (`.kiro/specs/zone-generator/`). "Req X.Y"
below means a requirement of THIS spec unless it says "umbrella".

**Out of step 9:** loose props and decoration, placed as `.mod` objects: crates, bones,
banners, furniture (step 11, and umbrella Req 32.4 forbids them until then); wilderness POIs
(step 10); NPC spawns and door records in the client, which belong to the SQL export (M6): this
step builds the frame a door hangs in and names the spot; the Classic engine; and the in-client
check (M6).

## Glossary

- **Feature**: a solid piece of the room's structure built into its mesh: a Pillar, Plinth,
  Boulder or Dais.
- **Pillar**: a floor-to-ceiling column.
- **Plinth**: a solid block you can't walk through, shorter than the room: an altar base, a
  statue base, a low wall.
- **Boulder**: a rough solid lump, in rock styles.
- **Dais**: a raised floor you can walk onto, by steps or a low rise.
- **Room_Layout**: the recipe saying which Features a room gets and how they're arranged.
- **Spine**: the floor that must stay clear: the paths joining the room's doors, and each
  door's Throat.
- **POI**: a named point in a room with a purpose ("boss", "treasure", "altar"). Advisory: it
  rides in the sidecar and never touches geometry.
- **Scale**: a 0–10 quality of a room: **finish** (raw rock to dressed stone), **structure** (how
  much is built into it: pillars, plinths, daises), **clutter** (how much lies about: boulders, and
  step 11's loose objects).
- **Weights**: eleven numbers, one for each value of a Scale; a value's chance is its weight over
  the sum.
- **Layer**: one source of Weights: the default, a race, a theme, an Overlay, a room kind or type,
  a rule, a control. A room's Weights are its Layers multiplied.
- **Overlay**: a named history laid over a zone, as a Layer: an ogre cave a tidier race took over.
- **Coherence**: 0–10, how strongly a room leans toward the rooms next to it.
- **Transition**: what stands where two wall styles meet: nothing, a Seam, a Frame or a Breach.
- **Door_Spot**: where a door could hang, in the sidecar: advisory, for the SQL export.

## Requirements

### Requirement 1: Measure what stands in stock rooms

**User Story:** As the project owner, I want stock room contents measured, so that density
and arrangement come from real zones.

1. A survey SHALL report per zone and style: the share of rooms with a Feature, Features per
   room, their size and height, the share of rooms with raised floor, its area and rise, and
   where Features stand (room centre, along a wall, in a ring or rows, far from the way in).
2. The survey SHALL say what it can't see: Features that are placed objects rather than
   part of the zone's mesh.
3. The numbers SHALL set the bands of Req 9 and the densities of Req 5.

### Requirement 2: The gate knows Features first

**User Story:** As a developer, I want the gate to catch a Feature in the way before any
generator places one.

1. The gate SHALL fail a room when a Feature stands in a Throat, leaves no path of the
   Spine's clear width between two doors, walls off any floor it was given, or leaves a
   POI unreachable. A Dais SHALL be walkable onto from the room's floor.
2. Each failure SHALL be named in the gate's diagnosis and pinned as a regression example.
3. These checks SHALL land before any layout places a Feature.

### Requirement 3: Feature meshes

**User Story:** As a player, I want solid pillars and raised floors, with nothing to fall
through or get caught in.

1. A Feature SHALL be a closed solid: faces all round and no gap at the floor or ceiling,
   including on moving floors and ceilings (step 8).
2. Features SHALL take each style's look: square or cut in `built` and `hewn`, irregular in
   `rough`, with the room's materials.
3. A Dais SHALL have its edges at most the walk agent's step-up, or steps that are.
4. Headroom over a Dais SHALL be at least the design's minimum.
5. Features SHALL have collision like any other solid face, and a triangle size in the era
   band; a zone's polygon count SHALL stay within the design's cap.

### Requirement 4: Placement keeps the way clear

**User Story:** As a player, I want a room with things in it that I can still walk through.

1. A Feature SHALL stand on the room's floor, inside its Outline or Box, clear of its Spine,
   of Bridge slots, and of the walls by the design's margin.
2. The Spine SHALL keep a clear width of at least the design's minimum in H.
3. A Feature that can't fit SHALL be dropped, and the drop recorded; a build SHALL never fail
   because a room is too full.
4. Placement SHALL be a pure function of the room, its doors, the recipe and the seed, and
   SHALL change no room, corridor, Level or wall of the layout.

### Requirement 5: Room layouts, as data

**User Story:** As a rule author, I want to say what a throne room holds in a file I can read.

1. Room_Layouts SHALL be TOML under `rules/rooms/`, checked strictly on load with failures
   named by file, field and expected value, as topology rules and wall styles are.
2. A Room_Layout SHALL be chosen by room type, then room kind, then a default.
3. A recipe SHALL name Features and arrangements (`ring`, `rows`, `corners`, `along_wall`,
   `far_end`, `centre`, `scatter`), counts or spacing in H, and POIs.
4. Every room type in `semantics.ROOM_TYPES` SHALL have a Room_Layout, and a room's `prop_hints`
   SHALL stop naming structure that now stands in it (Classic rooms, which stay empty, keep theirs).
5. `topology_rules.py check` SHALL cover these files, a command SHALL draw sample rooms, and
   `docs/TOPOLOGY_RULES.md` SHALL explain them.

### Requirement 6: POIs

**User Story:** As a person finishing a zone by hand, I want to know where the boss stands.

1. Each room SHALL record its POIs in the sidecar: name, purpose, position, and the Feature
   it belongs to, if any.
2. The climax room SHALL have a `boss` POI, the deep and treasure-like rooms a `treasure` POI.
3. POIs SHALL never change geometry or collision, and SHALL stand on walkable floor.
4. The map (SVG) SHALL show them.

### Requirement 7: Outdoor dungeons and stacked rooms

1. Outdoor dungeons SHALL take Features as dungeons do, with the step 5 and 7 guarantees held.
2. Features SHALL work with stacking and bridges: nothing rises through a Slab, and nothing
   stands under a Bridge's slot so as to block the view down.

### Requirement 8: Controls, sidecar and maps

1. A **Features** control (none, sparse, normal, dense; normal by default) SHALL show under
   Graph for dungeons and outdoor dungeons, and reach the CLI and server. `none` SHALL give
   the same rooms and walls as a build before this step. (Task 21 replaces the control with
   Req 15's; `none` keeps this meaning as structure and clutter at 0.)
2. The sidecar's `layout.rooms` SHALL record each room's Room_Layout, Features and drops.
3. The map (SVG) SHALL draw Features, and the EQ map files SHALL show them where they stand.

### Requirement 9: Like the stock zones, and everything else holds

1. Over many seeds at `normal`, built zones SHALL measure inside the survey's bands for raised
   floor, and for rooms with a solid at or above stock's band and at most 0.6, with the survey's
   own code (Features stand in for placed objects until step 11; design finding 1).
2. Classic builds, cities and wilderness SHALL be byte-identical. Step 6–8's bands, and the
   gate's first-try rate, SHALL still hold.
3. The same inputs SHALL give byte-identical `.eqg` contents (footer aside).
4. A 14-room build SHALL take at most step 8's build time plus 5 s.

### Requirement 10: Scales, as weights in the rules

**User Story:** As a rule author, I want to say how an ogre builds, and how a temple differs from
a fresh dig, so that a zone's rooms come from what they are and not from one slider.

1. Finish, structure and clutter SHALL each be Weights: eleven numbers at least 0, or the shorthand
   `{ peak, spread }`. A value's chance SHALL be its weight over the sum.
2. Weights SHALL be TOML under `rules/rooms/`, for the default, each race, each theme, each Overlay,
   room kinds and room types, checked strictly on load with failures named by file, field and
   expected value. `topology_rules.py check` SHALL cover them, and `docs/TOPOLOGY_RULES.md` SHALL
   explain them.
3. A room's Weights SHALL be its Layers multiplied, value by value. A Layer with `override = true`
   SHALL replace every less specific Layer.
4. When the product is all zeros, the most specific Layer with any weight SHALL decide: layers
   that disagree never fail a build.

### Requirement 11: Rooms vary, and neighbours mostly agree

**User Story:** As a player, I want a zone that changes as I walk it, with wings that belong
together and the odd room that doesn't.

1. Each room SHALL draw each Scale from its Weights, multiplied by a lean toward the rooms next to
   it already drawn, in graph order from the entrance.
2. Coherence SHALL be set per rule set and per Scale; at 0 a room SHALL ignore its neighbours.
3. Rules that grow the graph MAY set Weights on the rooms they make. Rooms they make later SHALL
   inherit them, and a room SHALL lean only on neighbours with the same rule Weights, so a rule
   can make a wing with a hard edge.
4. The draw SHALL be a pure function of the seed and the room's place in the graph, and SHALL take
   nothing from the layout's rng. The sidecar SHALL record each room's drawn values.
5. Generated zones SHALL measure inside the survey's band for how far finish drifts between
   neighbouring rooms and how often it breaks (task 12).

### Requirement 12: A room's finish is its wall style

1. Finish 0–3 SHALL draw `rough` rooms, 4–6 `hewn` and 7–10 `built`, and a room's value SHALL move
   its style's numbers within the style, as the style's file says.
2. Styles and looks SHALL apply per room and per corridor. Every step 8 check SHALL hold on a zone
   of mixed styles.
3. `themes.toml` SHALL stop naming a style: there SHALL be one source of a room's finish.
4. A plan that names `walls` SHALL give every room that style, with the same bytes as before this
   change.

### Requirement 13: Recipes read the Scales

1. A recipe line SHALL say which Scale scales it (structure unless named), and MAY name a threshold,
   e.g. boulders only from clutter 5. A value of 5 SHALL mean the recipe as written, 0 nothing, 10
   twice as much.
2. A temple SHALL draw low clutter and a fresh dig high, by data alone.
3. Req 9's bands SHALL hold under default rules. Clutter SHALL be in the sidecar for step 11 to read.

### Requirement 14: Transitions between styles

**User Story:** As a player, I want a masonry hall and a raw cave to meet in a way that looks meant.

1. Where a corridor joins rooms of different styles, a Transition SHALL be chosen from weights in
   `rules/rooms/transitions.toml`, by the pair of styles, multiplied by each room's type or kind.
2. A **Seam** SHALL change the corridor's look and walls at one clean line. A **Frame** SHALL set
   jambs and a lintel of the finer style at the door or the Seam. A **Breach** SHALL leave the finer
   room's opening broken, with the rougher corridor running up to it. **None** SHALL be a plain opening.
3. The gate SHALL learn Transitions first: floor flush through it, clear width and headroom held,
   no gap where sections meet, each failure named and pinned, before any generator places one.
4. Same-style pairs MAY take a Frame by the same file. A Frame that can't leave the clear width
   SHALL become a Seam, and the change be recorded; a build SHALL never fail for a Transition.
5. Every Frame SHALL record a Door_Spot in the sidecar: position, facing, width, height and the two
   finishes. No door SHALL be baked into the mesh, and the map (SVG) SHALL show them.
6. Stairs and bridges SHALL stay as built: their Transition stands at a door, not on the flight or span.

### Requirement 15: Controls

1. **Finish**, **Structure** and **Clutter** controls (From rules, or 0–10) and an **Overlay** select
   SHALL show under Graph, and reach the CLI and server, in place of Walls and Features. A number
   SHALL multiply in as the most specific Layer: a lean, not a pin.
2. Old plans SHALL load: `walls` as in Req 12.4, `features = none` as structure and clutter 0, and
   the other densities as a lean.
3. Pinning a seed SHALL still give byte-identical `.eqg` contents, footer aside.

## Exit criteria

1. Every requirement above has a passing test or, where a person must judge it, a step in
   `docs/ACCEPTANCE.md` "Step 9 — Room layouts".
2. The fast and thorough suites are green; the frontend builds.
3. The user signs off a human pass: rooms read as what they are (a throne room, a barracks,
   a cave), they feel designed and not scattered, a zone changes as you walk it without feeling
   random, styles meet in a way that looks meant, and you can always walk through.
