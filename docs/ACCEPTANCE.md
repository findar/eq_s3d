# User Acceptance Tests

A manual checklist to validate the generator after any **major change**
(geometry backend, layout, pacing/gating, textures, web viewer). The automated
suite (`python -m pytest tests/ -q`) covers correctness invariants; this list
covers the things only a human looking at the result can confirm.

Run the automated suite first — if it's red, stop and fix that before eyeballing
anything. Then walk this checklist in the web viewer.

```bash
python -m pytest tests/ -q          # must be all green first
cd web && npm run dev               # then open http://localhost:5173
```

Record pass/fail with the seed shown in the panel so issues are reproducible.
A change is acceptable when every **[MUST]** item passes for several random
seeds per theme.

---

## A. Core generation (all themes)

- [ ] **[MUST] Generates without error** — Generate succeeds for `dungeon`,
      `outdoor`, `city`; the panel shows seed, polys, bounds.
- [ ] **[MUST] Randomness** — Generating twice with the same controls yields a
      different seed and visibly different geometry.
- [ ] **[MUST] Performance** — Generation completes in under ~5 minutes (should
      be seconds for normal room counts).
- [ ] **[MUST] Lands on the floor** — On load the camera stands on a walkable
      surface, not inside rock or floating in void.
- [ ] **[SHOULD] Scale reads right** — A dungeon feels tight; an outdoor zone
      feels vast (theme-accurate footprint).

## B. Navigability (the "navigable" north-star)

> **Now partly automated (dungeon / box backend).** The traversability validator
> walks the real TER mesh from the safe point with an EQ-scale agent and reports
> which rooms are reachable and *why not* (cliff ramp / oversized step /
> misaligned corridor):
>
> ```bash
> python -m analyzer.traverse output/<zone>.eqg        # exits non-zero on FAIL
> python -m pytest tests/test_traversability.py -q     # seed-sweep regression
> ```
>
> It covers the mechanical MUSTs below for **dungeon** zones (the ✅-marked
> items). It does **not** cover outdoor yet (mesh is in a different
> coordinate frame than the room graph — see ROADMAP Known issues), nor the
> aesthetic "does it read as a place" judgement. Walk those in the viewer.
>
> **The generator now self-rejects invalid dungeons.** This validator runs in
> the generation hot path (`generators.pipeline.generate_validated`), so both
> `/api/generate` and `main.py generate` build → validate → retry on a fresh
> seed and never return a dungeon with an unreachable room: on exhaustion the
> server answers HTTP 503 instead of serving a broken GLB, and every rejected
> attempt is logged to `output/validation_failures.jsonl`. So for **dungeon**
> zones the ✅ navigability items below are enforced before you ever see the
> zone — this manual pass is the backstop and the sole gate for outdoor.
> (`main.py generate --no-validate` bypasses the gate to inspect a broken seed.)

- [ ] **[MUST] Walkable floors** — You can walk across each room's floor without
      hitting steep, slippery, or pit-like surfaces. Gentle undulation is fine.
      *(✅ auto for dungeon: the agent's walkable-slope cap rejects floors/ramps
      steeper than 40°; outdoor still manual.)*
- [ ] **[MUST] Rooms are reachable** — Every room can be reached on foot from the
      entrance; no room is sealed off. *(✅ auto for dungeon via
      `analyzer.traverse` — the core check. Outdoor still manual.)*
