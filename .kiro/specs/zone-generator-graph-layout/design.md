# Design — zone-generator-graph-layout (roadmap step 6)

Written at master `67e5b69`. Verify against the code before working a task.

## Overview

`LayoutGenerator._generate_once` does two jobs today:

- **Job A, the rooms and the graph:** `_scatter_rooms` → `_separate_rooms` →
  `_connect_rooms` (`generators/layout.py`). This is the TinyKeep scheme.
- **Job B, everything after:** pacing (`_apply_pacing`, which also biases room
  size by role), themes (`semantics.label_rooms`), re-separation, elevation,
  crossing splits (`_resolve_crossings`), conflict drops
  (`_resolve_conflicts`), fitting to an Envelope, corridors, materials, the
  safe point, gating.

Step 6 puts Job A behind a `LayoutEngine` seam and adds a second engine:

```
            ┌─ ClassicEngine: scatter → separate → Delaunay/MST/loops      (today)
Job A ──────┤
            └─ GraphEngine:  rule set + theme layers (TOML, checked on load)
                               │  recipe: stage by stage, rewrite until no Area left
                               ▼
                             Topology_Graph  (kinds, size classes, vertical relations)
                               │  placement: "spring"
                               ▼
                             rooms in the plane + the graph's edges
                 │
                 ▼  (rooms, edges, entry point): the contract Job B takes
Job B: pacing, themes, elevation (reads vertical relations), crossings,
       conflicts, Envelope fit, corridors, gating
                 │
                 ▼
Box backend / terrain backend, walkability gate, maps       (unchanged)
```

This is graph rewriting as shaggydev's "Graph rewriting" (2022-11-20) lays
it out: a manual start graph with placeholders, rules that replace a pattern
with a structure (each saying where the outside connections end up),
repeated until nothing is left to rewrite, then a physics-style layout
(springs between connected nodes, repulsion between all) and hallways along
the edges. Our hallways are the existing corridor router. The recipe of
stages is the one addition: it keeps the pacing controllable (the main path
first, then side rooms, then loops) where weighted random choice alone would
not.

The grammar shapes topology and room sizes only. It places no locks, keys or
bosses: pacing still derives roles from the finished graph (umbrella
Req 32.2) and gating still cuts spanning-tree edges (umbrella Req 21.5–21.8).

## Research findings

Measured at `67e5b69`.

1. **One opening per wall side.** `_open_facing_walls` opens one of a room's
   four walls (N, S, E, W) per corridor, and corridors leaving the same side
   share it. A room can therefore join at most 4 neighbours on separate walls;
   the driver's degree cap is 4 for this reason.
2. **Today's graphs (TinyKeep, `dungeon`, 40 seeds each).** Scratch probe over
   `LayoutGenerator.generate`:

   | rooms | dead-end share | loops (E − N + 1) | deepest room / n | max degree |
   |-------|----------------|-------------------|------------------|------------|
   | 5 | 0.56 | 0.00 | 0.64 | 4 |
   | 9 | 0.41 | 0.38 | 0.56 | 4 |
   | 14 | 0.31 | 0.97 | 0.50 | 4 |

   The graph is whatever the scatter gives: loops are rare below 9 rooms
   (12 % of the non-tree Delaunay edges come back, floored), and nothing can
   ask for more.
3. **Rooms are axis-aligned boxes everywhere.** `RoomSpec` is a centre, width,
   depth and height; the box backend, `_wall_point`, the gate's
   `_faces_in_room`, the Envelope fit and the maps all assume it. Room shapes
   are therefore step 8's (they touch all of these); step 6 only carries a
   `shape` attribute through the rules.
4. **Race scales rooms after the layout.** `semantics._apply_shape` multiplies
   a themed room by `race_scale(race)` (`generators/semantics.py`). Size
   classes slot in before it: rules say "small", the zone type says how big
   small is, the race scales the result. An ogre lair and a halfling lair use
   the same rule.
5. **Stock dungeon topology: task 1.** The survey walks the stock dungeons
   (befallen, crushbone, najena, gukbottom, guktop, permafrost, soldunga,
   kaesora, sebilis, chardok; warren-like, reported apart: blackburrow,
   runnyeye) and fills this finding with chamber count, chamber sizes,
   degrees, cycle rank, dead-end share and deep-end distance. Its numbers set
   the two base sets' recipes and the bands of Req 5.1.

