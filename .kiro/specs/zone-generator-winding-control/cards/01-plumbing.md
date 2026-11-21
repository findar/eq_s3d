# 1 — Winding on the plan, the spec and every reader

Index entry: `tasks.md` task 1. Requirements 1–4. Design "Data", "Scaled rules".

## Goal
`ZonePlan.winding` reaches the layout and is recorded on the ZoneSpec; the tunnel's `wander` is
scaled by it for the clearance measure (`wind`, `path`) and for every reader, so mesh, decor, map
and gate agree at any setting.

## Done when
- [x] At `winding` 0 no corridor has a `wind` or `path`; at 1 nothing changes; at 2 the largest
      stray per corridor is never smaller than at 1 on the same seed. → verify:
      `python -m pytest tests/test_winding_control.py -q`
- [x] At `winding` 2, over 5 cave graph builds, the mesh's corridor strip, the decor RoomContext
      cells and the map line agree (one test per reader, same command).
- [x] The byte check in `tasks.md` passes; a spec without `winding` loads as 1.0 and writes no key.
- [x] `python -m pytest tests/ -q -m "not slow" -n 4` is green.

## Pitfalls
- `_wind_limit` clips at `rules.wander × span`: a reader on the base rules silently clips a
  scaled leg. Grep every `tunnel_rules()` and `winding_legs(` caller.
- Follow `verticality` from plan to engine; don't add a second path.
- lessons-learned "Two `.eqg` writes are never byte-identical" (compare `bytes[:-4]`).

## Result
✔ ff88226 · 3131 passed
