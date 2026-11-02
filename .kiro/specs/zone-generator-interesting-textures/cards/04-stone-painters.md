# 4 — Painters: stone families

Index entry: `tasks.md` task 4. Design: "Painters". Requirement 4.

## Goal
Shared building blocks (tileable noise and Voronoi, ashlar and running-bond
layouts, per-cell palette jitter, a crc32 seed) and the stone families:
`dressed_stone`, `brick`, `flagstone`, `cobble`, `cave_rock`.

## Done when
- [x] Each family paints a 256×256 RGB image with its structure (blocks and
      joints, slabs, cells, strata), seamless across the wrap, pure across
      processes, distinct from the other families.
- [x] Edge energy is at least 0.02 for every stone family at a mid-grey base
      colour (the research floor; ours is 0.007 today).
- [x] Rendered samples looked at by the worker; the commit body says what was
      seen.
      → verify: `python -m pytest tests/test_painters.py -q`.
- [x] `python -m pytest tests/ -q` is green.

## Pitfalls
- Never `hash()`; seed from `zlib.crc32` of the name.
- Keep it vectorised numpy (lessons-learned "opensimplex was the bottleneck").

## Result
✔ 837c852 · 763 passed
