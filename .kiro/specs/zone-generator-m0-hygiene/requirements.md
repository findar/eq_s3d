# Requirements Document

## Introduction

M0 — Hygiene + PBT harness. First milestone spec under the umbrella spec
`zone-generator` (`.kiro/specs/zone-generator/requirements.md` and `design.md`).
It owns only its slice of the umbrella Delivery Plan (M0 row) and cites the
umbrella instead of restating it: "Req X.Y" below means zone-generator
Requirement X.Y, "Pn" means umbrella design Correctness Property n.

M0 delivers four things:

1. A Hypothesis property suite proving the invariants that exist **today**
   (P1 for dungeon, P2–P16), scoped to the current code. Later milestones widen
   the same properties (more themes, districts, new fields, edits).
2. The separate cave pipeline and the `cave` theme deleted, with their cave-only
   dependencies (`scikit-image`, `fast-simplification`). Cave returns later as a
   dungeon archetype (umbrella M3), and an organic "natural" geometry style for
   dungeons comes in umbrella M5.
3. The legacy Flask viewer and `flask` removed.
4. Local server hardening: loopback bind by default and CORS restricted to known
   local origins (Req 30.1, 30.2).

No geometry change is intended for dungeon, city or outdoor. If a property finds
a real bug, the fix is made at the root cause, which may change geometry for
some seeds (see Exit criteria).

As-built facts this spec was checked against (current `master`): `requirements.txt`
pins `scikit-image==0.26.0`, `fast-simplification==0.1.11` and `flask==3.1.0`
and has no Hypothesis; there is no `pytest.ini`; `server/app.py` uses
`allow_origins=["*"]` and its `__main__` binds `0.0.0.0:8000`; the cave path is
`ZoneBuilder._build_organic` (selected by `_CAVE_THEMES`) over
`generators/field/{cave,features,mesh,sdf}.py` and `noise.py::fbm_field`, with
`noise.py` importing `FieldGrid` from `sdf`; `tests/test_cave.py` tests only
that path and is deleted by M0; `main.py preview` and `generate --preview`
import `viewer/serve.py` (Flask).

## Glossary

Umbrella glossary terms are used unchanged, notably Zone_Generator, Server,
Web_App, Local_Frontend_Origin, CLI, Planner, Zone_Plan, Zone_Spec,
Layout_Generator, Room_Graph, Pacing_Role, Gate, Advisory_Data, Box_Backend,
Terrain_Backend, Zone_Builder, Raw_Build, Pipeline, Accepted_Build,
Traversal_Validator, Pinned_Seed, Fresh_Seed, Gated_Theme and Reference_Machine.
M0-specific terms:

- **Property_Suite**: the Hypothesis-based tests added by M0, in `tests/test_properties_core.py`, `tests/test_properties_layout.py`, `tests/test_properties_build.py` and `tests/test_properties_pipeline.py`.
- **Default_Run**: `python -m pytest tests/ -q` with no marker selection and the Default_Profile.
- **Default_Profile**: the Hypothesis settings profile used by the Default_Run; derandomized (fixed seed derivation) so that Default_Run pass/fail is reproducible.
- **Thorough_Profile**: a registered, randomized Hypothesis settings profile named `thorough`, selected with `--hypothesis-profile=thorough`, that raises example counts above the Default_Profile.
- **Slow_Marker**: the registered pytest marker `slow`, carried by every build-level property test so it can be deselected with `-m "not slow"`.
- **Property_Docstring**: the docstring of a Property_Suite test, naming its umbrella property number(s) and the umbrella requirement ids it validates.
- **Regression_Example**: an `@example(...)` decorator on a property test that pins a counterexample Hypothesis found, or a required boundary input.
- **M0_Box_Themes**: the themes built by the Box_Backend today: `dungeon` and `city`.
- **Cave_Pipeline**: the separate cave geometry path deleted by M0: `generators/field/cave.py`, `generators/field/features.py`, `generators/field/mesh.py`, `generators/field/sdf.py`, `fbm_field` in `generators/field/noise.py`, `ZoneBuilder._build_organic` and `_CAVE_THEMES`.
- **Cave_Words**: the prompt words "cave", "cavern", "grotto", "underground" and "tunnel".
- **Defined_Themes**: exactly `dungeon`, `city` and `outdoor`.
- **Legacy_Viewer**: the Flask preview server `viewer/serve.py` (with `viewer/index.html`) and the CLI entry points that launch it (`main.py preview`, `main.py generate --preview`).
- **Web_App_Origins**: the Server's own origins (`http://127.0.0.1:8000`, `http://localhost:8000`) plus the Local_Frontend_Origin (`http://localhost:5173`, `http://127.0.0.1:5173`).

