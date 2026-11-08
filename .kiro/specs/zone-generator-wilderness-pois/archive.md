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

## Follow-ups

Carried in from earlier steps and relevant here:

- **EQ models among the Features** (step 9, user 2026-11-07): bookcases, chairs, tables. Step 11; so is a Site's furniture.
- **Wilderness ground, water and tree textures and normal maps** (step 4, umbrella Req 16): still deferred.
- **Shoreline below water level on some seeds** (`synth.py`): a Site that likes water will find it.
