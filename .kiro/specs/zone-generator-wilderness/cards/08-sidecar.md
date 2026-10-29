# 8 — Wilderness advisory data in the `.zone.json` sidecar

Index entry: `tasks.md` task 8. Old tasks 12.6 and 12.7. Requirements 1.4, 3.7,
10.2, 14.4.

## Goal
The bowl assembly already collects everything a human finishing pass (and
the future SQL export) needs: which edge is which, where the invisible walls
are, which regions are damaging lava, and which regions are playable or
scenic. None of it reaches the sidecar yet. Write it there. It must never go
into the binary.

## Done when
- [x] A wilderness build's `.zone.json` contains:
      - `biome`, plus `biome_substitution` (`requested` / `resolved`) when a fallback fired
      - `edge_connections` (side → type)
      - `invisible_walls` (`{min_xy, max_xy, kind: "invisible_wall"}`)
      - `lava` regions with `damaging: true`
      - per-region `intent` (`playable` / `scenic`)
      - `poi_anchors`, including Spawn
      → verify: an example test in `tests/test_wilderness_sidecar.py` (example-based, not PBT).
- [x] Dungeon and city sidecars are unchanged (no new empty keys).
      → verify: the existing sidecar tests are still green.
- [x] `python -m pytest tests/ -q` is green.

## Hints
- The source data is on `BowlResult.edges` / `.barriers` (`generators/wilderness/bowl.py`)
  and `WildernessIntent.sidecar_record()` (`biome_resolve.py`).
- The writer is `write_sidecar` in `core/eqg.py`, and the builder calls it in
  `generators/builder.py`.

## Result
✔ branch `claude/wild-8-sidecar-09881f` · 498 passed · keys `biome`/`biome_substitution`/`edge_connections`/`invisible_walls`/`lava`/`region_intent`/`poi_anchors`, built in `ZoneBuilder._wilderness_sidecar`. Owns widened to `ai/expand.py` (keeps the substitution on `spec.wilderness`).
