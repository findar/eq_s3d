# Archive — zone-generator-quality

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

Decided 2026-11-18 by the lead after the user's "Skip and continue more work" (multi-zone worlds
wait on the user's design review). The user confirms at the first look (task 7).

1. **Step 19 is M3's quality gate, not Districts.** It is the unblocked umbrella piece that other
   work waits on (step 18's `edit_outside_bands`), and it is small; Districts and the `cave`
   archetype are a later step.
2. **Bands are the generator's own targets, measured from its output** (A1): stock zones have no
   room graph to measure. Ordinary output passes; only the dull tail is redrawn.
3. **Rebuilds and edits measure, they don't redraw** (A4).

## Follow-ups
