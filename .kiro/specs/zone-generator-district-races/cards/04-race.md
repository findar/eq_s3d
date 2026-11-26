# 4 — A race per District

Index entry: `tasks.md` task 4. Requirements 4.

## Goal
A District can carry its own race: its rooms and corridors are sized by that race's H, and a link between two races by the smaller.

## Done when
- [ ] `DistrictSpec.race` (written only when set); `district_plan` entries may name a race; unknown races warn and fall back.
- [ ] Rooms and corridors per District sized by its race (`semantics.room_side`, `corridor_size`); cross-District corridors by the smaller H.
- [ ] A giant/goblin pair over seeds 2000–2019 (16 rooms, Districts on) passes the gate; room-side medians per District match each race's band within 10%.
- [ ] Byte identity: zones whose Districts carry no race, and every zone without Districts, unchanged (step 27 byte check plus a districted fortress).
- [ ] Quick tier while working; `-m gate` and full suite alone at close.

## Pitfalls
- lessons-learned "Bound elevation by the corridor run": a giant's rooms are 3.7x a goblin's; check elevation and grade across a race boundary.
- If decor or geometry needs a fix, stop and report.

## Result
✔ 4f0daca · 4285 passed
