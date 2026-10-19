# TASK: layout-topology-control

Status: not-started        <!-- not-started | in-progress | blocked | done -->
Epic: Layout controllability — give the prompt/controls a handle on the room
graph's *shape*, the tier below ROADMAP "content layer / refinement". New
generator feature; no ROADMAP "Next" item names it yet (surface as an
integration note — see below).
Last touched: created (task-author draft)

## Goal

Let the user choose the **overall shape of a zone's room graph** — whether the
rooms string together as a mostly-linear corridor-chain, branch out into a tree
with side passages and dead-ends, or interconnect into a loopy network with many
alternate routes. Today this is not controllable: the layout always builds the
same shape (a minimum spanning tree over the rooms plus a *fixed* ~12% of the
leftover edges added back as loops), so every zone has the same middling
branchiness. This task adds one new control — call it **`topology`** — exposed
on the generator and threaded through the CLI, the web controls, and the prompt
planner, that selects between a small set of named shapes. Done when: picking
`linear`, `branching`, or `looped` produces graphs whose measured shape
(edge count, node-degree distribution, number of loops) is reliably and
visibly different; every room still stays reachable on foot in all three modes
and across all four themes; the same seed + same `topology` still reproduces an
identical zone; and a human confirms in the 3D viewer that a `linear` zone reads
as a corridor-string while a `looped` zone reads as interconnected.

Explicitly **out of scope** (a separate, later task): one-way / directed
connections and drop-down (fall-through, can't-climb-back) edges, and any
geometry for them. This task only changes which *undirected* edges exist, never
their direction or verticality semantics. See "Dependencies / follow-ups".

## Background (what a reader needs to know)

The **room graph** is the zone's abstract floor plan: rooms are nodes, corridors
are the edges that join them; every geometry backend (box dungeon/city, organic
cave, heightfield outdoor) turns that same graph into 3D unchanged. It is built
in `generators/layout.py::_connect_rooms`:

1. **Delaunay triangulation** of the room centres → a set of candidate edges.
2. **Minimum spanning tree** (Kruskal, shortest-first) over those candidates →
   the smallest connected sub-graph that reaches every room. This *guarantees
   reachability* and is the only structure that must never be weakened.
3. **Add-back loops:** the non-tree candidate edges ("extra") are shuffled and a
   hardcoded fraction is added back —
   `n_add = max(0, int(len(extra) * 0.12))` — to create alternate routes.

That fixed 12% is the *only* topology knob today, and it is not user-facing.

Two facts the implementer must respect:

- **An MST is not automatically linear.** Depending on where rooms land, the
  shortest-edge spanning tree can be a long path *or* a bushy star (one hub room
  wired to many others). So "linear" cannot be implemented as merely "MST with
  0% loops" — that can still come out star-shaped with a high-degree hub. A
  genuinely linear zone wants a **low-degree, path-like spanning structure** (a
  near-Hamiltonian chain through the rooms), not just zero loops. The task must
  change the *spanning-structure choice*, not only the loop fraction. (See
  "Design" for the concrete approach.)
- **Reachability is sacred.** Whatever structure a mode builds, it must still
  connect every room. The traversability validator (`analyzer.traverse`, baked
  into the generate hot path via `generators/pipeline.py::generate_validated`
  for dungeons) will *reject* and retry any dungeon that strands a room, so a
  topology mode that can disconnect the graph will manifest as generation
  failures / 503s, not silently.

## Design (decide + justify in the task; this is the recommended shape)

**Control shape: a named mode**, `topology ∈ {linear, branching, looped}`, with
`branching` the default (it reproduces today's behaviour, so existing seeds and
tests are unaffected unless they opt in). Rationale for a named enum over a raw
0..1 scalar: it matches the project's existing plan-layer control vocabulary
(`size`, `verticality` are named modes on `ai/schema.py::ZonePlan`, realized in
`ai/expand.py` — note `topology` itself goes a tier lower, as a `generate()`
parameter, but the named-mode precedent still holds), maps cleanly onto a web
dropdown, onto rule-planner keyword buckets, and onto an LLM `enum` in the plan
schema, and it lets
`linear` change the *spanning structure* (not just a loop percentage) — which a
single "loopiness" scalar cannot express. If, during implementation, a scalar
knob is still wanted it can ride *alongside* the mode later; do not block on it.

Each mode concretely sets the two real levers in `_connect_rooms`:

| Mode | Spanning structure | Extra-edge fraction |
|------|--------------------|---------------------|
| `linear` | A **low-degree, path-like** spanning tree over the Delaunay candidates (a chain that visits rooms in a spatial order — e.g. a greedy nearest-neighbour path, or an MST built with a degree penalty so no room becomes a hub), capped so max node degree stays small (target ≤ 3). | **0%** — no loops added. |
| `branching` | Today's shortest-edge MST (unchanged). | **~12%** (today's value — keep as the branching default so nothing regresses). |
| `looped` | Today's shortest-edge MST. | **High** — add back most/all of the extra edges (e.g. ~60–100% of `extra`), producing many cycles / alternate routes. |

