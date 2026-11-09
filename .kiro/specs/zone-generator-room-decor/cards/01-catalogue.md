# 1 — Catalogue every stock model

Index entry: `tasks.md` task 1. Requirements 1.1, 1.2, 1.5.

## Goal
`scripts/prop_catalogue.py build`: read every actor in every `_obj*.s3d` of the install (293 archives, 4,408 names, design finding 0), dedupe by name and mesh hash (a different mesh under the same name is a variant `NAME@zone`), and write the measured fields of the design's "The catalogue" table to `rules/decor/catalogue.json`, with zones and placement counts from each zone's `objects.wld`. Metadata only: no mesh or texture bytes. Report what didn't parse.

## Done when
- [ ] The catalogue covers every actor in every `_obj*.s3d`; the script prints counts and failures.
      → verify: `python scripts/prop_catalogue.py build --eq-path F:\everquest_rof2`
- [ ] Finding 0 has the final counts: models, variants, animated, failures.

## Pitfalls
Reuse `site_survey`'s `_obj.s3d` loader and `measure_model`, and `room_feature_survey.placed_objects`. Keep the JSON stable (sorted keys, entries sorted) so rebuilds diff cleanly. No tests beyond what task 3 needs.

## Result