## Requirements

### Requirement 1: Property-test harness

**User Story:** As a developer, I want a pinned property-testing harness with a fast default and a thorough mode, so that invariants are proven on every run without slowing the suite down.

Implements: zone-generator Delivery Plan M0 (harness); supports every property below.

#### Acceptance Criteria

1. THE Zone_Generator SHALL list Hypothesis in `requirements.txt` pinned to one exact version (`==`).
2. THE Zone_Generator SHALL register the Slow_Marker as the only custom marker in a `pytest.ini` at the repository root, with no marker-deselecting `addopts`, so that the Default_Run emits no unknown-marker warning.
3. THE Zone_Generator SHALL register the Thorough_Profile, randomized, so that for every Property_Suite test the maximum example count under the Thorough_Profile is at least 5 times that test's maximum example count under the Default_Profile.
4. THE Default_Run SHALL complete on the Reference_Machine in no more than 60 seconds beyond the Default_Run on the commit before M0 (baseline ≈ 85 s), each figure being the median wall-clock time of 3 consecutive runs with an empty `.hypothesis/` example database.
5. THE Property_Suite SHALL give every build-level property test (one that runs the Zone_Builder or the Pipeline) the Slow_Marker, `deadline=None` and a maximum example count between 10 and 25 inclusive under the Default_Profile.
6. THE Property_Suite SHALL give every test a Property_Docstring.
7. IF Hypothesis finds a counterexample to a property during M0, THEN THE Property_Suite SHALL carry that input as a Regression_Example on the same property test, with the assertion kept as the property stated in the umbrella design (scoped per this spec) and not narrowed to exclude the Regression_Example.
8. THE Zone_Generator SHALL list Hypothesis's local example database directory (`.hypothesis/`) in `.gitignore`.
9. THE Zone_Generator SHALL register the Default_Profile as derandomized, so that two Default_Runs on the same commit evaluate the same examples.

### Requirement 2: Format and IR round-trip properties

**User Story:** As a developer, I want every reader/writer and the Zone_Spec IR proven to round-trip, so that what the tool writes is exactly what it later reads.

Implements: zone-generator Req 11.1, 11.2, 11.3, 11.4. Properties: P11, P13, P14, P15.

#### Acceptance Criteria

1. FOR ALL lists of 0–2000 entries whose names are 1–64 printable ASCII characters (0x20–0x7E) excluding path separators and distinct case-insensitively, and whose payloads are 0–24,577 bytes (covering empty, exactly 8192-byte and multi-chunk payloads), plus at least one Regression_Example whose name block exceeds 35,000 bytes, THE Property_Suite SHALL assert that reading back a written PFS archive yields a name-to-bytes map identical to the input, with case-preserved names, byte-identical payloads and no extra entries (P13, in `test_properties_core.py`).
2. FOR ALL names of 1–64 printable ASCII characters, THE Property_Suite SHALL assert that the PFS filename CRC equals an independent MSB-first CRC (polynomial 0x04C11DB7, initial value 0, no final XOR) over the case-preserved name bytes followed by one NUL byte, that the PFS CRC differs from `zlib.crc32` for at least one generated name, and that the PFS CRC differs between a name and its case-swapped form for at least one generated name containing a letter (P14, in `test_properties_core.py`).
3. FOR ALL TER and ZON files the Zone_Builder writes for M0_Box_Themes, seeds 0–2,147,483,647 and room counts 2–12, THE Property_Suite SHALL assert that reading back the TER yields equal vertices, polygons (indices, material index, flags) and materials (name, shader, properties), and that reading back the ZON yields equal objects, lights and regions, with every float bit-equal after conversion to IEEE-754 single precision and every integer and string exact (P15, in `test_properties_core.py`).
4. FOR ALL Zone_Specs the Layout_Generator produces for seeds 0–2,147,483,647, themes dungeon, city and outdoor, room counts 1–30, locks 0–5 and elevation on or off, THE Property_Suite SHALL assert that serialising to JSON and loading back yields a dictionary equal to the original Zone_Spec's serialised dictionary field for field, with exact float equality, over every field the Zone_Spec serialises today (P11, in `test_properties_layout.py`).

