# TASK: multi-level-dungeon

Status: not-started        <!-- not-started | in-progress | blocked | done -->
Epic: Box-backend verticality — true multi-level / stacked-floor dungeons, so a
      zone can be vertically dense (rooms directly above each other, joined by
      vertical connectors) instead of a single planar layout with per-room Z
      nudges. A new geometry capability, not a correctness fix.
Last touched: created 2026-10-17 from a design discussion about wanting very
      vertically-spaced dungeons.

## Goal

Let the generator build dungeons with **real stacked levels**: rooms that sit
directly above/below one another and connect vertically (stairwells, shafts,
spiral stairs, ladders), driven by a control (e.g. a "levels" / floors input in
the web UI + a plan field). Done when a human can ask for an N-level dungeon and
walk a zone that genuinely reads as multiple floors — a room's ceiling is
another room's floor, reached by a vertical connector — with every level
reachable (traversability validator green) and the existing single-level
behaviour unchanged when levels = 1.

## Why

Today's dungeons are effectively **2.5D**, and this is a hard limitation baked
into the layout, not a tuning knob:

- `LayoutGenerator._scatter_rooms` scatters rooms in a 2D ellipse (`floor_z`
  starts at 0 for all).
- `LayoutGenerator._separate_rooms` resolves overlaps on **XY only** (AABB on
  width/depth). Because it never considers Z, two rooms can never share an XY
  footprint — so one room can **never** sit directly above another.
- `LayoutGenerator._connect_rooms` builds the graph from a Delaunay
  triangulation of the **XY** room centres → MST + a few loop edges. Adjacency
  is purely planar.
- `LayoutGenerator._assign_elevation` then BFS-walks that planar graph and
  offsets each room's `floor_z` by a continuous ±rise (the `verticality` plan
  field scales the chance + magnitude). This is a *height nudge on a flat map*,
  not a stack of discrete floors.
- Every corridor is therefore a **horizontal** run (`geometry.add_corridor`
  builds a straight or L-shaped leg in XY) with the height change carried by a
  ramp or staircase along that horizontal run. There is no vertical-only
  connector and no notion of "floor 2 is above floor 1".

The result: you can make the floor undulate, but you can't get a tower, a
multi-storey keep, a deep vertical mine shaft, or anything where the player
climbs through stacked chambers. This task adds that capability.

## Relationship to other tasks (read before starting)

- **Depends on / should follow `tasks/corridor-connection.md`.** That task is
  rebuilding corridor routing for same-axis pairs and bounding elevation
  steepness (walkable ramp grades, sane stair step height) — all for the
  *horizontal* model. Vertical connectors are an extension of exactly that
  elevation + stair work; building them on top of the fixed, shared
  elevation-split/step helper avoids inventing a second, divergent stair path.
  Starting this before corridor-connection lands risks duplicating (and then
  having to re-reconcile) stair geometry.
- **Must stay green on `tasks/traversability-validator.md`.** The validator
  walks the box-backend mesh to confirm every room is reachable. Vertical
  connectors MUST be walkable by the same check (a shaft the validator can't
  traverse = an unreachable level = a regression). May need the validator to
  understand vertical moves.
- Orthogonal to the cave/outdoor backends (`cave-*`, terrain) — this is a
  box-backend capability. Don't entangle it with those.

## Design direction / open questions (confirm with user before building)

These are decisions, not settled answers — the task starts with a short design
pass.

1. **Discrete floors vs. free stacking.** Two models:
   - *Discrete levels*: pick `N` floor bands at fixed Z spacing
     (`ceiling + slab`), assign each room to a level, lay each level out in its
     own plane, then connect levels. Cleaner, reads as "floors", easier to
     validate. **Recommended starting point.**
   - *Free 3D stacking*: let rooms take any Z and make separation 3D-aware.
     More organic, much harder to keep walkable/legible. Probably later, if at
     all.
2. **3D-aware separation.** `_separate_rooms` must allow XY overlap when rooms
   are Z-separated by at least `ceiling_height + slab_thickness` (so a stack is
   legal), while still pushing apart rooms that overlap in XY *and* Z. This is
   the core layout change.
3. **Cross-level connectivity.** How levels connect: a stairwell/shaft room that
   spans two levels, vertical edges added to the graph between vertically
   adjacent (overlapping-XY) rooms, and a guarantee that every level is
   reachable from the entrance (extend the BFS/MST reachability, and gating, to
   the 3D graph).
4. **Vertical connector geometry.** New primitive(s) in `generators/geometry.py`:
   a vertical shaft with a stair (spiral or switchback) or ladder, that lands
   flush on both the lower room's floor and the upper room's floor and is
   walkable. Reuse corridor-connection's elevation-split/step helper.
