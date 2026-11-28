# P-2 Traversable — plan

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

## Goal

Every zone the tool hands over is walkable end to end by an EQ-scale player (slope at most 40°,
step-up at most 3 u), proven on the real mesh, not on the room graph. A zone that strands a room is
never shown; it is drawn again.

## Scope

- The walk gate ([`analyzer/traverse.py`](../../../analyzer/traverse.py), [`analyzer/footprints.py`](../../../analyzer/footprints.py)) and its place in the
  pipeline ([`generators/pipeline.py`](../../../generators/pipeline.py): retries, blame, budget, failure log).
- What makes geometry walkable: corridor routing and openings ([`generators/routing.py`](../../../generators/routing.py),
  [`generators/geometry.py`](../../../generators/geometry.py)), elevation and its grade cap ([`generators/layout.py`](../../../generators/layout.py)), stairs,
  bridges, drops.
- Zone-type availability, as far as the gate decides it ([ZG-Req-3](../../../.kiro/specs/zone-generator/requirements.md#requirement-3-zone-type-availability), shared with P-1).
- Catching failures earlier than the mesh ([step 33](../../../.kiro/specs/zone-generator-layout-repair/tasks.md)'s plan check).

## Non-goals

- How a room looks (P-5) or how the layout is composed (P-7); this pillar only says whether a
  player can walk it.
- An automated in-client walk (needs a running EQEmu server; [umbrella decision 4](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision)).
- Ceiling headroom over every standable face ([umbrella Known Limitation 10](../../../.kiro/specs/zone-generator/design.md#known-limitations-as-built-findings-with-the-milestone-that-resolves-them); see [P-2-1](OPEN.md#p-2-1)).

## Requirements

| ID | Requirement | Parent | Status now |
|---|---|---|---|
| <a id="p-2-req-1"></a>P-2-Req-1 | The walk gate runs on every zone type | [ZG-Req-4](../../../.kiro/specs/zone-generator/requirements.md#requirement-4-traversability-gate) | Built for all four types: room-based types by the mesh walk, landscapes by the bowl gate plus the outdoor dungeon's rooms |
| <a id="p-2-req-2"></a>P-2-Req-2 | Corridors meet rooms flush and climb at walkable grades | [ZG-Req-5](../../../.kiro/specs/zone-generator/requirements.md#requirement-5-walkable-connections) | Built: one router (straight, Z or L route), a grade cap of 0.5, ramps split into rises of at most 2.5 u, stairs with risers of at most 2 u, Bridges, one-way drops |
| <a id="p-2-req-3"></a>P-2-Req-3 | Wilderness terrain lines up with the zone (the umbrella asked for rooms on pads in the room graph's frame) | [ZG-Req-6](../../../.kiro/specs/zone-generator/requirements.md#requirement-6-wilderness-terrain-alignment) | Superseded: laying the room graph over terrain was rejected in [M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) wave 3. A wilderness is an open landscape with its own bowl gate ([step 1](../../../.kiro/specs/zone-generator-wilderness/tasks.md)). [Umbrella decision 42](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) amended the parent for winding corridors |
| <a id="p-2-req-4"></a>P-2-Req-4 | A natural geometry style for dungeons that stays one connected walkable space | [ZG-Req-7](../../../.kiro/specs/zone-generator/requirements.md#requirement-7-natural-geometry-style-for-dungeons) | Served differently: the `rough` wall style ([step 8](../../../.kiro/specs/zone-generator-room-walls/tasks.md), [umbrella decision 28](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision)) and the `cave` Purpose ([step 21](../../../.kiro/specs/zone-generator-cave/tasks.md)). The [M5](../../../.kiro/specs/zone-generator/design.md#delivery-plan) `natural.py` transform was never built and is superseded |

This pillar shares [ZG-Req-3](../../../.kiro/specs/zone-generator/requirements.md#requirement-3-zone-type-availability) (only zone types that pass the gate are offered) with P-1, which
holds it as [P-1-Req-3](../P-1-web-app/PLAN.md#p-1-req-3).

## Traceability

Which slices served each requirement. ([`scripts/task_status.py`](../../../scripts/task_status.py)
will generate this table after [project-docs task 5](../../../.kiro/specs/project-docs/cards/05-tooling.md).)

| Requirement | Served by |
|---|---|
| [P-2-Req-1](#p-2-req-1) | [M0](../../../.kiro/specs/zone-generator-m0-hygiene/tasks.md) (the gate made sound), [M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) (the gate on every enabled type), steps [1](../../../.kiro/specs/zone-generator-wilderness/tasks.md) and [5](../../../.kiro/specs/zone-generator-outdoor-dungeon/tasks.md) (the bowl gate), steps [7](../../../.kiro/specs/zone-generator-dungeon-verticality/tasks.md), [8](../../../.kiro/specs/zone-generator-room-walls/tasks.md), [9](../../../.kiro/specs/zone-generator-room-layouts/tasks.md), [10](../../../.kiro/specs/zone-generator-wilderness-pois/tasks.md) and [11](../../../.kiro/specs/zone-generator-room-decor/tasks.md) (the gate learns each new kind of geometry), [step 28](../../../.kiro/specs/test-speed/tasks.md) (the gate's speed) |
| [P-2-Req-2](#p-2-req-2) | [M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) (one router, corridor continuity), [step 7](../../../.kiro/specs/zone-generator-dungeon-verticality/tasks.md) (stairs and Bridges), steps [23](../../../.kiro/specs/zone-generator-winding-tunnels/tasks.md) and [25](../../../.kiro/specs/zone-generator-winding-routes/tasks.md) (winding), [step 31](../../../.kiro/specs/zone-generator-district-races/tasks.md) (drops), [step 33](../../../.kiro/specs/zone-generator-layout-repair/tasks.md) (in progress) |
| [P-2-Req-3](#p-2-req-3) | [M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) wave 3 (rejected the drape), [step 1](../../../.kiro/specs/zone-generator-wilderness/tasks.md) (the landscape) |
| [P-2-Req-4](#p-2-req-4) | [step 8](../../../.kiro/specs/zone-generator-room-walls/tasks.md) (the `rough` wall style), [step 21](../../../.kiro/specs/zone-generator-cave/tasks.md) (the `cave` Purpose) |

## Slices

| Step | Spec | Status | Commits | What it did |
|---|---|---|---|---|
| Phase 2 and 2.5 (pre-spec, [ROADMAP](../../../ROADMAP.md#phase-2--25--procedural-geometry--elevation)) | — | done | (before specs) | Box rooms and corridors; elevation, ramps and stairs |
| Organic caves (pre-spec, [ROADMAP](../../../ROADMAP.md#organic-caves--features-removed-in-m0)) | — | removed in [M0](../../../.kiro/specs/zone-generator-m0-hygiene/tasks.md) | (before specs) | A cave pipeline built from signed distance fields (SDF); rendered as disconnected blobs |
| [M1](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) | [`zone-generator-m1-controls-traversability`](../../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) | done except the human walk (M1 task 22.5) | 133 | 30-room connectivity, one router, corridor continuity and conflict checks, backend registry, the gate on every enabled type, modes and controls (P-1), Build_Name and the format gate (P-3) |
| 33 | [`zone-generator-layout-repair`](../../../.kiro/specs/zone-generator-layout-repair/tasks.md) | in progress | 1 | Measure where a generate's time goes; check the plan before the mesh; repair locally |

Also served by: [M0](../../../.kiro/specs/zone-generator-m0-hygiene/tasks.md) (the gate's adjacency made sound; filed under P-9), [step 7](../../../.kiro/specs/zone-generator-dungeon-verticality/tasks.md) (the gate
learns stairs and bridges and stands on floors only; P-7), [step 8](../../../.kiro/specs/zone-generator-room-walls/tasks.md) (Outline floors and Throats;
P-5), [step 9](../../../.kiro/specs/zone-generator-room-layouts/tasks.md) (Features and Transitions; P-7), [step 10](../../../.kiro/specs/zone-generator-wilderness-pois/tasks.md) (Footprints of placed models; P-7),
[step 11](../../../.kiro/specs/zone-generator-room-decor/tasks.md) (placed Props; P-5), [step 16](../../../.kiro/specs/zone-generator-partial-rebuild/tasks.md) (the partial gate against a kept shell; P-6), [step 28](../../../.kiro/specs/test-speed/tasks.md) (the
gate's hot loops on arrays; P-9), [step 31](../../../.kiro/specs/zone-generator-district-races/tasks.md) (one-way drops, strong connectivity; P-7).

The gate learns each new kind of geometry before any generator makes it; that rule is why most
of this pillar's work sits inside other pillars' slices.
