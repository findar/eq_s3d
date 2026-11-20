# 1 — Stock tunnel survey

Index entry: `tasks.md` task 1. Requirement 1. Design "Survey".

## Goal
Measure how stock cave tunnels wind, so `[tunnel]` in `rough.toml` holds measured numbers (A3).

## Done when
- [x] `python scripts/tunnel_survey.py` (with `EQ_PATH='F:\everquest_rof2'`) runs over at least
      five stock cave zones and prints, for each tunnel and pooled, the median and p10–p90 of:
      - segment length;
      - turn angle;
      - wander as a share of span;
      - width.
- [x] `archive.md` "Decisions" records the pooled numbers and the proposed `[tunnel]` values
      (`segment`, `max_turn`, `wander`, `end`) in two or three lines. The full table goes in the
      commit body.
- [x] `python -m pytest tests/test_tunnel_survey.py -q` passes: the centreline extraction on a
      synthetic bent tunnel recovers its angles.

## Pitfalls
- Read the zones the way `scripts/wall_survey.py` does (it splits chambers with `scripts/dungeon_topology_survey.py`).
- A tunnel is a narrow floor run between wider chambers; say in the commit body how you told
  them apart.

## Result
✔ f4baf04 · 2860 passed
