# 5 — Gate and bands

Index entry: `tasks.md` task 5. Requirement 5. Design "Gate and bands".

## Goal
Rough-walled dungeons with winding tunnels pass the traversability gate, and their quality fail
share stays inside today's bands.

## Done when
- [ ] `scripts/sweep_themed_navigability.py` over cave and warren dungeons passes every build,
      with the counts in the commit body. It covers both layouts, 2–30 rooms, and each
      verticality.
- [ ] At least 200 Draws per layout, with the fail share per key in the commit body. A key above
      ~5% is a bug to find, or else an `archive.md` decision. → verify:
      `python -m pytest tests/test_quality.py -q`
- [ ] The full suite `python -m pytest tests/ -q` is green, run once with nothing else running.

## Pitfalls
- A gate failure is a geometry bug: fix it at its root, named in the commit.
- Keep sweep CSVs in `output/`.

## Result
