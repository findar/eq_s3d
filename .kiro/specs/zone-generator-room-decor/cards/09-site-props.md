# 9 — Site Props

Index entry: `tasks.md` task 9. Requirements 10.

## Goal
A Site's POIs are dressed by the same path: haybales and a cart at a farmstead, bedrolls and crates at a camp, offerings at a shrine. Every step 10 guarantee holds.

## Done when
- [ ] P10: Sites with Props pass the Footprint gate on 40 seeds at Normal and Dense; Site_Clear stays free; Decor `none` is step 10's bytes.
      → verify: `python -m pytest tests/test_site_props.py tests/test_site_builds.py -q`
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
Sites `none` and Decor `none` must each still give their old bytes. The Footprint gate (`analyzer/footprints.py`) already judges any placed model.

## Result