## The seam (`generators/layout_engine.py`)

```python
@dataclass
class LayoutContext:
    rng: random.Random
    room_min: float; room_max: float      # room side band (after _apply_room_scale)
    ceiling: float
    corridor_width: float
    separate: Callable[[List[RoomSpec]], None]   # LayoutGenerator._separate_rooms
    build: BuildContext                   # zone type, theme, race, race scale, room count

@dataclass
class EngineResult:
    rooms: List[RoomSpec]
    edges: List[Edge]                     # (i, j, relation)
    entry: Optional[Point] = None         # the graph's entrance room centre
    record: Optional[dict] = None         # what the sidecar's layout block reports

class LayoutEngine(Protocol):
    name: str
    sizes_rooms: bool                     # True: Job B's role bias leaves sizes alone
    def generate(self, ctx: LayoutContext, room_count: int,
                 envelope: Optional[Envelope]) -> EngineResult: ...
```

- `ClassicEngine` is the moved `_scatter_rooms`, `_rand_in_ellipse`,
  `_connect_rooms` and `_delaunay_edges`, drawing from the same `rng` in the
  same order; its edges carry relation `any`, `sizes_rooms` is False, `entry`
  is None. `_separate_rooms` stays on `LayoutGenerator` (Job B calls it too)
  and reaches engines through the context.
- The context is the seam's only coupling to the generator. Engines get no
  `LayoutGenerator`, so they can be tested alone.
- `LayoutGenerator(..., engine=None)` takes the engine; `None` is classic.
  An engine registry (`ENGINES = {"classic": ..., "graph": ...}`) is the one
  place names map to engines.
- **Job B's three touch points**, each a no-op for classic:
  - `_apply_pacing` gets `entry` from the result when the engine gives one
    (the Envelope's `entry` from step 5 still wins for an outdoor dungeon:
    the way in from the hill). Roles are still derived, never re-tagged.
  - The role size bias is skipped when `engine.sizes_rooms`.
  - `_assign_elevation` reads each edge's relation (see "Vertical
    relations").
- **Proof of no change (task 2):** before moving any code, capture sha256
  goldens of the Zone_Spec JSON and the `.eqg` contents (footer aside, per
  lessons-learned) for dungeon, city, wilderness and outdoor_dungeon on pinned
  seeds; the same test passes after. The Zone_Spec golden is what catches a
  change in rng order; the `.eqg` golden catches the rest.

## Rule-set files (`rules/topology/`)

```
rules/topology/
  classic_eq.toml          base set: the classic EQ dungeon
  warren.toml              base set: kobold / gnoll burrows
  layers/temple.toml       theme layer: a nave with side chapels
  themes.toml              theme → base set + layers
  README.md                -> docs/TOPOLOGY_RULES.md (the authoring guide)
```

