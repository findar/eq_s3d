# Requirements — zone-generator-layout-repair (roadmap step 33)

> **STATUS: roadmap step 33, ready.** Drafted 2026-11-27 at master `0eeec16`. The user, after the
> lead compared Edgar's graph-based generator with ours: "can we pause the step 32 work and focus on that if it should improve our build times?"
> Step 32 is paused (its task 1 parked on `agent/followups-1`). Task index: `tasks.md` (card
> format). Decisions: `archive.md`.

## Introduction

A generate draws a whole layout, routes corridors after the rooms, drops what collides
(`_resolve_conflicts`), builds the mesh, and gates it; any failure redraws the whole layout
(`pipeline.generate_validated`: up to `QUALITY_DRAWS` 32 failing plans, `DEFAULT_MAX_ATTEMPTS` 8,
inside `DEFAULT_BUDGET_S` 240 s). Edgar (Nepožitek, after Ma et al. 2014) places rooms only where
they are valid (configuration spaces), lays loops out first, settles each chain by local moves
scored by an energy (overlap, distance between neighbours that should touch), and backtracks to
the last good partial layout instead of starting over. Many of steps 30-32's failures (corridors
crossing, a ceiling slot on a door, a 5.7 u floor neck, breaches too long to fit) are visible on
the 2D plan before any mesh exists: the user's earlier question, "are we not able to run
collision detection checks earlier for more confidence?"

## Requirements

1. **Measure first.** Over a fixed job set, where a generate's time goes (plan Draws and why each
   was refused, layout redraws inside a Draw, mesh build, decor, gate, retries), and which
   refusals and gate failures a check on the 2D plan could have caught. The projected saving
   decides the scope of requirements 2-4; if it is small, the step says so and stops.
2. **Check the plan.** A plan check runs inside the layout, before the mesh, for every failure
   class requirement 1 shows the plan can see. Measured against the gate: what it catches, and
   that it never refuses a plan the gate would pass without saying so.
3. **Repair locally.** A plan-check failure is repaired where it is (move one room, reroute one
   corridor, back up to the last good District) before a whole redraw.
4. **Score intended contacts.** Rooms that should touch (breach pairs, return links) are pulled
   together during placement, so short breaches fit (step 32 requirement 1's lever).
5. **Faster, and no worse.** Whole-generate median and max fall by the measured share; the
   gate sweeps pass at master's count or better; bands under 5% per key; walkability unchanged.
   Zones may change bytes (named, with counts).
