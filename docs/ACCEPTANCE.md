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

> **Stock scale (step 7, task 17).** Every room-graph build (dungeon, city,
> outdoor dungeon; both layouts) changed size: rooms are sized for the race
> that lives in them, at the stock zones' scale. With body height H (a human
> is 6 u, an ogre 9, a giant 22, a dragon 21) every room is 2.5–10 H tall and
> 8–20 H on a side, so a human dungeon's rooms are 15–60 u tall and 48–120 u
> across (they were ~121 u tall and ~340 u across), and corridors are 3 H
> wide and 2.5 H tall (18 × 15 u for a human; they were 40–85 u wide and
> ~97 u tall). Size (small … huge) moves the rooms up or down their race's
> band. Every pinned case below was rebuilt at this scale through the
> server's generate route (60 cases, M1 through Step 6) and builds on the
> first attempt; only Step 6's e and f moved seed (3 -> 4, see there).
> Layouts differ from older screenshots. Outdoor dungeons shift their layout
> up to half a terrain cell sideways so the entrance wall holds the Tunnel
> (Step 5 case a needed it).

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

> **Layout: Classic (since step 6, task 21).** These seeds are Classic
> (TinyKeep) regression seeds, so build the Controls cases with Layout
> **Classic**. A description has no Layout toggle and now builds Graph, so
> the two prompt-driven M0 seeds walk a Graph layout: walk them as fresh
> layouts against the same three bars (like the seed-break note above), and
> for the Classic walk build the same seed from the Controls panel (Dungeon,
> 30 rooms, Layout Classic).

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

Dungeon cases: zone type **dungeon**, **12 rooms**, Layout **Classic**, seed
pinned (the seeds are Classic corridor-bug seeds; since step 6 Graph is the
default, so pick Classic). Elevated means Elevation checked at **moderate**. The wilderness case uses the Edges box.

| # | Zone type | Settings | Seed |
|---|-----------|----------|------|
| a | dungeon | 12 rooms, elevated (moderate) | 1955208177 |
| b | dungeon | 12 rooms, elevated (moderate) | 1516796975 |
| c | dungeon | 12 rooms, elevated (moderate) | 678358326 |
| d | dungeon | 12 rooms, flat | 7 |
| e | wilderness | edges N zoneline, E river (Step 1 case c) | 1955208177 |

Case b builds with every floor at the same height on Classic (its rooms got
no rise), so it is a second flat case in practice; c is the one with
real height changes. Each case builds on the first attempt from the command
line too, which is what the `.txt` overlay check below uses:

```bash
python main.py generate accept_a --zone-type dungeon --rooms 12 --verticality moderate --seed 1955208177 --layout classic
python main.py generate accept_b --zone-type dungeon --rooms 12 --verticality moderate --seed 1516796975 --layout classic
python main.py generate accept_c --zone-type dungeon --rooms 12 --verticality moderate --seed 678358326 --layout classic
python main.py generate accept_d --zone-type dungeon --rooms 12 --verticality flat --seed 7 --layout classic
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

> **Layout: Graph (since step 6, task 21).** The dungeon cases (a, b, c) now
> build with the default Graph layout; re-checked on Graph, each still builds
> on the first attempt with the materials below. Nothing here depends on the
> engine (materials come from the theme and race), so Layout stays at its
> default; Layout Classic (or `--layout classic`) gives the pre-step-6 rooms.

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

---

## Step 4 — Interesting textures

> Roadmap step 4 (`zone-generator-interesting-textures`). Dungeon and city
> surfaces are drawn from recipes: a structured painter per material family
> (dressed stone, brick, flagstone, cobble, cave rock, planks, plaster, ice,
> sky), graded toward the classic look measured from the stock zones (darker,
> more saturated, crisper than before), at the classic texel density (dungeon
> walls repeat every ~24 u, floors and ceilings ~28 u; city surfaces ~14 u;
> it was 100 u). Hallways in a themed dungeon match their rooms. Wilderness
> ground, water and trees are unchanged (a later step). Restart the Server on
> the merged code first and check the side panel shows no stale-code banner.

### Cases

Pin the seed. Cases a–d use the description box; e and f the Controls panel.
Each builds on the first attempt.

> **Layout: Graph (since step 6, task 21).** The dungeon cases (a–e) now build
> with the default Graph layout; re-checked on Graph, each still builds on the
> first attempt with its theme's materials. The surfaces come from the theme,
> not the engine, so Layout stays at its default.

| # | How | Seed | Walls / floors / ceilings |
|---|-----|------|---------------------------|
| a | `a gnoll temple dungeon with 8 rooms` | 7 | dressed stone / flagstone / cave rock |
| b | `a kobold tomb full of lava with 6 rooms` | 11 | cave rock (basalt) / flagstone / cave rock |
| c | `a giant ice keep with 8 rooms` | 7 | ice / flagstone / cave rock |
| d | `a wizard lair with 8 rooms` | 7 | brick / flagstone / cave rock |
| e | dungeon, 12 rooms, flat | 7 | dressed stone / flagstone / cave rock |
| f | city | 7 | plaster / cobble / sky |

From the command line (cases e and f):

```bash
python main.py generate looks_e --zone-type dungeon --rooms 12 --verticality flat --seed 7
python main.py generate looks_f --zone-type city --seed 7
```

### L.1 — Materials and themes

- [ ] **[MUST] Surfaces read as their material** — Walls show blocks, bricks,
      basalt or ice with joints; floors show slabs or cobbles; dungeon
      ceilings read as rough rock; city ceilings as sky.
- [ ] **[MUST] Themes differ** — Cases a–e look different from each other at
      a glance (sandstone temple, sooty basalt forge, pale ice, purple brick,
      plain stone), not one texture recoloured.
- [ ] **[MUST] Hallways match their rooms** — In a, b, c and d a hallway's
      floor and walls are the same as the rooms it joins; only ceilings are
      shared.
- [ ] **[SHOULD] Classic look** — Dark, earthy and crisp like a Classic–PoP
      dungeon, not pale, grey or blurry.

### L.2 — Scale, seams and repetition

- [ ] **[MUST] Scale** — A wall block is about a player's height or smaller;
      cobbles and slabs read at a walking scale.
- [ ] **[MUST] No seams** — Textures tile with no visible line where one
      repeat meets the next.
- [ ] **[SHOULD] Repetition** — At ~24 u a long wall repeats its texture many
      times; it should read as masonry, not wallpaper. Note any wall where the
      repeat is distracting.

### L.3 — Modes, preview and files

- [ ] **[MUST] Wilderness unchanged** — A wilderness zone still shows step 3's
      labelled placeholders on the ground and the same trees.
- [ ] **[MUST] Texture list** — In `<name>.zone.json` each dungeon or city
      entry in `textures` has `texture_mode: procedural`, its
      `texture_family` and `look_stats`; each material in the saved spec
      (`<name>.json`) has its `texel_density`.
- [ ] **[SHOULD] Placeholders on request** — With
      `EQ_S3D_TEXTURE_PROVIDER=placeholder` set before starting the Server,
      dungeons and cities show labelled placeholders again at 100 u.
- [ ] **[SHOULD] Snappy** — Generating takes no noticeably longer than step 3
      (a 30-room dungeon adds ~0.35 s; the budget is 2 s).

### L.4 — In-client check (deferred to M6)

- [ ] **[DEFERRED]** Seeing the textures, scale and seams in the RoF2 client
      needs a takeover install; it moves to M6's in-engine smoke load.

---

## Step 5 — Outdoor dungeon

> Roadmap step 5 (`zone-generator-outdoor-dungeon`). A hillside cave in the
> Blackburrow / Runnyeye mould: a compact (~1200 u) wilderness landscape with a
> hill backed onto a mountain side, a dungeon of rooms and ramps under the
> hill, and one cave mouth in its flank you walk into from the open ground.
> Restart the Server on the merged code first and check the side panel shows
> no stale-code banner.

### Cases

Pin the seed. Cases a–d use the description box; e–g the Controls panel with
**Outdoor dungeon** picked. Each builds on the first attempt.

> **Layout: Graph (since step 6, task 21).** Every case now lays its dungeon
> out with the default Graph layout (d with the `warren` set, the rest
> `classic_eq`, c with the `temple` layer); re-checked on Graph, each still
> builds on the first attempt with the theme, race and room count below. The
> checks (landscape, mouth, walk, maps) hold for either engine, so Layout
> stays at its default; Layout Classic (or `--layout classic`) gives the
> step 5 dungeon.

| # | How | Seed | What it shows |
|---|-----|------|---------------|
| a | `a cave in a hill where kobolds live` | 7 | kobold race, 5 rooms |
| b | `an old barrow on the moors` | 11 | plain, 5 rooms |
| c | `a hillside cave temple with 6 rooms` | 3 | temple theme |
| d | `a gnoll warren in the hills` | 2 | warren theme, gnoll race, 9 rooms |
| e | Controls: 5 rooms | 5 | defaults |
| f | Controls: 4 rooms, 1 lock, N zoneline, E river, trees dense | 2 | a lock, zoneline and river edges |
| g | Controls: 6 rooms, trees none | 42 | bare hill |

From the command line (cases e and f):

```bash
python main.py generate odungeon_e --zone-type outdoor_dungeon --rooms 5 --seed 5
python main.py generate odungeon_f --zone-type outdoor_dungeon --rooms 4 --locks 1 --edges N=zoneline,E=river --trees dense --seed 2
```

### O.1 — Landscape

- [ ] **[MUST] A hill on open ground** — The zone reads as wilderness with one
      hill standing out of it, backed onto the mountain Rim, not a crater and
      not a dungeon in a grass skin.
- [ ] **[MUST] Wilderness as before** — Rim, zonelines, river edges, ground
      layers and trees behave as in Step 1 and Step 2 (W.1–W.3, T.1–T.2).
- [ ] **[SHOULD] Size** — Compact: about 1200 u, the hill a good share of it.

### O.2 — Entrance

- [ ] **[MUST] One way in** — There is one cave mouth, in the hill's flank on
      the side away from the Rim, reached across open ground.
- [ ] **[MUST] No gaps** — Walk the trench, the mouth and the tunnel looking
      up, down and sideways: no sky or void shows through any seam where the
      ground meets the mouth's jambs, headwall or tunnel.
- [ ] **[MUST] Carved look** — The mouth reads as cut into the hill (a trench
      dug down to a rock face with an opening), not a doorway stuck on a slope.
- [ ] **[MUST] Walkable** — The trench and tunnel ramp are walkable both ways
      without jumping; nothing snags at the mouth.
- [ ] **[SHOULD] Enclosed** — From inside the dungeon the hill above is not
      visible through ceilings or walls; the rock over every room looks solid.

### O.3 — The dungeon and the walk

- [ ] **[MUST] Every room from the spawn** — From the outdoor spawn, walk in
      through the mouth and reach every room on foot (case f: the lock is
      advisory, walk through it).
- [ ] **[MUST] Entrance first** — The tunnel opens into the room the Pacing
      panel tags `entrance`; the `climax` room is the deepest, not the first.
- [ ] **[MUST] Under the hill** — No room or corridor pokes out of the hill's
      surface or past its foot.
- [ ] **[SHOULD] Classic outdoor dungeon** — It reads like Blackburrow or
      Runnyeye: a small warren under a hill, not a city block buried in dirt.
- [ ] **[SHOULD] Themes and races show** — Cases a–d look different from each
      other and from e (room shapes, materials, lighting).

### O.4 — Maps

- [ ] **[MUST] Two bands** — The Files panel lists `EQ map layer 0` and
      `EQ map layer 1`; the map (SVG) draws the dungeon, the lowland and the
      tunnel in one colour and the hill over the dungeon in another.
- [ ] **[MUST] Map matches the 3D view** — Room boxes, the tunnel and the
      trench sit where they are in the 3D view; the `Entrance` label is on the
      room the tunnel opens into.

### O.5 — Controls, sidecar and speed

- [ ] **[MUST] Controls** — Picking **Outdoor dungeon** shows Rooms, Locks and
      the Landscape box (edges, trees) and hides Size; Verticality shows
      since step 7 (see Step 7); each setting reaches the build (check the sidecar).
- [ ] **[MUST] Sidecar** — `<name>.zone.json` has an `outdoor_dungeon` block:
      `envelope` (bounds and floor limit), `rock_cover`, one `entrances` entry
      (tunnel id, room, apron centre, mouth) and `outdoor_spawn`; plus the
      wilderness keys (`edge_connections`, `vegetation`).
- [ ] **[MUST] Pinned seed repeats; blank seed is fresh** — As in W.4.
- [ ] **[SHOULD] Snappy** — A generate returns in well under a minute (a few
      seconds typical; the pipeline budget is 60 s).

Known limits (follow-ups in the spec's `archive.md`, not failures here):
since step 7's stock scale ogre outdoor dungeons build, and giants and dragons
build with rooms dropped (a taller host is a follow-up).

### O.6 — In-client check (deferred to M6)

- [ ] **[DEFERRED]** Zoning in through the zoneline, walking the mouth and
      the tunnel, and the map in the RoF2 client need a takeover install; it
      moves to M6's in-engine smoke load.

---

## Step 6 — Graph layouts

> Roadmap step 6 (`zone-generator-graph-layout`). A dungeon's room graph can
> now be **grown** instead of scattered. **Graph** is the default since
> task 21: a dungeon or outdoor dungeon request that names no layout (the
> Controls panel untouched, a description, the CLI without `--layout`) is
> grown. **Classic** is TinyKeep: rooms are scattered, pushed apart and joined by a cut-down
> triangulation, so the graph is whatever the rooms' positions give.
> **Graph** grows the graph first, by rewrite rules: start from a small graph
> of placeholders, apply rules (pattern → replacement) stage by stage until
> none is left, then place the rooms with a spring layout and make the
> corridors. The rules give every room a **kind** (`entrance`, `chamber`,
> `hub`, `lair`, `hall`, `passage`, `deep`) and a **size class** (`tiny` …
> `huge`); the theme maps kinds onto its room types (a temple's `deep` is its
> inner sanctum, a fortress's its throne room) and the race scales the units.
> The rules live in **rule sets**, TOML files under `rules/topology/`: two
> base sets, `classic_eq` (shaped like the classic dungeons) and `warren`
> (shaped like Blackburrow: more short loops, fewer dead ends, a shallower
> deep end, more small rooms), and one **theme layer**, `temple` (a nave: a
> large hall with two small chapels). Rule set **From theme** takes the
> theme's base set and layers (Warren → `warren`; Temple → `classic_eq` +
> `temple`; any other theme or none → `classic_eq`). Everything after the
> graph (pacing, themes, elevation, corridors, locks, the walkability gate,
> maps, textures) is as before. Restart the Server on the merged code first
> and check the side panel shows no stale-code banner.

### Cases

Pin the seed. **Every case is made from the Controls panel alone** (Zone
type, Rooms, Theme, Race, Layout, Rule set, Seed); leave the description box
empty, since a description doesn't take the Layout toggle (it always builds
Graph with the theme's rule set). Size, Verticality
and Locks stay at their defaults (medium, moderate, 0); Theme and Race stay
None unless the row names them. Each builds on the first attempt.

| # | Controls | Seed | What it shows (sidecar) |
|---|----------|------|-------------------------|
| a | Dungeon, 12 rooms, Layout **Classic** | 4 | `layout.engine: classic`; no loop, 5 dead ends |
| b | Dungeon, 12 rooms, Layout **Graph**, Rule set **classic_eq** | 4 | `classic_eq`, no layers; 1 loop, 5 dead ends; kinds entrance, chamber ×6, lair ×3, passage, deep |
| c | Dungeon, 12 rooms, Layout **Graph**, Rule set **warren** | 4 | `warren`; 3 loops, 1 dead end, a shallow deep end (0.25 against b's 0.50); 5 small rooms and no large |
| d | Dungeon, 12 rooms, Theme **Temple**, Layout **Graph**, Rule set From theme | 4 | `classic_eq` + layer `temple`; `nave` applied (a large `hall` with two small `lair` chapels); the `deep` room is the `inner_sanctum` and the boss room |
| e | Dungeon, 12 rooms, Race **Ogre**, Layout **Graph**, Rule set From theme | 4 | the ogre (body height 9 u, `race_scale` 1.5 = 9 / 6) reaches the big-race rule `great_hall` (`race_scale >= 1.4`): a `huge` `hall` on the way (room_4); rooms sized from the ogre's bands (mean floor area ~2.6× b's); the theme falls back to `fortress`, the `deep` room (room_5) is the `throne`; `edge_fidelity` 1.0 |
| f | Dungeon, 12 rooms, Race **Giant**, Layout **Graph**, Rule set From theme | 4 | e's graph (the same `applied` list, great hall included) at the giant's body height, 22 u: rooms far bigger again (mean floor area ~6× e's, (22 / 9)²), `edge_fidelity` 1.0 |
| g | Outdoor dungeon, 5 rooms, Layout **Graph**, Rule set From theme, Landscape defaults | 4 | `classic_eq` under the hill: the mouth opens into the `entrance` room and the `deep` room is the climax |

Cases a, b and c share seed and room count on purpose: compare them side by
side. They use 12 rooms rather than the first look's 9 because the shapes
differ more clearly with more rooms. Cases e and f share a seed on purpose:
both races are big, so they grow the same graph and differ only in scale.
(They were seed 3 until step 7: task 6's vertical rules moved the rng, and
seed 3 no longer grows a great hall; seed 4 does.) A temple needs at least 7 rooms for its
nave (with fewer it doesn't fit: the sidecar still lists the `temple` layer
but `applied` has no `nave`), so keep d at 9 or more.

From the command line (cases a, b, c and g). The CLI has `--layout` and
`--rule-set` but **no dungeon theme or race flag** (its `--theme` is the old
alias for `--zone-type`), so d, e and f are made in the Controls panel only:

```bash
python main.py generate graph_a --zone-type dungeon --rooms 12 --seed 4 --layout classic
python main.py generate graph_b --zone-type dungeon --rooms 12 --seed 4 --layout graph --rule-set classic_eq
python main.py generate graph_c --zone-type dungeon --rooms 12 --seed 4 --layout graph --rule-set warren
python main.py generate graph_g --zone-type outdoor_dungeon --rooms 5 --seed 4 --layout graph
```

Case h is the rule tooling, from the repo root:

```bash
python scripts/topology_rules.py check                     # every shipped file and each theme's merged set
python scripts/topology_rules.py dry-run classic_eq --graphs 20 --rooms 5-20
python scripts/topology_rules.py dry-run warren --graphs 20 --rooms 5-20
python scripts/topology_rules.py dry-run classic_eq --theme temple --rooms 9-16 --race-scale 1.6
python scripts/topology_rules.py draw classic_eq --out output/rules/
python scripts/topology_rules.py draw warren --out output/rules/
python scripts/topology_rules.py draw classic_eq --theme temple --out output/rules/
```

### G.1 — Shape and connectivity

- [ ] **[MUST] Reads as a dungeon** — b, c and d have a way in, side rooms
      and a deep end worth reaching, not a ring of equal rooms or a string of
      beads.
- [ ] **[MUST] Every room on foot** — In each of a–g, walk from the spawn to
      every room; no room is cut off (case g: in through the mouth, as O.3).
- [ ] **[MUST] Corridors as good as Classic's** — b–g have no new odd joins:
      every corridor meets its rooms flush, none runs through a room or along
      a wall face, and no two rooms overlap in plan.
- [ ] **[SHOULD] Loops show** — b's loop and c's three loops can be walked
      round, coming back to where they started.

### G.2 — Rule sets look different

- [ ] **[MUST] A warren is a warren** — On the map (M), c looks unlike b:
      more loops, fewer dead ends, the deep end nearer the way in, smaller
      rooms.
- [ ] **[MUST] The temple shows its nave** — d has one large hall with two
      small rooms off it as chapels.
- [ ] **[SHOULD] Graph and Classic differ** — a and b, same seed and rooms,
      are different dungeons on the map (rooms still look alike in 3D; see
      Known limits).

### G.3 — Sizes and pacing

- [ ] **[MUST] Sizes fit the part** — Rooms the sidecar's `layout.rooms`
      tags `huge` or `large` (the deep room, halls, hubs) are clearly bigger
      than the `small` lairs and dead ends.
- [ ] **[MUST] The deep room is the climax** — In every Graph case the room
      whose `layout.rooms` kind is `deep` is the one the Pacing panel (and
      `rooms[].role`) calls `climax`; in a themed case (d, e, f) it is also
      the boss room (`boss: true`). The `entrance` kind is the `entrance`
      role, where the spawn stands.
- [ ] **[MUST] The race sizes the rooms** — e's rooms are clearly bigger
      than b's and it has its great hall; f is e's dungeon bigger again.
      Neither loses a loop to its size. Corridors and ramps stay walkable
      for the player. (Since step 7 task 17 rooms are at stock scale for
      their race; see "Stock scale" at the top.)

### G.4 — Controls and sidecar

- [ ] **[MUST] Controls** — Theme and Race show for Dungeon, City and
      Outdoor dungeon; Layout for Dungeon and Outdoor dungeon; Rule set only
      while Layout is Graph. Each setting reaches the build (check the
      sidecar's `content` and `layout`).
- [ ] **[MUST] Graph is the default** — On a fresh page load the Layout
      select shows **Graph** (its first option) with Rule set **From theme**
      visible. Dungeon, 9 rooms, seed 3, Layout left alone: the sidecar has
      `layout.engine: graph`; switch Layout to Classic and generate again:
      `engine: classic`. A description build (`a dungeon with 9 rooms`, seed
      3) has `engine: graph`. From the command line,
      `python main.py generate d1 --zone-type dungeon --rooms 9 --seed 3`
      gives `engine: graph` and the same with `--layout classic` gives
      `classic`. City and Wilderness show no Layout and build as before.
- [ ] **[MUST] From theme** — Theme **Warren**, Layout Graph, Rule set From
      theme, 12 rooms, seed 4 builds with `layout.rule_set: warren` (c's
      graph); Theme Temple gives `classic_eq` with `layers: ["temple"]`.
- [ ] **[MUST] Sidecar `layout` block** — A Graph build's `<name>.zone.json`
      has `layout` with `engine: graph`, `rule_set`, `layers`,
      `placement: spring`, `applied` (the stage and rule of each application,
      in order), `rooms` (per room: `kind`, `size`, `district`, `node`),
      `edges` (each with its vertical relation), `shape` (`dead_end_share`,
      `cycle_rank`, `deep_end`), `edge_fidelity` (1.0 in every case above)
      and `relations_broken` (0). A Classic build's block has
      `engine: classic` and `shape`.
- [ ] **[MUST] Pinned seed repeats; blank seed is fresh** — As in W.4, for
      Graph as for Classic.
- [ ] **[SHOULD] Snappy** — A Graph build takes no longer than the Classic
      build of the same controls plus 10 s (14 rooms, seed 4, at stock
      scale: Classic ~0.7 s, Graph ~1.4 s; before step 7 task 17 Classic
      was ~4 s).

### G.5 — Tooling and the guide

- [ ] **[MUST] check** — `check` prints `ok` for every shipped file and each
      theme's merged set, and ends `all checks passed`. A broken copy (say a
      replace kind misspelt `hubb`) fails with a line naming the file, the
      rule, the field and what was expected.
- [ ] **[MUST] dry-run** — Reports each stage's completion, how often each
      rule fired (and any that never did), the shape measures and the size
      mix. Without `--race-scale 1.4` or more, `great_hall` is listed as
      never fired; it is the big-race rule, so that is expected.
- [ ] **[MUST] draw** — Writes `classic_eq.html`, `warren.html` and
      `classic_eq-temple.html` into `output/rules/`; each shows the start
      graph, the recipe and every rule as a before → after diagram, clear
      enough to write a rule from.
- [ ] **[SHOULD] The guide** — `docs/TOPOLOGY_RULES.md` explains the format
      with the shipped sets as examples and how to check, dry-run and draw;
      following it you could add a rule to a copy of `classic_eq` and see it
      fire in a dry run.

Known limits (follow-ups in the spec's `archive.md`, not failures here):
Classic rooms all look alike (rectangles with their zone's textures; Graph's room
shapes came with step 8, room contents are step 9); description words don't choose a
layout (a description builds Graph with the theme's rule set; words like
"maze" choosing a rule set are a fast follow); the warren bands rest on one stock zone
(Blackburrow); and a race with no theme builds fortress rooms (cases e and
f), the existing default.

### G.6 — In-client check (deferred to M6)

- [ ] **[DEFERRED]** Walking a grown dungeon, its loops and its room sizes
      in the RoF2 client needs a takeover install; it moves to M6's in-engine
      smoke load.

---

## Step 7 — Dungeon verticality

> Roadmap step 7 (`zone-generator-dungeon-verticality`). A **Graph** dungeon
> or outdoor dungeon now has **Levels**: rooms can sit directly above other
> rooms, joined by **stairs** (treads and risers of about 2 u, usually two
> flights turning back on themselves, because one Level is a long climb). A
> corridor between same-Level rooms can be a **bridge**: a railed deck
> crossing over a lower room, down a shaft cut through that room's ceiling.
> **Verticality** sets how much of this there is: Flat is one Level, Moderate
> uses the rules' weights, Dramatic doubles them. Dramatic is more on average
> (about 2.7 Levels against 2.3 at 12 rooms) but about a third of seeds at 12
> rooms stack the same at both, so the cases below use a seed that shows the
> difference. Classic stays one Level. Restart the Server on the merged code
> first and check the side panel shows no stale-code banner.

### Cases

Pin the seed. **Every case is made from the Controls panel alone**; leave the
description box empty. Layout is Graph throughout, Size and Locks stay at
their defaults (medium, 0), Theme and Race stay None and Rule set From theme
unless the row names them. Each builds on the first attempt.

| # | Controls | Seed | What it shows (sidecar `layout`) |
|---|----------|------|-------------------------|
| a | Dungeon, 12 rooms, Rule set **classic_eq**, **Flat** | 10 | One Level; `stacked_share` 0; 12 flat corridors; one EQ map file |
| b | Dungeon, 12 rooms, Rule set **classic_eq**, **Moderate** | 10 | Levels 0 and 1 (9 and 3 rooms); `stacked_share` 0.06; 2 stairs, each 102 u up in 52 risers; 2 map layers |
| c | Dungeon, 12 rooms, Rule set **classic_eq**, **Dramatic** | 10 | Levels 0, 1, 2 (4, 7, 1 rooms); `stacked_share` 0.13; 4 stairs; a bridge (`corr_4`) over `room_1`; 3 map layers |
| d | Dungeon, 12 rooms, Rule set **warren**, **Moderate** | 10 | Levels -1 and 0 (4 and 8 rooms); `stacked_share` 0.04; 3 stairs; 2 map layers |
| e | Dungeon, 12 rooms, Rule set **warren**, **Dramatic** | 10 | Levels -2, -1, 0 (3, 2, 7 rooms); `stacked_share` 0.08; 4 stairs; a bridge (`corr_4`) over `room_7`; 3 map layers |
| f | Dungeon, 12 rooms, Theme **Temple**, **Moderate** | 13 | `classic_eq` + layer `temple`, `nave` applied; Levels -1, 0, 1 (1, 9, 2 rooms); `stacked_share` 0.07; 2 stairs; 3 map layers |
| g | Dungeon, 12 rooms, Race **Ogre**, **Moderate** | 10 | `great_hall` applied; Levels -1, 0, 1 (1, 9, 2 rooms); 3 stairs, each 132 u up in 66 risers; 2 map layers |
| h | Dungeon, 8 rooms, Race **Dragon**, **Moderate** | 10 | `great_hall` applied; Levels 0 and 1 (5 and 3 rooms); `stacked_share` 0.19; 2 stairs, each 252 u up in 126 risers; 2 map layers |
| i | Outdoor dungeon, 8 rooms, **Dramatic**, Landscape defaults | 13 | Levels -1 and 0 (3 and 5 rooms), the tunnel entering Level 0; `stacked_share` 0.18; 2 stairs; a bridge (`corr_0`) over `room_6`; 3 map layers |
| j | Dungeon, 12 rooms, Rule set **classic_eq**, **Moderate** | 11 | `bridge_hall` applied; Levels 0 and 1 (7 and 5 rooms); `stacked_share` 0.15; 2 bridges, `corr_4` over `room_1` and `corr_10` over `room_6`; 2 map layers |

Cases a, b and c share seed and rule set on purpose, as do d and e: compare
them side by side.

### V.1 — Levels

- [ ] **[MUST] Reads like a multi-level dungeon** — b, c, e and f have rooms
      you can stand under and rooms you look up to; going up or down feels
      like arriving somewhere new, as in Guk, Befallen or Unrest, not a flat
      map with a few steps.
- [ ] **[MUST] Every room on foot** — In each of a–j, walk from the spawn to
      every room on every Level; no room is cut off (case i: in through the
      mouth, as O.3).
- [ ] **[MUST] No odd joins in 3D** — Stacked rooms don't poke into each
      other, no corridor runs through a room, and a floor above isn't visible
      through the ceiling below.
- [ ] **[MUST] Verticality does what it says** — a is flat; c has more Levels
      and more stacking than b, and e more than d. Layout Classic with the same
      controls has one Level (its `layout` block has no `levels`).
- [ ] **[MUST] Rule sets stay themselves** — d and e still read as warrens
      (more loops, smaller rooms) and b and c as classic dungeons; f still has
      its nave, one large hall with two small chapels.

### V.2 — Stairs

- [ ] **[MUST] Walk them both ways** — In b, walk up a stair and back down.
      You don't catch on a riser, slide or fall through, and you can stop on
      any tread and on the landing.
- [ ] **[MUST] They look like stairs** — Separate treads and risers, walls
      and a ceiling all the way, no gaps at the landing or where a flight
      meets a room's floor.
- [ ] **[MUST] Headroom** — Your head never hits the ceiling on a tread, a
      landing or a stair door.
- [ ] **[MUST] Doors along a wall** — A stair that starts partway along a
      wall rather than at its middle still meets the room flush, and doesn't
      clip another room.
- [ ] **[SHOULD] Sized for the race** — g's stairs are longer and wider than
      b's, and fit an ogre. h's are very long (see Known limits).

### V.3 — Bridges

- [ ] **[MUST] Walk the deck** — In j, cross both bridges: flush at both
      ends, continuous, and the rails stop you walking off.
- [ ] **[MUST] From below** — From `room_1` and `room_6`, look up through the
      slot in the ceiling at the deck. The shaft's walls have no gaps, and you
      can walk the room beneath without anything in your way.
- [ ] **[SHOULD] Reads as a crossing** — Standing on a deck you look down
      into a void and a room, in c, e and i as well as j.

### V.4 — Outdoor dungeons

- [ ] **[MUST] Goes down into the hill** — i's tunnel opens on the top Level;
      the lower rooms are below it, never above. Nothing pokes out of the
      hill's surface or past its foot.
- [ ] **[MUST] The step 5 list still holds** — O.1–O.3 in case i: one
      entrance, the spawn outside, every room reachable.

### V.5 — Maps, controls and sidecar

- [ ] **[MUST] One band per stacked Level** — The Files panel lists the map
      layers the table gives. In the map, each stacked Level draws in its own
      colour, and the rooms on it sit where they are in the 3D view. A Level
      with nothing stacked on it can share a band (g has three Levels and two
      layers).
- [ ] **[MUST] Controls** — Verticality shows for Dungeon, City and Outdoor
      dungeon, and each setting reaches the build (the side panel's plan shows
      it).
- [ ] **[MUST] Sidecar** — A Graph build's `<name>.zone.json` `layout` block
      has `levels` (room id to Level), `stacked_share`, and `connectors` (per
      corridor: `kind` of `flat`, `ramp`, `stair` or `bridge`, `rise`,
      `risers`, `switchback`, and `over` on a bridge).
- [ ] **[MUST] Pinned seed repeats; blank seed is fresh** — As in W.4, for a
      stacked build as for a flat one.
- [ ] **[SHOULD] Snappy** — A multi-level build takes no longer than the Flat
      build of the same controls plus 10 s (14 rooms, seed 8: Flat ~0.3 s,
      Dramatic ~2.4 s).

Known limits (follow-ups in the spec's `archive.md`, not failures here):
room shapes came after this step (step 8), and room contents are step 9; a dragon's stairs are very long, because risers stay about
2 u however big the race; an outdoor dungeon almost always has two Levels even
at Dramatic (of 30 seeds at each size, none reached three at 5 rooms, one at
8, four at 12); giant and dragon outdoor dungeons drop rooms; stacked floors
sit further apart than stock, whose stacking is low rooms over low rooms; and
a shaft over a tall hall, or a short deck, can read as a chimney or a landing
(the user looked at bridges on 2026-11-05 and asked for no change).

### V.6 — In-client check (deferred to M6)

- [ ] **[DEFERRED]** Walking stairs and bridges in the RoF2 client needs a
      takeover install; it moves to M6's in-engine smoke load.

---

## Step 8 — Room walls

> Roadmap step 8 (`zone-generator-room-walls`). A **Graph** room keeps its Box for
> placement and corridors, and draws its real walls inside it, in one of three styles:
> **Rough** is a natural cave (irregular walls, a ceiling that rises and falls, a rolling
> floor, rock on every surface), **Hewn** a man-made cave (a convex room of a few long
> facets, a floor that's still laid, moving ceilings) and **Built** a masonry dungeon
> (mostly plain rectangles, some with cut corners, wings or crosses; flat floors and
> ceilings). Since step 9 each room takes the style of its **finish**, 0-3 Rough, 4-6 Hewn,
> 7-10 Built, so a zone can mix them; step 9's section covers the mixing. Here the
> **Finish** control (step 9 task 21, which replaced Walls) leans every room one way: 9 for
> Built, 5 for Hewn, 1 for Rough. It leans and doesn't pin, so the cases below use seeds
> where every room took the style. Corridors match in the rock styles; stairs and bridges
> stay square. Classic stays rectangles. Restart the Server on the merged code first and
> check the side panel shows no stale-code banner.

### Cases

Pin the seed. **Every case is made from the Controls panel alone**; leave the description
box empty. Layout is Graph (l aside), Size and Locks stay at their defaults, Verticality
is Moderate unless the row names it, Theme and Race stay None, and Rule set, Finish,
Structure, Clutter and Overlay stay From theme or From rules unless the row names them.
Each builds on the first attempt (checked through the server's own route).

| # | Controls | Seed | What it shows (sidecar `layout.rooms`) |
|---|----------|------|-------------------------|
| a | Dungeon, 12 rooms, Rule set **classic_eq**, Finish **9** | 15 | Every room `built`; 6 plain, 4 `cut`, 2 `ell`; mean `fill` 0.95; a bridge (`corr_8`) over `room_9` |
| b | Same, Finish **5** | 15 | Every room `hewn`; 10 `blob`, 1 `long`, 1 `cut`; mean `fill` 0.87 |
| c | Same, Finish **1** | 15 | Every room `rough`; 10 `blob`, 1 `long`, 1 `ell`; mean `fill` 0.75 |
| d | Dungeon, 12 rooms, Theme **Warren** | 4 | 10 `rough`, 2 `hewn`: the theme leans rough |
| e | Dungeon, 12 rooms, Theme **Mine delve** | 4 | 6 `hewn`, 6 `rough`; a bridge (`corr_7`) over `room_7` |
| f | Dungeon, 12 rooms, Theme **Temple** | 1 | 9 `built`, 3 `hewn`; `nave` applied, its hall `long` |
| g | Dungeon, 12 rooms, Theme **Ice keep**, Finish **1** | 9 | Every room `rough`, but its walls stay ice |
| h | Dungeon, 12 rooms, Race **Ogre**, Finish **1** | 8 | `great_hall` applied; every room `rough`; bigger bends for a bigger body; about 14,300 polygons |
| i | Dungeon, 8 rooms, Race **Dragon**, Finish **5** | 8 | `great_hall` applied; every room `hewn`; about 23,500 polygons |
| j | Dungeon, 12 rooms, Rule set **classic_eq**, Finish **1** | 37 | Every room `rough`; two bridges in a cave, `corr_7` over `room_3` and `corr_8` over `room_1` |
| k | Outdoor dungeon, 8 rooms, **Dramatic**, Landscape defaults | 13 | Every room `rough`; two Levels; a bridge (`corr_0`) over `room_6`; the Tunnel opens into a shaped room |
| l | Dungeon, 12 rooms, Layout **Classic** | 10 | No `walls`; all rectangles; about 640 polygons |

Cases a, b and c share a seed on purpose, and have the same rooms, Levels and corridor
routes: Finish moves nothing but each room's style. To see what a style draws without
building a zone:

```bash
python scripts/topology_rules.py draw-walls --out output/rules/
```

### R.1 — The styles

- [ ] **[MUST] Obvious at a glance** — a, b and c look like three different places, not one
      dungeon with different textures.
- [ ] **[MUST] Rough reads as a cave** — c and d's rough rooms have no Box left to see: no long straight
      wall along a room's side, a ceiling that rises and falls, rock underfoot and overhead.
- [ ] **[MUST] Hewn reads as cut** — b and e's hewn rooms are a few long, straight facets:
      laid out by someone, not formed by water.
- [ ] **[MUST] Built reads as masonry** — a and f have square walls and flat floors and
      ceilings, with cut corners and wings among mostly plain rooms.
- [ ] **[MUST] Kinds show** — f's nave is long, and hubs and deep rooms differ from side rooms.
- [ ] **[SHOULD] Themes keep their character** — g's walls are ice, not rock.

### R.2 — Walking them

- [ ] **[MUST] Every room on foot** — In each of a–l, walk from the spawn to every room
      (case k: in through the mouth, as O.3).
- [ ] **[MUST] Nothing shows through** — Look along walls, up at ceilings and across floors:
      no gaps, no seam of void at a wall's foot or head, no see-through at a door.
- [ ] **[MUST] Floors don't trap or slide** — c's rolling floor walks like a floor: no pits,
      no slope that stops you, no step you catch on.
- [ ] **[MUST] Doors** — Each door meets its corridor flush, the floor level across it, with a
      lintel over it; the room opens out from a straight strip inside it.
- [ ] **[SHOULD] Headroom** — Ceilings come down, but never so low you stoop or clip them.

### R.3 — Corridors, stairs and bridges

- [ ] **[MUST] Corridors match** — In c, corridors wander a little and their ceilings move;
      their ends meet the rooms square. In a they stay ruler-straight.
- [ ] **[MUST] Bridges in a cave** — In j, cross both bridges and look up from below, as V.3:
      the shaft is closed, and the room's ceiling doesn't move around the slot.
- [ ] **[MUST] Stairs in a cave** — In c, stairs walk as in V.2. They stay square.
- [ ] **[SHOULD] Sized for the race** — h's and i's bends are bigger than c's and b's.

### R.4 — Maps, controls and sidecar

- [ ] **[MUST] Map draws walls** — The map (M) draws each room's real shape, and it matches
      the 3D view. The EQ map layers bend with the walls.
- [ ] **[MUST] Controls** — Finish shows for Dungeon and Outdoor dungeon under Graph, and hides
      under Classic and for City and Wilderness.
- [ ] **[MUST] Sidecar** — `layout` has `walls`, and each entry in `layout.rooms` has `style`,
      `shape`, `fill` and `outline` (`null` for a plain room).
- [ ] **[MUST] Pinned seed repeats; blank seed is fresh** — As in W.4.
- [ ] **[SHOULD] Snappy** — 14 rooms take about 6 s; 30 Rough rooms about 32 s.

Known limits (follow-ups in the spec's `archive.md`, not failures here): stairs and bridges
stay square in caves; rough rooms read about
13% narrower than their Box, hewn 7%, built 4%; Classic stays rectangles; built zones are
fully flat, a touch flatter than stock; what's inside rooms (pillars, stalactites) is step 9.
Style measures rest on few built stock zones (Befallen, Kurn's Tower, the Qeynos Catacombs).

### R.5 — In-client check (deferred to M6)

- [ ] **[DEFERRED]** Walking shaped rooms in the RoF2 client needs a takeover install; sharp
      concave corners may snag there. It moves to M6's in-engine smoke load.

## Step 9 — Room layouts

> Roadmap step 9 (`zone-generator-room-layouts`). Rooms vary as you walk a zone, by rules,
> not at random. Every **Graph** room draws three **Scales** from 0 to 10: **finish** (raw
> rock to dressed stone, which picks its wall style), **structure** (how much is built
> into it) and **clutter** (how much lies about). The weights come from the default, the
> race, the theme, an **Overlay** (what happened to the place since), the room's kind and
> type and a rule's wing, blended together, and a room leans toward its neighbours, so a
> zone changes slowly and a wing keeps a hard edge. What stands in a room comes from its
> **recipe** (`rules/rooms/layouts.toml`), moved by its Scales: **pillars**, **plinths**,
> **daises** you walk onto, and **boulders** (a stand-in until step 11's placed objects).
> Where two styles meet, the corridor carries a **Transition**: a **Seam** (the look changes
> at one clean line), a **Frame** (two jambs and a lintel in the finer style, recorded as a
> Door_Spot for a door later) or a **Breach** (uneven jambs, nothing overhead). The
> **Finish**, **Structure** and **Clutter** controls (From rules or 0-10) lean every room's
> draw; **Overlay** picks one. Restart the Server on the merged code first and check the
> side panel shows no stale-code banner.

### Cases

Pin the seed. **Every case is made from the Controls panel alone**; leave the description
box empty. Dungeon, Layout Graph, 16 rooms and Verticality Moderate unless the row says
otherwise; Size and Locks at their defaults; Theme and Race None; Rule set, Finish,
Structure, Clutter and Overlay From theme or From rules unless the row names them. Each
builds on the first attempt (checked through the server's own route). Styles are built /
hewn / rough rooms, from `layout.rooms.<id>.style`; Transitions are from `layout.transitions`.

| # | Controls | Seed | What it shows |
|---|----------|------|---------------|
| a | All From rules | 3 | 11 / 3 / 2: mostly built, with a cave wing and a masonry wing; frames on `corr_0`, `corr_6` and `corr_13`, seams on `corr_1` and `corr_11`; 4 daises, 2 pillars, 2 boulders |
| b | Race **Ogre** | 4 | 1 / 5 / 10; a breach on `corr_10`, a seam on `corr_12`; 9 pillars, 4 plinths, 2 boulders |
| c | Race **Goblin** | 4 | 2 / 6 / 8: b's rooms, kept a little finer |
| d | Theme **Temple** | 1 | 12 / 4 / 0; `nave` applied; 14 pillars, 6 plinths, 5 daises; no boulders |
| e | Theme **Mine delve** | 5 | 1 / 5 / 10; 28 boulders, mostly in collapsed galleries |
| f | Race **Ogre**, Overlay **Reclaimed** | 4 | b's rooms and styles with the mess gone: no boulders, a few more pillars |
| g | Overlay **Ruined** | 4 | 0 / 1 / 15; 25 boulders |
| h | Finish **1** | 7 | 7 / 0 / 9: rough, but a masonry wing stays built (a wing's edge is hard) |
| i | Finish **9** | 7 | 16 / 0 / 0, on h's rooms |
| j | Structure **1** | 7 | h's rooms, near bare: 4 pillars |
| k | Structure **9** | 7 | 8 pillars, 5 daises, 2 plinths |
| l | Clutter **1** | 7 | No boulders |
| m | Clutter **9** | 7 | 22 boulders |
| n | Theme **Fortress** | 1 | A throne (`room_12`: a dais, a plinth and pillars) and a barracks (`room_9`) |
| o | Theme **Corrupted sanctum** | 1 | An inner sanctum (`room_12`) ringed with pillars round a plinth; 5 / 6 / 5 |
| p | Theme **Warren** | 1 | 0 / 0 / 16: one cave throughout, so no Transitions; 12 boulders |
| q | All From rules | 10 | Every form: a breach on `corr_1`, frames on `corr_2` and `corr_11`, a seam on `corr_16` |
| r | Race **Giant**, 10 rooms | 6 | Frames on `corr_1`, `corr_3` and `corr_5` at giant size; about 23,200 polygons |
| s | 12 rooms, Rule set **classic_eq**, **Dramatic** | 4 | Two Levels; a bridge (`corr_7`) over `room_7`; a breach and a frame |
| t | Outdoor dungeon, 8 rooms, Landscape defaults | 2 | 1 / 0 / 7; a seam |

b, c and f share a seed and so the same rooms, as do h to m: compare them side by side.
What a room stands is in `layout.rooms.<id>.features`, what didn't fit in `dropped`, and its
Scales in `scales`.

### L.1 — Rooms that vary

- [ ] **[MUST] Not random** — In a and q, the zone changes as you walk it, and neighbours
      mostly agree: a run of caves, then a run of masonry, not a coin toss per room.
- [ ] **[MUST] Races and themes show** — b's ogre rooms read rougher and fuller than d's temple;
      e and g are strewn with rock, and d is swept clean.
- [ ] **[MUST] Overlays show** — f is b tidied: the same rooms, no boulders.
- [ ] **[SHOULD] Wings hold** — In a and h, a masonry wing stays built among caves, and a cave
      wing stays rough among masonry.

### L.2 — The controls lean

- [ ] **[MUST] Each Scale each way** — h is rougher than i, j barer than k, and l clearer than
      m, all on the same rooms.
- [ ] **[MUST] A lean, not a pin** — h keeps its masonry wing; no case is one value everywhere.
- [ ] **[MUST] From rules is as before** — Finish, Structure and Clutter all From rules give a.

### L.3 — What stands in rooms

- [ ] **[MUST] Named rooms read as themselves** — n's throne has its dais and seat; o's sanctum
      is ringed; d's temple has rows of pillars; p's caves have rock lying about.
- [ ] **[MUST] The way through stays clear** — Walk door to door in every room of a, b, d and m:
      nothing stands in a doorway or blocks the path, and daises walk on and off.
- [ ] **[MUST] Pieces suit the room** — A rough room's pillars and boulders are rough; a built
      room's are square.
- [ ] **[SHOULD] Not too full or too empty** — Most rooms of a hold little or nothing; a few
      hold a lot.

### L.4 — Transitions

- [ ] **[MUST] Every form** — In q, walk `corr_1` (breach), `corr_2` (frame) and `corr_16`
      (seam): each looks meant, the floor stays flush across it, and nothing shows through.
- [ ] **[MUST] A frame fits** — The frames in q and r leave room to walk through at the race's
      size, with headroom under the lintel.
- [ ] **[MUST] Door_Spots** — Each frame shows as a bar on the map (M), and has a `door_spot` in
      its `layout.transitions` entry.
- [ ] **[SHOULD] Stairs and bridges** — In s, the bridge and stairs stay square; their change of
      style stands at a door.

### L.5 — Maps, controls and sidecar

- [ ] **[MUST] Controls** — Finish, Structure, Clutter and Overlay show for Dungeon and Outdoor
      dungeon under Graph, and hide under Classic and for City and Wilderness.
- [ ] **[MUST] Map** — The map draws each room's Features and the Door_Spot bars.
- [ ] **[MUST] Sidecar** — Each `layout.rooms` entry has `scales`, `style`, `room_layout`,
      `features` and `dropped`; `layout.transitions` has every corridor's form.
- [ ] **[MUST] Pinned seed repeats; blank seed is fresh** — As in W.4.

Known limits (not failures here): Features are meshes standing in for placed objects, so
boulders read as shortened pillars, and furniture (benches, braziers, bookcases) is step
11's. Rerolling a room's contents without moving the layout isn't a control yet. A
control's number leans the rooms and doesn't pin them: a wing's written edge wins.

### L.6 — In-client check (deferred to M6)

- [ ] **[DEFERRED]** Walking Features and Transitions in the RoF2 client needs a takeover
      install. It moves to M6's in-engine smoke load.

## Step 10 — Wilderness POIs

> Roadmap step 10 (`zone-generator-wilderness-pois`). Wilderness and outdoor-dungeon
> landscapes now hold **Sites**: a **camp** (a fire ring and tents, or lean-tos), a **hut**,
> a **farmstead** (hut, barn and a corral), a **watchtower**, a **shrine** (a monument,
> sometimes ringed by standing stones) and a **ruin** (broken walls round a court). Each is
> built from **Structures**, generated models placed as ZON objects like trees. Who built a
> Site, its **Inhabitant** (human, orc, gnoll, centaur), weights its kind and sets its
> material set and variants (an orc tent is hide, a centaur builds lean-tos). Huts, lean-tos
> and ruins are walked into through an opening at least 8 u wide and 8 u high; towers are
> solid. Each Site names its POIs (camp fire, hut interior, lookout ...) in the sidecar only.
> The **Sites** (None, Sparse, Normal, Dense) and **Inhabitants** (biome's mix, or one)
> selects sit beside Trees in the Wilderness box, for Wilderness and Outdoor dungeon. Restart
> the Server on the merged code first and check the side panel shows no stale-code banner.

### Cases

Pin the seed. Leave the description box empty unless the row is a prompt. Wilderness with
the default edges (all mountain), Trees normal and Rooms 5; Sites Normal and Inhabitants
biome's mix unless the row names them. Each builds on the first attempt (checked through
`main.py`'s path). A Site reads `<Inhabitant> <kind>`, its Structures from
`sites.sites[].structures`; a model file is `site_<structure>_<variant>_<material set>.mod`.

| # | Controls | Seed | What it shows |
|---|----------|------|---------------|
| a | Defaults | 7 | Gnoll camp: a fire ring and 4 hide tents facing it; a centaur shrine (a lone burial mound) |
| b | Defaults | 19 | One human hut (timber) with a rail fence run: walk in |
| c | Defaults | 9 | Human farmstead: hut, barn, and a corral of 4 rail fences on its open side |
| d | Defaults | 1 | Gnoll watchtower (one stone tower); a human ruin (one wall) |
| e | Defaults | 5 | Human shrine: an obelisk ringed by 3 standing stones; a human hut |
| f | Defaults | 13 | Human ruin of 3 walls round a court; a farmstead; a gnoll wattle hut and stake fence |
| g | Defaults | 18 | Centaur camp: a fire ring and 2 hide lean-tos (walk in); a human hut |
| h | Inhabitants **human** | 7 | A farmstead (hut and 4 fences; its barn dropped, "in its Site_Clear") and a hut; `timber_thatch` |
| i | Inhabitants **orc** | 7 | Two orc camps (4 and 3 tents), `site_tent_hide_hide.mod` |
| j | Inhabitants **gnoll** | 7 | i's two camps in `crude_timber` |
| k | Inhabitants **centaur** | 7 | i's two camps with lean-tos for tents (`hide_canvas`), each walked into |
| l | Sites **None** | 1955208177 | No Sites, `models` empty; step 9's bytes (below) |
| m | Sites **Sparse** | 1955208177 | One human farmstead (hut, barn, 3 fences) |
| n | Sites **Normal** | 1955208177 | m, and a human ruin of 3 walls |
| o | Sites **Dense** | 1955208177 | n, and a gnoll wattle hut |
| p | Outdoor dungeon, Sites **Dense** | 1 | Gnoll watchtower pair: two stone towers |
| q | Outdoor dungeon, Sites **Dense** | 4 | Human ruin of 3 walls |
| r | Outdoor dungeon, Sites **Dense** | 6 | Human watchtower, one timber tower |
| s | Outdoor dungeon, Sites **Dense** | 2 | None: the shrine drops, "no eligible ground" (a known limit) |
| t | Prompt `orc camp on the plains` | 7 | i, with `control_source` `prompt` |
| u | Prompt `empty wilderness` | 7 | Sites none, `control_source` `prompt` |

a, h, i, j and k share a seed: compare who builds. l to o share a seed and ground: each step
keeps the last one's Sites and adds one. From the command line:

```bash
python main.py generate sites_a --zone-type wilderness --seed 7
python main.py generate sites_i --zone-type wilderness --seed 7 --inhabitant orc
python main.py generate b1955208177 --zone-type wilderness --seed 1955208177 --sites none
python main.py generate sites_p --zone-type outdoor_dungeon --seed 1 --sites dense
```

The name `b1955208177` in l matters: built so, its `.eqg` less the 4-byte footer has
sha256 `8aaf8daf…`, the step 9 build `tests/test_site_builds.py` pins. A build from the page
has another name and so other bytes; on the page, check l has no Structures and its trees and
ground look like step 9's.

**Since step 13 (point Site Sockets)** these cases build other Sites: a Site now stands on one
of the World's points, in Groups the way stock hamlets sit, so the kind drawn and where it
lands both move. The ground, trees and water are the same; only l (Sites None) is unchanged.
Rebuilt on step 13's code, each on its first attempt:

| # | Now |
|---|-----|
| a | A human camp (3 canvas tents) and a gnoll camp (4 hide tents) side by side, Group 0 |
| b | One human hut with a rail fence (as before) |
| c | A human farmstead (hut and 3 fences; its barn still drops "in its Site_Clear") |
| d | Two human huts, far apart |
| e | A gnoll shrine (lone monument) and a human hut |
| f | A human shrine ringed by 3 standing stones beside a gnoll shrine, and a human hut |
| g | A gnoll shrine ringed by 4 stones, and an orc camp of 2 tents |
| h | Two human huts together |
| i | An orc ruin (4 walls and a stone) beside an orc lashed watchtower |
| j | Two gnoll wattle huts together |
| k | A centaur ruin beside a centaur burial mound |
| m | A centaur camp of 3 hide lean-tos |
| n | m, and an orc shrine |
| o | n, and a human shrine (still each step keeps the last one's Sites and adds one) |
| p | A human shrine |
| q | A human camp |
| r | A centaur ruin (3 walls, 2 stones) |
| s | A human shrine: s no longer drops its Site |
| t | i's orc ruin and watchtower, `control_source` `prompt` |

P.1's "each kind" now needs these: camp a, hut b, farmstead c, watchtower i, shrine f, ruin i
or k. The step 13 section's cases show the Groups.

### P.1 — Sites read as what they are

- [ ] **[MUST] Each kind** — a's camp, b's hut, c's farmstead, d's tower, e's shrine and f's
      ruin each read as that place, and look Classic-era next to the trees.
- [ ] **[MUST] Inhabitants differ** — h to k on one seed: h builds farms in timber and thatch,
      i and j camps in hide and crude timber, k lean-tos; the four look apart.
- [ ] **[MUST] Where a builder would** — Every Site stands on flat ground, off the Rim and
      out of water, clear of Spawn and zonelines; nothing floats or sinks to its roof.
- [ ] **[SHOULD] Not too many, not too few** — l to o step none, one, two, three; Normal reads
      as a Karana with a few places, not a town.

### P.2 — The way stays open

- [ ] **[MUST] Walk in** — In b walk into the hut, in g and k into a lean-to, in f into the
      ruin's court: the opening takes you without a snag (8 u wide, 8 u high) and the floor is
      the ground.
- [ ] **[MUST] Never in the way** — In a, c and o, walk round every Site: no fence, tent or
      wall shuts off ground, and trees keep out of each Site's ground.
- [ ] **[MUST] Outdoor dungeons hold** — In p, q and r the Site keeps off the Host_Hill, the
      Tunnel and the Mouth; the dungeon walk is as in step 5.

### P.3 — Maps, controls and sidecar

- [ ] **[MUST] Controls** — Sites and Inhabitants show beside Trees for Wilderness and Outdoor
      dungeon, and hide for Dungeon and City.
- [ ] **[MUST] Maps** — The map (M) and `<name>.map.svg` draw each Structure's Footprint and a
      marker and label (`Gnoll camp`) at each Site; `maps/<name>.txt` has a sienna loop per
      Footprint and a `P` label (`Gnoll_camp`) per Site.
- [ ] **[MUST] Sidecar** — `<name>.zone.json` has a `sites` block: `control`,
      `control_source`, `inhabitant`, `target`, `band`, `models`, `drops`, and per Site its
      `kind`, `inhabitant`, centre, `structures` (kind, variant, yaw, `enterable`) and `pois`.
- [ ] **[MUST] Prompt words** — t builds orc camps; u builds none.
- [ ] **[MUST] Pinned seed repeats; blank seed is fresh** — As in W.4.

Known limits (not failures here): outdoor dungeons get Sites on only some seeds (s; archive
decision 11). Sites spread at random where stock plains cluster. A farmstead often loses its
barn to its own Site_Clear (h). Sites are bare: furniture and loose props are step 11's.

### P.4 — In-client check (deferred to M6)

- [ ] **[DEFERRED]** Walking into huts and lean-tos and round Sites in the RoF2 client needs a
      takeover install. It moves to M6's in-engine smoke load.

## Step 11 — Decorating rooms

> Roadmap step 11 (`zone-generator-room-decor`). Rooms and Sites now hold **Props**: the
> client's own models (furniture, lights, crates, banners, rock and bone), catalogued from the
> install's `_obj*.s3d` archives and copied into the build unchanged. A room's **recipe**
> (`rules/decor/rooms.toml`: its room type, else its kind, else the zone type, else the
> default) says what it takes. Its race, theme or zone type picks a **Set**, which is whose
> models it uses. A Prop is mounted on the **floor**, on a **wall**, on the **ceiling** or
> **raised** on another Prop (a candle on a table, a crate on a crate). Each light-bearing
> Prop adds a ZON point light. The **Decor** control (None, Sparse, Normal, Dense) sets how
> much is placed. The **Decor seed** rerolls the Props alone: the zone and its layout stay
> the same. The **⟳ reroll decor** button beside Decor in the side panel does the same with
> a fresh decor seed. Decor needs the EQ install on the Server (`EQ_PATH`); without it a build
> has no Props and warns `NO_INSTALL`. Restart the Server on the merged code first and check
> the side panel shows no stale-code banner.

### Cases

Pin the seed. **Every case is made from the Controls panel alone**; leave the description
box empty. Dungeon, Layout Graph, 16 rooms, and Size, Verticality and Locks at their defaults,
unless the row says otherwise. City has 12 rooms, Outdoor dungeon has the Rooms its row names,
and Wilderness has Rooms 5 with the Step 10 defaults (Trees, Sites Normal, Inhabitants biome's
mix). Theme and Race are None, Decor is Normal and Decor seed is blank (the zone's seed)
unless the row names them. Each was built on this code through the Server's own route
(`POST /api/generate`) and built on the first attempt with the gate passing. Counts are from
the sidecar's top-level `decor` block (`props`, `lights`, `models`). A room's Props are in
`rooms[].props` (`key`, `kind`, `mount`, `set`) and a Site's in `sites.sites[].props`; a
room's type is `layout.rooms.<id>.room_layout`.

| # | Controls | Seed | Decor seed | Decor | What it shows |
|---|----------|------|------------|-------|---------------|
| a | Defaults | 2 | blank (2) | **Dense** | 135 Props, 45 lights, 43 models. MISTBANNER ×4 on `room_13`'s walls, GENTAPESTRY602 ×2 in `room_12`. Nine torch models, among them WALLTORCH200, WALLTORCHARMSTUB200, CDTORCH101, VETORCH101, POTORCHAINS504T and TORCHPOINT. Stacked crates: in `room_2` HPCRATES401@abysmal and CRATEG sit on crates; in `room_9` CRATEK and CRATEG do. A table set in `room_6`. `room_14` is bare |
| b | Defaults | 2 | blank | **None** | No Props, and no `decor` block in the sidecar. The rooms and walls are a's |
| c | Defaults | 2 | blank (2) | **Sparse** | 44 Props, 22 lights. One MISTBANNER |
| d | Defaults | 2 | blank (2) | Normal | 72 Props, 36 lights. MISTBANNER ×2 (`room_13`), GENTAPESTRY602 (`room_12`), NTHRONE with two braziers in the deep room (`room_5`). Leaving Decor at its default gives these same Props |
| e | Defaults | 2 | **1000** | Normal | **Reroll:** d's zone (the sidecar `layout` is identical) with other Props: 66 Props, 32 lights, 4 bare rooms. `room_12` now holds TAKBANNER701 ×2, `room_5` an HHTHRONE, and `room_0` braziers and torches |
| f | Defaults | 2 | **2** | Normal | Same Props as d: a decor seed equal to the zone's is the default |
| g | Theme **Fortress** | 2 | blank (2) | Normal | **Room types:** throne `room_5` (NTHRONE, FLAG2 ×2, braziers, HUMRUG1). Barracks `room_2` (GOTHBED303 and 3 BED2) and `room_6` (rows of beds). Armory `room_4` (3 HHRACK and 4 VSWRACKS302 in rows) and `room_15` (6 MISTSKRACK702). Battle arena `room_13` (SCAFLAG800 ×3). Storeroom `room_14` is bare. 100 Props |
| h | Race **Ogre** | 1 | blank (1) | Normal | 108 Props, 14 in the `ogre` Set. QRGFLAG ×4, GENTAPESTRY602 ×4. Crates stacked in `room_6` and `room_12` |
| i | Race **Goblin** | 1 | blank (1) | Normal | 127 Props, 33 `goblin`. Every torch is the goblins' PERTORCH1 (32) |
| j | Race **Gnoll** | 1 | blank (1) | Normal | 118 Props, 24 `gnoll`. 12 banners and 38 crates, stacked in five rooms |
| k | Theme **Tomb** | 1 | blank (1) | Normal | 109 Props, 12 `undead`. Dark: 16 lights. Rock, bones, bone piles, webs and urns; no banners or furniture. Ossuary, vault and ritual chamber rooms |
| l | Theme **Wizard lair** | 2 | blank (2) | Normal | 112 Props, 32 `erudite`. Bookcases, desks, and books raised on desks (SHBOOK301 in `room_9` and `room_11`). PAFLAG104 |
| m | **City**, 12 rooms | 1 | blank (1) | Normal | 89 Props, 30 lights. Barrels, bookcases, MISTLAMP lamps, plants and braziers; 4 in the `human` Set. `room_10` is the fullest (15); `room_3` is bare |
| n | **Outdoor dungeon**, 8 rooms | 2 | blank (2) | Normal | 34 Props, 11 lights; NTHRONE in the deep room. Lighter than a dungeon, by the outdoor-dungeon weights |
| o | **Outdoor dungeon**, 5 rooms | 4 | blank (4) | Normal | TAKBANNER701 ×2 behind the throne (ACBTHRONE301) in `room_4`. The human ruin Site holds two chests (GOTHCHEST301). **Known issue:** a banner here sits about 2.4 u into the wall |
| p | **Outdoor dungeon**, 5 rooms | 3 | blank (3) | Normal | A table and 3 chairs with a candle on the table in `room_2`. **Known issue:** its MIRTORCH701 sits about 2.1 u into the wall |
| q | **Wilderness** | 7 | blank (7) | Normal | **Sites:** the gnoll camp has BARSTOOL1, CRATEG ×2 and FURSTACK2; the centaur shrine has CANDLE ×2 and MISTFURN703. 7 Props, 2 lights |
| r | **Wilderness** | 9 | blank (9) | Normal | Human farmstead yard: a WAGON, BARREL4 ×3, an MBENCH301 and a fishing pole (POPFISHPOLE500) |
| s | **Wilderness** | 7 | blank | **None** | q's Sites (same Structures), no Props |
| t | **Wilderness** | 7 | blank (7) | **Sparse** | The shrine has CANDLE ×2 and SCULL; the camp has BARSTOOL1, HPCRATES402 ×2 and BONES. 7 Props: on two small Sites Sparse places as many as Normal, only other models |
| u | **Wilderness** | 7 | blank (7) | **Dense** | 10 Props: the camp adds BONES3 ×2, the shrine a second MISTFURN703 |

a to f share a zone: b, c, d and a step the Decor control on the same rooms, and d, e and f
show the decor seed. s, t, q and u do the same for Sites. Compare them side by side. From the
command line (theme and race are page-only, so g to l need the page):

```bash
python main.py generate decor_a --seed 2 --rooms 16 --decor dense
python main.py generate decor_e --seed 2 --rooms 16 --decor-seed 1000
python main.py generate decor_m --zone-type city --seed 1 --rooms 12
python main.py generate decor_o --zone-type outdoor_dungeon --seed 4 --rooms 5
python main.py generate decor_q --zone-type wilderness --seed 7
```

These give the same Props as the page (checked for a, e and q). Task 22 (lights as a set) moved
the counts of a to g, m and n; h to l weren't rebuilt through the page after it, so their counts
may be a few Props off. The `.eqg` files contain the
client's own models and textures, so they are for your own client and server: don't commit or
share them.

**Since step 13 (point Site Sockets)** the Site cases build other Sites (see step 10's note):
q, s, t and u (wilderness 7) hold a human camp and a gnoll camp side by side, not the gnoll
camp and centaur shrine; o (outdoor dungeon 4) holds a human camp of 3 tents, not the ruin
with chests. n and p (outdoor dungeons 2 and 3) now also have a Site: a human shrine and a
human ruin of 4 walls. r's farmstead is unchanged. The rooms and their Props are untouched.

### D.1 — The Props look placed

- [ ] **[MUST] Banners show and hang flat** — In a, walk `room_13` and `room_12`. Each
      MISTBANNER and tapestry can be seen (not invisible or a black sheet), hangs flat against
      the wall, faces into the room, and is not sunk into the wall or floating off it. The same
      goes for g's FLAG2 and SCAFLAG800 and h's QRGFLAG.
- [ ] **[MUST] Torches on the wall** — In a, d and g, every wall torch has its back flush to
      the wall at about head height, with its flame on the room side. No torch stands free in
      the air or is buried in the stone. Several torch models show, not one model everywhere
      (i is the exception: a goblin zone uses goblin torches).
- [ ] **[MUST] Standing on the floor** — Tables, chairs, chests, beds, racks, rock and bones
      rest on the floor. None floats or is sunk to its knees, including on uneven rough floors
      (k).
- [ ] **[MUST] Stacks sit on what's below** — In a's `room_2` and `room_9`, and in h and j, a
      stacked crate sits on the top of the crate below. Candles and books (a `room_6`, l) sit on
      their table or desk.
- [ ] **[MUST] Nothing below the world** — From outside or below each zone (fly out), no Prop
      hangs under the floor or outside the walls.
- [ ] **[SHOULD] Lights match** — With Lights on, the lit torches and braziers glow where they
      stand, and tomb (k) reads darker than a or g.

### D.2 — Rooms read as what they are

- [ ] **[MUST] Room types** — g's throne has its seat, flags and rug, its barracks have beds,
      its armories have weapon racks, and its storeroom is empty or holds crates.
- [ ] **[MUST] Races and themes differ** — Goblin (i), gnoll (j), ogre (h), tomb (k) and wizard
      lair (l) each use their own models where they have them, and the five look apart. A room
      keeps to one culture.
- [ ] **[MUST] Cities** — m reads as a lived-in town: barrels, shelves, lamps and plants, lit,
      not a dungeon's bones and rubble.
- [ ] **[MUST] Outdoor dungeons** — n, o and p are furnished like a smaller dungeon, and o's
      ruin Site holds its chests on the ground.
- [ ] **[SHOULD] Not too full or too empty** — In d, most rooms hold a few things and a couple
      hold a lot, and one may be bare. It reads like a Classic-era dungeon, not a warehouse.

### D.3 — Sites look natural

- [ ] **[MUST] Camp Props** — In q and u, the camp's stool, crates and furs stand on the ground
      near the fire and tents, upright on slopes, not inside a tent wall and not on the path
      through. The shrine's candles stand by the monument.
- [ ] **[MUST] Farm Props** — In r, the wagon, barrels and bench stand in the farmstead's yard,
      clear of the hut's opening and the fences.
- [ ] **[MUST] None leaves Sites alone** — s has q's Sites unchanged and nothing at them.

### D.4 — The way stays open

- [ ] **[MUST] Rows leave gaps** — In g, walk between the rows of racks in `room_4` and
      `room_15` and between the beds in `room_2` and `room_6`. Where a row stands, there is a
      gap to walk through or round it, and no row walls off part of the room.
- [ ] **[MUST] Door to door** — In a (Dense) and m, walk every room from door to door. No Prop
      stands in a doorway or blocks the path, and you don't snag on rubble.
- [ ] **[MUST] Gate held** — Every case built on the first attempt with the gate passing
      (`validated` in the side panel).

### D.5 — Controls, reroll and sidecar

- [ ] **[MUST] Decor steps** — b, c, d and a on one zone go none, few, more, most (0, 44, 72
      and 135 Props). The rooms and walls don't change between them.
- [ ] **[MUST] Reroll keeps the zone** — e is d's zone with other Props. Then press
      **⟳ reroll decor** on d: the rooms, walls and corridors stay where they were and only the
      Props change. The Decor row reads `normal · seed <the new decor seed>`.
- [ ] **[MUST] Controls** — Decor and Decor seed show for Dungeon, City, Outdoor dungeon and
      Wilderness. The Decor list is None, Sparse, Normal, Dense, with Normal selected.
- [ ] **[MUST] Maps** — The map (M) draws each Prop over a traced outline (dots for wall,
      raised and ceiling Props), and `maps/<name>.txt` has a purple loop for each floor Prop's
      footprint.
- [ ] **[MUST] Sidecar** — `<name>.zone.json` has a top-level `decor` block (`control`,
      `seed`, `props`, `lights`, `models`, `rooms`, `bare`, `drops`, `check`), and each room and
      Site has `props`, `dressing` and `decor_drops`. `check` is empty.
- [ ] **[MUST] Pinned seed repeats** — The same seed and decor seed give the same Props.

Known issues (not regressions; open follow-ups in the spec's `archive.md`):

- Some wall Props still sit into the wall on outdoor dungeons: in p (seed 3) MIRTORCH701 by
  about 2.1 u, and in o (seed 4) a banner by about 2.4 u. This was already so before task 14.
- GENMETCRATE700 builds at twice its stock size because of the scale limit.
- Floor models placed along a wall still assume their front is +X, so a bench or rack can
  face the wall side-on.
- Wall Props at inside corners aren't checked for poking sideways into the next wall.
- The `.eqg` rotation direction hasn't been checked in the client.
- City seed 53 falls under the per-room hard edge, at 1.67 Props a room. City raised, plant
  and furniture Props sit near the tops of their bands.
- Corridors get no lights yet, because no corridor contexts are built.
- The page's tooltip still says Decor is "in the rooms", though Sites take it too.
- Doorway gates aren't placed as doors, and pieces stock always places together aren't
  placed whole.
- Rerolling step 9's Structure and Clutter Features without moving the layout is still open:
  the decor seed covers Props only.
- The thorough suite at this step (task 15): 2371 passed, 1 failed. The failure is
  `tests/test_properties_mapgeom.py::test_reachable_only`, where an outline polyline differs
  between the reachable and all-floor outlines on a synthetic world. It replays the same at
  `3ae15d5^`, the code before step 11; the outline code is unchanged here. It belongs with
  step 10's open failures: three dungeon and outline tests under the thorough profile and
  the mapgeom face-order bug. Those three passed in this run; they fail on some draws only.

### D.6 — Lights as a set, once a room (task 22)

- [ ] **[MUST] One height** — A room's wall torches hang at one height. In a, `room_12`'s three
      VETORCH101 are level (before, they ran from −190.0 to −186.8), and so are `room_3`'s
      POTORCHAINS504T. In d, `room_10`'s three DROVTORCH200 are level. On a raised part of a
      floor a torch may sit higher, but only by that floor's step, never a little off.
- [ ] **[MUST] Opposite or evenly spaced** — In d, `room_0`, `room_5`, `room_6` and `room_9`
      have their two lights on directly opposite walls. `room_2`, `room_10` and `room_13` have an
      opposite pair plus one in the middle of the end wall. `room_11` and `room_12` have two on
      one wall, evenly spaced. No room has its lights bunched on one side.
- [ ] **[MUST] Corners** — Floor lights at corners stand in opposite corners or in all four:
      k's candles in `room_2` and candelabras in `room_5`, and m's MISTLAMP pairs in `room_6` and
      `room_7`.
- [ ] **[MUST] Once a room** — In l, each room with a desk has one (`room_2`, `room_6`,
      `room_9`, `room_11`). Forges, anvils, fires, carts and boxes are also placed at most once
      a room (`once` in `rules/decor/rooms.toml`).
- [ ] **[SHOULD] Still lit** — The rooms in a, d and g aren't darker than before: a set that
      doesn't fit drops to a smaller set, not to none.

### D.7 — In-client check (deferred to M6)

- [ ] **[DEFERRED]** Seeing the Props, their lights and their collision in the RoF2 client
      needs a takeover install. It moves to M6's in-engine smoke load.

---

## Step 12 — World Sockets

> Roadmap step 12 (`zone-generator-world-sockets`). A zone is now made in stages: the
> **World** (the terrain, from the zone's seed) offers **Sockets**, the rooms and Sites
> **attach** to them, then **Decor** places the Props. An outdoor dungeon has a `hillside`
> Socket (`hill0`, the hill its Tunnel goes into) and a `ground` Socket (the open ground its
> Sites stand on); a wilderness has one `ground` Socket; a dungeon or city has one `root`
> Socket at the origin. Each stage has its own seed: **seed** (the World), **Rooms seed**
> (the rooms and the Sites) and **Decor seed** (the Props), the last two defaulting to the
> first. The side panel's **Seeds** section shows the rooms and decor seeds with
> **reroll rooms** and **reroll decor** buttons; the Controls panel has a **Rooms seed** box
> (every zone type). Corridors now take wall lights too. A build writes its stage hand-offs
> (`<name>.world.json`, `.attach.json`, `.rooms.json`) into its build folder, and
> `scripts/stage.py` reruns one stage from the one before. Restart the Server on the merged
> code first and check the side panel shows no stale-code banner.

### Cases

Pin the seed. Leave the description box empty and set only what the row names: Layout,
Size, Verticality, Locks, Decor (Normal) and the other controls stay at their defaults, and
**Rooms is the page's default 5** unless the row says otherwise. Every case was built on this
code through the Server's own route (`POST /api/generate`) on its first attempt with the gate
passing. Sockets are the sidecar's `sockets` block, the seeds its `seeds` block, the Spawn
`outdoor_dungeon.outdoor_spawn`, and a corridor's Props `corridors[].props` (`from_room`,
`to_room`).

| # | Controls | Seed | Rooms seed | What it shows |
|---|----------|------|------------|---------------|
| a | **Outdoor dungeon**, 8 rooms | 2 | blank (2) | Hill `hill0` on the **W** side; the Tunnel's Mouth at (−140, 0), Spawn at (−340, 140, 13.0). Rooms on two levels (room_0, 1, 3 and 4 at Z 35, room_6 at 21; room_2, 5 and 7 at Z −67 to −81). Two lit corridors: NIHTORCH804 between room_1 and room_4, TORCH1 between room_1 and room_3. 33 Props |
| b | **Outdoor dungeon**, 8 rooms | 2 | **12345** | **Rooms reroll:** a's hill, ground and terrain textures, the same trees (16, the same kinds), and the same Spawn (−340, 140, 13.0). The rooms are laid out and dressed anew (room_0, 1, 2 and 5 at Z 22, room_4 at 36, room_3, 6 and 7 at −80 to −88; flagstone floors become cave rock) and the Mouth moves along the same hill to (−180, −40). No lit corridors this time; 35 Props |
| c | **Wilderness** | 7 | blank (7) | Two Sites: a centaur shrine at (−910, 1056) and a gnoll camp at (488, 316). Step 11's case q |
| d | **Wilderness** | 7 | **12345** | **Rooms reroll:** c's ground and water, and its 100 trees. The Sites are new: the centaur shrine now at (1097, −615), and a human shrine at (659, −613) in place of the gnoll camp |
| e | Dungeon, Layout Graph, **16 rooms** | 2 | blank (2) | **Step 11's zone, unchanged:** step 11's case d. The same rooms, walls and corridors; NTHRONE in `room_5`, GENTAPESTRY602 in `room_12`, MISTBANNER ×2 in `room_13`. 70 Props, 32 lights (was 72 and 36): corridors now carry lights (TORCH1 between room_9 and room_6 and between room_11 and room_13, NIHTORCH801 between room_5 and room_3), and rooms carry one wall light fewer at most |
| f | Dungeon, Layout Graph, 16 rooms, Decor **None** | 2 | blank | e's rooms, walls and corridors with no Props. Should match a step 11 build of this exactly |
| g | **City**, 12 rooms | 1 | blank (1) | **Step 11's zone, unchanged:** step 11's case m, the same streets and buildings. 103 Props, 45 lights (was 89 and 30): three lit corridors, two torches each (TORCH1 room_0–room_5, TORCHPOINT room_5–room_10, SLTORCH101 room_1–room_5) |
| h | Dungeon | 34 | blank | **Corridor torches:** NIHTORCH804 in the corridors room_1–room_0 and room_1–room_3, POTORCHAINS504T in the high corridor room_4–room_2 (Z about 110) |
| i | Dungeon | 5 | blank | **Corridor torches:** NIHTORCH802 room_2–room_4, TORCHPOINT room_2–room_1, NIHTORCH804 room_1–room_3 |
| j | **City** | 15 | blank | **Corridor torches in a row:** TORCHPOINT ×3 along room_1–room_4, NIHTORCH801 ×4 along room_1–room_2, one NIHTORCH801 in room_0–room_4 |
| k | **City** | 18 | blank | NIHTORCH802 ×3 along room_2–room_3, NIHTORCH804 ×4 along room_1–room_2 |
| l | **City** | 30 | blank | Three lit streets: NIHTORCH801 ×2 room_1–room_4, TORCH1 ×3 room_3–room_4, NIHTORCH801 ×2 room_0–room_4 |
| m | **Outdoor dungeon** | 18 | blank | **Spawn moved most** (task 20): Spawn (−340, 140) now at Z −8.34 (was −7.50). Hill W |
| n | **Outdoor dungeon** | 25 | blank | Spawn (140, −340) at Z 24.20 (was 23.76). Hill **S**. One lit corridor: WALLTORCHARMSTUB200 room_1–room_3 |
| o | **Outdoor dungeon** | 26 | blank | Spawn (−340, 140) at Z 26.92 (was 27.25). Hill W |
| p | **Outdoor dungeon** | 3 | blank | Spawn (−340, 140) at Z −5.01 (was −4.71). Hill W; the Mouth at (−100, −40) |
| q | **Outdoor dungeon**, 8 rooms, Theme **Fortress**, Race **Troll**, Verticality **Flat** | 3 | blank | **The Apron under the Spawn:** the troll's tall Tunnel digs its Apron trench right under the Spawn: Spawn (−340, 140) at Z −36.11, about 31 u below p's ground there. The Mouth is at (−300, 120). Four lit corridors |

a and b, and c and d, are the reroll pairs: open them side by side, or build a (or c) and press
**reroll rooms**. The ⟳ button gives a fresh rooms seed, so its rooms differ from b's; the World
stays a's either way. From the command line (Theme and Race are page-only, so q needs the
page):

```bash
python main.py generate sockets_a --zone-type outdoor_dungeon --seed 2 --rooms 8
python main.py generate sockets_b --zone-type outdoor_dungeon --seed 2 --rooms 8 --rooms-seed 12345
python main.py generate sockets_d --zone-type wilderness --seed 7 --rooms-seed 12345
python main.py generate sockets_e --seed 2 --rooms 16 --layout graph
python main.py generate sockets_j --zone-type city --seed 15 --rooms 5
```

These give the same rooms, Sites, Sockets and Props as the page (checked for b, d, e and j).
The `.eqg` files contain the client's own models and textures (Decor): don't commit or share
them.

**Since step 13 (point Site Sockets)** every outdoor dungeon case has a Site, and the
wilderness pair moved: a has a human shrine at (341, 120) and b an orc shrine on the same point;
c has a human camp at (738, −873) and a gnoll camp at (868, −927); d a human hut and a human
shrine at (868, −927) and (1002, −839). m has a human hut, n a gnoll ruin, o and p human ruins.
The hover text on the `ground` diamond now says `sites, 1` on a and the other outdoor
dungeons; the Sites themselves show as point diamonds (step 13). The Spawns, rooms, corridors
and Props are unchanged. The known issues "Outdoor dungeons get Sites on only some seeds"
and "Sites still spread at random" are fixed by step 13.

### S.1 — Rerolling the rooms keeps the World

- [ ] **[MUST] Same hill, new rooms** — In a then b, the terrain is the same: the same hills,
      the same Rim and ground textures, the same groves (a tree or two may stand a little aside, clear of the new Mouth or Sites), and you spawn at the same spot. The hill the
      Tunnel goes into is the same (west). Only the dungeon inside is new, and its Mouth sits
      somewhere else on that hillside, with its Apron dug in front of it.
- [ ] **[MUST] Same ground, new Sites** — In c then d, the ground, the water and the groves are
      the same. The Sites stand in new places and may be different Sites (d has two shrines
      where c had a shrine and a camp). Each stands on the ground as before: level enough, not
      in water, not in a tree.
- [ ] **[MUST] The button** — On a, **reroll rooms** builds the same hill with new rooms, and
      the Seeds section shows the new rooms seed with the decor seed unchanged. Pressing it
      again gives new rooms again. On a wilderness it moves the Sites.
- [ ] **[MUST] Walkable after a reroll** — In b and d, walk from the Spawn to the Mouth, through
      every room, and to each Site. Nothing is cut off or floating.
- [ ] **[MUST] Rooms seed box** — Typing 12345 in the Controls panel's Rooms seed box with seed
      2 gives b again; blank gives a.

### S.2 — Zones step 11 built look the same

- [ ] **[MUST] Dungeon** — e and f are step 11's d and b: the same rooms in the same places,
      the same walls, corridors and stairs, and the room Props you knew (the throne, the
      tapestry and banners). The rooms are no darker than before.
- [ ] **[MUST] City** — g is step 11's m: the same streets and buildings, still lit and
      lived-in.
- [ ] **[SHOULD] Nothing else moved** — Any dungeon, city or wilderness seed you remember from
      step 11 builds the same zone; only its lights differ (corridors lit, rooms' wall lights
      a little fewer). Only outdoor dungeons move otherwise, and only by their Spawn height (S.5).

### S.3 — Sockets on the map

- [ ] **[MUST] Diamonds** — Press **M** on a. The map shows an **orange** diamond `hill0` on
      the west hill with a short tick pointing west (the way out of the hill), and a **green**
      diamond `ground` at the Spawn. On c a single green `ground` diamond. On e and g a
      **grey** `root` diamond at the origin, by the first room.
- [ ] **[MUST] Hover text** — Hovering a diamond names it: `hillside hill0 (W): dungeon, 8
      rooms`, `ground ground: sites, 0` on a; `ground ground: sites, 2` on c; `root root:
      dungeon, 16 rooms` on e.
- [ ] **[MUST] Where the map says** — In 3D, the dungeon's Tunnel does go into the hill the
      orange diamond marks, on the side its tick points to.
- [ ] **[SHOULD] Downloads unchanged** — The map's SVG and PNG downloads don't carry the
      diamonds (they are drawn on the dialog only).

### S.4 — Corridor lights

- [ ] **[MUST] On the wall** — In h, i and a, each corridor torch hangs on a corridor wall at
      about head height, flame toward the corridor, back flush to the wall: not in the
      doorway, not floating, not sunk.
- [ ] **[MUST] In a row** — In j, k and l, a street's torches run along it evenly spaced, on
      its walls, and none stands in the way through.
- [ ] **[MUST] High corridors** — h's torch in the corridor between room_4 and room_2 (high
      up) hangs on that corridor's own wall, not on a room below it.
- [ ] **[SHOULD] Lit, not floodlit** — The corridors read as lit passages; rooms aren't darker
      than in step 11 and corridors aren't brighter than rooms.

### S.5 — Outdoor dungeons stand on one landscape

- [ ] **[MUST] Feet on the ground** — In m, n, o and p you appear at the Spawn standing on the
      grass: not hovering, not sunk to the ankles. Each moved under a unit, so compare with
      step 11 only if you remember a float or a sink there.
- [ ] **[MUST] Spawn in the Apron** — In q you appear at the bottom of the Apron's trench,
      in front of the troll-sized Mouth, standing on the dug floor. You are not left floating
      where the ground was before the dig, and not under the floor.
- [ ] **[MUST] Gate held** — Every case builds on its first attempt (`validated` in the side
      panel).

### S.6 — The stage commands

From the repo root, with `EQ_PATH` set:

```bash
python scripts/stage.py world od3 --zone-type outdoor_dungeon --seed 3 --out output/stage
python scripts/stage.py attach output/stage/od3.world.json --plan room_count=5 --rooms-seed 9 --out output/stage
python scripts/stage.py rooms output/stage/od3.attach.json --out output/stage
python scripts/stage.py decor output/stage/od3.rooms.json --out output/stage
```

- [ ] **[MUST] One stage at a time** — `world` says `Sockets hill0 (hillside), ground
      (ground)`; `attach` says `hill0 (hillside) seed 9: 5 rooms` and `ground (ground) seed 9:
      0 Sites`; `rooms` says `8 RoomContexts` (5 rooms and 3 corridors); `decor` ends
      `room check: ok`.
- [ ] **[MUST] A loop of seconds** — Each command's own time ("world took …") is about a
      second or less for world, attach and rooms, and a few seconds for decor (0.1, 0.7,
      1.7 and 5.4 s measured, on a busy machine). Imports add several seconds a launch.
- [ ] **[MUST] Each stage looks like its stage** — `od3.world.glb` is the terrain with its
      Sockets as columns; `od3.attach.glb` the rooms as boxes; `od3.rooms.glb` the terrain
      with the dungeon cut in; `od3.decor.glb` the rooms with their Props. Rerun `attach`
      with another `--rooms-seed`, then `rooms` and `decor`: new rooms, the same terrain.
- [ ] **[SHOULD] The build's hand-offs** — A build folder holds `<name>.world.json`,
      `<name>.attach.json` and `<name>.rooms.json`, and `stage.py attach` on that World file
      (same plan fields) writes the same `attach.json`.

Known issues (not regressions; open follow-ups in the spec's `archive.md`):

- Outdoor dungeons get Sites on only some seeds: every outdoor dungeon case above has
  `ground ground: sites, 0`.
- Stair and Bridge corridors get no lights or Props.
- The page's Socket markers work out where to draw from the rooms' labels on the map; if the
  map's labels change, the markers quietly disappear (a console warning).
- Sites still spread at random where stock plains cluster them.
- City decor sits near the tops of its bands.
- The thorough suite at this step (task 16): 3044 passed, none failed (36 min, while the
  cases above were built alongside). Step 11's `test_properties_mapgeom.py::test_reachable_only`
  and step 10's three thorough-profile failures fail on some draws only and passed in this run;
  they stay open.

### S.7 — In-client check (deferred to M6)

- [ ] **[DEFERRED]** Corridor lights and the moved Spawns in the RoF2 client need a takeover
      install. It moves to M6's in-engine smoke load.

## Step 13 — Point Site Sockets

> Roadmap step 13 (`zone-generator-site-sockets`). The World now offers **point `site`
> Sockets** (`site0`, `site1` ...) on good ground, in **Groups** the way stock zones cluster
> their hamlets, and each Site stands on one. A Site's kind is drawn first by the biome's and
> Inhabitant's weights; it then takes the next point in Group order that fits it, so Sites
> gather in a Group until it is full and only then start another. An outdoor dungeon keeps only
> its rooms, corridors, Tunnel and Apron clear, so at Normal and Dense it now always gets a Site.
> The map dialog (M) draws every point as a small orange diamond: filled where a Site stands,
> hollow where unused. **Reroll rooms** moves the Sites among the same points. Restart the
> Server on the merged code first and check the side panel shows no stale-code banner.

### Cases

Pin the seed. Leave the description box empty; Trees normal, Rooms 5, Sites **Normal** and
Inhabitants biome's mix unless the row names them. Every case was built on this code through
the Server's own route (`POST /api/generate`) on its first attempt with the gate passing.
A Site's point is `sites.sites[].socket` in the sidecar; the point's Group is on its entry in
`sockets` (`group`).

| # | Controls | Seed | Rooms seed | What it shows |
|---|----------|------|------------|---------------|
| a | **Wilderness** | 1003 | blank | **A hamlet:** a human hut at (600, −281) and a human camp at (599, −502), both on Group 0's points (`site0`, `site1`). 10 points, 6 Groups |
| b | **Wilderness**, Sites **Dense** | 1003 | blank | **A bigger hamlet:** a's two, and a gnoll camp at (687, −178) and a human shrine at (815, −28): four Sites in Group 0 |
| c | **Wilderness** | 1001 | blank | A centaur camp (4 hide lean-tos) at (−682, −562) and a human hut at (−818, −478), both in Group 2 |
| d | **Wilderness** | 1001 | **12345** | **Rooms reroll:** c's ground, water and trees. The Sites move to other points: a gnoll wattle hut at (−145, −17) in Group 1 and a centaur burial mound ringed by 5 stones at (417, −672) in Group 6 |
| e | **Wilderness** | 1004 | blank | **Two apart:** a human ruin (one wall) at (−162, −27) in Group 4 and a gnoll wattle hut at (−916, −9) in Group 1, about 750 u apart |
| f | **Wilderness**, Sites **Dense** | 1005 | blank | A human camp at (−457, 1082) and a human hut at (−645, 995) in Group 5, and an orc ruin (2 walls) alone in Group 1 |
| g | **Wilderness** | 1002 | blank | A centaur camp (2 lean-tos) at (439, 1018) and a centaur burial mound at (505, 831), Group 4 |
| h | **Outdoor dungeon** | 2 | blank | **A Site by the dungeon:** a human shrine at (341, 120), across the ground from the west hill and its Mouth. 6 points |
| i | **Outdoor dungeon** | 3 | blank | A human ruin of 4 walls at (214, 412). Only 2 points: this landscape has little flat ground |
| j | **Outdoor dungeon** | 18 | blank | A human hut at (439, 115). Hill W |
| k | **Outdoor dungeon**, Sites **Dense** | 2 | blank | h's shrine and no more: Dense asks for more, but the other points are too small for any kind left (a known lean) |

c and d are the reroll pair: build c and press **reroll rooms** (the ⟳ gives a fresh rooms
seed, so its Sites differ from d's; the ground stays c's either way). From the command line:

```bash
python main.py generate points_a --zone-type wilderness --seed 1003
python main.py generate points_b --zone-type wilderness --seed 1003 --sites dense
python main.py generate points_d --zone-type wilderness --seed 1001 --rooms-seed 12345
python main.py generate points_h --zone-type outdoor_dungeon --seed 2
```

The `.eqg` files contain the client's own models and textures (Decor): don't commit or share
them.

### T.1 — Sites read as hamlets

- [ ] **[MUST] Together on good ground** — In a and b the Sites stand near one another on one
      patch of level ground, like a small hamlet seen in a stock plains zone, not strewn across
      the zone. b adds two more to the same place.
- [ ] **[MUST] Room to breathe** — In a, b, c and f no two Sites overlap or crowd: a tent,
      fence or wall of one never stands in another's ground, and you can walk between them.
- [ ] **[MUST] Not on a slope or in water** — Every Site above stands on ground about as level
      as before (step 10): nothing tilts, floats, sinks to its roof or stands in water.
- [ ] **[SHOULD] Apart when they're apart** — In e the two Sites read as two separate places,
      each on its own patch of ground.
- [ ] **[SHOULD] Not too many** — At Normal a wilderness still reads as a Karana with a place or
      two, not a town.

### T.2 — Outdoor dungeons get a Site

- [ ] **[MUST] One, out of the way** — In h, i and j the Site stands on the open ground, not on
      the hill above the dungeon, not in the Tunnel or the Apron trench, and not on the path from
      the Spawn to the Mouth.
- [ ] **[MUST] The dungeon walk holds** — In h, walk from the Spawn to the Mouth and through
      every room: as in step 12.

### T.3 — The points on the map

- [ ] **[MUST] Diamonds where the Sites stand** — Press **M** on a. Small orange diamonds mark
      the points: two filled (where the hut and the camp stand, next to their Site markers and
      labels), the rest hollow.
- [ ] **[MUST] Hover text** — Hovering a filled diamond names its point, Group and Site, for
      example `site site0, Group 0: hut`; a hollow one says `site site5, Group 2: unused`.
      Points of one Group sit close together on the map.
- [ ] **[MUST] Outdoor dungeons too** — On h the six points show, one filled (the shrine), with
      `hill0` and `ground` drawn as in step 12.

### T.4 — Rerolling the rooms moves the Sites

- [ ] **[MUST] Same points, new Sites** — On c, **reroll rooms**: the ground, water and trees
      stay; the hollow and filled diamonds stand in the same places, but a different set of
      them is filled, and the Sites may be other kinds (d).
- [ ] **[MUST] Walkable after a reroll** — In d walk from the Spawn to each Site.

Known issues (not regressions; open follow-ups in the spec's `archive.md`):

- The kind mix follows step 10's weights, which give fewer farmsteads (about 10 %) than stock
  plains (about 27 %): retuning the weights against a stock survey is a follow-up.
- At Dense a big Site often starts a new Group, so Dense gathers less than Normal (decision 11).
- Outdoor-dungeon points are mostly small, so big recipes (farmsteads, ruins of many walls)
  rarely fit there, and Dense seldom adds a second Site (k). Flatter points are a follow-up.
- The thorough suite at this step (task 13): 3103 passed, 3 failed (45 min, while the cases
  above were built alongside). Two failed on pytest's own temporary folders going missing
  mid-run and passed alone. The third, `test_corridor_clearance.py::test_elevated_box_builds_have_one_band`,
  drew a 30-room dungeon (seed 403, moderate) with 4 depth bands on 3 Levels: it fails the
  same way on the code before this step (dungeon layout, untouched here), so it is
  pre-existing and stays open.

### T.5 — In-client check (deferred to M6)

- [ ] **[DEFERRED]** Walking round the hamlets in the RoF2 client needs a takeover install. It
      moves to M6's in-engine smoke load.

## Step 14 — Web UI cleanup

> Roadmap step 14 (`zone-generator-web-cleanup`). The page shows only what applies. The header
> has a **Describe | Controls** switch and one **Generate** button: Describe shows the
> description box, Controls shows the Controls panel (collapsible with the ▾ beside the
> switch). The page remembers the choice in this browser and starts in Controls. The Controls
> sit in labelled groups (Zone, Layout, Content, Landscape, Decor, Seeds), and each control,
> panel row and overlay toggle shows only when it does something. Nothing a build makes
> changed. Restart the Server on the merged code first and check no stale-code banner shows.

Check at the page's full width (1280 px or wider) and once narrower (about 900 px).

### U.1 — Describe or Controls

- [ ] **[MUST] One at a time** — Press **Describe**: the description box shows and the Controls
      panel goes. Press **Controls**: the panel shows and the box goes. The seed box stays in
      both.
- [ ] **[MUST] Generate sends what shows** — In Describe, type `a flooded temple`, Generate: the
      side panel's Plan says Mode `prompt`. In Controls, Generate: Mode `controls`.
- [ ] **[MUST] No silent fallback** — In Describe with the box empty, Generate is greyed out;
      typing turns it on. Enter in the box generates.
- [ ] **[MUST] Remembered** — Choose Describe, reload the page: it opens in Describe. Choose
      Controls, collapse the panel with ▾, reload: Controls, collapsed.
- [ ] **[SHOULD] Reroll keeps its mode** — After a Describe build, **reroll rooms** rebuilds
      from the same description (Mode stays `prompt`).

### U.2 — Only what applies

- [ ] **[MUST] Dungeon** — Zone, Layout, Content, Decor and Seeds show; no Landscape. With Layout
      **Classic**, Rule set, Finish, Structure, Clutter and Overlay go; back to **Graph**, they
      return.
- [ ] **[MUST] City** — No Layout group at all (a city has no layout choice); Content shows.
- [ ] **[MUST] Wilderness** — Zone shows only Zone type; Landscape (four edges, Trees, Sites,
      Inhabitants), Decor and Seeds show; no Layout or Content. Set Sites **none**: Inhabitants
      goes.
- [ ] **[MUST] Outdoor dungeon** — Zone without Size; Layout, Content, Landscape, Decor, Seeds.
- [ ] **[MUST] Decor None** — Set Decor to None: the decor seed box goes.
- [ ] **[MUST] Disabled types stay** — A zone type the server has turned off still shows in the
      list, greyed, with its reason.
- [ ] **[MUST] Side panel before a build** — Reload with the Server stopped (or watch the first
      second): the panel says only "No zone yet" under the build line.
- [ ] **[MUST] Side panel after a build** — A dungeon with Decor shows Props, the decor seed and
      **reroll decor**; with Decor None they go. A wilderness shows no Gates row and no Content.
      The overlay toggles list only what the zone has: Trees on a wilderness with trees, Gates
      on a zone with locks; Wireframe and Room IDs always.

### U.3 — Lined up

- [ ] **[MUST] Header** — One row at full width: every button and box the same height, text on
      one baseline, no button text on two lines.
- [ ] **[MUST] Controls** — In each group the labels line up in one column and the boxes in the
      next, all boxes of a group the same width. Groups with nothing to show are gone, not empty
      frames.
- [ ] **[MUST] Side panel** — Values line up on one right edge; the ⟳ buttons line up in their
      own column.
- [ ] **[SHOULD] Narrow** — At about 900 px the header wraps between groups (the switch, the
      seed, the buttons), never through the middle of a control.
- [ ] **[MUST] Banner on top** — With a stale server (restart it after a commit, or leave the
      page open across a merge) the orange stale-code banner shows above the open Controls.

### U.4 — Nothing else moved

- [ ] **[MUST] Same zones** — A seed you know builds the same zone as before (the same rooms,
      Sites and Props).
- [ ] **[MUST] Keys** — Typing in any box doesn't move the camera; R resets the view, M opens
      the map, Esc closes it.
- [ ] **[MUST] The rest** — The Files list, the map dialog and its Socket diamonds, reproduce,
      and the reroll buttons work as in step 13.

Known issues (not regressions):

- The decor seed and Inhabitants are still sent when hidden (Decor None, Sites none): leaving
  them out builds the same zone but records a different value in the sidecar's `seeds` and
  `sites` blocks, so they stay (task 3).
- The Controls panel covers the top of the 3D view while open; collapse it with ▾ to see the
  whole zone.
- The page still has no type check (`@types/three` deferred).

## Step 15 — Decor rule sets and the room view

> Roadmap step 15 (`zone-generator-decor-rules`). Decor rules now come in layers: files in
> `rules/decor/layers/` merged onto `rules/decor/rooms.toml`, given to a theme by
> `rules/decor/themes.toml` or chosen in the Controls' **Decor rules** select. The tomb's
> Weights moved into `layers/tomb.toml`, and tomb builds came out byte-identical. A room of any
> decorated build opens in the **Room view**, which shows that room alone with every Prop's
> reason. `docs/DECOR_RULES.md` is the guide to writing a layer. Restart the Server on the
> merged code first and check no stale-code banner shows. The first room after a restart takes
> about 15 seconds; the ones after it open in under a second.

Build each case in Controls (Decor **Normal**, Decor rules **From theme** unless the case says
otherwise):

| Case | Zone | Settings | Seed |
|---|---|---|---|
| a | Dungeon | Layout Graph, Rooms 16 | 2 |
| b | City | | 5 |
| c | Dungeon | Theme Tomb, Rooms 10 | 4 |
| d | Dungeon | Theme Temple, Rooms 10, Decor rules **tomb** | 4 |
| e | Dungeon | Layout Classic, Rooms 10 | 4 |

### R.1 — Opening and closing a room

- [ ] **[MUST] From the side panel** — Case a: the side panel's **Rooms** list shows each room
      with its Prop count (room_14 at 0). Click room_5: the room view replaces the 3D view,
      framed on that room alone.
- [ ] **[MUST] From the map** — Open the map (M) and click a room: its room view opens. Do it on
      case a (Graph) and on case e (Classic).
- [ ] **[MUST] Close puts the zone back** — Close (or Esc): the zone is back with the camera
      where you left it and the overlays as they were.
- [ ] **[MUST] Keys** — With a room open, WASD and R don't move the zone's camera behind it;
      typing in the page's boxes moves nothing.
- [ ] **[MUST] Camera** — Drag turns around the room, scroll zooms, and up stays up.
- [ ] **[SHOULD] Cutaway** — The walls are cut away above head height, so the floor and the
      Props show from outside. Untick **Cutaway**: the walls stand whole. Tick it: cut again.

### R.2 — Why each Prop is where it is

- [ ] **[MUST] Props by recipe line** — Case a room_5 (the deep room, the boss): the list groups
      Props under lines such as `rooms.toml dressing.boss props[0]`, each with a count and the
      kinds it placed. The throne and two braziers stand at the boss's POI on the dais.
- [ ] **[MUST] Hover both ways** — Hover a line: its Props light up in the room. Hover a Prop:
      its line lights up in the list.
- [ ] **[MUST] POIs and Dressing** — room_5 lists its boss POI with the Dressing it got (throne,
      braziers); room_15 lists its treasure POI (chests). Labels on shows the POI markers'
      names in the room.
- [ ] **[MUST] Drops say why** — Case a room_11 lists two drops (`laid_table` and `crate_stack`,
      "no spot"); case b room_2 lists two lamps dropped with "no spot".
- [ ] **[MUST] A bare room** — Case a room_14 opens with no Props; its Props row reads `0 (bare)`.
- [ ] **[MUST] Same as the zone** — For any room, the Props in the room view are the ones the
      zone shows in that room: same kinds, same places.
- [ ] **[SHOULD] Other kinds of room** — Case a room_0 (entrance), room_6 (chamber, 8 Props),
      room_13 (hall); case b room_3 (16 Props, `zones.city` lines); case c room_5 (vault: boss
      and treasure) and room_7 (collapsed gallery, 11 Props). Each list reads as an account of
      that room.

### R.3 — The toolbar

- [ ] **[MUST] Reroll** — ⟳ gives the room a fresh decor seed: different Props, the room itself
      unchanged, in under a second.
- [ ] **[MUST] Decor level** — Sparse gives fewer Props than Dense in the same room (case a room_6:
      6 against 8).
- [ ] **[MUST] Decor rules** — On case a, **As built** shows what the build placed; **tomb**
      re-decorates the room with that layer added: fewer lights, more debris and hanging
      chains.
- [ ] **[MUST] Re-read rules** — Edit a count in `rules/decor/rooms.toml` (case a room_6's
      `kinds.chamber` line), press **re-read rules**: the room shows the change with the same
      seed and no restart. Put the file back and re-read again: as before.
- [ ] **[MUST] A broken rule file** — Break `rooms.toml` (an unknown `at`), re-read: the room
      view shows the check's error naming the file, and stays usable. Put it back.

### R.4 — Layers in builds

- [ ] **[MUST] Tomb from the theme** — Case c's side panel Props section shows layers `tomb`. Its
      rooms read as Befallen: bones, debris and hanging chains, almost no lights.
- [ ] **[MUST] Nothing named, nothing changed** — Case a and case b show no layers, and build
      the same zones as before step 15 (the same rooms and Props).
- [ ] **[MUST] Chosen in Controls** — Case d's side panel shows layers `tomb`, and its rooms are
      darker and more cluttered than the same temple built with From theme (fewer light Props,
      more debris); that build shows no layers. Decor rules shows only where Decor does,
      and goes when Decor is None.

### R.5 — Writing a layer

Follow `docs/DECOR_RULES.md` ("Layers and `mode`", "The loop: check, draw") to write a small
layer, for example `rules/decor/layers/try_bones.toml`:

```toml
[layer]
name        = "try_bones"
description = "Bones on chamber floors"

