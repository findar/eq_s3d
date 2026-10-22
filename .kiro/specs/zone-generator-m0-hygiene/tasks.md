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
  - [x] 2.3 Add `tests/conftest.py`
    - When the module is imported, register the `default` profile (`max_examples=100, derandomize=True, database=None, deadline=200`) and the `thorough` profile (`max_examples=500, derandomize=False, deadline=None`, default database). Then call `load_profile("default")`.
    - Add a `no_api_keys` fixture. It deletes `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `STABILITY_API_KEY`, `EQ_S3D_PLANNER` and `EQ_S3D_TEXTURE_PROVIDER`, then calls `ai.planner.set_planner(None)` and `generators.textures.factory.set_provider(None)`.
    - Add a `no_network` fixture. It patches `socket.socket.connect`, `connect_ex`, `bind` and `socket.getaddrinfo` so that loopback and `AF_UNIX` pass through, and every other target is recorded in `attempts` and raises `OSError`.
    - _Requirements: 1.3, 1.9, 5.4, 5.5, 8.3, 8.4_
    - **Done.** Added `tests/conftest.py`. Registers the `default` and `thorough`
      Hypothesis profiles at import (before the Hypothesis plugin's profile
      selection), then `load_profile("default")`. Added the `no_api_keys` and
      `no_network` fixtures per the design.
    - **API verification:** `ai.planner.set_planner(planner)` and
      `generators.textures.factory.set_provider(provider)` both exist with the
      documented `None -> restore auto-select` behaviour (read in the worktree;
      names match the design, no deviation). `get_planner`/`get_provider` honour
      `EQ_S3D_PLANNER` / `EQ_S3D_TEXTURE_PROVIDER` env overrides, so `no_api_keys`
      deletes those two plus the three key vars and resets the forced globals.
    - **`no_network` detail:** `attempts` is the yielded list (tests assert
      `attempts == []`). Loopback classification covers `127.0.0.0/8`, `::1`,
      the `localhost`/`::1` host strings, and IPv4-mapped loopback
      (`::ffff:127.*`); AF_UNIX (str/bytes address) and unrecognised address
      shapes pass through. `getaddrinfo(None, ...)` (used for passive binds)
      passes through. Teardown is handled by `monkeypatch` (fixtures restore the
      real socket attrs automatically).
    - **Verification:** `python -m pytest tests/ -q` green (197 passed, no
      unknown-marker warning, clean collection). Fixture behaviour smoke-tested
      in a throwaway test (deleted): `no_api_keys` -> rule planner + procedural
      provider; `no_network` passes a `127.0.0.1` bind, blocks a foreign
      `connect` and a foreign `getaddrinfo` with `OSError` and records each.
      Staged `tests/conftest.py` only (siblings' `strategies.py` / `pbt_helpers.py`
      left untouched and unstaged).
    - **Commit:** `cc6e34ebd5f41915d8504dab98eaedc913910fc9`
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
  - [x] 2.5 Add `tests/pbt_helpers.py`
    - Implement `scaled`, `build_settings`, `fresh_dir`, `build_raw`, `room_graph`, `solvable_walk`, `run_for`, `upward_faces`, `ramp_rises`, `opening_floor_z`, `clear_advisory`, `f32` and `ref_crc` per the design Helpers table.
    - `build_raw` must compare the TER and ZON read back from the `.eqg`, never the `.eqg` bytes. `run_for` must call the production `LayoutGenerator._elevation_run`. `ref_crc` must not use `core.pfs`'s table.
    - `build_settings(n)` asserts `10 <= n <= 25`.
    - _Requirements: 1.3, 1.5, 2.2, 2.3, 3.2, 3.3, 3.4, 4.2, 4.5_
    - **Done.** Added `tests/pbt_helpers.py` with all 13 helpers. Verified against
      the real code: `ZoneBuilder(spec).build(output_dir=, write_glb=False)` →
      `BuildResult.eqg_path`; archive members are `ter_<name>.ter` and `<name>.zon`
      (confirmed in `core/eqg.EqgZone.write` / `builder.ZoneBuilder.build`). TER
      read via `core.ter.TerFile`; `PfsArchive.from_file`/`.get` are
      case-insensitive. `run_for` calls the production
      `LayoutGenerator._elevation_run` (sets `size_multiplier =
      ai.expand._SIZE_SCALE[size]`, then `_apply_room_scale(room_count)`).
      `ref_crc` is a standalone MSB-first bitwise CRC (poly 0x04C11DB7, init 0,
      no final XOR, over name+NUL), independent of `core.pfs`'s table —
      cross-checked equal to `core.pfs._filename_crc32` for a sample set
      including `"gukbottom.ter"`, `"Ab"`, `"aB"`, empty and 64-char names.
      Module imports cleanly (`python -c "import tests.pbt_helpers"` from the
      worktree root) and all helpers smoke-tested against a real seed-7 dungeon
      build (TER read-back, 108 upward faces, max ramp rise 2.47, solvable walk
      visits all rooms, `clear_advisory` resets roles/gates while keeping
      `dungeon_theme`, `opening_floor_z` finds the corridor-opening floor).
    - **Deviations (noted, vs the design Helpers table):**
      1. `run_for(spec, theme, room_count, size, a, b)` — the design lists
         `run_for(spec, theme, room_count, size)`, but the production
         `_elevation_run(a, b)` needs the two `RoomSpec` endpoints to compute a
         per-corridor run, so `a`/`b` are accepted explicitly. `spec` is kept for
         parity (currently unused by the run computation). No re-implementation:
         it still calls the production function.
      2. `upward_faces`/`ramp_rises`/`opening_floor_z` accept either a `TerFile`
         or raw TER bytes (convenience; callers may hold either), via a small
         `_ter()` adapter.
      3. `no_network` is intentionally NOT in this module — it is a pytest
         fixture owned by `tests/conftest.py` (task 2.3), as the prompt directed.
    - **Deliverable commit:** `1091c8e` (adds `tests/pbt_helpers.py`; tracker
      line recorded in a follow-up commit).

- [x] 3. Checkpoint: harness in place
  - Run `python -m pytest tests/ -q`. It must be green with no `PytestUnknownMarkWarning`. Commit the harness. Ask the user if questions arise.
  - **Done.** Suite green: **197 passed in 87.50s**, exit 0. No
    `PytestUnknownMarkWarning` — confirmed by re-running `--collect-only` with
    `-W error::pytest.PytestUnknownMarkWarning`, which collected all 197 tests
    cleanly (would have errored on any unknown mark). The harness code
    (`pytest.ini`, `.gitignore`, `requirements.txt`, `tests/conftest.py`,
    `tests/strategies.py`, `tests/pbt_helpers.py`) was already committed across
    tasks 2.1–2.5 (HEAD `29bc319` at checkpoint entry); the working tree was
    already clean on entry (no leftover `COMMIT_EDITMSG_TMP`, no unexpected code
    changes), so this checkpoint commit lands only the checkbox bookkeeping.
  - **Commit:** `171f3d2` ("M0 checkpoint 3: harness in place (197 passed, no unknown-mark warning)") — tracker bookkeeping only.

- [ ] 4. Capture the outdoor TER baseline before any deletion
  - [ ] 4.1 Capture the fork-point hashes and add the baseline test
    - On the unchanged fork-point code, in the worktree venv, run a one-off snippet (don't commit it). For each seed in `(7, 1955208177, 2147483647)`, build `LayoutGenerator("outdoor", seed=s).generate(f"ob{s}", room_count=6)` through `build_raw` and print `sha256(ter_bytes)`.
    - Add `tests/test_hygiene.py` with `OUTDOOR_BASELINE_SEEDS` and `test_outdoor_ter_matches_fork_point`, parametrised over the three seeds, asserting each hash against its literal. Add a comment naming the fork-point commit hash and the capture procedure. A later mismatch is a bug in the deletion, never a reason to recapture.
    - Commit this first, before any task-5 deletion.
    - _Requirements: 6.3_

- [ ] 5. Delete the cave pipeline and the `cave` theme
  - Commit one sub-task at a time and keep the suite green after each commit. Code and the tests of that code are deleted in the same commit. 5.2 and 5.3 land in one commit. `test_outdoor_ter_matches_fork_point` must pass unchanged after every commit.
  - [x] 5.1 Delete the cave pipeline code and its dependencies
    - Delete `generators/field/cave.py`, `features.py`, `mesh.py` and `sdf.py`.
    - `generators/field/noise.py`: delete `fbm_field` and `from .sdf import FieldGrid`. Keep `_value_noise_3d` and its helpers. Reword the module docstring to "terrain heightfields". Drop "caves" from the `generators/field/__init__.py` comment.
    - `generators/builder.py`: delete `_CAVE_THEMES`, the cave branch of `_build_geometry` and `_build_organic`. Reword the step-1 comment and the `'cave_rock'` mention in the material colour docstring.
    - `generators/layout.py`: delete the `"cave"` entries in the per-theme material table and light-colour table.
    - `generators/pipeline.py`: drop "cave" from the `DEFAULT_GATED_THEMES` comment and the module and `generate_validated` docstrings. The set stays `{"dungeon"}`.
    - `requirements.txt`: remove `scikit-image==0.26.0` and `fast-simplification==0.1.11`.
    - Delete `tests/test_cave.py` in the same commit.
    - If a remaining cave-theme test goes red on this commit, fold 5.2 + 5.3 into it rather than committing red.
    - _Requirements: 6.1, 6.2, 6.4, 6.10, 7.1, 7.2_
    - **Done.** Deleted `generators/field/{cave,sdf,mesh,features}.py` and
      `tests/test_cave.py` in one commit. `noise.py`: removed `fbm_field` and the
      `from .sdf import FieldGrid` import; kept `_value_noise_3d` + helpers
      (terrain still imports it) and reworded the module docstring to terrain
      heightfields; `field/__init__.py` comment no longer names caves.
      `builder.py`: removed `_CAVE_THEMES`, the cave branch of `_build_geometry`
      and `_build_organic`; reworded the step-1 comment and the material-colour
      docstring (dropped `'cave_rock'`). `layout.py`: dropped the `"cave"` entries
      from the material palette and the light-colour table. `pipeline.py`: dropped
      "cave" from the `DEFAULT_GATED_THEMES` comment and the module /
      `generate_validated` docstrings; the gated set value is unchanged
      (`{"dungeon"}`). `requirements.txt`: removed `scikit-image==0.26.0` and
      `fast-simplification==0.1.11`. No remaining cave-theme test went red, so
      5.2 + 5.3 were NOT folded in — they stay separate as planned.
    - **Verification:** `python -m pytest tests/ -q` → **196 passed** (no
      `PytestUnknownMarkWarning`). `test_outdoor_ter_matches_fork_point` → 3
      passed, unchanged (outdoor terrain depends on value-noise, not fbm/sdf).
      `python -c "import generators.builder, generators.layout,
      generators.pipeline, generators.field.noise"` imports cleanly; `_value_noise_3d`
      still importable. `git grep` confirms zero remaining references to the
      deleted field modules / `fbm_field` / `FieldGrid` / `_CAVE_THEMES` /
      `_build_organic` and to `skimage` / `fast_simplification`. Cave-only deps
      not uninstalled from the venv (that's task 5.4); pins removed from
      `requirements.txt`.
    - **Commit:** `d1429e47fee611c966c8018d6a1b98fd3d5d6fa3` — staged only the 5.1
      fileset (`generators/field/{cave,sdf,mesh,features}.py` deletions,
      `generators/field/{noise,__init__}.py`, `generators/{builder,layout,pipeline}.py`,
      `requirements.txt`, `tests/test_cave.py`). The sibling agent's
      `tests/test_server.py` (task 7.2) was left unstaged.
  - [x] 5.2 Remove `cave` from the theme surface
    - `ai/schema.py` and `server/app.py`: `VALID_THEMES = ["dungeon", "outdoor", "city"]`.
    - `main.py`: `--theme` `choices=["dungeon", "outdoor", "city"]`.
    - `web/index.html`: drop `<option value="cave">` and change the placeholder to `e.g. a flooded temple with lots of chambers`. Then run `cd web; npx vite build`.
    - `ai/rule_planner.py::_THEME_WORDS`: remove the `cave` bucket and append its words (`cave`, `cavern`, `grotto`, `tunnel`, `underground`, `mine`) to the `dungeon` bucket. Keep `mine` in `_ARCHETYPE_WORDS["mine_delve"]`, the dict order and the strict-`>` tie rule. Update the module docstring example per the design.
    - `generators/zone_spec.py::ZoneSpec.from_dict`: map theme `cave` to `dungeon`. No other theme is remapped.
    - `server/app.py` controls path: keep the existing 400 before the factory is built, and change the detail to list the valid themes per the design.
    - Commit together with 5.3.
    - _Requirements: 6.4, 6.5, 6.6, 6.7, 6.8_
    - **Done.** All verified against the real code first:
      - `VALID_THEMES` was `["dungeon", "outdoor", "cave", "city"]` in BOTH
        `ai/schema.py` and `server/app.py`; both now `["dungeon", "outdoor", "city"]`.
        Confirmed at runtime: `ai.schema.VALID_THEMES == server.app.VALID_THEMES ==
        ['dungeon', 'outdoor', 'city']`.
      - `main.py` `--theme` choices updated; argparse exits 2 on `--theme cave`.
      - `web/index.html`: cave `<option>` dropped, placeholder is now
        `e.g. a flooded temple with lots of chambers`. Frontend bundle rebuilt
        successfully; the rebuilt `web/dist/` carries the new placeholder and only
        dungeon/outdoor/city options.
      - `ai/rule_planner.py::_THEME_WORDS`: cave bucket removed, its six words
        appended to the `dungeon` bucket. Dict order is now `outdoor, city,
        dungeon` (the cave key simply dropped; relative order of the surviving
        keys preserved). `mine` kept in `_ARCHETYPE_WORDS["mine_delve"]`; the
        `_match_theme` strict-`>` tie rule is untouched. Module docstring example
        reworded to "a big flooded cavern … large dungeon with a water region".
      - `generators/zone_spec.py::ZoneSpec.from_dict`: adds `theme = "dungeon" if
        theme == "cave"` before constructing the spec; only `cave` remapped.
      - `server/app.py` controls 400 detail now
        `f"Unknown theme: {req.theme!r}; valid themes: {', '.join(VALID_THEMES)}"`,
        still raised before the factory is built.
      - No deviations from the design for 5.2. The `web/dist/` build artifacts are
        gitignored in this repo, so they were rebuilt-and-verified but NOT staged
        (the design's "stage the built assets" doesn't apply when dist is ignored).
    - **Deliverable commit (shared with 5.3):** `f5c6008`.
  - [x] 5.3 Retarget the cave-theme tests
    - `tests/test_pipeline.py`: delete the `assert "cave" not in DEFAULT_GATED_THEMES` line (~182).
    - `tests/test_traversability.py`: docstring "Outdoor/cave" → "Outdoor".
    - `tests/test_generators.py::test_rule_planner_open_is_zero`: keep the cave prompt and add `assert plan.theme == "dungeon"`.
    - `tests/test_planner.py`: update the five cave-theme tests per the design (`test_roundtrip_dict` and the two `TestExpand` tests use `outdoor`/`dungeon`; `test_from_dict_ignores_unknown` asserts `cave` → `dungeon`; `test_detects_cave` becomes `test_cave_words_mean_dungeon`, one prompt per Cave_Word). Add `test_zonespec_cave_theme_normalised`.
    - `tests/test_server.py`: add a controls POST with `theme="cave"` → 400, detail names all three Defined_Themes, `OUTPUT_DIR` stays empty.
    - `tests/test_pipeline.py`: add a `TestCliArgs` class with `main.main(["generate", "x", "--theme", "cave", "--output", out])` → `SystemExit(2)` and `out` not created. Add a slow example: unpinned `generate_validated` on `plan_to_spec(RulePlanner().plan("a dark underground cavern with many tunnels"), seed=s)` returns a validated build with theme `dungeon`.
    - _Requirements: 6.5, 6.6, 6.7, 6.8, 6.9_
    - **Done.** All retargets verified against the real test files first:
      - `test_pipeline.py`: removed the `assert "cave" not in DEFAULT_GATED_THEMES`
        line from `TestGating::test_dungeon_is_gated_by_default`. Added
        `TestCliArgs::test_cave_theme_rejected_by_argparse`
        (`--theme cave` → `SystemExit(2)`, output dir not created) and a slow
        `test_cave_prompt_builds_validated_dungeon`
        (`RulePlanner().plan("a dark underground cavern with many tunnels")` plans
        `dungeon`, then `generate_validated` returns a validated build whose
        `vb.spec.theme == "dungeon"`).
      - `test_traversability.py`: module docstring reworded — the "Outdoor/cave …
        organic cave" clause now reads "Outdoor … heightfield terrain" (the cave
        mesh no longer exists, so the stale half-sentence was dropped along with
        the literal "cave").
      - `test_generators.py::test_rule_planner_open_is_zero`: kept the cave prompt,
        added `assert p.theme == "dungeon"`.
      - `test_planner.py`: `test_roundtrip_dict` → `outdoor`; `test_plan_to_spec_basic`
        → `outdoor`; `test_regions_added` → `dungeon`; `test_from_dict_ignores_unknown`
        asserts `cave` → `dungeon`; `test_detects_cave` replaced by parametrised
        `test_cave_words_mean_dungeon` (one prompt per Cave_Word: cave, cavern,
        grotto, underground, tunnel — each → `dungeon`); new
        `test_zonespec_cave_theme_normalised` (ZoneSpec dict with `theme="cave"` →
        `dungeon`).
      - `test_server.py`: appended `test_controls_cave_theme_rejected` (controls
        POST `theme="cave"` → 400, detail names dungeon/outdoor/city, `OUTPUT_DIR`
        stays empty) — added after the task-7.2 example tests, which were left
        undisturbed. `tests/strategies.py` NOT edited.
    - **Deviation (noted):** the task text spells the CLI test as
      `main.main(["generate", "x", "--theme", "cave", "--output", out])`, but on
      this branch `main.main()` still reads `sys.argv` (the `main(argv=None)`
      refactor is task 6.1). To avoid pre-empting 6.1's signature change, the test
      patches `sys.argv` and calls `main.main()` with no args. The asserted
      behaviour (argparse exit 2 on `--theme cave`, no output dir) is identical;
      task 6.1 can switch it to the positional-argv form once `main(argv=None)` lands.
    - **Verification:** `python -m pytest tests/ -q` → **204 passed**, exit 0, no
      `PytestUnknownMarkWarning`. `test_outdoor_ter_matches_fork_point` passes
      unchanged (3 passed). Frontend bundle rebuilds cleanly.
    - **Deliverable commit (shared with 5.2):** `f5c6008`.
  - [x] 5.4 Run the suite without the cave-only dependencies installed
    - In the worktree venv, run `pip uninstall -y fast-simplification scikit-image`, then `python -m pytest tests/ -q`. Record the result here: zero failures, zero errors.
    - _Requirements: 7.3_
    - **Done.** In the isolated `-Venv` worktree (`..\eq_s3d-worktrees\agent-m0-hygiene\.venv`),
      uninstalled both cave-only packages: `fast_simplification-0.1.11` and
      `scikit-image-0.26.0` (confirmed "Successfully uninstalled" for each). This makes
      the installed env match the pinned `requirements.txt` (task 5.1 already removed
      both pins — not re-added, not reinstalled).
    - **Suite result with both packages uninstalled:** `python -m pytest tests/ -q` →
      **209 passed, zero failures, zero errors** (39.24 s). No `skimage` or
      `fast_simplification` import error — the cave-pipeline removal in 5.1–5.3 left
      no residual dependency on the cave-only packages. (Two pre-existing warnings
      only: a starlette `anyio.abc.BlockingPortal` deprecation and a runpy
      `server.app` warning — both unrelated to the cave removal.)
    - No code change in this task — verification + tracker note only.
  - [x] 5.5 Update the docs and steering for the cave removal
    - `docs/ACCEPTANCE.md`: remove `cave` from the theme list, retire C "Single connected cave" and section D (pending umbrella M5), drop the cave sweep snippet, and change "outdoor/cave" to "outdoor".
    - `.kiro/steering/lessons-learned.md`: rewrite the cave entries to "cave pipeline removed in M0; cave = dungeon archetype (M3), natural style (M5)". Keep the walkable-floor, no-decimation and voxel-fidelity facts as M5 guidance.
    - _Requirements: 6.1, 6.10_
    - **Done.** Docs + steering only; no code touched. Verified both files against
      their real contents before editing.
      - `docs/ACCEPTANCE.md`: section A "Generates without error" theme list is now
        `dungeon`, `outdoor`, `city` (dropped `cave`). Section B: the three
        "outdoor/cave" / "Outdoor/cave" occurrences (the gate sentence and the two
        ✅-auto notes) → "outdoor" / "Outdoor". Section C "Single connected cave"
        item prefixed *Retired: pending the natural geometry style (umbrella M5).*
        Section D "Caves specifically" gained the same retirement lead line noting
        the cave pipeline was removed in M0; its checklist items are kept as history
        (not deleted). The quick seed-sweep snippet now builds `theme='dungeon'`
        (same pattern, one-line change).
      - `.kiro/steering/lessons-learned.md`: added a lead blockquote under
        "Geometry / fields" and under "Performance" stating the cave pipeline was
        removed in M0 and cave returns as a dungeon archetype (umbrella M3) and the
        natural geometry style (umbrella M5); the cave entries are kept VERBATIM as
        M5 guidance (never decimate walkable floors; voxel ≈ 12 u matches Classic–PoP
        edge length; clamp floors one-sided and re-intersect with the floor plane
        after blends; the walkable-floor shaping facts). No hard-won fact deleted.
    - **Commit:** `d6d9d5aa4a49d4a1fff1c5fcaebe6181cc07aaeb` — staged only
      `docs/ACCEPTANCE.md`, `.kiro/steering/lessons-learned.md` and this spec's
      `tasks.md`. (Note: that commit object carries a stale subject line from a
      concurrent sibling commit because git fell back to `.git/COMMIT_EDITMSG`;
      the committed *content* is exactly the 5.5 fileset above — verified by
      `git show --stat`: 3 files, docs + steering + this tracker, no code.)

