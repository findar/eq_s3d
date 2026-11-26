# Archive — zone-generator-hall-length

## What landed

| Tasks | What landed | Commits |
|---|---|---|
| 1 | `stock_room_shapes.py --halls`, `grid_score.py --halls`: stock built halls 1.05–2.96x ours at 1; `HALL_MIN` 0.5, `HALL_MAX` 3.0 and the knob per layout (decision 2) | 2 |
| 2 | `ZonePlan.hall_length` / `ZoneSpec.hall_length` (written only when not 1) scale the Graph run, the classic/city scatter and the outdoor gap; at 1 every zone byte-identical; outdoor stops at ~1.6x (decisions 3, 4) | 4 |
| 3 | Hall length slider, build summary, server pass-through, planner words (`match_hall_length`: short 0.6, long 2.0), LLM prompt line | 2 |
| 4 | `--hall-length` on both sweeps; first run failed (decision 5); re-run on task 8's tree: gate 696/695/696 at 0.5/1/3.0, bands <= 3.5%, draw at 3.0 cave 3.7/5.0 s, outdoor 9.9/17.3 s | 3 |
| 8 | Five root causes fixed in `generators/` (angled lines crossing sibling corridors, a corridor 0.04 u off a third room's wall, a stair over and under one room, a Prop cutting floor on the gate's samples, the classic scatter below the separation floor); 9 of 942 plans moved at 1, named | 7 |
| 5 | `docs/ACCEPTANCE.md` "Step 30 — Hall length" (fortress, cave, outdoor at 0.5/1/3.0, seed 731402518) | 2 |
| 6 | The user's look: "as far as look and feel goes hall length is good for now" | — |

## Decisions

1. **Step 30 is a Hall length scalar** (the lead, 2026-11-25, on the user's "You pick next").
   The user's idea at the step 26 second look: "a future task should also adjust length of
   halls". Modelled on Winding (step 26): one plan field, a Controls slider and prompt words;
   1 is today's zones, byte for byte.
2. **`HALL_MIN` 0.5, `HALL_MAX` 3.0** (task 1): stock zone-median hall length (door to door,
   throats/direct and passages <= 3 H left out) p10/p90 over ours at 1, in H: built 1.05/2.96,
   cave 0.53/0.92, city 0.77/2.17 (outdoor, open areas, 1.29/3.7, not used). Knobs for task 2:
   **Graph** (built, warren, cave) the run, affine not proportional (run x2 gives d2d x1.72
   built, x1.81 cave), so scale it by about `1 + 1.4(L-1)` built/warren, `1 + 1.25(L-1)` cave;
   **classic and city** the scatter ellipse's spread (`ClassicEngine._scatter_rooms`; x1.6 gives
   x1.8, x2 gives x2.5), not the separation gap or `CLASSIC_SPREAD` (room sizes); **outdoor**
   the run does nothing (the Envelope fit shrinks it to the hill), the separation gap after the
   fit does (x2 gives x1.8). No knob shortens below the separation floor (a full corridor
   width, the Z-corridor rule): at 0.5 built Graph reaches ~0.7, classic/city ~0.82, outdoor
   1.0; only cave tracks down to 0.5.

3. **Below 1, halls shorten as far as the separation floor allows** (the lead, 2026-11-25, at
   task 1). Rooms keep a full corridor width apart (Z-corridors need it), so at `HALL_MIN` built
   Graph reaches ~0.7, classic/city ~0.82, outdoor ~1.0; only caves track 0.5. Task 2's 15% bar
   applies at 1 and above; below 1 it reports the ratio reached. `HALL_MAX` 3.0 stands if task 4's
   draw time and the outdoor hill fit hold; else it comes down, by measurement.
4. **Outdoor dungeons stop at about 1.6x; `ai/expand.py` widened** (the lead, 2026-11-25, at
   task 2). The hill can't hold longer halls with full-size rooms: door-to-door p50 1.61x at both
   2 and 3 (1.28x at 30 rooms), no room dropped in 160 builds; accepted under the card's "as far
   as the hill allows". `plan_to_spec` in `ai/expand.py` is the plan's only way to the layouts, so
   its three-line pass-through is accepted outside task 2's Owns.
5. **Task 4's first run failed; fix the causes, keep the range** (the lead, 2026-11-25). Gate
   694 at 1 and 0.5, 690 at 3.0 (six cave graph seeds, three a long corridor with no headroom); 0.5
   pushes city/classic/moderate bands to 7.0%. Stock built zones reach 2.96x, so `HALL_MAX` stays
   3.0 and the failures are bugs long or short halls expose: task 8 fixes them, then task 4 re-runs.

## Follow-ups

- `ZONE_PLAN_JSON_SCHEMA` lacks `winding` and `hall_length` (the LLM planner reads the prompt line).
- WASD while the Hall length slider has focus, not checked.
- Outdoor halls stop at ~1.6x (1.21x on seed 731402518); outdoor doesn't shorten below 1.
- cave classic dramatic 21 s1866540615 still fails the gate at 1 (decor footprint_cut, pre-existing).
- Per-district hall length, a race per district, intruder districts and one-way drops: the
  user's ideas at the look, taken up as step 31.
- Check corridor headroom, risers and room crossings on the plan, before the mesh is built
  (the user's question at task 8: catch what the gate finds earlier, cut retries).