5. **Controls surface.** A "Levels" number input in the web UI (alongside Rooms;
   1 = current flat-ish behaviour), a `levels` field on `ZonePlan`
   (`ai/schema.py`, with validate() clamping) threaded through
   `ai/expand.plan_to_spec`, and a `LayoutGenerator` parameter. The rule/LLM
   planner should be able to infer it from prompts like "a five-storey tower".
   Decide how `levels` interacts with the existing `verticality` field (likely:
   `verticality` = within-level undulation, `levels` = how many stacked floors).
6. **Backward compatibility.** `levels = 1` (and un-specified) MUST reproduce
   today's single-plane behaviour so existing seeds/tests/acceptance don't move.

## Acceptance criteria

- [ ] A `levels`/floors control exists end to end: web UI number input →
      `GenerateRequest` → `LayoutGenerator`, and a `ZonePlan.levels` field the
      planner can set, validated/clamped to a sane range.
- [ ] With `levels >= 2`, the layout places rooms on distinct stacked Z bands
      and at least some rooms share an XY footprint across levels (a room
      directly above another), verified by a test (two rooms overlapping in XY
      with non-overlapping Z extents).
- [ ] Levels are connected by a **vertical** connector that lands flush on both
      the lower-room floor and the upper-room floor (test: connector floor Z at
      each landing == the respective room floor_z, within tolerance), and is
      walkable (grade/step bound, same bar as corridor-connection #2).
- [ ] Every room on every level is reachable from the entrance — the
      **traversability validator passes** for several multi-level seeds
      (dungeon/box backend), including ones with 3+ levels.
- [ ] `levels = 1` reproduces the current single-level behaviour; existing
      generator/corridor tests stay green and existing acceptance seeds are
      unchanged.
- [ ] `docs/ACCEPTANCE.md` gets a multi-level item (human 3D confirm: the zone
      reads as real stacked floors, you can climb between them, no floating or
      intersecting rooms) and it passes for N seeds.

## Subtasks

- [ ] **Design pass + user sign-off** on the open questions above (discrete
      levels vs free stacking; how `levels` relates to `verticality`; connector
      style). Write the decision into Notes before coding.
- [ ] 3D-aware `_separate_rooms`: allow XY overlap when Z-separated; keep
      pushing apart rooms overlapping in both XY and Z.
- [ ] Level assignment: distribute rooms across `N` Z bands at
      `ceiling + slab` spacing (discrete-levels model).
- [ ] Cross-level graph: add vertical edges between XY-overlapping,
      Z-adjacent rooms; guarantee per-level reachability from the entrance
      (extend MST/BFS); extend gating to the 3D graph if locks are on.
- [ ] Vertical connector primitive in `generators/geometry.py` (shaft +
      spiral/switchback stair or ladder), reusing corridor-connection's
      elevation-split/step helper; lands flush + walkable at both ends.
- [ ] Controls: `levels` on `ZonePlan` (+ `validate()`), through
      `ai/expand.plan_to_spec` and `LayoutGenerator`; `GenerateRequest.levels`
      in `server/app.py`; "Levels" number input in `web/index.html` +
      `web/src/main.ts` (parse/clamp like Rooms) + `web/src/api.ts`; rebuild
      `web/dist`. Planner inference for "tower/storey/levels" prompts.
- [ ] Tests: stacked-footprint placement, vertical-connector flush landing +
      walkability, multi-level traversability sweep, and a `levels=1`
      no-regression check.
- [ ] Human 3D validation on several multi-level seeds; log findings here.
- [ ] Sync ROADMAP (promote from backlog → a built capability) and this file.

## Deliverables

- Code: `generators/layout.py` (3D separation, level assignment, cross-level
  graph), `generators/geometry.py` (vertical connector), `ai/schema.py`
  (`levels` field), `ai/expand.py` (thread it), `server/app.py`
  (`GenerateRequest.levels`), `web/index.html` + `web/src/main.ts` +
  `web/src/api.ts` (+ rebuilt `web/dist`).
- Tests: `tests/test_generators.py` (placement + connector), extend
  `tests/test_traversability.py` with multi-level seeds.
- Docs: `docs/ACCEPTANCE.md` (multi-level item), ROADMAP, this file.
- Commits: <hashes, newest last>

## Notes / decisions / blockers

- This is a **capability add**, deliberately sequenced AFTER
  `corridor-connection` (vertical connectors build on the fixed stair/ramp
  helper) and gated by the **traversability validator** (a level you can't walk
  to is a hard failure, not a cosmetic one).
- Per the standing project lesson: passing structural tests are necessary but
  not sufficient for geometry — every elevation/corridor bug so far only showed
  in the 3D viewer. Keep a human 3D eyeball in the acceptance bar for the
  stacked-floor reading and the climb between floors.
- Keep `verticality` (within-level floor undulation) and `levels` (count of
  stacked floors) conceptually distinct so a prompt can combine them
  ("a tall tower with uneven floors").
- Don't special-case themed vs. plain zones — this is a theme-independent box
  backend change; the content/semantic layer sits on top unchanged.