### Requirement 3: Layout invariant properties

**User Story:** As a zone author, I want layout guarantees (connectivity, roles, solvable locks, walkable grades, flush openings, plan normalisation) proven over many seeds, so that rare seeds cannot produce a broken layout.

Implements: zone-generator Req 2.3, 2.4, 2.5, 2.8, 5.1, 5.2, 5.4, 21.1, 21.2, 21.5. Properties: P3, P4, P6, P7, P12.

#### Acceptance Criteria

1. FOR ALL seeds 0–2,147,483,647, room counts 1–30 and M0_Box_Themes, with each semantic-labelling input (dungeon theme, race, tint) either empty or drawn from its vocabulary, THE Property_Suite SHALL assert that the Room_Graph is connected with exactly the requested room count, that exactly one room has Pacing_Role `entrance` and, for 2 or more rooms, that exactly one room has Pacing_Role `climax` and that room is not the entrance (P3 with a single District, in `test_properties_layout.py`).
2. FOR ALL seeds, room counts 3–30, lock counts 1–5 and M0_Box_Themes, with semantic-labelling inputs as in criterion 1, THE Property_Suite SHALL assert that the layout has at least 1 Gate and no more Gates than requested, and that a simulated player starting in the entrance, who crosses ungated corridors freely and a gated corridor only after visiting its key room, visits every room (P4 with a single District, in `test_properties_layout.py`).
3. FOR ALL seeds, room counts 2–30, verticality values in {flat, moderate, dramatic}, elevation on or off and M0_Box_Themes, with semantic-labelling inputs as in criterion 1, THE Property_Suite SHALL assert `|from_z − to_z| ≤ run × 0.5 + 0.01` for every corridor, tree and loop edges alike, with run as defined in umbrella Req 5.4 (P6, in `test_properties_layout.py`).
4. FOR ALL seeds, room counts 2–12 and M0_Box_Themes, THE Property_Suite SHALL assert that every corridor's `from_z` and `to_z` equal the `floor_z` of its `from_room` and `to_room`, and that the Box_Backend walkable floor directly under each opening point `(from_x, from_y)` and `(to_x, to_y)` lies within 0.01 units of that room's `floor_z` (P7, in `test_properties_layout.py`).
5. FOR ALL dictionaries holding any subset of today's Zone_Plan fields plus zero or more unknown keys, with correctly typed values (integers any integer including negative and out-of-range values, booleans any boolean, vocabulary and free-text fields any string, `regions` any list of strings), THE Property_Suite SHALL assert that `ZonePlan.from_dict` yields every field inside its domain per umbrella Req 2.3, 2.4 and 2.8 and that a second `validate()` returns an equal Zone_Plan (P12 without the controls path, in `test_properties_layout.py`).
6. THE Property_Suite SHALL include in the criterion 2 test at least one Regression_Example where gate placement takes the key-room fallback (every non-entrance room outside the gated subtree is already behind another Gate, for example 3 rooms whose entrance has two leaf children with locks ≥ 2), and the test SHALL assert that the fallback ran for that example.
7. THE Property_Suite SHALL include at least one example where elevation relaxation takes the conflict fallback (neighbour walkable Z-bands do not intersect), asserting that the fallback ran and that the criterion 3 bound holds after relaxation; IF no seed reaches that branch through generation, THEN the example SHALL drive the relaxation step directly on a constructed room set, and a bound failure there SHALL be fixed at the root of the fallback.

Note (criterion 3): known suspect — semantic room-type `sink` offsets (−30 to +8 units × race scale) apply to `floor_z` even when elevation is off, where relaxation does not run. If this property fails there, the fix is made at the root (for example, suppress or relax `sink` when elevation is off), never by excluding semantic inputs from the strategy. A geometry-changing fix triggers the 3D pass in Exit criteria.

### Requirement 4: Build-level properties

**User Story:** As a zone author, I want walkability, ramp subdivision, advisory isolation and seed determinism proven on real builds, so that the guarantees hold on the bytes the client loads.

Implements: zone-generator Req 4.3 (dungeon), 5.3, 26.1 (Zone_Spec, TER, ZON), 27.1, 27.2. Properties: P1, P5, P8, P9.

