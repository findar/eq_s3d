# Archive — zone-generator-export

Finished work and the decisions later tasks rely on. Agents don't need to read
this file to pick up a task; it holds the "why".

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

Decided 2026-11-16 by the lead: the user said "Keep working and we can validate this in the next
step" with step 16's checks open, and the lead chose umbrella M6 as step 17. The user confirms
the choice and these decisions at the first look (task 8).

1. **The export is the umbrella's** (Requirements 8 and 10): a takeover of an existing short
   name, default `arena`, written beside the build; the build's files never change.
2. **No zone ids** (amendment A1). The SQL addresses rows by short name, so nothing needs the
   EQEmu `zoneidnumber`, and no hand-curated id table is kept.
3. **The bundled short names come from the install** (amendment A2), names and container only.
4. **Pinned schema:** the EQEmu `doors` and `zone` repository columns as of 2026-11-16
   (`common/repositories/base/base_doors_repository.h`, `base_zone_repository.h` on the
   `EQEmu/Server` master branch). The SQL writes only columns in that set.
5. **The UPDATE sets the safe point and `underworld`** (lowest floor less a margin) and nothing
   else; fog, clip planes, sky and `ztype` stay stock (follow-up).
6. **Nothing is ever executed or copied into the install**: the SQL is a file to review; the
   install steps are the user's.
7. **Load rule** (task 2): the client tries `<short>.eqg` first and falls back to the `.s3d`
   (its `dbg.txt`; `clz.eqg` + loose `clz.zon` loads the same way `arena` ships), so stock
   `arena` is `arena.eqg` + `arena.zon`. The install steps move aside `arena.eqg`, `arena.zon`,
   `arena.s3d`, `arena_obj.s3d`, `arena_EnvironmentEmitters.txt`, keep `arena_chr.*`. Task 10
   checks for "Loaded arena.EQG." in `Logs\dbg.txt`.
8. **Door model** (task 2): no door model is global, so the build packs `BBDOOR1`
   (`ecommons_obj.s3d`, mesh `b29f16cdfe7d32a6`, 12 tris, 1 x 10 x 10.05, hinge at the origin)
   through the decor importer as `obj_bbdoor1.mod`, listed in the `.zon` models and not placed;
   rows name it `OBJ_BBDOOR1`.
9. **Door fields** (task 2): `opentype 0` (90° swing), `size` 100 per unit scale (500 for a
   50-unit corridor), `heading` in EQ 0-512 units (`deg * 512 / 360`, clockwise), `incline 0`,
   `keyitem` a per-tier placeholder, `lockpick 0`, every other column its stock default.
   **Revised by task 4:** `lockpick 32767` (EQEmu `zone/doors.cpp` treats no value specially: a
   player picks when skill >= lockpick, so 0 and -1 are pickable); `keyitem` 990000 + tier,
   named in the script's header for the user to replace.
10. **The short-name list** (task 1): 496 zones from the install, long names from the client's own
   zone table (485 filled). Equipment archives (`*equip*`) and `sky` are dropped as companions;
   a stem with both a zone `.s3d` and `.eqg` (`arena`, `nektulos`, `tutoriala`, `tutorialb`) is
   recorded as `eqg`, which matches the client's load order (decision 7).
11. **A door seals its corridor at an opening** (lead, from task 4's sweep: 30 of 120 locks on 40
   seeds sat on a Z-route jog shorter than the corridor is wide, where a door across the jog can't
   close the way). The row goes at the corridor's opening nearest the lock, across the doorway,
   not at the lock point (amendment A3). The Gate's lock stays where layout put it, for the map
   and the sidecar.

## Follow-ups
