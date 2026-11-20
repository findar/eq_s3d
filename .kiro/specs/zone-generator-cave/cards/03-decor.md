# 3 — The decor layer

Index entry: `tasks.md` task 3. Requirements 2.4, 2.5. Design "Rule files" (Decor).

## Goal
`rules/decor/layers/cave.toml` and `cave = { layers = ["cave"] }` in `rules/decor/themes.toml`:
crystal models in `crystal_grotto` and `cavern`, rock and fungus where the catalogue has them,
nothing built.

## Done when
- [ ] The layer validates and a `cave` build's decor uses crystal models in its climax and no
      furniture tag anywhere. → verify: `python -m pytest tests/test_decor_rules.py -q`
- [ ] Look at 3 `cave` builds' room views with Decor Normal; say what you saw in the commit body.
- [ ] The byte check passes; `python -m pytest tests/ -q` is green.

## Pitfalls
Models come only from `rules/decor/catalogue.json` (client art is never committed). The guide is
`docs/DECOR_RULES.md`; `layers/tomb.toml` is the worked example.

## Result
