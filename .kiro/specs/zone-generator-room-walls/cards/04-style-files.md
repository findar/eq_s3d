# 4 — Style files and their tooling

Index entry: `tasks.md` task 4. Requirements 5.

## Goal
`rules/walls/{built,hewn,rough}.toml` and a strict loader in step 6's checker manner. `check` covers them; `draw` writes each style's sample Outlines; the guide explains them.

## Done when
- [ ] W10: every bad value (unknown key, wrong type, a shape that doesn't exist, a band out of order) fails, naming file, field and expected.
      → verify: `python -m pytest tests/test_wall_styles.py -q`
- [ ] `python scripts/topology_rules.py check` prints `ok` for each style file.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Parameters come from task 1's bands, not the design's examples.

## Result
