# Archive — zone-generator-winding-routes

## What landed

| Tasks | What landed | Commits |
|---|---|---|
| 1 | `routing.wind_route` gives one centreline door to door (run-outs square to each wall, bends cut at most `max_turn`, wander); `transitions.measure_routes` keeps it only where its strip clears every room and corridor by a half-width, stored as `CorridorSpec.path` | `6fa72b6`, `1c8d176`, `a7f45ff` |
| 2 | A corridor with a `path` is built as one winding strip, its rise spread along it in pieces within `MAX_SEG_RISE`; `corridor_continuity` reads the path | `7e6c7dc`, `0b9bae3` |
| 3 | Decor RoomContexts, the map line and outline and the EQ map follow the path | `33fdce1`, `e0c3205` |
| 4 | Cave run factor 9 -> 4 widths (61% of rough corridors wind; door-to-door median 102 u) | `58072f2` |
| 5 | Gate 691/696 (step 23's five residuals), bands under 5%; two placement fixes the new layouts exposed (floor POI off outline walls, decor `walk` off drop edges) | `1d18c74`, `7c7330e`, `2a2ec33`, `0946cb6` |
| 6 | `docs/ACCEPTANCE.md` "Step 25 — Winding routes" (cases a-h); thorough 4040 passed, 1 (stale-server test, the run's own commit) | `7b80745` |
| 7 | First look: "these look acceptable" (user) | — |

## Decisions

1. **Step 25 is winding routes** (lead, 2026-11-21, after the user's "continue ... keep working").
   It answers step 23's decision 6 follow-up: wind the whole route, so ramps wind, bends stop being
   square, and cave rooms can come back toward stock tunnel length.
2. **The path is stored, not re-derived** (A3). The clearance check needs the whole spec, so the
   readers take `CorridorSpec.path` rather than repeating it.

3. **The gate baseline for task 5 is 691/696** (lead, measured at `3871e84` with
   `EQ_PATH='F:\everquest_rof2'`, cave + warren, both layouts, 2-30 rooms, 2 seeds, `--seed 23`).
   The five failures are step 23's residuals (its archive "Follow-ups"). Without `EQ_PATH` the
   stock models leave the decor and the count is 695/696, so always sweep with it set.
4. **The cave run drops from 9 to 4 widths** (task 4; 40 cave graph builds per factor, seeds
   1000-1039, 8-30 rooms, flat/moderate/dramatic, `EQ_PATH` set). Rough corridors that wind (a
   `path` or a winding leg), that have a `path`, and door-to-door length (u, path else route):

   | factor | rough | wind | path | p25 | p50 | p75 |
   |---|---|---|---|---|---|---|
   | 3 | 711 | 48% | 39% | 66 | 79 | 86 |
   | **4** | 710 | **61%** | 55% | 86 | 102 | 110 |
   | 5 | 706 | 72% | 64% | 106 | 124 | 134 |
   | 6 | 706 | 74% | 73% | 127 | 147 | 158 |
   | 7 | 709 | 75% | 74% | 147 | 170 | 183 |
   | 9 | 707 | 80% | 75% | 190 | 216 | 232 |

   4 is the lowest with half winding. Its p75 (110 u) sits under the plain stock tunnels' p75
   (163 u, step 23 decision 6) and its median inside all stock tunnels' p25-p75 (76-341 u);
   at 9 the median was above the plain p75.
5. **Task 5's two root fixes** (lead, at the task 5 gate; the shorter cave runs' new layouts
   exposed both, neither is a winding fault). A floor POI (boss, treasure) keeps a body's
   radius off the outline walls when the room has such floor (`room_layouts._floor_poi`,
   `1d18c74`; POIs move in every outline style, goldens `2a2ec33`). Decor's `walk` keeps a
   half-width off a floor's own drop edge, a dais top or ledge (`decor.placement._near_drop`,
   `0946cb6`). Gate back to 691/696, only step 23's five residuals.

6. **First look accepted** (user, 2026-11-21): "the corridors do infact seem to wind, it might be interesting if we could add a scalar to how "windy" they become but for now these look acceptable". A windiness scalar is a
   follow-up, not part of this step.

## Follow-ups
- **A windiness scalar** (the user, at the first look): a control for how much corridors wind,
  e.g. scaling `wander` and the turn count, and possibly the run factor with it.
- **Z corridors don't wander at factor 4**: their runs between bend cuts are too short, so the
  path is the jog cut as one diagonal. Straight corridors under about 80 u don't wind at all
  (case b's Level -1 ramps, which wound per leg at step 23).
- **Warrens wind little**: 11 of 47 rough corridors over four builds get a path, all Z diagonals.
- **U routes never wind**, and `corridor_conflicts` still measures the straight route, not the path.
- **Task 5's fixes not looked at in 3D**: the boss off the wall (case g) and the dais top (case h).
- **Step 23's five gate residuals** remain (its archive "Follow-ups").
