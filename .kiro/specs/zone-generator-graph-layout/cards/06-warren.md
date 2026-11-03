# 6 — Base set warren

Index entry: `tasks.md` task 6. Requirements 5.1, 5.2.

## Goal
`rules/topology/warren.toml`, a second base set written only as data (no code change), tuned to the warren-like zones' bands, and the `warren` theme pointed at it in `themes.toml`.

## Done when
- [ ] The file loads and passes every check, commented as an example.
- [ ] G6: `warren`'s measures fall in the warren-like bands, and differ from `classic_eq`'s in the direction finding 5 states.
      → verify: `python -m pytest tests/test_ruleset_warren.py -q`
- [ ] No file outside `Owns` changed: if the warren needs code, stop and say what (that's the extensibility test failing, and worth knowing).

## Pitfalls

## Result
