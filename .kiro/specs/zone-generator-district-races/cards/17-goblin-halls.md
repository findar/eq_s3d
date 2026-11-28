# 17 — Goblin-sized links between Districts keep goblin hall lengths

Index entry: `tasks.md` task 17. Requirements 4, 5, 6, 11.

## Goal
The user, at the step 31 look: "the goblin corridors end up very long". A Threshold or breach between a giant and a goblin District is cut to the goblins' size (the smaller race) but its length is set and capped in giant H (decision 18: the 164 H cap at the larger race; aca9840: cross links use the larger race's run), so an 18 u wide goblin tunnel runs up to 3,123 u (520 goblin H; task 11 case d `corr_26`, 142 giant H). A goblin-sized link should read as a goblin tunnel: long by goblin standards at most.

## Done when
- [ ] The cause named: which of the run, the spring placement of the two Districts, the breach span (`BREACH_SPAN`) and the cap makes these links long, with numbers on task 11's cases d, i, v, p.
- [ ] Every link between Districts is measured door to door in the H of the race that sized it (`semantics.corridor_race`); over the `--intrusion` sweep seed 31 and the giant-fortress prompt on seeds 2020–2029: p50 inside stock's built band (10.7–30.2 H, decision 2) and max at most 164 H in that race's H. Table in the commit body, before and after.
- [ ] Giant halls inside the giant District keep their 3x (decision 5's band); goblin District halls unchanged.
- [ ] Zones without a District race byte-identical to master (each built in its own process).
- [ ] `--intrusion` sweep seed 31 240/240; the 120-Draw intrusion bands every key under 5%; 24-room whole-generate max under 300 s; quick tier; `-m gate` and the full suite alone at close.
- [ ] `docs/ACCEPTANCE.md` step 31: cases re-measured (links in their own race's H) and re-pinned where a seed lost its drop or breaches.
- [ ] A decision in `archive.md` (21 and up) replacing decision 18's "at the larger race's H" for links.

## Pitfalls
- Don't shrink giant rooms or giant halls to get there: the giants' scale is the look the user kept.
- Breaches are best-effort (decision 20); a tighter span may cost breaches. Report the breach rate (task 6 measured 82% of pairs at 2+ links).
- Stacked Districts and the relax runaway (7a9b90e): keep `HALL_SCALE_CAP` behaviour.

## Result
✔ 66e9f96 · 4408 passed + test_bridges re-pinned (quick 3203 passed)
