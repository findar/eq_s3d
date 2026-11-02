# 6 — Outdoor-dungeon backend and gate

Index entry: `tasks.md` task 6. Requirements 5, 7.1, 8.2.

## Goal
A backend builds the merged TER (terrain + dungeon), materials from the wilderness kit and step 4 recipes, and the gate checks reachability from the Outdoor_Spawn plus the bowl and trunk checks.

## Done when
- [ ] D4: on a sample of seeds every room is reachable from the Outdoor_Spawn through an Entrance; corridors continuous.
- [ ] D6: same inputs, same `.eqg` contents (footer aside).
- [ ] D7: dungeon, city and wilderness builds unchanged.
- [ ] A failing build is retried with a fresh seed.
      → verify: `python -m pytest tests/test_outdoor_dungeon_build.py -q`.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- `generators/pipeline.py` is a cross-branch hotspot; keep the change small.
- lessons-learned: the bowl gate and trunk check already exist; compose them.

## Result
