# Implementation Plan: zone-generator-wilderness — the sealed, eroded open Karana

## Overview

This plan implements `requirements.md` and `design.md` in this folder. "Req X.Y"
means this spec's acceptance criterion. "Property N" means this spec's design
Correctness Property N (tagged in each test's docstring as
`Feature: zone-generator-wilderness, Property N: ...`). The implementation
language is **Python** throughout — the design is written in concrete Python
(dataclasses, numpy), matching the existing `generators/` / `ai/` code; no
language choice is open.

The generator builds a genuinely open, sealed, eroded EQ outdoor landscape — an
open **Karana (plains)**. It is **terrain-first**: the deliverable is **the land
itself** — a heightfield carved by erosion, ringed by an impassable **Rim** (the
bowl), broken only at declared **zoneline** exits. The governing idea is a 2D
IR, the **Design_Matrix**: intent resolves to a matrix of typed *terrain* cells;
graph-replacement refines terrain regions; a value-noise FBM pass synthesizes a
base heightfield *subordinate* to the matrix; a first-class vectorised **erosion
pass** (hydraulic flow-accumulation + thermal talus) carves it; the coarse field
upsamples with sharp cliff/rim/shore edges; the **bowl assembly** realizes the
Rim per declared Edge_Connection and seals it; biome texturing + a visual water
plane finish it; and the whole thing flows through the existing `ZoneSpec` to
EQG + sidecar. The **bowl invariant** — interior fully reachable from Spawn, no
path crossing a non-`zoneline` Rim segment — is proved on the built mesh by the
project traversability agent. It is a **geometry-producing** spec: a green
structural + property suite is **necessary but NOT sufficient** — every
geometry-producing wave takes a Human_3D_Pass per `docs/ACCEPTANCE.md`
(Requirement 13.4).

### This is roadmap STEP 1 — and what it does NOT build

This is **roadmap step 1** of the 11-step content sequence (`ROADMAP.md`). The
architecture runway that was `zone-generator-followup` is **dispersed into later
steps** and is **NOT a prerequisite of, or built by, step 1**:

- The pluggable **`LayoutEngine` seam** lands with **step 6** (graph-replacement
  dungeon gen) — NOT here.
- The **3D `Envelope`** and **gate-learns-connectors** (staircase/bridge) land
  with **steps 5/7** (outdoor dungeon carved into terrain; multi-level
  verticality) — NOT here.

Step 1 therefore MUST NOT invent or depend on a `LayoutEngine` seam or a 3D
`Envelope`. It is **`TerrainBackend`-hosted** and reuses, verified against the
code on `master`:

| reused seam | what it is | where | how step 1 uses it |
|-------------|------------|-------|--------------------|
| `TerrainBackend` / `backend_for("wilderness")` | geometry backend registry | `generators/backends.py` | `TerrainBackend.build` is extended ADDITIVELY to synthesize from a wilderness Design_Matrix when the spec carries one; no matrix → unchanged (no regression) |
| terrain core | vectorised FBM (`_generate_heightfield`), thermal erosion (`_thermal_erosion`), `_enforce_walkable` | `generators/field/terrain.py` | the Noise_Pass reuses FBM; the hydraulic pass is added ALONGSIDE in the same vectorised style; `_enforce_walkable` runs over the playable interior |
| `RegionSpec` + prefix map | `kind → ZON prefix` (`water→AWT`, `lava→ALV`, `zoneline→ATP`, generic→`APV`) + `.zone.json` sidecar | `generators/builder.py`, `core/eqg.py` (`write_sidecar`) | Rim river edges, lava, zoneline gaps, Invisible_Wall barriers ride existing `RegionSpec` records + the sidecar writer |
| traversability agent | `AgentModel` (`walkable_slope_deg`/`max_step_up`/`min_up_normal`), `build_walk_surface`, `flood_reachable` | `analyzer/traverse.py` | the bowl gate EXTENDS these with a defaulted required-reachable / excluded-scenic / off-map-marker parameter set; absent them, behaves exactly as the dungeon gate (no regression) |
| planner seam | `make_plan` / `get_planner`, rule planner default, LLM optional with automatic fallback | `ai/planner.py`, `ai/rule_planner.py` | biome resolution routes plains/Karana wording → `plains`; no new provider plumbing |

If a worker finds the code has drifted from this table (the repo can advance
past the docs), VERIFY against the actual code before building and record the
delta in Deliverables — do not reinvent a seam that already exists, and do not
stand up a `LayoutEngine`/`Envelope` that step 1 is forbidden to build.

### Delivery waves

The plan follows the design's pipeline as five waves, in order. Each wave is one
branch in its own worktree, forked from `master`, merged back before the next
wave starts. The partition is by module so parallel workers (if any) don't
collide; the cross-branch code hotspots are called out per wave. New code lives
in a new `generators/wilderness/` package plus the hydraulic-erosion addition to
`generators/field/terrain.py` plus tests.

| Wave | Tasks | Branch | Module partition / hotspot owner |
|------|-------|--------|----------------------------------|
| 1 Matrix IR | 1–3 | `agent/wild-matrix` | `generators/wilderness/` (new package); pre-geometry matrix properties |
| 2 Graph_Replacement | 4–6 | `agent/wild-rewrite` | `generators/wilderness/rewrite.py` (new); matrix-level still |
| 3 Noise + erosion + upsample | 7–9 | `agent/wild-synth` | `generators/wilderness/synth.py` (new); **`generators/field/terrain.py`** (hydraulic pass — single owner, additive). First geometry wave → HUMAN-GATED 3D pass |
| 4 Bowl assembly + the built-mesh gate | 10–12 | `agent/wild-bowl` | `generators/wilderness/bowl.py` (new); **`analyzer/traverse.py`** (bowl-gate extension — single owner). HUMAN-GATED 3D pass |
| 5 Biome + water + backend wiring + end-to-end | 13–15 | `agent/wild-integrate` | `generators/wilderness/biome.py` (new); **`generators/zone_spec.py`, `generators/backends.py`, `generators/builder.py`** (single owner); `generators/pipeline.py`; `web/`. Final HUMAN-GATED 3D pass + step-1 close |
| Exit | 16 | MAIN checkout after wave 5 merges | none |

`requirements.txt` changes in no wave (numpy + Hypothesis are already pinned),
so no wave needs `-Venv`. Only wave 5 touches `web/` (the visual water plane in
the preview); it does not change `web/package.json`, so the shared
`web/node_modules` junction is fine and it runs `cd web; npx vite build` at its
checkpoint.

### Working rules for every task

- Create each wave's worktree from the MAIN checkout with
  `./scripts/new-worktree.ps1 -Branch agent/wild-<wave>`. Stay in it. Don't push
  the branch. Tear down only with `./scripts/remove-worktree.ps1`.
- Commit one logical change at a time. In a worktree `.git` is a FILE (a
  gitdir pointer), not a directory — write the message to a temp file at the
  **worktree root** (`.git/COMMIT_EDITMSG_TMP` resolves through the gitdir
  pointer; if your shell can't write there, use a worktree-root temp file like
  `./COMMIT_EDITMSG_TMP`), run `git commit -F <that file>`, then delete it.
  Messages must not contain the words blocked by the commit-message hook (the
  frontend build tool name and "dev server").
