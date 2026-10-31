# 7 — Pipeline post-pass: map artifacts for accepted builds only

Index entry: `tasks.md` task 7. Design: "Pipeline post-pass", Decisions 8–9,
"Sidecar additions", "Output layout". Requirements 3, 8.

## Goal
Write the map SVG and `maps/<name>*.txt` only for the accepted build: after the
gates, before the move out of the scratch attempt. `ZoneBuilder.build` stops
writing the SVG. An outline or writer failure never fails the build; it leaves
a warning instead.

## Done when
- [ ] `ZoneBuilder.build` writes no `.map.svg`. The post-pass in
      `generate_validated` writes it (with the outline when there is one) and
      the EQ map files, through `OutputRoot`.
- [ ] `TraversalReport.surface` exposes the validator's walk surface (not
      serialised), and the post-pass passes it to `extract_outline`.
- [ ] Fallbacks: if the extractor raises or the floor is empty, write the
      schematic-only SVG, no `maps/`, and warning `outline_unavailable:<cause>`.
      If the writer raises, keep the outline SVG, remove `maps/`, and warn
      `eqmap_unavailable:<cause>`. Causes are sanitised (`_cause`).
      → verify: examples in `tests/test_pipeline.py`.
- [ ] The sidecar gains `map_files` and the `outline` block (Req 8.4).
- [ ] Property 16 (map artifacts exist exactly for the accepted build) and
      Property 17 (byte-identical map files for the same plan, seed and name)
      hold, marked `slow`. The CLI and server give the same map files for one
      plan, seed and name.
      → verify: `python -m pytest tests/test_properties_pipeline.py tests/test_pipeline.py -q`.
- [ ] Ungated builds (`--no-validate`) still get map artifacts.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- `generators/pipeline.py` is a cross-branch hotspot; keep edits minimal and
  merge promptly.
- `server/app.py` builds `map_url` from the zone id, so the SVG must still exist
  at that path after this task.
- If the sidecar needs a change in `core/eqg.py` (not in Owns), stop and say so.

## Result
