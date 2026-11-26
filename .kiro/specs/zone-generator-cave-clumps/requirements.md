# Requirements — zone-generator-cave-clumps (roadmap step 29)

> **STATUS: done (closed 2026-11-25; look skipped at the user's word: "Skip the look").** Drafted 2026-11-25 at master `056296a`. After closing
> step 27 the user said "You pick step 27 followups". The lead picked the two that answer the
> user's own first-look words ("i would expect the potential for rooms to clump"), plus the
> draw time step 27 cost. Task index: `tasks.md` (card format). Decisions: `archive.md`.

## Introduction

Step 27 put cave rooms at any bearing with angled entries, but its own measures left two gaps
against stock caves (`archive.md` of zone-generator-random-placement, decision 5 and
"Follow-ups"):

- **No room opens straight into another.** Stock chambers touch directly on 0.30 of edges
  (`scripts/stock_room_shapes.py`, "direct"); ours always have a corridor between them.
- **Rooms don't clump.** Nearest-neighbour minimum 1.39–1.64 median sides (stock 0.63, target
  ≤ 1.0); seed 731402518 reads 1.64.

It also made cave placement 2.7x slower (30 rooms: 25.7 s against 9.5 s; decision 6), mostly
in `start_positions` → `_start_crossings` (10.5 s of 64 tries) and `_untangle` (5.4 s).

## Requirements

1. **Cave draw time.** A 30-room cave Graph layout draws in at most 1.5x the 9.5 s
   pre-step-27 time (≤ 14 s), on the same seeds, with **identical placements** (the same
   centres to float equality), so the speed-up changes no build.
2. **Rooms open into each other.** In cave Graph layouts, 0.20–0.35 of edges (stock 0.30)
   join two rooms through a throat: the rooms nearly abut and the corridor between them is no
   longer than one corridor width door to door, so the eye reads one room opening into the
   next. Every reader (mesh, outline, gate, decor, map, transitions) takes a throat as it
   takes any corridor.
3. **Rooms clump.** Cave nearest-neighbour minimum ≤ 1.0 median side and CV ≥ 0.30 over cave
   seeds 2000–2039 and on seed 731402518, with step 27's bearing and entry-angle targets still
   met (axis share ≤ 0.35, entry p50 ≥ 15°) and the grid score ≤ 0.10.
4. **Nothing else moves.** Built, hewn, warren, outdoor, classic, city and wilderness builds
   stay byte-identical (the step 27 byte check), unless a named fix needs otherwise.
5. **The gate holds.** The cave/warren gate sweep passes at least what step 27 passed
   (694/696 on its sweep); bands within 5%.
