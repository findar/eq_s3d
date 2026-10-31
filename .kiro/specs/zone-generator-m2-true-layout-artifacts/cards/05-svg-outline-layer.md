# 5 — Outline layer in the map SVG

Index entry: `tasks.md` task 5. Design: "Map viewer outline layer", Decisions
10–11. Requirement 7.

## Goal
`render_map_svg` takes an optional outline and draws it under every schematic
annotation: walls solid, ledges dashed, corridors along their routes, lighter
room fills. With no outline its output is byte-for-byte unchanged.

## Done when
- [ ] `tests/reference_mapview.py` is a frozen copy of today's
      `render_map_svg` (header names the fork commit; test-only, never edited).
- [ ] Property 14: with `outline=None` the output equals the reference for any
      spec, size and padding (100 specs, no builds).
- [ ] Property 15: with an outline, the outline group comes after the background
      and before every annotation; room fill-opacity is ≤ 0.35; the legend has
      `wall` and `ledge`; corridors follow `corridor_route` waypoints.
      → verify: `python -m pytest tests/test_properties_mapview.py tests/test_generators.py -q`.
- [ ] The worker opens one SVG per test seed in a browser; anything odd goes in
      Result.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- The existing `TestMapView` tests must pass unchanged.
- Format outline coordinates `:.1f` like the rest of the file, so the SVG stays
  a pure function of its inputs (task 7's Property 17 depends on it).

## Result
