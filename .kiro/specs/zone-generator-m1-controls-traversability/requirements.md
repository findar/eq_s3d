# Requirements Document

## Introduction

M1 — Controls + all-zone-type traversability + format gate. Second milestone spec
under the umbrella spec `zone-generator`
(`.kiro/specs/zone-generator/requirements.md` and `design.md`). It owns its
slice of the umbrella Delivery Plan (the M1 row) and cites the umbrella instead
of restating it: "Req X.Y" below means zone-generator Requirement X.Y, and "Pn"
means umbrella design Correctness Property n.

M1 makes the browser a first-class, two-mode generator and makes every zone type
the UI offers genuinely walkable, with a Tier-1 format check in the build path and a
short-name takeover install model. Per the umbrella traceability table, M1
delivers these requirement slices:

- **Req 1** — Explicit generation modes (prompt vs controls, each its own
  Generate action; the CLI stays controls-only).
- **Req 2 (geometry-control slice)** — Control coverage and plan
  normalisation: M1 exposes the controls that change generated geometry today
  (zone type, room count, size, verticality, locks, seed, Target_Shortname);
  the content-layer and district controls wait for M3, where they first drive
  generation. Normalisation of every plan field applies now. *(P12.)*
- **Req 3** — Zone type availability (offer only Enabled_Zone_Types; gate by
  the traversability result). *(P2, P19.)*
- **Req 4 (city, wilderness slice)** — the traversability gate, extended from
  M0's dungeon-only gating to city and wilderness. *(P1, P2.)*
- **Req 6** — Wilderness terrain alignment (terrain generated in the Room_Graph
  frame with walkable room pads), the precondition for gating wilderness.
  *(P1, P18.)*
- **Req 7 (park slice only)** — keep the Zone_Generator free of any cave zone
  type or separate cave pipeline (Req 7.11); the Natural_Style transform itself
  is M5, not M1.
- **Req 8** — Short-name takeover install model (`target_shortname` end to end,
  the Known_Zone_List, the `/api/shortnames` picker; the bundle `.zip` is M6).
  *(P41.)*
- **Req 9** — Tier-1 RoF2 format check in the Pipeline (the normal-map check in
  9.4 is deferred to M3 with normal maps). *(P20, P40, P41.)*
- **Req 31** — File-system confinement (the tool writes only inside the
  Output_Directory and never touches the EQ_Install). *(P41.)*
- **Req 11.10 (zone-type slice) and umbrella design decision 19** — the
  zone-type vocabulary rename: `theme` → `zone_type`, `outdoor` → `wilderness`,
  with legacy keys and values accepted on load. M1 rebuilds this surface anyway
  (modes, controls, availability), so the rename rides along; the content-layer
  renames and the `condition` axis are M3.

M1 also carries a **re-verification of the M0 corridor-connectivity
requirement**. Req 5 (Walkable connections) and its properties P6/P7/P8 are
marked done in M0, but they were validated under a Traversal_Validator whose
face-adjacency test was later found unsound (it bridged real gaps by comparing
XY bounding boxes and centroid Z). M0 corrected the validator (true triangle
contact at matching floor height) and the M0 suite re-ran green — but the
build-level navigability, ramp and determinism properties only draw **2–12
rooms**, and the disconnection a user saw in the human pass was on **30-room**
dungeons. M1 therefore widens and strengthens the connectivity guarantee under
the sound gate (see Requirement 5 below) before it can honestly claim Req
4.3 for every zone type. **Flat first, then elevation** (user decision): prove flat
corridors connected, then harden the elevation path on top; a flat / no-elevation
build is available so the flat case can be generated and verified directly.

**Explicitly out of M1** (named so scope stays bounded):
- Angled (non-axis-aligned) corridors. Req 5.6 still mandates three axis-aligned
  legs; relaxing it is a later umbrella amendment paired with the room-shape
  vocabulary (umbrella design decision 18), after M1's flat connectivity is
  proven in 3D.
- The room-shape vocabulary (umbrella design decision 18).
- The Natural_Style / `cave` Purpose (umbrella Req 7 transform, M5; Req 33, M3).
- Controls for topology, the district switch, Purpose, Builder, Inhabitants,
  Condition and Element (Req 2.1 / 2.2 remainder) and the content-layer field
  renames (`dungeon_theme` → `purpose`, `dungeon_race` → `builder` /
  `inhabitants`, `elemental_tint` → `element`, `semantic_type` → `room_type`) —
  all M3. Those fields still normalise in M1 (Req 2.8) under their current names.
