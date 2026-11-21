# Requirements Document

> **STATUS: roadmap step 25, ready.** Drafted 2026-11-21 at master `169e985`. After step 24 the
> user said "continue ... keep working". The lead chose winding routes, the first follow-up step 23
> left (its archive decision 6): each straight leg of a rough corridor winds alone, so a Z
> corridor's ramp, which sits on its short middle jog, never winds, every bend is still a square
> 90° turn, and cave rooms had to stand about twice as far apart as stock for legs to be long
> enough to bend. Task index: `tasks.md` (card format). Decisions: `archive.md`.

## Introduction

A rough corridor's route is straight, Z, L or U, with axis-aligned legs. Step 23 winds each plain
leg on its own, between square ends that weld to a bend square or a room opening. This step winds
the route as ONE centreline from opening to opening: it leaves each room straight, cuts its bends
as turns no sharper than the tunnel's `max_turn`, wanders along the way, and carries any rise
along its whole length. The layout is still not touched.

## Amendments to the umbrella (on top of step 23's A1–A4)

- **A1: A rough corridor winds door to door.** Where a rough corridor's whole route can wind, one
  centreline replaces its legs and bend squares in the mesh, decor, map and gate. Its route,
  footprint, openings and Levels stay as they are, so placement and conflicts are unchanged.
  Stairs, bridges, a corridor holding a Transition line, and routes that fail the clearance check
  keep step 23's per-leg winding.
- **A2: Only into measured free space.** The route's strip (centreline ± half-width, mitres
  included) keeps at least the player's half-width from every room box and every other corridor's
  boxes that overlap it in Z, checked exactly against the finished spec. A route that fails falls
  back to step 23's legs.
- **A3: Recorded in the spec.** The chosen centreline is stored on the corridor
  (`CorridorSpec.path`, written only when set), so the mesh, decor, map and gate read one line and
  none re-measures the clearance.
- **A4: Bytes.** A zone with no rough corridor stays byte-identical.

## Requirements

1. **The route line.** `routing.wind_route` gives a centreline from opening A to opening B: a
   straight run-out of `max(hw, end)` from each opening, perpendicular to its wall; bends cut as
   turns of at most `max_turn` each; segments `segment` long; a wander of at most `wander` × span.
   Pure and seeded per corridor.
2. **The clearance check.** `transitions.measure_winds` keeps a route line only when A2 holds and
   stores it in `CorridorSpec.path`; else per-leg `wind` as in step 23.
3. **The mesh.** `_emit_route` builds a corridor with a `path` as one winding strip from opening
   to opening, its rise spread over the path between the two run-outs, every piece within
   `MAX_SEG_RISE` (lessons-learned "A ramp must be SUBDIVIDED"); its ends weld to the openings.
4. **The readers.** Decor RoomContexts, the map line and outline, and the gate's
   `corridor_continuity` read `path`.
5. **Stock length again.** With routes winding, the cave run factor is re-measured: the lowest
   factor that keeps at least half of cave rough corridors winding, compared with the plain stock
   tunnels (step 23 decision 6: plain p75 163 u door to door).
6. **Gate and bands.** Cave and warren sweeps pass the gate at master's count before this step or
   better; fail shares stay in the bands.
