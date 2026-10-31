# 1 — EQ map core: convention, grounding, format, parse

Index entry: `tasks.md` task 1. Design: "EQ map writer and parser",
"Grounding_Check", research findings 1–2. Requirements 4, 5.2, 6.

## Goal
Add `generators/eqmap.py` with everything that doesn't need an outline: the
pinned map coordinate convention, the Grounding_Check that proves it against
stock RoF2 zones, the record formatter, the parser and `write_map_files`.
Task 6 adds `build_map_file` (outline → layers) on top.

## Done when
- [ ] `world_to_map` / `map_to_world` are the pinned candidate (negate + swap,
      `(mx, my) = (−y, −x)`), Z unchanged, and round-trip every finite point.
      → verify: `python -m pytest tests/test_eqmap.py -q -k convention` (Property 8).
- [ ] The Grounding_Check picks the pinned candidate on `tutoriala` with median
      ≤ 5 u and best/runner-up ≤ 0.25, and leaves the install untouched
      (snapshot names, sizes, mtimes before and after). `bazaar` runs the same
      check under `@pytest.mark.slow`. Both skip when `EQ_PATH` is unset
      (`core.env.env_value`) or the zone's files are missing.
      → verify: `python -m pytest tests/test_eqmap.py -q -k grounding`; record the medians in the commit body.
- [ ] Property 9: the Grounding_Check recovers a known candidate on
      `asymmetric_wall_meshes()`.
      → verify: `python -m pytest tests/test_eqmap.py -q -k grounding_recovers`.
- [ ] Format round-trip (Property 10) and parser tolerance (Property 11) hold;
      every stock `maps/*.txt` parses with zero skipped lines (slow, skips
      without the install).
      → verify: `python -m pytest tests/test_eqmap.py -q`.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- Keep this task's strategies (`map_layers`, `garbage_lines`,
  `asymmetric_wall_meshes`) inside `tests/test_eqmap.py`. `tests/strategies.py`
  belongs to task 3, and keeping them apart lets tasks 1 and 3 run in parallel.
- The install is read-only (Req 4.6). `core/paths` refuses writes there, but the
  test must prove nothing changed, not just that nothing raised.
- The design measured the convention at `5dabd21`. Re-run it; don't copy the
  numbers.

## Result
