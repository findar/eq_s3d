# Archive — zone-generator-placeholder-textures

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

Signed off 2026-11-01; master `2ce32f9`. Suite 738 (fast; thorough 3× green).

| Task | What landed |
|------|-------------|
| 1 | Material names `<set>_<surface>` (race first; `<race>_dungeon` for shared, `city`, `wild`, `liquid`); `Opaque_MaxCB1.fx` replaces `<fixed-function>`, which the format gate now rejects; geometry adds no unused bare materials; golden geometry hashes prove rename-only |
| 2 | 5×7 bitmap font and the 256×256 placeholder painter: base colour, a pattern per surface class, the name twice, WCAG 4.5:1 plate, seamless, pure |
| 3 | Placeholder as the default texture mode for surfaces (procedural/ai by override; tree bark/leaf unchanged); sidecar `textures` list |
| 4 | Textured GLB terrain: one primitive per material, TER UVs, embedded PNG, base-colour fallback; no-texture GLB byte-identical; UV probe found our walls ran v upward |
| 5 | Viewer: anisotropic filtering on textures, wireframe over material lists |
| 6–7 | First look signed off with one finding (mirrored floors), fixed: floors v = −y |
| 8 | ACCEPTANCE "Step 3 — Placeholder textures"; timing test (0.20 s vs 0.26 s before) |
| 9 | Human acceptance pass: signed off, no findings |
| 11 | Wall UVs follow EQ's convention (v down, u right from inside); goldens re-recorded without UVs |
| 12 | Build-file route segments use `fullmatch` (a trailing newline slipped past `match`); flaky runner issues recorded in lessons-learned |

Measured on the way (design "Research findings" and task 4): stock walls run v
down as z rises on 88–98 % of wall edges; classic textures are 256×256 and
named by set and surface; classic texel density is still unmeasured.

## Decisions

The design's "Decisions" section (1–4) stands. The user answered its open
questions on 2026-11-01, each with the recommended option:

- **Placeholder look (Open question 1):** base colour, a Surface_Class
  pattern and the Material_Name as text.
- **Default Texture_Mode (Open question 2):** `placeholder` for every build;
  `procedural` and `ai` stay selectable with `EQ_S3D_TEXTURE_PROVIDER`.
- **Textured preview (Open question 3):** in step 3 (Req 6); trees stay in
  base colours.
- **Race in the set name (Open question 4):** race first
  (`gnoll_temple_wall`, `gnoll_dungeon_floor`).