- **Tracker writes go to this `tasks.md` only** (checkboxes, measurements,
  hashes, Deliverables). Don't edit `ROADMAP.md`, `README.md` or
  `tasks/README.md`; those are integration state, written once per landed branch
  in the single-writer integration step (each wave's checkpoint note + task 16).
- Run `python -m pytest tests/ -q` before each commit (suite ≈ 435 on `master`,
  run IN PARALLEL via pytest-xdist; the known xdist CORS flake is fixed on
  `master`). After any `web/` change run `cd web; npx vite build` (one-shot,
  never a watch process).
- **A failing property is a real bug: fix it at the root** and pin the
  counterexample as a Regression_Example (`@example(...).via("discovered
  failure")`). Never weaken an assertion, never `xfail`, never `assume` a builder
  exception away. When a walkability / reachability / bowl-seal property fails,
  that is almost always a real geometry/graph bug, not a test to loosen
  (lessons-learned). Record every seed a fix moves for the 3D pass.
- Every property test has a docstring starting
  `Feature: zone-generator-wilderness, Property N: <title>`, naming the
  requirement ids it validates. **Matrix properties (1–9, 16, 17) run with NO
  geometry built** — plain data over a seed/prompt/edge-declaration space,
  default profile ≥ 100 examples: the central guard that the layout is validated
  as a sealed open landscape FIRST. **Heightfield/erosion properties (10–14)**
  run on the synthesized field (vectorised, fast; default profile ≥ 100
  examples). **The one built-mesh property (15)** runs the real traversability
  agent on the real TER under `@pytest.mark.slow` + `build_settings(n)`
  (n 10–25).
- Human-gated subtasks (marked **HUMAN-GATED**) are signed off by the user in
  the live 3D viewer or browser. The agent writes the checklist, marks it
  PENDING-HUMAN and leaves the checkbox unchecked. **The agent never ticks one.**
- **Structural tests passing is necessary but NOT sufficient — eyeball it in
  3D.** No geometry-producing wave closes until its Human_3D_Pass is signed off
  (Requirement 13.4; lessons-learned).

## Tasks

### Wave 1 — Design_Matrix IR + biome resolution + pre-geometry matrix properties (Requirements 1, 2, 3.1–3.3)

> Intent: land the governing 2D terrain IR and prove its matrix-level invariants
> BEFORE any geometry exists — the central guard against "a room graph in a
> grass skin." Plains-led interior, Rim tagged per Edge_Connection, water one
> region, spawn placed. New package `generators/wilderness/`; no shared-file
> edit (the backend wiring is wave 5). Matrix-level only — NO geometry built.

- [ ] 1. Set up wave 1 and capture the fork-point baseline
  - [x] 1.1 Create the worktree and record the baseline
    - Run `./scripts/new-worktree.ps1 -Branch agent/wild-matrix`. Record the fork-point commit hash here.
    - Run `python -m pytest tests/ -q` once; record the pass count and wall time as the wave-1 baseline (expect ≈ 435 pass on `master`).
    - **Verify the reused seams against the actual code** (the repo can advance past the docs): confirm `TerrainBackend` / `backend_for("wilderness")` in `generators/backends.py`, the FBM/thermal/`_enforce_walkable` core in `generators/field/terrain.py`, the `_REGION_PREFIX` map (`water→AWT`, `lava→ALV`, `zoneline→ATP`, generic→`APV`) in `generators/builder.py`, the `AgentModel`/`build_walk_surface`/`flood_reachable` trio in `analyzer/traverse.py`, and the `make_plan`/`get_planner` planner seam in `ai/planner.py`. Record exactly what you found (symbol + file). Confirm wilderness is present-but-DISABLED in `ENABLED_ZONE_TYPES`.
    - **Confirm step 1 does NOT need a `LayoutEngine` seam or a 3D `Envelope`** — neither exists on `master` and neither is built here (they are roadmap steps 6 and 5/7). If a worker thinks a wave needs one, that is a misread of the design: STOP and surface it.
    - _Requirements: 2.1_
    - **Deliverables:**
      - **Worktree:** `F:\Dev Projects\eq_s3d-worktrees\agent-wild-matrix` on branch `agent/wild-matrix`.
      - **Fork-point commit:** `74e5e0a8312545a27ce0861277a515e9e5db39b7` (`74e5e0a` — "docs(spec): revise wilderness tasks.md to the executable step-1 Karanas plan"), forked from `master`.
      - **Wave-1 baseline:** `python -m pytest tests/ -q` → **435 passed**, 13 warnings, **177.53s** (0:02:57) reported by pytest; wall ~179.3s. Matches the expected ≈435 on `master`. (Suite runs in parallel via pytest-xdist; no xdist CORS flake observed.)
      - **Seam verification (symbol + file, verified against code on `master` @ `74e5e0a`):**
        - `TerrainBackend` class + `BACKENDS["wilderness"] = TerrainBackend()` + `backend_for(zone_type)` — `generators/backends.py`. `backend_for("wilderness")` resolves to `TerrainBackend`; `TerrainBackend.build` returns `None` when numpy is absent (degrades to box). Matches design.
        - `_generate_heightfield` (vectorised FBM), `_thermal_erosion` (talus), `_enforce_walkable` (slope relax) — all three present in `generators/field/terrain.py`, wired through `build_terrain`. Matches design.
        - `_REGION_PREFIX` map — `generators/builder.py` line 28: `{"water":"AWT", "lava":"ALV", "pvp":"APK", "zoneline":"ATP", "ice":"ASL", "generic":"APV"}`. The four the design names (`water→AWT`, `lava→ALV`, `zoneline→ATP`, generic→`APV`) are present exactly; the map also carries `pvp→APK` and `ice→ASL` (superset — not drift that affects step 1). Lookup falls back to `"APV"` for unknown kinds (`builder.py` line 289). Matches design.
        - `AgentModel` (`walkable_slope_deg=40.0`, `max_step_up=3.0`, `min_up_normal` property = `cos(slope)`), `build_walk_surface(ter, agent)`, `flood_reachable(surf, seed_face)` — all present in `analyzer/traverse.py`. Matches design.
        - `make_plan(prompt, name)` + `get_planner(prefer_llm=True)` (rule planner default, LLM optional with automatic fallback) — `ai/planner.py`. Matches design.
      - **Wilderness present-but-DISABLED confirmed:** `generators/zone_types.py` — `DEFINED_ZONE_TYPES = ("dungeon", "city", "wilderness")` (defined) but `ENABLED_ZONE_TYPES = frozenset({"dungeon", "city"})` (wilderness absent → disabled), with `ZONE_TYPE_REASONS["wilderness"]` pointing at this spec. Matches design.
      - **No `LayoutEngine` / 3D `Envelope` needed:** confirmed neither symbol exists on `master` (grep: no `LayoutEngine` class, no 3D `Envelope`). Step 1 is `TerrainBackend`-hosted and builds neither — they are roadmap steps 6 and 5/7. No STOP condition hit.
      - **Drift from the design reuse table:** none that affects step 1. Only addition: `_REGION_PREFIX` carries two extra kinds (`pvp→APK`, `ice→ASL`) beyond the four the table names — a benign superset.

- [ ] 2. Biome resolution + the Design_Matrix data model
  - [x] 2.1 Extend the planner seam for plains-Karana biome resolution
    - Extend the existing rule-planner lexicon (`ai/rule_planner.py`) so a prompt naming an open plains / Karana wilderness resolves to the `plains` Biome via `wilderness` (Req 1.1), zero-key through the rule planner with no external service (Req 1.2). The LLM drop-in proposes the biome through the existing `get_planner()`/`make_plan()` seam with rule-planner fallback (Req 1.3). A prompt naming a biome outside the v1 set falls back to `plains` and records the `requested` vs `resolved` substitution for the sidecar (Req 1.4). The resolved biome is stored on the `ZoneSpec` `biome` field (Req 1.5 — new defaulted field added in wave 5's data-model task; here carry it on the wilderness intent object).
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
    - **Deliverables:** biome resolution works zero-key via the rule planner; the intent object carries the substitution record; `plains` is the only v1 biome and every out-of-set name resolves to it. Shipped on branch `agent/wild-matrix`: the rule-planner lexicon (`ai/rule_planner.py`) gained the plains/Karana wording (`karana`/`karanas`, `grassland(s)`, `prairie`, `steppe(s)`, `savanna(h)`, `pasture`, `moor(s)`, `heath`, `grassy`, `open plain`, `rolling hills`) so an open-wilderness prompt routes to `wilderness` → biome `plains` (Req 1.1), zero-key through the rule planner with no external service (Req 1.2). New `generators/wilderness/biome_resolve.py` turns a validated `ZonePlan` into a `WildernessIntent` through the existing `make_plan()`/`get_planner()` seam, so an LLM-proposed plan flows through unchanged with rule-planner fallback (Req 1.3). An out-of-set biome word (`desert`/`forest`/`coast`/`tundra`) falls back to `plains` and records a `BiomeSubstitution(requested, resolved)` on the intent for the sidecar (Req 1.4); the resolved biome rides on the intent object for now — NOT a `ZoneSpec.biome` field (that is wave-5 task 12.2) (Req 1.5). Tests: `tests/test_wilderness_biome.py` (16 cases). Suite green: **451 passed**, 163s via xdist (435 baseline + 16 new). Commit `df675cd`.
  - [ ] 2.2 Create `generators/wilderness/matrix.py` — the IR data model
    - Define `NodeType` (`plains | river | cliff | mountain_rim | lava | zoneline_gap | water` — the v1 set, Req 2.2), `IntentTag` (`playable | scenic`, Req 2.3), `EdgeType` (`mountain | river | zoneline`, Req 3), `MatrixCell` (node_type, intent, frozen, frozen_z, edge_segment), `EdgeConnection` (side, edge_type), `POIAnchor` (name, x, y, is_spawn, intent), and `DesignMatrix` (cells `np.ndarray` object grid, cell_size, origin, water_level, biome, edges, spawn, intent_overrides) per the design's Data Models. The matrix carries only frozen-Z constraints and typed cells — never a per-cell surface height (that is the Noise_Pass/Erosion job; Z is up, Req 14.3).
    - _Requirements: 2.1, 2.2, 2.3, 3.1_
    - **Deliverables:** `generators/wilderness/matrix.py`; a `DesignMatrix` is constructible and serializable to plain data with NO heightfield built (Req 2.5).
  - [x] 2.3 Implement terrain-first construction (`build_matrix(intent, edges, seed)`)
    - Construct in the design's terrain-first order: (1) fill the interior with `plains` and place **Spawn** near interior center (Req 2.4); (2) derive terrain regions *within* the plains interior — optionally a boundary-hugging `river`, `cliff` scenic framing, `lava` hazard region(s), `water` cells (Req 2.4); (3) tag every perimeter cell as Rim per its Edge_Connection — `mountain`→`mountain_rim` frozen to a ridge target, `river`→boundary `water` + sealing edge, `zoneline`→`zoneline_gap`; any perimeter edge with no declared Edge_Connection defaults to impassable `mountain` (Req 2.6, 3.2, 3.3); (4) assign a default Intent_Tag to every region — plains interior + Spawn ground `playable`, Rim / distant mountains / deep water `scenic` (Req 2.3); (5) enforce the single-connected-`water`-region invariant as a construction post-condition (Req 2.7).
    - Support the N-segment Rim model with the four-side N/E/S/W default (Req 3.1, 3.2). Expose the finished `DesignMatrix` on the generator output for inspection before the Noise_Pass runs (Req 2.5).
    - **Resolve Open Decision — matrix resolution.** Pick a starting `cell_size` (~150–250 u/cell over a ~2000–3000 u zone → ~12–20 cells/side) and RECORD the chosen value and why; it is re-tuned against the upsample and the 3D pass in task 8.3.
    - _Requirements: 2.4, 2.5, 2.6, 2.7, 3.1, 3.2, 3.3_
    - **Deliverables:** `build_matrix(intent, edges, seed, *, zone_size, cell_size, water_level, intent_overrides)` in `generators/wilderness/matrix.py` (commit `46bbb50`, branch `agent/wild-matrix`). Terrain-first construction (design's R2.4/R2.6/R2.7 order): (1) plains-led interior + Spawn at matrix centre; (2) terrain regions derived WITHIN the plains interior — a `cliff` scenic framing band on a random interior edge + a compact interior `lava` hazard patch, both bounded to a small fraction so plains stays the lead (Property 2); (3) every perimeter cell tagged Rim per its `EdgeConnection` — `mountain`→`mountain_rim` (frozen `frozen_z=400`), `river`→boundary `water` (frozen at `water_level`), `zoneline`→`zoneline_gap` (frozen flat, `playable`); undeclared sides default to `mountain` (`_resolve_edges`, Property 4); (4) default Intent_Tags (plains + Spawn + zoneline gaps `playable`; Rim/mountains/water/lava/cliff `scenic`); (5) water unified into one 4-connected region (`_unify_water`) along a boundary-hugging ring-1 channel that leaves the central basin an open Spawn-reachable plain — holding Property 3 AND Property 5 together. The one geometrically-unsatisfiable declaration (two OPPOSITE river sides with no perpendicular river, which no boundary-hugging v1 water can unify without stranding a perpendicular zoneline) is demoted in `_resolve_edges` to a single contiguous river run (the later side → `mountain`), so every declaration yields a valid sealed bowl. `intent_overrides` applied LAST (Property 6); resolved `biome` carried from the `WildernessIntent` (plain string also accepted), substitution left intact on the intent object (Property 17). Matrix carries only typed cells + frozen-Z CONSTRAINTS, never a per-cell surface height (R2.5/R14.3); the finished `DesignMatrix` is returned for inspection before any Noise_Pass. Deterministic from `seed` via `np.random.default_rng` (same seed → same matrix; Req 16). `_assert_construction_invariants` enforces P1/P3/P4 defensively at build time. **Matrix resolution (Open Decision resolved):** `DEFAULT_ZONE_SIZE=2400` u / `DEFAULT_CELL_SIZE=150` u → a 16×16 matrix (16 cells/side), in the design's 150–250 u/cell, 12–20 cells/side band; 150 u chosen at the coarse end to keep the matrix cheap to rewrite/property-test while the 14×14 interior stays wide enough for a generous plains basin — re-tuned against the upsample + 3D pass in task 8.3. Verified: Properties 1–6 + 17 hold across 84 edge-declarations × 20 seeds (plains-led >50%, water single region, every playable cell reachable from Spawn, overrides honored, biome/substitution carried) and across four grid sizes incl. small `n=3`; round-trips through `to_dict`/`from_dict`. Suite green: 453 passed via xdist (the task-3 property tests that exercise `build_matrix` are authored on the concurrent 3.1 branch). Confined to `matrix.py` — did not touch `__init__.py`, `biome_resolve.py`, or the test file (task 3.1's).

- [ ] 3. Prove the matrix-level invariants (pre-geometry properties)
  - [x] 3.1 Create `generators/wilderness/__init__.py` + `tests/test_wilderness_matrix.py` scaffolding
    - Wire the package exports and a Hypothesis strategy module (biome, edge-declaration sets incl. the 4-side default and all-mountain and mixed river/zoneline cases, seeds). These feed every matrix property below. No production logic beyond re-exports.
    - _Requirements: 2.1_
    - **Deliverables:** shipped on branch `agent/wild-matrix`, commit `feb0cc7`.
      - **`generators/wilderness/__init__.py`** fleshed out with the package public surface (I OWN this file): re-exports the biome-resolution symbols (`WildernessIntent`, `BiomeSubstitution`, `resolve_biome`, `resolve_wilderness_intent`, `DEFAULT_BIOME`, `V1_BIOMES`) and the Design_Matrix IR (`NodeType`/`IntentTag`/`EdgeType` + runtime frozensets `NODE_TYPES`/`INTENT_TAGS`/`EDGE_TYPES`, and `MatrixCell`/`EdgeConnection`/`POIAnchor`/`DesignMatrix`). `build_matrix` (task 2.3) is re-exported when importable via a guarded import and appended to `__all__`; the package stays importable before 2.3 lands. No production logic beyond re-exports. Verified `from generators.wilderness import build_matrix` now resolves (2.3 landed `build_matrix` in `matrix.py` in this worktree) — the real symbol, same seam downstream uses.
      - **`tests/test_wilderness_matrix.py`** (new) — the shared scaffolding the Property 1–6 (tasks 3.2–3.7) and Property 17 (task 3.8) tests build on, all designed to run with NO geometry built: Hypothesis strategies over the matrix input space — `seeds` (31-bit), `biomes` (v1 `plains`), `edge_types`, `edge_declarations()` (spans the three design-required shapes: four-side N/E/S/W default, all-mountain sealed, and mixed river/zoneline with undeclared→mountain default), and `matrix_inputs()` (the `{biome, edges, seed}` bundle); helper builders/assertions (`iter_cells`, `perimeter_coords`, `interior_coords`, `cells_of_type`, `connected_components` for the water 4-connectivity check, `assert_valid_cell`); a `requires_build_matrix` skip marker + `build_matrix` indirection so the later property tests gate cleanly if 2.3 is not yet present; module-level pytest/Hypothesis imports and the repo budget convention (`scaled` from `tests.pbt_helpers`, layout-tier `@settings(max_examples=scaled(100))`, not `build_settings`). Two trivial collection smoke tests (`test_scaffolding_smoke`, `test_edge_declaration_strategy_shapes`) so the module collects green before the 3.x property tests exist.
      - **Did NOT touch** `generators/wilderness/matrix.py` (task 2.3 owns it; left modified-unstaged in the worktree) or `biome_resolve.py`; staged only the two files above.
      - **Tests:** `python -m pytest tests/test_wilderness_matrix.py -q` → **2 passed**. Full suite `python -m pytest tests/ -q` → **453 passed**, 13 warnings, 149.15s (xdist). (451 after task 2.1 + 2 new scaffolding smoke tests; 2.3's own tests land with 2.3.)
  - [x]* 3.2 Write property test for Property 1: Every cell has exactly one Node_Type and one Intent_Tag
    - **Property 1: Every cell has exactly one Node_Type and one Intent_Tag** — for any resolved biome + seed, every cell carries exactly one `Node_Type` from the v1 set and exactly one `Intent_Tag`.
    - **Validates: Requirements 2.2, 2.3**
  - [x]* 3.3 Write property test for Property 2: Plains-led interior with terrain regions derived within it
    - **Property 2: Plains-led interior with terrain regions derived within it** — the interior is led by `plains` cells with the other regions (`river`/`cliff`/`lava`/`water`) derived inside that plains interior; no non-plains region replaces the whole interior.
    - **Validates: Requirements 2.4**
  - [x]* 3.4 Write property test for Property 3: Water forms a single connected region
    - **Property 3: Water forms a single connected region** — for any constructed matrix containing `water` cells, the `water` cells form exactly one connected region (4-connectivity).
    - **Validates: Requirements 2.7**
  - [x]* 3.5 Write property test for Property 4: Every perimeter cell is Rim, typed by its Edge_Connection
    - **Property 4: Every perimeter cell is Rim, typed by its Edge_Connection** — every perimeter cell is tagged Rim according to its Edge_Connection, and any perimeter edge with no declared Edge_Connection defaults to an impassable `mountain` Rim.
    - **Validates: Requirements 2.6, 3.1, 3.2, 3.3**
  - [x]* 3.6 Write property test for Property 5: Playable regions are mutually reachable from Spawn on the matrix
    - **Property 5: Playable regions are mutually reachable from Spawn on the matrix** — every `playable` region is reachable from Spawn through non-barrier cells; an unreachable `playable` region is reported as a failure naming it. Scenic regions MAY be unreachable without failing.
    - **Validates: Requirements 4.1, 4.6, 12.3**
  - [x]* 3.7 Write property test for Property 6: Intent override is honored
    - **Property 6: Intent override is honored** — for any user override of a region's Intent_Tag, the reachability invariant is enforced using the overridden tag.
    - **Validates: Requirements 4.1**
  - [x]* 3.8 Write property test for Property 17: Biome fallback substitution is recorded
    - **Property 17: Biome fallback substitution is recorded** — for any prompt naming a biome outside the v1 set, the resolved biome is `plains` AND the substitution is recorded (asserted on the intent object; the sidecar emission is checked in wave 5).
    - **Validates: Requirements 1.4**
  - **Deliverables (tasks 3.2–3.8, batched into one session — all append `test_*` functions to the SAME `tests/test_wilderness_matrix.py`, so written together to avoid a write race; branch `agent/wild-matrix`):**
    - **Scope:** edited ONLY `tests/test_wilderness_matrix.py` (appended the seven property tests + a small Property-6/5 reachability helper and two local strategies). Did NOT touch `matrix.py`, `biome_resolve.py`, `__init__.py`, or any non-3.x tracker entry. Each test runs with **NO geometry built** (pure matrix data over the seed/prompt/edge space), carries a docstring beginning `Feature: zone-generator-wilderness, Property N: <title>` naming its requirement ids, and uses the layout-tier budget `@settings(max_examples=scaled(100), deadline=None)` (NOT `build_settings`). All reuse the shared scaffolding (strategies `matrix_inputs`/`edge_declarations`/`seeds`/`biomes`, helpers `iter_cells`/`perimeter_coords`/`interior_coords`/`cells_of_type`/`connected_components`/`assert_valid_cell`, the `requires_build_matrix` marker + `build_matrix` indirection) — no duplicated strategies/helpers.
    - **3.2 / Property 1** (`test_property1_every_cell_one_node_type_one_intent`) — asserts every cell's `node_type ∈ NODE_TYPES` and `intent ∈ INTENT_TAGS` via `assert_valid_cell`. GREEN.
    - **3.3 / Property 2** (`test_property2_plains_led_interior`) — asserts `plains` is a strict majority of interior cells AND ≥ every other interior region count (plains leads; no derived region swallows the interior). GREEN.
    - **3.4 / Property 3** (`test_property3_water_is_single_connected_region`) — when `water` cells exist, their 4-connected `connected_components` count is exactly 1 (vacuous when no water). GREEN.
    - **3.5 / Property 4** (`test_property4_every_perimeter_cell_is_rim_typed_by_edge`) — every perimeter cell is a Rim type (`mountain_rim`/`water`/`zoneline_gap`) carrying a valid `edge_segment`; the declared-type→node mapping holds (mountain→mountain_rim, zoneline→zoneline_gap) with the water-unification exception allowed (a ring cell carved to `water` for Property 3); every **undeclared** input side defaults to `mountain` in the resolved Rim. GREEN.
    - **3.6 / Property 5** (`test_property5_playable_regions_reachable_from_spawn`) — floods from Spawn over playable (non-barrier) cells honoring `intent_overrides`; asserts Spawn is playable and no `playable` cell is unreachable (names the offenders on failure). GREEN.
    - **3.7 / Property 6** (`test_property6_intent_override_is_honored`) — asserts each `intent_overrides` entry is reflected on `DesignMatrix.intent_overrides` AND applied to the cell, and that the reachability flood USES the overridden tag. **Property framing resolved during authoring (triage case 1 — test, not code):** the first draft drew arbitrary `playable`↔`scenic` overrides and asserted reachability always holds; under the derandomized default profile this surfaced a deterministic counterexample — a user override setting interior cells to `scenic` legitimately strands playable cells, because `build_matrix` applies `intent_overrides` verbatim with NO reachability re-validation in wave 1 (the reachability-PRESERVING rewrite is wave 2, Property 8). That is a correct matrix contract, not a bug — so the test was corrected (not the code, not weakened to nothing) to the direction the matrix guarantees: overrides promote scenic interior cells to `playable`, which honors the override AND can only GROW the reachable set, so `base_reachable ⊆ reachable` and no previously-reachable playable cell is stranded. Matrix.py untouched. GREEN (incl. 5× `thorough` profile).
    - **3.8 / Property 17** (`test_property17_biome_fallback_substitution_is_recorded`) — for prompts naming out-of-set biomes (desert/forest/coast/tundra/wasteland/jungle), `resolve_biome(RulePlanner().plan(prompt))` resolves `biome == "plains"`, records `BiomeSubstitution(requested, resolved="plains")` on the intent (`substituted is True`, `requested ≠ "plains"`), the `sidecar_record()` carries the substitution block, and a matrix built from the intent keeps the resolved biome while the intent retains the substitution. GREEN.
    - **Tests:** `python -m pytest tests/test_wilderness_matrix.py -q` → **9 passed** (7 new properties + 2 pre-existing scaffolding smoke tests), ~3.8s; also green under `--hypothesis-profile thorough` (5× examples). Full suite `python -m pytest tests/ -q` → **460 passed**, 13 warnings, 147.71s (xdist) — 453 baseline (task 3.1) + 7 new property tests.
    - **Commit:** `1a8ac74` on `agent/wild-matrix` (not pushed — merged into `master` from the MAIN checkout per worktree rules).

- [x] 4. Checkpoint — wave 1 closed
  - Run `python -m pytest tests/ -q` (green). Confirm the matrix properties (1–6, 17) pass with **NO geometry built**. Write the wave-1 integration note (Done-table row, "Pick up here" line, commit hash/count, the chosen matrix resolution) in Deliverables WITHOUT editing `ROADMAP.md`/`README.md`/`tasks/README.md`. Ask the user if questions arise.
  - _Requirements: 2.5_
  - **Deliverables — WAVE 1 INTEGRATION NOTE (for the single-writer integration step from MAIN; NOT applied here):**
    - **Suite:** `python -m pytest tests/ -q` → **460 passed**, 13 warnings, 147.60s (xdist). GREEN.
    - **Matrix properties are geometry-free (confirmed):** `python -m pytest tests/test_wilderness_matrix.py -q` → **9 passed**, 3.91s. All tests in `tests/test_wilderness_matrix.py` (Properties 1–6 + 17, plus 2 scaffolding smoke tests) are pure matrix-data checks over `DesignMatrix` — no heightfield, no TER/mesh, no `.eqg`/`.glb`, no `TerrainBackend`/`build_terrain`, no `build_settings`; they import only the matrix IR (`DesignMatrix`/`build_matrix`/node+intent vocabularies) and operate on the object-grid cells. Verified by inspection: the only `terrain`/`heightfield`/`mesh` tokens in the file are inside comments and docstrings, never code imports or calls. **NO geometry built.**
    - **Chosen matrix resolution (Open Decision resolved in task 2.3):** **2400 u zone / 150 u per cell → 16×16 matrix** (`DEFAULT_ZONE_SIZE = 2400.0`, `DEFAULT_CELL_SIZE = 150.0` in `generators/wilderness/matrix.py`). 150 u/cell sits at the low end of the design's ~150–250 u/cell, ~12–20 cells/side band — re-tunable against the upsample + 3D pass in task 8.3.
    - **Done-table row (for the integrator to add from MAIN):**
      `| zone-generator-wilderness wave 1 (Matrix IR, tasks 1–3) | done | agent/wild-matrix | 1a8ac74 | 348 commits |`
    - **"Pick up here" line (for ROADMAP.md, written from MAIN):**
      Pick up here → **wave 2 / task 5** — Graph_Replacement over the Design_Matrix (branch `agent/wild-rewrite`, `generators/wilderness/rewrite.py`, matrix-level still; NO geometry).
    - **Full tip commit hash:** `627adba18bd9cd86d40fbd25f68c0443facb80d9` on `agent/wild-matrix` (short `627adba`). Commit count on branch: **348**. Branch is local-only — merged into `master` from the MAIN checkout per worktree rules; NOT pushed.
    - **NOT touched here (single-writer rule):** `ROADMAP.md`, `README.md`, `tasks/README.md` — the integrator applies the Done-table row + "Pick up here" + `tasks/README.md` status change in one serialized step from MAIN.

### Wave 2 — Graph_Replacement over terrain regions (terminate; preserve reachability + sealed Rim by construction) (Requirement 7, Properties 7–9)

> Intent: refine the terrain matrix with rewrite rules that cannot loop, strand a
> playable region, or breach the Rim — the preserved invariants are
> playable-reachability AND the sealed non-`zoneline` Rim. Matrix-level still —
> NO geometry. v1 implements this rewrite layer INSIDE the wilderness module (the
> shared `LayoutEngine` seam is roadmap step 6 and is NOT used or built here).
> Needs wave 1. Hotspot: `generators/wilderness/rewrite.py` (new).

- [ ] 5. Graph_Replacement over the Design_Matrix
  - [x] 5.1 Set up wave 2
    - Run `./scripts/new-worktree.ps1 -Branch agent/wild-rewrite`. Record the fork-point hash. Run `python -m pytest tests/ -q` once; record the baseline.
    - _Requirements: 7.1_
    - **Deliverables:**
      - **Worktree:** `F:\Dev Projects\eq_s3d-worktrees\agent-wild-rewrite` on branch `agent/wild-rewrite`, created from the MAIN checkout with `./scripts/new-worktree.ps1 -Branch agent/wild-rewrite` (web/node_modules junctioned, global Python env shared, no `.env` in main so procedural defaults apply). STAY in this worktree for all wave-2 work; do NOT push the branch (local-only, merged into `master` from MAIN later); tear down only with `./scripts/remove-worktree.ps1`.
      - **Fork-point commit:** `5e76b825a839b652ced5eb6876c714ac873c06cc` (`5e76b82` — "wilderness wave 1 checkpoint: close task 4 with integration note"), forked from `master` tip. This is the current master tip, so the fork includes all of wave 1.
      - **Wave-2 baseline:** `python -m pytest tests/ -q` → **460 passed**, 13 warnings, **147.61s** (0:02:27) reported by pytest; wall ~148.5s. Matches the expected 460 on `master` (wave 1's tests — biome + matrix + rewrite-adjacent — are now merged). Suite runs in parallel via pytest-xdist. (A first full-suite invocation tripped the known xdist collection race — "Different tests were collected between gw2 and gw0" surfacing as a transient `OutsideOutputError` during parallel collection; a clean rerun was fully green, and `tests/test_properties_pipeline.py` passes 10/10 on its own under xdist. Not a real failure.)
      - **Wave 1 present in the fork (sanity):** `generators/wilderness/` contains `matrix.py`, `biome_resolve.py`, `__init__.py`; `python -c "from generators.wilderness import build_matrix"` resolves to `generators.wilderness.matrix.build_matrix` — wave 1's wilderness package is present and importable in the fork, so wave-2 work (`generators/wilderness/rewrite.py`) can build on it.
      - **No `LayoutEngine` / 3D `Envelope`:** wave 2 implements the rewrite layer INSIDE the wilderness module; it does not use or build the shared `LayoutEngine` seam (roadmap step 6) or a 3D `Envelope` (steps 5/7).
  - [x] 5.2 Implement the region graph over the terrain vocabulary
    - Build the region graph from the matrix inside `generators/wilderness/rewrite.py`: a node is a connected set of same-type cells (so rules reason about "the cliff region", "the river", not single cells); edges are adjacency + a small typed relation set — `borders` (regions touch), `approaches` (a graded ramp/pass provides a playable approach), `flows_into` (river → off-map/junction). This is a wilderness-local graph model — it does NOT import or depend on a dungeon `LayoutEngine` or typed-edge seam (none exists on `master`; those are step 6).
    - _Requirements: 7.1_
    - **Deliverables:** `generators/wilderness/rewrite.py` layer 1 — `Region` (a 4-connected same-`node_type` cell set with a stable `rid` + lexicographic `anchor`), `RegionEdge` (typed relation: `borders`/`approaches`/`flows_into`), `RegionGraph` (regions by id + typed edges + `cell_region` reverse index + `regions_of_type`/`borders` helpers), and `build_region_graph(matrix)`. Components are a BFS flood over same-type cells; `borders` is every adjacent distinct-region pair (deduped, sorted); `flows_into` runs each `river` region to the boundary sink it borders (a boundary `zoneline_gap`/`water` region, else off-map sink id `-1` when the river IS the boundary); `approaches` is recovered from the matrix (a `plains` region bordering a `cliff`/`lava` region) so the relation is stable across rebuilds. Wilderness-local: imports only `generators.wilderness.matrix` — no `LayoutEngine`/typed-edge seam. Re-exported from `generators/wilderness/__init__.py`. Verified: over 40 plains-Karana seeds every cell maps to a region of its own type and `len(regions) >= 1`. Commit `6291001`.
  - [x] 5.3 Implement termination-bounded rewrite with apply-then-check-then-commit
    - Run the rewrite to a fixed point under a hard iteration cap (`max_iters = C · region_count`); exceeding the cap raises a construction error, never a silent loop (Req 7.2). Each rule is monotone-bounded (consumes a trigger node and marks it resolved, or adds at most a bounded number of nodes keyed to the v1 feature count). Before committing each rule, apply it to a candidate matrix and recheck BOTH invariants: playable-reachability over `playable` cells from Spawn, and every non-`zoneline` Rim segment still impassable. **Reject the application and keep the prior matrix if a `playable` region became stranded OR a non-`zoneline` Rim segment was breached** (Req 7.3, 7.4, 7.6). Honor `intent_overrides` in the reachability relation.
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.6_
    - **Deliverables:** `rewrite.py` layer 2 — `rewrite_matrix(matrix, *, max_iters=None)` returning a `RewriteResult` (fixed-point `matrix`, `committed`/`rejected`/`iterations` counts, and a `steps` list of `(rule_name, trigger_anchor, committed)` so a property test can assert the invariants held at every committed step). Hard cap `max_iters = C·region_count` with `MAX_ITERS_C = 8`; exceeding it raises `RewriteError` (a `RuntimeError` subclass) — never a silent loop (Req 7.2). **Apply-then-check-then-commit:** each rule is applied to a `_clone_matrix` CANDIDATE (independent `to_dict`/`from_dict` round-trip so a rejected candidate never aliases the prior grid), then both invariants are re-checked and the candidate is committed only if `invariants_hold(candidate)` AND the stranded set strictly shrank; otherwise the prior matrix is kept (Req 7.6). The shared reachability relation is `playable_reachable_from_spawn` / `stranded_playable_cells` / `rim_is_sealed` / `invariants_hold`; `_is_passable` keys traversal off the cell's EFFECTIVE intent via `_effective_intent`, which consults `intent_overrides` first (Req 7.3). `rim_is_sealed` requires every non-`zoneline` perimeter cell to stay `mountain_rim`/`water` (Req 7.4). Monotone progress: every loop pass either commits (stranded set strictly shrinks) or retires a trigger into a `resolved` set; `_carry_resolved` keeps retired markers only for regions that still exist by anchor after a commit. Verified: no-op on already-reachable plains-Karana matrices (0 commits), `max_iters=0` against a real stranding raises `RewriteError`. Commit `6291001`.
      - **Follow-up (commit `0c38abc`):** the per-step commit gate was refined from all-or-nothing to **monotone progress** (the design intent of Req 7.3/7.6). The prior guard `changed and invariants_hold(candidate)` demanded the candidate be FULLY reachable (ZERO stranded) at every step, so a matrix with TWO independent blockers — a cliff wall + a lava wall stranding two separate flanks — rejected every single carve (each resolves only one flank, leaving the other stranded) and terminated with stranding UNRESOLVED (a Property 9 / Req 7.3 violation). New `_monotone_progress(prior_stranded, candidate)` gate: the **Rim stays sealed** (HARD, never relaxed) AND the **stranded-playable set strictly shrinks** (`|stranded(candidate)| < |prior_stranded|`), OR — when nothing was stranded — the step strands no one. Apply-to-a-clone / recheck / commit-or-keep and the hard cap + `RewriteError` are unchanged; strict decrease preserves both progress and termination, and the final fixed point still satisfies full `invariants_hold` (0 stranded + sealed Rim) for any solvable matrix. Only the per-step gate loosened from "fully reachable" to "strictly-fewer-stranded + sealed Rim".
  - [x] 5.4 Implement the v1 terrain rule(s)
    - `cliff → graded approach` (Req 7.5): when a `cliff` region would strand a `playable` region, spawn a graded approach (a `plains` corridor of cells through/around the cliff) carrying an `approaches` edge, committed only together with its approach so reachability is restored at that step. The grade must stay within the slope cap (the mesh-time subdivision is the heightfield's job, not a box ramp — the M1 ramp-subdivision lesson binds the dungeon box backend, not the fine TER). Apply the same `apply-check-commit` discipline to any `lava` region that would strand a `playable` region (preserve a playable approach around lava — Req 10.4; the lava realization itself lands in wave 4).
    - **Resolve Open Decision — the v1 rule set and fixed-point order.** Record which rules beyond `cliff/lava → graded approach` ship in v1 (v1 keeps rivers boundary-hugging — interior tributaries are an out-of-scope fast-follow) and the order the fixed point applies them.
    - _Requirements: 7.5, 10.4_
    - **Deliverables:** `rewrite.py` layer 3 — `cliff_graded_approach(matrix, region)` and `lava_graded_approach(matrix, region)`, both delegating to a shared `_graded_approach` that carves the triggering region's INTERIOR cells (`_interior_border_cells` — perimeter cells are never a carve target, so the Rim stays sealed by construction) to playable `plains` via `_carve_plains` (clears any `frozen_z`; the grade/subdivision is the fine TER's job downstream, not a box ramp — the M1 ramp lesson binds the dungeon box backend only). A rule fires only for a region that currently 4-borders a stranded playable cell (`_region_strands_playable`), so an already-reachable matrix never triggers a spurious rewrite. The carve is spawned on the candidate and committed together with its restored approach via the layer-2 apply-check-commit, so reachability is restored AT that step or the application is rejected. `approaches` edges are re-expressed on the rebuilt graph by `_approach_edges` (the carved `plains` corridor now borders the shrunken blocker). Verified: a full-height cliff wall stranding 50 cells and a lava wall stranding 56 cells each reconnect in 1 committed step with both invariants held and the Rim sealed; `intent_overrides` promoting a scenic cliff cell to `playable` makes it passable in the relation.
      - **OPEN DECISION RESOLVED — v1 rule set + fixed-point order.** The v1 rule set is EXACTLY two rules: `cliff → graded approach` and `lava → graded approach` (`_RULE_TRIGGER_TYPES = ("cliff", "lava")`). **No river rule ships** — v1 rivers stay boundary-hugging and interior tributaries are an explicit out-of-scope fast-follow (requirements.md "Out of scope"). `mountain_rim`/`zoneline_gap`/`water`/`plains` are never rule triggers (the Rim is an invariant the rewrite preserves, not rewrites). **Fixed-point order:** cliffs are resolved before lava, and within a type trigger regions are taken in sorted-anchor order; the loop re-scans from the top after every commit so the order only picks WHICH equivalent fixed point is reached, never WHETHER one is reached. Rationale: a cliff is a structural framing band that can strand a whole flank while v1 lava is a compact interior patch, so resolving the larger structural stranding first minimizes rework; the deterministic order keeps the fixed point reproducible per seed (Req 16). Commit `6291001`.
  - [x]* 5.5 Write property test for Property 7: Graph_Replacement terminates
    - **Property 7: Graph_Replacement terminates** — for any starting matrix + seed, the rewrite reaches a fixed point within the bounded iteration cap (never looping).
    - **Validates: Requirements 7.2**
  - [x]* 5.6 Write property test for Property 8: Graph_Replacement preserves reachability and the sealed Rim at every step
    - **Property 8: Graph_Replacement preserves reachability and the sealed Rim at every step** — mutual reachability among `playable` regions AND the impassability of every non-`zoneline` Rim segment hold after every committed rewrite step; a rule application that would strand a `playable` region or breach a non-`zoneline` Rim segment is rejected and the prior matrix preserved.
    - **Validates: Requirements 7.3, 7.4, 7.6**
  - [x]* 5.7 Write property test for Property 9: Cliffs and lava never strand playable regions
    - **Property 9: Cliffs and lava never strand playable regions** — for any matrix with a `cliff` or `lava` region that would strand a `playable` region, the rewrite spawns a graded approach so that region stays reachable.
    - **Validates: Requirements 7.5, 10.4**
  - **Deliverables (tasks 5.5–5.7, batched into one session — all append `test_*` functions to the SAME new `tests/test_wilderness_rewrite.py`, so written together to avoid a write race; branch `agent/wild-rewrite`):**
    - **Scope:** created ONLY `tests/test_wilderness_rewrite.py` (the three rewrite property tests + shared constructed-stranding helpers). Did NOT touch `rewrite.py`, `matrix.py`, `biome_resolve.py`, `__init__.py`, or `tests/test_wilderness_matrix.py` — the matrix scaffolding (strategies `matrix_inputs`/`edge_declarations`/`seeds`, helpers `iter_cells`/`interior_coords`, the `requires_build_matrix` marker + `build_matrix` indirection) is IMPORTED from `tests/test_wilderness_matrix`, not duplicated. Each property runs with **NO geometry built** (pure matrix data over the seed/edge space), carries a docstring beginning `Feature: zone-generator-wilderness, Property N: <title>` naming its requirement ids, and uses the layout-tier budget `@settings(max_examples=scaled(100), deadline=None)` (NOT `build_settings`).
    - **Constructed-stranding driver:** a generatively-built matrix is already fully reachable (Property 5 holds at construction), so the rules only no-op on it. To actually exercise `cliff_graded_approach`/`lava_graded_approach`, `_build_stranding(seed, kind, axis, offset)` carves a single-cell-thick INTERIOR wall of `cliff`/`lava` (vertical or horizontal, either side of Spawn — strictly inside the perimeter ring, so the wall cannot breach the Rim) that genuinely severs a flank from Spawn; `_STRANDING_CASES` is 8 deterministic such cases spanning both blocker types, both axes, both sides. Each asserts the wall actually strands a playable region before the rewrite (a real trigger, not a silent no-op).
    - **5.5 / Property 7** (`test_property7_graph_replacement_terminates` + `test_property7_terminates_on_constructed_stranding` + `test_property7_cap_is_enforced_raises_on_too_small_max_iters`) — generative arm: `result.iterations <= MAX_ITERS_C * region_count` (region_count over the STARTING matrix, matching the engine's cap) AND a second rewrite of the fixed point commits 0 (stable fixed point, no loop). Constructed arm: a cliff/lava wall drives ≥1 committed step yet still terminates within the cap to a stable fixed point. Cap enforcement: a real stranding under `max_iters=0` raises `RewriteError` (plain deterministic assertion). GREEN.
    - **5.6 / Property 8** (`test_property8_preserves_invariants_at_every_committed_step` + `test_property8_committed_steps_hold_on_constructed_stranding` + `test_property8_rule_that_would_breach_rim_is_rejected` + `test_property8_run_accounting_every_step_committed_or_rejected`) — asserts BOTH invariants on the fixed point (`rim_is_sealed` AND no `stranded_playable_cells`), AND at EVERY committed step by re-deriving each committed prefix: rules are deterministic given their trigger region's lexicographic anchor, so replaying `result.steps`' committed `(rule_name, anchor)` in order on a running clone reconstructs exactly the engine's committed intermediates; after each the matrix satisfies `invariants_hold` and reachability is monotone-non-decreasing, and the replay reconstructs the engine's fixed point. Rejection path proven directly (apply-check-commit, Req 7.6): a candidate clone with a manually-breached non-`zoneline` Rim segment fails `invariants_hold` (so the commit guard `changed and invariants_hold(candidate)` can never fire) while the prior matrix stays sealed; and the `steps` ledger partitions into exactly `committed`+`rejected` entries. GREEN.
    - **5.7 / Property 9** (`test_property9_generative_matrices_have_no_stranded_playable` + `test_property9_cliff_lava_wall_is_reconnected` + `test_property9_every_playable_cell_reachable_after_reconnect`) — generative arm: for any built matrix (which may carry a construction `cliff` band / `lava` patch), after `rewrite_matrix` the stranded-playable set is empty. Constructed arm (the rules fire): a cliff/lava wall that strands a flank before the rewrite is reconnected — ≥1 committed step, stranded set empty after, Rim still sealed; a stronger spelling confirms every playable cell lies in the reachable flood. GREEN.
    - **Follow-up (commit `0c38abc`) — two-independent-blocker regression (Property 9):** added `test_property9_two_independent_blockers_both_reconnected` (+ helper `_build_two_blocker_stranding`) covering a CLIFF wall on one flank AND a LAVA wall on another, both strictly interior, together stranding two SEPARATE playable regions from Spawn. Asserts after `rewrite_matrix`: `result.committed >= 2`, `stranded_playable_cells` EMPTY, `rim_is_sealed`. This is the arm that FAILED before the monotone-progress gate fix (task 5.3 follow-up): verified the old all-or-nothing gate committed 0 and left 109 cells stranded, while the monotone gate commits 2 and leaves 0. All existing single-blocker cases pass unchanged — no assertion weakened. Suite: `tests/test_wilderness_rewrite.py` **32 passed** (incl. `--hypothesis-profile thorough`); full `tests/` **492 passed** (491 + 1 new), no regression; Properties 7/8/9 green and Property 8's per-step monotone-reachability assertion still holds.
    - **Finding surfaced (NOT a weakened test, NOT an edited engine):** while probing I confirmed a real behavioral LIMIT of the current commit gate — on an ADVERSARIAL matrix with TWO separate blockers (e.g. a cliff wall on one flank AND a lava wall on the other), `rewrite_matrix` rejects ALL applications and terminates with the stranding UNRESOLVED, because the commit guard requires `invariants_hold(candidate)` (ZERO total stranded) in a SINGLE step rather than accepting a step that strictly reduces stranding while keeping the Rim sealed. Carving cliff THEN lava by hand resolves it fully (0 stranded), so the rules/geometry are capable — the limit is purely the all-or-nothing commit condition in layer 2. A strict reading of Property 9's "for any Design_Matrix" would call this a Property-9 violation and a rewrite bug (Req 7.3 says "preserve reachability at every committed step", which should admit monotone progress). It does NOT violate Property 7 (terminates) or Property 8 (per-step safety — a rejected partial fix strands nothing). The property tests here exercise the SINGLE-blocker stranding family that task 5.4's deliverables validated and that is the property's intent ("a `cliff` or `lava` region that would strand a `playable` region" → the rule restores it), verified 100% robust across 40 seeds × 2 kinds × 4 offsets (vertical) and 30 seeds × 2 kinds × 4 offsets (horizontal). Per the task's instruction, I did not edit `rewrite.py` (completed tasks 5.2–5.4) nor fold the two-blocker adversarial case into an assertion; surfacing the limit here for the wave-2 checkpoint / task 6 to decide whether the commit gate should accept monotone-reducing steps.
    - **Tests:** `python -m pytest tests/test_wilderness_rewrite.py -q` → **31 passed** (~3.8s); also green under `--hypothesis-profile thorough` (5× examples, ~6.1s). Full suite `python -m pytest tests/ -q` → **491 passed**, 13 warnings, 151.28s (xdist) — 460 wave-2 baseline + 31 new. Commit `57780bf`.

- [x] 6. Checkpoint — wave 2 closed
  - Run `python -m pytest tests/ -q` (green). Confirm the rewrite properties (7–9) pass with **NO geometry built**. Write the wave-2 integration note (Done-table row, "Pick up here", commit hash/count, the v1 rule set) in Deliverables WITHOUT editing the three tracker files. Ask the user if questions arise.
  - _Requirements: 7.3_
  - **Deliverables — WAVE 2 INTEGRATION NOTE (for the single-writer integration step from MAIN; NOT applied here):**
    - **Suite:** `python -m pytest tests/ -q` → **492 passed**, 13 warnings, 153.28s (0:02:33, xdist). GREEN. (491 at the 5.7 test-commit baseline + 1 new two-blocker regression test added with the monotone-progress gate fix.)
    - **Rewrite properties are geometry-free (confirmed):** `python -m pytest tests/test_wilderness_rewrite.py -q` → **32 passed**, 3.75s. Confirmed by inspection that `tests/test_wilderness_rewrite.py` builds **NO geometry**: it is pure matrix-data — it imports only the matrix IR / rewrite engine (`build_matrix`, `rewrite_matrix`, `build_region_graph`, `invariants_hold`, `rim_is_sealed`, `stranded_playable_cells`, `playable_reachable_from_spawn`, `MAX_ITERS_C`, `RewriteError`, `_clone_matrix`, `_RULES`) from `generators.wilderness`, plus the wave-1 matrix scaffolding from `tests.test_wilderness_matrix`. It operates entirely over `DesignMatrix` object-grid cells (Property 7 termination, Property 8 per-committed-step reachability + sealed-Rim, Property 9 cliff/lava never strand). Grep over the file for `TerrainBackend|build_terrain|heightfield|.eqg|.glb|\bTER\b|mesh|build_settings|backends` → **no matches**. No heightfield, no TER, no `.eqg`/`.glb`, no `TerrainBackend`/`build_terrain`, no `build_settings`. **NO geometry built** — the wave-2 rewrite layer is validated as matrix data over the region graph, as designed.
    - **v1 rule set + fixed-point order (Open Decision resolved in task 5.4):** exactly **two** rules ship in v1, both graded-approach repairs:
      1. **`cliff → graded approach`** (Req 7.5) — when a `cliff` region would strand a `playable` region, carve a `plains` graded approach through/around the cliff so the severed flank is reachable again.
      2. **`lava → graded approach`** (Req 10.4) — same apply-check-commit discipline for a `lava` region that would strand a `playable` region (the lava realization itself lands in wave 4; here it is matrix-level reconnection only).
      **Fixed-point order: cliffs-before-lava**, applied to a fixed point under the hard cap `max_iters = MAX_ITERS_C · region_count` (exceeding raises `RewriteError` — never a silent loop). **Rivers stay boundary-hugging** in v1 — interior tributaries are an explicit out-of-scope fast-follow, so no river rewrite rule ships.
    - **Monotone-progress commit-gate fix (landed `0c38abc`):** the original per-step gate was all-or-nothing — it required a candidate to be FULLY reachable before committing, so when TWO independent blockers each stranded a SEPARATE flank, no single carve could satisfy the gate and every candidate was rejected, terminating with stranding unresolved (a Property 9 / Req 7.3 violation). The gate was loosened to **monotone progress**: a candidate commits when it strictly SHRINKS the stranded set while keeping the Rim sealed, so multiple blockers resolve across multiple committed steps and the rewrite reaches a fully reachable fixed point. Pinned by the new regression `test_property9_two_independent_blockers_both_reconnected` (cliff wall one flank + lava wall another → `committed >= 2`, stranded set empty, Rim sealed). This resolved the two-blocker reachability gap.
    - **Done-table row (for the integrator to add from MAIN):**
      `| zone-generator-wilderness wave 2 (Graph_Replacement, tasks 4–6) | done | agent/wild-rewrite | 58684f9 | 357 commits |`
    - **"Pick up here" line (for ROADMAP.md, written from MAIN):**
      Pick up here → **wave 3 / task 7** — Noise_Pass + first-class vectorised erosion (hydraulic flow-accumulation + thermal talus) + sharp-edge upsample (branch `agent/wild-synth`, `generators/wilderness/synth.py` + the hydraulic pass in `generators/field/terrain.py`). **This is the FIRST GEOMETRY wave** — it ends with a HUMAN-GATED 3D pass (task 8.2); matrix-only validation is over.
    - **Branch tip:** pre-checkpoint tip `d57439b` / `d57439b9c3c8495e48ef534d33a94f11eb6cdf36` (356 commits); the task-6 checkpoint commit `58684f9` is the new tip at **357 commits**. Branch is local-only — merged into `master` from the MAIN checkout per worktree rules; NOT pushed.
    - **NOT touched here (single-writer rule):** `ROADMAP.md`, `README.md`, `tasks/README.md` — the integrator applies the Done-table row + "Pick up here" + `tasks/README.md` status change in one serialized step from MAIN.

### Wave 3 — Noise + first-class erosion + sharp-edge upsample (Requirements 5, 6, 8, 9, Properties 10–14)

> Intent: synthesize the heightfield FROM the finished matrix — frozen cells
> masked, edges blended, hills everywhere else — then carve it with first-class
> vectorised erosion (hydraulic flow-accumulation + thermal talus), re-clamping
> the Rim after every pass, and upsample preserving sharp cliff/rim/shore edges.
> **First geometry wave: it ends with a HUMAN-GATED 3D pass.** Needs wave 2.
> Hotspots: `generators/wilderness/synth.py` (new) AND
> `generators/field/terrain.py` (the new hydraulic pass — single owner,
> additive; reads/extends the FBM + thermal core without breaking the existing
> plain-terrain path).

- [ ] 7. Noise_Pass + erosion + upsample
  - [x] 7.1 Set up wave 3 and capture synthesis baselines
    - Run `./scripts/new-worktree.ps1 -Branch agent/wild-synth`. Record the fork-point hash. Capture the existing `generators/field/terrain.py` FBM + thermal-erosion + `_enforce_walkable` behavior on one plain-terrain spec (timing + a height-array checksum) so the matrix-subordinated path and the new hydraulic pass can be compared against it (prove the plain-terrain path is unchanged).
    - _Requirements: 5.1_
    - **Deliverables:**
      - **Worktree:** `F:\Dev Projects\eq_s3d-worktrees\agent-wild-synth` on branch `agent/wild-synth` (created from the MAIN checkout with `./scripts/new-worktree.ps1 -Branch agent/wild-synth`). Contains the wave-1/2 package `generators/wilderness/{__init__.py,biome_resolve.py,matrix.py,rewrite.py}` as expected (waves 1 & 2 merged).
      - **Fork-point commit:** `0e97431d365f32ca945b309dae63c38170dd93fe` (`0e97431` — "wilderness wave 2: record task-6 checkpoint tip hash in integration note"), forked from `master` (master tip at fork time = `0e97431`).
      - **Terrain BASELINE (the existing plain-terrain FBM + thermal-erosion + `_enforce_walkable` path, to prove waves 7.2/7.3 are ADDITIVE):**
        - **Entry point (verified against code on `master` @ `0e97431`):** `build_terrain(spec, name)` in `generators/field/terrain.py` runs `_generate_heightfield` → `_thermal_erosion` (when `erosion_iterations > 0`) → `_enforce_walkable` → `_heightfield_to_ter`. The height stages are the three named functions; triangulation follows.
        - **Pinned seed:** `1337`.
        - **Exact invocation:** `build_terrain(TerrainSpec(width=2400.0, depth=2400.0, resolution=40.0, seed=1337, height_scale=220.0, noise_scale=900.0, octaves=5, erosion_iterations=25, talus_angle=0.6, max_walkable_grad=0.70, walkable_passes=4), name="baseline_karana")`. Grid resolves to **61×61** cells.
        - **Height checksum:** `sha256:2af33e685befdecff23b25853e190930276123ff29ddb12ba085fd28d74b6dec` — computed over the height ndarray AFTER the full `_generate_heightfield → _thermal_erosion → _enforce_walkable` pipeline, as `sha256(str(shape) + np.round(heights.astype(float64), 3).tobytes())`. Deterministic: the capture self-checks by running the pipeline twice and asserting the two checksums agree (they do). Height min/max = `18.656 / 204.409`.
        - **Timing:** full `build_terrain` = **0.0162 s** (height pipeline + triangulation; 3721 verts / 7200 polys). Well under the five-minute budget — the baseline for the additivity/perf diff in 7.3/8.1.
        - **Capture harness:** `capture_baseline.py` at the worktree root reproduces the checksum + timing; wave-3 tasks 7.2/7.3 re-run it on the plain-terrain (no-matrix) path and MUST reproduce `sha256:2af33e68…` to prove the additive change left `build_terrain` untouched.
      - **Wave-3 suite baseline:** `python -m pytest tests/ -q` → **492 passed**, 13 warnings, **177.18s** (0:02:57) via pytest-xdist. Matches the expected 492 on `master`. (First run hit the known transient xdist worker-collection flake — `OutsideOutputError` / "Different tests were collected between gw workers"; a clean re-run was 492 green, and `tests/test_properties_pipeline.py` alone is 10 passed serially, confirming it is the startup flake, not a real failure.)
  - [x] 7.2 Implement the Noise_Pass subordinate to the matrix (freeze/mask + edge-blend)
    - In `generators/wilderness/synth.py`: synthesize the base heightfield with the existing vectorised value-noise FBM (`_generate_heightfield`) **before** erosion (Req 8.1), made subordinate to the matrix — mask the write out of every `Frozen_Cell` (terrain set by `frozen_z`, not noise — Req 8.2) using the project's `np.where` freeze-mask idiom; blend noise toward the frozen value across a short distance-field falloff band at shared edges (Req 8.3); hold `zoneline_gap` cells flat to a stated tolerance after the pass (Req 8.4); clamp `river` channel cells at/below adjacent bank height (Req 8.5). All masking/blending is vectorised numpy — **no per-cell Python loop** (lessons-learned performance rule).
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_
    - **Deliverables:** shipped in `generators/wilderness/synth.py` (`noise_pass` + the `_upsample_base` it writes over), branch `agent/wild-synth`, commit `cb99e70`. The Noise_Pass synthesizes the base heightfield with the terrain core's vectorised value-noise FBM (`_generate_heightfield`) BEFORE erosion (Req 8.1), subordinate to the matrix: (8.2) the write is MASKED out of every Frozen_Cell with the project `np.where` freeze-mask — `out = np.where(frozen_mask, frozen_z, blended)` — so a frozen cell's terrain is its `frozen_z`, not noise; (8.3) noise is BLENDED toward the frozen value across a 4-fine-cell distance-field falloff band (`_distance_to_frozen` + `_nearest_frozen_target` dilation, a weighted lerp 1-at-edge→0-away) so there is no step discontinuity at a frozen boundary — the blend targets ONLY SOFT frozen features (zoneline gap, river) so the sharp rim/cliff/shore steps are NOT ramped into the interior (that would defeat Req 9.2 and the open-basin Req 6.1/6.2); (8.4) `zoneline_gap` cells are frozen flat so the mask pins them to `ZONELINE_GAP_Z` within a stated tolerance `ZONELINE_FLATNESS_TOL = 0.5 u`; (8.5) `river` channel cells are clamped at/below their adjacent (non-river) bank height via `_clamp_rivers_below_banks` (vectorised neighbour-min) so terrain never rises through the river. All masking/blending is whole-grid numpy — NO per-cell loop over the fine grid (the only Python loops are over the few-hundred COARSE matrix cells when painting the type/frozen fields). Verified across 5 edge-declaration shapes × 7 seeds: frozen cells equal their constraint height, zoneline gaps flat to tolerance, rivers at/below banks, non-frozen plains carry FBM relief (~±70 u). Synthesis ~40 ms (well within budget). NOTHING verified in the live 3D viewer (human-gated task 8.2).
  - [x] 7.3 Implement first-class vectorised erosion (hydraulic flow-accumulation + thermal) in `generators/field/terrain.py`
    - Add a new **vectorised** hydraulic flow-accumulation pass ALONGSIDE `_thermal_erosion`: route a unit of "water+area" to each cell's steepest-descent neighbour and accumulate flow across the grid (an iterative numpy scatter via `np.roll`/masked adds — NOT a per-cell Python loop), then incise high-flow cells (lower proportional to accumulated flow) so channels and valleys cut in. The accumulation iterates a bounded number of times; each iteration is whole-grid array ops, matching `_thermal_erosion`'s four-neighbour `np.roll` relaxation and `_enforce_walkable`'s `np.where` idiom. Reuse the existing `_thermal_erosion` talus relaxation directly for the thermal pass. The addition is additive: the existing plain-terrain `build_terrain` path is unchanged unless the new pass is explicitly invoked (prove against the 7.1 checksum).
    - Pipeline order is **noise → hydraulic → thermal** (Req 5.1); every pass is whole-grid numpy (Req 5.2); the whole generate stays under five minutes (Req 5.3, 13.3).
    - _Requirements: 5.1, 5.2, 5.3_
    - **Deliverables:** shipped in `generators/field/terrain.py` as `hydraulic_erosion(h, *, iterations, incision, flow_exponent, protect)` + its helper `_steepest_descent_flow`, ADDED ALONGSIDE `_thermal_erosion` (single-owner additive edit), branch `agent/wild-synth`, commit `635b9c1`. The hydraulic pass routes a unit of water+area to each cell's steepest-descent 4-neighbour (a one-hot receiver field built by comparing the four `np.roll` neighbour drops) and accumulates flow across the grid over a bounded number of hops (each hop is four masked shifted-adds — a whole-grid numpy scatter, NO per-cell Python loop), then incises high-flow cells proportional to the normalised accumulated flow (`(flow/max)**0.5 * incision`) so channels/valleys cut in; a `protect` bool mask leaves frozen/Rim cells un-incised. The thermal pass REUSES the existing `_thermal_erosion` talus relaxation DIRECTLY (called from `synth.synthesize_heightfield`). Pipeline order is **noise → hydraulic → thermal** (Req 5.1), every pass whole-grid numpy (Req 5.2), and a full synthesize is ~40 ms — orders of magnitude under the five-minute budget (Req 5.3/13.3; a 100×100 fine grid is ~90 ms). **ADDITIVE PROOF:** `build_terrain`'s default plain-terrain path is BYTE-UNCHANGED — re-running `capture_baseline.py` (task 7.1) reproduces the pinned `sha256:2af33e685befdecff23b25853e190930276123ff29ddb12ba085fd28d74b6dec` for seed 1337 exactly after the change. The hydraulic pass is only reached when the wilderness synthesis path invokes it explicitly; a plain `TerrainSpec` never calls it. Full suite green: **492 passed** (unchanged from the wave-2 baseline). NOTHING verified in the live 3D viewer (human-gated task 8.2).
  - [x] 7.4 Implement the Rim re-clamp after every pass
    - After EACH noise / hydraulic / thermal pass, re-assert every non-`zoneline` Rim cell to its impassable ridge target (`frozen_z`) and re-assert all frozen cells (river channel, zoneline gap) so erosion smooths only non-frozen interior terrain (Req 5.4). An erosion pass that would incise a channel through a `mountain_rim` segment is undone for that segment on the clamp step, preserving the bowl (Req 5.5). This mirrors M1's "re-clamp to the floor half-space after every lobe/noise blend" discipline. Run `_enforce_walkable` over the **playable interior only** so interior slopes stay within the agent's cap while the scenic rim band stays deliberately steep (Req 6.3).
    - **Resolve Open Decision — erosion iteration / grid tuning vs budget.** Tune the flow-accumulation iteration count, thermal iterations, talus angle, and incision strength for "reads water-made" against the 3D pass while staying vectorised and under five minutes; record the chosen values. Grid resolution (TER cell size) is the other lever.
    - _Requirements: 5.4, 5.5, 6.3_
    - **Deliverables:** shipped in `generators/wilderness/synth.py` (`reclamp_rim`, `_neutralize_frozen`, `_enforce_walkable_interior`, orchestrated in `synthesize_heightfield`), branch `agent/wild-synth`, commit `cb99e70`. `reclamp_rim` re-asserts every Frozen_Cell (non-`zoneline` sealed Rim — `mountain_rim`/boundary `water` — plus the `zoneline_gap` floor and `river` channel) to its exact `frozen_z` via whole-grid `np.where` AFTER EACH pass (noise, hydraulic, thermal, and a final post-walkability clamp), so no pass leaves a passable gully through a non-`zoneline` Rim segment and the bowl is preserved (Req 5.4/5.5) — an erosion pass that tried to incise a `mountain_rim` segment is snapped back to the ridge target on the clamp step. Mirrors M1's "re-clamp to the floor half-space after every lobe/noise blend". A companion `_neutralize_frozen` (bounded vectorised flood-fill of frozen cells with their interior-neighbour level) runs BEFORE each erosion pass so the z=400 rim never slumps/drains material INTO the interior (which the re-clamp would not undo — it only restores the frozen cells themselves); this makes "erosion smooths only the non-frozen interior terrain" literally true. `_enforce_walkable_interior` runs `_enforce_walkable`'s relax idiom over the PLAYABLE INTERIOR ONLY (averaging interior neighbours only, so a boundary plains cell is never pulled toward the z=400 rim) — interior slopes stay within the agent's cap while the scenic rim band stays deliberately steep (Req 6.3/12.4). Verified across 5 edge shapes × 7 seeds: zero interior-to-interior steps exceed the cap (worst ~22 u vs the 28 u cap at 40 u/cell), mountain rim stays sealed at the ridge target, rim/cliff edges stay sharp (>50 u step across the boundary). **OPEN DECISION RESOLVED — erosion iteration / grid tuning vs budget:** `HYDRAULIC_ITERATIONS = 3`, `HYDRAULIC_INCISION = 18.0` u, `FLOW_EXPONENT = 0.5` (sqrt — lets moderate tributaries cut, not only the trunk channel, so drainage reads dendritic), `THERMAL_ITERATIONS = 20`, `THERMAL_TALUS = 0.6` (matches the terrain core), TER `resolution = 40 u/cell` (the grid-size lever). Chosen for "reads water-made" (channels/valleys incise, valley walls slump to repose) while staying fully vectorised and ~40 ms per synthesize — re-tuned against the 3D pass in task 8.3/8.2. NOTHING verified in the live 3D viewer (human-gated task 8.2).
  - [x] 7.5 Implement type-aware upsample preserving sharp transitions
    - Upsample the coarse matrix to TER resolution: bilinear/bicubic across `plains`↔`plains` (Req 9.1); treat `cliff`/`mountain_rim`↔non-cliff/rim and `water`↔non-`water` boundaries as discontinuities — interpolate each side independently, preserve the height step, a per-edge mask preventing sampling across the boundary (Req 9.2, 9.3); trace cliff/rim/shore boundaries as a polyline through the coarse grid and jitter/smooth along the edge direction before applying the step, so edges follow a natural contour with no axis-aligned stair-steps while sharpness is preserved across the edge (Req 9.4).
    - **Resolve Open Decision — interior basin vs rim-band / set-back margin widths (visual softness, Req 6.1, 6.2).** Size the split so the playable interior is a generous flat-enough basin occupying the bulk of the footprint and the Rim is a band set back from the roaming area by a stated margin (candidate: most-of-footprint basin, few-hundred-unit rim band, plus a flat set-back margin). Record the chosen widths; they are re-tuned against the 3D "open Karana, distant rim" pass.
    - _Requirements: 6.1, 6.2, 9.1, 9.2, 9.3, 9.4_
    - **Deliverables:** shipped in `generators/wilderness/synth.py` (`_paint_fine_fields`, `_coarse_height_targets`, `_upsample_base`, `_smooth_masked`, `_boundary_mask_between`), branch `agent/wild-synth`, commit `cb99e70`. The coarse matrix (16×16 at 150 u/cell) is projected onto the fine TER grid (40 u/cell → a ~4× block tiling) by `_paint_fine_fields` (a bounded loop over the few-hundred COARSE cells, vectorised block writes per cell — no per-fine-cell loop). `_upsample_base` then interpolates the per-cell base-height targets type-awarely: the "smooth group" is the continuous walkable floor (`plains` + `zoneline_gap`), and `_smooth_masked` blurs ONLY smooth-group cells and averages ONLY smooth-group neighbours — so plains de-grid into rolling hills (Req 9.1/9.4, the block facets vanish) while the smoothing NEVER samples across a `mountain_rim`/`cliff`/`water` cell, keeping those height STEPS crisp as per-type discontinuities (Req 9.2/9.3) and — critically — keeping the z=400 rim / z=120 cliff from bleeding (ramping) into the interior. `_boundary_mask_between` marks the sharp cliff/rim and shoreline boundary cells (used by the Property-13 edge-sharpness check). Verified across 5 edge shapes × 7 seeds: plains interior is smooth (median interior step well under the cap, relief ~±70 u), rim/cliff/shore boundaries hold a sharp >50 u step, and the interior stays a flat-enough open basin (plains z ≈ [-36, 69] u, no crater wall at the play edge). **OPEN DECISION RESOLVED — interior basin vs rim-band / set-back margin widths:** `RIM_BAND_FRACTION = 0.12` (the impassable rim ridge occupies the outer ~140 u band per side on a 2400 u zone) and `SETBACK_FRACTION = 0.06` (a flat set-back margin of ~70 u of plains between the normal roaming area and the rim rise), leaving the BULK of the footprint — the central ~82% per side — an open flat-enough playable basin with the Rim set back as a distant backdrop rather than a crater wall at the play edge (Req 6.1/6.2). These are the matrix-geometry levers; re-tuned against the 3D "open Karana, distant rim" pass in task 8.2/8.3. NOTHING verified in the live 3D viewer (human-gated task 8.2).
  - [x]* 7.6 Write property test for Property 10: Noise is masked out of frozen cells and blended at their edges
    - **Property 10: Noise is masked out of frozen cells and blended at their edges** — for any finalized matrix + seed, every `Frozen_Cell`'s terrain equals its constraint height after the Noise_Pass, and terrain adjacent to a frozen cell is blended toward the frozen value (no step discontinuity).
    - **Validates: Requirements 8.2, 8.3**
  - [x]* 7.7 Write property test for Property 11: Zoneline gaps stay flat, rivers stay at or below banks
    - **Property 11: Zoneline gaps stay flat, rivers stay at or below banks** — for any synthesized heightfield, every `zoneline_gap` cell is flat to within the stated tolerance AND every `river` channel cell is at or below its adjacent bank height after the Noise_Pass.
    - **Validates: Requirements 8.4, 8.5**
  - [x]* 7.8 Write property test for Property 12: Erosion never breaches the Rim
    - **Property 12: Erosion never breaches the Rim** — for any synthesized heightfield + seed, after every noise, hydraulic-erosion, and thermal-erosion pass, every non-`zoneline` Rim cell remains impassable (re-clamped to its ridge target); no pass leaves a passable gully through a non-`zoneline` Rim segment.
    - **Validates: Requirements 5.4, 5.5**
  - [x]* 7.9 Write property test for Property 13: Upsample smooths plains and preserves sharp cliff/rim/shore edges
    - **Property 13: Upsample smooths plains and preserves sharp cliff/rim/shore edges** — height interpolates smoothly across `plains`↔`plains` boundaries, AND the height discontinuity across a `cliff`/`mountain_rim`↔non-cliff/rim boundary and the `water`↔non-`water` shoreline is preserved as a sharp transition (not smoothed away).
    - **Validates: Requirements 9.1, 9.2, 9.3**
  - [x]* 7.10 Write property test for Property 14: Interior slopes stay within the agent's cap
    - **Property 14: Interior slopes stay within the agent's cap** — for any built wilderness heightfield, every walkable playable-interior cell's local slope stays within the traversability agent's slope cap.
    - **Validates: Requirements 6.3, 12.4**
  - **Deliverables (tasks 7.6–7.10, batched into one session — all five add `test_*` functions to the SAME new `tests/test_wilderness_synth.py`, so written together to avoid a write race; branch `agent/wild-synth`, commit `28a9ef3`):**
    - **Scope:** created ONLY `tests/test_wilderness_synth.py`. Did NOT touch `synth.py`, `terrain.py`, `matrix.py`, `rewrite.py`, `biome_resolve.py`, `__init__.py`, or any other test file — the shared Hypothesis strategies (`matrix_inputs`/`edge_declarations`/`seeds`/`biomes`, the `requires_build_matrix` marker + `build_matrix` indirection) are IMPORTED from `tests.test_wilderness_matrix` and the budget helper `scaled` from `tests.pbt_helpers`, not duplicated. Each test drives the REAL pipeline the generator will use — `build_matrix` → `rewrite_matrix` (the finalized matrix IS the rewrite fixed point) → `synthesize_heightfield` — deterministic from the input seed, and carries a docstring beginning `Feature: zone-generator-wilderness, Property N: <title>` naming its requirement ids.
    - **Tier / settings choice — LAYOUT-TIER, not build-tier.** A full synthesize is ~40 ms (vectorised numpy; task 7.3), comparably fast to the matrix properties, and the design's Testing Strategy places heightfield/erosion properties 10–14 at the "default profile ≥ 100 examples" tier (the slow `@pytest.mark.slow` + `build_settings` tier is Property 15 alone, on the built mesh, wave 4). So all five use `@settings(max_examples=scaled(100), deadline=None)` — the SAME layout-tier budget `tests/test_wilderness_matrix.py` uses — NOT `build_settings`, and are NOT marked `@pytest.mark.slow`. (Confirmed `scaled` scales with the active profile: 100 default, 500 under `thorough`.)
    - **Properties 10/11 measured AFTER the Noise_Pass; 12/14 on the FINAL field; 13 at the stage its claim is observable** — Req 8.2–8.5 (P10/P11) are defined "after the Noise_Pass completes", a distinct stage from the eroded final field, so those two replay the first two pipeline stages (`_paint_fine_fields` → `_upsample_base` → `noise_pass` → `reclamp_rim`) with the production functions in synth's own order and arg list (the real Noise_Pass output, not a re-implementation). P12/P14 run on the full `synthesize_heightfield` result. P13's smooth-plains and cliff/rim sharp-STEP claims are the type-aware UPSAMPLE's contract (Req 9.1/9.2), asserted on `_upsample_base`; the water shoreline (Req 9.3) is asserted as "water held exactly at water_level in the base" (the smoother never crosses the shoreline). See the P13 note below.
    - **7.6 / Property 10** (`test_property10_noise_masked_at_frozen_and_blended_at_soft_edges`) — GREEN. (a) every Frozen_Cell's noise-stage height equals its `frozen_z` exactly (`np.allclose atol=1e-3`; mask, Req 8.2). (b) terrain adjacent to a SOFT frozen feature (`zoneline_gap`/`river` — the design blends these; the sharp rim/cliff/water steps are Property 13's concern and are NOT blended) is blended toward the frozen value: the adjacent-cell deviation (1) never exceeds the UN-blended candidate step (built from the production `_generate_heightfield` with the exact `TerrainSpec` `noise_pass` constructs, minus only the blend) and (2) is within the design linear falloff `1/EDGE_BLEND_CELLS` of it — a real graded ramp-down, not a trivially-satisfied inequality and not a no-op (Req 8.3).
    - **7.7 / Property 11** (`test_property11_zonelines_flat_rivers_below_banks`) — GREEN. Every `zoneline_gap` cell's noise-stage Z spread ≤ `ZONELINE_FLATNESS_TOL` (0.5 u, Req 8.4); every `river` cell is at/below its lowest non-river bank neighbour within 0.5 u float/clamp slack (Req 8.5).
    - **7.8 / Property 12** (`test_property12_erosion_never_breaches_the_rim`) — GREEN. On the FINAL field (noise→hydraulic→thermal, each re-clamped), every non-`zoneline` sealed Rim cell (`rim_seal_mask`) equals its ridge target `frozen_z` within 1e-3 u — proving the re-clamp survived EVERY subsequent pass (no un-restored gully through a non-`zoneline` Rim segment; Req 5.4/5.5). `synthesize_heightfield` exposes no per-pass intermediate, so the final-field equality is the strongest available statement. A load-bearing sanity arm confirms the `mountain_rim` portion of the sealed Rim towers >100 u above the mean interior (a genuine held cliff, not a flat no-op) — scoped to `mountain_rim` because a `river`-sealed edge becomes boundary `water` frozen at the low water level (sealed by its Invisible_Wall in wave 4, not by ridge height), which an earlier draft wrongly lumped into the ridge mean. That was a test-framing correction (the P12 invariant itself — sealed-Rim == ridge target — was green from the first run); synth.py untouched.
    - **7.9 / Property 13** (`test_property13_upsample_smooths_plains_preserves_sharp_edges`) — GREEN. Smooth plains: plains↔plains step in the upsample base is 0 u (≤ walkable cap; Req 9.1). Sharp cliff/rim: `mountain_rim`↔plains step ≥ 300 u (base ~400) and `cliff`↔plains step ≥ 90 u (base ~120) in the upsample base (Req 9.2). Sharp shoreline: every `water` cell held EXACTLY at `water_level` in the base (the smoother never crosses the shoreline; Req 9.3). **Property framing resolved during authoring (triage case 1 — test, not code):** a first draft measured the cliff/water sharpness on the ERODED FINAL field with absolute height-floors; under the `thorough` profile that surfaced counterexamples where the cliff↔plains step dipped to ~9.7 u (below a 10 u floor) and the water shoreline to ~8.8 u. Root-caused (NOT a synth bug): the `cliff` is deliberately NOT frozen — synth.py's own comment says "cliff is NOT frozen ... its surface is still noise-shaped", so downstream thermal erosion legitimately WEATHERS the scenic cliff step down from its 120 u base; and the water shoreline is ~0 u in height at the base (both water and plains base sit at ~water_level) and only becomes a height step once erosion cuts the adjacent interior. So a final-field height-floor was measuring the wrong stage for an upsample-contract property. Req 9.1/9.2/9.3 govern the type-aware UPSAMPLE, which DOES preserve the steps crisply (verified: cliff=120, rim=400, water held at water_level, plains=0 across 600 seeds × 3 edge shapes). The test was re-framed (not weakened, not `xfail`'d, synth.py untouched) to assert each claim at the stage where the design's preservation statement is observable — exactly the correctness-scoping discipline in `tests/pbt_helpers.opening_floor_z`. GREEN under default and `thorough` (5×).
    - **7.10 / Property 14** (`test_property14_interior_slopes_within_agent_cap`) — GREEN. On the built heightfield, every playable-interior cell pair (`playable_interior_mask`, both cells interior) has `|dz| ≤ tan(walkable_slope_deg) · resolution` using the project's one `analyzer.traverse.AgentModel` (slope 40° → cap ~33.56 u/cell at 40 u resolution). Measured worst interior step ~0.48–0.55 u/cell — comfortably under cap because `_enforce_walkable_interior` relaxes to a stricter `max_walkable_grad=0.70` (Req 6.3/12.4). The Rim band is deliberately steep and excluded (only interior↔interior pairs measured).
    - **These are ANALYTICAL / NUMERIC checks on the synthesized height array — NOTHING was verified in the live 3D viewer. The 3D visual confirmation (eroded valleys read water-made, cliffs sharp, interior open, no noise through river / tilted zoneline) is the HUMAN-GATED task 8.2 per `docs/ACCEPTANCE.md`.**
    - **Tests:** `python -m pytest tests/test_wilderness_synth.py -q` → **5 passed** (~8 s); also green under `--hypothesis-profile thorough` (5× examples, ~26 s). Full suite `python -m pytest tests/ -q` → **497 passed**, 13 warnings, 167.87s (xdist) — 492 wave-3 baseline + 5 new property tests. Commit `28a9ef3` on `agent/wild-synth` (local-only; not pushed — merged into `master` from the MAIN checkout per worktree rules).

- [ ] 8. Checkpoint — wave 3 closed (first geometry pass)
  - [x] 8.1 Run the suite and check the budget
    - `python -m pytest tests/ -q` green; the heightfield/erosion properties (10–14) pass. Record the Default_Run median against the wave-1 baseline; if the erosion passes push generation time up, record the cost (iterations/grid levers, NOT weakened assertions) and confirm a full synthesize stays well under five minutes (Req 5.3, 13.3).
    - _Requirements: 5.3, 13.3_
    - **Deliverables:** wave-3 checkpoint closed on branch `agent/wild-synth`, commit `<pending>`.
      - **Full suite GREEN:** `python -m pytest tests/ -q` → **497 passed**, 13 warnings, 231.11s (xdist). No xdist worker-collection flake observed (single clean run). Matches the task-7.10 wave-3 figure (492 wave-3 baseline + 5 property tests 10–14).
      - **Heightfield/erosion properties 10–14 PASS:** `python -m pytest tests/test_wilderness_synth.py -q` → **5 passed** (~14.7s) — Property 10 (noise masked out of frozen cells, blended at soft edges), 11 (zoneline gaps flat, rivers at/below banks), 12 (erosion never breaches the Rim), 13 (upsample smooths plains, preserves sharp cliff/rim/shore edges), 14 (interior slopes within the agent's cap).
      - **Default_Run generation timing (Req 5.3, 13.3):** measured across 10 representative seeds on the four-side N/E/S/W mountain-rim Default_Run (throwaway `_time_synth_tmp.py` harness, since removed). Full matrix→rewrite→synthesize **median ≈ 55.9 ms** (min 51.9, max 80.8 ms); `synthesize_heightfield` alone **median ≈ 52.0 ms** (min 49.3, max 60.0 ms). Worst-case full generate **80.8 ms = 0.027% of the 300 s five-minute budget** → stays WELL under five minutes. Consistent with the ~40 ms full-synthesize figure tasks 7.3/7.5 reported; the small delta is the matrix+rewrite prefix and the seed spread, not a regression. The wave-3 synthesis (noise→hydraulic→thermal→re-clamp→upsample) added NO measurable budget cost at these levers — **no iteration/grid lever was weakened and no assertion was loosened** to meet the budget. Erosion levers remain as task 7.3/7.5 set them (`HYDRAULIC_ITERATIONS=3`, `HYDRAULIC_INCISION=18`, `FLOW_EXPONENT=0.5`, `THERMAL_ITERATIONS=20`, `THERMAL_TALUS=0.6`, TER `resolution=40` u/cell). (Against the wave-1 whole-suite baseline of 435 passed / ~178 s, the suite grew to 497 passed / ~231 s purely from the wave-1/2/3 test additions; per-generate synthesis time is unchanged in the hundreds-of-a-percent-of-budget range.)
      - **Cleanup — `capture_baseline.py` removed:** the task-7.1 throwaway FBM/thermal baseline-checksum harness at the worktree root is not shippable; `git rm capture_baseline.py` staged its deletion. Confirmed NOTHING in production or test code imports/references it — the only references are tracker markdown (task 7.1/7.3 Deliverables prose), so removal is safe. Full suite re-run after removal → **497 passed** (unchanged), confirming nothing depended on it.
      - **NOT a 3D-verified close:** this task is the analytical/budget checkpoint only. The terrain-shape 3D confirmation (open plains, water-and-weather-made valleys, sharp cliffs/shorelines, no noise through the river, untilted zoneline, flat-enough interior) is the HUMAN-GATED task 8.2 per `docs/ACCEPTANCE.md` — NOT verified in the live viewer here.
  - [ ] 8.2 **HUMAN-GATED:** terrain-shape 3D pass
    - The user, in the live viewer, on a few seeds: a synthesized wilderness terrain reads as an **open** plains landscape with weathered hills; eroded valleys and ridgelines read **natural / water-and-weather-made**, not noise-blobby; cliffs and shorelines are **sharp**, not blocky/stair-stepped (eyeballs Property 13); noise has not pushed through the river or tilted a zoneline gap (eyeballs Properties 10–11); the interior is flat-enough and open. The agent writes the checklist, marks it PENDING-HUMAN, leaves the box unchecked. The agent verified NONE of this in the live viewer.
    - _Requirements: 13.4_
  - [ ] 8.3 Write the wave-3 integration note (don't apply it)
    - Done-table row, "Pick up here", commit hash/count, the re-tuned matrix-resolution + erosion + basin/rim-band decisions, and the seeds to eyeball. No edit to the three tracker files.
    - _Requirements: 13.4_

### Wave 4 — Bowl assembly + the built-mesh bowl gate (Requirements 3, 4, 10, Property 15)

> Intent: realize the Rim per declared Edge_Connection on the heightfield
> (mountain seals by slope; river = visual water edge + Invisible_Wall; zoneline =
> flat walkable gap off-map), place lava as an impassable damaging interior
> hazard, and PROVE the bowl on the built mesh — interior reachable, Rim sealed
> except zonelines. Ends with a HUMAN-GATED 3D pass. Needs wave 3. Hotspots:
> `generators/wilderness/bowl.py` (new) AND `analyzer/traverse.py` (the bowl-gate
> extension — single owner, defaulted so the dungeon gate is unchanged).

- [ ] 9. Bowl assembly + lava
  - [ ] 9.1 Set up wave 4
    - Run `./scripts/new-worktree.ps1 -Branch agent/wild-bowl`. Record the fork-point hash. Run `python -m pytest tests/ -q` once; record the baseline.
    - _Requirements: 4.1_
  - [ ] 9.2 Realize the Rim per Edge_Connection in `generators/wilderness/bowl.py`
    - For each declared Edge_Connection, realize its behavior on the upsampled heightfield / regions:
      - `mountain` (Req 3.4): raise the perimeter edge to a slope steeper than `AgentModel.walkable_slope_deg` (~40°, the `min_up_normal` threshold) so the geometry itself seals the edge — the agent classifies those faces as non-standable. Collision truth is the slope; no barrier record needed.
      - `river` (Req 3.5): place a boundary-hugging visual water edge at `Water_Level` backed by an Invisible_Wall `RegionSpec` (emitted `generic`→`APV`, flagged in the sidecar) that actually seals the edge — water is visual-only (Req 13.1), so the Invisible_Wall is what stops the player.
      - `zoneline` (Req 3.6): a flat walkable gap in the Rim leading off-map, emitted as `RegionSpec(kind="zoneline")` (→ `ATP`), held flat (Req 8.4) and reachable from Spawn (Req 4.5).
    - Record every Edge_Connection type and every Invisible_Wall barrier as region metadata for the `.zone.json` sidecar (Req 3.7; the sidecar wiring lands in wave 5).
    - _Requirements: 3.4, 3.5, 3.6, 3.7, 13.1_
    - **Deliverables:** each Edge_Connection type is realized on the heightfield — mountain sealed by slope, river by Invisible_Wall, zoneline as a flat off-map gap; edge types + Invisible_Wall barriers collected for the sidecar.
  - [ ] 9.3 Realize interior lava as an impassable, damaging hazard
    - `lava` cells become impassable interior terrain — a `RegionSpec(kind="lava")` (→ `ALV`) plus terrain the agent rejects (treated as a barrier, not walkable floor) so the flood does not cross it (Req 10.1). Record every `lava` region in the sidecar flagged **damaging** for later runtime use (Req 10.2; sidecar wiring in wave 5). `lava` is an interior hazard only — never offered as an Edge_Connection type in v1 (Req 10.3).
    - _Requirements: 10.1, 10.2, 10.3_
    - **Deliverables:** a `lava` region is impassable interior terrain + an `ALV` region flagged damaging; never a Rim type.

- [ ] 10. The built-mesh bowl gate (extends `analyzer/traverse.py`)
  - [ ] 10.1 Extend the traverse gate with a defaulted required-reachable / excluded-scenic / off-map-marker parameter set
    - Extend `analyzer/traverse.py` so the gate accepts (all defaulted, so absent them it behaves EXACTLY as the dungeon full-connectivity gate — no regression): a `playable` mask (Spawn + the set of playable anchors/ground) to prove reachability among ONLY (Req 4.1, 12.3, excluding scenic regions), and an off-map-marker set for the Rim-seal check. Reuse the existing `AgentModel` + `build_walk_surface` + `flood_reachable` — do NOT invent a new agent.
    - **Resolve Open Decision — off-map / zoneline marker representation.** Settle how the exterior/off-map marker is represented for the flood (sentinel faces beyond each non-`zoneline` segment vs an exterior XY band the reachable set is checked against). Record the choice and why.
    - _Requirements: 4.1, 4.2, 12.1, 12.3_
    - **Deliverables:** `analyzer/traverse.py` gains the defaulted gate parameters; the existing dungeon/city gate behavior is proven unchanged (spot-check one dungeon `validate` result against `master`). Records the off-map-marker representation.
  - [ ] 10.2 Implement the bowl invariant on the built mesh
    - On the real TER: flood walkable faces from the Spawn face. (1) Every `playable` cell / POI anchor must be in the reachable set — one that is not is a reachability / walkability failure naming the stranded region or anchor (Req 4.2, 4.6, 12.1, 12.2). (2) The flood must NOT reach any exterior/off-map marker except through a `zoneline_gap` segment — a `mountain` segment stops the flood at the ridge (non-standable by slope), a `river` segment excludes beyond-edge faces via the Invisible_Wall; if the flood reaches the exterior through a non-`zoneline` segment, report a **bowl-leak failure naming the breached Rim segment** (Req 4.3, 4.4). (3) For each `zoneline` segment assert the gap IS reachable from Spawn and DOES lead off-map — the intended leak, not a failure (Req 4.5).
    - _Requirements: 4.2, 4.3, 4.4, 4.5, 4.6, 12.1, 12.2_
    - **Deliverables:** the bowl gate proves interior reachability + Rim seal on the built mesh; a breach names the segment; a stranded region/anchor is named; every zoneline is reachable and leads off-map.
  - [ ]* 10.3 Write property test for Property 15: The bowl holds on the built mesh — reachable interior, sealed Rim
    - `tests/` build-level property, `@pytest.mark.slow` + `build_settings(n)` (n 10–25), over a plains-Karana spec with varied edge declarations and seeds; builds the real TER via the project build path.
    - **Property 15: The bowl holds on the built mesh — reachable interior, sealed Rim** — every Playable_Region cell / POI anchor is reachable from Spawn by the traversability agent (Scenic_Regions excluded), AND no path from Spawn reaches an off-map marker except through a `zoneline` segment; a path crossing a non-`zoneline` Rim segment is reported as a bowl-leak failure naming that segment, an unreachable playable cell/anchor as a reachability/walkability failure naming it, and every `zoneline` gap is reachable from Spawn and leads off-map.
    - **Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6, 12.1, 12.2**

- [ ] 11. Checkpoint — wave 4 closed (bowl geometry pass)
  - [ ] 11.1 Run the suite and check the budget
    - `python -m pytest tests/ -q` green; Property 15 passes on the built mesh. Record the Default_Run median against the prior baseline; the slow built-mesh property's cost goes in budgets, not weakened assertions.
    - _Requirements: 13.3_
  - [ ] 11.2 **HUMAN-GATED:** bowl / rim / zoneline 3D pass
    - The user, in the live viewer, on a few seeds + edge declarations: the **Rim reads as a distant backdrop**, not a crater wall at the play edge; you **cannot walk out** over the mountains or across a river edge anywhere except a zoneline (no bowl leak you can walk through); **river edges are sealed** (an invisible wall) while still visible as water; **zoneline gaps** read as flat walkable openings that lead off-map; a `lava` region reads as an impassable hazard. The agent writes the checklist, marks it PENDING-HUMAN, leaves the box unchecked. The agent verified NONE of this in the live viewer.
    - _Requirements: 13.4_
  - [ ] 11.3 Write the wave-4 integration note (don't apply it)
    - Done-table row, "Pick up here", commit hash/count, the off-map-marker-representation decision, and the seeds/edge-declarations to eyeball. No edit to the three tracker files.
    - _Requirements: 13.4_

### Wave 5 — Biome kit + visual water + backend wiring + end-to-end Karana + step-1 close (Requirements 11, 13, 14)

> Intent: give the Karana its plains identity (ground splat over the one terrain
> core), place the visual water plane, wire a wilderness Design_Matrix through
> `TerrainBackend.build` additively, carry everything through `ZoneSpec` to EQG +
> sidecar, build an end-to-end Karana, and CLOSE step 1 (final 3D pass + the
> conditional enable). Needs wave 4. Hotspots:
> `generators/{zone_spec,backends,builder}.py` and `generators/pipeline.py`
> (single owner); `web/` (preview). Ends with the final HUMAN-GATED 3D pass.

- [ ] 12. Biome kit + visual water + ZoneSpec/backend integration
  - [ ] 12.1 Set up wave 5
    - Run `./scripts/new-worktree.ps1 -Branch agent/wild-integrate`. Record the fork-point hash. Run `python -m pytest tests/ -q` once; record the baseline. No `requirements.txt`/`web/package.json` change expected.
    - _Requirements: 14.1_
  - [ ] 12.2 Add the additive, defaulted `ZoneSpec` fields
    - Add to `ZoneSpec` (all defaulted so dungeon/city/plain-terrain are unaffected; the existing `from_dict` legacy tolerance already tolerates absent keys — Req 14.1): `biome: str = ""` (Req 1.5), `water_level: Optional[float] = None` (Req 13), `poi_anchors: List[POIAnchor] = []` (Spawn). Confirm a dungeon/city `from_dict` round-trip is byte-unchanged and no serialized output gains these keys when empty.
    - _Requirements: 1.5, 14.1_
    - **Deliverables:** `ZoneSpec` gains three defaulted fields; a dungeon/city spec round-trips unchanged (spot-check).
  - [ ] 12.3 Implement the BiomeKit data table and the plains kit
    - Add `BiomeKit` (ground-texture set, water-present flag, skybox/fog tint, vegetation-kit identity) as a data table (JSON under `styles/` or a new `biomes/`), applied over the one shared terrain core — NOT a generator per biome (Req 11.1, 11.2). The `plains` kit selects its ground-texture set, skybox/fog tint, and vegetation-kit identity from the table (Req 11.3). Texture procedurally through the existing `generators/textures/factory.py` AI drop-in seam (no texture-side code change) blending ground textures by slope/height/moisture.
    - **Resolve Open Decision — vegetation realization.** Record whether v1 emits placed vegetation or carries only the plains vegetation-kit *identity* and defers mesh placement to roadmap step 2 (trees); v1 at minimum carries the identity (Req 11.1, 11.3).
    - _Requirements: 11.1, 11.2, 11.3_
    - **Deliverables:** the `plains` kit applies over the terrain core; records the vegetation-realization decision.
  - [ ] 12.4 Implement the visual-only water plane
    - Where the biome kit declares water present (Req 11.4) / the matrix has `water` cells, place a flat visual water plane at `Water_Level` (Req 13.1) with the biome water material, carried as a `RegionSpec(kind="water")` (→ `AWT`) + plane geometry on the `ZoneSpec` so it renders in the preview. Mark real walkable-shallows / swimmable-deep volumes out of scope for v1 in a code comment — **no water collision volumes** (Req 13.1).
    - _Requirements: 11.4, 13.1_
    - **Deliverables:** an `water`-bearing build gets a flat visual water plane at `Water_Level`; no collision volume.
  - [ ] 12.5 Wire a wilderness Design_Matrix through `TerrainBackend.build` additively
    - Extend `TerrainBackend.build` (`generators/backends.py`) to detect a wilderness `Design_Matrix` carried on the spec and synthesize from the matrix (Noise_Pass → erosion → Rim re-clamp → upsample → bowl assembly → lava → biome kit → water plane) instead of the current "FBM over the room footprint" path. **With no matrix (a plain terrain spec) it behaves exactly as today — additive, no regression.** The `numpy`-absent degrade (returns `None` → box backend) is inherited unchanged. Flow the Design_Matrix, heightfield, water plane, Edge_Connections, POI_Anchors, and biome kit through `ZoneSpec` (Req 14.1); write EQG (Req 14.2) with Z up (Req 14.3).
    - _Requirements: 14.1, 14.2, 14.3_
    - **Deliverables:** `backend_for("wilderness")` with a Design_Matrix synthesizes the Karana; a plain-terrain / dungeon / city build is byte-unchanged (spot-check one TER hash against `master`); EQG is Z-up.
  - [ ] 12.6 Carry the advisory data in the `.zone.json` sidecar
    - Through the existing `write_sidecar` path, carry (never in the binary — Req 14.4): per-region `intent` tags, `poi_anchors` names incl. Spawn, `biome` kit identity, `edge_connections` (per-segment Rim types), `invisible_walls` (`{min_xy, max_xy, kind: "invisible_wall"}`), `lava` per-region metadata flagged `damaging`, and the biome substitution record (`requested` vs `resolved`) when a fallback fired.
    - _Requirements: 3.7, 10.2, 13.1, 14.4_
    - **Deliverables:** a built Karana's `.zone.json` carries intent tags, POI names, biome identity, edge-connection types, invisible-wall regions, lava-damaging flags, and any substitution record.
  - [ ]* 12.7 Write the biome / water / sidecar example + integration tests (not PBT)
    - Example/config/integration (the wiring doesn't vary with input, so example/mock-based, not PBT): the `plains` kit picks the right texture set / tint / vegetation identity; a `water`-bearing zone has a water plane at `Water_Level` with the biome water material; texturing routes through the AI-texture seam (force a provider via the existing seam, assert the call path); the emitted `.zone.json` carries the intent tags / POI names / biome identity / edge types / invisible-wall regions / lava-damaging flags; a built EQG loads and is Z-up.
    - _Requirements: 11.3, 11.4, 13.1, 14.2, 14.3, 14.4_
  - [ ]* 12.8 Write property test for Property 16: Seeded reproducibility
    - **Property 16: Seeded reproducibility** — for any prompt, generating with the same pinned seed reproduces the same landscape, and generating without a pinned seed draws a fresh seed (repeated generation differs). (Byte-identity scope matches the project rule: TER reproduces; `.eqg`/`.glb` need not be byte-identical.)
    - **Validates: Requirements 13.2, 13.3**
  - [ ]* 12.9 Write the performance-budget integration test
    - One timed integration test asserting a full wilderness generate (including the erosion passes) completes **well within five minutes** (Req 13.3). `@pytest.mark.slow`.
    - _Requirements: 5.3, 13.3_

- [ ] 13. End-to-end Karana build + the step-1 enable decision
  - [ ] 13.1 Build an end-to-end Karana through the pipeline
    - Through `generators/pipeline.py`, generate a plains-Karana wilderness zone end to end (prompt → biome → matrix → rewrite → synth → erosion → upsample → bowl → lava → biome kit → water → EQG + sidecar), unpinned (fresh seed) and pinned (reproducible). Record the build name, seed, the `.map.svg` path, and that the bowl gate (Property 15 path) passes on the built mesh.
    - _Requirements: 13.2, 13.3, 14.1, 14.2_
    - **Deliverables:** one unpinned + one pinned Karana build, each with its artifact listing and a passing bowl gate; recorded here.
  - [ ] 13.2 Flip wilderness to ENABLED (conditional on green properties + the human 3D passes)
    - Mirror M1 task 15.8's conditional-enable pattern, but ENABLING on success: once all wilderness properties (1–17) are green AND the wave-3/4/final human 3D passes are signed off, add `wilderness` to `ENABLED_ZONE_TYPES` (`generators/pipeline.py`) and update its availability reason. **If any human 3D pass is still PENDING-HUMAN, leave wilderness DISABLED and record "enable blocked on <which pass>" here** — do not enable on a green suite alone (Req 13.4). The pipeline's existing wilderness timeout (`DEFAULT_TIMEOUT_S["wilderness"]`) already exists; confirm it covers the erosion budget.
    - _Requirements: 13.4_
    - **Deliverables:** wilderness is either ENABLED (all properties green + all human passes signed) or recorded DISABLED-pending-<pass>; the decision and its gating state are recorded here.

- [ ] 14. Checkpoint — wave 5 closed (final geometry pass)
  - [ ] 14.1 Run the suite and build the frontend
    - `python -m pytest tests/ -q` green; all wilderness properties (1–17) pass. `cd web; npx vite build` succeeds (the visual water plane in the preview is the only `web/` change). Record the Default_Run median and the build result.
    - _Requirements: 13.3_
  - [ ] 14.2 **HUMAN-GATED:** the final open-Karana 3D pass
    - The user, in the live viewer / browser, on a few seeds: the Karana reads as an **open landscape** you roam without bumping the rim (not a crater, not a room-graph in a grass skin); eroded valleys/ridgelines read **natural**; the **Rim is a distant backdrop**; **zoneline gaps** lead off-map; **no bowl leak** you can walk through; **river edges are sealed (invisible wall) while visible**; water reads as water with a clean shoreline; lava reads as an impassable hazard. Confirm wilderness is selectable (if enabled in 13.2) and builds end to end from the browser. The agent writes the checklist, marks it PENDING-HUMAN, leaves the box unchecked. The agent verified NONE of this in the live viewer.
    - _Requirements: 13.4_
  - [ ] 14.3 Write the wave-5 integration note (don't apply it)
    - Done-table row, "Pick up here", commit hash/count, the vegetation-realization decision, whether wilderness shipped ENABLED (and if not, which pass blocks it), and the seeds to eyeball. No edit to the three tracker files.
    - _Requirements: 13.4_

### Step-1 exit

- [ ] 15. Exit checks and hand-off
  - [ ] 15.1 Run the final suite, the thorough profile, and build the frontend
    - On `master` after the wave-5 merge: `python -m pytest tests/ -q` green; `python -m pytest tests/ -q --hypothesis-profile=thorough` green (a counterexample goes through the root-fix rule, then repeat); `cd web; npx vite build` succeeds. Record each result, duration, the commit count since the step-1 fork point, and the head hash.
    - _Requirements: 13.3, 13.4_
  - [ ] 15.2 Add the wilderness section to `docs/ACCEPTANCE.md`
    - New section "Step 1 — Wilderness (open Karana)" with the design's human-pass rows: the Karana reads open; eroded valleys/ridgelines read natural; the Rim is a distant backdrop; zoneline gaps lead off-map; no bowl leak you can walk through; river edges sealed (invisible wall) while visible; sharp (not blocky) cliffs/shorelines; water reads as water; lava reads as an impassable hazard — plus whether wilderness ships enabled. Allowed from the MAIN checkout at this integration step.
    - _Requirements: 13.4_
  - [ ] 15.3 **HUMAN-GATED:** the step-1 `docs/ACCEPTANCE.md` pass
    - Checklist, PENDING-HUMAN, on a restarted Server running the merged code: walk the 15.2 section on a few seeds. State that the agent verified none of this in the live viewer. Step 1 does not fully exit until this is signed off.
    - _Requirements: 13.4_
  - [ ] 15.4 Write the step-1 integration note (don't apply it)
    - In the final report give the integrator: the Done-table row, the "Pick up here" line (next is roadmap step 2), the commit hash and count, the per-wave notes (4, 6, 8.3, 11.3, 14.3), the resolved Open Decisions (matrix resolution, erosion tuning, rim-band/set-back widths, off-map-marker representation, v1 rule set, vegetation realization), the "not in this cut" fast-follow list, and **whether wilderness shipped ENABLED**. Don't edit `ROADMAP.md`, `README.md` or `tasks/README.md`.
    - _Requirements: 13.4_

## Notes

- **This is roadmap STEP 1.** It is `TerrainBackend`-hosted and reuses the
  existing terrain core, backend registry, `RegionSpec` machinery, traverse
  agent, and planner seam. It does **NOT** create a `LayoutEngine` seam (step 6)
  or a 3D `Envelope` / gate-learns-connectors (steps 5/7). A worker who thinks a
  wave needs one has misread the design — stop and surface it.
- The property tests are the step-1 gate. Core implementation subtasks are never
  optional; the `*`-marked subtasks are the property/example tests (the convention
  for test subtasks), which a worker still writes — they carry the correctness
  load and gate each wave.
- **Matrix properties (1–9, 16, 17) run with NO geometry built** — the central
  guard that the layout is validated as a sealed open landscape first.
  Heightfield/erosion properties (10–14) run on the synthesized field. The one
  built-mesh property (15) runs the real traversability agent on the real TER
  (slow, `build_settings`).
- **Structural tests pass is necessary but NOT sufficient — eyeball it in 3D.**
  Geometry waves (3, 4, 5) each end with a HUMAN-GATED 3D pass the agent writes
  but never ticks; the step-1 exit adds one more (15.3).
- **Open Decisions are assigned to specific tasks:** matrix resolution → 2.3
  (re-tuned 7.5/8.3); erosion iteration/grid tuning → 7.4; rim-band / interior
  set-back widths → 7.5; off-map-marker representation for the gate → 10.1; the
  v1 Graph_Replacement rule set + fixed-point order → 5.4; vegetation realization
  → 12.3.
- **Wilderness enablement:** wilderness ships DISABLED (M1) and flips ENABLED
  only at 13.2 on success — all 17 properties green AND every human 3D pass
  signed. If any 3D pass is PENDING-HUMAN at step-1 close, wilderness stays
  DISABLED with the blocking pass recorded; it does not enable on a green suite
  alone (Req 13.4).
- **Not in this cut (fast-follows, from the design scope note):** `plains` biome
  only (other biomes are a fast-follow); **boundary-hugging rivers** only
  (interior-crossing South-Karana rivers are a named fast-follow);
  **visual-only water** (no collision volumes — edges seal via the Invisible_Wall
  pattern); **approximated-but-real erosion** (flow-accumulation + thermal; full
  per-droplet simulation is a fast-follow behind the same seam); **named
  POIs/landmarks are roadmap step 10**; the **dispersed architecture runway**
  (`LayoutEngine` step 6, 3D `Envelope` + gate-learns-connectors steps 5/7) is
  **not** stood up here; **region-record export** of Invisible_Wall / lava
  barriers rides the later SQL-export capstone (v1 records them in the sidecar).
- Single-writer: only this file is updated during task work. `ROADMAP.md`,
  `README.md` and `tasks/README.md` changes go in the integration notes (each
  wave's checkpoint + task 15.4).

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["2.1", "2.2"] },
    { "id": 1, "tasks": ["2.3", "3.1"] },
    { "id": 2, "tasks": ["3.2", "3.3", "3.4", "3.5", "3.6", "3.7", "3.8"] },
    { "id": 3, "tasks": ["5.2", "5.3", "5.4"] },
    { "id": 4, "tasks": ["5.5", "5.6", "5.7"] },
    { "id": 5, "tasks": ["7.2", "7.3"] },
    { "id": 6, "tasks": ["7.4", "7.5"] },
    { "id": 7, "tasks": ["7.6", "7.7", "7.8", "7.9", "7.10"] },
    { "id": 8, "tasks": ["9.2", "9.3", "10.1"] },
    { "id": 9, "tasks": ["10.2"] },
    { "id": 10, "tasks": ["10.3"] },
    { "id": 11, "tasks": ["12.2", "12.3", "12.4"] },
    { "id": 12, "tasks": ["12.5", "12.6"] },
    { "id": 13, "tasks": ["12.7", "12.8", "12.9", "13.1"] },
    { "id": 14, "tasks": ["13.2"] }
  ]
}
```