#### Acceptance Criteria

1. FOR ALL seeds 0–2,147,483,647, room counts 2–12 and elevation on or off, THE Property_Suite SHALL assert that a dungeon Raw_Build (no Pipeline retry) passes the Traversal_Validator, counting any Zone_Builder exception as a property failure rather than a discarded example (P1 for dungeon, in `test_properties_build.py`).
2. FOR ALL Box_Backend builds of M0_Box_Themes with elevation on, seeds 0–2,147,483,647 and room counts 2–12, THE Property_Suite SHALL assert that every sloped corridor floor segment in the written TER rises at most 2.51 units from its low edge to its high edge (2.5 units plus 0.01 tolerance) (P8, in `test_properties_build.py`).
3. FOR ALL M0_Box_Themes, seeds and room counts 3–12, THE Property_Suite SHALL assert that the TER and ZON for a Zone_Plan with locks 1–5 are byte-identical to the TER and ZON for the same Zone_Plan and seed with locks 0 (P5 locks, in `test_properties_build.py`).
4. FOR ALL themes dungeon, city and outdoor, room counts 2–12, locks 0–5 and elevation on or off, THE Property_Suite SHALL assert that two Raw_Build runs (Layout_Generator plus Zone_Builder, no Pipeline) with the same Zone_Plan, Pinned_Seed and zone name, writing to two distinct output directories, produce equal Zone_Spec dictionaries and byte-identical TER and ZON (P9 without map artifacts, in `test_properties_build.py`).
5. FOR ALL Zone_Specs built for M0_Box_Themes, seeds and room counts 3–12, THE Property_Suite SHALL assert that the TER is byte-identical to the TER built from the same Zone_Spec with every Advisory_Data field present today cleared (Pacing_Roles, depth, semantic labels, Gates, `prop_hints`, `encounter_intent`, `boss`) (P5 advisory clearing, in `test_properties_build.py`).
6. THE Property_Suite SHALL use strategies for criterion 2 that produce at least one corridor whose total rise exceeds 2.5 units, so that ramp subdivision is exercised.

Note (criterion 2): elevation is ramp-only today (no stair corridors are generated), so P8 has no stair case in M0.

### Requirement 5: Pipeline properties

**User Story:** As a zone author, I want the validated-generation loop, fresh seeding and the no-API default proven, so that every returned zone is gated and the tool runs with zero keys.

Implements: zone-generator Req 4.4 (traversal), 4.5 (traversal), 4.6 (traversal), 26.2, 26.4, 28.1 (Planner), 28.2 (prompt and CLI generation), 28.4. Properties: P2, P10, P16.

#### Acceptance Criteria

