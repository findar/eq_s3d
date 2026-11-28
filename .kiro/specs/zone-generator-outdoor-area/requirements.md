# Requirements — zone-generator-outdoor-area (roadmap step 35)

> **STATUS: roadmap step 35, ready.** Drafted 2026-11-28 at master `152e956`. The user set the working order,
> "to be clear, we should be working top down. area map > dungeon > rooms > decor", then "i mean one zones area, so like a wilderness or outdoor dungeon. we should be generating the external area before anything we attach to it", and said "Yes, plan it" to taking on the area layer's open items after steps 32
> and 34. Task index: `tasks.md` (card format). Decisions: `archive.md`. Pillars: P-7 Engaging (wilderness,
> outdoor dungeon), P-2 Traversable, P-8 World ([working order](../../../docs/pillars/README.md#working-order)).

## Introduction

A wilderness is always 2400 u square and an outdoor dungeon's host 1200 u
([P-7-3](../../../docs/pillars/P-7-engaging/OPEN.md#p-7-3)). Every wilderness gets a lava patch whatever its theme
([P-5-6](../../../docs/pillars/P-5-look-and-feel/OPEN.md#p-5-6)). The outdoor dungeon is entered only by a Tunnel one terrain
cell wide into its hill ([P-7-4](../../../docs/pillars/P-7-engaging/OPEN.md#p-7-4)). Its host hill is sized without knowing what
it will hold, so giant and dragon dungeons drop rooms and few reach three Levels
([P-7-20](../../../docs/pillars/P-7-engaging/OPEN.md#p-7-20), [P-7-19](../../../docs/pillars/P-7-engaging/OPEN.md#p-7-19)). Some helpers
re-derive the landscape instead of reading it once ([P-8-4](../../../docs/pillars/P-8-world/OPEN.md#p-8-4)), and the slowest
outdoor-dungeon plans take up to 223 s ([P-9-8](../../../docs/pillars/P-9-engineering/OPEN.md#p-9-8)).

The area is generated first and what attaches to it is fitted after: the area's plan may read what will
attach (a race, a Verticality, a room count) to size itself, but the dungeon never reshapes the area after.

## Requirements

1. **Measure first.** Stock Classic-PoP outdoor zones give: zone extent (width, depth, aspect), and for zones
   holding a built or cave interior, how big its host feature is against the interior and how the interior is
   entered (mouth width, entrance kinds). Each later default cites this measure.
2. **Area size.** A wilderness's extent comes from the plan's Size within stock's range (task 1), random when
   unset, and may be non-square; an outdoor dungeon's whole zone likewise. Size words and the Controls set it.
   A plan that names no Size keeps today's sizes only if the measure says so.
3. **Area features by theme.** Interior ground features (the lava patch first) follow the plan's theme and
   are off unless the theme calls for them.
4. **The area is read once.** Every outdoor-dungeon step reads the one landscape the area built; none
   re-derives it. Byte-identical.
5. **A host sized to what it holds.** The host feature (the hill) is sized from the plan before the dungeon is
   laid in it, so giant and dragon dungeons keep their rooms and a Dramatic one can reach three Levels; the
   dungeon is then fitted inside, never the area reshaped after.
6. **Ways in.** The entrance is a wide, flaring Mouth by default (width from task 1), and at least one other
   kind stock uses (from sinkhole, ravine, ruin stairs, cliff opening, well; task 1 picks by frequency) can be
   drawn; every kind walkable both ways.
7. **Gate, bands and time.** Wilderness and outdoor-dungeon gate sweeps at master's count or better; bands
   under 5% per key; outdoor-dungeon whole generate within the ~5 min budget, with the 223 s plan named
   (fixed, or the reason).