The spanning structure and the add-back set must both be drawn from
`self.rng` (the existing seeded generator) so pinned seeds reproduce. Put the
mode selection inside `_connect_rooms` (or a helper it calls) so all three
backends inherit it for free — do **not** fork per-backend.

Degenerate cases to keep working: `room_count` 1 (no edges) and 2 (single edge)
must behave identically in every mode; a Delaunay fallback-to-chain (collinear
points) already yields a linear chain and is fine for any mode.

## Acceptance criteria

Each is checkable with existing tooling (pytest under `tests/`, graph-metric
assertions on the generated edge/corridor list, `analyzer.traverse`) plus the
named human 3D pass. "Edges" = the room-graph edges, read either from
`_connect_rooms` directly or reconstructed from `spec.corridors` the way
`tests/test_generators.py::TestLayout.test_connectivity_reachable` already does.

- [ ] **New `topology` parameter exists and defaults to today's behaviour.**
      `LayoutGenerator.generate(..., topology="branching")` with the default
      value produces the *same* graph it does today for a given seed (a
      regression test pins a seed and asserts the edge set is unchanged from the
      pre-change baseline, so `branching` is provably a no-op rename of current
      behaviour). *(test: `tests/test_generators.py::TestTopology`)*
- [ ] **The three modes are measurably distinct.** For a sweep of ≥10 seeds at
      `room_count=14`, assert the graph metrics order as expected:
      `linear` has the **fewest** edges (≈ n−1, i.e. zero or near-zero cyclomatic
      number `E − N + 1`) and a **low max degree** (≤ 3); `looped` has the
      **most** edges and a **strictly higher** cyclomatic number than
      `branching`, which in turn is ≥ `linear`. Assert the ordering
      (`loops(linear) ≤ loops(branching) < loops(looped)` and
      `maxdeg(linear) ≤ maxdeg(branching)`), not brittle absolute counts.
      *(test: `tests/test_generators.py::TestTopology`)*
- [ ] **`linear` is actually path-like, not a star.** On the same sweep, assert
      `linear`'s max node degree ≤ 3 and that it has ≥ (n−3) degree-≤2 nodes —
      i.e. it reads as a chain, catching the "MST came out star-shaped" trap
      called out in Background. *(test: `tests/test_generators.py::TestTopology`)*
- [ ] **Reachability preserved in every mode.** For each mode, every room is
      reachable from the entrance across a seed sweep — reuse the reachability
      walk in `test_connectivity_reachable`, parametrised over the three modes.
      *(test: `tests/test_generators.py::TestTopology`)*
- [ ] **Determinism holds.** Same seed + same `topology` ⇒ identical edge set
      (and identical room positions). Room-position equality follows the pattern
      in `TestLayout.test_deterministic_seed` (which compares centres only); the
      **edge-set** equality is a new, stronger assertion this task adds on top.
      Different `topology` with the same seed ⇒ a different edge set (modes don't
      collapse together).
      *(test: `tests/test_generators.py::TestTopology`)*
