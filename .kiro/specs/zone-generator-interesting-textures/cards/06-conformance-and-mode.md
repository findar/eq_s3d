# 6 — Conformance and the recipe texture mode

Index entry: `tasks.md` task 6. Design: "Conformance", "Overview" step 5.
Requirements 4.4, 5, 7.

## Goal
`procedural` mode draws every surface through its recipe and painter and is the
default; placeholders and AI stay selectable; the sidecar texture list gains
each texture's family and Look_Stats; the salted-`hash()` seed is gone.

## Done when
- [ ] Y5: for every family × the dungeon, city and outdoor profiles × sample
      colours, Look_Stats lie in the p10–p90 band except the recipe's listed
      exceptions.
- [ ] With no override, builds draw recipe textures; `placeholder` and `ai`
      work by override; the texture list records family and Look_Stats.
- [ ] Procedural textures are byte-identical across processes (fresh-process
      test, different `PYTHONHASHSEED`).
- [ ] Tree textures follow Open question 4's answer.
      → verify: `python -m pytest tests/test_texture_conformance.py -q`.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- Step 3's tests assert placeholders are the default; update them only with
  the user's OK (they're outside `Owns`).

## Result
