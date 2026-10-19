# TASK: eq-map-export

Status: not-started        <!-- not-started | in-progress | blocked | done -->
Epic: In-client EQ map generation — produce the plain-text map files the
      EverQuest client draws on its in-game Map window, so a player who loads a
      generated zone sees a real top-down map of it. New capability (ROADMAP
      backlog: "EQ in-client map export"); distinct from the existing web SVG
      schematic.
Last touched: created 2026-10-18 from a roadmap-review discussion.

## Goal

The EverQuest client renders its in-game map (the "M" window) from plain-text
files in its `maps/` folder: each line of the file is either a line segment
(`L x1,y1,z1,x2,y2,z2,R,G,B`) tracing a wall, or a label (`P x,y,z,R,G,B,size,text`).
Today this project generates no such file — a player who loads a generated zone
has a blank in-game map. This task adds a generator step that, **after a zone
passes the traversability validator**, extracts the zone's walkable wall outline
from its 3D geometry and writes a correct EQ map file so the in-game map matches
the walls the player actually walks into.

The map MUST be derived from the zone's actual triangle mesh (the "TER mesh" —
the terrain geometry stored in the `.eqg`), not from the abstract room/corridor
plan (the "ZoneSpec" — the data model of room boxes and corridor endpoints).
Those two disagree in exactly the ways that matter for a map: a corridor stored
in the plan as two endpoints is realised in the mesh as a multi-segment bent
ramp, so a plan-derived map would draw a straight line through solid rock. The
mesh is ground truth; a navigation aid must trace ground truth. Done when loading
a generated dungeon zone in a client (or a faithful viewer of the `.txt`) shows a
map whose lines sit on the zone's actual walls, correctly oriented.

Scope is **dungeon/box backend only** — the one backend whose mesh is trusted and
sits in the room-graph coordinate frame. Outdoor and cave meshes live in a
different coordinate frame (see ROADMAP "Known issues") and the cave backend is
shelved, so they are explicitly out of scope here, matching the boundary the
traversability gate already enforces.

## Background / confirmed format (see docs/RESEARCH.md "In-client EQ map files")

Grounded against the martinlindhe/eqformat_map reader (with unit-test vectors),
the crande25/eql-maps mesh-derived generator, and the EQ forums. Key facts:

- Record types, by the first two chars of the line:
  - `L x1, y1, z1, x2, y2, z2, R, G, B` — a wall/ledge line segment.
  - `P x, y, z, R, G, B, size, text` — a label (size 2 = medium; text may
    contain commas).
  - Colour channels are integers 0–255.
- Files are named by zone **short name**: `<shortname>.txt`, with optional depth
  layers `<shortname>_1.txt`, `_2.txt`, `_3.txt` (client auto-detects 1–3).
- **Coordinate inversion:** the map file's first two coordinates are inverted
  vs. in-game `/loc` — both negated AND swapped in order (map (X,Y) derived from
  world by negate+swap); Z is world Z. Getting this wrong renders the map
  mirrored/rotated relative to the zone. This is the single highest-risk detail.
- Verified example records (reader test vectors):
  - `L 2881.0, -2022.0, -295.0, 2885.0, -2027.0, -295.0, 128, 255, 0`
  - `P 5531.2642, -168.7061, -299.5485, 128, 255, 0, 2, Gargoyle_Island`
- Depth-band colour convention: black = main level, tan/gray = above,
  purple/blue = below. Only wall/ledge boundaries are drawn (not floor interiors).

Mesh-derived extraction method (shared, reusable core):
1. Take the TER triangle mesh (available in-process in `generators/builder.py`
   at build time — no need to re-unpack the `.eqg`).
2. Classify each triangle floor / wall / ceiling by its surface normal.
3. Keep edges where floor meets wall (the walkable boundary) plus open ledges;
   drop flat floor interiors and ceilings.
4. Chain edges into polylines; simplify; drop duplicate contours.
5. Convert world → map coords (negate+swap XY) and colour by depth band.
6. Emit `L` records; optional `P` labels for entrance / boss from pacing data.

