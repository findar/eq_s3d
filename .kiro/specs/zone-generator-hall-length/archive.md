# Archive — zone-generator-hall-length

## What landed

| Tasks | What landed | Commits |
|---|---|---|

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

## Follow-ups
