# Requirements Document

> **STATUS: roadmap step 26, ready.** Drafted 2026-11-21 at master `3f925f8`. At the step 25 first
> look the user said: "it might be interesting if we could add a scalar to how \"windy\" they
> become but for now these look acceptable", then chose it as step 26 ("Windiness scalar").
> Task index: `tasks.md` (card format). Decisions: `archive.md`.

## Introduction

How much a rough corridor winds is fixed today by the one `[tunnel]` table in
`rules/walls/rough.toml` (measured from 113 stock tunnels: wander 0.2 of the span, turns of at
most 60°, runs of 20–72 u) and by the cave run factor (4 corridor widths, step 25). This step
adds one user-facing scalar, **Winding**, that scales how far corridors stray. 0 builds them
straight. 1 is today's stock-measured tunnel. Higher values wander further.

## Requirements

1. **The plan field.** `ZonePlan.winding` is a float, default 1.0, clamped to
   `[0, WINDING_MAX]`. A plan without it means 1.0. Bad values fall back to 1.0, as `verticality`
   does.
2. **What it scales.** The tunnel's `wander` is multiplied by `winding` for every rough corridor
   in the zone: the per-leg `wind` limit (step 23) and the door-to-door `path` (step 25) alike.
   `segment`, `max_turn` and `end` stay as measured, so no turn is sharper than stock at any
   setting. At `winding = 0` no corridor gets a `wind` or a `path`, so corridors are straight
   with square bends. Whether the cave run factor also follows `winding` is decided by
   measurement (task 2), not assumed.
3. **Recorded, read by everyone.** The zone's `winding` is recorded on the ZoneSpec (written
   only when it is not 1.0). Every reader that re-derives a leg's centreline (mesh, decor
   RoomContexts, map, gate) winds with the same scaled rules, so they agree at any setting.
4. **Bytes.** At `winding = 1` (or absent) every zone is byte-identical to before this step.
   Zones with no rough corridor are byte-identical at any setting.
5. **Controls and words.** The web Controls get a **Winding** slider wherever a zone can have
   rough corridors (dungeon, city, outdoor dungeon), default 1, shown in the build summary. The
   rule planner reads words: straight ("straight", "regular", "orderly") lowers it, twisting
   ("twisting", "winding", "meandering", "serpentine", "labyrinthine") raises it. The LLM
   planner's schema gets the field. The server passes it through.
6. **Gate and bands.** Cave and warren gate sweeps (`EQ_PATH` set) pass at master's count or
   better at `winding` 0, 1 and `WINDING_MAX`. Quality fail shares stay under 5% per key.
