# TASK: layout-oneway-connections

Status: not-started        <!-- not-started | in-progress | blocked | done -->
Epic: Layout controllability — directed (one-way) room connections (the tier
below ROADMAP "content layer / refinement"). New generator feature; the second
of a deliberately split pair (see "Dependencies"). No ROADMAP "Next" item names
it yet — surface as an integration note.
Last touched: created (task-author draft; renamed from layout-oneway-dropdown to
reflect the directed-edge abstraction, not just the drop realization)

## Goal

Let a zone contain **one-way connections** between rooms: a connector you can go
through in only one direction — enter room B from room A, but not walk back from
B to A the same way. Today **every** connection between two rooms is a two-way
corridor (a walkable ramp or stairs you can traverse both ways), so a directed
connection is a genuinely new kind of edge. The connection's "one-wayness" is
the core idea; it can be *realized* in more than one way, and this task delivers
two realizations:

- a **drop-down** (vertical): you step/fall off a ledge or down a shaft from a
  higher room into a lower one and **cannot climb back up** — the one-wayness is
  pure geometry (the ledge is too tall to climb), so it is fully enforced now;
- a **one-way wall/door** (planar, same floor height): a passage you go through
  from one side only, at roughly equal elevation — like a secret door openable
  from one face, a portcullis/one-way gate, or a collapse you can squeeze
  through but not back past. Because it is at the same height, its one-wayness is
  **not** something flat EQG geometry can enforce (see "Realization 2" for the
  constraint and the honest scope decision this task makes).

Done when: a user can ask for one-way connections (via the prompt, the CLI, or
the web controls) and pick which kind; the generator places that many directed
edges; a **drop** goes strictly downhill by more than a player can climb and is
physically impossible to climb back; the destination of a one-way edge may be a
**dead end with no walk-back route** (that is acceptable and must be allowed —
not every dungeon gives you a way back); and the "every room is reachable from
the entrance" guarantee still holds, now read as **directed** reachability (you
can always get *into* every room by following connections in their allowed
direction; a room you cannot even enter is a bug). A human confirms in the 3D
viewer that you can walk to a drop, fall down it, land on the lower floor, and
that a drop-fed dead-end room is reachable going in but has no way back up.

### Settled design constraints (decided by the human — do NOT reopen)

These are fixed requirements, not open questions. Pin them; do not "improve"
them into forcing a return path.

1. **A dead end behind a one-way edge is acceptable.** A one-way connection may
   leave its destination reachable *only* via that edge, with **no required
   walk-back route**. Some real dungeons give you a way back and some don't; the
   generator must accept **both**. The feature must therefore **not** force an
   alternate walkable return corridor, and must **not** be "fixed" by quietly
   adding one.
2. **"Every room reachable from the entrance" still holds — as directed
   reachability.** Reachability is about getting *in*: following every
   connection in its allowed direction from the entrance, can you enter every
   room? A one-way edge is fine (you enter the destination through it). A room
   you cannot enter by *any* direction is still a bug and must still fail
   validation.
3. **Dungeon-only for v1** (box backend). See "Backends" — cave is shelved /
   untrustworthy in 3D, and outdoor's mesh is in a different coordinate frame
   from the room graph so the validator can't map rooms onto it (both are
   recorded ROADMAP Known issues). One-way edges need the box backend's
   ramp/stair elevation machinery and the dungeon-gated validator, so restrict
   v1 to `dungeon` and state why.

## Background (what a reader needs to know)

- **Room graph.** A zone's abstract floor plan: rooms are nodes, corridors are
  the edges joining them. It is built in `generators/layout.py::_connect_rooms`,
  which returns a list of **undirected** `(i, j)` room-index edges. Each edge
  becomes one corridor in `_build_corridors`, which appends a `CorridorSpec` to
  the `ZoneSpec`. The box geometry backend turns every `CorridorSpec` into 3D in
  `generators/geometry.py::MeshBuilder.add_corridor`.
- **Elevation + corridors today (from the landed `corridor-connection` task).**
  Rooms get floor heights by BFS over the graph (`_assign_elevation`), capped so
  a corridor's rise stays walkable (grade cap `max_grade = 0.5 ≈ 26.6°`), then
  relaxed so even loop edges stay walkable (`_relax_elevation`). Corridors carry
  that rise as a **subdivided walkable ramp**: a single-quad ramp reads as an
  unclimbable cliff to the validator's per-triangle agent, so ramps are
  subdivided to rise ≤ ~2.5u per segment (`_add_ramp_corridor`, `MAX_SEG_RISE`).
  Routing picks straight / 3-segment **Z-corridor** / L-bend through one
  `_emit_route` helper so both openings land flush (the Z-corridor fix for
  same-axis parallel walls — do not regress it). **A drop is the deliberate
  inverse of all this:** an edge whose Z difference *exceeds* what a ramp/step
  can climb, realized as a ledge/shaft you fall down — not a ramp, not
  sub-step stairs.