TOML because Python 3.13 reads it with no new dependency (`tomllib`), it
allows comments, and each rule is one block. Every node and edge is a small
inline table (`{id = "a", kind = "Area"}`), not a mini-syntax inside a
string, so there is one parser (TOML's) and every field has a name a check
can point at. That matters most for rules a prompt writes later (Req 3.2).

### A base set, annotated

```toml
# rules/topology/classic_eq.toml
[set]
name        = "classic_eq"
description = "A classic EQ dungeon: a way through, side rooms, a deep end."
placement   = "spring"                  # a Placement name (registry in embed.py)

# The start graph. Room nodes need a size; Area is a placeholder rules expand.
start_nodes = [ {id = "e", kind = "entrance", size = "medium"},
                {id = "a", kind = "Area"},
                {id = "d", kind = "deep",     size = "huge"} ]
start_edges = [ {a = "e", b = "a"},
                {a = "a", b = "d"} ]

[rules.lengthen]
description = "The way through gets longer"
match    = [ {id = "x", kind = "Area"} ]
replace  = [ {id = "x", kind = "Area"}, {id = "y", kind = "Area"} ]
edges    = [ {a = "x", b = "y"} ]
reattach = { x = ["x", "y"] }          # x's outside edges split between x and y, in order

[rules.branch]
description = "A dead-end side room off the way through"
match    = [ {id = "x", kind = "Area"} ]
replace  = [ {id = "x", kind = "Area"}, {id = "l", kind = "lair", size = "small"} ]
edges    = [ {a = "x", b = "l"} ]
reattach = { x = ["x"] }

[rules.great_hall]
description = "Big races get a great hall on the way"
when     = { race_scale = ">=1.5" }    # offered only in this context
match    = [ {id = "x", kind = "Area"} ]
replace  = [ {id = "x", kind = "Area"}, {id = "g", kind = "hall", size = "huge"} ]
edges    = [ {a = "x", b = "g"} ]
reattach = { x = ["g", "x"] }

[rules.shortcut]
description = "Join two finished chambers a few rooms apart"
match       = [ {id = "p", kind = "chamber"}, {id = "q", kind = "chamber"} ]
match_hops  = { p_q = [2, 3] }         # p and q 2-3 hops apart, no edge between them
replace     = [ {id = "p", kind = "chamber"}, {id = "q", kind = "chamber"} ]
edges       = [ {a = "p", b = "q"} ]
reattach    = { p = ["p"], q = ["q"] }

# (passage, side_wing and loop are left out of this excerpt)

[rules.finish]
description = "A placeholder becomes a chamber"
match    = [ {id = "x", kind = "Area"} ]
replace  = [ {id = "x", kind = "chamber", size = "medium"} ]
reattach = { x = ["x"] }

# The recipe: stages in order. `apply` weights the stage's rules; `share` is
# the stage's part of the room budget. The last stage takes the rest and must
# be able to finish every Area.
[[recipe]]
stage = "Main path"
apply = { lengthen = 3, passage = 1 }
share = 0.4

[[recipe]]
stage = "Side rooms"
apply = { branch = 3, side_wing = 1, great_hall = 1 }
share = 0.4

[[recipe]]
stage = "Loops"
apply = { loop = 1, shortcut = 1 }
share = 0.1

[[recipe]]
stage = "Finish"
apply = { finish = 1 }
share = "rest"
```

### The vocabulary (checked on load)

- **Node fields:** `id` (unique within the rule), `kind`, `size` (required on
  every room node, forbidden on `Area`), optional `shape` (`rect` only until
  step 8), optional `district` (an integer label; see "Districts").
- **Kinds:** `Area` (placeholder) and the room kinds `entrance`, `chamber`,
  `passage`, `hub`, `lair`, `hall`, `deep`. A set may declare extra kinds in
  `[set] kinds = [...]`; the themes map kinds to room types (Req 7.4), and a
  kind no theme maps falls back to the theme's default type with a note.
- **Size classes:** `tiny`, `small`, `medium`, `large`, `huge`.
- **Edge fields:** `a`, `b`, optional `rel` (`above`, `below`, `level`,
  `any`; default `any`), optional `tags` (`threshold` only, in step 6).
- **Reattach:** each match node maps to the replacement nodes its outside
  edges move to, as a list; one target takes them all, several split them in
  order. This is the article's "specify where external connections end up",
  and it is what keeps the graph connected by construction.
- **`when`:** keys `theme`, `race`, `race_scale`, `zone_type`, `room_count`;
  values an exact value, a list (any of), or a comparison string (`">=1.5"`).
- **Recipe:** every stage names only rules in the set (or its layers), shares
  are numbers in (0, 1] summing to at most 1, the last stage is `"rest"` and
  its rules include one that turns an `Area` into a room.

**Checking** (`generators/topology/ruleset.py`): load every file, then run
every check and collect every failure (not stop at the first), each as
`file › rule or stage › field: what was found, what was expected`. A build
whose rule set fails raises with the whole report (Req 3.3). The shipped sets
are loaded and checked by a test, so a broken rule fails the suite.

### Theme layers and the theme map

```toml
# rules/topology/layers/temple.toml
[layer]
name        = "temple"
description = "A nave with side chapels, before the deep end"
fits        = ["classic_eq"]           # base sets this layer can add to

[rules.nave]
description = "A long hall with two chapels off its sides"
match    = [ {id = "x", kind = "Area"} ]
replace  = [ {id = "n", kind = "hall",    size = "large"},
             {id = "c1", kind = "lair",   size = "small"},
             {id = "c2", kind = "lair",   size = "small"},
             {id = "x", kind = "Area"} ]
edges    = [ {a = "n", b = "c1"}, {a = "n", b = "c2"}, {a = "n", b = "x"} ]
reattach = { x = ["n", "x"] }

[stages."Side rooms"]                  # add weight to a base stage...
apply = { nave = 2 }

# [[insert]] after = "Main path"       # ...or insert a whole stage
```

```toml
# rules/topology/themes.toml
default = { base = "classic_eq" }
warren  = { base = "warren" }
temple  = { base = "classic_eq", layers = ["temple"] }
```

A layer never edits its base file; the loader merges them at build time and
checks the merged set as well as each file (Req 4.5). Themes not listed use
`default`. A request can name a base set, and the theme's layers still apply
when they fit it.

## Growing the graph (`generators/topology/rewrite.py`)

**Matching.** For each rule, find every placement of its match in the graph:
node kinds equal, the match's edges present between the matched nodes,
`match_hops` distances held, and the `when` condition true for the build.
Matches are 1–3 nodes, so brute force over a graph of at most 30 rooms and a
few placeholders is cheap.

**Applying.** Remove the matched nodes, add the replacement, add its edges,
move each removed node's outside edges as `reattach` says (a node kept by id
keeps its identity, so its earlier edges and attributes stay).

