# Writing topology rules

This guide is for anyone writing a rule set for the graph layout engine
(roadmap step 6): a person editing TOML by hand, or a model generating rules
from a prompt. It covers what the rules do, the file format field by field,
the shipped files as worked examples, the check, dry-run and draw loop, and
the traps that are easy to fall into.

The design is in `.kiro/specs/zone-generator-graph-layout/design.md`. The
code is in `generators/topology/`: `ruleset.py` loads and checks files,
`rewrite.py` grows graphs, and `draw.py` draws them.

Graph is the default layout for `dungeon` and `outdoor_dungeon` zones
(graph-layout task 21): a request that names no layout grows its rooms by
these rules. Classic (TinyKeep) is Layout **Classic** in the Controls panel
or `--layout classic` on the command line.

## What graph rewriting is here

The engine follows shaggydev's "Graph rewriting" (2022-11-20). A dungeon
starts as a small abstract graph with no coordinates. Some of its nodes are
placeholders (kind `Area`). A **rule** is a pattern and a replacement: find
the pattern in the graph (the *match*), take it out, put the replacement in,
and say where the removed nodes' connections to the rest of the graph go.
Rules run stage by stage until no placeholder is left and the graph has
exactly the requested number of rooms. A placement function then lays the
rooms out (a spring layout), and the corridor router joins them.

In this engine:

- A **node** is a room or an `Area`. A room has a kind (`chamber`, `lair`,
  ...) and a size class (`tiny` to `huge`).
- An **edge** is a connection, which later becomes a corridor. It can say
  which way the floor goes (`above`, `below`, `level`) and can carry a
  `threshold` tag.
- A **rule set** is one TOML file: a start graph, rules, and a **recipe**
  (ordered stages, each with rule weights and a share of the room budget).
- A **theme layer** adds rules and stages to a base set for one theme.
  `themes.toml` says which theme uses which base set and layers.

## Files

```
rules/topology/
  classic_eq.toml          base set: the classic EQ dungeon
  warren.toml              base set: kobold / gnoll burrows (task 6)
  layers/temple.toml       theme layer: a nave with side chapels
  themes.toml              theme -> base set + layers
  README.md                points here
rules/walls/
  built.toml, hewn.toml, rough.toml   wall styles (see "Wall styles")
```

A base set's `[set] name` must equal its file name without `.toml`. The same
goes for a layer's `[layer] name`, because the theme map finds files by name.

## The format, field by field

TOML, read with Python's `tomllib`. Every node and edge is a small inline
table (`{id = "x", kind = "Area"}`). An inline table has to fit on one line;
an array can span lines.

### `[set]`

| field | required | what |
|---|---|---|
| `name` | yes | the file name without `.toml` |
| `description` | yes | one line, shown on the drawn page |
| `placement` | yes | a placement name; only `"spring"` exists now |
| `kinds` | no | extra room kinds beyond the base vocabulary, lower case, e.g. `["burrow"]` |
| `start_nodes` | yes | the start graph's nodes (see Nodes); exactly one `entrance` |
| `start_edges` | no | the start graph's edges (see Edges) |

The base kinds are `Area` (the placeholder) and the room kinds `entrance`,
`chamber`, `passage`, `hub`, `lair`, `hall` and `deep`.

### Nodes

| field | where | what |
|---|---|---|
| `id` | everywhere | unique within the rule (or the start graph) |
| `kind` | everywhere | a kind of the set: `Area`, a room kind, or one from `kinds` |
| `size` | `start_nodes`, `replace` | required on every room node and forbidden on an `Area`: `tiny`, `small`, `medium`, `large`, `huge` |
| `shape` | `start_nodes`, `replace` | optional; `"auto"` (the default: the wall style picks by kind), or a fixed `"rect"`, `"blob"`, `"long"`, `"cut"`, `"ell"`, `"cross"` (see "Wall styles") |
| `district` | `start_nodes`, `replace` | optional whole number, default 0: a district label (structure only in step 6) |

Match nodes take only `id` and `kind`.

### Edges

| field | what |
|---|---|
| `a`, `b` | node ids within the same list: match ids for `match_edges`, replacement ids for `edges`, start ids for `start_edges` |
| `rel` | optional: `above`, `below`, `level` or `any` (the default). It reads "b relative to a": `{a = "p", b = "x", rel = "below"}` means x is below p |
| `tags` | optional: `["threshold"]`, or `["bridge"]` (step 7: the edge, on one Level, is a Bridge over the lower room one of its rooms is stair-joined to; the placement lines it up across that room) |

