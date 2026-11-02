# Design — zone-generator-outdoor-dungeon (roadmap step 5)

Written at master `a311b50`. Verify against the code before working a task.

## Overview

An outdoor-dungeon build composes what exists, with one new constraint (the
Envelope) and one new piece of geometry (the Entrance):

1. **Host_Terrain.** The wilderness pipeline (Design_Matrix → synth → bowl)
   at a smaller size, with the matrix asked for one Host_Hill (a raised
   region) the dungeon will sit under.
2. **Envelope.** From the hill's built heights: for each XY in the hill's
   footprint, the dungeon may occupy `z ∈ [floor_limit, surface(x, y) −
   Rock_Cover − room height]`. Expressed as a continuous predicate
   (`contains(box) -> bool`, `top_at(x, y)`), per the followup design's
   "continuous preferred".
3. **Layout inside the Envelope.** `LayoutGenerator.generate(envelope=…)`:
   TinyKeep scatter within the footprint, floor heights assigned within the
   Envelope's band, separation and elevation as today, every room and corridor
   checked against `contains`. Without an Envelope nothing changes.
4. **Entrance.** Pick a point on the hill's flank facing the Outdoor_Spawn;
   flatten an Apron into the heightfield there; route a Tunnel (an existing
   ramp corridor, grade-capped) from the Apron to the nearest room; cut the
   Mouth: remove the terrain triangles the Tunnel's opening passes through and
   close the gap between the Tunnel's portal and the slope with a headwall and
   jambs, so nothing can be fallen or seen through.
5. **One TER.** Terrain mesh (minus the Mouth) + box-backend dungeon mesh,
   materials from both (wilderness kit outdoors, step 4 recipes indoors).
6. **Gate.** `analyzer.traverse` on the merged TER from the Outdoor_Spawn:
   every room reached (through an Entrance), corridors continuous; the
   wilderness bowl and trunk checks on the open ground.

## Research findings

Measured at `a311b50` with a scratch probe over `F:\everquest_rof2`.

1. **Scale.** Spans (world units, X × Y): mistmoore 728×840, blackburrow
   603×886, unrest 980×680, highkeep 358×758, runnyeye 664×515, kaesora
   816×1455. Our wilderness is 2400×2400; our dungeons vary with room count.
2. **Height.** Upward-facing surfaces (p10 to p90) spread over roughly
   100–290 u: blackburrow −159 to 13, runnyeye −135 to 20, kaesora −272 to 16,
   mistmoore −238 to −140.