- [ ] **All backends still build; dungeon still passes the validator.** Generate
      a dungeon in each mode and confirm `analyzer.traverse output/<zone>.eqg`
      exits 0 (every room reachable on the real mesh), and that cave/outdoor/city
      generate without error in each mode. *(validator:
      `python -m analyzer.traverse output/<zone>.eqg`; smoke: the generate call
      itself under `tests/test_generators.py::TestTopology`)*
- [ ] **Control is wired end-to-end.** The CLI (`main.py generate --topology`),
      the web controls (dropdown → `api.ts` → `/api/generate`), and the rule
      planner (keywords, e.g. "winding/maze/interconnected" → `looped`,
      "straightforward/linear/corridor" → `linear`) all set it, and it flows
      through `generators/pipeline.py::generate_validated` unchanged. *(tests:
      `tests/test_planner.py` keyword case for the rule planner; manual CLI run
      recorded in the task notes; web path confirmed by a build +
      the human 3D pass below)*
- [ ] **Human 3D eyeball (necessary, not sufficient — this project's rule).**
      Per `docs/ACCEPTANCE.md` the structural tests above are necessary but NOT
      sufficient for a geometry/layout change, so confirm in the web viewer with
      recorded seeds that: a `linear` dungeon reads as a **corridor-string**
      (walk end to end, few/no side branches), a `branching` one has side
      passages/dead-ends, and a `looped` one is visibly **interconnected** (you
      can circle back by a different route). Check the top-down map (press **M**)
      as the quick read. Covers `docs/ACCEPTANCE.md` §A "Core generation"
      (generates without error, randomness) and §B "Navigability" (every room
      reachable on foot) for all three modes, plus §E "Map reads correctly".
      Record the seeds used. *(human: `docs/ACCEPTANCE.md` §A, §B, §E)*

## Subtasks

Ordered; each is a sensible commit.

- [ ] **Baseline + metrics harness.** Before changing anything, capture the
      current edge set for a couple of pinned seeds (so the `branching`-is-a-noop
      regression has a reference), and write the small graph-metric helpers the
      tests need (edge count, degree sequence, cyclomatic number `E−N+1`,
      reachability) — reuse the adjacency reconstruction from
      `test_connectivity_reachable` rather than inventing a new one.
- [ ] **Add the `topology` lever to `_connect_rooms`.** Implement the three
      modes per the Design table: a path-like/degree-capped spanning structure
      for `linear`, today's MST for `branching`/`looped`, and the per-mode
      extra-edge fraction. Keep all randomness on `self.rng`. Leave
      `generate(...)`'s default as `branching` so nothing regresses.
- [ ] **Thread `topology` through `generate(...)` and the planner path.** Add the
      parameter to `LayoutGenerator.generate`, to `ai/schema.py::ZonePlan` (+ the
      LLM JSON schema enum) and `ai/expand.py::plan_to_spec`, and detect keywords
      in `ai/rule_planner.py`. The server/CLI call `generate_validated` with a
      `spec_factory` closure, so `topology` is just captured in that closure — no
      change to `pipeline.py` itself.
- [ ] **Wire the CLI + web controls.** Add `--topology` (choices
      linear/branching/looped, default branching) to `main.py generate`; add the
      dropdown to the web controls panel, the field to `GenerateParams`/the POST
      body in `web/src/api.ts` and `web/src/main.ts`, and the field to the
      server's `GenerateRequest` in `server/app.py`. Build the frontend
      (`cd web && npx vite build`) when web files change.
- [ ] **Tests.** Add `tests/test_generators.py::TestTopology` covering every
      acceptance criterion above (distinctness ordering, linear-is-path-like,
      reachability per mode, determinism, branching-is-noop baseline), and a
      rule-planner keyword case in `tests/test_planner.py`. Keep it focused — one
      class, no test-for-test's-sake padding.
- [ ] **Full suite green** (`python -m pytest tests/ -q`) and generate the
      eyeball seeds (one dungeon per mode) into `output/` for the human pass;
      run `analyzer.traverse` on each dungeon.
- [ ] **Human 3D validation pass** per the acceptance criterion; record seeds +
      result in Notes. Note explicitly in Notes that the structural tests are
      necessary-not-sufficient and the 3D pass is the real sign-off.

## Deliverables

What actually shipped. Fill in as work lands.

- Code: `generators/layout.py` (the `topology` lever in `_connect_rooms` +
  `generate`), `ai/schema.py`, `ai/expand.py`, `ai/rule_planner.py`,
  `server/app.py`, `main.py`, `web/src/{api,main}.ts` (+ the control markup).
- Tests: `tests/test_generators.py::TestTopology`; a rule-planner keyword case in
  `tests/test_planner.py`.
- Docs: this task file kept in sync. (ROADMAP / README / tasks/README index are
  integration state — see the integration note, do NOT edit them here.)
- Commits: <hashes, newest last>

## Notes / decisions / blockers

- **Scope fence — topology SHAPE only.** One-way / directed edges and drop-down
  connectors are a *separate* follow-up task. This one never gives an edge a
  direction or a fall-through semantic; it only decides which undirected edges
  exist. If an elegant seam for direction suggests itself while editing
  `_connect_rooms`, note it for the follow-up rather than building it.
- **Dependencies / follow-ups:**
  - *Follow-up (not in scope):* one-way / drop-down connections — will likely
    reuse the same `topology`/edge-selection seam and the stair/ramp helper from
    `corridor-connection`.
  - *Interaction with elevation:* `_assign_elevation` and `_relax_elevation` BFS
    over the edge set, and the `corridor-connection` grade cap bounds `dz` by
    corridor run. A `looped` graph has more (and more loop) edges, so expect
    `_relax_elevation` to do more work; a `linear` graph has fewer edges and
    longer chains. Verify elevation still lands walkable in all three modes (the
    validator covers this for dungeons) — it should, since nothing about the
    elevation math changes, but it's the obvious place a surprise hides.
  - *Interaction with gating:* `_apply_gating` locks BFS-tree edges; with
    `linear` (near-pure tree) there are fewer non-tree edges, with `looped` many
    more. Solvability is still guaranteed by construction, but a quick check that
    `locks>0` + each topology still passes the existing gating-solvability tests
    is worth a line in the test.
- **Structural tests pass ≠ done.** Per `lessons-learned.md` and the cave
  history, automated connectivity/metric tests can be green while the viewer
  shows something wrong. The human 3D pass is the real gate for this layout
  change — do not mark `done` on a green suite alone.
- **Env / tooling (pwsh):** shell is PowerShell — use `;` not `&&`,
  `Remove-Item`, `$env:VAR`. Commit via a temp message file (`git commit -F
  .git/COMMIT_EDITMSG_TMP`, then delete it) — heredocs fail in pwsh. The
  commit-message hook blocks the literal words "Vite" and "dev server"; describe
  the frontend build without them. Don't push agent branches.
- **Determinism caveat to watch:** if `linear` uses a greedy nearest-neighbour
  path, make sure any tie-breaking / starting-room choice is drawn from
  `self.rng`, not from set/dict iteration order, or two runs of the same seed
  could diverge.

---

### Integration note (for the single-writer integration step — do NOT apply here)

- `tasks/README.md` board — add a row:
  `| [layout-topology-control](layout-topology-control.md) | not-started | Layout controllability — user control of room-graph shape (linear / branching / looped); topology SHAPE only, one-way/drop-down edges are a separate follow-up |`
- No existing ROADMAP "Next" item names this; suggest noting it under
  refinement / layout controllability when it lands, and recording the chosen
  control shape (named mode `linear`/`branching`/`looped`, default `branching`).
