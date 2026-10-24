# Requirements Document

## Introduction

M2 — True-layout artifacts. Third milestone spec under the umbrella spec
`zone-generator` (`.kiro/specs/zone-generator/requirements.md` and `design.md`).
It owns the M2 row of the umbrella Delivery Plan and cites the umbrella instead
of restating it: "Req X.Y" below means zone-generator Requirement X.Y, and "Pn"
means umbrella design Correctness Property n.

M2 makes the zone's map tell the truth. One extractor traces the walls and
ledges of the walkable floor from the built TER mesh; that outline feeds an
EverQuest in-client map file and a mesh-traced layer under the existing web
schematic, and the browser offers the build's own files for download. Per the
umbrella traceability table, M2 delivers:

- **Req 12** — Mesh-derived outline (all criteria). *(P21, P22.)*
- **Req 13** — EverQuest in-client map file (all criteria), with the map
  coordinate convention grounded against stock RoF2 data. *(P9, P23, P24, P25.)*
- **Req 14** — True-layout map and artifacts in the Web_App, **except** the
  Export half: the Export action and its `<short>.eqg`, `<short>.sql` and bundle
  downloads in 14.6, and the `export/<short>/<file>` path in 14.5, are M6
  (umbrella design decision 20). M2 serves and offers the build's own
  `<name>.*` files only. *(P21.)*
- **P9 (artifact slice)** — map artifacts are byte-identical across runs with
  the same plan, Pinned_Seed and Build_Name (Req 26.1 as it applies to maps).

Umbrella design decision 19 applies: text below says `zone_type` and
`wilderness`. Umbrella design decision 20 applies: every M2 file is named by the
Build_Name (`<name>`), never by a Target_Shortname.

**Explicitly out of M2** (named so scope stays bounded):

- The Export (`export/<short>/`), the Target_Shortname picker, `<short>`
  renames of the map files, `<short>.sql` and the bundle `.zip` (Req 8, 10 and
  the Export half of 14.5/14.6) — M6. (The umbrella M2 row still lists "bundle";
  decision 20 moved it.)
- District hulls in the map SVG. Req 14.1 lists them among the annotations the
  outline must sit under; they exist only once districts exist (M3). M2 keeps
  the ordering rule so M3 adds hulls after the outline without rework.
- The quality and conformance read-outs the umbrella design places in the
  Artifacts panel (M3).
- Multi-level dungeons. Depth_Bands are built and tested now (on synthetic
  stacked meshes), but generated M2 zones are expected to be single-band.
- Any change to how the Box_Backend or Terrain_Backend builds geometry. The
  outline reports the mesh as it is (see design Open question 2 on open room
  walls).
- Session versions above v1 and the "current cursor version" of Req 14.6 beyond
  "the latest build" (Sessions are M4).

As-built facts this spec was checked against (`master` at `5dabd21`; M1 is
designed but not merged, its wave 1 is in progress on `agent/m1-connectivity`):

- `generators/mapview.py::render_map_svg(spec, size=720, padding=40)` draws a
  spec-only schematic: corridors as straight `from → to` sticks, rooms as
  role-coloured rectangles (fill-opacity 0.82) with depth number, room id,
  semantic type, role label and a boss star, gate links, a legend and a scale
  bar. Its frame is the room and corridor extents, north (+Y) up. There is no
  outline input.
- `ZoneBuilder.build` writes `<name>.map.svg` (schematic) into the build output
  on every build when `write_glb` is on, including attempts the Pipeline later
  rejects. No EQ map file is written anywhere; there is no `generators/mapgeom.py`
  or `generators/eqmap.py`.
- `analyzer/traverse.py` classifies a face as standable by `|n_z| ≥ cos 40°`, so
  box ceilings count as standable; the flood from the safe point reaches only
  upward-facing faces in every build probed (dungeon, city, wilderness).
- The Server serves `/api/zones/{filename}` from a flat `output/web/` and
  rejects any `/`; the Web_App has a Map modal with "Download SVG" only.
