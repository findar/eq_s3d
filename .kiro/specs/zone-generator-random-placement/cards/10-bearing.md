# 10 — Caves at any bearing

Index entry: `tasks.md` task 10. Requirement 7, design "First-look fixes".

## Goal
Cave Graph rooms clump and spread at any bearing, and corridors meet their walls at an angle.

## Done when
- [ ] Task 9's measures on seed 731402518 and cave seeds 2000–2039 meet task 9's targets
      (bearing spread and clumping near stock; entry angles not all square), before/after in the
      commit body; the grid score stays ≤ 0.10.
- [ ] The grown graph, Levels and stairs unchanged; door-to-door median within 4/3 of before.
- [ ] Cave/warren gate sweep (`--only cave warren --layouts classic graph --verticality flat moderate dramatic --rooms 2-30 --seeds 2 --seed 23`, `EQ_PATH` set) ≥ 693/696.
- [ ] Built, hewn, warren and outdoor builds byte-identical (the Req 6 byte check, plus a fortress
      and an outdoor dungeon compared by archive entry).
- [ ] `EQ_PATH='F:\everquest_rof2' python -m pytest tests/ -q -n 4` (full, alone) green.

## Pitfalls
- lessons-learned "Geometry / fields": flush openings, ramp subdivision, grade by run.
- An angled opening must be read the same by mesh, outline, decor RoomContexts, gate and map.
- If it needs files beyond Owns (decor, transitions, gate), stop and report.

## Result
