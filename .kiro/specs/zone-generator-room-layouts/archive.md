# Archive — zone-generator-room-layouts

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

Signed off 2026-11-07; master `e7a5219`. Suite 1951 thorough (one failure,
`test_canonical_outline`, is a face-order bug in `generators/mapgeom.py` that
reproduces on master and predates this step). Rooms hold Features, and what a
room is like (its finish, structure and clutter) comes from the rules.

| Task | What landed |
|------|-------------|
| 1 | Stock room contents survey: free-standing solids in 0–40% of rooms; the Dais first |
| 2 | The walk gate judges Features before anything places one |
| 3 | Feature meshes: pillar, boulder, dais and the rest, in each style's form |
| 4 | Placement and the Spine: Throats kept clear, rows and walls fill their length |
| 5 | Room layouts (recipes) as checked data under `rules/rooms/` |
| 6 | Graph builds stand Features in their rooms |
| 7 | The Features control, sidecar `features`, Features on the maps |
| 8 | First look signed off; the user moved what a room is like into the rules |
| 9 | A dais takes its style's form |
| 10 | Themes and named rooms read as themselves |
| 11 | Gate sweep and stock bands |
| 12 | How stock rooms change: neighbours mostly agree, 0–41% break; default finish Coherence 4 |
| 13 | Finish, Structure and Clutter as Weights (0–10) in `rules/rooms/scales.toml` |
| 14 | Rooms draw their Scales, leaning toward their neighbours |
| 15 | Rules grow wings with a hard edge |
| 16 | A room's Finish is its wall style |
| 17 | A room's recipe reads its Scales |
| 18 | The gate walks through a Transition, held to its own width and head |
| 19 | Seam, Frame and Breach in the mesh |
| 20 | Builds choose Transitions from rules |
| 21 | Finish, Structure, Clutter and Overlay controls |
| 22 | Second look signed off; boulders read as short pillars (follow-up) |
| 23 | Scales blend as a bell, Layers as a geometric mean; frames keep off rooms |
| 24 | `docs/ACCEPTANCE.md` "Step 9" (cases a–t) and step 8's cases on Finish; a rough floor flush at a shared Throat corner |
| 25 | Human acceptance pass signed off |

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
- **What stock's rooms do (task 12, 2026-11-06):** few zones hold to one finish. Neighbours mostly agree, and 0–41% of them break. A lean can't make wings, so the default finish coherence is 4 and wings come from rules. Style changes don't narrow, so a Seam is the common join.
- **The door itself stays the SQL export's** (settled call, kept): a Frame in the mesh, a Door_Spot in the sidecar.

## Follow-ups

- **Regenerate a room's contents, keeping its layout** (user, 2026-11-07): contents run last from per-room streams, so a contents seed would reroll them. Finish picks walls, so a reroll covers Structure and Clutter only.
- **Boulders read as short pillars** (task 22): their meshes stand in until step 11.
- **EQ models among the Features** (user, 2026-11-07): bookcases, chairs, tables alongside pillars. That is step 11, placed objects.
- **Map outline depends on face order** (task 24's thorough run): `test_canonical_outline` in `generators/mapgeom.py`, a floor beside a 3u step. Predates this step.
- **A sunken court and rock columns wider at the foot** (task 9): question 3 allows a sunken court as a Dais ring, and a rough pillar could flare at its foot. Neither was asked for at the first look.

Carried in from earlier steps and relevant here:

- **Low stacking room type** (step 7): stock stacks low rooms. A low gallery with features would suit here, but it's a layout change, so not in this step.
- **Stairs and bridges stay square in caves** (step 8): a Feature near one could soften it.
