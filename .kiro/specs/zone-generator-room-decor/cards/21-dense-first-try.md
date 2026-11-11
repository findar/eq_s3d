# 21 — Dense passes the gate first try

Index entry: `tasks.md` task 21. Requirement 12.1. Added by the coordinator after task 15.

## Goal
Task 14 proved the gate's first try at Normal only. Task 15 found a 16-room Graph dungeon at Dense fails it for pinned seeds 4 (`footprint_cut` in `room_9`) and 7 (`throat_narrow` in `room_13`), so the page returns 503 for a pinned seed. Make placement agree with the gate at Dense (fix the cause in placement, as decisions 31 and 47 did), and extend the sweep to Dense.

## Done when
- [ ] Dense dungeon and city: first try 40/40 over seeds 0–39 (16-room Graph dungeon included), Normal still 40/40 and inside its bands.
      → verify: `python -m pytest tests/test_decor_bands.py -q -n 0`
- [ ] Seeds 4 and 7 at Dense build first try; the ACCEPTANCE known-issue line for them is removed.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Don't make Dense sparser to pass: fix where placement and the gate disagree. Timing tests fail under parallel load: rerun alone.

## Result
