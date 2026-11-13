# Lessons learned — technical gotchas

Hard-won facts discovered during development. Each one cost real debugging time;
read before touching the relevant area so it isn't rediscovered.

## File formats

- **PFS CRC is NOT reflected zlib CRC32.** It's EQ's own big-endian CRC:
  polynomial `0x04C11DB7`, init 0, case-sensitive, computed over the filename
  *including* the null terminator. Reference: `EQEmu/zone-utilities
  src/common/pfs_crc.cpp`. Using a standard zlib CRC silently breaks name lookup.
- **PFS name blocks can be multi-chunk deflate.** RoF2 name blocks are 35 KB+ and
  span multiple deflate streams; the reader must concatenate chunks.
- **WLD specifics:** magic `0x54503D02`; old-format flag `0x00015500` (16-bit UV);
  fragment `0x36` = mesh; string-hash XOR key is
  `[0x95,0x3A,0xC5,0x2A,0x95,0x7A,0x95,0x6A]`.
- **EQG collision is per-triangle**, from the polygon's `0x01` flag (confirmed in
  `azone/map.cpp::CompileEQG`). No BSP tree needed. This is why dense organic
  meshes work as collision exactly like hand-made zones.
- **ZON (EQGZ) rotations are radians, yaw first.** An object's three
  rotation floats are (yaw, pitch, roll) in radians, and a region's rotation
  is one float in radians (stock values mostly −π/2). Stock object tilts
  reach ~0.46 rad. 53 of the 88 stock zones ship ZON as the `EQTZ` text
  format instead, which `core/zon.py` doesn't read.
- **Two `.eqg` writes are never byte-identical.** `core/pfs.py` puts the
  write time in the archive footer, so reproducibility tests compare
  `bytes[:-4]`; every archive entry is identical run to run.
- **Era/format boundary is Gates of Discord (2003):** Classic→PoP = `.s3d`/WLD;
  GoD onward = `.eqg`. Classic–PoP (the default look) therefore needs the WLD
  reader, not just the EQG path.

## Geometry / fields

