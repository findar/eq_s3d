# Design — zone-generator-graph-layout (roadmap step 6)

Written at master `67e5b69`. Verify against the code before working a task.

## Overview

`LayoutGenerator._generate_once` does two jobs today:

- **Job A, the rooms and the graph:** `_scatter_rooms` → `_separate_rooms` →
  `_connect_rooms` (`generators/layout.py`). This is the TinyKeep scheme.
- **Job B, everything after:** pacing (`_apply_pacing`), themes
  (`semantics.label_rooms`), re-separation, elevation, crossing splits
  (`_resolve_crossings`), conflict drops (`_resolve_conflicts`), fitting to an
  Envelope, corridors, materials, the safe point, gating.

Step 6 puts Job A behind a `LayoutEngine` seam and adds a second engine:

```
            ┌─ ClassicEngine: scatter → separate → Delaunay/MST/loops   (today)
Job A ──────┤
            └─ GrownEngine:   rewrite rules → Topology_Graph → spring layout
                              (iterate to no      (no coordinates)  (rooms in the plane)
                               placeholders)
                 │
                 ▼  (rooms, edges): the contract Job B already takes
Job B: pacing, themes, elevation, crossings, conflicts, Envelope fit,
       corridors, gating   (unchanged)
                 │
                 ▼
Box backend / terrain backend, walkability gate, maps   (unchanged)
```

This is graph rewriting as shaggydev's "Graph rewriting" (2022-11-20) lays
it out: a manual start graph with placeholders, rules that replace a pattern
with a structure, repeated until nothing is left to rewrite, then a
physics-style layout (springs between connected nodes, repulsion between all)
and hallways along the edges. Our hallways are the existing corridor router.

The grammar is a topology grammar only. It says which rooms connect and what
kind of room each is; it places no locks, keys or bosses. Pacing still derives roles from the graph
(umbrella Req 32.2) and gating still cuts spanning-tree edges (umbrella
Req 21.5–21.8), so the grown graph's shape (a deep end far from the entrance,
dead-end side rooms, loops) is what changes the play, through the code that
already reads it.

## Research findings

Measured at `67e5b69`.

1. **One opening per wall side.** `_open_facing_walls` opens one of a room's
   four walls (N, S, E, W) per corridor, and corridors leaving the same side
   share it. A room can therefore join at most 4 neighbours on separate walls;
   the Topology_Grammar's degree cap is 4 for this reason.
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
3. **Stock dungeon topology: task 1.** The survey walks the classic dungeons
   (befallen, blackburrow, crushbone, najena, gukbottom, guktop, permafrost,
   soldunga, runnyeye, kaesora, sebilis, chardok) and fills this finding with
   the table of chamber count, degrees, cycle rank, dead-end share and deep-end
   distance. Its numbers set the profile weights (task 4) and the bands of
   Req 4.1.

## The seam (`generators/layout_engine.py`)

```python
@dataclass
class LayoutContext:
    rng: random.Random
    room_min: float; room_max: float      # room side band (after _apply_room_scale)
    ceiling: float
    corridor_width: float
    separate: Callable[[List[RoomSpec]], None]   # LayoutGenerator._separate_rooms

class LayoutEngine(Protocol):
    name: str
    def generate(self, ctx: LayoutContext, room_count: int,
                 envelope: Optional[Envelope]) -> Tuple[List[RoomSpec], List[Edge]]: ...
```

- `ClassicEngine` is the moved `_scatter_rooms`, `_rand_in_ellipse`,
  `_connect_rooms` and `_delaunay_edges`, drawing from the same `rng` in the
  same order. `_separate_rooms` stays on `LayoutGenerator` (Job B calls it
  too) and reaches engines through the context.
- The context is the seam's only coupling to the generator. Engines get no
  `LayoutGenerator`, so they can be tested alone.
- `LayoutGenerator(..., engine=None)` takes the engine; `None` is classic.
  An engine registry (`ENGINES = {"classic": ..., "grown": ...}`) is the one
  place names map to engines.
