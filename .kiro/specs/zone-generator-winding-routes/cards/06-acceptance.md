# 6 — Acceptance section

Index entry: `tasks.md` task 6.

## Goal
`docs/ACCEPTANCE.md` "Step 25 — Winding routes": a cave's routes in 3D and on the map, a ramp
route between Levels, a stair and a bridge still square, a warren, and a built fortress unchanged.

## Done when
- [x] The section is written, and every case was run with its seed on agent servers (8020–8050
      only).
- [x] Thorough run `python -m pytest tests/ -q --hypothesis-profile=thorough`, failures named in
      the commit body.

## Result
✔ 7b80745 · 4040 passed thorough, 1 stale-HEAD flake passed alone
