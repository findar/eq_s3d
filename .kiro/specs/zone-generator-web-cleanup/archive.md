# Archive — zone-generator-web-cleanup

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

| Tasks | What landed | Commits |
|---|---|---|
| 1 | Six labelled Control groups as aligned grids; header on one row; side panel aligned; the stale-code banner above the open Controls | `3ccd8ac`, `1c4a6d1` |
| 2 | Describe \| Controls switch and one Generate, remembered; no silent fallback | `0bfdb20` |
| 3 | Only what applies: controls, groups, request fields, side panel, overlay toggles | `79fc0af` |
| 4 | Acceptance section "Step 14 — Web UI cleanup" | `d8ecbb9` |
| 5–6 | Look and acceptance signed off ("All good"); closed | |

## Decisions

Decided 2026-11-14 by the lead on the design's recommendations, from the user's request ("only
show controls when they can be used, ... clean alignment, ... a way to show only the text
prompt or the controls when we generate"); the user sees them at the first look.

1. **One Generate button and a Describe | Controls switch** (design question 1).
2. **Controls is the default mode** with nothing remembered (question 2).
3. **An empty description disables Generate** in Describe mode; no silent fallback (question 3).
4. **Controls that don't apply are hidden**, not disabled; disabled zone types stay visible with
   their reason (question 4).

## Follow-ups

- **Hidden controls still sent** (task 3): the decor seed (Decor None) and Inhabitants (Sites none)
  build the same zone when left out, but the sidecar then records another value, so they're sent.
- **The open Controls cover the top of the 3D view**; collapse with ▾.
