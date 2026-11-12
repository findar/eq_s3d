# 14 — Corridor RoomContexts (only if question 7 is yes)

Index entry: `tasks.md` task 14. Requirement 8. Design question 7; step 11's follow-up "Corridor lights".

## Goal
`room_context.contexts` also returns one RoomContext per corridor (`source = "corridor"`): its floor and ceiling on the plan grid, wall faces from the mesh, both doorways as doors with their clear zones, and its way through kept clear like a Spine, so step 11's placement lights corridors as it already can. Decor `none` is unchanged. Decor-on goldens, the room corpus and the P12 bands are recaptured once, in this task's commits.

## Done when
- [ ] Corridor contexts round-trip; the room corpus is re-recorded and its contract passes.
      → verify: `python -m pytest tests/test_room_context.py -q` and `python -m pytest tests/test_room_context.py -q -m slow`
- [ ] Decor builds pass the gate with corridor Props; Decor `none` bytes unchanged.
      → verify: `python -m pytest tests/test_decor_builds.py tests/test_layout_engine.py -q`
- [ ] The P12 bands still hold.
      → verify: `EQ_PATH='F:\everquest_rof2' python -m pytest tests/test_decor_bands.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Stairs and Bridges are corridors: a Bridge's deck has railings and a shaft beneath, and a Staircase's floor isn't flat. Read them as the gate does, or leave them out and say so. Lights in a corridor go on its walls, clear of its whole width.

## Result