> **The cave pipeline was removed in M0.** Cave returns as a dungeon archetype
> (umbrella M3) and the natural geometry style (umbrella M5). The cave-specific
> entries below (the first five here, plus "Localized feature SDFs" and "Voxel
> budget" under Performance) describe the removed field pipeline. They are kept
> VERBATIM as hard-won guidance for whoever rebuilds the natural style in M5 —
> they are not describing current code.

- **Automated structural tests can pass while the 3D viewer shows it's broken.**
  The cave backend's `TestCaveConnectivity` reports a single watertight component,
  yet caves still render as disconnected blobs in the viewer. The analysis and
  the render disagree — so for major geometry changes, a passing test suite is
  NECESSARY but NOT SUFFICIENT; confirm in 3D per `docs/ACCEPTANCE.md`. Caves are
  shelved pending a rebuild ("cavify the dungeon layout"); use `dungeon` meanwhile.
- **voxel=12 matches Classic/Kunark/PoP** (~12–14 u median triangle edge, measured
  across real zones). Smaller = too modern/smooth, larger = too coarse.
- **Don't decimate cave meshes.** Quadric decimation collapses the flat walkable
  floor. Control poly count with `voxel` size instead.
- **Walkable floors need deliberate shaping:** chambers are flat-bottomed domes
  (sphere ∩ half-space), wall noise is tapered to near-zero near the floor AND
  clamped one-sided so it can raise bumps but never dig pits below `floor_z`.
  After any lobe/noise blend, re-intersect the chamber with the floor plane.
- **Multi-lobe chambers + smooth-min can bow below the floor** at lobe junctions —
  always re-clamp to the floor half-space afterward (this exact regression was
  caught by the walkability tests).
- **Same-axis room pairs need a Z-route, not an L.** Most corridors connect two
  rooms whose facing walls are PARALLEL (both E/W, or both N/S) — `_wall_point`
  always cuts both openings on the same (dominant-centre-delta) axis, so this is
  the common case, not the exception. A single-corner **L-bend** cannot serve it:
  one of its two legs ends up running ALONG a wall face instead of out through
  the opening, so it meets that opening at the wrong XY and (with elevation) the
  wrong floor height, leaving a gap. `geometry.add_corridor` now routes by case:
  **straight** (collinear openings), **Z-corridor** (3 segments: perpendicular
  stub out of A, a cross-jog, perpendicular stub into B — for parallel walls),
  or **L-bend** (2 segments, only for a genuine cross-axis pair). All three go
  through one `_emit_route` helper that confines the WHOLE rise to a single leg
  (flat before it, flat after), so ramp and stair behave identically and both
  openings land flush regardless of which leg carries. Caught at seed 1955208177
  in the 3D viewer; the earlier "L-bend" framing (seeds 481893615, 1516796975)
  was the same bug seen partially. Regressions:
  `TestCorridorRouting::test_same_axis_pair_routes_as_z_corridor_flush` and
  `::test_pinned_and_random_seeds_corridors_connect_and_walkable`.
- **A ramp must be SUBDIVIDED or the traversability agent can't climb its own
  slope.** `analyzer.traverse` connects two walkable faces only when their
  centroids are within `max_step_up` (~3u) in Z. A ramp built as a SINGLE quad
  splits into two triangles whose centroids sit `dz/3` apart — so any ramp with
  `dz > ~9u` reads as an unclimbable gap and every room beyond it shows up as a
  1000u-away island, even though the floor looks continuous. `_add_ramp_corridor`
  now subdivides the slope into segments that each rise `<= MAX_SEG_RISE` (2.5u).
  A flush floor at the opening is NECESSARY but not sufficient — the per-triangle
  agent is the real bar. (This is also why generated elevation uses ramps, not
  stairs: stairs would need sub-player-height steps to clear the same 3u limit.)
- **Bound elevation by the corridor run, and clamp loop edges too.** Room heights
  are assigned by BFS over the room graph; `_assign_elevation` caps each tree
  step so `|dz| <= run * max_grade` (0.5 ≈ 26.6°, under the agent's 40° cap).
  But a LOOP (non-tree) edge joins two rooms placed down separate tree paths, so
  its own run never constrained their gap — leaving the occasional cliff
  corridor (seed 4). `_relax_elevation` then pulls every room into the walkable
  Z-band of ALL its neighbours (loop edges included) until the graph settles;
  rooms already consistent don't move, so verticality is preserved.

## Performance

> **Cave-pipeline note:** the localized-SDF and voxel-budget entries below
> describe the cave field pipeline removed in M0. Cave returns as a dungeon
> archetype (umbrella M3) and the natural geometry style (umbrella M5); these are
> kept VERBATIM as M5 guidance, not a description of current code.

- **opensimplex was the bottleneck** (~26 s for a big cave). Replaced with a fully
  vectorised numpy value-noise → ~1 s. Never reintroduce a per-voxel Python loop.
- **Localized feature SDFs** (`add_cone_local` / `add_capsule_local`) compute only
  within a feature's bounding box: 97 s → 8 s for large caves. Use these, not
  whole-grid SDFs, when placing many small features.
- **Voxel budget** is capped (~2.5M); `_make_grid` auto-coarsens voxel size for
  sprawling footprints. Account for tunnel wander & chamber lobes when sizing the
  grid or features clip the bounds.

## Web viewer

- **Z-up camera.** The tilt bug was Three.js defaulting to Y-up; the camera is set
  to Z-up to match EQ. Movement/forward vectors assume this.
- **GLB preview uses per-material base colours**, not real DDS textures (would need
  UV packing). The palette comes through; actual texture rendering doesn't.
- **Movement keys must be suppressed while typing** in a form field, or WASD flies
  the camera instead of editing the prompt.

## Environment / tooling (Windows + PowerShell)

- **Shell is pwsh.** Use `;` not `&&`; `$env:VAR` not `%VAR%`; `Remove-Item`,
  `Get-ChildItem`, etc. Never use cmd syntax.
- **Commit messages: heredocs fail in PowerShell.** Write the message to
  `.git/COMMIT_EDITMSG_TMP` and `git commit -F` it, then delete the temp file.
- **`git diff > file.patch` corrupts non-ASCII bytes in PowerShell.** The `>`
  redirect decodes git's raw UTF-8 stdout through the console code page and
  re-encodes it, mangling em dashes, arrows, etc. (`—` → `ΓÇö`). A patch written
  this way then fails `git apply` with a bytewise "patch does not apply" even
  though the text looks right. Use `git diff --output=file.patch` (git writes the
  file itself, raw bytes) — or `git diff | Out-File -Encoding utf8`. Same trap for
  any `git show`/`git cat-file` piped through PowerShell: to inspect raw bytes,
  go through Python `subprocess.run(..., capture_output=True).stdout`, not a PS
  pipe.
- **A commit-message hook blocks the words "Vite" and "dev server"** — avoid them
  in commit messages (describe the frontend build without those literal words).
- **Never start long-running processes** (dev server, watchers) with a blocking
  shell call — they hang. The user runs those manually.
- **`git worktree remove` follows a junction and deletes the TARGET.** The
  parallel-agent worktrees (`scripts/new-worktree.ps1`) share `web/node_modules`
  via a Windows junction. Running a bare `git worktree remove` on such a worktree
  recurses THROUGH the junction and deletes files inside the MAIN repo's
  `node_modules` (confirmed in a smoke test — it got partway, dropping 3
  top-level packages, before stalling on a locked `esbuild.exe` and prompting for
  input; a `cd web; npm install` restored it). Always tear down with
  `scripts/remove-worktree.ps1`, which unlinks the junction as a LINK (`cmd
  rmdir`, no recursion) before removing the worktree. Same trap for any manual
  cleanup: delete a junction with `rmdir`/`(Get-Item).Delete()`, never
  `Remove-Item -Recurse` which can follow it into the target.
- EQ install for analysis lives at `F:\everquest_rof2` (1057 eqg, 1010 s3d).
- **Use `fullmatch`, not `match` with `^…$`, to validate input.** `$` also
  matches just before a trailing `\n`, so `re.match(r"^[A-Za-z0-9_.-]+$",
  "gen_t\n")` succeeds. The build-file route let such a segment reach the
  filesystem (404 instead of 400); Hypothesis drew one only rarely, so step 1b's
  Property 18 failed about once per thorough run. Fixed in `server/app.py`
  `_safe_segment` and pinned as `@example`s.
- **`Path.resolve` on Windows can keep the `\\?\` prefix under a race.**
  Python 3.13's `ntpath.realpath` resolves through the OS and strips the
  long-path prefix only if a second lookup returns the same path or fails
  with the same Windows error. If another process is creating the path in
  between (one error "path not found", the next "file not found"), the
  prefix stays, and `\\?\F:\…\output\web` compares UNEQUAL to
  `F:\…\output\web`. This was the parallel test runner's mystery failure on a
  fresh worktree's first run: four workers import `server.app` at once, one
  hits the race in its import-time `OutputRoot(OUTPUT_DIR).mkdir()` and
  raises `OutsideOutputError: path X resolves outside output root X` (two
  identical-looking paths), so that worker collects fewer tests and xdist
  reports "Different tests were collected between gw0 and gw2". It only
  happens before `output/web` exists, which is why re-runs never failed.
  Fixed in `core/paths._resolve`, which now strips a leftover `\\?\` (and
  turns `\\?\UNC\` back into `\\`); `tests/test_paths.py` simulates it. Any
  other code comparing resolved paths on Windows should go through
  `_resolve` or strip the prefix the same way. A parallel run that hangs with
  its workers gone (seen once) is still unexplained: kill leftover `python …
  pytest` processes (`Get-CimInstance Win32_Process` filtered on the command
  line) and run it again.

- **Worktree agents leak edits into the MAIN checkout.** Twice in step 11 (tasks 19
  and 10) an agent working in `..\eq_s3d-worktrees\<scope>` also left an uncommitted
  edit to a file in `F:\Dev Projects\eq_s3d` (an early draft of its own change), which
  then blocked the merge. Before merging a branch, run `git status` in the main checkout;
  if a modified file also changed on the branch, compare it with the branch's version
  (`git show <branch>:<file> | diff - <file>`) and discard the stray copy only when the
  branch has it. Brief agents to use absolute worktree paths for every edit. One cause, seen
  in task 21: a .NET call such as `[System.IO.File]::WriteAllText("rel\path", ...)` resolves a
  relative path against the PROCESS's directory (the main checkout), not PowerShell's `$PWD`,
  so the edit lands in main. Pass .NET file APIs absolute paths.
- **Parallel agents must not share a commit-message file, nor run full suites at once.** Worktrees
  share one `.git` and the session's scratchpad, so two agents writing `.git/COMMIT_EDITMSG_TMP` (or
  one scratch file) overwrite each other: in step 12 a task-6 commit went in under task 12's
  message. Give each agent its own file in its own worktree (`.commitmsg-<n>.txt`). Three full
  suites at once ran out of memory (80 MemoryError failures) and push time-limit tests over;
  check for a running `pytest tests/` before starting one, and re-run such failures alone.

## Design calls already settled (don't relitigate)

- **Tracker writes are single-writer, and that rule is UNCONDITIONAL — do not
  "optimise" it back into a solo-vs-parallel conditional.** Agents update only
  their own `tasks/<id>.md`; `ROADMAP.md`, `README.md`, and `tasks/README.md`
  are written once per landed branch at an explicit integration step. The
  temptation is to say "let the agent update ROADMAP directly when it's the only
  one running." That's the trap: a working agent generally can't know whether
  other agents are live at that moment, so a conditional rule will eventually
  fire in the wrong mode and clobber `ROADMAP.md` at merge. Safety must not
  depend on knowledge the agent doesn't have. One always-on rule costs a little
  convenience in solo sessions and removes an entire conflict class forever.
- TinyKeep layout over BSP/WFC/prefab/pure-random (see ROADMAP "NOT doing").
- Pacing is analytical (graph-derived), not a full mission-graph grammar.
- Gating adopted only the solvability-invariant idea from graph rewriting.
- Gates/pacing are suggestions — never write them into geometry or collision.
- Doors are runtime records (EQEmu `doors` table), produced by the future SQL
  export, not baked into the mesh.