1. FOR ALL dungeon `generate_validated` calls with a Fresh_Seed and `max_attempts` 1–8 that return, THE Property_Suite SHALL assert that the returned build passed the Traversal_Validator, that the number of builds run is between 1 and `max_attempts`, and that the returned seed equals the seed of the final build (P2, in `test_properties_pipeline.py`).
2. FOR ALL Pinned_Seeds 0–2,147,483,647 whose dungeon Raw_Build is forced to fail the Traversal_Validator (through an injected failing agent model or spec factory), THE Property_Suite SHALL assert that `generate_validated` raises `GenerationFailed` with `pinned=True` and `attempts == 1`, the single recorded failure carrying the pinned seed (P2, in `test_properties_pipeline.py`).
3. FOR ALL sequences of 3–10 unpinned `generate_validated` calls with identical inputs and no caller-supplied `rng`, THE Property_Suite SHALL assert that every drawn seed lies in 0–2,147,483,647 and that the drawn seeds are not all equal (P10, in `test_properties_pipeline.py`).
4. WHILE `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, every AI-texture key and the `EQ_S3D_PLANNER` override are unset and outbound socket connections are blocked, THE Property_Suite SHALL assert that `get_planner().name == "rule"` and that the active texture provider is procedural (P16, in `test_properties_pipeline.py`).
5. WHILE the state of criterion 4 holds, THE Property_Suite SHALL assert that a prompt through the Server and control options through the CLI each produce an Accepted_Build and that no outbound socket connection is attempted (P16, in `test_properties_pipeline.py`).
6. FOR ALL unpinned dungeon `generate_validated` calls whose every Raw_Build is forced to fail, with `max_attempts` 1–8 and `timeout_s` large enough never to bind, THE Property_Suite SHALL assert that `GenerationFailed` is raised with `pinned=False`, `timed_out=False` and `attempts == max_attempts` (P2 exhaustion, in `test_properties_pipeline.py`).

Note: criteria 1, 2, 5 and 6 are build-level and carry the Slow_Marker per Requirement 1.5. Pipeline behaviour for ungated themes stays with the umbrella spec (out of scope for M0).

### Requirement 6: Remove the cave pipeline and the cave theme

**User Story:** As a developer, I want the separate cave pipeline and the `cave` theme gone, so that every zone flows through the shared layout and backends and a passing suite no longer vouches for shelved geometry.

Implements: zone-generator design Decision 17 / Delivery Plan M0 (cave deletion); umbrella Req 2.8, 3.1, 7 (no cave theme or separate pipeline).

#### Acceptance Criteria

1. THE Zone_Generator SHALL contain no Cave_Pipeline: no `generators/field/cave.py`, `generators/field/features.py`, `generators/field/mesh.py` or `generators/field/sdf.py` file, no `fbm_field` in `generators/field/noise.py`, no `ZoneBuilder._build_organic`, no `_CAVE_THEMES`, and no import of any of these anywhere in the source.
2. THE Zone_Generator SHALL keep `_value_noise_3d` in `generators/field/noise.py`, with no import of `sdf` in that module.
3. FOR EACH seed in a fixed set of outdoor seeds, THE Terrain_Backend SHALL write a TER byte-identical to the TER written for the same Zone_Spec at the M0 fork-point commit, with the baseline hashes recorded in the test.
4. THE Zone_Generator SHALL define exactly the Defined_Themes in the Planner schema, the Server, the CLI `--theme` choices and the Web_App theme list, with no layout material table or light table keyed by `cave`.
5. WHEN a prompt contains one or more Cave_Words and the prompt's outdoor or city theme words do not tie or outscore them, THE Planner SHALL produce a Zone_Plan with theme `dungeon` (interim: no forced archetype until the cave archetype lands in umbrella M3).
6. WHEN a Zone_Plan dictionary or Zone_Spec dictionary carrying theme `cave` is loaded, THE Zone_Generator SHALL normalise the theme to `dungeon`.
7. IF a controls-mode generate request names theme `cave`, THEN THE Server SHALL return a 4xx validation error listing the Defined_Themes before any build starts.
8. IF the CLI is invoked with `--theme cave`, THEN THE CLI SHALL exit with status 2 before any build starts.
9. WHEN a prompt containing one or more Cave_Words is generated through the Pipeline, THE Pipeline SHALL return an Accepted_Build that passed the Traversal_Validator.
10. THE Zone_Generator test suite SHALL contain no test of the Cave_Pipeline: `tests/test_cave.py` is removed and every cave-theme test elsewhere is removed or retargeted to `dungeon`.
11. THE Zone_Generator SHALL keep `styles/cave.json` and the analyzer's cave reference-zone list unchanged, as inputs to the future cave archetype.

### Requirement 7: Remove cave-only dependencies

**User Story:** As a developer, I want the dependencies that only the cave pipeline used gone, so that the environment matches the code and nobody re-enables a step that collapses walkable floors.

Implements: zone-generator design Dependencies residue (`scikit-image`, `fast-simplification`).

#### Acceptance Criteria

1. THE Zone_Generator SHALL list no `fast-simplification` entry and no `scikit-image` entry in `requirements.txt`.
2. THE Zone_Generator SHALL contain no source file that imports `skimage` or `fast_simplification` or calls trimesh quadric decimation.
3. WHEN the Default_Run executes in an environment without `fast_simplification` and `skimage` installed, THE Zone_Generator test suite SHALL pass with zero failures and zero errors.

### Requirement 8: Legacy viewer decision

**User Story:** As a developer, I want one browser preview path, so that dependencies and docs describe what is actually used.

Implements: zone-generator design Dependencies residue (`flask`). Decision: remove (user-confirmed; verified that only main.py's preview entry points use it).

#### Acceptance Criteria

1. THE Zone_Generator SHALL contain no Legacy_Viewer: no `viewer/` directory, no `preview` CLI subcommand, no `--preview` option on `main.py generate`, no module importing `flask` or the viewer package, and no code reading `args.preview`.
2. THE Zone_Generator SHALL list no `flask` entry in `requirements.txt`.
3. IF the CLI is invoked with the `preview` subcommand, THEN THE CLI SHALL exit with status 2 and an argument error naming `preview` as an invalid choice, opening no HTTP listener and creating or modifying no file in the output directory.
4. IF the CLI is invoked as `generate --preview`, THEN THE CLI SHALL exit with status 2 before any build, with an argument error naming `--preview` as unrecognized, opening no HTTP listener and creating or modifying no file in the output directory.
5. WHEN the CLI is invoked with `--help` or `generate --help`, THE CLI SHALL print help text that lists no preview subcommand and no preview option.
6. THE Zone_Generator SHALL contain no instruction, command or URL in `README.md`, `docs/` or the `main.py` module docstring that launches the Legacy_Viewer.

Note: no post-generate hint replacing the preview option is printed.

### Requirement 9: Local server binding and CORS

**User Story:** As the single local user, I want the server to listen only on my machine and to grant cross-origin access only to my own frontend, so that running it does not expose my machine.

Implements: zone-generator Req 30.1, 30.2.

#### Acceptance Criteria

1. WHEN the Server is started through `python -m server.app`, THE Server SHALL listen on 127.0.0.1 port 8000 and accept no connections on any non-loopback interface address.
2. WHEN a non-preflight request carries an `Origin` header equal to one of the Web_App_Origins, THE Server SHALL include in the response an `Access-Control-Allow-Origin` header byte-identical to that `Origin`.
3. IF a request carries an `Origin` header outside the Web_App_Origins, THEN THE Server SHALL omit every `Access-Control-Allow-*` header from the response (browser enforcement is sufficient; no special status code is required).
4. THE Server SHALL send no `Access-Control-Allow-Origin: *` header in any response.
5. WHILE the frontend is served on the Local_Frontend_Origin and proxies API calls to 127.0.0.1:8000, WHEN the Web_App requests a generation and loads the resulting preview, THE Server SHALL answer each request with a success response and no CORS rejection.
6. WHEN a CORS preflight request from one of the Web_App_Origins requests a method and headers the Web_App uses, THE Server SHALL return a success response with `Access-Control-Allow-Origin` equal to that origin and `Access-Control-Allow-Methods` and `Access-Control-Allow-Headers` covering the requested method and headers.
7. WHEN a request carries no `Origin` header, THE Server SHALL process the request normally and include no `Access-Control-Allow-*` header in the response.

Note: `http://localhost:8000` stays in the Web_App_Origins even though a 127.0.0.1-only bind (criterion 1) does not answer `::1`; browsers fall back to IPv4 when `localhost` resolves to `::1` first. The human smoke pass in Exit criteria confirms this.

