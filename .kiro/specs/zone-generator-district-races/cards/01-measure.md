# 1 — Measure stock: race hall lengths, drops, layered links

Index entry: `tasks.md` task 1. Requirements 1.

## Goal
Know, from stock, whether races differ in hall length, how high stock drops run and how often passages drop, and how many links join a zone's built and cave parts, so later tasks set `MAX_DROP`, the flush weight, per-race/Purpose hall lengths and the intrusion link count from data.

## Done when
- [ ] `python scripts/stock_room_shapes.py --eq-path F:\everquest_rof2 --halls --by-race` prints door-to-door p10/p50/p90 in H per race group (the zone -> race table in the script, each name checked against the install).
- [ ] `python scripts/stock_drops.py --eq-path F:\everquest_rof2` prints drop heights (p50/p90/max) and the share of passage ends that drop, per kind, and the link count between built and cave parts in mixed zones.
- [ ] Decision in `archive.md`: `MAX_DROP`, the flush weight, which races/Purposes get a hall-length default (and its value, or "no signal"), the intrusion link count. Tables in the commit body.
- [ ] Quick tier green.

## Pitfalls
- The raster can't see passages narrower than its cells; say what it misses.
- No generator code.
- lessons-learned "Automated structural tests can pass while the 3D viewer shows it's broken": a measured drop may be a ledge you can't reach; spot-check three in the client data.

## Result