- **Proof of no change (task 2):** before moving any code, capture sha256
  goldens of the Zone_Spec JSON and the `.eqg` contents (footer aside, per
  lessons-learned) for dungeon, city, wilderness and outdoor_dungeon on pinned
  seeds; the same test passes after. This is the `routing.py` extraction
  method the followup design named. The Zone_Spec golden is what catches a
  change in rng order; the `.eqg` golden catches the rest.

## Topology_Grammar (`generators/topology/`)

`graph.py` holds the `TopologyGraph`: labelled nodes and an undirected edge
set, with the shape measures (dead-end share, cycle rank, deep-end distance).
`rewrite.py` holds the matcher and the driver; `rules.py` holds the rules and
profiles as data.

**Labels.** One placeholder, `Area` (a part of the dungeon not yet decided),
and the room kinds: `entrance`, `chamber`, `passage` (a small linking room),
`hub` (a crossroads), `lair` (a dead end), `deep` (the far end). The kinds
are advisory: pacing still derives roles from the finished graph (umbrella
Req 32.2), and the sidecar records the kinds for the themes and later steps.

**Start graph:** `entrance — Area — deep`. (1 room: `entrance`; 2 rooms:
`entrance — deep`; both skip the rules.)

**A rule** is a declaration:

```python
Rule("branch",
     pattern=["Area"],                      # nodes to find (labels; edges between them)
     replace=["Area", "lair"], edges=[(0, 1)],
     reattach={0: 0},                       # pattern node 0's outside edges go to replacement node 0
     rooms=1)                               # net rooms added once its placeholders finish
```

The matcher finds every placement of a pattern (labels, and the pattern's
edges present between the matched nodes; patterns are 1–3 nodes, so brute
force over a graph of at most 30 rooms and a few placeholders is cheap). The
pattern's outside connections reattach as the rule says: this is the
article's "specify where external connections end up", and it's what keeps
the graph connected by construction.

**The v1 rules** (task 4 weights them from the survey):

| rule | pattern → replacement | shape it makes |
|------|-----------------------|----------------|
| `lengthen` | `Area` → `Area — Area` | a longer way through |
| `passage` | `Area` → `passage — Area` | a small room on the way |
| `branch` | `Area` → `Area` + `lair` hanging off it | a dead-end side room |
| `side_wing` | `Area` → `Area` + `hub — {lair, lair}` hanging off it | a wing of side rooms |
| `crossroads` | `Area` → `hub` joined to `Area`, `Area` (outside edges split between them) | a fork that meets again downstream |
| `loop` | `Area` → a ring of `chamber, Area, Area` (outside edges on two ring nodes) | a loop around |
| `shortcut` | `chamber`, `chamber` 2–3 hops apart, no edge → add the edge | a loop between finished rooms (a 2-node pattern) |
| `finish` | `Area` → `chamber` | ends a placeholder |

**Driver.** Each step: list every match of every rule, drop the ones whose
result breaks an invariant (connected; degree ≤ 4; loops close over 3–5
rooms) or can no longer finish at exactly n rooms (each remaining `Area`
needs at least one room, so a rule is legal only if rooms so far + its rooms
+ placeholders left ≤ n), pick one by profile weight (candidates in sorted
order, then the rng), apply it, repeat. When the room budget is spent only
`finish` is legal, so every placeholder ends as a room and the count is
exact. The step cap is `8 × n`; reaching it raises `TopologyError` naming
the cap and the profile. Same discipline as the wilderness rewrite
(`generators/wilderness/rewrite.py`: apply, check, commit, capped), but the
code is not shared: that one rewrites matrix cells and its goldens pin it.

**Profiles** are weights over the rules (task 4 sets the numbers from the
survey):

- `linear`: `lengthen`, `passage`, some `branch`; no `loop`, `crossroads`,
  `side_wing` or `shortcut` (meets umbrella Req 22.2: only `branch` makes a
  degree-3 room).
