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
