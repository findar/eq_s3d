# Requirements Document

> **STATUS: roadmap step 22, DONE (closed 2026-11-20; first look skipped at the user's word).** Drafted 2026-11-20 at master `b11764b`. After step 21 the
> user said "Pick the next step yourself". Multi-zone worlds still wait on the user's design
> review. The lead chose the "district look", carried as a follow-up since step 6: stock zones mix
> built and cave parts, but today a District takes District 0's walls and decor. The step also
> fixes the cave dressing follow-ups from step 21. The user confirms the choice at the first look
> (task 7). Task index: `tasks.md` (card format). Decisions: `archive.md`.

## Introduction

Step 20 gave each District its own Purpose, palette, light and climax. Two things still follow
the zone's single Purpose (`spec.dungeon_theme`, which is District 0's):

- **Room Scales** (`generators/room_scales.py` `draw_room_scales`). Finish picks the wall style, so
  a cave District after a fortress District gets built walls. A fortress District after a cave
  District gets rough walls.
- **Decor layers** (`generators/builder.py` `decor_layers_of`). Every room takes District 0's
  layer, so a cave District's crystal grotto gets benches and banners.

Step 21's first builds also showed four cave problems:
- warm orange light in `warren`, `collapsed_gallery` and `passage` rooms inside a cave;
- wall torches;
- the shared treasure dressing (chests, urns);
- ceilings about 12% lower than with no profile, although measured caves are taller than
  dungeons.

## Amendments

- **A1: A room's look follows its District's Purpose.** In a multi-District zone, a room's Scales
  layer is its own `room_theme` and so is its decor layer. Corridors take the layer of the room
  they leave (`from_room`). A Threshold corridor therefore takes the outer District's look. A
  one-District zone's rooms all have `room_theme == dungeon_theme`, so nothing changes for it.
- **A2: Cave rooms are lit cold and dressed as caves.** In a `cave` Purpose room, a Room_Type that
  carries `_WARM` light takes the cave light instead. The `cave` decor layer weighs out wall
  torches and the treasure dressing. Other Purposes keep the same Room_Types' warm light.
- **A3: The cave profile keeps its ceilings.** The Size shift from `styles/cave.json` changes a
  cave's footprints and leaves its room heights as they were with no profile.
- **A4: Bytes.**
  - A zone with no Districts whose Purpose isn't `cave` stays byte-identical.
  - Districted zones and `cave` zones may change. Each golden that moves is recaptured in its
    own commit, which names it.

## Glossary

- **Byte check:** `python -m pytest tests/test_layout_engine.py tests/test_site_builds.py
  tests/test_decor_builds.py tests/test_partial_rebuild.py -q`.
- **District look:** a room's wall style (from its Finish) and its decor layer.

## Requirements

### Requirement 1: Walls per District
1. In a multi-District dungeon, each room draws its Scales from its own District's Purpose layer
   (`[themes.<purpose>]` in `rules/rooms/scales.toml`).
2. A cave District draws mostly `rough` walls whichever District comes first. A built Purpose's
   District draws no `rough` walls when it follows a cave District.

### Requirement 2: Decor per District
1. In a multi-District dungeon, each room's Decor uses its District Purpose's decor layers.
   Corridors use their `from_room`'s.
2. The sidecar's decor record names the layers per District.

### Requirement 3: Cave dressing
1. A `cave` room's light is never `_WARM`.
2. `cave` builds place no wall torches and no treasure dressing.

### Requirement 4: Cave ceilings
1. A `cave` zone's room heights match the same seed with no profile, within the race band.

### Requirement 5: Navigable and in band
1. Districted dungeons, including ones with a `cave` District, pass the traversability gate on
   both layouts with 8–30 rooms.
2. Their quality fail share stays inside today's bands.

### Requirement 6: Bytes
The byte check passes. Any golden that moves is named (A4).
