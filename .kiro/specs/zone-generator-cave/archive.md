# Archive — zone-generator-cave

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

Decided 2026-11-19 by the lead after the user's "Continue" (multi-zone worlds wait on the user's
design review). The user confirms at the first look (task 8).

1. **Step 21 is M3's `cave` Purpose.** The last unbuilt piece of M3; the Natural_Style (M5) is
   a later step.
2. **The look is the `rough` wall style** (A1): a low finish on `[themes.cave]`, no new geometry.
3. **Room scale from `styles/cave.json`** (A3); bands unchanged unless task 6 measures `cave`
   above ~5% on a key.
4. **The cave profile is a band shift** (task 4, `9c86fbe`): dungeon rooms are sized from race
   bands since step 7, so `cave.json`'s `floor_area` (15% under `dungeon.json`) becomes a Size
   shift of −0.089, as `outdoor_dungeon.py` does; caves come out 7.6% (classic) / 13.9% (graph)
   smaller than with no profile. District 0 unknown (Districts on, nothing proposed) → `dungeon`.

## Follow-ups
- **Cave ceilings drop with the shift** (task 4): about −12%, against `cave.json`'s taller
  measured ceilings (474 vs 303); shrinking sides only needs `_apply_room_scale`.
- **A cave District in another theme's zone gets no cave decor** (task 3): decor layers follow
  the zone's theme, so its cavern and crystal grotto take the generic recipes (benches, banners).