- [ ] 6. Remove the legacy viewer
  - [x] 6.1 Delete the viewer and its CLI entry points
    - Delete `viewer/` (`serve.py`, `index.html`).
    - In `main.py`, delete `cmd_preview`, `_launch_preview`, the `preview` subparser, the `--preview` option and the `if args.preview:` block. Rewrite the module docstring so it lists only `generate`. Change the entry point to `def main(argv: list[str] | None = None)` with `parser.parse_args(argv)`.
    - Remove `flask==3.1.0` from `requirements.txt` and rename the section comment to "API backend".
    - Drop `preview=False` from `TestCliEscapeHatch._args` in `tests/test_pipeline.py`.
    - Confirm that `README.md` and `docs/` contain no preview launch instruction.
    - _Requirements: 8.1, 8.2, 8.6_
    - **Done.** Deleted `viewer/` via `git rm -r` (both `serve.py` and
      `index.html`). `main.py`: removed `cmd_preview`, `_launch_preview`, the
      `preview` subparser, the `--preview` option and the `if args.preview:`
      block; docstring now lists only `generate`; entry point is
      `def main(argv: list[str] | None = None)` with `parser.parse_args(argv)`
      (the only CLI signature change). `requirements.txt`: dropped `flask==3.1.0`,
      section comment renamed `# Web viewer / API backend` → `# API backend`.
      `tests/test_pipeline.py`: dropped `preview=False` from
      `TestCliEscapeHatch._args`; switched the existing `TestCliArgs` cave-theme
      test to drive `main.main([...])` positionally (behaviour unchanged — still
      `SystemExit(2)`, output dir not created), removing the `sys.argv` monkeypatch
      `_cli` helper. (The NEW preview CLI tests are task 6.2 — not added here.)
    - **Verification (worktree `-Venv`):**
      - `python -m pytest tests/ -q` → **205 passed**, 2 warnings (pre-existing
        starlette `BlockingPortal` deprecation + a runpy `server.app` warning),
        no `PytestUnknownMarkWarning`. Exit 0.
      - `python -c "import main; main.main(['generate','smoke6_1','--rooms','3','--output','output'])"`
        → built a validated 3-room dungeon through the argv path end to end
        (seed 209879124, 1 attempt); smoke artifacts cleaned up afterward.
      - `python main.py --help` lists only `{generate}` (no preview).
      - `git grep -in preview -- main.py viewer` → nothing (viewer gone,
        `main.py` clean).
    - **README/docs preview scan (flag, don't fix):** `docs/*.md` has **no**
      preview mentions. `README.md` mentions "preview" at lines 6, 47, 111, but
      all three describe the `.glb` as a *browser preview artifact*, not a launch
      instruction for the deleted viewer/CLI — and README is single-writer
      integration state, so left untouched. No stray launch instruction found.
    - **Commit (staged `main.py`, `requirements.txt`, `tests/test_pipeline.py`,
      deleted `viewer/`):** `5eb913fea13f1afb351a155215940317753df055`.
  - [x] 6.2 Add CLI tests for the removed preview paths
    - Add these to the `TestCliArgs` class in `tests/test_pipeline.py` (created in 5.3), using `no_network`:
      - `main.main(["preview", "x"])` exits with code 2 and stderr names `preview` as an invalid choice.
      - `main.main(["generate", "x", "--preview", "--output", out])` exits with code 2 and stderr names `--preview` as unrecognized.
      - In both cases no non-loopback bind and no listener is recorded, and `out` doesn't exist afterwards.
      - Neither `--help` nor `generate --help` output mentions "preview".
    - _Requirements: 8.3, 8.4, 8.5_
    - **Done.** Added three methods to `TestCliArgs` in `tests/test_pipeline.py`:
      `test_preview_subcommand_rejected` (argparse `invalid choice: 'preview'`,
      exit 2, `no_network == []`), `test_preview_option_rejected`
      (`unrecognized arguments: --preview`, exit 2, `no_network == []`, output
      dir absent afterwards), and `test_help_does_not_mention_preview`
      (`--help` and `generate --help` both exit 0 and their stdout has no
      "preview"). Verified the real argparse wording against `main.main(argv)`
      before writing the asserts. The `no_network` fixture yields its `attempts`
      list, which records every non-loopback connect/bind; `attempts == []`
      proves no foreign listener opened on either rejected path. Full suite
      `python -m pytest tests/ -q` → **216 passed** (2 pre-existing
      deprecation/runtime warnings, unrelated).

- [ ] 7. Bind the server to loopback and restrict CORS
  - [x] 7.1 Implement the loopback bind and `LocalCORSMiddleware` in `server/app.py`
    - Add `HOST = "127.0.0.1"`, `PORT = 8000` and the `WEB_APP_ORIGINS` tuple.
    - Subclass `CORSMiddleware` and override `preflight_response` so that every `access-control-allow-*` header is removed when the origin is disallowed. Register the subclass with an explicit `allow_origins`, `allow_methods=["GET", "POST"]` and `allow_headers=["Content-Type"]`, and without credentials or expose headers.
    - Change `__main__` to `uvicorn.run("server.app:app", host=HOST, port=PORT, reload=False)`.
    - If 1.1 found that the override point differs at the pinned starlette version, use the design's fallback instead: a pure ASGI wrapper that strips the headers.
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.6, 9.7_
    - **Done.** Commit `aca7020ecc32aaf9a16fe19a7492d10ec3c70f07` (only `server/app.py` staged). Implemented the design shape verbatim — no ASGI fallback needed.
    - **API check (worktree venv, starlette 0.41.3) — for task 7.3:** `CORSMiddleware.is_allowed_origin` EXISTS with signature `(self, origin: 'str') -> 'bool'`, and `preflight_response` is `(self, request_headers: 'Headers') -> 'Response'`. The design override (`super().preflight_response(...)` + `self.is_allowed_origin(request_headers["origin"])`) works as written; no deviation. Task 7.3's foreign-origin property test can rely on `is_allowed_origin` / the four-member `WEB_APP_ORIGINS` tuple directly.
    - **Verification:** `python -c "import server.app; print(server.app.WEB_APP_ORIGINS, server.app.HOST, server.app.PORT)"` → the four origins + `127.0.0.1 8000`. `runpy.run_module("server.app", run_name="__main__")` with `uvicorn.run` patched → called as `('server.app:app', host='127.0.0.1', port=8000, reload=False)` (no real bind). TestClient smoke: allowed origin → ACAO echoed; foreign GET → no ACAO; foreign preflight → 400 with zero `access-control-allow-*`; allowed preflight → 200 + ACAO + methods `GET, POST`; no-Origin → no ACA-*. No `*` wildcard emitted anywhere. Full suite: **200 passed** in the worktree venv.
    - **Note (not my scope):** `VALID_THEMES` still lists `cave`; that's task 5.2, left untouched. `test_server.py` is task 7.2 (not yet present).
  - [x] 7.2 Add example tests in `tests/test_server.py`
    - Use `TestClient`, with `OUTPUT_DIR`/`FAILURE_LOG` monkeypatched to `tmp_path`. Every response goes through an `assert_no_wildcard` helper. Cover:
      - 9.1: `runpy.run_module("server.app", run_name="__main__")` with `uvicorn.run` captured; assert host `127.0.0.1` and port 8000, with no real bind.
      - 9.2: ACAO is echoed byte-identically for each of the four origins.
      - 9.5: with origin `http://localhost:5173`, POST `/api/generate` (pinned seed, 3 rooms) returns 200 and is validated, then GET `glb_url` and `zone_url` return 200, each with ACAO echoed.
      - 9.6: a preflight for `POST` + `content-type` returns 200 with matching ACAO and Allow-Methods/Allow-Headers.
      - 9.7: a request with no `Origin` gets no ACA-* header.
    - _Requirements: 9.1, 9.2, 9.4, 9.5, 9.6, 9.7_
    - **Done.** `tests/test_server.py` added with a module-level
      `assert_no_wildcard(resp)` helper (Req 9.4) that every response is routed
      through, plus a `client` fixture that monkeypatches `server.app.OUTPUT_DIR`
      and `server.app.FAILURE_LOG` to a `tmp_path` so no artifacts leak into the
      worktree. Tests: `test_main_binds_host_and_port` (9.1, `uvicorn.run`
      monkeypatched — no real bind), `test_health_echoes_origin` (9.2,
      parametrised over all four `WEB_APP_ORIGINS`), `test_generate_and_fetch_files`
      (9.5, pinned seed 42 + 3-room dungeon → 200/validated, then `glb_url` +
      `zone_url` → 200, ACAO echoed on each), `test_preflight_from_allowed_origin`
      (9.6, parametrised), `test_no_origin_no_cors_headers` (9.7). Property 18 /
      Req 9.3 deliberately NOT here — that's task 7.3.
    - **Verification:** `python -m pytest tests/test_server.py -q` → **11 passed**
      (2 benign warnings: starlette TestClient anyio-alias DeprecationWarning, and
      the standard runpy "found in sys.modules" RuntimeWarning for the 9.1
      re-exec — neither affects correctness). The full-suite check (`pytest tests/
      -q`) could NOT be run clean because the sibling's task-5.1 cave removal was
      mid-edit in this shared worktree: `generators/field/sdf.py` was deleted but
      `noise.py` still had `from .sdf import FieldGrid`, so `test_terrain.py`
      failed to collect. That is the sibling's in-flight partition, unrelated to
      this task; my import surface (`HOST`/`PORT`/`WEB_APP_ORIGINS`/CORS) is
      untouched by it, and my file collects and passes. Re-run the full suite once
      5.1 lands.
    - **Route / schema verification against the real `server/app.py` (no
      deviations from the task's assumed names):**
      - Routes: `GET /api/health`, `POST /api/generate`, `GET /api/zones/{filename}`.
      - Generate request body: `{prompt?, theme, rooms, elevation, seed?}` —
        pinned a seed via `seed` and requested 3 rooms via `rooms: 3` on the
        controls path (`theme: "dungeon"`).
      - Response fields: `glb_url`, `zone_url` (also `map_url`), `validated`,
        `seed`, `rooms` — all as named in the task. URLs are
        `/api/zones/{id}.glb` and `/api/zones/{id}.zone.json`.
      - Monkeypatch targets confirmed as the real module globals read at request
        time: `server.app.OUTPUT_DIR`, `server.app.FAILURE_LOG`. App object is
        `server.app.app`. Imported `WEB_APP_ORIGINS`, `HOST`, `PORT` from `server.app`.
      - Note (9.6 detail): Starlette's preflight response lists Allow-Headers as
        `Accept, Accept-Language, Content-Language, Content-Type` (safelisted set +
        our `Content-Type`); the test asserts `content-type` is present
        case-insensitively rather than exact-match, and Allow-Methods ⊇ {POST}.
    - **Commit (staged only `tests/test_server.py`):** `69700d3`.
  - [x] 7.3 Write the property test for foreign origins
    - **Property 18: Foreign origins get no CORS grant**
    - In `tests/test_server.py`, `@given(origins_outside)`: simple GET, POST and preflight responses carry no `access-control-allow-*` header and never `Access-Control-Allow-Origin: *`. Include a Property_Docstring.
    - **Validates: Requirements 9.3, 9.4**
    - **Done.** Appended `test_foreign_origins_get_no_cors` to `tests/test_server.py`
      (`@settings(max_examples=scaled(100))` + `@given(origin=origins_outside)`),
      with a local `_assert_no_cors_grant` check that reuses the 7.2 module-level
      `assert_no_wildcard` helper (no duplication). For each drawn foreign origin
      it issues (a) GET `/api/health`, (b) a preflight OPTIONS `/api/generate`
      (Access-Control-Request-Method POST + Access-Control-Request-Headers
      content-type), and (c) a simple POST `/api/generate`. The POST carries
      `theme="cave"`, which the controls path rejects 400 *before* any
      factory/build runs, so the test stays fast and writes no artifacts; the
      assertion is on the CORS headers of whatever status returns, never
      requiring 200. All three responses must carry no `access-control-allow-*`
      header and no `ACAO: *`.
    - **Fixture discipline:** the `@given` test takes NO function-scoped fixtures.
      It uses a module-scoped `_FOREIGN_CLIENT = TestClient(app_mod.app)` (avoids
      the Hypothesis function_scoped_fixture health check). No OUTPUT_DIR /
      FAILURE_LOG monkeypatch is needed because none of the three paths write
      artifacts (health touches nothing; the cave POST 400s before the factory;
      the preflight returns before any handler body). The existing 7.2 example
      tests and the 5.3 cave-controls-400 test were left untouched — this is a
      pure append.
    - **Property_Docstring:** `Feature: zone-generator-m0-hygiene, Property 18
      (umbrella P-CORS): Foreign origins get no CORS grant` + `Validates: M0 Req
      9.3, 9.4`.
    - **Verification:** `python -m pytest tests/test_server.py -q` → **13 passed**
      (12 prior + this property test over 100 examples, default profile). Full
      `python -m pytest tests/ -q` → **205 passed**, exit 0.
    - **Commit (staged only `tests/test_server.py`):** `1c218cd`.

- [x] 8. Checkpoint: removals and server change landed
  - Run `python -m pytest tests/ -q`. It must be green. Tasks 4–7 are committed separately (4.1 first; 5.2 + 5.3 together). Ask the user if questions arise.
  - **Verified:** `python -m pytest tests/ -q` GREEN — 217 passed (2 unrelated warnings: anyio `BlockingPortal` deprecation and a `runpy` RuntimeWarning; no `PytestUnknownMarkWarning`). Re-ran collection under `--co -q -W error::pytest.PytestUnknownMarkWarning`: 217 tests collected, exit 0 — proves no unknown-mark warning (the `slow` marker is registered in `pytest.ini`). Tasks 4–7 and the 9.x property-test commits are all landed; working tree clean. HEAD `b14c176`, 43 commits since fork-point `99d346a`.

- [ ] 9. Core property module (`tests/test_properties_core.py`)
  - [x] 9.1 Write the property test for the PFS archive round-trip
    - **Property 1: PFS archive round-trip** (umbrella P13)
    - `test_pfs_roundtrip` over `pfs_entries`, with a budget of `scaled(100)`.
    - Assert that `from_bytes(to_bytes(arc))` gives an equal name→bytes map with case-preserved names and no extra entries.
    - Pin `@example` for 600 bulk names of length 60 (name block ≈ 39,000 B, which is also multi-chunk).
    - If a CRC collision or a sentinel clash appears, stop and ask the user. Don't narrow the strategy.
    - **Validates: Requirements 2.1, 1.6**
    - **Done.** Created `tests/test_properties_core.py` with `test_pfs_roundtrip`
      as its first property. Verified against the real `core/pfs.py` API:
      construct `PfsArchive()`, `arc.add(name, data)` per entry, serialize with
      `arc.to_bytes()`, parse with `PfsArchive.from_bytes(...)`. The round-trip
      map is read off `parsed.files` (`{f.name: f.data}`), NOT via `arc.get()`
      (which is case-insensitive) — so case preservation is actually asserted.
      Property asserts: same key set (case-preserved), `len(parsed.files) ==
      len(entries)` (catches a dropped entry from any CRC/sentinel collapse), and
      byte-equal payloads.
    - **`@example`:** 600 distinct printable-ASCII names of length 60, built
      inline from a seeded RNG over the same alphabet `pfs_entries` uses
      (case-insensitively deduped) → name block = 4 + 600*(4+61) = **39,004 B**,
      well over the 8192-B deflate chunk, so it exercises the multi-chunk
      `_deflate_chunks`/`_inflate_chunks` path.
    - **One deviation from the literal task:** added `deadline=None` to the
      `@settings` (alongside `max_examples=scaled(100)`). The default profile sets
      `deadline=200` ms; the ~39 KB / up-to-2000-entry archives take a few hundred
      ms to serialize+parse (a cost that scales with entry count, not a
      correctness signal), so the per-example wall-clock deadline flaked. The
      strategy and the property are unchanged — only the deadline is lifted.
    - **CRC collision / sentinel clash:** NONE surfaced across the 100 generated
      examples + the pinned 39 KB example.
    - **Verification:** `python -m pytest tests/test_properties_core.py -q` →
      **1 passed** (100 examples + the @example). Full `python -m pytest tests/ -q`
      → **208 passed** (205 prior + 3; note the +3 vs the single new test reflects
      concurrent sibling landings in the shared worktree branch state at run time),
      exit 0.
    - **Commit (`tests/test_properties_core.py`):**
      `2b1dad8e79918147b63ad094be6e9d6e9ea10826`. (The 9.1 `tasks.md` note itself
      was swept into a concurrent sibling's commit `d6d9d5a` in the shared
      worktree; the hash backfill lands in a follow-up `tasks.md`-only commit.)
  - [x] 9.2 Write the property test for the PFS filename CRC
    - **Property 2: PFS filename CRC matches the reference** (umbrella P14)
    - `test_pfs_crc_matches_reference`: assert `_filename_crc32(n) == ref_crc(n)`.
    - Pin `@example`s for the two existence claims: `"gukbottom.ter"` differs from `zlib.crc32`, and `"Ab"` differs from `"aB"`. Add `event()` counts across generated names.
    - **Validates: Requirements 2.2, 1.6**
    - **Done.** Appended `test_pfs_crc_matches_reference` to
      `tests/test_properties_core.py` (9.1's `test_pfs_roundtrip` left
      untouched). Budget `@settings(max_examples=scaled(100))` over the
      `pfs_names` strategy (`tests.strategies`). Core assertion:
      `core.pfs._filename_crc32(n) == ref_crc(n)` (`tests.pbt_helpers`) for every
      generated name. **Real CRC symbol confirmed:** `core.pfs._filename_crc32`
      (`name: str -> int`) — the design/pbt_helpers docstring reference was
      accurate; used the real one. Pinned `@example`s for both existence claims:
      `"gukbottom.ter"` (asserts EQ CRC != `zlib.crc32(...) & 0xFFFFFFFF` — EQ CRC
      is NOT the reflected zlib CRC32) and `"Ab"` vs `"aB"` (asserts
      `_filename_crc32("Ab") != _filename_crc32("aB")` — case-sensitive). Added
      `event()` counts (`differs from zlib.crc32: <bool>` and `crc parity`) so the
      "differs" claims show in statistics — verified via
      `--hypothesis-show-statistics`: `differs from zlib.crc32: True` at 100% over
      100 examples. Both `@example`s pass.
    - **Verification:** `python -m pytest tests/test_properties_core.py -q` →
      **2 passed**. Full `python -m pytest tests/ -q` → **210 passed**, 2
      pre-existing warnings (starlette `BlockingPortal` deprecation, runpy
      `server.app`), no `PytestUnknownMarkWarning`. Staged only
      `tests/test_properties_core.py` for the code commit.
    - **Commit:** `4ba550e` ("M0 9.2: property test for PFS filename CRC (P14)").
  - [x] 9.3 Write the property test for the built TER/ZON round-trip
    - **Property 3: Built TER and ZON round-trip** (umbrella P15)
    - `test_ter_zon_roundtrip` with `@pytest.mark.slow` and `build_settings(20)`, over `box_themes`, n 2–12 and `semantic_inputs`.
    - Assert that `ter.to_bytes()` from `ZoneBuilder._build_geometry` equals the archived TER. Then assert field-wise equality of vertices, polygons, materials, objects, lights and regions, with floats bit-equal via `f32`.
    - **Validates: Requirements 2.3, 1.5, 1.6**
    - **Done.** Appended `test_ter_zon_roundtrip` to
      `tests/test_properties_core.py` (9.1 `test_pfs_roundtrip` and 9.2
      `test_pfs_crc_matches_reference` left untouched — pure append + an
      extended import block). `@pytest.mark.slow` + `@build_settings(20)` over
      `box_themes` (dungeon/city), `room_counts(2, 12)` and `semantic_inputs`.
      Build goes through `ai.expand.plan_to_spec(ZonePlan(...), seed=0x7E51)`
      (so `dungeon_theme`/`dungeon_race`/`elemental_tint` are realised) + the
      `build_raw` read-back; `@given` takes no `tmp_path` — the `.eqg` is written
      into `fresh_dir()`.
    - **Verified against the real code first (two findings):**
      - `ZoneBuilder._build_geometry(self, name, ter_version) -> TerFile`:
        `ZoneBuilder.build` calls it as `_build_geometry(spec.name.lower(), 2)`
        and serialises placement via `_build_zon(f"ter_{spec.name.lower()}.ter")`,
        so the re-derivation uses those exact arguments. `build_raw` archives the
        TER under `ter_<name>.ter` and the ZON under `<name>.zon`.
      - **DESIGN DEVIATION (field list):** the design/task name
        "objects, lights and regions" as *TerFile* fields, but the real
        `core.ter.TerFile` carries ONLY `vertices`, `polygons`, `materials`
        (plus `name`/`magic`/`version`). `objects`, `lights` and `regions` are
        `core.zon.ZonFile` fields — the design conflated the two binaries. The
        property's INTENT (builder geometry+placement round-trips into the
        archive; elemental tints realise ZON regions) is preserved by asserting
        the round-trip on BOTH binaries: TER bytes + field-wise
        vertices/polygons/materials, and ZON bytes + field-wise
        models/objects/regions/lights. Every float on both sides is snapped to
        IEEE-754 single precision via `f32` before comparison. Confirmed a
        sweep of semantic themes (e.g. `mine_delve`, `lava_forge`) emits ZON
        regions, so the region-comparison path is genuinely exercised.
    - **No round-trip mismatch surfaced** — the builder's serialisation is
      byte-stable and parses back field-identical across every example.
    - **Verification (worktree `-Venv`):**
      `python -m pytest tests/test_properties_core.py -q` → **3 passed**
      (21.37 s). Full `python -m pytest tests/ -q` → **217 passed**, 2
      pre-existing warnings (starlette `BlockingPortal` deprecation, runpy
      `server.app`), no `PytestUnknownMarkWarning`. Exit 0 (62.23 s).
      *Analytically verified; NOT eyeballed in the 3D viewer — no geometry
      changed (test-only), so no 3D pass is owed here.*
    - **Commit (staged only `tests/test_properties_core.py`):** `f9946c5`.

- [ ] 10. Layout property module (`tests/test_properties_layout.py`)
  - [x] 10.1 Write the property test for the ZoneSpec JSON round-trip
    - **Property 4: ZoneSpec JSON round-trip** (umbrella P11)
    - `test_zonespec_json_roundtrip` over `spec_themes`, n 1–30, locks 0–5, elevation and `semantic_inputs`.
    - Assert `ZoneSpec.from_dict(json.loads(j)).to_dict()` (normalised through JSON) `== json.loads(j)`, with exact float equality.
    - **Validates: Requirements 2.4, 1.6**
    - **Done.** Created `tests/test_properties_layout.py` with
      `test_zonespec_json_roundtrip` as the first test in the module. Verified
      against the real code first:
      - `ZoneSpec.to_dict` / `ZoneSpec.from_dict` are the exact names
        (`generators/zone_spec.py`). `to_dict` emits tuples as lists; `from_dict`
        rebuilds tuples. `CorridorSpec.floor_z` is a `@property` (not a dataclass
        field), so `asdict` omits it and `from_dict(**fields)` never sees it —
        no round-trip hazard.
      - Production path is `ai.expand.plan_to_spec(ZonePlan(...), seed=seed)`
        (same path the other layout tests use) — the full real layout, so the
        spec carries realistic rooms/corridors/gates/materials + semantic fields.
        `semantic_inputs` map onto `ZonePlan.{dungeon_theme,dungeon_race,
        elemental_tint}`; the `None` elemental-tint sentinel is passed as `""`
        (ZonePlan's field default).
      - Assertion framed exactly as the design states: `j = json.dumps(spec.to_dict())`,
        then `json.loads(json.dumps(ZoneSpec.from_dict(json.loads(j)).to_dict()))
        == json.loads(j)`. The outer json dump/load on the reserialised side puts
        BOTH sides in the same list-not-tuple shape so the `==` is a pure JSON
        fixpoint with exact float equality. **No adjustment to the assertion was
        needed** — the round-trip is a clean fixpoint for every drawn input; no
        counterexample surfaced.
      - ONE deviation from the bare design wording: added
        `@settings(deadline=None, max_examples=scaled(100))`. A full layout for up
        to 30 rooms + semantic layer occasionally exceeds the Default_Profile's
        200 ms per-example deadline on a cold first call (import/JIT warmup, then
        ~1–35 ms thereafter), which Hypothesis flagged as a flaky DeadlineExceeded.
        That's timing variance, not a property failure. Budget stays 100 (via
        `scaled(100)`, so it still 5×-scales under `thorough`); NOT a build-tier
        test, so no `slow` marker and no `build_settings`.
    - **Verification:** `python -m pytest tests/test_properties_layout.py -q
      --hypothesis-show-statistics` → **1 passed, 100 passing examples, 0 failing,
      0 invalid**. Full suite `python -m pytest tests/ -q` → **208 passed**
      (2 pre-existing unrelated warnings: starlette anyio-alias deprecation,
      runpy re-import).
    - **Commit:** the clean single-file commit of `tests/test_properties_layout.py`
      is `799dc6a` (`git show --stat 799dc6a` → 1 file, 75 insertions). NOTE: this
      worktree had **concurrent sibling agents committing on the same branch**
      (forbidden by the single-writer-per-worktree rule), which raced the shared
      `.git` — HEAD was reset/advanced under this task mid-commit and a sibling's
      broad `git add`/commit swept the layout-test file into their `37e0947`
      ("11.1") commit, leaving `799dc6a` dangling. The test content IS present and
      tracked in the current HEAD tree (verified: `git grep -l
      test_zonespec_json_roundtrip HEAD -- tests/test_properties_layout.py`). The
      hash co-mingling across 10.1 / 11.1 / 5.5 must be reconciled at the
      single-writer integration step, not here.
  - [x] 10.2 Write the property test for connectivity and pacing roles
    - **Property 5: Layout connectivity and pacing roles** (umbrella P3, single District)
    - `test_connectivity_and_roles` over `box_themes`, n 1–30 and `semantic_inputs`.
    - Assert that the Room_Graph is connected and has exactly n rooms, that exactly one room is the entrance, and that for n ≥ 2 exactly one room is the climax and it isn't the entrance.
    - **Validates: Requirements 3.1, 1.6**
    - **Done.** Appended `test_connectivity_and_roles` to
      `tests/test_properties_layout.py` (after 10.1's
      `test_zonespec_json_roundtrip`, which is untouched; reused its
      `plan_to_spec(ZonePlan(...), seed=seed)` path and
      `@settings(deadline=None, max_examples=scaled(100))` idiom). Verified
      against the real code first:
      - Role names come from `LayoutGenerator._apply_pacing`
        (`generators/layout.py`): roles are
        `entrance | climax | hub | deadend | standard`. **Exactly one
        `entrance`** (the room farthest from the layout centroid). **Climax =
        the deepest room by graph depth, assigned only when `n > 1`**
        (`climax = ... if n > 1 else entrance`); the role loop checks
        `i == entrance` before `i == climax`, so at `n == 1` the single room is
        `entrance` and there is NO `climax` room — the `n >= 2` guard is
        therefore correct and verified by the test's `else: assert climaxes == []`
        branch.
      - Connectivity is structurally guaranteed by `_connect_rooms`: an MST
        (spanning tree) over all rooms plus ~12% loop edges, so the Room_Graph is
        always one component. `n == 1` yields no corridors — a single isolated
        node, which the test's `_connected` helper treats as connected.
      - `pbt_helpers.room_graph(spec)` builds adjacency from
        `corridors[*].from_room/to_room` and seeds every room id as a key, so
        `set(adj) == set(room_ids)` and the component walk are exact.
      - **No adjustment to the assertions was needed** — connectivity and the
        entrance/climax counts held for every drawn input; **no counterexample
        surfaced** (a disconnected graph or wrong role count would have been a
        real layout bug).
    - **Verification:** `python -m pytest tests/test_properties_layout.py -q` →
      **2 passed** (10.1 + 10.2). Full suite `python -m pytest tests/ -q` →
      **211 passed** (2 pre-existing unrelated warnings: starlette anyio-alias
      deprecation, runpy re-import).
    - **Commit:** clean single-file code commit of
      `tests/test_properties_layout.py` is `17980cb`
      (`git show --stat 17980cb` → 1 file, +81/-2). Tracker commit for this
      tasks.md follows separately.
  - [x] 10.3 Find a generated input that reaches the key-room fallback (one-off scan, not committed)
    - Scan `LayoutGenerator.generate` over seeds, n 4–8, locks 3–5 and M0_Box_Themes. Stop at the first input where some `gate.key_room_id` equals the entrance id, and record it here.
    - If no input turns up in ≥ 200k candidates, stop and report to the user. A constructed `_apply_gating` call would be a deviation that needs their approval.
    - _Requirements: 3.6_
    - **Done.** One-off throwaway scan (temp `_scan_fallback.py`, run via the
      worktree venv and then deleted — no code deliverable) over
      `LayoutGenerator(theme, seed).generate(name, room_count=n, locks=k)` with
      seeds increasing from 0, then theme in `["dungeon", "city"]`, then
      `room_count` 4..8, then `locks` 3..5. This drives the real gated path:
      `generate(..., locks=k)` calls `_apply_gating` internally when `locks > 0`,
      and the entrance is the room with `role == "entrance"` (set by
      `_apply_pacing`). The fallback is observed from the output with no spy —
      per the design, the fallback ran iff some `gate.key_room_id` equals the
      entrance id.
    - **First hit (after 485 candidates scanned):**
      - Input tuple: **`seed=16, theme="dungeon", room_count=5, locks=4`**
      - Entrance id: **`room_0`** (the BFS root / depth-0 room)
      - Total gates: **4** — `gate_0→room_1`, `gate_1→room_0`, `gate_2→room_0`,
        `gate_3→room_0`.
      - Fallback gate (first `key_room_id == entrance_id`): **`gate_1`**
        (`corridor_id=corr_2`, `key_room_id=room_0`, `tier=1`). Gates 2 and 3
        also fall back to `room_0`.
    - Reproducibility confirmed: a fresh
      `LayoutGenerator("dungeon", seed=16).generate("rep", room_count=5, locks=4)`
      again yields entrance `room_0`, 4 gates, and `gate_1/2/3.key_room_id ==
      room_0`.
    - For task 10.4: pin `@example(seed=16, theme="dungeon", room_count=5,
      locks=4, expect_fallback=True)` and assert `key_room_id == entrance_id`
      for at least one gate.
  - [x] 10.4 Write the property test for gating solvability, including the pinned fallback
    - **Property 6: Gating is solvable** (umbrella P4, single District)
    - `test_gating_solvable` over `box_themes`, n 3–30, locks 1–5, `semantic_inputs` and an `expect_fallback` argument (`False` for generated cases).
    - Assert `1 <= len(gates) <= locks` and that `solvable_walk` visits every room.
    - Pin the 10.3 input as `@example(..., expect_fallback=True)`. For that example, assert `key_room_id == entrance_id`.
    - **Validates: Requirements 3.2, 3.6, 1.6**
    - **Done.** Appended `test_gating_solvable` to
      `tests/test_properties_layout.py` (10.1 `test_zonespec_json_roundtrip` and
      10.2 `test_connectivity_and_roles` left untouched — pure append plus two
      extra imports: `example` from hypothesis, and `LayoutGenerator` /
      `solvable_walk` / `_entrance_id`). Drives the SAME gated path 10.3 verified:
      `LayoutGenerator(theme, seed=seed).generate(name, room_count=n, locks=k)`
      (`locks > 0` runs `_apply_gating` internally). `@given` over `box_themes`,
      `room_counts(3, 30)`, `locks` 1–5, `semantic_inputs`, and
      `expect_fallback=st.just(False)` for generated cases.
      `@settings(deadline=None, max_examples=scaled(100))` — layout-tier (gating
      never builds the binary, never touches geometry per umbrella P5), so no
      `slow` marker and no `build_settings`; deadline lifted for the same cold-call
      warmup reason as 10.1/10.2.
      - Assertions: `1 <= len(gates) <= locks`; and `solvable_walk(spec)` (the
        fixpoint walk from the entrance, crossing a gated corridor only once its
        `key_room_id` is visited) equals the full room-id set — every room reached.
      - Pinned fallback `@example(seed=16, theme="dungeon", n=5, locks=4,
        semantic={neutral}, expect_fallback=True)` — param names aligned to
        `@given` (`n`, not `room_count`), neutral `semantic` so it reproduces the
        plain `generate(name, room_count=5, locks=4)` call 10.3 scanned. For
        `expect_fallback=True` the test additionally asserts some
        `gate.key_room_id == entrance_id`, proving the key-room fallback path runs
        and is still solvable.
    - **10.3 reproduction verified independently** (one-off, not committed): a
      fresh `LayoutGenerator("dungeon", seed=16).generate("rep", room_count=5,
      locks=4)` yields entrance `room_0`, 4 gates
      (`gate_0→room_1`, `gate_1/2/3→room_0`), so a gate keys off the entrance id
      (fallback exercised), and `solvable_walk` reaches all 5 rooms.
    - **No generated input failed solvability** — `solvable_walk` visited every
      room across all 100 examples + the pinned case. A miss would have been a
      real gating-solvability bug (umbrella P4); the strategy was never narrowed
      and the assertion never weakened.
    - **Verification (worktree `-Venv`):**
      `.\.venv\Scripts\python.exe -m pytest tests/test_properties_layout.py -q` →
      **3 passed** (10.1 + 10.2 + 10.4). Full `.\.venv\Scripts\python.exe -m
      pytest tests/ -q` → **218 passed**, 2 pre-existing unrelated warnings
      (starlette `BlockingPortal` deprecation, runpy `server.app`), exit 0
      (61 s). *Analytically verified; test-only, no geometry changed, so no 3D
      pass is owed here.*
    - **Commit (staged only `tests/test_properties_layout.py`):** `116b264`.
  - [x] 10.5 Write the property test for the elevation grade cap
    - **Property 7: Elevation grade cap** (umbrella P6)
    - `test_elevation_grade_cap` through `ai.expand.plan_to_spec` over `box_themes`, n 2–30, `verticality`, elevation and `semantic_inputs`.
    - Assert `|from_z − to_z| <= run_for(...) * 0.5 + 0.01` for every corridor, tree and loop edges alike.
    - The known suspect here is semantic `sink` with elevation off. If it fails, follow task 13.1. Never drop semantic inputs from the strategy.
    - **Validates: Requirements 3.3, 1.6**
    - **Done.** Added `test_elevation_grade_cap` to
      `tests/test_properties_layout.py` exactly as specified: driven through
      `ai.expand.plan_to_spec` over `box_themes`, `room_counts(2, 30)`, the full
      `verticality` strategy, `st.booleans()` for elevation, and the full
      `semantic_inputs` strategy (none dropped). For every corridor it resolves
      the two endpoint rooms by id and asserts
      `|from_z − to_z| <= run_for(spec, theme, n, plan.size, a, b) * 0.5 + 0.01`,
      with `run_for` calling the production `LayoutGenerator._elevation_run`.
      `@settings(deadline=None, max_examples=scaled(100))` — layout-tier only
      (no binary build), so no `slow` marker.
    - **This property caught a GENUINE production bug** (two root causes, both in
      `generators/layout.py`), fixed under task 13.1 first; the test is NOT
      weakened to pass. Green over 100 examples (default) and 500 (thorough).
    - **Commit:** `d47111a` — `tests/test_properties_layout.py` only.
  - [x] 10.6 Write the relax-conflict fallback example test
    - **Property 7: Elevation grade cap** (umbrella P6, constructed conflict case)
    - `test_relax_conflict_fallback`: set up `LayoutGenerator("dungeon", seed=0)` with `_apply_room_scale(3)` and rooms E (z 0), B (z 0) and C (z 200), each 200×200 on the X axis with 40 u gaps, and `adj` with B inserted first.
    - Precondition: B's two walkable bands, computed with `gen._elevation_run`, are disjoint. This proves the midpoint branch runs.
    - Postcondition: after `_relax_elevation`, every adjacent pair satisfies `|Δz| <= run * 0.5 + 0.01`.
    - **Validates: Requirements 3.7, 1.6**
    - **Done.** Appended `test_relax_conflict_fallback` to
      `tests/test_properties_layout.py` (10.1/10.2/10.4/10.5 left untouched). It
      is an EXAMPLE test (plain `def`, no `@given`/`@settings`, no `slow`, no
      binary build) that drives `_relax_elevation`'s conflicting-neighbours
      midpoint branch directly, per the design "Fallback-path examples → Relax
      conflict fallback (Req 3.7)".
    - **Verified against the real post-13.1 code:** signature is
      `_relax_elevation(self, rooms, adj, entrance, iterations=200)` — the test
      calls it exactly as the design specifies, `gen._relax_elevation(rooms, adj,
      entrance)`. `RoomSpec` fields used are the real dataclass
      (`id, center_x, center_y, floor_z, width, depth, height`); rooms are
      `width=depth=200` on +X with centre spacing 240 (200 + 40 u gap), all on
      y=0, so each corridor is a straight single leg and
      `gen._elevation_run(a,b) == 44`, giving `cap = 44 * max_grade(0.5) = 22`.
      `adj = {1:[0,2], 2:[1], 0:[1]}` with B (index 1) inserted first.
    - **Precondition holds (midpoint branch runs):** at the initial Z, B's two
      bands `[E.z−cap, E.z+cap] = [−22, 22]` and `[C.z−cap, C.z+cap] = [178, 222]`
      are DISJOINT, so no single Z satisfies both neighbours and the `lo > hi`
      midpoint branch fires on pass 1 (B is the first non-entrance node visited).
      Confirmed by running the real generator before writing the assertion.
    - **Postcondition passes:** after `gen._relax_elevation(rooms, adj, 0)` the
      final floor_z are E=0.0, B≈22.00007, C≈44.00007; both adjacent pairs satisfy
      `|Δz| ≤ run*0.5+0.01` (22.00007 ≤ 22.01 for E–B, 22.0 ≤ 22.01 for B–C) —
      the thin-tolerance case Req 3.7 calls out.
    - **Verification:** `.\.venv\Scripts\python.exe -m pytest
      tests/test_properties_layout.py -q` → **5 passed**; full suite
      `python -m pytest tests/ -q` → **220 passed** (2 pre-existing unrelated
      warnings: starlette `BlockingPortal` deprecation, runpy `server.app`).
    - **Commit:** `d2f88656faf630831622574f58435be9c50d2d32` ("M0 10.6: add
      relax-conflict fallback example test") — staged only
      `tests/test_properties_layout.py` (1 file, +93).
  - [x] 10.7 Write the property test for flush openings
    - **Property 8: Flush openings** (umbrella P7)
    - `test_flush_openings` with a budget of `scaled(50)`, over `box_themes`, n 2–12 and elevation, using `geometry.build_mesh(spec).to_ter(...)` in memory.
    - Assert that `from_z`/`to_z` equal the rooms' `floor_z`.
    - Assert that every `opening_floor_z` value under `(from_x, from_y)` and `(to_x, to_y)` lies within 0.01 u of that room's `floor_z`.
    - **Validates: Requirements 3.4, 1.6**
    - **Done.** `test_flush_openings` added to `tests/test_properties_layout.py`,
      `@settings(deadline=None, max_examples=scaled(50))` over `seeds`,
      `box_themes`, `room_counts(2, 12)` and `elevation`. Builds the Box_Backend
      mesh in memory via `build_mesh(spec).to_ter(...)` — no `ZoneBuilder`, no
      `.eqg`, so no `slow`/`build_settings`. Property_Docstring: "Feature:
      zone-generator-m0-hygiene, Property 8: Flush openings" (umbrella P7),
      "Validates: M0 Req 3.4; umbrella Req 1.6". Analytically verified, NOT
      eyeballed in the 3D viewer.
    - **Band-artifact finding (why the first run stopped):** with `band=c.height`
      (≈97 u) the strict-flush inner assertion tripped on one opening of seed=1 /
      dungeon / n=8 / elevation=True (corr_6). Diagnosis: NOT a flush bug. At
      every opening `from_z`/`to_z` equalled the room `floor_z` exactly AND a
      flush floor face (|z−floor_z| ≤ 0.01) was present. The only faces tripping
      the assertion were the SAME Z-corridor's legitimately-elevated far leg
      (a walkable ramp within the grade cap) overhanging the opening XY — swept
      into the probe because the band spanned the whole corridor-height column.
    - **Decision (design-faithful, invariant unchanged):** the helper
      `opening_floor_z(ter, x, y, z_ref, band)` has `band` precisely to scope the
      probe to the SEAM. Changed both calls from `band=c.height` to
      `band=MAX_SEG_RISE` (2.5 u, imported from `generators.geometry`, the
      step-up / per-segment-rise limit). The `z_ref ± band` window is exactly what
      the design expresses; a real step at the seam is ≤ 2.5 u off and is STILL
      caught by the strict **0.01 u** assertion (preserved verbatim), while a
      Z-corridor's distant walkable far end is correctly excluded. Correct probe
      scoping, not a loosened assertion. Assertion (1) (`from_z`/`to_z` ==
      `floor_z`, exact), the non-empty-probe assertion, and the 0.01 u strictness
      are all unchanged.
    - **Verification:** `pytest tests/test_properties_layout.py -q` green (6
      passed). The previously-failing case (seed=1, dungeon, n=8, elevation=True)
      re-run explicitly — corr_6 present and now passes with the tight band. Full
      suite `pytest tests/ -q` green: **221 passed**.
    - **Deliverable commit:** `47373ea` — staged only
      `tests/test_properties_layout.py` (1 file, +139 −1).
  - [x] 10.8 Write the property test for ZonePlan normalisation
    - **Property 9: ZonePlan normalisation** (umbrella P12, no controls path)
    - `test_zoneplan_normalisation` over `zone_plan_dicts`.
    - Assert that every field of `ZonePlan.from_dict(d)` is inside its umbrella-Req 2.3/2.4/2.8 domain, and that a second `validate()` returns an equal plan.
    - **Validates: Requirements 3.5, 1.6**
    - **Done.** Appended `test_zoneplan_normalisation` to
      `tests/test_properties_layout.py` (added `zone_plan_dicts` to the
      `.strategies` import; the 6 existing tests 10.1/10.2/10.4/10.5/10.6/10.7
      are untouched). Budget `scaled(100)`, `deadline=None`, no `slow` marker
      (pure `ai.schema` logic, no binary build, no controls path).
    - **Real normalisation API (verified in `ai/schema.py`):** the entry is
      `ZonePlan.from_dict(d)` — it drops keys outside the dataclass, constructs
      the plan from the survivors, then calls `.validate()`, which clamps/filters
      every field IN PLACE and returns self. So `from_dict` IS the normalisation
      and `validate()` is the fixpoint step. Idempotence is asserted by calling
      `plan.validate()` a second time and comparing `to_dict()` before/after.
    - **Field domains asserted (the REAL `validate()` domains):** `theme` in
      VALID_THEMES = {dungeon, outdoor, city} — any out-of-vocab theme ("cave"
      included) maps to "dungeon", so the assertion is membership, which covers
      the cave→dungeon case the strategy exercises (task 2.4) with no
      special-casing; `room_count` int in [1, 30]; `locks` int in [0, 5]; `size`
      in {small, medium, large, huge}; `verticality` in {flat, moderate,
      dramatic}; `regions` a list with every kind in VALID_REGION_KINDS;
      `dungeon_theme`/`dungeon_race`/`elemental_tint` each `""` or in their
      vocab; `elevation` a bool.
    - **Deviation note:** the design says "theme cave→dungeon"; the real
      `validate()` is broader — it maps ANY out-of-vocab theme to "dungeon". The
      test asserts the real (broader) domain (`theme in VALID_THEMES`), which
      subsumes the cave case. No counterexample surfaced — no field escaped its
      domain for any input.
    - **Verification:** `tests/test_properties_layout.py` → **7 passed**; full
      suite `python -m pytest tests/ -q` → **222 passed**, 2 pre-existing
      warnings (starlette `BlockingPortal` deprecation + runpy `server.app`),
      exit 0.
    - **Commit:** `a716c70` ("M0 10.8: property test for ZonePlan
      normalisation") — staged only `tests/test_properties_layout.py`.
  - [x] 10.9 Write the property test that cave words never yield a cave theme
    - **Property 19: Cave words never yield a cave theme**
    - `test_cave_words_mean_dungeon` in `tests/test_properties_layout.py`, budget 100, over prompts containing one or more Cave_Words mixed with random filler and optional outdoor/city/dungeon keywords.
    - Assert that `RulePlanner().plan(prompt).theme` is in the Defined_Themes, and equals `dungeon` whenever the dungeon-bucket score (computed in the test from `_THEME_WORDS` with `str.count`) is strictly greater than the outdoor and city scores. Include a Property_Docstring.
    - **Validates: Requirements 6.5**
    - **Done.** Appended `test_cave_words_mean_dungeon` to
      `tests/test_properties_layout.py` (10.1/10.2/10.4–10.8 left untouched).
      Added a module-level `cave_prompts` composite strategy: it always draws
      1–3 words from `tests.strategies.CAVE_WORDS`, optionally salts 0–3 words
      from the OTHER `_THEME_WORDS` buckets (`_OTHER_THEME_WORDS` = every outdoor
      / city word plus the non-cave dungeon words), adds an `st.text()` filler,
      and shuffles all tokens into one prompt string via `st.permutations`.
      Budget `scaled(100)`, `deadline=None` (layout-tier, no build, no `slow`).
    - **Verified against the real code first:**
      - `RulePlanner().plan(prompt).theme` is the API; `RulePlanner` and
        `_THEME_WORDS` imported from `ai.rule_planner`.
      - `_THEME_WORDS` buckets (post-5.2): `outdoor` = [outdoor, forest, field,
        meadow, hills, plains, valley, mountain, wilderness, swamp, desert,
        coast]; `city` = [city, town, village, market, bazaar, streets, plaza];
        `dungeon` = [dungeon, crypt, catacomb, ruin, temple, keep, fortress,
        lair, stronghold, vault, **cave, cavern, grotto, tunnel, underground,
        mine**]. Confirmed the five cave words are folded into the dungeon bucket.
      - `_match_theme` scores each bucket as `sum(text.count(w) for w in words)`
        over `prompt.lower()` — i.e. `str.count` substring counting — and keeps
        the first bucket with a strictly-greater score (strict `>` tie rule,
        default `dungeon`). The test mirrors this exactly in `_bucket_score`, so
        the strictly-greater premise is computed the same way the planner scores.
    - **Assertions:** (1) `theme in DEFINED_THEMES` (`{dungeon, city, outdoor}`,
      never `cave`) for every prompt; (2) when the test-computed dungeon score is
      strictly greater than BOTH the outdoor and city scores, `theme == "dungeon"`.
      Ties / outdoor-or-city-outscoring only assert Defined_Themes membership
      (tie rule unchanged; outdoor/city win ties — not over-constrained).
    - **Verification (worktree `-Venv`):**
      `python -m pytest tests/test_properties_layout.py -q` → **8 passed** (the
      new test + 10.1/10.2/10.4–10.8). Full suite `python -m pytest tests/ -q` →
      **223 passed**, 2 pre-existing warnings (starlette `BlockingPortal`
      deprecation + runpy `server.app`), exit 0. No cave-word prompt yielded a
      "cave" or other non-Defined theme, and no strictly-greater-dungeon prompt
      failed to resolve to `dungeon` across the full 100-example budget — no
      planner bug surfaced.
    - **Commit:** `a7d7c1f` ("M0 10.9: Property 19 cave words never yield a cave
      theme") — staged only `tests/test_properties_layout.py`.

- [ ] 11. Build property module (`tests/test_properties_build.py`, all `@pytest.mark.slow` with `build_settings`)
  - [x] 11.1 Write the property test for raw dungeon navigability
    - **Property 10: Raw dungeon builds are navigable** (umbrella P1, dungeon)
    - `test_raw_dungeon_navigable` with `build_settings(20)`, over dungeon, n 2–12 and elevation, using `LayoutGenerator.generate` + `build_raw` + `validate(eqg, spec=spec)`.
    - Builder exceptions propagate as failures. Never call `assume` here.
    - **Validates: Requirements 4.1, 1.5, 1.6**
    - **Done.** Created `tests/test_properties_build.py` (module header: all tests
      here are `@pytest.mark.slow` with `build_settings`) and added
      `test_raw_dungeon_navigable` as the first test, decorated
      `@pytest.mark.slow` + `@build_settings(20)` + `@given(s=seeds,
      n=room_counts(2, 12), elevation=st.booleans())`. Property: builds a dungeon
      via `LayoutGenerator(theme="dungeon", seed=s).generate("navdun",
      room_count=n, elevation=elevation)`, then `build_raw(spec, out)` in a
      `fresh_dir()`, then asserts `analyzer.traverse.validate(result.eqg_path,
      spec=spec).passed`. No `assume` — builder exceptions propagate (Req 4.1).
      Property_Docstring present (names umbrella P1 and "Validates: M0 Req 4.1,
      1.5; umbrella P1").
    - **Real validator API used:** `analyzer.traverse.validate(eqg_path, *,
      spec=ZoneSpec) -> TraversalReport`; "is navigable" is `report.passed`
      (`total_rooms > 0 and reachable_rooms == total_rooms`). It loads the TER
      from the `.eqg`, builds a per-triangle walk surface, floods from the
      entrance safe point, and maps each room's floor footprint onto the
      reachable set — the same validator `tests/test_traversability.py` uses.
    - **Verification (worktree `-Venv`):** `python -m pytest
      tests/test_properties_build.py -q` → **1 passed** (~2.4 s warm;
      `--hypothesis-show-statistics` confirms **20 passing examples**, stopped at
      `max_examples=20`, typical per-example runtime ~49–391 ms — a cold run is
      several seconds). Full `python -m pytest tests/ -q` → **208 passed**,
      2 warnings (pre-existing starlette `BlockingPortal` + runpy `server.app`),
      ~22 s. No counterexample surfaced.
    - **NOT 3D-verified:** this is an ANALYTICAL navigability check on the TER
      mesh (`analyzer.traverse`), necessary but not sufficient per the project
      rule — not eyeballed in the live 3D viewer. If a non-navigable dungeon ever
      fails this property, treat it as a real geometry bug (task 13.1), not an
      input to assume away.
    - **Commit:** `37e0947` ("M0 11.1: property test for raw dungeon
      navigability"). Note: because sibling tasks (9.x/10.x) run on this same
      `agent/m0-hygiene` branch, two concurrently-untracked sibling files
      (`tests/test_properties_core.py`, `tests/test_properties_layout.py`) were
      present in the shared index and got swept into this commit alongside
      `tests/test_properties_build.py`. All three are now tracked and correct in
      HEAD; the 11.1 file itself is `tests/test_properties_build.py`.
  - [x] 11.2 Write the property test for ramp subdivision
    - **Property 11: Ramp subdivision** (umbrella P8)
    - `test_ramp_subdivision` with `build_settings(20)`, over `box_themes`, n 2–12, elevation on and verticality `moderate`/`dramatic`, through `plan_to_spec`.
    - Assert that every value in `ramp_rises(ter)` is ≤ 2.51.
    - Pin an `@example` with a corridor whose total rise exceeds 2.5 u, and assert that precondition inside the test.
    - **Validates: Requirements 4.2, 4.6, 1.5, 1.6**
    - **Done.** Appended `test_ramp_subdivision` to `tests/test_properties_build.py`
      (reuses 11.1's `fresh_dir`/`build_raw`/`seeds`/`room_counts` idioms, leaves
      `test_raw_dungeon_navigable` untouched). Verified against the real code first:
      - `ai.expand.plan_to_spec(plan, seed)` is the only path that applies plan
        `verticality` (`ai.expand._VERTICALITY` → elevation chance + rise min/max);
        `elevation=plan.elevation and plan.verticality != "flat"`. The test builds a
        `ZonePlan(theme, room_count=n, verticality, elevation=True)` and drives
        `plan_to_spec`. Verticality strategy restricted to `moderate`/`dramatic`
        (local `st.sampled_from(["moderate","dramatic"])`); themes from
        `tests.strategies.box_themes` (dungeon/city), n via `room_counts(2,12)`.
      - `pbt_helpers.ramp_rises(ter)` accepts TER bytes or a `TerFile` (`_ter`
        normalises); fed `ter_bytes` from `build_raw`. Returns per-triangle rise of
        every upward (walkable, nz ≥ cos40°) face; assertion is `max(rises) <= 2.51`
        (`MAX_SEG_RISE = 2.5` in `generators/geometry.py`, +0.01 tolerance).
      - Precondition proof the subdivision path ran: measured on the spec's
        `CorridorSpec.from_z/to_z` BEFORE geometry. Pinned
        `@example(s=0, theme="dungeon", n=3, verticality="dramatic")` yields a
        corridor span ~71.3 u (≫ 2.5); the test hard-asserts `max_span > 2.5` for
        that exact tuple. Random elevated-verticality draws may roll flat
        (elevation_chance 0.5/0.85) → legitimate vacuous pass; no `assume` is called
        (build-property rule). On the pinned example: 126 upward faces, worst
        per-triangle rise 2.469 u (≤ 2.51), 0 over.
      - ANALYTICAL check only (per-triangle rise on the TER mesh), NOT a live 3D
        viewer confirmation — flagged per `docs/ACCEPTANCE.md` / the
        "structural tests pass ≠ done" rule.
    - **Verification:** `tests/test_properties_build.py` → 2 passed in ~10 s; full
      suite `python -m pytest tests/ -q` → **212 passed** in ~53 s (2 pre-existing
      starlette/runpy deprecation warnings, unrelated to this change).
    - **Deliverable commit:** `3c22e51`.
  - [x] 11.3 Write the property test that locks never touch geometry
    - **Property 12: Locks never touch geometry** (umbrella P5, locks)
    - `test_locks_do_not_touch_geometry` with `build_settings(15)`, over `box_themes`, n 3–12 and locks 1–5, compared with locks 0 for the same plan and seed.
    - Assert that TER and ZON are byte-identical.
    - **Validates: Requirements 4.3, 1.5, 1.6**
    - **Done.** Appended `test_locks_do_not_touch_geometry` to
      `tests/test_properties_build.py` (11.1/11.2 left untouched; reuses the
      module's `build_raw` / `fresh_dir` / `box_themes` / `plan_to_spec` /
      `ZonePlan` idioms). `@pytest.mark.slow`, `@build_settings(15)`, over
      `box_themes`, n (`room_counts(3, 12)`) and `locks` 1–5. For one fixed plan
      and seed it builds twice — once with the drawn `locks` (1–5), once with
      `locks=0` — each into its own `fresh_dir()`, and asserts the read-back TER
      and ZON are BYTE-IDENTICAL (not the `.eqg`, whose PFS footer stamps time).
    - **Verified against real code first:** `ZonePlan` is a dataclass with a
      `locks: int = 0` field (clamped to [0,5] in `validate`); `plan_to_spec`
      passes `locks=plan.locks` into `LayoutGenerator.generate`; `plan_to_spec`
      uses the EXPLICIT `seed` arg (no fresh random is drawn when seed is given),
      so same plan + same seed differ ONLY by `locks`. Same name built into two
      `fresh_dir()`s is safe — `build_raw` reads the named TER/ZON members back
      out and compares those bytes, not the archive. Property PASSES: locks never
      changed TER or ZON for any example (no gating-into-geometry leak).
    - **Verification:** `tests/test_properties_build.py` → 3 passed (5.57s). Full
      suite `python -m pytest tests/ -q` → **224 passed, 2 warnings in 38.97s**
      (the two pre-existing warnings: starlette `BlockingPortal` deprecation and
      the runpy `server.app` warning). ANALYTICAL byte-equality check on the built
      TER/ZON — NOT confirmed in the live 3D viewer (see docs/ACCEPTANCE.md).
    - **Code commit:** `4edb768` (`tests/test_properties_build.py` only). Tracker
      bookkeeping lands in the follow-up commit.
  - [x] 11.4 Write the property test for seed determinism
    - **Property 13: Seed determinism** (umbrella P9, no map artifacts)
    - `test_seed_determinism` with `build_settings(15)`, over `spec_themes`, n 2–12, locks 0–5 and elevation.
    - Run two `plan_to_spec` + `build_raw` passes into two `fresh_dir()`s. Assert equal Zone_Spec dicts and byte-identical TER and ZON.
    - **Validates: Requirements 4.4, 1.5, 1.6**
    - **Done.** Appended `test_seed_determinism` to `tests/test_properties_build.py`
      (11.1/11.2/11.3 left untouched). `@pytest.mark.slow`, `@build_settings(15)`,
      drawing `spec_themes` (dungeon/city/outdoor), `room_counts(2, 12)`, `locks`
      0–5 and an `elevation` bool (with `verticality="moderate"` so the elevation
      flag actually toggles multi-level layout — `plan_to_spec` ANDs
      `elevation and verticality != "flat"`). Two `plan_to_spec(plan, seed=s)` +
      `build_raw` passes into two separate `fresh_dir()`s; asserts
      `spec1.to_dict() == spec2.to_dict()` AND byte-identical TER AND byte-identical
      ZON. Deliberately does NOT compare `.eqg` bytes (PFS footer stamps
      `int(time.time())`) or any texture/`.glb` output (salted procedural texture
      `hash()` can vary across processes); `build_raw` reads TER/ZON back out of
      the archive, so texture salting is irrelevant to the comparison.
    - **Verified against real code first:** `plan_to_spec` draws a fresh
      `random.randint` only when `seed is None`, so with an explicit seed the whole
      layout/geometry/placement pipeline is a pure function of (plan, seed);
      `ZoneSpec.to_dict()` exists; `spec_themes = {dungeon, city, outdoor}`;
      `ZonePlan` carries `name/theme/room_count/locks/elevation/verticality`.
    - **Verification (ANALYTICAL byte-equality on built TER/ZON, NOT eyeballed in
      the 3D viewer — see docs/ACCEPTANCE.md):**
      `tests/test_properties_build.py -q` → **4 passed in 9.23s**. Full suite
      `tests/ -q` → **225 passed in 46.64s** (only 2 pre-existing unrelated
      warnings: starlette `BlockingPortal` deprecation + runpy `server.app`).
      **No same-seed pair diverged** in spec, TER, or ZON — determinism holds
      across the drawn inputs.
    - **Commit:** `7b10b16` (code — `tests/test_properties_build.py` only).
  - [x] 11.5 Write the property test for advisory clearing
    - **Property 14: Advisory clearing leaves the TER unchanged** (umbrella P5, advisory clearing)
    - `test_advisory_clearing` with `build_settings(15)`, over `box_themes`, n 3–12, locks 1–5 and `semantic_inputs`.
    - Assert that the TER of `spec` is byte-identical to the TER of `clear_advisory(spec)`.
    - **Validates: Requirements 4.5, 1.5, 1.6**
    - **Done.** Appended `test_advisory_clearing` to `tests/test_properties_build.py`
      (11.1–11.4 left untouched). `@pytest.mark.slow`, `@build_settings(15)`, over
      `box_themes`, n (room_count) 3–12, locks 1–5 and `semantic_inputs`. Builds
      the spec via `plan_to_spec` (so the semantic layer realises advisory data),
      builds the original and `clear_advisory(spec)` into two separate
      `fresh_dir()`s via `build_raw`, and asserts the two TERs are byte-identical.
    - **Verified against real code:**
      - `pbt_helpers.clear_advisory` deep-copies (confirmed: `spec.to_dict()`
        unchanged after the call), resets the 7 room advisory fields
        (`role='standard'`, `graph_depth=0`, `semantic_type=''`, `district=0`,
        `prop_hints=[]`, `encounter_intent=''`, `boss=False`) and empties `gates`,
        while KEEPING `room_theme` and spec-level `dungeon_theme`/`dungeon_race`/
        `elemental_tint` — confirmed in a smoke test (room_theme `fortress` and the
        dungeon_* fields survive the clear).
      - `plan_to_spec` realises the advisory surface: with valid `semantic_inputs`
        vocab a seed-7 fortress build populated `role` {entrance, hub, standard,
        climax, deadend}, `graph_depth` {0..3}, `semantic_type` {throne,
        gatehouse, guard_post, ...}, `prop_hints`/`encounter_intent`/`boss` all
        truthy, and `locks=3` realised 3 gates — so the invariant is exercised,
        not vacuous.
      - `build_raw` reads the TER/ZON back out of the `.eqg` (never the `.eqg`
        bytes, whose PFS footer stamps `time.time()`).
    - **Advisory clearing NEVER changed the TER** — byte-identical in every
      example (and the ZON too, sanity-noted). No geometry-leak bug found.
    - **ANALYTICAL byte-equality verification only — NOT confirmed in the live 3D
      viewer** (geometry byte-identity is a stronger-than-visual check here).
    - **Verification:** `python -m pytest tests/test_properties_build.py -q` →
      **5 passed in 10.96s**. Full suite `python -m pytest tests/ -q` →
      **226 passed in 46.30s** (only the two pre-existing unrelated warnings:
      starlette `BlockingPortal` deprecation + runpy `server.app`).
    - **Commit:** `8c44f02` ("M0 11.5: property test for advisory clearing (TER byte-identical)") — `tests/test_properties_build.py` only.

- [ ] 12. Pipeline property module (`tests/test_properties_pipeline.py`)
  - [x] 12.1 Write the property test that returned builds passed the gate
    - **Property 15: Returned builds passed the gate** (umbrella P2)
    - `test_returned_build_is_validated`: slow, `build_settings(15)`, `max_attempts` 1–8, `rng=st.randoms(use_true_random=False)`, a spy `spec_factory` and `failure_log=None`.
    - Assert that the result is validated, that `1 <= calls <= max_attempts`, and that the returned seed equals the last seed the factory received.
    - `GenerationFailed` → `assume(False)`.
    - **Validates: Requirements 5.1, 1.5, 1.6**
    - **Done.** Created `tests/test_properties_pipeline.py` (first test in the
      module) with `test_returned_build_is_validated`. Marked `@pytest.mark.slow`
      with `@build_settings(15)`; `@given(max_attempts=st.integers(1, 8),
      rng=st.randoms(use_true_random=False))`; `failure_log=None`; output dir via
      `fresh_dir()` (no `tmp_path` under `@given`).
    - **Real `generate_validated` signature/result shape used:**
      `generate_validated(spec_factory, *, theme, zone_id, seed=None,
      output_dir, write_glb, ter_version, max_attempts, timeout_s, gated_themes,
      validate_enabled, agent, rng, failure_log)`. `spec_factory(seed) ->
      ZoneSpec`. Returns a `ValidatedBuild` dataclass; the property reads
      `.validated` (gate ran AND passed) and `.seed` (the seed that produced the
      returned zone). On a gated theme (dungeon) with no pinned seed, the loop
      does `use_seed = _fresh_seed(rng)` → `spec_factory(use_seed)` → build →
      `validate`; on pass it returns `seed=use_seed`, so `result.seed` equals the
      LAST seed the factory was handed. `_fresh_seed(rng)` calls
      `rng.randint(0, 2**31-1)` — the Hypothesis `randoms` object supplies it.
    - **Spy/factory idiom:** reused `test_pipeline`'s `_good_*` pattern — the spy
      records each seed it receives and a call counter, then ignores that seed
      for GEOMETRY and builds a fixed navigable dungeon (`LayoutGenerator(
      "dungeon", seed=1).generate("p15", room_count=3)`) so the gate passes on
      attempt 1. `write_glb=False` to stay fast.
    - **Assume-skip check:** the factory builds a connected, sub-second dungeon,
      so every example returns on the first attempt — NO example was
      assume-skipped (no `GenerationFailed`). `calls` is always 1 here, well
      within `[1, max_attempts]`, and `result.seed == seeds_seen[-1]` holds.
    - **Verification (worktree `-Venv`):**
      `python -m pytest tests/test_properties_pipeline.py -q` → **1 passed** in
      1.86s (15 examples under the default profile). Full
      `python -m pytest tests/ -q` → **209 passed**, 2 pre-existing warnings
      (starlette `BlockingPortal` deprecation + runpy `server.app`), no
      `PytestUnknownMarkWarning`, exit 0.
    - **Deliverable commit:** `0a1e245` — staged only
      `tests/test_properties_pipeline.py`.
  - [x] 12.2 Write the property test that forced failures are reported
    - **Property 16: Forced failures are reported, never swapped** (umbrella P2, pinned + exhaustion)
    - `test_forced_failure_reported`: slow, `build_settings(15)`. The factory builds a dungeon (n 2–4) plus one isolated room, keyed on the seed.
    - Pinned case: expect `GenerationFailed(pinned=True)` with `attempts == 1` and `failures[0].seed == seed`.
    - Unpinned case: `max_attempts` 1–8 and `timeout_s=1e9`; expect `pinned=False`, `timed_out=False` and `attempts == max_attempts`.
    - **Validates: Requirements 5.2, 5.6, 1.5, 1.6**
    - **Done.** Appended `test_forced_failure_reported` to
      `tests/test_properties_pipeline.py` below 12.1's
      `test_returned_build_is_validated` (left untouched; its imports
      `generate_validated`, `GenerationFailed`, `ValidatedBuild`,
      `build_settings`, `fresh_dir` are reused, plus a grouped `RoomSpec` import
      for the isolated room). `@pytest.mark.slow`, `@build_settings(15)`.
      - Factory `_forced_fail_factory(rooms)` mirrors
        `tests/test_pipeline._broken_spec`: builds the dungeon on the seed the
        pipeline hands it (keyed on the seed, n 2–4), then appends one far-away
        isolated `RoomSpec` so the traversability gate rejects every attempt
        regardless of seed.
      - Verified against `generators/pipeline.py`: `GenerationFailed` carries
        `.pinned`, `.timed_out`, `.attempts` (`= len(failures)`) and `.failures`
        (list of `AttemptFailure`, each with `.seed`). A pinned seed is signalled
        by passing `seed=<int>` (non-None ⇒ `pinned`); unpinned passes
        `seed=None`. Both branches asserted with the real attribute names — no
        adaptation needed, no swapped/wrong seed observed.
      - **Verification:** `python -m pytest tests/test_properties_pipeline.py -q`
        → **2 passed** in 11.68s. Full suite `python -m pytest tests/ -q` →
        **213 passed** in 57.55s, exit 0 (2 pre-existing unrelated warnings, no
        `PytestUnknownMarkWarning`).
    - **Deliverable commit:** `2541c14` — staged only
      `tests/test_properties_pipeline.py`.
  - [x] 12.3 Write the property test that fresh seeds vary
    - **Property 17: Fresh seeds vary** (umbrella P10)
    - `test_fresh_seeds_vary`: slow, `build_settings(10)`. Make k ∈ 3–10 unpinned calls on a 2-room dungeon with `rng` omitted, using a spy to record seeds.
    - Assert that every seed is in 0–2,147,483,647 and that the seeds are not all equal.
    - **Validates: Requirements 5.3, 1.5, 1.6**
    - **Done.** Appended `test_fresh_seeds_vary` to
      `tests/test_properties_pipeline.py` (12.1/12.2 untouched; reuses
      `generate_validated`, the 12.1 spy `spec_factory` idiom, `fresh_dir` and
      `build_settings`). `@pytest.mark.slow`, `@build_settings(10)`,
      `@given(k=st.integers(3, 10))` (no `tmp_path` on `@given` — uses
      `fresh_dir()`). Makes `k` unpinned `generate_validated` calls on a navigable
      2-room dungeon with BOTH `rng` and `seed` omitted, so each call draws a
      fresh seed via `_fresh_seed(None)`; the spy records every seed. Asserts the
      factory was called `k` times, every recorded seed ∈ `[0, 2147483647]`, and
      `len(set(seeds)) > 1` ("not all equal", not "all distinct" — a rare
      collision is acceptable).
    - **Fresh-seed independence confirmed:** `_fresh_seed(None)` (read in
      `generators/pipeline.py`) pulls from the module-level `random` generator via
      `random.randint(0, 2**31 - 1)`. Hypothesis's `default` profile
      `derandomize=True` only fixes Hypothesis's INPUT buffer, not the pipeline's
      internal RNG, so the `k` draws still vary within one example — verified
      (`[_fresh_seed(None) for _ in range(5)]` → 5 distinct values). No
      randomness regression; strategy NOT narrowed.
    - **Verification (worktree `-Venv`):**
      `python -m pytest tests/test_properties_pipeline.py -q` → **3 passed in
      8.14s**. Full suite `python -m pytest tests/ -q` → **227 passed in 51.69s**
      (2 pre-existing warnings only). Staged only
      `tests/test_properties_pipeline.py` for the code commit.
    - **Commit:** `1cce4b3` (code — `tests/test_properties_pipeline.py` only).
  - [x] 12.4 Write the no-API default selection example test
    - umbrella P16 (example)
    - `test_no_api_default_selection` with `no_api_keys` + `no_network`.
    - Assert `get_planner().name == "rule"`, that the active texture provider is procedural, and that `attempts == []`.
    - **Validates: Requirements 5.4, 1.6**
    - **Done.** Appended `test_no_api_default_selection` to
      `tests/test_properties_pipeline.py` (12.1/12.2/12.3 left untouched). Plain
      example test — no `@given` — so the function-scoped `no_api_keys` and
      `no_network` fixtures are used directly. Carries the P16 docstring naming
      the property and validated reqs.
    - **API verified against the real code first:**
      - `ai.planner.get_planner()` returns `RulePlanner` (which has
        `name = "rule"`) when no key / no `EQ_S3D_PLANNER` override and the
        forced global is `None` — `no_api_keys` deletes the env vars and calls
        `set_planner(None)`, so auto-select re-runs.
      - `generators.textures.factory.get_provider()` returns `ProceduralProvider`
        (which has `name = "procedural"`) under the same no-key path
        (`set_provider(None)` reset by the fixture). Asserted via `.name ==
        "procedural"`.
      - `no_network` yields its `attempts` list directly (conftest:
        `yield attempts`), so the test asserts `no_network == []`.
    - **Verification (worktree `-Venv`):**
      `python -m pytest tests/test_properties_pipeline.py -q` → **4 passed** (the
      3 existing pipeline properties + the new example). Full suite
      `python -m pytest tests/ -q` → **228 passed**, 2 pre-existing warnings
      (starlette `BlockingPortal` deprecation, runpy `server.app`), exit 0.
      Observed defaults: planner `rule`, provider `procedural`, `attempts == []`.
    - **Deliverable commit:** `826cfde` ("M0 12.4: add no-API default selection
      example test") — staged `tests/test_properties_pipeline.py` only.
  - [x] 12.5 Write the no-API prompt and CLI example test
    - umbrella P16 (example, slow)
    - `test_no_api_prompt_and_cli` with `no_api_keys` + `no_network`.
    - Server path: `TestClient(server.app.app)` with `OUTPUT_DIR`/`FAILURE_LOG` → `tmp_path`. POST a prompt, then GET `glb_url`.
    - CLI path: `main.main(["generate", "p16", "--rooms", "5", "--output", str(tmp_path)])`.
    - Assert that both produce an Accepted_Build and that `attempts == []`.
    - **Validates: Requirements 5.5, 1.6**
    - **Done.** Appended `test_no_api_prompt_and_cli` (`@pytest.mark.slow`, plain
      example test) to `tests/test_properties_pipeline.py` — 12.1–12.4 untouched.
      Uses `no_api_keys` + `no_network` fixtures plus `tmp_path`/`monkeypatch`
      (fine for an example test; the function-scoped-fixture health check only
      bites `@given` tests).
    - **Real request schema (verified in `server/app.py`):** `/api/generate`
      takes `GenerateRequest {prompt, theme, rooms, elevation, seed}`. A non-empty
      `prompt` routes through the planner (`make_plan` → `plan_to_spec`), sets
      `source="prompt"` and `planner=get_planner().name`, and ignores the explicit
      theme/rooms. The 200 `GenerateResponse` carries `validated: bool`, `glb_url`,
      `zone_url`, `map_url`, `source`, `planner`, `attempts`. Test POSTs
      `{"prompt": "a dark dungeon with a few rooms"}`, asserts `source=="prompt"`,
      `planner=="rule"` (the zero-key default), `validated is True`
      (Accepted_Build = gate ran AND passed), then GETs `glb_url` → 200.
      `OUTPUT_DIR`/`FAILURE_LOG` are module globals read at request time (by both
      `generate` and `get_zone_file`), so monkeypatching
      `server.app.OUTPUT_DIR`/`FAILURE_LOG` → `tmp_path/server` redirects both the
      write and the fetch — matches the task-7.2 `client` fixture pattern.
    - **Real CLI artifacts (verified in `main.py` + `builder.py`):**
      `main.main(["generate","p16","--rooms","5","--output",str(cli_out)])`
      (post-6.1 `main(argv)` takes the argv list) runs the default gated `dungeon`
      theme through `generate_validated`. `ZoneBuilder.build` writes `{name}.eqg`
      and `{name}.glb`; `cmd_generate` saves `{name}.json`. Test asserts `p16.eqg`,
      `p16.glb`, `p16.json` all exist under `cli_out` — the CLI Accepted_Build.
    - **attempts==[] (both paths):** the test asserts `no_network == []` after BOTH
      paths. The TestClient's loopback socketpair transport passes through the
      `no_network` guard (finding 4: 127.*/::1/AF_UNIX allowed), so only a
      genuinely foreign connect would be recorded — none was. Both the
      prompt→zone and CLI→zone flows ran with zero API keys and zero outbound
      network.
    - **Verification:** `tests/test_properties_pipeline.py -q` → **5 passed in
      9.31s** (only the pre-existing starlette `BlockingPortal` deprecation
      warning). Full suite `tests/ -q` → **229 passed in 49.00s**, zero
      failures/errors, no `PytestUnknownMarkWarning` (the two warnings are the
      pre-existing starlette deprecation + the runpy `server.app` note).
    - **Commit:** `49fa586` (code: `tests/test_properties_pipeline.py`);
      this tracker line recorded in the follow-up commit.

- [ ] 13. Root-cause fixes for counterexamples (conditional)
  - [x] 13.1 Fix any counterexample at its root
    - Only applies if a Property_Suite test fails, during tasks 9–12 or the thorough run in 16.3. Otherwise, mark this "not triggered" here. Don't fix anything ahead of time.
    - When a property fails:
      1. Stop and record the counterexample here.
      2. Pin it as `@example(...).via("discovered failure")` on the same test.
      3. Fix it at the root in the generator, following the design's Root-cause fix policy table. Known suspects: P6 `sink` with elevation off; the P6 relax midpoint/exit; the P4 key-room fallback. Never narrow the property or its strategy.
    - A PFS CRC collision or sentinel clash is a format limit: ask the user.
    - If the fix changes layout or geometry for any seed, record the affected seeds and flag the 3D pass (task 18.2). The pass covers the dungeon sections of `docs/ACCEPTANCE.md` on those seeds plus 1955208177, 1516796975 and 481893615.
    - _Requirements: 1.7, 3.3, 3.6, 3.7_
    - **TRIGGERED.** The 10.5 property `test_elevation_grade_cap` caught a
      genuine production bug in the elevation grade cap (umbrella P6). TWO root
      causes surfaced, both in `generators/layout.py`; both fixed at the root,
      the property was NOT weakened or narrowed.

    - **Counterexample 1 — semantic `sink` with elevation OFF** (the design's
      flagged suspect; minimised + reproducible):
      - seed=1, theme=dungeon, n=10, verticality='flat', elevation=False,
        semantic={'dungeon_theme':'', 'dungeon_race':'', 'elemental_tint':'lava'}.
      - Failing corridor `corr_4` (`room_1`→`room_5`): `|Δz|=20.0`,
        `run=23.5573`, `cap=run*0.5+0.01=11.7886`. 20.0 >> 11.79 — a cliff ~70%
        over the walkable grade cap.
      - **Root cause:** `semantics._apply_shape` does
        `room.floor_z += rt.sink * scale` for sink room types
        (battle_arena/vault −20, throne +8, flooded_gallery −25, sump −30). An
        `elemental_tint` (or `dungeon_theme`/`dungeon_race`) makes the dungeon
        "themed", so `layout.generate` runs the semantic layer and applies those
        biases. But `_assign_elevation` AND its `_relax_elevation` pass were
        guarded by `if elevation:`. With elevation=False the sunk/raised floors
        are never relaxed, so a sunk room next to a flat room is a cliff corridor
        steeper than `max_grade` (0.5). This is the historic cliff-corridor
        failure mode, now reachable with elevation OFF via the semantic sink path.
      - **Fix (design option (a), recommended):** when the layout is `themed`,
        run the relax pass over the graph even with elevation off — new
        `_relax_semantic_floors(rooms, edges, entrance)` builds the same
        adjacency `_assign_elevation` uses and reuses the proven
        `_relax_elevation` clamp (no random rises). The sink CHARACTER survives
        where the run can carry it (post-fix corr_4 floors still differ: 8.0 /
        8.221 / 11.779) while every corridor stays inside the cap. Did NOT drop
        sink when elevation is off (option (b)) — that would silently discard
        realised content (umbrella P5 wants it kept).

    - **Counterexample 2 — relax loop-exit residual** (the design's "Relax
      conflict midpoint" suspect, exit-tolerance variant; surfaced on the next
      Hypothesis example after fix 1):
      - seed=3600, theme=dungeon, n=12, verticality='dramatic', elevation=True,
        semantic all-empty (`elemental_tint=None`).
      - Failing corridor `corr_2` (`room_6`→`room_9`): `|Δz|=12.3796`,
        `cap=12.3718` — over by 0.0078 (also corr_3/4/7, max overshoot 0.0078).
      - **Root cause:** `_relax_elevation` is a Gauss-Seidel sweep; exiting at
        `moved < 0.01` can leave a room up to ~0.01 off-band on the final pass
        (a neighbour clamped earlier in the same sweep moved after it was read),
        pushing the odd corridor a few thousandths past `run*max_grade + 0.01`.
      - **Fix (design: "Tighten the exit"):** changed the fixpoint exit from
        `moved < 0.01` to `moved < 1e-4`. The cap's own 0.01 tolerance is NOT
        widened.

    - **Files / functions changed** (`generators/layout.py` only; `semantics.py`
      untouched):
      - `LayoutGenerator.generate` — added `elif themed:` branch calling
        `_relax_semantic_floors` when elevation is off.
      - `LayoutGenerator._relax_semantic_floors` — NEW helper.
      - `LayoutGenerator._relax_elevation` — exit tolerance `0.01` → `1e-4`
        (+ docstring).

    - **Verification:**
      - `test_properties_layout.py` green — 100 examples default, 500 thorough
        (incl. `test_elevation_grade_cap`).
      - Counterexample 1 reproduced and confirmed resolved: all 10 corridors of
        seed=1/dungeon/n=10/flat/elevation=False/tint=lava now satisfy the cap
        (worst dz/cap ratio 0.999).
      - **Outdoor TER baseline regression guard:** `tests/test_hygiene.py` →
        `test_outdoor_ter_matches_fork_point` PASSES unchanged (3/3). Outdoor is
        not themed/sink-biased and its floors already converged below 1e-4, so
        the fix did not reach the outdoor path.
      - Full suite `python -m pytest tests/ -q` → **219 passed**, 2 pre-existing
        warnings (starlette `BlockingPortal`, runpy `server.app`).
      - Pinned corridor seeds 1955208177 / 1516796975 / 481893615 are exercised
        by `test_generators.py` + `test_traversability.py` + `test_pipeline.py`
        and remained green in the full suite.

    - **GEOMETRY / LAYOUT CHANGE — 3D pass required (task 18.2(b)).** This fix
      changes dungeon `floor_z` geometry in two regimes:
      1. **themed dungeons with elevation OFF** (any `dungeon_theme` /
         `dungeon_race` / non-None `elemental_tint`) — the new relax pass now
         runs, so sink/raise floors move (previously they didn't). Affected
         conditions, not a fixed seed list: ANY themed box-theme dungeon built
         with elevation off. Representative affected seed: **1** (the recorded
         counterexample, dungeon/n=10/flat/tint=lava).
      2. **any dungeon with elevation ON** — the tighter relax exit (1e-4) nudges
         loop-edge convergence, so floors can shift by < 0.01 from before.
         Representative affected seed: **3600** (dungeon/n=12/dramatic).
      - **Task 18.2(b) must walk the dungeon sections of `docs/ACCEPTANCE.md` on
        the affected seeds (1, 3600) PLUS the standing corridor seeds
        1955208177, 1516796975, 481893615.**
      - **NOT verified in the live 3D viewer by the agent** — structural/
        walkability tests pass (necessary, not sufficient per steering). A human
        must eyeball the themed-sink dungeons and the pinned seeds in 3D.

    - **Deviation from 13.1 step 2 (`@example(...).via("discovered failure")`
      pin):** not added to the test. The parent dispatch was explicit — *do NOT
      edit the 10.5 test to make it pass; only the generator* — and the test is
      green and deterministic (default profile is `derandomize=True`) without
      pins. Both counterexamples are recorded here and in the fix commit message
      `0e3799a`, so the regression history is preserved. If the pins are wanted
      as literal `@example` decorators, that is a one-line-each follow-up that
      does not change behaviour.

    - **Commits:** generator fix `0e3799a` (`generators/layout.py`); property
      test `d47111a` (`tests/test_properties_layout.py`).

- [ ] 14. Residue guards
  - [x] 14.1 Extend `tests/test_hygiene.py` with the residue guards
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
    - **Done.** Appended 11 residue-guard test functions to `tests/test_hygiene.py`
      (the 4.1 baseline `test_outdoor_ter_matches_fork_point` is untouched). Every
      forbidden token is assembled by string CONCATENATION (`"fbm"+"_field"`,
      `"ski"+"mage"`, `"view"+"er"`, etc.) and this module is excluded from every
      scan, so it never matches its own source even if the exclusion were dropped.
      Tracked `*.py` files are enumerated via `git ls-files '*.py'` (minus
      `tests/test_hygiene.py`). Import checks use AST (not substring) so the prose
      word "viewer" in comments — which legitimately survives in `core/eqg.py`,
      `scripts/measure_corridors.py`, `tests/test_traversability.py` — does NOT
      trip the guard; only a real `import viewer`/`from viewer`/`import flask` or
      `from flask` would. Guards:
      - `test_deleted_field_modules_absent`, `test_no_import_of_deleted_field_modules`
        (AST, absolute + relative incl. `from .sdf`), `test_no_cave_pipeline_tokens`
        (`fbm_field`/`_build_organic`/`_CAVE_THEMES`).
      - `test_noise_keeps_value_noise_and_drops_sdf` (AST: `_value_noise_3d` still
        defined, no `sdf` import).
      - `test_layout_tables_have_no_cave_key` (AST-parses the `theme_palettes`
        material table and `colors` light table in `layout.py`; asserts keys ==
        `{"dungeon","city","outdoor"}`, no `"cave"`).
      - `test_no_cave_only_dependency_tokens` (`import/from skimage`,
        `fast_simplification`, `simplify_quadric_decimation`).
      - `test_theme_surface_is_three` (imports `ai.schema`/`server.app` and reads
        `VALID_THEMES`; regex-parses `main.py` `--theme choices=[...]` and
        `web/index.html` `<option value="...">`; all four sets ==
        `{"dungeon","city","outdoor"}`).
      - `test_viewer_directory_absent`, `test_no_viewer_or_flask_imports`
        (flask/viewer imports via AST + `args.preview` token scan).
      - `test_test_cave_module_absent`, `test_requirements_clean_and_pins_hypothesis`
        (no `scikit-image`/`fast-simplification`/`flask` dep line; pins `hypothesis==`).
    - **All guards PASS as-is — no residue found.** Verified the real tree first:
      every deleted module absent, no forbidden token in any tracked `.py`, all
      four theme surfaces equal the three Defined_Themes, both layout tables
      cave-free, `requirements.txt` clean and pinning `hypothesis==6.170.5`. The
      only `viewer`-substring hits are the English word in three comments (not
      imports), correctly ignored by the AST import guard.
    - **Verification:** `.\.venv\Scripts\python.exe -m pytest tests/test_hygiene.py -q`
      → **14 passed** (3 baseline + 11 guards), 2.78 s. Full suite
      `python -m pytest tests/ -q` → **240 passed**, 2 pre-existing unrelated
      warnings (starlette `BlockingPortal` deprecation, runpy `server.app`), no
      `PytestUnknownMarkWarning`, 51.22 s.
    - **Commits:** `e6c7ae6` (code: `tests/test_hygiene.py`, 344 insertions),
      tracker line in the follow-up commit.

- [x] 15. Checkpoint: Property_Suite complete
  - Run `python -m pytest tests/ -q`. The suite must be green with the Property_Suite included and no unknown-marker warning. Commit each property module separately. Ask the user if questions arise.
  - **Done.** Working tree clean at checkpoint. HEAD `8dc15a5`; 72 commits since
    fork-point (`git rev-list --count 99d346a..HEAD` = 72). Property modules
    9–12 committed separately, counterexample fix 13.1 landed, residue guards
    14.1 landed.
    - **Suite GREEN: 240 passed** (2 warnings, 49.44 s). The two warnings are a
      starlette `anyio.abc.BlockingPortal` deprecation and the runpy `server.app`
      warning from `test_main_binds_host_and_port` — neither is a
      `PytestUnknownMarkWarning`.
    - **Property_Suite collected (per module, `--co -q`):**
      `tests/test_properties_core.py` = 3, `tests/test_properties_layout.py` = 8,
      `tests/test_properties_build.py` = 5, `tests/test_properties_pipeline.py`
      = 5 (21 property tests total). All four modules present and collected.
    - **No unknown-marker warning:**
      `pytest tests/ --co -q -W error::pytest.PytestUnknownMarkWarning` exits 0,
      so collection raises no `PytestUnknownMarkWarning` (the `slow` marker is
      registered in `pytest.ini`).

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
