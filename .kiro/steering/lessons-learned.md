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
- **Era/format boundary is Gates of Discord (2003):** Classic→PoP = `.s3d`/WLD;
  GoD onward = `.eqg`. Classic–PoP (the default look) therefore needs the WLD
  reader, not just the EQG path.

## Geometry / fields

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
- **Corridor endpoints usually differ on BOTH axes** (rooms are offset). A single
  axis-aligned tube misses one wall opening and leaves geometry (and stairs)
  floating. Corridors bend into an **L-shape** to meet both openings; staircases
  must start flush with the lower floor and finish flush with the upper (every
  riser emitted, first tread at the base level).

## Performance

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
- **A commit-message hook blocks the words "Vite" and "dev server"** — avoid them
  in commit messages (describe the frontend build without those literal words).
- **Never start long-running processes** (dev server, watchers) with a blocking
  shell call — they hang. The user runs those manually.
- EQ install for analysis lives at `F:\everquest_rof2` (1057 eqg, 1010 s3d).

## Design calls already settled (don't relitigate)

- TinyKeep layout over BSP/WFC/prefab/pure-random (see ROADMAP "NOT doing").
- Pacing is analytical (graph-derived), not a full mission-graph grammar.
- Gating adopted only the solvability-invariant idea from graph rewriting.
- Gates/pacing are suggestions — never write them into geometry or collision.
- Doors are runtime records (EQEmu `doors` table), produced by the future SQL
  export, not baked into the mesh.
