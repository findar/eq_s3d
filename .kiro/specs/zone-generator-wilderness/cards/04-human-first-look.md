# 4 — HUMAN: first look at a Karana (terrain + bowl)

Index entry: `tasks.md` task 4. **Type: human. Agents never tick this.** It
replaces old tasks 8.2 and 11.2, which couldn't run before task 2.

## Setup
Restart the server with `EQ_S3D_DEV_WILDERNESS=1`, then open the web app.
Check that the side panel shows no stale-code banner.

## Cases
| # | Edges | Seeds |
|---|-------|-------|
| a | all mountain (default) | 1337, 1, 42, 20250126 |
| b | N zoneline | 7, 2985 |
| c | N zoneline, E river | 1955208177, 123456789, 2024 |
| d | any (the matrix seeds lava) | 99, 2024 |

## Checklist
- [ ] Reads as an **open plain with weathered hills**, not a crater and not a
      room graph in a grass skin.
- [ ] Valleys and ridges look **water-made** (branching drainage), not noise blobs.
- [ ] Cliffs and shorelines are **sharp**, not stair-stepped.
- [ ] The **Rim reads as a distant backdrop**, not a wall right at the play edge.
- [ ] You **can't walk out** over a mountain or across a river edge.
- [ ] A **zoneline gap** is a flat, walkable opening leading off the map.
- [ ] **Lava** reads as a hazard you can't walk onto.
- [ ] The zone feels **big enough** to be a Karana (it's 2400 u today).

## Result
Write findings as short bullets below. Each becomes an item in task 5.
<!-- e.g. "- c/2024: rim too close on E side, ~1 cell from play edge" -->
