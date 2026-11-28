# Archive — zone-generator-layout-repair

## What landed

| Tasks | What landed | Commits |
|---|---|---|
| 1 | `scripts/generate_profile.py`: per-phase time and refusal reasons per generate; 210 generates, 0 gate failures, decor 44% / finish 28% / gate 16% / plan 6% | 2 |

## Decisions

1. **Step 33 is layout check-and-repair, measured first; step 32 is paused** (the lead, 2026-11-27, on the user's
   "can we pause the step 32 work and focus on that if it should improve our build times?"). Both own
   `generators/layout.py`; step 32 task 1 is parked on `agent/followups-1` and resumes after this step.
2. **A plan check and local repair would not make generates faster: cut cards 2-4 as speed work**
   (task 1's measurement, master `c3d9b99`, quiet machine). Of 210 generates (the 24-room
   intrusion and sequential sets, 60 from the seed-31 sweep, the prompt seeds 2020-2029, 20
   zones without a race), 210 passed on the first attempt. None was rejected by the gate. Two
   specs were refused by the bands, and 5 layout redraws inside a Draw took 4 s of 8676 s. Catching
   the failures the plan can see would save 0%, and repairing them locally 0.05%. The median stays
   27.3 s and the max 144 s, far under the 15% bar. The time goes to decor (44%, RoomContexts 12%),
   the map files (~24%) and the gate (16%). The seat on `agent/followups-1` does not change this
   (0.4%). Recommendation: stop step 33 as a speed step. Card 2 is worth keeping only as a cheap
   guard (a corridor-crossing check that names the gate reason), not for speed. Cards 3-4 (repair,
   contact energy) are a quality lever for step 32's breach rate: `_resolve_conflicts` drops 266
   loop edges, so fold them into step 32 if the seat leaves gaps. A speed step should profile decor
   placement and RoomContexts, and `_write_map_artifacts`. The lead decides.

3. **Step 33 stops after its measure** (the lead, 2026-11-27, on the user's condition "if it should improve our
   build times"): 210 generates on a quiet machine all passed first attempt with no gate rejection; the projected
   saving is 0-0.05%. Generate time is decor 44% (RoomContexts 12%), finish 28% (map files ~a quarter of it), gate
   16%, plan 6%. `scripts/generate_profile.py` stays for later speed work. Step 32 resumes.

## Follow-ups
- Loops-first planning (designed one-way loops) and corridors as placed blocks: later slices, after task 3.
- A speed step, if wanted: decor placement and RoomContexts (44%), `_write_map_artifacts` (about 7% of all time), the gate (16%).
- Plan check as a guard naming the gate reason (card 2), and local repair / contact scoring as a quality lever (266 loop edges dropped by `_resolve_conflicts` over 210 generates).