3. **Covered floor is NOT measured yet.** A simple test ("is there a surface
   8–250 u above this upward face?") is contaminated by faces nobody walks on:
   sky planes (eastkarana at z 939, qeytoqrg at 516), roof tops and the outer
   backs of dungeon shells. It gave befallen, an indoor dungeon, 9.6 %
   covered. Task 1 replaces it with a walk from the safe point, which keeps
   only real floor.
4. **The runway exists on paper.** The retired `zone-generator-followup`
   design specifies typed edges (`floor | staircase | bridge | shaft`), a 3D
   `Envelope` with `envelope=None` reproducing today, and a gate that learns
   connectors with rise/run and headroom rules. Step 5 needs the Envelope and
   ramp connectors through it; staircases are Open question 5.

## Envelope (`generators/envelope.py`)

```
@dataclass(frozen=True)
class Envelope:
    footprint: Polygon (XY)          # the Host_Hill's area
    floor_limit: float               # lowest floor allowed
    surface: Callable[[x, y], float] # terrain height
    rock_cover: float
    def top_at(x, y) -> float        # surface(x, y) - rock_cover
    def contains_box(x0, y0, z0, x1, y1, z1) -> bool
        # footprint covers the box, z0 >= floor_limit,
        # z1 <= min(top_at) over the box's footprint (sampled at 8 u)
```

`LayoutGenerator.generate(envelope=None)` threads it: `_scatter_rooms` samples
inside the footprint; elevation assignment clamps each room's floor so its box
fits; `_build_corridors` rejects or re-routes a corridor whose swept box leaves
the Envelope (the existing crossing and conflict resolvers apply). Rooms that
cannot fit are dropped down to a minimum of 3 (`rooms_reduced`).

## Host terrain

The Design_Matrix gains an optional `host_hill` request: one connected region
of raised `hills` cells near the bowl's middle, at least the Envelope's
footprint plus a margin, with the Outdoor_Spawn's region on the side the
Entrance will face. Size (Open question 2) scales the matrix grid; the bowl,
rim, water and lava rules are unchanged.

## Entrance

- **Apron:** a disc on the flank, heights blended to the mouth floor with the
  wilderness's smooth falloff, grade ≤ the walkable slope.
- **Tunnel:** a ramp corridor (`geometry._add_ramp_corridor`, subdivided per
  lessons-learned) from the Apron edge to the first room's wall opening, its
  rise confined to one leg as today.
- **Mouth:** drop the terrain triangles whose XY lies inside the Tunnel's
  portal rectangle and above its floor; add a headwall (the terrain face above
  the portal, down to the Tunnel ceiling) and two jambs (portal sides to the
  slope), all collidable, using the cliff material.
- **Check:** the Mouth is watertight to the walk agent: no path from the
  Apron or the Tunnel falls out of the mesh, and the Tunnel's floor meets the
  Apron flush.

## Correctness properties

| P | Statement | Reqs |
|---|-----------|------|
| D1 | Without an Envelope, layouts are byte-identical to today | 2.2 |
| D2 | Every room and corridor box lies inside the Envelope | 2.1, 4.3 |
| D3 | Terrain heights equal the plain Host_Terrain everywhere outside the Apron and Mouth | 3.3 |
| D4 | Every room is reachable from the Outdoor_Spawn on the merged TER, through an Entrance | 4, 5.2 |
| D5 | The Tunnel floor meets the Apron flush; no walkable path leaves the mesh at the Mouth | 4.1 |
| D6 | Same inputs, same `.eqg` contents | 8.2 |
| D7 | Dungeon, city and wilderness builds unchanged | 8.1 |

## Risks

- **The Mouth is the hard part.** Stitching a box tunnel to a heightfield
  without cracks is new geometry; a spike task (task 5) proves it and gets a
  human look before the rest is built on it.
- **Fit.** A small hill may not hold many rooms; the layout drops rooms rather
  than fail, and the sidecar says so.
- **Gate cost.** The merged TER is larger than either part; the walk must stay
  inside the 60 s budget (wilderness gates take ~1 s today).

## Open questions (answered 2026-11-01; see `archive.md`)

1. **First archetype.** Default: a hillside cave (Blackburrow, Runnyeye):
   tunnels and rooms under a hill, one or more cave mouths in its flank.
   Alternative: a surface structure over catacombs (Mistmoore, Unrest), which
   needs buildings on terrain first.
2. **Zone size.** Default: compact, about 1200 u square (the classic outdoor
   dungeons are 360–980 u on a side, and a hill plus approach needs room).
   Alternatives: the measured classic range (~800 u), or wilderness size
   (2400 u).
3. **Entrances.** Default: one. Alternative: one to three, each a separate
   Apron, Mouth and Tunnel.
4. **How it's chosen.** Default: a new `outdoor_dungeon` zone type.
   Alternative: a dungeon option ("setting: outdoor") so any dungeon can be
   put in a hill.
5. **Connectors.** Default: ramps only (walkable by construction, as today).
   Alternative: staircases now, with the gate learning rise/run and headroom
   (the followup's F4), which step 7 needs anyway.

## Decisions

1. Compose existing pipelines; the only new geometry is the Entrance.
2. The Envelope is a continuous predicate, and `envelope=None` reproduces
   today exactly.
3. One TER for collision; advisory data (Entrances, Envelope) in the sidecar.
4. Measure the classic anatomy first (task 1) and set defaults from it.
