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

## Follow-ups

Carried in from earlier steps and relevant here:

- **EQ models among the Features** (step 9, user 2026-11-07): bookcases, chairs, tables. Step 11; so is a Site's furniture.
- **Wilderness ground, water and tree textures and normal maps** (step 4, umbrella Req 16): still deferred.
- **Shoreline below water level on some seeds** (`synth.py`): a Site that likes water will find it.
