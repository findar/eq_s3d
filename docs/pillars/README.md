# Pillars

The project's work, organised by the outcome it serves rather than by the order it was done.
Terms in capitals are defined in the [glossary](../ARCHITECTURE.md#glossary); ID and link rules
are in [`docs/STYLE.md`](../STYLE.md). Each pillar has four files:

| File | What it holds |
|---|---|
| `PLAN.md` | Goal, scope, non-goals, the pillar's requirements with their parents and status, a traceability table, and the slices (steps) that served it |
| `DESIGN.md` | How that part of the system works now, checked against the code |
| `DECISIONS.md` | The settled calls, from the umbrella design's 48 decisions and the step archives |
| `OPEN.md` | Its open items, each checked against the code; items found already fixed are listed at the end |

Start with [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) for the whole system, and the root
[`OPEN.md`](../../OPEN.md) for every open item in one list.

## Working order

The user, 2026-11-27: "to be clear, we should be working top down. area map > dungeon > rooms > decor".
Then, on what "area map" means: "i mean one zones area, so like a wilderness or outdoor dungeon. we
should be generating the external area before anything we attach to it". Work is picked from the largest
scale down; a finer layer waits until the one above it settles. The multi-zone world ([P-8](P-8-world/PLAN.md))
sits above all of this and still waits on the user's design review:

| Order | Layer | Pillars |
|---|---|---|
| 1 | Area map: one zone's external area (a wilderness, or the outside of an outdoor dungeon), generated before anything attached to it | [P-7 Engaging](P-7-engaging/PLAN.md) (wilderness, outdoor dungeon), [P-2 Traversable](P-2-traversable/PLAN.md) (its walk gate) |
| 2 | Dungeon: layout, Districts, links, drops | [P-7 Engaging](P-7-engaging/PLAN.md), [P-2 Traversable](P-2-traversable/PLAN.md) |
| 3 | Rooms: shapes, walls, floors | [P-5 Look and feel](P-5-look-and-feel/PLAN.md) (geometry) |
| 4 | Decor | [P-5 Look and feel](P-5-look-and-feel/PLAN.md) (decor; off by default since [step 34](../../.kiro/specs/zone-generator-decor-off/tasks.md)) |

[P-1](P-1-web-app/PLAN.md), [P-3](P-3-rof2-eqemu/PLAN.md), [P-4](P-4-true-layout/PLAN.md), [P-6](P-6-iterative-feedback/PLAN.md) and [P-9](P-9-engineering/PLAN.md) serve every layer.

## The pillars

The "Requirements" column names each pillar's parent product requirements. All of them come
from the umbrella spec's
[`requirements.md`](../../.kiro/specs/zone-generator/requirements.md) (`ZG-Req-<n>`), except
the proposed ones, which are drafts listed [below](#proposed-product-requirements).

| Pillar | Outcome | Requirements |
|---|---|---|
| [P-1 Web app and controls](P-1-web-app/PLAN.md) | One page, with a prompt and controls, builds and shows a zone | [ZG-Req-1](../../.kiro/specs/zone-generator/requirements.md#requirement-1-explicit-generation-modes) to [ZG-Req-3](../../.kiro/specs/zone-generator/requirements.md#requirement-3-zone-type-availability) |
| [P-2 Traversable](P-2-traversable/PLAN.md) | Every build can be walked: no pits, no islands, no cliffs; the walk gate proves it | [ZG-Req-4](../../.kiro/specs/zone-generator/requirements.md#requirement-4-traversability-gate) to [ZG-Req-7](../../.kiro/specs/zone-generator/requirements.md#requirement-7-natural-geometry-style-for-dungeons) |
| [P-3 Usable in RoF2 and EQEmu](P-3-rof2-eqemu/PLAN.md) | The output loads in the client and on a server | [ZG-Req-8](../../.kiro/specs/zone-generator/requirements.md#requirement-8-export-time-short-name-takeover) to [ZG-Req-11](../../.kiro/specs/zone-generator/requirements.md#requirement-11-format-and-ir-round-trips) |
| [P-4 True-layout artifacts](P-4-true-layout/PLAN.md) | The map and sidecar show the zone as built | [ZG-Req-12](../../.kiro/specs/zone-generator/requirements.md#requirement-12-mesh-derived-outline) to [ZG-Req-14](../../.kiro/specs/zone-generator/requirements.md#requirement-14-true-layout-map-and-artifacts-in-the-web_app) |
| [P-5 EverQuest look and feel](P-5-look-and-feel/PLAN.md) | Indistinguishable from a hand-made Classic–PoP zone | [ZG-Req-15](../../.kiro/specs/zone-generator/requirements.md#requirement-15-era-fidelity-and-measured-conformance) to [ZG-Req-17](../../.kiro/specs/zone-generator/requirements.md#requirement-17-textured-preview), [ZG-Req-33](../../.kiro/specs/zone-generator/requirements.md#introduction) |
| [P-6 Iterative feedback](P-6-iterative-feedback/PLAN.md) | Edit a build by prompt and keep what you liked | [ZG-Req-18](../../.kiro/specs/zone-generator/requirements.md#requirement-18-sessions-and-feedback-interpretation) to [ZG-Req-20](../../.kiro/specs/zone-generator/requirements.md#requirement-20-history-undo-and-redo) |
| [P-7 Engaging every time](P-7-engaging/PLAN.md) | Layouts worth exploring, different on every seed | [ZG-Req-21](../../.kiro/specs/zone-generator/requirements.md#requirement-21-composed-solvable-layout) to [ZG-Req-25](../../.kiro/specs/zone-generator/requirements.md#requirement-25-quality_degraded-is-always-visible) |
| [P-8 World](P-8-world/PLAN.md) | Zones that sit in a larger world: Sockets, outdoor dungeons, zone lines | proposed [ZG-Req-34](#zg-req-34) to [ZG-Req-37](#zg-req-37) |
| [P-9 Engineering](P-9-engineering/PLAN.md) | Tests, speed, tooling and docs that keep the rest moving | [ZG-Req-26](../../.kiro/specs/zone-generator/requirements.md#requirement-26-determinism-and-fresh-seed-randomness) to [ZG-Req-32](../../.kiro/specs/zone-generator/requirements.md#requirement-32-settled-design-constraints); proposed [ZG-Req-38](#zg-req-38) to [ZG-Req-42](#zg-req-42) |

## Proposed product requirements

P-8 and P-9 have requirements with no parent in the umbrella spec. Each is written as a pillar
requirement whose parent is proposed here, numbered on from the umbrella's last ([ZG-Req-33](../../.kiro/specs/zone-generator/requirements.md#introduction)).
They are drafts for the user's review. The umbrella adopts them later; until then they live
only here.

| ID | Proposed requirement | Pillar requirement |
|---|---|---|
| <a id="zg-req-34"></a>ZG-Req-34 | A World describes one or more zones and how they connect, saved as versioned JSON | [P-8-Req-1](P-8-world/PLAN.md#p-8-req-1) |
| <a id="zg-req-35"></a>ZG-Req-35 | Zone lines join generated zones and land the player at a matching point on both sides | [P-8-Req-2](P-8-world/PLAN.md#p-8-req-2) |
| <a id="zg-req-36"></a>ZG-Req-36 | A World chooses its attach points and can hold more than one dungeon | [P-8-Req-3](P-8-world/PLAN.md#p-8-req-3) |
| <a id="zg-req-37"></a>ZG-Req-37 | Each build stage reads only the World and the earlier stages' hand-offs | [P-8-Req-4](P-8-world/PLAN.md#p-8-req-4) |
| <a id="zg-req-38"></a>ZG-Req-38 | The test suite runs in tiers sized to when they are needed | [P-9-Req-8](P-9-engineering/PLAN.md#p-9-req-8) |
| <a id="zg-req-39"></a>ZG-Req-39 | Heavy runs are serialised across agents on one machine | [P-9-Req-9](P-9-engineering/PLAN.md#p-9-req-9) |
| <a id="zg-req-40"></a>ZG-Req-40 | Continuous integration, releases, and migration of saved builds across format changes | [P-9-Req-10](P-9-engineering/PLAN.md#p-9-req-10) |
| <a id="zg-req-41"></a>ZG-Req-41 | A slice closes only when its pillar's design and open list are up to date | [P-9-Req-11](P-9-engineering/PLAN.md#p-9-req-11) |
| <a id="zg-req-42"></a>ZG-Req-42 | Generation failures can be reviewed in one place | [P-9-Req-12](P-9-engineering/PLAN.md#p-9-req-12) |

## Balance

A slice (one step spec, or a milestone spec) sits under the pillar whose outcome it mostly
moved. A step that helped two pillars is counted once, and the other pillar's `PLAN.md` names it
under "Also served by". Commits were counted with read-only `git log` at `c3d9b99` (the commit
that opened the project-docs spec). A commit belongs to a step by its `Task:` trailer (929
commits), else by the merge that brought it in (228), else by the spec folder it touched or the
scope in its subject line (161).

| Pillar | Slices | Steps | Commits | Share |
|---|---|---|---|---|
| P-1 | 1 | [step 14](../../.kiro/specs/zone-generator-web-cleanup/tasks.md) | 11 | 1% |
| P-2 | 2 | [M1](../../.kiro/specs/zone-generator-m1-controls-traversability/tasks.md) and [step 33](../../.kiro/specs/zone-generator-layout-repair/tasks.md) | 134 | 10% |
| P-3 | 1 | [step 17](../../.kiro/specs/zone-generator-export/tasks.md) | 27 | 2% |
| P-4 | 1 | [step 1b](../../.kiro/specs/zone-generator-m2-true-layout-artifacts/tasks.md) | 35 | 3% |
| P-5 | 13 | steps [1](../../.kiro/specs/zone-generator-wilderness/tasks.md), [2](../../.kiro/specs/zone-generator-wilderness-trees/tasks.md), [3](../../.kiro/specs/zone-generator-placeholder-textures/tasks.md), [4](../../.kiro/specs/zone-generator-interesting-textures/tasks.md), [8](../../.kiro/specs/zone-generator-room-walls/tasks.md), [11](../../.kiro/specs/zone-generator-room-decor/tasks.md), [15](../../.kiro/specs/zone-generator-decor-rules/tasks.md), [21](../../.kiro/specs/zone-generator-cave/tasks.md), [23](../../.kiro/specs/zone-generator-winding-tunnels/tasks.md), [24](../../.kiro/specs/zone-generator-flooded-rooms/tasks.md), [25](../../.kiro/specs/zone-generator-winding-routes/tasks.md), [26](../../.kiro/specs/zone-generator-winding-control/tasks.md), [29](../../.kiro/specs/zone-generator-cave-clumps/tasks.md) | 413 | 31% |
| P-6 | 2 | steps [16](../../.kiro/specs/zone-generator-partial-rebuild/tasks.md), [18](../../.kiro/specs/zone-generator-edits/tasks.md) | 41 | 3% |
| P-7 | 14 | steps [5](../../.kiro/specs/zone-generator-outdoor-dungeon/tasks.md), [6](../../.kiro/specs/zone-generator-graph-layout/tasks.md), [7](../../.kiro/specs/zone-generator-dungeon-verticality/tasks.md), [9](../../.kiro/specs/zone-generator-room-layouts/tasks.md), [10](../../.kiro/specs/zone-generator-wilderness-pois/tasks.md), [13](../../.kiro/specs/zone-generator-site-sockets/tasks.md), [19](../../.kiro/specs/zone-generator-quality/tasks.md), [20](../../.kiro/specs/zone-generator-districts/tasks.md), [22](../../.kiro/specs/zone-generator-district-looks/tasks.md), [27](../../.kiro/specs/zone-generator-random-placement/tasks.md), [30](../../.kiro/specs/zone-generator-hall-length/tasks.md), [31](../../.kiro/specs/zone-generator-district-races/tasks.md), [32](../../.kiro/specs/zone-generator-races-followups/tasks.md), and the [follow-up runway](../../.kiro/specs/zone-generator-followup/tasks.md) | 480 | 37% |
| P-8 | 1 | [step 12](../../.kiro/specs/zone-generator-world-sockets/tasks.md) | 59 | 4% |
| P-9 | 3 | [M0](../../.kiro/specs/zone-generator-m0-hygiene/tasks.md), [step 28](../../.kiro/specs/test-speed/tasks.md), and the [project-docs](../../.kiro/specs/project-docs/tasks.md) spec | 115 | 9% |
| **Attributed** | **38** | | **1315** | |
| Unattributed | | pre-spec phases, integration commits | 112 | |
| **All non-merge commits** | | | **1430** | |

Three more commits are left out of both rows: one in the umbrella spec and two tagged pre-spec.

### What the balance shows

- **P-5 and P-7 hold 68% of the commits.** Since [step 12](../../.kiro/specs/zone-generator-world-sockets/tasks.md), nearly every step has been about the
  look (P-5: caves, winding, clumps) or the layout (P-7: Districts, races, halls, intrusion).
  Each was asked for and is real progress. But the other pillars have stood still.
- **P-3 is proven only on paper.** One step built the SQL and door export. No zone has been
  loaded in the RoF2 client or applied on an EQEmu server ([P-3-1](P-3-rof2-eqemu/OPEN.md#p-3-1)). Seven of its twelve open
  items wait on the user.
- **P-1 has had one step** ([step 14](../../.kiro/specs/zone-generator-web-cleanup/tasks.md), the Controls). Its open list (17 items) is longer than that
  suggests: the CLI lags the page, and some lists are hard-coded in the HTML.
- **Requirements no slice ever served:** the conformance report ([ZG-Req-15](../../.kiro/specs/zone-generator/requirements.md#requirement-15-era-fidelity-and-measured-conformance)) and normal maps
  ([ZG-Req-16](../../.kiro/specs/zone-generator/requirements.md#requirement-16-procedural-normal-maps)) in P-5; topology control ([ZG-Req-22](../../.kiro/specs/zone-generator/requirements.md#requirement-22-topology-control)) in P-7; and the content renames of
  [umbrella decision 19](../../.kiro/specs/zone-generator/design.md#decisions-made-in-this-revision) in P-1.
- **P-8 stopped after one step.** [Step 12](../../.kiro/specs/zone-generator-world-sockets/tasks.md) built the World and Sockets. Multi-zone worlds wait on
  a design review ([P-8-1](P-8-world/OPEN.md#p-8-1)).

## Open items by pillar

| Pillar | Open | In flight | Parked | Waiting | Total | Already fixed |
|---|---|---|---|---|---|---|
| P-1 | 12 | 0 | 4 | 1 | 17 | 3 |
| P-2 | 9 | 2 | 1 | 1 | 13 | 6 |
| P-3 | 4 | 0 | 1 | 7 | 12 | 3 |
| P-4 | 3 | 1 | 0 | 1 | 5 | 3 |
| P-5 | 29 | 0 | 4 | 5 | 38 | 15 |
| P-6 | 7 | 0 | 0 | 1 | 8 | 4 |
| P-7 | 27 | 1 | 2 | 7 | 37 | 10 |
| P-8 | 3 | 0 | 0 | 1 | 4 | 1 |
| P-9 | 9 | 5 | 2 | 0 | 16 | 3 |
| **All** | **103** | **9** | **14** | **24** | **150** | **48** |
