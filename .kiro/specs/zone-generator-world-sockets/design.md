# Design — zone-generator-world-sockets (roadmap step 12)

Written 2026-11-12 at master `ad392b8`. Verify against the code before working a task; the
line references below are from that commit.

## Overview

```
plan ── world inputs (seed, biome, edges, zone size, Socket requests: a Host_Hill)
         │
WORLD    world_for(...) ──> World: terrain grid, water, regions, Spawn, Sockets
         │                   saved: <name>.world.json          tests: tests/fixtures/worlds/
         │
ATTACH   per Socket, in order (hillside, then ground), from the World + plan fields + rooms_seed
         │  (rooms in plan_to_spec, Sites in the build: see "Where the stages run")
         │  hillside: Envelope -> layout -> fit -> Entrance (+ the Apron as a Terrain edit)
         │  ground:   Sites on the World's ground, keeping clear of earlier Attachments
         │  root:     the layout, as today
         │                   saved: <name>.attach.json
         │
BUILD    TER from the World + Terrain edits + Attachments; RoomContexts from the mesh
         │                   saved: <name>.rooms.json          tests: tests/fixtures/rooms/ (step 11)
         │
DECOR    Props per RoomContext, from decor_seed (step 11, unchanged)
         │
PACK     trees, Site models, Props -> ZON, .eqg, GLB, sidecar; then the gate
```

Each stage reads only the hand-off before it, plus its own controls and seed. With no stage
seed set, every stage seed is the zone's seed, and every build is step 11's, byte for byte
(Req 6.1).

## Today's pipeline (as read at `ad392b8`)

### Where things are made

| What | Where | Reads |
|---|---|---|
| Plan -> spec, one seed (`rng_seed`) for all | `ai/expand.py::plan_to_spec` | the plan |
| Dungeon/city layout | `LayoutGenerator.generate` (`generators/layout.py`), then `_dress_rooms` (Scales, walls, Features) for graph dungeons | `rng_seed` |
| Wilderness world | `wilderness/build.py::wilderness_spec` -> `synthesize_landscape` (matrix, rewrite, synth, bowl; `lru_cache(8)`) | seed, biome, edges |
| Outdoor dungeon | `outdoor_dungeon.py::outdoor_dungeon_spec` | see below |
| Geometry | `ZoneBuilder._build_geometry` -> `backends.backend_for(zone_type)`: `BoxBackend` (`geometry.build_mesh`) or `TerrainBackend` (`build_wilderness_ter`, or `build_outdoor_dungeon_ter`) | the spec |
| Sites | `ZoneBuilder.build` -> `wilderness/build.py::sites_for` -> `sites/placement.py::place_sites` (own salted stream from the zone seed) | landscape, the **built TER** |
| Trees | `wilderness/build.py::vegetation_for` (keeps off Sites) | landscape, built TER, Sites |
| Decor | `builder.py::decor_for` -> `room_context.contexts` / `site_contexts` -> `decor.placement.place` | built TER, spec; `decor_seed` |
| Gate, retry | `pipeline.py::generate_validated`: build, `_traversal_report` / `outdoor_dungeon_report` / bowl, `check_eqg`; a fresh seed for the whole zone on failure | the `.eqg` |

### The outdoor dungeon, step by step

`outdoor_dungeon_spec(name, seed, ...)`:

1. `wilderness_spec(..., landform=DEFAULT_HOST_HILL, zone_size=1200)`: the world is asked for
   a hill (radius 250, relief 120, flank 300) at matrix-build time. The Landform is the same
   whatever the dungeon; its centre and approach side come from the seed.
2. `build_wilderness_ter(spec, ...)`: the whole host TER, used only for planning.
3. `host_envelope`: footprint = the hill disc clipped to the bowl's interior (no room under
   the Rim's strips); surface = the TER's grid, interpolated as the client walks it; floor
   limit = the ground at the hill's approach foot less `floor_depth(verticality, race)`;
   Rock_Cover 24 u; `entry` = the approach foot.
