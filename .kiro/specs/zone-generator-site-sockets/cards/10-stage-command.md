# 10 — The stage command on version 2

Index entry: `tasks.md` task 10. Requirement 6.5. Design "Hand-offs".

## Goal
`scripts/stage.py world` writes a v2 World and marks each point Socket in its GLB (a small post per point); `attach` reads v2 and attaches Sites to the points; both refuse v1 files with the reader's message. Each prints its time.

## Done when
- [ ] `world` then `attach` on a wilderness give the files a full build writes for the same seeds.
      → verify: `python -m pytest tests/test_stage_script.py -q`
- [ ] Seconds, not a build.
      → verify: `python scripts/stage.py world sw --zone-type wilderness --seed 1000 --out output/stage` then `python scripts/stage.py attach output/stage/sw.world.json --rooms-seed 9 --out output/stage`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Write under `output/` through the `OutputRoot`, as builds do. The post marking a point is a marker, not a Site model.

## Result
