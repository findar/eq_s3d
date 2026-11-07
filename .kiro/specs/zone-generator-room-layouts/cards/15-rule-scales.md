# 15 — Rules set Weights

Index entry: `tasks.md` task 15. Requirements 11.3, 11.5.

## Goal
A topology rule can set Weights on the rooms it makes, inherited by what they grow into, which is how a wing gets a hard edge.

## Done when
- [x] Rule files accept `scales` on a node, checked strictly; `generators/topology/ruleset.py` names every bad value.
- [x] Inherited through rewriting; no lean across different rule Weights (F12).
- [x] `rules/topology/classic_eq.toml` grows wings with a hard edge, as chardok has (design finding 3), and a mine wing on a temple; `python scripts/topology_rules.py check` passes.
- [x] Built zones are inside task 12's band: `python -m pytest tests/test_room_scales.py -q`.

## Pitfalls
Follow how `rule_shape` rides from a rule to a room.

## Result
✔ ddfc948 · 1853 passed