4. `plan_dungeon`: lay out in the Envelope (`layout_in_envelope`), shrinking up to three
   times and trying the graph engine's facings; `align_to_grid` slides the layout under half a
   terrain cell so the entrance room's wall holds a cell; `plan_entrance` picks, over that
   wall's strips and every portal row, the Tunnel with the least Apron digging that keeps the
   Rock_Cover, the grade and clear of other rooms.
5. The Apron (dug ground in front of the Mouth) may lower the Spawn; the layout's rooms,
   corridors, lights and gates are copied into the host spec; `wilderness["dungeon"]` records
   the Entrance, Rock_Cover, floor limit, rooms asked for and warnings.
6. In the build, `build_outdoor_dungeon_ter` builds the host TER **again**, digs the Apron,
   cuts the Mouth and merges the dungeon mesh.

So the Mouth is an output of the room layout, not an input to it; the world is shaped for the
dungeon only through the Landform request; and the terrain grid, node types and bowl are what
the dungeon's planning reads of the world.

### Sites

`place_sites(land, ter, seed, ...)` reads the TER's vertex grid (`ground_for`: heights from
the built TER, so an outdoor dungeon's Apron is already dug), the synth's node types, Rim seal
and playable-interior masks, Spawn, and the outdoor dungeon's Kept_Clear capsules
(`keep_clear_shapes`: the hill disc, the Tunnel, the Apron). It then draws, per Site, an
Inhabitant and a kind, and a centre scored by the recipe's likes plus a Gumbel draw, from one
stream. "Where" and "what" are interleaved in that stream.

### What every build recomputes that a hand-off could skip

- The outdoor dungeon's host TER, twice per build (plan and build). Cheap (finding 2), but
  the planner needs no TER at all, only the grid.
- On a decor reroll (`decor_seed`), the planner, the whole TER, the gate and the maps, though
  only Props change. On a gate failure, a fresh seed for world, rooms and Props alike.
- In tests: a zone build (and usually the gate) wherever a test needs a hill, an Entrance, a
  Site or a room. Only decor tests run off a recording today (step 11 task 18).

The in-process `lru_cache`s (landscape, Sites, trees) don't survive across test workers or a
server restart, and they key on the TER's fingerprint, so they only save repeat calls inside
one build.

## Research findings

### 1. Where the time goes in one build (design-time probe, `ad392b8`)

Measured with seed 7 at the plan's defaults, Decor Normal, the install present, on this
machine while the suite ran in parallel (so slow by an unknown factor; ratios are what count).
Warm means the catalogue, models and imports already loaded.

| Zone type | World (landscape synth) | Plan (`plan_to_spec`) | Build, Decor none (warm) | Build, Decor Normal (warm) | Gate |
|---|---|---|---|---|---|
| dungeon | — | 1.25 s cold | 0.18 s | 1.87 s | 4.6 s |
| city | — | 0.01 s | — | — | 0.7 s |
| wilderness | 0.12 s | 0.12 s | 0.22 s | 0.99 s | 2.0 s (bowl) |
| outdoor dungeon | 0.03 s | 0.89 s | 0.47 s | 2.12 s | 9.6 s |

A cold first build with Decor on took 5-13 s (catalogue load, model import). In a warm
dungeon build with Props, `decor_for` is about 1.3 s (placement 0.7-1.2 s, `contexts` 0.5-0.7
s) and packing the PFS about 0.5 s.

So **making terrain is not what's slow**: a landscape is 0.03-0.12 s. The time is in the gate
(seconds per zone), cold model import, decor placement and packing. Isolation pays by letting
a test run one stage without the stages after it (build, pack, gate), not by skipping terrain.

### 2. Where the suite's time goes

