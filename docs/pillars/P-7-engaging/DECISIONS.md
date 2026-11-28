# P-G Engaging every time — decisions

## Umbrella decisions

| # | Decision | In short |
|---|---|---|
| 7 | Quality is soft, traversability hard | Quality checked before building and redrawn cheaply; on exhaustion the best walkable candidate is returned, degraded |
| 9 | Districts use a BFS-tree cut | Contiguity and one Threshold per pair by construction |
| 10 | Topology control is in; multi-level and one-way are follow-ons | Topology was never built (OPEN G-1); multi-level landed in step 7, one-way drops in step 31 |
| 14 | Degraded quality is always visible | One `quality_summary` shape in responses and sidecar; a banner with no close button |
| 25 | Step 5: the `outdoor_dungeon` zone type and the 3D Envelope | A Host_Hill Landform, one Entrance, dungeon and wilderness controls together |
| 26 | Step 6: the `LayoutEngine` seam and the Graph engine, made the default | TOML rule sets; Req 32.1 (TinyKeep) holds for Classic only; no locks in the grammar |
| 27 | Step 7: Levels, stairs, Bridges; stock scale from body height H | Replaces the race multiplier; changed every room-graph build once |
| 29 | Step 9: Features in rooms; what a room is like in the rules | Scales Finish, Structure, Clutter; Transitions; the line with step 11's Props |
| 30 | Step 10: Sites in the wilderness | Structures as ZON objects on unchanged ground; the gate learns Footprints first |
| 33 | Step 13: Sites on point Sockets | Groups as stock hamlets cluster; keep the dungeon under the hill clear, not the whole hill |
| 38 | Step 19: the quality gate | Bands from the generator's own output, one-sided, ≤ 1% failing; rebuilds and edits measured, not redrawn |
| 39 | Step 20: Districts | Off by default; dungeons only; 11 Purposes; partition before pacing |
| 41 | Step 22: District looks | Scales and decor follow the District's Purpose; untouched zones byte-identical |
| 45 | Step 27: random placement and room-size spread | Built and hewn keep the lattice (the user's choice); caves at any bearing |
| 47 | Step 30: Hall length | 0.5–3.0; outdoor stops at ~1.6× on its hill |
| 48 | Step 31: District races, intrusion, drops | Links sized by the smaller race; drops one-way, never the only way back; map layers |

## Slice decisions

Each slice's `archive.md` "Decisions": [outdoor-dungeon](../../../.kiro/specs/zone-generator-outdoor-dungeon/archive.md),
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

- TinyKeep over BSP, WFC, prefabs, pure random walk and grid rule-tiles.
- Pacing is analytical (graph-derived), not a mission-graph grammar.
- Gating adopted only the solvability invariant; multi-key fragments are not needed.
- Gates and pacing are suggestions; they never alter geometry or collision.
