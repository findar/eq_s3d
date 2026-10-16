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
