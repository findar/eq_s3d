# 2 — Versions of one zone

Index entry: `tasks.md` task 2. Requirements 1, 2.1, 2.2 (the full path). Design "Versions",
"Rebuild" (steps 1–3, full path only); decision 1.

## Goal
Every build saves `<name>.request.json` (the request as the Server resolved it, seeds resolved)
and `<name>.spec.json` (`ZoneSpec.save` plus the decor layers) with its other files. `POST
/api/rebuild {zone, version, decor_seed?, rooms_seed?}` reads the parent's request, applies the
change and builds `v<n+1>` of the same zone through the existing Generate path (a full rebuild
for now, for both seeds; task 3 makes the decor one partial). The new version's sidecar has
`version: {n, parent, changed, how: "full"}`; v1 has none. `GET /api/zones/<zone>/versions`
lists the versions (n, parent, changed, how, created, took_ms). Version numbers can't collide
when two rebuilds of one zone run at once.

## Done when
- [ ] A v1 build is unchanged but for the two saved files. → verify: `python -m pytest tests/test_layout_engine.py tests/test_site_builds.py tests/test_decor_builds.py tests/test_site_decor_builds.py -q`
- [ ] A rebuild with a new decor seed or rooms seed writes `v2` of the same zone whose `.eqg` equals a Generate of the same request with that seed (footer aside); `/versions` lists v1 and v2; an unknown zone, version or a body naming no change answers 404/400, never a path outside the output root; two rebuilds at once get two numbers. → verify: `python -m pytest tests/test_versions.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Lessons-learned: `fullmatch` for path segments; `Path.resolve` and the `\\?\` prefix (go through
`core/paths`). A failed rebuild leaves no `v<n+1>` folder (the pipeline's scratch rules). A
prompt-mode request must rebuild without calling the planner again: save the plan it produced
and rebuild from that.

## Result
✔ 3eb99c9 · 3205 passed