The extraction core (steps 1–4, mesh → simplified world-space polylines) is
deliberately separable from the EQ `.txt` writer (steps 5–6) because a FOLLOW-UP
task (`tasks/web-svg-mesh-outline.md`) will reuse the same polylines to draw an
accurate web map. Build the extractor as its own function/module with no EQ-txt
assumptions baked in.

## Acceptance criteria

Each criterion names its verification mechanism. Structural tests passing is
necessary but NOT sufficient in this project (every corridor/geometry bug so far
passed the suite and was caught only in a 3D/visual check), so a human visual
confirmation of the rendered map is part of the bar.

- [ ] A new unit test (`tests/test_eqmap.py::TestEqMapFormat`) round-trips the
      format: given a tiny hand-built set of polylines + labels, the writer emits
      lines that re-parse to the same values, and the two documented reader test
      vectors above parse/emit byte-faithfully (field order, 0–255 colours,
      comma-in-label handling).
- [ ] A unit test (`tests/test_eqmap.py::TestCoordTransform`) pins the world→map
      coordinate transform on known points: a world point maps to the negate+swap
      XY (Z unchanged), and the transform is its own inverse round-trip. Include
      an asymmetric point (x != y, both non-zero, different signs) so a missed
      negate OR a missed swap both fail the test.