There is at most one edge per pair of nodes, and no edge joins a node to
itself. In step 6, `above` and `below` only change the floor height along
the corridor; rooms never stack.

### `[rules.<name>]`

| field | required | what |
|---|---|---|
| `description` | yes | one line, shown on the drawn page |
| `match` | yes | 1 to 3 nodes, matched by **exact kind** |
| `match_edges` | no | edges that must join the matched nodes. The match is *induced*: no other edge may join them |
| `match_hops` | no | `{ p_q = [lo, hi] }`: match nodes p and q are lo to hi hops apart (2 <= lo <= hi), so not adjacent. The key is the two ids joined by `_` |
| `replace` | yes | the nodes that take the match's place |
| `edges` | no | edges among the replacement nodes |
| `reattach` | yes | for **every** match id, a non-empty list of replacement ids that take its outside edges |
| `when` | no | conditions on the build (see below); the rule is offered only when all of them hold |

**Kept and new nodes.** A replacement node that reuses a match id is the
same graph node. It keeps its id and its edges among the outside nodes (via
`reattach`). If its kind is unchanged it also keeps its size, shape and
district. If the kind changes, it takes the replacement's attributes. Every
other replacement id is a new node and gets a fresh id (`n000`, `n001`, ...).

**Reattach.** A matched node's *outside edges* are its edges to nodes outside
the match. `reattach = { x = ["x"] }` moves all of them to one target.
`reattach = { x = ["x", "y"] }` splits them. They are sorted by the outside
neighbour's id and cut into contiguous chunks, one per target in the listed
order, with earlier targets taking the larger chunks: edge i of E goes to
target `i * k // E` of k. A moved edge keeps its relation and tags. This is
the article's "specify where external connections end up", and it is what
keeps the graph connected without any extra work.

**`when`.** The keys are `theme`, `race`, `race_scale`, `zone_type` and
`room_count`. Each value can be an exact value, a list (any of), or, for
numbers, a comparison string such as `">=1.5"` (operators `>=`, `<=`, `==`,
`!=`, `>`, `<`). Text keys take the values from the schema: themes such as
`temple` or `warren`, races such as `ogre` or `kobold`, and zone types
`dungeon`, `city`, `wilderness` or `outdoor_dungeon`. A key the build doesn't
set fails its condition.

### `[[recipe]]`

| field | what |
|---|---|
| `stage` | a name, unique in the recipe |
| `apply` | `{ rule = weight, ... }`, with weights above 0 |
| `share` | a number in (0, 1], the stage's part of the room budget, or `"rest"` on the last stage |

The rules:

- Numeric shares sum to at most 1.
- The last stage, and only the last, is `"rest"`.
- The rest stage must include a rule that turns an `Area` into a room (its
  match has an `Area` and its replacement has none).

How a stage runs: its budget is `round(share x n)` plus whatever earlier
stages left unspent. The budget is counted in **rooms plus Areas**, since an
Area is a room to come: `lengthen` spends 1 and `finish` spends 0. Each step
picks a rule by weight among the stage's rules that have a legal placement,
then picks one of that rule's placements at random. A stage that runs out of
legal matches ends early and passes its leftover budget on. The rest stage
runs until the graph has exactly n rooms and no Area. If it gets stuck, the
grow raises `TopologyError`.

### Layers (`layers/<name>.toml`)

