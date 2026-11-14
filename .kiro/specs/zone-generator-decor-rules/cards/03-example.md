# 3 — The tomb layer, the guide and the tools

Index entry: `tasks.md` task 3. Requirement 3. Design "The worked example"; decision 3.

## Goal
Move the tomb theme's decor out of `rules/decor/rooms.toml` into `rules/decor/layers/tomb.toml` (its `[weights.themes.tomb]` and the recipes only tomb rooms reach: find them with `coverage` over the room types the tomb theme's rooms take), map `tomb = { layers = ["tomb"] }` in `rules/decor/themes.toml`, and prove a tomb build loads the same `DecorRules` as before and builds the same bytes. Write `docs/DECOR_RULES.md`, the authoring guide (mirroring `docs/TOPOLOGY_RULES.md`): the sections and fields, lookup and Weights blending, layers and `mode`, the tomb layer as the worked example, how to try a layer on a build (`--decor-layer`, the page's Decor rules control), the traps, the commands. Extend `scripts/topology_rules.py`: `check rules/decor` checks each layer and each mapped theme's merged set; `draw-decor` takes a repeatable `--layer`.

## Done when
- [ ] Base + tomb equals the pre-step rules for a tomb room (a test), and a tomb build is byte-identical (a decor golden with Theme Tomb; add one if none exists, captured BEFORE moving anything). → verify: `python -m pytest tests/test_decor_layers.py tests/test_decor_builds.py -q`
- [ ] `python scripts/topology_rules.py check rules/decor` passes and names the tomb layer; `python scripts/topology_rules.py draw-decor --layer tomb` runs. Quote both outputs' first lines in the commit body.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
A recipe a tomb room reaches that other themes' rooms also reach must stay in the base (use `coverage` across every theme, not just tomb). Lessons-learned "Environment": write commit messages to your own `.commitmsg-<n>.txt`.

## Result
