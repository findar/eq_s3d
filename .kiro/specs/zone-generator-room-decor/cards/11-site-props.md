# 11 — Site Props

Index entry: `tasks.md` task 11. Requirements 11.

## Goal
A Site's POIs are dressed from the catalogue by the same path, from the Site's RoomContext (task 18): haybales and a cart at a farmstead, crates at a camp, offerings at a shrine. Every step 10 guarantee holds.

## Done when
- [ ] P11: Sites with Props pass the Footprint gate on 40 seeds at Normal and Dense; Site_Clear stays free; Decor `none` is step 10's bytes.
      → verify: `python -m pytest tests/test_site_props.py tests/test_site_builds.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Sites `none` and Decor `none` must each still give their old bytes.

## Result