- **The traversability validator — and the crux of this task.**
  `analyzer/traverse.py` walks the **real TER mesh** from the safe point with an
  EQ-scale agent and checks every room is reachable on foot. It is baked into
  the generate hot path by `generators/pipeline.py::generate_validated` (build →
  validate → retry on a fresh seed; gated for `dungeon` only), so a dungeon that
  strands a room is auto-rejected and retried, or the server returns 503.
  **Critically, its reachability is currently UNDIRECTED and symmetric.** In
  `build_walk_surface`, two standable faces become adjacent only when
  `_z_gap_ok(fi, fj)` holds, defined as `abs(centroid_z[fi] − centroid_z[fj]) <=
  agent.max_step_up` (~3u). A genuine drop has a vertical gap *larger* than
  `max_step_up`, so under today's rule the upper lip and the lower floor are
  **not adjacent at all** — the flood fill can't cross a drop in *either*
  direction. Result if nothing changes: a drop-fed room reads as unreachable and
  `generate_validated` rejects every such zone (or the diagnostics call it an
  "oversized stair step or drop"). So this task's make-or-break item is teaching
  the validator **directed** reachability — a drop is a legal one-way (downward)
  transition — *without loosening* the walkable-slope / step-up guarantees that
  catch cliff ramps and oversized steps for ordinary two-way floors and
  corridors.
