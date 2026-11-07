# Archive — zone-generator-room-walls

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

Signed off 2026-11-07 (with step 9's pass); master `f75cef9`. Built at master
`1c69568`, suite 1628 (fast and thorough green). Graph rooms take one of three
wall styles, `built`, `hewn` and `rough`, each an Outline cut from the room's Box.

| Task | What landed |
|------|-------------|
| 1 | Stock wall survey: Fill, wander and corner bands per style; Outlines take 5–20% off the Box |
| 2 | The walk gate judges shaped rooms (Outline floors, Throats kept clear) before anything makes one |
| 3 | Outlines and their meshes: Cells (Voronoi for `rough`, `facet` for `hewn`, a grid for `built`), plumb walls |
| 4 | Wall styles as checked TOML data under `rules/`, with check and draw tooling |
| 5 | Graph dungeons draw each room's Outline; Classic stays rectangles, byte-identical |
| 6 | Floors and ceilings move with the style, flat at every Throat |
| 7 | The Walls control, sidecar `walls`, and the style on the maps |
| 8 | First look signed off (no findings) |
| 9 | Corridors match their rooms' style |
| 10 | Textures follow the style |
| 11 | Outdoor dungeons draw their walls |
| 12 | Styles tuned to the stock bands; gate sweep; shaped rooms keep their Box (question 4) |
| 13 | Nothing left to tune |
| 14 | `docs/ACCEPTANCE.md` "Step 8"; small rooms wander less |
| 15 | Human acceptance pass signed off with step 9's, on the cases rewritten for step 9's Finish control |

Step 9 task 16 later made a room's style its Finish, drawn from the rules'
Scales. The page's control is now Finish; a plan's `walls` still pins one style.

## Decisions

The design's "Decisions" section stands. The user took the recommended answer to every open question on 2026-11-06:

1. The styles are `built`, `hewn` and `rough`.
2. One style per zone, with rules able to fix a shape; a mix by district is a follow-up.
3. The Classic engine stays rectangles, byte-identical.
4. Whether shaped rooms grow to keep their floor area is decided in task 13, from task 12's measure and the first look.
5. Stairs and bridges stay as built in this step; check them at the first look.
6. `built` rooms change too (L-shapes, crosses, alcoves, cut corners, some plain rectangles); every Graph build changes once, its goldens recaptured with old and new hashes.

- **What the survey changed (task 1, 2026-11-06):** Outlines take off about 5–20% of the Box (true Fill 0.80–0.95), because all-rectangle builds measure 0.78–0.81 on the survey's Fill and stock measures 0.64–0.75. Plain rectangles stay `built`'s commonest shape, with a new `cut` shape (corners cut) next. Mixed zones are left out of the bands.
- **How each style draws (task 3, 2026-11-06, from looking at sample plans):** `rough` is Voronoi at about 4 H with walls wandering inward about 1.3 H, because Cells alone kept the Box's straight sides; `hewn` is a new `facet` complex, corners cut at uneven angles, because relaxed Voronoi drew the same bitten rectangles and stock hewn rooms are convex polygons; `built` is a 4 H grid. Fill floor 0.65.

- **Shaped rooms keep their Box (question 4, task 12):** true Fill averages 0.75 rough, 0.86 hewn, 0.93 built, so rooms read about 13%, 7% and 4% narrower. Survey Fill is in band, the first look had no complaint, and growing Boxes would move every layout once, so they don't grow. The cost lands mostly on rough, and a stock-sized cave is close to the race band's low end at small sizes. Revisit it if a look says rooms feel small.

## Follow-ups

- **Rough 30-room builds take about 32 s** (task 12; 6 s at 14 rooms). Inside the 60 s budget, but the gate's seam test (`_tri_tri_xy_contact`, per-pair Python) is now the slowest step.
- **Bridges and stairs stay square in caves** (question 5, first look): no complaint yet, but they're the last straight lines in a rough zone.
- **Rule set Warren with Walls From theme is built** (task 7): the style follows the theme, not the rule set, so a warren with no theme gets masonry. Theme Warren gets rough.

Carried in from earlier steps and relevant here:

- **Room kinds don't show** (step 6): answered here through each style's shapes table.
- **Low stacking room type** (step 7): stock stacks low rooms, and `hewn` or `rough` low galleries are a natural place for it. Not in this step.
- **The district look** (step 6): one style per zone in this step (Open question 2). Task 1 found stock zones often mix built and cave parts (chardok, cazicthule, hole, gukbottom's temple, soldungb's wing), so a mix by district is the natural next step.
