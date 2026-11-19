# 1 — The quality meter

Index entry: `tasks.md` task 1. Requirement 1. Design "Meter".

## Goal
`generators/quality.py`: `measure`, `bands_for`, `spec_key`, `quality_summary`, the report
dataclasses, and a band table that is all unbounded until task 2 fills it.

## Done when
- [ ] Each metric matches a hand-worked spec (a line, a loop, a star, a two-Level graph, a room
      with an Outline). → verify: `python -m pytest tests/test_quality.py -q`
- [ ] Hypothesis properties: umbrella 24.2 (repeat, JSON round-trip, advisory fields and Gates
      don't matter) and 24.3 (pass ⇔ all in band; Out_Of_Band_List exact; score 0 ⇔ pass,
      strictly increasing as one value moves away). Same command.
- [ ] 24.4's unbounded cases. Same command.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Read the layout and verticality from wherever the spec records them; if it doesn't, `spec_key`
takes them as arguments and say so in the commit body (task 3 passes them from the plan). Don't
build anything in tests: specs only.

## Result
✔ d21a5ff · 3537 passed
