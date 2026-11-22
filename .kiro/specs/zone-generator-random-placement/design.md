# Design — random room placement (step 27)

## Starting point

Step 26 task 8 (`generators/topology/embed.py`, `generators/layout.py`,
`generators/layout_engine.py`; winding-control archive decision 5):

- `layout.JITTER_PROFILES = {"cave"}` → `LayoutContext.jitter` → `spring(jitter=True)` →
  `EngineResult.jittered`; the sidecar's layout record gets `"jitter": true`.
- Each edge's sideways offset is 0.4–1.0 of its slack (the two rooms' half-extents across less
  1.5 corridor widths) and its run is spaced 1.25–1.75×, salted from room ids and sizes. Stair and
  Bridge edges get neither.
- Jittered builds put both doors mid-span (`_straight_across`), keep U-route stair doors
  `U_CORNER_MARGIN` (3 u) from a wall's end, and `_mark_bridges` refuses a slot meeting a door's
  in-room piece (`_slot_meets_door`).

Step 26 task 8's first attempt jittered every zone at 0.3–0.6 of the half-extents with centred
doors: 36 failures, warrens lost loops (cycles 0.175 vs band 0.19–0.29), tombs and an outdoor
bowl failed the gate. Its final form (slack-bounded offset, straight doors) has not been tried
outside caves. Start from the final form, not the first.

## Approach

- **Switch.** Replace the profile set with "every Graph build" (keep a way to turn it off for a
  test, e.g. `LayoutContext.jitter`). The spacing range may differ per zone kind: built and hewn
  corridors are halls, not tunnels, so 1.25–1.75× may stretch them more than it needs to. Pick
  by measurement against Requirement 2's door-to-door limit.
- **Warrens.** The loss of loops came from the start placement: an offset neighbour can make a
  loop edge's two rooms face on a wall another corridor already uses, so Job B drops it. Measure
  `cycles` and `dead_ends` per offset range; if loops still drop, keep the start's loop-closing
  rank (`close`, `pending`) on the un-offset position and offset only after the side is chosen.
- **Outdoor dungeon.** Rooms are sized to the Envelope and stepped down the hill
  (`layout_in_envelope`); the offset must stay inside the Envelope (`fit_to_envelope`). Its
  stairs and Levels are where the first attempt failed (seed 1654615998): check them first.
- **Seed.** Task 8 salts from room ids and sizes. Requirement 5 asks for the build's own seed:
  wire `LayoutContext.seed` (or the rooms seed) through so two builds whose rooms happen to match
  don't place alike. This moves cave goldens once more; do it in the same task as the switch.

## Measuring set

Grid score, door-to-door median, `relations_broken`, `edge_fidelity`, cycles and dead ends,
over Graph seeds 2000–2039 (8–30 rooms, verticality cycling) for each dungeon theme and the
outdoor dungeon, at `b77d5a9` and after. `scratchpad` has a starting script; put the measuring
script in `scripts/` if it is reused by a later task.
