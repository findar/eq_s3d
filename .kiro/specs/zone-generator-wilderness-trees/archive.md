# Archive — zone-generator-wilderness-trees

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

Signed off 2026-11-01; master `8160b17`. Suite 655 (fast and thorough).

| Task | What landed |
|------|-------------|
| 1 | `core/zon.py`: object and region rotations are radians, yaw in the first field (stock zones confirm; object tilts reach 0.46 rad) |
| 2 | Vegetation kit as data (`styles/vegetation.json`, `plains_grassland`: broadleaf, conifer, sapling) and its loader |
| 3 | Procedural `.mod` tree models (6-sided sunk trunk, flag clear, opaque; card canopy, passable, chroma) and bark/leaf DDS textures |
| 4 | Placement on Eligible_Ground in groves with meadow between; Grove_Ratio 0.50–0.80 over 540 zones, species share within 0.07 |
| 5 | Build integration: models, textures and one ZON object per tree in the `.eqg`; trunk walkability check in the bowl gate; `vegetation` sidecar block; dungeon and city `.eqg` unchanged |
| 6 | GLB `vegetation` node beside `terrain`; tree-less GLBs byte-identical to before |
| 7 | Format gate checks placed models, their textures and shaders (folded into existing checks) |
| 8 | Density from prompt words, `--trees` and `controls.trees`, source recorded |
| 9 | Web Trees selector and overlay toggle; camera frames on the terrain node |
| 10–11 | First look in 3D signed off; nothing to tune |
| 12 | ACCEPTANCE "Step 2 — Trees"; timing test (dense adds ~0.4 s, budget 3 s); thorough run green |
| 13 | Human acceptance pass: signed off, no findings |

Found on the way, left open: dungeon and city materials write the placeholder
shader `<fixed-function>` (tolerated by the format gate); the PFS footer holds
the write time, so two `.eqg` writes differ in their last 4 bytes; "open" in a
prompt means no trees, so "open plains" is treeless (Req 3.2 as written).

## Decisions

The design's "Decisions" section (1–5) stands. The user answered its open
questions on 2026-10-31, each with the recommended option:

- **Tree collision (Open question 1):** trunk solid, canopy walk-through, as in
  the classic Karanas. Trunks keep Tree_Clearance so a player always passes.
- **Density control (Open question 2):** prompt words plus a Trees selector
  (none / sparse / normal / dense) on the web and CLI.
- **Rim slopes (Open question 3):** no trees on the rim; plains below 30° only.
- **Maps (Open question 4):** no trees on the EQ `.txt` or the web SVG.
