# 4 — Cave run length

Index entry: `tasks.md` task 4. Requirement 5. Design "Run length".

## Goal
Bring cave rooms back toward stock tunnel length now that whole routes wind.

## Done when
- [x] At factors 3, 4, 5, 6, 7 and 9, over 40 cave graph builds each: the share of rough corridors
      that wind (a `path` or a winding leg) and the door-to-door median, in the commit body and in
      `archive.md` "Decisions".
- [x] `PROFILE_RUN_FACTOR["cave"]` set to the lowest factor with at least half winding.
- [x] `python -m pytest tests/test_cave_profile.py tests/test_winding.py -q` green; tests re-pinned
      only where the factor moved them, named in the commit.

## Result
✔ 58072f2 · 3111 passed · factor 4
