# 9 — The room view per District

Index entry: `tasks.md` task 9. Requirement 2. Added by the lead at the task 2 merge.

## Goal
The room view (`generators/decor/room_view.py`) and `scripts/stage.py decor` dress a districted
zone's rooms and corridors with their own District's layers, as the build does since task 2. They
read the sidecar's `decor.districts` record and pass `rules_of` to `BareCap`. Without that record
they behave as today.

## Done when
- [x] A districted build (a fortress District, then a cave District, Decor on): the room view of
      every room and corridor returns the same Props as the build placed. → verify:
      `python -m pytest tests/test_district_decor.py tests/test_room_view.py -q` (needs
      `EQ_PATH='F:\everquest_rof2'`)
- [x] `scripts/stage.py decor` on that build's hand-off equals the build. Same command.
- [x] The byte check passes.

## Pitfalls
- Old sidecars have no `decor.districts`, so the room view reads them as one District.
- Another agent's sweeps and full suite may be running: use `-n 2` and no full suite.

## Result
✔ 3f1eaf6 · 159 passed
