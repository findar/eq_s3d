# 3 — Rule-set format, loader and checks

Index entry: `tasks.md` task 3. Requirements 3.1–3.3. Design "Rule-set files", "The vocabulary".

## Goal
`TopologyGraph` (nodes with kind, size, shape, district; edges with relation and tags; the shape measures) and `ruleset.py`: load base sets, layers and the theme map from TOML, merge a base with its layers, and run every check, collecting every failure as `file › rule or stage › field: found, expected`.

## Done when
- [ ] `TopologyGraph` measures dead-end share, cycle rank, deep-end distance and the Size_Class mix (the survey's definitions).
- [ ] Every check in the design's vocabulary has a test with a minimal bad file, asserting the message names the file, rule or stage, and field (G2).
- [ ] A file with several problems reports all of them, not the first; a failing set raises with the whole report.
      → verify: `python -m pytest tests/test_topology_ruleset.py -q`

## Pitfalls
- Test files live in `tmp_path`; the shipped sets come in tasks 5 and 6.
- Messages are for a model as much as a person: say what was expected, with the allowed values.

## Result
