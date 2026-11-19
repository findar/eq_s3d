# Archive — zone-generator-districts

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

Decided 2026-11-18 by the lead after the user's "continue working" (multi-zone worlds wait on the
user's design review). The user confirms at the first look (task 9).

1. **Step 20 is M3's Districts.** It is the next unblocked umbrella piece after the quality gate;
   the `cave` archetype is a later step.
2. **Off by default** (A1): every existing zone stays byte-identical and step 19's bands stay
   valid. Turning the default on waits for the first look.
3. **Partition before pacing** (A4), so each District's climax gets the climax's size bias.
4. **New palettes only in multi-District zones** (design "Purposes"), so one-District zones don't
   move.
5. **District adjacency is a tree** (task 1, `c2c0a14`): only the cut edges link Districts, so
   two sibling Districts that shared a loop corridor lose it, and every Threshold is a bridge
   (task 3's gating relies on it). Umbrella 23.3 allowed a cycle of Districts.
6. **"Next to" means across a Threshold** (task 2, `de2e44e`): `sequential` checks each District
   against its parent; `factional` relaxes to per-Threshold contrast, then to distinct, with a note.
7. **Three variant levels** (as built, `abandoned`, `ruined`), in the Material_Name; light moods
   `lit`, `dim`, `faint`. A pinned single Purpose is `pinned=True` (task 4 decides when).
8. **With Districts, a zone tint drives regions and lights but not the palette**: a lava temple
   split into Districts keeps its lava pools and light but loses its lava floor. Judged at the
   first look.
9. **Crossing splits are guarded, then redrawn in the layout** (task 3, `195b918`): a split that
   would join two Districts drops the edge (if still connected) or swaps it for the shortest clean
   edge on the same pair; a Draw that still fails is redrawn inside `generate` (up to 8,
   `DISTRICT_ATTEMPTS`), since the pipeline's plan errors don't cover `ValueError`. Failing Draws:
   classic 15.7%, graph 3.0%; over 200 generates per layout none failed. The design's fallback
   (waypoint to A's District) barely helped and was dropped. Notes go to `gen.warnings`.
10. **The plan** (task 4, `ff0021a`): a plan pins when it proposes one Purpose two or more times
    with none open; a theme alone doesn't pin. A District phrase with no room count raises a dungeon
    to 8 rooms (2 areas) or 14 (3). Notes collect in `plan_to_spec(..., warnings=[])`; task 5 carries
    them to the response and sidecar (a `ZoneSpec` notes field if rebuilds must keep them).

## Follow-ups
