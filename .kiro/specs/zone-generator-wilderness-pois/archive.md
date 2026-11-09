# Archive — zone-generator-wilderness-pois

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

Nothing yet. Rows are added at the close step (task 14).

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

Carried in from earlier steps and relevant here:

- **EQ models among the Features** (step 9, user 2026-11-07): bookcases, chairs, tables. Step 11; so is a Site's furniture.
- **Wilderness ground, water and tree textures and normal maps** (step 4, umbrella Req 16): still deferred.
- **Sites spread at random where stock plains cluster** (task 11): Clark–Evans R pooled 1.45, inside the all-zone stock band 0.64–1.64 but above plains alone (0.50–0.95). A soft "near another Site" like would pull them together.
- **The survey splits a farmstead in two** on seeds 1001 and 1004 (hut and fences more than 100 u apart); a smaller farmstead loses its barn.
- **A farmstead often loses its barn** (task 12): dropped "in its Site_Clear" on 5 of 20 seeds at Normal.
- **`altar_stone` is built but no recipe places it** since task 10's shrine.
- **Shoreline below water level on some seeds** (`synth.py`): a Site that likes water will find it.
