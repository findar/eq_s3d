# Requirements Document

## Introduction

eq_s3d generates EverQuest zones for the RoF2 client from a natural-language
prompt or an explicit set of controls, previews them in a browser, and hands
back files a user can install by taking over an existing zone short name. This
is the **umbrella** requirements document for the whole system. It pairs with
`design.md` (the target design) and has no `tasks.md`.

Implementation is split into per-milestone specs (M0–M6 from the design's
Delivery plan, e.g. `zone-generator-m0-hygiene`). Each milestone spec cites the
requirement IDs it implements ("Implements zone-generator Req 4.3") and owns its
own tasks. Requirements here describe the system, not the order it is built in;
the traceability table at the end maps each requirement to its pillar,
milestone and correctness properties.

Requirements are grouped by pillar:

- P-A Web app with input controls — Requirements 1–3
- P-B Traversable — Requirements 4–7
- P-C RoF2-usable format — Requirements 8–11
- P-D True-layout artifacts — Requirements 12–14
- P-E EverQuest look and feel — Requirements 15–17 and 33 (the `cave` Purpose, which also serves P-G)
- P-F Iterative feedback — Requirements 18–20
- P-G Engaging every time — Requirements 21–25
- Cross-cutting — Requirements 26–32

Caves are not a zone type or a separate geometry pipeline: a cave is the `cave`
Purpose of a `dungeon` (Requirement 33), and the organic look is the optional
Natural_Style applied to a dungeon's Box_Backend output (Requirement 7).

Vocabulary rule: every descriptive axis below (Zone_Type, Enclosure, Purpose,
Builder, Inhabitants, Condition, Element, Room_Type) is a separate field with a
closed, normalised value list. The bare word "theme" is never a field name; it
may appear only as a UI label. Legacy names (`theme`, `outdoor`, `dungeon_theme`,
`dungeon_race`, `elemental_tint`, `semantic_type`, `room_theme`, `district_theme`)
are accepted on load and mapped per Requirement 11.10; design decision 19 records
the vocabulary and the milestone in which each rename lands.

The delivery model (how milestone specs relate to this one) is a process
constraint, not system behaviour, and is recorded in its own short section after
the requirements.

## Glossary

