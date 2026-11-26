# 7 — Flush or a drop, and one-way loops

Index entry: `tasks.md` task 7. Requirements 7, 8.

## Goal
Links between Districts meet flush by weight and otherwise enter the lower room partway up its wall as a drop; an intruder entered only by drops gets a flush way back from its far side.

## Done when
- [ ] `CorridorSpec.drop` (u, written only when set); geometry cuts the lower room's opening `drop` u up and keeps the wall below; decor and the map read it.
- [ ] Drops chosen by a salted draw at the flush weight, never above `MAX_DROP`, and only where the directed graph stays strongly connected; an all-drop intruder gets a flush return from the room farthest from the landing.
- [ ] Over seeds 2000–2039 with intrusion: drop share within 5 points of 1 - flush weight; every zone passes the task 2 gate; at least one all-drop intruder with its return loop, named.
- [ ] Zones without intrusion byte-identical.
- [ ] Quick tier; `-m gate` and full suite alone at close.

## Pitfalls
- lessons-learned "Same-axis room pairs need a Z-route" and the flush-opening rule: only the lower end drops; the upper end stays flush.
- Decor must not block the landing (`generators/decor/placement.py` clear zones).

## Result
