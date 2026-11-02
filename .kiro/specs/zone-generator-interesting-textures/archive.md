# Archive — zone-generator-interesting-textures

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

Signed off 2026-11-01; master `e59e37f`. Suite 843 (fast; thorough green).

| Task | What landed |
|------|-------------|
| 1 | WLD reader keeps UVs and per-polygon texture indices; classic wall repeat medians reproduced within 0.5 u |
| 2 | Texture_Profile in `styles/*.json` (texel density per surface, Look_Stats bands), replacing `uv.scale`; dungeon walls 24.1 u, city 14 u |
| 3 | Recipes as data (`styles/texture_recipes.json`): every one of 253 buildable dungeon and city names resolves; themes with different palettes differ |
| 4 | Painter building blocks (crc32 seeds, tileable noise and Worley cells, ashlar layout) and the stone families |
| 5 | Planks, plaster, ice and sky painters |
| 6 | Grading toward the classic median and into the band (ice and sky exempt where natural); recipe mode the default for dungeons and cities; texture list records family and Look_Stats; salted-`hash()` seed fixed |
| 7 | `texel_density` on each `MaterialSpec` (the IR), set by the builder from the profile; placeholders keep 100 u |
| 8–9 | First look signed off with one finding, fixed: hallways match the rooms they join |
| 10 | ACCEPTANCE "Step 4 — Interesting textures"; timing (+0.35 s on a 30-room dungeon); thorough run green |
| 11 | Human acceptance pass: signed off, no findings |
| 13 | Root cause of the fresh-worktree test failures (Windows `\\?\` path-prefix race), fixed in `core/paths` |

Deferred to a later step: wilderness ground, water and tree textures, and
normal maps.

## Decisions

The design's "Decisions" section (1–4) stands. The user answered its open
questions on 2026-11-01:

- **Texel density (Open question 1):** each theme's measured classic density
  per surface (p50); placeholder mode keeps step 3's 100 u so labels stay
  readable.
- **Normal maps (Open question 2):** no. Classic–PoP zones have none; umbrella
  Req 16 stays planned as a later option.
- **Scope (Open question 3):** dungeon and city first; wilderness ground waits
  for a later step.
- **Trees (Open question 4):** trees wait with the wilderness ground, so a
  Karana stays consistent (the user's choice after scope narrowed).
