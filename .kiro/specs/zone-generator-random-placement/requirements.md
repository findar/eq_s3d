# Requirements Document

> **STATUS: roadmap step 27, ready.** Drafted 2026-11-22 at master `b77d5a9`. At the step 26
> second look the user said: "i would say it looks good but a future task should also adjust length of halls and also when we generate rooms they should end up randomly positioned and connected", then chose this one as step 27 ("Random room placement").
> Task index: `tasks.md` (card format). Decisions: `archive.md`.

## Introduction

Step 26 (winding control, task 8) took cave Graph layouts off the lattice: each edge is offset
sideways and spaced at a salted amount, keeping its wall side, and facing pairs run straight.
Every other Graph zone still places each neighbour centred one run off a wall, so rooms of
similar size line up in rows and columns. Graph is the default layout for dungeons and outdoor
dungeons, so most builds show it.

Grid score at `b77d5a9` (share of room-centre pairs whose x or y agree within 10 u; seeds
2000–2007, 8–20 rooms, defaults otherwise):

| Zone | classic | graph |
|---|---|---|
| dungeon fortress / tomb / mine_delve | 0.080 / 0.071 / 0.074 | 0.263 / 0.263 / 0.263 |
| dungeon temple / warren | 0.082 / 0.069 | 0.293 / 0.215 |
| dungeon cave | 0.086 | **0.060** (step 26) |
| city | 0.079 | 0.079 (city has no Graph engine) |
| outdoor dungeon | – | 0.223 |

The classic layout (TinyKeep: scattered rooms, separation, MST plus loops) and cave Graph sit at
0.06–0.09, which is what random placement scores. This step brings every Graph zone there.

## Requirements

1. **Random positions everywhere.** Every Graph-layout zone (every dungeon theme and rule set,
   and the outdoor dungeon) places its rooms off the lattice: per theme, the grid score's mean
   over the measuring set is at most 0.10 and no build reads as rows and columns.
2. **Still connected, the same way.** The grown graph is unchanged: the same rooms, the same
   edges, every edge on its wall side (one opening per wall, step 6 finding 1). Rooms join their
   own neighbours, not across the zone: `relations_broken` and `edge_fidelity` hold, and the
   door-to-door median grows by at most a third over `b77d5a9` per theme.
3. **Shape bands hold.** Each rule set's built shape stays in its band (dead ends, cycles, and
   the rest of `tests/test_topology_levels.py`'s checks); a warren keeps its loops.
4. **Navigable.** The gate holds at master's count or better on the cave/warren sweep and on a
   new sweep over the other Graph themes and the outdoor dungeon. Quality bands stay under 5%.
5. **Randomness, not noise.** Different seeds give different placements; the same seed gives the
   same zone. The offset comes from the build, not from a global rng stream other code shares.
6. **Bytes.** Classic-layout zones, cities and wilderness stay byte-identical. Graph zones change
   (the user's request); each moved golden is named in its commit.
