# 4 — Rules and profiles from the survey

Index entry: `tasks.md` task 4. Requirements 4. Design "Topology_Grammar".

## Goal
The v1 rules of the design table (`lengthen`, `passage`, `branch`, `side_wing`, `crossroads`, `loop`, `shortcut`, `finish`) as data, and the `linear`, `branching`, `looped` profiles, weighted so the grown graphs fall in the survey's bands.

## Done when
- [ ] Each rule is tested on a small graph: its replacement, its reattachment, and the rooms it adds.
- [ ] G4: over seeds and room counts 5–30, each profile's shape stats fall inside the design finding 3 bands; `linear` meets umbrella Req 22.2; for 14 rooms cycle ranks order `linear` ≤ `branching` < `looped`.
      → verify: `python -m pytest tests/test_topology_profiles.py -q`
- [ ] The weights and the bands they hit are in the commit body.

## Pitfalls
- Bands are over a seed sweep, not per graph: assert on means and p10–p90 over a fixed seed list, not on every single draw.
- Small n (1–4) can't show a shape; the start graph covers them (design).

## Result