- [ ] A unit test (`tests/test_eqmap.py::TestExtractOutline`) on a known dungeon
      seed asserts the extractor returns a non-empty set of polylines, every
      emitted segment endpoint lies on a wall triangle edge of the mesh (within
      tolerance), and no segment crosses a room interior where there is no wall
      (spot-checked against the box backend's known wall positions).
- [ ] The map step runs in the pipeline only AFTER the traversability validator
      passes, for the dungeon theme: generating a dungeon via `main.py generate`
      and via `/api/generate` writes `output/<zone>.txt` (plus any depth-layer
      files); an ungated theme (outdoor/cave) writes NO map file. Verified by
      `tests/test_eqmap.py::TestPipelineHook` (dungeon → file exists; outdoor →
      absent) and by a CLI run.
- [ ] `docs/ACCEPTANCE.md` gains an "EQ map export" section and it passes for the
      pinned dungeon seeds below: a human loads the generated `.txt` (in a client
      `maps/` subfolder, or a faithful `.txt` map viewer) and confirms — the map
      lines sit on the actual zone walls, the map is correctly oriented (not
      mirrored/rotated — this catches a coord-transform error the unit test can't
      fully prove), the entrance/boss labels sit on the right rooms, and a
      multi-level seed's depth bands read sensibly.
- [ ] Full suite green: `python -m pytest tests/ -q`.
- [ ] No regression to the existing web SVG map: `generators/mapview.py` and the
      web map modal are untouched (confirmed by diff) and the web map still opens.

Pinned dungeon seeds for the visual pass (reuse known-good corridor seeds so the
map is checked against geometry already validated in 3D): a flat multi-room seed
plus the formerly-broken-elevation seeds now walking 9/9 — 1955208177, 1516796975,
678358326 — so the map is confirmed against bent/ramped corridors specifically.

## Subtasks

Ordered; each is roughly one commit.

- [ ] **Confirm the format against a real file (grounding).** If any real EQ
      `maps/*.txt` is available (from the RoF2 install at `F:\everquest_rof2`,
      e.g. an existing dungeon map), read a handful of `L`/`P` lines and confirm
      field order, colour range, and the coordinate orientation against a known
      `/loc`. Record the confirmation (or "no sample available, relying on
      RESEARCH.md") in Notes. Do NOT commit any game asset.
- [ ] **Coordinate transform + writer.** Add `generators/eqmap.py` with the
      world→map transform (negate+swap XY, keep Z) and a writer that emits `L`
      and `P` records to a string/file given polylines + labels + colours. Unit
      tests: `TestEqMapFormat`, `TestCoordTransform`.
- [ ] **Mesh outline extractor (the reusable core).** Add an extractor (same
      module or `generators/mapgeom.py`) that takes the TER mesh (vertices +
      polygons, as built in `builder.py`) and returns simplified world-space
      polylines of the floor↔wall boundary, classified by depth band. Keep it
      free of any EQ-`.txt` specifics so the follow-up SVG task can reuse it.
      Unit test: `TestExtractOutline`.
- [ ] **Depth-band colouring + labels.** Colour the `L` lines by depth band
      (community convention); derive entrance/boss `P` labels from the pacing
      data already on `RoomSpec` (role/boss). Assemble the single base-layer
      `<shortname>.txt` (v1 is single-layer per the locked decision; depth-band
      colouring still applies within it).
- [ ] **Pipeline hook, post-validation.** Wire map emission to run after
      `generators.pipeline.generate_validated` returns a PASSING gated build, so
      only validated dungeons get a map and ungated themes get none. Decide and
      document the exact call site (see Open decisions). Unit test:
      `TestPipelineHook`; confirm via a `main.py generate` run and an
      `/api/generate` call.
- [ ] **Docs + acceptance.** Add the `docs/ACCEPTANCE.md` "EQ map export"
      section with the pinned seeds and the visual checklist; run the human pass
      and record findings here.
- [ ] Full suite green; update this file's Deliverables + Status.

## Deliverables

- Code: `generators/eqmap.py` (transform + `.txt` writer), mesh outline
  extractor (same module or `generators/mapgeom.py`), pipeline hook in
  `generators/pipeline.py` (and/or the server/CLI call sites that invoke it).
- Tests: `tests/test_eqmap.py`.
- Docs: `docs/ACCEPTANCE.md` (new section); `docs/RESEARCH.md` already carries the
  format research.
- Integration state (written later by the single-writer integration step, NOT by
  this task): ROADMAP backlog item "EQ in-client map export" → promoted to a
  built capability; `tasks/README.md` board row for `eq-map-export`.
- Commits: <hashes, newest last>

## Notes / decisions / blockers

### Decisions locked (user-confirmed 2026-10-18)

1. **Pipeline call site — write in `generate_validated` after a PASS.** The
   existing web SVG is written INSIDE `ZoneBuilder.build()`
   (`generators/builder.py`), which runs on every build attempt — including
   attempts the validator later rejects and retries. The EQ map must only be
   written for the FINAL passing zone, so it does NOT go where the SVG is.
   Decision: emit it in `generators.pipeline.generate_validated` once a gated
   build PASSES, giving a single guaranteed source and mirroring how validation
   is centralised there.
2. **Single layer for v1.** Write a single base `<shortname>.txt`. Emitting
   `_1/_2/_3` depth layers is deferred (becomes meaningful once
   `tasks/multi-level-dungeon.md` lands); the depth-band COLOURING of lines
   still applies within the single file.
3. **Labels = entrance + boss only for v1.** Use the role/boss data already on
   `RoomSpec`. Per-room type labels are deferred to avoid a cluttered map.

### Traps folded in from lessons-learned / repo history

- **Structural pass ≠ correct.** The coordinate transform especially can pass a
  unit test and still render mirrored/rotated in-client — hence the mandatory
  human visual criterion. Do not declare done on tests alone.
- **Measure with a NEAREST-vertex probe, not a wide window** when asserting that
  emitted segments lie on wall edges — a wide tolerance window previously gave a
  misleading "ramp gap" reading in the corridor work. Use nearest-edge distance.
- **Mesh vs plan coordinate frames.** Only dungeon/box is in the room-graph
  frame; do not attempt outdoor/cave here (they'd map onto the wrong geometry —
  the same mismatch that keeps them out of the traversability gate).
- **pwsh commit convention** (single-writer tracker = this task file only): write
  the message to `.git/COMMIT_EDITMSG_TMP`, `git commit -F` it, then always
  delete the temp file; never `git add .`; do not push.

### Relationship to other tasks

- Follow-up: `tasks/web-svg-mesh-outline.md` reuses this task's mesh outline
  extractor to make the WEB map mesh-accurate. Keep the extractor cleanly
  separable so that task is additive, not a rewrite.
- Shares the dungeon-only coordinate-frame boundary with
  `tasks/validate-in-pipeline.md` / `tasks/traversability-validator.md`.
- `tasks/multi-level-dungeon.md`, if landed first, makes depth layers more
  meaningful; not a hard dependency (single-layer works regardless).
