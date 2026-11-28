# 1 — Measure stock outdoor zones: extent, host features, ways in

Index entry: `tasks.md` task 1. Requirement 1.

## Done when
- [x] `scripts/stock_outdoor_area.py` over the Classic-PoP outdoor zones in the RoF2 install (`.s3d`/WLD terrain; list the zones): walkable extent width, depth and aspect, p10/p50/p90/max, in u.
- [x] For outdoor zones holding a built or cave interior (name them: e.g. a ruin in a hill, a cave mouth, a sunken entrance): the host feature's size against the interior's footprint and depth, the entrance width, and the entrance kind (mouth, sinkhole, ravine, ruin stairs, cliff opening, well), with counts.
- [x] Defaults proposed for tasks 4-6 (Size range per Size word, host margin, Mouth width, which second entrance kind) as archive decision 2, each citing the measure or saying there was no signal.

## Pitfalls
- The analyzer reads both `.s3d` and `.eqg`; Classic-PoP is `.s3d` (lessons-learned, era boundary).

## Result
✔ f857d88 · 67 zones in the size bands, 331 interiors; defaults in archive decision 2