**Driver.** For each recipe stage: while the stage's room budget isn't spent,
list every match of the stage's rules, drop the ones whose result breaks an
invariant (connected; degree ≤ 4; loops close over 3–5 rooms) or can no
longer reach exactly n rooms (each remaining `Area` still needs a room, so a
rule is legal only if rooms so far + its rooms + `Area`s left ≤ n), pick one
by weight (candidates in sorted order, then the rng), apply it. A stage with
no legal match ends early and its budget passes on. The last stage finishes
every `Area`. The step cap is `8 × n` per stage; reaching it raises
`TopologyError` naming the set, the stage and the cap.

Same discipline as the wilderness rewrite (`generators/wilderness/rewrite.py`:
apply, check, commit, capped), but the code is not shared: that one rewrites
matrix cells and its goldens pin it.

The driver records every application (stage, rule, nodes); the sidecar
carries it (Req 7.5).

## Size classes

The zone type's measured base side (`(room_min + room_max) / 2` after
`_apply_room_scale` for the requested count) times the class multiplier,
with the same gaussian spread the classic engine draws (±15 %); height by
the class too. Starting values, tuned in task 8 against finding 5's chamber
sizes:

| class | footprint × | height × |
|-------|-------------|----------|
| tiny | 0.5 | 0.8 |
| small | 0.75 | 0.9 |
| medium | 1.0 | 1.0 |
| large | 1.4 | 1.2 |
| huge | 1.9 | 1.5 |

The race scale applies afterwards in `semantics`, as today. The rules own
size, so the role bias in `_apply_pacing` is skipped for this engine
(`sizes_rooms`).

## Placement (`generators/topology/embed.py`)

The router joins two rooms through facing walls, as straight, L or Z
corridors (lessons-learned "Same-axis room pairs need a Z-route"), and Job B
splits a corridor that crosses a third room and drops loop corridors that
conflict. So Placement's job is to put connected rooms near each other on a
free side and unconnected rooms apart, so that Job B has little to change.
Placements are named in a registry; a rule set picks one, so a later maze
set can bring its own (`archive.md` "Follow-ups").