[kinds.chamber]
mode  = "add"
props = [ { kind = ["bone_pile", "skull"], at = "scatter", count = [2, 3] } ]
```

- [ ] **[MUST] Check** — `python scripts/topology_rules.py check rules/decor` lists the new file
      `ok` with its one entry. Take `mode` out: it fails, naming both files.
- [ ] **[MUST] In the page** — Reload the page (no Server restart): Decor rules lists
      `try_bones` with its description, in Controls and in the room view.
- [ ] **[MUST] In the room** — Case a room_6 with Decor rules `try_bones`: a line
      `try_bones.toml kinds.chamber props[0]` places bones, beside the base's lines.
- [ ] **[SHOULD] The guide is enough** — Could you have written that layer from the guide
      alone? Note what was missing.
- [ ] **[MUST] Clean up** — Delete the file; reload: the option is gone.

Since the step 15 close: a layer's own Weights (`[weights.layer]`) reach every room and corridor of
a build that takes it, so the tomb layer now changes case d (it held only the tomb theme's
Weights at sign-off and changed nothing there). Tomb builds (case c) are byte-identical.

Known issues (not regressions):

- Builds cache the merged rules per Server process: after editing a layer, restart the Server
  before building with it. The room view always reads the files fresh.
- The stage command (`scripts/stage.py`) keeps its own copy of the per-room decor step, so its
  Prop positions differ slightly from a build's.
- Sites (wilderness and outdoor-dungeon Points) don't open in the room view; rooms only, by
  design for this step.

## Step 16 — Partial rebuild

> Roadmap step 16 (`zone-generator-partial-rebuild`). A zone now keeps its **versions**: every
> reroll makes the next one (`v2`, `v3` ...) beside the last, and the header's ◂ `v2` ▸ steps
> through them. A decor change (**reroll decor**, or **Use in zone** from the room view) is
> rebuilt from the parent's saved stages, so the rooms, the textures and the walkability check
> of the empty zone are kept and only the Props are placed and checked again. **reroll rooms**
> builds the whole zone again. Each room can now keep a decor seed of its own. Restart the
> Server on the merged code first and check no stale-code banner shows.

Build each case in Controls (Decor **Normal**, Decor rules **From theme**, Seeds blank):

| Case | Zone | Settings | Seed |
|---|---|---|---|
| a | Dungeon | Layout Graph, Rooms 16 | 2 |
| b | City | | 5 |
| c | Outdoor dungeon | Rooms 5 | 2 |
| d | Wilderness | | 4 |

### V.1 — Versions

- [ ] **[MUST] A first build is v1** — Case a: the header shows `v1` with no arrows, and the side
      panel's Version row reads `v1 of 1`.
- [ ] **[MUST] Reroll decor makes v2** — Press **reroll decor** in the side panel's Seeds: the
      page shows it busy (`rebuilding from v1…`) with v1 still on screen, then opens `v2`. The
      Version row reads `v2 of 2 · from v1 · decor seed`; the Decor seed changed, the Rooms seed
      didn't.
- [ ] **[MUST] Same rooms, new Props** — v2's rooms, corridors, walls and textures are v1's; only
      the Props moved.
- [ ] **[MUST] Stepping** — ◂ opens v1, ▸ opens v2 again: each loads its own zone, side panel and
      map (M), and the camera stays where it was. ◂ is greyed on v1 and ▸ on the newest.
- [ ] **[MUST] Rerolling an older version** — On v1, reroll decor: the new version is `v3`,
      `from v1`. Versions are never overwritten.
- [ ] **[MUST] Reroll rooms** — Press **reroll rooms**: the next version has a new layout, and
      its Version row ends `rooms seed`. It takes as long as a Generate.
- [ ] **[SHOULD] Files** — Each version's files (`.eqg`, map files, sidecar) download from its own
      side panel, and on disk sit in their own folder, `output/web/<zone>/v<n>/`, with
      `.request.json` and `.spec.json` beside them.

### V.2 — Quick decor rerolls

- [ ] **[MUST] Quick** — Case a, reroll decor three times. Each takes about 3 seconds, against
      about 10 for a Generate of the same zone. Case b about 1 second; case c about 4; case d
      about 1.5.
- [ ] **[MUST] Every zone type** — Reroll decor on cases b, c and d: each opens a new version with
      the same ground or rooms and new Props. On c and d the Sites keep their places and their
      buildings; only the Props on and around them change.
- [ ] **[SHOULD] After a restart** — Restart the Server and reroll decor on an existing zone: it
      works, and the first one is slower (a few seconds more), the ones after it quick again.

### V.3 — Use in zone

- [ ] **[MUST] Greyed until rerolled** — Case a, step back to v1 (◂) and open room_6 (a chamber,
      8 Props) in the room view: **Use in zone** is greyed. Press ⟳ until you like the room: it
      turns on.
- [ ] **[MUST] One room changes** — Press **Use in zone**: the page builds the next version
      from v1 (`· room decor`) and reopens room_6 on it with the Props you chose. Close the room view:
      room_6 is as you chose it, and every other room's Props are as they were.
- [ ] **[MUST] It sticks** — Open room_6 again on that version: **As built** shows the chosen
      room, and Use in zone is greyed. Use in zone on a second room keeps the first one's choice.
- [ ] **[MUST] Reroll decor starts over** — Reroll decor after that: every room's Props change,
      room_6's choice included (a new decor seed is a new start for every room).
- [ ] **[SHOULD] Undo by stepping** — ◂ goes back to the version before the choice.
- [ ] **[SHOULD] A bare room stays bare** — Case a v1, room_14 (bare): ⟳ leaves it empty. Whether
      a room is bare is the zone's decision, so a room's own seed doesn't change it.

Known issues (not regressions):

- An outdoor dungeon's decor reroll still checks its outdoor part in full (its Sites' Props come
  from the decor seed), so case c stays near 4 seconds.
- Kept checks live only as long as the Server: the first rebuild after a restart takes longer.

---

## Step 17 — Export

> Roadmap step 17 (`zone-generator-export`). A build can now be **exported** as a takeover of an
> existing zone, `arena` by default: a copy of the build renamed for that zone's short name, a
> SQL script for that zone's server rows, and a bundle with install notes. The export is written
> beside the build, in `output/web/<zone>/v<n>/export/<short>/`; the build's own files never
> change, and nothing is copied into an EverQuest folder or run against a database. Restart the
> Server on the merged code first (with `EQ_PATH` pointing at the RoF2 install) and check no
> stale-code banner shows.

Build each case in Controls (Decor **Normal**, Decor rules **From theme**, Seeds blank, Rooms 5
unless a case says otherwise):

| Case | Zone | Settings | Seed | Gates |
|---|---|---|---|---|
| a | Dungeon | Locks 2 | 2 | 2 (tiers 0 and 1) |
| b | City | | 5 | none |
| c | Outdoor dungeon | Rooms 5 | 2 | none |
| d | Wilderness | | 4 | none |

### X.1 — The Export row

- [ ] **[MUST] Where it is** — Case a: at the bottom of the side panel's Files section sits
      **Export**: a **Replaces** filter box, a list of zones, a **Spawn cleanup** tick (off), the
      note "Installing replaces **arena**'s client files and server rows. The tool writes only to
      output/.", and a button **Export to arena**. With no build open the row isn't shown.
- [ ] **[MUST] arena is picked** — The list shows `arena — The Arena` selected and scrolled into
      view, without scrolling the page.
- [ ] **[MUST] Filtering** — Type `guk` in Replaces: the list narrows to the Guk zones
      (`gukbottom — Lower Guk`, `guktop` ...). Type `knowledge`: only `poknowledge — Plane of
      Knowledge` (it matched the long name). Case doesn't matter (`GUK` works). Clear the box:
      the whole list is back, and the zone you last picked is still picked.
- [ ] **[MUST] Picking moves the note and the button** — Pick `befallen — Befallen`: the note
      reads "Installing replaces **befallen**'s ..." and the button **Export to befallen**. Pick
      arena again before X.2.
- [ ] **[SHOULD] Installed first** — Zones in your install come first. With no install configured
      (`EQ_PATH` in neither the environment nor `.env`), every zone reads `(not installed)` and
      is greyed, but still exports.
- [ ] **[MUST] Busy** — Press **Export to arena**: the button greys and reads `Exporting…`, and
      the message under it says `Exporting…`, until the result shows. A second press while busy
      does nothing.
- [ ] **[MUST] The result** — The message reads `<zone> v1 → arena`, and under it a list:
      **Bundle (.zip)** first (in bold), then **Zone archive (.eqg)**, **EQ map layer 0 (.txt)**
      and **EQ map layer 1 (.txt)**, **Server rows (.sql)**, **Zone sidecar (.json)**, **Install
      notes (.txt)**. Each one downloads. Hovering one shows its file name (`arena.eqg`,
      `maps/arena.txt` ...). No warning shows.
- [ ] **[MUST] Spawn cleanup** — Tick Spawn cleanup and export again: the message ends
      `· spawn cleanup`. Untick it before X.3.
- [ ] **[MUST] An unknown name** — Type `arenna` in Replaces (the list empties; the button reads
      **Export to arenna**) and press Enter: the message, in red, reads "unknown short name
      'arenna'; closest: arena, arena2, barren, warrens, arelis". Nothing is written.
- [ ] **[SHOULD] A new version clears it** — Reroll decor (v2): the list of files goes away and
      the button exports v2. Step back to v1 (◂): export again to see v1's files.
- [ ] **[SHOULD] Every zone type** — Export cases b, c and d to arena: each lists the same files
      (case c has three map layers, b and d one), and none warns.

### X.2 — What the bundle holds

Open case a's **Bundle (.zip)** (or the folder `output/web/<zone>/v1/export/arena/`).

- [ ] **[MUST] The files** — `arena.eqg`, `maps/arena.txt` and `maps/arena_1.txt`, `arena.sql`,
      `arena.zone.json` and `INSTALL.txt`. No `gen_...` name is left in any file name.
- [ ] **[MUST] INSTALL.txt** — It says the bundle replaces the zone 'arena' and that nothing has
      been copied into a client or run against a database. It lists the files, then three steps:
      **1. Client** (work on a COPY of the RoF2 folder; move aside `arena.eqg`, `arena.zon`,
      `arena.s3d`, `arena_obj.s3d`, `arena_EnvironmentEmitters.txt`; keep `arena_chr.s3d` and
      `arena_chr.txt`; copy in `arena.eqg` and the map files), **2. Server** (back up the rows
      the header names, replace the placeholder key ids, apply it by hand with `mysql`),
      **3. Check** (zone into 'arena', look for "Loaded arena.EQG." in `Logs\dbg.txt`), and how
      to undo. It opens cleanly in Notepad.
- [ ] **[MUST] The SQL header** — `arena.sql` starts with `--` comments: it takes over the
      EXISTING zone 'arena' (version 0), finds rows by short name and changes no zone id, names
      the rows to back up (the zone row, its doors rows), says "2 here" doors and that spawns are
      left alone, that fog, clip planes and sky stay as they are, and lists the placeholder key
      items (`tier 0: keyitem 990000`, `tier 1: keyitem 990001`) and "lockpick 32767; only the
      key opens them".
- [ ] **[MUST] One transaction** — The statements sit between `START TRANSACTION;` and
      `COMMIT;`: one `UPDATE zone` setting only `safe_x`, `safe_y`, `safe_z` and `underworld`
      (`WHERE short_name='arena' AND version=0`), one `DELETE FROM doors WHERE zone='arena' AND
      version=0`, then one `INSERT INTO doors` per Gate.
- [ ] **[MUST] Safe point and underworld** — Case a: safe point 17.977, -9.335, 5.000, in the
      entrance room on its floor (compare the map, M); `underworld` -102.500, about 100 below the
      lowest floor.
- [ ] **[MUST] The door rows** — Two rows, both `name 'OBJ_BBDOOR1'`, `lockpick 32767`,
      `opentype 0`, `size 180` (the 18-u corridor), `keyitem` 990000 and 990001. Each stands at
      the doorway of its Gate's corridor nearest the lock, on that room's floor: door 1 at
      x 207.2, y -30.8, z 102 (heading 128, a north/south wall: room_2's floor is 102); door 2 at
      x 209.2, y 9.0, z 101.3 (heading 0, an east/west wall, at room_2's end of the ramp from
      room_4). On the map (M, Gates on) each door is at a room's opening of the corridor with a
      lock, not out in the middle of the corridor. (Rows list `pos_y` before `pos_x`.)
- [ ] **[MUST] No Gates, no doors** — Cases b, c and d: the header says "0 here" with no key
      items listed, and the script has the `UPDATE zone` and the `DELETE FROM doors` but no
      `INSERT`.
- [ ] **[SHOULD] Spawn cleanup** — With the tick on, the header also names the spawn rows to back
      up and says "and deletes its spawns", and the script ends with deletes from `spawn2`,
      `grid_entries`, `grid` and `ground_spawns` before `COMMIT;`. Without it those tables are
      never named.

### X.3 — One build, two exports

- [ ] **[MUST] Two names, two folders** — Case a: export to arena, then to `befallen`. On disk,
      `output/web/<zone>/v1/export/` holds `arena/` and `befallen/`, each with its own files
      named for its zone (`befallen.eqg`, `befallen.sql` ...); arena's files are still there.
- [ ] **[MUST] The build is untouched** — The build's own files in `output/web/<zone>/v1/` (its
      `.eqg`, maps, sidecar, `.spec.json`) have the same dates and sizes as before the exports,
      and the zone still loads in the viewer as before.
- [ ] **[SHOULD] Exporting again replaces** — Export to arena a second time: the `arena/` folder
      is rewritten (new dates), with the same files.

### X.4 — In the client

Never on your only install. Make a SCRATCH COPY of the RoF2 folder (for example
`F:\everquest_rof2_scratch`) and do every step there.

- [ ] **[MUST] The copy** — Follow INSTALL.txt step 1 in the scratch copy: move the five stock
      arena files out (keep them), copy in case a's `arena.eqg` and its map files.
- [ ] **[MUST] It loads** — Start the scratch copy's client, zone into `arena`: no crash, and
      `Logs\dbg.txt` has "Loaded arena.EQG.". Without the SQL on your server you arrive at
      stock arena's safe point, which may be off our floor (you fall): that's expected. Walk or
      warp to the safe point in the SQL.
- [ ] **[MUST] Our zone** — The rooms, corridors, walls and textures are case a's as in the
      viewer, and the floors hold you (collision works). The map (in-game map window) shows our
      layout.
- [ ] **[SHOULD] Cases b, c, d** — Do the same with each one's `arena.eqg` in turn: each loads
      and is walkable.

Applying the SQL is OPTIONAL, and only on a test server you can restore (back up the rows its
header names first, as INSTALL.txt says). With case a's script applied:

- [ ] **[SHOULD] Safe point** — Zoning into arena puts you on the entrance room's floor.
- [ ] **[SHOULD] Doors stand and swing right** — A door stands in each locked corridor's doorway
      nearest its lock, upright on the floor, filling the doorway. Note which way each one swings
      (into the room or into the corridor) and whether it opens from the side you meet it on;
      the direction is not yet confirmed, so record what you see.
- [ ] **[SHOULD] Locked** — Without the key the door doesn't open, and Pick Lock never opens it.
      With a key item set in place of the placeholder (990000 / 990001) on the row, and that item
      on you, it opens.
- [ ] **[SHOULD] Undo** — Restore the server rows from your backup and the stock arena files in
      the scratch copy: stock arena loads again.

Known issues (not regressions):

- Which way a door swings is unverified until this pass: the rows keep one convention (hinge at
  the doorway's +y or +x jamb). Report the direction you see.
- Fog, clip planes, sky and zone type stay stock arena's, so the sky and draw distance are
  arena's, not tuned for the zone.

## Step 18 — Edits

> Roadmap step 18 (`zone-generator-edits`, the rest of umbrella M4). Typed feedback on the open
> version ("make the boss room bigger") is read into edits, applied to that version's saved
> spec, and built as the next version of the same zone. **Undo** opens the version this one
> came from and **Redo** the newest one made from it; nothing is ever deleted. Restart the
> Server on the merged code first (with `EQ_PATH` pointing at the RoF2 install) and check no
> stale-code banner shows. With no LLM key the rule interpreter reads the text; with one, an
> LLM may, falling back to the rules.

Build each case in Controls (Decor **Normal**, Decor rules **From theme**, Seeds blank unless a
case pins one):

| Case | Zone | Settings | Seed |
|---|---|---|---|
| a | Dungeon | Layout **Graph**, Rooms 8 | 2 |
| b | City | | 5 |
| c | Outdoor dungeon | Rooms 5 | 2 |

### X.1 — The Feedback section

- [ ] **[MUST] Where it is** — Case a: the side panel opens with **Feedback**: a text box
      ("e.g. make the boss room bigger"), **Apply**, **↶ Undo** and **↷ Redo**. Apply is grey
      until you type; Undo and Redo are grey on v1. With no build open the section isn't shown.
- [ ] **[MUST] Typing doesn't fly** — Click in the box and type `wasd qe` and a space: the text
      appears and the camera doesn't move. Click the 3D view and W moves again.
- [ ] **[MUST] Not understood** — Type `paint it purple please` and press Enter: the message
      reads "Not applied: v1 stays open.", a note says what wasn't understood, and the help lists
      the edits it knows. v1 stays open and no new version appears in the header.

### X.2 — Edits

Start each from case a's v1 unless it says otherwise. After each, the header shows the new
version (◂ `v2` ▸), the message starts `v1 → v2 (full rebuild)` or `(partial rebuild)`, the
Version row names the text, and the edited rooms are tinted until the next change.

- [ ] **[MUST] Bigger boss room** — `make the boss room bigger`: a full rebuild; the note reads
      "widened room_5 by 25%" (or a smaller share "of the 25% asked" with what stopped it). Walk
      to the boss room: it's wider, its doors still open onto their corridors, and the floor is
      walkable to every wall. **Every other room looks as it did in v1** (step back with ◂ to
      compare); a room next door may show a moved doorway lintel, and it is tinted too.
- [ ] **[MUST] Taller and locked** — From v2, `make the boss room taller and lock the way into
      the boss room`: both apply (two notes; the lock's names the corridor and the key's room).
      The ceiling is higher; on the map the new Gate stands on the corridor into the boss room
      and its key in an earlier room. The door model stands in that doorway.
- [ ] **[MUST] Less decor** — From v3, `less decor`: a partial rebuild in a few seconds; every
      room has fewer Props, the rooms' shapes are unchanged.
- [ ] **[MUST] A new purpose** — From v1, `make the entrance a crypt`: a partial rebuild that
      branches from v1 (its Version row says "from v1"); the note reads "room_0 is now an
      ossuary" (crypt is read as ossuary), the entrance's Props change to an ossuary's, nothing
      else does.
- [ ] **[SHOULD] Redecorate one room** — `redecorate the boss room`: only that room's Props
      change.
- [ ] **[SHOULD] Refused, with a reason** — `make the entrance a crypt` on the crypt version:
      "Not applied", and "room_0 is already an ossuary". Case c, `make the boss room
      bigger`: "rooms under a hill can't be resized yet".
- [ ] **[SHOULD] A city** — Case b, `make the boss room bigger` and `lock the way into the boss
      room`: both apply; the city's other buildings and streets are unchanged.
- [ ] **[SHOULD] Start over** — `start over`: a new layout as the next version (full), not a new
      zone.

### X.3 — Undo and redo

- [ ] **[MUST] Undo** — On v3 (made from v2, made from v1): **↶ Undo** opens v2, then v1, where
      it greys. Each version loads as it was built (model, map, side panel).
- [ ] **[MUST] Redo** — On v1, **↷ Redo** opens the newest version made from v1 (v5 if you made
      the crypt edit from v1 last), not simply v2. On a version nothing was made from it greys.
      Hover either button: its tooltip names the version it would open.
- [ ] **[MUST] History** — Hover the header's `v<n>`: the tooltip lists every version with its
      parent and its edit text.
- [ ] **[SHOULD] Nothing lost** — After undoing, make a new edit: a new version appears; the
      versions you undid are still there (◂ ▸ reaches them).

## Step 19 — Quality

> Roadmap step 19 (`zone-generator-quality`, umbrella M3's quality gate). Every generate measures
> its room graph against targets for its zone type, layout, room count and verticality (loops,
> dead ends, floor heights, room sizes and the like) before building, and redraws a dull seed.
> A zone that still misses them (a pinned seed, an edit) is built anyway and says so plainly.
> Restart the Server on the merged code first (with `EQ_PATH` pointing at the RoF2 install) and
> check no stale-code banner shows.

Build each case in Controls (Decor **Normal**, Decor rules **From theme**, Seeds blank unless a
case pins one):

| Case | Zone | Settings | Seed |
|---|---|---|---|
| a | Dungeon | Layout **Graph**, Rooms 10, Verticality **Moderate**, Theme **Fortress** | 1853087170 |
| b | Dungeon | Layout **Classic**, Rooms 7, Verticality **Moderate**, Theme **Temple** | 1192137566 |
| c | Dungeon | Layout **Graph**, Rooms 10, Verticality **Moderate**, Theme **Fortress** | |
| d | City | Rooms 8 | |

### X.1 — Outside the targets

- [ ] **[MUST] The banner** — Case a: an amber banner at the foot of the 3D view says the zone is
      walkable but outside quality targets, "2 metrics out of band", and that the pinned seed
      was built as asked. It has no close control, and it stays put when you open the Controls,
      move the camera or collapse the side panel.
- [ ] **[MUST] The list** — Click the banner's link: the side panel's **Quality** list opens with
      focus on it, `elevation_range — 0 (band 7–…)` and `elevation_levels — 1 (band 2–…)` first,
      then the other metrics with their values. In the 3D view every room is on one floor,
      which is what those two say.
- [ ] **[MUST] A different shortfall** — Case b: one metric out, `size_cv — 0.208 (band 0.25–…)`.
      On the map the rooms are much the same size.
- [ ] **[SHOULD] An edit outside the targets** — On case a, Feedback `make the boss room bigger`:
      v2 is built and still flagged, now with the reason "edit outside bands". ◂ to v1 shows
      v1's own reason again.

### X.2 — Inside the targets

- [ ] **[MUST] Passed** — Case c (no seed): no banner, and the Version row shows quality passed.
      Generate it three or four times: each passes, and none takes noticeably longer than
      before this step.
- [ ] **[MUST] A city** — Case d passes too.
- [ ] **[SHOULD] Start over** — On case a, Feedback `start over`: the new version passes and the
      banner goes away; Undo brings the banner back for the version that had it.
- [ ] **[SHOULD] An old zone** — Open a zone built before this step (◂ ▸ through an older zone's
      versions): "quality unknown", no banner and no list.

### X.3 — Do the targets catch dull layouts?

- [ ] **[MUST] Judge the rejects** — Run `python scripts/quality_sweep.py --per-key 40 --only dungeon
      --svg 3` (a few minutes): it lists failing seeds with their controls and writes maps of
      some to `output/quality_sweep_svg/`. Open those (or build the seeds pinned, as in cases a
      and b) beside a few passing ones. The failing ones should read as dull: a straight line of
      same-size rooms, a comb of dead ends, every room on one floor, one hub with six corridors.
      If a failing one looks fine, or a passing one looks dull, note its seed and settings.

## Step 20 — Districts

> Roadmap step 20 (`zone-generator-districts`, umbrella M3's Districts). A larger dungeon can be
> split into 2–3 **Districts**, like a dungeon's wings: each has its own theme (its Purpose),
> palette, light mood and boss, and they are joined by one corridor each, the **Threshold**. It
> is **off by default**: the Controls' **Districts** box (dungeon only), the CLI's `--districts`
> or a prompt naming contrasting areas ("fallen to the dead", "upper and lower", "two rival
> factions") turns it on. Districts need 8 rooms for 2 and 14 for 3. Restart the Server on the
> merged code first (with `EQ_PATH` pointing at the RoF2 install) and check no stale-code banner
> shows.

Build each case in Controls (Size **medium**, Verticality **moderate**, Decor **Normal**, Decor
rules **From theme**, Theme **None**, everything else at its default) or, where it says
Describe, by typing the text in Describe. Every case was built through the Server with the seed
shown, and the results quoted below are what those builds gave:

| Case | Zone | Settings | Seed |
|---|---|---|---|
| a | Dungeon | Layout **Classic**, Rooms 16, **Districts** ticked | 971456024 |
| b | Dungeon | Layout **Graph**, Rooms 16, **Districts** ticked | 1671788217 |
| c | Describe | `a temple fallen to the dead` | 1972559028 |
| d | Dungeon | Layout **Graph**, Rooms 16, Locks 3, **Districts** ticked | 484702260 |
| e | Describe | `a fortress with upper and lower halls` | 66356526 |
| f | Dungeon | Layout **Classic**, Rooms 16, Districts **unticked** | 971456024 |
| g | Describe | `a city fallen to the dead` | 5 |

### X.1 — Districts on the map

- [ ] **[MUST] Classic** — Case a, open the **Map**: three dashed hulls, one light fill each,
      drawn under the corridors and rooms; the legend lists "District 1 — corrupted_sanctum",
      "District 2 — tomb", "District 3 — ice_keep" and a threshold line. Two corridors are drawn
      heavier in gold: `corr_4` (room_2 → room_5) and `corr_12` (room_3 → room_8). Every room
      sits inside its own District's hull. The side panel's plan readout has a Districts row
      naming the three.
- [ ] **[MUST] Graph** — Case b: three hulls, legend "District 1 — sunken_ruin", "District 2 —
      tomb", "District 3 — corrupted_sanctum"; gold Thresholds `corr_0` and `corr_13`. Hulls of
      neighbouring Districts may overlap where one wraps round another (seen in step 20's own
      run); note it if it makes the map hard to read.
- [ ] **[MUST] One Threshold between two Districts** — On either map, follow each District's
      edge: the only corridor crossing from one hull into another is the gold one. No second
      corridor joins the same two Districts.
- [ ] **[MUST] The room panel** — Case a, click room_6 (or pick it in the room list): its
      District row reads "District 1 — corrupted_sanctum"; room_10 reads "District 2 — tomb".

### X.2 — Walking across a Threshold (only a human can confirm this)

- [ ] **[MUST] Palette and light change** — Case a in 3D: walk from the entrance (room_0)
      through District 1 to room_5, then along the gold `corr_4` into room_2. The floor and walls
      change from corrupted sanctum to tomb materials as you cross, and the light changes with
      them (on this seed room_5's light is violet and room_2's orange). Do the same through `corr_12`
      (room_3 → room_8, tomb to ice keep). The change should read as entering a different wing,
      not as a texture seam: note where the switch happens (in the corridor, at the doorway) and
      whether it looks deliberate.
- [ ] **[MUST] Graph** — Case b, `corr_0` (room_2 sunken ruin → room_3 tomb): both sides are
      cool blue light, so the change rests on the materials and the light's reach. Say whether
      the two areas still read as different places.
- [ ] **[MUST] One boss per District** — Case a: each District has one climax room, its boss
      room: room_6 (District 1), room_10 (District 2), room_11 (District 3). Each is the deepest
      room of its own District from where you entered it, not the deepest of the zone. Walk to
      each; it should feel like the end of its wing. The floors are walkable all the way.
- [ ] **[SHOULD] Still one zone** — Walk the whole of case a or b: every room is reachable, no
      corridor dead-ends in a wall, and the Thresholds are ordinary walkable corridors.

### X.3 — A prompt that turns them on

- [ ] **[MUST] Fallen to the dead** — Case c: Describe with the Districts box **unticked**. The
      zone comes back with the box ticked, 8 rooms (the prompt names no count, so it's raised to
      8), the plan readout's Districts row "temple, tomb", and two hulls on the map with one gold
      Threshold, `corr_1` (room_2 → room_4). The tomb half is the fallen one: its palette is
      `tomb_abandoned` and its light is dimmer, so in 3D it should look older, greyer and darker
      than the temple half. Each half has its boss (room_2 and room_5).
- [ ] **[SHOULD] A plain prompt stays off** — Describe `a small goblin cave dungeon with 6
      rooms`: the box comes back unticked, no hulls, no gold corridors.

### X.4 — Locks on Thresholds

- [ ] **[MUST] Gates on the Thresholds first** — Case d: three Gates. On the map, Gate 0 stands
      on the Threshold `corr_2` (into District 2, tomb) and Gate 1 on the Threshold `corr_11`
      (into District 3, corrupted sanctum); the third, with only two Thresholds to use, sits
      inside District 3 on `corr_12`. Every key is on the entrance side of its Gate (all three
      are in room_1, in District 1, as they are on this seed with Districts off too). In 3D a
      door model stands in each Threshold's doorway.
- [ ] **[SHOULD] Solvable** — Walk case d in order: key, Gate 0, Gate 1, Gate 2. No Gate's key
      is behind it.

### X.5 — A pinned single Purpose

- [ ] **[MUST] Upper and lower** — Case e: the plan readout's Districts row "fortress,
      fortress" and a note in the warnings, "district_purpose_pinned: every District is
      fortress". Two hulls, both "fortress" in the legend, and one gold Threshold, `corr_5`
      (room_1 → room_4). The second District is a variant: `fortress_abandoned` palette and dim
      light, so walking room_1 → room_4 in 3D it is the same kind of place, gone to ruin. Note
      whether the two halves look distinct enough to be worth splitting.

### X.6 — Switched off, and where they don't apply

- [ ] **[MUST] Off is the zone it always did** — Case f: no hulls, no gold corridors, no
      Districts row, no District in the room panel. It is the same zone this seed built before
      step 20: step 20's own run built these controls on the code from before the step and on
      the merged code, and every file inside the `.eqg` came out identical (zone name aside), as
      did case d's controls with the box unticked. Compare with case a: the same seed with the box
      ticked gives different rooms.
- [ ] **[MUST] A city ignores them, with a note** — Case g: a city is built as usual (the plan
      asked for Districts, but the box is hidden for a city), and the warnings carry
      "districts_ignored: Districts apply to dungeons only; this city builds without them".
      No hulls on the map.
- [ ] **[SHOULD] Too few rooms** — Dungeon, Layout **Graph**, Rooms 6, Districts ticked, seed 7:
      it builds as one District with the note "districts_too_few_rooms: 6 rooms; Districts need
      8 or more".
- [ ] **[SHOULD] Rerolls keep them** — On case a, **reroll rooms** then ◂ back to v1: both
      versions show the box ticked and their own Districts on the map.

## Step 21 — Caves

> Roadmap step 21 (`zone-generator-cave`, umbrella M3's `cave` Purpose). A cave is not a zone
> type: it is a dungeon whose Purpose (the page's **Theme**) is **Cave**. Its rooms are a cave
> mouth (entrance), caverns (hubs), grottoes, flooded galleries, sumps, collapsed galleries,
> warrens and passages, with a **crystal grotto** as the climax. The look comes from the
> `rough` wall style (wandering walls, a moving ceiling) that low-finish rooms already draw; there
> is no new geometry. Light is cold and dim, brightest in the crystal grotto; flooded galleries
> and sumps hold water; the decor layer `cave` puts rock, stalagmites, fungus, roots and crystals
> in the rooms and nothing built. Rooms are sized from the measured `styles/cave.json`, so they
> come out smaller than an unthemed dungeon's. Prompts with "cave", "cavern", "grotto",
> "underground" or "tunnel" pick the Theme. Restart the Server on the merged code first (with
> `EQ_PATH` pointing at the RoF2 install) and check no stale-code banner shows.

Build each case in Controls (Size **medium**, Verticality **moderate**, Decor **Normal**, Decor
rules **From theme**, everything else at its default) or, where it says Describe, by typing the
text in Describe. Case f has no page control (the page has the Districts box but no list of
District themes); send it as the body shown, or build it from the CLI with
`--districts --district-theme fortress --district-theme cave` (the CLI was not run for this
section, so the CLI zone may differ). Every case was built through the Server's
`/api/generate` with the seed shown, and the results quoted below are what those builds gave:

| Case | Zone | Settings | Seed |
|---|---|---|---|
| a | Dungeon | Layout **Graph**, Rooms 12, Theme **Cave** | 731402518 |
| b | Dungeon | Layout **Classic**, Rooms 12, Theme **Cave** | 731402518 |
| c | Describe | `a dark cavern` | 1840275513 |
| d | Describe | `an old mine` | 1840275513 |
| e | Describe | `a cave in a hill where kobolds live` | 1840275513 |
| f | Dungeon | `{"mode":"controls","controls":{"zone_type":"dungeon","layout":"graph","room_count":16,"size":"medium","verticality":"moderate","decor":"normal","districts":true,"district_plan":["fortress","cave"]},"seed":731402518}` | 731402518 |
| g | Dungeon | Layout **Graph**, Rooms 12, Theme **Tomb** | 731402518 |
| h | Dungeon | Layout **Graph**, Rooms 12, Theme **None** | 731402518 |

### X.1 — A cave on the graph layout (the default)

- [ ] **[MUST] The rooms** — Case a: 12 rooms, passed the gate on the first build, rule set
      `warren` (the side panel's layout readout). The entrance room_0 is a `cave_mouth`, the hubs
      are room_3 (`cavern`) and room_1 and room_6 (`flooded_gallery`), and the climax and boss room
      is room_4, a `crystal_grotto`. The rest are grottoes, flooded and collapsed galleries and a
      warren. No room has a built name (no hall, barracks, vault or throne room).
- [ ] **[MUST] Rough walls** — Case a in 3D: 10 of the 12 rooms draw `rough` walls and 2 draw
      `hewn` (room_6 and room_9); none draws `built`. Walk room_0 → room_3 → room_4: the walls
      wander in and out, the ceiling rises and falls, and no wall is a straight panel. The two
      hewn rooms should read as worked rock, still not masonry. Say whether the cave reads as a
      found place or as a dungeon with bumpy walls (only a human can confirm this).
- [ ] **[MUST] Cold, dim light** — Case a in 3D: the cave mouth is grey-blue (0.47, 0.55, 0.68),
      the cavern and grottoes a dim blue-grey (about 0.21–0.26, 0.25–0.30, 0.31–0.38), the flooded
      galleries a little bluer. The crystal grotto room_4 is the brightest room, a cold blue
      (0.54, 0.65, 0.90). Known: the shared Room_Types keep their own light, so the warren
      (room_8) and the collapsed galleries (room_9, room_10) are a warm dim orange (about 0.5,
      0.27, 0.07). Say whether those warm rooms break the cave's mood or read as torch-lit dens.
- [ ] **[MUST] The crystal climax** — Case a, room_4: crystal clusters on the floor and the
      roof, CRYSTAL4 ×7, CRYS2E ×6 and a VELIUMCRYSTALS202, with a stalactite (SLCSTALAG404) and
      rubble. In 3D the clusters should be big enough to read across the room (10 u and more),
      not specks, and the room should feel like the end of the cave (only a human can confirm
      this).
- [ ] **[MUST] Water in the flooded galleries** — Case a: the sidecar has five water regions,
      `AWT_water_1`, `_5`, `_6`, `_7` and `_11`, one in each flooded gallery (room_1, room_5,
      room_6, room_7, room_11) and nowhere else. In 3D each of those rooms has its floor under
      water and is still walkable out.
- [ ] **[MUST] Cave decor, nothing built** — Case a: 100 Props, 12 decor lights. They are rubble
      and rocks (HAVRUBBLE301, NROCKS303, WKROCK8), stalagmites and stalactites (SLCSTALAG400 ×10,
      STALAG101), mushrooms (MUSHROOM1, MUSHROOM3), roots on the cave mouth's roof (GKROOT700 ×2),
      bones, and a few wall torches (WALLTORCH200, WALLTORCHARMSTUB200, DROVTORCH200). No
      furniture, banners, braziers or chains (no Prop of category furniture or hanging). The only
      made things are treasure: two chests and an urn in room_6, a chest and two urns in the
      warren room_8 (the treasure Dressing, which the cave layer keeps). Say whether the torches
      and chests belong in a cave or should go.
- [ ] **[SHOULD] Materials** — Case a: the floor and walls are `cave_floor` and `cave_wall`, the
      ceiling `dungeon_ceiling`, all of the `cave_rock` family: damp dark rock, not dressed
      stone.
- [ ] **[SHOULD] Smaller rooms** — Compare case a with case h (same seed, no Theme): the rooms'
      outlines average about 3,550 u² in case a against about 4,800 u² in case h. The Room_Types
      differ too, so this is a rough measure; in 3D the cave's rooms should feel tighter, except
      the cavern hub and the crystal grotto, which are large on purpose.

### X.2 — A cave on the classic layout (box walls: a known limit)

- [ ] **[MUST] Same cave, box walls** — Case b: 12 rooms, passed the gate on the first build.
      The entrance is room_7 (`cave_mouth`), the climax room_6 (`crystal_grotto`, VELIUMCRYSTALS201
      ×4, CRYSTAL4 ×4, NIHSEWCRYS803 ×3, POECRYST503 on the roof), four caverns as hubs (room_1,
      room_2, room_9, room_10). **The walls are boxes**: the classic layout draws no per-room
      finish, so no room draws `rough` (step 21 decision 5). The cave's light, water, materials
      and decor still apply. Known limit, not a fault: note whether the cave decor alone makes it
      read as a cave.
- [ ] **[MUST] Water and decor** — Case b: two water regions, `AWT_water_3` (the sump room_3) and
      `AWT_water_11` (the flooded gallery room_11). 117 Props, almost all rock, rubble, stalagmites
      (CDSTALAG103, SLCSTALAG40x, WARRENSTALAG206), fungus (NSHROOMS301, MUSHROOM1/4) and bones,
      four wall torches and a root; no furniture and no containers on this seed.

### X.3 — Prompts

- [ ] **[MUST] "A dark cavern"** — Case c: a dungeon, Theme **Cave** (the plan readout), layout
      Graph, 5 rooms (no count in the prompt), mood dark. Rule set `warren`, all 5 rooms `rough`.
      Entrance room_0 `cave_mouth`, climax room_4 `crystal_grotto` (CRYSTAL4 ×7, VELIUMCRYSTALS202
      ×2, POECRYST503, two RUBY gems), water in the flooded gallery room_3.
- [ ] **[MUST] "An old mine" stays a mine** — Case d: Theme **mine_delve**, not cave. Rule set
      `classic_eq`; the rooms are an entry hall, forges (room_1 and room_4, each with lava), a
      collapsed gallery and a vault climax; warm orange light; built Props in the vault (NTHRONE,
      KELBRAZ, NIHFURNACE801, chests) and pick-axes in a forge.
- [ ] **[MUST] A cave in a hill** — Case e: an **outdoor dungeon** (zone type unchanged by the cave
      words), Theme **Cave**, race kobold, 5 rooms, rule set `warren`, every room `rough`. The way
      in is from the hill's north face. The entrance room_0 (`cave_mouth`) is on the top Level
      (Level 0, with room_1–room_3); the climax room_4 (`crystal_grotto`) is one Level down
      (Level −1, 92 u lower). Walk in from the outdoor spawn: you enter at the cave mouth, not at
      the deep room, and go down to the crystals (this is the entrance fix step 21 made). Known:
      the flooded gallery room_2 has **no water** here, because an outdoor dungeon keeps only the
      host landscape's regions (its one region, `ALV_lava_0`, is a lava pool out on the land, at
      x 440, y 440).

### X.4 — A cave District next to a built one

- [ ] **[MUST] On the map** — Case f: three hulls, legend "District 1 — fortress", "District 2 —
      cave", "District 3 — warren" (the third Purpose drawn, as 16 rooms allow three). The gold
      Threshold into the cave is `corr_10` (room_2 → room_4); into the warren `corr_2` (room_6 →
      room_9). The cave District holds room_4 (grotto), room_6 (flooded gallery, with water
      `AWT_water_6`), room_7 and room_8 (caverns), room_10 and room_11 (collapsed galleries); its
      boss room is room_10.
- [ ] **[MUST] Crossing into it** — Case f in 3D, room_2 → `corr_10` → room_4: the palette changes
      to the cave's and the light drops from the fortress's warm (about 0.7–0.95, 0.4–0.5, 0.1) to
      the cave's dim blue-grey (0.19, 0.22, 0.28). Known limits, both follow-ups of this step: the
      cave District takes the **zone's** finish and decor, so its walls are `built` (room_4,
      room_6, room_7, room_8, room_10, room_11 all draw `built`) and its decor is the fortress
      recipes: two banners (CMFLAG101) in the cavern room_7, benches (HPBENCH400) in room_8, a
      throne (NTHRONE) in the boss room. Its boss room is a collapsed gallery, not a crystal
      grotto. Note how much of a cave it still reads as.
- [ ] **[SHOULD] The other way round** — Same body with `"district_plan":["cave","fortress"]`:
      District 1 is the cave (entrance room_0 `cave_mouth`, climax room_5 `crystal_grotto` with
      crystal clusters), the zone takes Theme cave's finish and decor, and 14 of the 16 rooms draw
      `rough`, the fortress and lava-forge Districts included (District 3 is `lava_forge` here).
      The finish follows the first District's Purpose, not each District's.

### X.5 — Another Purpose unchanged

- [ ] **[MUST] Tomb** — Case g: a tomb as before step 21 (ossuaries, ritual chambers, a vault
      climax, the `tomb` decor layer). Step 21's own run built case g, case g with Layout
      **Classic**, case h and case d on the code from before the step (`a377d54`) and on the
      merged code: case g on both layouts came out with every file inside the `.eqg` identical
      (zone name aside).
- [ ] **[MUST] Case h unchanged** — Case h (Theme None) and case d (`an old mine`) against the
      code from before the step: identical `.eqg` contents, zone name aside. (Step 21's run
      found a few Props moved, from task 3's retag of VSPBLOCK301 from rock to brick, which
      shrank the rock pool every theme draws from; the lead reverted that retag to keep A6, so
      a cave mouth may still show that square slab as a rock — a follow-up.)

## Step 22 — District looks

> Roadmap step 22 (`zone-generator-district-looks`). In a dungeon with Districts, each District
> now looks like its own Purpose: its rooms draw their wall style (`rough`, `hewn`, `built`) from
> their District's Purpose, and their decor from its decor layers. A corridor takes the look of
> the room it starts from (its `from_room`); a Threshold takes the outer District's look
> (the lower District id), whichever end it was drawn from.
> The room view dresses each room from its own District's layers too. Step 21's cave follow-ups
> are fixed: cave rooms are never lit warm, cave decor has no wall torches and no chests or urns,
> and the cave profile shrinks a cave's footprints but no longer its ceilings. **The wall lights
> a cave had came from its torches, so a cave's corridors are now unlit** (see X.3). Restart
> the Server on the merged code first (with `EQ_PATH` pointing at the RoF2 install) and check no
> stale-code banner shows.

Build each case in Controls (Size **medium**, Verticality **moderate**, Decor **Normal**, Decor
rules **From theme**, everything else at its default). Cases a–c pin the Districts' Purposes,
which the page has no control for: send the body shown to `/api/generate`, or build it from the
CLI with `--districts --district-theme fortress --district-theme cave` (the CLI was not run for
this section, so the CLI zone may differ). Every case was built through the Server's
`/api/generate` with the seed shown, and the results quoted below are what those builds gave:

| Case | Zone | Settings | Seed |
|---|---|---|---|
| a | Dungeon | `{"mode":"controls","controls":{"zone_type":"dungeon","layout":"graph","room_count":12,"size":"medium","verticality":"moderate","decor":"normal","districts":true,"district_plan":["fortress","cave"]},"seed":971456024}` | 971456024 |
| b | Dungeon | Case a's body with `"district_plan":["cave","fortress"]` | 971456024 |
| c | Dungeon | Case a's body with `"room_count":16` and seed 731402518 (step 21's case f) | 731402518 |
| d | Dungeon | Layout **Graph**, Rooms 12, Theme **Cave** (step 21's case a) | 731402518 |
| e | Dungeon | Layout **Classic**, Rooms 12, Theme **Cave** (step 21's case b) | 731402518 |
| f | Dungeon | Layout **Graph**, Rooms 16, Theme **Fortress**, Districts **unticked** | 731402518 |
| g | Dungeon | Layout **Graph**, Rooms 12, Theme **None** (step 21's case h) | 731402518 |

### X.1 — A cave District after a fortress one

- [ ] **[MUST] The Districts** — Case a: 12 rooms, passed the gate on the first build. Two hulls,
      "District 1 — fortress" (room_0–room_5: gatehouse, storeroom, barracks, armory, guard post,
      and the throne room room_5 as boss) and "District 2 — cave" (room_6–room_11: a grotto, two
      caverns, a sump with water `AWT_water_9`, two collapsed galleries; boss room_11). The gold
      Threshold is `corr_10` (room_3 → room_6).
- [ ] **[MUST] Walls change at the Threshold** — Case a in 3D: every fortress room draws `built`
      walls and every cave room draws `rough` (6 of 6; step 21's case f drew `built` there). Walk
      room_3 → `corr_10` → room_6: straight masonry panels on the fortress side, wandering walls
      and a moving ceiling past the doorway. Say whether it reads as walking out of a fortress
      into a cave, and where the change happens (in the corridor or at the doorway).
- [ ] **[MUST] Decor changes at the Threshold** — Case a: the fortress rooms keep the fortress
      recipes (stools, crates and barrels, a chest, a weapon rack, braziers and torches, and in
      room_5 the throne CDTHRONE101 with three COMFLAG303 banners and a chain). The cave rooms
      carry only rock, rubble, stalagmites, crystals and bones: room_8 (cavern) STALAG102 ×2,
      WARRENSTALAG206, VELIUMCRYSTALS202, SLCSTALAG402 and rubble; the boss room_11 19 Props,
      rubble ×10, SLCSTALAG400 ×5, CRYS4E, CRYSTAL4 and bones. No furniture, banner, torch or
      chest in the cave District (step 21's case f had banners, benches and a throne there). The
      sidecar's `decor.districts` reads fortress `[]`, cave `["cave"]`. Three cave rooms (room_6,
      room_7, room_10) are bare on this seed, so the cave District is sparse: say whether it
      reads as empty.
- [ ] **[MUST] The Threshold takes the outer District's look** — Case a: `corr_10` starts in the
      fortress room_3, so it carries a fortress TORCHPOINT and is the last lit corridor; the
      cave's own corridors (`corr_5`–`corr_9`) have no Props and no light. Built like case a,
      seeds 1840275513 and 484702260 draw Thresholds from the cave end (`corr_1` room_2 →
      room_1, `corr_9` room_5 → room_3); since the lead's fix they still look like the fortress.
- [ ] **[MUST] The room view of a cave room** — Case a, open room_8 in the room view: the same 7
      Props as in the zone, under `cave.toml types.cavern` and `cave.toml every` lines. room_11
      lists its boss POI with the cave Dressing (rubble, CRYS4E, CRYSTAL4) under `cave.toml
      dressing.boss`. Press ⟳ on room_8 a few times: each reroll stays cave decor (seen with room
      seeds 4242 and 77: stalagmites, rubble, a crystal). Open the fortress room_5: the throne,
      banners and torches, and no cave line. `corr_10` opens with its TORCHPOINT.
- [ ] **[SHOULD] Three Districts** — Case c: "fortress", "cave", "warren"; Thresholds `corr_10`
      (room_2 → room_4, into the cave) and `corr_2` (room_6 → room_9, cave into warren, so it
      takes the cave look). The cave District (room_4, room_6, room_7, room_8, room_10, room_11)
      draws 4 `rough` and 2 `hewn` (room_6, room_8), no `built`, and cave decor only: no banners,
      benches or throne, which step 21 found there. The room view of room_7 and room_10 gives the
      zone's Props, layer `cave`. Its boss room is still a collapsed gallery (room_10), not a
      crystal grotto (see X.5).

### X.2 — A fortress District after a cave one

- [ ] **[MUST] The Districts** — Case b: "District 1 — cave" (room_0 `cave_mouth`, a collapsed
      gallery, a grotto, a flooded gallery with water `AWT_water_3`, a passage, and the climax
      room_5 `crystal_grotto`) and "District 2 — fortress" (three barracks, a battle arena, a
      prison cell, and the armory room_11 as boss). The Threshold is `corr_10` (room_3 → room_6).
- [ ] **[MUST] Walls** — Case b: every fortress room draws `built`, none `rough` (step 21's reverse
      case drew `rough` in 14 of 16 rooms, the fortress District included). The cave District
      draws 1 `rough` (room_4) and 5 `hewn`: on this seed its rooms drew Finish 4–6, as a cave's
      Room_Types pull the Finish up a little. It is an unlucky seed (task 1 measured 80–85%
      `rough` over 20 seeds); case c's order reversed (seed 731402518, 16 rooms) draws `rough` in
      all five cave rooms. Say whether the hewn cave still reads as a cave next to the built
      fortress.
- [ ] **[MUST] Decor** — Case b: the cave District has rock, rubble, stalagmites, crystals (the
      flooded gallery room_3 CRYSTAL4, CRYS4E) and in the crystal grotto VELIUMCRYSTALS201 ×2,
      CRYSTAL4 ×7, VELIUMCHIPS200 ×3, POECRYST503 and a gem (SERUJEWELS301). The fortress
      District has beds, pallets, chairs, candles, chests (TCHESTS305, TCHESTS303), racks, a
      throne (HHTHRONE) and torches. In the room view, room_5 lists the crystals with layer
      `cave`; room_10 lists its beds and chests with no cave layer.
- [ ] **[SHOULD] Its corridors** — Case b: the cave corridors (`corr_0`–`corr_4`) and the
      Threshold `corr_10` (it starts in the cave room_3) are unlit; `corr_6` and `corr_8` in the
      fortress carry torches.

### X.3 — A cave's light and dressing

- [ ] **[MUST] No warm rooms** — Case d: every room's light is cold. The warren room_8 is
      (0.26, 0.30, 0.37) and the collapsed galleries room_9 and room_10 (0.23, 0.27, 0.34), where
      step 21 had a warm orange (0.51, 0.28, 0.08) and (0.47, 0.26, 0.07). The other rooms are as
      in step 21 (cave mouth 0.47, 0.55, 0.68; crystal grotto 0.54, 0.65, 0.90). Case e
      (classic) likewise: all twelve lights blue-grey, the crystal grotto room_6 brightest.
- [ ] **[MUST] No torches, chests or urns** — Case d: 101 Props, every one rock, rubble,
      stalagmites, crystals or bones (category `debris`) or the cave mouth's two roots
      (GKROOT700, `plant`). No light, container or furniture Prop anywhere; step 21 had wall
      torches (WALLTORCH200, WALLTORCHARMSTUB200, DROVTORCH200, TORCH1, NIHTORCH80x) and chests
      and urns in room_6 and room_8. Case e: 100 Props of the same kinds, none built. Note that
      crystals now show outside the grotto too (CRYSTAL4 ×2 in the flooded gallery room_6, one in
      the warren room_8).
- [ ] **[MUST] Dark corridors (judge this)** — Case d: **no decor light at all** (`decor.lights`
      0; step 21 had 12) and no Prop in any of the 12 corridors (step 21 had a torch in 6 of
      them). The only light is the 12 rooms' own, so in 3D a corridor is lit only by what spills
      in from the rooms at its ends. Case e is the same (0 decor lights, 0 corridor Props). Walk
      room_0 → room_3 → room_4 and room_6 → room_9 → room_11: say whether the dark passages feel
      right for a cave or are too dark to play, and whether a cave wants a faint light of its own
      in its corridors (glowing fungus, crystals).
- [ ] **[SHOULD] Water and climax as before** — Case d: water in the five flooded galleries
      (`AWT_water_1`, `_5`, `_6`, `_7`, `_11`); the climax room_4 has CRYSTAL4 ×7, CRYS4R ×6,
      CRYS4E ×4 and VELIUMCRYSTALS202 ×2.

### X.4 — A cave's ceilings and footprints

- [ ] **[MUST] Taller than step 21, same footprints** — Case d against the same build on the code
      from before the step (`b11764b`, built through its own Server for this section): every
      room has the same width and depth, and every room but the crystal grotto (60 u, at the
      cap both times) is about 13% taller. Mean room height 29.7 u against 26.9 u: the cave mouth
      25.5 u (was 22.5), the cavern room_3 55.2 u (was 48.8), the grotto, warren and collapsed
      galleries 17.0 u (was 15.0). Case e (classic): mean 33.8 u against 29.9 u, caverns 44.9 u
      (was 39.7), the crystal grotto 58.5 u (was 51.7). Corridors are unchanged (18 u wide, 15 u
      high). In 3D the caverns and the grotto should feel tall, not squashed.
- [ ] **[SHOULD] Still smaller rooms** — Case d against case g (same seed, no Theme): mean room
      footprint (width × depth) 4,566 u² against 6,369 u². The Room_Types differ, so this is a
      rough measure; the cave should still feel tighter than the unthemed dungeon, except the
      cavern and the crystal grotto. (Task 4's own measure: footprints 6–13% smaller than the
      same cave with no profile, heights within about 1%.)

### X.5 — Known, not this step

- [ ] **[SHOULD] A cave District's boss room** — When the cave is not the first District its
      climax is not a crystal grotto: collapsed galleries in cases a and c (room_11, room_10),
      and over seeds 1840275513, 1671788217 and 484702260 (built like case a) a flooded or a
      collapsed gallery. On 1840275513 a crystal grotto is drawn, as a dead end (room_5), while
      the boss room is the flooded gallery room_11. As District 1 (case b) the cave's climax is
      its crystal grotto. Note whether the cave District's end feels like an end.

### X.6 — A one-District dungeon unchanged

- [ ] **[MUST] Fortress, Districts off** — Case f, built on the code from before the step
      (`b11764b`) and on the merged code: every file inside the `.eqg` came out identical (zone
      name aside), 209 entries, and the rooms' sizes and heights are the same.
- [ ] **[MUST] No Theme** — Case g: the same check, 118 entries, all identical. In 3D both look
      as they did.

## Step 23 — Winding tunnels

> Roadmap step 23 (`zone-generator-winding-tunnels`). A rough corridor's plain legs (no stairs,
> not a bridge) now wind. Each one follows a centreline of short runs (20–72 u between turns,
> turns of at most 60°) that wanders sideways into the free space around the leg. It runs
> straight for 20 u at each end, so it still meets its room or bend square. The numbers come
> from a survey of 113 stock cave tunnels (`[tunnel]` in `rules/walls/rough.toml`). The floor is
> a mitred strip under rough walls, with a ceiling that follows it. The layout is unchanged,
> except that **a cave's graph rooms now stand much further apart**: the cave profile spaces them
> about 9 corridor widths apart, so its tunnels are long enough to bend (see X.5). Stairs,
> bridges, hewn corridors and built corridors stay straight. The gate's corridor check, corridor
> decor, the map's lines and the outline all follow the tunnel. A fix to the floor relief moves
> rough and hewn room floors a little in every zone that has them (see X.3, X.4). Restart the
> Server on the merged code first (with `EQ_PATH` pointing at the RoF2 install) and check no
> stale-code banner shows.

Build each case in Controls (Size **medium**, Decor **Normal**, Decor rules **From theme**,
everything else at its default unless the row says otherwise). Every case was built through the
Server's `/api/generate` with the seed shown, and the results quoted below are what those builds
gave. The "before" builds ran on the code from before the step (`b2db7b4`), on its own Server.
Every case passed the gate on the first build.

| Case | Zone | Settings | Seed |
|---|---|---|---|
| a | Dungeon | Layout **Graph**, Rooms 12, Theme **Cave**, Verticality **Moderate** (step 22's case d) | 731402518 |
| b | Dungeon | Layout **Graph**, Rooms 12, Theme **Cave**, Verticality **Dramatic** | 23 |
| c | Dungeon | Layout **Graph**, Rooms 12, Theme **Warren**, Verticality **Moderate** | 731402518 |
| d | Dungeon | Layout **Graph**, Rooms 16, Theme **Fortress**, Walls **Built**, Verticality **Moderate** | 731402518 |
| e | Dungeon | Layout **Graph**, Rooms 16, Theme **Fortress**, Verticality **Moderate** (step 22's case f) | 731402518 |
| f | Dungeon | Layout **Classic**, Rooms 12, Theme **Cave**, Verticality **Moderate** (step 22's case e) | 731402518 |

### X.1 — A cave's tunnels in 3D and on the map

- [ ] **[MUST] Which tunnels wind** — Case a: 13 corridors. 12 are rough; the stair `corr_10`
      (room_5 → room_8, 102 u up) is not. 15 of the 30 rough legs wind. Each Z-shaped corridor
      winds its two long legs (1.6 to 16.6 u of sideways wander) and keeps its short middle jog
      straight. The three straight corridors wind the most: `corr_8` (room_0 → room_3), `corr_9`
      (room_3 → room_7) and `corr_12` (room_11 → room_10) each make 4 or 5 turns over about
      210 u and stray 37 to 39 u from the straight line. `corr_4`, `corr_5` and `corr_11` stay
      straight. They start in the hewn rooms room_6 and room_9 and take the hewn look, which has
      no tunnel.
- [ ] **[MUST] In 3D** — Case a: walk room_0 → `corr_8` → room_3 → `corr_9` → room_7. The floor
      should bend smoothly, with no seam, step or gap at a turn. The walls should keep their
      rough wobble round the bends, and the ceiling should follow the floor (no ceiling cutting
      across a bend, no wall through the floor). Both ends should still meet their doorway square.
      Then walk the Z corridor `corr_0` (room_1 → room_4) through its jog. Say whether the
      tunnels read as natural passages or as zig-zags. Not looked at in the 3D viewer for this
      section.
- [ ] **[MUST] On the map** — Case a: the map's corridor lines follow the bends. `corr_8`'s line
      turns with the tunnel where `b2db7b4` drew a straight line. The EQ map files trace the tunnel walls
      (1,195 lines, against 1,109 before). In the viewer, the map overlay and the 3D walls should
      agree. A straight corridor whose two doorways are a little out of line ends its line with
      a short sideways jog (`corr_8`: x 22.5 at room_0, 19.9 at room_3). The jog is the end
      square, as before the step.

### X.2 — Ramps, stairs and bridges

- [ ] **[MUST] A winding ramp** — Case a (Moderate): `corr_8` climbs 4.6 u and `corr_9` 6.7 u,
      and both wind along the whole climb. A Z corridor puts its climb on the middle jog, which
      stays straight (`corr_7`: 4.6 u up over its 27 u jog).
- [ ] **[MUST] Steeper winding ramps** — Case b (Dramatic) has three Levels: 0 (room_0 to
      room_5), -1 (room_6, room_7, room_8) and -2 (room_9, room_10, room_11). Inside Level -1,
      `corr_4` (room_7 → room_6) runs 27.1 u down over 166 u (grade 0.16), with 3 turns and 24 u
      of wander. `corr_8` (room_6 → room_8) runs 26.8 u up with 16.7 u of wander. Walk both in
      3D, up and down: the slope should feel even, with no lip at a turn. Levels are joined by
      stairs, never by a ramp, so no ramp tunnel runs from one Level to the next.
- [ ] **[MUST] Stairs and the bridge stay straight** — Case b: the stairs `corr_7` (room_3 →
      room_6), `corr_9` (room_8 → room_9) and `corr_10` (room_8 → room_10), each 102 u, and the
      bridge `corr_6` (room_0 → room_3) over room_8 are built as before: straight and square,
      with no rough break. In 3D, a winding tunnel next to a straight stair should not look out
      of place.
- [ ] **[SHOULD] What stays straight on Level -2** — Case b: `corr_11` (room_9 → room_11) winds.
      `corr_12` (room_11 → room_10) stays straight: room_10 is hewn, and the corridor changes look
      at a seam.

### X.3 — A warren's tunnels (mostly straight)

- [ ] **[MUST] Why a warren barely winds** — Case c: 12 rough corridors and 24 rough legs, and
      **none winds**. A warren keeps the dungeon spacing (only the cave profile spreads its rooms
      out), so its corridors run 50 to 73 u from end to end. A leg needs about 80 u to turn: 20 u
      straight at each end, plus a run between. Over three more warren builds (seed 10 with 12
      rooms, seed 13 with 20 rooms, seed 23 at Dramatic) 0 of 75 rough legs winds. A warren's
      corridors look as before the step: short, rough-walled and straight. Say whether that is
      fine for a warren, or whether a warren wants the cave's spacing too.
- [ ] **[SHOULD] Floors shift a little** — Case c against `b2db7b4`: the same rooms and
      corridors, but the relief fix lowers parts of 10 rooms' floors by up to 4 u. As a result
      room_1 draws different crates, barrels and torches. No other room's or corridor's decor
      changed.

### X.4 — A built fortress unchanged

- [ ] **[MUST] Built walls** — Case d against `b2db7b4`: every one of the 209 files inside the
      `.eqg` is identical, zone name aside. All 16 rooms are built and no corridor is rough.
- [ ] **[SHOULD] A fortress with some rough rooms** — Case e: five rooms draw `rough` (room_9 and
      room_12 to room_15) and one draws `hewn` (room_5). Six corridors take a wall break (one of them hewn), and none winds
      (the dungeon spacing again). Against `b2db7b4` only the terrain and the zone file change:
      111 of 19,419 vertices drop, by up to 2.7 u, all on the floors of the rough rooms room_13,
      room_14 and room_15 (the relief fix). 7 Props rest about 0.01 u lower. Footprints and
      corridors are unchanged.
- [ ] **[SHOULD] The classic cave** — Case f: every file identical (66 entries). The classic
      layout draws box walls (step 21's known limit), so it has no rough corridor to wind.

### X.5 — A cave's rooms further apart

- [ ] **[MUST] Same rooms, longer tunnels** — Case a against `b2db7b4`: the same 12 rooms (same
      Room_Type, width, depth and height) and the same 13 corridors between the same rooms. The
      rooms now stand much further apart. The mean distance between neighbouring room centres is
      225 u (was 101), the zone covers 920 × 843 u (was 416 × 373), and a plain corridor runs
      212 u from doorway to doorway on average (was 56). The same seed at Dramatic gives 200 u
      against 53. In 3D, say whether the cave now feels like chambers joined by long tunnels, as
      stock caves do, or whether the walks between rooms are too long and empty.

### X.6 — Decor in a tunnel

- [ ] **[MUST] Cave tunnels are bare and unlit** — Case a: no corridor carries a Prop or a
      light. A corridor's decor is its wall lights, and the cave decor layer has none (step 22,
      X.3), so every winding tunnel is dark and lit only by what spills in from the rooms at its
      ends. With Decor **Dense** (same seed) the corridors stay bare. The tunnels are now about
      four times as long as in step 22, so walk `corr_8` (227 u) in 3D and say whether a dark
      tunnel that long is too dark to play.
- [ ] **[MUST] The room view of a tunnel** — Case a: open `corr_8` in the room view. Its box
      spans x 13.5 to 71.4 and y −12.4 to 214.3: 58 u across, room for the 18 u corridor and its
      wander. At `b2db7b4` the box was 18 × 60 u. No Props, also after a reroll (seed 4242).
- [ ] **[SHOULD] Props in a winding tunnel (not reachable)** — No build through the route puts
      a Prop in a winding tunnel today. The corridors that carry torches (a fortress's, a
      fortress District's and the Thresholds) are built and never wind. Also tried: Theme Cave
      with the `tomb` decor layer, Districts fortress + cave and cave + fortress (seed 971456024),
      and Walls **Rough** with Theme Fortress or no Theme (seed 731402518). None put a Prop in a
      tunnel that winds. So decor reading the winding floor is covered only by
      `tests/test_winding_readers.py`.

## Step 25 — Winding routes

> Roadmap step 25 (`zone-generator-winding-routes`). Step 24 (flooded rooms) has no section of
> its own: its look was skipped at the user's word. A rough corridor now winds **door to door**
> where it can: one centreline (`path` on the corridor) leaves each doorway straight for 20 u,
> cuts each square bend as two 45° turns, wanders sideways on any run long enough, and spreads
> any rise over everything between the two straight run-outs. The mesh, the decor, the map and
> the gate all read that one line. A corridor keeps step 23's per-leg winding (or stays straight)
> when it is a stair or a bridge, holds a Transition line, takes a look with no tunnel (hewn), is
> too short to wind, or when its strip would come within a player's half-width (1.5 u) of a room
> or another corridor. With whole routes winding, **a cave's graph rooms stand closer again**:
> the cave run drops from 9 corridor widths to 4 (see X.5). Task 5 also fixed two faults the new
> layouts exposed (see X.6). Restart the Server on the merged code first (with `EQ_PATH` pointing
> at the RoF2 install) and check no stale-code banner shows.

Build each case in Controls (Size **medium**, Decor **Normal**, Decor rules **From theme**,
everything else at its default unless the row says otherwise). Every case was built through the
Server's `/api/generate` with the seed shown, on the merged code (`9f8cef7`), and the results
quoted below are what those builds gave. The "before" builds ran on the code from before the step
(`169e985`), on its own Server. Every case passed the gate on the first build. At `169e985` case
b does not build: the gate rejects it (room_7's treasure POI is not on reached floor), so it has
no "before".

| Case | Zone | Settings | Seed |
|---|---|---|---|
| a | Dungeon | Layout **Graph**, Rooms 12, Theme **Cave**, Verticality **Moderate** (step 23's case a) | 731402518 |
| b | Dungeon | Layout **Graph**, Rooms 12, Theme **Cave**, Verticality **Dramatic** (step 23's case b) | 23 |
| c | Dungeon | Layout **Graph**, Rooms 12, Theme **Warren**, Verticality **Moderate** (step 23's case c) | 731402518 |
| d | Dungeon | Layout **Graph**, Rooms 16, Theme **Fortress**, Walls **Built**, Verticality **Moderate** | 731402518 |
| e | Dungeon | Layout **Graph**, Rooms 16, Theme **Fortress**, Verticality **Moderate** | 731402518 |
| f | Dungeon | Layout **Classic**, Rooms 12, Theme **Cave**, Verticality **Moderate** | 731402518 |
| g | Dungeon | Layout **Graph**, Rooms 13, Theme **Cave**, Verticality **Flat** (task 5's boss POI) | 402962484 |
| h | Dungeon | Layout **Graph**, Rooms 28, Theme **Cave**, Verticality **Dramatic** (task 5's dais) | 1752055716 |

### X.1 — A cave's routes in 3D and on the map

- [ ] **[MUST] Which corridors wind door to door** — Case a: 13 corridors, 12 of them rough and
      plain (the stair `corr_10`, room_5 → room_8, 102 u up, is not). **8 have a path.** Five are
      Z corridors (`corr_0`, `corr_1`, `corr_2`, `corr_6`, `corr_7`): each leaves its doorway
      straight for 20 u, takes its jog as one diagonal between two 45° turns, and runs 20 u
      straight into the far doorway. Their runs are too short to wander, so that is all they do
      (`corr_0`, room_1 → room_4: 102 u door to door, against 109 u along its square route).
      Three are straight corridors that wander: `corr_8` (room_0 → room_3), `corr_9` (room_3 →
      room_7) and `corr_3` (room_6 → room_3) each make 3 turns and stray 4.5 to 10.0 u from the
      straight line (`corr_8`: 112 u, turns of up to 45°, 10.0 u off the line).
- [ ] **[MUST] Which keep their legs, and why** — Case a: `corr_5` (room_6 → room_10) and
      `corr_11` (room_9 → room_11) each hold a Transition line (a seam from hewn to rough), so they
      keep their legs and stay straight. `corr_4` (room_6 → room_9) joins two hewn rooms, and the
      hewn look has no tunnel. `corr_12` (room_11 → room_10) is straight and 96 u long: between its
      two run-outs only 56 u is left, too little to wander, so it gets no path and keeps step 23's
      winding leg (up to 19.8 u of wander). So 9 of the 12 rough corridors wind, 8 of them door to
      door. A route turned down for **clearance** is rarer: in case h, `corr_27` (room_12 →
      room_20, a 121 u Z) would pass 0.73 u from the stair `corr_24`'s box at room_12's doorway,
      under the 1.5 u half-width, so it keeps its square legs. In case e, `corr_12` (room_9 →
      room_12) would fold its strip at a turn and keeps its legs too.
- [ ] **[MUST] In 3D** — Case a: walk room_1 → `corr_0` → room_4. The jog should be one smooth
      diagonal, with no square corner, seam, step or gap at either turn, and the rough walls and
      ceiling should follow it. Both ends should meet their doorway square. Then walk room_0 →
      `corr_8` → room_3 → `corr_9` → room_7: three gentle bends each. Say whether the tunnels read
      as natural passages or as a Z with its corners clipped. Not looked at in the 3D viewer for
      this section.
- [ ] **[MUST] On the map** — Case a: the map's corridor lines follow each path, the Z
      corridors' diagonals included. `corr_8`'s line runs (10.4, 8.1) → (9.8, 28.1) →
      (9.6, 37.1) → (−1.2, 66.2) → (8.2, 87.1) → (8.0, 96.1) → (7.4, 116.1), opening to opening,
      with no square jog at its ends (step 23 drew one where the doorways were out of line). The
      EQ map files trace the tunnel walls: 1,097 lines on layer 0 (1,195 at `169e985`, where the
      tunnels were twice as long) and 93 on layer 1, as before. In the viewer, the map overlay and
      the 3D walls should agree. Not looked at in the 3D viewer for this section.
- [ ] **[SHOULD] The best and the worst** — Case g winds 14 of its 15 rough corridors door to
      door (the 15th, `corr_10`, holds a seam): 9 Z corridors with their diagonal and 5 straight
      ones that wander (up to 10.4 u off the line, `corr_14`). Case b winds only 3 of its 8 (see
      X.2).

### X.2 — Ramps, stairs and bridges

- [ ] **[MUST] A winding ramp** — Case a (Moderate): `corr_9` (room_3 → room_7) climbs 14.0 u.
      Its path is 104 u: flat for 20 u out of room_3, then the whole 14 u spread evenly over the
      next 64 u (grade 0.22) through its three turns, then flat for the last 20 u into room_7.
      `corr_3` (room_6 → room_3) drops 11.3 u over 66.5 u the same way (grade 0.17). Walk both up
      and down in 3D: the slope should feel even, with no lip at a turn and no step at either
      run-out. Not looked at in the 3D viewer for this section.
- [ ] **[MUST] A Z corridor's rise moves off the jog** — At step 23 a Z corridor climbed on its
      short middle jog, which stayed straight. Now the rise runs over the whole path between the
      run-outs. Case b: `corr_0` (room_1 → room_0) drops 2.5 u over 75.3 u (its 115 u path:
      20 u flat, two 16.4 u turn pieces and a 42.5 u run, 20 u flat), `corr_5` (room_5 → room_4)
      3.0 u over 49.9 u. A steeper one is in the warren seed 13 build (Theme **Warren**, Rooms 20,
      **Moderate**): `corr_4` (room_1 → room_0) climbs 6.5 u along a 97 u path. Not looked at in
      the 3D viewer for this section.
- [ ] **[MUST] Stairs and bridges stay square** — Case b has three Levels: 0 (room_0 to
      room_5), −1 (room_6, room_7, room_8) and −2 (room_9, room_10, room_11). The stairs `corr_7`
      (room_3 → room_6), `corr_9` (room_8 → room_9) and `corr_10` (room_8 → room_10), each 102 u,
      and the bridges `corr_3` (room_2 → room_0, over room_8) and `corr_6` (room_0 → room_3, over
      room_6) have no path and no rough break: straight and square, built as before. In 3D, a
      winding tunnel next to a square stair should not look out of place. Not looked at in the 3D
      viewer for this section.
- [ ] **[SHOULD] Level −1's ramps are straight now** — Case b: `corr_4` (room_7 → room_6,
      15.2 u down) and `corr_8` (room_6 → room_8, 12.8 u down) are straight corridors of 76 u,
      too short to wind as a route or as a leg, so they are plain straight ramps. At step 23 the
      same seed spread its rooms further and both wound (`corr_4` over 166 u). `corr_11` (room_9 →
      room_11, 19.9 u up, 78 u) is the same on Level −2. Say whether straight ramps that short
      look wrong among winding tunnels.

### X.3 — A warren (few paths, no wander)

- [ ] **[MUST] How little a warren winds** — Case c: 12 rough corridors, and **3 get a path**
      (`corr_5`, `corr_7`, `corr_11`): Z corridors whose jog becomes a diagonal, with no wander.
      The other 9 are straight or Z corridors of 50 to 70 u, too short for a route line, and none
      winds per leg either. Over three more warren builds (seed 10 with 12 rooms, seed 13 with 20
      rooms, both Moderate, and seed 23 at Dramatic with 12) it is 3 of 10, 4 of 17 and 1 of 8.
      So 11 of the 47 rough corridors in the four builds get a path, all of them a Z's diagonal,
      and none wanders. A warren keeps the dungeon spacing (only the cave profile's run changed),
      and its corridors average 50 to 59 u door to door. Say whether the clipped jogs alone are
      enough for a warren.
- [ ] **[SHOULD] What else moved** — Case c against `169e985`: the same rooms. The mesh grows
      from 9,786 to 9,810 vertices (the three diagonals). Room_8's treasure moves 4.5 u off its
      wall (task 5's POI margin), and its decor is redrawn (106 Props in the zone before, 111
      now). In `corr_5` a torch moves 1.6 u, onto the diagonal's wall, and one brazier in room_4
      moves. Check in 3D that `corr_5`'s torch sits on the wall. Not looked at in the 3D viewer
      for this section.

### X.4 — A built fortress unchanged

- [ ] **[MUST] Built walls** — Case d against `169e985`: every one of the 209 files inside the
      `.eqg` is identical, zone name aside. No corridor is rough, so nothing has a path.
- [ ] **[SHOULD] The classic cave** — Case f: every one of the 67 files identical. The classic
      layout draws box walls, so it has no rough corridor.
- [ ] **[SHOULD] A fortress with some rough rooms** — Case e against `169e985`: the same 16
      rooms and 17 corridors, and the same POIs. One rough corridor gets a path: `corr_13`
      (room_9 → room_13, a Z between two rough rooms), its jog cut as a diagonal (mesh 19,419 →
      19,427 vertices). Its wall torch (NIHTORCH804) moves from (440.0, 177.3) to (436.1, 160.3),
      onto the diagonal: 5.7 u off the centreline, 11.1 u above the floor. This is **a Prop in a
      winding route**, which step 23 could not show (its X.6). Check in 3D that the torch sits on
      the diagonal's wall, not in the air or inside the rock. Room_5 (the hewn throne room, with a
      dais) has its decor redrawn by task 5's drop-edge fix: 6 Props out, 13 in, 116 in the zone
      against 109. The other rough corridors keep their legs: `corr_12`'s strip would fold,
      `corr_14` and `corr_16` are 43 and 42 u, and `corr_15` holds a Transition line. Not looked at
      in the 3D viewer for this section.

### X.5 — A cave's rooms closer again

- [ ] **[MUST] Same rooms, shorter tunnels** — Case a against `169e985`: the same 12 rooms (same
      Room_Type, width, depth and height) and the same 13 corridors between the same rooms. With
      the cave run at 4 widths instead of 9, the mean distance between the centres of rooms a
      corridor joins is 156 u (258 at `169e985`), the zone spans 624 × 575 u (984 × 914), and a
      plain corridor runs 105 u door to door on average (222), from 86 to 121 u. Step 23's X.5
      quoted 225 u, 920 × 843 u and 212 u for its build, measured its own way. Measured as here,
      the `169e985` build gives the figures in brackets, so the rooms now stand about 60 % as far
      apart as at step 23, and 105 u is close to the 102 u median measured for factor 4 (archive
      decision 4). In 3D, say whether the cave now feels like chambers joined by tunnels of stock
      length, or whether it has gone back to rooms too close together. Not looked at in the 3D
      viewer for this section.
- [ ] **[SHOULD] The room view of a tunnel** — Case a: open `corr_8` in the room view. Its box
      spans x −11.0 to 19.4 and y 7.9 to 116.4: 30 u across, room for the 18 u corridor and its
      10 u of wander. No Prop stands in it, and the zone has no decor lights (the cave decor layer
      has no wall lights).

### X.6 — Task 5's two fixes

- [ ] **[MUST] A boss off the outline walls** — Case g: room_4 is the rough crystal grotto with
      the boss. The boss POI stands at (239.0, 225.2), 2.98 u from the nearest outline wall line,
      more than a body's radius (2 u). Before the fix the free cell farthest from the doors was
      the tip of a sharp outline corner, and the boss's own Dressing shut the pocket it stood in.
      In 3D, walk to the boss: it should stand on open floor, not wedged in a corner. Not looked
      at in the 3D viewer for this section.
- [ ] **[MUST] Decor off a dais top's edge** — Case h: room_11 is a hewn crystal grotto with a
      dais 7.16 u high, steps on its N side, its top spanning x 629.4 to 677.5 and y 151.3 to
      184.8. The boss stands on the top at (653.5, 164.9). The top carries a VELIUMCRYSTALS202
      at (665.1, 167.5) and a CRYSTAL4 at (645.2, 166.9), 17.3 and 17.9 u in from the top's
      N edge (y 184.8) and at least 12.4 u from any other edge, with a stalactite (SLCSTALAG404) overhead.
      Before the fix two crystals stood on the top and the only way round them ran along the
      lip. In 3D, climb the steps and walk round the crystals to the boss: there should be room
      to pass without edging along the drop. Not looked at in the 3D viewer for this section.

## Step 26 — Winding control

> Roadmap step 26 (`zone-generator-winding-control`). One user-facing scalar, **Winding**, scales
> how far rough corridors stray. **0** builds every corridor straight with square bends, **1** is
> step 25's stock-measured tunnel (byte-identical to before the step), **2** (`WINDING_MAX`) strays
> further. Above 1 the wander alone gains little (the 30° heading cap holds a run's stray to about
> 0.29 of its middle), so a cave's run also grows by 2 corridor widths per unit above 1: 4 widths
> at 1, **6 at 2**, and the cave's rooms stand further apart (archive decisions 1 and 2). A
> warren's run is the shared dungeon run and does not grow, so a warren barely answers above 1.
> Turn sharpness and run-outs never change. The Controls get a Winding slider, and the rule
> planner reads words. Task 4 fixed three faults the Winding 2 layouts exposed (see X.6). After the
> first look, tasks 8 to 10 took the cave's rooms off the grid and let framed corridors wind, at
> every setting (see X.7). Restart the Server on the merged code first (with `EQ_PATH` pointing at the RoF2 install) and check no
> stale-code banner shows.

Build each case in Controls (Size **medium**, Decor **Normal**, Decor rules **From theme**,
everything else at its default unless the row says otherwise). Every case was built through the
Server's `/api/generate` with the seed shown, on the task-5 branch (`8b85544`: task 4's fixes
merged with master `2bfb895`), and the results quoted below are what those builds gave. Every
case passed the gate on the first build. The "before" builds ran on the code from before the step
(`c120210`) on its own Server. The "before the fix" builds in X.6 ran the gate sweep's own build
(no retry) on master `2bfb895`, which lacks task 4's fixes.

**Since then:** tasks 8 to 10 changed every cave graph layout (Requirement 4 amended), so the
numbers in X.1, X.2, X.5's last item and X.6 are task 5's code (`b70c5fc`), not master's. Case a
at master is in X.7, beside these as "before". The warren and fortress cases (X.3, X.4) and the
words (X.5) still hold.

| Case | Zone | Settings | Seed |
|---|---|---|---|
| a0 | Dungeon | Layout **Graph**, Rooms 12, Theme **Cave**, Verticality **Moderate**, Winding **0** (step 25's case a) | 731402518 |
| a1 | Dungeon | As a0, Winding **1** | 731402518 |
| a2 | Dungeon | As a0, Winding **2** | 731402518 |
| c2 | Dungeon | Layout **Graph**, Rooms 12, Theme **Warren**, Verticality **Moderate**, Winding **2** (also built at 0 and 1; step 25's case c) | 731402518 |
| d2 | Dungeon | Layout **Graph**, Rooms 16, Theme **Fortress**, Walls **Built**, Verticality **Moderate**, Winding **2** (also built at 1; step 25's case d) | 731402518 |
| p | Prompt | "a twisting cave", "straight cave passages", "a cave with a winding stair", "a cave" (rule planner, no API key) | 731402518 |
| x1 | Dungeon | Layout **Graph**, Rooms 30, Theme **Cave**, Verticality **Moderate**, Winding **2**, Size and Decor at their defaults | 432395022 |
| x2 | Dungeon | Layout **Graph**, Rooms 19, Theme **Cave**, Verticality **Flat**, Winding **2**, Size and Decor at their defaults | 2096692951 |
| x3 | Dungeon | Layout **Graph**, Rooms 26, Theme **Cave**, Verticality **Dramatic**, Winding **2**, Size and Decor at their defaults | 770923935 |

### X.1 — One cave at Winding 0, 1 and 2

The same 12 rooms and 13 corridors between the same rooms at every setting: 12 rough plain
corridors and the stair `corr_10` (room_5 → room_8, 102 u up), which never winds. "Stray" is the
largest sideways distance of a corridor's centreline (its path, or its wound legs) from its square
route. A Z corridor's diagonal cuts its corners but strays 0 by that measure. These are
`b70c5fc`'s builds: on master the rooms stand elsewhere and the corridors are straight, so walk
X.7.1 instead.

| Corridor | Rooms | Form | Stray at 0 / 1 / 2 (u) | Door to door at 0 / 1 / 2 (u) |
|---|---|---|---|---|
| `corr_0` | room_1 → room_4 | Z | — / path 0 / path 0 | 109.1 / 101.8 / 145.0 |
| `corr_1` | room_1 → room_0 | Z | — / path 0 / path 0 | 120.2 / 117.1 / 163.5 |
| `corr_2` | room_1 → room_5 | Z | — / path 0 / path 0 | 96.5 / 89.9 / 131.0 |
| `corr_3` | room_6 → room_3 | straight, 11 u down | — / path 6.7 / path 2.1 | 104.6 / 106.5 / 153.2 |
| `corr_4` | room_6 → room_9 | joins hewn rooms | — / — / — | 103.9 / 103.9 / 153.2 |
| `corr_5` | room_6 → room_10 | Z, Transition line | — / — / — | 120.7 / 120.7 / 169.4 |
| `corr_6` | room_2 → room_0 | Z | — / path 0 / path 0 | 91.2 / 85.9 / 125.6 |
| `corr_7` | room_4 → room_3 | Z | — / path 0 / path 0 | 114.1 / 106.5 / 156.4 |
| `corr_8` | room_0 → room_3 | straight | — / path 10.0 / path 11.5 | 108.0 / 112.0 / 158.8 |
| `corr_9` | room_3 → room_7 | straight, 14 u up | — / path 4.5 / path 10.4 | 103.1 / 104.0 / 152.0 |
| `corr_11` | room_9 → room_11 | Z, Transition line | — / — / — | 109.6 / 109.6 / 155.4 |
| `corr_12` | room_11 → room_10 | straight | — / leg 5.3 / path 11.2 | 96.4 / 100.4 / 142.7 |

- [ ] **[MUST] Winding 0: straight, square bends** — Case a0: none of the 12 rough corridors has a
      path or a wound leg. The seven Z corridors run as three straight legs with two square
      corners and the five straight ones as one line; each centreline is exactly its square
      route. The mesh has 10,018 vertices (10,254 at 1). In 3D, walk room_1 → `corr_0` →
      room_4: two square corners, rough walls along straight legs. Say whether a straight rough
      tunnel reads as a hewn passage or still as a cave. Not looked at in the 3D viewer for this
      section.
- [ ] **[MUST] Winding 1: step 25's cave** — Case a1: 9 of the 12 rough corridors wind, 8 with a
      path (five Z diagonals and three that wander: `corr_3`, `corr_8`, `corr_9`) and `corr_12`
      on a wound leg (stray 5.3 u; its 56 u between run-outs is too short for a route). `corr_4`
      joins two hewn rooms, and `corr_5` and `corr_11` hold a Transition line, so those three stay
      straight. This is step 25's X.1, unchanged. Not looked at in the 3D viewer for this section.
- [ ] **[MUST] Winding 2: further strays, longer tunnels** — Case a2: 9 wind, all 9 with a path.
      `corr_12` now has room for a route between its run-outs (142.7 u door to door) and wanders
      11.2 u. The same three stay straight for the same reasons. The largest stray goes from
      10.0 u (`corr_8`) to 11.5 u, and `corr_9` from 4.5 to 10.4 u, but `corr_3` drops from 6.7 to
      2.1 u: the wander is drawn afresh within a larger limit, not scaled. Over the 12 rough
      corridors the mean stray goes 0 → 2.2 → 2.9 u. The tunnels get longer mostly from the run:
      a plain corridor averages 106.5 u door to door at 0, 104.9 u at 1 and **150.5 u at 2**
      (125.6 to 169.4 u). The mesh has 10,780 vertices. In 3D, walk room_0 → `corr_8` → room_3 →
      `corr_9` → room_7, and room_11 → `corr_12` → room_10: each should bend gently, with no turn
      sharper than at 1. Say whether 2 reads as more natural than 1, or just as longer. Not looked
      at in the 3D viewer for this section.
- [ ] **[MUST] Rooms further apart at 2** — With the cave run at 6 widths instead of 4, the mean
      distance between the centres of rooms a corridor joins is 197.1 u at 2 (155.9 u at 0 and 1),
      and the rooms span 769 × 711 u (624 × 575 u at 0 and 1). The rooms themselves are the same.
      In 3D, say whether the cave at 2 still feels like chambers joined by tunnels, or like rooms
      strung far apart. Not looked at in the 3D viewer for this section.
- [ ] **[MUST] On the map** — Cases a0, a1 and a2: the map's corridor lines follow each
      centreline. At 0 every line is the square route. At 1, `corr_8` runs (10.4, 8.1) →
      (9.8, 28.1) → (9.6, 37.1) → (−1.2, 66.2) → (8.2, 87.1) → (8.0, 96.1) → (7.4, 116.1), as in
      step 25. At 2 it runs (15.5, −0.1) → (15.1, 19.9) → (14.9, 28.9) → (25.8, 58.5) →
      (13.0, 126.5) → (12.8, 135.5) → (12.4, 155.5). The EQ map files have 976, 1,004 and 1,069
      lines on layer 0 at 0, 1 and 2, and 93 on layer 1 at each. In the viewer, the map overlay
      and the 3D walls should agree at each setting. Not looked at in the 3D viewer for this
      section.

### X.2 — Winding 1 is unchanged

- [ ] **[MUST] Byte-identical to before the step** — Case a1 against `c120210` (no Winding):
      every one of the 47 files inside the `.eqg` is identical, zone name aside (the ZON also
      names its TER in capitals, masked the same way). A plan at 1 leaves `winding` out of the
      plan and the spec. The four byte-identity test files cover the other goldens. Since tasks 8
      and 9 this holds only for zones with no jittered cave layout: case a at 1 now differs from
      `b70c5fc` in 28 files, changed or new (51 against 47), as it should; X.7.4 has the zones that stay
      identical.

### X.3 — A warren at 2 (barely changes)

- [ ] **[MUST] How little a warren answers** — Case c2 against the same warren at 1: every one of
      the 122 files inside the `.eqg` is identical. The same 3 Z corridors get a path (`corr_5`,
      `corr_7`, `corr_11`, their jog cut as a diagonal), none wanders, and the other 9 are 50 to
      70 u long, too short for a route or a wound leg. The warren seed 13 build (Rooms 20,
      **Moderate**) is identical at 2 and 1 too (140 files; 4 of its 17 rough corridors get a
      path). A warren's run is the shared dungeon run (2 widths), which the Winding does not
      grow, so this is expected (archive decision 2: over 20 warren builds the mean stray stays
      0.08 u at every Winding from 1 to 3). Only 0 changes a warren: case c at 0 drops the three
      diagonals (9,786 vertices, against 9,810 at 1 and 2), and its corridors average 60.1 u door
      to door (59.0 u at 1). Say whether a warren should answer the slider at all (a follow-up:
      grow its run without moving the bytes of non-rough dungeons).

### X.4 — A built fortress unchanged

- [ ] **[MUST] Built walls at 2** — Case d2 against the same fortress at 1, and against `c120210`:
      every one of the 209 files inside the `.eqg` is identical both times, zone name aside. No
      corridor is rough, so the Winding has nothing to scale (the spec still records
      `winding: 2.0`).

### X.5 — The slider and the words

- [ ] **[MUST] The slider** — In Controls, the **Winding** slider (0 to 2, step 0.25, default 1,
      its value shown beside it) shows for Dungeon, City and Outdoor dungeon and hides for
      Wilderness. Checked in the browser on an agent Server: with the slider focused, the arrow
      keys moved it from 1 to 2 and the value beside it read 2; thirty presses of W left the 3D
      view unmoved and the slider at 2. Generating case a2 that way showed **Winding 2** in the
      plan readout, Quality passed and 10,780 vertices, the same build as through the API. Check
      it yourself the same way, and that WASD moves the camera again once you click the view.
- [ ] **[MUST] The words** — Prompt mode with no API key (the rule planner), seed 731402518:
      "a twisting cave" plans Winding **1.75**, "straight cave passages" plans **0.25**, "a cave
      with a winding stair" plans 1 (the stair phrase is dropped, so `winding` is left out of the
      plan), and "a cave" plans 1. Each builds a 5-room graph cave and passes the gate. In
      Controls the prompt is never read: Controls at Winding 0.5 with the prompt "a twisting cave"
      plan **0.5**. Check the plan readout's Winding row each time.
- [ ] **[SHOULD] The words move the rooms only above 1** — "straight cave passages" (0.25) lays
      out the same rooms as "a cave" (1). "a twisting cave" (1.75) spreads them as the run grows
      above 1: room_1's outline starts at (183.6, −62.4) instead of (152.8, −60.3). (Those
      coordinates are `b70c5fc`'s; since task 8 the cave's rooms stand elsewhere. Not rebuilt for
      X.7.)

### X.6 — Task 4's three fixes

Each was a gate failure at Winding 2 in a cave graph layout with `EQ_PATH` set. Built on master
`2bfb895` with the gate sweep's build, each fails as described. On `8b85544` each passes, and
through the Server each passed on the first build. Since task 8 the three seeds lay out
differently, so the rooms and spots below are no longer where they were; rebuilt for X.7 through
the Server on `92c00e0`, each still passes the gate on the first build (37,710, 17,600 and 30,065
vertices).

- [ ] **[MUST] A bridge keeps off a doorway already on its wall** — Case x1, room_2. Before the
      fix, `corr_3` (room_6 → room_2) was straightened as a Bridge over room_12, onto y −22.2 on
      room_2's west wall (x −108.9). That put it 14.1 u from the doorway of the U-stair `corr_13`
      (room_2 → room_8, side W) at y −36.3. Both are 18 u wide, so the openings overlapped and the
      gate found an open seam at (−110.9, −29.2). Now `corr_3` keeps its Z route with a path, from
      (−231.6, 2.5) to (−108.9, −13.4), 22.9 u from the stair's doorway. In 3D, look at room_2's
      west wall: two separate doorways with a pier of rock between them and no gap in the wall.
      Not looked at in the 3D viewer for this section.
- [ ] **[MUST] A decor footprint no longer cuts the floor** — Case x2, room_17: a rough flooded
      gallery with doors S and W and a dais (7.1 u, steps on its S side) holding the treasure POI
      at (890.4, 142.6). Before the fix the gem dressing the POI (CDGEM101, `decor_0114`) stood at
      (897.8, 153.3) and cut 476 u² of floor at (861, 161) off from the entrance. That floor
      joins the doors only by a lane one cell wide, running corner to corner between the dais and
      the wall. Now the gem stands at (900.8, 129.1) and the room's decor is redrawn (9 Props in
      its box, 7 before). In 3D, walk from the W door round the dais's N side into the NW corner
      near (861, 161): you should get there without squeezing past a Prop. Not looked at in the
      3D viewer for this section.
- [ ] **[MUST] A hollow rock no longer narrows a throat** — Case x3, room_7: a rough passage with
      doors S and N and a DNROCK101 (scale 1.55) over its middle. Before the fix the rock stood at
      (153.2, 200.7). It is hollow at head height: the gate's samples found a free hole inside it,
      nearest the core, that no door reached, so both doors' ways to the core read under 8 u wide.
      Decor now counts that hole as maybe free. The rock stands at (154.2, 198.2), with the room's
      decor redrawn (8 Props, 5 before). In 3D, walk from the S door past the rock to the N door:
      there should be a clear 8 u way past it, and nothing should look reachable inside the rock.
      Not looked at in the 3D viewer for this section.

### X.7 — First-look fixes

At the first look (2026-11-21) the user said "conceptually the winding is ok", but seed
731402518's cave rooms sat on a grid and "between room 9 and 11 is a sharper turn". Three tasks
answer it (archive decisions 4 to 7). Task 8 moves a cave Graph layout's rooms off the lattice:
each neighbour stands off its wall side by a seeded amount sideways and at 1.25 to 1.75 times the
run, and two rooms whose walls share enough span get both doors mid-span, so the corridor runs
straight. Only cave zones do this. Task 9 gives a framed corridor (one holding a Transition line:
a frame, breach or seam) a door-to-door path, held straight through the line so the frame stands
square across it. Task 10 fixed three gate faults the new layouts exposed.

Every case below was built through `/api/generate` (rule planner, no API key, `EQ_PATH` set) on
an agent Server running this branch (`92c00e0`, master with tasks 8 to 10), and passed the gate
on the first build with its seed kept. "Before" is task 5's code (`b70c5fc`) on its own Server,
except where X.7.3 says "before the fix": that is the gate sweep's own build on `83410e9`, after
tasks 8 and 9 but before task 10. Build cases a0 to a2 as in X.1 (Size **medium**, Decor
**Normal**). The other cases leave Size and Decor at their defaults.

| Case | Zone | Settings | Seed |
|---|---|---|---|
| a0, a1, a2 | Dungeon | As in X.1: Layout **Graph**, Rooms 12, Theme **Cave**, Verticality **Moderate**, Winding **0**, **1**, **2** | 731402518 |
| f1 | Dungeon | Layout **Graph**, Rooms 10, Theme **Cave**, Verticality **Moderate**, Winding **1** | 1025 |
| t1 | Dungeon | Layout **Graph**, Rooms 24, Theme **Cave**, Verticality **Moderate**, Winding **0** (also built at 1) | 937463091 |
| t2 | Dungeon | Layout **Graph**, Rooms 27, Theme **Cave**, Verticality **Moderate**, Winding **2** | 2071938654 |
| t3 | Dungeon | Layout **Graph**, Rooms 21, Theme **Cave**, Verticality **Dramatic**, Winding **2** | 644918873 |
| c1, d1, w13 | Dungeon | Cases c and d (X.3, X.4) at Winding **1**, and the warren seed 13 build (Rooms 20, **Moderate**) at 1 | 731402518, 13 |

#### X.7.1 — Seed 731402518 off the grid

The same 12 rooms and 13 corridors join the same rooms as before (room ids unchanged): 12 rough
corridors and the stair `corr_10` (room_5 → room_8, a U-route 102 u up, never rough). room_6
and room_9 are hewn. The rooms keep their sizes, but every centre moved:

| Room | Before, Winding 0 and 1 | Before, Winding 2 | Now, Winding 0 and 1 | Now, Winding 2 |
|---|---|---|---|---|
| room_0 | (10.4, −22.6) | (15.5, −30.8) | (8.3, −1.8) | (10.8, −1.2) |
| room_1 | (181.9, −27.9) | (232.8, −37.5) | (181.1, −20.9) | (236.4, −20.4) |
| room_2 | (−124.1, −31.7) | (−157.3, −43.1) | (−14.8, 172.8) | (−12.3, 230.6) |
| room_3 | (7.4, 161.3) | (12.4, 200.8) | (−25.3, −200.6) | (−20.4, −260.7) |
| room_4 | (194.3, 148.5) | (246.5, 181.5) | (158.7, −235.2) | (214.0, −295.3) |
| room_5 | (193.1, −174.3) | (248.1, −223.3) | (369.9, −39.9) | (482.0, −41.6) |
| room_6 | (−167.0, 163.0) | (−210.5, 204.4) | (−218.9, −168.0) | (−273.8, −228.1) |
| room_7 | (6.3, 335.9) | (11.7, 421.9) | (−48.4, −370.6) | (−43.5, −478.0) |
| room_8 | (226.2, −174.3) | (281.3, −223.3) | (403.0, −39.9) | (515.1, −41.6) |
| room_9 | (−326.8, 167.4) | (−415.1, 209.0) | (−392.9, −156.3) | (−504.6, −213.4) |
| room_10 | (−178.3, 327.0) | (−224.5, 414.4) | (−238.5, 22.4) | (−292.3, 20.6) |
| room_11 | (−334.8, 329.5) | (−424.0, 416.0) | (−425.6, 3.8) | (−539.4, 0.1) |

The grid score is the share of the 66 centre pairs whose x or y agree within 10 u. Before, it was
**0.227** at 0 and 1 (15 pairs) and 0.212 at 2. Now it is **0.030** at 0 and 1 (2 pairs) and
0.045 at 2 (3 pairs). Of the 2 pairs at 1, room_5 and room_8 are the stair's stacked pair, which
is never offset, and room_0 and room_11 agree in y by chance, 434 u apart. The rooms now spread
892 × 599 u at 0 and 1 (624 × 575 before) and 1,118 × 764 u at 2 (769 × 711). Rooms a corridor
joins stand 174.0 u apart on average at 0 and 1 (155.9 before) and 225.6 u at 2 (197.1). The
mesh has 10,380, 10,800 and 11,425 vertices at 0, 1 and 2 (10,018, 10,254 and 10,780 before).

Every rough corridor is now **straight** at 0 and 1, where before 7 of the 12 were Z routes. At
1, 9 of the 12 take a path, and every path wanders. Before, five of the eight paths were Z
diagonals that strayed 0. Stray and door to door are measured as in X.1: the largest sideways
distance of the centreline from its square route, and the centreline's length.

| Corridor | Rooms | Form before → now | Stray now at 0 / 1 / 2 (u) | Door to door now at 0 / 1 / 2 (u) | Door to door before (u) |
|---|---|---|---|---|---|
| `corr_0` | room_1 → room_4 | Z → straight | — / path 1.8 / path 23.9 | 134.6 / 134.7 / 208.6 | 109.1 / 101.8 / 145.0 |
| `corr_1` | room_1 → room_0 | Z → straight, 14 u down | — / path 9.8 / path 10.5 | 116.2 / 119.5 / 173.0 | 120.2 / 117.1 / 163.5 |
| `corr_2` | room_1 → room_5 | Z → straight, 21 u down | — / path 15.1 / path 21.2 | 125.0 / 131.6 / 189.9 | 96.5 / 89.9 / 131.0 |
| `corr_3` | room_6 → room_3 | straight (11 u down) → straight | — / path 10.6 / path 11.0 | 123.7 / 127.0 / 186.5 | 104.6 / 106.5 / 153.2 |
| `corr_4` | room_6 → room_9 | straight, joins hewn rooms | — / — / — | 118.0 / 118.0 / 174.7 | 103.9 / 103.9 / 153.2 |
| `corr_5` | room_6 → room_10 | Z → straight, seam | — / — / path 8.4 | 135.8 / 135.8 / 196.6 | 120.7 / 120.7 / 169.4 |
| `corr_6` | room_2 → room_0 | Z → straight | — / path 7.0 / path 12.9 | 118.5 / 120.2 / 178.8 | 91.2 / 85.9 / 125.6 |
| `corr_7` | room_4 → room_3 | Z → straight | — / path 2.9 / path 2.3 | 98.4 / 98.8 / 148.9 | 114.1 / 106.5 / 156.4 |
| `corr_8` | room_0 → room_3 | straight → straight, 14 u up | — / path 7.4 / path 24.1 | 122.8 / 124.6 / 193.5 | 108.0 / 112.0 / 158.8 |
| `corr_9` | room_3 → room_7 | straight (14 u up) → straight | — / path 5.7 / path 1.2 | 98.6 / 100.2 / 145.9 | 103.1 / 104.0 / 152.0 |
| `corr_11` | room_9 → room_11 | Z → straight at 0 and 1, Z at 2; seam | — / — / path 0 | 99.6 / 99.6 / 167.5 | 109.6 / 109.6 / 155.4 |
| `corr_12` | room_11 → room_10 | straight | — / path 6.6 / path 7.8 | 127.0 / 128.4 / 189.0 | 96.4 / 100.4 / 142.7 |

Over the 12 rough corridors the mean stray is 0, **5.6** and **10.3** u at 0, 1 and 2 (0, 2.2
and 2.9 u before). The 10 without a Transition line average 118.3, 120.3 and 178.9 u door to door
(104.7, 102.8 and 148.1 u before by the same measure).

- [ ] **[MUST] The grid is gone** — Cases a0, a1 and a2: look at the map and fly over the cave.
      Before, rooms stood in rows and columns about 170 u apart: rows of three at y −22 to −32
      (room_0, room_1, room_2), y 161 to 167 (room_3, room_6, room_9) and y 327 to 336 (room_7,
      room_10, room_11), and a column at x 6 to 10 (room_0, room_3, room_7). Now no three rooms
      line up; the stair pair room_5 / room_8 shares a row at y −39.9, as a stacked pair always
      does, and room_0 / room_11 agree in y, 434 u apart. Say whether the cave now reads as chambers placed by hand, and whether the straight
      doorways (each pair's doors face each other mid-wall) look too regular. Not looked at in
      the 3D viewer for this section.
- [ ] **[MUST] Winding 0: straight tunnels between offset rooms** — Case a0: all 12 rough
      corridors are single straight legs, no path, no wound leg, no bends at all now (before,
      seven had two square corners). In 3D, walk room_1 → `corr_2` → room_5 (125.0 u, 21 u
      down): one straight ramped tunnel. Not looked at in the 3D viewer for this section.
- [ ] **[MUST] Winding 1: every path wanders** — Case a1: 9 of the 12 rough corridors take a
      path and each strays off its line (1.8 to 15.1 u), where before most were Z routes whose
      diagonal strayed 0. `corr_4` (two hewn rooms), `corr_5` and `corr_11` (seams) stay
      straight. In 3D, walk room_1 → `corr_2` → room_5 (15.1 u) and room_1 → `corr_1` → room_0
      (9.8 u): each should bend gently with no sharp turn. Not looked at in the 3D viewer for
      this section.
- [ ] **[MUST] Winding 2: further** — Case a2: 11 of the 12 take a path; only `corr_4` stays
      straight. The largest strays are `corr_8` 24.1 u, `corr_0` 23.9 u and `corr_2` 21.2 u. In
      3D, walk room_0 → `corr_8` → room_3: it should swing well off its line and back, with no
      turn sharper than at 1. Say whether 2 now reads as more natural than 1, or just as longer.
      Not looked at in the 3D viewer for this section.
- [ ] **[MUST] room_9 → room_11 (`corr_11`) has no sharp turn** — The corridor the user named is
      still `corr_11` (room_9, hewn, to room_11, rough), the framed one, with a seam where the
      hewn look meets the cave. Before, at every setting, it was a Z with an 8 u jog and two
      square bends and no path (the "sharper turn"). Now at 0 and 1 it is one straight leg,
      (−405.1, −131.9) → (−405.1, −32.3), 99.6 u, no path, with the seam at (−405.1, −95.5),
      36.4 u from room_9's door: the cave side past the seam (63 u) is too short to wind by the
      stock tunnel, and a straight corridor has no bend to cut. At 2 its rooms' walls share only
      25.2 u across, under the 27 u (1.5 corridor widths) a straight door pair needs, so it is a
      Z again, but with a path: a 20 u
      run-out from room_9's door (−504.6, −188.9), on straight to (−504.6, −129.9) with the seam
      at y −164.3 on that straight, one 45° diagonal across the jog to (−539.4, −95.0), straight
      on to room_11's door (−539.4, −35.9); 167.5 u. In 3D, walk room_9 → room_11 at each
      setting: at 0 and 1 a straight tunnel with the hewn-to-rock seam square across it; at 2
      two gentle 45° turns, no square corner, the seam square on the first straight. Not looked
      at in the 3D viewer for this section.
- [ ] **[SHOULD] The other seam, `corr_5`** — Case a2: `corr_5` (room_6, hewn, to room_10) is
      straight with a path at 2 that wanders 8.4 u, its seam at (−285.1, −109.1) on a straight
      stretch. At 0 and 1 it stays straight with no path, like `corr_11`. In 3D, check the seam
      stands square across the tunnel at 2. Not looked at in the 3D viewer for this section.

#### X.7.2 — A framed corridor that winds at Winding 1

Case f1. `corr_8` joins room_4 (the boss's crystal grotto) to room_5 as a Z route with a
**frame** (jambs 1.5 u in, a lintel 2 u down) at (310.1, 223.5), 5 u out from room_4's north
door at (310.1, 218.5). Its path: a 20 u straight run-out north to (310.1, 238.5), holding the
frame; the first bend cut to (300.9, 247.7); the cross leg west wandering 2.9 u off its line (at
(270.4, 250.6)); the second bend cut, (239.9, 247.7) to (230.7, 256.9); a 20 u run-out into
room_5's south door at (230.7, 276.9). Door to door 127.4 u; 12,487 vertices. At `b70c5fc` the
seed lays out differently (rooms on the lattice, 11,641 vertices) and no framed corridor in it
has a path: of its two seams, `corr_3` is one straight leg and `corr_9` a Z with square bends, as
every framed corridor was before task 9. Over cave graph seeds 1000–1039 at 1, 17 of the 19 framed Z
corridors now take a path (0 before; archive decision 6).

- [ ] **[MUST] The frame square, the cave side winding** — In 3D, walk from room_4's north door
      through the frame into `corr_8` and on to room_5. The frame should stand square across
      the tunnel on its straight run-out, both jambs and the lintel at right angles to the walls,
      with no bend inside it. Past it, both corners should be cut (no square corner) and the
      middle stretch should drift gently sideways. Say whether the frame reads as set into the
      tunnel or as stuck on. Not looked at in the 3D viewer for this section.

#### X.7.3 — Task 10's three fixes

Each seed failed the gate before the fix (gate sweep build on `83410e9`) and passes now through
the Server. At `b70c5fc` each passed too, with its rooms elsewhere (still on the lattice).

- [ ] **[MUST] t1: a hairline gap at a stair door** — Case t1 at Winding 0 (and 1), room_9
      (centre (−6.3, −166.9), 70 × 74 u, floor −108.2). Before the fix it failed at both
      settings: "no walkable path from the core to throat (7.7, −181.6, 7.7, −157.9)". The U-route
      stair `corr_10` from room_3 arrives at room_9's south door (16.7, −201.8), and the stair
      door's outline piece started 0.0022 u short of the room's Core at x 7.7, so the outline
      drew a link 0.0022 u wide there that the gate read as unreached. Now a gap that small
      counts as touching, and it passes at both (25,703 and 26,491 vertices; at `b70c5fc`,
      24,669 and 25,125, room_9 at (−196.7, 32.8)). In 3D, walk off the stair at room_9's south
      door and on into the room across x 7.7 between y −182 and −158: one floor, no seam, sliver
      or step. Not looked at in the 3D viewer for this section.
- [ ] **[MUST] t2: a Bridge's slot keeps off a doorway** — Case t2, room_5 (centre (130.3,
      −78.3), 83 × 84 u, floor −112.5). Before the fix, `corr_8` (room_0 → room_2, a straight
      41 u at y −65.2, 0 to −10.5 u high) was a Bridge over room_5, its slot cut in room_5's
      ceiling over the west end. `corr_12` (room_5 → room_9, a Bridge over room_22) has its west
      door at (90.7, −54.4), and that door's 2 u piece into room_5 stood in the slot's Throat:
      "wall across throat (88.7, −83.2, 108.8, −47.2)". Now no Bridge's slot may meet a door's
      piece on the bridged room's walls: `corr_8` is no longer a Bridge and runs as it did, with
      no slot in room_5's ceiling. `corr_4`'s Bridge over room_16 is dropped by the same rule;
      `corr_12` keeps its Bridge over room_22. 34,148 vertices (31,537 at `b70c5fc`, with Bridges
      `corr_16` and `corr_23` instead). In 3D, stand in room_5's west end by `corr_12`'s door:
      the ceiling should be whole, and the doorway clear, with no wall stub across the way in.
      Not looked at in the 3D viewer for this section.
- [ ] **[MUST] t3: decor clears a dais's way** — Case t3, room_12, a flooded gallery (centre
      (535.4, −17.9), 55 × 63 u, floor −218.0) with a dais (5.1 u) over its middle and a door S
      at x 511 to 529. Before the fix, `decor_0062` (crystals, (548.6, −25.7)) and `decor_0068`
      (a stalactite, (519.0, −14.5)) shut both 8 u ways from door S to the dais's east step at
      (537.5, −17.5), the floor-level spot the gate aims at: "throat_narrow". Decor never checked,
      as it aimed at the dais top. Now it aims where the gate does, and the room has 12 Props:
      the crystal cluster (CRYSTAL4) stands at (546.3, −13.8), and the stalactites hang
      at (533.0, 1.5), (521.0, −32.5), (515.0, −48.5) and (555.0, −34.5). 24,604 vertices (22,672
      at `b70c5fc`, where room_12 is a different room with no dais). In 3D, walk from door S to
      the dais's east step: an 8 u clear way past the Props. Also look at the stalactite at
      (515.0, −48.5), over the door's west half just inside the room: say whether it reads as in
      the way. Not looked at in the 3D viewer for this section.

#### X.7.4 — Built and warren zones unchanged

- [ ] **[MUST] Fortress and warrens byte-identical at 1** — Cases d1 (built fortress, 16 rooms),
      c1 (warren, 12 rooms) and the warren seed 13 build (20 rooms), each at Winding 1, against
      the same builds at `b70c5fc`: every file in each `.eqg` is identical, 209 of 209, 122 of
      122 and 140 of 140, with the zone name masked in lower and upper case (the ZON names its
      TER in capitals). Their vertex counts match too (18,948, 9,810 and 21,622). Only cave
      zones jitter (archive decision 5). As a check that the comparison can tell: case a1 against `b70c5fc` differs in 28
      files.

## Step 27 — Random room placement

> Roadmap step 27 (`zone-generator-random-placement`). At the step 26 look the user asked that
> generated rooms "end up randomly positioned and connected". The plan was to take every Graph
> zone off the lattice. Task 1 tried that for built and hewn dungeons, but no setting kept both
> stock wall runs and hall length, and the user chose to keep built zones on the grid (archive
> decision 2). So two kinds of zone leave the lattice: **cave** Graph dungeons, as since step 26,
> now salted by the build's own seed, and **outdoor dungeons** (Envelope builds). An outdoor
> dungeon's grid score drops from about 0.22 to about 0.09, and its doors are closer together. The
> room nearest the way in is still the entrance room. Every other Graph dungeon (fortress, temple,
> tomb, warren and the rest), classic layouts, cities and wilderness keep their room layout. The
> grown graph doesn't change: the same rooms, the same edges, the same Levels and stairs. (A big
> plan that now fits on a different try is the exception; see case d.) Along the way the step
> fixed these:
> - Decor reads the corridor's wall stubs at a door's edges, and a ceiling Prop's whole plan stays
>   inside its room (task 1).
> - Wall decor checks its whole edge across an outline bend, and a corridor's context counts only
>   the rooms on its own Level (task 3).
> - The outdoor ground raster reads each pixel's own face past the tunnel notch, and a POI keeps a
>   gate sample between a Prop and a wall (task 4).
> - A 30-room outdoor dungeon draws in under a minute again (task 8).
>
> Restart the Server on the merged code first (with `EQ_PATH` pointing at the RoF2 install) and
> check no stale-code banner shows. Then walk the cases in the viewer (http://localhost:5180/).

Build each case in Controls with the seed shown. Cases a, f, w and k use Size **medium** and Decor
**Normal**. The others leave Size and Decor at their defaults (medium, Normal) unless the row says
otherwise. Every case was built through the Server's `/api/generate` (rule planner, no API key,
`EQ_PATH` set) on master `c1dcfb2`. Every build passed the gate and the Format_Checker on the
first build with its seed kept. None was Quality_Degraded, and no seed had to be swapped. The
"before" builds ran the same requests on the code from before the step (`b77d5a9`) on its own
Server. In Y.5, "before the fix" for cases s and p is the gate sweep's own build (no retry),
rerun for this section on `7e5f41d` (task 3 merged, before task 4's fixes). For cases b and u it
is the suite failure recorded in task 3's commit 9208d2b, not rebuilt here. The grid score is `scripts/grid_score.py`'s: the share of
room-centre pairs whose x or y agree within 10 u. Rooms scattered at random score 0.06 to 0.09.

| Case | Zone | Settings | Seed |
|---|---|---|---|
| a | Dungeon | Layout **Graph**, Rooms 12, Theme **Cave**, Verticality **Moderate** (step 26's case a1) | 731402518 |
| o | Outdoor dungeon | Layout **Graph**, Rooms 14, Verticality **Moderate**, no theme | 731402518 |
| t | Outdoor dungeon | Layout **Graph**, Rooms 14, Theme **Temple**, Verticality **Dramatic** | 731402518 |
| f | Dungeon | Layout **Graph**, Rooms 16, Theme **Fortress**, Walls **Built**, Verticality **Moderate** (step 26's case d1); also with Decor **None** | 731402518 |
| w | Dungeon | Layout **Graph**, Rooms 12, Theme **Warren**, Verticality **Moderate** (step 26's case c1); also Rooms 20 at seed 13 | 731402518, 13 |
| k | Dungeon | Layout **Classic**, Rooms 12, Theme **Fortress**, Verticality **Moderate**; also with Decor **None** | 731402518 |
| c | City | defaults | 731402518 |
| b | Outdoor dungeon | Rooms 5, everything else default (the decor suite's pinned build) | 2 |
| u | Outdoor dungeon | Rooms 8, Size **small** (the `outdoor_cave` room recording) | 114 |
| s | Outdoor dungeon | Layout **Graph**, Rooms 17, Verticality **Dramatic** | 1139996531 |
| p | Outdoor dungeon | Layout **Graph**, Rooms 26, Verticality **Dramatic** | 1801994134 |
| d | Outdoor dungeon | Layout **Graph**, Rooms 30, Theme **Corrupted Sanctum**, Verticality **Flat** | 1078956947 |

### Y.1 — A cave, salted by its own seed

Case a. The same 12 rooms and 13 corridors join the same rooms as before. 11 rooms are on Level 0
and room_8 is on Level 1, reached by the stair `corr_10` (room_5 → room_8, 102 u up). Before, the
cave's offsets used a salt shared by every build. Now the build's seed draws them (Requirement 5),
so every centre moves. The before column is step 26's X.7.1 "Now, Winding 0 and 1" layout, built
again here with the same centres.

| Room | Before (`b77d5a9`) | Now |
|---|---|---|
| room_0 (entrance) | (8.3, −1.8) | (22.8, 2.1) |
| room_1 | (181.1, −20.9) | (215.8, −5.8) |
| room_2 | (−14.8, 172.8) | (−133.4, 21.4) |
| room_3 | (−25.3, −200.6) | (24.8, −177.0) |
| room_4 (climax) | (158.7, −235.2) | (196.8, −209.6) |
| room_5 | (369.9, −39.9) | (196.8, 186.9) |
| room_6 | (−218.9, −168.0) | (−184.9, −223.8) |
| room_7 | (−48.4, −370.6) | (0.3, −347.8) |
| room_8 (Level 1) | (403.0, −39.9) | (230.0, 186.9) |
| room_9 | (−392.9, −156.3) | (−368.6, −223.1) |
| room_10 | (−238.5, 22.4) | (−173.7, −395.4) |
| room_11 | (−425.6, 3.8) | (−345.7, −416.0) |

Grid score **0.076** now (5 of 66 pairs), 0.030 before (2 pairs). It is one new random draw, not
a trend: over seeds 2000–2039 the cave's mean is 0.065 (0.066 before; task 1). The 5 pairs:
room_5 / room_8 (the stacked stair pair, never offset), room_0 / room_1 and room_6 / room_9 in y,
and room_0 / room_3 and room_4 / room_5 in x, each of those four at least 179 u apart. The rooms now span
599 × 603 u (829 × 543 before). The median corridor is 121.0 u door to door at both. 10,820
vertices (10,800 before).

- [ ] **[MUST] Still a cave off the grid** — Case a: look at the map and fly over the cave. No three
      rooms should line up. room_5 and room_8 share a row at y 186.9, as a stacked pair always
      does. Say whether it still reads as chambers placed by hand. Not looked at in the 3D
      viewer for this section.
- [ ] **[MUST] The stair and the Level** — Case a: walk room_5 → `corr_10` → room_8 (102 u up).
      The stair should land flush in both rooms. Not looked at in the 3D viewer for this section.

### Y.2 — Outdoor dungeons off the lattice

Cases o and t. Each keeps its 14 rooms, its 15 edges between the same rooms, its Levels and its
stairs. Only the positions inside the hill change. The Tunnel still comes in on the entrance
room's wall from the way in, and that room is still the nearest top-Level room to the mouth.

**Case o** (no theme, Moderate). room_2, room_5 (climax) and room_11 are on Level −1, reached by
two stairs, `corr_1` (room_1 → room_2) and `corr_8` (room_8 → room_11), each 102 u down.

| Room | Before (`b77d5a9`) | Now |
|---|---|---|
| room_0 (entrance) | (−79.8, −148.1) | (−160.1, −141.2) |
| room_1 | (−69.3, −29.8) | (−125.9, −29.6) |
| room_2 (Level −1) | (−109.6, −29.8) | (−166.2, −29.6) |
| room_3 | (70.3, −32.8) | (−166.8, 82.8) |
| room_4 | (−58.2, 95.8) | (−20.2, −38.8) |
| room_5 (Level −1, climax) | (−240.4, −29.8) | (−118.6, 108.5) |
| room_6 | (70.9, 105.8) | (−2.0, 106.5) |
| room_7 | (64.9, 226.7) | (34.5, 227.1) |
| room_8 | (208.0, 116.8) | (117.5, 54.7) |
| room_9 | (80.0, 341.0) | (3.3, 333.4) |
| room_10 | (−64.9, 228.7) | (154.8, 206.4) |
| room_11 (Level −1) | (208.0, 76.9) | (154.2, 54.7) |
| room_12 | (4.4, 355.5) | (96.3, 363.2) |
| room_13 | (−84.3, 347.1) | (199.0, 326.0) |

Grid score **0.132** now (12 of 91 pairs), **0.209** before (19). This seed sits above the
outdoor mean, which is 0.090 over seeds 2000–2039 (0.221 before; task 8). Two of its 12 pairs
are the stair pairs (room_1 / room_2 and room_8 / room_11), which are never offset. The other
ten agree by chance, 106 to 227 u apart. Before, a row of four ran at y −30 to −33
(room_1, room_2, room_3, room_5) and a column of four at x 65 to 80 (room_3, room_6, room_7, room_9). The
entrance is room_0 now and before. The Tunnel's mouth is at (−160.0, −220.0) on its S wall (it was
at (−80.0, −220.0)), 79 u from its centre. The next-nearest top-Level room is room_1, at 193 u.
The median corridor is **48.7 u** door to door (65.2 before). `corr_13` (room_3 → room_6) is now a
Bridge over room_5; before, no corridor bridged. 15,141 vertices (14,449 before).

**Case t** (Temple, Dramatic). room_7 and room_11 (climax) are on Level −1. The stair `corr_5`
(room_7 → room_4) runs 102 u up.

| Room | Before (`b77d5a9`) | Now |
|---|---|---|
| room_0 (entrance) | (149.7, −79.9) | (−73.2, −138.6) |
| room_1 | (146.6, 52.4) | (−131.8, −11.2) |
| room_2 | (274.2, 55.6) | (−269.9, 1.1) |
| room_3 | (145.9, 169.9) | (−159.3, 122.0) |
| room_4 | (−10.6, 58.1) | (12.9, 50.9) |
| room_5 | (145.9, 273.2) | (−186.6, 237.9) |
| room_6 | (−163.3, 61.4) | (135.5, 101.2) |
| room_7 (Level −1) | (−10.6, 13.3) | (15.4, 6.2) |
| room_8 | (−25.1, 201.5) | (−0.3, 202.1) |
| room_9 | (−167.6, −48.8) | (240.2, 73.5) |
| room_10 | (−172.6, 200.1) | (146.0, 234.8) |
| room_11 (Level −1, climax) | (−130.5, 13.3) | (141.0, 60.5) |
| room_12 | (−25.5, 325.8) | (−12.5, 324.5) |
| room_13 | (−155.6, 327.8) | (142.7, 359.0) |

Grid score **0.099** now (9 of 91 pairs), **0.231** before (21). Before, rooms stood in a column
at x 146 to 150 (room_0, room_1, room_3, room_5) and rows at y 52 to 61 (room_1, room_2, room_4,
room_6). Now room_6, room_10, room_11 and room_13 stand at x 135.5 to 146.0 (five of the nine pairs),
y 60 to 359. The entrance is room_0 now and before: the mouth at (−80.0, −220.0) on
its S wall, 82 u away. The next-nearest top-Level room is room_1, at 215 u. The median corridor is
**54.5 u** door to door (58.9 before). Before, `corr_0` (room_6 → room_4) bridged room_11; now no
corridor bridges. 12,436 vertices (12,162 before).

- [ ] **[MUST] The grid is gone** — Cases o and t: look at the map and fly over each hill. Before,
      rooms stood in rows and columns (see above). Now only the stair pairs share a line by
      design. In case t, say whether room_6, room_10, room_11 and room_13 (x 135.5 to 146.0)
      read as a column. Not looked at in the 3D viewer for this section.
- [ ] **[MUST] The way in faces the entrance room** — Cases o and t: walk in from the outdoor
      Spawn through the Tunnel. Each time it should open on room_0's S wall, with no other room
      nearer the mouth. Not looked at in the 3D viewer for this section.
- [ ] **[MUST] Stairs and Levels intact** — Case o: walk room_1 → `corr_1` → room_2 and room_8 →
      `corr_8` → room_11 (102 u down each). Case t: walk room_7 → `corr_5` → room_4 (102 u up).
      Each stair should land flush, and no room should poke out of the hill or through another
      Level's room. In case o, cross `corr_13` over room_5 (the climax): the Bridge's floor
      should be whole and room_5's ceiling slot clear. Not looked at in the 3D viewer for this
      section.
- [ ] **[SHOULD] Shorter halls** — Cases o and t: door to door is shorter now (median 48.7 and
      54.5 u, from 65.2 and 58.9), because facing doors run straight and the fit to the hill is
      smaller. Say whether the halls feel too short. Hall length is a later step. Not looked at
      in the 3D viewer for this section.

### Y.3 — Built and warren Graph dungeons keep the lattice

- [ ] **[MUST] Fortress: the same layout** — Case f against `b77d5a9`: the spec is identical,
      zone name aside, with the same 16 rooms, room_0 at (−6.2, −17.7), the climax room_5 at
      (475.0, −17.0), 4 stairs, and grid score **0.158** at both (19 of 120 pairs, on the
      lattice). With Decor **None** every file in the `.eqg` is identical (5 of 5). With Decor
      **Normal** 208 of the 217 files are the same, and the Props differ in room_1 (the
      barracks, redrawn), room_4 (a brazier moved 2.9 u), room_5 and room_7 (a banner moved
      each) and `corr_13` (a torch moved). Building at each commit of the step places those
      moves at task 1's decor fixes (the door stubs, 8ed510d, and the ceiling Prop's plan,
      4a1d27a) and at 9208d2b (wall Props read along their edge, and corridor contexts per
      Level). These are the general fixes Requirement 6 allows. 18,948 vertices at both. In 3D,
      the fortress should look as it did in step 26 (room_5's banner now hangs at (430.6, 21.6)
      and room_7's at (277.2, 345.9)). Not looked at in the 3D viewer for this section.
- [ ] **[MUST] Warrens byte-identical** — Case w against `b77d5a9`, Decor **Normal**: every file is
      identical, 122 of 122 (12 rooms) and 140 of 140 (seed 13, 20 rooms). Grid score 0.288 and
      0.100, the same at both. 9,810 and 21,622 vertices.

### Y.4 — Classic and city

- [ ] **[MUST] City byte-identical** — Case c against `b77d5a9`: every file in the `.eqg` is
      identical, 65 of 65. 456 vertices.
- [ ] **[MUST] Classic fortress: the same layout, decor moved by two fixes** — Case k against
      `b77d5a9`: the spec is identical, zone name aside, with the same 12 rooms (room_7 the
      entrance at (209.6, −92.7), room_6 the climax at (−102.0, −208.8)), and grid score 0.121
      at both. With Decor **None** every file is identical (5 of 5). With Decor **Normal** 87 of
      95 files are the same, and the Props differ in room_7 (the gatehouse: a chain and two
      rocks) and room_8 (the prison cell: a chain, buckets, a torch, rocks). Building at each
      commit places the moves at 4a1d27a (a ceiling Prop's whole plan inside the room) and
      9208d2b. **Requirement 6 says classic
      zones keep their bytes**, and its byte check (`tasks.md`) passes because the pinned
      classic goldens don't hit these rooms. Decide whether a general decor fix may move a
      decorated classic zone, as it may a built Graph one. In 3D, look at room_8's chain at
      (−71.3, 188.5) and room_7's at (190.3, −73.3): each should hang wholly inside its room.
      Not looked at in the 3D viewer for this section.

### Y.5 — The fixes found on the way

- [ ] **[MUST] A banner across an outline bend** — Case b, room_4: a deep room with an outline
      wall (centre (274.9, 49.8), floor −63.0, 110 × 108 u) on Level −1. Before the fix (9b95ac0), the 20.5 u banner stood at the end of a short outline
      wall whose next stretch bends 105°, and 8.6 u of it hung behind the wall
      (`test_banners_show_in_the_glb_in_front_of_their_wall` failed). Decor now reads a wall
      Prop's edges every 1 u, so that spot is refused. room_4's banner hangs at (326.4, 36.2),
      beside the throne at (280.7, 15.6). Grid score 0.200 (2 of 10 pairs; 0.600 before). 7,046
      vertices. In 3D, look at room_4's banner from the room: all of its cloth should be in front
      of the wall, with no corner through the bend. Not looked at in the 3D viewer for this
      section.
- [ ] **[MUST] A corridor under another Level's room** — Case u (the `outdoor_cave` recording),
      `corr_2`: room_5 → room_3 on Level −1, from (74.4, −5.3) to (74.4, 17.7), floor −96.1. It
      runs under room_1 (Level 0, centre (39.0, 52.9), 118 × 120 u, floor 5.9). Room context
      used to drop every corridor cell inside any room's plan box as that room's doorway,
      whatever its Level, so `corr_2` had no floor to dress
      (`test_contexts_are_consistent` failed on the re-recorded corpus). Now only rooms at the
      corridor's heights count. `corr_2` carries no Props in this build, so the fix shows only in
      the context. 10,161 vertices. In 3D, walk room_5 → `corr_2` → room_3 under room_1: one
      continuous floor the whole way. Not looked at in the 3D
      viewer for this section.
- [ ] **[MUST] The shrine altar** — Case s. Before the fix (`7e5f41d`, the gate sweep's build), it
      failed the gate: "bowl: poi_unreached: site0:shrine altar: at (438, 470) is not on reached
      ground". The ground raster mapped each pixel to grid triangle 2q / 2q+1, but the Tunnel's
      notch drops one quad's two triangles. So every pixel past the notch read the quad north
      of it, and the altar's pixel read the bowl's rim (a face 414 u tall). Now each pixel reads
      its own face. The shrine Site stands at (448.8, 457.4), with its altar POI at (437.9,
      469.7, −13.8). It passes (20,236 vertices). Grid score **0.066** (0.206 before). In 3D, walk from the outdoor Spawn to the shrine and stand at the
      altar: open ground, no lip or step. Not looked at in the 3D viewer for this section.
- [ ] **[MUST] The treasure POI by a wall** — Case p, room_24 (centre (435.7, 19.1), 53 × 49 u,
      floor −5.7, Level 0, up the stair `corr_14` from room_21). Before the fix
      (`7e5f41d`, the gate sweep's build), it failed: "room_24: poi_unreached: treasure: the
      treasure POI at (458, -0, -6) is not on reached floor". An urn by the corner POI left a
      1.7 u strip by the wall. That strip read open on decor's cells but shut on the gate's 2 u
      samples. Decor now also reads the room on the gate's own samples. The treasure POI is at
      (458.3, −0.2), with the chest at (447.3, 2.6) and urns at (453.0, 0.2) and (453.0, 4.9).
      It passes (25,358 vertices). Grid score **0.071** (0.154 before). In 3D, walk to room_24's
      treasure corner: you should reach the POI past the urns, with no squeeze against the wall.
      Not looked at in the 3D viewer for this section.
- [ ] **[SHOULD] A 30-room outdoor dungeon builds in good time** — Case d. Through the Server,
      with each build running alone, the whole generate (draw, build and gate) took **72.0 s**
      now and 128.0 s at `b77d5a9`. Task 8 timed the draw alone (quality_sweep's spec): 103 s at
      `b77d5a9`, 367 s after task 3's Envelope jitter (`7e5f41d`), and 44 s now. Over task 4's
      sample of 27–30 room draws, the p95 is 50 s and the max 97 s, against 627 s and 655 s
      before task 8. The zone is Flat, with no stairs. The plan fits a different try now, so the
      graph isn't the one from before: 30 corridors (35 before). Grid score 0.064 (0.099
      before). The entrance is room_18, with the mouth at (340.0, −40.0) on its E wall, 170 u
      away (the next-nearest room is 200 u). 19,515 vertices (16,537 before). Generate it in
      Controls and say whether the wait feels acceptable. Not looked at in the 3D viewer for
      this section.

### First-look fixes (tasks 9–13)

> At the first look (archive decision 4) the user built case a and said the cave "still seems
> roughly on a grid", expecting rooms that can clump and entrances that come in at angles. The
> same look found that room sizes "feel mostly similar". The cause was that each neighbour moved
> only sideways along its N/S/E/W wall, doors were cut square, and every room was one class side
> ±15%, near-square. Task 10 places cave rooms at any bearing, with corridors that meet the wall
> at an angle (caves only, the user's choice). Task 11 draws room sides, aspects and areas from
> stock's spread for every kind of zone, up to 26 H (156 u; 48 u is the floor). Built and warren
> Graph dungeons still keep the lattice, and only caves get angled entries.

The cases below reuse a, f, o and c from the table above, with the same controls and seed
731402518. Every "now" build ran through `/api/generate` on a Server started for this section
(rule planner, no API key, `EQ_PATH` = `F:\everquest_rof2`, master `e741a86`, after task 12).
Each passed the gate and the Format_Checker on its first build (validated, 1 attempt, not
Quality_Degraded, no warnings). The "before" column is `71fbd06`, the merge just before task 10.
It was drawn with `plan_to_spec` on a detached checkout of that commit with the same controls
and seed, not built through a Server. On master, `plan_to_spec` gives the same rooms as the
Server's `.spec.json` in all four cases, and the before cave and fortress match Y.1's and Y.3's
"now" layouts. The measures are `scripts/grid_score.py`'s `spec_shape` (task 9):

- **Bearing**: each corridor's centre-to-centre bearing, as its offset from the nearest axis
  (0–45°). "ax10" is the share within 10° of an axis. Stock caves have 0.28, and about 0.33 of
  their edges are 30–45° off.
- **Nearest neighbour**: each room's nearest other centre, in 3D. The spread is given as its CV
  and as min/median/max over the zone's median room side. Stock caves have CV 0.38 and a min of 0.63.
- **Entry angle**: the angle between a corridor's first leg and its wall's outward normal, at
  both ends (0° is square).
- **Size**: the side is √(w·d), and the zone's median side is also given in H (6 u). The area CV
  and max/min are per zone. The aspect is long/short. Stock has an area CV of 0.8–0.95, a
  max/min of 9–16, and an aspect p50 of about 1.25 with 0.25–0.30 of rooms over 1.5.

| Case | Build (now) | Gate | Vertices | Time |
|---|---|---|---|---|
| a, cave | `gen_1795604008_9f8d04` | passes, 1 attempt, format passed | 10,787 | 9.2 s |
| f, fortress | `gen_1795604018_5b92e7` | passes, 1 attempt, format passed | 20,886 | 13.2 s |
| o, outdoor dungeon | `gen_1795604031_d2282e` | passes, 1 attempt, format passed | 13,614 | 8.7 s |
| c, city | `gen_1795604039_04d038` | passes, 1 attempt, format passed | 632 | 3.3 s |

#### Z.1 — The first-look cave (case a)

Dungeon, Layout **Graph**, Rooms **12**, Theme **Cave**, Verticality **Moderate**, Size
**medium**, Decor **Normal**, seed **731402518**. It has the same 13 corridors between the same
rooms. The stair `corr_10` (room_5 → room_8, 102 u up) is unchanged, and room_8 is still the one
Level 1 room. room_0 is still the entrance and room_4 the climax.

| Room | Before (`71fbd06`) centre, w × d | Now centre, w × d |
|---|---|---|
| room_0 (entrance) | (22.8, 2.1), 59.6 × 65.5 | (28.8, 1.2), 48 × 67 |
| room_1 | (215.8, −5.8), 61.4 × 63.3 | (173.8, −0.4), 64.2 × 48 |
| room_2 | (−133.4, 21.4), 53 × 54.7 | (34.8, 93.0), 48 × 66 |
| room_3 (cavern) | (24.8, −177.0), 79.6 × 94.4 | (−88.6, −118.8), **156 × 98.6** |
| room_4 (climax) | (196.8, −209.6), 99.7 × 104.1 | (80.7, −198.1), 98.4 × 78.2 |
| room_5 | (196.8, 186.9), 74.1 × 67 | (389.8, 87.1), 48 × 81.6 |
| room_6 | (−184.9, −223.8), 68.1 × 63.1 | (−272.1, −361.9), 106.6 × 48 |
| room_7 | (0.3, −347.8), 52.1 × 56.5 | (−210.0, −179.5), 48 × 55.8 |
| room_8 (Level 1) | (230.0, 186.9), 58.5 × 48 | (413.8, 87.1), 48 × 54.4 |
| room_9 | (−368.6, −223.1), 51.9 × 52.9 | (−289.8, −629.5), 48 × 90.2 |
| room_10 | (−173.7, −395.4), 59.9 × 54.1 | (−24.2, −380.1), 48 × 63.4 |
| room_11 | (−345.7, −416.0), 68.3 × 76.1 | (−109.5, −527.1), 48 × 61.3 |

| Measure | Before | Now | Stock caves / task 9 target |
|---|---|---|---|
| Edge bearings within 10° of an axis | **0.85** (11 of 13; max offset 12.6°) | **0.38** (5 of 13) | 0.28 / ≤ 0.35 |
| Edge bearings 30–45° off | 0 | **0.23** (3 of 13: 30°, 37°, 44°) | 0.33 / ≥ 0.25 |
| Nearest-neighbour CV | 0.16 | **0.27** | 0.38 / ≥ 0.30 |
| Nearest neighbour min/med/max ÷ median side | 1.72 / 2.76 / 3.10 | 1.64 / 2.50 / 3.67 | min 0.63 / ≤ 1.0 |
| Nearest neighbour, u | 107–194 (closest: the stair pair) | **93–208** (closest: room_0 / room_2) | |
| Entry angle p50 / p90 / share over 20° | 0° / 0° / 0 | **29.9° / 40.0° / 0.69** | ≥ 15° / ≤ 55° / ≥ 0.30 |
| Median side | 62.4 u (10.4 H) | 56.5 u (9.4 H) | 8.5–15 H |
| Side min / max, max ÷ median | 52.4 / 101.9 u, 1.63 | 51.1 / 124.0 u, **2.20** | 2.35 |
| Area CV, max/min | 0.48, 3.8 | **0.73, 5.9** | 0.80, 8.6 |
| Aspect p50 / max / share over 1.5 | 1.10 / 1.22 / 0 | **1.37 / 2.22 / 0.33** | 1.31 / 1.93 / 0.32 |
| Grid score | 0.076 | 0.076 | |

The task 9 targets are bars over seeds 2000–2039, not for one seed. This seed meets the entry and
aspect bars, and comes close on the bearing ones (0.38 and 0.23). Clumping is the weak spot. The
spread is wider (CV 0.27, rooms 93 to 208 u from their nearest), but the closest pair (room_0 and
room_2, 92.7 u) is still 1.64 median sides apart, against stock's 0.63. Rooms opening straight
into each other remain a follow-up. Nine of the 13 corridors now meet their walls at 25–40°. The
ones still square are `corr_6` (room_2 → room_0), `corr_9` (room_3 → room_7), the stair `corr_10`
(0°) and `corr_5` (6°). room_3 (a 156 × 98.6 cavern, the 26 H cap) now has 5.9× the floor of
room_8 (48 × 54.4). Before, the largest room had 3.8× the floor of the smallest.

- [ ] **[MUST] No longer a grid** — Case a: look at the map, then fly over the cave. Edges
      should run at many bearings, not mostly N/S/E/W. room_5 and room_8 (the stair pair)
      still share y 87.1 by design. Say whether it reads as chambers placed by hand now.
      Not looked at in the 3D viewer for this section.
- [ ] **[MUST] Entrances at an angle** — Case a: walk `corr_3` (room_6 → room_3), `corr_7`
      (room_4 → room_3) and `corr_8` (room_0 → room_3), each about 40° off square, and `corr_0`
      (room_1 → room_4, 32°). Each opening should be cut where the tunnel meets the rock, with no
      sliver of wall across the doorway, no gap beside it and a flush floor at both ends. Also
      walk `corr_5` (room_6 → room_10) and `corr_11` (room_9 → room_11), which carry seams. Not
      looked at in the 3D viewer for this section.
- [ ] **[MUST] Clumped and spread rooms** — Case a: room_0 and room_2 sit 92.7 u apart, while
      room_9 is 208 u from its nearest (room_11). Say whether the cave now has tight clusters and
      open gaps, or whether it should clump harder (stock's closest pairs are much closer).
      Not looked at in the 3D viewer for this section.
- [ ] **[MUST] Small grottos beside a big cavern** — Case a: stand in room_3 (156 × 98.6 u),
      then in room_7 (48 × 55.8) and room_2 (48 × 66). The sizes should read clearly different,
      and room_6 (106.6 × 48) and room_9 (48 × 90.2) should read as long galleries. Not looked at
      in the 3D viewer for this section.
- [ ] **[MUST] Stair and Level intact** — Case a: walk room_5 → `corr_10` → room_8 (102 u up).
      The stair should land flush in both rooms. Not looked at in the 3D viewer for this section.

#### Z.2 — Size variance: a fortress, an outdoor dungeon and a city

These keep their square doors (entry angles 0–7° before and now). Only room sizes and shapes
change, and so does the placement that fits them.

| Case | Median side | Side min–max (max ÷ median) | Area CV | Area max/min | Aspect p50 / max / over 1.5 |
|---|---|---|---|---|---|
| f, before | 78.8 u (13.1 H) | 55.4–118.8 u (1.51) | 0.50 | 4.6 | 1.10 / 1.22 / 0 |
| f, now | 106.0 u (17.7 H) | 51.8–156.0 u (1.47) | **0.62** | **9.1** | 1.29 / 1.77 / 0.31 |
| o, before | 72.3 u (12.0 H) | 55.6–117.5 u (1.63) | 0.48 | 4.5 | 1.08 / 1.24 / 0 |
| o, now | 63.5 u (10.6 H) | 48.1–118.8 u (1.87) | **0.61** | **6.1** | 1.26 / 2.22 / 0.21 |
| c, before | 86.1 u (14.4 H) | 52.3–110.7 u (1.28) | 0.44 | 4.5 | 1.23 / 1.39 / 0 |
| c, now | 96.3 u (16.0 H) | 58.8–146.7 u (1.52) | **0.66** | **6.2** | 1.20 / 1.50 / 0 |

Decision 7's per-kind bars (built and city: area CV ≥ 0.70, max/min ≥ 8; outdoor: ≥ 0.60 and
≥ 6.5) are medians over many seeds. One zone can fall either side. Here the fortress clears
max/min but not CV, the outdoor dungeon clears CV and falls just short on max/min, and the
5-room city is under both.

**Case f** (Dungeon, Layout **Graph**, Rooms **16**, Theme **Fortress**, Walls **Built**,
Verticality **Moderate**, Size medium, Decor Normal). It has the same 17 corridors between the
same rooms and the same 4 stairs: `corr_6` (room_3 → room_2), `corr_8` (room_7 → room_10),
`corr_9` (room_10 → room_9) and `corr_10` (room_8 → room_11), each 102 u. It stays on the lattice
(grid 0.125, 0.158 before; ax10 0.76 at both), but the layout is redrawn around the new sizes:
room_0 (the gatehouse) moves from (−6.2, −17.7) to (776.4, 29.3), and the climax room_5 (the
throne room) from (475.0, −17.0), 120 × 98, to (578.1, 83.7), 156 × 131.7. The biggest rooms
are room_2 (an armory hub) and room_15 (a storeroom), each 156 × 156. The smallest are room_11
(a storeroom, 55.9 × 48), room_13 (a guard post, 48 × 71.2) and room_6 (barracks, 48 × 78.6).
Six of the 16 rooms touch the 156 u cap on one side and four the 48 u floor. The median side
(17.7 H) is above the class's usual 11–13.5 H at this seed.

- [ ] **[MUST] Halls and side rooms** — Case f: walk room_0 → room_1 → room_2 → room_4. Say
      whether the big halls (room_2, room_5, room_15) and the small rooms (room_11, room_13)
      read as a fortress's mix, or whether a 156 × 156 storeroom (room_15) looks wrong for its
      type. Also say whether the fortress as a whole feels too big now. Not looked at in the 3D
      viewer for this section.
- [ ] **[MUST] Doorways flush, stairs intact** — Case f: walk the 4 stairs (`corr_6`, `corr_8`,
      `corr_9`, `corr_10`). Each should land flush, with built walls whole around every door,
      including where a long wall (room_9, 89.3 × 156) or a narrow room (room_10, 80.1 × 48)
      takes a door. Not looked at in the 3D viewer for this section.

**Case o** (Outdoor dungeon, Layout **Graph**, Rooms **14**, Verticality **Moderate**, no
theme). Grid score 0.077 (0.132 before), ax10 0.27 (0.40 before). room_0 is still the entrance,
with the Tunnel's mouth at (−160.0, −180.0) on its S wall. room_2, room_5 (climax) and room_11
are still on Level −1. 14 of the 15 edges are the same. The stair room_1 → room_2 is gone:
room_2 is now reached by `corr_13` from room_3 (90.5 u down), next to `corr_6` (room_8 →
room_11, 102 u down). The biggest room is room_3 (132 × 107), and room_13 (102.3 × 101) is
close behind. The smallest is room_12 (48.2 × 48). room_6 (106.6 × 48) is a long hall, and room_5
(62.1 × 105.6) is a long climax.

- [ ] **[MUST] Big and small under the hill** — Case o: walk in from the outdoor Spawn through
      the Tunnel to room_0, then room_1 → room_3 → `corr_13` → room_2 → room_5. Say whether
      room_3 and room_13 read as big halls and room_12 and room_4 (60.4 × 48) as small ones. No
      room should poke out of the hill or through another Level's room. Not looked at in the 3D
      viewer for this section.
- [ ] **[MUST] Stairs and Levels intact** — Case o: walk `corr_13` (room_3 → room_2, 90.5 u
      down) and `corr_6` (room_8 → room_11, 102 u down). Each should land flush. Not looked at
      in the 3D viewer for this section.

**Case c** (City, defaults: 5 rooms). The layout is redrawn. The hub is now room_3 (156 ×
137.9, the 26 H cap) instead of room_4. The entrance is room_2 (111.6 × 121.2) and the climax
room_4 (87.5 × 105.9). The smallest is room_1, a dead end (48 × 72). `corr_2` (room_1 → room_3)
climbs 19.9 u. 632 vertices (456 at Y.4).

- [ ] **[SHOULD] A city of unequal blocks** — Case c: walk every room. room_3 should read as the
      big central space and room_1 as a small side court. Check that `corr_2`'s 19.9 u climb is a
      walkable ramp that lands flush. Not looked at in the 3D viewer for this section.

## Step 29 — Cave clumps

> Roadmap step 29 (`zone-generator-cave-clumps`). At step 27's first look the user said "i would
> expect the potential for rooms to clump". In stock caves about 0.30 of the edges join two
> chambers directly, with no passage between them. Ours always had a corridor, and the closest
> rooms stood 1.4–1.6 median sides apart (stock 0.63). Now about a quarter of a cave's edges are
> **throats**: the two rooms stand 8 u wall to wall with their doors in line, so the corridor
> between them is a straight 12 u door to door (archive decision 2). A throat is an ordinary
> level corridor, never a stair or a Bridge. Caves only: built, hewn, warren, outdoor, classic,
> city and wilderness builds keep their bytes. The step also made a 30-room cave draw faster
> (3.94 s to 3.21 s, the same placements; decision 3), and fixed one decor case the throats
> exposed (task 4).
>
> Restart the Server on the merged code first (with `EQ_PATH` pointing at the RoF2 install) and
> check no stale-code banner shows. Then walk the cases in the viewer (http://localhost:5180/).

Every "now" build ran through `/api/generate` (rule planner, no API key, `EQ_PATH` =
`F:\everquest_rof2`, branch `agent/clumps-5` at `4b7154f`, task 4 merged). Each passed the gate
and the Format_Checker on its first build (validated, 1 attempt, no warnings). The "before" column
is step 27's Z.1 "Now" layout. Task 1 kept every placement float-equal, and task 3's "before" row
for this seed matches Z.1's measures. It was not rebuilt for this section. The measures are
`scripts/grid_score.py --shapes` (see Z.1 for what each one means). "thrt" is the share of edges
whose corridor is no longer than its width door to door. The entry angle now reads only
non-throat corridor ends, because a throat's doors face square by design (decision 4).

| Case | Zone | Settings | Seed | Build (now) | Vertices |
|---|---|---|---|---|---|
| a | Dungeon | Layout **Graph**, Rooms **12**, Theme **Cave**, Verticality **Moderate**, Size **medium**, Decor **Normal** (step 27's case a, Z.1) | 731402518 | `gen_1795652894_48a5b1` (8.5 s) | 10,928 |
| h1 | Dungeon | Layout **Graph**, Rooms **11**, Theme **Cave**, Verticality **Dramatic**, Size medium, Decor Normal | 154876844 | `gen_1795653000_be2ea2` | 16,490 |
| h2 | Dungeon | Layout **Graph**, Rooms **17**, Theme **Cave**, Verticality **Dramatic**, Size medium, Decor Normal | 500150329 | `gen_1795653034_9985ae` | 22,740 |

### C.1 — The first-look cave (case a)

The same 12 rooms at the same sizes, and the same 13 corridors between the same rooms. room_0 is
still the entrance and room_4 the climax. The stair `corr_10` (room_5 → room_8, 102 u up) is
unchanged, and room_8 is still the one Level 1 room. The layout is redrawn around the throats, so
every centre moves.

| Room | Before (Z.1 "Now") | Now |
|---|---|---|
| room_0 (entrance) | (28.8, 1.2) | (−1.9, 7.0) |
| room_1 | (173.8, −0.4) | (−66.0, 20.5) |
| room_2 | (34.8, 93.0) | (54.1, 21.5) |
| room_3 (cavern) | (−88.6, −118.8) | (79.4, −210.8) |
| room_4 (climax) | (80.7, −198.1) | (−197.2, −172.1) |
| room_5 | (389.8, 87.1) | (−154.5, 253.4) |
| room_6 | (−272.1, −361.9) | (383.6, −420.9) |
| room_7 | (−210.0, −179.5) | (117.1, −296.0) |
| room_8 (Level 1) | (413.8, 87.1) | (−178.5, 253.4) |
| room_9 | (−289.8, −629.5) | (583.2, −451.3) |
| room_10 | (−24.2, −380.1) | (481.8, −173.8) |
| room_11 | (−109.5, −527.1) | (713.9, −247.1) |

**Three throats** (3 of 13 edges, 0.23), each level, 0 steps, no Bridge, 18 u wide:

| Corridor | Rooms | Walls 8 u apart | Doors (door to door) | Floor | Bearing off axis |
|---|---|---|---|---|---|
| `corr_1` | room_1 → room_0 | room_1's E at x −33.9, room_0's W at x −25.9 | (−35.9, 18.5) → (−23.9, 18.5), **12.0 u** | 0.0 | 11.9° |
| `corr_6` | room_2 → room_0 | room_2's W at x 30.1, room_0's E at x 22.1 | (32.1, 14.5) → (20.1, 14.5), **12.0 u** | 0.0 | 14.5° |
| `corr_9` | room_3 → room_7 | room_3's S at y −260.1, room_7's N at y −268.1 | (117.1, −258.1) → (117.1, −270.1), **12.0 u** | 14.0 | 23.9° |

So room_1, room_0 and room_2 make one clump of three round the entrance, room_0 opening W and E,
and room_7 (a 48 × 55.8 collapsed gallery) opens off the S wall of room_3 (the 156 × 98.6
cavern). The other ten corridors run 97.6–288.2 u door to door. The nearest pair is room_0 /
room_2, **57.8 u** centre to centre (two 48 u wide rooms), 1.02 median sides (the median side is
56.5 u). Next are room_0 / room_1 (65.5 u, 1.16) and room_3 / room_7 (93.2 u, 1.65). The farthest
from its nearest is room_11, 244 u from room_10 (4.32).

| Measure | Before (task 3's row, = Z.1) | Now | Bar (requirements 2, 3) |
|---|---|---|---|
| Grid score | 0.076 | **0.045** | ≤ 0.10 |
| Edge bearings within 10° of an axis | 0.38 | **0.23** | ≤ 0.35 |
| Nearest-neighbour CV | 0.27 | **0.51** | ≥ 0.30 |
| Nearest neighbour min / med / max ÷ median side | 1.64 / 2.50 / 3.67 | **1.02** / 1.85 / 4.32 | min ≤ 1.0 |
| Entry angle p50 (non-throat ends) / p90 / share over 20° | 30° / 40° / 0.69 | 25° / 40° / 0.80 | p50 ≥ 15° |
| Throat share | 0 | **0.23** (3 of 13) | 0.20–0.35 |
| Area CV, max/min; aspect p50 | 0.73, 5.9; 1.37 | 0.73, 5.9; 1.37 | |

Over cave seeds 2000–2039 (task 3's commit 293d9cc, `plan_to_spec`, not built here):

| Measure | Before | Now | Bar |
|---|---|---|---|
| Grid score | 0.044 | 0.053 | ≤ 0.10 |
| Within 10° of an axis | 0.27 | 0.29 | ≤ 0.35 |
| Nearest-neighbour CV | 0.30 | **0.46** | ≥ 0.30 |
| Nearest neighbour min ÷ median side | 1.36 | **0.95** | ≤ 1.0 (stock 0.63) |
| Entry p50, non-throat ends (all ends) | 18° | 21.1° (0°) | ≥ 15° |
| Throat share | 0.00 | **0.24** | 0.20–0.35 (stock 0.30) |

Entry p50 over all ends reads 0° over the 40 seeds: a quarter of the ends are throats (square by
design), on top of the ~45% already square (stairs, bent and short corridors). Over the
non-throat ends it is 21.1°.

- [ ] **[MUST] Each throat flush and walkable** — Case a: walk room_1 → `corr_1` → room_0 →
      `corr_6` → room_2, then room_3 → `corr_9` → room_7. Each throat should be a short, level
      12 u step from one room into the next: the floor flush at both doors, no lip, no gap, and
      the two doors in line (`corr_1` along y 18.5, `corr_6` along y 14.5, `corr_9` along x
      117.1). Not looked at in the 3D viewer for this section.
- [ ] **[MUST] No wall sliver or seam between abutting rooms** — Case a: at each throat, look
      along the 8 u of rock between the two rooms' walls (above, to the sides of the opening, and
      from the far side of each room). It should read as one solid wall, with no thin sliver, no
      crack you can see through, and no open seam between the two room shells. Not looked at in
      the 3D viewer for this section.
- [ ] **[MUST] Clumps read as one cave, not a grid** — Case a: look at the map, then fly over.
      room_1, room_0 and room_2 sit almost in a row (y 20.5, 7.0, 21.5, bearings 12° and 14.5°
      off the x axis). Say whether the clump reads as one cave opening on itself or as three
      boxes in a line, and whether room_7 reads as a side chamber of room_3. Also say whether the
      cave as a whole clumps enough now (stock's closest pairs are closer still). Not looked at in
      the 3D viewer for this section.
- [ ] **[MUST] Non-throat corridors still angled** — Case a: walk `corr_0` (room_1 → room_4),
      `corr_3` (room_6 → room_3), `corr_7` (room_4 → room_3) and `corr_8` (room_0 → room_3). They
      should still meet their walls at an angle (p50 25°, p90 40°), each opening cut where the
      tunnel meets the rock, with no sliver across the doorway and a flush floor at both ends.
      Also walk the three that wind (`corr_5`, `corr_11`, `corr_12`). Not looked at in the 3D
      viewer for this section.
- [ ] **[MUST] Stair and Level intact** — Case a: walk room_5 → `corr_10` → room_8 (102 u up).
      The stair should land flush in both rooms. Not looked at in the 3D viewer for this section.

### C.2 — A boulder by the middle of a room (task 4's fix, cases h1 and h2)

Task 4's gate sweep found two cave rooms, neither of them on a throat, that failed the gate's
`throat_narrow` at both doors on task 3's code (`acf6f59`): case h1's room_9 and case h2's
room_13. Both now pass on their first build. The gate's clear-width check read the open shell of a boulder
as floor. When a rock Prop (WKROCK8, RUJROCKS704) covered the free samples near the room's middle,
the gate's core moved into the boulder's hollow, which no door reaches, and every door read shut.
Decor now refuses that Prop (a8d84cf). Each room keeps two blocking Props.

- **h1, room_9**: a collapsed gallery at (−483.8, −354.7), floor −190.0, 70.0 × 71.8 u, with three
  boulders.
- **h2, room_13**: a collapsed gallery at (−2.3, 374.2), floor −116.0, 61.0 × 53.8 u, with one
  boulder.

- [ ] **[MUST] Still walkable round the boulder** — Cases h1 and h2: walk into room_9 (h1) and
      room_13 (h2) from each door and cross to the far side, round the boulders and the Props
      near the middle. There should be a clear way everywhere, with no squeeze between a rock
      Prop and a boulder. Also say whether you can see into a boulder's hollow. Not looked at in
      the 3D viewer for this section.

### C.3 — Known, not this step

- **Built stairs moved over the 41 seeds, 135 → 143.** The grammar's edges, Levels and applied
  rules are the same before and after, but where rooms moved, Job B splits edges differently
  and builds more stairs. Case a has the same one stair.
- **This seed's nearest pair is 1.02 median sides**, just over the ≤ 1.0 bar, accepted
  (decision 4). The 40-seed median is 0.95.
- **Cave Graph Flat quality fail share 3.8% → 5.0%** (240 draws per key; 3 more `max_degree`
  Draws on task 3's layout). Every key is within the 5-point band; the other cave keys moved
  0–0.4 points.
- **The gate reads a solid Feature's hollow as floor** (archive follow-up). Decor now steers
  round it (C.2), but the gate's own samples inside a boulder's plan should be skipped.
- **Gate sweep 694/696**, as at step 27. The two failures were on master before step 29 (warren
  graph dramatic 16 seed 565590263, cave classic dramatic 21 seed 1866540615).
- **Cave draw time** is 1.8x pre-step-27 (decision 3); about 2 s of a 30-room draw is outside
  `embed.py`, a follow-up.
- **Nothing in this section was looked at in the 3D viewer.**

## Step 30 — Hall length

> Roadmap step 30 (`zone-generator-hall-length`). At step 26's second look the user said a
> future task should also adjust the length of halls. One scalar, **Hall length**, now scales
> how far apart the rooms stand, and so how long the halls between them run, as a multiple of
> today's: **0.5** (`HALL_MIN`) to **3.0** (`HALL_MAX`), with **1** today's zones. The rooms
> themselves (count, sizes, kinds) never change. Graph layouts (built, warren, cave) stretch the
> corridor run. Classic and city stretch the scatter. Outdoor dungeons stretch the gap between
> rooms after the hill fit. Below 1, rooms still keep a full corridor width apart (Z-corridors
> need it), so only caves shorten all the way: a built Graph reaches about 0.7, classic and city
> about 0.87, and an outdoor dungeon does not shorten at all (archive decisions 2 and 3). Above
> 1, the outdoor hill can't hold much longer halls with full-size rooms, so outdoor dungeons
> stop at about 1.6x however high the slider goes (decision 4). Cave throats stay a 12 u
> straight step at every length. The Controls get a Hall length slider, and the rule planner
> reads words. Task 8 fixed the faults that long and short halls exposed. Two of them were real
> at 1 too (see H.5).
>
> Restart the Server on the merged code first (with `EQ_PATH` pointing at the RoF2 install) and
> check no stale-code banner shows. Then walk the cases in the viewer.

Every build ran through `/api/generate` in Controls mode (rule planner, no API key, `EQ_PATH` =
`F:\everquest_rof2`, branch `agent/halls-5` at master `56a30f7`, with tasks 2, 3, 4 and 8
merged). All nine passed the gate and the Format_Checker on their first build (validated, 1
attempt, no warnings). None needed a retry. Each case uses one seed, **731402518**, at all three
lengths. The measures are `scripts/grid_score.py`'s `hall_lengths` and `throat_ids` on each
build's `.spec.json`: each corridor's length door to door (its path, else its route's
waypoints), throats left out. "Ratio" is the median over the same zone's median at 1.

| Case | Zone | Settings | Seed |
|---|---|---|---|
| f | Dungeon | Layout **Graph**, Rooms **16**, Theme **Fortress**, Walls From theme, Verticality **Moderate**, Size **medium**, Decor **Normal**, Hall length **0.5 / 1 / 3.0** | 731402518 |
| c | Dungeon | Layout **Graph**, Rooms **12**, Theme **Cave**, Verticality **Moderate**, Size **medium**, Decor **Normal**, Hall length **0.5 / 1 / 3.0** (step 29's case a at 1) | 731402518 |
| o | Outdoor dungeon | Rooms **12**, Verticality **Moderate**, Size **medium**, Decor **Normal**, Hall length **0.5 / 1 / 3.0** | 731402518 |
| p | Prompt | "a cave with long tunnels", "a fortress with short corridors", "an outdoor dungeon with long hallways" (rule planner, no API key) | 731402518 |

| Case | Hall length | Build | Time | Vertices | Halls (throats) | Door to door p10 / p50 / p90 (u) | Ratio | Rooms span (u) |
|---|---|---|---|---|---|---|---|---|
| f | 0.5 | `gen_1795678452_a8afd2` | 13.5 s | 21,467 | 17 (0) | 23.0 / 42.9 / 159.3 | **0.72** | 805 × 535 |
| f | 1 | `gen_1795678465_81738e` | 11.5 s | 21,422 | 17 (0) | 37.5 / 59.5 / 204.4 | 1 | 1,087 × 576 |
| f | 3.0 | `gen_1795678477_5c2e67` | 11.2 s | 21,924 | 17 (0) | 123.2 / 190.4 / 227.3 | **3.20** | 1,312 × 950 |
| c | 0.5 | `gen_1795678424_8e114f` | 7.9 s | 9,979 | 10 (3) | 64.9 / 81.2 / 97.7 | **0.45** | 683 × 481 |
| c | 1 | `gen_1795678432_59b9cf` | 5.4 s | 10,928 | 10 (3) | 123.1 / 178.9 / 275.3 | 1 | 984 × 791 |
| c | 3.0 | `gen_1795678437_d5cf92` | 9.0 s | 14,846 | 10 (3) | 451.0 / 618.9 / 806.7 | **3.46** | 1,942 × 2,818 |
| o | 0.5 | `gen_1795678489_0cb1fd` | 8.7 s | 14,078 | 13 (0) | 47.7 / 56.7 / 114.2 | **1.00** | 593 × 508 |
| o | 1 | `gen_1795678498_3a8919` | 7.4 s | 14,078 | 13 (0) | 47.7 / 56.7 / 114.2 | 1 | 593 × 508 |
| o | 3.0 | `gen_1795678505_a8453c` | 9.0 s | 14,923 | 13 (0) | 68.6 / 68.8 / 118.6 | **1.21** | 634 × 527 |

In every case each length builds the same rooms (same ids, kinds and sizes) and the same
corridors between the same rooms. Only where the rooms stand moves, and some floor heights. The
fortress's four U-stairs (`corr_6`, `corr_8`, `corr_9`, `corr_10`, each about 102 u of rise)
set its p90 at 0.5 and 1. A stair's length follows its rise, so the stairs barely move while
the plain halls scale (at 3.0 the plain halls catch up with them): the fortress's plain halls run 23.0–109.9 u at 0.5, 33.1–90.1 u at 1 and
112.1–228.2 u at 3.0. The cave's stair `corr_10` (room_5 → room_8, 102 u up) is 97.6 u door to
door at every length. The cave grows by more than 3x at 3.0 because its run scales affinely,
not in proportion (decision 2). Case c at 1 is step 29's case a (10,928 vertices, the same
three throats).

### H.1 — Long halls at 3.0

- [ ] **[MUST] Long cave tunnels walkable, ramps read as ramps** — Case c at 3.0: walk room_1 →
      `corr_2` → room_5 (**841.2 u**, 186.4 u at 1, 11.5 u up), room_0 → `corr_8` → room_3
      (525.1 u, 14.0 u up) and room_11 → `corr_12` → room_10 (490.2 u, 17.5 u up). Each rise is
      the same as at 1, spread over a much longer run. It should read as a gentle ramp or barely
      a slope, never a step, with flush floors at both doors and headroom all the way. Also walk
      room_9 → `corr_11` → room_11 (800.0 u, 17.5 u down). Say whether tunnels this long read
      as cave passages or as tedious walks. Not looked at in the 3D viewer for this section.
- [ ] **[MUST] Long fortress halls and stairs** — Case f at 3.0: walk room_0 (the entrance) →
      `corr_5` → room_1 (**140.8 u**, 40.0 u at 1, a 12.4 u ramp up), room_15 → `corr_14` →
      room_14 (150.3 u, 6.5 u up, level at 1) and room_15 → `corr_15` → room_13 (112.2 u, 7.1 u
      up, level at 1). Each ramp should read as one even slope and land flush at both doors.
      Then walk the U-stairs room_3 → `corr_6` → room_2 (227.4 u, 102.0 u down) and room_10 →
      `corr_9` → room_9 (227.2 u, 103.6 u down, 1.6 u more than at 1). Each stair should keep
      every riser under 3 u and land flush. One U-stair got shorter: room_7 → `corr_8` → room_10
      is 151.5 u (234.8 u at 1); check it still lands flush. Not looked at in the 3D viewer for
      this section.
- [ ] **[MUST] The zone still reads as one place** — Cases c and f at 3.0, from above: the cave
      spans 1,942 × 2,818 u (984 × 791 u at 1), the fortress 1,312 × 950 u (1,087 × 576 u at 1).
      Say whether long halls make the zone feel bigger in a good way, or like rooms strung far
      apart with nothing between them. Not looked at in the 3D viewer for this section.

### H.2 — Short halls at 0.5

- [ ] **[MUST] Short fortress halls don't squeeze rooms or merge walls** — Case f at 0.5: the
      closest rooms now stand **19.0 u** wall to wall (room_0 / room_1, room_1 / room_2,
      room_12 / room_14, room_14 / room_15), one 18 u corridor width plus 1 u. At 1 only
      room_14 / room_15 stood that close, and the next pair 28.9 u. Walk the 23.0 u halls:
      room_5 → `corr_4` → room_3 (Level 1, floor 116), room_1 → `corr_7` → room_2 and room_2 →
      `corr_11` → room_4. Each should be a short, clear hall with its own wall on both sides. The
      two rooms' walls should stay separate: no shared sliver, no seam you can see through, no
      doorway cut into a third room's wall. Not looked at in the 3D viewer for this section.
- [ ] **[MUST] The steepest short ramp** — Case f at 0.5: room_0 → `corr_5` → room_1 is 23.0 u
      door to door and rises 11.5 u (a 0.5 grade, 26.6°, the steepest the layout allows). It
      should still walk as a ramp, flush at both doors, not a wall to jump. The floors move at
      0.5 too: `corr_12` (room_9 → room_12, 96.1 u, 18.9 u down) and `corr_15` (room_15 →
      room_13, 109.9 u, 18.9 u up) are ramps here and level at 1. Not looked at in the 3D viewer
      for this section.
- [ ] **[MUST] Short cave tunnels** — Case c at 0.5: walk room_6 → `corr_4` → room_9 (**49.8 u**,
      125.9 u at 1), room_1 → `corr_2` → room_5 (69.4 u, 10.9 u up) and room_0 → `corr_8` →
      room_3 (66.5 u, 11.6 u up). The closest pair not on a throat, room_1 / room_3, stands
      34.2 u wall to wall. The tunnels should still read as tunnels, each room keeps its own
      walls, and the ramps stay walkable. Say whether a cave at 0.5 reads as tight and clumped,
      or as rooms jammed together. Not looked at in the 3D viewer for this section.

### H.3 — Throats and outdoor dungeons

- [ ] **[MUST] Cave throats still throats at every length** — Case c at 0.5, 1 and 3.0: the same
      three throats each time, `corr_1` (room_1 → room_0), `corr_6` (room_2 → room_0) and `corr_9`
      (room_3 → room_7). Each is **12.0 u** door to door and level, with the two rooms' walls
      8.0 u apart. Hall length never stretches a throat. At each length walk all three: a short,
      level step from one room into the next, doors in line, no lip. Not looked at in the 3D
      viewer for this section.
- [ ] **[MUST] Outdoor dungeons stop short of the slider** — Case o. At 0.5 the layout is the
      same as at 1 (the spec is equal, name and `hall_length` aside; 14,078 vertices both), as
      decisions 2 and 3 expect: the rooms already stand a corridor width apart. At 3.0 the halls
      reach only **1.21x** on this seed (median 68.8 u against 56.7 u). Most plain halls are
      68.6 u, held at the gap the hill fit allows, and the rooms span 634 × 527 u against
      593 × 508 u. Decision 4 measured 1.6x at both 2 and 3 over many seeds (1.28x at 30 rooms).
      The hill can't hold longer halls with full-size rooms, so outdoor dungeons stop at about
      1.6x, and some seeds stop lower. At 3.0 walk room_8 → `corr_12` → room_11 (95.2 u, 49.1 u
      at 1; its rise is 9.0 u, 14.0 u at 1) and room_5 → `corr_4` → room_2 (80.6 u, 58.0 u at 1).
      Say whether the slider should say so, or stop at 1.6 for outdoor dungeons. Not looked at
      in the 3D viewer for this section.

### H.4 — The slider and the words

- [ ] **[MUST] The slider** — In Controls, the **Hall length** slider (0.5 to 3, step 0.1,
      default 1, its value shown beside it) shows for Dungeon, City and Outdoor dungeon and hides
      for Wilderness. After a build, the plan readout shows a **Hall length** row (1 when the
      plan leaves it out), and the browser console's `[input] controls:` line carries
      `hall_length=<value>`. Build case f at 3.0 that way: the readout should show Hall length 3,
      Quality passed and 21,924 vertices, the same build as through the API. Check that WASD
      leaves the camera alone while the slider is focused, and moves it again once you click the
      view. Not checked in the browser for this section. Not looked at in the 3D viewer for this
      section.
- [ ] **[MUST] The words** — Prompt mode with no API key (the rule planner). Short words plan
      Hall length **0.6** and long words **2.0**. Anything else plans 1 and leaves the field out.
      A prompt can't reach 0.5 or 3.0; use the slider for those. Checked with the rule planner:

      | Prompt | Hall length | Also |
      |---|---|---|
      | "a fortress with long halls" | 2.0 | |
      | "a cave with long tunnels" | 2.0 | |
      | "an outdoor dungeon with long hallways" | 2.0 | |
      | "a far-flung cave" | 2.0 | |
      | "a sprawling fortress" | 2.0 | also Size huge, 25 rooms |
      | "a fortress with short corridors" | 0.6 | |
      | "a cave with short passages" | 0.6 | |
      | "a compact cave" | 0.6 | also Size small, 3 rooms |
      | "a cramped warren" | 0.6 | also Size small |
      | "tight tunnels and long halls" | 0.6 | short wins a tie |
      | "a fortress", "a long-forgotten crypt", "short on light, a cave" | 1 (left out) | bare "long" and "short" never fire |

      "long" and "short" fire only before halls, hallways, corridors, passages, passageways or
      tunnels. The words alone are compact, tight, cramped, close-set (short) and sprawling,
      far-flung, spread out (long). "a cave spread out over the hills" plans 2.0 but reads as
      Wilderness, which has no halls. Through the Server, seed 731402518: "a cave with long
      tunnels" planned 2.0 (`gen_1795678572_a323b1`, a 5-room cave, 5,536 vertices), "a fortress
      with short corridors" 0.6 (`gen_1795678576_e2c6d6`, 5,700) and "an outdoor dungeon with
      long hallways" 2.0 (`gen_1795678580_5cbd2b`, 6,637). Each passed the gate on its first
      build. Try them and check the plan readout's Hall length row each time. In Controls the
      prompt is never read.

### H.5 — Hall length 1, and what task 8 moved

- [ ] **[MUST] 1 is today's zones, but for nine plans** — A plan at 1 leaves `hall_length` out
      of the plan, and a zone at 1 builds as before the step, with one exception. Two of task
      8's fixes were real faults at 1 too, so **9 of 942** plans at Hall length 1 (the gate
      sweep's 696 draws plus every theme, layout and verticality) now differ from master before
      the step. In seven (82be46c), an angled corridor's straight line ran through a sibling
      corridor's legs or stair box in its Z band, a tube through a tube (by rooms: cave graph
      moderate 6, 11 and 29, cave graph dramatic 17, 26 and 27, warren graph dramatic 18). In
      two (0d890ad), a corridor stood 0.04 u (cave graph moderate 25) or 0.006 u (warren graph
      moderate 29) off a third room's wall, the open seam a 0.5 build exposed. Every other plan
      is byte-identical at 1. Case c at 1 is unchanged (10,928 vertices, step 29's case a). No
      case here is one of the nine.

### H.6 — Known, not this step

- **Outdoor dungeons stop at about 1.6x** (decision 4) and do not shorten below 1 (decision 3).
  This seed reached 1.21x at 3.0. The slider still runs 0.5 to 3 for them.
- **Below 1 only caves shorten fully** (decision 3): the fortress reached 0.72 here, classic and
  city reach about 0.87, outdoor 1.0.
- **Stairs don't scale.** A U-stair's length follows its rise, so a fortress's longest halls
  barely change.
- **Gate sweep 696 / 695 / 696** at 0.5 / 1 / 3.0, and quality bands at most 3.5% per key (task
  4, on task 8's code). The one failure at 1 (cave classic dramatic 21, seed 1866540615) fails
  on master before the step too.
- **Draw time at 3.0**: 30-room Graph caves 3.7 s median, 5.0 s max; outdoor dungeons 9.9 s
  median, 17.3 s max (task 4).
- **Follow-up**: check corridor headroom, risers and room crossings on the plan, before the mesh
  is built, to catch what the gate finds earlier and cut retries.
- **Nothing in this section was looked at in the 3D viewer.**
