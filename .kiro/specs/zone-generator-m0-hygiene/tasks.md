# Implementation Plan: M0 — Hygiene + PBT harness

## Overview

This plan implements `requirements.md` and `design.md` in this folder. "Req X.Y"
means this spec's criterion. "Property N" means this spec's design Correctness
Property N. "Pn" means the umbrella (`zone-generator`) property. Steps are ordered
so each one can be committed on its own and the suite stays green after each
commit. The only exception is 5.2 + 5.3, which land in one commit.

Working rules for every task:

- Work in a `-Venv` worktree, because `requirements.txt` changes:
  `./scripts/new-worktree.ps1 -Branch agent/m0-hygiene -Venv`. Stay in it. Don't
  push the branch.
- Commit one logical change at a time. Write the message to
  `.git/COMMIT_EDITMSG_TMP`, run `git commit -F .git/COMMIT_EDITMSG_TMP`, then
  delete the file. Messages must not contain the words blocked by the
  commit-message hook (the frontend tool name and "dev server").
- Tracker writes go to this `tasks.md` only (checkboxes, recorded measurements,
  commit hashes). Don't edit `ROADMAP.md`, `README.md` or `tasks/README.md`.
  Those changes go in the integration note (task 18.3).
- Run `python -m pytest tests/ -q` before each commit.

## Tasks

- [ ] 1. Set up the worktree and capture pre-M0 baselines
  - [ ] 1.1 Create the M0 worktree with an isolated venv
    - Run `./scripts/new-worktree.ps1 -Branch agent/m0-hygiene -Venv` from the MAIN checkout. In the worktree venv, install the current `requirements.txt` pins and record the fork-point commit hash here.
    - Check the installed starlette version (pulled in by `fastapi==0.115.6`) and confirm that `CORSMiddleware.preflight_response(self, request_headers)` exists with that signature. Record the result here for task 7.1.
    - _Requirements: Delivery and process (-Venv worktree)_
  - [ ] 1.2 Record the pre-M0 Default_Run timing baseline
    - On the fork-point code, in the worktree venv, with no `pytest.ini`, run `python -m pytest tests/ -q` 3 times in a row. Delete `.hypothesis/` before each run if it exists. Record the three wall-clock times and their median here (expected ≈ 85 s).
    - _Requirements: 1.4_

