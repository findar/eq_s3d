# Requirements Document

> **STATUS: roadmap step 20, DONE (closed 2026-11-19; first look skipped at the user's word).** Drafted 2026-11-18 at master `a26d07b`. After step 19 the
> user said "continue working"; multi-zone worlds still wait on their design review, so the lead
> chose the next unblocked umbrella piece: M3's Districts (umbrella Requirement 23). The user
> confirms the choice at the first look (task 9). Task index: `tasks.md` (card format).
> Decisions: `archive.md`.

## Introduction

A dungeon today has one Purpose from end to end: a 20-room fortress is fortress rooms, one
palette and one boss. Umbrella Requirement 23 splits a larger dungeon into 2–3 **Districts**
(like a dungeon's wings), each with its own Purpose, palette, light mood and climax, joined by
one corridor each, the **Threshold**. A prompt like "a temple fallen to the dead" or "two
factions" asks for them. The umbrella design ("Districts", "District partition") is the starting
point; this spec amends it where the code has moved on.

## Amendments to the umbrella

- **A1 — Off by default in this step.** The umbrella switches Districts on for every zone of 8
  or more rooms. That would change every such zone's rooms and corridors and invalidate step 19's
  bands before anyone has looked at a District. Here the switch is off unless the Controls'
  Districts box, the CLI's `--districts` or a contrasting-area prompt phrase (23.9) turns it on.
  Turning the default on is a later call, after the first look.
- **A2 — Dungeons only.** Districts apply to `dungeon` zones, both layouts (`classic` and
  `graph`). Cities keep their own content; outdoor dungeons (an Envelope under a hill) come
  later. A switch that is on for another zone type is ignored with a Sidecar note.
- **A3 — Purposes are the archetypes as built.** The vocabulary is `semantics.ARCHETYPES` (11
  names today; `cave` arrives with its own step). The four archetypes without a palette
  (`war_city`, `warren`, `corrupted_sanctum`, `mine_delve`) get one, so 23.5 holds on any pair.
- **A4 — Partition before pacing.** The umbrella partitions after pacing. Pacing's size bias
  grows the climax, and each District has its own climax, so the zone entrance is found first
  (pacing's rule), the graph is partitioned and its cross-District edges dropped, and pacing then
  runs once on the pruned graph with one climax per District. With k = 1 none of this draws from
  the rng, so 23.6 holds byte for byte.
- **A5 — Graph rule sets' `district` labels are not used.** The partition is the umbrella's
  tree cut on the engine's graph; a rule set's own labels stay in the layout record.
- **A6 — The bands learn Districts.** Dropping cross-District edges lowers the loop count, so the
  quality bands gain the District count in their key and `district_balance` gets a bound
  (step 19 decision 4's rule).

## Glossary

- **District**, **Threshold**, **Purpose**: as in the umbrella glossary.
- **District relationship**: `sequential` (default), `factional` or `abandoned_vs_active`.
- **Compatibility table**: bundled data naming which Purposes may sit next to each other and
  which contrast.

## Requirements

### Requirement 1: The partition

1. `generators/districts.py` `district_count(n, on)` gives umbrella 23.1's k.
2. `partition_districts(rooms, edges, entrance, k, rng)` is the umbrella design's tree cut: every
   room in one District, each District's induced subgraph connected and at least
   max(3, ⌊n / (k + 1)⌋) rooms; exactly one edge kept between each pair of adjacent Districts,
   flagged as the Threshold; the same partition for the same inputs (23.2, 23.3). When no cut
   meets the sizes, k drops and the requested and resolved counts are returned for a note (23.1).
3. With k = 1 the partition returns the edges unchanged and takes nothing from the rng.
4. `ZoneSpec.districts` holds the umbrella's `DistrictSpec` list (empty for one District),
   survives a JSON round-trip, and an older spec without it loads as empty.

### Requirement 2: Purposes, palettes and lights

1. The compatibility table and the relationship rule choose each District's Purpose when none is
   proposed (23.8); proposals fill the first k Districts (23.11); an unknown Purpose or
   relationship is ignored with a note (23.12); a pinned single Purpose gives every District it,
   with palette and light variants (23.10).
2. Rooms take their room types from their own District's Purpose by in-District depth; each
   District has one climax, the deepest room from its District entrance (23.4).
3. Every archetype has a palette (A3); `abandoned_vs_active` gives the non-entrance Districts a
   lower-saturation palette and dimmer light (23.8).
4. The two rooms at each end of a Threshold differ in material set and in light colour or
   intensity (23.5).

### Requirement 3: The layout

1. `LayoutGenerator` partitions after the engine and before pacing (A4), on both layouts, and
   records Threshold corridors (`CorridorSpec.threshold`) and `spec.districts`.
2. With locks, min(locks, Thresholds) Gates go on Threshold corridors first, keys on the
   entrance side (23.7); solvability holds.
3. A corridor split that resolves a crossing never adds a second edge between two Districts; if
   it would, the Draw fails as a plan error and is redrawn (the pipeline already counts those).
4. With the switch off, or k resolved to 1, every existing zone is byte-identical (23.6, A1).
5. The rooms stay walkable and joined: the existing walkability and solvability gates pass.

### Requirement 4: The plan, prompt, CLI and Server

1. `ZonePlan` gains `districts` (bool, default off), `district_plan` (up to 3 proposals) and
   `district_relationship`; a saved plan without them loads with them off.
2. The rule planner turns on Districts for a bundled contrasting-area phrase, proposing the
   named count (2–3), a Purpose per area and one relationship (23.9). The LLM planner's schema
   carries the same fields.
3. The CLI takes `--districts`; the Server's generate accepts the same fields; a switch on a
   zone type other than dungeon is ignored with a note in `warnings` (A2).
4. The sidecar carries `districts` and, per room, its District, and per corridor its Threshold
   flag (umbrella 27.3).

### Requirement 5: Quality

1. The band key gains the resolved District count; the sweep measures districted dungeons and
   fills their rows by step 19 decision 4's rule; `district_balance` is bounded for k ≥ 2 (A6).
2. Existing rows (k = 1) don't move.

### Requirement 6: The page and the map

1. The Controls panel has a Districts box (shown for dungeon) sent with generate; a prompt that
   turned Districts on shows it ticked.
2. The map draws each District's hull, coloured per District, and marks Threshold corridors
   (umbrella 14.1's order: hulls among the annotations, after the outline).
3. The room panel names the room's District and its Purpose.

### Requirement 7: Bytes

With the switch off, every geometry golden stays byte-identical
(`tests/test_layout_engine.py tests/test_site_builds.py tests/test_decor_builds.py tests/test_partial_rebuild.py`).
