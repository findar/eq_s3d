# Archive — zone-generator-decor-off

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

1. **Decor defaults to off** (the user, 2026-11-27: "since decor placement takes so much of build time, can we disable it for now? it's not critical at the moment since we only worry about room generation and can decorate and optimize that part later as well"). Step 33 measured decor at 44% of generate
   time. The levels stay; only the default changes.

## Follow-ups
- Decor placement speed (step 33 archive): profile placement and RoomContexts before decor comes back on.
