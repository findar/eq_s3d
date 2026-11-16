# Research & Investigations

A record of the external approaches we investigated, what we concluded, and the
resources behind each decision. This is the "why we chose what we chose" log —
so settled questions aren't relitigated and the sources are attributable.

Each source is cited inline. Content from external sources has been paraphrased
and summarised; no substantial verbatim quotes are reproduced.

---

## Layout / dungeon-generation approaches

### TinyKeep spatial layout — ADOPTED (our layout backend)

The room-graph is built by scattering rooms, separating overlaps, Delaunay-
triangulating the centres, reducing to an MST, then adding back a few loop edges.
Chosen over the alternatives below because it yields composed hub-and-branch
layouts without grid regularity or tangling, which fits the "hand-crafted EQ
sprawl" look. Now implemented in `generators/layout.py`.

- Source: the TinyKeep author's write-up of the scatter → separate → Delaunay →
  MST + loops procedure (gamedeveloper.com / "Procedural Dungeon Generation
  Algorithm"). Reviewed; adopted the method, adapted to 3D with graph-based
  elevation.

### Surveyed and rejected layout families

Evaluated against the north-star (natural, non-grid, hand-crafted EQ feel):

- **BSP (binary space partitioning)** — recursive rectangular splits. Too
  grid-regular / boxy; reads as modern/tiled, not organic.
- **WFC (wave function collapse)** — tile-constraint solving. Grid-based and hard
  to steer at a global level; wrong aesthetic.
- **Cellular automata** — great for *cave* carving; effectively what our SDF cave
  backend already does. Kept the idea where it fits (caves), not as the layout.
- **Prefab stitching** — needs authored room content we deliberately don't have.
- **Pure random walk / Drunkard's Walk** — tangles into mazes; low composition.

Context: general proc-gen surveys and the common roguelike-dungeon literature
(e.g. RogueBasin's procedural-generation articles). Decision recorded in ROADMAP
"Deliberately NOT doing".

### Dormans graph rewriting — PARTIALLY ADOPTED (gating only)

Mission/space graph-rewriting (generate a mission as a graph, then rewrite into
space) is a powerful grammar approach. We adopted **only** the solvability-
invariant idea for lock-and-key gating (cut a BFS-tree edge, place the key in the
near partition), not a full grammar engine — EQ gates by depth/danger, not Zelda-
style lock chains.

- Source: Joris Dormans / boristhebrave's writings on graph rewriting for level
  generation (boristhebrave.com). Reviewed; extracted the invariant, not the
  engine. See `generators/layout.py::_apply_gating`.

### Labyrinth (Ryan Carpenter) — EVALUATED, NOT ADOPTED

A 3D dungeon generator (Unity/C#) built around "Blueprints": single-cell grid
marks parsed in a second pass to spawn rooms rule-tile style, placed via
Drunkard's Walk + divergent/unique placement, connected with Delaunay + A*, and
organised into "Zones" with their own rooms/rules/loot. Wrapped in a step-
debuggable "Blueprint Operations" instruction-queue architecture.

Verdict: does **not** improve our design.
- The standard parts (Delaunay, A*, Prim's/MST, Drunkard's Walk) we already do,
  with the stronger-for-our-goal choice (TinyKeep over walk+A*).
- Its signature feature — **grid + rule-tile rooms** — produces grid-snapped,
  tiled rooms that read as modern roguelike (Binding of Isaac / Enter the
  Gungeon, which the author cites), the opposite of hand-crafted EQ sprawl.
  Recorded in ROADMAP "Deliberately NOT doing".
- Its "Zones house their own rooms/rules/loot" idea is the same instinct as our
  planned **content / semantic layer** — mild confirmation of that direction, but
  we theme organic geometry rather than grid tiles.
- Worth noting as engineering: the "Blueprint Operations" step-debuggable
  pipeline is a tidy command/pipeline pattern. Not worth a refactor now (we have
  determinism, tests, and the top-down map for inspection), but a reasonable
  pattern to revisit if generation ever needs step-through debugging.

- Source: Ryan Carpenter, "Labyrinth Procedural Generator"
  (https://ryancarpenterpf.dev/labyrinth_demo.html). The page itself cites
  standard references: procedurally-generated-dungeons write-ups, the
  Bowyer–Watson algorithm (Delaunay), Amit's A* pages (Red Blob Games), and
  Ondřej Nepožitek's Edgar / Enter-the-Gungeon layout example.

---

## Geometry representation

### SDF + marching cubes for caves — ADOPTED

Carve chambers/tunnels into a signed-distance field, roughen with FBM noise,
extract the surface with marching cubes. Chosen because natural rock is irregular
by definition — exactly where procedural shines — and the per-triangle collision
model of EQG means a dense organic mesh behaves like a hand-made zone. See
`generators/field/`.

- Technique references: standard SDF primitive/operation formulas and the
  polynomial smooth-min (Inigo Quilez, iquilezles.org/articles/distfunctions);
  marching cubes via scikit-image's `measure.marching_cubes`.

### Heightfield + thermal erosion for outdoor terrain — ADOPTED

FBM hills relaxed by thermal erosion with a walkable-gradient cap. Standard
terrain-synthesis approach; see `generators/field/terrain.py`.

---

## "Should we train a bespoke model?" — investigated, decided NO (for the core)

Full reasoning in ROADMAP "Should we train a bespoke model instead?" and the
"Content / semantic layer" note. Summary: a from-scratch 3D-mesh zone generator
is the wrong tool (too little data — only a few hundred real EQ zones; hard
global constraints like watertightness/navigability/solvability that generative
models violate; poor controllability; and it doesn't help with the format /
packaging work we've already solved). ML belongs in the planner / semantic layer,
an optional learned "EQ-ness" critic, and textures — not in generating geometry.

---

## Format / ground-truth references

The authoritative sources used to implement the binary formats (also linked from
the README):

- EQEmu/zone-utilities (github.com/EQEmu/zone-utilities) — C++ structs/loaders;
  ground truth for EQG, the PFS CRC (`src/common/pfs_crc.cpp`), and per-triangle
  collision (`azone/map.cpp::CompileEQG`).
- WLD File Reference by Windcatcher (vegaseq.com) — legacy S3D/WLD format.
- xackery/quail (github.com/xackery/quail) — Go PFS implementation (archived).
- EQGZI getting-started (vegaseq.com) — existing zone-creation pipeline.
- knervous/eqsage (github.com/knervous/eqsage) — browser S3D/EQG viewer.

Measured era-fidelity data (triangle edge length by expansion) is derived from a
local RoF2 install, not an external source; see ROADMAP "Geometric fidelity by
era".

---

## Content / semantic layer — dungeon theme vocabulary & districts

The design research behind the content layer (ROADMAP "Next" #1): what a
"dungeon theme" is, the room-type vocabulary, the race-scale axis, and how
multi-area zones are modelled. Grounded in real EQ zones but deliberately not
limited to them. Content from the EQ community wikis below is paraphrased and
summarised (no substantial verbatim quotes); *content was rephrased for
compliance with licensing restrictions*.

### What real EQ dungeons actually are

Surveyed the canonical Classic–PoP dungeons to extract the recurring "place"
archetypes rather than copy specific zones:

- **Iksar fortress-city** — Sebilis / Chardok: ancient reptilian-empire ruins,
  a long entry to a central junction ("the rock") that splits into separate
  camps, royal/throne areas behind picked locks, tunnel warrens. A military
  fortress that is also an ancestral home. ([Old Sebilis, StrategyWiki](https://strategywiki.org/wiki/EverQuest/Zones/Old_Sebilis);
  [Chardok, EQ2 wiki](https://eq2.fandom.com/wiki/Chardok))
- **Frog-people sunken city** — Guk: an ancient Trollish city reclaimed by
  frogloks, split into an intact living upper city and ruined undead lower
  depths, with swimming pools / island platforms and two warring factions.
  ([Into the Depths: Guk, everquest.com](https://www.everquest.com/news/imported-eq-enus-50954);
  [Lower Guk, P1999](https://wiki.project1999.com/index.php/Lower_Guk))
- **Wizard's lava lair/prison** — Najena: a dark-elf magician's carved labyrinth
  in lava mountains, prison cells behind a guard keyring, undead in the halls,
  traps, a ramp from a basement to her chamber. Keyed progression + lava + cells.
  ([Najena, P1999](https://wiki.project1999.com/Najena))
- **Fear-god temple** — Cazic-Thule: an Aztec-like jungle pyramid run by
  lizardman caretakers and priests, built around living sacrifice and altars of
  fear, obelisks, ascending levels, a hidden archon at the top.
  ([Cazic Thule, P1999](https://wiki.project1999.com/Cazic_Thule);
  [Temple of Cazic-Thule, fandom](https://everquest.fandom.com/wiki/Temple_of_Cazic-Thule))
- **Giant war-city** — Kael Drakkel: home of the Kromzek/Kromrif giants, built
  *at giant scale*, covered in war-god statuary, with three temples, a battle
  arena, and a king's hall. ([Into the Depths: Kael Drakkal, everquest.com](https://www.everquest.com/news/imported-eq-enus-51649);
  [Kael Drakkel, P1999](https://wiki.project1999.com/Kael_Drakkel))
- **Buried ice keep** — Permafrost: a ruined castle buried in glacial ice, home
  to an ice dragon; excavated castle rooms *plus* a goblin-dug cave warren — two
  architectures in one zone. ([Permafrost, P1999](https://wiki.project1999.com/Permafrost))

### Design decision — archetypes by function, not by zone

We name themes by **function** (what kind of place it is), so the vocabulary
stays EQ-flavoured (realised through the measured Classic–PoP palette/scale)
while covering general high fantasy and real-world analogues, not only the zones
above. Decided NOT to hard-limit the vocabulary to literal EQ zones — the
north-star is "looks like a natural EQ zone", and the EQ look lives in
resolution/proportion/palette/texture (per the "Content / semantic layer" note
in ROADMAP), not in copying a specific floor-plan.

Archetype set (each carries a room-type arc + palette; realised with **no new
art**):

| Archetype | EQ touchstone | Also covers (high-fantasy / real-world) |
|-----------|---------------|------------------------------------------|
| `fortress` | Sebilis | castle keep, garrison |
| `warren` | Splitpaw / goblin caves | any dug-out creature den (kobold, ratmen) |
| `war_city` | Kael Drakkel, Chardok | civilisation stronghold-city |
| `temple` | Cazic-Thule | Aztec/Khmer temple-pyramid, cult shrine |
| `tomb` / `crypt` | — | Egyptian necropolis, catacombs |
| `wizard_lair` | Najena | mad-mage tower/undercroft |
| `corrupted_sanctum` | — | fallen/defiled holy place, sealed evil |
| `mine_delve` | Sol A/B | real-world mine, dwarven delve |
| `sunken_ruin` | Guk | drowned undercity, Basilica-Cistern-like |
| `lava_forge` | — | dwarven/duergar forge, Solusek |
| `ice_keep` | Permafrost | glacier-buried structure |

### Three orthogonal axes

A theme is **archetype × race × elemental tint**:

1. **Archetype** — picks the room-type arc + palette (table above).
2. **Race** — a *global scale/architecture multiplier* applied to room footprint,
   ceiling height, and corridor width/height, so a giant hall dwarfs a froglok
   warren. Grounded in EQ: Kael Drakkel is explicitly built for giants, Guk for
   frog/troll scale. **Scale values are relative placeholders** (see gap below).
3. **Elemental tint** — optional region/light overlay (`lava` → `ALV_`,
   `ice`/`water` → `AWT_`) layered on any archetype, reusing the existing region
   volumes.

Room semantic-type vocabulary (shared, realisable): `entry_hall, gatehouse,
guard_post, barracks, armory, prison_cell, storeroom, laboratory,
summoning_hall, ossuary, flooded_gallery, sump, shrine, sacrifice_chamber,
forge, ritual_chamber, battle_arena, throne, vault, inner_sanctum,
collapsed_gallery, warren, passage`. Each type → deterministic realization
rules (shape/proportion bias, region, light mood, elevation character, palette)
plus suggestion fields (prop hints, encounter intent, boss) carried as data.

### KNOWN GAP — race scale is relative, pending real EQ model dimensions

The race-scale multipliers (e.g. `giant` 2.2×, `froglok` 0.9×) are **relative
placeholders**. Real limits should come from EQ model bounding boxes (doorway
clearance, headroom per race), which we do not yet have. The RoF2 install at
`F:\everquest_rof2` could later be mined for model bounds the same way the
era-fidelity triangle-edge table was derived. Until then, treat race scale as a
tunable relative knob, not an accurate per-race measurement. Tracked in ROADMAP.

### Multi-area zones — "districts"

Real EQ zones are frequently several places in one: Guk's living upper vs.
undead lower, Sebilis splitting three ways at "the rock", Permafrost's castle +
goblin warren, Chardok's fortress + the separate Halls of Betrayal faction
([Chardok B, Allakhazam](https://everquest.allakhazam.com/db/zones.html?zstrat=185)).
So a zone's narrative is not always one linear arc — it is often 2–3 **districts**,
each its own sub-theme, joined at a hub or a gated threshold, sometimes in
tension (live vs. dead, loyalists vs. betrayers).

Model: a **graph partition on top of the pacing graph**. Grow districts from
seed rooms outward along graph edges (multi-source BFS / graph cut) so each
district is contiguous and boundaries fall on natural chokepoints (hubs). The
boundary corridor becomes a **threshold** — a natural place to reuse the
existing gating (a locked door between districts) and to flip palette/light
mood sharply so crossing *feels* like entering a new place. Each district gets
its own sub-theme and its own entrance→climax arc.

Decisions (from the user):
- **Auto-split large zones by default, with an off switch.** Rough thresholds:
  ≥8 rooms → 2 districts, ≥14 → 3, capped at 3. A `multi_district` control /
  planner field forces single-district.
- **Multiple climaxes are allowed** — climax is *per-district*, not per-zone. A
  2-district warring zone legitimately has two boss rooms. The existing
  single-climax pacing is just the 1-district case.
- **District relationship** tag (`sequential` / `factional` (in tension) /
  `abandoned_vs_active`) proposed by the planner, tinting suggestion fields
  (e.g. "faction skirmish at the boundary").

IR impact (advisory metadata, rides in the sidecar + future SQL export, like
pacing/gates — never baked into geometry): `RoomSpec` gains `district`,
`district_theme`; `ZoneSpec` gains `districts: List[DistrictSpec]`. Planner
`ZonePlan` gains optional district proposals; a deterministic partitioner
realises them and invents sensible defaults when the planner is silent.

### Implementation sequencing (two steps)

- **Step 1 — single-district content layer:** archetype × race × elemental
  tint; semantic room types assigned from the pacing arc; theme →
  geometry/region/light/texture realization; suggestion fields carried to
  sidecar + map + viewer. Verified in the 3D viewer before moving on.
- **Step 2 — districts:** graph partition (auto-split + off switch),
  per-district sub-themes, per-district climaxes, gated thresholds, map/viewer
  rendering of district boundaries. Verified separately.

Each step gets its own acceptance eyeball pass because structural tests passing
is necessary but not sufficient (the cave lesson).

---

## In-client EQ map files (`maps/*.txt`)

The EverQuest client renders its in-game Map window (M key) from plain-text line
files in the client's `maps/` folder (or a selectable subfolder of it). These
are **not** the same as our web `*.map.svg` schematic — they are navigation
overlays the player trusts to match the walls they walk, so they must be derived
from the actual walkable geometry (the TER mesh), not from the ZoneSpec.

Confirmed against the martinlindhe/eqformat_map reader (Rust, with unit-test
vectors) and the EQ forums; the crande25/eql-maps project generates these the
same mesh-derived way we plan to.

### File layout

- One base file per zone, named by the zone **short name**: `<shortname>.txt`.
- Up to three additional layers: `<shortname>_1.txt`, `_2.txt`, `_3.txt`.
  The reader auto-detects layers 1–3 alongside the base. Layers are typically
  used as depth bands (main level vs. above vs. below).
- The client matches a map to a zone by filename short name — renaming breaks it.
- Custom maps go in a **subfolder** of `maps/` (e.g. `maps/Brewall/`) so they
  appear as a selectable set and the patcher doesn't overwrite them.

### Record formats (one record per line)

Two record types, distinguished by the first two characters of the line:

```
L  x1, y1, z1, x2, y2, z2, R, G, B
P  x, y, z, R, G, B, size, text
```

- `L ` — a **line** segment (wall / ledge boundary). Nine comma-separated
  fields: two 3D endpoints then an RGB colour.
- `P ` — a **label/point**. Eight fields: a 3D position, an RGB colour, an
  integer `size` (2 = medium), and the label text. Label text may itself
  contain commas (parsers split into at most 8 fields, text takes the remainder).
- Colour channels are integers **0–255** (readers normalise to 0–1).

Verified example records (from the reader's test vectors):

```
L 2881.0, -2022.0, -295.0, 2885.0, -2027.0, -295.0, 128, 255, 0
P 5531.2642, -168.7061, -299.5485, 128, 255, 0, 2, Gargoyle_Island
```

### Coordinate convention (important)

EQ is Z-up and ~1 unit ≈ 1 foot (same as our world). **But the map file's first
two coordinates are inverted relative to in-game `/loc`:** both negated in sign
*and* swapped in order. In practice the map X/Y are a transform of world X/Y
(negate + swap); Z is world Z. This transform must be applied when writing (and
inverted when reading) or the map renders mirrored/rotated versus the zone.

### Depth-band colouring (community convention)

Lines are coloured by the depth band of the geometry they trace, so overlapping
levels stay legible:

- **Black** — the main walkable level (most of the floor area).
- **Tan / gray** — above the main level.
- **Purple / blue** — below the main level.

Only wall/ledge boundaries are drawn; flat floor interiors are left blank so the
map stays readable when levels overlap.

### How a map is extracted from zone geometry (the mesh-derived method)

The approach used by crande25/eql-maps and the one we adopt:

1. Take the zone's TER triangle mesh (we have it in-process at build time; no
   need to re-unpack the `.eqg`).
2. Classify each triangle as floor / wall / ceiling by its surface normal.
3. Keep the edges where floors meet walls — the walkable boundary — plus open
   ledges. Discard flat floor interiors and ceilings.
4. Chain those edges into polylines; simplify; drop duplicate contours.
5. Convert world → map coordinates (negate+swap XY) and colour by depth band.
6. Emit `L` records (and optional `P` labels for entrance / boss from pacing).

This "extract top-down wall outlines from the mesh" core is reusable: it drives
both the EQ `.txt` export and (separately) an accurate web SVG outline layer.

### Scope boundary

Mesh-derived means the map is only correct where the mesh is trustworthy and in
the room-graph coordinate frame — **dungeon/box backend today**. Outdoor/cave are
in a different coordinate frame (see Known issues) and cave is shelved, so EQ map
export is dungeon-first, matching where the traversability gate already runs.

Sources: martinlindhe/eqformat_map (format + test vectors), crande25/eql-maps
(mesh-derived generation method), EQ official forums (coordinate inversion),
Fanra's EQ wiki (maps folder / layer files). Content rephrased for compliance.

---

## Step 17: takeover and doors

Export spec task 2 (`.kiro/specs/zone-generator-export/`). Read from the RoF2 install at
`F:\everquest_rof2` (read only) on 2026-11-16, plus EQEmu's server source and docs.
`tests/test_export_grounding.py` pins the install facts below (it skips without `EQ_PATH`).
The decisions are 7 to 9 in the spec's `archive.md`.

### 1. Which archive the client loads for a short name

**Four short names ship both a zone `.s3d` and an `.eqg`:** `arena`, `nektulos`, `tutoriala`
and `tutorialb` (zone archives only; companions such as `_obj`/`_chr` left out). Each `.s3d`
holds a full `<short>.wld` (arena 2,600 polygons, tutoriala 73,633), so neither copy is a stub.

| short | `.eqg` holds | loose `<short>.zon` |
|---|---|---|
| arena | `ter_arena.ter`, 55 `.mod`, no `.zon` | EQGZ, 56 models (`TER_arena.TER` + all 55 `.mod`), 129 objects |
| tutoriala | `ter_jail.ter`, no `.zon` | EQGZ, 29 models, 147 objects |
| tutorialb | `ter_mines.ter`, no `.zon` | EQGZ, 134 models, 938 objects |
| nektulos | its own `nektulos.zon`, no `.ter` | EQTZ (v4 text header, 254 bytes) |

So for `arena` the loose `.zon` is the missing half of the `.eqg` zone: its model table names
`TER_arena.TER` and every `.mod` in `arena.eqg`, and nothing outside it. Across the install there
are 167 loose `.zon` files: 163 EQGZ beside an `.eqg` (3 of them also beside an `.s3d`), 2 EQGZ
with no archive, and 2 EQTZ, both beside an `.eqg` (one of them `nektulos`).

**The client tries `<short>.eqg` first.** The client's own log (`Logs\dbg.txt`, from the user's
October sessions) has one line per zone-in, "Attempting to load `<short>`.EQG.", for every zone
entered: `clz`, `tox`, `erudnext`, `crushbone`, `mistmoore`, `unrest`. When the `.eqg` exists it
logs "Loaded `<short>`.EQG." (`clz`); when it doesn't (the other five, all `.s3d`-only) it goes on
to "Loading zone specific files." and loads the `.s3d`. `clz` (character select) is built
exactly as `arena` is: `clz.eqg` holding `ter_basemain.ter` and no `.zon`, plus a loose EQGZ
`clz.zon` naming only files in it; the client loads it. EQEmu's map builder takes the same order
(zone-utilities `azone/map.cpp`: standard `.eqg`, then v4 `.eqg`, then `.s3d`; its EQG loader
reads a `.zon` inside the archive and falls back to the loose `<short>.zon` only when the archive
has none).

**Conclusion:** with both present the client loads `arena.eqg` + `arena.zon`, not
`arena.s3d`. **Not seen directly for `arena`**: the log has no arena visit. Task 10 confirms it:
zone into `arena` and look for "Loaded arena.EQG." in `Logs\dbg.txt`. Also unverified: which
`.zon` wins when our `.eqg` carries one inside and a loose `arena.zon` is still there (azone
prefers the one inside; the client is unknown).

**Install steps that work either way:** move aside `arena.eqg`, `arena.zon`, `arena.s3d`,
`arena_obj.s3d` and `arena_EnvironmentEmitters.txt` (it places four brazier-flame emitters at
the stock zone's coordinates), then copy in our `arena.eqg` (its `.zon` inside) and our
`maps\arena*.txt`. Keep `arena_chr.s3d` and `arena_chr.txt`: they hold the zone's NPC models,
not geometry.

### 2. What a doors row's `name` names, and our Door model

**The name is a model the client already holds for the zone.** EQEmu's docs give names such as
`IT11161` and `POPCREATE501`; the server only copies `name` into the spawn packet
(`zone/doors.cpp`), so the client draws whatever model of that name it has loaded.

- **`.s3d` zones:** the actor's tag without `_ACTORDEF`, from the zone's `_obj` archive. The
  decor catalogue (`rules/decor/catalogue.json`) lists 199 actors named DOOR/GATE/PORTC across
  163 `_obj.s3d` archives; 155 of them are never placed in any `objects.wld`, as expected of
  models the server places as doors (e.g. `ARENADOOR200` in `arena_obj.s3d`, `DOOR1` in
  `freporte_obj.s3d`).
- **`.eqg` zones:** the `.mod` file name without `.MOD`, keeping its `OBJ_` prefix; an EQEmu
  forum thread shows `dreadspire` rows named `OBJ_BDRM_LDOOR`, and `dreadspire.eqg` holds
  `obj_bdrm_ldoor.mod`. 207 of the 1,057 `.eqg` archives hold 1,177 `.mod` files named
  DOOR/GATE/PORTC, most starting `obj_` (not all: `pok_door.mod`, `bazaardoor.mod`). In
  `arena`, `tutoriala`, `tutorialb` and `dreadspire` every door `.mod` is also in the `.zon`
  model table (and placed once there as an object).
- **Shared door archives** exist but load per zone, not globally: `doors.eqg` (8
  `obj_switch_door_*` models, 1.1 MB) and `pok_book.eqg` load only for zones whose
  `<short>_assets.txt` names them (146 such lists; `doors.eqg` is in 2). `arena` has none.

**Nothing global is a door.** `Resources\GlobalLoad.txt` names no door archive (its object
archive is `Global_obj`, the rest item and character archives), and `global_obj.s3d` holds one
actor, `POKTELE500` (the old PoK stone). The `GEquip*` item models (`IT…`) are global, but no
item model is known to be a plain door.

**Decision: pack the Door model into our `.eqg`.** The model is **`BBDOOR1`**, the classic plain
door, from **`ecommons_obj.s3d`** (`ecommons_obj.wld`; the same mesh ships in `kithicor_obj`,
`nro_obj`, `oasis_obj` and `qeynos_obj`), catalogue mesh hash `b29f16cdfe7d32a6`. It is a
12-triangle slab **1 x 10 x 10.05 units** (x thick, y wide, z tall) with its hinge edge at the
origin (x -1..0, y -10..0, z 0..10.05) and one 256x256 texture, `bbdoor1.bmp`. Through the decor
importer (`generators.decor.stock.Importer`) it packs as a 1,134-byte `.mod` plus a 262,272-byte
DDS. It's era-right for the Classic default and goes through the importer Props already use.
Task 5 packs it as `obj_bbdoor1.mod` (the stock `OBJ_` convention) and lists it in the `.zon`
model table with no placed object; the rows name it `OBJ_BBDOOR1`. **Unverified until task 10:**
that the client draws a door from a `.mod` listed in the `.zon` but not placed there, and that
the `OBJ_` stem (not the file name) is the lookup key in our own zone.

### 3. The doors row for a plain locked door

From the pinned columns (`common/repositories/base/base_doors_repository.h`, 37 columns),
`zone/doors.cpp`, and EQEmu's "Door Open Types" page:

| column | value | why |
|---|---|---|
| `opentype` | `0` | 0-4 and 8 are the standard 90° swing (opens backward), 5-7 the same opening forward; 50, 53 and 54 draw nothing, 57 teleports, 59/60 lift |
| `size` | `100` per 1.0 scale | default 100, a uniform scale of the model. `BBDOOR1` is 10 units, so a 50-unit corridor wants `size = 500` (task 4 computes it from the corridor) |
| `heading` | 0-512 float | EQ units, not degrees: `doors.cpp` wraps it with `fmod(h, 512)` and turns it by `h * pi/256`, rotating by `-h` about Z (clockwise seen from above). Degrees convert as `deg * 512 / 360` |
| `incline` | `0` | int, a tilt of the model; 0 stands it upright |
| `keyitem` | a placeholder item id per tier | locked: the door opens freely only when `keyitem`, `lockpick` and `guild` are all 0 |
| `lockpick` | `0` | with a key set, 0 means anyone with Pick Lock skill and a pick can open it (`lockpick <= skill`); the docs' "-1 = unpickable" has no special case in `doors.cpp` |
| rest | stock defaults | `nokeyring 0`, `triggerdoor 0`, `door_param 0`, `invert_state 0`, `dest_zone 'NONE'`, `client_version_mask 4294967295`, `close_timer_ms 5000`, `min/max_expansion -1`, `version 0` |

The hinge is at the model's origin, so the row's position is one jamb of the opening, not its
centre: the slab runs along local -y from `pos`, turned by `heading` (task 4 offsets it).

Sources: the RoF2 install (archives and `Logs\dbg.txt`); EQEmu/Server
`common/repositories/base/base_doors_repository.h` and `zone/doors.cpp` (master,
2026-11-16); docs.eqemu.dev "doors" schema and "Door Open Types"; EQEmu/zone-utilities
`src/azone/map.cpp` and `src/common/eqg_loader.cpp`; EQEmulator forum threads on doors in
newer zones (via search snippets; the pages refused direct reads). Content rephrased.
