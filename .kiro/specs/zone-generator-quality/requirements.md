# Requirements Document

> **STATUS: roadmap step 19, ready.** Drafted 2026-11-18 at master `19c041d`. The user said "Skip
> and continue more work" after step 18; multi-zone worlds still wait on their design review, so
> the lead chose the next unblocked umbrella piece: M3's quality gate (umbrella Requirements 24
> and 25). The user confirms the choice at the first look (task 7). Task index: `tasks.md` (card
> format). Decisions: `archive.md`.

## Introduction

Every generate today passes the hard gates (walkable, corridors joined, RoF2 format) or is
redrawn, but nothing judges whether the layout is worth looking at: a dungeon can come back as a
straight line of same-size rooms on one floor. Umbrella Requirement 24 adds a **quality gate**: a
meter that reads the room graph from the spec alone, bands per kind of zone, and a soft gate that
redraws a dull seed before it is built. Requirement 25 makes a result that misses the bands
visible everywhere it shows. Districts (the rest of M3) are not in this step.

## Amendments to the umbrella

- **A1 — Bands are keyed by what the generator has now.** The umbrella keyed bands by a
  `topology` control (linear / branching / looped) that was never built; rule sets and the
  layout engine took its place. Bands are keyed by zone type, layout (`classic` or `graph`),
  room count and verticality, and are measured from the generator's own output by a sweep
  (task 2), set so its ordinary output passes and only the dull tail is redrawn.
- **A2 — The metric set follows the spec as it is.** `room_type_diversity` reads
  `semantic_type` (the umbrella's design table called it `semantic_diversity`).
  `district_balance` is reported but unbounded until Districts land. Task 2 may drop a metric
  that no band can use, recording why.
- **A3 — No Session.** Step 18 made the versions the history (edits A1, A2), so "undo and redo
  responses" are opening a version, and the page shows each version's sidecar `quality` entry
  (25.8). Versions built before this step have none and show quality unknown (25.11).
- **A4 — Rebuilds measure, they don't redraw.** A decor rebuild or a partial edit keeps its
  parent's room graph, so it is measured and recorded but never redrawn. Its reason, if it fails,
  is its parent's (`edit_outside_bands` for an edit). A rooms reroll draws a new `rooms_seed` and
  is redrawn like an unpinned generate.

## Glossary

- **Quality_Meter**, **Quality_Bands**, **Quality_Block**, **Quality_Degraded**,
  **Out_Of_Band_List**: as in the umbrella glossary.
- **Draw**: one `spec_factory` call for a seed (or `rooms_seed`) without building.

## Requirements

### Requirement 1: The quality meter

1. `generators/quality.py` `measure(spec)` computes umbrella 24.1's metrics from the spec alone
   (A2): `cyclomatic`, `max_degree`, `dead_end_ratio`, `critical_path_ratio`,
   `branching_factor`, `elevation_range`, `elevation_levels`, `role_diversity`,
   `room_type_diversity`, `size_cv`, `district_balance`. The graph is the rooms and the
   corridors joining two rooms (`from_room`, `to_room`).
2. Umbrella 24.2 and 24.3 hold: the same result for repeated calls, after a JSON round-trip and
   after changing only `prop_hints`, `encounter_intent`, `boss` or Gates; a pass exactly when
   every metric is in its inclusive band; the Out_Of_Band_List and the score as 24.3 defines.
3. `bands_for(zone_type, layout, n_rooms, verticality)` returns the bands as data in the module
   (A1); umbrella 24.4's unbounded cases hold (fewer than 4 rooms, fewer than 2 Districts, no
   Purpose).
4. `quality_summary(report)` is the one JSON shape `{degraded, reason, score, metrics,
   out_of_band}` (umbrella Quality_Block).

### Requirement 2: The bands

1. A sweep script measures the meter over the generator's own specs for every enabled zone type,
   both layouts, each verticality and a spread of room counts, and times a Draw.
2. The bands are set from the sweep so that, per key, at most a set share of ordinary draws fail
   (task 2 sets the share and records it), and the expected number of draws per generate stays
   within the time a generate already takes.

### Requirement 3: The gate in the pipeline

1. Umbrella 24.5–24.8 in `generate_validated`: an unpinned seed is drawn and measured before
   building, redrawn on a quality failure up to 32 Draws, then the lowest score is built
   (earliest on a tie) and returned Quality_Degraded `quality_degraded` if it passes the hard
   gates; a pinned seed is built as asked and returned `quality_outside_bands_pinned` when it
   fails. A hard-gate failure after the quality loop continues the existing retry loop with
   fresh seeds and no more quality Draws.
2. The quality Draws count against the existing timeout; a timeout during them builds the best
   seed so far.
3. The sidecar gets a `quality` entry equal to the returned Quality_Block (25.4); `ValidatedBuild`
   carries the report.
4. A4: rebuilds and edits measure and record without redrawing.
5. A pinned seed builds byte-identical to today apart from the sidecar's new `quality` entry.

### Requirement 4: Responses and the CLI

1. Generate, rebuild and edit responses carry the Quality_Block (25.1–25.3), its reason also in
   `warnings` when degraded.
2. An edit whose result fails the bands is accepted and marked `edit_outside_bands` (umbrella
   18.7).
3. The CLI prints a degraded result's reason, count and each out-of-band entry and exits 0; a
   passing result prints no quality warning (25.9).
4. The versions listing carries each version's `degraded` and `reason`.

### Requirement 5: The page

1. Umbrella 25.5–25.8, 25.10 and 25.11: the banner over the 3D view while the open version is
   degraded, with the count, the reason and a link that opens the metrics; the passed indicator
   otherwise; quality unknown for a version with no `quality` entry; the metrics list out-of-band
   entries first as `metric — value (band lo–hi)`; a response with no new build changes nothing.
2. Opening a version (the header's ◂ ▸, Undo, Redo) shows that version's sidecar entry.

### Requirement 6: Unchanged

1. Geometry for a given seed, `rooms_seed` and `decor_seed` is unchanged; the golden builds stay
   byte-identical apart from the sidecar's `quality` entry.
2. Wilderness builds (no rooms) pass with every band unbounded and carry the entry.