- Mapping Zone_Type and Enclosure onto the EQ `ztype`, sky and outdoor flags (M6).
- The normal-map format check (Req 9.4), districts, topology, the quality gate
  (umbrella M3), and the Tier-2 SQL export / bundle (Req 10, M6).

As-built facts this spec was checked against (current `master` after the M0
merge):
- `server/app.py` binds `127.0.0.1:8000` and uses `LocalCORSMiddleware` with an
  explicit origin list (M0). It exposes `/api/generate`, `/api/themes`,
  `/api/zones/{filename}`, `/api/health` and `/api/version`. There is **no**
  `mode` field, **no** `/api/shortnames`, and no `target_shortname` anywhere.
- `GenerateRequest` is the legacy flat shape `{prompt?, theme, rooms, elevation,
  seed}`; a non-empty prompt silently wins over the controls. The controls path
  does **not** yet go through `ZonePlan.from_controls` — that method does not
  exist; controls currently call `LayoutGenerator(...).generate(...)` directly
  while prompts call `make_plan` → `plan_to_spec`. Req 1.7/1.8 (both modes yield
  identical specs for equal plans + seed) is therefore new work.
- `generate_validated` gates **dungeon only** (`DEFAULT_GATED_THEMES = {"dungeon"}`);
  city and outdoor (to be renamed wilderness) pass through ungated. The outdoor
  terrain mesh is generated in
  a different coordinate frame than the Room_Graph (origin → +X/+Y rather than
  centred on the rooms), so it cannot be gated until Req 6 lands.
- `analyzer/traverse.py` is the sound validator (true XY triangle contact +
  floor-height-at-contact, M0). It has no `rof2check` sibling yet.
- The `.eqg`/TER/ZON/GLB/map artifacts are named `<zone_id>.*` where `zone_id`
  is `gen_<ts>_<hex>`; there is no short name and no `maps/<short>.txt`.
- `web/` has one Generate button, a `#prompt` box and an advanced panel with
  `#theme`, `#rooms`, `#elevation`, `#seed`; it added room-id labels and a
  server/web build-version line in M0. There is no controls-mode button,
  no size/verticality/locks/topology/archetype controls, and no short-name
  picker.
- The zone-level selector is the field `theme` with values `dungeon`, `outdoor`
  and `city` throughout (`ai/schema.py::VALID_THEMES`, `server/app.py`, CLI
  `--theme`, `web/`, the Sidecar); no substitution warning exists yet.
- The Web_App already suppresses movement keys while a form field has focus
  (Req 2.7 is satisfied today; M1 keeps it green as the panel grows).

## Glossary

Umbrella glossary terms are used unchanged, notably Zone_Generator, Server, CLI,
Web_App, Planner, Zone_Plan, Zone_Spec, Layout_Generator, Zone_Builder,
Geometry_Backend, Box_Backend, Terrain_Backend, Pipeline, Raw_Build,
Accepted_Build, Traversal_Validator, Format_Checker, Zone_Type,
Defined_Zone_Types, Enabled_Zone_Types, Gated_Zone_Type, Enclosure, Room_Graph, Target_Shortname, Known_Zone_List,
Default_Target, Fresh_Seed, Pinned_Seed, Sidecar and Output_Directory. New terms
introduced by this spec are defined where first used.

## Requirements

Each requirement below implements the umbrella requirement it names; the
umbrella's acceptance criteria are the contract. Criteria restated here are the
ones M1 makes true for the first time, the M1-specific scope boundary, or a
strengthening M1 adds; everything else in the cited umbrella requirement still
applies.

### Requirement 1: Explicit generation modes

Implements zone-generator Requirement 1.

**User Story:** As a zone author, I want a description mode and a controls mode
with separate Generate actions, so that I always know which input produced the
zone.

#### Acceptance Criteria

1. THE Server SHALL accept a `mode` field on `/api/generate` of `prompt` or
   `controls` and SHALL honour Req 1.1–1.6 (mode routing, legacy-field mapping
   when `mode` is absent).
