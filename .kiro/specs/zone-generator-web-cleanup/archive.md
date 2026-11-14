# Archive — zone-generator-web-cleanup

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

| Tasks | What landed | Commits |
|---|---|---|

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
