# TASK: web-svg-mesh-outline

Status: not-started        <!-- not-started | in-progress | blocked | done -->
Epic: Web viewer UX / map accuracy — make the browser's top-down map trace the
      zone's real walls (from the 3D geometry) instead of only the abstract
      room/corridor plan, so the web map agrees with the first-person view and
      with the in-game EQ map. Follow-up to `tasks/eq-map-export.md`.
Last touched: created 2026-10-18 from a roadmap-review discussion.

## Goal

The web app shows a top-down map of each generated zone in a modal (the "M"
window in the browser viewer). Today that map is a SCHEMATIC drawn from the
abstract plan (the "ZoneSpec" — rooms as rectangles, corridors as single
straight lines, elevation shown only as a depth number), so it does not match
the walls the player actually sees in the 3D view: a corridor that bends and
ramps in 3D is drawn as one straight stick, and rooms are plain boxes rather
than their real walled outline. This task adds an ACCURATE outline layer to the
web map, traced from the zone's real triangle mesh (the same "extract wall
outlines from the mesh" core built in `tasks/eq-map-export.md`), so the web map
reflects true geometry.

Crucially this is ADDITIVE, not a replacement. The current schematic carries
information the mesh cannot: room roles (entrance / hub / climax colouring),
pacing depth numbers, boss markers, and lock→key gate connectors. Those stay.
The real wall outline is drawn UNDERNEATH them, so the web map becomes "accurate
geometry + helpful annotations" rather than losing the annotations. Done when
the web map modal shows wall outlines that match the 3D view, with the existing
role/pacing/gate annotations still overlaid and legible.

Scope is **dungeon/box backend only** — the backend whose mesh is trusted and in
the room-graph coordinate frame (outdoor/cave are in a different frame and cave
is shelved). For non-dungeon themes the map falls back to today's schematic-only
rendering, unchanged.

## Dependency

- **Hard dependency on `tasks/eq-map-export.md`.** That task builds the reusable
  mesh outline extractor (TER triangle mesh → classify triangles by surface
  normal → keep floor↔wall boundary edges → chain into simplified world-space
  polylines). This task CONSUMES those polylines to draw the web SVG. Do not
  start until that extractor exists and is cleanly separable (no EQ-`.txt`
  assumptions). If the extractor needs a small signature tweak to be reusable
  here, make it in this task but keep the EQ exporter green.

## Acceptance criteria

Each criterion names its verification mechanism. Because this is a visual change,
a human eyeball in the actual web modal is required (structural tests are
necessary but not sufficient in this project).

- [ ] The map renderer can draw mesh-derived wall polylines: a unit test
      (`tests/test_mapview.py::TestMeshOutlineLayer`) feeds a known dungeon
      seed's extracted polylines in and asserts the produced SVG contains
      polyline/path elements for the walls (non-empty) AND still contains the
      existing annotation elements (role-coloured room rects or markers, depth
      labels, and gate lines when gating is on).
- [ ] For a non-dungeon theme (or when no mesh outline is available), the map
      falls back to the current schematic rendering unchanged: a test asserts
      the outdoor/cave path produces the same schematic output as before (golden
      compare or element-count check), so the fallback is proven.
- [ ] The web map modal renders the accurate outline for a generated dungeon:
      `docs/ACCEPTANCE.md` gains a "Web map accuracy" section and it passes for
      the pinned seeds below — a human opens the browser "M" map and confirms the
      drawn walls match the first-person 3D view (bent/ramped corridors are no
      longer straight sticks; room outlines match), and the entrance/hub/climax
      colours, depth numbers, boss stars, and gate links are all still present
      and readable on top.
- [ ] Orientation agrees with the 3D view AND with the EQ map export: the web
      outline, the first-person view, and the `tasks/eq-map-export.md` `.txt`
      map all show the zone in the same orientation for at least one seed
      (human-confirmed; catches an axis/flip mismatch between the two renderers).
- [ ] Full suite green (`python -m pytest tests/ -q`) and a web build succeeds
      (`cd web && npm run build`) with the rebuilt bundle committed.

Pinned dungeon seeds: a flat multi-room seed plus the bent/ramped-corridor seeds
1955208177, 1516796975, 678358326 (so the "straight stick vs. real bend"
improvement is the thing being checked).

## Subtasks

Ordered; each roughly one commit.

- [ ] **Consume the extractor.** Call the mesh outline extractor from
      `eq-map-export` for dungeon zones; get world-space polylines into the map
      renderer's input. Confirm the extractor's signature works unchanged (or
      make the minimal reusable tweak, keeping the EQ exporter green).
- [ ] **Render the outline layer in `generators/mapview.py`.** Draw the
      polylines as the base layer (projected top-down with the same Y-flip the
      SVG already uses), beneath the existing room/corridor/role/gate drawing.
      Keep the schematic annotations on top. Unit test:
      `TestMeshOutlineLayer`.
- [ ] **Fallback path.** When there is no mesh outline (non-dungeon theme, or
      extractor returns empty), render exactly today's schematic. Test the
      fallback is byte/element-stable vs. current output.
- [ ] **Wire through server/web if needed.** The SVG is already served as the
      `map_url` sidecar and injected by the web modal (`web/src/main.ts`), so
      ideally no web-code change is required — verify. If the outline needs the
      mesh and the SVG is built where the mesh isn't handy, adjust the build
      call site (coordinate with where `eq-map-export` hooks in). Rebuild
      `web/dist` if any web/src changed.
- [ ] **Docs + acceptance.** Add `docs/ACCEPTANCE.md` "Web map accuracy"; run the
      human pass (outline matches 3D; annotations intact; orientation agrees with
      the EQ `.txt`); record findings here.
- [ ] Full suite green + web build; update Deliverables + Status.

## Deliverables

- Code: `generators/mapview.py` (outline layer + fallback), possibly a small
  reuse tweak to the extractor from `generators/eqmap.py`/`mapgeom.py`, and any
  build call-site change needed to supply the mesh; rebuilt `web/dist` if
  `web/src` changed.
- Tests: `tests/test_mapview.py`.
- Docs: `docs/ACCEPTANCE.md` (new section).
- Integration state (written later by the single-writer integration step, NOT by
  this task): `tasks/README.md` board row for `web-svg-mesh-outline`; ROADMAP
  note that the web map is now mesh-accurate for dungeons.
- Commits: <hashes, newest last>

## Notes / decisions / blockers

- **Additive, not a rewrite.** The explicit bar-raiser decision behind splitting
  this out: the schematic annotations (role colours, pacing depth, boss stars,
  gate links) are information the mesh cannot provide and must be preserved.
  Draw the real outline UNDER them. If a reviewer sees the annotations removed,
  that is a regression, not a simplification.
- **Depends on the extractor existing** (`tasks/eq-map-export.md`). Building the
  extractor was deliberately sequenced into the EQ-map task because the EQ map
  (which the player navigates by) is the forcing function that justifies and
  hardens ground-truth extraction; the web map reuses it once proven.
- **Dungeon-only**, same coordinate-frame boundary as the traversability gate and
  the EQ map export. Non-dungeon falls back to the schematic.
- **Orientation must agree across all three views** (web outline, 3D, EQ `.txt`).
  A top-down projection flip here that disagrees with the EQ map's negate+swap
  transform would be confusing; the cross-view orientation criterion guards it.
- **pwsh commit convention** (single-writer tracker = this task file only): write
  the message to `.git/COMMIT_EDITMSG_TMP`, `git commit -F` it, then always
  delete the temp file; never `git add .`; do not push.
