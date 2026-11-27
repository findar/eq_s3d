# 16 — The giant fortress prompt builds its goblin breaches

Index entry: `tasks.md` task 16. Requirements 4, 10, 11.

## Goal
The step 31 headline prompt, "a towering giant fortress the goblins tunnelled into, with 16 rooms", builds a giant host with a goblin intruder joined by breaches, and passes the gate on pinned seeds. At task 11 it planned the whole zone as giant: the gate's Transition clearance check measured every goblin-sized opening against giant H ("leaves 13–18 u clear, under 44 u"), so pinned seeds 2020–2023 and 0 failed, and the one random seed that passed had no goblin breach.

## Done when
- [ ] The cause named: why the prompt's plan reaches the build without a goblin District race (or with one the gate ignores). Check against decision 17.
- [ ] The gate's Transition clearance check reads the race the opening was sized by (`semantics.corridor_race`, the smaller race of its two ends), not `spec.dungeon_race`; a zone with no District race reads exactly as before.
- [ ] `flood_level` reads the room's race (`semantics.room_race`), so water in a goblin room is goblin depth (the archive follow-up).
- [x] The prompt on seeds 2020–2029: every zone passes the gate; at least 8 of 10 have a goblin breach, each miss traced.
- [ ] `docs/ACCEPTANCE.md` step 31 case p re-pinned to a passing seed with its breaches.
- [ ] `--intrusion` sweep, seed 31: 240/240; byte check: zones without a District race byte-identical to master; quick tier; `-m gate` and the full suite alone at close.

## Pitfalls
- Don't loosen the clearance bar: it's per race, not removed.
- Byte identity: build each zone in its own process (lessons-learned, the in-process leak).

## Result
