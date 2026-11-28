# P-7 Engaging every time — design (living)

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

Checked against the code at master `c3d9b99` (2026-11-27, the commit that opened the project-docs spec). Authoring guide for rule sets:
[`docs/TOPOLOGY_RULES.md`](../../TOPOLOGY_RULES.md).

## Two layout engines

`LayoutGenerator` ([`generators/layout.py`](../../../generators/layout.py)) runs one engine behind the `LayoutEngine` seam
([`generators/layout_engine.py`](../../../generators/layout_engine.py)), then the shared steps (routing, elevation, pacing, gating,
Districts, semantics). Graph is the default for `dungeon` and `outdoor_dungeon`; `city` and plans
saved before [step 6](../../../.kiro/specs/zone-generator-graph-layout/tasks.md) use Classic.

| | Classic (`ClassicEngine`) | Graph (`GraphEngine`) |
|---|---|---|
| Rooms | scatter, push apart, join by a Delaunay triangulation cut to a minimum spanning tree plus some loops (TinyKeep) | grown by graph rewriting: a rule set's recipe of stages applies pattern → replacement rules until no placeholder is left |
| Rules | in code | TOML under [`rules/topology/`](../../../rules/topology) ([`classic_eq.toml`](../../../rules/topology/classic_eq.toml), [`warren.toml`](../../../rules/topology/warren.toml), layer [`temple.toml`](../../../rules/topology/layers/temple.toml), `themes.toml`), checked strictly on load |
| Placement | scatter spread × hall length | spring layout, each neighbour on its own wall; caves at any bearing with angled entries; outdoor jitter inside the Envelope; built and hewn keep the row-and-column lattice (the user's choice) |
| Levels | one | whole-number Levels from `above` / `below` / `level` relations; `may_overlap_in_plan` stacks rooms; Verticality scales the vertical rules (flat one Level, moderate as written, dramatic double) |
| Climax | pacing's deepest room | the rules' `deep` room |

## Scale

Rooms and corridors are sized from the resident race's body height H: rooms 2.5–10 H tall and
8–20 H across (sides spread as stock's do: the 5th to 95th percentile runs 0.66 to 2.1 times the median, 26 H at most), corridors 3 H
wide and 2.5 H tall. `hall_length` (0.5–3) scales the Graph run, the Classic scatter and the
outdoor gap; below 1 rooms still keep a corridor width apart. `size` shifts within the race's
bands; the `cave` Purpose shifts footprints from [`styles/cave.json`](../../../styles/cave.json).

## Pacing and gating

Roles from the graph: `entrance` (nearest the way in), `hub`, `deadend`, `climax`, with
`graph_depth`. Locks are advisory `GateSpec`s placed so every key is reachable before its lock
(the solvability invariant; threshold Gates first in a districted zone). Neither becomes
geometry; an Export turns a Gate into an EQEmu door.

## Districts ([`generators/districts.py`](../../../generators/districts.py))

Off by default; on from the Controls box, `--districts`, or a prompt phrase ("fallen to the
dead", "upper and lower"). A dungeon of 8+ rooms is cut into 2 Districts (3 from 14 rooms) by a
tree cut of the room graph, before pacing, so each District gets its own climax. Each District
has a Purpose (by relationship: `sequential`, `factional`, `abandoned_vs_active`, `intrusion`, or
pinned), palette, light mood, race and Threshold corridor. Since [step 22](../../../.kiro/specs/zone-generator-district-looks/tasks.md) a room's wall style and
decor follow its District; since [step 31](../../../.kiro/specs/zone-generator-district-races/tasks.md):

- **Race per District**: sizes its rooms, corridors and decor; a giant District's halls run 3×;
  a link between Districts is sized in the smaller race (capped at 164 H).
- **Intrusion**: a younger District breaks into its host by up to 3 breaches, best effort; its
  decor spills into the host rooms.
- **Drops**: 1 in 10 links between Districts is a one-way drop (6–80 u); the gate needs strong
  connectivity.

## What a room holds ([`room_layouts.py`](../../../generators/room_layouts.py), [`room_scales.py`](../../../generators/room_scales.py), [`transitions.py`](../../../generators/transitions.py), [`rules/rooms/`](../../../rules/rooms))

- **Scales**: Finish (its wall style), Structure and Clutter, each a Weights array over 0–10
  written by Layers (rule set, theme, race, overlay, room kind) whose product blends as a
  geometric mean; a room leans toward its neighbours by a Coherence, stopping at a District edge.
- **Features**: solid structure (pillar, boulder, dais and kin) placed by recipes
  ([`layouts.toml`](../../../rules/rooms/layouts.toml)) off the Spine, the paths joining a room's doors; the gate judges them.
- **POIs**: advisory spots in the sidecar.
- **Transitions**: where two rooms' styles meet, a corridor carries a Seam, Frame or Breach
  ([`transitions.toml`](../../../rules/rooms/transitions.toml)).

## Landscapes

- **Outdoor dungeon** ([`outdoor_dungeon.py`](../../../generators/outdoor_dungeon.py), [`envelope.py`](../../../generators/envelope.py)): a compact wilderness with a Host_Hill
  Landform; the dungeon is laid out inside an Envelope (the hill's footprint, a floor limit, the
  surface less a Rock_Cover); one Entrance (Apron trench, one-cell Tunnel, Mouth); rooms go only
  down from the Tunnel's Level.
- **Sites** ([`generators/sites/`](../../../generators/sites), [`rules/sites/`](../../../rules/sites)): the World posts point `site` Sockets on good
  ground in Groups (a per-biome `groups` block; for plains, a Clark–Evans clustering ratio of 0.50–0.95, where 1 is random and lower is more clustered). The Sites stage draws a kind
  by biome and Inhabitant weights (human, orc, gnoll, centaur), then stands it on the next fitting
  point in Group order. 11 Structure kinds; camp, hut, farmstead, watchtower, shrine, ruin recipes.

## Quality ([`generators/quality.py`](../../../generators/quality.py))

`measure(spec)` reads the room graph only: `cyclomatic`, `max_degree`, `dead_end_ratio`,
`critical_path_ratio`, `branching_factor`, `elevation_range`, `elevation_levels`,
`role_diversity`, `room_type_diversity`, `size_cv` (spread of room sizes), `district_balance`. Bands (`BAND_TABLE`) are
keyed by zone type, layout, room count, verticality and District count, one-sided on each
metric's dull side, set so at most 1% of ordinary Draws fail (0.5% outdoor dungeon); zones under
4 rooms are unbounded. A random-seed generate redraws a failing plan before building (up to 32
Draws; about 1.03 per generate on average). A pinned seed, a rebuild or an edit is built anyway and marked
degraded (`quality_outside_bands_pinned`, `quality_degraded`, `edit_outside_bands`). The page
shows a banner with no close button and lists the metrics out of band.