**`spring`** (the article's physics layout, with rooms as rectangles):

1. **Start positions:** breadth-first from `entrance`, each room beside its
   first placed neighbour on a free side (N, S, E, W: finding 1), pointing
   away from rooms already placed.
2. **Springs:** iterate: each edge pulls its two rooms toward a rest length of
   their half-sizes plus one corridor run; every pair of rooms repels, more
   strongly as their footprints near each other. Fixed iteration count and
   step size, so it's deterministic.
3. **Overlaps:** `ctx.separate` resolves what's left exactly as for classic
   rooms (Req 6.2's clearance is the same code).
4. **Envelope:** the layout is centred on the footprint and scaled to the
   inradius, as `_scatter_rooms` does; Job B's fit check and the Envelope
   retry loop do the rest (Req 6.6).

**No stacking in step 6.** Separation keeps every pair of room footprints
apart in plan, so no room can sit over another, by intent or by accident; a
corridor that crosses a room is split by Job B as today. Step 7 relaxes this
for pairs a rule joined with `above` or `below` only, with a vertical
clearance, and keeps every other pair apart in plan. Placement checks pairs
through one predicate (`may_overlap_in_plan(a, b)`, always False in step 6)
so step 7 changes one function.

**Edge_Fidelity bar.** Task 8 measures it (grammar edges still present as
corridors after Job B, over the grammar's edge count) on the sweep seeds and
sets the bar at its measured mean less a margin, at least 0.85; below that
the placement is the bug, not the bar. Connectivity is never traded: the
crossing split keeps the graph connected and conflicts drop only loop edges.

## Vertical relations

`_assign_elevation` today draws, per tree edge, whether the floor changes
and by how much, bounded by the corridor's run times `max_grade`, then
`_relax_elevation` settles loops. With relations:

- `any`: as today (the classic engine's edges are all `any`: no change).
- `above` / `below`: the change happens, in that direction; the amount is
  drawn as today and bounded the same way.
- `level`: no change.

`_relax_elevation` may still pull a room to keep a loop walkable; a relation
it had to break is counted in the sidecar. Stacking along these edges is
step 7.

## Districts (structure only)

A rule may give nodes a `district` label and tag an edge `threshold`
(e.g. a `wing` rule whose new rooms are district 1 and whose joining edge is
the threshold). Step 6 carries both onto `RoomSpec.district` (which exists
today, always 0) and the sidecar. The district look (materials and lights
differing across a threshold, umbrella Req 23.5) and the umbrella's district
counts (Req 23.1) are a follow-up; no step 6 rule set has to use districts,
but the format and the check accept them.

## The dry run, the diagrams and the guide (`scripts/topology_rules.py`)

```bash
python scripts/topology_rules.py check                      # every shipped file
python scripts/topology_rules.py dry-run warren --graphs 50 --rooms 5-20
python scripts/topology_rules.py draw classic_eq --out output/rules/
```

- `check`: the load-time checks over one file or all, exit 1 on any failure.
- `dry-run`: grow graphs over seeds and room counts; report each stage's
  completion rate, each rule's application count (and the rules that never
  fired), the shape measures (p10 / p50 / p90) and the Size_Class mix.
- `draw`: one HTML page per set, a before → after SVG per rule: nodes drawn
  by kind and sized by class, edges with relation arrows (up / down), and
  reattachment shown as dashed outside edges moving from the match to their
  targets. The same drawing code draws a built zone's Topology_Graph, so a
  sidecar's trace can be looked at too.
- `docs/TOPOLOGY_RULES.md`: the authoring guide. The format field by field,
  the two shipped sets and the temple layer as worked examples, and the
  check → dry-run → draw loop for writing a new set.

## Selection and the sidecar

- `ZonePlan.layout`: `classic` (default) | `graph`; `ZonePlan.rule_set`:
  `""` (from the theme) or a base set name. A missing field loads as the
  default (legacy tolerance, umbrella Req 11.1); an unknown value is an error
  naming the allowed values.
- `--layout` and `--rule-set` on the CLI, the same in the server's controls,
  a Layout toggle in the Controls panel with a Rule set select shown when
  Layout is Graph ("From theme" first).
- Taken by `dungeon` and `outdoor_dungeon`; other zone types ignore it.
  Dungeon is the focus: the sweeps, tuning and acceptance cases are dungeon
  first, the outdoor dungeon has to build and pass its gate.
- The builder writes the sidecar from the Zone_Spec, so the engine's record
  rides on a `ZoneSpec.layout` dict that is `None` for classic builds and left
  out of the spec's JSON when `None` (G1: classic Zone_Spec JSON unchanged).
  The shape measures are computed by the builder from the spec's rooms and
  corridors, so classic builds also get `{"engine": "classic", "shape": …}`
  in the sidecar and the two can be compared from the files:

```json
"layout": {"engine": "graph", "rule_set": "classic_eq", "layers": ["temple"],
           "applied": [["Main path", "lengthen"], ["Side rooms", "nave"], ...],
           "rooms": {"room_3": {"kind": "lair", "size": "small", "district": 0}},
           "shape": {"dead_end_share": 0.33, "cycle_rank": 1, "deep_end": 0.56},
           "edge_fidelity": 0.92, "relations_broken": 0}
```

## Correctness properties

| P | Statement | Reqs |
|---|-----------|------|
| G1 | Classic builds are byte-identical to today (Zone_Spec JSON, `.eqg` contents) | 2.2, 7.3 |
| G2 | Every check failure names file, rule or stage, field; a mutated valid file fails with the field it broke | 3.2, 3.3 |
| G3 | Every grown graph has no `Area` left, is connected, has exactly n rooms, max degree ≤ 4, loops of 3–5 | 4.1, 4.2 |
| G4 | The driver terminates or raises `TopologyError`; same seed, same graph | 4.3, 4.4 |
| G5 | A layer merges without changing its base file; the merged set passes the checks | 4.5 |
| G6 | Each base set's shape measures fall in its survey bands; `warren` differs from `classic_eq` in the measured direction | 5 |
| G7 | Rooms take their class's size; grown rooms never overlap in plan and keep the corridor clearance; the `entrance` node is the entrance room; the final graph is connected | 6.1–6.4 |
| G8 | Mean Edge_Fidelity ≥ the bar over the sweep seeds | 6.4 |
| G9 | `above` / `below` / `level` edges hold after elevation unless the loop relax broke them (counted) | 6.5 |
| G10 | Grown rooms fit an Envelope as classic ones do | 6.6 |
| G11 | Umbrella Req 21 holds on grown layouts (entrance, climax, solvable gates) | 8.1 |
| G12 | Grown builds pass the walkability gate; same inputs, same `.eqg` | 8.2, 8.3 |

G2–G11 are tests and Hypothesis properties over seeds, room counts 1–30 and
the shipped sets (G2 mutates fields of the shipped files). G12 is a sweep
over built zones (task 12), not a per-commit property.

## Risks

- **Placement is the hard part.** A graph the plane can't hold cleanly gets
  split and pruned by Job B until it is TinyKeep's graph again, or worse.
  Edge_Fidelity is measured from the first placement commit, and the rules
  keep loops short (3–5 rooms) so every loop can be drawn locally.
- **Springs settle into local minima.** A spring layout can fold a branch
  across the main path. The breadth-first start keeps it near a clean layout,
  and fidelity shows when it doesn't.
- **Big size classes crowd the layout.** A `huge` room with four neighbours
  needs room on all sides; the spring rest lengths use the real half-sizes.
- **Walkability on new shapes.** Longer paths mean longer elevation chains;
  the grade cap bounds every corridor already, but the gate sweep (task 12) is
  where a new failure class would show. Fix the root cause in the rules or
  placement, not the test (project.md).
- **The settled TinyKeep call.** Umbrella Req 32.1 says rooms are laid out with
  TinyKeep and every edge is a Delaunay edge. That stays true for the classic
  engine and is amended for the graph engine at the close (umbrella decision
  26). The ROADMAP "NOT doing" entry on the Dormans mission grammar stands:
  this grammar has no locks or keys.

## Decisions

The user's answers (2026-11-03) are in `archive.md` "Decisions". The design
follows from them:

1. Job B is shared; an engine produces rooms, edges, and optionally an entry
   point. Its three touch points (entry, role size bias, relations) are
   no-ops for classic.
2. The grammar shapes topology and room sizes only: no locks, keys or bosses.
3. Rules, recipes, layers and the theme map are TOML data with one parser and
   named fields; every check reports file, rule, field.
4. Rules set kinds and size classes; themes map kinds to room types; the race
   scales sizes after the layout.
5. The rule format carries vertical relations, `shape` and `district` now;
   step 6 acts on relations through elevation only, keeps rooms rectangular,
   and keeps every room apart in plan.
6. Placement is named per rule set (`spring` in step 6); connections are the
   existing corridor router.
7. The seam lands first and is proven byte-identical by goldens captured
   before the move.
8. Measure the stock dungeons first (task 1) and set both base sets from them.