2. THE Server SHALL build the controls-mode Zone_Plan through a single
   `ZonePlan.from_controls` path and the prompt-mode Zone_Plan through the
   Planner, so that two requests whose plans and Pinned_Seed are equal expand to
   identical Zone_Specs (Req 1.7) and a controls request equals the CLI's plan
   for the same options and seed (Req 1.8, 1.9).
3. THE Server SHALL reject an unknown `mode` and an empty prompt-mode prompt with
   HTTP 400 before any build, creating no Session and writing no file (Req 1.10,
   1.11), and SHALL include the producing `mode` in the response (Req 1.12).
4. THE Web_App SHALL present two Generate actions ("Generate from description"
   and "Generate from controls") that send the matching `mode` (Req 1.1, 1.2),
   and SHALL show beside the current zone which action produced it (Req 1.12).

### Requirement 2: Control coverage and plan normalisation

Implements zone-generator Requirement 2.

**User Story:** As a zone author, I want every parameter the plan understands to
be available as a control and to be normalised predictably, so that I can dial in
a zone without surprises.

#### Acceptance Criteria

1. THE Web_App Controls panel SHALL expose zone type, room count (1–30), size,
   verticality (including `flat`), locks (0–5), seed and Target_Shortname, and
   SHALL send a blank seed as "no seed" (Req 2.1, geometry-control slice).
2. THE CLI SHALL accept zone type, room count, size, verticality, locks, seed
   and Target_Shortname as options and build every plan through the controls
   path (Req 2.2 slice, Req 1.9).
3. THE Web_App and CLI SHALL NOT yet expose topology, the district switch,
   Purpose, Builder, Inhabitants, Condition or Element (deferred to M3, where
   they first drive generation); a controls-mode request or plan dictionary
   that carries any of those fields SHALL still be normalised per criterion 4.
4. THE Planner SHALL normalise exactly as Req 2.3–2.6 and 2.8 require: truncate
   and clamp room count and locks, drop out-of-schema keys, replace
   out-of-vocabulary values with the field default (including a stored zone
   type `cave` → `dungeon`), be idempotent, and produce equal field values whether an
   input arrives through the plan-dictionary path or the controls path (P12).
5. THE Server SHALL reject a non-integer room count, locks or seed with HTTP 400
   naming the field before any build (Req 2.9); THE CLI SHALL exit status 2 on an
   out-of-domain option, writing no file (Req 2.10).
6. THE Web_App SHALL keep delivering key presses to a focused field without
   moving the camera as the panel grows (Req 2.7).

### Requirement 3: Zone type availability tied to the gate

Implements zone-generator Requirement 3.

**User Story:** As a zone author, I want the tool to offer only zone types that
are known to produce walkable zones, so that I never receive a broken zone.

#### Acceptance Criteria

1. THE Server SHALL serve the Defined_Zone_Types at `GET /api/zone_types`
   (legacy alias `GET /api/themes`), each with `enabled` equal to membership in
   Enabled_Zone_Types and a non-empty `reason` (Req 3.1), and SHALL treat every
   member of Enabled_Zone_Types as a Gated_Zone_Type (Req 3.2).
2. THE Enabled_Zone_Types SHALL be exactly the zone types whose
   Geometry_Backend passes the traversability sweep (Req 4.3): `dungeon` (from
   M0), plus `city` and `wilderness` once Requirements 4 and 6 land. A zone
   type is offered as enabled only after its sweep passes.
3. THE Web_App SHALL render non-enabled zone types disabled with their
   `reason` and preselect a member of Enabled_Zone_Types (Req 3.3); THE Server
   and CLI SHALL reject a controls/CLI zone type outside Enabled_Zone_Types
   (Req 3.4, 3.6) and substitute `dungeon` with a `zone_type_substituted`
   warning for a prompt-planned disabled zone type (Req 3.5, 3.7).
4. THE Server SHALL return only Accepted_Builds whose zone type is a member of
   Enabled_Zone_Types (Req 3.8).

### Requirement 4: Traversability gate for city and wilderness

Implements zone-generator Requirement 4 (the city and wilderness slice; M0
delivered the dungeon slice, M5 the natural style).