- **Doors are runtime records, not geometry (a settled design call).** A
  functional EQ door is a row in the EQEmu `doors` table referencing an animated
  door model — the *server* drives open/close and gatekeeping. The repo
  deliberately **never bakes a door into the `.ter`** (a door welded into the
  mesh is a door-shaped wall that can't open). The existing gating feature
  follows this exactly: a `GateSpec` carries `corridor_id` + lock position as
  **data for the future SQL export**, while the corridor geometry stays an open
  gap. This fact is the hinge for Realization 2 below.
- **EQG collision is per-triangle (lessons-learned).** The mesh *is* the
  collision model; there is no BSP, no scripting, and **no one-sided-triangle
  collision**. That means a flat wall you can pass through from one side but not
  the other **cannot be expressed in baked geometry at all** — a triangle you
  can walk through is walk-through-able from both sides. A tall ledge, by
  contrast, *is* enforceable by pure geometry (you physically cannot climb it).
  This asymmetry is exactly why the two realizations below have different honest
  scopes.

## Core concept (realization-agnostic — this is the heart of the task)

The shared core of this task is **not** any one geometry trick; it is the
**directed-edge abstraction** and the **directed-reachability** change that go
with it. Both realizations ride on this core, which is the make-or-break work.

### Data model — a directed edge is real IR, not sidecar

A one-way edge changes how the validator must read the graph (and, for a drop,
the geometry too), so it is **real IR**, not advisory sidecar data. Add the
minimal fields to `CorridorSpec` in `generators/zone_spec.py`:

- `one_way: bool = False` — this corridor is traversable in one direction only,
  from `from_` to `to_`.
- `realization: str = ""` — how the one-wayness is realized: `"drop"` (a
  fall/ledge/shaft, vertical) or `"wall"` (a planar one-way passage at equal Z).
  Empty for an ordinary two-way corridor. Keeping this as a distinct field (vs a
  bare `drop: bool`) is what lets the single directed abstraction carry *both*
  realizations and leaves room for future ones — do not collapse it back to a
  drop-only flag.
- Direction convention: the existing `from_*`/`to_*` endpoints already imply a
  direction. **Pin the convention: you may traverse `from_` → `to_` only.** For
  a drop this additionally means `from_` is the TOP and `to_` is the BOTTOM
  (`from_z > to_z`); assert that when the layout builds a drop so no backend has
  to guess which end is the lip. For a one-way wall the two ends are at (near-)
  equal Z, so the direction is carried **only** by the `from_`/`to_` ordering
  and the `one_way` flag — there is no height cue.

These fields default to today's values, so every existing spec/test is a no-op
unchanged. They serialize through `to_dict`/`from_dict` automatically (both use
`asdict`/`**`), but **add a round-trip assertion** to the tests since a missing
field in an old `.json` must still load (it will, via the dataclass default).

### Validator — directed reachability (shared by BOTH realizations)

This is the correctness core; give it its own subtask and acceptance criteria.
In `analyzer/traverse.py`, reachability must become **directed from the
entrance**, and it must accept a legal one-way transition in its allowed
direction **for both realizations**:

- Keep the existing symmetric step-up/slope adjacency for normal walking
  (`abs(dz) <= agent.max_step_up`, slope cap) **unchanged** — that is what
  catches cliff ramps and oversized steps, and must not be loosened.
- Make the flood fill **directed**: from the seed face, walk symmetric
  walk-edges both ways, but traverse a one-way edge **only** in its allowed
  `from_`→`to_` direction. A room is reachable iff some face in its footprint is
  in the directed-reachable set. This makes a one-way-fed dead-end room **pass**
  (you enter through the edge) while a genuinely unenterable room still
  **fails**.
- **Ground every one-way transition in the SPEC, not only in mesh geometry.**
  The spec carries `from_room`/`to_room` and now `one_way`/`realization` on each
  corridor; the validator must use these so it only treats an *intended* one-way
  opening as a legal directed transition — a steep bit of ordinary floor must
  not read as a legal drop, and an ordinary opening must not silently read as
  one-way. This spec-grounding is what makes the two realizations tractable:
  - **drop:** on top of the unchanged symmetric adjacency, add a **directed
    descend** transition — from a higher standable face to a lower standable
    face that overlap in XY (within `adjacency_eps`) when the drop height
    `dz_down` is within a new `max_drop` fall bound (a fall a player survives /
    that is clearly a deliberate drop, not noise — pick and justify a value,
    generous relative to player height; it is a *fall*, not a step). One-way:
    upper→lower only, never lower→upper. Gate it on the corridor's `realization
    == "drop"` + `one_way` so an *unintended* oversized gap (no flag) still
    fails as before.
  - **wall:** the two faces are at (near-)equal Z and DO already satisfy the
    symmetric `_z_gap_ok` adjacency (they're a normal flush opening). So the
    mesh alone would read it as two-way. To honour the one-way *semantic* in the
    validator, treat a corridor with `realization == "wall"` + `one_way` as a
    **directed** graph edge between its two rooms (room-graph-level, like
    `_diagnose_via_graph` already reasons over corridors): reachable `from_room`
    → `to_room`, not back. (This is a validator-model choice, not a claim that
    the mesh blocks the return — see Realization 2 for why the mesh can't.)
- Update `classify_corridor` / `_diagnose_via_graph` so an intended one-way
  corridor is reported as the expected directed edge (a drop reads as the
  expected one-way drop, not a failure), while an **unintended** oversized
  vertical gap stays a failure. (`classify_corridor` / `_diagnose_via_graph`
  currently call a big gap "oversized stair step or drop" — split that so an
  intended `drop` is expected and an unflagged gap still fails.)
- **Single source of truth for the drop thresholds:** the climbable step
  (`max_step_up`, ~3u), the layout's "make it a real drop" margin, and the
  validator's `max_drop` must be consistent so geometry the layout builds as a
  drop is exactly what the validator accepts as a one-way descend. State the
  three numbers and their relationship in one place in the task notes.

**Determinism:** same seed + same controls (including the one-way count/kind) ⇒
identical zone. Draw every choice (which edges, which realization, any
tie-break, any added depth) from `self.rng`, never from set/dict iteration
order. **Guard the no-op:** adding an RNG draw for edge selection *after* the
existing draws could perturb later consumers (elevation, gating) even when
`one_way=0`, so take the one-way draws only when `one_way > 0` (or otherwise
prove they don't shift the `one_way=0` stream). The "default is a no-op" test
against a pinned seed is the proof this holds.

## Realization 1 — drop-down (vertical; fully enforced by geometry NOW)

A drop is enforceable today because it is **pure geometry** — a ledge too tall
to climb physically blocks the return with no door or runtime logic needed. This
is the worked example and carries the full geometry detail.

### Layout — choosing which edges become drops

After the undirected graph + elevation are built, convert the requested number
of edges to one-way drops. Recommended selection, all drawn from `self.rng`:

- Prefer **non-tree (loop) edges** and/or edges leading to a leaf/dead-end room,
  so converting them to one-way cannot strand the graph: the spanning tree still
  reaches every room two-way, and a leaf behind a drop is exactly the accepted
  dead-end case. **The robust rule: only convert an edge whose removal leaves
  the graph connected via the remaining two-way edges** (so directed
  reachability is guaranteed even before the validator checks it). State the
  chosen rule and why. (This mirrors how `_apply_gating` reasons about tree vs
  non-tree edges.)
- Orient each chosen drop **downhill**: the higher-floor room is `from_` (top),
  the lower is `to_`. If the two rooms are too close in Z (the elevation cap
  kept them within a climbable step), **deepen the drop**: lower the destination
  room (and relax its other neighbours) so `from_z − to_z` exceeds the climbable
  threshold by a clear margin — a drop must be an actual fall, not a tall step.
  Define the threshold in one place (see Core concept notes) and keep the
  geometry and the validator reading the same number.
- Emit the converted edge as a `CorridorSpec` with `one_way=True,
  realization="drop"` and the top/bottom endpoints, instead of a ramp.

### Geometry — realize a drop as a fall, not a ramp

In `MeshBuilder.add_corridor` (or a dedicated `_add_drop_corridor` it dispatches
to when `cor.realization == "drop"`), realize the drop so the upper room's floor
**ends at a lip** over the lower room / opens into a short vertical **shaft**,
and the player falls the Z gap to the lower floor. Concretely:

- The upper end is a flat floor at `from_z` that stops at the opening (the lip);
  the lower end is a flat floor at `to_z`. The vertical face between them is a
  wall/shaft the player drops down — **not** a subdivided walkable ramp and
  **not** sub-step stairs. This is the explicit inverse of `_add_ramp_corridor`.
- Reuse the `_emit_route` routing (straight / Z / L) for the **XY** path so the
  opening still meets both walls flush — do **not** reinvent routing and do
  **not** regress the same-axis Z-corridor / flush-opening fixes documented in
  `lessons-learned.md`. Only the **vertical** treatment differs: the rise is a
  single drop at the lip rather than spread along a walkable slope.
- Keep the opening wide/clear enough that the player actually falls through (no
  lip geometry that blocks the fall or that the agent would read as a wall it
  can't pass).

## Realization 2 — one-way wall/door (planar, equal Z) — honest scope decision

A one-way wall is a passage at (near-)equal floor height you can go through from
one side only. Unlike a drop, its one-wayness is a **semantic/collision
property, not a height barrier** — geometrically it is close to an ordinary
corridor opening at the same floor height.

**The hard constraint (grounded in this repo's settled facts):**

- **EQG collision is per-triangle; the mesh is the collision model.** There is
  no one-sided-triangle collision and no scripting in the mesh. A flat opening
  you can walk through one way is walk-through-able **both** ways. So a true
  "passable from one side only" wall **cannot be baked into the `.ter`** —
  geometry physically cannot enforce it at equal Z.
- **Doors are runtime records, not geometry (settled).** An actual
  openable-from-one-side door is a row in the EQEmu `doors` table that the
  *server* gatekeeps; the repo already handles the comparable gating feature
  this way (`GateSpec` → future SQL export), leaving the corridor an open gap.

**Scope decision (option b — IR now, enforcement at export):** Realize the
one-way wall **now** as (1) the directed IR on `CorridorSpec` (`one_way=True,
realization="wall"`, `from_`→`to_`), and (2) an ordinary, physically two-way
corridor opening at equal Z that is **marked** one-way — advisory until the
door/SQL export can enforce it. The validator treats it as a directed edge at
the room-graph level (see Core concept), and the future EQEmu door/SQL export
owns turning that marking into an enforced door record. We do **NOT** claim
collision-level one-way at equal Z, because the per-triangle mesh cannot deliver
it and doors-are-records is a settled call.

Rationale for picking (b) over the alternatives:

- **(a) fully realized now as geometry** — rejected: impossible under
  per-triangle collision at equal Z (above). The only "geometry" that enforces
  one-wayness is a height barrier, which is Realization 1 (a drop), not a wall.
- **(c) defer entirely to the door-export task** — rejected as the *primary*
  path because the whole point of this task is the directed-edge abstraction;
  landing the IR + directed-reachability now (shared with the enforced drop)
  means the future door export only has to *consume* an existing seam rather
  than invent it. (c) is effectively what the enforcement half becomes — this
  task explicitly leaves the physical gatekeeping of a `realization == "wall"`
  edge to the door/SQL export, and says so in Notes so nobody later mistakes the
  advisory marking for an enforced wall.

So: **drop is enforced now (geometry); wall is directed IR + advisory marking
now, enforced later by the door export.** The task tests the wall at that honest
level — IR + directed reachability — not at a collision level the engine can't
deliver yet.

## Control surface — how a user asks for one-way connections

Thread the controls through every layer, all converging on
`generators/pipeline.py::generate_validated` via the `spec_factory` closure (no
change to `pipeline.py` itself — the closure captures the controls). Note the
precedent is only partial: `locks` reaches `generate()` **only** through the
plan path (`ZonePlan.locks` → `plan_to_spec`) — it is NOT wired to the CLI or
the control-driven factories today (`main.py`'s factory calls
`generate(name, room_count=rooms)`; `server/app.py`'s control `factory` calls
`generate(zone_id, room_count=rooms, elevation=...)`; neither passes `locks`,
and there is no `--locks` flag or `locks` on `GenerateRequest`/`GenerateParams`).
So the plan-path wiring copies the existing `locks` pattern, but the **CLI and
control-path wiring is NEW** — you are adding the field to those surfaces for the
first time.

Control shape — expose **a count and a kind**:

- `LayoutGenerator.generate(..., one_way: int = 0, one_way_kind: str = "drop")`
  — how many one-way edges, and which realization (`"drop"` | `"wall"`). Default
  0 = today's behaviour. (A future v2 could mix kinds; v1 picks one kind per
  generate to keep it simple — state that.)
- **Plan layer:** add `one_way: int = 0` and `one_way_kind: str = "drop"` to
  `ai/schema.py::ZonePlan` (clamp `one_way` 0..N, validate `one_way_kind` to the
  enum in `validate()`), to `ZONE_PLAN_JSON_SCHEMA` (an integer field + an
  `enum` field the LLM may set), and pass both through
  `ai/expand.py::plan_to_spec` into `generate(...)`.
- **Rule planner:** detect keywords in `ai/rule_planner.py`. Drop words:
  "drop", "drop-down", "pit", "shaft", "trap door"/"trapdoor", "chute", "fall",
  "oubliette" → `one_way_kind="drop"`, request ≥1. Wall words: "one-way",
  "secret door", "portcullis", "collapse"/"cave-in", "squeeze through" →
  `one_way_kind="wall"`, request ≥1 (scale count the way `_lock_count` does). Add
  a focused keyword test for each kind.
- **CLI:** `main.py generate --one-way N --one-way-kind {drop,wall}` (default 0 /
  drop), threaded into the control-driven `spec_factory`.
- **Web:** a one-way count field + a kind dropdown in the web controls panel →
  `web/src/api.ts` (`GenerateParams` + POST body) → `web/src/main.ts`; and the
  matching fields on `server/app.py::GenerateRequest`, passed into the
  control-driven `factory`. Rebuild the frontend when web files change (`cd web
  && npx vite build`).

## Acceptance criteria

Each names its verification mechanism. Structural tests are **necessary but not
sufficient** in this repo (every corridor bug so far passed the suite and was
caught only in 3D), so a human 3D criterion is mandatory and listed last.

### Directed abstraction (shared core — tested once)

- [ ] **Directed IR exists and round-trips.** `CorridorSpec` gains `one_way`
      (default False) and `realization` (default ""), with the traverse-only-
      `from_`→`to_` convention (and, for a drop, top=`from_`/bottom=`to_`); a
      spec with a one-way edge saves and reloads with the flags and endpoints
      intact, and an *old* `.json` without the fields still loads (defaults
      apply). *(test: `tests/test_generators.py::TestOneWay` — plus a
      `ZoneSpec.save`/`load` round-trip assertion.)*
- [ ] **Default is a no-op.** `generate(..., one_way=0)` (the default) produces
      the same spec it does today for a pinned seed — no corridor gains
      `one_way`/`realization`, no elevation change. *(test:
      `tests/test_generators.py::TestOneWay` pins a seed and asserts the corridor
      set/flags are unchanged from the `one_way=0` baseline.)*
- [ ] **Directed reachability: a one-way-fed dead-end PASSES.** For **each**
      realization, a dungeon with a one-way edge into a dead-end room validates
      as fully reachable — every room *enterable* by following edges in their
      allowed direction — even though the dead-end has no walk-back. *(validator:
      `python -m analyzer.traverse output/<zone>.eqg` exits 0; regression:
      `tests/test_traversability.py::TestOneWay` constructs a drop-fed dead end
      AND a wall-fed dead end and asserts `report.passed` is True and the
      dead-end room's `reachable` is True in both.)*
- [ ] **A genuinely unenterable room still FAILS.** The directed change must not
      make the validator permissive: a constructed zone with a room that cannot
      be entered by any direction (e.g. an isolated room, or one reachable only
      by going *against* a one-way edge — climbing up a drop, or against a wall's
      allowed direction) still reports `passed == False` with that room
      unreachable. *(test: `tests/test_traversability.py::TestOneWay` — build the
      "reachable only against the one-way" case for both kinds and assert it
      FAILS; reuse/adapt the constructed-breakage pattern from
      `TestValidatorFlagsBreakage`.)*
- [ ] **Walking guarantees not loosened.** The directed change must not weaken
      the ordinary two-way checks: the existing traversability regressions (cliff
      ramp / oversized step / misaligned corridor on the former-bad seeds) still
      FAIL for the right reason, and the `corridor-connection` seeds
      (1955208177, 1516796975, 678358326) still PASS. Add an assertion that an
      *unintended* big vertical gap — no `one_way`/`drop` flag — is still
      reported as a failure, not silently accepted as a drop. *(test: existing
      `tests/test_traversability.py` suite stays green unchanged, plus the new
      assertion.)*
- [ ] **Determinism.** Same seed + same `one_way`/`one_way_kind` ⇒ identical spec
      (corridor set, flags, floor heights). A different `one_way` count with the
      same seed ⇒ a different spec. Test "no-op default" and "different count
      differs" against the **same pinned seed** so they stay mutually consistent
      (and so any RNG draw added for edge selection is proven not to perturb the
      `one_way=0` baseline). *(test: `tests/test_generators.py::TestOneWay`,
      following `TestLayout.test_deterministic_seed`.)*

### Realization 1 — drop (enforced by geometry now)

- [ ] **A drop is downhill and deep.** A `one_way=1, one_way_kind="drop"`
      dungeon has exactly one corridor with `one_way and realization=="drop"`,
      `from_z > to_z`, and the gap `from_z − to_z` exceeds the climbable
      threshold by the stated margin (an actual fall, not a tall step). *(test:
      `tests/test_generators.py::TestOneWay`.)*
- [ ] **Human 3D — fall and can't climb back.** Per `docs/ACCEPTANCE.md`,
      confirm in the web viewer with recorded seeds that you can walk up to a
      drop and **fall down it**, landing on the lower room's floor; it reads as a
      **ledge/shaft fall, not a ramp or stairs**; a drop-fed **dead-end room is
      reachable going in but has no walk-back** (you physically cannot climb back
      up); and nothing floats / no see-through at the lip or shaft. *(human:
      `docs/ACCEPTANCE.md` §A, §B, §C — see the combined 3D criterion below.)*

### Realization 2 — one-way wall (IR now, enforcement at export — tested at that honest level)

- [ ] **A wall edge is directed IR at equal Z, not a height barrier.** A
      `one_way=1, one_way_kind="wall"` dungeon has exactly one corridor with
      `one_way and realization=="wall"` whose two ends are at (near-)equal Z
      (`abs(from_z − to_z)` within the climbable step), and whose geometry is an
      ordinary physically-traversable opening (NOT a drop/shaft). *(test:
      `tests/test_generators.py::TestOneWay`.)*
- [ ] **The wall's one-wayness is honoured in the validator, honestly scoped.**
      The validator treats the `realization=="wall"` corridor as a **directed**
      room-graph edge (`from_room`→`to_room` only): the wall-fed dead-end PASSES
      (covered above), and a room reachable only by going *against* the wall
      FAILS (covered above). The task explicitly does NOT assert collision-level
      one-way at equal Z — that is deferred to the door/SQL export and recorded
      in Notes. *(test: `tests/test_traversability.py::TestOneWay`; scope
      statement recorded in Notes.)*

### Whole-feature gates

- [ ] **Wired end-to-end + still gated.** The one-way count/kind flows from the
      CLI (`main.py generate --one-way --one-way-kind`), the web controls (count
      + kind dropdown → `api.ts` → `/api/generate` → control `factory`), and the
      rule planner (keywords → `ZonePlan.one_way`/`one_way_kind`) through
      `generate_validated` unchanged; a generated one-way dungeon of each kind
      passes the pipeline gate (is actually served, not 503'd). *(tests:
      `tests/test_planner.py` keyword case per kind; CLI runs recorded in Notes;
      web path confirmed by a frontend build + the human 3D pass.)*
- [ ] **Full suite green** — `python -m pytest tests/ -q`.
- [ ] **Human 3D eyeball (necessary, not sufficient — this project's rule).** Per
      `docs/ACCEPTANCE.md`, confirm in the viewer with recorded seeds the drop
      behaviour described in the Realization-1 criterion above, and that a `wall`
      edge reads as an ordinary clean opening at the same floor height with no
      see-through (its one-wayness is advisory, so you may be able to walk back
      through it in-client — that is expected for v1 and noted). Record the
      seeds. Covers `docs/ACCEPTANCE.md` §A "Core generation" (generates without
      error, lands on the floor), §B "Navigability" (every room reachable on
      foot — here, directed), and §C "Enclosure / no see-through" at the one-way
      opening. *(human: `docs/ACCEPTANCE.md` §A, §B, §C.)*

## Subtasks

Ordered; each is a sensible commit.

- [ ] **Repro / baseline the validator crux.** Before changing anything,
      construct (or generate + hand-edit) a small dungeon with one deliberate
      drop and run `python -m analyzer.traverse` on it to **capture the current
      failing behaviour** (the drop-fed room reported unreachable / "oversized
      stair step or drop"). Paste the real output into Notes so the directed-
      reachability change is anchored to the measured symptom, not a guess.
- [ ] **Directed IR + convention.** Add `one_way` / `realization` to
      `CorridorSpec`, pin the traverse-only-`from_`→`to_` convention (and
      top=`from_`/bottom=`to_` for a drop, asserted when a drop is built), and
      confirm `ZoneSpec` save/load round-trips (incl. loading an old field-less
      `.json`).
- [ ] **Directed reachability in `analyzer/traverse.py`.** Make the flood fill
      directed; add the one-way **descend** transition for drops (upper→lower
      within `max_drop`, XY-overlap) on top of the unchanged symmetric walk
      adjacency; treat a `realization=="wall"` corridor as a directed room-graph
      edge; ground every one-way transition in the spec's flags so only intended
      edges are accepted. Update `classify_corridor` / the diagnosis so an
      intended one-way reads as expected and an unintended gap still fails. This
      is the make-or-break commit — land it with its own tests (`TestOneWay`).
- [ ] **Drop geometry (Realization 1).** Realize a `realization=="drop"`
      corridor as a lip/shaft fall in `MeshBuilder.add_corridor` (a
      `_add_drop_corridor` path), reusing `_emit_route` for XY routing and NOT
      regressing the Z-corridor / flush-opening fixes. Verify the drop opening is
      a clean fall (enclosed, no see-through) in a generated GLB.
- [ ] **Wall geometry (Realization 2).** Realize a `realization=="wall"`
      corridor as an ordinary flush opening at (near-)equal Z — reuse the normal
      corridor path, no new mesh trick — marked one-way in the IR. Confirm the
      opening is enclosed (no see-through) and that the directed reachability
      from the previous subtask treats it one-way. Record the deferred-
      enforcement scope in Notes.
- [ ] **Layout: choose + orient drops / place walls.** Add `one_way` /
      `one_way_kind` to `generate(...)`; select the edges from `self.rng` under
      the stated connectivity-safe rule; for drops, orient downhill and deepen
      the Z gap past the climbable threshold with margin; for walls, keep the two
      ends at (near-)equal Z and just mark direction; emit the directed
      `CorridorSpec` in `_build_corridors`. Keep `one_way=0` a provable no-op.
- [ ] **Control surface.** Thread the count + kind through `ai/schema.py` (+ JSON
      schema), `ai/expand.py`, `ai/rule_planner.py` (drop + wall keywords +
      tests), `main.py generate --one-way/--one-way-kind`,
      `server/app.py::GenerateRequest` + the control factory, and
      `web/src/{api,main}.ts` + the controls markup. Build the frontend when web
      files change.
- [ ] **Tests.** `tests/test_generators.py::TestOneWay` (IR, no-op default,
      determinism, drop-downhill-and-deep, wall-equal-Z) and
      `tests/test_traversability.py::TestOneWay` (one-way-fed dead-end PASSES for
      both kinds, against-direction FAILS for both, walking guarantees intact),
      plus the rule-planner keyword cases. Keep it focused — new feature →
      targeted regressions, no padding.
- [ ] **Full suite green** (`python -m pytest tests/ -q`); generate the eyeball
      seeds (at least one drop dungeon and one wall dungeon) into `output/`, run
      `analyzer.traverse` on each, and **record the concrete seed values in
      Notes** as a named artifact — this feature is new so no failing seed
      pre-exists (unlike `corridor-connection`'s pinned seeds), so the worker
      establishes and records them here for the human pass to reproduce.
- [ ] **Human 3D validation pass** per the acceptance criteria; record seeds +
      result in Notes. State explicitly that the structural tests are necessary-
      not-sufficient and the 3D fall-and-can't-climb-back check is the real
      sign-off for the drop.

## Deliverables

What actually shipped. Fill in as work lands.

- Code: `generators/zone_spec.py` (directed IR on `CorridorSpec`),
  `analyzer/traverse.py` (directed reachability + one-way descend + wall-as-
  directed-edge + diagnosis), `generators/geometry.py` (`_add_drop_corridor` +
  dispatch in `add_corridor`; wall reuses the normal path),
  `generators/layout.py` (`one_way`/`one_way_kind` in `generate`, edge
  selection, downhill/deepen for drops, `_build_corridors` emit), `ai/schema.py`,
  `ai/expand.py`, `ai/rule_planner.py`, `main.py`, `server/app.py`,
  `web/src/{api,main}.ts` (+ control markup).
- Tests: `tests/test_generators.py::TestOneWay`,
  `tests/test_traversability.py::TestOneWay`, rule-planner keyword cases in
  `tests/test_planner.py`.
- Docs: this task file kept in sync; a `lessons-learned.md` note on the directed-
  reachability change (the drop gotcha + the "wall one-wayness is advisory until
  the door export" scope) once it lands. (ROADMAP / README / tasks/README index
  are integration state — see the integration note, do NOT edit them here.)
- Commits: <hashes, newest last>

## Notes / decisions / blockers

- **Why two realizations of one concept.** The human clarified that a drop-down
  is only ONE example of a one-way connection; the real feature is the directed-
  edge abstraction. A drop is the **vertical** realization (enforced by pure
  geometry — a tall ledge you can't climb); a one-way **wall/door** is the
  **planar/equal-Z** realization. They share the directed IR + directed-
  reachability core; they differ only in how (and whether) the one-wayness is
  physically enforced.
- **Realization 2 scope is deliberate and honest (option b).** At equal Z, EQG's
  **per-triangle collision** cannot express a wall passable from one side only
  (there is no one-sided collision and no in-mesh scripting), and **doors are
  runtime records, not baked geometry** (a settled design call — a door welded
  into the `.ter` is a door-shaped wall that can't open). So a `wall` edge is
  realized NOW as the directed IR + an ordinary two-way opening **marked**
  one-way (advisory), and its physical enforcement is **deferred to the future
  EQEmu door/SQL export**, which owns the `doors` table exactly as the gating
  feature's `GateSpec` already does. Do NOT promise collision-level one-way walls
  — the engine/export can't enforce them yet. The **drop**, by contrast, IS
  enforced now because it is pure geometry.
- **The crux restated:** the validator's adjacency is symmetric
  (`abs(dz) <= max_step_up`), so (a) a real drop produces NO adjacency either way
  and the flood fill can't even descend, and (b) a wall at equal Z reads as an
  ordinary two-way opening. The fix is a **directed** flood fill plus a
  spec-grounded one-way transition per realization: a **directed descend** for
  drops (upper→lower, within `max_drop`, XY-overlap, ON TOP of the unchanged
  symmetric walk adjacency), and a **directed room-graph edge** for walls — never
  a loosening of the step-up/slope test (that still must catch cliffs and
  oversized steps for ordinary floors). Keep the three drop thresholds
  consistent: `max_step_up` (~3u, climbable step), the layout's deepen-margin
  (make a drop clearly > step), and the validator's `max_drop` (fall bound).
  Record the chosen values together.
- **Measurement trap (from `corridor-connection`):** when probing floor Z at an
  opening, use a probe ALONG the wall line / NEAREST-vertex carefully — a plain
  wide-window probe latched onto a stair-tread edge and gave a false "ramp gap"
  reading before. Reuse `scripts/measure_corridors.py` patterns if you measure
  the drop lip.
- **Structural tests pass ≠ done.** Per `lessons-learned.md` and the cave
  history, the suite can be green while the viewer shows something wrong. The 3D
  fall-and-no-walk-back check is the real gate; do not mark `done` on a green
  suite alone.
- **Env / tooling (pwsh):** shell is PowerShell — `;` not `&&`, `Remove-Item`,
  `$env:VAR`. Commit via a temp message file (`git commit -F
  .git/COMMIT_EDITMSG_TMP`, then delete it) — heredocs fail in pwsh. The
  commit-message hook blocks the literal words "Vite" and "dev server"; describe
  the frontend build without them. Don't push agent branches.
- **Backends:** dungeon-only for v1. Cave is shelved (untrustworthy in 3D) and
  outdoor's heightfield mesh is in a different coordinate frame from the room
  graph, so the validator can't map rooms onto it (both ROADMAP Known issues).
  One-way edges rely on the box backend's elevation machinery and the
  dungeon-gated validator; applying them to cave/outdoor would ride on
  broken/ungated ground. State this; don't try to extend v1.
- **Dependency: `tasks/layout-topology-control.md`.** That task adds the
  `topology` named-mode control (linear / branching / looped) that changes which
  *undirected* edges exist in `_connect_rooms`. THIS task is the second of the
  split pair: directed one-way edges are an edge **attribute** layered on
  whatever undirected graph topology produced. **Do not redo topology-shape work
  here** — build on the graph it hands you. If topology has landed when this
  starts, the one-way edge selection should work over whatever edge set topology
  produced (loop edges in particular are the natural candidates, and `looped`
  yields more of them). If topology has *not* landed, this still works on today's
  MST+12%-loops graph — just note the ordering.

---

### Integration note (for the single-writer integration step — do NOT apply here)

- **RENAME:** this task was renamed `layout-oneway-dropdown` → `layout-oneway-
  connections` (the id now reads as the general directed-edge feature, not just
  the drop realization). The old `tasks/layout-oneway-dropdown.md` is removed;
  there is no stale duplicate. Any board row for the old id must be replaced.
- `tasks/README.md` board — add (or replace the old `layout-oneway-dropdown`
  row with) a row:
  `| [layout-oneway-connections](layout-oneway-connections.md) | not-started | Layout controllability — one-way (directed) connections: drop-down (vertical, geometry-enforced now) + one-way wall (planar equal-Z, IR now / enforced at door export); directed reachability in the validator; builds on layout-topology-control; dungeon-only v1 |`
- No existing ROADMAP "Next" item names this; when it lands, note it under
  layout controllability / refinement alongside `layout-topology-control`, and
  record the settled decisions: dead-end-behind-a-one-way is allowed,
  reachability becomes DIRECTED (enter-every-room, no forced return path),
  dungeon-only v1, drop enforced by geometry now / wall enforced at the future
  door export.