- `RoomSpec.boss` is a boolean; no Zone_Spec field carries a boss name.
- The local RoF2 install (`F:\everquest_rof2`) holds 143 stock map files in
  `maps/` (no subfolders); 38 of their zones ship as `.eqg`, 24 of those with a
  `.ter` terrain. The design records the line grammar found there and the
  grounding result for the coordinate convention.

## Depends on M1

M2 is written against M1's **designed** interfaces
(`.kiro/specs/zone-generator-m1-controls-traversability/`). Each dependency
names the M1 wave that delivers it; the design's Delivery waves say which M2
work can start before it lands.

| # | M1 interface M2 consumes | M1 wave | M2 use |
|---|--------------------------|---------|--------|
| D1 | `generators/routing.py` (`corridor_route`, `route_footprint`) | 1 | Doorway_Span oracle in tests; routed corridor centrelines in the SVG |
| D2 | `analyzer/traverse.py` walk surface with the union-find speed-up (`WalkSurface.component`) and no corridor through a third room | 1 | Reachable floor region; extraction time on 30-room dungeons |
| D3 | `zone_type` / `wilderness` vocabulary | 2 | Names in code, Sidecar and tests |
| D4 | Wilderness terrain in the Room_Graph frame; `wilderness` enabled | 3, 4 | Outline on Terrain_Backend meshes (Req 12.11) |
| D5 | Scratch attempt directory per attempt, removed on rejection; move into the build directory on acceptance | 4 | Post-pass artifact writing; nothing left by rejected attempts (Req 14.3) |
| D6 | `GenerateRequest`/`GenerateResponse` with `mode`, `version`, `eqg_url`, `warnings` | 5 | Response gains the map artifact list |
| D7 | Build_Name naming, `<Output_Directory>/<zone id>/v<version>/`, Sidecar on every build, `core/paths.OutputRoot`, `GET /api/zones/{zone_id}/{version}/{filename}` with the Build_File_Allow_List | 6 | Map file names and location, confined writes, the serving route M2 extends to `maps/` |

## Glossary

Umbrella glossary terms are used unchanged, notably Zone_Generator, Server, CLI,
Web_App, Zone_Spec, Zone_Builder, Box_Backend, Terrain_Backend, Geometry_Backend,
Pipeline, Raw_Build, Accepted_Build, Traversal_Validator, Agent_Model,
Enabled_Zone_Types, Build_Name, Build_File_Allow_List, Sidecar,
Output_Directory, EQ_Install, Pinned_Seed, Advisory_Data, Outline_Extractor,
Depth_Band, Main_Band, EQ_Map_Writer, Map_Parser and Map_Viewer. New terms:

