# 4 — The SQL script

Index entry: `tasks.md` task 4. Requirement 3. Design "SQL"; decisions 4, 5 and task 2's door
decisions.

## Goal
`generators/sqlexport.py` `export_sql(...)` as the design describes it. Task 6 calls it from the
export.

## Done when
- [ ] Build SQLite tables of the pinned columns, seeded with stock rows for `arena` and two other
      short names (with doors). Apply the script once, and twice. Each time `arena` has one row
      with our safe point and underworld and only our doors (one per Gate, at the locks); the
      other names' rows are untouched. With spawn cleanup the four spawn tables' `arena` rows go;
      without it those tables are never named. → verify: `python -m pytest tests/test_sqlexport.py -q`
- [ ] A non-finite value writes no script and names the field. The header is comment lines only
      and names the short name. One transaction wraps every change. Same command.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
SQLite and MySQL differ (`START TRANSACTION` vs `BEGIN`): write MySQL, and let the test adapt only
that keyword. Never open a database connection outside the test.

## Result
