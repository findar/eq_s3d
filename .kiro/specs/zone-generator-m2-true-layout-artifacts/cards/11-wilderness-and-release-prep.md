# 11 — Wilderness coverage, acceptance section, thorough run

Index entry: `tasks.md` task 11. Design: Testing Strategy, "Human pass".
Requirement 1.7; exit criteria 1–3.

## Goal
Prove the outline and map files on wilderness builds, write the step 1b section
of the acceptance checklist, and run the thorough profile once.

## Done when
- [ ] Property 3 draws 5 wilderness builds, and Property 13 includes wilderness
      builds (`slow`). Record the extraction time for one wilderness build.
      → verify: `python -m pytest tests/test_properties_mapgeom.py tests/test_eqmap.py -q`.
- [ ] `docs/ACCEPTANCE.md` gains "Step 1b — True-layout map", built from the
      design's human-pass table: walls match on seeds 1955208177, 1516796975,
      678358326 and one flat seed, plus one wilderness seed; annotations stay
      readable; downloads are named `<name>.*`; the task 10 overlay lands on the
      walls.
- [ ] `python -m pytest tests/ -q` is green, and
      `python -m pytest tests/ -q --hypothesis-profile=thorough` is green once.
      Record its duration in Result.
- [ ] The frontend builds (`cd web; npx vite build`).

## Pitfalls
- A wilderness map is the border plus slope breaks over 40° (accepted, see
  `archive.md`). Don't add contours.

## Result