## Delivery and process (not system behaviour)

- Hypothesis is added in a `-Venv` worktree (`requirements.txt` is a cross-branch hotspot); the same branch drops `fast-simplification`, `scikit-image` and `flask`.
- Agent re-pointing: `.kiro/agents/{orchestrator,task-author,task-worker,task-reviewer,task-readiness}.json` move from `tasks/<id>.md` / `tasks/_TEMPLATE.md` to `.kiro/specs/<feature>/tasks.md`, keeping the single-writer rule and the "eyeball it in 3D" bar; the orchestrator `fs_write` allow-list gains `.kiro/specs/**`. The currently uncommitted `orchestrator.json` change is committed or discarded first; the stray local `.kiro/agents/*.json.bak` files (gitignored) are deleted.
- Steering: `.kiro/steering/project.md` describes Kiro specs replacing the `tasks/` board for new work and drops the cave theme from the backend list; `.kiro/steering/lessons-learned.md` cave notes are updated to say the cave pipeline was removed (cave becomes a dungeon archetype in umbrella M3; the natural geometry style comes in umbrella M5).
- Docs (M0 may edit): the `docs/ACCEPTANCE.md` cave section is marked retired pending umbrella M5.
- Integration step (MAIN checkout, single writer): reconcile `tasks/README.md` (5 task files missing from the index; `content-layer-dungeon` status mismatch); remove ROADMAP's false claim that a `ZoneSpec.districts` placeholder exists; update the README "organic caves" feature line and the ROADMAP cave items to the archetype/natural-style plan; mark `tasks/cave-backend-refactor.md` absorbed by M0 and `tasks/cave-cavify-dungeon.md` moved to umbrella M5; mark the other absorbed task files per the umbrella "Scope of open task files" table; retire `.kiro/specs/content-layer-districts`.
- Counterexamples are fixed at the root cause, never by weakening a property; the known suspect paths are the gate key-room fallback (P4), the `_relax_elevation` conflict fallback (P6) and semantic `sink` offsets with elevation off (P6).

