# 8 — Density control: prompt, CLI, server

Index entry: `tasks.md` task 8. Design: "Density control". Requirements
3.1–3.3.

## Goal
`trees` (none/sparse/normal/dense) reaches `spec.wilderness` from the prompt,
`--trees` and `controls.trees`, the way `edges` does, with its source recorded.

## Done when
- [ ] The prompt words in Req 3.2 map to their levels; controls beat the CLI
      beats the prompt beats the default.
- [ ] `trees` on a non-wilderness zone type or with a bad value: server 400
      naming `trees` before any write; CLI exit 2.
- [ ] The sidecar records the level and its source.
      → verify: `python -m pytest tests/test_wilderness_trees_controls.py -q`.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- Mirror `_require_edges` and `--edges`; `main.py` is a cross-branch hotspot.
- No Zone_Plan schema change (design Decision 3).

## Result