- **Zone_Generator**: the eq_s3d system as a whole (planner, layout, backends, pipeline, analyzers, server, web app, CLI).
- **Web_App**: the browser frontend (3D viewer, prompt bar, Controls panel, short-name picker, Artifacts panel, Feedback panel, metrics panel).
- **Server**: the local HTTP backend serving `/api/*`.
- **Local_Frontend_Origin**: the configured origin of the frontend build or preview served locally (default: the frontend's local port on 127.0.0.1/localhost).
- **CLI**: the `main.py` command-line entry point; it has no prompt mode (controls only).
- **Planner**: the component that turns a prompt or a control set into a Zone_Plan; rule-based by default, LLM-backed when a key is configured.
- **Zone_Plan**: the small declarative plan (zone type, room count, size, verticality, locks, topology, district switch and proposals, purpose, builder, inhabitants, condition, element, Target_Shortname, …) produced by the Planner.
- **Zone_Spec**: the intermediate representation of a zone (zone type, Style_Profile, geometry style, rooms, corridors, lights, regions, gates, districts, materials, safe point, seed, shortname); everything downstream consumes it.
- **Layout_Generator**: the component that expands a Zone_Plan into a Zone_Spec (TinyKeep layout, topology, pacing, districts, semantics, elevation, corridors, gating).
- **Room_Graph**: the graph whose nodes are Zone_Spec rooms and whose edges are corridors (`from_room`/`to_room`).
- **Pacing_Role**: a room label in {entrance, hub, deadend, climax, standard} derived from the Room_Graph.
- **District**: a contiguous group of rooms (comparable to a WoW dungeon wing) sharing a Purpose, palette, light mood and one climax; a District may override the zone's Purpose, Condition, Inhabitants and Element.
- **Threshold**: the single corridor joining two adjacent Districts.
- **Gate**: an advisory lock on a corridor together with the room holding its key; realised as an EQEmu `doors` row, never as geometry.
- **Advisory_Data**: Pacing_Roles, graph depth, Room_Type labels, District metadata, Threshold flags, Gates, suggestion fields (`prop_hints`, `encounter_intent`, `boss`) and all reports (quality, conformance, format). `room_purpose` is a realised content-layer field, not Advisory_Data.
- **Zone_Type**: the zone-level selector of a Zone_Plan and Zone_Spec (field `zone_type`; legacy key `theme`); one of Defined_Zone_Types. It selects the Geometry_Backend, the scale and Style_Profile and, from M6, the EQ `ztype`.
- **Defined_Zone_Types**: the Zone_Type vocabulary of the Zone_Generator: `dungeon`, `city` and `wilderness` (legacy value `outdoor` reads as `wilderness`). Any other Zone_Type name (including the retired `cave`) is undefined.
- **Enclosure**: whether a zone is `indoor` or `outdoor` (sky, levitation and outdoor casting); derived from the Zone_Type (dungeon and city → `indoor`, wilderness → `outdoor`) until set independently. "Outdoor" refers only to Enclosure, never to a Zone_Type.
- **Purpose**: the content-layer function of a Zone_Plan or District (field `purpose`; legacy `dungeon_theme`, formerly "Archetype"), for example `fortress`, `temple`, `tomb`, `mine`, `warren`, `wizard_tower`, `sewer`, `vault`, `cave`; supplies Room_Types, palette, light mood and regions; `fortress` is the default.
- **Builder**: who built the place (field `builder`; legacy `dungeon_race` scale half); sets architectural scale.
- **Inhabitants**: who lives there now (field `inhabitants`; legacy `dungeon_race` encounter half); drives encounter suggestions only.
- **Condition**: the zone's current state (field `condition`), from `active`, `abandoned`, `ruined`, `haunted`, `flooded`, `overgrown`, `infested`, `cursed`; at most two values; a Condition may imply an Element (for example `flooded` → `water`).
- **Element**: an elemental overlay (field `element`; legacy `elemental_tint`): `water`, `lava` or `ice`; supplies palette, regions and light mood.
- **Room_Type**: what a room is (field `room_type`; legacy `semantic_type`), for example `barracks` or `flooded_crypt`; assigned from the Purpose.
- **Geometry_Backend**: a mesh generator selected by Zone_Type; one of Box_Backend, Terrain_Backend.
- **Box_Backend**: the architectural box mesh backend (dungeon, city), covering every dungeon Purpose including `cave`.
- **Terrain_Backend**: the heightfield backend (wilderness).
- **Natural_Style**: an optional geometry styling transform applied to a dungeon's validated Box_Backend output (rounded chambers, winding tunnels, rough walls), selected by the Zone_Spec's geometry style (`natural`; default `built`); never a separate zone type or Geometry_Backend.
- **Zone_Builder**: the component that runs the selected Geometry_Backend, textures, ZON and archive assembly and writes the build files.
- **Raw_Build**: a single build of a Zone_Spec without any pipeline retry.
- **Pipeline**: the validated generation loop that draws seeds, builds, runs the gates, retries and writes artifacts for the returned build.
- **Accepted_Build**: the build the Pipeline (or an accepted edit) returns to the caller.
- **Enabled_Zone_Types**: the subset of Defined_Zone_Types the Web_App, Server and CLI offer for generation; fixed per release.
- **Agent_Model**: the EQ-scale player model used for traversal: walkable slope ≤ 40°, step up ≤ 3 units, player height 6 units.
- **Traversal_Validator**: the analyzer that floods the standable faces of the built mesh from the safe point using the Agent_Model. Headroom (ceiling clearance) is outside its scope.
- **Format_Checker**: the Tier-1 RoF2 format validator run on every built `.eqg`.
- **Liquid_Surface_Material**: a material whose polygons form the top surface of a water, lava or slime region; the only materials allowed passable polygons.
- **Known_Zone_List**: the list of RoF2 zone short names with long name, EQEmu zone id and client container type, bundled with the tool and optionally marked against an EQ_Install.
- **Target_Shortname**: the existing RoF2 zone short name a generated zone takes over; every artifact is named for it (written `<short>` below).
- **Default_Target**: the Known_Zone_List entry used when no Target_Shortname is given.
- **EQ_Install**: a local RoF2 client folder configured through `EQ_PATH`; read-only for the Zone_Generator.
- **Output_Directory**: the directory the Zone_Generator writes into (`output/` by default, or the CLI `--output` path).
- **Build_File_Allow_List**: the file extensions the Server serves from a build directory: `.eqg`, `.glb`, `.zone.json`, `.map.svg`, `.png`, `.sql`, `.txt`, `.zip`.
- **Sidecar**: the `<short>.zone.json` advisory file written next to each build.
- **SQL_Exporter**: the Tier-2 component producing `<short>.sql` for an EQEmu server.
- **Outline_Extractor**: the component that extracts wall/ledge polylines and depth bands from a built TER mesh.
- **Depth_Band**: one of at most 4 vertical layers the Outline_Extractor assigns outline polylines to.
- **Main_Band**: the Depth_Band containing the safe point's floor.
- **EQ_Map_Writer**: the component that writes EverQuest in-client map files (`maps/<short>.txt`, `<short>_1..3.txt`).
- **Map_Parser**: the reader for the EQ map line grammar (`L …` lines and `P …` labels).
- **Map_Viewer**: the top-down SVG renderer (`<short>.map.svg`).
- **Style_Profile**: measurements taken from real Classic–PoP zones (`styles/<profile>.json`); a Zone_Spec's Style_Profile is its Zone_Type's profile, or the `cave` profile when its Purpose (single-District zone, or District 0) is `cave`.
- **Conformance_Meter**: the analyzer comparing a built zone's measured metrics with its Zone_Spec's Style_Profile.
- **Texture_Generator**: the component producing diffuse and normal-map textures per material (procedural by default, AI provider optional).
- **Normal_Map**: a tangent-space normal texture stored as a separate DDS in the `.eqg` and referenced by the material property `e_TextureNormal0`.
- **Preview**: the `<short>.glb` file the Web_App renders.
- **Quality_Meter**: the component computing a QualityReport (metrics, failures, out-of-band list, score) from a Zone_Spec.
- **Quality_Bands**: per-metric inclusive target ranges keyed by zone type, topology, room count and verticality.
- **Quality_Degraded**: the state of a returned build whose QualityReport failed; carries a reason in {`quality_degraded`, `quality_outside_bands_pinned`, `edit_outside_bands`}.
- **Out_Of_Band_List**: the list of `{metric, value, lo, hi}` entries for every metric outside its band.
- **Quality_Block**: the single JSON shape `{degraded, reason, score, metrics, out_of_band}` used in HTTP responses and the Sidecar.
- **Session**: server-side, in-memory state for one generated zone: plan, spec, base seed, version history and cursor.
- **Session_Store**: the component that creates, locks, persists and evicts Sessions.
- **Edit_Op**: one structured edit from the edit vocabulary with a room reference and validated parameters.
- **Edit_Interpreter**: the component that turns feedback text into Edit_Ops (rule-based default, LLM optional).
- **Edit_Engine**: the component that applies Edit_Ops to a Zone_Spec and reports the Affected_Set.
- **Affected_Set**: the room ids and corridor ids whose geometry an edit may change.
- **Pinned_Seed**: a seed supplied by the caller, in 0–2,147,483,647; **Fresh_Seed**: a seed drawn by the Zone_Generator, in the same range.
- **Gated_Zone_Type**: a Zone_Type whose builds must pass the Traversal_Validator before the Pipeline returns them.
- **Reference_Machine**: the single local development machine with the Output_Directory on local disk and no concurrent generation; time budgets are measured on it with the AI texture provider and the LLM Planner disabled.

## Requirements

### Requirement 1: Explicit generation modes

**User Story:** As a zone author, I want a description mode and a controls mode with separate Generate actions, so that I always know which input produced the zone.

#### Acceptance Criteria

1. WHEN the user activates "Generate from description", THE Web_App SHALL send a generate request with `mode` = `prompt` carrying the prompt text, the seed and the Target_Shortname.
2. WHEN the user activates "Generate from controls", THE Web_App SHALL send a generate request with `mode` = `controls` carrying the Controls panel values, the seed and the Target_Shortname.
3. WHEN a generate request has `mode` = `prompt`, THE Server SHALL build the Zone_Plan from the prompt text through the Planner, SHALL take only the seed and Target_Shortname from request fields outside the prompt, and SHALL ignore every other control field.
4. WHEN a generate request has `mode` = `controls`, THE Server SHALL build the Zone_Plan from the control values and SHALL ignore any prompt text.
5. WHEN a generate request omits `mode` and carries a non-empty prompt, THE Server SHALL handle the request as `mode` = `prompt`.
6. WHEN a generate request omits `mode` and carries an empty or absent prompt, THE Server SHALL handle the request as `mode` = `controls`, mapping the legacy flat fields (`theme` or `zone_type`, `rooms`, `elevation`, `seed`) to control values.
7. WHEN two generate requests, one in each mode, yield equal Zone_Plans and carry the same Pinned_Seed, THE Server SHALL expand them into identical Zone_Specs and SHALL build both through the Pipeline.
8. WHEN the CLI is invoked with a set of control options and a Pinned_Seed, THE CLI SHALL produce a Zone_Plan and Zone_Spec equal to those of a controls-mode generate request carrying the same values and seed.
9. THE CLI SHALL build every Zone_Plan from control options through the controls path.
10. IF a generate request has a `mode` other than `prompt` or `controls`, THEN THE Server SHALL respond HTTP 400 naming the accepted modes, before any build, creating no Session and writing no file.
11. IF a generate request has `mode` = `prompt` and an empty or whitespace-only prompt, THEN THE Server SHALL respond HTTP 400 stating that a description is required, before any build, creating no Session and writing no file.
12. THE Server SHALL include the producing `mode` in each generate response, and THE Web_App SHALL show beside the current zone which Generate action produced it.

### Requirement 2: Control coverage and plan normalisation

**User Story:** As a zone author, I want every parameter the plan understands to be available as a control and to be normalised predictably, so that I can dial in a zone without surprises.

#### Acceptance Criteria

1. THE Web_App Controls panel SHALL expose zone type, room count (bounded 1–30), size, verticality, locks (bounded 0–5), topology, district switch, purpose, builder, inhabitants, condition (up to two values), element, seed and Target_Shortname, and SHALL send a blank seed as "no seed" so that the Server draws a Fresh_Seed.
2. THE CLI SHALL accept zone type, room count, size, verticality, locks, topology, district switch, seed and Target_Shortname as options.
3. WHEN a Zone_Plan is built from any input, THE Planner SHALL truncate room count and locks to integers and clamp each to its nearest bound (room count 1–30, locks 0–5).
4. WHEN a Zone_Plan is built from a dictionary, THE Planner SHALL drop keys outside the Zone_Plan schema.
5. WHEN an already-normalised Zone_Plan is normalised again, THE Planner SHALL return an equal Zone_Plan.
6. FOR ALL input dictionaries, THE Planner SHALL produce equal field values on the shared keys whether the dictionary enters through the plan-dictionary path or the controls path.
7. WHILE a Web_App text input, number input, select or textarea has keyboard focus, THE Web_App SHALL deliver key presses to that field and SHALL NOT move the camera.
8. WHEN a Zone_Plan field holds a value outside its vocabulary, THE Planner SHALL replace the value with the field default (zone type → `dungeon`, size → `medium`, verticality → `moderate`, topology → `branching`, purpose, builder, inhabitants and element → empty), SHALL drop Condition values outside the Condition vocabulary and keep the first two, SHALL drop region kinds outside the region vocabulary and SHALL keep only the first 3 district proposals; the Zone_Type vocabulary is Defined_Zone_Types (dungeon, city, wilderness), so a stored or dictionary zone type value `cave` normalises to `dungeon` like any other out-of-vocabulary value, with Enabled_Zone_Types gating left to Requirement 3.
9. IF a generate request carries a non-integer room count, locks or seed, THEN THE Server SHALL respond HTTP 400 naming the field, before any build. (The truncation in criterion 3 applies to Planner and dictionary inputs.)
10. IF a CLI option value is out of its domain or unparsable, THEN THE CLI SHALL print an error naming the option and exit with status 2, writing no file.

### Requirement 3: Zone type availability

**User Story:** As a zone author, I want the tool to offer only zone types that are known to produce walkable zones, so that I never receive a broken zone.

#### Acceptance Criteria

1. THE Server SHALL list exactly the Defined_Zone_Types (dungeon, city, wilderness), each once, at `GET /api/zone_types` (legacy alias `GET /api/themes`), each with `enabled` equal to membership in Enabled_Zone_Types and a non-empty human-readable `reason`.
2. THE Pipeline SHALL treat every member of Enabled_Zone_Types as a Gated_Zone_Type.
3. THE Web_App SHALL render zone type options whose `enabled` is false as disabled and non-selectable, showing their `reason`, and SHALL preselect a member of Enabled_Zone_Types by default.
4. IF a controls-mode request names a zone type outside Enabled_Zone_Types (including an undefined zone type name such as `cave`), THEN THE Server SHALL respond HTTP 400 listing Enabled_Zone_Types, before any build and writing no file.
5. IF the Planner selects a zone type outside Enabled_Zone_Types for a prompt, THEN THE Server SHALL build with the fixed substitute zone type `dungeon`, return a `zone_type_substituted` warning naming the planned and the substituted zone type, and record the planned zone type as `planned_zone_type` in the Sidecar; WHEN no substitution occurs, THE Server SHALL return no `zone_type_substituted` warning.
6. IF a CLI invocation names a zone type outside Enabled_Zone_Types (including an undefined zone type name such as `cave`), THEN THE CLI SHALL print an error listing Enabled_Zone_Types and exit with status 2, writing no file.
7. WHEN a generate response carries a `zone_type_substituted` warning, THE Web_App SHALL display the planned and the substituted zone type until the next generation request.
8. THE Server SHALL return only Accepted_Builds whose zone type is a member of Enabled_Zone_Types.

### Requirement 4: Traversability gate

**User Story:** As a zone author, I want every returned zone to be walkable end to end by an EQ-scale player, so that no room is ever stranded.

#### Acceptance Criteria

1. THE Traversal_Validator SHALL classify a mesh face as standable when its slope is at most 40° and SHALL connect two standable faces when they share a vertex or their XY footprints touch within 2 units, and the vertical distance between their centroids is at most 3 units.
2. THE Traversal_Validator SHALL report a pass only when the Zone_Spec has at least one room and every room's footprint contains a standable face reachable from the start face (the standable face nearest the safe point in XY, ties broken by the smallest vertical distance), and SHALL report the room id and failure reason of each failing room.
3. FOR every zone type in Enabled_Zone_Types, any seed in 0–2,147,483,647, room counts 2–12 and verticality on or off, THE Geometry_Backend for that zone type SHALL produce a Raw_Build that passes the Traversal_Validator.
4. WHERE validation is enabled (the default), THE Pipeline SHALL return a build of a Gated_Zone_Type only after the build passed both the Traversal_Validator and the Format_Checker.
5. IF a build fails the Traversal_Validator or the Format_Checker and the seed is not pinned, THEN THE Pipeline SHALL append one line (zone, zone type, seed, attempt number, failed checks) to the validation failure log and retry with a Fresh_Seed while fewer than `max_attempts` (default 8) builds have run and less than `timeout_s` (default 20 s) has elapsed, checking the budget after each build so that at least one build completes.
6. IF a build with a Pinned_Seed fails the Traversal_Validator or the Format_Checker, THEN THE Pipeline SHALL append one line to the validation failure log and raise a generation failure flagged as pinned, building no other seed.
7. IF the Pipeline exhausts its build or time budget or raises a pinned generation failure, THEN THE Server SHALL respond HTTP 503 with diagnostics listing each rejected seed and its failed checks, and THE CLI SHALL print one line per rejected build to stderr and exit with status 1.
8. IF the selected Geometry_Backend cannot run because an optional dependency is missing, THEN THE Zone_Builder SHALL build with the Box_Backend and record a `backend_fallback` warning in the build result.
9. WHERE `--no-validate` is selected on the CLI, THE Pipeline SHALL run exactly one Raw_Build and return it marked not validated, and THE CLI SHALL report that traversability checking was skipped.
10. THE Pipeline SHALL report, for each Accepted_Build, the seed built, the number of builds run (1 to `max_attempts`) and the validated flag.
11. WHEN the Pipeline rejects a build attempt, THE Pipeline SHALL leave no file of that attempt in the Output_Directory, building each attempt in a scratch directory inside the Output_Directory and removing that directory after rejection.

### Requirement 5: Walkable connections

**User Story:** As a player, I want corridors that meet rooms flush and climb at walkable grades, so that I never hit an invisible ledge or an unclimbable ramp.

#### Acceptance Criteria

1. THE Layout_Generator SHALL set each corridor's `from_z` and `to_z` equal to the `floor_z` of its `from_room` and `to_room`.
2. THE Box_Backend SHALL place the corridor floor edge at each opening on the connected room's wall, within the opening width and within 0.01 units vertically of that room's `floor_z`.
3. THE Box_Backend SHALL carry corridor elevation on ramps, SHALL subdivide every sloped corridor floor (|from_z − to_z| > 0.01) into segments that each rise at most 2.5 units, and SHALL keep corridors between equal-height rooms flat within 0.01 units.
4. THE Layout_Generator SHALL keep |from_z − to_z| ≤ run × 0.5 + 0.01 for every corridor, including corridors that close loops in the Room_Graph, where run is the horizontal length of the leg carrying the elevation change (the single leg of a straight corridor or the middle cross-jog of a three-leg corridor).
5. THE Box_Backend SHALL confine a corridor's whole rise to the leg named in criterion 4, keep every other leg flat at the adjoining room's `floor_z` within 0.01 units, and join consecutive legs within 0.01 units.
6. WHEN a corridor joins two rooms through parallel facing walls whose openings are not collinear, THE Box_Backend SHALL route the corridor as three axis-aligned legs (a stub perpendicular to each wall and a cross-jog between them).

### Requirement 6: Wilderness terrain alignment

**User Story:** As a zone author, I want wilderness terrain to sit under the rooms the layout planned, so that wilderness zones are as walkable as dungeons.

#### Acceptance Criteria

1. THE Terrain_Backend SHALL generate terrain in the Room_Graph coordinate frame with no translation, rotation or scaling, with XY bounds extending at least one terrain sample spacing beyond the full XY footprint of every room and corridor.
2. THE Terrain_Backend SHALL shape the terrain so that the height at every terrain vertex inside a room footprint is within the room's `floor_z` ± 1 unit.
3. THE Terrain_Backend SHALL give every terrain triangle that intersects a corridor footprint a slope of at most 40°.
4. THE Terrain_Backend SHALL leave every room and corridor identical before and after terrain generation (position, size, `floor_z`, endpoints and route).
5. THE Terrain_Backend SHALL keep the centroids of edge-adjacent terrain triangles under a corridor footprint within 3 units of each other in Z.
6. THE Terrain_Backend SHALL make each corridor's centreline height run continuously from its `from_room` `floor_z` to its `to_room` `floor_z`, within ± 1 unit at each end.

### Requirement 7: Natural geometry style for dungeons

**User Story:** As a zone author, I want an optional natural look for dungeons that still reads as one connected, walkable space, so that cave-like dungeons match hand-made Classic–PoP caves without a separate cave pipeline.

#### Acceptance Criteria

1. WHERE the Zone_Spec's zone type is `dungeon` and its geometry style is `natural`, THE Zone_Builder SHALL apply the Natural_Style to the Box_Backend output before writing the build files.
2. WHILE the Zone_Spec's geometry style is `built` or its zone type is not `dungeon`, THE Zone_Builder SHALL write the Geometry_Backend output without the Natural_Style transform.
3. THE Natural_Style SHALL derive its mesh from the Zone_Spec's rooms and corridors as the Layout_Generator produced them, leaving every room and corridor (position, size, `floor_z`, endpoints and route) and the Room_Graph identical before and after styling.
4. THE Natural_Style SHALL produce a mesh whose triangles form exactly one edge-connected component, with no detached pieces.
5. THE Natural_Style SHALL keep every standable face inside a room footprint at or above that room's `floor_z` − 1 unit.
6. THE Natural_Style SHALL emit walkable floor faces without any mesh decimation step.
7. THE Natural_Style SHALL produce a mesh whose median triangle edge length lies within the median-edge band of the Zone_Spec's Style_Profile (the `dungeon` or `cave` profile; Classic–PoP era fidelity, about 12–14 units).
8. FOR any seed, room counts 2–12 and elevation on or off, THE Zone_Builder SHALL produce for a natural-styled dungeon a Raw_Build that passes the Traversal_Validator.
9. FOR every corridor of a natural-styled dungeon, THE Zone_Builder SHALL produce a Traversal_Validator path linking a standable face in the corridor's `from_room` to a standable face in its `to_room` without entering the footprint of a third room.
10. WHEN the Natural_Style is applied, THE Zone_Builder SHALL report in the build result the mesh resolution (voxel size or subdivision length) actually used.
11. THE Zone_Generator SHALL build every zone through the Box_Backend or the Terrain_Backend, with Defined_Zone_Types as the only zone type vocabulary, so that the Zone_Generator offers no cave zone type and contains no separate cave geometry pipeline.

(The Preview of a natural-styled build equals its collision mesh under Requirement 17.6.)

### Requirement 8: Short-name takeover install model

**User Story:** As a zone author, I want to choose which existing RoF2 zone my generated zone replaces and get files already named for it, so that installing is a copy, not a rename exercise.

#### Acceptance Criteria

1. THE Known_Zone_List SHALL provide, for each known RoF2 short name, its long name, EQEmu zone id, client container type (`s3d` or `eqg`) and an `in_install` flag.
2. WHERE an EQ_Install is configured, THE Known_Zone_List SHALL set `in_install` for each short name whose zone archive is present in the EQ_Install, excluding companion archives (`*_obj*`, `*_chr*`, `*_lit`, `*_assets`, `gequip*`, `global*`), and SHALL add no short name absent from the bundled list.
3. IF no EQ_Install is configured or the configured path is unreadable, THEN THE Known_Zone_List SHALL serve the bundled list with `in_install` false for every entry.
4. THE Server SHALL return the Known_Zone_List entries (`shortname`, `long_name`, `container`, `in_install`) and the Default_Target at `GET /api/shortnames`.
5. THE Web_App SHALL show a Target_Shortname picker beside both Generate actions that filters by case-insensitive substring on short or long name, lists `in_install` entries first (alphabetical within each group), preselects the Default_Target, and shows a note stating that installing replaces that zone's client files and server rows and that the tool writes only to the Output_Directory.
6. IF the Target_Shortname is absent, empty or whitespace-only, THEN THE Zone_Generator SHALL use the Default_Target.
7. IF a controls-mode request names a Target_Shortname outside the Known_Zone_List, THEN THE Server SHALL respond HTTP 400 naming it and up to 5 closest known names, before any build and writing no file.
8. IF a prompt-derived Zone_Plan carries a Target_Shortname outside the Known_Zone_List, THEN THE Planner SHALL substitute the Default_Target and record a `shortname_defaulted` warning.
9. WHEN a prompt contains a Known_Zone_List short name or exact long name as a whole word (case-insensitive), THE Planner SHALL set the Target_Shortname to that entry; WHEN the prompt contains none, THE Planner SHALL leave the Target_Shortname empty; WHEN the prompt contains two or more, THE Planner SHALL use the first and record a `shortname_ambiguous` warning.
10. THE Zone_Builder SHALL name the archive `<short>.eqg`, its terrain and zone entries `ter_<short>.ter` and `<short>.zon`, and the ZON's first model reference `TER_<SHORT>.TER`.
11. THE Zone_Generator SHALL name every other artifact of a build for the Target_Shortname: `<short>.glb`, `<short>.zone.json` (whose `shortname` field equals the Target_Shortname), `<short>.map.svg`, `maps/<short>.txt` and `maps/<short>_1.txt`…`_3.txt`, `<short>.sql` and `<short>.bundle.zip`.
12. THE Zone_Generator SHALL write each build into a directory under the Output_Directory unique per zone id and version, so that a second build for the same Target_Shortname overwrites no file of an earlier build.
13. THE Default_Target SHALL be the Known_Zone_List entry `arena` (a low-traffic zone with no progression, flag or key dependency), identical across the Server, CLI and Web_App and returned by `GET /api/shortnames`. *(Note: the end user may manually rename the generated files to install over a different short name; whether the client and server accept such a manual rename is confirmed in a follow-up, the M6 in-engine smoke load, not by this requirement.)*
14. IF a CLI invocation names a Target_Shortname outside the Known_Zone_List, THEN THE CLI SHALL print an error naming it and up to 5 closest known names and exit with status 2, writing no file.
15. THE Zone_Generator SHALL match Target_Shortnames case-insensitively and SHALL use the lowercase form in every `<short>` artifact name, with `TER_<SHORT>.TER` the only uppercase form.

### Requirement 9: Tier-1 RoF2 format check

**User Story:** As a zone author, I want every build checked against the format rules the RoF2 client relies on, so that a file the tool hands me is loadable.

#### Acceptance Criteria

1. WHEN the Pipeline builds a zone, THE Format_Checker SHALL verify that the archive parses, that every entry decompresses to its recorded size, and that every entry's stored CRC equals the EQ filename CRC of its name.
2. WHEN the Pipeline builds a zone, THE Format_Checker SHALL verify that `ter_<short>.ter` and `<short>.zon` are present, that both re-serialise byte-identically after being read, and that the ZON's first model reference is `TER_<SHORT>.TER`.
3. WHEN the Pipeline builds a zone, THE Format_Checker SHALL verify that every polygon's material index lies in 0 to (material count − 1), rejecting −1, and that every material's diffuse texture is present in the archive and decodes as a DDS with power-of-two width and height.
4. WHEN the Pipeline builds a zone, THE Format_Checker SHALL verify that every material carrying `e_TextureNormal0` names a file present in the archive that decodes as a DDS with the same width and height as that material's diffuse texture.
5. WHEN the Pipeline builds a zone, THE Format_Checker SHALL verify that every polygon on a material other than a Liquid_Surface_Material is collidable, that every passable polygon uses a Liquid_Surface_Material, and that at least one polygon is collidable.
6. WHEN the Pipeline builds a zone, THE Format_Checker SHALL verify that at least one standable face lies 0 to 10 units (inclusive) below the safe point in Z and within 50 units of it in XY, and that every vertex coordinate is finite with magnitude below 30000.
7. WHEN the Pipeline builds a zone, THE Format_Checker SHALL verify that the Target_Shortname is in the Known_Zone_List and that the archive file name, its TER and ZON entry names, the ZON model reference and the Sidecar `shortname` all use the same Target_Shortname.
8. THE Format_Checker SHALL report a pass only when every check in criteria 1–7 passes.
9. FOR every zone type in Enabled_Zone_Types, either geometry style of a dungeon (`built` or `natural`) and any seed, THE Zone_Builder SHALL produce a Raw_Build that passes the Format_Checker.
10. WHEN a check fails, THE Format_Checker SHALL report one message per failed check naming the check and the offending entry, material, polygon or value.
11. IF the archive cannot be parsed or an entry cannot be decoded, THEN THE Format_Checker SHALL report a failure message naming the archive or entry, raise no exception to its caller, and still report every check that does not depend on the failed item.
12. WHEN an Accepted_Build is produced, THE Pipeline SHALL write the Format_Checker result (pass flag and messages) into the Sidecar.

### Requirement 10: Tier-2 EQEmu SQL export

**User Story:** As a server operator, I want a reviewable SQL script that points the chosen short name's existing server rows at the generated zone, so that I can enter it on my EQEmu server.

#### Acceptance Criteria

1. WHEN an Accepted_Build is produced, THE SQL_Exporter SHALL write `<short>.sql` into the Output_Directory containing exactly one `UPDATE zone … WHERE short_name = '<short>' AND version = 0` that sets safe x, y and z to the Zone_Spec safe point, no `INSERT INTO zone` statement and no statement that changes the zone id.
2. THE SQL_Exporter SHALL emit one `DELETE FROM doors` scoped to the Target_Shortname and version 0, followed by one `doors` insert per Gate (zero when there are no Gates) whose position equals that Gate's lock position, with door ids unique within the Target_Shortname.
3. WHERE spawn cleanup is enabled (an export option in the Web_App and CLI, default off, recorded in the Sidecar), THE SQL_Exporter SHALL additionally emit deletes of the Target_Shortname's `spawn2`, `grid`, `grid_entries` and `ground_spawns` rows for version 0; WHILE spawn cleanup is disabled, THE SQL_Exporter SHALL emit no statement referencing those tables.
4. IF the Target_Shortname is not in the Known_Zone_List or has no EQEmu zone id, THEN THE SQL_Exporter SHALL write no `<short>.sql`, leave any existing one untouched and report an error naming the short name, and THE Pipeline SHALL still accept the build, skipping the SQL and bundle with a `sql_export_skipped` warning.
5. WHEN the script is applied once, or twice in a row, to a database of the pinned EQEmu schema (version fixed in the M6 milestone spec) containing stock rows for the Target_Shortname and other zones, THE script SHALL leave exactly one `zone` row for the Target_Shortname with its original zone id and the generated safe point, only the generated doors for that short name, and every other short name's rows unchanged.
6. THE SQL_Exporter SHALL write into statements only finite numeric values and short names taken from the Known_Zone_List; IF a value is non-finite, THEN THE SQL_Exporter SHALL write no `.sql` and report an error naming the field.
7. THE SQL_Exporter SHALL begin the script with a header of SQL comment lines only, naming the Target_Shortname and zone id and instructing the user to back up the affected rows before applying it.
8. THE Zone_Generator SHALL deliver the SQL script only as a file in the Output_Directory, opening no connection to any database and changing no database.
9. WHEN the bundle for an Accepted_Build is requested, THE Server SHALL serve `<short>.bundle.zip` containing `<short>.eqg`, the `maps/` files, `<short>.sql`, `<short>.zone.json` and an `INSTALL.txt` describing the manual steps: back up the stock client files and server rows, move the stock archives aside, copy the generated files in, apply the SQL.
10. THE SQL_Exporter SHALL wrap every data-changing statement of the script in a single transaction.
11. IF a bundle is requested for a nonexistent build or for a build without `<short>.sql`, THEN THE Server SHALL produce no archive and report an error naming the missing build or file.

### Requirement 11: Format and IR round-trips

**User Story:** As a developer, I want every reader and writer to round-trip, so that what the tool writes is exactly what it later reads and validates.

#### Acceptance Criteria

1. FOR ALL archives of 0–2000 entries with ASCII names distinct case-insensitively and payloads from 0 bytes to beyond 8192 bytes (including name blocks spanning more than one 8192-byte deflate chunk), reading back a written PFS archive SHALL yield the same name-to-bytes map with byte-identical payloads.
2. THE Zone_Generator SHALL compute PFS filename CRCs case-sensitively as the MSB-first CRC with polynomial 0x04C11DB7 and initial value 0 over the name bytes as stored followed by one NUL byte.
3. FOR ALL TER and ZON files written by the Zone_Builder, reading back the written bytes SHALL yield the same vertices, polygons (indices, material index and flags), materials (name, shader and every property), lights and regions, equal at on-disk field precision (float32 values compared exactly).
4. FOR ALL Zone_Specs produced by the Layout_Generator or the Edit_Engine, serialising to JSON and loading back SHALL produce a dictionary equal to the original.
5. WHEN a Zone_Spec dictionary lacking newer fields (`shortname`, `topology`, `geometry_style`, `districts`, corridor `id` and `threshold`, `district_purpose`, material `normal_texture`) is loaded, THE Zone_Generator SHALL fill those fields with their documented defaults (`shortname` → the Default_Target, `geometry_style` → `built`), leave present fields unchanged and ignore unknown extra keys.
6. THE Zone_Generator SHALL read geometry (vertices, triangles and texture names) from `.s3d` zones (old- and new-format WLD) and from `.eqg` zones for analysis.
7. THE Zone_Builder SHALL write every generated zone as `.eqg`.
8. IF a PFS or WLD file has an unrecognised magic or an unsupported version, THEN THE Zone_Generator SHALL raise an error naming the file kind and the bad value and return no partial data.
9. WHEN a Zone_Spec dictionary whose zone type lies outside Defined_Zone_Types (including the retired `cave`) is loaded, THE Zone_Generator SHALL load the Zone_Spec with zone type `dungeon` and its rooms, corridors and Style_Profile unchanged, and THE Zone_Builder SHALL build it with the Box_Backend.
10. WHEN a Zone_Plan or Zone_Spec dictionary carrying a legacy vocabulary key is loaded, THE Zone_Generator SHALL map `theme` → `zone_type`, the value `outdoor` → `wilderness`, `dungeon_theme` → `purpose`, `dungeon_race` → `builder` and `inhabitants`, `elemental_tint` → `element`, `semantic_type` → `room_type`, `room_theme` → `room_purpose` and `district_theme` → `district_purpose`, preferring the new key when both are present, and SHALL write only the new keys.

### Requirement 12: Mesh-derived outline

**User Story:** As a zone author, I want the map outline traced from the actual mesh, so that the map matches the walls the player walks along.

#### Acceptance Criteria

1. THE Outline_Extractor SHALL compute the outline from the built TER mesh and the safe point only, so that identical TER bytes and safe point yield identical polylines, classifications and Depth_Bands regardless of Advisory_Data.
2. THE Outline_Extractor SHALL emit only segments every point of which lies within 0.05 units of a boundary edge of the selected floor region (standable faces; a boundary edge is an edge not shared by two faces of the region).
3. THE Outline_Extractor SHALL emit no segment that crosses the doorway span of any corridor opening between the opening's two side edges.
4. THE Outline_Extractor SHALL classify a polyline as `wall` where a non-standable face rising above the floor shares the boundary edge and as `ledge` where the floor beyond the edge is absent or drops more than 3 units, splitting polylines where the class changes.
5. WHERE reachable-only extraction is selected (the default), THE Outline_Extractor SHALL use as the floor region the standable faces the Traversal_Validator reaches from the safe point; otherwise THE Outline_Extractor SHALL use all standable faces.
6. THE Outline_Extractor SHALL place each polyline in exactly one of at most 4 Depth_Bands, mark the band holding the safe point's floor as the Main_Band, and, when more than 4 floor levels overlap, merge the adjacent pair with the smallest vertical gap until 4 remain.
7. IF the floor region is empty or the Outline_Extractor fails, THEN THE Pipeline SHALL still return the build, write a schematic-only map SVG, write no EQ map files and record a warning naming the cause.
8. WHEN no standable floors overlap in XY with a vertical separation greater than 12 units (twice the Agent_Model's player height), THE Outline_Extractor SHALL place all polylines in the Main_Band.
9. WHEN standable faces overlap in XY with a vertical separation greater than 12 units, THE Outline_Extractor SHALL place their polylines in different Depth_Bands, subject to the merge rule of criterion 6.
10. THE Outline_Extractor SHALL emit segments covering at least 99% of the floor region's boundary length outside doorway spans to within 0.05 units.
11. THE Outline_Extractor SHALL apply to meshes from every Geometry_Backend of a zone type in Enabled_Zone_Types.

### Requirement 13: EverQuest in-client map file

**User Story:** As a player, I want a map file the RoF2 client's map window can load, so that the generated zone has a usable in-game map.

#### Acceptance Criteria

1. WHEN an Accepted_Build is produced, THE EQ_Map_Writer SHALL write one file per Depth_Band: the Main_Band to `maps/<short>.txt` and the remaining bands to `maps/<short>_1.txt` through `maps/<short>_3.txt` in ascending order of median floor Z, writing no file for a missing band.
2. THE EQ_Map_Writer SHALL write one record per line, line records as `L x1, y1, z1, x2, y2, z2, r, g, b` and label records as `P x, y, z, r, g, b, size, text`, with coordinates to exactly 4 decimal places, integer colour channels 0–255, size ∈ {1, 2, 3}, non-empty label text, and spaces in label text written as `_`.
3. THE Map_Parser SHALL parse `L` and `P` records of that grammar into map layers, accepting records with or without a space after each comma, keeping everything after the seventh comma of a `P` record (commas included) as label text, and ignoring blank lines.
4. FOR ALL map layers, parsing the EQ_Map_Writer's formatted text SHALL yield a layer with the same record counts and order, coordinates within 0.00005, identical colours and sizes, and label text equal to the original with spaces replaced by `_` (round-trip property).
5. THE EQ_Map_Writer SHALL convert world X/Y to map coordinates with the one of the 8 sign/swap combinations that minimises the median distance between a stock EQG zone's map-file endpoints (converted back to world) and that zone's TER wall edges, that median being at most 5 units, and SHALL leave Z unchanged.
6. FOR ALL finite world points, converting to map coordinates and back SHALL return the original point.
7. THE EQ_Map_Writer SHALL place every line endpoint, converted back to world, inside the standable-face XY bounding box plus 0.5 units and at a Z between the lowest standable Z and the highest standable Z plus the Agent_Model's player height (6 units).
8. THE EQ_Map_Writer SHALL write exactly one label "Entrance" and, for each climax room, exactly one label with that room's boss name or "Boss", no other labels, all at size 2.
9. THE EQ_Map_Writer SHALL place every label inside its room's footprint at a Z between the room's `floor_z` and `floor_z` + 6.
10. THE EQ_Map_Writer SHALL use one colour per Depth_Band: black (0, 0, 0) for the Main_Band and a distinct non-black colour for each other band.
11. IF a non-blank line is malformed, THEN THE Map_Parser SHALL skip that line, continue parsing and report the count and line numbers of the skipped lines.

### Requirement 14: True-layout map and artifacts in the Web_App

**User Story:** As a zone author, I want to see and download the true-layout map and every build file from the browser, so that I can review and take the zone with me.

#### Acceptance Criteria

1. THE Map_Viewer SHALL write the mesh outline (walls solid, ledges dashed) as SVG elements placed before every schematic annotation in document order (role-coloured rooms, corridors, depth labels, boss markers, gate links, District hulls, legend and scale bar).
2. WHEN no outline is supplied, THE Map_Viewer SHALL produce output byte-identical to the schematic-only rendering.
3. IF a Raw_Build is rejected, THEN THE Pipeline SHALL leave no map SVG or EQ map file of that Raw_Build in the Output_Directory.
4. WHEN an Accepted_Build is returned, THE Web_App Artifacts panel SHALL display that build's map SVG, replacing any earlier one.
5. WHEN `GET /api/zones/{zone_id}/{version}/{filename}` names an existing file in that build's directory, THE Server SHALL serve the file's bytes unchanged, where `{filename}` may be `maps/<short>.txt`.
6. THE Web_App Artifacts panel SHALL offer, for the current cursor version, downloads of the map SVG, a PNG rendered in the browser from that SVG at 2× its viewBox, each EQ map `.txt` file, `<short>.eqg`, `<short>.sql` and the bundle `.zip`.
7. IF a build-file request passes the checks of Requirement 30.10 but names no existing file in that build's directory, THEN THE Server SHALL respond HTTP 404 with no file content.
8. IF an artifact fails to load, THEN THE Web_App Artifacts panel SHALL mark that artifact unavailable and keep the other artifacts usable.

### Requirement 15: Era fidelity and measured conformance

**User Story:** As a zone author, I want generated zones measured against real Classic–PoP zones of the same zone type, so that "looks like EverQuest" is a number, not a claim.

#### Acceptance Criteria

1. THE Layout_Generator SHALL size rooms from the floor-area and extent measurements in the Zone_Spec's Style_Profile so that the zone's total floor area falls within that profile's floor-area band.
2. THE Layout_Generator SHALL assign every room's Room_Type from the Zone_Plan Purpose, or from `fortress` when the Zone_Plan names none.
3. WHEN an Accepted_Build is produced, THE Conformance_Meter SHALL measure width_x, width_y, ceiling height, floor area, polygon density, median triangle edge length, material count and light density, and report for each the value, the inclusive band [min − slack·std, max + slack·std] from the Style_Profile (slack from the profile, default 1.0) and an in-band flag, plus the within-band fraction (in-band metrics divided by banded metrics).
4. THE Pipeline SHALL write the conformance report into the Sidecar.
5. THE Pipeline SHALL return the same Accepted_Build whatever the conformance report says, using the report to reject, retry or modify no build.
6. FOR every zone type in Enabled_Zone_Types over at least 20 Fresh_Seeds with the default Zone_Plan, THE Zone_Generator SHALL produce builds whose median within-band fraction is at least 0.75 and each of whose median triangle edge length is within the Style_Profile band.
7. WHEN the Zone_Plan names a Builder, a Condition or an Element, THE Layout_Generator SHALL apply that Builder's scale, that Condition's palette and light adjustments and that Element's palette, regions and light mood (defaults: Builder scale 1.0, no Condition, no Element; an Element implied by a Condition applies when none is named).
8. THE Web_App SHALL display every conformance metric's value, band and in-band flag and the within-band fraction.
9. IF the Style_Profile lacks a profile or statistic for a metric, THEN THE Conformance_Meter SHALL report that metric unbanded and exclude it from the within-band fraction, and THE Pipeline SHALL still return the build.

### Requirement 16: Procedural normal maps

**User Story:** As a zone author, I want every material to ship a matching normal map, so that surfaces show relief in the client like real EQG zones.

#### Acceptance Criteria

1. WHERE normal maps are enabled (the default), THE Texture_Generator SHALL produce for each material a diffuse DDS and a Normal_Map DDS with identical width and height.
2. WHERE the procedural provider is used, THE Texture_Generator SHALL derive each material's diffuse and Normal_Map from the same tileable height field, and SHALL produce from a constant height field a diffuse with no relief shading and a Normal_Map of (128, 128, 255) at every texel.
3. THE Texture_Generator SHALL encode Normal_Map texels whose decoded vectors (`rgb/127.5 − 1`) have length within 0.02 of 1 and a positive Z component, and SHALL encode a constant height field as (128, 128, 255) at every texel.
4. WHERE the procedural provider is used, THE Texture_Generator SHALL produce Normal_Maps that tile seamlessly: the largest per-channel absolute difference between the last and first rows is no larger than the largest per-channel difference between any two adjacent rows, and likewise for columns.
5. WHEN the AI texture provider returns a material, THE Texture_Generator SHALL use the provider's normal map resized to the diffuse dimensions when one is returned, and otherwise derive the Normal_Map from the diffuse luminance satisfying criterion 3.
6. THE Texture_Generator SHALL use a single fixed tangent-space convention (R = tangent X, G = bitangent Y, B = normal Z) whose G sign for a height rising along +V matches the stock EQG Normal_Maps measured in an EQ_Install.
7. THE Zone_Builder SHALL pack each Normal_Map into the `.eqg` and reference it through the material property `e_TextureNormal0` alongside `e_TextureDiffuse0`, under a `.dds` name distinct from every diffuse texture name (default `<diffuse stem>_n.dds`), so that every `e_TextureNormal0` names a DDS present in the same `.eqg`.
8. IF a Normal_Map cannot be produced for a material, THEN THE Zone_Builder SHALL keep that material's diffuse reference, omit its `e_TextureNormal0` reference, record a `normal_map_skipped` warning naming the material in the response `warnings` and the Sidecar, and complete the build.
9. WHERE the procedural provider is used, THE Texture_Generator SHALL produce byte-identical diffuse and Normal_Map bytes for identical (name, description, colour, kind, size, seed).
10. WHERE normal maps are disabled (CLI `--no-normal-maps`, or the Web_App/Zone_Plan toggle), THE Zone_Builder SHALL pack no Normal_Map DDS and write no `e_TextureNormal0` property.
11. IF the AI texture provider returns an error or an undecodable image for a material, THEN THE Texture_Generator SHALL produce that material's diffuse and Normal_Map with the procedural provider from the same inputs.

### Requirement 17: Textured preview

**User Story:** As a zone author, I want the browser preview to show real textures and normal maps, so that I can judge the look without loading the client.

#### Acceptance Criteria

1. THE Zone_Builder SHALL embed in the Preview, for every material, the same diffuse texture packed in the `.eqg` (same width and height; a re-encoded PNG is allowed with each channel within 2/255 of the DDS texel) and SHALL keep each vertex's UVs from the `.eqg` mesh.
2. THE Web_App SHALL render each Preview material with its embedded diffuse texture and, where present, its Normal_Map as the normal texture.
3. THE Zone_Builder SHALL embed a material's Normal_Map as the Preview normal texture where the material carries `e_TextureNormal0`, and SHALL embed no normal texture otherwise.
4. IF embedding a material's diffuse texture fails, THEN THE Zone_Builder SHALL give that Preview material its base colour and no textures, record a warning naming the material, and still write the Preview and the `.eqg`.
5. WHEN a Preview material has no diffuse texture, THE Web_App SHALL render that material with its base colour and render every other material unaffected.
6. THE Zone_Builder SHALL write, for every Geometry_Backend and for Natural_Style output, a Preview whose vertex positions and triangles equal the `.eqg` collision mesh.

### Requirement 18: Sessions and feedback interpretation

**User Story:** As a zone author, I want to type follow-up instructions like "make the boss room bigger", so that I refine the current zone instead of starting over.

#### Acceptance Criteria

1. WHEN the Pipeline returns an Accepted_Build, THE Server SHALL create a Session holding the Zone_Plan, Zone_Spec, base seed and a history whose single entry, version 0, is that build with its artifacts and Quality_Block, and SHALL return the `session_id` and version 0; WHEN no Accepted_Build is returned, THE Server SHALL create no Session.
2. WHEN feedback text is submitted to `POST /api/sessions/{id}/edit`, THE Edit_Interpreter SHALL emit zero or more Edit_Ops drawn only from the edit vocabulary (`widen_room`, `narrow_room`, `taller_room`, `lower_room`, `add_room`, `remove_room`, `add_region`, `remove_region`, `set_purpose`, `set_verticality`, `add_lock`, `remove_lock`, `reroll_room`, `set_topology`, `regenerate`), with every parameter clamped into its inclusive schema range and targets resolved against the current Zone_Spec by room id, Pacing_Role ("boss room" → climax, "entrance") or Room_Type; IF a target resolves to several rooms, THEN THE Edit_Interpreter SHALL reject that Edit_Op as ambiguous with a note listing the candidate rooms.
3. WHEN an edit request carries explicit `ops` instead of feedback text, THE Server SHALL validate those Edit_Ops against the same vocabulary and ranges without invoking the Edit_Interpreter.
4. IF the Edit_Interpreter produces no Edit_Ops, THEN THE Server SHALL respond `applied: false` with a help message listing the supported edit kinds and leave the Session's history, cursor and current artifacts byte-identical.
5. IF an Edit_Op's target resolves to no room, THEN THE Edit_Engine SHALL reject that Edit_Op with a note naming the op and the target and apply the remaining Edit_Ops.
6. FOR ALL input strings of 0–2000 characters, including empty, whitespace-only and arbitrary Unicode strings, THE Edit_Interpreter SHALL return a (possibly empty) list of valid Edit_Ops and the interpreter name without raising an error.
7. WHERE an LLM key is configured, THE Edit_Interpreter SHALL accept the LLM output only as JSON matching the Edit_Op schema, re-validate and clamp it, and use the rule-based interpreter on any LLM error, on no LLM response within 15 seconds, or on a schema failure.
8. THE Web_App Feedback panel SHALL provide a text box with an Apply action, a history list (version, Edit_Ops, accepted/rejected, Quality_Degraded marker; rejected entries kept client-side only), an undo action disabled at version 0 and a redo action disabled at the newest version.
9. IF an explicit `ops` request contains any invalid Edit_Op (unknown kind, missing parameter or out-of-range value), THEN THE Server SHALL respond `applied: false` listing each invalid Edit_Op with its reason, apply no Edit_Op, and leave the Session byte-identical.
10. IF the Edit_Engine rejects every Edit_Op of a request, THEN THE Server SHALL respond `applied: false` with the rejection notes and leave the Session byte-identical.
11. WHEN an edit is accepted, THE Web_App SHALL highlight exactly the Affected_Set rooms in the 3D view and clear the highlight on the next edit, undo or redo.

### Requirement 19: Edit application and acceptance

**User Story:** As a zone author, I want edits to change only what I asked for and never leave me with a broken zone, so that iteration is safe.

#### Acceptance Criteria

1. THE Edit_Engine SHALL produce the same output Zone_Spec, Affected_Set and notes for identical (Zone_Spec, Edit_Ops, base seed, version, salt).
2. WHILE the zone type uses the Box_Backend and the geometry style is `built`, THE Zone_Builder SHALL produce, for every room and corridor outside the Affected_Set, the same triangles (positions, winding and material) before and after an edit's rebuild.
3. THE Edit_Engine SHALL give `add_region`, `remove_region` and `set_purpose` a geometric Affected_Set containing no corridor and no room other than the target room, and SHALL give `add_lock` and `remove_lock` an empty geometric Affected_Set.
4. IF a resize Edit_Op would overlap a neighbouring room, THEN THE Edit_Engine SHALL clamp the resize to the largest non-overlapping size, leave every other room unchanged and report the requested and applied size in the edit notes.
5. IF `remove_room` targets the entrance or would leave any room unreachable from the entrance, THEN THE Edit_Engine SHALL reject that Edit_Op with a note and apply the remaining Edit_Ops.
6. THE Edit_Engine SHALL keep every surviving corridor's `id` unchanged across edits.
7. WHEN an edited build passes the Format_Checker and, for a Gated_Zone_Type, the Traversal_Validator, THE Server SHALL accept the edit as the next version even when its quality report fails, marking it Quality_Degraded with reason `edit_outside_bands`.
8. WHEN the candidate of a randomised Edit_Op (`add_room`, `reroll_room`, `set_topology`, `regenerate`) fails the Format_Checker, the Traversal_Validator (for a Gated_Zone_Type) or a Quality_Band, THE Server SHALL build the next salt, up to 5 candidates in total, and keep the candidate with the best quality score among those passing the hard gates (ties to the lowest salt).
9. IF no candidate passes the Format_Checker and, for a Gated_Zone_Type, the Traversal_Validator, THEN THE Server SHALL respond `applied: false` with the gate diagnostics and leave the Session's history, cursor and current artifacts byte-identical.
10. THE Edit_Engine SHALL leave the input Zone_Spec equal to its value before the call.
11. WHEN an edit request contains only deterministic Edit_Ops, THE Server SHALL build exactly one candidate.
12. WHEN an edit is accepted, THE Server SHALL include the Affected_Set (room ids and corridor ids) and the edit notes in the response.

### Requirement 20: History, undo and redo

**User Story:** As a zone author, I want exact undo and redo across my edits, so that I can explore without fear of losing a good version.

#### Acceptance Criteria

1. WHEN an edit is accepted, THE Session_Store SHALL discard the history entries after the cursor, append one entry (full Zone_Spec snapshot, seed, Edit_Ops, feedback text, interpreter name, artifact directory and Quality_Block) with version = cursor version + 1, and move the cursor to the new entry.
2. WHEN undo is requested with the cursor after version 0, THE Server SHALL move the cursor back exactly one retained version, make the current Zone_Spec, TER, `.eqg`, Preview, Sidecar and Quality_Block byte-identical to that version's stored ones, and return the new cursor version.
3. WHEN redo is requested with the cursor before the newest version, THE Server SHALL move the cursor forward exactly one retained version, make the current Zone_Spec, TER, `.eqg`, Preview, Sidecar and Quality_Block byte-identical to that version's stored ones, and return the new cursor version.
4. IF undo is requested at version 0 or redo at the newest version, THEN THE Server SHALL respond HTTP 409 and leave the Session byte-identical.
5. FOR ALL Sessions, replaying the stored Edit_Ops and seeds of versions 1..N on version 0 SHALL reproduce every stored Zone_Spec snapshot exactly and byte-identical TER.
6. THE Server SHALL return at `GET /api/sessions/{id}`, without side effects, a Session summary holding the session id, the cursor version, the newest version and, per retained entry, its version, Edit_Ops, feedback text and Quality_Block `degraded` and `reason`.
7. THE Session_Store SHALL serialise edit, undo and redo operations per Session so that each operation starts from the state the preceding operation left (concurrent requests are rejected per Requirement 30.7).
8. WHEN an edit is accepted after one or more undos, THE Session_Store SHALL delete the artifact files of the discarded redo entries, after which a redo request receives HTTP 409.
9. THE Session_Store SHALL keep every retained entry's version number unchanged after evictions, and undo across an evicted gap SHALL move to the nearest retained earlier version.
10. WHEN the Server restarts, THE Session_Store SHALL start with no Sessions; Session history and cursors are held in memory only, while artifact files may remain on disk until cleanup.

### Requirement 21: Composed, solvable layout

**User Story:** As a zone author, I want every zone to have a clear entrance, a climax and solvable locks, so that it plays like a designed dungeon.

#### Acceptance Criteria

1. THE Layout_Generator SHALL produce exactly the requested number of rooms and a connected Room_Graph for every seed, room count, topology and district setting.
2. THE Layout_Generator SHALL label exactly one room per Zone_Spec `entrance`, WHERE the zone has 2 or more rooms exactly one room per District `climax`, and no room both.
3. THE Layout_Generator SHALL assign each room exactly one Pacing_Role with precedence entrance, climax, hub, deadend, standard: entrance = the room whose centre is farthest (XY Euclidean) from the mean of the room centres; climax = the room of greatest graph depth from the entrance, ties to the lowest room index (single-District case; multi-District zones per Requirement 23.4); hub = any other room with degree ≥ 3; deadend = any other room with degree 1; standard = every remaining room.
4. THE Layout_Generator SHALL place the safe point at the XY centre of the entrance room, at Z exactly the entrance room's `floor_z` + 5.
5. WHEN locks ≥ 1 and the zone has at least 3 rooms, THE Layout_Generator SHALL place Gates such that a simulated player starting at the entrance, who may cross a gated corridor only after visiting its key room, reaches every room.
6. THE Layout_Generator SHALL place between 0 and `locks` Gates, each on an existing corridor id with at most one Gate per corridor (fewer than requested when too few qualifying tree edges exist), and THE Zone_Builder SHALL record the requested and placed Gate counts in the Sidecar.
7. THE Layout_Generator SHALL place each Gate's key in a room outside the set of rooms reachable only through that Gate's corridor, and SHALL use the entrance as a key room only when no other room qualifies, recording a note when it does.
8. WHEN locks = 0 or the zone has fewer than 3 rooms, THE Layout_Generator SHALL place zero Gates without error.

### Requirement 22: Topology control

**User Story:** As a zone author, I want to choose a linear, branching or looped layout, so that I control how the zone flows.

#### Acceptance Criteria

1. THE Layout_Generator SHALL accept a topology of `linear`, `branching` or `looped`, and WHEN no topology is supplied, THE Layout_Generator SHALL produce the same Zone_Spec as for `branching`.
2. WHERE topology is `linear`, THE Layout_Generator SHALL produce, for every room count 1–30, a Room_Graph with maximum degree at most 3 in which at least n − 3 of the n rooms have degree at most 2.
3. WHEN a 14-room zone is built from the same seed under each topology, THE Layout_Generator SHALL produce cyclomatic numbers (E − N + 1) ordered linear ≤ branching < looped.
4. WHERE topology is `branching` and the zone has a single District, THE Layout_Generator SHALL produce for a given seed rooms and a Room_Graph edge set identical to those of the layout without the topology control.
5. WHEN a prompt contains "winding", "maze" or "interconnected", THE Planner SHALL set topology `looped`, taking precedence over any linear wording.
6. WHEN a prompt contains "straightforward" or "linear" and none of the looped words of criterion 5, THE Planner SHALL set topology `linear`.
7. WHEN a prompt contains neither looped nor linear words, THE Planner SHALL set topology `branching`.
8. IF the Layout_Generator receives a topology value outside `linear`, `branching` and `looped`, THEN THE Layout_Generator SHALL raise an error naming the allowed values and produce no Zone_Spec. (Planner input is normalised first per Requirement 2.8.)

### Requirement 23: Districts

**User Story:** As a zone author, I want larger zones split into 2–3 distinct areas joined at deliberate crossings, so that big zones feel composed rather than uniform.

#### Acceptance Criteria

1. THE Layout_Generator SHALL use k = 1 District when the district switch is off or the zone has fewer than 8 rooms, k = 2 for 8–13 rooms and k = 3 for 14 or more rooms; IF no partition satisfying criteria 2 and 3 exists, THEN THE Layout_Generator SHALL decrement k until one does (k = 1 always does) and record a Sidecar note with the requested and resolved counts. Planner district proposals do not override these counts.
2. THE Layout_Generator SHALL place every room in exactly one District such that each District's induced subgraph of the Room_Graph is connected and has at least max(3, ⌊n / (k + 1)⌋) rooms, producing the same partition for the same seed and Zone_Plan.
3. THE Layout_Generator SHALL keep exactly one corridor between each pair of Districts that share at least one corridor, removing the other cross-District corridors, flag that corridor as the Threshold and flag no other corridor; District adjacency may form a cycle.
4. THE Layout_Generator SHALL give each District exactly one purpose and exactly one climax, the room of greatest in-District graph distance from the District entrance (ties to the lowest room id), where the District entrance is the zone entrance for its own District and, for every other District, that District's endpoint of the first Threshold crossed on the shortest path from the zone entrance (ties to the lowest room id); no other room is a climax.
5. THE Layout_Generator SHALL give the two endpoint rooms of each Threshold non-identical material sets and light moods differing in colour or intensity, including when both Districts share an purpose.
6. WHERE the resolved District count is 1, THE Layout_Generator SHALL produce the same rooms, corridors, materials, lights, Pacing_Roles and Gates as with the district switch off, differing only by the reduction note.
7. WHERE locks ≥ 1 and k ≥ 2, THE Layout_Generator SHALL place min(locks, number of Thresholds) Gates on Threshold corridors before any other corridor, placing each Threshold Gate's key on the zone-entrance side so that the key room is reachable from the entrance without crossing that Gate.
8. WHERE no purposes are proposed, THE Layout_Generator SHALL choose District purposes from the District relationship (default `sequential`) using the bundled compatibility table: `sequential` → pairwise-distinct purposes with every consecutive pair compatible, `factional` → pairwise-distinct contrasting purposes, `abandoned_vs_active` → one purpose, with every non-entrance District given a lower-saturation palette and lower light intensity.
9. WHEN a prompt contains a bundled contrasting-area phrase (for example "living and dead", "two factions", "upper and lower"), THE Planner SHALL switch districts on and propose a District count equal to the number of named areas clamped to 2–3, one purpose per proposed District and exactly one District relationship.
10. WHERE the Zone_Plan pins a single purpose, THE Layout_Generator SHALL give every District that purpose, satisfy criterion 5 through palette and light variants, and record a Sidecar note.
11. WHEN the number of District proposals differs from k, THE Layout_Generator SHALL use the first k proposals and choose the remaining Districts' purposes per criterion 8.
12. IF a proposed purpose or District relationship is unknown, THEN THE Layout_Generator SHALL ignore that value, apply the default and record a Sidecar note naming the value.

### Requirement 24: Quality gate

**User Story:** As a zone author, I want dull layouts rejected and redrawn the way unwalkable ones are, so that every generation is worth looking at.

#### Acceptance Criteria

1. THE Quality_Meter SHALL compute from the Zone_Spec alone, without a mesh: `cyclomatic` = E − N + 1; `max_degree`; `dead_end_ratio` = rooms of degree 1 / N; `critical_path_ratio` = climax depth / (N − 1); `branching_factor` = mean degree of rooms with degree ≥ 2; `elevation_range` = max − min `floor_z`; `elevation_levels` = distinct `floor_z` values after 8-unit binning; `role_diversity` = distinct Pacing_Roles; `room_type_diversity` = distinct Room_Types / N; `size_cv` = coefficient of variation of room floor area; `district_balance` = smallest / largest District room count.
2. FOR ALL Zone_Specs, THE Quality_Meter SHALL return identical metric values, pass result, Out_Of_Band_List and score for repeated calls, for the Zone_Spec after a JSON round-trip, and after changing only `prop_hints`, `encounter_intent`, `boss` or Gates.
3. THE Quality_Meter SHALL report a pass exactly when every metric lies within its inclusive band; SHALL list in the Out_Of_Band_List exactly the failing metrics, once each, with value and `lo`/`hi` (null for an unbounded side); and SHALL report a score of 0 exactly on a pass and otherwise the sum over failing metrics of the distance to the violated bound divided by the normaliser (the band width, or |bound| for a half-open band, minimum 1), strictly increasing as any single out-of-band value moves away from its band.
4. THE Quality_Meter SHALL select Quality_Bands by zone type, topology, room count and verticality, and SHALL leave every band unbounded for zones with fewer than 4 rooms, `district_balance` unbounded for zones with fewer than 2 Districts, `dead_end_ratio` unbounded for `linear` topology and `room_type_diversity` unbounded for zones without a Purpose.
5. WHILE the seed is not pinned, THE Pipeline SHALL measure each drawn seed's Zone_Spec before building, redraw a Fresh_Seed without building on a quality failure, stop after 32 failing draws, and build the first passing seed.
6. WHEN 32 quality draws have failed, THE Pipeline SHALL build the seed with the lowest quality score (the earliest on a tie); IF that build passes the hard gates, THEN THE Pipeline SHALL return it as Quality_Degraded with reason `quality_degraded` and its Out_Of_Band_List; IF that build fails a hard gate, THEN THE Pipeline SHALL continue the hard-gate retry loop of Requirement 4.5 with Fresh_Seeds and no further quality draws.
7. WHEN a Pinned_Seed's Zone_Spec fails quality, THE Pipeline SHALL build only that seed and, if the build passes the hard gates, return the build as Quality_Degraded with reason `quality_outside_bands_pinned` and its Out_Of_Band_List.
8. WHEN a build's quality report passes, THE Pipeline SHALL return the build not Quality_Degraded with an empty reason; the Quality_Meter itself never marks a build Quality_Degraded.

### Requirement 25: Quality_Degraded is always visible

**User Story:** As a zone author, I want to be told plainly when the zone I got is walkable but misses quality targets, and which metrics fell short, so that a degraded result is never mistaken for a good one.

#### Acceptance Criteria

1. WHEN the Server returns a build from generate, an accepted edit, undo or redo, THE Server SHALL include the build's Quality_Block in the response.
2. WHEN a returned build is Quality_Degraded, THE Server SHALL set the Quality_Block's `degraded` to true, its `reason` to one of `quality_degraded`, `quality_outside_bands_pinned` or `edit_outside_bands` that also appears in the response `warnings`, and its `out_of_band` to the non-empty Out_Of_Band_List (`metric`, `value`, `lo`, `hi`).
3. WHEN a returned build is not Quality_Degraded, THE Server SHALL set `degraded` to false, `reason` to null, `out_of_band` to empty and `score` to 0, and SHALL put no quality reason in `warnings`.
4. THE Pipeline SHALL write into the build's Sidecar a `quality` entry that, after JSON parsing, equals the Quality_Block returned in the response.
5. WHILE the most recent build-bearing response's Quality_Block has `degraded` true, THE Web_App SHALL show a banner over the 3D viewport, without a close control and persisting through camera movement and panel collapse/expand, stating that the zone is walkable but outside quality targets, the number of out-of-band metrics (the length of `out_of_band`) and the reason, exposed to assistive technologies as a status message, with a link that opens and focuses the metrics panel.
6. WHILE the most recent build-bearing response's Quality_Block has `degraded` true, THE Web_App metrics panel SHALL list every `out_of_band` entry as `metric — value (band lo–hi)` before any in-band metric, followed by the remaining metrics with their values.
7. WHEN a build-bearing response's Quality_Block has `degraded` false, THE Web_App SHALL remove any degraded banner and show a quality-passed indicator that stays visible until the next build-bearing response.
8. WHEN the Web_App loads any build version (generate, undo, redo or the Session summary), THE Web_App SHALL show the banner or the quality-passed indicator and the metrics list exactly as given by that build's Sidecar `quality` entry.
9. WHEN a CLI run returns a Quality_Degraded build, THE CLI SHALL print the reason, the out-of-band count and each out-of-band entry's metric, value, `lo` and `hi`, and exit with status 0; WHEN the build is not Quality_Degraded, THE CLI SHALL print no quality warning.
10. WHEN a response carries no new build (`applied: false`, HTTP 409 or any error), THE Web_App SHALL leave the banner or indicator and the metrics list unchanged.
11. IF a loaded build's Sidecar has no valid `quality` entry, THEN THE Web_App SHALL show a quality-unknown indicator and no metrics list.

### Requirement 26: Determinism and fresh-seed randomness

**User Story:** As a zone author, I want a new zone every time by default and an exact reproduction when I pin a seed, so that randomness is a feature and results are repeatable.

#### Acceptance Criteria

1. WHEN two independent runs receive the same Zone_Plan, Pinned_Seed, Target_Shortname and arguments for any zone type in Enabled_Zone_Types (dungeons in either geometry style), THE Zone_Generator SHALL produce equal Zone_Spec dictionaries and byte-identical TER, ZON, `<short>.map.svg` and EQ map files (`.eqg` and `.glb` are not required to be byte-identical).
2. WHEN a generation is requested without a seed, THE Pipeline SHALL draw a Fresh_Seed in 0–2,147,483,647 for that call, such that three consecutive unpinned calls with identical inputs do not all share one seed.
3. THE Server SHALL include in each generate response the seed of the Accepted_Build (the seed actually built after any retries).
4. WHILE a seed is pinned, THE Pipeline SHALL build only that Pinned_Seed and draw no Fresh_Seed for any retry.
5. WHEN the user activates the Web_App reproduce action, THE Web_App SHALL request a generation pinned to the shown seed with the stored Zone_Plan (without re-running the Planner), and THE Server SHALL return a Zone_Spec equal to the one shown.
6. IF a Pinned_Seed lies outside 0–2,147,483,647, THEN THE Server SHALL respond HTTP 400 and THE CLI SHALL exit with status 2, before any build.

### Requirement 27: Advisory data stays out of geometry and collision

**User Story:** As a zone author, I want pacing, gates and other suggestions to stay suggestions, so that my manual finishing pass starts from geometry they never altered.

#### Acceptance Criteria

1. FOR every zone type in Enabled_Zone_Types, every seed and room counts 1–30, THE Zone_Builder SHALL produce byte-identical TER for two Zone_Plans that differ only in locks (1–5 versus 0).
2. FOR every zone type in Enabled_Zone_Types and every already-generated Zone_Spec, THE Zone_Builder SHALL produce byte-identical TER for that Zone_Spec and for a copy with every Advisory_Data field cleared (Pacing_Roles, depth, Room_Type labels, District metadata, Threshold flags, Gates, `prop_hints`, `encounter_intent`, `boss`) and room dimensions, floors, corridors, regions, lights and materials kept.
3. THE Zone_Builder SHALL carry in the Sidecar, per room, its Pacing_Role, depth, Room_Type label, District, `prop_hints`, `encounter_intent` and `boss`; per Gate, its corridor and key room; and per corridor, its Threshold flag.
4. THE Zone_Generator SHALL write Advisory_Data only to the Sidecar, the SQL export and the map artifacts (map SVG annotations and EQ map labels), and to no `.eqg` entry.
5. WHILE the zone type uses the Box_Backend, THE Zone_Builder SHALL produce after an `add_lock` or `remove_lock` edit a TER byte-identical to the prior version's.

### Requirement 28: No API required by default

**User Story:** As a zone author, I want the whole tool to work with no API keys and no network, so that it runs anywhere.

#### Acceptance Criteria

1. WHILE no LLM key is configured, THE Zone_Generator SHALL produce every Zone_Plan with the rule-based Planner and interpret all feedback with the rule-based Edit_Interpreter.
2. WHILE no API key is configured and network access is unavailable, THE Zone_Generator SHALL produce, through the Server, an Accepted_Build from a prompt written to the Output_Directory and an edit applied and undone, and, through the CLI, an Accepted_Build from control options, with no network error.
3. IF the LLM Planner raises an error, produces no response within 15 seconds or returns schema-invalid output, THEN THE Planner SHALL produce the Zone_Plan with the rule-based planner for the same prompt, the request SHALL complete without error, and THE Server SHALL record the planner actually used in the response and the Sidecar (`planner`).
4. THE Zone_Generator SHALL open outbound network connections only to the provider of a configured API key, and none when no key is configured.
5. WHILE no AI-texture key is configured, THE Texture_Generator SHALL produce every diffuse texture and Normal_Map procedurally.

### Requirement 29: Time budgets

**User Story:** As a zone author, I want generation and edits to finish in predictable time, so that the browser loop stays usable.

#### Acceptance Criteria

1. WHEN a validated generation with a Fresh_Seed of 2–30 rooms runs for any zone type in Enabled_Zone_Types on the Reference_Machine, THE Pipeline SHALL return an Accepted_Build or a generation failure within 300 seconds of wall-clock time (request receipt to response, or CLI process start to exit).
2. THE Pipeline SHALL complete validated dungeon (geometry style `built`) and city generations of 2–12 rooms on the Reference_Machine within 20 seconds at the 95th percentile over at least 20 consecutive generations per zone type.
3. THE Pipeline SHALL complete validated wilderness generations of 2–12 rooms on the Reference_Machine within 60 seconds at the 95th percentile over at least 20 consecutive generations.
4. WHEN one Edit_Op is applied to a Box_Backend Session (geometry style `built`) of 2–12 rooms on the Reference_Machine, THE Server SHALL return the response (including salt retries) within 5 seconds at the 95th percentile over at least 20 edits.
5. WHERE cave is in Enabled_Zone_Types, THE Pipeline SHALL complete validated cave generations of 2–12 rooms on the Reference_Machine within 180 seconds at the 95th percentile over at least 20 consecutive generations.

### Requirement 30: Local server security and session limits

**User Story:** As the single local user, I want the server safe by default and bounded in what it keeps, so that running it does not expose my machine or fill my disk.

#### Acceptance Criteria

1. THE Server SHALL bind to 127.0.0.1 by default.
2. WHEN a request's Origin is the Server's own origin or the Local_Frontend_Origin, THE Server SHALL send cross-origin permission headers, and for any other Origin THE Server SHALL omit them.
3. WHERE the Server is bound to a non-loopback address, IF an `/api/*` request lacks a bearer token equal to `EQ_S3D_TOKEN`, THEN THE Server SHALL respond HTTP 401 and change no Session and no file.
4. THE Session_Store SHALL issue Session ids with at least 128 bits of cryptographic randomness, and THE Server SHALL expose no endpoint that lists Sessions.
5. IF a request names an unknown Session id or a Session idle for more than 24 hours, THEN THE Server SHALL respond HTTP 404 and leave every other Session unchanged.
6. WHEN creating a Session would exceed 32 Sessions, THE Session_Store SHALL first evict the Session whose most recent request is oldest.
7. IF an edit, undo or redo arrives while another edit, undo or redo on the same Session is in flight, THEN THE Server SHALL respond HTTP 429 and leave that Session unchanged by the rejected request.
8. FOR ALL interleavings of operations on two Sessions, THE Session_Store SHALL leave each Session's history entry count, cursor and artifact bytes as they would be had the other Session's operations never run.
9. THE Server SHALL remove every Unicode control character except newline and tab from feedback text and then keep its first 2000 characters, before the Edit_Interpreter runs.
10. IF a build-file request has a path segment that fails `^[A-Za-z0-9_.-]+$`, contains `..`, has an extension outside the Build_File_Allow_List, or resolves outside that build's directory within the Output_Directory, THEN THE Server SHALL respond HTTP 400 with no file content.
11. IF the Server is configured to bind to a non-loopback address while `EQ_S3D_TOKEN` is unset or empty, THEN THE Server SHALL refuse to start and report an error.
12. WHEN a Session's history would exceed 50 entries, THE Session_Store SHALL evict the oldest entry that is neither the first entry nor the entry at the cursor.
13. WHEN a Session or history entry is evicted or a Session expires after 24 hours idle, THE Session_Store SHALL delete the files belonging only to that Session or entry and leave every other file untouched.

### Requirement 31: File-system confinement

**User Story:** As a zone author, I want the tool to write only into its output folder and never touch my EverQuest install, so that installing stays my deliberate, reversible step.

#### Acceptance Criteria

1. THE Zone_Generator SHALL create, write, rename and delete files (including intermediate and temporary files, with dependency temporary files directed into a temporary directory inside the Output_Directory) only at paths whose fully resolved location (after `..`, symlinks and junctions) lies inside the resolved Output_Directory.
2. THE Zone_Generator SHALL leave the EQ_Install's file list, file sizes and file contents byte-identical before and after any generate, edit, export or bundle operation, creating, modifying, renaming and deleting nothing under it.
3. THE Zone_Generator SHALL read API keys only from the process environment and the gitignored `.env` file, with the process environment taking precedence, and SHALL run with no API key present.
4. IF a write, rename or delete would resolve outside the Output_Directory, THEN THE Zone_Generator SHALL perform no operation, report an error naming the path and leave existing output unchanged.
5. IF the Output_Directory equals or lies inside the EQ_Install, THEN THE Zone_Generator SHALL refuse to run before writing any file (the CLI exits with a non-zero status; the Server refuses to start).
6. THE Zone_Generator SHALL write no API key value into any output file, HTTP response, console output or log.

### Requirement 32: Settled design constraints

**User Story:** As the project owner, I want decisions already settled to bind the system, so that they are not relitigated in each milestone.

#### Acceptance Criteria

1. THE Layout_Generator SHALL lay out rooms with the TinyKeep scheme (scatter, separate, triangulate, spanning tree, added loop edges) such that no two room footprints overlap and, for every topology and at least 3 non-collinear rooms, every Room_Graph edge is a Delaunay edge of the room centres and the Room_Graph contains a minimum spanning tree of that triangulation.
2. THE Layout_Generator SHALL derive Pacing_Roles as a function of the Room_Graph and room centres alone; Pacing_Roles may bias room size during layout, and THE Layout_Generator SHALL NOT add, remove or re-route rooms or corridors to satisfy a Pacing_Role.
3. THE Layout_Generator SHALL place Gates only on existing corridors with keys in existing rooms, producing for a given seed the same rooms and corridors with k locks as with 0 locks.
4. THE Zone_Builder SHALL write `.eqg` archives containing no `.mod` entries and `.zon` files containing no placeable-object instances, and SHALL carry prop suggestions only as `prop_hints` in the Sidecar.
5. THE Zone_Generator SHALL use Z as the vertical axis in the Zone_Spec, TER, ZON, Preview and EQ map files, with `floor_z` measured along Z and every standable face normal having a positive Z component, and THE Web_App camera SHALL be Z-up.
6. THE Layout_Generator and the Conformance_Meter SHALL use the zone type's Classic–PoP Style_Profile, and no Zone_Plan field SHALL select another era's profile.
7. THE Zone_Generator SHALL obtain every mesh from the Zone_Spec and SHALL accept no externally authored mesh or model file as generation input.

## Delivery Model (process constraints)

These govern how the system is built, not how it behaves.

- Each milestone M0–M6 in `design.md` is delivered by its own Kiro spec (e.g. `zone-generator-m0-hygiene`) that cites the requirement IDs it implements and owns its own `tasks.md`. This umbrella spec has no `tasks.md`.
- A milestone exits only after the full test suite passes, the frontend builds when `web/` changed, and the human 3D acceptance pass in `docs/ACCEPTANCE.md` is walked. Structural tests are necessary but not sufficient.
- Kiro specs replace the `tasks/` board for new work; open task files are absorbed per the design's scope table, done task files stay as history.
- The custom agents (orchestrator, task-author, task-worker, task-reviewer, task-readiness) are re-pointed from `tasks/<id>.md` to `.kiro/specs/<feature>/tasks.md`.
- Single-writer rule: `ROADMAP.md` and `README.md` (and `tasks/README.md` until retired) are written only in the integration step from the main checkout; a milestone spec's `tasks.md` is owned by the one branch working it.

## Traceability

Milestones and properties refer to `design.md` (Delivery plan; Correctness Properties).

| Requirement | Pillar | Milestone | Properties |
|-------------|--------|-----------|------------|
| 1 Explicit generation modes | P-A | M1 | — (human pass) |
| 2 Control coverage and normalisation | P-A | M1 | P12 |
| 3 Zone type availability | P-A / P-B | M1 | P2, P19 |
| 4 Traversability gate | P-B | M0 (dungeon), M1 (city, wilderness), M5 (cave) | P1, P2 |
| 5 Walkable connections | P-B | M0 | P6, P7, P8 |
| 6 Wilderness terrain alignment | P-B | M1 | P1, P18 |
| 7 Natural, connected caves | P-B | M1 (park), M5 | P1 (cave) |
| 8 Short-name takeover | P-C | M1 (M6 for bundle) | P41 |
| 9 Tier-1 format check | P-C | M1 (normals check M3) | P20, P40, P41 |
| 10 Tier-2 SQL export | P-C | M6 | P37 |
| 11 Format and IR round-trips | P-C | M0 | P11, P13, P14, P15 |
| 12 Mesh-derived outline | P-D | M2 | P21, P22 |
| 13 EQ map file | P-D | M2 | P9, P23, P24, P25 |
| 14 Map and artifacts in the Web_App | P-D | M2 | P21 |
| 15 Era fidelity and conformance | P-E | M3 | P38 |
| 16 Procedural normal maps | P-E | M3 | P9, P40 |
| 17 Textured preview | P-E | M3 | — (human pass) |
| 18 Sessions and interpretation | P-F | M4 | P34, P35 |
| 19 Edit application and acceptance | P-F | M4 | P31, P32, P34, P39 |
| 20 History, undo and redo | P-F | M4 | P32, P33 |
| 21 Composed, solvable layout | P-G | M0 | P3, P4 |
| 22 Topology control | P-G | M3 | P28 |
| 23 Districts | P-G | M3 | P3, P4, P29, P30 |
| 24 Quality gate | P-G | M3 | P26, P27 |
| 25 Quality_Degraded visible | P-G | M3 (generate), M4 (edits) | P39 |
| 26 Determinism and randomness | Cross-cutting | M0 | P2, P9, P10 |
| 27 Advisory isolation | Cross-cutting | M0 | P5, P31 |
| 28 No API by default | Cross-cutting | M0, M4 (edits) | P16 |
| 29 Time budgets | Cross-cutting | M0–M5 | P17 |
| 30 Server security and sessions | Cross-cutting | M0 (bind/CORS), M4 (sessions) | P35, P36 |
| 31 File-system confinement | Cross-cutting | M1 | P41 |
| 32 Settled design constraints | Cross-cutting | all | — |
