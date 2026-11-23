# 9 — Measure what the eye sees, and stock room sizes

Index entry: `tasks.md` task 9. Requirements 7 and 8, design "First-look fixes".

## Goal
Measures that match the user's eye (a cave that still reads as a grid at grid score 0.076), and
stock targets for room sizes and cave placement.

## Done when
- [x] A measuring script reports, per build: edge bearing spread (share of edges within 10° of an
      axis), nearest-neighbour distance spread (clumping), door entry angle, room side / aspect /
      area spread. Run on seed 731402518 (Dungeon, Graph, 12 rooms, Cave, Moderate) and over
      seeds 2000–2039 for cave, fortress, outdoor dungeon and city; numbers in the commit body.
- [x] Stock: room side, aspect and area distributions per kind of zone (built dungeon, cave,
      city, outdoor) from stock zones in `F:\everquest_rof2`, with the zones and method named;
      cave placement measures from stock caves where rooms can be told apart, or why not.
- [x] Targets for tasks 10 and 11 in archive.md "Decisions", one or two lines each.

## Pitfalls
- Reuse `analyzer/` (style metrics, `inspect.py`) before writing a new reader; Classic–PoP
  zones are `.s3d`/WLD.
- Don't change generator code here.

## Result
✔ ba87985 · targets in archive.md decision 5
