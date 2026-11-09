# 4 — Prop textures

Index entry: `tasks.md` task 4. Requirements 4.

## Goal
Procedural wood, rough timber, iron, cloth, hide, bone, stone, ceramic and flame at the measured texel density, grouped into Material_Sets by race and theme.

## Done when
- [ ] Every material decodes at its size and density; every set names only materials that exist.
      → verify: `python -m pytest tests/test_prop_textures.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Follow `generators/textures/sites.py`; reuse its materials where they're the same (timber, hide, stone).

## Result

