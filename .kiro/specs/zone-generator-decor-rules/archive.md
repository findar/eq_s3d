# Archive — zone-generator-decor-rules

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

Decided 2026-11-14 by the lead on the design's recommendations, after the user agreed to the
shape proposed ("that sounds good"): decor layers like topology layers, a theme map, an
authoring guide, tooling, and the single-room view to see a layer's effect.

1. **A layer refuses clashes unless the entry says `mode = "add"` or `"replace"`** (design
   question 1).
2. **Layers come from the theme map plus `decor_layers` in the request** (question 2).
3. **Tomb is the worked example layer**, byte-identical (question 3).
4. **The room view re-decorates the build's saved RoomContexts with rules read fresh**
   (question 4), **in the page** (question 5), **rooms only** (question 6).

## Follow-ups

- **`scripts/stage.py` `decor_stage` keeps its own copy of the bare cap** and doesn't settle Props
  (import, origin, wall), so its positions differ from a build's (task 4). It could call
  `builder.BareCap` and `settle_room`.
- **The room view's first call in a fresh server process is slow** (16 s quiet, the install's
  archives read once); rerolls after it are under 1 s median (task 4).