**User Story:** As a zone author, I want every returned zone — dungeon, city or
wilderness — walkable end to end by an EQ-scale player, so that no room is ever
stranded.

#### Acceptance Criteria

1. FOR `city` and `wilderness`, any seed in 0–2,147,483,647, room counts 2–12
   and verticality on or off, THE Geometry_Backend for that zone type SHALL produce a
   Raw_Build that passes the sound Traversal_Validator (Req 4.3), measured under
   the M0-corrected adjacency test.
2. THE Pipeline SHALL gate `city` and `wilderness` as Gated_Zone_Types
   (extending today's `DEFAULT_GATED_THEMES`), retrying on a Fresh_Seed and raising on exhaustion or
   a pinned failure exactly as Req 4.4–4.11 specify, and SHALL build each attempt
   in a scratch directory it removes on rejection (Req 4.11, and Requirement
   10 of this spec for confinement).
3. WHERE a Geometry_Backend's optional dependency is missing, THE Zone_Builder
   SHALL fall back to the Box_Backend with a `backend_fallback` warning
   (Req 4.8).

### Requirement 5: Large-zone corridor connectivity (strengthens umbrella Req 5 under the sound gate)

Strengthens zone-generator Requirement 5 (M0) and its properties P6/P7/P8. This
is M1's foundational slice: the "every offered zone type walks end to end" exit
criterion depends on it.

**User Story:** As a player, I want every corridor to actually land on both rooms
it joins — including in large, 30-room dungeons — so that I never find a room I
can see but cannot reach.

#### Acceptance Criteria

1. THE build-level navigability, flush-opening and ramp-subdivision properties
   (P1, P7, P8) SHALL cover room counts through **30** (not only 2–12), so the
   regime users actually generate is tested.
2. THE Zone_Builder SHALL satisfy a corridor-floor-continuity property: for every
   corridor of a Gated_Zone_Type build, the corridor's walkable floor SHALL form a
   continuous path from a standable face in its `from_room` to a standable face
   in its `to_room` with no gap, verified on the mesh under the sound
   Traversal_Validator — not merely a floor face present at each opening.
3. THE Pipeline SHALL generate a **flat** (no-elevation) build on request from
   the controls, the CLI and the plan (verticality `flat`), and a flat
   Gated_Zone_Type build SHALL
   pass criteria 1 and 2 for every seed in the sweep and room counts through 30.
4. WHEN criteria 1–3 hold for flat builds, THE Zone_Builder SHALL hold the same
   continuity property for elevation-on builds across the sweep (the
   flat-first-then-elevation order), with any failure fixed at the root in the
   Layout_Generator or Box_Backend, never by weakening a property.
5. Req 5.1–5.6 (flush openings, grade cap, confined rise, the three-axis-aligned-
   leg route) SHALL remain satisfied unchanged; M1 adds continuity and the
   30-room range on top of them and does not relax the axis-aligned-leg rule
   (angled corridors are out of M1).

### Requirement 6: Wilderness terrain alignment

Implements zone-generator Requirement 6.

**User Story:** As a zone author, I want wilderness terrain to sit under the
rooms the layout planned, so that wilderness zones are as walkable as dungeons.

#### Acceptance Criteria

1. THE Terrain_Backend SHALL generate terrain in the Room_Graph coordinate frame
   with no translation, rotation or scaling and bounds past every room and
   corridor footprint (Req 6.1), leaving every room and corridor unchanged
   (Req 6.4).
2. THE Terrain_Backend SHALL hold each terrain vertex inside a room footprint
   within that room's `floor_z` ± 1 unit (Req 6.2), keep corridor-footprint
   triangles at or under 40° slope with edge-adjacent centroids within 3 units in
   Z (Req 6.3, 6.5), and run each corridor's centreline continuously between its
   rooms' `floor_z` within ± 1 unit (Req 6.6).
3. WHEN criteria 1 and 2 hold, `wilderness` SHALL become a Gated_Zone_Type
   (Requirement 4 of this spec) and a member of Enabled_Zone_Types
   (Requirement 3 of this spec), as the terrain is then under its rooms (P1,
   P18).

### Requirement 7: No cave zone type or cave pipeline

Implements zone-generator Requirement 7, acceptance criterion 7.11 only (the
"park" slice; the Natural_Style transform is M5).

**User Story:** As the project owner, I want the Zone_Generator to contain no
cave zone type or separate cave geometry pipeline, so that caves return only
as a dungeon Purpose (M3) and the natural style (M5), not a parallel path.

#### Acceptance Criteria

1. THE Zone_Generator SHALL build every zone through the Box_Backend or the
   Terrain_Backend, with Defined_Zone_Types (dungeon, city, wilderness) the only
   Zone_Type vocabulary, offering no cave zone type and containing no separate
   cave geometry pipeline (Req 7.11). (M0 removed the pipeline; M1 keeps it
   absent as the backend registry and zone-type surface change.)

### Requirement 8: Short-name takeover install model

Implements zone-generator Requirement 8 (the M6 bundle `.zip` excepted).

**User Story:** As a zone author, I want to choose which existing RoF2 zone my
generated zone replaces and get files already named for it, so that installing is
a copy, not a rename exercise.

#### Acceptance Criteria

1. THE Known_Zone_List SHALL provide each known RoF2 short name's long name,
   EQEmu zone id, container type and `in_install` flag per Req 8.1–8.3, sourced
   from a bundled list and marked against the EQ_Install when configured.
2. THE Server SHALL serve the list and the Default_Target at
   `GET /api/shortnames` (Req 8.4); THE Web_App SHALL show the Target_Shortname
   picker beside both Generate actions with the filtering, ordering, default and
   install note of Req 8.5.
3. THE Zone_Generator SHALL resolve the Target_Shortname per Req 8.6–8.9 and
   8.14 (default when blank; HTTP 400 / CLI exit 2 for an unknown controls/CLI
   name; planner defaulting and prompt detection), the Default_Target being
   `arena` (Req 8.13).
4. THE Zone_Builder SHALL name the archive and its TER/ZON entries and model
   reference per Req 8.10 and every other build artifact per Req 8.11, into a
   per-zone-id-and-version directory (Req 8.12), using the lowercase short name
   everywhere except `TER_<SHORT>.TER` (Req 8.15, P41). The `.bundle.zip` named
   in Req 8.11 is produced in M6, not M1.

### Requirement 9: Tier-1 RoF2 format check in the pipeline

Implements zone-generator Requirement 9 (the normal-map check 9.4 excepted —
normal maps and their check are M3).

**User Story:** As a zone author, I want every build checked against the format
rules the RoF2 client relies on, so that a file the tool hands me is loadable.

#### Acceptance Criteria

1. THE Format_Checker SHALL run in the Pipeline on every build and verify the
   archive, TER/ZON round-trip and model reference, material indices and diffuse
   DDS, collision policy, safe-point standable face and finite coordinates, and
   the Target_Shortname name agreement — Req 9.1–9.3 and 9.5–9.7.
2. THE Pipeline SHALL treat the Format_Checker as a hard gate alongside the
   Traversal_Validator (Req 4.4): a build of a Gated_Zone_Type is returned only after
   both pass, with the same retry/exhaustion behaviour, and the Format_Checker
   result written into the Sidecar (Req 9.12).
3. THE Format_Checker SHALL report one message per failed check (Req 9.10) and
   SHALL raise no exception to its caller when the archive or an entry cannot be
   parsed, still reporting every independent check (Req 9.11).
4. FOR every member of Enabled_Zone_Types and any seed, THE Zone_Builder SHALL produce a
   Raw_Build that passes the Format_Checker (Req 9.9, scoped to `built`
   geometry; the `natural` style is M5). The normal-map check (Req 9.4) is
   deferred to M3 and SHALL be absent until normal maps exist.

### Requirement 10: File-system confinement

Implements zone-generator Requirement 31.

**User Story:** As a zone author, I want the tool to write only into its output
folder and never touch my EverQuest install, so that installing stays my
deliberate, reversible step.

#### Acceptance Criteria

1. THE Zone_Generator SHALL confine every create/write/rename/delete (including
   the per-attempt scratch directories of Requirement 4 of this spec and any
   dependency temp files) to paths resolving inside the Output_Directory (Req 31.1, 31.4),
   and SHALL leave the EQ_Install byte-identical (Req 31.2).
2. THE Zone_Generator SHALL refuse to run if the Output_Directory equals or lies
   inside the EQ_Install (Req 31.5), read API keys only from the environment and
   `.env` (Req 31.3), and never write a key value into any output, response, log
   or console (Req 31.6).

### Requirement 11: Zone type vocabulary rename

Implements zone-generator Requirement 11.10 (the zone-type slice) and umbrella
design decision 19.

**User Story:** As a zone author, I want the zone-level selector named for what
it is, so that "dungeon / city / wilderness" is never confused with the
haunted-or-flooded flavour of a zone that M3 adds.

#### Acceptance Criteria

1. THE Zone_Plan, Zone_Spec, Sidecar, Server request and response bodies, CLI
   and Web_App SHALL name the zone-level selector `zone_type` with values
   `dungeon`, `city` and `wilderness`, and SHALL write no `theme` key and no
   `outdoor` Zone_Type value.
2. WHEN a Zone_Plan dictionary, Zone_Spec dictionary or generate request
   carries the legacy key `theme` or the legacy value `outdoor`, THE
   Zone_Generator SHALL read it as `zone_type` / `wilderness`, preferring
   `zone_type` when both keys are present (Req 11.10).
3. THE CLI SHALL accept `--zone-type` and SHALL accept `--theme` as a
   deprecated alias with the same values (legacy `outdoor` included).
4. THE Server SHALL serve `GET /api/zone_types` and keep `GET /api/themes` as an
   alias returning the same body, and SHALL emit warnings named
   `zone_type_substituted` and record `planned_zone_type` in the Sidecar
   (Req 3.5).
5. FOR ALL Zone_Plans and Zone_Specs, serialising, renaming the `zone_type` key
   to `theme` (and `wilderness` to `outdoor`) and loading back SHALL yield a
   value equal to the original (legacy-load round-trip).
6. THE M1 rename SHALL leave the content-layer fields (`dungeon_theme`,
   `dungeon_race`, `elemental_tint`, `semantic_type`, `room_theme`,
   `district_theme`) under their current names; those renames are M3.

## Delivery order within M1

M1 lands in waves so the connectivity foundation is proven before the zone
types that depend on it are gated:

1. **Connectivity (Requirement 5).** Widen the properties to 30 rooms, add
   the corridor-floor-continuity property, and add the flat build path. Fix any
   failure at the root. Prove flat first, then elevation. Verified in 3D.
2. **Zone type rename (Requirement 11).** `theme` → `zone_type`, `outdoor` →
   `wilderness`, legacy keys on load. Mechanical; lands early so later waves
   are written against the new names.
3. **Backend registry + wilderness alignment (Requirements 6, 7).** The
   `GeometryBackend` registry, terrain in the Room_Graph frame with room pads.
4. **All-zone-type gate + availability (Requirements 4, 3).** Gate city and
   wilderness; `/api/zone_types` reflects the sweep result.
5. **Controls + modes (Requirements 1, 2).** `ZonePlan.from_controls`, the
   explicit `mode`, the two Generate actions and the geometry-control panel.
6. **Short names + format gate (Requirements 8, 9, 10).** The
   Known_Zone_List, the picker, `<short>.*` naming, `rof2check` in the pipeline,
   and confinement.

Waves 2, 5 and 6 touch `server/app.py`, `ai/expand.py` and `generators/pipeline.py`
(cross-branch hotspots); keep one owner of each at a time.

## Exit criteria

M1 exits only when:

1. The full suite passes (`python -m pytest tests/ -q`), including the widened
   30-room connectivity properties and the corridor-floor-continuity property,
   and a `--hypothesis-profile=thorough` run is recorded.
2. The frontend builds (`web/` changed).
3. The `docs/ACCEPTANCE.md` human pass is walked and signed off: both Generate
   actions do what they say; **every offered zone type (dungeon, city,
   wilderness) walks end to end in the viewer**, including flat and elevated 30-room
   dungeons and the seeds from the M0 pass (`1949459644`, `1510177507`);
   wilderness rooms sit on their pads; the short-name picker lists the install's zones and
   the downloaded files carry the chosen short name. Structural tests are
   necessary but not sufficient — the connectivity and terrain claims are
   confirmed in 3D.
4. Any root-cause fix that changed geometry records the affected seeds for the
   3D pass.
