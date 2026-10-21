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
