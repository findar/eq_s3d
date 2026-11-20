# Archive — zone-generator-districts

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

| Tasks | What landed | Commits |
|---|---|---|
| 1 | `generators/districts.py`: the partition (2 Districts from 8 rooms, 3 from 14; a tree of cut edges), `DistrictSpec`, `ZoneSpec.districts`, `CorridorSpec.threshold` | `c2c0a14` |
| 2 | A Purpose per District (sequential, factional, abandoned_vs_active; pinned), three variant levels, four new palettes, room labels and lights per District | `de2e44e` |
| 3 | Districts in both layouts: partition before pacing, one climax per District, Threshold Gates first, crossing splits guarded and redrawn | `195b918` |
| 4 | `ZonePlan` fields, the rule planner's contrasting-area phrases, the LLM prompt | `ff0021a` |
| 5 | CLI `--districts` / `--district-theme` / `--district-relationship`, the Server, the sidecar's `districts` and `threshold` | `bfb4f47`, `75c4d54` |
| 6 | Bands keyed by the resolved District count, from 7200 Draws; `district_balance` bounded low (decision 11); a subnormal-gap fix in `evaluate` | `a74eef9`, `33b72e0` |
| 7 | The Districts box, District hulls and gold Thresholds on the map, the legend, the room's District | `fee1c5c` |
| 8 | `docs/ACCEPTANCE.md` "Step 20 — Districts" (seven cases, run through the Server); thorough 3719 passed, 1 pre-existing failure | `6f59ad0` |
| 9 | First look skipped at the user's word ("Skip acceptance"); Districts stay off by default | — |

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
11. **Bands key on the resolved District count** (task 6): `BAND_TABLE[(zone_type, layout,
    verticality, k)]`, k = `len(spec.districts)` or 1, so the k = 1 rows are step 19's unchanged;
    k = 2/3 rows use step 19 decision 4's rule, keep a bound only where it fails some Draw, always
    bound `district_balance` low, and leave `cyclomatic` unbounded (districted trees reach 0 loops).

## Follow-ups

- **Default on for 8+ rooms** (A1): not answered at the first look; Districts stay off unless
  asked for.
- **Not looked at in person:** the palette and light change across a Threshold in 3D; an edit
  that removes rooms from a districted zone (a District's `room_ids` could go stale).
- **Similar neighbours:** case b's tomb and sunken_ruin both get cool blue light across their
  Threshold; only the materials differ.
- **Repeated Purpose:** three proposals of one Purpose gave as built / abandoned / as built; the
  first and third Districts match and the `ruined` level never appears.
- **Map:** hulls of a wrapping District overlap their neighbour; the page numbers Districts from
  1 while the warnings count from 0; Purposes shown raw (`corrupted_sanctum`).
- **Pre-existing:** thorough failure `test_raw_navigable` at seed 8869712 (27-room classic
  dungeon, no Districts, a gap in room_4's outline; fails on `a26d07b` too); all three keys in one
  room at case d's seed with Districts off as well.
