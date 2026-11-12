# 6 — The stages in the build; hand-offs saved

Index entry: `tasks.md` task 6. Requirements 3.3, 5.1, 5.2, 6.3. Design "Where the stages run", question 6.

## Goal
`ZoneBuilder.build` runs through `generators/stages.py`: the World from the spec, the Entrance's edit applied, the TER made once, the ground Socket attached, then trees, RoomContexts, decor and pack as today. `BuildResult` carries the World, the Attachments and the RoomContexts the build made. The pipeline's post-pass writes `<name>.world.json`, `<name>.attach.json` and `<name>.rooms.json` into the accepted build's directory (scratch attempts keep none). The sidecar gains a `sockets` block (each Socket's id, kind, point, side, and what attached). Bytes unchanged.

## Done when
- [ ] P9: every zone type's build directory holds the three files; each stage rerun from its hand-off gives the same text; a file of another version is refused, named.
      → verify: `python -m pytest tests/test_handoffs.py -q`
- [ ] Bytes unchanged; decor and Site builds pass.
      → verify: `python -m pytest tests/test_layout_engine.py tests/test_decor_builds.py tests/test_site_builds.py -q`
- [ ] Build time up by at most 0.2 s a zone type, from `python scripts/stage_timings.py --seeds 1-5`, in the commit body.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
`pipeline.py` and `builder.py` are cross-branch hotspots: small edits. Every write goes through the `OutputRoot` (umbrella Req 31, confinement). `decor_for` already builds the contexts: hand them on, don't build them twice; with Decor `none` none are built, and `rooms.json` holds an empty list rather than costing a Decor-none build half a second. Hand-off files aren't page downloads (question 6): leave `_build_artifacts` alone.

## Result
