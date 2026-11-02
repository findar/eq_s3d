# 3 — Texture recipe data and resolver

Index entry: `tasks.md` task 3. Design: "Recipes". Requirement 3.

## Goal
`resolve(material_name) -> (family, params, source)` maps every name a build
can produce to a Texture_Family through `styles/texture_recipes.json`.

## Done when
- [ ] Y3: every Material_Name from every archetype × tint × race, city and
      wilderness biome resolves; names with no entry fall back by Surface and
      report `source = "fallback"`.
- [ ] The same Surface under two themes with different palettes resolves to a
      different family or parameters (Req 3.2).
- [ ] A malformed recipe file fails with an error naming the field.
      → verify: `python -m pytest tests/test_texture_recipes.py -q`.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- The name list comes from code (`generators/semantics.py` archetypes, tints,
  races; `styles/biomes.json`), not a hand-written list in the test.
- Match order: exact set, then `*_<theme>`, then the Surface fallback.

## Result
