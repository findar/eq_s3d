# 7 — Zone type, prompt words, controls, sidecar

Index entry: `tasks.md` task 7. Requirements 6.

## Goal
The `outdoor_dungeon` zone type (or Open question 4's alternative) is enabled and selectable from the prompt, controls, CLI and server; the sidecar records the Envelope, Rock_Cover, Entrances and Outdoor_Spawn.

## Done when
- [ ] Prompt words map to the zone type; room count, theme, race, tint, edges and trees work.
- [ ] Server and CLI accept it; the listing shows it enabled; the sidecar has the new block.
      → verify: `python -m pytest tests/test_outdoor_dungeon_controls.py -q`.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- `main.py` is a cross-branch hotspot.
- Hygiene tests pin the CLI options and web control ids; ask before widening to them.

## Result
