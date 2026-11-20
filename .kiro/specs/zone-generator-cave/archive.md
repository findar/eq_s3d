# Archive — zone-generator-cave

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

| Tasks | What landed | Commits |
|---|---|---|
| 1 | The `cave` Purpose: Room_Types `cave_mouth`, `cavern`, `grotto`, `crystal_grotto`; cold and crystal light; damp-rock palette; kind map; `cave` in `VALID_DUNGEON_THEMES` | `b526dd8` |
| 2 | `[themes.cave]` finish (rough on graph, never built), recipes, topology `cave = { base = "warren" }`, `cave_rock` textures | `6463109` |
| 3 | `rules/decor/layers/cave.toml`: crystal clusters, stalagmites, mushrooms, roots; no furniture | `8946f16`, `31bc537` |
| 4 | Room scale from `styles/cave.json` as a Size band shift (−0.089); `LayoutGenerator(profile=)` | `9c86fbe` |
| 5 | Cave words pick the Purpose; Districts neighbours and contrasts; "Cave" on the page; outdoor Entrance on the top Level (fix) | `1b44160`, `aba7bee`, `5c1e8e6` |
| 6 | Outline fix (no hairline links, no floor hung off a sliver); gate 348/348; cave fail share 0.8–3.8%, bands unchanged | `371c55e`, `fcc3a35` |
| 7 | ACCEPTANCE "Step 21 — Caves" (cases a–h); VSPBLOCK301 retag reverted for A6; thorough 3799 passed | `bae1ae8`, `7319049` |
| 8 | First look skipped at the user's word, 2026-11-20 | — |
| 10 | A graph-layout cave recorded for the room-context corpus (seed 125) | `d869ca4` |

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
5. **The `rough` look holds on the graph layout only** (task 2, `6463109`): the classic layout
   draws no per-room finish, so classic caves keep box walls; graph caves (the default layout)
   draw 86% `rough`, 14% `hewn`, never `built` (finish weights 7–10 written as 0). Topology base
   is `warren`, so `cavern` appears only as the hub. Amends A1.

## Follow-ups
- **Cave ceilings drop with the shift** (task 4): about −12%, against `cave.json`'s taller
  measured ceilings (474 vs 303); shrinking sides only needs `_apply_room_scale`.
- **A cave District in another theme's zone gets no cave decor** (task 3): decor layers follow
  the zone's theme, so its cavern and crystal grotto take the generic recipes (benches, banners).
- **Classic-layout caves look built** (task 2): no per-room finish on classic, so no `rough`
  walls; a high-finish race (giant) pushes graph caves toward `hewn`.
- **Warren "open seam"** (task 6 comparison sweep, graph 18–24 rooms): one warren build failed
  the gate on an open seam, a class cave never hit; not investigated.
- **`test_w1_outline_is_inside_connected_and_reaches_every_door` flakes** ("no Cell's fan folds
  over"): rare, same 8 failing examples on master before the outline fix.
- **VSPBLOCK301 reads as a rock** (task 7): a square cut slab tagged rock; task 3 retagged it
  brick, which moved rocks in other themes' decorated zones (Theme None, mine_delve), so the lead
  reverted it for A6. Retag it in a step that may move decor bytes.
- **A cave District after a built District gets built walls and the first District's decor**
  (task 7, case f): finish and decor follow District 0's Purpose; cave first makes 14 of 16
  rooms rough, the built Districts included. Wider than the decor follow-up above.
- **No water in an outdoor cave's flooded galleries** (task 7, case e): outdoor dungeons keep
  only the host landscape's regions (any Purpose).
- **Warm light in warren and collapsed galleries inside a cave**; wall torches and the shared
  treasure dressing (chests, urns) in cave builds (task 7).