- `branching`: the classic EQ mix from the survey.
- `looped`: `branching` with `loop`, `crossroads` and `shortcut` up.

The driver counts each rule's applications; the sidecar carries the counts
(Req 6.3).

## Embedding (`generators/topology/embed.py`)

The router joins two rooms through facing walls, as straight, L or Z
corridors (lessons-learned "Same-axis room pairs need a Z-route"), and Job B
splits a corridor that crosses a third room and drops loop corridors that
conflict. So the Embedding's job is to put connected rooms near each other on
a free side and unconnected rooms apart, so that Job B has little to change.
It is the article's physics layout, with rooms as rectangles:

1. **Sizes:** each room's footprint is drawn like the classic engine's (same
   band, same gaussian), so the themed shapes and the role biases behave the
   same.
2. **Start positions:** breadth-first from `entrance`, each room beside its
   first placed neighbour on a free side (N, S, E, W: finding 1), pointing
   away from rooms already placed. A good start keeps the springs from
   folding the graph over itself.
3. **Springs:** iterate: each edge pulls its two rooms toward a rest length
   of their half-sizes plus one corridor run; every pair of rooms repels,
   more strongly as their footprints near each other. Fixed iteration count
   and step size; all from the context's rng and sizes, so it's
   deterministic.
4. **Overlaps:** `ctx.separate` resolves what's left exactly as for classic
   rooms (Req 5.1's clearance is the same code).
5. **Connections:** the Topology_Graph's edges are the `(i, j)` edges handed
   to Job B, which routes the corridors. The `entrance` room's centre goes to
   pacing as the entry point (the Envelope's `entry` mechanism from step 5),
   so it becomes the entrance room (Req 5.2).
6. **Envelope:** the layout is centred on the footprint and scaled to the
   inradius, as `_scatter_rooms` does; Job B's existing fit check and the
   Envelope retry loop do the rest (Req 5.4).

**Edge_Fidelity bar.** Task 5 measures the Edge_Fidelity (grammar edges
still present as corridors after Job B, over the grammar's edge count) on
the sweep seeds and sets the bar at its measured mean less a margin, at
least 0.85; below that the embedding is the bug, not the bar. Connectivity
is never traded: Job B's crossing split keeps the graph connected and
conflicts drop only loop edges.

## Selection and the sidecar

A `layout` field on `ZonePlan` (`classic` | `linear` | `branching` |
`looped`; Open question 1), `--layout` on the CLI, `layout` in the server's
controls, a select in the Controls panel, prompt words in the rule planner
(Open question 2). `classic` is the default and a missing field loads as
`classic` (legacy tolerance, umbrella Req 11.1). The sidecar gets a
`layout` block:

```json
"layout": {"engine": "grown", "profile": "branching",
           "rules": {"extend": 4, "branch": 3, "loop": 1},
           "shape": {"dead_end_share": 0.33, "cycle_rank": 1, "deep_end": 0.56},
           "edge_fidelity": 0.92}
```

The builder writes the sidecar from the Zone_Spec, so the grown engine's
record rides on a `ZoneSpec.layout` dict that is `None` for classic builds
and left out of the spec's JSON when `None` (G1: classic Zone_Spec JSON
unchanged). The `shape` part is measured by the builder from the spec's
rooms and corridors, so classic builds get `{"engine": "classic", "shape":
…}` in the sidecar too and the two can be compared from the files.

## Correctness properties

| P | Statement | Reqs |
|---|-----------|------|
| G1 | Classic builds are byte-identical to today (Zone_Spec JSON, `.eqg` contents) | 2.2, 6.2 |
| G2 | Every grown graph has no placeholder left, is connected, has exactly n rooms, max degree ≤ 4, loops of 3–5 | 3.2, 3.3 |
| G3 | The driver terminates or raises `TopologyError`; same seed, same graph | 3.4, 3.5 |
| G4 | Profile shape stats fall in the survey bands; `linear` meets umbrella 22.2; cycle ranks order for 14 rooms | 4 |
| G5 | Grown rooms never overlap and keep the corridor clearance; the `entrance` node is the entrance room; the final graph is connected | 5.1–5.3 |
| G6 | Mean Edge_Fidelity ≥ the bar over the sweep seeds | 5.3 |
| G7 | Grown rooms fit an Envelope as classic ones do | 5.4 |
| G8 | Umbrella Req 21 holds on grown layouts (entrance, climax, solvable gates) | 7.1 |
| G9 | Grown builds pass the walkability gate; same inputs, same `.eqg` | 7.2, 7.3 |

G2–G8 are Hypothesis properties over seeds, room counts 1–30 and profiles.
G9 is a sweep over built zones (task 8), not a per-commit property: a build
plus gate is seconds per seed.

## Risks

- **Embedding is the hard part.** A grammar graph that the plane can't hold
  cleanly gets split and pruned by Job B until it is TinyKeep's graph again,
  or worse. Edge_Fidelity is measured from the first embedding commit, and the
  rules keep loops short (3–5 rooms) so every loop can be drawn locally.
- **Springs settle into local minima.** A spring layout can fold a branch
  across the spine. The breadth-first start positions keep it near a clean
  layout, and fidelity shows when it doesn't.
- **Overlap pushes break adjacency.** `_separate_rooms` moves rooms along the
  axis of least overlap and can carry a room off its neighbour's side. The
  relax pass and the gap at placement keep pushes small; task 5 measures how
  often a push changes which wall faces a neighbour.
- **Walkability on new shapes.** Longer spines mean longer elevation chains;
  the elevation code bounds every corridor's grade already, but the gate sweep
  (task 8) is where a new failure class would show. Fix the root cause in the
  layout, not the test (project.md).
- **The settled TinyKeep call.** Umbrella Req 32.1 says rooms are laid out
  with TinyKeep and every edge is a Delaunay edge. That stays true for the
  classic engine and is amended for the grown one at the close (umbrella
  decision 26); the ROADMAP "NOT doing" entry on the Dormans mission grammar
  stands, since this grammar has no locks or keys.

## Open questions (for the user; defaults recommended)

1. **What the option is called and what it offers.** Default: one `layout`
   option with `classic` (today, the default), `linear`, `branching` and
   `looped` (grown, by profile). Alternative: two options, an engine switch
   (`classic` | `grown`) and a separate topology control.
2. **Topology control (umbrella Req 22).** Default: this step builds it
   through the grown engine: the planner's words (`winding`, `maze`,
   `interconnected` → `looped`; `linear`, `straightforward` → `linear`) pick a
   grown profile, and a prompt with neither word builds `classic` as today.
   Umbrella Req 22.4 and 22.7 are amended at the close to say so.
   Alternative: leave Req 22 for later and select grown layouts by an
   explicit option only.
3. **Which zone types.** Default: `dungeon` and `outdoor_dungeon` (the
   Envelope path is shared). `city` keeps classic until districts (umbrella
   Req 23) give it a reason to grow. Alternative: all three room zone types.
4. **Districts.** Default: out of step 6. A `wing` is a natural seed for a
   district later, but districts bring materials and thresholds (umbrella
   Req 23) and are their own work. Alternative: build them here on top of
   the grammar.
5. **The default engine.** Default: `classic` stays the default through
   step 6; the human comparison pass (task 12) says whether `branching`
   becomes the default for prompts without topology words, and the close
   records it. Alternative: grown becomes the default as soon as the gate
   sweep is green.

## Decisions

1. Job B is shared and unchanged; an engine produces only rooms and edges.
2. The grammar shapes topology only: no locks, keys or bosses in it.
3. Rules are data (pattern, replacement, reattachment, rooms added); the
   room budget check plus `finish` makes the count exact.
4. Placement is a spring layout over the finished graph, then the existing
   separation; connections are the existing corridor router.
5. The seam lands first and is proven byte-identical by goldens captured
   before the move.
6. Measure the stock dungeons first (task 1) and set the profiles from them.
