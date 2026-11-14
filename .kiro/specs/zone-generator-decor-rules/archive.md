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
