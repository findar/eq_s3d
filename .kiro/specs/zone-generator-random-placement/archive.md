# Archive — zone-generator-random-placement

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

1. **Step 27 is random room placement** (the user, 2026-11-22: "Random room placement", after
   the step 26 second look: "i would say it looks good but a future task should also adjust length of halls and also when we generate rooms they should end up randomly positioned and connected"). Every Graph zone leaves the lattice as cave zones did at
   step 26; the grown graph and its wall sides stay; classic, city and wilderness keep their
   bytes. Hall length control is a separate later step.

2. **Built and hewn Graph dungeons keep the lattice** (the user, 2026-11-22, choosing "Keep
   built zones on grid"). Task 1 jittered them (grid 0.196-0.233 -> 0.066-0.085) but found
   no setting that kept both stock wall measures and hall length: straight doors put built
   wall run at 48 u (stock band 28-39), mid-wall doors need a jog and make halls 1.44-1.59x
   longer, doors within 0.6 of the middle leave run at 40.33 (band edge 40.17). Only caves and
   outdoor dungeons leave the lattice; task 2 (warrens) is dropped. Task 1 keeps its general
   fixes (decor reads door stubs, ceiling Props inside the room, grade cap, layout independent
   of wall style) and wires the build seed into the cave jitter.

3. **Decor bug fixes apply everywhere** (the lead, 2026-11-23, at task 5). The acceptance
   build found a decorated classic fortress (seed 731402518) with Props moved in room_7 and
   room_8 (87 of 95 files match; Decor None identical). They trace to `4a1d27a` (a ceiling Prop
   kept inside its room; a chain hung 4.4 u through a wall) and `9208d2b` (wall decor read along
   its edges; a banner 8.6 u behind a wall). Those are fixes, so they stay; Requirement 6 is
   amended to name them rather than keep the bug for byte-identity.

## Follow-ups
