# Archive — zone-generator-wilderness-pois

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

| Task | What landed | Commits |
|---|---|---|
| 1 | `scripts/site_survey.py`: 24 Classic outdoor zones, 367 stock Sites; bands for Sites per area, Structures per Site and spacing; stock Structure sizes; DTOW/BTOW are rock spires, Sites aren't drawn to water | `73929ec` |
| 2 | The gate judges placed models from their own collidable triangles (`analyzer/footprints.py`); the Footprint check replaces `trees_block` and agrees with it on tree-only zones | `9f9ff29` |
| 3 | 11 Structure kinds in 18 variants (`generators/sites/models.py`), front facing +X; the survey's values in `rules/sites/` | `5e0dd5e`, `8998ba0` |
| 4 | Timber, crude timber, thatch, hide, canvas and stone at 31.2 u a tile; four material sets (`generators/textures/sites.py`) | `bd9104d` |
| 5 | `rules/sites/` (sites, inhabitants, biomes) and its strict loader; `topology_rules.py check rules/sites` and `draw-sites` | `0f007cd` |
| 6 | Site placement on its own stream (`generators/sites/placement.py`); trees keep off Site ground | `3bfa78b` |
| 7 | Sites in wilderness and outdoor-dungeon builds: models, ZON objects, the gate on every build, the sidecar `sites` block; `none` is step 9's bytes | `2fabea3` |
| 8 | Sites and Inhabitant controls on the plan, CLI and page; prompt words; Footprints and labels on both maps, read from the built `.eqg` | `2bd2fdd` |
| 9 | First look signed off ("Looks good", 2026-11-08) | `66cf655` |
| 10 | Tuned to stock's mix: 48% of Sites are one Structure (stock 51%) | `ba3d886` |
| 11 | `tests/test_site_bands.py`: Normal builds inside the stock bands with the survey's own code; Clark–Evans R in place of raw spacing p50; gate 40/40; Sites cost 0.64 s | `d90b81c` |
| 12 | `docs/ACCEPTANCE.md` "Step 10 — Wilderness POIs", 21 pinned cases; thorough 2078 passed, 4 failed (3 pre-step-10, 1 timing) | `5603f25` |
| 13 | Acceptance pass signed off ("Yes, signed off", 2026-11-08) | — |
| 14 | Closed on the trackers | this commit |
| 15 | Camps keep 2–4 tents (ground 36 → 46 u); targets round to keep their mean; a kind with no ground is redrawn | `3db8f9c` |

56 commits from the spec draft (`b3e621f`) to the close.

## Decisions

The design's eight open questions, answered by the user 2026-11-07 ("Looks good" to every
recommendation, master `b3e621f`):

1. **Terrain under a Site is unchanged.** Pick ground already flat enough and bury a skirt;
   no pad is flattened. Flattening is a follow-up only if a look says Sites sit badly.
2. **Enterable in v1: huts, lean-tos and ruins**, floored by the ground. Towers are solid; no
   upper floors or ladders.
3. **Kinds: camp, hut, farmstead, watchtower, shrine, ruin.**
4. **Inhabitants: human, orc, gnoll, centaur** (plains). Others come with their biomes.
5. **Step 10 is Structures** (buildings, tents, fire rings, fences, towers, stones). Furniture
   and loose props, haybales included, are step 11, which can fill a Site's POIs.
6. **Both controls:** Sites (None, Sparse, Normal, Dense) and Inhabitants.
7. **No roads** in this step.
8. **No ZON light.** A camp fire is a model, and a `Light_Spot` POI marks it for later.

Set by the tasks:

9. **Clear width 8 u, head height 8 u** (task 2, `analyzer/footprints.py`), matching the
   Transition check's headroom; the player is 6 u tall. A model that encloses at least 4 u² of
   free ground is Enterable and needs an 8 u x 8 u way in. Solid parts must be closed and wound
   outward (the gate reads "inside a solid" from the first triangle above facing up).
10. **Yaw is the way a Structure's front faces** (task 6), radians counter-clockwise from +X;
    a model's opening faces +X at yaw 0. Fences and ruin walls run across the yaw, their radius
    the half-length. Placement's own clear width (6 u, `generators/sites/placement.py`) must
    become the gate's 8 u (`analyzer.footprints.CLEAR_WIDTH`): task 7 lines them up.
11. **Outdoor dungeons get Sites on some seeds, not most** (task 15): over 38 seeds, 8 at
    Normal and 15 at Dense. Their open ground is about 0.8e6 u², so the target averages under
    one, and with the Host_Hill, Tunnel and Mouth kept clear the eligible ground left is often
    smaller than the smallest recipe (a shrine, 38 u). A kind that finds no ground is redrawn
    from the others before the Site drops. The first look (task 9) judges whether that's enough.

## Follow-ups

Found in step 10:

- **Wilderness size** (user, 2026-11-08): every wilderness is 2400 u square and outdoor dungeons 1200 u. The Size control could pick a range measured from stock outdoor zones, random when unset, maybe non-square; content already scales by area. Later, by the user's word.
- **Three dungeon and outline failures under the thorough profile** (task 12; they fail at `0f007cd^` too) and the mapgeom face-order bug: proposed as one separate fix.

Carried in from earlier steps and relevant here:

- **EQ models among the Features** (step 9, user 2026-11-07): bookcases, chairs, tables. Step 11; so is a Site's furniture.
- **Wilderness ground, water and tree textures and normal maps** (step 4, umbrella Req 16): still deferred.
- **Sites spread at random where stock plains cluster** (task 11): Clark–Evans R pooled 1.45, inside the all-zone stock band 0.64–1.64 but above plains alone (0.50–0.95). A soft "near another Site" like would pull them together.
- **The survey splits a farmstead in two** on seeds 1001 and 1004 (hut and fences more than 100 u apart); a smaller farmstead loses its barn.
- **A farmstead often loses its barn** (task 12): dropped "in its Site_Clear" on 5 of 20 seeds at Normal.
- **`altar_stone` is built but no recipe places it** since task 10's shrine.
- **Shoreline below water level on some seeds** (`synth.py`): a Site that likes water will find it.
