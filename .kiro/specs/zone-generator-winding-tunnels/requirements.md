# Requirements Document

> **STATUS: roadmap step 23, DONE (closed 2026-11-20; the user's first look: "looks good").** Drafted 2026-11-20 at master `b2db7b4`. After step 22 the
> user said "Pick the step yourself". Multi-zone worlds still wait on the user's design review.
> The lead chose winding tunnels. Angled corridors have been "wanted" since M1, and the north
> star asks for natural geometry. A cave's corridors are its last straight boxes: their walls
> already wobble (`corridor_break`), but every leg still runs dead straight along X or Y. The
> user confirms the choice at the first look (task 7). Task index: `tasks.md` (card format).
> Decisions: `archive.md`.

## Introduction

Stock cave zones (Blackburrow, Runnyeye, Crystal Caverns, Solusek's Eye) join their chambers by
tunnels that bend at any angle. Our corridors follow `generators/routing.py`'s routes. A route is
straight, Z, L or U, and each of its legs is axis-aligned. A rough corridor (`CorridorSpec.rough >
0`, from the `rough` wall style's `corridor_break`) only pulls its walls in, so its floor is still
a straight strip.

This step makes a rough corridor's floor wind. Each plain leg becomes a polyline of short
segments that wanders sideways inside the free space around the leg. The two ends stay square
where the leg meets a room or a bend. The layout is not touched: routes, footprints, conflict
checks and Levels stay as they are. Winding happens at dressing time, inside clearance measured
from the finished spec. Only a rough corridor's mesh and the things read from it change.

## Amendments to the umbrella

- **A1: Rough corridors wind.** This amends Requirement 6.6 and the routing design's
  "axis-aligned legs". A plain leg (no steps, no bridge) of a corridor with `rough > 0` is built
  along a winding centreline. Its route, footprint and openings stay axis-aligned, so placement,
  conflicts, the Envelope and Levels are unchanged. Stairs, bridges and non-rough corridors stay
  straight.
- **A2: Wind only into free space.** A leg's sideways wander is bounded by its clearance: the
  distance to every other room Box, corridor footprint and Level's floor in plan, less the
  player's half-width. A leg with no clearance stays straight.
- **A3: Measured, not invented.** Segment length, bend angle and wander come from a stock tunnel
  survey (task 1). They sit in `rules/walls/rough.toml` under `[tunnel]`, and the survey's
  numbers are recorded in `archive.md`.
- **A4: Bytes.** A zone with no rough corridor stays byte-identical. A zone with rough corridors
  changes its mesh, decor in those corridors, map lines and the sidecar's corridor record. Each
  golden that moves is recaptured in its own commit, which names it.

## Glossary

- **Plain leg:** one leg of a corridor's route that has no steps and is not a bridge.
- **Wander:** the sideways offset of a winding centreline from the leg's straight centreline.
- **Byte check:** `python -m pytest tests/test_layout_engine.py tests/test_site_builds.py
  tests/test_decor_builds.py tests/test_partial_rebuild.py -q`.

## Requirements

### Requirement 1: Stock tunnel survey
1. Measure the tunnels of at least five stock cave zones: segment length, bend angle, sideways
   wander against the tunnel's span, and width. Report the medians and p10–p90.

### Requirement 2: The winding centreline
1. `routing.wind_leg` gives a deterministic polyline for a plain leg, from a seed, the leg, its
   half-width, its clearance and the `[tunnel]` rules.
2. Each turn is at most the surveyed maximum. The first and last stretch, at least the
   half-width long, run along the leg's axis. The whole strip, centreline ± half-width, stays
   inside the leg's clearance.
3. The floor's heights along the leg are the leg's own (a ramp stays a ramp, every rise within
   `MAX_SEG_RISE`).

### Requirement 3: The mesh
1. A winding leg is built as a floor strip, walls with the rough wobble, and a ceiling. It welds
   to the square ends and bends exactly.
2. The traversability gate passes every winding corridor.

### Requirement 4: What reads the corridor
1. Corridor RoomContexts (decor) rasterise the winding floor and walls, so no Prop stands in a
   wall or blocks the way.
2. The map outline and the EQ map lines follow the tunnel's walls.

### Requirement 5: Navigable and in band
1. Rough-walled dungeons, on the graph layout and in cave and warren zones, pass the gate with
   8–30 rooms at each verticality.
2. Their quality fail share stays inside today's bands.

### Requirement 6: Bytes
The byte check passes, and any golden that moves is named (A4).
