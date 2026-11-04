# Archive — zone-generator-graph-layout

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

Signed off 2026-11-04; master `264b55a`. Suite 1225 (fast); thorough green
(task 15). Graph is the default layout for new dungeon and outdoor-dungeon
requests.

| Task | What landed |
|------|-------------|
| 1 | Stock dungeon topology survey (`scripts/dungeon_topology_survey.py`): chambers split by floor width (40 u); classic bands from 5 zones, warren from blackburrow (6 of 12 zones failed the map check) |
| 2 | `generators/layout_engine.py`: the `LayoutEngine` seam, `ClassicEngine` (TinyKeep, moved), byte-identical goldens captured first; Job B's three touch points (entry, role size bias, edge relations) |
| 3 | `generators/topology/`: `TopologyGraph` and the TOML rule-set loader, every check collected and reported by file, rule or stage, field |
| 4 | The rewrite driver: matcher, reattachment, `when` conditions, recipe stages and budgets, invariants (connected, degree ≤ 4, loops), step cap, theme layers |
| 5 | `rules/topology/classic_eq.toml`, `layers/temple.toml`, `themes.toml`, tuned to the survey's classic bands |
| 6 | `rules/topology/warren.toml`, data only: the format extends with no code change |
| 7 | `scripts/topology_rules.py` (check, dry-run, draw), `generators/topology/draw.py`, the authoring guide `docs/TOPOLOGY_RULES.md` |
| 8 | Placement (`generators/topology/embed.py`): size classes, the spring layout, `GraphEngine`; grown zones keep the classic floor area |
| 9 | `ZonePlan.layout` / `rule_set`, each theme's kind → room type map, the sidecar `layout` block |
| 10 | CLI `--layout` / `--rule-set`, server controls (400s), graph outdoor dungeons: the layout faces the hill's way in, other facings retried, the entrance room wide enough for the Tunnel |
| 11 | Web: Layout toggle and Rule set select |
| 12 | Gate sweep (graph 216/216 first try); two step 5 bugs fixed: rooms under the map edge, the spawn floating over the dug Apron |
| 13 | First look signed off; findings: rooms look alike (follow-up), themes need the description box (task 14) |
| 14 | Theme and Race in the Controls panel; a temple gets its nave from 7 rooms |
| 15 | ACCEPTANCE "Step 6 — Graph layouts" (Controls panel only), graph-vs-classic timing test, thorough run green |
| 16 | Acceptance pass signed off; the default decided: Graph |
| 18 | Loops survive placement: rings of four or five (the driver refuses three), each neighbour on its own wall (fidelity 0.82–0.92 → 0.97–0.99) |
| 19 | Rooms carry their kind; the rules' `deep` room is the climax and the boss |
| 20 | Big races: rooms placed at race-scaled size (giant fidelity 0.865 → 0.991); ogres get great halls |
| 21 | Graph is the default for new requests; plans saved before step 6 rebuild as Classic (`ZonePlan.from_saved`) |

Not done here, carried forward: see Follow-ups.

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

- **Grown rooms keep the classic floor area (task 8, 2026-11-03):** the size-class base is divided by the grown graph's RMS class multiplier, so a grown zone has the same total room area as a classic one of the same count. Without it a `classic_eq` mix had ~1.5× the area and grown rooms failed tight Envelopes (not 3 rooms in a 1000 u disc, where classic fits 3–5). Size classes are therefore relative within a zone; the zone type and race still set absolute scale.

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
- **Room kinds don't show** (first look, task 13): grown and classic dungeons are hard to tell apart because every room is a rectangle with the same textures. Kinds (lair, hall, hub, deep) could drive shape (step 8) and contents (step 9), and perhaps materials.
- **The walk surface takes ceilings as floor** (found by task 1): `analyzer.traverse.build_walk_surface` tests |nz|, so a downward-facing ceiling passes as standable; in befallen it made a second "floor" 14 u above the real one. The survey keeps only floor-wound WLD faces. Check whether `scripts/outdoor_dungeon_survey.py` and the gate on our own TERs are affected.
- **Rule-format gaps found writing `classic_eq` (task 5):** (a) matches are by exact kind, so "join any two rooms" needs one rule per kind pair: a `room` wildcard kind in matches would fix it; (b) `reattach` splits outside edges by neighbour id, so a rule can't say which side of the path a new node takes; (c) a rule that adds only edges spends no stage budget, so a stage of only such rules saturates; (d) a kept node keeps its old size, so sizes written on kept nodes are ignored (the checker could flag them). Worth fixing before prompt-written rules.
- **Rule sets in the page are hard-coded** (task 11): the Rule set, Theme and Race selects list their values in `web/index.html`; a route listing them would keep a new rule-set file from needing a page edit.
- **A race with no theme builds fortress rooms** (task 15): the existing default archetype (`semantics.DEFAULT_ARCHETYPE`); the Theme select's "None" can read as "no theme" when a race is set.
- **The CLI has no theme or race flags** (task 15): `--theme` is the old alias for `--zone-type`.
- **Warren bands rest on one zone** (blackburrow; runnyeye's split failed): a better chamber split (lumpy caves, wide doorways, passage-only loops) would firm up both base sets' bands.