| table / field | what |
|---|---|
| `[layer] name`, `description` | as for a set |
| `[layer] fits` | the base sets this layer can be merged onto |
| `[layer] kinds` | extra kinds the layer uses (declare a base set's extra kind here too if you use it) |
| `[rules.<name>]` | as in a set; a name must not clash with the base's rule names |
| `[stages."<base stage>"] apply` | weights added to a base stage (added to existing weights) |
| `[[insert]] after, stage, apply, share` | a whole new stage after a named base stage; several inserts after one stage keep their file order |

A layer never edits its base. The loader merges them and checks the merged
recipe again (shares still at most 1, the rest stage still last).

### `themes.toml`

```toml
default = { base = "classic_eq" }
temple  = { base = "classic_eq", layers = ["temple"] }
```

The keys are `default` (required) and dungeon theme names. A theme the file
doesn't list uses `default`. A request can name a base set instead of the
theme's, and the theme's layers still apply when their `fits` includes it.

## Worked example: `classic_eq`

[`rules/topology/classic_eq.toml`](../rules/topology/classic_eq.toml) is
the classic EQ dungeon. Its start graph is entrance, one placeholder, deep
end:

```toml
start_nodes = [ {id = "e", kind = "entrance", size = "medium"},
                {id = "a", kind = "Area"},
                {id = "d", kind = "deep",     size = "huge"} ]
start_edges = [ {a = "e", b = "a"},
                {a = "a", b = "d"} ]
```

`lengthen` makes the way through longer. The placeholder's two outside
edges (the way in and the way on) split one each, so `y` sits further along:

```toml
[rules.lengthen]
description = "The way through gets one placeholder longer"
match    = [ {id = "x", kind = "Area"} ]
replace  = [ {id = "x", kind = "Area"}, {id = "y", kind = "Area"} ]
edges    = [ {a = "x", b = "y"} ]
reattach = { x = ["x", "y"] }
```

`branch` keeps every edge on `x` and adds a dead end. `crossroads` moves all
of x's edges to a new hub (`reattach = { x = ["h"] }`), which hangs two
placeholders off the way. `passage` uses a relation:
`{a = "p", b = "x", rel = "below"}`, so the floor drops after the passage.
`great_hall` uses a condition: `when = { race_scale = ">=1.4" }`, so only
the big races (ogres, giants) get it.

`shortcut` matches two finished rooms by distance and adds only an edge.
They must be exactly 3 hops apart, so the new loop is a ring of four (at 2
hops it would be a triangle, which the driver rejects; see "The invariants"):

```toml
[rules.shortcut]
match      = [ {id = "p", kind = "chamber"}, {id = "q", kind = "chamber"} ]
match_hops = { p_q = [3, 3] }
replace    = [ {id = "p", kind = "chamber", size = "medium"},
               {id = "q", kind = "chamber", size = "medium"} ]
edges      = [ {a = "p", b = "q"} ]
reattach   = { p = ["p"], q = ["q"] }
```

The recipe has four stages: a short main path (share 0.1), side rooms
(0.45), loops (0.1), then `Finish` on `"rest"`. Finish mixes the finishing
rules (`finish`, `finish_large`) with growth rules, including three (`split`,
`annex`, `deepen`) that grow from finished rooms. The traps below explain
why.

## Worked example: the `temple` layer

[`rules/topology/layers/temple.toml`](../rules/topology/layers/temple.toml)
adds a nave: a large hall in line on the way, with two small chapels off it.
It inserts a stage of its own and adds weight to a base stage:

```toml
[layer]
name = "temple"
fits = ["classic_eq"]

[[insert]]
after = "Main path"
stage = "Nave"
apply = { nave = 1 }
share = 0.05

[stages."Side rooms"]
apply = { nave = 1 }
```

The nave's `reattach = { x = ["n", "x"] }` splits the placeholder's way in
and way on between the hall and the placeholder after it. That puts the hall
in line on the way through rather than off to one side.

## The loop: check, dry-run, draw

```bash
python scripts/topology_rules.py check                     # every shipped file + each theme's merged set
python scripts/topology_rules.py check path/to/my_set.toml # one file (or several)
python scripts/topology_rules.py dry-run classic_eq --graphs 50 --rooms 5-20
python scripts/topology_rules.py dry-run classic_eq --theme temple --race-scale 1.6
python scripts/topology_rules.py draw classic_eq --out output/rules/
python scripts/topology_rules.py draw classic_eq --theme temple --out output/rules/
```

`<set>` is a base set name in `rules/topology/` or a path to a `.toml` file.

1. **check** loads every file and runs every check. It merges each layer
   onto the base sets it fits, and loads each theme's merged set. It prints
   `ok` or `FAIL` per file and exits 1 if anything failed.
2. **dry-run** grows `--graphs` graphs (seeds 0.., room counts cycling over
   `--rooms`). The build context is `--theme`, `--race-scale` (default 1.0)
   and `--zone-type` (default `dungeon`). It reports:
   - the `TopologyError` count and messages;
   - per stage, how often it was *complete* (spent its budget, or for the
     rest stage, finished the graph) or *ended early* (no legal match left);
   - each rule's application count and the share of graphs it fired in,
     plus the rules that never fired;
   - the shape measures (dead-end share, cycle rank per room, deep-end
     distance) and the size class mix, each as p10 / p50 / p90 / mean.

   It exits 1 if any graph raised. A `when` rule that never fires may only
   need the right context (`great_hall` needs `--race-scale 1.4`).
3. **draw** writes `<set>.html` (or `<set>-<theme>.html`) with the start
   graph, the recipe as a table, a before and after diagram for every rule,
   the rules of every layer that fits, and one example graph grown at 15
   rooms. Open it in a browser. `output/` is gitignored.

How to read a diagram: the match is on the left and the replacement on the
right. Node fill and outline show the kind; an `Area` is a dashed circle,
and the radius shows the size class. A **bold id** is the same graph node on
both sides. Each dotted "outside" stub stands for one match node's edges to
the rest of the graph. On the right, dashed lines from the stub show where
those edges go, numbered in order when they split. An orange arrowhead
points to the higher end of an `above` / `below` edge, a double tick marks
`level`, and a red bar marks `threshold`. Under each card, captions list the
`when` condition, the rooms and budget the rule adds, and notes such as
"the size written here is ignored".

### What a check error looks like

Each problem is one line: file › rule or stage › field: what was found, what
was expected. Every problem in the file is listed, not just the first:

```
FAIL  classic_eq.toml: 2 problem(s)
      classic_eq.toml › set › start_nodes[2].size: found "big", expected one of tiny, small, medium, large, huge
      classic_eq.toml › recipe "Loops" › apply.rng: found a rule not in the set, expected a rule of the set (or its layers): one of annex, branch, cavern, ...
```

A build never falls back silently: a set that fails its checks fails the
build with this same report. If you are a model fixing your own output,
change exactly the field named, to one of the values listed after
"expected".

## The invariants

The driver checks these after every application. It rejects any placement
that would break one and tries another:

- **Connected.** `reattach` keeps this by construction, provided every match
  node's outside edges go somewhere.
- **Degree at most 4.** A room opens at most one wall per side. Areas count
  toward a room's degree.
- **Loops of 4 to 5.** Every edge on a cycle lies on a cycle of 4 to 5
  nodes. Areas count as nodes, and since each becomes at least one room, a
  loop through an Area can only get longer. A ring of three is rejected,
  even through an Area: the router leaves a room through the wall facing
  the other room, so a triangle puts two of its corridors on one wall,
  where they overlap past the doorway and the build splits or drops one.
  Write loops as rings of four or five (`loop` in `classic_eq` hangs three
  rooms off the placeholder and joins them back), and give `match_hops`
  rules a minimum of 3.
- **Exact room count.** Rooms plus Areas never pass n, because each Area
  still needs a room. The last Area is never finished while the graph is
  short of n, unless some growth rule left in the recipe can grow without an
  Area.
- **Step cap.** A stage takes at most 8 x n steps, after which it raises
  `TopologyError` naming the set, the stage and the cap.

## Traps

These came up writing `classic_eq` (task 5). Check for each one before you
run a dry-run.

- **The rest stage needs rules that grow from finished rooms.** An `Area`
  can be boxed in: at 4 connections, or on a loop of 5 that can't get
  longer. If every growth rule in the rest stage matches an `Area`, the
  stage gets stuck short of n and raises `TopologyError`. `classic_eq`'s
  `split`, `annex` and `deepen` match finished rooms, at low weights, as the
  fallback (0 failures in 1040 graphs).
- **Edge-only rules spend no budget.** A rule like `shortcut` adds no node,
  so it spends nothing. A stage made only of such rules runs until no match
  is left, or until the step cap. Put growth rules beside them, and keep
  their weights low.
- **Sizes on kept nodes are ignored.** A replacement node that reuses a
  match id with the same kind keeps its old size, whatever `size` you write
  (the format still requires one on every room node). To resize, change
  the kind, or add a new node. The diagram captions such a node "kept".
- **Reattach splits by neighbour id.** The split order follows the outside
  neighbours' ids, not their position. So a rule can't choose which side of
  the path a new node takes: with `["x", "y"]`, which of the way in and the
  way on goes to `x` depends on ids. Symmetric rules (in line on the way)
  are fine; "this side, not that side" can't be expressed.
- **Matching is by exact kind.** There is no "any room" wildcard: to join
  any two rooms you need one rule per kind pair. `shortcut` matches only
  `chamber`s.
- **The match is induced.** Matched nodes must not have any edge between
  them beyond the `match_edges` you list. Two chambers that are already
  joined don't match a two-chamber pattern with no `match_edges`.
- **Shares count Areas.** A rule that adds an `Area` spends budget now for a
  room that comes later. The `round(share x n)` rounding means a share of
  0.05 gives a budget of 1 from n = 10, and 0 below that.

## Writing a new set (checklist for a person or a model)

1. Copy `classic_eq.toml` to `rules/topology/<name>.toml` and set
   `[set] name = "<name>"`.
2. Keep exactly one `entrance` in the start graph, and at least one `Area`.
3. Give every room node in `start_nodes` and `replace` a size, and give no
   `Area` a size.
4. Give every match id an entry in `reattach`.
5. End the recipe with a `"rest"` stage that holds a finishing rule, plus at
   least one growth rule that matches only room kinds.
6. Run `check` until it passes, then `dry-run` until no `TopologyError` is
   left and the measures sit where you want them, then `draw` and read the
   diagrams.
7. To use the set for a theme, add it to `themes.toml`.

## Wall styles

The rules above decide a dungeon's rooms and how they join. A **wall style** decides
what those rooms look like: `rules/walls/<name>.toml`, checked in the same way. Each
room keeps its Box (the rectangle placement and corridors use) and draws its real
walls inside it, so a style can never break a layout.

```toml
[style]
name = "rough"              # must match the file's name
description = "A natural cave."
complex = "voronoi"         # how the Box divides: voronoi, grid or facet
cell_size_h = 4.0           # Cell size, in the race's body heights (not for facet)
wobble_h = 1.3              # how far each wall vertex wanders inward (optional)
fill = [0.70, 0.85]         # floor over Box, before walls wander (not for facet)
floor_relief_h = [0.0, 0.9] # how far a floor can rise
ceiling_spread = [0.1, 0.6] # how far a ceiling can fall, over the room's height
corridor_break = 0.15       # how far corridor walls come in, over its width
relief_scale_h = 5.0        # how far apart rises and falls are (optional, 5 unless set)

[shapes]                    # room kind -> shape -> weight; `default` is required
default = { blob = 2, ell = 1 }
hall = { long = 3, blob = 1 }

[look]                      # theme (the theme's own textures) or rock
wall = "rock"
floor = "rock"
ceiling = "rock"
```

| Complex | Draws |
|---|---|
| `voronoi` | Irregular Cells. With `wobble_h`, no wall keeps to the Box's side. |
| `facet` | One polygon: the Box with each corner cut at an uneven angle. `shape` sets how deep. |
| `grid` | Square Cells with cuttable corners: wings, crosses and cut corners, walls on the grid. |

| Shape | Means |
|---|---|
| `rect` | The plain Box. |
| `blob` | Grows evenly from the middle. |
| `cut` | Loses its corners first. |
| `long` | Grows along the Box's long side: a gallery. |
| `ell` | Two arms. |
| `cross` | Four arms. |

To see what a style draws, without building a zone:

```bash
python scripts/topology_rules.py check rules/walls/rough.toml
python scripts/topology_rules.py draw-walls --out output/rules/
```

The numbers behind the shipped styles are in the room walls spec's design, finding 1
(`scripts/wall_survey.py` measures them).

## Room layouts

The rules decide the rooms and the wall styles their shapes. `rules/rooms/layouts.toml` decides
what stands in them, checked the same way. A room takes its room type's recipe, else its kind's,
else the default, and every room type must have one (`features = []` is a recipe).

```toml
[types.throne]
features = [ { kind = "dais", at = "far_end", poi = "boss" },
             { kind = "plinth", at = "on_dais", height_h = 1 },
             { kind = "pillar", at = "rows", spacing_h = 8 } ]
```

| Field | Means |
|---|---|
| `kind` | `pillar` (floor to ceiling), `plinth`, `boulder`, or `dais` (a raised floor you walk onto) |
| `at` | `centre`, `far_end`, `ring`, `rows`, `corners`, `along_wall`, `scatter`, `on_dais` |
| `count` | how many: a number or `[low, high]`; an arrangement may place fewer |
| `side_h`, `height_h`, `spacing_h` | across, over the floor (a dais: its rise), between neighbours, in body heights |
| `radius` | a ring, as a share of the room's short side |
| `share` | a dais's floor, as a share of the room's |
| `chance` | how likely this line is at all |
| `poi` | a point of interest it carries: `boss`, `treasure`, `altar`, `guard`, `ambush`, `view` |

The way through always stays clear. A spot in the way is dropped and recorded in the sidecar, so
a recipe can ask for more than a small room can hold. Stock rooms are mostly bare of solids, and
their furniture is placed objects, which is a later step's: keep ordinary rooms simple, and let
named ones stand out. To see what a recipe draws, without building a zone:

```bash
python scripts/topology_rules.py check rules/rooms/layouts.toml
python scripts/topology_rules.py draw-rooms --out output/rules/
```
