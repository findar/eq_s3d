# TASK: content-layer-districts

Status: not-started        <!-- not-started | in-progress | blocked | done -->
Epic: Content / semantic layer, Step 2 (ROADMAP "Next" #1 — districts). Split
      out of `tasks/content-layer-dungeon.md` (which delivered Step 1,
      single-theme rooms) so this one coherent change — making a zone several
      themed places at once — is tracked on its own.
Last touched: created 2026-10-18, promoted from the Step 2 block of
      content-layer-dungeon.md.

## Goal

A generated dungeon is currently ONE themed place: every room is drawn from a
single "archetype" (e.g. fortress) with one entrance→boss progression. Real
EverQuest zones are often several places in one — Lower Guk's living upper half
vs. the undead lower half, Chardok's fortress vs. the separate faction halls.
This task lets a generated zone be **1–3 districts**: contiguous groups of rooms,
each with its own sub-theme and its own entrance→climax arc, joined at a hub or a
gated threshold, so crossing from one into another feels like entering a new
place.

Concretely: partition the zone's room graph (the "pacing graph" — rooms are
nodes, corridors are edges, already labelled with role and depth-from-entrance)
into contiguous districts; give each its own sub-theme and climax; make the
boundary a natural chokepoint where the palette and lighting flip sharply and an
optional locked door can sit; and carry it all as advisory metadata (sidecar /
map / viewer), never baked into geometry — the same way pacing and gating already
ride alongside the mesh. Done when a human generates a large dungeon and walks a
zone that reads as 2–3 distinct themed areas with a visible boundary between
them, and a single-district zone (small, or the off switch set) is unchanged from
today.

Scope: dungeon/box backend only (where the content layer runs; cave/outdoor are
untouched). No new art, no placed prop models — districts realise through the
existing region/light/texture/shape pipeline plus suggestion data, exactly like
Step 1.

## Design — already decided, do not re-derive

The full design and the user's decisions live in `docs/RESEARCH.md`
("Multi-area zones — districts" and the "Implementation sequencing" note). Build
to that. Summary of the binding decisions:

- **Partition model:** grow districts from seed rooms outward along graph edges
  (multi-source BFS / graph cut) so each district is contiguous and boundaries
  fall on natural chokepoints (hubs).
- **Auto-split by room count, with an off switch:** ≥8 rooms → 2 districts,
  ≥14 → 3, capped at 3. A `multi_district` control / planner field forces
  single-district. Below the threshold (or off) → today's single-district
  behaviour, unchanged.
- **Per-district climaxes:** climax is per-district, not per-zone — a 2-district
  warring zone legitimately has two boss rooms. The existing single-climax
  pacing is just the 1-district case.
- **Boundary = threshold:** the corridor between two districts is a threshold;
  reuse the existing lock-and-key gating for an optional locked door there, and
  flip palette/light mood sharply across it so the crossing reads.
