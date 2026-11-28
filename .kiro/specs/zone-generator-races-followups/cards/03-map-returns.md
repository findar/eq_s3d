# 3 — The map's returns are real

Index entry: `tasks.md` task 3. Requirement 2.

## Goal
The map's "return" mark comes from the layout's record of a drop's flush return, not a guess; District labels keep clear of the legend.

## Done when
- [ ] `CorridorSpec` carries a return flag (written only when set) from layout's `drop_returns`; zones without one byte-identical.
- [ ] `mapview` marks returns from it; a test on a zone with a drop-only entry and its return.
- [ ] No District label overlaps the legend on step 31's acceptance cases (a test of the label boxes).
- [ ] Map tests; quick tier; frontend build if web files change.

## Result
✔ f571fb9 · quick 3220 passed · map tests 13 passed · 3 zones without a return byte-identical to master
