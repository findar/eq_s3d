# P-B Traversable — plan

## Goal

Every zone the tool hands over is walkable end to end by an EQ-scale player (slope ≤ 40°,
step-up ≤ 3 u), proven on the real mesh, not on the room graph. A zone that strands a room is
never shown; it is drawn again.

## Scope

- The walk gate (`analyzer/traverse.py`, `analyzer/footprints.py`) and its place in the
  pipeline (`generators/pipeline.py`: retries, blame, budget, failure log).
- What makes geometry walkable: corridor routing and openings (`generators/routing.py`,
  `generators/geometry.py`), elevation and its grade cap (`generators/layout.py`), stairs,
  bridges, drops.
- Zone-type availability as far as the gate decides it (Req 3 is shared with P-A).
- Catching failures earlier than the mesh (step 33's plan check).

## Non-goals

- How a room looks (P-E) or how the layout is composed (P-G); this pillar only says whether a
  player can walk it.
- An automated in-client walk (needs a running EQEmu server; umbrella decision 4).
- Ceiling headroom over every standable face (umbrella Known Limitation 10; see OPEN B-1).

## Requirements (umbrella IDs)

| ID | Requirement | Status now |
|---|---|---|
| P-B.4 | Traversability gate on every zone type | Built for all four types: room types by the mesh walk, landscapes by the bowl gate plus the outdoor dungeon's rooms |
| P-B.5 | Walkable connections: corridors meet rooms flush and climb at walkable grades | Built: one router (straight, Z, L), grade cap 0.5, ramps split into ≤ 2.5 u rises, stairs with ≤ 2 u risers, Bridges, one-way drops |
| P-B.6 | Wilderness terrain alignment (rooms on pads in the room-graph frame) | Superseded: the room-graph drape was rejected in M1 wave 3; wilderness is an open landscape with its own bowl gate (step 1); 6.6 amended by decision 42 for winding corridors |
| P-B.7 | Natural geometry style for dungeons, still one connected walkable space | Served differently: the `rough` wall style (step 8, decision 28) and the `cave` Purpose (step 21); the M5 `natural.py` transform was never built and is superseded |
| P-B.3 | Zone type availability tied to the gate (shared with P-A) | Built |

## Slices

| Step | Spec | Status | Commits | What it did |
|---|---|---|---|---|
| Phase 2 / 2.5 (pre-spec) | — | done | (pre-spec) | Box rooms and corridors; elevation, ramps and stairs |
| Organic caves (pre-spec) | — | removed in M0 | (pre-spec) | SDF cave pipeline; rendered as disconnected blobs |
| M1 | [`zone-generator-m1-controls-traversability`](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) | done except the human walk (22.5) | 133 | 30-room connectivity, one router, corridor continuity and conflict checks, backend registry, the gate on every enabled type, modes and controls (P-A), Build_Name and the format gate (P-C) |
| 33 | [`zone-generator-layout-repair`](../../../.kiro/specs/zone-generator-layout-repair/tasks.md) | in progress | 1 | Measure where a generate's time goes; check the plan before the mesh; repair locally |

Also served by: M0 (the gate's adjacency made sound; filed under Engineering), step 7 (the gate
learns stairs and bridges and stands on floors only; P-G), step 8 (Outline floors and Throats;
P-E), step 9 (Features and Transitions; P-G), step 10 (Footprints of placed models; P-G),
step 11 (placed Props; P-E), step 16 (the partial gate against a kept shell; P-F), step 28 (the
gate's hot loops on arrays; Engineering), step 31 (one-way drops, strong connectivity; P-G).

The gate learns each new kind of geometry before any generator makes it; that rule is why most
of this pillar's work sits inside other pillars' slices.
