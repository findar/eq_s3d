# 3 — Stair geometry and switchbacks

Index entry: `tasks.md` task 3. Requirements 3.1–3.3. Design "Staircases".

## Goal
Stair geometry a layout can ask for: straight stairs with risers ≤ Riser_Cap (finding 7), and Switchbacks (two flights and a flush landing in a stairwell box) when the leg is shorter than the stair's run; flush at both ends; headroom kept.

## Done when
- [x] A corridor with a stair kind builds risers ≤ Riser_Cap and treads of the set depth; a switchback when its leg is short; both flush with the room floors.
- [ ] Every generated stair passes the task 2 gate checks (property test over rise, leg length, width).
      → verify: `python -m pytest tests/test_stair_geometry.py tests/test_traverse_connectors.py -q`
- [x] Ramps and flat corridors build byte-identically (the classic goldens and `tests/test_wall_uvs.py` pass).

## Pitfalls
- lessons-learned "Same-axis room pairs need a Z-route": the whole rise stays on one leg; the switchback folds within that leg's stairwell, it doesn't add a leg.
- UVs on treads and risers: follow step 3's wall UV convention (`tests/test_wall_uvs.py`).

## Result
