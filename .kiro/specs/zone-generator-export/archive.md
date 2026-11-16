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

## Follow-ups
