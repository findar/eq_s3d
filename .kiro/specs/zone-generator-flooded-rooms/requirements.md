# Requirements Document

> **STATUS: roadmap step 24, DONE (closed 2026-11-21; the look skipped at the user's word).** Drafted 2026-11-20 at master `1897d62`. At the step 23
> first look the user said: "a flooded room just has a square of water in the middle so that's
> something we should address", then "Yes, fix it". Task index: `tasks.md` (card format).
> Decisions: `archive.md`.

## Introduction

A room whose Room_Type floods it (`flooded_gallery`, `sump`: `RoomType.region == "water"`) got
one water region, a box 0.76 of the room's width and depth, centred, and no visible water at
all. The viewer draws a region as a translucent box, so a flooded room showed a square of water
in its middle whatever the room's shape.

## Requirements

1. **Water fills the room.** A flooded room has a visible, flat water surface at one water line
   over its whole floor: each Outline Cell of a shaped room, the floor rectangle of a box room.
   It meets every wall; floor relief above the line stands out of it.
2. **It can be walked through.** The surface is non-collidable (`FLAG_PASSABLE`) and uses the
   `liquid_water` material (alpha shader), so the walk gate and the map never stand on it.
3. **The water region matches the water.** The room's `AWT` region covers the room's footprint
   from just under its floor to the water line, on the room's final floor height. The mesh
   reads the water line from that region (realised content), never from the Room_Type, which
   is advisory: clearing advisory data leaves the mesh unchanged (M0 Property 14).
6. **The gate reads only solid faces.** The outline, feature, transition and corridor checks
   that read walls and seams from the mesh skip non-collidable faces, as the walk surface
   already does (`WalkSurface.solid`).
4. **Shallow.** The water line stands `FLOOD_DEPTH_H` = 0.6 H over the floor (3.6 u for a
   human). The water ends at each doorway, so a deep pool would show a wall of water there.
5. **Bytes.** A zone with no flooded room stays byte-identical. Lava rooms (`forge`) keep their
   region as it is.
