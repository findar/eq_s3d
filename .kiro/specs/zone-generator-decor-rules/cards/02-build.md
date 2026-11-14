# 2 — Layers through the build

Index entry: `tasks.md` task 2. Requirements 2.2–2.5. Design "Through the build", "Caching"; decision 2.

## Goal
`ZonePlan.decor_layers` (a tuple of names, validated against the folder; unknown → an error naming the known ones), the CLI's repeatable `--decor-layer`, the server's `controls.decor_layers` (400 on an unknown name), `/api/controls` listing `decor_layers: [{name, description}]` read from the folder, the builder loading the theme map's layers plus the plan's (`_decor_data()` cached per tuple of layer names), and the sidecar's `decor.layers` recording what was used. Only Decor reads it: the World and rooms stages don't see it.

## Done when
- [ ] A build naming a test layer (written into a temporary rules folder, or a fixture layer under `tests/fixtures/`) gets its Props; the same build with no layer is byte-identical to before; an unknown name is refused on the CLI and with a 400 that names the known ones; `/api/controls` lists the folder's layers. → verify: `python -m pytest tests/test_decor_layers_build.py -q`
- [ ] Bytes stay. → verify: `python -m pytest tests/test_layout_engine.py tests/test_site_builds.py tests/test_decor_builds.py tests/test_site_decor_builds.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
`generators/pipeline.py` and `main.py` are cross-branch hotspots (steering "Parallel agents"): keep edits minimal. A plan field that reaches a Zone_Spec hash breaks every golden: keep `decor_layers` out of the spec, as `decor` and `decor_seed` are. If the sidecar gains `decor.layers` only when non-empty, older readers stay happy; check `web/src/api.ts` doesn't need it yet (task 5 types it).

## Result
✔ f37d4a6 · 3155 passed
