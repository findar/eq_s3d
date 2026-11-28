# Archive — zone-generator-races-followups

## What landed

| Tasks | What landed | Commits |
|---|---|---|

## Decisions

1. **Step 32 is step 31's follow-ups, breach rate first** (the lead, 2026-11-27, on the user's "You pick"):
   the user asked for overlap, and task 17's shorter links cut pairs at 2+ links from 82% to 68%.
2. **An intruder is seated against its host, and a raced zone's breach may climb Levels** (task 1).
   82 % of refused candidates were past the breach bound: the giant host grows 3.67x and the intruder
   hangs off one host room by its Threshold. `layout._seat_intruders` moves the intruder (with the
   Districts beyond it) by a rigid motion (8 turns x a grid) to where most of its rooms face host rooms
   in reach; its halls keep their lengths, the host stays, and the nearest pair takes the Threshold if
   its own is out of reach. A breach across Levels is a planned stair, only where a District has a
   race (race-less zones byte-identical). `test_new_breaches_fill_most_pairs` back to 0.8 for both
   layouts. `--intrusion` seed 31: pairs at 2+ links 68.2 % -> 91.7 %, links p50 20.2 -> 26.4 H,
   max 163.4 H; prompt seeds 9/10 with a goblin breach.

## Follow-ups
- Stair breaches are held to zones with a District race (task 1) only to keep race-less zones
  byte-identical; race-less dramatic Graph intrusions would gain breaches the same way (a named change).
- Prompt seed 2024 still joins the goblins by its Threshold alone (nearest pair 221 u, bound 158 u, no
  clear seat).
