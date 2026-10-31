# 10 — `.txt` overlay preview script

Index entry: `tasks.md` task 10. Design Open question 1 (answered: this script
replaces the in-client check in 1b, see `archive.md`).

## Goal
`scripts/eqmap_preview.py <build dir>` draws `maps/<name>*.txt` back through
`map_to_world` on top of `<name>.map.svg` and writes `<name>.overlay.svg` next
to it, so a person can see that the EQ map lines land on the walls, north-up.

## Done when
- [ ] The script parses each layer with `parse_map_layer`, converts with
      `map_to_world`, and draws the lines in a contrasting colour over the SVG
      in the same frame. It reads only the build dir and writes one file there.
- [ ] Run on one dungeon build; the command and output path go in Result.
      → verify: `python scripts/eqmap_preview.py output/<zone_id>/v1`.

## Pitfalls
- It's a dev tool: add a test only if something in it is non-obvious.

## Result
