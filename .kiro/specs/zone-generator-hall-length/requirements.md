# Requirements — zone-generator-hall-length (roadmap step 30)

> **STATUS: done (closed 2026-11-26; the user's look: "as far as look and feel goes hall length is good for now").** Drafted 2026-11-25 at master `83ec73a`. At the step 26
> second look the user said "a future task should also adjust length of halls"; after step 29
> closed they said "You pick next", and the lead picked this, the oldest of the user's open ideas.
> Task index: `tasks.md` (card format). Decisions: `archive.md`.

## Introduction

How far apart joined rooms stand, and so how long the halls between them run, is fixed per
layout today: Graph layouts space rooms by `embed.RUN_FACTOR` corridor widths (2.0; caves 4,
step 25), drawn per edge by the jitter (steps 26–29); the classic layout by its separation gap
and footprint spread (`generators/layout.py`); outdoor dungeons by the Envelope fit. Nothing
lets a user ask for long, sprawling halls or a tight, compact zone. This step adds one scalar,
**Hall length**, modelled on Winding (step 26).

## Requirements

1. **The plan field.** `ZonePlan.hall_length` is a float, default 1.0, clamped to
   `[HALL_MIN, HALL_MAX]` (set by task 1's measurement). A plan without it means 1.0; bad values
   fall back to 1.0, as `winding` does. Recorded on the ZoneSpec only when it isn't 1.0.
2. **What it scales.** The door-to-door length of every ordinary corridor scales by about
   `hall_length` (median within 15% of `hall_length` x the zone's length at 1, over seeds):
   Graph run spacing, the classic layout's room spacing, and the outdoor dungeon's spacing
   inside its Envelope as far as the hill allows. Throats (step 29) stay throats. Room sizes,
   the grown graph, Levels and stairs stay as they are; elevation stays within the grade cap
   at every setting.
3. **Bytes.** At `hall_length = 1` (or absent) every zone is byte-identical to before this step.
4. **Controls and words.** The web Controls get a **Hall length** slider wherever a zone has
   corridors between rooms (dungeon, city, outdoor dungeon), default 1, shown in the build
   summary. The rule planner reads words: long ("long halls", "sprawling", "far-flung",
   "spread out") raises it; short ("compact", "tight", "cramped", "close-set") lowers it. The
   LLM planner's schema gets the field; the server passes it through.
5. **Gate and bands.** Gate sweeps (`EQ_PATH` set) pass at master's count or better at
   `HALL_MIN`, 1 and `HALL_MAX`; quality fail shares stay under 5% per key; draw time at
   `HALL_MAX` stays within the ~5 min budget.
