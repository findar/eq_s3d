# Archive — zone-generator-district-races

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

1. **Step 31 is district races, intrusion and one-way drops** (the lead, 2026-11-26, from the
   user's ideas at the step 30 look). One spec, ordered so the one-way gate (task 2) lands
   before anything makes a drop. The bar for drops is the user's: strong connectivity (a drop
   may be the only way in, never the only way back), weighted toward flush.
2. **`MAX_DROP` 80 u, flush weight 0.9, giant hall length 3.0, intrusion links 3** (task 1): drop p90 84 u (cave 79), 11 % of passage ends drop;
   only giants (kael, 1 zone: 38.5 H vs built band 10.7-30.2, 3.8x ours, clamped) show a hall signal, no other race or Purpose
   (orc, dark elf: LDoN kit / city kind; dragon: u only); 13 mixed zones join built and cave by 3 links (median).
3. **A drop's height is drawn from stock, capped by `MAX_DROP`; the giant default is provisional** (the lead,
   2026-11-26, at task 1). `MAX_DROP` 80 u is the gate's limit, inflated by water and steep slopes; task 7 draws each drop's
   height from stock's (p50 24 u) under it, not uniformly. Giant 3.0 rests on one zone (kael, 7 halls): it applies to giant
   Districts only (requirement 5), and the step 31 look decides whether it stays.

## Follow-ups
