# 16 — Measure race body heights and stock room sizes

Index entry: `tasks.md` task 16. Requirements 10.1. Design "Race-sized rooms". Added at the user's request (2026-11-04).

## Goal
`scripts/race_size_survey.py`: (1) each dungeon race's body height from its character model in the client files (`F:\everquest_rof2`: the `global*_chr.s3d` and per-zone `_chr` archives, and `.eqg` models), for the default human, goblin, froglok, kobold, lizardman, gnoll, sarnak, troll, ogre, giant and dragon; (2) room heights and footprints in stock zones against the race that lives there (e.g. Crushbone/orcs, Blackburrow/gnolls, Runnyeye/goblins, Kael Drakkel/giants, Nagafen's lair and Veeshan's Peak/dragons, Befallen/humans), to set the band multiples. Finding 8 holds both tables and the proposed bands.

## Done when
- [x] The script prints each race's measured body height (model, how measured: e.g. the standing mesh's Z extent at its default size), naming any race it couldn't find and what it fell back to.
      → verify: `python scripts/race_size_survey.py --eq-path F:\everquest_rof2`
- [x] For the listed zones: room (chamber) heights and sides, p10/p50/p90, divided by the resident race's height; zones whose rooms don't separate cleanly are named and left out.
- [x] Design finding 8: the race table, the room table, and proposed band multiples (height min/max, footprint min/max, as multiples of H) that hold across the zones kept.

## Pitfalls
- Character meshes are skinned: measure the default pose's vertex bounds, at the race's default size (EQ scales some races).
- Reuse the step 6 and 7 surveys' WLD walk for rooms (`scripts/dungeon_topology_survey.py`, `scripts/dungeon_vertical_survey.py`).
- No tests: a script that writes a finding.

## Result
✔ 6c8268f · survey
