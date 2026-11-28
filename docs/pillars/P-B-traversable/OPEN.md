# P-B Traversable — open items

Status and Checked as in [P-A's OPEN](../P-A-web-app/OPEN.md). Roll-up: [OPEN.md](../../../OPEN.md).

| ID | Item | Source | Status | Checked |
|---|---|---|---|---|
| B-1 | No ceiling-clearance check over an ordinary standable face (only Transitions and Enterable openings check head height) | umbrella Known Limitation 10 | open | code: `analyzer/traverse.py` |
| B-2 | The gate's seam rule joins floors within 2 u in XY and 3 u in Z with no wall test; geometry hugging a room's outside wall can read as joined through it | step 31 archive | open | record |
| B-3 | The gate reads a solid Feature's hollow as floor; decor refuses the Prop that would move the core there, the gate should skip samples inside a solid Feature's plan | step 29 archive | open | record |
| B-4 | Three gate residuals (footprint cuts): warren classic flat 23 s490919952 (decor alley), warren classic flat 26 s1205085953 (Prop-to-wall gap), cave classic moderate 8 s1728424002 (door jamb missing from decor's room data) | steps 23, 26 archives | open | record |
| B-5 | cave classic dramatic 21 s1866540615 fails alone in a fresh process (decor footprint_cut 68 u²) | steps 30, 31 archives | open | record |
| B-6 | Two `--pair` seeds fail on master: cave_first:sunken_ruin graph moderate 24 s313486578 (room_10 walled off); cave_second:ice_keep graph moderate 17 s1985365888 (room_11 footprint_cut) | step 31 archive | open | record |
| B-7 | 16-room Graph dungeon seed 26 fails with Decor none (room_8 open seam): geometry, not decor | step 11 archive | open | record |
| B-8 | Thorough-profile failures: `test_raw_navigable` seed 8869712 (room_4 outline gap, step 20); `test_room_placement` f4 seed 33757 (step 15); `test_site_models` p3 tent at seed 963196 read as enterable (steps 18, 19); `test_w1_outline_is_inside_connected_and_reaches_every_door` at 300 examples (two wall loops, a folded fan; kept at 60, test-speed, step 21) | those archives | open | record |
| B-9 | Check corridor headroom, risers and room crossings on the plan before the mesh is built (catch what the gate finds earlier, cut retries) | step 30 archive (the user's question) | in flight (step 33) | — |
| B-10 | Intersecting corridors on the elevated path slip past the continuity and conflict checks (30-room controls build, seed 105770060) | M1 `tasks.md` (parked bug) | parked (low priority) | record |
| B-11 | The M1 human acceptance walk (task 22.5) was never ticked | M1 `tasks.md`; ROADMAP "Still open from M1" | waiting | code: `tasks.md` 1697 `[ ]` |
| B-12 | With elevation on, `_assign_elevation` re-derives every floor and drops the content layer's sink/raise bias (M0 fixed only the elevation-off path) | ROADMAP Known issues | open | code: `generators/layout.py` 1197 |
| B-13 | `corridor_conflicts` measures a corridor's straight route, not its winding path | step 25 archive | open | record |
| B-14 | Loops-first planning (designed one-way loops) and corridors as placed blocks | step 33 archive | in flight (later step 33 slices) | — |

## Fixed (dropped from the list)

| Item | Fixed by |
|---|---|
| The walk surface takes ceilings as floor (step 6 task 1) | `e25abe6` (step 7 task 18) |
| Two of step 23's five gate residuals: the outline slit (cave graph flat 29 s1259910114) and decor's clear width (warren graph moderate 25 s616736071) | `7566697`, `74ae74e` (step 26 task 10) |
| Build-level properties didn't cover large zones (2–12 rooms only) | M1 wave 1, merge `c63f056` (30 rooms, corridor-floor continuity) |
| Cave theme broken in 3D despite passing tests | M0, merge `b0d412f` (pipeline deleted) |
| Outdoor mesh and room graph in different frames (umbrella Known Limitation 2) | superseded: the drape was rejected (M1 wave 3, `fbadf63`) and wilderness rebuilt as a landscape (step 1) |
| Multi-level / stacked-floor dungeons (ROADMAP design item) | step 7, master `406292e` |
