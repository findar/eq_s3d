# 1 — Decor layers in the loader

Index entry: `tasks.md` task 1. Requirements 1 and 2.1. Design "Decor layers"; decision 1.

## Goal
`load_decor(path, tags, layers=())` reads `rules/decor/layers/<name>.toml` files (a `[layer]` table with `name` matching the file and `description`, plus any of the base's sections) and merges them onto the base's raw tables in order before today's parse: new keys are added; an existing recipe, Group, Dressing or weights entry is refused naming both files, unless the layer entry says `mode = "add"` (lines appended; weights Categories added, clashing Categories refused) or `mode = "replace"`. Each layer file is checked on its own, and the merged set as a whole, every failure named by file, entry and field (`RuleSetError`). Add `layer_names(path)` (name -> description, from the folder) and `layers_for(theme, race, extra)` reading `rules/decor/themes.toml` (theme map, optional `[races]`; ship it with no mappings yet). With no layers, the result is today's `DecorRules`, equal field for field.

## Done when
- [ ] Merge, clash refusal, `mode = "add"`/`"replace"`, a bad layer file's errors named by file, and the merged-set check are tested on small layer files written in `tmp_path`. → verify: `python -m pytest tests/test_decor_layers.py tests/test_decor_rules.py -q`
- [ ] `load_decor()` with no layers equals the pre-task `DecorRules` (a test), and bytes stay. → verify: `python -m pytest tests/test_layout_engine.py tests/test_site_builds.py tests/test_decor_builds.py tests/test_site_decor_builds.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Mirror `generators/topology/ruleset.py`'s layer merge and error wording, don't import its private merge if it doesn't fit. Keep `DecorRules` the one type callers read. Record the merge order (theme, race, request) in the docstring.

## Result