- [ ] 2. Build the property-test harness
  - [x] 2.1 Pin test dependencies and ignore the Hypothesis database
    - Add `hypothesis==6.170.5` and `httpx==0.28.1` to `requirements.txt`, with httpx commented as test-only (it backs FastAPI `TestClient`). Install both in the venv.
    - Add `.hypothesis/` to `.gitignore` under "Test artifacts".
    - _Requirements: 1.1, 1.8_
    - **Done.** Added a `# Testing` block to `requirements.txt` pinning `hypothesis==6.170.5` and `httpx==0.28.1` (commented test-only, backs FastAPI `TestClient`). Added `.hypothesis/` under "Test artifacts" in `.gitignore`. Installed both into the worktree venv (`hypothesis` + `sortedcontainers` fresh; `httpx==0.28.1` already satisfied, pulled in earlier). Suite green: **197 passed** before commit.
    - **Commit:** `4a16304` ("M0 2.1: pin test deps and ignore Hypothesis database") — `requirements.txt` and `.gitignore` only.
  - [x] 2.2 Add `pytest.ini` at the repo root
    - Set `testpaths = tests`. Register `slow` as the only custom marker, with the description from the design. No `addopts`.
    - _Requirements: 1.2_
    - **Done.** Added `pytest.ini` at the repo root with the exact design content: `[pytest]`, `testpaths = tests`, and a `markers` block registering only `slow` ("build-level property test (runs the Zone_Builder or Pipeline); deselect with -m \"not slow\""). No `addopts`. Verified `pytest --markers` lists the `slow` marker and `pytest --co -q` collects 197 tests from `tests/` with no unknown-marker warning. (Hypothesis isn't installed in the venv yet — task 2.1 — so the Property_Suite modules aren't present; marker registration is the deliverable here.)
    - **Commit:** `48ea28b` ("Add pytest.ini registering the slow marker (M0 2.2)") — `pytest.ini` only.
  - [ ] 2.3 Add `tests/conftest.py`
    - When the module is imported, register the `default` profile (`max_examples=100, derandomize=True, database=None, deadline=200`) and the `thorough` profile (`max_examples=500, derandomize=False, deadline=None`, default database). Then call `load_profile("default")`.
    - Add a `no_api_keys` fixture. It deletes `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `STABILITY_API_KEY`, `EQ_S3D_PLANNER` and `EQ_S3D_TEXTURE_PROVIDER`, then calls `ai.planner.set_planner(None)` and `generators.textures.factory.set_provider(None)`.
    - Add a `no_network` fixture. It patches `socket.socket.connect`, `connect_ex`, `bind` and `socket.getaddrinfo` so that loopback and `AF_UNIX` pass through, and every other target is recorded in `attempts` and raises `OSError`.
    - _Requirements: 1.3, 1.9, 5.4, 5.5, 8.3, 8.4_
  - [x] 2.4 Add `tests/strategies.py`
    - Implement `seeds`, `room_counts(lo, hi)`, `box_themes`, `spec_themes`, `semantic_inputs`, `verticality`, `zone_plan_dicts`, `pfs_names` and `origins_outside` as specified in the design Strategies table.
    - Implement `pfs_entries` as a descriptor-based composite: explicit entries are `(name, (length, byte_seed))`; bulk entries use `bulk_n`/`bulk_seed` with case-insensitive deduplication. Expand payloads with `random.Random(byte_seed).randbytes(length)`. This keeps the Hypothesis buffer under its limit.
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.3, 3.5, 9.3_
    - **Done.** Added `tests/strategies.py` with module constants `DEFINED_THEMES`
      and `CAVE_WORDS`, and strategies `seeds`, `room_counts`, `box_themes`,
      `spec_themes`, `verticality`, `semantic_inputs`, `zone_plan_dicts`,
      `pfs_names`, `pfs_entries` (descriptor-based composite, reaches the full
      2000-entry regime so the P13 600-name `@example` is drawable) and
      `origins_outside`. Verified: module imports standalone
      (`python -c "import tests.strategies"`); every strategy produces examples;
      `zone_plan_dicts` feeds `ZonePlan.from_dict` cleanly; `pfs_entries` yields
      case-insensitively-unique name→bytes maps with deterministic payload
      expansion; `origins_outside` never emits an allowed origin;
      `pytest --collect-only` still green (197 tests, no import error).
    - **Symbol deviations / notes:**
      - All vocab constants (`VALID_DUNGEON_THEMES`, `VALID_DUNGEON_RACES`,
        `VALID_ELEMENTAL_TINTS`, `VALID_REGION_KINDS`) and `ZonePlan` live in
        **`ai/schema.py`** (imported from there) — names match the design.
      - `origins_outside` filters against `server.app.WEB_APP_ORIGINS`, which
        **does not exist yet** (task 7.1 adds it). The strategy does a late
        import of `WEB_APP_ORIGINS` and falls back to the design's literal tuple
        (`http://127.0.0.1:8000`, `http://localhost:8000`,
        `http://localhost:5173`, `http://127.0.0.1:5173`) until 7.1 lands, so
        `strategies.py` imports cleanly now. **Dependency for 7.1:** server/app.py
        must expose `WEB_APP_ORIGINS` with exactly that membership.
      - `ai.schema.VALID_THEMES` still contains `"cave"` at the fork point
        (removed in 5.2), so `DEFINED_THEMES` is a hand-written literal
        `{"dungeon","city","outdoor"}`, and `zone_plan_dicts`' `theme` vocab still
        includes `"cave"` on purpose (to exercise the cave→dungeon normalisation).
    - **Commit:** `fd60c42` (adds `tests/strategies.py`; this tracker line was
      recorded in a follow-up commit).
  - [ ] 2.5 Add `tests/pbt_helpers.py`
    - Implement `scaled`, `build_settings`, `fresh_dir`, `build_raw`, `room_graph`, `solvable_walk`, `run_for`, `upward_faces`, `ramp_rises`, `opening_floor_z`, `clear_advisory`, `f32` and `ref_crc` per the design Helpers table.
    - `build_raw` must compare the TER and ZON read back from the `.eqg`, never the `.eqg` bytes. `run_for` must call the production `LayoutGenerator._elevation_run`. `ref_crc` must not use `core.pfs`'s table.
    - `build_settings(n)` asserts `10 <= n <= 25`.
    - _Requirements: 1.3, 1.5, 2.2, 2.3, 3.2, 3.3, 3.4, 4.2, 4.5_

- [ ] 3. Checkpoint: harness in place
  - Run `python -m pytest tests/ -q`. It must be green with no `PytestUnknownMarkWarning`. Commit the harness. Ask the user if questions arise.

