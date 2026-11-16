# Archive — zone-generator-decor-rules

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

| Tasks | What landed | Commits |
|---|---|---|
| 1–2 | Decor layers in the loader (`load_decor(..., layers)`, `layer_names`, `layers_for`, `mode` add/replace, clashes refused) and through the build: `ZonePlan.decor_layers`, `--decor-layer`, `controls.decor_layers`, `/api/controls` `decor_layers`, sidecar `decor.layers`; no layer, same bytes | `f37d4a6` … `6610254` |
| 3 | `layers/tomb.toml` (the tomb's Weights; tomb builds byte-identical, TOMB golden), `themes.toml`, `docs/DECOR_RULES.md`, `topology_rules.py check` and `draw-decor --layer` | `5f97273` … `7d807b5` |
| 4 | `generators/decor/room_view.py` and `POST /api/room_decor`: one room re-decorated from the saved RoomContexts, rules read fresh; `builder.BareCap` and `settle_room` shared with the build | `2f01c97` … `ee563e3` |
| 5–6 | The Decor rules control, and the Room view in the page (Props by recipe line, POIs, drops, two-way hover, reroll, Decor, Decor rules, re-read rules, cutaway) | `4a5c1c1` … `6a20f77` |
| 7–9 | First look, acceptance section (`docs/ACCEPTANCE.md` R.1–R.5) and thorough run, acceptance; at acceptance the 3D view's size (a step 14 regression) and the map dialog's size were fixed | `b21a901` … `f48fcc6` |

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

5. **A layer has its own Weights, `[weights.layer]`** (2026-11-15, after the close, user: "Yes,
   fix it"). Every room and corridor of a build that takes the layer gets them, after the theme's
   entry in the blend; Sites keep their biome's look. The tomb layer holds its look there, so
   Decor rules "tomb" darkens any build; tomb builds stay byte-identical.

## Follow-ups

- **`scripts/stage.py` `decor_stage` keeps its own copy of the bare cap** and doesn't settle Props
  (import, origin, wall), so its positions differ from a build's (task 4). It could call
  `builder.BareCap` and `settle_room`.
- ~~**The tomb layer does nothing outside a tomb**~~ (found at task 8): fixed after the close by
  decision 5 (a layer's own `[weights.layer]`).
- **A pre-existing thorough failure in room placement** (task 8):
  `test_room_placement.py::test_f4_placement_keeps_the_way_clear_and_never_fails` with w=112,
  d=118, voronoi, seed 33757, one E door, a far-end boss dais: "doors joined, no pocket". Same on
  `74991ef`, before step 15.
- **The room view's first call in a fresh server process is slow** (16 s quiet, the install's
  archives read once); rerolls after it are under 1 s median (task 4).
