# Archive — zone-generator-winding-tunnels

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

Decided 2026-11-20 by the lead after the user's "Pick the step yourself". Multi-zone worlds wait
on the user's design review. The user confirms at the first look (task 7).

1. **Step 23 is winding tunnels.** Angled corridors have been "wanted" since M1, and a cave's
   corridors are its last straight boxes. This is the first piece of M5's "winding tunnels",
   built on the Box backend. M5's other parts, rounded rooms and the re-voxelise vs deform
   decision, wait.
2. **The layout is untouched** (A1, A2). Winding happens at dressing time, only into clearance
   measured from the finished spec, so routes, conflicts, the Envelope and Levels are the same
   and only rough corridors' meshes change.
3. **Stock tunnels wind like this** (task 1, `scripts/tunnel_survey.py`, 113 tunnels in 7 rough caves,
   p10/p50/p90): segment between turns 16/40/72 u, turn 24/48/87 deg, wander 0.07/0.25/1.50 of span,
   width 12/20/31 u, end straight 20/37/84 u. Proposed `[tunnel]`: `segment = [16, 72]`,
   `max_turn = 85`, `wander = 0.25`, `end = 20`.

## Follow-ups
