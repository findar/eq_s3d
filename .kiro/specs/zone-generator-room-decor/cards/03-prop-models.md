# 3 — Prop models

Index entry: `tasks.md` task 3. Requirements 3.

## Goal
The v1 Prop_Kinds of the design's "Props" table as generated models: stock triangle counts and sizes (finding 1), closed and outward-wound where solid, `FLAG_PASSABLE` where a player walks over or under, origin at the Mount point, front facing +X at yaw 0, at least one variant each.

## Done when
- [ ] P3: every kind and variant is closed where solid, round-trips through `.mod` exactly, and has its origin at its Mount.
      → verify: `python -m pytest tests/test_prop_models.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Follow `generators/sites/models.py` (step 10 decision 9: solids closed, wound outward; the gate reads inside from the first triangle above). Silhouette over detail (design Risks).

## Result

