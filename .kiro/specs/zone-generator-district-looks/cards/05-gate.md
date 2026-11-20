# 5 — Gate and bands

Index entry: `tasks.md` task 5. Requirement 5. Design "Gate and bands".

## Goal
Districted dungeons that have a cave District and a built one, in both orders, pass the
traversability gate on both layouts. Their quality fail share stays inside today's bands.

## Done when
- [ ] `scripts/sweep_themed_navigability.py` passes every build in the sweep, and the commit body
      gives the counts. The sweep covers:
      - districted builds on both layouts;
      - 8–30 rooms, each verticality;
      - Purposes pinned with the cave District first, then second.
- [ ] At least 200 districted Draws per layout, with the fail share per key in the commit body.
      Above ~5% on a key is a bug to find, or else an `archive.md` decision.
      → verify: `python -m pytest tests/test_quality.py -q`
- [ ] The full suite `python -m pytest tests/ -q` is green, run once with nothing else running.

## Pitfalls
- A gate failure is a geometry bug: fix it at its root. If the fix is outside `Owns`, stop and
  report.
- Keep sweep CSVs in `output/`.

## Result
