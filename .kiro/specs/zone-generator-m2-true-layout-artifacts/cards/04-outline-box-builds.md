# 4 — Outline on box builds

Index entry: `tasks.md` task 4. Design: Testing Strategy (build-level budgets),
research finding 5. Requirements 1.1–1.4, 1.7.

## Goal
Run the extractor on real dungeon and city builds, now that doorways have
walls (task 2). Add the build branches of Properties 1–3 and the
`doorway_spans(spec)` oracle, and measure extraction time and the ledge share.

## Done when
- [x] `tests/pbt_helpers.py` gains `doorway_spans(spec)`, built from
      `routing.corridor_route`.
- [x] Property 1 (the outline is a function of the TER and safe point, and
      passing the validator's surface gives the same result) holds on 15 builds,
      marked `slow`.
- [x] Properties 2 and 3 draw box builds as well as synthetic worlds (one
      `@given` per property, build branch inside the build budget): no segment
      crosses a Doorway_Span, and coverage is ≥ 99%.
      → verify: `python -m pytest tests/test_properties_mapgeom.py -q`.
- [x] Depth bands on box builds are explained, not assumed. Done: the stacked
      floors are a layout bug (Z-corridor ramps run inside room footprints,
      because rooms sit only half a corridor width apart). The fix and the
      "box builds are single-band" check moved to task 14. This task asserts no
      band count on builds.
- [x] The commit body records extraction time for a 12-room and a 30-room
      dungeon (target ≤ 1 s) and the wall/ledge share on seeds 1955208177,
      1516796975 and 678358326.
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
- A property failure on a build is a real geometry or extractor bug; fix it at
  the root. Don't draw around the mesh (design Overview).
- If ledges are still common after task 2, report the share and where it comes
  from. Don't widen this task into `geometry.py`.

## Result
✔ 20536a9 · 549 passed (3 skipped)