- [ ] **[MUST] Corridors connect cleanly** — Each corridor meets both rooms it
      joins; no corridor (or staircase) floats detached from a wall opening.
      *(✅ auto for dungeon: a corridor that's nominally walkable but whose mesh
      opening doesn't meet the room is reported as a "misaligned/detached
      corridor".)*
- [ ] **[MUST] Stairs are continuous** — Staircases start flush with the lower
      floor and end flush with the upper floor — no gap to step over at either
      landing. *(✅ auto for dungeon: oversized stair steps / landing gaps beyond
      the agent's max step-up are flagged by name.)*

## C. Enclosure / no see-through (the "enclosed rooms" requirement)

- [ ] **[MUST] No seeing outside** — From inside any room you cannot see through
      a wall, floor, or ceiling into empty space or other geometry.
- [ ] **[MUST] No floating geometry** — No stray blobs/shards hang in the air
      near the zone.
- [ ] **[MUST] Floors render solid from above** — Looking down, the floor is
      opaque (not back-face-culled / see-through).
- *Retired: pending the natural geometry style (umbrella M5).* **[SHOULD] Single
      connected cave** — For the `cave` theme, the whole zone is one continuous
      space (chambers joined by tunnels), not separate bubbles.

## D. Caves specifically

*Retired: pending the natural geometry style (umbrella M5).* The cave pipeline
was removed in M0; these items return when the natural geometry style ships.

- [ ] **[MUST] Natural shapes** — Chambers read as irregular organic blobs, not
      perfect spheres; tunnels wind rather than running dead straight.
- [ ] **[SHOULD] Era-accurate detail** — Wall relief looks hand-sculpted at EQ
      resolution (not glassy-smooth, not blocky).
- [ ] **[SHOULD] Features present** — Stalactites / stalagmites / pillars appear
      and fuse with the rock (not obviously placed props).

## E. Pacing & gating (suggestions, not authored content)

- [ ] **[SHOULD] Pacing visible** — The climax room is grandest, hubs are
      spacious, dead-ends intimate; lighting dims/cools with depth.
- [ ] **[SHOULD] Map reads correctly** — Press **M**: rooms coloured by role with
      depth numbers, corridors drawn, and (for keyed dungeons) lock/key markers
      with a key→door connector.
- [ ] **[SHOULD] Keyed dungeon is solvable** — Ask for a keyed dungeon; on the
      map every key sits earlier on the path than the lock it opens.

## F. Web viewer UX

- [ ] **[MUST] Typing is safe** — While typing in the prompt box *or the seed
      box*, WASD/Space/R edit the text and do NOT move the camera.
- [ ] **[SHOULD] Seed input reproduces** — Enter a seed in Controls, Generate,
      then "⟳ reproduce" (refills + copies the seed) and Generate again: the
      same seed + theme/rooms/elevation yields an identical zone (same polys /
      bounds). Blank seed = a fresh random zone each time.
- [ ] **[SHOULD] Overlays toggle** — Wireframe, lights, regions, and gates each
      show/hide from the panel.
- [ ] **[SHOULD] Reset view** — "Reset View" (or R, when not typing) returns the
      camera to the start.
- [ ] **[SHOULD] Z-up / level horizon** — The horizon stays level; the world is
      not tilted.

## G. Output integrity

- [ ] **[MUST] Round-trips** — The generated `.eqg` reads back through our own
      reader (`python -m analyzer.inspect output/<name>.eqg --theme <theme>`
      runs clean).
- [ ] **[SHOULD] Metrics in range** — The inspector's ✓/⚠ against the style
      profile are mostly ✓ (occasional ⚠ on materials is expected).

---

## Quick seed sweep (optional, scripted)

A fast programmatic sanity check for the structural MUSTs (connectivity,
watertightness) without opening the browser:

```bash
python -c "from generators.layout import LayoutGenerator; from generators.builder import ZoneBuilder; from core.ter import TerFile; from core.pfs import PfsArchive; import numpy as np, trimesh
for seed in [1,5,42,99,678358326]:
    s=LayoutGenerator(theme='dungeon',seed=seed).generate('q',room_count=5)
    r=ZoneBuilder(s).build(output_dir='output',write_glb=False)
    t=TerFile.from_bytes(PfsArchive.from_file(r.eqg_path).get('ter_q.ter'))
    V=np.array([[v.x,v.y,v.z] for v in t.vertices]); F=np.array([[p.v1,p.v2,p.v3] for p in t.polygons])
    m=trimesh.Trimesh(vertices=V,faces=F,process=False)
    print(f'seed {seed}: comps={len(m.split(only_watertight=False))} watertight={m.is_watertight}')"
```

Expect `comps=1` and `watertight=True` for every seed. Then clean up:
`Remove-Item output/q.*`
---

## M1 — Controls, zone types, connectivity

Walk this section after the M1 milestone (controls + all-zone-type
traversability + format gate) lands on `master`. It is the human-pass companion
to the structural suite: the suite proves connectivity/continuity/format
analytically; this list is what only a person at the viewer and the browser can
confirm. Restart the Server on the merged code first and confirm `/api/version`
reports `stale: false` before you start; confirm each build's panel
`build_commit` matches the `master` head you are testing.

> **Vocabulary note.** M1 renamed `theme` → `zone_type` and `outdoor` →
> `wilderness`. M1 offered only **dungeon** and **city**; **wilderness** was
> enabled when the `zone-generator-wilderness` milestone closed (roadmap step
> 1), so all three are offered now. Walk wilderness under "Step 1" below.

> **One-time seed break (Decision 13).** The wave-1 connectivity fixes
> deliberately re-route corridors, so a seed pinned before M1 generally produces
> a *different* layout on M1. This is intended, not a regression. The two M0
> human-pass seeds below were both moved by the crosses-room split; eyeball them
> as *fresh* M1 layouts, not as a match to any pre-M1 screenshot.

### M1.A — Zone-type gate and availability

- [ ] **[MUST] Picker lists all defined zone types** — The Controls zone-type
      dropdown lists `dungeon`, `city`, `wilderness` in defined order.
- [ ] **[MUST] Enabled types build** — `dungeon`, `city` and `wilderness` are
      selectable and build end to end; none shows a disabled reason.
- [ ] **[MUST] Undefined types are refused** — A direct request for an
      undefined zone type (e.g. `cave`) is rejected before any file is written,
      and the error lists the enabled set.

### M1.B — Dungeon walk (flat and elevated, 30 rooms)

Generate each at **flat (Elevation unchecked)** and **elevated (Elevation
checked, at moderate and dramatic where exposed)**. Confirm all three bars:
(1) walks end to end — every room reachable on foot, no floating island, no
unclimbable ramp; (2) ramps land flush at both openings and are subdivided
finely enough to climb; (3) no corridor runs through a third room or crosses
another corridor.

- [ ] **[MUST] M0 seed — `create a dungeon with 30 rooms`, seed `1949459644`**
      — prompt-driven, flat AND elevated. (M1-moved layout; see the seed-break
      note.)
- [ ] **[MUST] M0 seed — `a dungeon with 30 rooms and long halls`, seed
      `1510177507`** — prompt-driven, flat AND elevated. Long halls mean long
      ramps; watch bar 2.
- [ ] **[MUST] Moved seeds — flat 30-room dungeons** — spot-check a spread of
      the loop-edge-drop seeds that the wave-1 conflict fix re-routed: dungeon,
      30 rooms, flat, seeds `2`, `41`, `64`, `110`, `159`, `160`, `173`. All
      three bars hold on each.
- [ ] **[SHOULD] Moved seeds — crosses-room split spread** — a handful of flat
      30-room dungeons in seeds 1–200 (e.g. `5`, `8`, `9`) that the A→C→B split
      re-routed; confirm no corridor clips a third room.
- [ ] **[SHOULD] Elevated moved cases** — dungeon 26 rooms seed `2985` dramatic
      (reachability case) walks end to end; dungeon 13 rooms seed `13` dramatic
      (short-ramp case, corr_13) lands flush at both ends.

### M1.C — City walk (flat and elevated, 12 and 30 rooms)

- [ ] **[MUST] City flat** — city, 12 rooms and 30 rooms, flat, walk end to end;
      no corridor through a third room or across another corridor.
- [ ] **[MUST] City elevated** — city, 12 rooms and 30 rooms, elevated; ramps
      land flush and every room is reachable.
- [ ] **[SHOULD] City moved seeds** — spot-check the loop-edge-drop city seeds:
      city 30 rooms flat, seeds `41`, `64`, `93`, `110`, `159`, `160`.

### M1.D — Both Generate actions

- [ ] **[MUST] Generate from description (prompt)** — The header's description
      Generate action builds from the prompt text; the panel shows the build was
      produced in **prompt** mode.
- [ ] **[MUST] Generate from controls** — The Controls Generate action builds
      from the panel fields (zone type / rooms / size / verticality / locks /
      seed); the panel shows the build was produced in **controls** mode.
- [ ] **[MUST] Blank seed is fresh** — Generating with the seed box empty yields
      a new seed and visibly different geometry each time.
- [ ] **[MUST] Typing is safe** — While typing in the prompt box or the seed
      box, WASD/Space/R edit the text and do NOT move the camera.
- [ ] **[SHOULD] Substitution warning reads in words** — If a prompt asks for a
      disabled zone type, the build is substituted to `dungeon` and the warning
      region says so in plain words (`zone_type_substituted`).

### M1.E — Naming and per-build folders

- [ ] **[MUST] Consistent file names** — For one build with name `<name>`, every
      downloaded/served artifact carries that name consistently: `<name>.eqg`,
      `ter_<name>.ter`, `<name>.zon`, `<name>.glb`, `<name>.zone.json`,
      `<name>.map.svg`.
- [ ] **[MUST] One folder per build** — Each build lands in exactly one
      `<zone_id>/v1/` folder; a second generate makes a new `<zone_id>/v1/`, it
      never overwrites or scatters files outside that folder.
- [ ] **[SHOULD] Format gate honoured** — A served/accepted build passes the
      Tier-1 format check (`analyzer.rof2check.check_eqg`); the panel/sidecar
      reports `format_passed`.

## Step 1 — Wilderness (open Karana)

> The `zone-generator-wilderness` milestone (roadmap step 1), signed off on
> 2026-10-29 and enabled for everyone. Re-walk it after a major change to the
> wilderness pipeline. Check the side panel shows no stale-code banner.

### Cases

Pick **wilderness**, set the edges in the Edges box, pin the seed. Task 5
changed no settings, so no seed moved since the first look.

| # | Edges | Seeds |
|---|-------|-------|
| a | all mountain (default) | 1337, 1, 42, 20250126 |
| b | N zoneline | 7, 2985 |
| c | N zoneline, E river | 1955208177, 123456789, 2024 |
| d | any (the matrix seeds lava) | 99, 2024 |
| e | S river (water and mud banks) | 7 |

### W.1 — Landform and bowl

- [ ] **[MUST] Open plain** — Reads as an open plain with weathered hills, not a
      crater and not a room graph in a grass skin.
- [ ] **[SHOULD] Water-made relief** — Valleys and ridges look carved by water
      (branching drainage), not noise blobs.
- [ ] **[SHOULD] Sharp edges** — Cliffs and shorelines are sharp, not
      stair-stepped.
- [ ] **[MUST] Rim is a backdrop** — The mountain Rim reads as a distant
      backdrop, not a wall right at the play edge.
- [ ] **[MUST] Sealed** — You can't walk out over a mountain edge or across a
      river edge.
- [ ] **[MUST] Zoneline gap** — A zoneline edge is a flat, walkable opening
      leading off the map.
- [ ] **[MUST] Lava** — Lava reads as a hazard you can't walk onto.
- [ ] **[SHOULD] Size** — The zone feels big enough to be a Karana (2400 u today).

### W.2 — Water

- [ ] **[MUST] Water plane** — Every river and water body has a flat, see-through
      surface at one level; the bed under it is visibly lower.
- [ ] **[SHOULD] Shoreline** — The water edge meets the bank. Known issue: on
      some seeds part of the shore sits below the water level, so the surface
      hovers over the bank (tracked, fix belongs in `synth.py`). Note how bad it
      looks, not just whether it happens.
- [ ] **[MUST] Water doesn't block** — You can walk into the shallows; the
      surface is not a floor and not a wall.

### W.3 — Ground textures (biome kit)

The preview shows each material's base colour, not the real DDS textures.

- [ ] **[MUST] Layered ground** — The plains are not one flat colour: dry grass
      on the high ground, bare dirt and rock where it is steep, dark mud along
      the water.
- [ ] **[SHOULD] Layers sit where they should** — Rock hugs the foot of the Rim
      and steep slopes, not the open flats; mud only beside water.
- [ ] **[SHOULD] Region kinds read apart** — Rim, cliff, lava, zoneline and the
      river bed are each distinct from the plains.

### W.4 — Sidecar and reproducibility

- [ ] **[MUST] Sidecar** — `<name>.zone.json` carries `biome: plains`, the four
      `edge_connections` as set, an `invisible_walls` box per river edge, `lava`
      regions marked `damaging`, `region_intent` for every region (water and
      lava scenic, zoneline playable) and a `Spawn` POI anchor.
- [ ] **[MUST] Pinned seed repeats** — Generating the same pinned seed and edges
      twice gives the same landscape.
- [ ] **[MUST] Blank seed is fresh** — With the seed box empty, each generate
      gives a different landscape.
- [ ] **[SHOULD] Snappy** — A wilderness generate returns in a few seconds (the
      pipeline budget is 60 s).

---

## Step 1b — True-layout map

> Roadmap step 1b (`zone-generator-m2-true-layout-artifacts`). Each accepted
> build now carries a map traced from its own mesh (`<name>.map.svg`, walls
> solid, ledges dashed), EverQuest in-client map files (`maps/<name>.txt`, plus
> `maps/<name>_1.txt` .. for stacked floors) and a Files panel of downloads.
> Along the way doorways and corridor bends gained walls, and rooms moved a
> full corridor width apart so corridors never run through them (task 14), so
> **every box layout moved**. Don't compare against older screenshots: the
> check is "the map matches the 3D" on whatever each seed builds now. Restart
> the Server on the merged code first and check the side panel shows no
> stale-code banner.

### Cases

Dungeon cases: zone type **dungeon**, **12 rooms**, seed pinned. Elevated means
Elevation checked at **moderate**. The wilderness case uses the Edges box.

| # | Zone type | Settings | Seed |
|---|-----------|----------|------|
| a | dungeon | 12 rooms, elevated (moderate) | 1955208177 |
| b | dungeon | 12 rooms, elevated (moderate) | 1516796975 |
| c | dungeon | 12 rooms, elevated (moderate) | 678358326 |
| d | dungeon | 12 rooms, flat | 7 |
| e | wilderness | edges N zoneline, E river (Step 1 case c) | 1955208177 |

Case b builds with every floor at the same height on the current code (its
rooms got no rise), so it is a second flat case in practice; c is the one with
real height changes. Each case builds on the first attempt from the command
line too, which is what the `.txt` overlay check below uses:

```bash
python main.py generate accept_a --zone-type dungeon --rooms 12 --verticality moderate --seed 1955208177
python main.py generate accept_b --zone-type dungeon --rooms 12 --verticality moderate --seed 1516796975
python main.py generate accept_c --zone-type dungeon --rooms 12 --verticality moderate --seed 678358326
python main.py generate accept_d --zone-type dungeon --rooms 12 --verticality flat --seed 7
python main.py generate accept_e --zone-type wilderness --seed 1955208177 --edges N=zoneline,E=river
```

Each prints its build folder (`output/<name>_<id>/v1/`), which holds
`<name>.eqg`, `<name>.glb`, `<name>.map.svg`, `<name>.zone.json` and
`maps/<name>.txt`.

### 1b.A — Walls in 3D (tasks 2 and 14)

Walk cases a–d in the 3D view.

- [ ] **[MUST] Doorways walled** — Every doorway is a gap in a solid wall: wall
      on both sides of the corridor mouth and a lintel above it. You can't see
      past a doorway's sides into the void, and you can't walk round it.
- [ ] **[MUST] Corridor bends walled** — At every bend of a corridor (L or Z
      route) the outer corner is closed; no open seam where two legs meet.
- [ ] **[MUST] Corridors clear of rooms** — No corridor runs through a third
      room or along inside a room's wall; rooms sit visibly apart.
- [ ] **[MUST] Still walks end to end** — Every room is reachable on foot;
      ramps on case c land flush at both openings.

### 1b.B — Map matches the 3D view

Open the map dialog for each case and compare it with the 3D view from above.

- [ ] **[MUST] Walls match** — Every solid line on the map sits where the 3D
      shows a wall, and every wall in the 3D has a line. Rooms and corridors
      are drawn by their real outline, not just the room boxes.
- [ ] **[MUST] Doorways open** — Each doorway is a gap in the map's line, at the
      place the corridor meets the room.
- [ ] **[MUST] Ledges dashed** — Dashed lines appear exactly where the floor
      ends with no wall. Box builds should have none now (doorways and bends
      are walled); on case e the dashes are the zoneline gap and the river
      edge.
- [ ] **[MUST] Wilderness border** — On case e the map shows the walkable
      border of the terrain plus slope breaks over 40°. No contour or path
      lines: that's the accepted content, not a gap.
- [ ] **[MUST] North-up** — The map's top is +Y (north) in the 3D view, and
      left/right are not mirrored.

### 1b.C — Annotations

- [ ] **[MUST] Readable over the outline** — Room roles, room ids, depth
      numbers, the boss star and gate links are all still readable on top of
      the outline lines (the outline sits under them, never over).

### 1b.D — Files panel and downloads

Use case a (any case works). The browser's download folder should get each
file under the build's name.

- [ ] **[MUST] Every file listed** — The Files panel lists the map SVG, the map
      PNG, each `maps/<name>*.txt` file, the `.eqg`, and the other build files,
      each with a label naming its type.
- [ ] **[MUST] Named `<name>.*`** — Downloads arrive as `<name>.map.svg`,
      `<name>.map.png`, `<name>.txt` (and `<name>_1.txt` .. when there are
      stacked floors) and `<name>.eqg`; nothing named after a URL path or
      `download`.
- [ ] **[MUST] PNG at 2×** — The PNG's pixel size is twice the SVG's viewBox
      (open the SVG in a text editor for the viewBox; check the PNG's size in
      the file's properties). The map dialog's "Download PNG" gives the same
      file.
- [ ] **[MUST] One missing file marks only itself** — The panel probes each file
      when a build is shown; it doesn't re-probe on a page reload (the reload
      clears the panel). To exercise it: in the browser's developer tools,
      Network tab, block the request URL pattern `*/maps/*`, then generate.
      Only the `.txt` entries show as unavailable; the rest stay usable. Unblock
      afterwards. Then delete one file of that build on disk (e.g.
      `maps/<name>.txt`) and click its link: the Server answers 404 and no
      other link is affected.
- [ ] **[SHOULD] Keyboard** — Tab reaches every download link; WASD doesn't
      move the camera while the panel or the map dialog has focus.

### 1b.E — `.txt` overlay

For each command-line build above, draw its EQ map files back over its
outline (the path is the build folder the generate printed):

```bash
python scripts/eqmap_preview.py output/<name>_<id>/v1
```

It writes `<name>.overlay.svg` in that folder and prints the line and label
count (about 130–150 lines; 2 labels for a dungeon, 0 for wilderness).

- [ ] **[MUST] Lands on the walls** — Open the overlay SVG: the `.txt` lines sit
      exactly on the outline's walls, with no offset, scale or mirror.
- [ ] **[MUST] North-up** — The overlay has the same orientation as the 3D view
      from above.
- [ ] **[MUST] Labels in place** — `Entrance` and `Boss` labels sit inside the
      entrance and climax rooms.

### 1b.F — In-client check (deferred to M6)

- [ ] **[DEFERRED]** Loading `maps/<name>.txt` in the RoF2 client and seeing
      lines on the walls in the right orientation needs a takeover install; it
      moves to M6's in-engine smoke load. Not part of this pass.

---

## Step 2 — Trees

> Roadmap step 2 (`zone-generator-wilderness-trees`). Wilderness plains now
> carry trees: three species (broadleaf, conifer, sapling) placed in groves
> with open meadow between, packed into the `.eqg` as generated `.mod` models
> and drawn in the preview as a separate `vegetation` node. The terrain is
> untouched: the same seed and edges give the same ground at every density.
> Restart the Server on the merged code first and check the side panel shows
> no stale-code banner.

### Cases

Pick **wilderness**, set the edges and **Trees** in the Wilderness box, pin
the seed. Each case builds on the first attempt.

| # | Edges | Trees | Seed | Trees placed |
|---|-------|-------|------|--------------|
| a | N zoneline | dense | 7 | 198 |
| b | N zoneline, E river | normal | 1955208177 | 96 |
| c | S river | sparse | 7 | 45 |
| d | all mountain (default) | none | 1337 | 0 |
| e | prompt: `a dense wooded karana` | (from the prompt) | any | — |

From the command line:

```bash
python main.py generate trees_a --zone-type wilderness --seed 7 --edges N=zoneline --trees dense
python main.py generate trees_b --zone-type wilderness --seed 1955208177 --edges N=zoneline,E=river --trees normal
python main.py generate trees_c --zone-type wilderness --seed 7 --edges S=river --trees sparse
python main.py generate trees_d --zone-type wilderness --seed 1337 --trees none
```

The preview shows each tree in its species' base colours: a brown trunk and
flat green leaf cards, not the real bark and leaf textures (those are in the
`.eqg` for the client).

### T.1 — Groves and grounding

- [ ] **[MUST] Groves, not a scatter** — Trees gather in groves of a handful to
      a dozen or so, with open meadow between and the odd lone tree. They are
      not spread evenly like a grid or a sprinkle.
- [ ] **[MUST] On the ground** — Every trunk meets the ground, slopes included;
      no base floats above the grass and no tree is buried to the canopy.
- [ ] **[SHOULD] Species read apart** — Broadleaf, conifer and sapling are
      distinguishable, and the mix reads as a Karana, not a forest.
- [ ] **[SHOULD] Size** — Trees look the right size next to the hills and the
      zone, like the tall Karana trees (roughly 50–130 u before per-tree
      scaling), not shrubs and not giants.
- [ ] **[SHOULD] Density steps** — Cases c, b and a read as clearly sparser to
      denser; case d has no trees at all.

### T.2 — Where trees may not stand

- [ ] **[MUST] Not in water** — No tree stands in a river or on its surface;
      the shore band stays clear.
- [ ] **[MUST] Not on cliffs or the Rim** — The mountain Rim and steep slopes
      stay bare rock; trees only on the plains.
- [ ] **[MUST] Spawn clearing** — There's an open clearing around Spawn.
- [ ] **[MUST] Zone exits clear** — A zoneline gap (cases a and b) has no tree
      in or just in front of it; you can fly straight out through it.
- [ ] **[MUST] No walled-off meadow** — Trees never close off a meadow: every
      open area you can see has a way in between the trunks.

### T.3 — Trunk and canopy

Tree trunks are solid and canopies are walk-through in the `.eqg` (polygon
flags). The preview is free-fly with no collision, so it can't show this; the
in-client check is M6.

- [ ] **[SHOULD] Shape** — Each tree reads as a trunk with a canopy on top:
      crossed leaf cards for broadleaf and sapling, stacked tiers for conifer.
- [ ] **[DEFERRED]** Walking into a trunk stops you and walking through a
      canopy doesn't, in the RoF2 client. Moves to M6's in-engine smoke load.

### T.4 — Selector, toggle and sidecar

- [ ] **[MUST] Trees selector** — The Trees selector shows only for
      wilderness, and changing it changes how many trees the next build has.
- [ ] **[MUST] Prompt words** — Case e builds a dense wood; `barren plains`
      builds none; `sparse karana plains` builds sparse.
- [ ] **[MUST] Toggle** — The Trees checkbox under Overlays hides and shows the
      trees, is reachable with Tab and Space, and is greyed out on a build
      without trees (case d, any dungeon or city).
- [ ] **[MUST] Framing unchanged** — The camera starts in the same place as
      the same seed with Trees set to none.
- [ ] **[MUST] Sidecar** — `<name>.zone.json` carries a `vegetation` block:
      `kit`, `level`, `level_source` (`controls`, `cli`, `prompt` or
      `default`), `counts` per species, `total`, the `models` filenames and a
      `grove_ratio` between 0.45 and 0.85.
- [ ] **[MUST] Pinned seed repeats** — The same seed, edges and Trees give the
      same trees twice.
- [ ] **[SHOULD] Snappy** — A dense build is not noticeably slower than none
      (trees add well under a second today; the budget is 3 s).

---

## Step 3 — Placeholder textures

> Roadmap step 3 (`zone-generator-placeholder-textures`). Every material is
> named `<set>_<surface>` (`gnoll_temple_wall`, `gnoll_dungeon_floor`,
> `city_ceiling`, `wild_plains`) and drawn as a 256×256 placeholder: its base
> colour, a pattern for its kind of surface (floor tiles, wall bricks, ceiling
> hatch, ground dots, water waves) and its name in capitals, twice. The
> browser preview shows the textures, and the sidecar lists them all. Walls,
> floors and ceilings now carry UVs the way stock zones do, so text reads the
> right way up. Trees keep their own bark and leaf textures (base colours in
> the preview). Restart the Server on the merged code first and check the side
> panel shows no stale-code banner.

### Cases

Pin the seed. Cases b and c use the description box; the rest use the
Controls panel. Each builds on the first attempt.

| # | How | Seed | Materials |
|---|-----|------|-----------|
| a | dungeon, 12 rooms, flat | 7 | `dungeon_floor`, `_wall`, `_ceiling` |
| b | description `a gnoll temple dungeon with 8 rooms` | 7 | `gnoll_dungeon_*` plus `gnoll_temple_floor`, `_wall` |
| c | description `a kobold tomb full of lava with 6 rooms` | 11 | `kobold_dungeon_*` plus `kobold_lava_floor`, `_wall` |
| d | city | 7 | `city_floor`, `_wall`, `_ceiling` |
| e | wilderness, edges N zoneline, E river | 1955208177 | ten `wild_*` ground layers plus `liquid_water` |

From the command line (cases a, d and e):

```bash
python main.py generate tex_a --zone-type dungeon --rooms 12 --verticality flat --seed 7
python main.py generate tex_d --zone-type city --seed 7
python main.py generate tex_e --zone-type wilderness --seed 1955208177 --edges N=zoneline,E=river
```

### X.1 — Names and patterns

- [ ] **[MUST] Every surface is labelled** — Each floor, wall and ceiling (and
      each wilderness ground layer and the water) shows its material name and
      a pattern; no surface is a plain colour or noise.
- [ ] **[MUST] Names match surfaces** — Floors say `…_FLOOR`, walls `…_WALL`,
      ceilings `…_CEILING`; themed rooms in b and c say `GNOLL_TEMPLE_…` or
      `KOBOLD_LAVA_…` while corridors say `…_DUNGEON_…`; wilderness layers say
      `WILD_…` where that ground is (plains, rock on slopes, mud by water).
- [ ] **[SHOULD] Patterns read apart** — Tiles on floors, bricks on walls, a
      diagonal hatch on ceilings, dots on wilderness ground, waves on water.
- [ ] **[SHOULD] Colours carry over** — Each texture keeps its material's base
      colour, so the zone's palette is the same as before step 3.

### X.2 — Orientation, seams, legibility

- [ ] **[MUST] Upright on walls** — From inside a room or corridor, wall
      labels read left to right and the right way up, on all four sides.
- [ ] **[MUST] Unmirrored on floors and ceilings** — Floor labels read
      unmirrored from above and ceiling labels from below (their direction
      depends on which way you face).
- [ ] **[MUST] No seams** — Textures tile with no visible line where one
      repeat meets the next; labels are never cut by a tile edge.
- [ ] **[SHOULD] Readable, not overwhelming** — Labels can be read from a few
      steps away and don't drown the room. Big wilderness layers (rock, lava)
      repeat less often, so their labels are larger; that's expected.

### X.3 — Preview and files

- [ ] **[MUST] Trees unchanged** — Case e's trees keep their brown trunks and
      green canopies; the Trees toggle still hides them.
- [ ] **[MUST] Overlays work** — Wireframe shows the textured meshes' edges;
      the camera starts where it did before step 3.
- [ ] **[MUST] Texture list** — `<name>.zone.json` has a `textures` list, one
      entry per material (trees' `veg_*` too), each naming its `.dds`, set,
      surface, kind of surface, polygon count and `texture_mode`
      (`placeholder`, or `vegetation` for trees).
- [ ] **[SHOULD] Old look on request** — With `EQ_S3D_TEXTURE_PROVIDER=procedural`
      set before starting the Server, builds use the old noise textures and
      the list says `procedural`.
- [ ] **[SHOULD] Snappy** — Generating takes no longer than before step 3
      (today placeholders are a little faster than noise; the budget is 2 s).

### X.4 — In-client check (deferred to M6)

- [ ] **[DEFERRED]** Seeing the placeholders in the RoF2 client (and that the
      `Opaque_MaxCB1.fx` shader now on every dungeon and city material renders)
      needs a takeover install; it moves to M6's in-engine smoke load.
