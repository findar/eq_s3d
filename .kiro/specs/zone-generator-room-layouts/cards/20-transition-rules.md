# 20 — Transitions as data, in builds

Index entry: `tasks.md` task 20. Requirements 14.1, 14.4, 14.5.

## Goal
Builds choose Transitions from `rules/rooms/transitions.toml`, and record Door_Spots.

## Done when
- [ ] The file is checked strictly, and `python scripts/topology_rules.py check` covers it; chosen by pair times room type or kind (F15).
- [ ] A Frame that can't fit becomes a Seam, recorded. Every Frame has a Door_Spot in the sidecar, drawn on the map.
- [ ] `python -m pytest tests/test_transition_rules.py tests/test_features_sweep.py -q` is green, first try included.
- [ ] `python -m pytest tests/ -q` is green; the rest of the mesh is unchanged by a Transition.

## Pitfalls
Nothing goes in the binary for a door: doors are the SQL export's.

## Result