- **Floor_Face**: a TER triangle whose unit geometric normal has `n_z ≥ cos 40°` (upward-facing within the Agent_Model's walkable slope; Req 32.5). Box ceilings are not Floor_Faces.
- **Floor_Region**: the set of Floor_Faces the Outline_Extractor works on: in reachable-only mode the Floor_Faces the Traversal_Validator reaches from the safe point, otherwise every Floor_Face.
- **Floor_Boundary**: the points on edges of Floor_Region faces where the floor ends: a point is on the Floor_Boundary when the XY points just outside the face across that edge (any distance up to 0.1 units) lie inside no Floor_Region face whose plane height there is within the Agent_Model's step-up (3 units) of the point. Edges shared or overlapped by neighbouring floor (welds, T-junctions, overlapping corridor ends) are therefore not boundary.
- **Outline**: the Outline_Extractor's result: polylines classified `wall` or `ledge`, each in one Depth_Band, plus the Floor_Region bounds.
- **Doorway_Span**: for each end of a corridor, the segment on its room's footprint boundary that the corridor's end leg crosses: perpendicular to that leg, centred on the leg's axis, as long as the corridor's width. Its two endpoints are the opening's side edges.
- **Stacked_Floors**: two Floor_Region faces that overlap in XY with a vertical separation greater than 12 units (twice the Agent_Model's player height).
- **Map_Convention**: the fixed mapping from world `(x, y, z)` to EQ map coordinates and back.
- **Reference_Zone**: a stock RoF2 zone shipped as an `.eqg` with a `.ter` terrain and a stock `maps/<zone>.txt` in the EQ_Install, used to ground the Map_Convention.
- **Grounding_Check**: the routine that scores the 8 sign/swap candidates for the Map_Convention against a Reference_Zone.
- **Map_Layer**: the parsed or to-be-written content of one EQ map file: an ordered list of line records and label records.
- **Map_Artifacts**: a build's `<name>.map.svg` and its `maps/<name>.txt` / `maps/<name>_1.txt` … `_3.txt` files.
- **Artifacts_Panel**: the Web_App section that shows the map SVG and offers the current build's files for download.

## Requirements

Each requirement implements the umbrella requirement it names; the umbrella's
acceptance criteria are the contract. Criteria restated here are the ones M2
makes true, the M2 scope boundary, or a refinement M2 adds (marked
"refines"); everything else in the cited umbrella requirement still applies.

### Requirement 1: Mesh-derived outline

Implements zone-generator Requirement 12 (criteria 12.1–12.5, 12.10, 12.11).

**User Story:** As a zone author, I want the map outline traced from the actual mesh, so that the map matches the walls the player walks along.

#### Acceptance Criteria

1. THE Outline_Extractor SHALL compute the Outline from the TER mesh and the safe point only, so that identical TER bytes and safe point yield identical polylines, classifications and Depth_Bands regardless of Advisory_Data (Req 12.1).
2. THE Outline_Extractor SHALL emit only segments every point of which lies within 0.05 units of the Floor_Boundary (Req 12.2; refines "boundary edge" to the Floor_Boundary so that T-junctions and overlapping corridor ends are not reported as walls).
3. THE Outline_Extractor SHALL emit no segment that crosses the interior of a Doorway_Span, touching it only at its side edges (Req 12.3).
4. THE Outline_Extractor SHALL emit segments that cover at least 99% of the Floor_Boundary length outside Doorway_Spans to within 0.05 units (Req 12.10).
5. THE Outline_Extractor SHALL classify a polyline piece as `wall` where a non-Floor_Face rising above the floor shares the boundary edge and as `ledge` everywhere else on the Floor_Boundary (floor beyond absent, or more than 3 units away vertically), splitting polylines where the class changes (Req 12.4).
6. WHERE reachable-only extraction is selected (the default), THE Outline_Extractor SHALL use as the Floor_Region the Floor_Faces the Traversal_Validator reaches from the safe point; otherwise THE Outline_Extractor SHALL use all Floor_Faces (Req 12.5).
7. THE Outline_Extractor SHALL accept the TER of every Geometry_Backend serving a zone type in Enabled_Zone_Types (Box_Backend for `dungeon` and `city`, Terrain_Backend for `wilderness`) and satisfy criteria 1–5 on each (Req 12.11).
8. THE Outline_Extractor SHALL return polylines of at least 2 points with no two consecutive points closer than 0.01 units, in an order determined by their coordinates alone.

### Requirement 2: Depth bands

Implements zone-generator Requirement 12 (criteria 12.6, 12.8, 12.9).

**User Story:** As a player, I want overlapping floors drawn on separate map layers, so that a floor above me never hides the one I stand on.

#### Acceptance Criteria

1. THE Outline_Extractor SHALL place each polyline in exactly one of at most 4 Depth_Bands and mark as the Main_Band the band holding the floor under the safe point (Req 12.6).
2. WHEN the Floor_Region contains no Stacked_Floors, THE Outline_Extractor SHALL place all polylines in the Main_Band (Req 12.8).
3. WHEN the Floor_Region contains Stacked_Floors, THE Outline_Extractor SHALL place the polylines of the two floors of every stacked pair in different Depth_Bands, subject to criterion 4 (Req 12.9).
4. IF separating the Stacked_Floors would need more than 4 Depth_Bands, THEN THE Outline_Extractor SHALL merge the adjacent pair of bands with the smallest vertical gap, repeating until 4 remain (Req 12.6).
5. WHEN a polyline runs across the height boundary between two Depth_Bands, THE Outline_Extractor SHALL split the polyline at that boundary so each piece lies in one band.

### Requirement 3: Outline failure fallback

Implements zone-generator Requirement 12 (criterion 12.7).

**User Story:** As a zone author, I want a build that walks but can't be traced to still reach me, so that a map problem never costs me a zone.

#### Acceptance Criteria

1. IF the Floor_Region is empty or the Outline_Extractor raises an error, THEN THE Pipeline SHALL still return the Accepted_Build, write the schematic-only map SVG, write no EQ map file and record a warning `outline_unavailable:<cause>` in the Sidecar and the generate response (Req 12.7).
2. IF the EQ_Map_Writer raises an error after a successful extraction, THEN THE Pipeline SHALL still return the Accepted_Build with the outline map SVG, remove any partly written EQ map file of that build and record a warning `eqmap_unavailable:<cause>`.

### Requirement 4: Grounded map coordinate convention

Implements zone-generator Requirement 13 (criteria 13.5, 13.6).

**User Story:** As a player, I want the in-game map oriented like the zone, so that walking north on the map is walking north in the world.

#### Acceptance Criteria

1. THE Grounding_Check SHALL score each of the 8 sign/swap candidates by the median 3D distance between the Reference_Zone's stock map line endpoints, converted back to world with that candidate and Z unchanged, and the nearest edge of a non-Floor_Face of that zone's TER.
2. THE EQ_Map_Writer SHALL use the Map_Convention equal to the candidate the Grounding_Check selects for each Reference_Zone it is run on, that candidate's median being at most 5 units and at most 0.25 times the runner-up's median (Req 13.5).
3. THE EQ_Map_Writer SHALL leave Z unchanged under the Map_Convention (Req 13.5).
4. FOR ALL finite world points, converting to map coordinates and back SHALL return the original point (Req 13.6).
5. WHERE the EQ_Install or a Reference_Zone's files are absent, THE Zone_Generator SHALL keep the pinned Map_Convention and the Grounding_Check test SHALL report itself skipped.
6. THE Grounding_Check SHALL read the EQ_Install only, writing nothing under it (Req 31.2).

### Requirement 5: EQ map file writer

Implements zone-generator Requirement 13 (criteria 13.1, 13.2, 13.7–13.10).

**User Story:** As a player, I want a map file the RoF2 client's map window can load, so that the generated zone has a usable in-game map.

#### Acceptance Criteria

1. WHEN an Accepted_Build has an Outline, THE EQ_Map_Writer SHALL write one file per Depth_Band into `<build dir>/maps/`: the Main_Band to `<name>.txt` and the remaining bands to `<name>_1.txt` through `<name>_3.txt` in ascending order of median floor Z, writing no file for a missing band (Req 13.1, with Build_Name naming per decision 20).
2. THE EQ_Map_Writer SHALL write one ASCII record per line, each line ending in CR LF, line records as `L x1, y1, z1, x2, y2, z2, r, g, b` and label records as `P x, y, z, r, g, b, size, text`, with coordinates to exactly 4 decimal places, integer colour channels 0–255, size ∈ {1, 2, 3}, non-empty label text, and spaces in label text written as `_` (Req 13.2).
3. THE EQ_Map_Writer SHALL write one line record per consecutive point pair of every Outline polyline in that band and no line record whose two endpoints are equal.
4. THE EQ_Map_Writer SHALL place every line endpoint, converted back to world, inside the Floor_Region's XY bounding box plus 0.5 units and at a Z between the lowest Floor_Region Z and the highest Floor_Region Z plus the Agent_Model's player height (6 units) (Req 13.7).
5. THE EQ_Map_Writer SHALL write exactly one label `Entrance` and, for each room with Pacing_Role `climax`, exactly one label `Boss` (no Zone_Spec field carries a boss name in M2), no other labels, all at size 2, each in the file of the Depth_Band holding that room's floor (Req 13.8).
6. THE EQ_Map_Writer SHALL place every label inside its room's footprint at a Z between the room's `floor_z` and `floor_z` + 6 (Req 13.9).
7. THE EQ_Map_Writer SHALL colour every line of a Depth_Band with that band's single colour: black (0, 0, 0) for the Main_Band and a distinct non-black colour for each other band, for walls and ledges alike (Req 13.10).

### Requirement 6: EQ map parser

Implements zone-generator Requirement 13 (criteria 13.3, 13.4, 13.11).

**User Story:** As a developer, I want a reader for the EQ map grammar that round-trips our files and reads stock ones, so that what we write is checked by what we read.

#### Acceptance Criteria

1. THE Map_Parser SHALL parse `L` and `P` records into a Map_Layer, accepting one or more spaces (or none) after each comma, integer or decimal coordinates, CR LF or LF line endings and blank lines, and keeping everything after the seventh comma of a `P` record (commas included, surrounding whitespace removed) as label text (Req 13.3).
2. FOR ALL Map_Layers, parsing the EQ_Map_Writer's formatted text SHALL yield a Map_Layer with the same record counts and order, coordinates within 0.00005, identical colours and sizes, and label text equal to the original with spaces replaced by `_` (round-trip, Req 13.4).
3. IF a non-blank line is malformed, THEN THE Map_Parser SHALL skip that line, continue parsing and report the count and line numbers of the skipped lines (Req 13.11).
4. WHEN the EQ_Install is present, THE Map_Parser SHALL parse every stock file in its `maps/` folder with zero skipped lines.

### Requirement 7: True-layout map SVG

Implements zone-generator Requirement 14 (criteria 14.1, 14.2).

**User Story:** As a zone author, I want the web map to show the real walls under the helpful annotations, so that the map agrees with the 3D view without losing the room roles and gates.

#### Acceptance Criteria

1. WHEN an Outline is supplied, THE Map_Viewer SHALL draw every Outline polyline (walls solid, ledges dashed) as SVG elements placed after the background and before every schematic annotation in document order (corridors, rooms, depth numbers, room ids, labels, boss markers, gate links, legend and scale bar; District hulls join this list in M3) (Req 14.1).
2. WHEN no Outline is supplied, THE Map_Viewer SHALL produce output byte-identical to the pre-M2 schematic-only rendering for the same Zone_Spec, size and padding (Req 14.2).
3. WHEN an Outline is supplied, THE Map_Viewer SHALL frame the map on the union of the room extents and the Outline bounds with north (+Y) up, and draw room fills with fill-opacity at most 0.35 so the outline stays visible under them.
4. WHEN an Outline is supplied, THE Map_Viewer SHALL draw each corridor along its routed centreline instead of a straight `from → to` line.
5. WHEN an Outline is supplied, THE Map_Viewer SHALL add `wall` and `ledge` entries to the legend.

### Requirement 8: Map artifacts for accepted builds only

Implements zone-generator Requirements 13.1 and 14.3, and P9 for map artifacts (Req 26.1).

**User Story:** As a zone author, I want map files only for the build I am handed, and the same files every time I repeat a build, so that a folder never holds a map of a zone that doesn't exist.

#### Acceptance Criteria

1. WHEN the Pipeline accepts a build, THE Pipeline SHALL extract the Outline and write the Map_Artifacts into that build's directory before returning, through the Output_Directory confinement of M1 (Req 31.1).
2. IF a Raw_Build is rejected, THEN THE Pipeline SHALL leave no map SVG or EQ map file of that Raw_Build in the Output_Directory (Req 14.3).
3. FOR ALL generate runs with the same plan, Pinned_Seed and Build_Name, THE Pipeline SHALL write byte-identical `<name>.map.svg` and `maps/*.txt` files (P9, Req 26.1).
4. WHEN the Pipeline writes Map_Artifacts, THE Pipeline SHALL record in the Sidecar the relative paths of the map files written and, per Depth_Band, its index, role, height range and polyline counts by class.
5. THE CLI SHALL write the same Map_Artifacts as the Server for the same plan, Pinned_Seed and Build_Name.

### Requirement 9: Serving build files

Implements zone-generator Requirement 14 (criteria 14.5 without the Export path, 14.7) and Requirement 30.10 for the `maps/` path.

**User Story:** As a zone author, I want every file of my build reachable by a stable URL, so that the browser can show and download them.

#### Acceptance Criteria

1. WHEN `GET /api/zones/{zone_id}/{version}/{filename}` or `GET /api/zones/{zone_id}/{version}/maps/{filename}` names an existing file in that build's directory, THE Server SHALL serve the file's bytes unchanged (Req 14.5).
2. IF a build-file request passes the checks of Req 30.10 but names no existing file in that build's directory, THEN THE Server SHALL respond HTTP 404 with no file content (Req 14.7).
3. IF any segment of a build-file request fails `^[A-Za-z0-9_.-]+$`, contains `..`, has an extension outside the Build_File_Allow_List, or resolves outside that build's directory within the Output_Directory, THEN THE Server SHALL respond HTTP 400 with no file content (Req 30.10).
4. WHEN a build-file request uses HEAD, THE Server SHALL respond with the status and headers the GET would produce and no body.
5. WHEN a build is accepted, THE Server SHALL include in the generate response the URL of the map SVG, of `<name>.eqg` and of each EQ map file written.

### Requirement 10: Artifacts panel

Implements zone-generator Requirement 14 (criteria 14.4, 14.6 without the Export action and its downloads, 14.8).

**User Story:** As a zone author, I want to see the true-layout map and download my build's files from the browser, so that I can review the zone and take it with me.

#### Acceptance Criteria

1. WHEN an Accepted_Build is returned, THE Artifacts_Panel SHALL display that build's map SVG, replacing any earlier one (Req 14.4).
2. THE Artifacts_Panel SHALL offer, for the latest build, downloads of the map SVG, a PNG, each EQ map `.txt` file and `<name>.eqg`, each saved under its build file name (the PNG as `<name>.map.png`) (Req 14.6, build files only).
3. WHEN the PNG download is requested, THE Web_App SHALL render the PNG in the browser from the displayed SVG at 2× its viewBox width and height, with no server request (Req 14.6).
4. IF an artifact fails to load, THEN THE Artifacts_Panel SHALL mark that artifact unavailable and keep the other artifacts usable (Req 14.8).
5. THE Artifacts_Panel SHALL present each download as a native link or button with a visible text label naming the file type, reachable by keyboard.
6. WHILE a field of the Artifacts_Panel or the map dialog has focus, THE Web_App SHALL keep movement keys from moving the camera (Req 2.7).

## Delivery order within M2

1. **EQ map core (Requirements 4, 5.2, 6).** Pinned Map_Convention with the
   Grounding_Check test, the record formatter and the parser. Needs nothing from
   M1.
2. **Outline extractor and Depth_Bands (Requirements 1, 2).** On synthetic
   meshes first, then on box builds. Needs M1 wave 1 (D1, D2).
3. **Map SVG outline layer (Requirement 7).** Needs step 2 and D1.
4. **Pipeline post-pass, EQ map files, Sidecar, CLI (Requirements 3, 5, 8).**
   Needs M1 waves 4 and 6 (D5, D7).
5. **Serving and the Artifacts_Panel (Requirements 9, 10).** Needs M1 waves 5
   and 6 (D6, D7).
6. **Wilderness coverage and the human pass.** Needs M1 waves 3 and 4 (D4).

## Exit criteria

M2 exits only when:

1. The full suite passes (`python -m pytest tests/ -q`), including the M2
   properties, and a `--hypothesis-profile=thorough` run is recorded.
2. The frontend builds (`web/` changed).
3. The `docs/ACCEPTANCE.md` M2 section is walked and signed off: the web map's
   walls match the 3D view on seeds 1955208177, 1516796975, 678358326 and one
   flat seed; the PNG, `.txt` and `.eqg` downloads arrive named `<name>.*`.
4. The in-client check (the `.txt` loads from a client `maps/` subfolder with
   lines on walls and correct orientation) is walked once a generated zone can
   be entered in the client. Entering it needs a short-name takeover, which is
   the M6 Export; see design Open question 1 for how M2 closes without it.
