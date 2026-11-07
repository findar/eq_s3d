# Archive — zone-generator-room-layouts

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

Nothing yet. Rows are added at the close step (task 15).

## Decisions

The design's "Decisions" section stands. The user took the recommended answer to every open question on 2026-11-06:

1. A Features control: None, Sparse, Normal (default), Dense.
2. Solids stand on an unbroken floor; no holes. The gate has its own check.
3. No real pits: a sunken court is a Dais ring around a lower middle.
4. Graph builds in every style, plain `built` rooms and outdoor dungeons included. Classic stays empty.
5. Step 9 is solid structure and advisory POIs. Anything loose or small that could be a `.mod` is step 11.
6. EQ map files gain lines for free-standing Features, in the map post-pass.
7. Tasks 1–7 land now; step 8's human pass runs before or with task 8; step 8 closes before step 9.

- **What the survey changed (task 1, 2026-11-06):** free-standing solids are in 0–40% of stock rooms, not most, and placed objects (93–648 per zone) fill the rest. Features stand in for objects until step 11: named rooms always, ordinary rooms mostly bare, a ceiling of 0.6 of rooms at `normal`. The Dais is the first Feature.

- **What a room is like belongs to the rules (user, 2026-11-06, after the first look):** "an ogre race would build rooms differently than a human might"; "an array of weights where the chance for any value 0-10 would be it's weight / sum"; "you might have an ogre cave that a tidier race took over"; "some eq zones are a bit random"; "transitions like doors are something we still would need to address". So: Scales as Weights, Layers multiplied, neighbours leaning by a Coherence, rule-made wings, and Transitions. Requirements 10–15, tasks 12–21.
- **The door itself stays the SQL export's** (settled call, kept): a Frame in the mesh, a Door_Spot in the sidecar.

## Follow-ups

- **A sunken court and rock columns wider at the foot** (task 9): question 3 allows a sunken court as a Dais ring, and a rough pillar could flare at its foot. Neither was asked for at the first look.

Carried in from earlier steps and relevant here:

- **Step 8's human pass is open** (2026-11-06): the user set it aside and asked to go on. Findings there land first.
- **Low stacking room type** (step 7): stock stacks low rooms. A low gallery with features would suit here, but it's a layout change, so not in this step.
- **Stairs and bridges stay square in caves** (step 8): a Feature near one could soften it.
