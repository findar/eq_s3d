# Archive — zone-generator-decor-off

## What landed

| Tasks | What landed | Commits |
|---|---|---|
| 1–2 | Decor defaults to `none`; tests choose decor explicitly; sweeps take `--decor`; stage reruns and edits read the new default. Generate median 27.3 -> 6.3 s, max 144.2 -> 69.1 s | `9ca118f`, `fd1dd2f`, `1c04627` |

## Decisions

1. **Decor defaults to off** (the user, 2026-11-27: "since decor placement takes so much of build time, can we disable it for now? it's not critical at the moment since we only worry about room generation and can decorate and optimize that part later as well"). Step 33 measured decor at 44% of generate
   time. The levels stay; only the default changes.

## Follow-ups
- Map files (`_write_map_artifacts`) are now 57% of generate time: the next speed target.
- The rule planner's "bare" picks `sparse`, now more decor than the default.
- Not looked at in the browser: the Decor list defaulting to None, a page generate building bare rooms.
- Decor placement speed (step 33 archive): profile placement and RoomContexts before decor comes back on.
