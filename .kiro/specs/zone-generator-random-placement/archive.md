# Archive — zone-generator-random-placement

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

1. **Step 27 is random room placement** (the user, 2026-11-22: "Random room placement", after
   the step 26 second look: "i would say it looks good but a future task should also adjust length of halls and also when we generate rooms they should end up randomly positioned and connected"). Every Graph zone leaves the lattice as cave zones did at
   step 26; the grown graph and its wall sides stay; classic, city and wilderness keep their
   bytes. Hall length control is a separate later step.

2. **Built and hewn Graph dungeons keep the lattice** (the user, 2026-11-22, choosing "Keep
   built zones on grid"). Task 1 jittered them (grid 0.196-0.233 -> 0.066-0.085) but found
   no setting that kept both stock wall measures and hall length: straight doors put built
   wall run at 48 u (stock band 28-39), mid-wall doors need a jog and make halls 1.44-1.59x
   longer, doors within 0.6 of the middle leave run at 40.33 (band edge 40.17). Only caves and
   outdoor dungeons leave the lattice; task 2 (warrens) is dropped. Task 1 keeps its general
   fixes (decor reads door stubs, ceiling Props inside the room, grade cap, layout independent
   of wall style) and wires the build seed into the cave jitter.

3. **Decor bug fixes apply everywhere** (the lead, 2026-11-23, at task 5). The acceptance
   build found a decorated classic fortress (seed 731402518) with Props moved in room_7 and
   room_8 (87 of 95 files match; Decor None identical). They trace to `4a1d27a` (a ceiling Prop
   kept inside its room; a chain hung 4.4 u through a wall) and `9208d2b` (wall decor read along
   its edges; a banner 8.6 u behind a wall). Those are fixes, so they stay; Requirement 6 is
   amended to name them rather than keep the bug for byte-identity.

4. **First look: caves still read as a grid; room sizes too alike** (the user, 2026-11-23: "Looking at a cave, the layout still seems roughly on a grid using the seed 731402518in the acceptance pass.  i would expect the potential for rooms to clump, entrances to come in at angles.  also this makes me realize that our room sizes feel mostly similar, when there would normally be some kind of variance").
   Cause: each neighbour is offset only along its N/S/E/W wall side and doors cut square, so
   edges stay near the axes; rooms are one class side ±15% and near-square. The user chose
   "Caves only" for any-bearing placement and angled entries, and "Every zone" for size
   variance. Requirements 7 and 8 added; tasks 9–13.

5. **Targets for tasks 10 and 11** (task 9, measured on 48 stock zones' chambers; full tables
   in `ba87985`; `python scripts/grid_score.py --shapes`, `scripts/stock_room_shapes.py`).
   - Task 10, caves (spec, seeds 2000–2039 and 731402518): edge bearings within 10° of an axis
     ≤ 0.35 (stock caves 0.28, ours 0.64; 0.85 at 731402518) and ≥ 0.25 of them 30–45° off
     (stock 0.33, ours 0.05). Clumping: nearest neighbour min ≤ 1.0 median side (stock 0.63,
     ours 1.64) and CV ≥ 0.30 (stock 0.38, ours 0.19). Entry angle on the spec p50 ≥ 15°,
     share over 20° ≥ 0.30, p90 ≤ 55° (stock can't set it: the raster reads our square doors
     at 9–22°; stock p90 56°). Stock chambers also open straight into each other on 0.30 of
     edges (ours never).
   - Task 11, every kind (built, cave and enclosed-city stock agree, so one distribution):
     keep each zone's median side where the class puts it (stock 8.5–15 H, ours 11–13.5 H)
     and spread side/median as stock p5/p25/p75/p95 0.66/0.84/1.30/2.1 (ln sd 0.35; max/median
     about 2.3, ours 1.45–1.66); area CV 0.8–0.95 (ours 0.42–0.55), area max/min 9–16 per
     zone (ours 4–6); aspect p50 1.25 on the spec (stock 1.31 read, less ~0.07 for door stubs),
     p90 1.8, share over 1.5 0.25–0.30 (ours 0–0.15), the odd hall to 3–6. In H the stock
     p90 is 20–22 H, p95 24–26 H, so the 20 H band top clips the big rooms: open it to about
     26 H (a human's 156 u still under a dragon's 168 u minimum). The Size control keeps
     shifting the median. Outdoor dungeons take the cave numbers (stock outdoor "rooms" are
     open ground cut at narrowings).

6. **Cave bearing placement costs 2.7x draw time at 30 rooms** (the lead, 2026-11-23, at task 10).
   A 30-room cave draws in 25.7 s against 9.5 s on master (card bar 1.5x); capping bearing tries
   cost fidelity (0.928 < 0.936), so the time is accepted against the ~5 min budget. Angled
   corridors whose Transition no line holds square lose it (about 2 of 130 over seeds 2000-2039).

7. **Task 11's amended bars** (the lead, 2026-11-23). Under the 26 H top with class medians kept:
   area CV ≥ 0.70 and max/min ≥ 8 per kind. Fidelity: cave ≥ 0.930; outdoor −0.020 and warren
   −0.011 accepted while every final corridor graph stays connected and every dropped tree edge's
   rooms stay joined (master drops tree edges too, re-routed through a third room). Warren 27
   outdoor draw at 1.7x accepted (keeps all 27 rooms). Outdoor dungeons cap rooms at 22 H under
   the hill (one big hall under the hill takes the ground Sites need); outdoor bars CV ≥ 0.60,
   max/min ≥ 6.5 (measured 0.63, 6.7); outdoor_w zero-site 4/30 (master 1) accepted. Outdoor
   draw p95 (`quality_sweep --per-key 200 --seed 23`, master → branch): classic 3.9–6.2 s → 7.3–7.5 s,
   graph flat 34 s → 56 s (graph dramatic and moderate faster); plan errors 11 → 1 of 1200.

## Follow-ups
- **Rooms opening straight into each other** (stock 0.30 of edges; nn min 1.39 vs stock 0.63).
- **Outdoor loop corridors under size variance:** fidelity 0.925 → 0.905, loops lost fitting
  bigger rooms on the hill (163 vs 102 layout tries at warren 27).
- **Fit `dungeon_keep_clear` to the rooms** so big halls under a hill leave ground for Sites
  (outdoor_w zero-site 8/30 at 26 H).
- **Decor survey reads the zone's tallest room as open sky** (city seed 11 drops its climax, 13
  of 21 Props; master drops 1 of 5 rooms the same way).
- **Cave draw time** (task 10, decision 6): `start_positions` spends 10.5 s of a 30-room cave on
  64 tries, ~70% in `_start_crossings`; `_untangle` 5.4 s. Incremental crossing counts would cut it.
- **Not looked at in 3D** (task 10): angled openings, long straight tunnels aimed at a room
  centre, held lines through frames.