- [ ] 4. Capture the outdoor TER baseline before any deletion
  - [ ] 4.1 Capture the fork-point hashes and add the baseline test
    - On the unchanged fork-point code, in the worktree venv, run a one-off snippet (don't commit it). For each seed in `(7, 1955208177, 2147483647)`, build `LayoutGenerator("outdoor", seed=s).generate(f"ob{s}", room_count=6)` through `build_raw` and print `sha256(ter_bytes)`.
    - Add `tests/test_hygiene.py` with `OUTDOOR_BASELINE_SEEDS` and `test_outdoor_ter_matches_fork_point`, parametrised over the three seeds, asserting each hash against its literal. Add a comment naming the fork-point commit hash and the capture procedure. A later mismatch is a bug in the deletion, never a reason to recapture.
    - Commit this first, before any task-5 deletion.
    - _Requirements: 6.3_

- [ ] 5. Delete the cave pipeline and the `cave` theme
  - Commit one sub-task at a time and keep the suite green after each commit. Code and the tests of that code are deleted in the same commit. 5.2 and 5.3 land in one commit. `test_outdoor_ter_matches_fork_point` must pass unchanged after every commit.
  - [ ] 5.1 Delete the cave pipeline code and its dependencies
    - Delete `generators/field/cave.py`, `features.py`, `mesh.py` and `sdf.py`.
    - `generators/field/noise.py`: delete `fbm_field` and `from .sdf import FieldGrid`. Keep `_value_noise_3d` and its helpers. Reword the module docstring to "terrain heightfields". Drop "caves" from the `generators/field/__init__.py` comment.
    - `generators/builder.py`: delete `_CAVE_THEMES`, the cave branch of `_build_geometry` and `_build_organic`. Reword the step-1 comment and the `'cave_rock'` mention in the material colour docstring.
    - `generators/layout.py`: delete the `"cave"` entries in the per-theme material table and light-colour table.
    - `generators/pipeline.py`: drop "cave" from the `DEFAULT_GATED_THEMES` comment and the module and `generate_validated` docstrings. The set stays `{"dungeon"}`.
    - `requirements.txt`: remove `scikit-image==0.26.0` and `fast-simplification==0.1.11`.
    - Delete `tests/test_cave.py` in the same commit.
    - If a remaining cave-theme test goes red on this commit, fold 5.2 + 5.3 into it rather than committing red.
    - _Requirements: 6.1, 6.2, 6.4, 6.10, 7.1, 7.2_
  - [ ] 5.2 Remove `cave` from the theme surface
    - `ai/schema.py` and `server/app.py`: `VALID_THEMES = ["dungeon", "outdoor", "city"]`.
    - `main.py`: `--theme` `choices=["dungeon", "outdoor", "city"]`.
    - `web/index.html`: drop `<option value="cave">` and change the placeholder to `e.g. a flooded temple with lots of chambers`. Then run `cd web; npx vite build`.
    - `ai/rule_planner.py::_THEME_WORDS`: remove the `cave` bucket and append its words (`cave`, `cavern`, `grotto`, `tunnel`, `underground`, `mine`) to the `dungeon` bucket. Keep `mine` in `_ARCHETYPE_WORDS["mine_delve"]`, the dict order and the strict-`>` tie rule. Update the module docstring example per the design.
    - `generators/zone_spec.py::ZoneSpec.from_dict`: map theme `cave` to `dungeon`. No other theme is remapped.
    - `server/app.py` controls path: keep the existing 400 before the factory is built, and change the detail to list the valid themes per the design.
    - Commit together with 5.3.
    - _Requirements: 6.4, 6.5, 6.6, 6.7, 6.8_
  - [ ] 5.3 Retarget the cave-theme tests
    - `tests/test_pipeline.py`: delete the `assert "cave" not in DEFAULT_GATED_THEMES` line (~182).
    - `tests/test_traversability.py`: docstring "Outdoor/cave" → "Outdoor".
    - `tests/test_generators.py::test_rule_planner_open_is_zero`: keep the cave prompt and add `assert plan.theme == "dungeon"`.
    - `tests/test_planner.py`: update the five cave-theme tests per the design (`test_roundtrip_dict` and the two `TestExpand` tests use `outdoor`/`dungeon`; `test_from_dict_ignores_unknown` asserts `cave` → `dungeon`; `test_detects_cave` becomes `test_cave_words_mean_dungeon`, one prompt per Cave_Word). Add `test_zonespec_cave_theme_normalised`.
    - `tests/test_server.py`: add a controls POST with `theme="cave"` → 400, detail names all three Defined_Themes, `OUTPUT_DIR` stays empty.
    - `tests/test_pipeline.py`: add a `TestCliArgs` class with `main.main(["generate", "x", "--theme", "cave", "--output", out])` → `SystemExit(2)` and `out` not created. Add a slow example: unpinned `generate_validated` on `plan_to_spec(RulePlanner().plan("a dark underground cavern with many tunnels"), seed=s)` returns a validated build with theme `dungeon`.
    - _Requirements: 6.5, 6.6, 6.7, 6.8, 6.9_
  - [ ] 5.4 Run the suite without the cave-only dependencies installed
    - In the worktree venv, run `pip uninstall -y fast-simplification scikit-image`, then `python -m pytest tests/ -q`. Record the result here: zero failures, zero errors.
    - _Requirements: 7.3_
  - [ ] 5.5 Update the docs and steering for the cave removal
    - `docs/ACCEPTANCE.md`: remove `cave` from the theme list, retire C "Single connected cave" and section D (pending umbrella M5), drop the cave sweep snippet, and change "outdoor/cave" to "outdoor".
    - `.kiro/steering/lessons-learned.md`: rewrite the cave entries to "cave pipeline removed in M0; cave = dungeon archetype (M3), natural style (M5)". Keep the walkable-floor, no-decimation and voxel-fidelity facts as M5 guidance.
    - _Requirements: 6.1, 6.10_

- [ ] 6. Remove the legacy viewer
  - [ ] 6.1 Delete the viewer and its CLI entry points
    - Delete `viewer/` (`serve.py`, `index.html`).
    - In `main.py`, delete `cmd_preview`, `_launch_preview`, the `preview` subparser, the `--preview` option and the `if args.preview:` block. Rewrite the module docstring so it lists only `generate`. Change the entry point to `def main(argv: list[str] | None = None)` with `parser.parse_args(argv)`.
    - Remove `flask==3.1.0` from `requirements.txt` and rename the section comment to "API backend".
    - Drop `preview=False` from `TestCliEscapeHatch._args` in `tests/test_pipeline.py`.
    - Confirm that `README.md` and `docs/` contain no preview launch instruction.
    - _Requirements: 8.1, 8.2, 8.6_
  - [ ] 6.2 Add CLI tests for the removed preview paths
    - Add these to the `TestCliArgs` class in `tests/test_pipeline.py` (created in 5.3), using `no_network`:
      - `main.main(["preview", "x"])` exits with code 2 and stderr names `preview` as an invalid choice.
      - `main.main(["generate", "x", "--preview", "--output", out])` exits with code 2 and stderr names `--preview` as unrecognized.
      - In both cases no non-loopback bind and no listener is recorded, and `out` doesn't exist afterwards.
      - Neither `--help` nor `generate --help` output mentions "preview".
    - _Requirements: 8.3, 8.4, 8.5_

- [ ] 7. Bind the server to loopback and restrict CORS
  - [ ] 7.1 Implement the loopback bind and `LocalCORSMiddleware` in `server/app.py`
    - Add `HOST = "127.0.0.1"`, `PORT = 8000` and the `WEB_APP_ORIGINS` tuple.
    - Subclass `CORSMiddleware` and override `preflight_response` so that every `access-control-allow-*` header is removed when the origin is disallowed. Register the subclass with an explicit `allow_origins`, `allow_methods=["GET", "POST"]` and `allow_headers=["Content-Type"]`, and without credentials or expose headers.
    - Change `__main__` to `uvicorn.run("server.app:app", host=HOST, port=PORT, reload=False)`.
    - If 1.1 found that the override point differs at the pinned starlette version, use the design's fallback instead: a pure ASGI wrapper that strips the headers.
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.6, 9.7_
  - [ ] 7.2 Add example tests in `tests/test_server.py`
    - Use `TestClient`, with `OUTPUT_DIR`/`FAILURE_LOG` monkeypatched to `tmp_path`. Every response goes through an `assert_no_wildcard` helper. Cover:
      - 9.1: `runpy.run_module("server.app", run_name="__main__")` with `uvicorn.run` captured; assert host `127.0.0.1` and port 8000, with no real bind.
      - 9.2: ACAO is echoed byte-identically for each of the four origins.
      - 9.5: with origin `http://localhost:5173`, POST `/api/generate` (pinned seed, 3 rooms) returns 200 and is validated, then GET `glb_url` and `zone_url` return 200, each with ACAO echoed.
      - 9.6: a preflight for `POST` + `content-type` returns 200 with matching ACAO and Allow-Methods/Allow-Headers.
      - 9.7: a request with no `Origin` gets no ACA-* header.
    - _Requirements: 9.1, 9.2, 9.4, 9.5, 9.6, 9.7_
  - [ ] 7.3 Write the property test for foreign origins
    - **Property 18: Foreign origins get no CORS grant**
    - In `tests/test_server.py`, `@given(origins_outside)`: simple GET, POST and preflight responses carry no `access-control-allow-*` header and never `Access-Control-Allow-Origin: *`. Include a Property_Docstring.
    - **Validates: Requirements 9.3, 9.4**

- [ ] 8. Checkpoint: removals and server change landed
  - Run `python -m pytest tests/ -q`. It must be green. Tasks 4–7 are committed separately (4.1 first; 5.2 + 5.3 together). Ask the user if questions arise.

- [ ] 9. Core property module (`tests/test_properties_core.py`)
  - [ ] 9.1 Write the property test for the PFS archive round-trip
    - **Property 1: PFS archive round-trip** (umbrella P13)
    - `test_pfs_roundtrip` over `pfs_entries`, with a budget of `scaled(100)`.
    - Assert that `from_bytes(to_bytes(arc))` gives an equal name→bytes map with case-preserved names and no extra entries.
    - Pin `@example` for 600 bulk names of length 60 (name block ≈ 39,000 B, which is also multi-chunk).
    - If a CRC collision or a sentinel clash appears, stop and ask the user. Don't narrow the strategy.
    - **Validates: Requirements 2.1, 1.6**
  - [ ] 9.2 Write the property test for the PFS filename CRC
    - **Property 2: PFS filename CRC matches the reference** (umbrella P14)
    - `test_pfs_crc_matches_reference`: assert `_filename_crc32(n) == ref_crc(n)`.
    - Pin `@example`s for the two existence claims: `"gukbottom.ter"` differs from `zlib.crc32`, and `"Ab"` differs from `"aB"`. Add `event()` counts across generated names.
    - **Validates: Requirements 2.2, 1.6**
  - [ ] 9.3 Write the property test for the built TER/ZON round-trip
    - **Property 3: Built TER and ZON round-trip** (umbrella P15)
    - `test_ter_zon_roundtrip` with `@pytest.mark.slow` and `build_settings(20)`, over `box_themes`, n 2–12 and `semantic_inputs`.
    - Assert that `ter.to_bytes()` from `ZoneBuilder._build_geometry` equals the archived TER. Then assert field-wise equality of vertices, polygons, materials, objects, lights and regions, with floats bit-equal via `f32`.
    - **Validates: Requirements 2.3, 1.5, 1.6**

- [ ] 10. Layout property module (`tests/test_properties_layout.py`)
  - [ ] 10.1 Write the property test for the ZoneSpec JSON round-trip
    - **Property 4: ZoneSpec JSON round-trip** (umbrella P11)
    - `test_zonespec_json_roundtrip` over `spec_themes`, n 1–30, locks 0–5, elevation and `semantic_inputs`.
    - Assert `ZoneSpec.from_dict(json.loads(j)).to_dict()` (normalised through JSON) `== json.loads(j)`, with exact float equality.
    - **Validates: Requirements 2.4, 1.6**
  - [ ] 10.2 Write the property test for connectivity and pacing roles
    - **Property 5: Layout connectivity and pacing roles** (umbrella P3, single District)
    - `test_connectivity_and_roles` over `box_themes`, n 1–30 and `semantic_inputs`.
    - Assert that the Room_Graph is connected and has exactly n rooms, that exactly one room is the entrance, and that for n ≥ 2 exactly one room is the climax and it isn't the entrance.
    - **Validates: Requirements 3.1, 1.6**
  - [ ] 10.3 Find a generated input that reaches the key-room fallback (one-off scan, not committed)
    - Scan `LayoutGenerator.generate` over seeds, n 4–8, locks 3–5 and M0_Box_Themes. Stop at the first input where some `gate.key_room_id` equals the entrance id, and record it here.
    - If no input turns up in ≥ 200k candidates, stop and report to the user. A constructed `_apply_gating` call would be a deviation that needs their approval.
    - _Requirements: 3.6_
  - [ ] 10.4 Write the property test for gating solvability, including the pinned fallback
    - **Property 6: Gating is solvable** (umbrella P4, single District)
    - `test_gating_solvable` over `box_themes`, n 3–30, locks 1–5, `semantic_inputs` and an `expect_fallback` argument (`False` for generated cases).
    - Assert `1 <= len(gates) <= locks` and that `solvable_walk` visits every room.
    - Pin the 10.3 input as `@example(..., expect_fallback=True)`. For that example, assert `key_room_id == entrance_id`.
    - **Validates: Requirements 3.2, 3.6, 1.6**
  - [ ] 10.5 Write the property test for the elevation grade cap
    - **Property 7: Elevation grade cap** (umbrella P6)
    - `test_elevation_grade_cap` through `ai.expand.plan_to_spec` over `box_themes`, n 2–30, `verticality`, elevation and `semantic_inputs`.
    - Assert `|from_z − to_z| <= run_for(...) * 0.5 + 0.01` for every corridor, tree and loop edges alike.
    - The known suspect here is semantic `sink` with elevation off. If it fails, follow task 13.1. Never drop semantic inputs from the strategy.
    - **Validates: Requirements 3.3, 1.6**
  - [ ] 10.6 Write the relax-conflict fallback example test
    - **Property 7: Elevation grade cap** (umbrella P6, constructed conflict case)
    - `test_relax_conflict_fallback`: set up `LayoutGenerator("dungeon", seed=0)` with `_apply_room_scale(3)` and rooms E (z 0), B (z 0) and C (z 200), each 200×200 on the X axis with 40 u gaps, and `adj` with B inserted first.
    - Precondition: B's two walkable bands, computed with `gen._elevation_run`, are disjoint. This proves the midpoint branch runs.
    - Postcondition: after `_relax_elevation`, every adjacent pair satisfies `|Δz| <= run * 0.5 + 0.01`.
    - **Validates: Requirements 3.7, 1.6**
  - [ ] 10.7 Write the property test for flush openings
    - **Property 8: Flush openings** (umbrella P7)
    - `test_flush_openings` with a budget of `scaled(50)`, over `box_themes`, n 2–12 and elevation, using `geometry.build_mesh(spec).to_ter(...)` in memory.
    - Assert that `from_z`/`to_z` equal the rooms' `floor_z`.
    - Assert that every `opening_floor_z` value under `(from_x, from_y)` and `(to_x, to_y)` lies within 0.01 u of that room's `floor_z`.
    - **Validates: Requirements 3.4, 1.6**
  - [ ] 10.8 Write the property test for ZonePlan normalisation
    - **Property 9: ZonePlan normalisation** (umbrella P12, no controls path)
    - `test_zoneplan_normalisation` over `zone_plan_dicts`.
    - Assert that every field of `ZonePlan.from_dict(d)` is inside its umbrella-Req 2.3/2.4/2.8 domain, and that a second `validate()` returns an equal plan.
    - **Validates: Requirements 3.5, 1.6**
  - [ ] 10.9 Write the property test that cave words never yield a cave theme
    - **Property 19: Cave words never yield a cave theme**
    - `test_cave_words_mean_dungeon` in `tests/test_properties_layout.py`, budget 100, over prompts containing one or more Cave_Words mixed with random filler and optional outdoor/city/dungeon keywords.
    - Assert that `RulePlanner().plan(prompt).theme` is in the Defined_Themes, and equals `dungeon` whenever the dungeon-bucket score (computed in the test from `_THEME_WORDS` with `str.count`) is strictly greater than the outdoor and city scores. Include a Property_Docstring.
    - **Validates: Requirements 6.5**

- [ ] 11. Build property module (`tests/test_properties_build.py`, all `@pytest.mark.slow` with `build_settings`)
  - [ ] 11.1 Write the property test for raw dungeon navigability
    - **Property 10: Raw dungeon builds are navigable** (umbrella P1, dungeon)
    - `test_raw_dungeon_navigable` with `build_settings(20)`, over dungeon, n 2–12 and elevation, using `LayoutGenerator.generate` + `build_raw` + `validate(eqg, spec=spec)`.
    - Builder exceptions propagate as failures. Never call `assume` here.
    - **Validates: Requirements 4.1, 1.5, 1.6**
  - [ ] 11.2 Write the property test for ramp subdivision
    - **Property 11: Ramp subdivision** (umbrella P8)
    - `test_ramp_subdivision` with `build_settings(20)`, over `box_themes`, n 2–12, elevation on and verticality `moderate`/`dramatic`, through `plan_to_spec`.
    - Assert that every value in `ramp_rises(ter)` is ≤ 2.51.
    - Pin an `@example` with a corridor whose total rise exceeds 2.5 u, and assert that precondition inside the test.
    - **Validates: Requirements 4.2, 4.6, 1.5, 1.6**
  - [ ] 11.3 Write the property test that locks never touch geometry
    - **Property 12: Locks never touch geometry** (umbrella P5, locks)
    - `test_locks_do_not_touch_geometry` with `build_settings(15)`, over `box_themes`, n 3–12 and locks 1–5, compared with locks 0 for the same plan and seed.
    - Assert that TER and ZON are byte-identical.
    - **Validates: Requirements 4.3, 1.5, 1.6**
  - [ ] 11.4 Write the property test for seed determinism
    - **Property 13: Seed determinism** (umbrella P9, no map artifacts)
    - `test_seed_determinism` with `build_settings(15)`, over `spec_themes`, n 2–12, locks 0–5 and elevation.
    - Run two `plan_to_spec` + `build_raw` passes into two `fresh_dir()`s. Assert equal Zone_Spec dicts and byte-identical TER and ZON.
    - **Validates: Requirements 4.4, 1.5, 1.6**
  - [ ] 11.5 Write the property test for advisory clearing
    - **Property 14: Advisory clearing leaves the TER unchanged** (umbrella P5, advisory clearing)
    - `test_advisory_clearing` with `build_settings(15)`, over `box_themes`, n 3–12, locks 1–5 and `semantic_inputs`.
    - Assert that the TER of `spec` is byte-identical to the TER of `clear_advisory(spec)`.
    - **Validates: Requirements 4.5, 1.5, 1.6**

- [ ] 12. Pipeline property module (`tests/test_properties_pipeline.py`)
  - [ ] 12.1 Write the property test that returned builds passed the gate
    - **Property 15: Returned builds passed the gate** (umbrella P2)
    - `test_returned_build_is_validated`: slow, `build_settings(15)`, `max_attempts` 1–8, `rng=st.randoms(use_true_random=False)`, a spy `spec_factory` and `failure_log=None`.
    - Assert that the result is validated, that `1 <= calls <= max_attempts`, and that the returned seed equals the last seed the factory received.
    - `GenerationFailed` → `assume(False)`.
    - **Validates: Requirements 5.1, 1.5, 1.6**
  - [ ] 12.2 Write the property test that forced failures are reported
    - **Property 16: Forced failures are reported, never swapped** (umbrella P2, pinned + exhaustion)
    - `test_forced_failure_reported`: slow, `build_settings(15)`. The factory builds a dungeon (n 2–4) plus one isolated room, keyed on the seed.
    - Pinned case: expect `GenerationFailed(pinned=True)` with `attempts == 1` and `failures[0].seed == seed`.
    - Unpinned case: `max_attempts` 1–8 and `timeout_s=1e9`; expect `pinned=False`, `timed_out=False` and `attempts == max_attempts`.
    - **Validates: Requirements 5.2, 5.6, 1.5, 1.6**
  - [ ] 12.3 Write the property test that fresh seeds vary
    - **Property 17: Fresh seeds vary** (umbrella P10)
    - `test_fresh_seeds_vary`: slow, `build_settings(10)`. Make k ∈ 3–10 unpinned calls on a 2-room dungeon with `rng` omitted, using a spy to record seeds.
    - Assert that every seed is in 0–2,147,483,647 and that the seeds are not all equal.
    - **Validates: Requirements 5.3, 1.5, 1.6**
  - [ ] 12.4 Write the no-API default selection example test
    - umbrella P16 (example)
    - `test_no_api_default_selection` with `no_api_keys` + `no_network`.
    - Assert `get_planner().name == "rule"`, that the active texture provider is procedural, and that `attempts == []`.
    - **Validates: Requirements 5.4, 1.6**
  - [ ] 12.5 Write the no-API prompt and CLI example test
    - umbrella P16 (example, slow)
    - `test_no_api_prompt_and_cli` with `no_api_keys` + `no_network`.
    - Server path: `TestClient(server.app.app)` with `OUTPUT_DIR`/`FAILURE_LOG` → `tmp_path`. POST a prompt, then GET `glb_url`.
    - CLI path: `main.main(["generate", "p16", "--rooms", "5", "--output", str(tmp_path)])`.
    - Assert that both produce an Accepted_Build and that `attempts == []`.
    - **Validates: Requirements 5.5, 1.6**

- [ ] 13. Root-cause fixes for counterexamples (conditional)
  - [ ] 13.1 Fix any counterexample at its root
    - Only applies if a Property_Suite test fails, during tasks 9–12 or the thorough run in 16.3. Otherwise, mark this "not triggered" here. Don't fix anything ahead of time.
    - When a property fails:
      1. Stop and record the counterexample here.
      2. Pin it as `@example(...).via("discovered failure")` on the same test.
      3. Fix it at the root in the generator, following the design's Root-cause fix policy table. Known suspects: P6 `sink` with elevation off; the P6 relax midpoint/exit; the P4 key-room fallback. Never narrow the property or its strategy.
    - A PFS CRC collision or sentinel clash is a format limit: ask the user.
    - If the fix changes layout or geometry for any seed, record the affected seeds and flag the 3D pass (task 18.2). The pass covers the dungeon sections of `docs/ACCEPTANCE.md` on those seeds plus 1955208177, 1516796975 and 481893615.
    - _Requirements: 1.7, 3.3, 3.6, 3.7_

- [ ] 14. Residue guards
  - [ ] 14.1 Extend `tests/test_hygiene.py` with the residue guards
    - Add to the module created in 4.1. Static checks over tracked `*.py` files, excluding this module. Build the forbidden tokens by string concatenation so the module doesn't match itself. Check that:
      - `generators/field/{cave,features,mesh,sdf}.py` don't exist, no source imports them (absolute or relative, including `from .sdf`), and no `fbm_field`, `_build_organic` or `_CAVE_THEMES` token remains
      - `noise.py` still defines `_value_noise_3d` and has no `sdf` import
      - `ai.schema.VALID_THEMES`, `server.app.VALID_THEMES`, the `main.py` `--theme` choices and the `web/index.html` theme `<option>` values all equal `{"dungeon", "city", "outdoor"}` as sets
      - `LayoutGenerator`'s material and light tables have no `"cave"` key
      - there's no `import skimage` / `from skimage`, `fast_simplification` or `simplify_quadric_decimation`
      - there's no `import flask` / `from flask`, no `viewer.` import and no `args.preview`, and `viewer/` doesn't exist
      - `tests/test_cave.py` doesn't exist
      - `requirements.txt` has no `scikit-image`, `fast-simplification` or `flask` line and pins `hypothesis==`
    - _Requirements: 1.1, 6.1, 6.2, 6.4, 6.10, 7.1, 7.2, 8.1, 8.2_

- [ ] 15. Checkpoint: Property_Suite complete
  - Run `python -m pytest tests/ -q`. The suite must be green with the Property_Suite included and no unknown-marker warning. Commit each property module separately. Ask the user if questions arise.

- [ ] 16. Measure the suite budget and run the thorough profile
  - [ ] 16.1 Check the Default_Run time budget
    - Run `python -m pytest tests/ -q` 3 times in a row, deleting `.hypothesis/` before each run. Record the median here against the 1.2 baseline. It must be ≤ baseline + 60 s.
    - If it's over, apply the design's budget levers in order: lower build budgets toward 10; cap P13 `bulk_n` at 500 and keep the 2000-entry case as an `@example`; weight outdoor in P9. Re-measure after each lever.
    - _Requirements: 1.4, 1.5_
  - [ ] 16.2 Verify derandomization, budgets and docstrings
    - Run the Default_Run twice with `--hypothesis-show-statistics` and record that the example counts per property test match.
    - Confirm that every Property_Suite test has a Property_Docstring and runs ≥ 5× the examples under `--hypothesis-profile=thorough` (via `scaled`). Confirm that every build-level test has `slow`, `deadline=None` and a budget of 10–25.
    - _Requirements: 1.3, 1.5, 1.6, 1.9_
  - [ ] 16.3 Run the Thorough_Profile once and record it
    - Run `python -m pytest tests/ -q --hypothesis-profile=thorough`. Record the result, the duration and the commit hash here.
    - Any counterexample goes through task 13.1, after which this run is repeated.
    - _Requirements: 1.3, Exit criteria_

- [ ] 17. Process items (agent configuration and steering)
  - [ ] 17.1 Resolve the uncommitted agent config and the stray backups
    - Inspect the uncommitted `.kiro/agents/orchestrator.json` change. Commit it if it's intended, discard it otherwise, and record which. Delete the gitignored `.kiro/agents/*.json.bak` files.
    - _Requirements: Delivery and process (agent re-pointing)_
  - [ ] 17.2 Re-point the agents to spec task lists
    - In `orchestrator.json`, `task-author.json`, `task-worker.json`, `task-reviewer.json` and `task-readiness.json`, move descriptions, prompts, welcome text and resources from `tasks/<id>.md` / `tasks/_TEMPLATE.md` / `tasks/README.md` to `.kiro/specs/<feature>/tasks.md`.
    - Add `.kiro/specs/**` to the orchestrator's `fs_write` allow-list. In `task-author`, change `tasks/**` → `.kiro/specs/**`.
    - Keep the worker deny list (`ROADMAP.md`, `README.md`, `tasks/README.md`). Keep the single-writer rule and the "eyeball it in 3D" bar word for word.
    - _Requirements: Delivery and process (agent re-pointing)_
  - [ ] 17.3 Update the steering
    - In `.kiro/steering/project.md`, rewrite "Task tracking" and "Running a task" so that `.kiro/specs/<feature>/tasks.md` is the unit of work for new work, and `tasks/` is kept as history.
    - _Requirements: Delivery and process (steering)_

- [ ] 18. Exit checks and hand-off
  - [ ] 18.1 Run the final suite and record the agent end-to-end run
    - Run `python -m pytest tests/ -q` on the branch head. Record that it's green, plus the commit count and head hash.
    - Record which task in this file the re-pointed agents (17.2) ran end to end. If none has yet, run one remaining task through the orchestrator and record it.
    - _Requirements: Exit criteria_
  - [ ] 18.2 Record the human pass hand-off (performed by the user)
    - Write the human checklist here and mark it PENDING-HUMAN:
      - (a) Smoke the Web_App on :5173 and on :8000 after the CORS change: generate one zone and load it.
      - (b) Only if 13.1 changed layout or geometry: walk the dungeon sections of `docs/ACCEPTANCE.md` on the affected seeds plus 1955208177, 1516796975 and 481893615.
    - State that nothing in M0 has been verified in the live 3D viewer by the agent.
    - _Requirements: 9.5, Exit criteria_
  - [ ] 18.3 Write the integration note (don't apply it)
    - In the final report, give the integrator:
      - the Done-table row, the "Pick up here" line, the commit hash and count
      - the `tasks/README.md` reconciliation (5 task files missing from the index; the `content-layer-dungeon` status mismatch)
      - the ROADMAP correction (no `ZoneSpec.districts` placeholder exists)
      - which task files to mark as absorbed, per the umbrella "Scope of open task files" table: `tasks/cave-backend-refactor.md` absorbed by M0; `tasks/cave-cavify-dungeon.md` → umbrella M5 (natural style)
      - the cave removal: drop the README "organic caves" feature line; mark the ROADMAP cave items (the Known issue, the organic phase row, the cave rebuild design note) as "cave pipeline removed"; note that mine prompts now yield `dungeon` + `mine_delve`
      - retirement of `.kiro/specs/content-layer-districts`
      - the secondary findings: `_assign_elevation` overwrites semantic `sink` when elevation is on (left for the content-layer follow-up); procedural texture seeds use salted `hash()`; the shared env runs fastapi/starlette versions other than the pins
    - _Requirements: Delivery and process (integration step)_

## Notes

- No task is optional. The property tests are the M0 deliverable, so none carry `*`.
- Task 4 (outdoor baseline) must be committed before any task-5 deletion. 5.2 and 5.3 land in one commit so the suite stays green.
- 10.3 and the 4.1 capture snippet are one-off scripts. Don't commit them. Their outputs (the pinned input, the baseline hashes) are what gets committed.
- 13.1 is conditional. Leave it unchecked with "not triggered" if no property fails. A geometry-changing fix makes 18.2(b) mandatory.
- 18.2 is carried out by the user. The agent only records the checklist and its status.
- Single-writer: only this file is updated during the work. `ROADMAP.md`, `README.md` and `tasks/README.md` changes go in the 18.3 note.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["2.1", "2.2"] },
    { "id": 3, "tasks": ["2.3", "2.4", "2.5"] },
    { "id": 4, "tasks": ["4.1", "7.1"] },
    { "id": 5, "tasks": ["5.1", "7.2"] },
    { "id": 6, "tasks": ["5.2", "7.3"] },
    { "id": 7, "tasks": ["5.3"] },
    { "id": 8, "tasks": ["5.4", "5.5", "6.1", "9.1", "10.1", "11.1", "12.1"] },
    { "id": 9, "tasks": ["6.2", "9.2", "10.2", "11.2", "12.2"] },
    { "id": 10, "tasks": ["9.3", "10.3", "11.3", "12.3"] },
    { "id": 11, "tasks": ["10.4", "11.4", "12.4"] },
    { "id": 12, "tasks": ["10.5", "11.5", "12.5"] },
    { "id": 13, "tasks": ["10.6", "14.1"] },
    { "id": 14, "tasks": ["10.7"] },
    { "id": 15, "tasks": ["10.8"] },
    { "id": 16, "tasks": ["10.9"] },
    { "id": 17, "tasks": ["13.1"] },
    { "id": 18, "tasks": ["16.1", "17.1"] },
    { "id": 19, "tasks": ["16.2", "17.2"] },
    { "id": 20, "tasks": ["16.3", "17.3"] },
    { "id": 21, "tasks": ["18.1"] },
    { "id": 22, "tasks": ["18.2", "18.3"] }
  ]
}
```
