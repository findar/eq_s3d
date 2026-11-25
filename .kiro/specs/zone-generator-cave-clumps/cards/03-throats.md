# 3 — Throats and clumps

Index entry: `tasks.md` task 3. Requirements 2–4, design "Throats" and "Clumps".

## Goal
Cave rooms open straight into each other on about 0.3 of edges and clump as stock caves do.

## Done when
- [ ] `python scripts/grid_score.py --shapes --kinds cave` over seeds 2000–2039 and on
      731402518: throat share 0.20–0.35, nn min ≤ 1.0 median side, nn CV ≥ 0.30, axis share
      ≤ 0.35, entry p50 ≥ 15°, grid ≤ 0.10. Before/after in the commit body.
- [ ] Graph, Levels and stairs unchanged; no throat on a stair, Bridge or between floors.
- [ ] 30-room cave draw median ≤ 14 s (task 1's script).
- [ ] Req 6 byte check green; a fortress and an outdoor dungeon compared by archive entry:
      identical.
- [ ] Quick tier while working; `-m gate` and the full suite alone green at close.

## Pitfalls
- Task 2's decision sets the throat length; don't go under it.
- lessons-learned "Same-axis room pairs need a Z-route": a throat's openings must face.
- A throat between rooms at different floor heights would need a rise in a run too short to
  climb (lessons-learned "Bound elevation by the corridor run"): keep throats level or skip.
- If decor, outline or gate needs a fix, stop and report.

## Result