- **District relationship tag** (`sequential` / `factional` / `abandoned_vs_active`)
  proposed by the planner, tinting the suggestion fields (e.g. "faction skirmish
  at the boundary").

## Preflight (do this first — the repo may have moved)

Step 1's navigability sign-off in `content-layer-dungeon.md` was marked BLOCKED
on `tasks/corridor-connection.md`. That task is now `Status: done`, so the
blocker should be cleared — but this project advances past its docs, so CONFIRM
before building on top:

- [ ] Re-run the Step 1 navigability sweep described in
      `content-layer-dungeon.md` Notes: `analyzer.traverse` across the archetypes
      × a couple of seeds. Expectation: themed zones now walk green with zero
      content-layer changes (the failures were the corridor bug, since fixed).
      Record the result. If they still fail, STOP and re-open the corridor issue
      rather than working around it in the district code.

## Current code state (verified 2026-10-18)

- `RoomSpec.district: int = 0` EXISTS (placeholder; every room is district 0
  today) and is already carried into the `.zone.json` sidecar (`builder.py`).
- `RoomSpec.district_theme`, a `DistrictSpec` type, and `ZoneSpec.districts` do
  NOT exist yet — they are to be added by this task.
- `generators/semantics.py` is explicitly "Step 1 — single district"; its
  `label_rooms()` / `realize_semantics()` assign one archetype across all rooms.

## Acceptance criteria

Each names its verification mechanism. Structural tests passing is necessary but
NOT sufficient here (every geometry/pacing change so far was only truly caught in
the 3D viewer), so a human 3D pass is on the bar.

- [ ] A deterministic partitioner splits the pacing graph into contiguous
      districts by the room-count thresholds, with an off switch:
      `tests/test_generators.py::TestDistricts` asserts — a ≥8-room zone yields 2
      districts and a ≥14-room zone yields 3 (capped at 3); each district is a
      connected sub-graph (every room reaches every other room in its district
      without leaving it); a <8-room zone OR `multi_district` off yields exactly
      1 district; and the split is deterministic for a fixed seed.
- [ ] Each district gets its own sub-theme and its own entrance→climax arc:
      `TestDistricts` asserts each district has exactly one climax room (so an
      N-district zone has N boss rooms) and that rooms in different districts
      carry different `district`/`district_theme` values.
- [ ] The boundary between districts is a single threshold corridor and the
      palette/light flips across it: a test asserts adjacent rooms on opposite
      sides of a boundary use different material/light sets; when gating is on, a
      `GateSpec` can be placed on the threshold corridor (reusing existing gating,
      solvability preserved — assert the key is reachable before the lock).
- [ ] IR extended and serialised: `RoomSpec.district_theme`, a `DistrictSpec`,
      and `ZoneSpec.districts` exist and round-trip through `ZoneSpec` save/load
      (`tests/test_generators.py` or `tests/test_zone_spec.py`); the rule/LLM
      planner can propose districts via `ZonePlan`, and the partitioner invents
      sensible defaults when the planner is silent (`tests/test_planner.py`).
- [ ] District boundaries render on the top-down map and in the viewer overlay:
      asserted structurally (map SVG / sidecar contains district grouping or a
      boundary marker) AND confirmed in the human 3D pass below.
- [ ] `docs/ACCEPTANCE.md` gains a "Districts" section and it passes for the
      pinned seeds below: a human generates large dungeons and confirms — the
      zone reads as 2–3 distinct themed areas (palette/light visibly change at the
      boundary), each area has its own boss chamber, the threshold reads as a
      deliberate crossing (and a locked door sits there when gating is on), and a
      single-district zone is indistinguishable from today's output.
- [ ] `levels = 1` equivalent for districts: `multi_district` off (or a
      sub-threshold room count) reproduces today's single-district zones —
      existing `TestSemantics`/`TestPlanner` and acceptance seeds stay green.
- [ ] Full suite green: `python -m pytest tests/ -q`.

Pinned seeds: pick two large-room-count dungeon seeds (≥8 and ≥14 rooms) that
pass the Step 1 navigability sweep, so districts are checked on top of already-
validated geometry; plus one small seed (<8 rooms) to confirm the single-district
no-op. Record the exact seeds in Notes once chosen.

## Subtasks

Ordered; each roughly one commit.

- [ ] **Preflight sweep** (above): confirm Step 1 navigability is green post
      corridor-connection; record seeds. Do not build on a red Step 1.
- [ ] **IR + partitioner.** Add `RoomSpec.district_theme`, `DistrictSpec`,
      `ZoneSpec.districts` (+ serialisation). Implement the deterministic
      multi-source BFS / graph-cut partitioner with the room-count thresholds and
      the `multi_district` off switch. Test: `TestDistricts` (counts,
      contiguity, determinism, single-district no-op).
- [ ] **Per-district sub-themes + climaxes.** Extend `generators/semantics.py`
      so each district gets its own archetype sub-theme and its own
      entrance→climax arc (N districts → N climaxes). Keep single-district output
      identical to today.
- [ ] **Threshold boundaries + gating + mood flip.** Mark the boundary corridor
      as a threshold; flip palette/light across it; allow an optional
      `GateSpec` on it via the existing gating (solvability preserved).
- [ ] **Planner + defaults.** `ZonePlan` optional district proposals + the
      relationship tag; rule planner keyword detection ("live and dead",
      "two factions"); deterministic defaults when the planner is silent. Test:
      `TestPlanner`.
- [ ] **Map + viewer rendering.** Draw district boundaries / grouping on the
      top-down map and the viewer overlay.
- [ ] **Docs + acceptance.** Add `docs/ACCEPTANCE.md` "Districts"; run the human
      3D pass on the pinned seeds; record findings.
- [ ] Full suite green; update Deliverables + Status.

## Deliverables

- Code: `generators/zone_spec.py` (`DistrictSpec`, `ZoneSpec.districts`,
  `RoomSpec.district_theme`), `generators/semantics.py` (per-district themes +
  climaxes), `generators/layout.py` (partitioner + threshold wiring),
  `ai/schema.py` + `ai/rule_planner.py` + `ai/expand.py` (district proposals),
  `generators/mapview.py` (boundary rendering), viewer overlay in `web/src`
  (+ rebuilt `web/dist` if touched).
- Tests: `tests/test_generators.py::TestDistricts`, `tests/test_planner.py`,
  zone-spec round-trip.
- Docs: `docs/ACCEPTANCE.md` (Districts); design already in `docs/RESEARCH.md`.
- Integration state (written later by the single-writer integration step, NOT by
  this task): `tasks/README.md` board row for `content-layer-districts`; ROADMAP
  content-layer status → Step 2 done; `tasks/content-layer-dungeon.md` can close
  once its Step 1 validation lands.
- Commits: <hashes, newest last>

## Notes / decisions / blockers

- **Why split from content-layer-dungeon.md:** that file had delivered Step 1 but
  still carried an unfinished Step 1 validation pass AND a full ~6-subtask Step 2
  — two outcomes in one file. Districts is a distinct, landable change, so it
  gets its own file (same reasoning that split the EQ-map SVG follow-up out).
  `content-layer-dungeon.md` now points here for Step 2 and keeps only the
  remaining Step 1 aesthetic/enclosure validation.
- **Advisory metadata, never geometry.** Districts ride in the sidecar/map/viewer
  like pacing and gating. No prop MODs, no new art — realise through existing
  region/light/texture/shape + suggestion data.
- **Open design question inherited from Step 1:** should the per-room `sink`
  elevation be suppressed/scaled for a FLAT zone? Deferred in
  content-layer-dungeon.md pending a 3D read of the gentle sink elevation; note
  it here in case districts make it more visible at boundaries.
- **pwsh commit convention** (single-writer tracker = this task file only): write
  the message to `.git/COMMIT_EDITMSG_TMP`, `git commit -F` it, then always
  delete the temp file; never `git add .`; do not push.
