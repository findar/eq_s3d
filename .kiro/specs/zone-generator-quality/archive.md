# Archive — zone-generator-quality

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

Decided 2026-11-18 by the lead after the user's "Skip and continue more work" (multi-zone worlds
wait on the user's design review). The user confirms at the first look (task 7).

1. **Step 19 is M3's quality gate, not Districts.** It is the unblocked umbrella piece that other
   work waits on (step 18's `edit_outside_bands`), and it is small; Districts and the `cave`
   archetype are a later step.
2. **Bands are the generator's own targets, measured from its output** (A1): stock zones have no
   room graph to measure. Ordinary output passes; only the dull tail is redrawn.
3. **Rebuilds and edits measure, they don't redraw** (A4).
4. **Bands are one-sided bounds on each metric's dull side** (task 2, `scripts/quality_sweep.py`
   over ~24k Draws). Each sits at the nearest round value that fails at most 1% of the row's
   Draws (0.5% on the outdoor dungeon, whose Draw builds a World and can take seconds). That
   keeps a key's fail share at 0–3.5% and the expected Draws per generate at about 1.03 or
   less. Unbounded: `room_type_diversity` (a theme's room types run out at about 5–8, so the
   ratio is set by theme and N, not by the seed), `branching_factor` (repeats `max_degree`),
   `district_balance` (no Districts), and `critical_path_ratio` on graph layouts (their climax
   sits near the entrance by design). Elevation is bounded only off `flat`.

## Follow-ups

- **Slow outdoor-dungeon Draws** predate step 19: on outdoor graph flat, 67 of 405 Draws took
  over 30 s, and a 30-room `ice_keep` (seed 1100087430) took 223 s alone. It is a generator cost.