## Exit criteria

- The Default_Run is green and the Property_Suite is green (any counterexample fixed at root and pinned as a Regression_Example).
- One full run under the Thorough_Profile passes at M0 exit, recorded in this spec's `tasks.md`.
- The Cave_Pipeline, the `cave` theme and the cave-only dependencies are gone, and the Default_Run passes without `skimage` or `fast_simplification` installed.
- A prompt with Cave_Words yields an Accepted_Build: a walkable dungeon.
- The agents run one spec task from this spec's `tasks.md` end to end.
- Human pass (`docs/ACCEPTANCE.md`) is light: (a) smoke the Web_App on the frontend port and on port 8000 after the CORS change — generate one zone and load it; (b) only if a root-cause fix changed layout or geometry, walk the dungeon sections of ACCEPTANCE on the affected seeds plus the pinned corridor seeds 1955208177, 1516796975 and 481893615, and note that 3D verification was done.

## Out of scope (later milestones)

P1 for city/outdoor (M1); the cave dungeon archetype (umbrella M3); the organic "natural" dungeon geometry style (umbrella M5); P2 format half and P17 time budgets; P2 Pipeline behaviour for ungated themes (umbrella); P3/P4 with districts (M3); P11 new fields per Req 11.5 (M1+); P12 controls path (M1); P12 wrong-typed Zone_Plan values such as a non-numeric `room_count` (umbrella Req 2.9, 2.10; M1); P9 map artifacts (M2); P16 edit/undo (M4); Req 30.3–30.13 tokens and sessions (M4), including any non-loopback bind option.

## Open questions

None.

## Traceability

| M0 requirement | Umbrella requirement(s) | Property | Test module |
|----------------|-------------------------|----------|-------------|
| 1 Harness (1.1–1.9) | Delivery Plan M0 | (all below) | `pytest.ini`, all Property_Suite modules |
| 2.1 | 11.1 | P13 | `test_properties_core.py` |
| 2.2 | 11.2 | P14 | `test_properties_core.py` |
| 2.3 | 11.3 | P15 | `test_properties_core.py` |
| 2.4 | 11.4 | P11 | `test_properties_layout.py` |
| 3.1 | 21.1, 21.2 | P3 | `test_properties_layout.py` |
| 3.2, 3.6 | 21.5 | P4 | `test_properties_layout.py` |
| 3.3, 3.7 | 5.4 | P6 | `test_properties_layout.py` |
| 3.4 | 5.1, 5.2 | P7 | `test_properties_layout.py` |
| 3.5 | 2.3, 2.4, 2.5, 2.8 | P12 | `test_properties_layout.py` |
| 4.1 | 4.3 | P1 (dungeon) | `test_properties_build.py` |
| 4.2, 4.6 | 5.3 | P8 | `test_properties_build.py` |
| 4.3 | 27.1, 27.2 | P5 (locks) | `test_properties_build.py` |
| 4.4 | 26.1 | P9 | `test_properties_build.py` |
| 4.5 | 27.1, 27.2 | P5 (advisory clearing) | `test_properties_build.py` |
| 5.1, 5.2, 5.6 | 4.4, 4.5, 4.6, 26.4 | P2 | `test_properties_pipeline.py` |
| 5.3 | 26.2 | P10 | `test_properties_pipeline.py` |
| 5.4, 5.5 | 28.1, 28.2, 28.4 | P16 | `test_properties_pipeline.py` |
| 6.1–6.11 Cave pipeline + theme removal | 2.8, 3.1, 7; Decision 17 | — | `test_properties_layout.py`, `tests/test_pipeline.py`, `tests/test_hygiene.py` |
| 7.1–7.3 Cave-only dependencies | Dependencies residue | — | `tests/test_hygiene.py` |
| 8.1–8.6 Legacy viewer | Dependencies | — | `tests/test_pipeline.py` (CLI) |
| 9.1–9.7 Bind + CORS | 30.1, 30.2 | — | `tests/test_pipeline.py` or a server test |
