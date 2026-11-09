# 3 — Auto-tags and the review sheet

Index entry: `tasks.md` task 3. Requirements 3.

## Goal
The auto-tagger proposes every Tag of every entry (Category, kind, Mount, Set, era, collision, suits, `use`) from name, geometry and observed placements, each with a confidence. `generators/decor/catalogue.py` loads the catalogue and `rules/decor/tags.toml` (reviewed Tags, keyed by entry, winning) strictly. `sheet` writes a local HTML contact sheet: textured top and side thumbnails, measures, placements and Tags, grouped by proposed kind, lowest confidence first, and the line to paste into `tags.toml` to correct an entry.

## Done when
- [ ] P3: rebuilding the catalogue keeps every reviewed Tag; a bad `tags.toml` value is named by entry and field.
      → verify: `python -m pytest tests/test_prop_catalogue.py -q`
- [ ] The sheet builds for the models finding 1's zones place (581 names).
      → verify: `python scripts/prop_catalogue.py sheet --eq-path F:\everquest_rof2 --out output/prop_sheet`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
The sheet shows the client's art: write it under `output/`, never commit it or publish it. Name patterns are rough (FAYBAR1, TABAC); placements are the strongest evidence for Mount and suits.

## Result

