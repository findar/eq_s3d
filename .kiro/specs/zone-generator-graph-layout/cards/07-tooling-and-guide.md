# 7 — Check, dry-run and draw; the authoring guide

Index entry: `tasks.md` task 7. Requirements 3.4–3.6. Design "The dry run, the diagrams and the guide".

## Goal
`scripts/topology_rules.py` with `check`, `dry-run` and `draw`; `generators/topology/draw.py` (the SVG drawing, shared with a built zone's graph); `docs/TOPOLOGY_RULES.md`, the authoring guide with the shipped sets as worked examples.

## Done when
- [ ] `check` passes on the shipped files and exits 1 with the report on a broken copy.
      → verify: `python scripts/topology_rules.py check`
- [ ] `dry-run` reports stage completion, rule counts (and rules that never fired), shape measures and the Size_Class mix.
      → verify: `python scripts/topology_rules.py dry-run classic_eq --graphs 50 --rooms 5-20`
- [ ] `draw` writes one page per set with a before → after diagram per rule (kinds, sizes, edges, relation arrows, reattachment), opened and looked at in the browser pane.
      → verify: `python scripts/topology_rules.py draw classic_eq --out output/rules/`
- [ ] The guide walks the format field by field and the check → dry-run → draw loop.

## Pitfalls
- Keep the script thin: loading and checking are `ruleset.py`'s, growing is `rewrite.py`'s.
- The guide must cover the traps task 5 hit (its commit `cf08918` and `archive.md` "Follow-ups"): the rest stage needs growth rules that work from finished rooms (an Area can be boxed in), edge-only rules spend no budget, and sizes on kept nodes are ignored.

## Result
