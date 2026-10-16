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
