# 6 — HUMAN: first look at placeholders in 3D

Index entry: `tasks.md` task 6. **Type: human. Agents never tick this.**

## Setup
Merge tasks 1–5 and 11, restart the server, and generate a themed dungeon (prompt
"a gnoll temple dungeon"), a city, and a wilderness zone with a river edge.

## Checklist
- [x] Every surface shows its name and a pattern, and the names match what the
      surfaces are.
- [x] Text reads the right way up and isn't mirrored.
- [x] Textures tile without visible seams.
- [x] The labels are readable but not overwhelming.

## Result
Signed off by the user (2026-11-01): "ceiling and wall look correct, floor
looks reversed but i think that's also acceptable for now". Finding for
task 7, at the user's choice:
- Floor labels read mirrored from above (floor `v` runs with +Y, so the
  picture is flipped top to bottom). Fix: floor `v = -y`.