The full suite was run as the task brief asks (`EQ_PATH='F:\everquest_rof2' python -m pytest
tests/ -q --durations=30 -p no:cacheprovider`, xdist `-n auto`) at `ad392b8`: **2383
passed in 3211 s (53.5 min)**, with finding 1's probes running beside it for a few minutes.
Per-test times are wall time on a busy worker, so they overstate each test alone; their
order is what counts. The 30 slowest, by file:

| File | Tests in the 30 | Their time | What they do |
|---|---|---|---|
| `test_vertical_build.py` | 11 (`test_stacked_builds_pass_the_gate_no_worse_than_flat[...]`) | 3,345 s | build and gate a sweep of seeds, stacked vs flat |
| `test_graph_layout_build.py` | 3 (`test_graph_builds_pass_the_gate_no_worse_than_classic[...]`) | 1,930 s | build and gate a sweep, graph vs classic |
| `test_decor_bands.py` | 3 (`test_dense_passes_the_gate_first_try[...]`, `test_p12_...[dungeon]`) | 1,171 s | build, gate and survey 40 seeds |
| `test_site_bands.py` | 3 (`test_stock_r_band`, `test_gate_first_try_rate_holds`, `test_p9_...`) | 1,026 s | build and gate wildernesses over seeds |
| `test_properties_layout.py` | 2 (`test_flush_openings`, `test_elevation_grade_cap`) | 844 s | Hypothesis over layouts (not marked `slow`) |
| `test_topology_embed.py` | 1 (`test_big_races_keep_their_loops[giant]`) | 478 s | graph layouts at giant scale (not marked `slow`) |
| `test_walls_build.py`, `test_features_sweep.py` | 3 | 666 s | first-try sweeps by wall style and Features |
| `test_properties_pipeline.py`, `test_pipeline.py` | 2 | 765 s | pipeline lifecycle (one not marked `slow`) |
| `test_corridor_clearance.py`, `test_bridges.py` | 2 | 690 s | sweeps |

What this says:

- **The suite's time is gate sweeps.** Twenty-five of the thirty are "build N seeds, run the
  zone gate on each, compare a first-try rate". They need the Build stage and the gate on the
  merged mesh; a World corpus alone can't replace them. What isolation buys them: they can
  share builds (the vertical, graph, walls and features sweeps build overlapping seeds per
  zone type and each builds its own), and a stage that checks itself (Req 7.4) lets a sweep
  run the Attach stage's check on many seeds and the zone gate on a few.
- **Three slow tests are in the fast suite** (`test_flush_openings`,
  `test_big_races_keep_their_loops[giant]`, `test_backend_fallback_reaches_warnings_and_sidecar`):
  together about 1,470 s of worker time that `-m "not slow"` still pays.
- **Where the corpora help directly**: the outdoor-dungeon planning and Site placement tests
  (task 12), and any sweep that measures only rooms or Sites (the Site bands' `stock_r` is
  placement only, 620 s).

