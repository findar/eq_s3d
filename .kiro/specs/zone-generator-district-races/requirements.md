# Requirements — zone-generator-district-races (roadmap step 31)

> **STATUS: done (closed 2026-11-27; the user's look: "just checked, it looks good").** Drafted 2026-11-26 at master `070126c`. At the step 30
> look the user said hall length "might be part of their look and feel" for races in
> Districts, then: "if we originally had a giant fortress that goblins tunneled into, i would
> expect there to be overlap"; "an entry into another district becoming one way if it does not
> meet flush with the floor ... give weight towards being flush but also allow variability";
> and "a drop being the only way in is fine, as long as it's not the only way back ... a drop
> in, and then a different drop out" (the goblins' drop in from an elevated height, and a flush
> passage back on the far side that forces the player across the District).
> Task index: `tasks.md` (card format). Decisions: `archive.md`.

## Introduction

A dungeon of 8+ rooms can be split into 2–3 Districts (step 20), each with its own Purpose,
walls and decor (step 22), joined to its neighbour by exactly one corridor, the Threshold.
Race is one per zone: `dungeon_race` sizes every room and corridor by its body height H
(`generators/semantics.py`). Hall length is one scalar per zone (step 30). The traversal gate
is two-way: two floors join only within `max_step_up` (3 u) of each other in either direction
(`analyzer/traverse.py`), so a drop reads as a wall.

This step makes Districts read as layered history: each District has its own race and hall
length, a younger District can **intrude** on an older one through several rough breaches, and
an entry between Districts may be a **one-way drop** where its floors don't meet.

## Requirements

1. **Measure first.** Before any default is set, stock zones give: hall length door to door
   per inhabiting race (or culture) in H; the drops between floors (where one walkable floor
   meets another more than `max_step_up` below): their height p50/p90/max and their share of
   passage ends; and, in zones that mix built and cave parts, how many links join the two
   parts. Each later default cites this measure, or says there was no signal.
2. **One-way navigation.** The gate reads a drop (a floor edge above another walkable floor,
   no wall between, the fall at most `MAX_DROP`, set by requirement 1) as a ONE-WAY link. A
   zone passes only if every room is reachable from the entrance AND the entrance is reachable
   from every room (strong connectivity). A drop may be the only way into a room or District;
   it may never be the only way back. Zones with no drop keep their gate reports (same pass,
   same reasons) over the sweep.
3. **Advisory gates and pacing on the directed graph.** Gate placement and solvability
   (`generators/layout.py` gating, `generators/edits.py` `solvable`) treat a drop as one-way.
   Gates and pacing stay advisory: never in geometry or collision.
4. **A race per District.** A `DistrictSpec` may carry its own `race` (default: the zone's).
   That District's rooms and corridors are sized by its race's H. A Threshold or breach between
   two races is sized by the SMALLER race (a goblin hole into a giant hall). A zone whose
   Districts carry no race of their own is byte-identical to before.
5. **Hall length per District.** Each Purpose and race may carry a default hall length
   (from requirement 1; 1 where there is no signal), multiplied by the plan's `hall_length`. A
   corridor inside a District takes that District's; a corridor between Districts the mean of
   its two ends. A zone without Districts, or whose defaults are all 1, is byte-identical.
6. **Intrusion.** A new District relationship, `intrusion`: the younger District (the
   intruder) may join its host by more than one link (2–3, from requirement 1), lifting the
   one-link rule for that pair only. Each extra link is a **breach**: rough-cut, sized to the
   smaller race, entering a host room through its wall.
7. **Flush or a drop.** Each link between Districts is placed flush where it can; a weighted
   share (from requirement 1; the user: "give weight towards being flush but also allow
   variability") enters its lower room partway up a wall as a drop of at most `MAX_DROP`. Every
   zone still passes requirement 2.
8. **One-way loops.** An intruder District may be entered only by a drop when a return path
   exists: a flush link out on the far side of the District (its exit at the room farthest,
   by graph distance, from the drop's landing), so the player must cross the District to get
   back (the user's example).
9. **Mixed boundary rooms.** A host room that a breach enters keeps its host shape and walls
   but takes some of the intruder's decor (the intruder's dressing spilling in).
10. **Controls and words.** Controls set each District's race and the relationship
    (`intrusion` among them); the rule planner reads phrases such as "a giant fortress the
    goblins tunnelled into" (host fortress/giant, intruder warren or cave/goblin, relationship
    intrusion). The LLM planner's schema gains the fields; the server passes them through.
11. **Gate and bands.** The districted sweeps (`--pair`, plus an intrusion sweep) pass at
    master's count or better; quality fail shares stay under 5% per key; zones without
    Districts are byte-identical; draw time stays within the ~5 min budget.
