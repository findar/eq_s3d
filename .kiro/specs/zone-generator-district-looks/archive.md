# Archive — zone-generator-district-looks

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

| Tasks | What landed | Commits |
|---|---|---|
| 1 | Each room's Scales (and wall style) from its District's Purpose; the lean stops at a District edge; rule wings keep their override | `1007a14`, `d87dabf` |
| 2 | Decor per District (rules once per Purpose, `BareCap` per-room rules), corridors from their `from_room`, sidecar `decor.districts`; lead fix: a Threshold takes the outer District's look | `e8a449f`, `3a27cac` |
| 3 | Cave rooms never lit warm (`_CAVE`); cave decor drops torches, lanterns, chests, urns (crystals and gems as treasure) | `f3af75f` |
| 4 | The cave profile shifts footprints only; heights through `height_shift` (`layout_engine`, `embed.room_size`) | `37c151e` |
| 5 | Cave-pair sweeps; five pre-existing gate failures fixed (clashing tree corridors redrawn, bridge-slot pinhole, slit-blind boulders and decor, steep POI); gate 552/552; fail share ≤ 4.7%/key, bands unchanged | `a1860cf`, `4e79bab`, `c31edef`, `001790d`, `bd03aac`, `434a00a`, `70104f8` |
| 6 | ACCEPTANCE "Step 22 — District looks" (cases a–g); thorough 3837 passed | `b1ed709` |
| 7 | First look skipped at the user's word, 2026-11-20 | — |
| 9 | Room view and `stage.py decor` per District; the room view route passes the record | `3f1eaf6`, `86f255f` |

## Decisions

Decided 2026-11-20 by the lead after the user's "Pick the next step yourself". Multi-zone worlds
wait on the user's design review. The user confirms at the first look (task 7).

1. **Step 22 is the District look.** A room's walls and decor follow its own District's Purpose.
   This is the "district look" follow-up carried since step 6: stock zones mix built and cave
   parts. The step also takes in step 21's cave dressing follow-ups. Two things wait: M5's
   Natural_Style, and normal maps (umbrella decision 24 kept them off the Classic look).
2. **Corridors take their `from_room`'s look** (A1), so a Threshold looks like the District it
   leaves.
3. **The lean stops at a District edge; rule wings keep their override** (task 1): a District edge is as hard as a wing's, and a cave wing in a fortress District stays rough.

## Follow-ups
- **Cave corridors are dark** (task 3): their wall lights came from the torch line the cave layer dropped; each room's own light is all a cave has. Judge at the first look.
- **A second cave District gets no crystal grotto boss** (task 6, 5 seeds): its climax takes another type; on seed 1840275513 a crystal grotto stands as a dead end.
- **Sparse cave Districts** (task 6, case a): three of six cave rooms bare; crystals appear outside the grotto.
- **A cave District can draw mostly `hewn`** (task 6, case b, seed 971456024: 1 rough, 5 hewn), against 80–85% rough measured.
- **`layout.rooms.<id>.district` is 0 in districted zones** (task 6): the graph node's own field; `rooms[*].district` is right.
- **`scripts/decor_room.py` ignores Districts** (task 9): it doesn't read the sidecar; an asked-for `decor_layers` stays one zone-wide list in the room view route.