**Targets** (Req 7.5; task 1 re-measures on an idle machine and may revise them, with the
user's word): the fast suite (`-m "not slow"`) under **5 minutes**, the full suite under
**25 minutes**, each test's first-try and band checks kept. Task 13 gets there by sharing
builds across the sweep files, moving placement-only and planning-only sweeps onto the
corpora, and marking or shrinking the three unmarked slow tests.

### 3. What the code already offers

- `Entrance.to_dict` / `from_dict`, `Landform.to_dict` / `from_dict`, `ZoneSpec.to_dict` /
  `from_dict`, `RoomContext` with a versioned JSON form and `room_context.dumps` (stable text).
- `Envelope(footprint, floor_limit, surface, rock_cover, entry)` takes any vectorised surface
  callable; `outdoor_dungeon._grid_surface(z, origin, res)` makes one from a height grid.
- `vegetation.placement.ground_for` and `sites.placement._terrain` need only the TER's vertex
  grid, the synth's node types, Rim seal and playable-interior masks, origin and resolution.
- The outdoor dungeon's grid is 32 x 32 cells of 40 u (zone 1200 u); a wilderness is 64 x 64
  (2400 u). A whole World's terrain is a few thousand numbers.
- `scripts/record_rooms.py` and `tests/test_room_context.py`: the recorder and contract test
  pattern this step repeats for Worlds.
- `scripts/decor_room.py`: one context to a GLB, the one-stage loop this step extends.

## The Socket

```python
@dataclass
class Socket:
    id: str                 # "root", "hill0", "ground"
    kind: str               # root | hillside | ground   (door reserved, design question 3)
    x: float; y: float; z: float      # the attach point: a hillside's approach foot (z = the
                                      # open ground there); ground: Spawn; root: the origin
    yaw: float              # the way in faces; a hillside's approach side as an angle
    side: str               # N, S, E, W where it has one ("" otherwise)
    width: float; height: float       # the opening: a hillside's least Tunnel (one terrain
                                      # cell); 0 where it doesn't apply
    level: int              # 0 today
    accepts: tuple[str, ...]          # ("dungeon",), ("dungeon", "city"), ("site",)
    ground: dict            # by kind, below
```

- **`hillside`** — `ground` holds the hill's footprint polygon (already clipped to the bowl's
  interior), the Rock_Cover, the grid's origin and resolution, and the indices of the
  undiggable cells (`_UNDIGGABLE` within a cell). The surface is the World's height grid
  (the TER's vertex grid after the water bed sinks), which the Socket references rather than
  copies. What the Socket does **not** fix: the floor limit (it depends on the dungeon's
  verticality and race, `floor_depth`), and the exact Mouth (design question 1).
- **`ground`** — `ground` names the playable ground (the World's masks) and Spawn, and carries
  `keep_clear`: the capsules earlier Attachments add (the outdoor dungeon's hill disc, Tunnel
  and Apron, today's `keep_clear_shapes`).
- **`root`** — nothing; a standalone dungeon or city.

A Socket's JSON keeps floats as Python writes them (`repr`), never rounded: the planner reads
the grid's heights and the footprint's points, and a rounded value moves a room (Req 1.5).
That is unlike the RoomContext, which rounds to 2 places because decor only reads it.

## The World

`generators/world.py` (new):

```python
@dataclass
class World:
    version: int
    recipe: dict            # zone_type, seed, biome, edges, zone_size, landform request
    terrain: Terrain | None # origin, res, heights (nx, ny) float64 exact, node_type raster,
                            # rim_seal and playable_interior masks, water_level
    regions: list           # RegionSpec dicts (water volumes, ...)
    spawn: tuple            # the safe point before any Apron lowers it
    sockets: list[Socket]

def world_for(zone_type, seed, *, biome, edges, zone_size, landform) -> World
```

`world_for` calls `synthesize_landscape` (unchanged) and reads off what later stages need. A
dungeon or city gets `terrain = None` and one `root` Socket. The World file is
`<name>.world.json`: about 100-200 KB for a wilderness, mostly the height grid.

The spec keeps its `wilderness` payload as the record of the World's inputs, so the Zone_Spec
JSON (and its golden hash) doesn't change; the World is derived from it, never stored in it.

## The Attach stage

```python
def attach(world: World, plan_fields, rooms_seed, engine) -> Attachments
```

Sockets attach in a fixed order: `hillside`, then `ground` (Req 3.3).

- **hillside** -> `outdoor_dungeon.plan_dungeon` reworked to read a Socket instead of
  `(host spec, TER)`: `host_envelope` from the Socket plus the dungeon's own floor depth;
  `align_to_grid`, `plan_entrance` and `_apron` on the Socket's grid. Output: the layout, the
  Entrance, the Apron as a Terrain edit (the dug height grid) and the Spawn's new height. The
  host TER is no longer built during planning (Req 2.4).
- **ground** -> `place_sites` reworked to take `(World terrain with edits applied, Socket)`
  instead of `(land, ter)`; `ground_for` and `_terrain` read the same arrays as today from
  the World. The stream is `sites_seed(rooms_seed)`: unchanged bytes while `rooms_seed` is
  unset.
- **root** -> `LayoutGenerator.generate` and `_dress_rooms` as today, seeded from
  `rooms_seed`.

The Attachments file `<name>.attach.json` holds, per Socket, the layout (the rooms, corridors,
lights, gates and layout record the spec gets today), the Entrance, and the Sites placement
(`SitePlacement.to_dict`, plus what rebuilding it needs).

### Order and Terrain edits

The Apron digs the ground before the Sites see it, and Sites keep off the Tunnel and Apron,
so the ground Socket must be read after the hillside attaches. Rather than hide that inside
the builder (today: `sites_for(spec, ter)` on the merged TER), the Attach stage applies each
Attachment's Terrain edits and Kept_Clear shapes to the World before the next Socket, and the
Build stage applies the same edits when it makes the TER. One function applies an edit, used
by both, so they can't disagree.

## Where the stages run

The Zone_Spec stays the IR, and its JSON stays what it is today (the golden hashes it). So
the stages split across the two calls that exist, without moving what the spec records:

- **`plan_to_spec`** runs the World stage and attaches the room Sockets (`root`, `hillside`).
  The spec gets the rooms, corridors, lights, gates, layout record and the Entrance, as
  today; the `wilderness` payload records the World's inputs, as today.
- **`ZoneBuilder.build`** keeps its signature and output. It re-derives the World from the
  spec's payload and seed (0.03-0.12 s), applies the Entrance's Terrain edit, makes the TER
  once, attaches the `ground` Socket (Sites, as `sites_for` does today but from the edited
  World), then trees, RoomContexts, decor and pack.

So the Sites Attachment is made in the build, as it is now, but from the World and the
earlier Attachments rather than from the TER. A stage driver (`generators/stages.py`, new)
holds the order and the edit-applying function both calls use.

Hand-offs are written next to the artifacts by the pipeline's post-pass: `<name>.world.json`,
`<name>.attach.json`, `<name>.rooms.json` (the RoomContexts, `room_context.save`). They are not
listed among the page's downloads (design question 6).

## Stage seeds

| Seed | Drives | Unset |
|---|---|---|
| `seed` | the World (matrix, synth, bowl), textures, trees | a fresh seed |
| `rooms_seed` | the Attach stage: the layout, its walls, Scales and Features; Site placement | `seed` |
| `decor_seed` | Props (step 11) | `seed` |

`rooms_seed` rides on the plan, the spec (`ZoneSpec.rooms_seed`, written only when set, so the
spec hash holds), the CLI (`--rooms-seed`), the controls and the page ("Reroll rooms", beside
"Reroll decor"). The sidecar's `seeds` block records all three. Trees stay on the World's
seed: they keep off the Sites, so a rooms reroll moves trees only near Sites.

## Bytes

What must not move, with no stage seed set (Req 6.1):

- `tests/test_layout_engine.py` GOLDENS (dungeon, dungeon_flat, temple_locks, city,
  wilderness, outdoor_dungeon) and the heightfield-layout golden: both the Zone_Spec hash and
  the `.eqg[:-4]` hash.
- The Decor and Site goldens (`test_decor_builds.py`, `test_site_builds.py`,
  `test_site_decor_builds.py`) and the room corpus (`scripts/record_rooms.py --check`).

How it holds: the World is derived from the same landscape; the planner reads the same
float64 grid (from the Socket, exact); the Sites' stream is salted from `rooms_seed`, which is
the zone seed when unset; no new spec field is written unless set. What would move once, if
the user chooses it: an exact Mouth Socket (question 1, every outdoor dungeon), point Site
Sockets (question 2, every build with Sites), corridor contexts (question 7, Decor-on builds).

## Testing in isolation

```
tests/fixtures/worlds/*.json  <── scripts/record_worlds.py (pinned seeds)
          │
          ├── attach tests: Envelope fit, Entrance, Apron, Sites   (no terrain, no TER, no gate)
          │
tests/fixtures/rooms/*.json   <── scripts/record_rooms.py (step 11)
          │
          └── decor tests                                          (no zone, step 11)
```

- **World corpus** (`tests/fixtures/worlds/`): Worlds from pinned seeds covering each biome,
  each approach side (N, S, E, W), water and none, and every Socket kind. A few MB at most.
- **Attach tests** load a World file and run one Socket's Attachment: milliseconds to a
  second, no `slow` mark. They check the Attach stage's own result (Req 7.4): every room
  inside the Envelope (`LayoutGenerator.fits`), the Tunnel covered and within grade, the Apron
  digging no undiggable cell, every Site's Kept_Clear and spacing.
- **Contract tests** (`slow`): a sample of the World corpus re-made from its seeds equals the
  files; an Attachment from a loaded Socket equals one from the live World (the exact-float
  check); the room corpus check stays.
- **Integration builds** keep the zone gate: a few per zone type, with the goldens.
- **The suite pass** (task 13): the slowest files of finding 2 that only need one stage move
  onto the corpora; files that need a build share one build per module where they can.

## Correctness properties

| # | Property | Req |
|---|---|---|
| P1 | A Socket and a World round-trip through JSON exactly; another version is refused, named | 1.1, 1.5, 5.3 |
| P2 | The World stage reads no room, Site or Decor field; same inputs give the same World text | 2.1, 2.3 |
| P3 | Each zone type offers its Sockets (wilderness ground; outdoor dungeon hillside + ground; dungeon/city root) | 2.2 |
| P4 | An Attachment from a saved Socket equals one from the live World | 1.5, 7.3 |
| P5 | A hillside Attachment's rooms lie in the Envelope; its Tunnel is covered and within grade; its Apron digs no undiggable cell | 3.1, 7.4 |
| P6 | Ground Attachments see every earlier Terrain edit and Kept_Clear shape; Build applies the same edits | 3.3 |
| P7 | With no stage seed set, every golden and the room corpus are unchanged | 6.1 |
| P8 | A new `rooms_seed` keeps the World file and the terrain outside the new edits | 4.2 |
| P9 | Every build writes its hand-offs; each stage rerun from its hand-off gives the same text | 5.1, 5.2 |
| P10 | The host TER is made once per outdoor-dungeon build | 2.4 |
| P11 | The suite meets finding 2's targets | 7.5 |

## Risks

- **Exact floats.** The planner's decisions (does a room fit, which strip, which portal row)
  turn on float comparisons. A Socket that rounds, or a grid rebuilt in another order, moves an
  outdoor dungeon. Hence repr floats, and P4.
- **Hidden reads.** `plan_dungeon`, `align_to_grid`, `plan_entrance` and `keep_clear_shapes`
  each call `landscape_for(host)` for the grid, resolution, node types, bowl interior or
  Landform. Every one must read the Socket instead, or the Attach stage still needs terrain
  and its tests can't run off the corpus. A test that fails if `synthesize_landscape` is called
  during an Attach test catches a missed one.
- **Two height grids.** The Entrance and `ground_for` read the TER's grid (after the water
  bed sinks); `keep_clear_shapes` digs a copy of `land.bowl.heights` (before). The World must
  carry what each reads, or a test must show they agree where the Apron digs (it never digs
  within a cell of water today).
- **The Apron and Spawn.** The Apron lowers the Spawn when it reaches it. The Spawn is World
  data, changed by an Attachment: it must flow through the Terrain edit, not be patched in
  `plan_to_spec`.
- **`pipeline.py`, `builder.py`, `main.py`, `ai/expand.py` are cross-branch hotspots.** Tasks
  that touch them are sequenced by `Depends`, and each keeps its edit small.
- **Gate attribution.** Rerolling only the failing stage on a gate failure is tempting but
  needs the gate to say which stage failed. Not in this step (design question 5).
- **Corpora go stale.** Each corpus has its contract test; a deliberate change re-records,
  in the same commit as the change.

## Open questions

These go to the user; each has a recommendation and what follows from it.

1. **What does a dungeon Socket fix: the hill, or the exact Mouth?**
   *Recommended: the hill.* The `hillside` Socket fixes the Host_Hill, its approach side and
   the entry point; the Attach stage lays out the rooms and then picks the exact Mouth inside
   the Socket, as `plan_entrance` does today, and reports it in the Attachment. Every outdoor
   dungeon keeps its bytes. The alternative, the World picking the Mouth (point, facing,
   floor) and the rooms building to it, is closer to "attach to that point", but the layout
   engines can't anchor an entrance room to a given wall today (TinyKeep scatters; the graph
   engine only biases its facing), so it needs a new layout constraint, raises planning
   failures, and changes every outdoor dungeon once. It becomes worth it when a World offers
   two or more mouths, which is out of this step.

2. **Are Site Sockets an area or points?**
   *Recommended: an area in this step.* One `ground` Socket names the playable ground; the
   Sites stage picks centres as it does now. Bytes kept. Points (the World places N Site
   spots, each with a size, and the Sites stage builds one Site at each) match the user's
   words and would fix step 10's "Sites spread at random where stock plains cluster", but they
   split today's interleaved draw (kind, then where), so every build with Sites changes once,
   step 10's count and size bands need re-checking, and small outdoor-dungeon grounds may
   offer no spot. A follow-up with its own look.

3. **Door Sockets (a building entrance in a city, a hut's interior)?**
   *Recommended: reserve the kind, offer none.* Cities are rooms like a dungeon's, with no
   buildings outside them, and step 10's Structures have openings but no interiors. The
   reader accepts `door` so the format needn't change later; nothing makes one.

4. **Which stage seeds?**
   *Recommended: `seed` (World), `rooms_seed` (rooms and Sites together), `decor_seed`
   (Props), each defaulting to `seed`.* Sites ride with the rooms because they attach to the
   same World in the same stage, and one "Reroll rooms" button is easier to read than two.
   The alternative, a separate `sites_seed`, is a small addition later if wanted. Trees stay
   on the World seed.

5. **Should a gate failure reroll only the failing stage?**
   *Recommended: not in this step.* A random-seed build that fails still draws a fresh seed
   for everything, as today, and a pinned seed still fails. Rerolling only the rooms would
   keep a World the user never chose, needs the gate to name which stage failed, and saves
   little time (finding 1: the World is the cheap part). Worth revisiting with M4.

6. **Where are hand-offs saved, and do rerolls read them back?**
   *Recommended: written into every build directory (`<name>.world.json`,
   `<name>.attach.json`, `<name>.rooms.json`), not offered as page downloads, and never read
   back by the server.* A reroll re-derives the earlier stages from their seeds; the World is
   0.03-0.12 s. One code path, nothing read from disk that a user could edit. The stage
   command (task 10) reads them, for the developer's one-stage loop. Cost: about 0.3-1 MB more
   per build directory.

7. **Corridor RoomContexts in this step?**
   *Recommended: yes, as one late task (Req 8).* Corridors are an output of the Attach and
   Build stages, and step 11's placement already handles `source = "corridor"`; stock puts as
   many Props in corridors and alcoves as in rooms. Decor `none` is unchanged; Decor-on
   goldens, the room corpus and the P12 bands are recaptured once. If no, it stays a
   follow-up and Req 8 is dropped.

8. **What should the suite's targets be?**
   *Recommended: the fast suite under 5 minutes, the full suite under 25 (today 53.5 minutes,
   finding 2), with every first-try and band check kept.* The fast suite is what agents
   iterate on; the full suite is run once before ticking a task. The fast suite wasn't timed
   separately here; task 1 does, and may revise the targets with your word. Most of the
   saving comes from sharing builds across the gate sweeps, which this step's stages make
   easier but which isn't only about Sockets.

## Decisions

None yet. The user's answers go here and in `archive.md` "Decisions".
