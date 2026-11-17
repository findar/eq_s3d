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
