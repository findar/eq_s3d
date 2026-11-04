# 13 — HUMAN: first look, classic against graph

Index entry: `tasks.md` task 13. **Type: human. Agents never tick this.**

## Setup
Merge tasks 1–12, restart the server. Generate seeds 3, 7 and 12 with 9 rooms as Classic, as Graph `classic_eq`, and as Graph `warren`; a temple dungeon on Graph; an ogre dungeon on Graph; a Graph outdoor dungeon. Open the rule diagrams (`python scripts/topology_rules.py draw classic_eq --out output/rules/`).

## Checklist
- [x] Graph dungeons read as dungeons: a way in, side rooms, a deep end worth reaching.
- [x] `warren` looks different from `classic_eq`, and like a warren; the temple shows its nave.
- [x] Room sizes feel right for the room's part, and scale for the ogre.
- [x] Corridors and rooms look as good as Classic's (no new odd joins); you can walk to every room.
- [x] The rule diagrams are clear enough to write a rule from.

## Result
Signed off by the user (2026-11-04): "connectivity looks good ... i think otherwise we are fine".
- Finding: classic and graph layouts are hard to tell apart because rooms look the same (rectangles, the same textures); room kinds don't show. Recorded as a follow-up for steps 8 and 9 (room shapes, POIs); not tuned in task 14.
- Finding: "i don't think we should be using the description box with the generation from controls". The Controls panel has no dungeon theme or race, so a themed or big-race graph dungeon could only be asked for in the description box, which doesn't take the Layout toggle. Task 14 adds Theme and Race to the Controls panel.
