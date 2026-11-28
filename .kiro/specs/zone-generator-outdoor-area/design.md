# Design — zone-generator-outdoor-area (roadmap step 35)

Written at master `152e956`. Verify against the code before each task: it moves.

- Sizes: `generators/wilderness/matrix.py` (`DEFAULT_ZONE_SIZE` 2400, `OUTDOOR_DUNGEON_ZONE_SIZE` 1200, the
  16x16 matrix at 150 u/cell); the plan's `size` (`ai/schema.py`, small to huge) today sizes dungeons only.
- Lava patch: `generators/wilderness/matrix.py` ~917.
- Outdoor dungeon: `generators/outdoor_dungeon.py` builds the host wilderness first, takes the hill's
  Envelope, `layout_in_envelope` sizes rooms to it, `plan_entrance` cuts the Tunnel and Mouth. `landscape_for`
  (`generators/wilderness/build.py`) is still called by `tunnel_doors`, `sidecar_block`, `_host_grid`, `_hill`.
- Order of tasks: measure (1); lava (2) and read-once (3) are small and independent; host sizing (4) then
  entrances (5) both live in `outdoor_dungeon.py`, so they run one after the other; area size (6) last among the
  build tasks because it changes every wilderness's bytes.
