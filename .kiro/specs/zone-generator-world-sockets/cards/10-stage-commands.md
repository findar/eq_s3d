# 10 — Stage commands

Index entry: `tasks.md` task 10. Requirement 5.4. Design "Testing in isolation", question 6.

## Goal
`scripts/stage.py` runs one stage from the previous stage's hand-off file and writes its own, with a GLB of that stage alone: `world` (zone type, World inputs and a seed -> `<name>.world.json` and the terrain with its Sockets marked), `attach` (a World file, plan fields and a rooms seed -> `<name>.attach.json` and the attached rooms or Sites alone), `rooms` (World and Attachments -> the TER and `<name>.rooms.json`), and `decor` (a rooms file -> the decorated rooms, as `scripts/decor_room.py` does for one). Each prints its time.

## Done when
- [ ] Each command runs from the previous one's output, and its file equals what a full build writes for the same seeds.
      → verify: `python -m pytest tests/test_stage_script.py -q`
- [ ] `world` then `attach` on an outdoor dungeon take seconds, not a build.
      → verify: `python scripts/stage.py world sw --zone-type outdoor_dungeon --seed 3 --out output/stage` then `python scripts/stage.py attach output/stage/sw.world.json --rooms-seed 9 --out output/stage`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Write under `output/` through the `OutputRoot`, as builds do. The `attach` GLB of rooms alone is the box mesh of the layout, not the merged outdoor TER.

## Result
