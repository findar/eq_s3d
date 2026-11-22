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

## Follow-ups
