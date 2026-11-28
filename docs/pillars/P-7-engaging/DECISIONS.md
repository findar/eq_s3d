# P-7 Engaging every time — decisions

Terms in capitals are defined in the [glossary](../../ARCHITECTURE.md#glossary).

Umbrella decision numbers link to the umbrella design's
[Decisions Made in This Revision](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision).

## Umbrella decisions

| # | Decision | In short |
|---|---|---|
| [7](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | Quality is soft, traversability hard | Quality checked before building and redrawn cheaply; on exhaustion the best walkable candidate is returned, degraded |
| [9](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | Districts are cut from a breadth-first tree of the room graph | Contiguity and one Threshold per pair by construction |
| [10](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | Topology control is in; multi-level and one-way are follow-ons | Topology was never built ([P-7-1](OPEN.md#p-7-1)); multi-level landed in [step 7](../../../.kiro/specs/zone-generator-dungeon-verticality/tasks.md), one-way drops in [step 31](../../../.kiro/specs/zone-generator-district-races/tasks.md) |
| [14](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | Degraded quality is always visible | One `quality_summary` shape in responses and sidecar; a banner with no close button |
| [25](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 5](../../../.kiro/specs/zone-generator-outdoor-dungeon/tasks.md): the `outdoor_dungeon` zone type and the 3D Envelope | A Host_Hill Landform, one Entrance, dungeon and wilderness controls together |
| [26](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 6](../../../.kiro/specs/zone-generator-graph-layout/tasks.md): the `LayoutEngine` seam and the Graph engine, made the default | TOML rule sets; [ZG-Req-32.1](../../../.kiro/specs/zone-generator/requirements.md#requirement-32-settled-design-constraints) (TinyKeep) holds for the Classic layout only; no locks in the grammar |
| [27](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 7](../../../.kiro/specs/zone-generator-dungeon-verticality/tasks.md): Levels, stairs, Bridges; stock scale from body height H | Replaces the race multiplier; changed every room-graph build once |
| [29](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 9](../../../.kiro/specs/zone-generator-room-layouts/tasks.md): Features in rooms; what a room is like in the rules | Scales Finish, Structure, Clutter; Transitions; the line with [step 11](../../../.kiro/specs/zone-generator-room-decor/tasks.md)'s Props |
| [30](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 10](../../../.kiro/specs/zone-generator-wilderness-pois/tasks.md): Sites in the wilderness | Structures as ZON objects on unchanged ground; the gate learns Footprints first |
| [33](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 13](../../../.kiro/specs/zone-generator-site-sockets/tasks.md): Sites on point Sockets | Groups as stock hamlets cluster; keep the dungeon under the hill clear, not the whole hill |
| [38](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 19](../../../.kiro/specs/zone-generator-quality/tasks.md): the quality gate | Bands from the generator's own output, one-sided, at most 1% of Draws failing; rebuilds and edits measured, not redrawn |
| [39](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 20](../../../.kiro/specs/zone-generator-districts/tasks.md): Districts | Off by default; dungeons only; 11 Purposes; partition before pacing |
| [41](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 22](../../../.kiro/specs/zone-generator-district-looks/tasks.md): District looks | Scales and decor follow the District's Purpose; untouched zones byte-identical |
| [45](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 27](../../../.kiro/specs/zone-generator-random-placement/tasks.md): random placement and room-size spread | Built and hewn keep the lattice (the user's choice); caves at any bearing |
| [47](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 30](../../../.kiro/specs/zone-generator-hall-length/tasks.md): Hall length | 0.5–3.0; outdoor stops at ~1.6× on its hill |
| [48](../../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) | [Step 31](../../../.kiro/specs/zone-generator-district-races/tasks.md): District races, intrusion, drops | Links sized by the smaller race; drops one-way, never the only way back; map layers |

## Slice decisions

Each slice's `archive.md` "Decisions" (steps [5](../../../.kiro/specs/zone-generator-outdoor-dungeon/tasks.md), [6](../../../.kiro/specs/zone-generator-graph-layout/tasks.md), [7](../../../.kiro/specs/zone-generator-dungeon-verticality/tasks.md), [9](../../../.kiro/specs/zone-generator-room-layouts/tasks.md), [10](../../../.kiro/specs/zone-generator-wilderness-pois/tasks.md), [13](../../../.kiro/specs/zone-generator-site-sockets/tasks.md), [19](../../../.kiro/specs/zone-generator-quality/tasks.md), [20](../../../.kiro/specs/zone-generator-districts/tasks.md), [22](../../../.kiro/specs/zone-generator-district-looks/tasks.md), [27](../../../.kiro/specs/zone-generator-random-placement/tasks.md), [30](../../../.kiro/specs/zone-generator-hall-length/tasks.md), [31](../../../.kiro/specs/zone-generator-district-races/tasks.md) and [32](../../../.kiro/specs/zone-generator-races-followups/tasks.md), in that order): [outdoor-dungeon](../../../.kiro/specs/zone-generator-outdoor-dungeon/archive.md),
[graph-layout](../../../.kiro/specs/zone-generator-graph-layout/archive.md),
[dungeon-verticality](../../../.kiro/specs/zone-generator-dungeon-verticality/archive.md),
[room-layouts](../../../.kiro/specs/zone-generator-room-layouts/archive.md),
[wilderness-pois](../../../.kiro/specs/zone-generator-wilderness-pois/archive.md),
[site-sockets](../../../.kiro/specs/zone-generator-site-sockets/archive.md),
[quality](../../../.kiro/specs/zone-generator-quality/archive.md),
[districts](../../../.kiro/specs/zone-generator-districts/archive.md),
[district-looks](../../../.kiro/specs/zone-generator-district-looks/archive.md),
[random-placement](../../../.kiro/specs/zone-generator-random-placement/archive.md),
[hall-length](../../../.kiro/specs/zone-generator-hall-length/archive.md),
[district-races](../../../.kiro/specs/zone-generator-district-races/archive.md),
[races-followups](../../../.kiro/specs/zone-generator-races-followups/archive.md).

## Settled (don't relitigate)

- TinyKeep over binary space partitioning, wave function collapse, prefabs, a pure random walk
  and grid rule-tiles ([ROADMAP "NOT doing"](../../../ROADMAP.md#deliberately-not-doing-and-why)).
- Pacing is analytical (read off the room graph), not a mission-graph grammar.
- Gating adopted only the solvability invariant; multi-key fragments are not needed.
- Gates and pacing are suggestions; they never alter geometry or collision.
