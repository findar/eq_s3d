# Roadmap & Open Items

The authoritative list of what's done, what's next, and known gaps. The README
carries the narrative "what it does / how it works"; this file is the tracker.
Keep it in sync when work lands (check items off, move them, note the commit).

Last updated: commit `5292435` (25 commits, 142 tests passing).

---

## Done

| Area | Summary |
|------|---------|
| Analyzer (Phase 0) | Extract style metrics from a RoF2 install; profiles in `styles/` |
| Core I/O (Phase 1) | PFS read/write (EQ big-endian CRC), TER/ZON serialisers, EQG assembler |
| WLD reader | Classic–PoP `.s3d`/WLD geometry reader (0x36 meshes) |
| Inspector (Phase 1b) | Rich terminal metrics + zone comparison |
| Geometry (Phase 2) | Box rooms/corridors; inward walls; planar UVs |
| Elevation (Phase 2.5) | Multi-level layout; ramp & staircase corridors |
| Web app | FastAPI + Vite/Three.js; generate + first-person walk + overlays |
| Organic caves | SDF + marching cubes; noise-roughened walls; multi-lobe chambers; winding tunnels |
| Walkable floors + features | Flat-bottomed domes; stalactites/stalagmites/pillars |
| Outdoor terrain | Heightfield + erosion; walkable rolling hills |
| Textures | Procedural seamless (no API) + AI provider drop-in |
| Prompt planning (Phase 3) | Rule planner (no API) + LLM drop-in; expand → ZoneSpec |
| Classic–PoP profiles | Analyzer reads s3d/WLD; profiles from Guk/Sebilis/Faydark… |
| Theme-accurate scale | Room size from measured per-theme floor_area |
| TinyKeep layout | Scatter → separate → Delaunay → MST + loops → graph elevation |
| Pacing | Graph-derived roles (entrance/hub/climax/deadend) + depth; biased geometry & lighting |
| Gating | Optional lock-and-key suggestions, solvability-guaranteed |
| Top-down map | SVG floor-plan sidecar + web modal |
| Staircase fix | L-shaped corridors meet both wall openings; stairs flush at both landings |

---

## Next — Phase 4: Refinement (highest priority)

The phase that turns a one-shot generator into an iterative tool.

- [ ] **Iterative chat loop** — refine an existing zone with follow-up prompts
      ("make the entrance wider", "add a water pool to the north") instead of
      regenerating from scratch. Needs: a session/zone-state concept server-side,
      a diff-style prompt interpretation, and a way to carry the seed/spec forward.
- [ ] **Partial regeneration** — re-run only changed rooms/textures, not the whole
      zone, so iteration is fast.
- [ ] **EQEmu SQL export** — zone records, spawn points, and door/key rows. A
      `GateSpec` maps to a `doors` row (`lock_x/y/z` → position, `corridor_id` →
      the opening, key → `keyitem`). This is what makes a generated zone playable.

---

## Design work captured, not yet built

- [ ] **Doorway-fit for gates** — catalogue the RoF2 door models used for doorways
      and their world-space footprints by theme (swinging wood/stone, portcullis,
      double doors, archway frames), then snap gated corridor openings to a chosen
      door type and record the model name on `GateSpec`. Prerequisite for a
      meaningful door export. (See README "Doors are records, not geometry".)
- [ ] **Water & mixed-environment zones**
  - [ ] Outdoor + water: a water plane at fixed Z, terrain sloped beneath it for a
        shoreline/lakebed, and an `AWT_` region so the client treats it as swimmable.
        Terrain backend needs a "water level" + shoreline shaping.
  - [ ] Cave-mouth-in-hillside: compose the SDF cave + heightfield terrain backends
        into one TER. Strongest argument for unifying both onto a single
        density-field representation (terrain as an SDF too).
- [ ] **Outdoor rooms as real places** — outdoor "rooms" currently only set terrain
      bounds; make them clearings, lookouts, etc.
- [ ] **Procedural normal maps** — textures are diffuse-only; real zones use the
      `e_TextureNormal0` material slot. No-API, high visual impact.

---

## Known issues / smaller fixes

- [ ] Style profiles for `city` and `cave` are thin (3–4 zones) — expand once more
      zone names are identified.
- [ ] Light-density stat reads 0 in profiles (most dungeon references use embedded
      MOD placement without ZON lights). Accurate, not a bug — but worth a note so
      it isn't "fixed" by mistake.
- [ ] Inspector ASCII bbox diagram doesn't render Z height — add a side-elevation view.
- [ ] Outdoor terrain is just the ground surface — no cliff walls, boulders, or
      vegetation yet.
- [ ] Web bundle is a single ~570 kB chunk (Vite warns > 500 kB). Cosmetic; could
      code-split Three.js if it ever matters.

---

## Deliberately NOT doing (and why)

Recording these so they aren't re-proposed:

- **Cave mesh decimation** — quadric decimation collapses the flat walkable floor
  into a few steep triangles. Poly count is controlled via `voxel` size instead.
- **Multi-key gating models (fragments / master key)** — the requested case was
  *independent* locks, which the N-separate-gates model already covers.
- **Baking doors into the `.ter`** — a door welded into the mesh is a door-shaped
  wall that can't open. Doors are runtime records (EQEmu `doors` table), produced
  by the SQL export, dropped into the open corridor gap.
- **Full Dormans mission-graph grammar** — EQ gates by depth/danger, not Zelda-style
  lock chains. We adopted only the solvability-invariant idea for gating.
