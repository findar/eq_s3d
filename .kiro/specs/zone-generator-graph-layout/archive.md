# Archive — zone-generator-graph-layout

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

Nothing yet. Rows are added at the close step (task 17).

## Decisions

The design's "Decisions" section (1–8) stands. The user settled the open
questions on 2026-11-03:

- **Graph rewriting as the article describes it:** the graph engine follows
  shaggydev's "Graph rewriting" (2022-11-20): basic rules (pattern →
  replacement, as data), iterate until no placeholder is left, place the
  rooms with a function over the graph (a spring layout), then create the
  connections. Replaces the first draft's hard-coded add-one-room operators.
- **A toggle, not shapes:** the rules decide the shape, so the choice on
  generation is the engine, Layout `classic` | `graph` (`classic` the
  default). The first draft's linear / branching / looped profiles are gone;
  a rule set's weights live in its file.
- **Recipes:** a rule set grows its graph by an ordered recipe of stages.
  Recipes are a first pass that will need iteration, and users may want
  access to them, so they live in the rule-set files with commented examples.
- **Prompt words are a fast follow** (see Follow-ups).
- **Zone types:** `dungeon` and `outdoor_dungeon`, dungeon the focus.
- **Districts become a rule, structure only:** a rule can label nodes with a
  district and tag the joining edge `threshold`; the district look is a
  follow-up.
- **Rule storage:** TOML rule-set files with strict checks (rules will be
  prompt-generated eventually, so checking is a requirement), a dry run, and
  before → after diagrams.
- **Rules set room sizes,** as fixed classes (`tiny` … `huge`) on the nodes
  they create; units come from the zone type, then the race's scale (an ogre
  room and a halfling room use the same rule).
- **Vertical:** rules carry `above` / `below` / `level` now; step 6 acts on
  them through elevation only and keeps every room apart in plan (no
  accidental stacking); stacking is step 7.
- **Room shapes:** step 8. The format carries `shape` now (`rect` only).
- **Themes and rule sets are layered:** a theme names a base set and adds
  its own layer of rules and stages; rules set room kinds, themes map kinds
  to their room types.
- **Two base sets to prove extensibility:** `classic_eq` and `warren`, plus
  the `temple` layer.

## Follow-ups

- **Prompt words choose the topology** (umbrella Req 22.5–22.7): words like
  "maze", "winding" or "linear" pick a rule set or recipe. A maze could also
  bring its own Placement (the user's "springiness applied a different
  way"): Placements are named per rule set for this.
- **The district look** (umbrella Req 23.5): materials and lights differing
  across a `threshold` edge, and the umbrella's district counts (Req 23.1).
- **Stacked rooms** along `above` / `below` edges, with stairs and shafts:
  step 7 (`may_overlap_in_plan`).
- **Room shapes** (Voronoi blobs and others) through the `shape` attribute:
  step 8.
- **Users editing recipes** from the web app or a prompt.
